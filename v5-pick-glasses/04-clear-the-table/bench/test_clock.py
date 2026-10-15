"""The clock against the cell it is a model of.

The arithmetic in ``clock.py`` is only worth anything if it agrees with the
bench, so most of this file does not check a formula against itself. It follows
a path on a real table and reads the time back out of the bench's own record of
what the jaw did.

That record is ``Record.waypoints``: where the jaw was told to be, written down
one WAYPOINT_PERIOD apart, from the first step of the action to the last. How
many entries it has is how long the action took. It covers the path only as far
as the jaw really got, and it covers the lift home afterwards, which is exactly
why the charge and the estimate are two different numbers — the last two tests
are about that difference.
"""

from __future__ import annotations

import math

import pytest
from work_cell.glasses.shapes import family
from work_cell.table.layout import TABLE_TOP_Z

import clock
from partners import (
    DESCEND_SPEED,
    PUSH_HEIGHT,
    TEST_SEEDS,
    TOP_SPEED,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    Bench,
    Chunk,
    Record,
    SpawnedGlass,
    Waypoint,
)

# Where the paths below run, and where the one glass stands: opposite ends of
# the glass zone, so no path reaches the glass unless it is meant to. A path
# that touched something by accident would be stopped early and would then
# measure the physics instead of the clock.
AWAY = (0.36, -0.42)
GLASS_AT = (0.60, -0.12)


def _path(*legs: tuple[float, float, float, float]) -> tuple[Waypoint, ...]:
    return tuple(Waypoint(*leg) for leg in legs)


def _straight(x: float, y: float, z: float, step: float, legs: int) -> tuple[Waypoint, ...]:
    """A drop onto (x, y, z) and then ``legs`` equal steps along x."""
    return _path((x, y, z, 0.0), *((x + step * k, y, z, 0.0) for k in range(1, legs + 1)))


# A family of path shapes, not of glasses: the clock reads nothing about a
# glass, and what its answer is made of is the shape of the path. Each one here
# is a different part of follow()'s rule — the waypoint period, the top speed,
# a leg of no length, a path that starts at travel height, and a turn.
PATHS = {
    "legs short enough to take one waypoint period each": _straight(*AWAY, PUSH_HEIGHT, 0.005, 4),
    "one leg too long to cover in a waypoint period": _straight(*AWAY, PUSH_HEIGHT, 0.100, 1),
    "a repeated waypoint the jaw cannot move to": _path(
        (*AWAY, PUSH_HEIGHT, 0.0),
        (*AWAY, PUSH_HEIGHT, 0.0),
        (AWAY[0] + 0.005, AWAY[1], PUSH_HEIGHT, 0.0),
    ),
    "a first waypoint already at travel height": _path(
        (*AWAY, TRAVEL_HEIGHT, 0.0),
        (*AWAY, TRAVEL_HEIGHT - 0.005, 0.0),
    ),
    "a quarter turn partway along": _path(
        (*AWAY, PUSH_HEIGHT, 0.0),
        (AWAY[0] + 0.005, AWAY[1], PUSH_HEIGHT, math.pi / 2),
        (AWAY[0] + 0.005, AWAY[1] + 0.005, PUSH_HEIGHT, math.pi / 2),
    ),
}


@pytest.fixture(scope="module")
def table() -> Bench:
    """One table for the whole file, because building the world is the slow part.

    It holds a single glass, standing in the far corner. A chunk has to name a
    glass — the bench reads that glass's position when it writes the record —
    so the table cannot be empty. Most of the paths here keep well away from
    it; the last test is the one that comes down on it on purpose.
    """
    outline, _ = next(iter(family("straight_glass", 1, seed=2)))
    glass = SpawnedGlass("glass_0", "straight_glass", outline, (*GLASS_AT, TABLE_TOP_Z), 0.0)
    return Bench(TEST_SEEDS, [glass])


