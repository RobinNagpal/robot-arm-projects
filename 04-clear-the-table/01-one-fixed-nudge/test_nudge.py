"""The tour, the paths, the memory and the whole loop, on glasses drawn across their range.

Two of these run the real cell and the rest run a paper one. The paper cell is
``_Paper`` below: it answers the same questions ``open_run`` asks of a work cell
and lands a pushed glass exactly where the push aimed. That is not physics and
is not meant to be -- it is there so that the deciding, the remembering and the
saying-done can be tested in milliseconds, without a graphics context, and
without waiting for the simulator on a machine that is busy.
"""

from __future__ import annotations

import math

import jaw_paths
import numpy as np
import pytest
import tour
from nudge import FRAMES_ALLOWED, KEPT_UP, ROOM_MARGIN, OneFixedNudge
from nudge import _furthest as furthest_reach
from remembered import Remembered
from work_cell.glasses.shapes import KIND_RANGES, family
from work_cell.glasses.spawn import SpawnedGlass
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

import tables
import wrist
from clock import LEG_AT_TOP_SPEED, crossing_seconds, path_seconds
from contract import GLASS_OVER, SAID_DONE, Done, Look
from open_run import HOME, clear_table
from partners import (
    FEEL_SPEED,
    PUSH_HEIGHT,
    TEST_SEEDS,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    Chunk,
    Felt,
    Push,
    Record,
    Seen,
    Waypoint,
    has_room,
)
from simulator import Simulator

import plan

# The tables measured on are below this, always. The ones above it are scored
# once and are not for poking at.
TRAINING = 0

KINDS = sorted(KIND_RANGES)


def _seen(i, x, y, widest=0.08, foot=0.09, height=0.15, standing=True):
    return Seen(i, x, y, height, widest, foot, standing)


def _look(seen, jaw=HOME, left=600.0):
    return Look(picture=np.zeros((4, 4, 3), dtype=np.uint8), seen=tuple(seen), jaw=jaw, seconds_left=left)


class _Paper:
    """A work cell made of arithmetic: no physics, no camera, no graphics context.

    It is the same shape as the real cell ``open_run`` builds, and it differs in
    one deliberate way: a push lands the glass exactly where it was aimed. So a
    table it marks as separated says the deciding was right, and says nothing
    at all about whether the arm could really have done it.
    """

    def __init__(self, glasses: list[Seen]) -> None:
        self.standing = {glass.id: glass for glass in glasses}
        self.looks = 0

    def glasses(self) -> int:
        return len(self.standing)

    def view(self, jaw: Waypoint):
        self.looks += 1
        on_table = list(self.standing.values())
        return np.zeros((4, 4, 3), dtype=np.uint8), wrist.in_picture(jaw, on_table)

    def truth(self):
        return tuple(self.standing.values())

    def follow(self, chunk) -> Record:
        last = chunk.waypoints[-1]
        if last.z <= PUSH_HEIGHT + 1e-9 and chunk.glass in self.standing:
            was = self.standing[chunk.glass]
            self.standing[chunk.glass] = Seen(
                was.id, chunk.aim[0], chunk.aim[1], was.height, was.widest, was.foot, True
            )
        return Record(chunk.as_push(), Felt(False, 0.0, False, 0.0, 0.0), chunk.aim, chunk.waypoints)

    def toppled(self) -> int:
        return sum(1 for glass in self.standing.values() if not glass.standing)

    def pickable(self) -> int:
        on_table = list(self.standing.values())
        return sum(
            has_room(glass.x, glass.y, [(o.x, o.y, o.widest) for o in on_table if o.id != glass.id])
            for glass in on_table
        )

    def charged(self) -> float:
        return 0.0


# ------------------------------------------------------------------- the tour


def test_the_tour_can_measure_every_corner_of_the_glass_zone():
    assert tour.survey(), "a tour with no stands in it would never see anything"
    assert tour.uncovered() == [], "the tour leaves part of the zone unmeasured"


