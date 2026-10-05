"""The parts of this solution that are not the borrowed model.

Nothing here downloads weights, loads a network or needs an accelerator. What
is tested is the join — the arithmetic that turns the model's actions into jaw
waypoints and the jaw's pose into its state — the two checks that run before
the model, and the loop around it, driven by a stand-in that answers
instantly.
"""

import math

import numpy as np
import pytest
from clear import ASKS_PER_TABLE, TAKE_MARGIN, TIPS, Tally, clear, jaw_now, nudge
from joining import (
    ACTION_SPAN,
    SLOTS,
    UP_HIGHER,
    chunk_for,
    hits_refused,
    nearest,
    to_jaw,
    to_state,
)
from policy import Downloaded
from work_cell.glasses.shapes import family
from work_cell.glasses.spawn import SpawnedGlass

import bench
from bench import PUSH_HEIGHT, TRAVEL_HEIGHT, Bench, Seen, Waypoint, _checked
from top_view import TOP_VIEW_HALF_FRAME, VIEW_CENTRE


def action_at(x, y, z, heading):
    """The six numbers that ``to_jaw`` reads as this jaw pose. The join, run backwards."""
    return to_state(Waypoint(x, y, z, heading))


def a_path(x, y, z, heading=0.0, steps=50):
    return to_jaw(np.tile(action_at(x, y, z, heading), (steps, 1)))


def seen_at(spots):
    """Glasses of one drawn family, stood where the test wants them."""
    drawn = family("straight_glass", len(spots), seed=7)
    return [
        Seen(i, x, y, outline.total_height, outline.max_diameter, 2 * outline.radius[0], True)
        for i, ((x, y), (outline, _)) in enumerate(zip(spots, drawn, strict=True))
    ]


class Stand_in:
    """A model that answers instantly with the jaw path the test chose."""

    def __init__(self, path):
        self.path = np.asarray(path, dtype=float)
        self.asked = 0

    def ask(self, picture, jaw):
        self.asked += 1
        return self.path

    def reset(self):
        pass


class Blind_camera:
    """A view that costs nothing. The stand-in model never looks at it."""

    def view(self):
        return np.zeros((*bench.TOP_VIEW_SIZE, 3), dtype=np.uint8)


# --------------------------------------------------------------- the reading


def test_the_middle_of_the_action_space_is_the_middle_of_the_frame():
    jaw = to_jaw(np.zeros((1, SLOTS)))[0]
    assert jaw[0] == pytest.approx(VIEW_CENTRE[0])
    assert jaw[1] == pytest.approx(VIEW_CENTRE[1])
    assert jaw[2] == pytest.approx((PUSH_HEIGHT + TRAVEL_HEIGHT) / 2)
    assert jaw[3] == pytest.approx(0.0)


def test_one_span_each_way_is_the_frame_and_the_height_range():
    action = np.zeros((2, SLOTS))
    action[0, :] = -ACTION_SPAN
    action[1, :] = ACTION_SPAN
    low, high = to_jaw(action)
    assert low[0] == pytest.approx(VIEW_CENTRE[0] - TOP_VIEW_HALF_FRAME)
    assert high[0] == pytest.approx(VIEW_CENTRE[0] + TOP_VIEW_HALF_FRAME)
    assert low[1] == pytest.approx(VIEW_CENTRE[1] - TOP_VIEW_HALF_FRAME)
    assert high[1] == pytest.approx(VIEW_CENTRE[1] + TOP_VIEW_HALF_FRAME)
    assert low[2] == pytest.approx(PUSH_HEIGHT)
    assert high[2] == pytest.approx(TRAVEL_HEIGHT)
    assert low[3] == pytest.approx(-math.pi)
    assert high[3] == pytest.approx(math.pi)


def test_the_two_slots_the_jaw_cannot_use_change_nothing():
    rng = np.random.default_rng(1)
    action = rng.normal(size=(20, SLOTS))
    other = action.copy()
    other[:, 3] = rng.normal(size=20)  # wrist flex
    other[:, 5] = rng.normal(size=20)  # gripper
    assert np.allclose(to_jaw(action), to_jaw(other))