def _clear_run(table: Bench, path: tuple[Waypoint, ...]) -> Record:
    """Follow a path that touches nothing, and return the bench's record of it.

    Touching nothing is asserted rather than hoped for: it is what makes this
    an action carried out in full, and the estimate is only comparable with the
    charge when the whole path really happened.
    """
    felt = table.follow(Chunk(0, path, (0.0, 0.0)))
    assert not felt.blocked and felt.touched is None and not felt.jammed
    return table.records[-1]


def _recorded_seconds(record: Record) -> float:
    """The seconds the record implies, counted here rather than asked of clock.py."""
    return (len(record.waypoints) - 1) * WAYPOINT_PERIOD


def _simulated_seconds(table: Bench, path: tuple[Waypoint, ...]) -> float:
    """The simulator's own clock across one action, which can see inside a waypoint period.

    The record is written on a WAYPOINT_PERIOD grid, so it cannot show a
    difference smaller than one entry. This can, at the cost of also counting
    the settling afterwards — which is why it is only ever used below to
    compare two actions that end in the same place.
    """
    before = float(table.data.time)
    table.follow(Chunk(0, path, (0.0, 0.0)))
    return float(table.data.time) - before


@pytest.mark.parametrize("shape", list(PATHS))
def test_the_estimate_is_the_seconds_the_bench_spends_on_the_path(table, shape):
    path = PATHS[shape]
    record = _clear_run(table, path)
    # The charge is that reading of the record and nothing else.
    assert clock.followed_seconds(record) == _recorded_seconds(record)
    # The estimate covers the drop and the legs. The record also holds the lift
    # back to travel height, which the cell does at DESCEND_SPEED from wherever
    # the path ended, so it is added here rather than hidden in the tolerance.
    # What is left is one entry of rounding: the record is written on a
    # WAYPOINT_PERIOD grid and an action need not end on it.
    lift = (TRAVEL_HEIGHT - path[-1].z) / DESCEND_SPEED
    assert _recorded_seconds(record) == pytest.approx(clock.path_seconds(path) + lift, abs=WAYPOINT_PERIOD)


def test_a_path_starting_at_travel_height_pays_the_drop_s_price_for_its_first_leg(table):
    """The quirk in follow() that the rule on its own does not say.

    A leg of no length is skipped before the loop stops calling legs the
    lead-in, so a path whose first waypoint already sits at travel height is
    not charged for a drop, and its first real leg is charged as the drop
    instead: at DESCEND_SPEED, with no waypoint period under it. Here that
    makes the two paths below the same motion, and they cost the same.
    """
    x, y = AWAY
    skipped = _path((x, y, TRAVEL_HEIGHT, 0.0), (x, y, TRAVEL_HEIGHT - 0.005, 0.0))
    dropped = _path((x, y, TRAVEL_HEIGHT - 0.005, 0.0))
    assert clock.path_seconds(skipped) == pytest.approx(clock.path_seconds(dropped))
    # Both end in the same place, so everything outside the path itself is the
    # same in both, and the simulator has to agree to the step.
    assert _simulated_seconds(table, skipped) == pytest.approx(_simulated_seconds(table, dropped), abs=1e-9)


def test_two_more_legs_cost_what_the_clock_says_two_more_legs_cost(table):
    """The same check without trusting anything about the lift.

    Both paths start and end in the same place, so the drop and the lift home
    are the same seconds in both, and the whole difference between them is the
    two extra legs.
    """
    x, y = AWAY
    straight = _path((x, y, PUSH_HEIGHT, 0.0), (x + 0.010, y, PUSH_HEIGHT, 0.0))
    detour = _path(
        (x, y, PUSH_HEIGHT, 0.0),
        (x + 0.020, y, PUSH_HEIGHT, 0.0),
        (x + 0.010, y, PUSH_HEIGHT, 0.0),
    )
    measured = _recorded_seconds(_clear_run(table, detour)) - _recorded_seconds(_clear_run(table, straight))
    predicted = clock.path_seconds(detour) - clock.path_seconds(straight)
    assert measured == pytest.approx(predicted, abs=1e-9)


