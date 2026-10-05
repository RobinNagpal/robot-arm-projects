"""The arithmetic, the shapes, the refusals and the interface.

Nothing here needs a fitted policy, an accelerator or a download. What is
tested is the part of this solution that is not the fitting: trimming a
recorded path into a chunk, resampling it, turning it back into waypoints the
bench will take, reading which glass a chunk is for, the scaling the model
sees, what a demonstration is dropped for, and the gate that refuses a glass
before the policy is asked about it.

One test builds an unfitted ACT and asks it for a chunk. That is the
interface test: random weights, no download, and the answer has to be a chunk
the bench would accept.
"""

from __future__ import annotations

import math

import chunks
import collect
import loop
import numpy as np
import pictures as pictures_module
import policy as policy_module
import pytest
from teacher import nudge

import bench
from bench import PUSH_HEIGHT, TRAVEL_HEIGHT, Felt, Record, Waypoint


def _seen(i, x, y, widest=0.08, foot=0.07, height=0.15):
    return bench.Seen(i, x, y, height, widest, foot, True)


def _path(*points):
    return tuple(Waypoint(*point) for point in points)


# ----------------------------------------------------------------- the chunk


def test_the_chunk_is_the_push_with_the_descent_back_off_and_lift_taken_off():
    path = _path(
        (0.4, 0.0, TRAVEL_HEIGHT, 0.0),  # coming down
        (0.4, 0.0, 0.15, 0.0),
        (0.4, 0.0, PUSH_HEIGHT, 0.0),  # the push starts here
        (0.41, 0.0, PUSH_HEIGHT, 0.0),
        (0.42, 0.0, PUSH_HEIGHT, 0.0),  # and ends here
        (0.40, 0.0, PUSH_HEIGHT, 0.0),  # backing off
        (0.40, 0.0, TRAVEL_HEIGHT, 0.0),  # lifting
    )
    kept = chunks.push_segment(path)
    assert [round(p.x, 3) for p in kept] == [0.4, 0.41, 0.42]
    assert all(p.z == pytest.approx(PUSH_HEIGHT) for p in kept)


def test_a_push_blocked_on_the_way_down_leaves_no_chunk():
    path = _path((0.4, 0.0, TRAVEL_HEIGHT, 0.0), (0.4, 0.0, 0.2, 0.0), (0.4, 0.0, TRAVEL_HEIGHT, 0.0))
    assert chunks.push_segment(path) == ()


def test_resampling_keeps_the_ends_and_the_straight_line_between_them():
    action = chunks.to_action(
        _path((0.4, -0.1, PUSH_HEIGHT, 0.5), (0.5, -0.1, PUSH_HEIGHT, 0.5), (0.6, -0.1, PUSH_HEIGHT, 0.5))
    )
    out = chunks.resample(action, 7)
    assert out.shape == (7, chunks.ACTION_WIDTH)
    assert out[0] == pytest.approx(action[0], abs=1e-6)
    assert out[-1] == pytest.approx(action[-1], abs=1e-6)
    assert out[:, 0] == pytest.approx(np.linspace(0.4, 0.6, 7), abs=1e-6)


def test_resampling_refuses_a_path_too_short_to_resample():
    with pytest.raises(ValueError):
        chunks.resample(chunks.to_action(_path((0.4, 0.0, PUSH_HEIGHT, 0.0))), 5)


@pytest.mark.parametrize("heading", [0.0, 1.0, -1.0, math.pi - 1e-3, -math.pi + 1e-3])
def test_a_heading_survives_the_trip_through_cosine_and_sine(heading):
    there = chunks.to_action(_path((0.45, -0.2, PUSH_HEIGHT, heading)))
    (back,), pulled = chunks.to_waypoints(there)
    assert pulled == 0
    assert math.cos(back.heading) == pytest.approx(math.cos(heading), abs=1e-6)
    assert math.sin(back.heading) == pytest.approx(math.sin(heading), abs=1e-6)


