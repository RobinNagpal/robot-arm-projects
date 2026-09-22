import math
import random

import pytest

from pick_place.settings import BLOCK
from pick_place.shapes import (
    PAD_HALF_WIDTH,
    area,
    best_grasp,
    canonical_phi,
    centroid,
    is_convex,
    random_block_outline,
    widest,
)


@pytest.fixture(scope="module")
def outlines():
    rng = random.Random(0)
    return [random_block_outline(rng) for _ in range(200)]


def test_outlines_are_convex_anticlockwise_and_centred(outlines):
    for outline in outlines:
        assert is_convex(outline)
        assert area(outline) > 0
        cx, cy = centroid(outline)
        assert abs(cx) < 1e-9 and abs(cy) < 1e-9


def test_outlines_keep_to_the_size_range(outlines):
    for outline in outlines:
        assert BLOCK.size[0] - 1e-9 <= widest(outline) <= BLOCK.size[1] + 1e-9


def test_every_outline_has_a_grasp_that_fits_the_gripper(outlines):
    for outline in outlines:
        grasp = best_grasp(outline, BLOCK.min_grip_width, BLOCK.max_grip_width)
        assert grasp is not None
        assert BLOCK.min_grip_width <= grasp.width <= BLOCK.max_grip_width


def test_the_fingers_touch_the_block_on_both_sides(outlines):
    """Along the closing line, the block's extent either side of the pinch point is half the width.

    Measured across the whole outline, not only at the pinch point: the far
    pad may meet a corner up to a pad's half width to one side.
    """
    for outline in outlines:
        g = best_grasp(outline, BLOCK.min_grip_width, BLOCK.max_grip_width)
        u = (math.cos(g.phi), math.sin(g.phi))
        v = (-u[1], u[0])
        across = [(x - g.x) * u[0] + (y - g.y) * u[1] for x, y in outline]
        assert min(across) == pytest.approx(-g.width / 2, abs=1e-9)
        assert max(across) == pytest.approx(g.width / 2, abs=1e-9)
        for extreme in (min(across), max(across)):
            touching = [
                (x - g.x) * v[0] + (y - g.y) * v[1]
                for (x, y), a in zip(outline, across, strict=True)
                if abs(a - extreme) < 1e-6
            ]
            assert min(touching) - PAD_HALF_WIDTH <= 1e-9 and max(touching) + PAD_HALF_WIDTH >= -1e-9


def test_a_square_is_held_through_its_middle():
    s = 0.02
    square = [(-s, -s), (s, -s), (s, s), (-s, s)]
    g = best_grasp(square, 0.03, 0.065)
    assert g.x == pytest.approx(0) and g.y == pytest.approx(0)
    assert g.width == pytest.approx(2 * s)


def test_a_block_too_wide_every_way_has_no_grasp():
    s = 0.05
    square = [(-s, -s), (s, -s), (s, s), (-s, s)]
    assert best_grasp(square, 0.03, 0.065) is None


@pytest.mark.parametrize("phi", [0.0, 0.5, -0.5, 1.5, -1.5, math.pi / 2, 2.0, -2.0, 3.0, -3.0])
def test_canonical_phi_is_the_same_line_in_the_right_half(phi):
    c = canonical_phi(phi)
    assert -math.pi / 2 < c <= math.pi / 2 + 1e-12
    # Same line: the directions are parallel or opposite.
    assert abs(math.sin(c - phi)) < 1e-9
