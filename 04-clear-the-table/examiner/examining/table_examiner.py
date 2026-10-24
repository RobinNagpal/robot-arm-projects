"""The examiner: it builds a table, hands the solution an attempt at it, and marks the table at the end.

``solution_contract.py`` says what a solution is given. This file is the other side of that
contract: the simulated UR5e, MoveIt, the wrist camera and the clock, wrapped so that a
solution can reach them only through ``TableAttempt``, ``Arm`` and ``WristCamera``.

**What the examiner keeps to itself.** The table number, which is also the seed that drew
the glasses; the simulator, which knows where every glass really is; and the marks. The
solution is given an arm and a clock, and nothing else.

**How an attempt ends.** The solution calls ``declare_finished``, or a glass goes over, or
the time runs out. The time runs out in three ways: fewer than ``FEWEST_ARM_SECONDS_TO_ACT``
arm seconds are left; a move does not fit in the time left, and so is refused rather than
cut short; or the solution has asked for ``MOST_PUSHES_PER_TABLE`` pushes. The last is needed
because a push MoveIt refuses costs no arm time, so without it a solution that keeps asking
for impossible pushes would never be stopped by the clock. Once an attempt has ended, the
next call to the arm or the camera raises ``TableAttemptOver``.

**What costs arm time.** Every motion the arm really makes, and every picture, because
the arm must stand still while one is taken. Planning is not arm time, so a refused move
costs nothing. A push stops after the motion in which a glass went over, and the
motions it did not make are not charged.
"""

from __future__ import annotations

import contextlib
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from work_cell.table.layout import TABLE_TOP_Z

from examiner.examining.one_table_cell import VIEW_WAYPOINTS, OneTableCell, viewing_joint_angles
from examiner.examining.solution_catalogue import SolutionChoice
from examiner.examining.solution_contract import (
    FINISHED,
    GLASS_OVER,
    OUT_OF_TIME,
    REACHED,
    REFUSED,
    RUNNING,
    STOPPED,
    AttemptState,
    GlassBox,
    HandPose,
    MoveItSettings,
    MoveResult,
    PushRequest,
    PushResult,
    Solution,
    TableAttemptOver,
    TableResult,
    WristPicture,
)
from examiner.motion.moveit_connection import MoveItConnection, flange_goal_for_fingertips
from examiner.motion.push_motions import moveit_collision_boxes
from examiner.simulation import wrist_camera
from examiner.simulation.arm_and_table_simulator import SETTLE_SECONDS_AFTER_MOTION

# The arm time one whole list of tables is given, the same fifteen minutes as problem 4's.
ARM_SECONDS_FOR_TABLE_LIST = 15 * 60.0

# Under this many arm seconds left, no push can be made: the trip to look alone costs more.
FEWEST_ARM_SECONDS_TO_ACT = 8.0

# The most pushes one table may be asked for, refused ones included.
MOST_PUSHES_PER_TABLE = 14

# What a picture costs: the arm stands still for as long as it is given to settle after a motion.
ARM_SECONDS_PER_PICTURE = SETTLE_SECONDS_AFTER_MOTION

# How long MoveIt may search for a free move, and how many times it starts again.
MOVEIT_PLANNING_SECONDS, MOVEIT_PLANNING_ATTEMPTS = 5.0, 3


def hand_pose_of_waypoint(waypoint) -> HandPose:
    return HandPose(waypoint.x, waypoint.y, waypoint.z, waypoint.heading)


def _poses_match(one, other) -> bool:
    turn = abs((one.heading - other.heading + math.pi) % (2 * math.pi) - math.pi)
    return math.dist((one.x, one.y, one.z), (other.x, other.y, other.z)) < 0.02 and turn < 0.05