def test_anything_the_model_can_emit_is_a_chunk_the_bench_will_take():
    rng = np.random.default_rng(2)
    for scale in (0.5, 1.0, 5.0, 100.0):
        path = to_jaw(rng.normal(scale=scale, size=(50, SLOTS)))
        _checked(tuple(Waypoint(*row) for row in path.tolist()))


def test_the_state_is_the_reading_run_backwards():
    rng = np.random.default_rng(3)
    action = rng.uniform(-1.5, 1.5, size=(30, SLOTS))  # inside the span, so nothing clips
    for row, jaw in zip(action, to_jaw(action), strict=True):
        back = to_state(Waypoint(*jaw))
        for slot in (0, 1, 2, 4):
            assert back[slot] == pytest.approx(row[slot], abs=1e-9)


def test_a_pose_outside_the_frame_clips_rather_than_running_away():
    state = to_state(Waypoint(0.0, 0.5, 0.55, 0.0))  # where the bench parks the jaw
    assert np.all(np.abs(state) <= ACTION_SPAN + 1e-12)


def test_a_wrongly_shaped_answer_is_refused():
    with pytest.raises(ValueError, match="chunk"):
        to_jaw(np.zeros((4, 7)))
    with pytest.raises(ValueError, match="chunk"):
        to_jaw(np.zeros(SLOTS))


# ------------------------------------------------- reading a glass off a path


def test_the_push_is_credited_to_the_glass_the_path_comes_nearest():
    seen = seen_at([(0.40, -0.30), (0.56, -0.20)])
    assert nearest(a_path(0.56, -0.20, PUSH_HEIGHT), seen) == 1
    assert nearest(a_path(0.40, -0.30, PUSH_HEIGHT), seen) == 0


def test_a_path_that_stays_above_every_glass_is_still_credited_to_one():
    seen = seen_at([(0.40, -0.30), (0.56, -0.20)])
    assert nearest(a_path(0.56, -0.20, TRAVEL_HEIGHT), seen) in {0, 1}


def test_a_path_through_a_refused_glass_is_caught():
    seen = seen_at([(0.40, -0.30), (0.56, -0.20)])
    assert hits_refused(a_path(0.56, -0.20, PUSH_HEIGHT), seen, {1}) == 1
    assert hits_refused(a_path(0.40, -0.30, PUSH_HEIGHT), seen, {1}) is None


def test_a_path_that_flies_over_a_refused_glass_is_not_caught():
    seen = seen_at([(0.56, -0.20)])
    assert hits_refused(a_path(0.56, -0.20, TRAVEL_HEIGHT), seen, {0}) is None


def test_the_chunk_carries_the_path_and_its_end_unchanged():
    seen = seen_at([(0.40, -0.30)])
    path = a_path(0.44, -0.28, PUSH_HEIGHT)
    chunk = chunk_for(path, seen)
    assert len(chunk.waypoints) == len(path)
    assert chunk.aim == pytest.approx((path[-1, 0], path[-1, 1]))
    assert chunk.as_push().glass == chunk.glass


# ----------------------------------------------------------------- the loop


def _table(seed=bench.TEST_SEEDS):
    return Bench(seed)


def test_the_jaw_reads_back_where_the_bench_parks_it():
    jaw = jaw_now(_table())
    assert (jaw.x, jaw.y) == pytest.approx((0.0, 0.5))
    assert jaw.z > TRAVEL_HEIGHT


def test_a_table_of_glasses_that_tip_is_refused_without_asking_the_model(monkeypatch):
    monkeypatch.setattr(nudge, "slides", lambda glass: "no")
    model = Stand_in(to_jaw(np.zeros((50, SLOTS))))
    refused, tally = clear(_table(), model, Blind_camera())
    assert model.asked == 0
    assert tally.asked == 0
    assert set(refused.values()) == {TIPS}


def test_a_model_that_never_frees_anything_is_stopped_by_the_table_budget():
    # A path parked in one corner, well clear of the glass zone: it touches
    # nothing, so no glass is ever freed and the shared budget is what ends
    # the table. Every answer is carried out, because none of them reaches a
    # glass refused for tipping.
    table = _table()
    model = Stand_in(a_path(0.15, -0.60, TRAVEL_HEIGHT))
    refused, tally = clear(table, model, Blind_camera())
    assert tally.asked == tally.followed == bench.PUSHES_PER_TABLE
    assert tally.ran_out_of_asks == 0
    assert refused and set(refused.values()) == {"push budget spent"}