def test_every_stand_is_a_pose_the_arm_can_hold_and_a_path_can_name():
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    for stand in tour.survey():
        assert tour.holdable(stand)
        jaw = stand.jaw()
        assert PUSH_HEIGHT <= jaw.z <= TRAVEL_HEIGHT
        assert abs(jaw.x - TABLE_CENTRE_XY[0]) <= half_x and abs(jaw.y - TABLE_CENTRE_XY[1]) <= half_y


@pytest.mark.parametrize("kind", KINDS)
def test_a_glass_whose_foot_is_surveyed_is_in_the_picture_whatever_its_height(kind):
    """Why the tour is built on the foot alone.

    ``tour.surveyed`` asks only whether the point on the table under the glass
    lands in the middle of the picture. That is the cautious question: the foot
    is what fixes a glass's place, and adding the glass's body to the line can
    only put more of it inside the frame. This checks that across the whole
    range of each family, so the tour is good for a tall glass and a squat one
    alike.
    """
    corners = [(x, y) for x in GLASS_ZONE[:2] for y in GLASS_ZONE[2:]]
    middle = ((GLASS_ZONE[0] + GLASS_ZONE[1]) / 2, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2)
    for outline, _ in family(kind, 8, seed=2):
        for x, y in [*corners, middle]:
            for stand in tour.survey():
                if tour.surveyed(stand, x, y):
                    assert wrist.sees(stand.jaw(), x, y, outline.total_height)


def test_the_stand_to_look_at_a_point_from_is_one_that_can_measure_it():
    for x, y in tour.checked():
        stand = tour.nearest(x, y)
        assert tour.surveyed(stand, x, y)


# ------------------------------------------------------------------ the paths


def test_a_look_costs_the_crossing_and_nothing_else():
    stand = tour.survey()[0]
    path = jaw_paths.to_look(stand, glass=0)
    assert len(path.waypoints) == 1
    assert path_seconds(path) == 0.0
    expected = math.dist((HOME.x, HOME.y), (stand.x, stand.y)) / 0.2
    assert crossing_seconds(HOME, path.waypoints[0]) == pytest.approx(expected)


def test_another_frame_from_where_the_jaw_stands_is_free():
    jaw = Waypoint(0.5, -0.3, PUSH_HEIGHT, 1.0)
    path = jaw_paths.stay(jaw, glass=0)
    assert crossing_seconds(jaw, path.waypoints[0]) == 0.0
    assert path_seconds(path) == 0.0


@pytest.mark.parametrize("kind", KINDS)
def test_a_push_path_takes_the_fingertips_to_where_the_glass_should_end_up(kind):
    """The shove has to be long enough to move the glass, and no longer.

    The fingertips come down ``APPROACH_GAP`` behind the glass's edge and stop
    one radius short of where its middle is aimed, so what the glass is given is
    exactly the distance solution 1 asked for. Checked on glasses drawn right
    across each family, because the gap is a fixed number and the radius is not.
    """
    for outline, _ in family(kind, 6, seed=3):
        glass = _seen(0, 0.46, -0.26, widest=outline.max_diameter, foot=2 * outline.radius[0])
        neighbour = _seen(1, 0.46, -0.16, widest=outline.max_diameter)
        pushes = [
            push
            for heading in (0.0, math.pi / 2, math.pi)
            for push in plan.along(glass, [neighbour], heading)
        ]
        assert pushes, "a glass with a single neighbour always has somewhere to go"
        for push in pushes:
            path = jaw_paths.to_push(HOME, push)
            tip = path.waypoints[-1]
            ahead = (math.cos(push.heading), math.sin(push.heading))
            landed = (tip.x + glass.widest / 2 * ahead[0], tip.y + glass.widest / 2 * ahead[1])
            assert math.dist(landed, push.aim) == pytest.approx(0.0, abs=1e-9)


