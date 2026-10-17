"""The check a solution runs over its own answer before the cell carries it out."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from keeping_clear import (
    BETWEEN_THE_HEIGHTS,
    CLEAR_ROOM,
    DRIVES_INTO_ANOTHER,
    MEETS_ANOTHER,
    MISSES_ITS_GLASS,
    UNTESTED,
    WOULD_TIP,
    Shoves,
    a_look,
    driven_home,
    kept_clear,
    may_tip,
    meets,
    met_by,
    squared_off,
    travels_between_the_heights,
    where_it_would_land,
    why_not_clear,
)
from open_run import interlocked
from partners import JAW_HALF_HEIGHT, PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Seen, Waypoint, has_room

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


def _push_at(glass: Seen, from_distance: float = 0.060, way: int = 1) -> Chunk:
    """A path that comes down behind a glass and shoves it along the table.

    It starts outside the glass, comes straight down, and then drives into it,
    which is the shape every push in this problem has. ``way`` is which side it
    comes from, so a test can shove a glass towards its neighbour or away from
    it, and those are two different answers.
    """
    start = (glass.x - way * from_distance, glass.y)
    over = Waypoint(start[0], start[1], TRAVEL_HEIGHT, 0.0)
    down = Waypoint(start[0], start[1], PUSH_HEIGHT, 0.0)
    shove = _along(start, (glass.x + way * 0.020, glass.y), PUSH_HEIGHT)
    return Chunk(glass=glass.id, waypoints=(over, down, *shove.waypoints), aim=(glass.x, glass.y))


def test_a_path_at_travel_height_is_left_alone():
    # Nothing on the table reaches travel height, so a path that stays there is
    # safe whatever it passes over, and the check has to say so without being
    # told which glasses are about.
    path = _along((0.40, -0.30), (0.70, 0.10), TRAVEL_HEIGHT)
    answer, why, _ = kept_clear(path, [WIDE_FOOT, NARROW_FOOT, TALL])
    assert why == ""
    assert answer is path


def test_a_sweep_over_the_glasses_is_pulled_up_out_of_the_way():
    # The failure this module exists for. The path's own numbers stay well above
    # the height a push happens at, so a solution reading its own answer would
    # call it a look, while the fingers hanging below the middle of the hand
    # drag through the top of a glass standing in the way.
    #
    # It names no glass, so there is nothing it could have meant to touch, and
    # every waypoint goes up. Where it travels is kept, because that is what the
    # solution asked for and the next picture is taken from there.
    sweeping = TALL.height + JAW_HALF_HEIGHT - 0.030
    assert sweeping > PUSH_HEIGHT
    path = _along((0.40, TALL.y), (0.75, TALL.y), sweeping)
    answer, why, pulled = kept_clear(path, [TALL])
    assert (why, pulled) == ("", True)
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)
    assert [(point.x, point.y) for point in answer.waypoints] == [
        (point.x, point.y) for point in path.waypoints
    ]
    assert not met_by(answer, [TALL])


def test_a_push_at_the_glass_it_names_is_left_alone():
    # The other glass stands across the line of the push, so neither the hand nor
    # the glass being shoved goes anywhere near it.
    aside = replace(TALL, id=7, x=WIDE_FOOT.x, y=WIDE_FOOT.y - 0.200)
    answer, why, _ = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT, aside], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert why == ""
    assert min(point.z for point in answer.waypoints) == PUSH_HEIGHT


def test_a_push_that_would_drive_its_glass_into_another_is_raised():
    # The half of the rule the hand cannot see. The glass ahead is far enough
    # that the hand never reaches it, so every check about the hand passes, and
    # the glass being shoved arrives closer to it than two glasses may stand. The
    # one that would break is the one nobody aimed at.
    ahead = replace(TALL, id=8, x=WIDE_FOOT.x + 0.090)
    shove = _push_at(WIDE_FOOT)
    assert not met_by(shove, [ahead])
    answer, why, _ = kept_clear(
        shove, [WIDE_FOOT, ahead], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert why == DRIVES_INTO_ANOTHER
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_glass_that_already_stands_close_may_still_be_moved():
    # The draw leaves some glasses nearly touching, and those are the glasses the
    # task is about. So the rule is not a fixed gap: a glass may be moved while it
    # stands closer than two glasses need, as long as it ends no closer than it
    # began. Here the neighbour sits across the line of the push, so the shove
    # leaves the two exactly as close as they were.
    across = replace(TALL, id=9, x=WIDE_FOOT.x, y=WIDE_FOOT.y - 0.070)
    needed = across.widest / 2 + WIDE_FOOT.widest / 2 + 2 * CLEAR_ROOM
    assert math.dist((across.x, across.y), (WIDE_FOOT.x, WIDE_FOOT.y)) < needed
    answer, why, _ = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT, across], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert why == ""
    assert min(point.z for point in answer.waypoints) == PUSH_HEIGHT

    # Straight at it is still refused, because that is getting closer.
    ahead = replace(TALL, id=10, x=WIDE_FOOT.x + 0.076)
    _, towards, _ = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT, ahead], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert towards == DRIVES_INTO_ANOTHER


def test_where_a_pushed_glass_lands_is_where_the_fingertips_stop():
    # The model of what a push does, which is the reference solution's own: while
    # the fingers are down they drive the glass ahead of them, and the fingertips
    # never get past where the glass's middle lands.
    shove = _push_at(WIDE_FOOT)
    landed = where_it_would_land(shove, WIDE_FOOT)
    assert landed[0] == pytest.approx(WIDE_FOOT.x + 0.020)
    assert landed[1] == pytest.approx(WIDE_FOOT.y)
    # A shove that stops short of the glass moves it nowhere rather than
    # backwards, and a path that never comes down moves it nowhere at all.
    short = _along((WIDE_FOOT.x - 0.20, WIDE_FOOT.y), (WIDE_FOOT.x - 0.10, WIDE_FOOT.y), PUSH_HEIGHT)
    assert where_it_would_land(short, WIDE_FOOT) == (WIDE_FOOT.x, WIDE_FOOT.y)
    high = _along((WIDE_FOOT.x - 0.20, WIDE_FOOT.y), (WIDE_FOOT.x + 0.10, WIDE_FOOT.y), TRAVEL_HEIGHT)
    assert where_it_would_land(high, WIDE_FOOT) == (WIDE_FOOT.x, WIDE_FOOT.y)


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
    answer, why, _ = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT, between], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert why == MEETS_ANOTHER
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_push_at_a_glass_that_would_tip_is_raised():
    # The cell's interlock would refuse this path, so the arm would not move and
    # the solution would be handed the same table back. Catching it first costs
    # nothing and leaves the solution free to spend the answer on something else.
    answer, why, _ = kept_clear(
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


def test_a_path_below_travel_height_is_lifted_even_where_nothing_stands():
    # A glass the arm has not looked at yet is in no list, so a path that comes
    # down over bare table has not been shown to be over bare table. The rule is
    # the cell's own travel height and not the tallest glass measured so far.
    over_everything = TALL.height + JAW_HALF_HEIGHT + 0.005
    assert over_everything < TRAVEL_HEIGHT
    path = _along((0.40, 0.10), (0.70, 0.10), over_everything)
    answer, why, pulled = kept_clear(path, [TALL])
    assert (why, pulled) == ("", True)
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_push_that_never_reaches_the_glass_it_names_is_raised():
    # Naming a glass is not aiming at one. A path that comes down far away from
    # the glass in its own name tells nobody anything about what it would hit.
    away = Chunk(
        glass=WIDE_FOOT.id,
        waypoints=_along((WIDE_FOOT.x + 0.30, 0.10), (WIDE_FOOT.x + 0.40, 0.10), PUSH_HEIGHT).waypoints,
        aim=(WIDE_FOOT.x, WIDE_FOOT.y),
    )
    answer, why, _ = kept_clear(away, [WIDE_FOOT], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,))
    assert why == MISSES_ITS_GLASS
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_path_that_crosses_its_own_glass_high_up_is_pulled_down_to_its_foot():
    # The failure that cost the first held-out walk its glasses, and the repair
    # that turns it into a usable answer. The path names the glass it crosses and
    # crosses nothing else, and the hand would arrive at that glass sideways near
    # its rim and tip it rather than move it.
    #
    # Because the fingers are below the top of the glass it names, the solution
    # plainly meant to touch that glass, so the path is pulled down to the height
    # where a shove goes through the foot. It still reaches the glass it names
    # and still meets no other, so that is the answer: the same intention, at the
    # one height the cell has a rule for.
    sweeping = TALL.height + JAW_HALF_HEIGHT - 0.030
    across = _along((TALL.x - 0.15, TALL.y), (TALL.x + 0.15, TALL.y), sweeping)
    naming = Chunk(glass=TALL.id, waypoints=across.waypoints, aim=(TALL.x, TALL.y))
    assert met_by(naming, [TALL]) == (TALL.id,)
    answer, why, pulled = kept_clear(naming, [TALL], target=TALL.id, tested=(TALL.id,))
    assert (why, pulled) == ("", True)
    assert all(point.z == PUSH_HEIGHT for point in answer.waypoints)
    assert met_by(answer, [TALL]) == (TALL.id,)


def test_a_sweep_that_would_still_meet_a_second_glass_is_raised_after_pulling():
    # Pulling a path onto the two heights cannot make a bad aim good, and this is
    # the case that proves it. The sweep names one glass and passes over another
    # on its way, so the pulled path meets a glass nobody chose and the answer
    # becomes a look. The reason reported is the one that finally stopped it --
    # the second glass -- and not the height it was drawn at, because a run's
    # record is there to say which rule a solution keeps falling foul of.
    second = replace(TALL, id=9, x=TALL.x - 0.10)
    sweeping = TALL.height + JAW_HALF_HEIGHT - 0.030
    across = _along((TALL.x - 0.15, TALL.y), (TALL.x + 0.15, TALL.y), sweeping)
    naming = Chunk(glass=TALL.id, waypoints=across.waypoints, aim=(TALL.x, TALL.y))
    answer, why, pulled = kept_clear(naming, [TALL, second], target=TALL.id, tested=(TALL.id,))
    assert (why, pulled) == (MEETS_ANOTHER, False)
    # Drawn, it failed on its height; what it could not be repaired past is the
    # other glass, and that is what is reported.
    assert why_not_clear(naming, [TALL, second], target=TALL.id) == BETWEEN_THE_HEIGHTS
    assert all(point.z == TRAVEL_HEIGHT for point in answer.waypoints)


def test_a_corner_is_put_in_where_a_path_comes_down_while_it_is_still_moving():
    # A jaw moving sideways while it comes down is how a rim gets clipped, so a
    # stretch that both travels and descends becomes two stretches: across at the
    # upper height, then straight down.
    start = Waypoint(TALL.x - 0.20, TALL.y, TRAVEL_HEIGHT, 0.0)
    slanting = Waypoint(TALL.x - 0.02, TALL.y, PUSH_HEIGHT, 0.0)
    squared = squared_off(Chunk(glass=TALL.id, waypoints=(start, slanting), aim=(TALL.x, TALL.y)), TALL)
    assert len(squared.waypoints) == 3
    corner = squared.waypoints[1]
    assert (corner.x, corner.y, corner.z) == (slanting.x, slanting.y, TRAVEL_HEIGHT)
    assert not travels_between_the_heights(squared)


def test_a_glass_nothing_has_tested_may_be_touched_but_not_driven():
    """The rule the toppled glasses put here, and the discipline the teacher keeps.

    The tipping rule has three answers, and measured over the glasses this cell
    draws it never gives the first: a foot would have to be over a hundred
    millimetres across to slide for certain and the widest the draw makes is
    ninety-four. So every glass on every table is one whose behaviour turns on a
    friction nothing here can see, and the rule's own words say a probe is safe
    while a push at the task is a gamble.

    So a shove that would *move* a glass is allowed only at a glass something has
    already watched move, and a shove that only comes to rest against one is
    allowed at any glass. That is what tells a probe from a push here, and it is
    read off what the path would do rather than off how long it is.
    """
    assert may_tip(WIDE_FOOT), "every glass this cell draws is one the rule is unsure about"

    driving = _push_at(WIDE_FOOT)
    _, why, _ = kept_clear(driving, [WIDE_FOOT], target=WIDE_FOOT.id)
    assert why == UNTESTED

    # The same shove, once this solution has watched that glass move.
    answer, why, _ = kept_clear(driving, [WIDE_FOOT], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,))
    assert why == ""
    assert answer is driving

    # A probe comes to rest against the glass rather than driving it, so it needs
    # no evidence: it is how the evidence is got.
    edge = WIDE_FOOT.x - WIDE_FOOT.widest / 2
    over = Waypoint(edge - 0.060, WIDE_FOOT.y, TRAVEL_HEIGHT, 0.0)
    down = Waypoint(edge - 0.060, WIDE_FOOT.y, PUSH_HEIGHT, 0.0)
    touch = _along((edge - 0.060, WIDE_FOOT.y), (edge, WIDE_FOOT.y), PUSH_HEIGHT)
    probe = Chunk(
        glass=WIDE_FOOT.id, waypoints=(over, down, *touch.waypoints), aim=(WIDE_FOOT.x, WIDE_FOOT.y)
    )
    assert meets(probe, WIDE_FOOT)
    _, why, _ = kept_clear(probe, [WIDE_FOOT], target=WIDE_FOOT.id)
    assert why == ""


def test_the_evidence_is_the_glass_having_moved_further_than_the_camera_can_err():
    """What ``tested`` means, kept in one place so three solutions agree about it."""
    shoves = Shoves()
    shoves.saw([WIDE_FOOT])
    assert shoves.tested([WIDE_FOOT]) == ()

    # Aimed at, but it has not moved: no evidence either way.
    shoves.aimed_at(WIDE_FOOT.id)
    assert shoves.tested([WIDE_FOOT]) == ()

    # Moved by less than the camera's own error: still not shown to have moved.
    barely = replace(WIDE_FOOT, x=WIDE_FOOT.x + CLEAR_ROOM / 2)
    assert shoves.tested([barely]) == ()

    # Moved further than that, so it slides.
    slid = replace(WIDE_FOOT, x=WIDE_FOOT.x + 0.005)
    assert shoves.tested([slid]) == (WIDE_FOOT.id,)

    # A glass that moved but was never aimed at says nothing about this solution:
    # something else moved it.
    untouched = Shoves()
    untouched.saw([WIDE_FOOT])
    assert untouched.tested([slid]) == ()


def test_the_stretch_that_drives_along_the_table_is_made_straight():
    """The last thing that was toppling glasses, and it is the shape and not the place.

    The cell turns the hand to each leg's own heading as that leg starts, so a
    driving stretch that wanders turns the hand while the fingers are against the
    glass, and a glass twisted at the foot goes over rather than sliding. The
    reference solution's shove is straight at one heading; a drawn one strays a
    few millimetres. So the stretch is replaced by the straight line between its
    own ends, and the glass, the direction, the distance and the number of
    waypoints are all left as the solution chose them.
    """
    edge = WIDE_FOOT.x - WIDE_FOOT.widest / 2
    over = Waypoint(edge - 0.060, WIDE_FOOT.y, TRAVEL_HEIGHT, 0.6)
    down = Waypoint(edge - 0.060, WIDE_FOOT.y, PUSH_HEIGHT, 0.6)
    # A driving stretch that wanders off the line between its own ends, the way a
    # drawn one does.
    wandering = tuple(
        Waypoint(
            edge - 0.060 + 0.010 * step,
            WIDE_FOOT.y + (0.008 if step % 2 else -0.008),
            PUSH_HEIGHT,
            0.6 + 0.05 * step,
        )
        for step in range(9)
    )
    drawn = Chunk(glass=WIDE_FOOT.id, waypoints=(over, down, *wandering), aim=(WIDE_FOOT.x, WIDE_FOOT.y))
    straightened = squared_off(drawn, WIDE_FOOT)

    low = [point for point in straightened.waypoints if point.z == PUSH_HEIGHT]
    # The waypoint the hand comes down at is already at the pushing height, so it
    # is the start of the stretch and is counted in it.
    assert len(low) == 1 + len(wandering)
    # Every point of it is on the line between its own ends, and the hand holds
    # one heading all the way along.
    first, last = low[0], low[-1]
    assert (first.x, first.y) == pytest.approx((down.x, down.y))
    assert (last.x, last.y) == pytest.approx((wandering[-1].x, wandering[-1].y))
    want = math.atan2(last.y - first.y, last.x - first.x)
    assert all(point.heading == pytest.approx(want) for point in low)
    for point in low:
        assert _off_the_line(point, first, last) < 1e-9
    # The hand is already turned the way it will push before it comes down, which
    # is the waypoint above the one it comes down at.
    assert straightened.waypoints[0].heading == pytest.approx(want)


def _off_the_line(point: Waypoint, first: Waypoint, last: Waypoint) -> float:
    """How far a waypoint is from the straight line between two others."""
    return abs(
        (last.x - first.x) * (point.y - first.y) - (last.y - first.y) * (point.x - first.x)
    ) / math.dist((first.x, first.y), (last.x, last.y))


def test_a_look_that_wanders_is_left_where_it_wanders():
    """Only a driving stretch is straightened, because only it touches a glass.

    Where a look goes is the solution's own business and the next picture is taken
    from the end of it, so its route is kept exactly and only its height changes.
    """
    wandering = tuple(
        Waypoint(0.40 + 0.02 * step, -0.30 + (0.01 if step % 2 else -0.01), 0.20, 0.3)
        for step in range(6)
    )
    drawn = Chunk(glass=0, waypoints=wandering, aim=(0.5, -0.3))
    lifted = squared_off(drawn)
    assert [(point.x, point.y) for point in lifted.waypoints] == [
        (point.x, point.y) for point in wandering
    ]
    assert all(point.z == TRAVEL_HEIGHT for point in lifted.waypoints)


def test_a_push_is_carried_on_until_its_glass_has_room():
    """The distance is arithmetic because the distance is below a drawn path's accuracy.

    The shove here stops at the near edge of the glass, which moves it nowhere,
    and that is what the fitted solutions drew: measured over twenty tables their
    shoves moved their glass a median of zero millimetres. The model's choice of
    glass and direction is kept and the shove is carried on along that same line
    until the glass has the room it needs to be picked up.
    """
    # Close enough across the line of the push that the glass has no room, and
    # far enough off that line that neither the hand nor the glass goes near it.
    crowding = replace(TALL, id=30, x=WIDE_FOOT.x, y=WIDE_FOOT.y - 0.090)
    assert not has_room(WIDE_FOOT.x, WIDE_FOOT.y, [(crowding.x, crowding.y, crowding.widest)])
    edge = WIDE_FOOT.x - WIDE_FOOT.widest / 2
    over = Waypoint(edge - 0.060, WIDE_FOOT.y, TRAVEL_HEIGHT, 0.0)
    down = Waypoint(edge - 0.060, WIDE_FOOT.y, PUSH_HEIGHT, 0.0)
    touch = _along((edge - 0.060, WIDE_FOOT.y), (edge, WIDE_FOOT.y), PUSH_HEIGHT)
    stopping = Chunk(
        glass=WIDE_FOOT.id, waypoints=(over, down, *touch.waypoints), aim=(WIDE_FOOT.x, WIDE_FOOT.y)
    )
    assert where_it_would_land(stopping, WIDE_FOOT) == (WIDE_FOOT.x, WIDE_FOOT.y)

    answer, moved = driven_home(
        stopping, [WIDE_FOOT, crowding], WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert moved > 0.0
    # It stops once the glass has room rather than carrying on for ever.
    landed = where_it_would_land(answer, WIDE_FOOT)
    assert has_room(*landed, [(crowding.x, crowding.y, crowding.widest)])
    # The line it was shoved along is the line the model drew.
    assert landed[1] == pytest.approx(WIDE_FOOT.y)
    assert landed[0] > WIDE_FOOT.x
    # And it is still an answer the whole rule accepts.
    assert why_not_clear(answer, [WIDE_FOOT, crowding], WIDE_FOOT.id, tested=(WIDE_FOOT.id,)) == ""


def test_a_push_is_not_carried_on_into_a_glass_that_is_in_the_way():
    """Nothing is added that the rule would not accept, so a crowded line stops early."""
    ahead = replace(TALL, id=31, x=WIDE_FOOT.x + 0.090)
    edge = WIDE_FOOT.x - WIDE_FOOT.widest / 2
    over = Waypoint(edge - 0.060, WIDE_FOOT.y, TRAVEL_HEIGHT, 0.0)
    down = Waypoint(edge - 0.060, WIDE_FOOT.y, PUSH_HEIGHT, 0.0)
    touch = _along((edge - 0.060, WIDE_FOOT.y), (edge, WIDE_FOOT.y), PUSH_HEIGHT)
    stopping = Chunk(
        glass=WIDE_FOOT.id, waypoints=(over, down, *touch.waypoints), aim=(WIDE_FOOT.x, WIDE_FOOT.y)
    )
    answer, moved = driven_home(
        stopping, [WIDE_FOOT, ahead], WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
    assert why_not_clear(answer, [WIDE_FOOT, ahead], WIDE_FOOT.id, tested=(WIDE_FOOT.id,)) == ""
    # The glass ahead is never driven into, so the shove stops short of freeing
    # this one, and the answer says so by how little it would move it.
    assert moved < 0.076


def test_an_answer_the_rule_refuses_is_not_carried_on_at_all():
    """A shove nobody could account for is not made longer; it is left for the rule to raise."""
    away = Chunk(
        glass=WIDE_FOOT.id,
        waypoints=_along((WIDE_FOOT.x + 0.30, 0.10), (WIDE_FOOT.x + 0.40, 0.10), PUSH_HEIGHT).waypoints,
        aim=(WIDE_FOOT.x, WIDE_FOOT.y),
    )
    answer, moved = driven_home(away, [WIDE_FOOT], WIDE_FOOT.id, tested=(WIDE_FOOT.id,))
    assert answer is away
    assert moved == 0.0


def test_a_push_that_meets_its_glass_down_at_the_pushing_height_is_left_alone():
    # The other side of the same rule: the shape every push in this problem has
    # -- come down outside the glass, then drive into it along the table -- meets
    # its glass only while the hand is down, and has to pass.
    answer, why, _ = kept_clear(
        _push_at(WIDE_FOOT), [WIDE_FOOT], target=WIDE_FOOT.id, tested=(WIDE_FOOT.id,)
    )
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
