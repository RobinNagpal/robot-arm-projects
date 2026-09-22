"""The outlines: each class has the corners, sides and angles it claims to have."""

import math
import random

import pytest

from synthetic.shapes import (
    CLASSES,
    RECTANGLE_RATIO,
    RHOMBUS_ACUTE_ANGLE,
    TRIANGLE_MIN_ANGLE,
    narrowest,
    outline,
    polygon_centroid,
    stable_edges,
    standing_on_edge,
    widest,
)

CORNERS = {
    "triangle": 3,
    "square": 4,
    "rectangle": 4,
    "rhombus": 4,
    "pentagon": 5,
    "hexagon": 6,
    "octagon": 8,
}


def sides(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:] + points[:1], strict=True)]


def angles(points):
    """The inside angle at each corner."""
    result = []
    for i, (x, y) in enumerate(points):
        (ax, ay), (bx, by) = points[i - 1], points[(i + 1) % len(points)]
        u, v = (ax - x, ay - y), (bx - x, by - y)
        result.append(math.acos((u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))))
    return result


def signed_area(points):
    return (
        sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)) / 2
    )


def many(name, count=200):
    rng = random.Random(name)
    return [outline(name, rng.uniform(0.04, 0.12), rng) for _ in range(count)]


@pytest.mark.parametrize("name", CLASSES)
def test_every_outline_has_its_corners_its_size_and_its_centre(name):
    rng = random.Random(1)
    for _ in range(100):
        size = rng.uniform(0.04, 0.12)
        points = outline(name, size, rng)
        assert len(points) == CORNERS[name]
        assert widest(points) == pytest.approx(size)
        assert polygon_centroid(points) == pytest.approx((0, 0), abs=1e-12)
        assert signed_area(points) > 0  # anticlockwise


def test_a_square_has_equal_sides_and_right_angles():
    for points in many("square"):
        assert max(sides(points)) == pytest.approx(min(sides(points)))
        assert angles(points) == pytest.approx([math.pi / 2] * 4)


def test_a_rectangle_is_never_nearly_a_square():
    for points in many("rectangle"):
        assert angles(points) == pytest.approx([math.pi / 2] * 4)
        ratio = max(sides(points)) / min(sides(points))
        assert RECTANGLE_RATIO[0] - 1e-9 <= ratio <= RECTANGLE_RATIO[1] + 1e-9


def test_a_rhombus_has_equal_sides_and_is_never_nearly_a_square():
    for points in many("rhombus"):
        assert max(sides(points)) == pytest.approx(min(sides(points)))
        assert RHOMBUS_ACUTE_ANGLE[0] - 1e-9 <= min(angles(points)) <= RHOMBUS_ACUTE_ANGLE[1] + 1e-9


def test_a_triangle_has_no_needle_sharp_corner():
    for points in many("triangle"):
        assert min(angles(points)) >= TRIANGLE_MIN_ANGLE - 1e-9
        assert sum(angles(points)) == pytest.approx(math.pi)


@pytest.mark.parametrize("name", ["pentagon", "hexagon", "octagon"])
def test_the_many_sided_shapes_are_regular(name):
    for points in many(name, 20):
        assert max(sides(points)) == pytest.approx(min(sides(points)))


def test_narrowest_width_of_known_shapes():
    square = [(0, 0), (2, 0), (2, 2), (0, 2)]
    rectangle = [(0, 0), (3, 0), (3, 1), (0, 1)]
    assert narrowest(square) == pytest.approx(2)
    assert narrowest(rectangle) == pytest.approx(1)


def test_a_lopsided_triangle_cannot_stand_on_every_edge():
    # The corner at (5, 1) hangs far beyond the short edge from (0, 0) to (1, 0).
    triangle = [(0.0, 0.0), (1.0, 0.0), (5.0, 1.0)]
    assert 0 not in stable_edges(triangle)
    assert stable_edges(triangle)


@pytest.mark.parametrize("name", CLASSES)
def test_standing_on_an_edge_puts_that_edge_on_the_floor_and_the_rest_above(name):
    rng = random.Random(2)
    for _ in range(50):
        points = outline(name, 0.1, rng)
        for edge in stable_edges(points):
            upright = standing_on_edge(points, edge)
            a, b = upright[edge], upright[(edge + 1) % len(upright)]
            assert a[1] == pytest.approx(0, abs=1e-12)
            assert b[1] == pytest.approx(0, abs=1e-12)
            assert min(y for _, y in upright) == pytest.approx(0, abs=1e-12)
            # Turning is not stretching.
            assert sides(upright) == pytest.approx(sides(points))