def _feeling_forward(push: Push) -> Chunk:
    """A path that comes down at ``push.start`` and creeps ``push.reach`` forward at the feeling speed."""
    step = FEEL_SPEED * WAYPOINT_PERIOD
    count = math.ceil(push.reach / step)
    dx, dy = step * math.cos(push.heading), step * math.sin(push.heading)
    x, y = push.start
    points = tuple(Waypoint(x + k * dx, y + k * dy, PUSH_HEIGHT, push.heading) for k in range(count + 1))
    return Chunk(push.glass, points, push.aim)


@pytest.mark.parametrize("kind", KINDS)
def test_the_fingertips_are_driven_to_the_glass_and_not_to_its_widest_part(kind):
    """The fault this solution was first written with, pinned so it cannot come back.

    ``plan.along`` puts the touchdown point ``APPROACH_GAP`` outside the glass's
    *widest* part, and problem 3's examiner then creeps forward until its force
    sensor finds the glass -- which on a stemmed glass is 20 mm further in,
    because at the jaw's height the glass is a stem. A chunk cannot creep. The
    first version shoved ``APPROACH_GAP + travel`` regardless, so a five
    millimetre test push never touched a stemmed glass at all, the glass was
    marked as having tipped, and the table was left as it was found.

    So the measurement is made here, against the real cell: how far the
    fingertips really travel from the touchdown point before they meet the
    glass, read off the examiner's own force sensor. The solution has to be told
    that distance, and ``to_push``'s ``reach`` is where it goes.
    """
    for outline, _ in family(kind, 3, seed=11):
        glass = SpawnedGlass("glass_0", kind, outline, (0.48, -0.26, TABLE_TOP_Z), 0.0)
        table = Simulator(0, [glass])
        seen = table.look()[0]
        radius = seen.widest / 2
        # Feel all the way in, as problem 3 does, and see where contact really is.
        asking = Push(0, (seen.x - radius - plan.APPROACH_GAP, seen.y), 0.0,
                      radius + plan.APPROACH_GAP + plan.FEEL_BEYOND, 0.0, (0.0, 0.0))
        met = table.follow(_feeling_forward(asking)).touched
        assert met is not None, "the examiner could not find the glass either"
        # A path told that distance puts the fingertips on the glass, and then
        # the distance asked for beyond it. A path told APPROACH_GAP falls short
        # by the whole difference, which for some families is the whole push.
        asked = 0.030
        path = jaw_paths.to_push(HOME, Push(0, asking.start, 0.0, asking.reach, asked, (0.0, 0.0)), met)
        reached = math.dist(asking.start, (path.waypoints[-1].x, path.waypoints[-1].y))
        assert reached == pytest.approx(met + asked), "told the distance, it drives to the glass and on"
        # Told ``APPROACH_GAP`` instead, the same path stops short by exactly
        # what the glass is narrower at the jaw's height than at its widest.
        assert plan.APPROACH_GAP + asked - met <= asked + 1e-9
        if kind == "stemmed_glass":
            # The case that proves the point: a five millimetre test push with
            # the planner's gap does not reach a stemmed glass at all, so the
            # glass cannot move and "it tipped" is the wrong thing to conclude.
            assert met > plan.APPROACH_GAP + plan.PROBE


@pytest.mark.parametrize("kind", KINDS)
def test_feeling_for_a_glass_never_takes_the_hand_past_the_corridor_the_planner_cleared(kind):
    """The safety bound on reaching deeper, which is what stops a leaning glass going over.

    A camera cannot tell "not touched yet" from "touched, and leaning": the
    glass does not move either way. Reaching deeper on that reading put four
    glasses on their sides. The bound is problem 3's own lean guard, and this
    checks the consequence that matters: however deep the fingertips are driven,
    they stop at or before the point ``plan.along`` checked the hand against,
    which is where the glass's own middle is meant to end up.
    """
    for outline, _ in family(kind, 4, seed=12):
        glass = _seen(0, 0.46, -0.26, widest=outline.max_diameter, foot=2 * outline.radius[0],
                      height=outline.total_height)
        neighbour = _seen(1, 0.46, -0.16, widest=outline.max_diameter)
        furthest = furthest_reach(glass)
        assert furthest >= plan.APPROACH_GAP, "it must at least reach the planner's own gap"
        for push in plan.along(glass, [neighbour], 0.0):
            path = jaw_paths.to_push(HOME, push, furthest)
            tip = path.waypoints[-1]
            # ``aim`` is where the glass's middle should land, and the planner
            # swept the hand all the way there.
            along = (tip.x - push.start[0]) * math.cos(push.heading) + (tip.y - push.start[1]) * math.sin(
                push.heading
            )
            limit = math.dist(push.start, push.aim)
            assert along <= limit + 1e-9