def test_a_leg_costs_a_waypoint_period_until_the_jaw_runs_out_of_speed():
    """Waypoints closer together than the jaw's top speed do not make it faster."""
    assert clock.leg_seconds(0.0) == WAYPOINT_PERIOD
    assert clock.leg_seconds(clock.LEG_AT_TOP_SPEED / 2) == WAYPOINT_PERIOD
    assert clock.leg_seconds(clock.LEG_AT_TOP_SPEED) == pytest.approx(WAYPOINT_PERIOD)
    for multiple in (1, 2, 5, 20):
        length = multiple * clock.LEG_AT_TOP_SPEED
        assert clock.leg_seconds(length) == pytest.approx(multiple * WAYPOINT_PERIOD)
        assert length / clock.leg_seconds(length) <= TOP_SPEED + 1e-12


def test_a_path_pays_for_the_drop_onto_its_first_waypoint():
    """A one-waypoint path is the drop and nothing else.

    It is also what the cheapest answer costs: a solution that only wants to
    stand somewhere and look still pays to come down there.
    """
    x, y = AWAY
    costs = []
    for z in (PUSH_HEIGHT, 0.10, 0.20, TRAVEL_HEIGHT):
        cost = clock.path_seconds(_path((x, y, z, 0.0)))
        assert cost == pytest.approx((TRAVEL_HEIGHT - z) / DESCEND_SPEED)
        costs.append(cost)
    # The lower the first waypoint, the further the jaw has to come down.
    assert costs == sorted(costs, reverse=True)
    assert costs[-1] == 0.0


def test_an_empty_path_is_refused_as_the_bench_refuses_it():
    with pytest.raises(ValueError):
        clock.path_seconds(())
    with pytest.raises(ValueError):
        clock.path_seconds(Chunk(0, (), (0.0, 0.0)))


def test_a_chunk_and_the_bare_waypoints_of_one_cost_the_same():
    """The runner prices a solution's answer; a diagram or a test prices a bare path."""
    path = PATHS["a quarter turn partway along"]
    assert clock.path_seconds(Chunk(0, path, (0.0, 0.0))) == clock.path_seconds(path)
    assert clock.path_seconds(list(path)) == clock.path_seconds(path)


def test_crossing_the_table_rises_with_the_distance_and_is_free_when_the_jaw_is_there():
    """What a look from the far corner costs before it costs anything else."""
    x, y = AWAY
    stands = Waypoint(x, y, PUSH_HEIGHT, 0.0)
    assert clock.crossing_seconds(stands, stands) == 0.0

    seconds = []
    for far in (0.0, 0.02, 0.05, 0.10, 0.20):
        across = Waypoint(x + far, y, PUSH_HEIGHT, 0.0)
        assert clock.crossing_seconds(stands, across) == pytest.approx(far / TOP_SPEED)
        # The arm takes as long coming back as it took going.
        assert clock.crossing_seconds(across, stands) == pytest.approx(far / TOP_SPEED)
        seconds.append(clock.crossing_seconds(stands, across))
    assert seconds == sorted(seconds)
    assert seconds[0] == 0.0

    # Height is not part of a crossing: the jaw crosses at travel height, and
    # the climb and the drop are already charged with the paths they belong to.
    overhead = Waypoint(x, y, TRAVEL_HEIGHT, 0.0)
    assert clock.crossing_seconds(stands, overhead) == 0.0


def test_the_home_pose_is_where_the_bench_really_stands_its_jaw(table):
    """The one number in this module copied out of problem 3 rather than imported.

    Problem 3 writes its park spot as a literal, in the world and again in the
    lift, so it cannot be borrowed through ``partners``. This is what keeps the
    copy honest: the flat spot has to be where the bench really puts the jaw,
    both before a table starts and after an action ends.
    """
    parked = table.data.mocap_pos[0]
    assert (clock.HOME.x, clock.HOME.y) == pytest.approx((parked[0], parked[1]))
    _clear_run(table, PATHS["legs short enough to take one waypoint period each"])
    moved_on = table.data.mocap_pos[0]
    assert (clock.HOME.x, clock.HOME.y) == pytest.approx((moved_on[0], moved_on[1]))
    # Its height is travel height and not the parked height, because a solution
    # is shown this pose and may write a path from it.
    assert PUSH_HEIGHT <= clock.HOME.z <= TRAVEL_HEIGHT


