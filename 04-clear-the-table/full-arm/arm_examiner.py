"""The examiner: it builds a table, hands the solution a run, and marks the table when the run ends.

``arm_contract.py`` says what a solution is given. This file is the other side of that
contract: the simulated UR5e, MoveIt, the wrist camera and the clock, wrapped so that a
solution can reach them only through ``Run``, ``Arm`` and ``Camera``.

**What the examiner keeps to itself.** The table number, which is also the seed that drew
the glasses; the simulator, which knows where every glass really is; and the marks. The
solution is given an arm and a clock, and nothing else.

**How a run ends.** The solution calls ``finish``, or a glass goes over, or the time runs
out. The time runs out in three ways: fewer than ``LEAST_ACTION`` arm seconds are left;
a move does not fit in the time left, and so is refused rather than cut short; or the
solution has asked for ``MOST_PUSHES`` pushes, or has had that many paths refused. The
last is needed because a push or a path MoveIt refuses costs no arm time, so without it
a solution that keeps asking for impossible ones would never be stopped by the clock.
Once a run has ended, the next call to the arm or the camera raises ``RunOver``.

**What costs arm time.** Every motion the arm really makes, and every picture, because
the arm must stand still while one is taken. Planning is not arm time, so a refused move
costs nothing. A push stops after the motion in which a glass went over, and the
motions it did not make are not charged.
"""

from __future__ import annotations

import contextlib
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import arm_camera  # noqa: F401  (mounts the wrist camera before anything renders)
from arm_contract import (
    FINISHED,
    GLASS_OVER,
    OUT_OF_TIME,
    REACHED,
    REFUSED,
    RUNNING,
    STOPPED,
    Box,
    Frame,
    Leg,
    Moved,
    Pose,
    Pushed,
    Request,
    RunOver,
    RunState,
    Settings,
    Solution,
    TableResult,
)
from arm_simulator import HOLD_AFTER
from cell import VIEWS, ArmCell, view_joint_sets
from moveit_link import MoveItLink, flange_goal
from pusher import TRAVEL, scene_boxes
from work_cell.table.layout import TABLE_TOP_Z

import wrist

# The arm time one whole list of tables is given, the same fifteen minutes as problem 4's.
ARM_BUDGET = 15 * 60.0

# Under this many arm seconds left, no push can be made: the trip to look alone costs more.
LEAST_ACTION = 8.0

# The most pushes one table may be asked for, refused ones included.
MOST_PUSHES = 14

# What a picture costs: the arm stands still for as long as it is given to settle after a motion.
CAPTURE_SECONDS = HOLD_AFTER

# How long MoveIt may search for a free move, and how many times it starts again.
PLANNING_TIME, PLANNING_ATTEMPTS = 5.0, 3


def pose_of(waypoint) -> Pose:
    return Pose(waypoint.x, waypoint.y, waypoint.z, waypoint.heading)


def _same_pose(a, b) -> bool:
    turn = abs((a.heading - b.heading + math.pi) % (2 * math.pi) - math.pi)
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) < 0.02 and turn < 0.05


@dataclass
class Tally:
    """Diagnosis that is not part of the mark: how often MoveIt refused, and why."""

    tables: int = 0
    pushes: int = 0
    refusals: int = 0
    refused_because: dict = field(default_factory=dict)
    planning_seconds: float = 0.0
    pictures: int = 0
    trips: int = 0

    def refused(self, why: str) -> None:
        key = why.split(":")[0]
        self.refused_because[key] = self.refused_because.get(key, 0) + 1


class _Clock:
    def __init__(self, cell: ArmCell, budget: float) -> None:
        self._cell, self._budget = cell, budget

    @property
    def used(self) -> float:
        return self._cell.arm_seconds

    @property
    def left(self) -> float:
        return self._budget - self._cell.arm_seconds