@pytest.mark.parametrize("kind", KINDS)
def test_every_push_path_is_one_the_jaw_could_follow(kind):
    """The heights, the table, the waypoint spacing and the length of the path.

    ``follow()`` refuses a path outside the heights the jaw rides at, off the
    table, or longer than a few hundred waypoints, and a refused path wastes an
    answer without moving the arm. The spacing is checked as well, because a leg
    longer than the jaw can cover in one waypoint period is a leg carried out
    slower than the path asked for.
    """
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    longest = 0
    for outline, _ in family(kind, 6, seed=4):
        glass = _seen(0, 0.46, -0.26, widest=outline.max_diameter, foot=2 * outline.radius[0])
        neighbour = _seen(1, 0.46, -0.16, widest=outline.max_diameter)
        for heading in np.arange(8) * math.pi / 4:
            for push in plan.along(glass, [neighbour], heading):
                points = jaw_paths.to_push(HOME, push).waypoints
                longest = max(longest, len(points))
                for point in points:
                    assert PUSH_HEIGHT - 1e-9 <= point.z <= TRAVEL_HEIGHT + 1e-9
                    assert abs(point.x - TABLE_CENTRE_XY[0]) <= half_x
                    assert abs(point.y - TABLE_CENTRE_XY[1]) <= half_y
                for one, next_one in zip(points, points[1:], strict=False):
                    gap = math.dist((one.x, one.y, one.z), (next_one.x, next_one.y, next_one.z))
                    assert gap <= LEG_AT_TOP_SPEED + 1e-9
    # Well inside what the examiner takes, which is 500. The longest path here is
    # the longest push the chooser will make, sampled a millimetre at a time.
    assert longest < 300


def test_the_examiner_itself_takes_the_paths_this_builds():
    """The one test that asks the simulator rather than arithmetic.

    Everything above checks a path against the rules written down in the examiner.
    This hands two real paths to the real cell, because a rule read out of the
    source and a rule enforced by the code are two different things.
    """
    stand = tour.survey()[0]
    for seed in range(TRAINING, TRAINING + 4):
        table = Simulator(seed, glasses=tables.table(seed))
        table.follow(jaw_paths.to_look(stand, glass=0))
        seen = table.look()
        settled = {glass.id for glass in seen if plan.room(glass, seen, ROOM_MARGIN)}
        push, _ = plan.choose(seen, settled)
        if push is not None:
            table.follow(jaw_paths.to_push(stand.jaw(), push))
            return
    raise AssertionError("none of four training tables offered a push to try the examiner with")


# ----------------------------------------------------------------- the memory


@pytest.mark.parametrize("kind", KINDS)
def test_several_looks_place_a_glass_better_than_one_look(kind):
    """Why the memory averages instead of keeping the newest reading.

    Each look draws its own error, so the mean of several is closer than one.
    Measured over a family of glasses and many draws rather than asserted of a
    single case, because one draw of a random error proves nothing.
    """
    noise = np.random.default_rng(7)
    one, many = [], []
    for outline, _ in family(kind, 10, seed=6):
        truth = (0.48, -0.26)
        for _try in range(10):
            held = Remembered()
            readings = [
                _seen(
                    0,
                    truth[0] + noise.normal(0, 0.0005),
                    truth[1] + noise.normal(0, 0.0005),
                    widest=outline.max_diameter,
                )
                for _ in range(plan.LOOKS_PER_PROBE)
            ]
            held.merge(readings[:1])
            one.append(math.dist(held.where(0), truth))
            held.merge(readings[1:])
            many.append(math.dist(held.where(0), truth))
    assert sum(many) / len(many) < sum(one) / len(one)