@dataclass
class ArmActivityCounts:
    """What the arm did over a list of tables, for diagnosis and not for the mark.

    It counts the tables marked, the pushes made and refused, the pictures taken and the trips
    to a viewing place, and it keeps how often each kind of reason for a refusal came up, so
    that a run can say why MoveIt turned its pushes down.
    """

    tables_marked: int = 0
    pushes_made: int = 0
    pushes_refused: int = 0
    refusal_reasons: dict = field(
        default_factory=dict
    )  # the part of each reason before its colon, and how often
    moveit_planning_seconds: float = 0.0
    pictures_taken: int = 0
    trips_to_look: int = 0

    def count_refusal(self, reason: str) -> None:
        kind = reason.split(":")[0]
        self.refusal_reasons[kind] = self.refusal_reasons.get(kind, 0) + 1


class _AttemptClock:
    def __init__(self, cell: OneTableCell, arm_seconds_given: float) -> None:
        self._cell, self._arm_seconds_given = cell, arm_seconds_given

    @property
    def arm_seconds_used(self) -> float:
        return self._cell.arm_seconds

    @property
    def arm_seconds_left(self) -> float:
        return self._arm_seconds_given - self._cell.arm_seconds


class _AttemptWristCamera:
    def __init__(self, attempt: SimulatedTableAttempt) -> None:
        self._attempt = attempt
        self.height, self.width = wrist_camera.WRIST_VIEW_SIZE
        self.focal_length = (self.height / 2) / math.tan(math.radians(wrist_camera.WRIST_VIEW_FOVY_DEG) / 2)

    def take_picture(self) -> WristPicture:
        attempt = self._attempt
        attempt._raise_if_over()
        simulator = attempt._cell.simulator
        hand = simulator.fingertips_waypoint()
        image = attempt._cell.wrist_camera.render_picture(hand)
        simulator.arm_seconds += ARM_SECONDS_PER_PICTURE
        attempt._arm_activity.pictures_taken += 1
        attempt._end_if_a_glass_fell_or_the_time_ran_out()
        return WristPicture(image, hand_pose_of_waypoint(hand), attempt.clock.arm_seconds_used)


class _AttemptArm:
    def __init__(self, attempt: SimulatedTableAttempt) -> None:
        self._attempt = attempt
        self.wrist_camera = _AttemptWristCamera(attempt)

    def hand_pose(self) -> HandPose:
        return hand_pose_of_waypoint(self._attempt._cell.simulator.fingertips_waypoint())

    def move_hand_to(
        self, hand_pose: HandPose, settings: MoveItSettings, obstacle_boxes: list[GlassBox]
    ) -> MoveResult:
        attempt = self._attempt
        attempt._raise_if_over()
        cell = attempt._cell
        simulator, moveit = cell.simulator, cell.moveit
        moveit.set_collision_boxes(moveit_collision_boxes(list(obstacle_boxes), settings.padding))
        # The two viewing poses are reached in postures chosen once and kept, because
        # some postures of the same pose put the forearm over the glasses.
        viewing_place = next(
            (k for k, view in enumerate(VIEW_WAYPOINTS) if _poses_match(hand_pose, view)), None
        )
        motion = moveit.plan_free_move(
            simulator.joint_angles(),
            None
            if viewing_place is not None
            else flange_goal_for_fingertips(
                hand_pose.x, hand_pose.y, TABLE_TOP_Z + hand_pose.z, hand_pose.heading
            ),
            velocity_scaling=settings.approach_speed,
            acceleration_scaling=settings.approach_speed,
            planning_time_seconds=MOVEIT_PLANNING_SECONDS,
            planning_attempts=MOVEIT_PLANNING_ATTEMPTS,
            goal_joint_angles=None if viewing_place is None else viewing_joint_angles()[viewing_place],
        )
        if not motion.planned:
            reason = f"no way to that pose: {motion.refusal_reason}"
            attempt._arm_activity.count_refusal("move: " + reason)
            return MoveResult(REFUSED, reason, self.hand_pose(), 0.0)
        if motion.duration_seconds > attempt.clock.arm_seconds_left:
            attempt._end_attempt(OUT_OF_TIME)
            return MoveResult(REFUSED, "the move does not fit in the time left", self.hand_pose(), 0.0)
        trajectory = simulator.run_joint_trajectory(motion.times, motion.joint_angles)
        attempt._arm_activity.trips_to_look += 1
        attempt._end_if_a_glass_fell_or_the_time_ran_out()
        return MoveResult(REACHED, "", self.hand_pose(), trajectory.arm_seconds)

    def push_glass(self, request: PushRequest, glass_boxes: list[GlassBox]) -> PushResult:
        attempt = self._attempt
        attempt._raise_if_over()
        cell = attempt._cell
        attempt._pushes_requested += 1
        pusher_result = cell.pusher.plan_and_make_push(
            list(glass_boxes),
            request,
            attempt.clock.arm_seconds_left,
            stop_once_a_glass_topples=True,
        )
        if not pusher_result.made:
            attempt._arm_activity.pushes_refused += 1
            attempt._arm_activity.count_refusal(pusher_result.refusal_reason)
            if (
                "are left" in pusher_result.refusal_reason
                or attempt._pushes_requested >= MOST_PUSHES_PER_TABLE
            ):
                attempt._end_attempt(OUT_OF_TIME)
            return PushResult(REFUSED, pusher_result.refusal_reason, self.hand_pose(), 0.0)
        attempt._arm_activity.pushes_made += 1
        attempt._end_if_a_glass_fell_or_the_time_ran_out()
        return PushResult(
            STOPPED if pusher_result.stopped_early else REACHED,
            "a glass went over" if pusher_result.stopped_early else "",
            self.hand_pose(),
            pusher_result.arm_seconds,
            tuple(stage[0] for stage in pusher_result.motion_stages),
            pusher_result.hand_touched_a_glass,
        )


