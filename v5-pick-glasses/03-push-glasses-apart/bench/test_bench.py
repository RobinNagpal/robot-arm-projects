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


def _push_once(kind, outline):
    """One square push of 40 mm against a glass standing on its own."""
    table = _alone(kind, outline)
    seen = table.look()[0]
    radius = seen.widest / 2
    felt = table.push(bench.Push(0, (seen.x - radius - 0.01, seen.y), 0.0, radius + 0.04, 0.04, (0, 0)))
    return table, felt


def test_a_push_slides_a_straight_glass_about_as_far_as_asked():
    """A tumbler is the clean case: straight walls and its weight low down, so
    the jaw meets it square and it goes where it is sent."""
    for outline, _ in family("straight_glass", 3, seed=2):
        table, felt = _push_once("straight_glass", outline)
        assert felt.touched is not None and not felt.blocked
        moved = table.position(0) - table.start[0]
        # The contact takes up a little before the glass moves.
        assert 0.030 < moved[0] < 0.041 and abs(moved[1]) < 0.003
        assert table.tilt(0) < 1.0


def test_a_push_at_this_height_tips_a_third_of_glasses_pushed_carelessly():
    """The price of holding the hand rolled, and the reason this problem is
    harder than it used to look.

    The hand has to be turned on its side to fit between the glasses at all,
    and turned on its side it cannot ride lower than 75 mm, because its fingers
    would strike the table. Pushed 75 mm up, a glass whose weight sits high —
    a tapered one, a short-stemmed one — tips over instead of sliding.

    This is not a fault to fix in the bench. It is the physics the six
    solutions are being asked to cope with, and coping with it is most of what
    separates them: a solution that pushes whatever it likes will topple
    glasses, and a toppled glass is a *wrong* outcome and not merely an
    unfinished one. Solution 1's probe exists for exactly this.

    The bound is loose on purpose. What is being asserted is that the risk is
    real and not universal, because a bench where nothing tipped would not be
    testing the thing that matters and one where everything tipped would leave
    nothing to measure.
    """
    toppled = standing = 0
    for kind in bench.KINDS:
        for outline, _ in family(kind, 12, seed=2):
            table, _ = _push_once(kind, outline)
            if table.tilt(0) >= bench.STANDING_TILT_DEG:
                toppled += 1
            else:
                standing += 1
    total = toppled + standing
    assert 0.15 * total <= toppled <= 0.55 * total, f"{toppled} of {total} toppled"


def test_a_straight_glass_is_the_one_kind_a_careless_push_never_tips():
    """Its walls are upright and its weight is low, so the jaw pushes it below
    its own centre of mass however tall it is. Worth stating because it is why
    the tables of tumblers are the ones every solution does best on."""
    for outline, _ in family("straight_glass", 12, seed=2):
        table, _ = _push_once("straight_glass", outline)
        assert table.tilt(0) < bench.STANDING_TILT_DEG


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