def test_a_glass_that_was_moved_is_remembered_from_scratch():
    held = Remembered()
    held.merge([_seen(0, 0.40, -0.30)])
    held.merge([_seen(0, 0.40, -0.30)])
    assert held.looks_of(0) == 2
    held.forget(0)
    # Still the best guess at where to go and look, but no longer a measurement.
    assert held.where(0) == (0.40, -0.30)
    assert held.looks_of(0) == 0
    held.merge([_seen(0, 0.50, -0.30)])
    assert held.where(0) == (0.50, -0.30), "the reading before the push was averaged in"
    assert held.looks_of(0) == 1


def test_the_memory_holds_a_glass_that_has_dropped_out_of_the_picture():
    held = Remembered()
    held.merge([_seen(0, 0.40, -0.30), _seen(1, 0.60, -0.12)])
    held.merge([_seen(0, 0.40, -0.30)])
    assert [glass.id for glass in held.glasses()] == [0, 1]


# ------------------------------------------------------------- the whole loop


def test_it_never_pushes_a_glass_that_already_has_room():
    """The mistake problem 3's examiner used to make impossible.

    Problem 3 racks a glass the moment it has room, so its chooser is only ever
    shown crowded glasses. Nothing is racked here, so a glass with room stays on
    the table, and a chooser shown one answers with a two-millimetre nudge of it
    for ever. The fix is in ``_decide``; this is what holds it there.
    """
    crowded = [_seen(0, 0.46, -0.30), _seen(1, 0.46, -0.20)]
    roomy = [_seen(2, 0.34, -0.42), _seen(3, 0.62, -0.42)]
    solution = OneFixedNudge()
    solution.begin(0)
    # Already surveyed, so that the first answer is a decision rather than a drive.
    solution.to_visit = []
    answer = solution.answer(_look(crowded + roomy))
    assert not isinstance(answer, Done)
    assert answer.glass in (0, 1)


def test_it_says_done_once_every_glass_it_can_see_has_room():
    spread = [_seen(0, 0.34, -0.42), _seen(1, 0.62, -0.42), _seen(2, 0.34, -0.10), _seen(3, 0.62, -0.10)]
    result = clear_table(OneFixedNudge(), TRAINING, 600.0, cell=_Paper(spread))
    assert result.ended_by == SAID_DONE
    assert result.separated and result.pickable_at_end == 4


def test_it_surveys_the_whole_zone_before_it_decides_anything():
    """The first answers are looks, because one picture is not the table."""
    solution = OneFixedNudge()
    solution.begin(0)
    stands = []
    for _step in range(len(tour.survey())):
        answer = solution.answer(_look([_seen(0, 0.46, -0.30), _seen(1, 0.46, -0.20)]))
        assert not isinstance(answer, Done)
        assert len(answer.waypoints) == 1, "a survey answer should only move the jaw somewhere to see from"
        stands.append((answer.waypoints[0].x, answer.waypoints[0].y))
    assert sorted(stands) == sorted((stand.x, stand.y) for stand in tour.survey())


def test_after_a_push_it_looks_again_and_sweeps_before_saying_done():
    """Cheap while it is working, thorough before it makes a claim.

    A push is carried out open-loop, so the glass has to be looked at again.
    Saying the table needs nothing is a different kind of statement, and that
    one is not made until the whole ring has been walked.
    """
    solution = OneFixedNudge()
    solution.begin(0)
    solution.to_visit = []
    solution.swept = True
    crowded = [_seen(0, 0.46, -0.30), _seen(1, 0.46, -0.20), _seen(2, 0.34, -0.42)]
    for _step in range(2 * FRAMES_ALLOWED):
        answer = solution.answer(_look(crowded))
        assert not isinstance(answer, Done)
        if len(answer.waypoints) > 1:
            break
    else:
        raise AssertionError("it never got round to pushing anything")
    assert solution.pushed is not None, "it should be waiting to see what the push did"
    assert not solution.swept, "it may not say done until it has looked from every side again"