class SimulatedTableAttempt:
    """One attempt at one table. The solution sees it only as ``solution_contract.TableAttempt``."""

    def __init__(
        self, table_number: int, cell: OneTableCell, arm_seconds_given: float, arm_activity: ArmActivityCounts
    ) -> None:
        self._table_number, self._cell, self._arm_activity = table_number, cell, arm_activity
        self._state: AttemptState = RUNNING
        self._finish_reason = ""
        self._pushes_requested = 0
        self._wall_clock_at_start = time.perf_counter()
        self._moveit_planning_seconds_at_start = cell.moveit.planning_seconds
        self.clock = _AttemptClock(cell, arm_seconds_given)
        self.arm = _AttemptArm(self)
        if self.clock.arm_seconds_left < FEWEST_ARM_SECONDS_TO_ACT:
            self._state = OUT_OF_TIME

    @property
    def state(self) -> AttemptState:
        return self._state

    def declare_finished(self, reason: str) -> None:
        if self._state == RUNNING:
            self._state, self._finish_reason = FINISHED, reason

    def _raise_if_over(self) -> None:
        if self._state != RUNNING:
            raise TableAttemptOver(self._state)

    def _end_attempt(self, state: AttemptState) -> None:
        if self._state == RUNNING:
            self._state = state

    def _end_if_a_glass_fell_or_the_time_ran_out(self) -> None:
        if self._cell.count_toppled_glasses():
            self._end_attempt(GLASS_OVER)
        elif (
            self.clock.arm_seconds_left < FEWEST_ARM_SECONDS_TO_ACT
            or self._pushes_requested >= MOST_PUSHES_PER_TABLE
        ):
            self._end_attempt(OUT_OF_TIME)


