"""Checks that need no trained model and no download: the arithmetic, the shapes and the refusals.

The two that matter most are the last two. One proves that the model is never
asked about a push the geometry refused, which is the whole safety argument.
The other proves the structural property the document's account rests on: each
heading stops at the first travel that works, so a group's job-finishing
pushes all land on the same contour.
"""

from __future__ import annotations

import math

import candidates
import features
import numpy as np
import pytest
import ranker
import rollout
from candidates import nudge, rule_choice, survivors

import bench
from bench import GRIP_ROOM, Push, Seen, has_room, in_zone


def _seen(i, x, y, widest=0.08, foot=0.07, height=0.15):
    return Seen(i, x, y, height, widest, foot, True)


def _crowded_pair(turn: float = 0.0, about=(0.46, -0.21)) -> list[Seen]:
    """Two glasses too close together, turned by ``turn`` about a point."""
    spots = [(0.0, -0.05), (0.0, 0.05)]
    out = []
    for i, (dx, dy) in enumerate(spots):
        c, s = math.cos(turn), math.sin(turn)
        out.append(_seen(i, about[0] + c * dx - s * dy, about[1] + s * dx + c * dy))
    return out


def _push(glass: Seen, heading: float, travel: float) -> Push:
    aim = (glass.x + travel * math.cos(heading), glass.y + travel * math.sin(heading))
    return Push(glass.id, (glass.x, glass.y), heading, 0.05, travel, aim)


# --------------------------------------------------------------- the inputs


def test_there_are_eight_inputs_and_a_row_is_that_long():
    seen = _crowded_pair()
    row = features.row(seen[0], seen[1:], _push(seen[0], 0.0, 0.03))
    assert len(features.NAMES) == features.INPUTS == 8
    assert row.shape == (8,)
    assert np.isfinite(row).all()


def test_the_same_arrangement_moved_and_turned_is_the_same_row():
    turn = 0.9
    here, there = _crowded_pair(), _crowded_pair(turn, about=(0.40, -0.35))
    a = features.row(here[0], here[1:], _push(here[0], 0.3, 0.04))
    b = features.row(there[0], there[1:], _push(there[0], 0.3 + turn, 0.04))
    # The two distances to fixed features of the cell are the two that may
    # differ, because the cell did not move with the glasses.
    np.testing.assert_allclose(np.delete(a, [3, 4]), np.delete(b, [3, 4]), atol=1e-9)


def test_pushing_straight_away_from_the_nearest_edge_is_one_value_whatever_the_bearing():
    for bearing in np.linspace(-math.pi, math.pi, 9):
        glass = _seen(0, 0.48, -0.26)
        near = _seen(1, 0.48 + 0.06 * math.cos(bearing), -0.26 + 0.06 * math.sin(bearing))
        assert features.contact_angle(glass, [near], bearing + math.pi) == pytest.approx(math.pi)
        assert features.contact_angle(glass, [near], bearing) == pytest.approx(0.0, abs=1e-9)


def test_room_at_the_destination_is_negative_while_the_glass_is_still_crowded():
    glass, near = _seen(0, 0.48, -0.26), _seen(1, 0.48, -0.19)
    assert features.room_at((glass.x, glass.y), [near]) < 0
    far = (glass.x, glass.y - 0.08)
    assert features.room_at(far, [near]) == pytest.approx(
        math.dist(far, (near.x, near.y)) - near.widest / 2 - GRIP_ROOM
    )
    assert has_room(*far, [(near.x, near.y, near.widest)]) == (features.room_at(far, [near]) >= 0)


def test_the_distances_to_the_zone_edge_and_the_rack_are_zero_outside_them():
    x_min, x_max, y_min, y_max = bench.GLASS_ZONE
    assert features.zone_edge_distance(x_min, (y_min + y_max) / 2) == pytest.approx(0.0)
    middle = ((x_min + x_max) / 2, (y_min + y_max) / 2)
    assert features.zone_edge_distance(*middle) > 0
    assert features.rack_distance(*middle) > 0
    assert features.rack_distance(features.RACK_BOX[0] + 0.01, features.RACK_BOX[2] + 0.01) == 0.0