def test_no_table_is_pushed_more_often_than_the_shared_budget_allows():
    # The thrown-away answers are not pushes and are not charged as pushes:
    # what the bench records is what the budget counts.
    table = _table()
    model = Stand_in(a_path(0.15, -0.60, TRAVEL_HEIGHT))
    _, tally = clear(table, model, Blind_camera())
    assert len(table.records) == tally.followed <= bench.PUSHES_PER_TABLE


def test_a_path_at_a_refused_glass_is_never_carried_out(monkeypatch):
    table = _table()
    seen = table.look()
    # A glass that is crowded, so the loop cannot rack it and get rid of it.
    crowded = next(g for g in seen if not nudge.room(g, seen, TAKE_MARGIN))
    monkeypatch.setattr(nudge, "slides", lambda glass, worst=crowded.id: "no" if glass.id == worst else "yes")
    model = Stand_in(a_path(crowded.x, crowded.y, PUSH_HEIGHT))
    refused, tally = clear(table, model, Blind_camera())
    assert refused[crowded.id] == TIPS
    assert tally.refused_path == tally.asked == ASKS_PER_TABLE
    assert tally.ran_out_of_asks == 1
    assert tally.followed == 0
    assert table.records == []


def test_a_glass_with_room_is_racked_before_anything_is_pushed():
    # Two glasses of a drawn family, stood far apart. Both have room, so the
    # loop should rack them and never ask.
    drawn = family("straight_glass", 2, seed=11)
    spots = [(0.36, -0.40), (0.60, -0.12)]
    table = Bench(
        0,
        [
            SpawnedGlass(f"glass_{i}", "straight_glass", outline, (x, y, bench.TABLE_TOP_Z), 0.0)
            for i, ((outline, _), (x, y)) in enumerate(zip(drawn, spots, strict=True))
        ],
    )
    model = Stand_in(to_jaw(np.zeros((50, SLOTS))))
    refused, tally = clear(table, model, Blind_camera())
    assert refused == {}
    assert tally.asked == 0
    assert len(table.taken) == 2


def test_the_tally_adds_up_and_reports_what_the_paths_looked_like():
    one, two = Tally(), Tally()
    one.saw(a_path(0.40, -0.30, PUSH_HEIGHT))
    two.saw(a_path(0.60, -0.12, TRAVEL_HEIGHT))
    two.asked = 2
    one.add(two)
    assert one.asked == 2
    assert one.summary()["lowest_mm_median"] == pytest.approx(1000 * (PUSH_HEIGHT + TRAVEL_HEIGHT) / 2)


# ------------------------------------------------------- the model's wrapper


def test_a_picture_that_is_not_the_top_view_is_refused_before_any_weights_are_touched():
    model = Downloaded(policy=None, pre=None, post=None)
    with pytest.raises(ValueError, match="top view"):
        model.ask(np.zeros((8, 8, 3), dtype=np.float32), Waypoint(0.0, 0.5, 0.55, 0.0))


def test_turning_the_height_slot_over_mirrors_the_height_and_nothing_else():
    rng = np.random.default_rng(5)
    action = rng.uniform(-1.5, 1.5, size=(20, SLOTS))
    up, down = to_jaw(action), to_jaw(action, up=-UP_HIGHER)
    assert np.allclose(up[:, [0, 1, 3]], down[:, [0, 1, 3]])
    assert np.allclose(up[:, 2] + down[:, 2], PUSH_HEIGHT + TRAVEL_HEIGHT)


def test_the_state_follows_whichever_way_the_height_slot_runs():
    jaw = Waypoint(0.48, -0.26, PUSH_HEIGHT, 0.0)
    assert to_state(jaw)[2] == pytest.approx(-ACTION_SPAN)
    assert to_state(jaw, up=-UP_HIGHER)[2] == pytest.approx(ACTION_SPAN)


def test_the_scored_reading_is_the_one_the_model_wrapper_defaults_to():
    assert Downloaded(policy=None, pre=None, post=None).up == UP_HIGHER
