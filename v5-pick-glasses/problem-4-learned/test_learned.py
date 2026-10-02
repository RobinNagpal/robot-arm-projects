"""Quick checks that need neither training nor a long run."""

from __future__ import annotations

import math

import numpy as np
import torch

import nets
import push_features as features
import rack_plan
import tables
from bench import KINDS, Seen


def _table(turn: float = 0.0) -> list[Seen]:
    middle = np.array([0.48, -0.26])
    seen = []
    for i, (dx, dy) in enumerate([(0.0, 0.0), (0.09, 0.02), (-0.03, 0.11)]):
        c, s = math.cos(turn), math.sin(turn)
        x, y = middle + [c * dx - s * dy, s * dx + c * dy]
        seen.append(Seen(i, float(x), float(y), 0.15, 0.07, 0.06, True))
    return seen


def test_every_table_has_two_kinds_and_a_crowded_glass():
    for seed in range(20):
        glasses = tables.scene(seed)
        assert 4 <= len(glasses) <= 6
        assert len({g.kind for g in glasses}) >= 2


def test_no_table_is_both_trained_and_held_out():
    assert tables.TEST_SEEDS > 9000 + 200


def test_a_turned_table_is_the_same_push():
    kinds = {0: "straight_glass", 2: "stemmed_glass"}
    a = features.encode(_table(), _table()[0], kinds, 0.4, 0.01, 0.05)
    b = features.encode(_table(1.1), _table(1.1)[0], kinds, 0.4 + 1.1, 0.01, 0.05)
    np.testing.assert_allclose(a, b, atol=1e-5)


def test_a_glass_not_measured_has_no_foot_and_says_so():
    row = features.encode(_table(), _table()[0], {}, 0.0, 0.0, 0.05)[0]
    assert row[features.LABELS.index(features.NOT_MEASURED)] == 1
    assert row[len(features.LABELS) + 2] == 0  # the foot


def test_mirroring_twice_changes_nothing():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(8, features.INPUTS)).astype(np.float32)
    y = rng.normal(size=(8, features.OUTPUTS)).astype(np.float32)
    x2, y2 = features.mirror(*features.mirror(x, y))
    np.testing.assert_array_equal(x, x2)
    np.testing.assert_array_equal(y, y2)


def test_the_rack_plan_keeps_room_for_a_wide_glass():
    # Slot 0 for a narrow glass leaves 2..5 free, room for two wide glasses
    # (2 and 4 with their neighbours). Taking slot 1 would leave room for one.
    free = rack_plan.ALL
    assert rack_plan.capacity(free - rack_plan.consumed(0, False), (True, True)) == 2
    assert rack_plan.capacity(free - rack_plan.consumed(1, False), (True, True)) == 1
    assert rack_plan.best_slot(free, False, [True, True]) in (0, 5)


def test_a_wide_glass_needs_its_neighbours_free():
    assert rack_plan.usable(frozenset({1, 2, 3}), True) == [2]
    assert rack_plan.usable(frozenset({1, 3}), True) == []


def test_side_net_gives_shape_and_kind():
    out = nets.SideNet().eval()(torch.zeros(2, 1, *nets.SMALL))
    assert out.shape == (2, 17 + len(KINDS))


def test_grip_labels_come_from_the_rule():
    # The rule never finds a grip on a short-stemmed glass in this cell, and
    # always does on a straight one: GripNet has both answers to learn.
    from work_cell.glasses.shapes import family

    short = [tables.true_grip("short_stemmed_glass", o) for o, _ in family("short_stemmed_glass", 10, 1)]
    straight = [tables.true_grip("straight_glass", o) for o, _ in family("straight_glass", 10, 1)]
    assert not any(g.holdable for g in short)
    assert all(g.holdable and 0 < g.height < 0.5 * o.total_height
               for g, (o, _) in zip(straight, family("straight_glass", 10, 1), strict=True))  # fmt: skip