class SimulatedExaminer:
    """Runs solutions on tables in the simulated cell, from one budget of arm time.

    ``arm_seconds_left`` is shared by every table this examiner starts, so a solution that is
    slow on one table has less for the next, as on a real list of tables.

    A tool that wants to watch a table, such as a film or a record, does the three steps
    itself: ``start_attempt``, then it attaches its watchers to ``cell_behind_attempt``, and
    then ``run_solution_on_attempt``. ``run_solution_on_table`` does the first and the last
    step for everyone else.
    """

    def __init__(
        self,
        moveit: MoveItConnection,
        arm_seconds_given: float = ARM_SECONDS_FOR_TABLE_LIST,
        arm_activity: ArmActivityCounts | None = None,
    ) -> None:
        self.moveit, self.arm_seconds_left = moveit, arm_seconds_given
        self.arm_activity = ArmActivityCounts() if arm_activity is None else arm_activity

    def make_cell_for_table(self, table_number: int) -> OneTableCell:
        """The simulated cell with this table's glasses on it. The tests replace it with a fake cell."""
        return OneTableCell(table_number, self.moveit)

    def start_attempt(self, table_number: int) -> SimulatedTableAttempt:
        cell = self.make_cell_for_table(table_number)
        return SimulatedTableAttempt(table_number, cell, self.arm_seconds_left, self.arm_activity)

    @staticmethod
    def cell_behind_attempt(attempt: SimulatedTableAttempt) -> OneTableCell:
        """The simulator behind an attempt, for the examiner's own tools, such as films and records.

        A solution is never given it.
        """
        return attempt._cell

    def mark_attempt(self, attempt: SimulatedTableAttempt) -> TableResult:
        cell = attempt._cell
        planning_seconds = cell.moveit.planning_seconds - attempt._moveit_planning_seconds_at_start
        wall_seconds = time.perf_counter() - attempt._wall_clock_at_start
        thinking_seconds = max(0.0, wall_seconds - cell.simulator.seconds - planning_seconds)
        state = attempt.state if attempt.state != RUNNING else FINISHED
        self.arm_seconds_left -= cell.arm_seconds
        self.arm_activity.tables_marked += 1
        self.arm_activity.moveit_planning_seconds += planning_seconds
        cell.close()
        return TableResult(
            table_number=attempt._table_number,
            glass_count=cell.glass_count(),
            pickable_at_start=cell.pickable_at_start,
            pickable_at_end=cell.pickable_glass_count(),
            glasses_toppled=cell.count_toppled_glasses(),
            ended_by=state,
            arm_seconds=cell.arm_seconds,
            pushes_requested=attempt._pushes_requested,
            thinking_seconds=thinking_seconds,
            finish_reason=attempt._finish_reason,
        )

    def run_solution_on_table(self, solution: Solution, table_number: int) -> TableResult:
        """Start the table, let the solution clear it, and mark it."""
        return self.run_solution_on_attempt(solution, self.start_attempt(table_number))

    def run_solution_on_attempt(self, solution: Solution, attempt: SimulatedTableAttempt) -> TableResult:
        """Let the solution clear a table that has already been started, and mark it."""
        try:
            with contextlib.suppress(
                TableAttemptOver
            ):  # the attempt ended, which is one of the ways a table ends
                solution.clear_table(attempt)
        except BaseException:
            attempt._cell.close()
            raise
        if attempt.state == RUNNING:
            attempt.declare_finished("the solution returned without saying it had finished")
        return self.mark_attempt(attempt)


# ------------------------------------------------------------------ a list of tables


def run_solution_down_table_list(
    solution: Solution,
    table_numbers: Sequence[int],
    moveit: MoveItConnection,
    arm_seconds_given: float = ARM_SECONDS_FOR_TABLE_LIST,
    arm_activity: ArmActivityCounts | None = None,
    print_each_table: bool = False,
) -> list[TableResult]:
    """Run one solution on each table of the list in turn, until the list or the arm time runs out.

    Every table draws on the same arm time, so the solution gets as far down the list as its
    speed allows. A table the clock ended before the arm moved on it is left out of the results,
    because the solution never really got it.
    """
    examiner = SimulatedExaminer(moveit, arm_seconds_given, arm_activity)
    results = []
    for table_number in table_numbers:
        if examiner.arm_seconds_left < FEWEST_ARM_SECONDS_TO_ACT:
            break
        result = examiner.run_solution_on_table(solution, table_number)
        if result.ended_by == OUT_OF_TIME and result.arm_seconds == 0.0:
            continue  # the clock ended this table before the arm did anything on it
        results.append(result)
        if print_each_table:
            print(
                f"table {table_number}: "
                f"{result.pickable_at_start}->{result.pickable_at_end}/{result.glass_count} "
                f"pickable, {result.arm_seconds:.0f} arm s, {result.pushes_requested} pushes requested, "
                f"{result.ended_by}, toppled {result.glasses_toppled}",
                flush=True,
            )
    return results