class _Camera:
    def __init__(self, run: TableRun) -> None:
        self._run = run
        self.height, self.width = wrist.WRIST_VIEW_SIZE
        self.focal_length = (self.height / 2) / math.tan(math.radians(wrist.WRIST_VIEW_FOVY_DEG) / 2)

    def capture(self) -> Frame:
        run = self._run
        run._check()
        simulator = run._cell.simulator
        hand = simulator.tcp()
        image = run._cell.camera.view(hand)
        simulator.arm_seconds += CAPTURE_SECONDS
        run._tally.pictures += 1
        run._after_action()
        return Frame(image, pose_of(hand), run.clock.used)


class _Arm:
    def __init__(self, run: TableRun) -> None:
        self._run = run
        self.camera = _Camera(run)

    def pose(self) -> Pose:
        return pose_of(self._run._cell.simulator.tcp())

    def move_to(self, pose: Pose, settings: Settings, scene: list[Box]) -> Moved:
        run = self._run
        run._check()
        cell = run._cell
        simulator, link = cell.simulator, cell.link
        link.scene(scene_boxes(list(scene), settings.padding))
        # The two viewing poses are reached in postures chosen once and kept, because
        # some postures of the same pose put the forearm over the glasses.
        named = next((k for k, view in enumerate(VIEWS) if _same_pose(pose, view)), None)
        motion = link.plan(
            simulator.joints(),
            None if named is not None else flange_goal(pose.x, pose.y, TABLE_TOP_Z + pose.z, pose.heading),
            vel=settings.approach_speed,
            acc=settings.approach_speed,
            planning_time=PLANNING_TIME,
            attempts=PLANNING_ATTEMPTS,
            goal_joints=None if named is None else view_joint_sets()[named],
        )
        if not motion.ok:
            why = f"no way to that pose: {motion.why}"
            run._tally.refused("move: " + why)
            return Moved(REFUSED, why, self.pose(), 0.0)
        if motion.seconds > run.clock.left:
            run._end(OUT_OF_TIME)
            return Moved(REFUSED, "the move does not fit in the time left", self.pose(), 0.0)
        ran = simulator.run(motion.times, motion.joints)
        run._tally.trips += 1
        run._after_action()
        return Moved(REACHED, "", self.pose(), ran.seconds)

    def follow(self, path: list[Leg], scene: list[Box], glass: int | None, settings: Settings) -> Pushed:
        run = self._run
        run._check()
        cell = run._cell
        # A path that comes down below travel height can move a glass, so it is
        # counted as a push. A path that stays up there only moves the arm.
        pushing = any(leg.z < TRAVEL - 1e-6 for leg in path)
        result = cell.pusher.follow(
            list(scene), list(path), glass, settings, run.clock.left, stop_when=lambda: cell.toppled() > 0
        )
        if not result.ok:
            run._paths += 1
            run._refused_paths += 1
            run._tally.refusals += 1
            run._tally.refused(result.why)
            if "are left" in result.why or run._refused_paths >= MOST_PUSHES:
                run._end(OUT_OF_TIME)
            return Pushed(REFUSED, result.why, self.pose(), 0.0)
        if pushing:
            run._paths += 1
            run._tally.pushes += 1
        else:
            run._tally.trips += 1
        run._after_action()
        return Pushed(
            STOPPED if result.stopped else REACHED,
            "a glass went over" if result.stopped else "",
            self.pose(),
            result.arm_seconds,
            tuple(stage[0] for stage in result.stages),
            result.touched,
        )

    def push(self, request: Request, scene: list[Box]) -> Pushed:
        run = self._run
        run._check()
        cell = run._cell
        run._pushes += 1
        boxes = list(scene)
        result = cell.pusher.push(boxes, request, run.clock.left, stop_when=lambda: cell.toppled() > 0)
        if not result.ok:
            run._tally.refusals += 1
            run._tally.refused(result.why)
            if "are left" in result.why or run._pushes >= MOST_PUSHES:
                run._end(OUT_OF_TIME)
            return Pushed(REFUSED, result.why, self.pose(), 0.0)
        run._tally.pushes += 1
        run._after_action()
        return Pushed(
            STOPPED if result.stopped else REACHED,
            "a glass went over" if result.stopped else "",
            self.pose(),
            result.arm_seconds,
            tuple(stage[0] for stage in result.stages),
            result.touched,
        )


