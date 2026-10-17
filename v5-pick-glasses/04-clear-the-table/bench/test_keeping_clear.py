"""The check a solution runs over its own answer before the cell carries it out."""

from __future__ import annotations

import math

from keeping_clear import (
    BETWEEN_THE_HEIGHTS,
    CLEAR_ROOM,
    MEETS_ANOTHER,
    MISSES_ITS_GLASS,
    WOULD_TIP,
    a_look,
    kept_clear,
    met_by,
    travels_between_the_heights,
    why_not_clear,
)
from open_run import interlocked
from partners import JAW_HALF_HEIGHT, PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Seen, Waypoint

# A glass with a wide foot, which the tipping rule lets anybody push, and a
# narrow-footed one, which it refuses. Both are drawn here rather than measured
# from a table so that a test says which case it is about; the rule itself is
# tested where it lives, in problem 3.
WIDE_FOOT = Seen(id=0, x=0.50, y=-0.20, height=0.150, widest=0.070, foot=0.070, standing=True)
NARROW_FOOT = Seen(id=1, x=0.50, y=-0.05, height=0.200, widest=0.080, foot=0.020, standing=True)
TALL = Seen(id=2, x=0.60, y=-0.20, height=0.220, widest=0.075, foot=0.070, standing=True)


def _along(start: tuple[float, float], end: tuple[float, float], z: float) -> Chunk:
    """A straight path from one place to another at one height, ten millimetres a step."""
    length = math.dist(start, end)
    heading = math.atan2(end[1] - start[1], end[0] - start[0])
    steps = max(1, math.ceil(length / 0.010))
    points = tuple(
        Waypoint(
            start[0] + part * (end[0] - start[0]),
            start[1] + part * (end[1] - start[1]),
            z,
            heading,
        )
        for part in (step / steps for step in range(steps + 1))
    )
    return Chunk(glass=0, waypoints=points, aim=end)


def _push_at(glass: Seen, from_distance: float = 0.060) -> Chunk:
    """A path that comes down behind a glass and shoves it along the table.

    It starts outside the glass, comes straight down, and then drives into it,
    which is the shape every push in this problem has.
    """
    start = (glass.x - from_distance, glass.y)
    over = Waypoint(start[0], start[1], TRAVEL_HEIGHT, 0.0)
    down = Waypoint(start[0], start[1], PUSH_HEIGHT, 0.0)
    shove = _along(start, (glass.x + 0.020, glass.y), PUSH_HEIGHT)
    return Chunk(glass=glass.id, waypoints=(over, down, *shove.waypoints), aim=(glass.x, glass.y))


def test_a_path_at_travel_height_is_left_alone():
    # Nothing on the table reaches travel height, so a path that stays there is
    # safe whatever it passes over, and the check has to say so without being
    # told which glasses are about.
    path = _along((0.40, -0.30), (0.70, 0.10), TRAVEL_HEIGHT)
    answer, why = kept_clear(path, [WIDE_FOOT, NARROW_FOOT, TALL])
    assert why == ""
    assert answer is path


def test_a_sweep_over_the_glasses_is_raised():
    # The failure this module exists for. The path's own numbers stay well above
    # the height a push happens at, so a solution reading its own answer would
    # call it a look, while the fingers hanging below the middle of the hand
    # drag through the top of a glass standing in the way.
    sweeping = TALL.height + JAW_HALF_HEIGHT - 0.030
    assert sweeping > PUSH_HEIGHT
    path = _along((0.40, TALL.y), (0.75, TALL.y), sweeping)
    answer, why = kept_clear(path, [TALL])
    assert why == BETWEEN_THE_HEIGHTS
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_push_at_the_glass_it_names_is_left_alone():
    answer, why = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT, TALL], target=WIDE_FOOT.id
    )
    assert why == ""
    assert min(point.z for point in answer.waypoints) == PUSH_HEIGHT


def test_a_push_that_would_sweep_a_second_glass_is_raised():
    # The push is aimed at the far glass and the near one stands on the way to
    # it, so the hand reaches a glass nobody chose to move.
    between = Seen(
        id=3,
        x=WIDE_FOOT.x - 0.030,
        y=WIDE_FOOT.y,
        height=0.150,
        widest=0.070,
        foot=0.070,
        standing=True,
    )
    answer, why = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT, between], target=WIDE_FOOT.id
    )
    assert why == MEETS_ANOTHER
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_push_at_a_glass_that_would_tip_is_raised():
    # The cell's interlock would refuse this path, so the arm would not move and
    # the solution would be handed the same table back. Catching it first costs
    # nothing and leaves the solution free to spend the answer on something else.
    answer, why = kept_clear(
        _push_at(NARROW_FOOT), [NARROW_FOOT], target=NARROW_FOOT.id
    )
    assert why == WOULD_TIP
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_raising_a_path_keeps_where_it_went():
    path = _along((0.40, -0.30), (0.70, 0.10), 0.120)
    raised = a_look(path)
    assert len(raised.waypoints) == len(path.waypoints)
    for before, after in zip(path.waypoints, raised.waypoints, strict=True):
        assert (after.x, after.y, after.heading) == (before.x, before.y, before.heading)
        assert after.z == TRAVEL_HEIGHT


