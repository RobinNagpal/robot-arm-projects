"""Tests for the parts of the arm cell that do not need MoveIt or the physics engine.

What is covered is what would be wrong *silently*: a hand turned the wrong way up,
a push whose end point is measured from the wrong place, a setting scaled the wrong
way round, a table that ends in the wrong way, and boxes merged into duplicates. The
motion itself is MoveIt's and the contact is MuJoCo's, and both are checked by
running, not by asserting.
"""

from __future__ import annotations

import math
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from examiner.motion.moveit_connection import flange_goal, quaternion
from examiner.motion.push_motions import (
    BACK_OFF,
    TRAVEL,
    Box,
    Pusher,
    Request,
    Settings,
    scene_boxes,
    table_box,
)
from examiner.simulation.ur5e_model import FINGERTIP_OFFSET, tool_pose
from shared.learning import table_and_push_encoding as F
from shared.turn_by_turn_loop import AS_NEEDED, EVERY_VIEW, Done, Memory, TurnByTurn, over_the_zone

TABLE_TOP = 0.75


# ----------------------------------------------------------------- the hand


@pytest.mark.parametrize("heading", [0.0, 0.7, math.pi / 2, -2.0, math.pi])
def test_the_hand_points_along_the_push_and_its_fingers_stack_upright(heading):
    position, rotation = tool_pose(0.5, -0.2, 0.85, heading)
    push = np.array([math.cos(heading), math.sin(heading), 0.0])
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9), "a rotation must be orthonormal"
    assert np.isclose(np.linalg.det(rotation), 1.0), "a rotation must not mirror"
    assert np.allclose(rotation[:, 2], push), "the tool's z axis is the way the hand points"
    assert np.allclose(rotation[:, 0], [0, 0, 1]), (
        "the fingers open along the tool's x axis, which is upright when rolled"
    )
    # The flange is behind the fingertips by the length of the tool.
    tip = position + FINGERTIP_OFFSET * push
    assert np.allclose(tip, [0.5, -0.2, 0.85])


def test_quaternion_round_trips_every_branch():
    for heading in np.linspace(-math.pi, math.pi, 25):
        _, rotation = tool_pose(0, 0, 1, heading)
        x, y, z, w = quaternion(rotation)
        assert math.isclose(x * x + y * y + z * z + w * w, 1.0, abs_tol=1e-9)
        built = np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ]
        )
        assert np.allclose(built, rotation, atol=1e-9)


def test_a_goal_can_name_a_box_the_line_may_pass_through():
    assert "without" not in flange_goal(0.5, 0, 1.0, 0.0)
    assert flange_goal(0.5, 0, 1.0, 0.0, without="glass_2")["without"] == "glass_2"


# ------------------------------------------------------------------ the push


def _pusher():
    return Pusher(SimpleNamespace(), SimpleNamespace())


def test_a_stroke_ends_where_the_glass_is_to_land_less_its_radius_plus_overreach():
    box = Box(0.5, -0.25, 0.04, 0.15, 0.03)
    settings = Settings(0.085, 0.05, 0.4, 0.01, 0.03, overreach=0.012)
    goals = _pusher().goals([box], Request(0, 0.0, 0.05, settings))
    tip_start = np.array(goals["down"]["position"]) + FINGERTIP_OFFSET * np.array([1, 0, 0])
    tip_end = np.array(goals["stroke"]["position"]) + FINGERTIP_OFFSET * np.array([1, 0, 0])
    # It starts the radius, the padding and the standoff behind the middle.
    assert math.isclose(tip_start[0], 0.5 - (0.04 + 0.01 + 0.03), abs_tol=1e-9)
    # It ends ``travel + overreach - radius`` past the middle.
    assert math.isclose(tip_end[0], 0.5 + (0.05 + 0.012 - 0.04), abs_tol=1e-9)
    assert math.isclose(tip_end[2], TABLE_TOP + 0.085, abs_tol=1e-9)