class TableRun:
    """One attempt at one table. The solution sees it only as ``arm_contract.Run``."""

    def __init__(self, table: int, cell: ArmCell, budget: float, tally: Tally) -> None:
        self._table, self._cell, self._tally = table, cell, tally
        self._state: RunState = RUNNING
        self._why = ""
        self._pushes = 0
        # Paths, for the solutions that answer with one: how many came down to
        # push or were refused, and how many of them MoveIt refused.
        self._paths = 0
        self._refused_paths = 0
        self._started = time.perf_counter()
        self._planning_before = cell.link.planning_seconds
        self.clock = _Clock(cell, budget)
        self.arm = _Arm(self)
        if self.clock.left < LEAST_ACTION:
            self._state = OUT_OF_TIME

    @property
    def state(self) -> RunState:
        return self._state

    def finish(self, why: str) -> None:
        if self._state == RUNNING:
            self._state, self._why = FINISHED, why

    def _check(self) -> None:
        if self._state != RUNNING:
            raise RunOver(self._state)

    def _end(self, state: RunState) -> None:
        if self._state == RUNNING:
            self._state = state

    def _after_action(self) -> None:
        if self._cell.toppled():
            self._end(GLASS_OVER)
        elif self.clock.left < LEAST_ACTION or self._pushes >= MOST_PUSHES:
            self._end(OUT_OF_TIME)


class SimExaminer:
    """Runs solutions on tables in the simulated cell, from one budget of arm time.

    ``budget`` is shared by every table this examiner starts, so a solution that is slow on
    one table has less for the next, as on a real list of tables.
    """

    def __init__(
        self,
        link: MoveItLink,
        budget: float = ARM_BUDGET,
        tally: Tally | None = None,
        make_cell: Callable[[int, MoveItLink], ArmCell] = ArmCell,
    ) -> None:
        self.link, self.left = link, budget
        self.tally = Tally() if tally is None else tally
        self.make_cell = make_cell

    def start(self, table: int) -> TableRun:
        return TableRun(table, self.make_cell(table, self.link), self.left, self.tally)

    @staticmethod
    def cell_of(run: TableRun) -> ArmCell:
        """The simulator behind a run, for the examiner's own tools: films and records, never a solution."""
        return run._cell

    def result(self, run: TableRun) -> TableResult:
        cell = run._cell
        planning = cell.link.planning_seconds - run._planning_before
        thinking = max(0.0, (time.perf_counter() - run._started) - cell.simulator.seconds - planning)
        state = run.state if run.state != RUNNING else FINISHED
        self.left -= cell.arm_seconds
        self.tally.tables += 1
        self.tally.planning_seconds += planning
        cell.close()
        return TableResult(
            table=run._table,
            glasses=cell.glasses(),
            separated_at_start=cell.pickable_at_start,
            separated_at_end=cell.pickable(),
            fell_over=cell.toppled(),
            ended_by=state,
            arm_seconds=cell.arm_seconds,
            pushes_asked=run._pushes + run._paths,
            thinking_seconds=thinking,
            why=run._why,
        )

    def run(
        self, solution: Solution, table: int, prepare: Callable[[TableRun], None] | None = None
    ) -> TableResult:
        """Start the table, let the solution clear it, and mark it.

        ``prepare`` is for the examiner's own tools: it is handed the run before the
        solution is, so that a film can watch the physics or a record can watch the pushes.
        """
        run = self.start(table)
        try:
            if prepare is not None:
                prepare(run)
            with contextlib.suppress(RunOver):  # the run ended, which is one of the ways a table ends
                solution.clear(run)
        except BaseException:
            run._cell.close()
            raise
        if run.state == RUNNING:
            run.finish("the solution returned without saying it had finished")
        return self.result(run)


