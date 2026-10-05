"""Checks that need no correction fitted and no weights downloaded.

What is testable here is the arithmetic between the bench and the model: the
cut that turns a recorded push into the part a chunk covers, the resampling,
and the reading that carries a waypoint into the model's units and back. That
reading is the one piece of arithmetic a mistake in would be invisible —
a chunk decoded through a wrong scale is still a well-formed chunk — so most
of what follows is about it, and over many drawn paths rather than one.

The model itself is not loaded. A test that downloads two gigabytes to find
out whether a scaling is right is not a test.
"""

from __future__ import annotations

import json
import math

import chunks
import numpy as np
import pytest
from correction import CORRECTION, RANK, SCALING, TABLES, Fitted, missing
from demonstrations import FEATURES, Watched, went_well
from partners import ACTION_SPAN, CAMERA, INSTRUCTION, SLOTS, to_jaw, to_state
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE

from bench import PUSH_HEIGHT, TRAVEL_HEIGHT, Bench, Chunk, Push, Waypoint

PATHS = 40


def drawn_push(rng: np.random.Generator) -> list[Waypoint]:
    """A straight run of waypoints across the table at push height, as a recorded push is."""
    x_min, x_max, y_min, y_max = GLASS_ZONE
    x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
    heading = rng.uniform(-math.pi, math.pi)
    travel = rng.uniform(0.02, 0.12)
    steps = int(rng.integers(20, 200))
    along = np.linspace(0.0, travel, steps)
    return [
        Waypoint(x + d * math.cos(heading), y + d * math.sin(heading), PUSH_HEIGHT, heading) for d in along
    ]


def recorded(flat: list[Waypoint]) -> tuple[Waypoint, ...]:
    """The same push as the bench writes it down: descent, the push, a back-off and a lift."""
    first, last = flat[0], flat[-1]
    back = math.atan2(last.y - first.y, last.x - first.x)
    down = [Waypoint(first.x, first.y, z, first.heading) for z in (TRAVEL_HEIGHT, 0.2, 0.1)]
    off = [
        Waypoint(last.x - d * math.cos(back), last.y - d * math.sin(back), PUSH_HEIGHT, last.heading)
        for d in (0.01, 0.02)
    ]
    up = [Waypoint(off[-1].x, off[-1].y, z, last.heading) for z in (0.1, TRAVEL_HEIGHT)]
    return tuple(down + flat + off + up)


# ----------------------------------------------------------------- the cut


def test_the_cut_keeps_the_flat_run_and_drops_the_ends():
    rng = np.random.default_rng(0)
    for _ in range(PATHS):
        flat = drawn_push(rng)
        part = chunks.pushing_part(recorded(flat))
        assert len(part) == len(flat)
        assert part[0] == flat[0]
        assert part[-1] == flat[-1]


def test_the_cut_is_empty_when_the_jaw_never_came_down():
    path = tuple(Waypoint(0.5, -0.2, z, 0.0) for z in np.linspace(TRAVEL_HEIGHT, 0.1, 6))
    assert chunks.pushing_part(path) == []


def test_a_recording_with_no_push_in_it_is_not_a_demonstration():
    # The jaw came down and went straight back up, which is what a push that
    # was blocked looks like. There is nothing to imitate in it.
    path = (Waypoint(0.5, -0.2, TRAVEL_HEIGHT, 0.0), Waypoint(0.5, -0.2, PUSH_HEIGHT, 0.0))
    assert chunks.demonstration(path) is None


# ---------------------------------------------------------- the resampling


def test_the_resampling_keeps_the_ends_and_spaces_the_rest_evenly():
    rng = np.random.default_rng(1)
    for _ in range(PATHS):
        flat = drawn_push(rng)
        out = chunks.resampled(flat)
        assert out.shape == (chunks.CHUNK, 4)
        assert out[0, 0] == pytest.approx(flat[0].x, abs=1e-12)
        assert out[-1, 1] == pytest.approx(flat[-1].y, abs=1e-12)
        steps = np.hypot(*np.diff(out[:, :2], axis=0).T)
        assert steps.std() < 1e-9
        assert chunks.across(flat) == pytest.approx(steps.sum(), rel=1e-9)