def test_the_room_widens_what_counts_as_a_meeting():
    # A reading is a millimetre or two out, so the check grows every glass before
    # asking whether the hand reaches it. What that is worth is exactly the room:
    # the line between a meeting and a miss moves out by that much and no more.
    grazing = _along((0.45, -0.20), (0.65, -0.20), PUSH_HEIGHT)

    def first_miss(room: float) -> float:
        """The smallest sideways offset at which this path misses the glass."""
        for tenth_mm in range(0, 2000):
            offset = tenth_mm / 10000
            beside = Seen(
                id=4,
                x=0.55,
                y=-0.20 + offset,
                height=0.150,
                widest=0.070,
                foot=0.070,
                standing=True,
            )
            if not met_by(grazing, [beside], room=room):
                return offset
        raise AssertionError("the path misses the glass somewhere within 200 mm")

    assert math.isclose(first_miss(CLEAR_ROOM) - first_miss(0.0), CLEAR_ROOM, abs_tol=1e-9)


def test_a_path_the_check_passes_is_a_path_the_cell_would_carry_out():
    # The two have to agree in one direction: everything this check lets through
    # is something the cell's interlock also lets through. Otherwise a solution
    # would spend answers on paths the arm never moves for.
    glasses = [WIDE_FOOT, NARROW_FOOT, TALL]
    for target in glasses:
        path = _push_at(target)
        if why_not_clear(path, glasses, target=target.id):
            continue
        assert interlocked(path, glasses) is None


def test_a_path_below_travel_height_is_raised_even_where_nothing_stands():
    # A glass the arm has not looked at yet is in no list, so a path that comes
    # down over bare table has not been shown to be over bare table. The rule is
    # the cell's own travel height and not the tallest glass measured so far.
    over_everything = TALL.height + JAW_HALF_HEIGHT + 0.005
    assert over_everything < TRAVEL_HEIGHT
    path = _along((0.40, 0.10), (0.70, 0.10), over_everything)
    answer, why = kept_clear(path, [TALL])
    assert why == BETWEEN_THE_HEIGHTS
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_push_that_never_reaches_the_glass_it_names_is_raised():
    # Naming a glass is not aiming at one. A path that comes down far away from
    # the glass in its own name tells nobody anything about what it would hit.
    away = Chunk(
        glass=WIDE_FOOT.id,
        waypoints=_along((WIDE_FOOT.x + 0.30, 0.10), (WIDE_FOOT.x + 0.40, 0.10), PUSH_HEIGHT).waypoints,
        aim=(WIDE_FOOT.x, WIDE_FOOT.y),
    )
    answer, why = kept_clear(away, [WIDE_FOOT], target=WIDE_FOOT.id)
    assert why == MISSES_ITS_GLASS
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_path_that_crosses_its_own_glass_high_up_is_raised():
    # The failure that cost the first held-out walk its glasses. The path names
    # the glass it crosses and crosses nothing else, so counting glasses passes
    # it, while the hand arrives at that glass sideways near its rim and tips it
    # rather than sliding it.
    sweeping = TALL.height + JAW_HALF_HEIGHT - 0.030
    across = _along((TALL.x - 0.15, TALL.y), (TALL.x + 0.15, TALL.y), sweeping)
    naming = Chunk(glass=TALL.id, waypoints=across.waypoints, aim=(TALL.x, TALL.y))
    assert met_by(naming, [TALL]) == (TALL.id,)
    answer, why = kept_clear(naming, [TALL], target=TALL.id)
    assert why == BETWEEN_THE_HEIGHTS
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_push_that_meets_its_glass_down_at_the_pushing_height_is_left_alone():
    # The other side of the same rule: the shape every push in this problem has
    # -- come down outside the glass, then drive into it along the table -- meets
    # its glass only while the hand is down, and has to pass.
    answer, why = kept_clear(_push_at(WIDE_FOOT), [WIDE_FOOT], target=WIDE_FOOT.id)
    assert why == ""
    assert answer.waypoints[-1].z == PUSH_HEIGHT


def test_a_path_that_only_comes_straight_down_is_judged_on_what_it_reaches():
    # Coming down is not travelling, and the cell watches the force all the way
    # down and backs the hand off the moment it touches anything. So a descent
    # is allowed at any height, and what decides such a path is the ordinary
    # question of which glasses the hand would reach.
    straight_down = Chunk(
        glass=WIDE_FOOT.id,
        waypoints=tuple(
            Waypoint(WIDE_FOOT.x - 0.060, WIDE_FOOT.y, z, 0.0)
            for z in (TRAVEL_HEIGHT, 0.200, 0.120, PUSH_HEIGHT)
        ),
        aim=(WIDE_FOOT.x, WIDE_FOOT.y),
    )
    assert not travels_between_the_heights(straight_down)