def test_the_crowd_is_counted_within_a_radius_nothing_wider_can_reach_past():
    glass = _seen(0, 0.48, -0.26)
    inside = _seen(1, 0.48 + features.CROWD_RADIUS - 0.001, -0.26)
    outside = _seen(2, 0.48 + features.CROWD_RADIUS + 0.001, -0.26)
    assert features.neighbours_within(glass, [inside, outside]) == 1
    # A glass further out than the radius cannot deny this one its room.
    assert features.room_at((glass.x, glass.y), [outside]) >= 0


def test_the_topple_ratio_agrees_with_the_tipping_rule_it_is_computed_from():
    # One at the limit, by construction: a foot twice the jaw's top edge times
    # the worst friction believed.
    at_the_limit = 2 * bench.JAW_TOP * nudge.MU_HIGHEST
    assert features.topple_ratio(at_the_limit) == pytest.approx(1.0)
    assert features.topple_ratio(at_the_limit + 0.01) < 1.0
    assert nudge.slides(_seen(0, 0.48, -0.26, foot=at_the_limit + 0.01)) == "yes"
    # Refused by the geometry is the same as a ratio past the ends of the
    # believed range of friction.
    refused = nudge.MU_HIGHEST / nudge.MU_LOWEST
    narrow = 2 * bench.JAW_TOP * nudge.MU_LOWEST - 0.001
    assert features.topple_ratio(narrow) > refused
    assert nudge.slides(_seen(0, 0.48, -0.26, foot=narrow)) == "no"


# ------------------------------------------------------------- the labels


def test_the_label_is_the_room_the_whole_table_gained():
    before = [_seen(0, 0.48, -0.26), _seen(1, 0.48, -0.20)]
    after = [before[0], Seen(1, 0.48, -0.14, 0.15, 0.08, 0.07, True)]
    gained = rollout.room_gained(before, after)
    assert gained == pytest.approx(
        nudge.shortfall([(g.x, g.y, g.widest) for g in before])
        - nudge.shortfall([(g.x, g.y, g.widest) for g in after])
    )
    assert gained > 0
    # Both glasses were short of room, so freeing the pair pays twice.
    assert gained > 0.06


def test_a_toppled_glass_is_the_worst_label_there_is():
    before = [_seen(0, 0.48, -0.26), _seen(1, 0.48, -0.20)]
    down = [before[0], Seen(1, 0.48, -0.30, 0.15, 0.08, 0.07, False)]
    assert -rollout.room_gained(before, down) > rollout.TOPPLED
    assert min(rollout.room_gained(before, after) for after in (before, down)) > rollout.TOPPLED


# ----------------------------------------------- what the geometry hands over


def test_each_heading_stops_at_the_first_travel_that_works():
    """At most one job-finishing push per heading, and they all land on one contour."""
    seen = bench.Bench(bench.TEST_SEEDS + 3).look()
    checked = 0
    for glass in seen:
        others = [o for o in seen if o.id != glass.id]
        layout = [(o.x, o.y, o.widest) for o in others]
        for heading in candidates.HEADINGS:
            along = nudge.along(glass, others, heading)
            freeing = [p for p in along if has_room(*p.aim, layout, nudge.AIM_MARGIN)]
            assert len(freeing) <= 1
            for push in freeing:
                checked += 1
                room = features.room_at(push.aim, others)
                assert room >= nudge.AIM_MARGIN - 1e-9
                if push.travel > nudge.STEP:
                    # The step before it did not have the room, and a step is
                    # 2 mm, so every one of these lands within 2 mm of the
                    # same line. That is why they tie on the label.
                    assert room <= nudge.AIM_MARGIN + nudge.STEP + 1e-9
    assert checked, "this table should offer at least one push that finishes the job"