def test_the_resampling_turns_the_short_way_round_the_circle():
    # A heading of 179 degrees and one of -179 are two degrees apart, and
    # interpolating the angles themselves would send the jaw the long way.
    points = [
        Waypoint(0.5, -0.2, PUSH_HEIGHT, math.radians(179)),
        Waypoint(0.55, -0.2, PUSH_HEIGHT, math.radians(-179)),
    ]
    out = chunks.resampled(points, 3)
    assert abs(out[1, 3]) > math.radians(179)


def test_the_resampling_refuses_a_path_that_went_nowhere():
    standing = [Waypoint(0.5, -0.2, PUSH_HEIGHT, 0.0)] * 5
    with pytest.raises(ValueError, match="no push in it"):
        chunks.resampled(standing)


# ------------------------------------------------------------- the reading


def test_a_waypoint_survives_the_trip_into_the_model_and_back():
    rng = np.random.default_rng(2)
    for _ in range(PATHS):
        flat = drawn_push(rng)
        waypoints = chunks.resampled(flat)
        again = to_jaw(chunks.as_action(waypoints))
        assert np.allclose(again[:, :3], waypoints[:, :3], atol=1e-9)
        turned = np.abs(np.angle(np.exp(1j * (again[:, 3] - waypoints[:, 3]))))
        assert turned.max() < 1e-9
        assert chunks.drift(waypoints) < 1e-9


def test_the_reading_pins_a_waypoint_outside_the_picture_to_its_edge():
    # The frame is what sets the scale, so a push starting off the edge of it
    # is a push this model has no way to ask for. It must not become a
    # training target that quietly means somewhere else.
    far = np.array([[TABLE_CENTRE_XY[0] + TABLE_SIZE[0] / 2, 0.0, PUSH_HEIGHT, 0.0]] * chunks.CHUNK)
    assert chunks.drift(far) > chunks.FAITHFUL


def test_an_action_fills_only_the_slots_the_reading_uses():
    action = chunks.as_action(np.array([[0.5, -0.2, PUSH_HEIGHT, 0.0]]))
    assert action.shape == (1, SLOTS)
    assert np.all(np.abs(action) <= ACTION_SPAN + 1e-12)


def test_the_state_is_the_reading_backwards():
    jaw = Waypoint(0.5, -0.2, 0.12, 1.1)
    back = to_jaw(to_state(jaw)[None, :])[0]
    assert back[:3] == pytest.approx((jaw.x, jaw.y, jaw.z), abs=1e-9)
    assert back[3] == pytest.approx(jaw.heading, abs=1e-9)


# ------------------------------------------------- the chunk the bench takes


def test_a_demonstration_decodes_into_a_chunk_the_jaw_could_follow():
    rng = np.random.default_rng(3)
    for _ in range(PATHS):
        action = chunks.demonstration(recorded(drawn_push(rng)))
        assert action is not None
        waypoints = to_jaw(action)
        assert np.all(waypoints[:, 2] >= PUSH_HEIGHT - 1e-9)
        assert np.all(waypoints[:, 2] <= TRAVEL_HEIGHT + 1e-9)
        assert np.all(np.abs(waypoints[:, 0] - TABLE_CENTRE_XY[0]) <= TABLE_SIZE[0] / 2)
        assert np.all(np.abs(waypoints[:, 1] - TABLE_CENTRE_XY[1]) <= TABLE_SIZE[1] / 2)
        chunk = Chunk.from_array(0, waypoints, (0.0, 0.0))
        assert len(chunk.waypoints) == chunks.CHUNK


# --------------------------------------------------- what the dataset holds