def test_looking_and_pushing_draw_on_the_one_budget(table):
    """There is no free look. A path to see from is charged like any other path."""
    x, y = AWAY
    look = _path((x, y, TRAVEL_HEIGHT - 0.01, 0.0))
    push = PATHS["legs short enough to take one waypoint period each"]
    arm = clock.Clock(budget=20.0)

    # What the runner asks before it hands a path over, and what it charges
    # afterwards: an estimate first, then the record of what really happened.
    assert arm.enough_for(look) and arm.enough_for(push)
    seeing, pushing = _clear_run(table, look), _clear_run(table, push)
    looked, pushed = arm.charge(seeing), arm.charge(pushing)

    assert looked > 0.0 and pushed > 0.0
    # The budget is charged the record, not the plan.
    assert (looked, pushed) == (clock.followed_seconds(seeing), clock.followed_seconds(pushing))
    assert arm.spent == pytest.approx(looked + pushed)
    assert arm.left == pytest.approx(20.0 - looked - pushed)

    # Half the time a path needs is not enough for it; exactly its own seconds are.
    assert not clock.Clock(budget=clock.path_seconds(push) / 2).enough_for(push)
    assert clock.Clock(budget=clock.path_seconds(push)).enough_for(push)
    # But not once the jaw has to come from the other end of the table to it,
    # which is the move the runner has to ask about and then charge.
    corner = Waypoint(*GLASS_AT, TRAVEL_HEIGHT, 0.0)
    tight = clock.Clock(budget=clock.path_seconds(push))
    assert not tight.enough_for(push, frm=corner)
    assert tight.enough_for(push, frm=push[0])  # already standing there
    assert tight.cross(corner, push[0]) == pytest.approx(clock.crossing_seconds(corner, push[0]))
    assert tight.spent == pytest.approx(clock.crossing_seconds(corner, push[0]))
    # Nothing is left owing. An action that ran over the budget ends the run,
    # and a solution is never shown a negative number of seconds.
    assert clock.Clock(budget=1.0, spent=5.0).left == 0.0


def test_a_blocked_path_is_not_charged_for_the_push_it_never_made(table):
    """The reason the charge is read from the record and not from the path.

    Both paths below come down on top of the glass, so the jaw touches it while
    still descending and the cell takes it straight back up. The second path
    then asks for 200 mm of pushing that never happens. The estimate grows by
    those two seconds, because planning has to assume the path will be carried
    out; the charge does not move, because the arm did not move.
    """
    x, y = (float(v) for v in table.position(0))
    down = _path((x, y, PUSH_HEIGHT, 0.0))
    down_and_push = _straight(x, y, PUSH_HEIGHT, -0.005, 40)

    charges = []
    for path in (down, down_and_push):
        felt = table.follow(Chunk(0, path, (0.0, 0.0)))
        # Touched on the way down, so nothing was pushed and nothing of the
        # path across the table was carried out.
        assert felt.blocked and felt.touched is None and felt.pushed == 0.0
        charges.append(clock.followed_seconds(table.records[-1]))

    # The same motion really happened both times: down until the glass stopped
    # it, and back up again.
    assert charges[1] == pytest.approx(charges[0], abs=WAYPOINT_PERIOD)
    # The estimate, meanwhile, grew by the forty legs that were asked for.
    assert clock.path_seconds(down_and_push) - clock.path_seconds(down) == pytest.approx(2.0)
    # So the path that was stopped early is charged a fraction of its estimate.
    assert charges[1] < clock.path_seconds(down_and_push) / 2
    assert charges[1] < clock.path_seconds(down)