def test_only_the_stroke_and_the_way_out_may_pass_through_the_pushed_glass():
    box = Box(0.5, -0.25, 0.04, 0.15, 0.03)
    goals = _pusher().goals(
        [box, Box(0.6, -0.1, 0.03, 0.15, 0.03)], Request(1, 1.0, 0.04, Settings.default())
    )
    assert goals["stroke"]["without"] == "glass_1"
    assert goals["back"]["without"] == "glass_1"
    assert goals["up"]["without"] == "glass_1"
    assert "without" not in goals["above"] and "without" not in goals["down"]


def test_the_hand_travels_above_the_tallest_glass_drawn():
    assert TRAVEL - 0.0695 > 0.22, "the underside of the hand at travel height must clear a 0.216 m glass"
    assert BACK_OFF > 0


def test_every_glass_gets_a_box_grown_by_its_padding_and_the_table_is_slightly_low():
    world = scene_boxes([Box(0.5, -0.2, 0.03, 0.15, 0.03)], 0.02)
    names = [b["id"] for b in world]
    assert names == ["table", "glass_0"]
    glass = world[1]
    assert glass["size"][0] == pytest.approx(2 * (0.03 + 0.02))
    assert glass["size"][2] == pytest.approx(0.15 + 0.02)
    assert world[0]["centre"][2] + world[0]["size"][2] / 2 < TABLE_TOP, (
        "MoveIt's table sits a few millimetres low"
    )
    assert table_box()["id"] == "table"


# -------------------------------------------------------------- the encoding


def test_a_push_survives_being_written_as_numbers_and_read_back():
    request = Request(2, 1.3, 0.06, Settings(0.1, 0.03, 0.5, 0.012, 0.04, 0.01))
    back = F.request_from(2, F.action_vector(request))
    assert back.glass == 2
    assert back.heading == pytest.approx(1.3, abs=1e-6)
    assert back.travel == pytest.approx(0.06, abs=1e-6)
    for name in F.SETTING_NAMES:
        assert getattr(back.settings, name) == pytest.approx(getattr(request.settings, name), rel=1e-5)


def test_a_network_cannot_ask_for_a_setting_outside_its_range():
    wild = np.array([1.0, 0.0, 5.0, -3.0, 9.0, 0.5, 0.5, 0.5, 0.5])
    request = F.request_from(0, wild)
    lo, hi = F.TRAVEL
    assert lo <= request.travel <= hi
    for name in F.SETTING_NAMES:
        low, high = F.RANGES[name]
        assert low - 1e-9 <= getattr(request.settings, name) <= high + 1e-9


def test_the_table_encoding_ignores_the_order_it_is_given_in_apart_from_the_order():
    boxes = [
        Box(0.4, -0.2, 0.03, 0.15, 0.03),
        Box(0.45, -0.2, 0.03, 0.15, 0.03),
        Box(0.6, -0.4, 0.04, 0.2, 0.03),
    ]
    rows, mask = F.table_tensor(boxes)
    flipped, _ = F.table_tensor(boxes[::-1])
    assert mask.sum() == 3 and not mask[3:].any()
    assert np.allclose(rows[:3][::-1], flipped[:3]), (
        "a glass's row must not depend on where it is in the list"
    )


def test_two_glasses_touching_are_both_short_of_room_and_one_far_away_is_not():
    boxes = [
        Box(0.4, -0.2, 0.03, 0.15, 0.03),
        Box(0.45, -0.2, 0.03, 0.15, 0.03),
        Box(0.62, -0.42, 0.03, 0.15, 0.03),
    ]
    assert F.room_short(boxes, 0) > 0 and F.room_short(boxes, 1) > 0
    assert F.room_short(boxes, 2) == 0
    assert F.pickable_count(boxes) == 1


def test_a_push_into_a_neighbour_or_with_one_standing_behind_it_is_not_clear():
    boxes = [Box(0.4, -0.2, 0.03, 0.15, 0.03), Box(0.46, -0.2, 0.03, 0.15, 0.03)]
    assert not F.hand_clear(boxes, 0, 0.0, 0.05), "straight into the neighbour"
    assert not F.hand_clear(boxes, 0, math.pi, 0.05), "the hand would come down where the neighbour stands"


