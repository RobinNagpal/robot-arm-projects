"""Quick checks that need neither training nor a long run."""

from __future__ import annotations

import math

import numpy as np

import features
import plan
from bench import GRIP_ROOM, Seen, in_zone


def _table(turn: float = 0.0) -> list[Seen]:
    """Three glasses round (0.48, -0.26), turned by ``turn`` about that point."""
    middle = np.array([0.48, -0.26])
    spots = [(0.0, 0.0), (0.09, 0.02), (-0.03, 0.11)]
    seen = []
    for i, (dx, dy) in enumerate(spots):
        c, s = math.cos(turn), math.sin(turn)
        x, y = middle + [c * dx - s * dy, s * dx + c * dy]
        seen.append(Seen(i, float(x), float(y), 0.15, 0.07, 0.06, True))
    return seen


def test_a_turned_table_is_the_same_example():
    a = features.encode(_table(), _table()[0], "straight_glass", 0.4, 0.01, 0.05)
    b = features.encode(_table(1.1), _table(1.1)[0], "straight_glass", 0.4 + 1.1, 0.01, 0.05)
    np.testing.assert_allclose(a, b, atol=1e-5)


def test_mirroring_twice_changes_nothing():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(8, features.INPUTS)).astype(np.float32)
    y = rng.normal(size=(8, features.OUTPUTS)).astype(np.float32)
    x2, y2 = features.mirror(*features.mirror(x, y))
    np.testing.assert_array_equal(x, x2)
    np.testing.assert_array_equal(y, y2)


def test_mirrored_offset_matches_a_mirrored_push():
    seen = _table()
    row = features.encode(seen, seen[0], "straight_glass", 0.0, 0.01, 0.05)
    flipped = [Seen(s.id, s.x, 2 * seen[0].y - s.y, s.height, s.widest, s.foot, True) for s in seen]
    other = features.encode(flipped, flipped[0], "straight_glass", 0.0, -0.01, 0.05)
    np.testing.assert_allclose(features.mirror(row, np.zeros((1, features.OUTPUTS)))[0], other, atol=1e-5)


def test_outcome_reads_movement_in_the_push_frame():
    before = _table()
    moved = [Seen(0, before[0].x, before[0].y + 0.03, 0.15, 0.07, 0.06, True), *before[1:]]
    row = features.outcome(before, moved, before[0], math.pi / 2, False)
    assert abs(row[0] * features.MOVE_SCALE - 0.03) < 1e-6 and abs(row[1]) < 1e-6
    assert row[features.TOPPLED] == 0


def test_no_shortfall_when_every_glass_has_room():
    widest = np.array([0.08, 0.08])
    apart = np.array([[0.0, 0.0], [GRIP_ROOM + 0.05, 0.0]])
    close = np.array([[0.0, 0.0], [0.10, 0.0]])
    assert plan.shortfall(apart, widest) == 0.0
    assert plan.shortfall(close, widest) > 0.0


class _Straight:
    """A stand-in model: every push moves the glass exactly its travel, and nothing topples."""

    def predict(self, rows: np.ndarray) -> np.ndarray:
        out = np.zeros((1, len(rows), features.OUTPUTS), dtype=np.float32)
        out[0, :, 0] = rows[:, len(features.KINDS) + 4]
        out[0, :, features.TOPPLED] = -10.0
        out[0, :, features.BLOCKED] = -10.0
        return out


def test_the_planner_keeps_to_the_map():
    seen = _table()
    verdict = plan.best_push(_Straight(), seen, seen[0], "straight_glass", np.random.default_rng(0))
    assert verdict.choice is not None
    assert in_zone(*verdict.choice.aim)


def test_a_glass_left_standing_near_the_edge_does_not_block_every_push():
    from bench import GLASS_ZONE

    seen = [*_table(), Seen(3, 0.40, GLASS_ZONE[3] - 0.005, 0.15, 0.07, 0.06, True)]
    verdict = plan.best_push(_Straight(), seen, seen[0], "straight_glass", np.random.default_rng(0))
    assert verdict.choice is not None
