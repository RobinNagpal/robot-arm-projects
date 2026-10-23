"""Tests for the loop: the three ways a table ends, and the one thing still refused.

The loop is tested against a cell of its own rather than against the physics
engine, for two reasons. The behaviour being checked is the loop's — when it
stops, what it charges, what it refuses — and none of that is physics; and the
real cell needs a renderer and so a graphics context, which a test should not
need. ``FakeCell`` below answers the ``Cell`` protocol and nothing else.

What is deliberately covered is the four things that would be wrong *silently*:
a solution that says ``Done`` straight away and is believed; one that never says
it and has to be stopped by the clock; one that knocks a glass over; and the
interlock refusing a glass the physics would tip. Each of those, got wrong,
still produces a ``TableResult`` that a scorecard would happily add up.

The tipping interlock is exercised against families of glasses rather than one,
because the rule it uses is a proportion — half the foot over the friction,
against how high the jaw pushes — and a rule like that can hold for one glass
and fail for a differently proportioned one.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

import numpy as np
import pytest
from work_cell.glasses.shapes import KIND_RANGES, draw

from clock import WAYPOINT_PERIOD, crossing_seconds, followed_seconds, path_seconds
from contract import GLASS_OVER, RAN_OUT, SAID_DONE, Done, Look
from open_run import (
    HOME,
    LEAST_ACTION,
    Tally,
    clear_queue,
    clear_table,
    hand_meets,
    interlocked,
    most_answers,
    open_cell,
    solution_one,
    tips,
)
from partners import (
    PUSH_HEIGHT,
    TEST_SEEDS,
    TRAVEL_HEIGHT,
    Chunk,
    Felt,
    Push,
    Record,
    Seen,
    Waypoint,
)
from wrist import WRIST_VIEW_SIZE

# Every path in these tests starts where the jaw starts, so that the crossing to
# the first path costs nothing and the arithmetic below is about one thing at a
# time. It is the middle of the glass zone, well inside the table.
START = (HOME.x, HOME.y)

# How many entries the retreat and the lift home add to an examiner record. The real
# number depends on the path; what matters to the loop is only that a record is
# longer than the legs it was commanded with, and these tests need a charge big
# enough to empty a budget in a few tables.
LIFT = 24


def glass(
    at: tuple[float, float] = START,
    *,
    id: int = 0,
    foot: float = 0.06,
    widest: float = 0.07,
    height: float = 0.12,
    standing: bool = True,
) -> Seen:
    """One glass as a look would report it. The numbers are measurements, not a size table."""
    return Seen(id=id, x=at[0], y=at[1], height=height, widest=widest, foot=foot, standing=standing)


def straight(start: tuple[float, float], end: tuple[float, float], *, z: float = PUSH_HEIGHT) -> Chunk:
    """A path that walks from one point to another in small steps.

    Built at a step the jaw can keep up with, because in this cell how far apart
    the waypoints are *is* how fast the jaw goes.
    """
    heading = math.atan2(end[1] - start[1], end[0] - start[0])
    steps = max(1, round(math.dist(start, end) / 0.005))
    points = tuple(
        Waypoint(
            start[0] + (end[0] - start[0]) * i / steps,
            start[1] + (end[1] - start[1]) * i / steps,
            z,
            heading,
        )
        for i in range(steps + 1)
    )
    return Chunk(glass=0, waypoints=points, aim=end)


def traced(chunk: Chunk, legs: int | None = None, lift: int = 0) -> Record:
    """An examiner record for a path, as if the jaw had followed ``legs`` of its waypoints.

    ``legs`` short of the whole path is a path the cell stopped early, which is
    what the budget has to charge honestly. ``lift`` stands for the retreat and
    the lift home, which the examiner also writes into the record.
    """
    points = chunk.waypoints[: (len(chunk.waypoints) if legs is None else legs + 1)]
    points = points + (points[-1],) * lift
    felt = Felt(blocked=False, touched=None, jammed=False, peak=0.0, pushed=0.0)
    return Record(push=chunk.as_push(), felt=felt, landed=chunk.aim, waypoints=points)


def nudge_away(across: float = 0.04) -> Chunk:
    """A short push across the middle of the glass zone, starting where the jaw starts."""
    return straight(START, (START[0] + across, START[1]))


@dataclass
class FakeCell:
    """A work cell with no physics in it, for testing the loop on its own.

    ``topple_after`` is how many paths it carries out before a glass goes over,
    ``refuse`` makes ``follow`` raise the way the examiner raises for a path the jaw
    cannot follow, and ``legs_followed`` makes it stop a path early.
    """

    on_table: list[Seen] = field(default_factory=lambda: [glass()])
    pickable_now: int = 0
    topple_after: int | None = None
    refuse: bool = False
    simulator_seconds: float = 0.0
    legs_followed: int | None = None
    lift: int = 0

    followed: list[Chunk] = field(default_factory=list)
    looks: int = 0
    fell: int = 0

    def glasses(self) -> int:
        return len(self.on_table)

    def view(self, jaw: Waypoint) -> tuple[np.ndarray, tuple[Seen, ...]]:
        self.looks += 1
        # One pixel is a picture. The loop never reads it, it only passes it on,
        # and this test is about the loop.
        return np.zeros((1, 1, 3), dtype=np.uint8), tuple(self.on_table)

    def truth(self) -> tuple[Seen, ...]:
        return tuple(self.on_table)

    def follow(self, chunk: Chunk) -> Record:
        if self.refuse:
            raise ValueError("waypoint 0 at (9.000, 9.000) is off the table")
        self.followed.append(chunk)
        if self.topple_after is not None and len(self.followed) >= self.topple_after:
            self.fell = 1
        return traced(chunk, self.legs_followed, self.lift)

    def toppled(self) -> int:
        return self.fell

    def pickable(self) -> int:
        return self.pickable_now

    def charged(self) -> float:
        return self.simulator_seconds


@dataclass
class Scripted:
    """A solution that answers from a list and repeats its last answer forever.

    ``begin`` forgets the last table, as a real solution's does, so the same
    object can be walked down a queue.
    """

    answers: list[object]
    name: str = "scripted"
    begun: list[int] = field(default_factory=list)
    seen: list[Look] = field(default_factory=list)
    asked: int = 0

    def begin(self, seed: int) -> None:
        self.begun.append(seed)
        self.asked = 0

    def answer(self, look: Look) -> object:
        self.seen.append(look)
        at = min(self.asked, len(self.answers) - 1)
        self.asked += 1
        return self.answers[at]


# --------------------------------------------------------------- saying done


def test_done_straight_away_is_believed_and_costs_no_arm_time():
    cell = FakeCell(on_table=[glass(), glass((0.5, -0.2), id=1)], pickable_now=2)
    solution = Scripted([Done("nothing to do")])
    tally = Tally()

    result = clear_table(solution, 7, 60.0, cell=cell, tally=tally)

    assert result.ended_by == SAID_DONE
    assert result.said_done
    assert result.answers == 1
    assert result.arm_seconds == 0.0
    assert cell.followed == []
    # It was asked once, which means it was shown the table once.
    assert cell.looks == 1
    assert solution.begun == [7]
    assert tally.done_because == {"nothing to do": 1}


def test_a_table_said_done_on_is_marked_on_how_it_was_left_not_on_the_claim():
    # Two glasses, one of them still crowded. Saying done does not make it clean.
    cell = FakeCell(on_table=[glass(), glass((0.5, -0.2), id=1)], pickable_now=1)
    result = clear_table(Scripted([Done()]), 11, 60.0, cell=cell)

    assert result.said_done
    assert not result.separated
    assert result.unfinished


def test_said_done_with_no_reason_is_still_logged():
    tally = Tally()
    clear_table(Scripted([Done()]), 3, 60.0, cell=FakeCell(), tally=tally)
    assert tally.done_because == {"no reason given": 1}


# ----------------------------------------------------------------- the clock


def test_never_saying_done_is_stopped_by_the_clock():
    push = nudge_away()
    cell = FakeCell(pickable_now=1)
    result = clear_table(Scripted([push]), 1, 10.0, cell=cell)

    assert result.ended_by == RAN_OUT
    assert not result.said_done
    assert len(cell.followed) >= 3
    # Every answer but the last was carried out, and the last did not fit.
    assert result.answers == len(cell.followed) + 1
    assert 0 < result.arm_seconds <= 10.0


def test_the_last_path_that_does_not_fit_is_not_cut_short_to_make_it():
    push = nudge_away()
    cell = FakeCell()
    # Exactly what one path is expected to cost from where the jaw starts, so one
    # is afforded and the second is not.
    budget = crossing_seconds(HOME, push.waypoints[0]) + path_seconds(push)
    result = clear_table(Scripted([push]), 1, budget, cell=cell)

    assert result.ended_by == RAN_OUT
    assert len(cell.followed) == 1
    assert result.answers == 2


def test_a_path_nothing_can_afford_is_never_made():
    push = nudge_away()
    cell = FakeCell()
    result = clear_table(Scripted([push]), 1, path_seconds(push) / 2, cell=cell)

    assert result.ended_by == RAN_OUT
    assert result.arm_seconds == 0.0
    assert cell.followed == []
    assert result.answers == 1


def test_the_arm_is_charged_for_the_motion_that_happened_not_the_one_commanded():
    push = nudge_away()
    # The cell stops the jaw after two legs, as it would on jamming.
    cell = FakeCell(legs_followed=2)
    result = clear_table(Scripted([push, Done()]), 1, 60.0, cell=cell)

    assert len(cell.followed) == 1
    # Nothing for the crossing, because the path starts where the jaw stands.
    assert result.arm_seconds == pytest.approx(2 * WAYPOINT_PERIOD)
    assert result.arm_seconds < path_seconds(push)


def test_crossing_the_table_to_a_path_is_charged():
    """Otherwise a look from the far corner costs what a look from here costs."""
    here = straight(START, (START[0] + 0.02, START[1]))
    far = straight((START[0] + 0.15, START[1]), (START[0] + 0.17, START[1]))
    assert path_seconds(here) == pytest.approx(path_seconds(far))

    near_cell, far_cell = FakeCell(), FakeCell()
    near = clear_table(Scripted([here, Done()]), 1, 60.0, cell=near_cell)
    away = clear_table(Scripted([far, Done()]), 1, 60.0, cell=far_cell)

    assert len(near_cell.followed) == len(far_cell.followed) == 1
    assert away.arm_seconds > near.arm_seconds
    assert away.arm_seconds - near.arm_seconds == pytest.approx(
        crossing_seconds(HOME, far.waypoints[0])
    )


def test_the_solution_is_told_how_much_arm_time_is_left():
    push = nudge_away()
    solution = Scripted([push, push, Done()])
    clear_table(solution, 1, 60.0, cell=FakeCell(), tally=Tally())

    told = [look.seconds_left for look in solution.seen]
    assert told[0] == 60.0
    assert told[1] < told[0] and told[2] < told[1]


def test_a_solution_that_moves_the_arm_nowhere_is_stopped_by_the_answer_guard():
    # A path the examiner will not take at all: the arm never moves, so the clock
    # never advances and only the guard can end the table.
    cell = FakeCell(refuse=True)
    tally = Tally()
    budget = 2.0
    result = clear_table(Scripted([nudge_away()]), 1, budget, cell=cell, tally=tally)

    assert result.ended_by == RAN_OUT
    assert result.arm_seconds == 0.0
    assert result.answers == most_answers(budget)
    assert tally.out_of_answers == 1
    assert tally.refused_by_simulator == result.answers
    assert len(tally.refused_because) == 1


def test_most_answers_only_binds_on_answers_that_move_the_arm_nowhere():
    """Every real leg costs at least a waypoint period, so the clock bites first."""
    for budget in (0.5, 1.0, 10.0, 60.0):
        assert most_answers(budget) >= budget / WAYPOINT_PERIOD


# ------------------------------------------------------------- a glass over


def test_a_toppled_glass_ends_the_table_at_once():
    push = nudge_away()
    cell = FakeCell(on_table=[glass(), glass((0.5, -0.2), id=1)], pickable_now=2, topple_after=2)
    result = clear_table(Scripted([push]), 5, 60.0, cell=cell)

    assert result.ended_by == GLASS_OVER
    assert not result.said_done
    assert result.toppled == 1
    assert result.failed and not result.separated
    # Stopped on the push that knocked it over, and asked nothing after.
    assert len(cell.followed) == 2
    assert result.answers == 2


def test_a_toppled_glass_ends_that_table_and_not_the_queue():
    push = nudge_away()

    def cell_for(seed: int) -> FakeCell:
        # The first table loses a glass; the second is finished cleanly.
        return FakeCell(pickable_now=1, topple_after=1) if seed == 0 else FakeCell(pickable_now=1)

    run = clear_queue(Scripted([push, Done()]), [0, 1], 60.0, cell_for=cell_for)

    assert run.attempted == 2
    assert run.results[0].ended_by == GLASS_OVER
    assert run.results[1].ended_by == SAID_DONE


# ------------------------------------------------------------- the interlock


def family(kind: str, count: int = 12) -> list[Seen]:
    """Glasses of one kind across the plausible range, as a look would measure them."""
    rng = random.Random(4)
    drawn = []
    for _ in range(count):
        outline = draw(kind, rng)[0]
        drawn.append(
            Seen(
                id=0,
                x=START[0],
                y=START[1],
                height=outline.total_height,
                widest=outline.max_diameter,
                foot=2 * float(outline.radius[0]),
                standing=True,
            )
        )
    return drawn


def test_tips_agrees_with_solution_ones_rule_across_families():
    """The interlock refuses exactly what ``slides`` answers "no" to, and nothing else.

    Across every kind of glass this cell draws, because the rule is a proportion
    and a proportion can hold for one glass and fail for another.
    """
    slides = solution_one().slides
    for kind in sorted(KIND_RANGES):
        drawn = family(kind)
        refused = {id(one) for one in tips(drawn)}
        for one in drawn:
            assert (id(one) in refused) == (slides(one) == "no"), kind


def test_a_glass_that_only_might_tip_is_not_refused():
    """"try" is the solution's to settle with a test push, not the cell's to refuse."""
    slides = solution_one().slides
    maybe = [one for kind in sorted(KIND_RANGES) for one in family(kind, 40) if slides(one) == "try"]
    if not maybe:
        pytest.skip("this draw produced no glass whose tipping depends on the friction")
    assert tips(maybe) == ()


def test_a_path_into_a_tipping_glass_is_refused_and_counted():
    # A wide foot slides; a narrow one tips. Both are measurements, not sizes.
    tipper = glass((START[0] + 0.04, START[1]), id=1, foot=0.01, widest=0.07, height=0.15)
    assert tips([tipper]) == (tipper,)

    into_it = straight(START, (tipper.x, tipper.y))
    cell = FakeCell(on_table=[glass(), tipper], pickable_now=1)
    result = clear_table(Scripted([into_it, Done("cannot touch that one")]), 2, 60.0, cell=cell)

    assert result.interlocks == 1
    assert cell.followed == []
    assert result.arm_seconds == 0.0
    # Refused, not ended: the solution was shown the same table again and
    # answered a second time.
    assert result.answers == 2
    assert result.ended_by == SAID_DONE


def test_the_interlock_lets_a_path_that_keeps_clear_through():
    tipper = glass((START[0] + 0.15, START[1] - 0.15), id=1, foot=0.01, widest=0.07, height=0.15)
    away = straight(START, (START[0], START[1] + 0.05))
    cell = FakeCell(on_table=[glass(), tipper], pickable_now=1)
    result = clear_table(Scripted([away, Done()]), 2, 60.0, cell=cell)

    assert result.interlocks == 0
    assert len(cell.followed) == 1
    assert interlocked(away, cell.truth()) is None


def test_the_interlock_ignores_a_path_that_rides_over_the_glass():
    """High enough and the hand passes above it, which is how a solution crosses the table."""
    tipper = glass(id=1, foot=0.01, widest=0.07, height=0.10)
    across = ((START[0] - 0.1, START[1]), (START[0] + 0.1, START[1]))
    assert hand_meets(straight(*across, z=PUSH_HEIGHT), tipper)
    assert not hand_meets(straight(*across, z=TRAVEL_HEIGHT), tipper)


def test_the_interlock_sees_the_whole_hand_and_not_only_the_fingertips():
    """A path that never aims at the glass still drags the wrist past it.

    The hand reaches back from the fingertips, so a push whose tips pass beside a
    glass can still sweep the body of the gripper through it. One figure for the
    whole hand would be either needlessly cautious or quietly dangerous, which is
    why the silhouette is checked stretch by stretch.
    """
    tipper = glass((START[0], START[1] + 0.05), id=1, foot=0.01, widest=0.07, height=0.15)
    # Driving in +x, so the hand trails behind in -x and passes the glass abeam.
    alongside = straight((START[0] - 0.10, START[1]), (START[0] + 0.10, START[1]))
    assert hand_meets(alongside, tipper)
    assert interlocked(alongside, [tipper]) == tipper.id


def test_a_single_waypoint_path_is_checked_where_it_comes_down():
    """One waypoint is a legal path: the jaw drops onto it and that is the whole motion."""
    tipper = glass(id=1, foot=0.01, widest=0.07, height=0.15)
    onto_it = Chunk(glass=1, waypoints=(Waypoint(tipper.x, tipper.y, PUSH_HEIGHT, 0.0),), aim=(START))
    assert hand_meets(onto_it, tipper)


# ------------------------------------------------------------------ the queue


def test_the_queue_walks_until_the_arm_time_runs_out():
    push = nudge_away()

    def cell_for(seed: int) -> FakeCell:
        return FakeCell(pickable_now=1, lift=LIFT)

    per_table = followed_seconds(traced(push, lift=LIFT))
    # Three tables' worth, and then too little left for the cheapest action.
    budget = 3 * per_table + LEAST_ACTION / 2
    run = clear_queue(Scripted([push, Done()]), [100, 101, 102, 103, 104], budget, cell_for=cell_for)

    assert run.attempted == 3
    assert [r.seed for r in run.results] == [100, 101, 102]
    assert run.arm_seconds == pytest.approx(3 * per_table)
    assert run.left < LEAST_ACTION
    assert not run.finished_the_queue


def test_a_table_the_arm_never_moved_on_is_not_counted():
    """The queue's own guard is a floor under one descent, and a path costs more.

    So the last table of a walk can be handed a few seconds, answer with a path
    that does not fit, and come back with the arm never having moved. Such a
    table is not a table the solution failed, and counting it would both
    overstate how far down the queue the solution reached and add every glass
    standing on it to the glasses it left crowded.
    """
    push = nudge_away()
    per_table = followed_seconds(traced(push, lift=LIFT))
    # Two tables' worth, and then exactly one descent left, which is enough to
    # pass the guard above and nowhere near enough to pay for a whole path.
    # That is the gap the guard cannot see.
    budget = 2 * per_table + LEAST_ACTION
    run = clear_queue(
        Scripted([push, Done()]),
        [100, 101, 102, 103],
        budget,
        cell_for=lambda seed: FakeCell(pickable_now=1, lift=LIFT),
    )

    assert [r.seed for r in run.results] == [100, 101]
    assert not run.finished_the_queue


def test_the_walk_carries_on_past_a_table_it_could_not_reach():
    """What did not fit was one path and not every path.

    The clock still holds time when a table is handed back untouched, so the
    next table is offered, and a solution asked for something cheaper there can
    still be given it. A queue in a real cell behaves the same way: it moves on
    to the next table rather than ending the shift.
    """
    long_push, short_push = nudge_away(across=0.2), nudge_away(across=0.01)
    long_cost = followed_seconds(traced(long_push, lift=LIFT))
    short_cost = followed_seconds(traced(short_push, lift=LIFT))
    assert short_cost < long_cost, "the second table has to be the cheaper one"

    class LongThenShort:
        """Asks for the long path on the first table and the short one after."""

        name = "long then short"

        def __init__(self) -> None:
            self.tables = 0

        def begin(self, seed: int) -> None:
            self.tables += 1
            self.answered = False

        def answer(self, look: Look):
            if self.answered:
                return Done("nothing more")
            self.answered = True
            return long_push if self.tables == 1 else short_push

    run = clear_queue(
        LongThenShort(),
        [100, 101],
        long_cost - 0.5,
        cell_for=lambda seed: FakeCell(pickable_now=1, lift=LIFT),
    )

    assert [r.seed for r in run.results] == [101], "the first was unreachable, the second was not"


def test_a_table_the_clock_stopped_partway_is_still_counted():
    """The other side of the same rule, so that it cannot be read too widely.

    A table where the arm did move and then ran out of time is a real attempt
    that the solution did not finish, and it is counted as one.
    """
    push = nudge_away()
    per_table = followed_seconds(traced(push, lift=LIFT))
    run = clear_queue(
        Scripted([push, push, Done()]),
        [100],
        per_table + LEAST_ACTION + 0.5,
        cell_for=lambda seed: FakeCell(pickable_now=1, lift=LIFT),
    )

    assert run.attempted == 1
    assert run.results[0].ended_by == RAN_OUT
    assert run.results[0].arm_seconds > 0.0
    assert not run.results[0].never_reached


def test_the_queue_reports_finishing_the_list_before_the_budget():
    run = clear_queue(
        Scripted([Done()]), [100, 101], 60.0, cell_for=lambda seed: FakeCell(pickable_now=1)
    )
    assert run.attempted == 2
    assert run.finished_the_queue
    assert run.left == 60.0


def test_each_table_is_told_what_is_left_of_the_whole_budget():
    push = nudge_away()
    solution = Scripted([push, Done()])
    per_table = followed_seconds(traced(push, lift=LIFT))
    clear_queue(solution, [1, 2], 60.0, cell_for=lambda seed: FakeCell(pickable_now=1, lift=LIFT))

    first_looks = [look.seconds_left for look in solution.seen[:2]]
    assert first_looks[0] == 60.0
    # The second table starts from what the first one left, not from a fresh share.
    assert solution.seen[2].seconds_left == pytest.approx(60.0 - per_table)


def test_the_tally_adds_up_over_the_queue():
    tally = Tally()
    clear_queue(
        Scripted([nudge_away(), Done("done")]),
        [1, 2, 3],
        60.0,
        tally=tally,
        cell_for=lambda seed: FakeCell(pickable_now=1),
    )
    assert tally.tables == 3
    assert tally.followed == 3
    assert tally.done_because == {"done": 3}
    assert "tables" in tally.summary()


# ---------------------------------------------------------------- the clocks


def test_thinking_time_leaves_out_the_examiners_own_share():
    """Thinking is the wall clock less what the cell charged to itself."""

    @dataclass
    class Slow(FakeCell):
        def view(self, jaw: Waypoint):
            # The cell's own cost: rendering and measuring, not thinking.
            self.simulator_seconds += 10.0
            return super().view(jaw)

    cell = Slow(pickable_now=1)
    result = clear_table(Scripted([Done()]), 1, 60.0, cell=cell)

    # The cell charged more to itself than the whole table took in wall time, so
    # there is no thinking left to report, and it is never negative.
    assert result.thinking_seconds == 0.0
    assert cell.simulator_seconds == pytest.approx(10.0)


def test_thinking_time_counts_what_the_solution_spends_deciding():
    @dataclass
    class Dawdling(Scripted):
        def answer(self, look: Look) -> object:
            until = time.perf_counter() + 0.02
            while time.perf_counter() < until:
                pass
            return super().answer(look)

    result = clear_table(Dawdling([Done()]), 1, 60.0, cell=FakeCell())
    assert result.thinking_seconds >= 0.02


def test_an_answer_that_is_neither_a_path_nor_done_is_an_error_not_a_score():
    with pytest.raises(TypeError, match="not a Chunk or Done"):
        clear_table(Scripted(["go left a bit"]), 1, 60.0, cell=FakeCell())


def test_the_look_is_taken_from_where_the_solution_drove_the_jaw():
    push = nudge_away()
    solution = Scripted([push, Done()])
    clear_table(solution, 1, 60.0, cell=FakeCell())

    assert solution.seen[0].jaw == HOME
    assert solution.seen[1].jaw == push.waypoints[-1]


def test_a_record_cannot_be_mistaken_for_a_commanded_path():
    """The two differ, which is the whole reason the loop charges from the record."""
    push = nudge_away()
    whole = traced(push)
    cut_short = traced(push, legs=1)
    assert followed_seconds(cut_short) < followed_seconds(whole)
    assert followed_seconds(traced(push, lift=LIFT)) > followed_seconds(whole)
    assert isinstance(whole.push, Push)


# ------------------------------------------------------------ the real cell


def test_one_real_table_through_the_real_cell():
    """The wiring: the draw, the physics, the camera on the arm, and the scorer.

    Every test above this one uses a cell of its own, so none of them would
    notice a name moving in ``tables.py``, ``wrist.py`` or ``scoring.py``. One
    table and two answers notices, and costs a fraction of a second.
    """
    push = nudge_away()
    solution = Scripted([push, Done("seen enough")])
    cell = open_cell(TEST_SEEDS)
    try:
        result = clear_table(solution, TEST_SEEDS, 60.0, cell=cell)
    finally:
        cell.camera.close()

    assert result.ended_by == SAID_DONE
    assert result.glasses == len(cell.simulator.glasses)
    assert result.arm_seconds > 0.0
    assert 0 <= result.pickable_at_end <= result.glasses

    first, second = solution.seen[0], solution.seen[1]
    assert first.picture.shape == (*WRIST_VIEW_SIZE, 3)
    # The camera is carried by the arm, so the second look is from somewhere
    # else and does not have to show the same glasses.
    assert first.jaw == HOME
    assert second.jaw == push.waypoints[-1]
    assert len(first.seen) <= result.glasses
    # A look reaches only as far as the camera does. On a table this crowded
    # that is less than the whole table from at least one of the two poses.
    assert min(len(first.seen), len(second.seen)) < result.glasses


def test_a_solution_is_told_why_its_path_was_not_carried_out():
    """Silence after a refusal would be a lie, so the next look carries the reason.

    The arm does not move when a path is refused, so the next look is the same
    table seen from the same place. Without a reason attached, a solution
    cannot tell "the cell refused my path" from "my push did nothing", and
    those two call for opposite responses: try somewhere else, or try harder.
    """
    reasons: list[str] = []

    class _Watching:
        name = "watching"

        def begin(self, seed: int) -> None:
            self.answers = 0

        def answer(self, look):
            reasons.append(look.refused)
            self.answers += 1
            if self.answers > 3:
                return Done("seen enough")
            # Far too long for the examiner to accept, so it is refused every time.
            return Chunk(0, tuple(Waypoint(0.48, -0.26, TRAVEL_HEIGHT, 0.0) for _ in range(900)),
                         (0.48, -0.26))

    clear_table(_Watching(), 0, 400.0)
    assert reasons[0] == "", "nothing has been refused before the first answer"
    assert any(reason for reason in reasons[1:]), "a refusal must reach the solution"