# ---------------------------------------------------------------------- the marks
#
# The marks are problem 4's scorecard, so a number from here is read on the same scale as
# a number from the top-down cell. The scorecard reads its own shape of result, so each
# table is written into that shape before it is marked.


def as_scored_table(result: TableResult):
    """The table as the scorecard marks it."""
    from examiner.examining import table_scoring

    ended = {
        FINISHED: table_scoring.SAID_DONE,
        OUT_OF_TIME: table_scoring.RAN_OUT_OF_TIME,
        GLASS_OVER: table_scoring.GLASS_OVER,
    }
    return table_scoring.ScoredTable(
        seed=result.table_number,
        glasses=result.glass_count,
        pickable_at_start=result.pickable_at_start,
        pickable_at_end=result.pickable_at_end,
        toppled=result.glasses_toppled,
        ended_by=ended[result.ended_by],
        arm_seconds=result.arm_seconds,
        thinking_seconds=result.thinking_seconds,
        pushes_requested=result.pushes_requested,
    )


def score_solution_on_tables(
    solution_choice: SolutionChoice,
    moveit: MoveItConnection,
    first_table: int,
    table_count: int,
    runs: int = 1,
    arm_seconds_given: float = ARM_SECONDS_FOR_TABLE_LIST,
    print_progress: bool = True,
) -> tuple[dict, ArmActivityCounts, list[list[dict]]]:
    """Run the chosen solution down the list ``runs`` times and score every run.

    Every run is given a newly built solution, so that nothing one run learned about its
    tables is carried into the next.

    It returns problem 4's scorecard summary with the spread across the runs, the counts of
    what the arm did, and every table's own row from every run.
    """
    from examiner.examining.table_scoring import ScorecardsOverRuns

    scorecards = ScorecardsOverRuns()
    arm_activity = ArmActivityCounts()
    rows_per_run: list[list[dict]] = []
    table_numbers = list(range(first_table, first_table + table_count))
    for run_index in range(runs):
        scorecard = scorecards.new_scorecard()
        started = time.perf_counter()
        results = run_solution_down_table_list(
            solution_choice.build_new_solution(),
            table_numbers,
            moveit,
            arm_seconds_given,
            arm_activity,
            print_progress,
        )
        for result in results:
            scorecard.add_table(as_scored_table(result))
        rows_per_run.append(scorecard.rows_per_table)
        if print_progress:
            print(
                f"run {run_index + 1}/{runs}: {len(results)} tables, "
                f"{sum(r.arm_seconds for r in results):.0f} arm s, "
                f"{time.perf_counter() - started:.0f} s of laptop time",
                flush=True,
            )
    return scorecards.summary(), arm_activity, rows_per_run


def one_line_summary(summary: dict) -> str:
    """The numbers a run is read by, on one line; with the spread when there are several runs."""
    spread = summary["spread"]

    def middle(key: str) -> str:
        entry = spread[key]
        if summary["runs"] > 1:
            return f"{entry['median']:g} (sd {entry['sd']:.2g})"
        return f"{entry['median']:g}"

    return (
        f"tables {middle('tables_attempted')}, glasses {middle('glasses')}, "
        f"pickable {middle('glasses_end.pickable_at_start')} -> {middle('glasses_end.pickable')} "
        f"(share {middle('glasses_end.pickable_share')}), broken {middle('glasses_end.broken')}, "
        f"separated {middle('outcome.separated')}, failed {middle('outcome.failed')}, "
        f"unfinished {middle('outcome.unfinished')}, "
        f"said done {middle('ended_by.said_done')}, arm s {middle('arm_seconds.total')}"
    )