def test_a_push_sideways_past_a_neighbour_that_is_far_enough_away_is_clear():
    boxes = [Box(0.4, -0.2, 0.03, 0.15, 0.03), Box(0.5, -0.2, 0.03, 0.15, 0.03)]
    assert F.hand_clear(boxes, 0, math.pi / 2, 0.05)


# -------------------------------------------------------------------- memory


def test_a_glass_seen_from_two_places_is_one_box_and_two_glasses_are_two():
    memory = Memory()
    memory.update([Box(0.5, -0.2, 0.03, 0.15, 0.03), Box(0.6, -0.3, 0.03, 0.15, 0.03)])
    memory.update([Box(0.502, -0.199, 0.031, 0.15, 0.03), Box(0.45, -0.1, 0.03, 0.15, 0.03)])
    assert len(memory.boxes) == 3
    assert any(abs(b.x - 0.502) < 1e-9 for b in memory.boxes), "the newer reading replaces the older"


# ---------------------------------------------------------------------- loop


class FakeCell:
    """Just enough cell for the examiner: it answers what the arm asks and moves nothing."""

    def __init__(self, topple_on: int | None = None, seconds: float = 12.0, refuse: bool = False) -> None:
        self.pushes = 0
        self.topple_on, self.seconds, self.refuse = topple_on, seconds, refuse
        self.pickable_at_start = 1
        hand = SimpleNamespace(x=0.48, y=-0.26, z=0.36, heading=0.0)
        self.simulator = SimpleNamespace(
            seconds=0.0, arm_seconds=0.0, tcp=lambda: hand, joints=lambda: [0.0] * 6
        )
        self.simulator.run = self._run
        self.link = SimpleNamespace(planning_seconds=0.0, scene=lambda boxes: None, plan=self._plan)
        self.camera = SimpleNamespace(view=lambda hand: np.zeros((4, 4, 3), np.uint8))
        self.pusher = SimpleNamespace(push=self._push)
        self.closed = False

    @property
    def arm_seconds(self):
        return self.simulator.arm_seconds

    def _plan(self, q, goal, **how):
        return SimpleNamespace(ok=True, why="", seconds=3.0, times=[0.0, 3.0], joints=[q, q])

    def _run(self, times, joints):
        self.simulator.arm_seconds += times[-1]
        return SimpleNamespace(seconds=times[-1])

    def _push(self, boxes, request, seconds_left=math.inf, stop_when=None):
        if self.refuse:
            return SimpleNamespace(ok=False, why="no way to the start of the push: no plan")
        if self.seconds > seconds_left:
            why = f"the push needs {self.seconds} s and {seconds_left} s are left"
            return SimpleNamespace(ok=False, why=why)
        self.simulator.arm_seconds += self.seconds
        self.pushes += 1
        stopped = stop_when is not None and stop_when()
        return SimpleNamespace(
            ok=True, why="", arm_seconds=self.seconds, stopped=stopped, stages=[("approach",)], touched=True
        )

    def glasses(self):
        return 3

    def toppled(self):
        return 1 if self.topple_on is not None and self.pushes >= self.topple_on else 0

    def pickable(self):
        return 1

    def close(self):
        self.closed = True


class Pushing(TurnByTurn):
    name = "always pushes glass 0"

    def __init__(self, looking=AS_NEEDED, glasses=1):
        self.looking, self.glasses = looking, glasses
        self.see = lambda frame: [Box(0.4 + 0.1 * k, -0.2, 0.03, 0.15, 0.03) for k in range(self.glasses)]

    def decide(self, turn):
        return Request(0, 0.0, 0.05, Settings.default())


class Finished(Pushing):
    name = "says done at once"

    def decide(self, turn):
        return Done("finished")


def _run(solution, cell, left=900.0, monkeypatch=None):
    from examiner.examining import table_examiner

    monkeypatch.setattr(table_examiner, "view_joint_sets", lambda: [[0.0] * 6, [0.0] * 6])
    judge = table_examiner.SimExaminer(SimpleNamespace(), left, make_cell=lambda table, link: cell)
    return judge.run(solution, 1), judge.tally