def test_the_printed_rule_over_the_survivors_is_solution_ones_own_choice():
    for seed in (bench.TEST_SEEDS + 1, bench.TEST_SEEDS + 5):
        seen = bench.Bench(seed).look()
        kept, why = survivors(seen, set())
        theirs, their_why = nudge.choose(seen, set())
        mine = rule_choice(kept)
        assert (mine.push if mine else None) == theirs
        # The refusals are the same, except that solution 1 also names every
        # glass left over once it has decided to push nothing at all.
        assert set(why) <= set(their_why) and all(their_why[g] == why[g] for g in why)


# -------------------------------------------------------- where the model sits


class _Spy:
    """Scores nothing and remembers everything it was asked about."""

    def __init__(self, worst_first: bool = False) -> None:
        self.rows = np.zeros((0, features.INPUTS))
        self.worst_first = worst_first

    def __call__(self, rows: np.ndarray) -> np.ndarray:
        self.rows = np.concatenate([self.rows, rows])
        # An ordering with nothing behind it, which is the worst a model can do.
        return -np.arange(len(rows), dtype=float) if self.worst_first else np.arange(len(rows), dtype=float)


def _table_with_a_glass_that_tips() -> list[Seen]:
    narrow = 2 * bench.JAW_TOP * nudge.MU_LOWEST - 0.002
    return [
        _seen(0, 0.42, -0.30),
        _seen(1, 0.42, -0.20),
        Seen(2, 0.56, -0.30, 0.15, 0.08, narrow, True),
        Seen(3, 0.56, -0.20, 0.15, 0.08, narrow, True),
    ]


def test_the_model_is_never_asked_about_a_push_the_geometry_refused():
    seen = _table_with_a_glass_that_tips()
    spy = _Spy()
    push, why = ranker.choose(seen, set(), spy)

    assert why[2] == why[3] == "tips before it slides"
    assert push is not None and push.glass not in (2, 3)
    # Every row the model saw is a push the geometry allowed, and the proof is
    # in the rows themselves: the topple ratio is one of the eight inputs.
    assert len(spy.rows) > 0
    assert spy.rows[:, 7].max() < nudge.MU_HIGHEST / nudge.MU_LOWEST
    # And every destination it saw is inside the zone and short of the limits.
    kept, _ = survivors(seen, set())
    assert len(kept) == len(spy.rows)
    for candidate in kept:
        assert candidate.glass.id not in (2, 3)
        assert in_zone(*candidate.push.aim)
        assert nudge.reachable(np.array(candidate.push.aim))


def test_an_ordering_with_nothing_behind_it_still_cannot_make_an_unsafe_push():
    seen = _table_with_a_glass_that_tips()
    kept, _ = survivors(seen, set())
    for backwards in (False, True):
        push, _ = ranker.choose(seen, set(), _Spy(worst_first=backwards))
        assert push in [c.push for c in kept]
        assert in_zone(*push.aim) and nudge.slides(next(g for g in seen if g.id == push.glass)) != "no"


def test_a_glass_already_pushed_too_often_is_not_offered_to_the_model():
    seen = _table_with_a_glass_that_tips()
    spy = _Spy()
    push, why = ranker.choose(seen, {0}, spy)
    kept, _ = survivors(seen, {0})
    assert 0 not in {c.glass.id for c in kept}
    assert push is None or push.glass != 0


# ------------------------------------------------------------- the interface


def test_the_ranker_sorts_by_its_own_score_and_survives_a_round_trip(tmp_path):
    rng = np.random.default_rng(0)
    rows = rng.normal(size=(200, features.INPUTS))
    # Something the trees can find: the label is the second input, which is travel.
    model = ranker.Ranker.fit(rows, rows[:, 1])
    assert model.importances()[0][0] == features.NAMES[1]

    path = tmp_path / "ranker.joblib"
    model.save(path)
    again = ranker.Ranker.load(path)
    np.testing.assert_allclose(model(rows[:5]), again(rows[:5]))

    seen = _crowded_pair()
    best, scores, _ = ranker.ranked(seen, set(), model)
    assert len(best) == len(scores) > 0
    assert (np.diff(scores) <= 1e-12).all()
    assert scores[0] == max(scores)
