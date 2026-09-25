"""The scenes, the collision shape and the push, on glasses drawn across their range."""

import math

import numpy as np
import pytest
from work_cell.glasses.shapes import family
from work_cell.glasses.spawn import SpawnedGlass

import bench


def _alone(kind: str, outline) -> bench.Bench:
    return bench.Bench(0, [SpawnedGlass("glass_0", kind, outline, (0.48, -0.26, bench.TABLE_TOP_Z), 0.0)])


@pytest.mark.parametrize("seed", [*range(12), *range(bench.TEST_SEEDS, bench.TEST_SEEDS + 12)])
def test_every_table_is_crowded_but_nothing_touches(seed):
    glasses = bench.scene(seed)
    spots = [(g.position[0], g.position[1], g.outline.max_diameter) for g in glasses]
    assert all(bench.in_zone(x, y) for x, y, _ in spots)
    for i, (x, y, w) in enumerate(spots):
        for ox, oy, ow in spots[i + 1 :]:
            assert math.dist((x, y), (ox, oy)) >= (w + ow) / 2 + bench.START_GAP - 1e-9
    assert any(not bench.has_room(x, y, [s for s in spots if s[:2] != (x, y)]) for x, y, _ in spots)


@pytest.mark.parametrize("kind", bench.KINDS)
def test_the_collision_shape_is_never_thinner_than_the_glass(kind):
    for outline, _ in family(kind, 10, seed=7):
        for bottom, top, radius in bench.slices(outline):
            inside = (outline.height >= bottom) & (outline.height <= top)
            assert radius >= outline.radius[inside].max() - 1e-9
        assert bench.slices(outline)[0][0] == 0.0


@pytest.mark.parametrize("kind", bench.KINDS)
def test_a_low_push_slides_a_glass_about_as_far_as_asked(kind):
    for outline, _ in family(kind, 3, seed=2):
        table = _alone(kind, outline)
        seen = table.look()[0]
        radius = seen.widest / 2
        felt = table.push(bench.Push(0, (seen.x - radius - 0.01, seen.y), 0.0, radius + 0.04, 0.04, (0, 0)))
        assert felt.touched is not None and not felt.blocked
        moved = table.position(0) - table.start[0]
        # The contact takes up a little before the glass moves; most on a
        # thin stem, which leans before it slides.
        assert 0.030 < moved[0] < 0.041 and abs(moved[1]) < 0.003
        assert table.tilt(0) < 1.0


def test_the_first_look_is_the_same_for_every_approach():
    first, again = bench.Bench(bench.TEST_SEEDS).look(), bench.Bench(bench.TEST_SEEDS).look()
    assert first == again


def test_a_look_carries_error_but_not_much():
    table = bench.Bench(bench.TEST_SEEDS)
    errors = [math.dist((s.x, s.y), table.position(s.id)) for _ in range(20) for s in table.look()]
    assert 0.0 < np.median(errors) < 0.002


def test_taking_a_crowded_glass_is_recorded_as_wrong():
    table = bench.Bench(bench.TEST_SEEDS)
    others = [(*table.position(j), g.outline.max_diameter) for j, g in enumerate(table.glasses)]
    crowded = next(
        i for i in range(len(others)) if not bench.has_room(*others[i][:2], others[:i] + others[i + 1 :])
    )
    table.take(crowded)
    assert table.taken[crowded] is False
    assert crowded not in [s.id for s in table.look()]