# ------------------------------------------------------------------ a list of tables


def clear_queue(
    build: Callable[[], Solution],
    seeds: Sequence[int],
    link: MoveItLink,
    budget: float = ARM_BUDGET,
    tally: Tally | None = None,
    log: Callable[[str], None] | None = None,
) -> list[TableResult]:
    """One solution down a list of tables until the list or the arm time runs out."""
    examiner = SimExaminer(link, budget, tally)
    solution = build()
    results = []
    for seed in seeds:
        if examiner.left < LEAST_ACTION:
            break
        result = examiner.run(solution, seed)
        if result.ended_by == OUT_OF_TIME and result.arm_seconds == 0.0:
            continue  # the clock ended this table before the arm did anything on it
        results.append(result)
        if log:
            log(
                f"table {seed}: {result.separated_at_start}->{result.separated_at_end}/{result.glasses} "
                f"separated, {result.arm_seconds:.0f} arm s, {result.pushes_asked} pushes asked, "
                f"{result.ended_by}, fell over {result.fell_over}"
            )
    return results


# ---------------------------------------------------------------------- the marks
#
# The marks are problem 4's scorecard, so a number from here is read on the same scale as
# a number from the top-down cell. The scorecard reads its own shape of result, so each
# table is written into that shape before it is marked.


def scored(result: TableResult):
    import contract

    ended = {FINISHED: contract.SAID_DONE, OUT_OF_TIME: contract.RAN_OUT, GLASS_OVER: contract.GLASS_OVER}
    return contract.TableResult(
        seed=result.table,
        glasses=result.glasses,
        pickable_at_start=result.separated_at_start,
        pickable_at_end=result.separated_at_end,
        toppled=result.fell_over,
        ended_by=ended[result.ended_by],
        arm_seconds=result.arm_seconds,
        thinking_seconds=result.thinking_seconds,
        answers=result.pushes_asked,
    )


def judge(
    build: Callable[[], Solution],
    link: MoveItLink,
    first: int,
    tables: int,
    runs: int = 1,
    budget: float = ARM_BUDGET,
    log: Callable[[str], None] | None = print,
) -> tuple[dict, Tally, list[list[dict]]]:
    """Walk the list ``runs`` times: problem 4's scorecard, the tally, and every table's own row."""
    from scoring import Repeats

    repeats = Repeats()
    tally = Tally()
    rows: list[list[dict]] = []
    for walk in range(runs):
        card = repeats.run()
        started = time.perf_counter()
        results = clear_queue(build, list(range(first, first + tables)), link, budget, tally, log)
        for result in results:
            card.table(scored(result))
        rows.append(card.tables)
        if log:
            log(
                f"run {walk + 1}/{runs}: {len(results)} tables, "
                f"{sum(r.arm_seconds for r in results):.0f} arm s, "
                f"{time.perf_counter() - started:.0f} s of laptop time"
            )
    return repeats.summary(), tally, rows


def headline(summary: dict) -> str:
    """The numbers a run is read by, on one line; with the spread when there are several runs."""
    spread = summary["spread"]

    def mid(key: str) -> str:
        entry = spread[key]
        if summary["runs"] > 1:
            return f"{entry['median']:g} (sd {entry['sd']:.2g})"
        return f"{entry['median']:g}"

    return (
        f"tables {mid('tables_attempted')}, glasses {mid('glasses')}, "
        f"pickable {mid('glasses_end.pickable_at_start')} -> {mid('glasses_end.pickable')} "
        f"(share {mid('glasses_end.pickable_share')}), broken {mid('glasses_end.broken')}, "
        f"separated {mid('outcome.separated')}, failed {mid('outcome.failed')}, "
        f"unfinished {mid('outcome.unfinished')}, "
        f"said done {mid('ended_by.said_done')}, arm s {mid('arm_seconds.total')}"
    )