def test_a_chunk_outside_the_jaw_s_range_is_pulled_in_and_the_count_says_so():
    there = np.array(
        [
            [0.45, -0.2, PUSH_HEIGHT - 0.05, 1.0, 0.0],
            [0.45, -0.2, PUSH_HEIGHT, 1.0, 0.0],
            [50.0, -0.2, TRAVEL_HEIGHT + 1.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    points, pulled = chunks.to_waypoints(there)
    assert pulled == 2
    assert all(PUSH_HEIGHT - 1e-9 <= p.z <= TRAVEL_HEIGHT + 1e-9 for p in points)
    assert points[1].z == pytest.approx(PUSH_HEIGHT)


def test_a_chunk_of_the_wrong_width_is_refused():
    with pytest.raises(ValueError):
        chunks.to_waypoints(np.zeros((4, 3)))


def test_the_chunk_is_charged_to_the_glass_the_jaw_ends_against():
    near, far = _seen(3, 0.50, 0.0, widest=0.08), _seen(4, 0.70, 0.0, widest=0.08)
    points = _path((0.40, 0.0, PUSH_HEIGHT, 0.0), (0.46, 0.0, PUSH_HEIGHT, 0.0))
    glass, aim = chunks.aimed_at(points, [near, far])
    assert glass == 3
    # Half a width in front of the fingertip is where the glass's middle is.
    assert aim == pytest.approx((0.46 + 0.04, 0.0))


def test_a_chunk_cannot_be_aimed_at_an_empty_table():
    with pytest.raises(ValueError):
        chunks.aimed_at(_path((0.4, 0.0, PUSH_HEIGHT, 0.0)), [])


# ---------------------------------------------------------------- the scaling


def _demonstrations(count=5):
    rng = np.random.default_rng(0)
    pictures = rng.integers(0, 256, size=(count, 8, 8, 3), dtype=np.uint8)
    actions = np.stack(
        [
            chunks.resample(
                chunks.to_action(
                    _path(
                        (0.40 + 0.01 * i, -0.2, PUSH_HEIGHT, 0.1 * i),
                        (0.50 + 0.01 * i, -0.2, PUSH_HEIGHT, 0.1 * i),
                    )
                ),
                6,
            )
            for i in range(count)
        ]
    )
    return pictures, actions


def test_the_scaling_puts_every_action_column_between_minus_one_and_one_and_comes_back():
    pictures, actions = _demonstrations()
    scale = policy_module.Scale.of(pictures, actions)
    there = scale.forward(actions)
    assert there.min() >= -1.0 - 1e-6 and there.max() <= 1.0 + 1e-6
    assert scale.back(there) == pytest.approx(actions, abs=1e-5)


def test_a_column_that_never_varies_does_not_divide_by_zero():
    pictures, actions = _demonstrations()
    # The height is the teacher's macro's, held at the lowest the jaw reaches.
    assert actions[:, :, 2].std() == pytest.approx(0.0, abs=1e-7)
    scale = policy_module.Scale.of(pictures, actions)
    assert np.isfinite(scale.forward(actions)).all()


def test_the_scaling_hands_the_model_pictures_as_colour_first_floats():
    pictures = np.zeros((5, *bench.TOP_VIEW_SIZE, 3), dtype=np.uint8)
    _, actions = _demonstrations()
    scale = policy_module.Scale.of(pictures, actions)
    rows, columns = pictures_module.SEEN_SIZE
    one = scale.picture(pictures[0])
    assert one.shape == (1, 3, rows, columns) and one.dtype == np.float32
    assert scale.picture(pictures).shape == (5, 3, rows, columns)


def test_the_bench_s_picture_is_shrunk_to_what_the_model_reads_and_stays_whole_numbers():
    rng = np.random.default_rng(1)
    picture = rng.integers(0, 256, size=(*bench.TOP_VIEW_SIZE, 3), dtype=np.uint8)
    small = pictures_module.shrink(picture)
    assert small.shape == (1, *pictures_module.SEEN_SIZE, 3) and small.dtype == np.uint8
    # Already the right size, so nothing happens and nothing is resampled twice.
    assert pictures_module.shrink(small) is small


def test_the_scaling_survives_being_saved_and_loaded(tmp_path):
    pictures, actions = _demonstrations()
    scale = policy_module.Scale.of(pictures, actions)
    scale.save(tmp_path / "scale.json")
    again = policy_module.Scale.load(tmp_path / "scale.json")
    assert again.forward(actions) == pytest.approx(scale.forward(actions), abs=1e-6)


# -------------------------------------------------------- what is not kept


class _Table:
    """Just enough of a bench for the drop rule and the loop."""

    def __init__(self, glasses, tilts=None, places=None):
        self.glasses = glasses
        self._tilts = tilts or {}
        self._places = places or {}
        self.records = []
        self.followed = []
        self.taken = {}

    def on_table(self):
        return [i for i in range(len(self.glasses)) if i not in self.taken]

    def tilt(self, i):
        return self._tilts.get(i, 0.0)

    def position(self, i):
        return np.array(self._places.get(i, (0.45, -0.2)))


class _Glass:
    def __init__(self, widest=0.08):
        self.outline = type("Outline", (), {"max_diameter": widest})()


def _record(felt=None, path=None):
    good = Felt(blocked=False, touched=0.01, jammed=False, peak=1.0, pushed=0.03)
    straight = _path(
        (0.40, -0.2, TRAVEL_HEIGHT, 0.0),
        (0.40, -0.2, PUSH_HEIGHT, 0.0),
        (0.45, -0.2, PUSH_HEIGHT, 0.0),
    )
    return Record(
        push=bench.Push(0, (0.4, -0.2), 0.0, 0.05, 0.03, (0.5, -0.2)),
        felt=felt or good,
        landed=(0.45, -0.2),
        waypoints=path if path is not None else straight,
    )


@pytest.mark.parametrize(
    ("probe", "felt", "tilts", "places", "why"),
    [
        (True, None, None, None, "a 5 mm test push, not a push at the task"),
        (False, None, {0: 45.0}, None, "a glass toppled"),
        (False, None, None, {0: (5.0, 5.0)}, "a glass left the glass zone"),
        (
            False,
            Felt(blocked=True, touched=None, jammed=False, peak=1.0, pushed=0.0),
            None,
            None,
            "blocked on the way down",
        ),
        (
            False,
            Felt(blocked=False, touched=None, jammed=False, peak=0.0, pushed=0.0),
            None,
            None,
            "never touched anything",
        ),
        (
            False,
            Felt(blocked=False, touched=0.01, jammed=True, peak=30.0, pushed=0.001),
            None,
            None,
            "jammed",
        ),
    ],
)
def test_a_push_that_did_not_work_is_dropped_and_the_reason_is_named(probe, felt, tilts, places, why):
    table = _Table([_Glass(), _Glass()], tilts=tilts, places=places)
    assert collect.dropped_because(_record(felt), probe, table, before=1.0) == why


def test_a_push_that_freed_nothing_is_dropped():
    table = _Table([_Glass(), _Glass()], places={0: (0.45, -0.2), 1: (0.46, -0.2)})
    # The shortfall afterwards is at least as large as it was before.
    assert collect.dropped_because(_record(), False, table, before=0.0) == "the table gained no room"


def test_a_push_that_worked_is_kept():
    table = _Table([_Glass()], places={0: (0.45, -0.2)})
    assert collect.dropped_because(_record(), False, table, before=1.0) is None


# -------------------------------------------------------------------- the gate


class _Camera:
    def view(self):
        return np.zeros((8, 8, 3), dtype=np.uint8)


class _Policy:
    """Always the same chunk: straight at where the test puts the crowded pair."""

    def __init__(self, x=0.46, y=-0.20):
        self.asked = 0
        self.x, self.y = x, y

    def chunk(self, picture):
        self.asked += 1
        return np.array(
            [[self.x - 0.02, self.y, PUSH_HEIGHT, 1.0, 0.0], [self.x, self.y, PUSH_HEIGHT, 1.0, 0.0]],
            dtype=np.float32,
        )


class _Standing(_Table):
    """A table that answers look() and follow() without any physics."""

    def __init__(self, seen):
        super().__init__([_Glass(g.widest) for g in seen])
        self.seen = seen

    def look(self):
        return [g for g in self.seen if g.id not in self.taken]

    def take(self, i):
        self.taken[i] = True

    def follow(self, chunk):
        self.followed.append(chunk)
        self.records.append(_record())
        return _record().felt


def test_a_glass_that_tips_before_it_slides_is_refused_and_never_reaches_the_policy():
    # A narrow foot: it tips at any friction this cell could have.
    narrow = _seen(0, 0.46, -0.20, foot=0.015)
    wide = _seen(1, 0.46, -0.14, foot=0.08)
    assert nudge.slides(narrow) == "no"
    table = _Standing([narrow, wide])
    brain = _Policy()
    refused = loop.clear(table, _Camera(), brain, loop.Tally())
    assert refused[0] == loop.TIPS
    assert all(chunk.glass == 1 for chunk in table.followed)


def test_every_glass_left_on_the_table_is_reported_with_a_reason():
    pair = [_seen(0, 0.46, -0.20), _seen(1, 0.46, -0.14)]
    table = _Standing(pair)
    refused = loop.clear(table, _Camera(), _Policy(), loop.Tally())
    assert set(refused) == {0, 1}
    assert all(reason for reason in refused.values())


def test_the_push_budget_is_the_bench_s_and_the_loop_stops_at_it():
    pair = [_seen(0, 0.46, -0.20), _seen(1, 0.46, -0.14)]
    table = _Standing(pair)
    tally = loop.Tally()
    loop.clear(table, _Camera(), _Policy(), tally)
    assert tally.chunks <= bench.PUSHES_PER_TABLE
    assert max(sum(c.glass == g for c in table.followed) for g in (0, 1)) <= bench.PUSHES_PER_GLASS


def test_a_glass_with_room_is_taken_rather_than_pushed():
    apart = [_seen(0, 0.40, -0.30), _seen(1, 0.55, -0.10)]
    table = _Standing(apart)
    brain = _Policy()
    assert loop.clear(table, _Camera(), brain, loop.Tally()) == {}
    assert table.taken == {0: True, 1: True}
    assert brain.asked == 0


# --------------------------------------------------------------- the interface


def test_an_unfitted_act_answers_with_a_chunk_the_bench_would_accept():
    pictures = np.zeros((1, *bench.TOP_VIEW_SIZE, 3), dtype=np.uint8)
    _, actions = _demonstrations()
    scale = policy_module.Scale.of(pictures, actions)
    model = policy_module.Imitator.new("act", scale, seed=0, device="cpu")
    assert model.net.config.pretrained_backbone_weights is None, "nothing is downloaded"
    assert model.chunk_length == chunks.CHUNK
    answer = model.chunk(pictures[0])
    assert answer.shape == (chunks.CHUNK, chunks.ACTION_WIDTH)
    points, _ = chunks.to_waypoints(answer)
    assert len(points) == chunks.CHUNK
    assert all(PUSH_HEIGHT - 1e-9 <= p.z <= TRAVEL_HEIGHT + 1e-9 for p in points)


def test_the_two_rungs_are_the_only_ones_offered():
    with pytest.raises(ValueError):
        policy_module.build("whatever")


@pytest.mark.parametrize(("rung", "picture_axes"), [("act", 4), ("diffusion", 5)])
def test_each_rung_is_handed_the_shape_it_expects_and_a_state_of_no_width(rung, picture_axes):
    """ACT takes a picture per example; the denoising rung takes one per observation step.

    Neither is given any robot state. The jaw is parked in the same place
    between pushes, so its pose carries nothing the picture does not, and the
    only reason the key exists at all is that LeRobot reads it.
    """
    pictures = np.zeros((2, *bench.TOP_VIEW_SIZE, 3), dtype=np.uint8)
    _, actions = _demonstrations()
    scale = policy_module.Scale.of(pictures, actions)
    net = policy_module.build(rung, seed=0, chunk=8)
    model = policy_module.Imitator(net, scale, rung, device="cpu")
    batch = model.batch(pictures, np.zeros((2, 8, chunks.ACTION_WIDTH), dtype=np.float32))
    assert batch[policy_module.PICTURE].ndim == picture_axes
    assert batch[policy_module.STATE].shape[-1] == 0
    assert batch["action"].shape == (2, 8, chunks.ACTION_WIDTH)
    assert not batch["action_is_pad"].any()
    assert net.config.pretrained_backbone_weights is None, "nothing is downloaded"


# ------------------------------------------------- a demonstration replays


def test_a_recorded_push_replayed_as_a_chunk_moves_the_same_glass_about_as_far():
    """The claim the whole method rests on: a trace is a demonstration.

    Solution 1's geometry picks a push, the bench makes it and writes down
    the path the jaw followed. Trimmed and resampled, that path is a chunk,
    and ``follow`` carries it out on the same table from the same start.
    """
    table = bench.Bench(11)
    seen = table.look()
    push, _ = nudge.choose(seen, set())
    assert push is not None
    before = table.position(push.glass).copy()
    table.push(push)
    went = float(np.linalg.norm(table.position(push.glass) - before))
    segment = chunks.push_segment(table.records[-1].waypoints)
    assert segment, "a push that touched something has a path at push height"

    again = bench.Bench(11)
    action = chunks.resample(chunks.to_action(segment), len(segment))
    points, pulled = chunks.to_waypoints(action)
    assert pulled == 0, "the bench's own path is inside the bench's own limits"
    start = again.position(push.glass).copy()
    again.follow(bench.Chunk(push.glass, points, push.aim))
    replayed = float(np.linalg.norm(again.position(push.glass) - start))
    assert replayed == pytest.approx(went, abs=0.003)