def test_it_will_not_say_done_until_it_has_looked_from_every_side():
    """The claim that a table needs nothing is only made after a whole sweep."""
    spread = [_seen(0, 0.34, -0.42), _seen(1, 0.62, -0.42), _seen(2, 0.34, -0.10), _seen(3, 0.62, -0.10)]
    solution = OneFixedNudge()
    solution.begin(0)
    solution.to_visit = []
    solution.swept = False
    answer = solution.answer(_look(spread))
    assert not isinstance(answer, Done), "it should go and look rather than take one picture's word"
    assert solution.swept and solution.to_visit is not None


@pytest.mark.parametrize("seed", range(TRAINING, TRAINING + 2))
def test_a_real_table_ends_with_the_solution_stopping_itself_or_a_glass_going_over(seed):
    """The real cell, the real camera, the real physics, on two training tables.

    The two endings asserted are the two that are the solution's own business.
    Running out of clock is not one of them: the budget here is far more than
    the solution asks for, so if it ever ends that way it is because the
    solution would not stop, which is the failure this is watching for.
    """
    assert seed < TEST_SEEDS
    result = clear_table(OneFixedNudge(), seed, 600.0)
    assert result.ended_by in (SAID_DONE, GLASS_OVER)
    assert result.arm_seconds > 0.0
    assert result.pickable_at_end >= 0


def test_what_it_spends_splits_into_looking_and_pushing():
    """The calibration reads these two, so they have to add up to about the charge.

    They are the solution's own estimates and the charge is the cell's, so they
    do not match to the second: the cell also charges the lift home at the end
    of every action, which an estimate made before the action cannot know about.
    The estimate is therefore the smaller of the two, and never by much.
    """
    solution = OneFixedNudge()
    result = clear_table(solution, TRAINING, 600.0)
    asked = solution.look_seconds + solution.push_seconds
    assert solution.look_seconds > 0.0, "it has to move the arm to see anything"
    assert asked <= result.arm_seconds + 1e-9
    assert asked > result.arm_seconds / 2


def test_the_test_push_asks_whether_the_glass_kept_up_not_whether_it_budged():
    """Why this solution's threshold is not problem 3's, which is a real difference.

    Problem 3's test push lands on a glass nothing has touched, so the first
    couple of millimetres go into taking up the contact, and it asks only
    whether the glass budged at all. Here the ranging push has already pressed
    against the glass, so that slack is gone and a sliding glass tracks the
    fingertips. Asking only whether it budged passed glasses that answered a
    five millimetre push with two, and a forty millimetre push put those on
    their sides. Both numbers are problem 3's; only the sum is this solution's.
    """
    assert KEPT_UP == pytest.approx(plan.PROBE - plan.PROBE_MOVED)  # noqa: SIM300
    assert plan.PROBE_MOVED < KEPT_UP < plan.PROBE


def test_the_margin_it_calls_room_is_the_one_problem_three_uses():
    """A glass is left alone when it has room, and the two problems agree what room is.

    Not a test of this solution so much as a guard on the pair of them: the
    number is three standard deviations of the error in a measured gap, and if
    problem 3's solution 1 ever revised it this solution would want to as well.
    """
    assert ROOM_MARGIN == pytest.approx(0.005)  # noqa: SIM300
    apart = [_seen(0, 0.40, -0.40), _seen(1, 0.62, -0.10)]
    assert all(plan.room(glass, apart, ROOM_MARGIN) for glass in apart)
    close = [_seen(0, 0.40, -0.40), _seen(1, 0.44, -0.40)]
    assert not any(plan.room(glass, close, ROOM_MARGIN) for glass in close)