def test_the_dataset_holds_one_flat_chunk_a_frame():
    assert FEATURES["action"]["shape"] == (chunks.CHUNK * SLOTS,)
    assert FEATURES["observation.state"]["shape"] == (SLOTS,)
    assert CAMERA in FEATURES


def test_the_instruction_is_the_one_solution_five_uses():
    # Not a tautology while it is imported: it is here so that replacing the
    # import with a copy fails the tests rather than quietly unmatching the
    # pair.
    assert INSTRUCTION == "the glasses are too close together, push them apart"


# ------------------------------------------- against the bench's own physics


def test_a_real_recorded_push_becomes_a_chunk():
    """One push on one table, and the recording of it turned into a target.

    This is the only test that runs the physics. It is here because the shape
    of a real recording — where the descent ends, where the back-off starts —
    is a property of the bench and not of the drawn paths above.
    """
    table = Bench(0)
    glass = table.look()[0]
    heading = 0.0
    table.push(
        Push(
            glass=glass.id,
            start=(glass.x - glass.widest / 2 - 0.01, glass.y),
            heading=heading,
            reach=0.06,
            travel=0.04,
            aim=(glass.x + 0.04, glass.y),
        )
    )
    path = table.records[-1].waypoints
    assert len(path) > chunks.CHUNK
    action = chunks.demonstration(path)
    assert action is not None and action.shape == (chunks.CHUNK, SLOTS)
    part = chunks.pushing_part(path)
    assert all(point.z == pytest.approx(PUSH_HEIGHT, abs=1e-6) for point in part)
    # The far end of the cut is the far end of the push, so the back-off is
    # not in it: no later waypoint of the cut comes back towards the start.
    walked = [math.dist((part[0].x, part[0].y), (p.x, p.y)) for p in part]
    assert walked == sorted(walked)


def test_a_push_that_touches_nothing_is_not_worth_imitating():
    table = Bench(0)
    seen = table.look()
    x_min, x_max, y_min, y_max = GLASS_ZONE
    corners = [(x, y) for x in (x_min, x_max) for y in (y_min, y_max)]
    clear_spot = max(corners, key=lambda spot: min(math.dist(spot, (g.x, g.y)) for g in seen))
    table.push(
        Push(
            glass=seen[0].id,
            start=clear_spot,
            heading=0.0,
            reach=0.03,
            travel=0.02,
            aim=(clear_spot[0] + 0.05, clear_spot[1]),
        )
    )
    assert went_well(table) == "never touched anything"


def test_the_watched_bench_takes_its_picture_before_the_jaw_moves():
    table = Watched(0)
    try:
        assert table.before is None
        glass = table.look()[0]
        table.push(
            Push(
                glass=glass.id,
                start=(glass.x - glass.widest / 2 - 0.01, glass.y),
                heading=0.0,
                reach=0.06,
                travel=0.02,
                aim=(glass.x + 0.02, glass.y),
            )
        )
        picture, jaw = table.before
        assert picture.shape == FEATURES[CAMERA]["shape"]
        assert picture.dtype == np.uint8
        # The jaw was parked when the picture was taken, which is the whole of
        # what this model's third input ever says here.
        assert jaw.z > TRAVEL_HEIGHT
    finally:
        table.close()


# ----------------------------------------------------- loading the correction


def test_the_correction_is_asked_for_before_anything_is_downloaded(tmp_path):
    assert missing(tmp_path) is not None
    with pytest.raises(FileNotFoundError, match="no correction"):
        Fitted.load("cpu", tmp_path)


def test_a_folder_with_an_adapter_in_it_is_accepted(tmp_path):
    (tmp_path / "adapter_config.json").write_text(json.dumps({"r": RANK}))
    assert missing(tmp_path) is None


def test_the_correction_settings_are_the_ones_the_document_describes():
    assert RANK == 16
    assert SCALING == 2 * RANK
    assert set(TABLES) == {"q_proj", "k_proj", "v_proj", "o_proj"}
    assert CORRECTION.name == "correction"