def test_a_solution_that_says_done_is_marked_finished_having_pushed_nothing(monkeypatch):
    from examiner.examining.solution_contract import FINISHED

    result, _ = _run(Finished(), FakeCell(), monkeypatch=monkeypatch)
    assert result.ended_by == FINISHED and result.pushes_asked == 0 and result.why == "finished"


def test_a_solution_that_never_stops_is_stopped_by_the_clock_and_not_allowed_to_overrun_it(monkeypatch):
    from examiner.examining.solution_contract import OUT_OF_TIME

    result, _ = _run(Pushing(), FakeCell(seconds=12.0), left=40.0, monkeypatch=monkeypatch)
    assert result.ended_by == OUT_OF_TIME
    assert result.arm_seconds <= 40.0, "a push that does not fit in the time left is never started"


def test_a_glass_going_over_ends_the_table_at_once(monkeypatch):
    from examiner.examining.solution_contract import GLASS_OVER

    result, _ = _run(Pushing(), FakeCell(topple_on=2), monkeypatch=monkeypatch)
    assert result.ended_by == GLASS_OVER and result.fell_over == 1
    assert result.pushes_asked == 2


def test_a_solution_that_keeps_asking_for_refused_pushes_is_stopped(monkeypatch):
    from examiner.examining.solution_contract import OUT_OF_TIME
    from examiner.examining.table_examiner import MOST_PUSHES

    cell = FakeCell(refuse=True)
    result, tally = _run(Pushing(), cell, monkeypatch=monkeypatch)
    assert result.ended_by == OUT_OF_TIME and result.pushes_asked == MOST_PUSHES
    assert tally.pictures == 2, "a refused push moves nothing, so the solution does not look again"


def test_one_picture_after_a_push_is_enough_when_it_shows_every_glass(monkeypatch):
    result, tally = _run(Pushing(AS_NEEDED, glasses=2), FakeCell(topple_on=3), monkeypatch=monkeypatch)
    assert result.pushes_asked == 3
    assert tally.pictures == 2 + 1 + 1, "both views at the start, then one after each push"


def test_a_solution_that_reads_the_pictures_takes_both_every_turn(monkeypatch):
    result, tally = _run(Pushing(EVERY_VIEW, glasses=2), FakeCell(topple_on=3), monkeypatch=monkeypatch)
    assert tally.pictures == 2 * 3


def test_the_arm_refuses_every_call_once_the_run_is_over(monkeypatch):
    from examiner.examining import table_examiner
    from examiner.examining.solution_contract import FINISHED, RunOver

    monkeypatch.setattr(table_examiner, "view_joint_sets", lambda: [[0.0] * 6, [0.0] * 6])
    cell = FakeCell()
    run = table_examiner.SimExaminer(SimpleNamespace(), 900.0, make_cell=lambda table, link: cell).start(1)
    run.arm.camera.capture()
    run.finish("enough")
    assert run.state == FINISHED
    with pytest.raises(RunOver):
        run.arm.camera.capture()
    with pytest.raises(RunOver):
        run.arm.push(Request(0, 0.0, 0.05, Settings.default()), [Box(0.5, -0.2, 0.03, 0.15, 0.03)])


def test_the_block_over_the_zone_covers_it_exactly_once_grown():
    from examiner.examining.one_table_cell import zone_box

    padding = 0.01
    tiles = over_the_zone(padding)
    zone = zone_box()
    xs = [t.x - t.radius - padding for t in tiles] + [t.x + t.radius + padding for t in tiles]
    ys = [t.y - t.radius - padding for t in tiles] + [t.y + t.radius + padding for t in tiles]
    assert min(xs) == pytest.approx(zone["centre"][0] - zone["size"][0] / 2)
    assert max(xs) == pytest.approx(zone["centre"][0] + zone["size"][0] / 2)
    assert min(ys) == pytest.approx(zone["centre"][1] - zone["size"][1] / 2)
    assert max(ys) == pytest.approx(zone["centre"][1] + zone["size"][1] / 2)
    assert all(t.height + padding == pytest.approx(zone["size"][2]) for t in tiles)


# ------------------------------------------------------- the data and the planner


def test_a_push_measured_from_straight_away_points_where_it_says():
    boxes = [Box(0.4, -0.2, 0.03, 0.15, 0.03), Box(0.46, -0.2, 0.03, 0.15, 0.03)]
    # Glass 0 has its neighbour to the east, so away from it is west: an angle of pi.
    assert abs(abs(F.away_angle(boxes, 0)) - math.pi) < 1e-9
    assert F.away_angle(boxes, 1) == pytest.approx(0.0)
    # A quarter turn on from "away" is sideways.
    sideways = F.relative_request(1, np.array([0.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]), boxes)
    assert sideways.heading == pytest.approx(math.pi / 2, abs=1e-9)


def test_an_informed_push_would_free_its_glass_if_it_went_as_asked():
    import random

    from examiner.simulation.taken_from_problem_3 import has_room
    from shared.learning import collect_training_pushes as CP

    boxes = [
        Box(0.45, -0.25, 0.03, 0.15, 0.03),
        Box(0.54, -0.25, 0.03, 0.15, 0.03),
        Box(0.60, -0.40, 0.03, 0.15, 0.03),
    ]
    rng = random.Random(3)
    found = 0
    for _ in range(20):
        request = CP.informed_request(rng, boxes)
        if request is None:
            continue
        found += 1
        g = boxes[request.glass]
        end = (
            g.x + request.travel * math.cos(request.heading),
            g.y + request.travel * math.sin(request.heading),
        )
        others = [(o.x, o.y, 2 * o.radius) for j, o in enumerate(boxes) if j != request.glass]
        assert has_room(*end, others, 0.005), "it must end with room"
        assert F.hand_clear(boxes, request.glass, request.heading, request.travel), (
            "and the hand must fit on the way"
        )
    assert found > 0, "this table has pushes that would free a glass"


def test_a_table_with_nothing_short_of_room_offers_no_informed_push():
    import random

    from shared.learning import collect_training_pushes as CP

    boxes = [Box(0.35, -0.1, 0.03, 0.15, 0.03), Box(0.6, -0.4, 0.03, 0.15, 0.03)]
    assert CP.informed_request(random.Random(0), boxes) is None


def test_every_setting_a_planner_nudges_stays_inside_its_range():
    import random

    from world_model import PlanningSolution

    planner = PlanningSolution.__new__(PlanningSolution)
    planner.rng = random.Random(1)
    boxes = [Box(0.4, -0.2, 0.03, 0.15, 0.03)]
    request = Request(
        0, 0.3, 0.05, Settings(0.075, 0.006, 0.3, 0.005, 0.02, 0.0)
    )  # every setting at the edge
    for _ in range(50):
        nudged = planner.shaken(request, boxes)
        lo, hi = F.TRAVEL
        assert lo <= nudged.travel <= hi
        for name in F.SETTING_NAMES:
            low, high = F.RANGES[name]
            assert low - 1e-9 <= getattr(nudged.settings, name) <= high + 1e-9


def test_a_spread_is_wider_than_nothing_and_the_same_every_time():
    from examiner.tools import compare_results

    rows = [
        {
            "glasses": 4,
            "pickable_at_start": 1,
            "pickable_at_end": 1 + (i % 2),
            "broken": 0,
            "outcome": "unfinished",
            "ended_by": "said done",
            "arm_seconds": 10.0,
        }
        for i in range(20)
    ]
    low, high = compare_results.interval(rows, "gain")
    assert low < high
    assert compare_results.interval(rows, "gain") == (low, high)
    assert compare_results.stats(rows)["gain"] == 10


def test_a_table_with_a_glass_over_pays_nothing_in_the_pickable_count():
    from examiner.tools import compare_results

    rows = [
        {
            "glasses": 4,
            "pickable_at_start": 1,
            "pickable_at_end": 3,
            "broken": 0,
            "outcome": "unfinished",
            "ended_by": "said done",
            "arm_seconds": 5.0,
        },
        {
            "glasses": 4,
            "pickable_at_start": 1,
            "pickable_at_end": 4,
            "broken": 1,
            "outcome": "failed",
            "ended_by": "a glass went over",
            "arm_seconds": 5.0,
        },
    ]
    stats = compare_results.stats(rows)
    assert stats["gain"] == 2 and stats["broken"] == 1 and stats["failed"] == 1


class _Asks:
    """A solution that always offers the same push, and gives up on a glass once it is set aside."""

    name = "asks"

    def __init__(self, request):
        self.request, self.refused = request, set()

    def begin(self):
        self.refused = set()

    def decide(self, look):
        return Done("nothing left") if self.request.glass in self.refused else self.request


class _Fears:
    """A world model that thinks a fast stroke tips a glass and a slow one does not."""

    def score(self, boxes, glass, vectors):
        topple = vectors[:, 4].astype(float)  # the stroke speed, scaled 0..1
        return -topple, np.ones(len(vectors)), topple


def _checked(speed, repair):
    import safety_check

    request = F.request_from(0, [1.0, 0.0, 0.5, 0.5, speed, 0.5, 0.5, 0.5, 0.5])
    wrapped = safety_check.Checked.__new__(safety_check.Checked)
    wrapped.inner, wrapped.model, wrapped.rng = _Asks(request), _Fears(), np.random.default_rng(0)
    wrapped.vetoed = wrapped.mended = 0
    wrapped.LIMIT, wrapped.REPAIR = 0.3, repair
    look = SimpleNamespace(boxes=[Box(0.5, 0.0, 0.03, 0.12, 0.02), Box(0.56, 0.0, 0.03, 0.12, 0.02)])
    return request, wrapped.decide(look)


def test_the_check_lets_a_safe_push_through_unchanged():
    request, answer = _checked(0.1, repair=1)
    assert answer is request


def test_the_check_mends_a_risky_push_keeping_its_glass_way_and_distance():
    request, answer = _checked(0.9, repair=1)
    assert not isinstance(answer, Done)
    assert (answer.glass, answer.heading, answer.travel) == (request.glass, request.heading, request.travel)
    assert F.action_vector(answer)[4] <= 0.3


def test_without_mending_a_risky_push_sets_the_glass_aside():
    _, answer = _checked(0.9, repair=0)
    assert isinstance(answer, Done)


# ------------------------------------------------------------ solution 2's ordering


def _seen_on(seed: int):
    from examiner.simulation import table_draw
    from examiner.simulation.taken_from_problem_3 import Seen

    return [
        Seen(
            id=i,
            x=float(g.position[0]),
            y=float(g.position[1]),
            height=g.outline.total_height,
            widest=g.outline.max_diameter,
            foot=2 * float(g.outline.radius[0]),
            standing=True,
        )
        for i, g in enumerate(table_draw.table(seed))
    ]


def test_problem_threes_ranked_files_leave_the_examiners_own_modules_in_place():
    import geometry_ranked

    from shared.learning import table_and_push_encoding

    assert table_and_push_encoding is sys.modules["shared.learning.table_and_push_encoding"]
    # Problem 3's files are not left behind under their plain names, where another
    # module asking for ``table_and_push_encoding`` could be handed one of them by mistake.
    assert "features" not in sys.modules
    assert geometry_ranked._LOADED["features"] is not table_and_push_encoding


def test_the_ranked_solution_makes_the_push_its_scores_put_first():
    import geometry_ranked

    seen = _seen_on(2000)
    kept, _ = geometry_ranked.candidates.survivors(seen, set())
    assert len(kept) > 1, "a table with one candidate cannot tell an ordering from no ordering"
    # A score that puts the last candidate first, so the pick cannot be the rule's by luck.
    last = kept[-1]
    solution = geometry_ranked.GeometryRanked(score=lambda rows: np.arange(len(rows), dtype=float))
    push = solution.choose(seen)
    assert push.glass == last.push.glass
    assert push.heading == pytest.approx(last.push.heading)
    assert push.travel >= last.push.travel


def test_the_ranked_solution_says_done_when_no_glass_is_left_to_push():
    import geometry_ranked

    seen = _seen_on(2000)
    solution = geometry_ranked.GeometryRanked(score=lambda rows: np.zeros(len(rows)))
    solution.skip = {glass.id for glass in seen}
    assert solution.choose(seen) is None
