"""What each class of shape is, as an outline on paper.

Every shape is a block: a flat outline pushed up into a solid, the way a
biscuit cutter makes a biscuit. This file only knows the outline. How thick
the block is and how it sits on the table are drawn in ``randomization.py``.

Each outline is a list of (x, y) corners in metres, going anticlockwise,
centred on its own centroid, scaled so that its widest distance across is
exactly ``size``. Using the same meaning of size for every class stops the
model from telling classes apart by how big they are.

No Gazebo in here, so the tests can check the geometry directly.
"""

from __future__ import annotations

import math
import random

CLASSES = ("triangle", "square", "rectangle", "rhombus", "pentagon", "hexagon", "octagon")

# Two classes that are close to each other have to be kept apart on purpose,
# or some labels are wrong by design: a 1.05 : 1 rectangle is a square to any
# eye. These are the gaps.
RECTANGLE_RATIO = (1.4, 2.5)
# A rhombus with corners near 90 degrees is a square turned 45 degrees.
RHOMBUS_ACUTE_ANGLE = (math.radians(45), math.radians(72))
# A triangle with one very sharp corner looks like a line from most angles.
TRIANGLE_MIN_ANGLE = math.radians(35)


def outline(name: str, size: float, rng: random.Random) -> list[tuple[float, float]]:
    """The corners of one shape of class ``name``, ``size`` metres across at its widest."""
    if name == "triangle":
        points = _triangle(rng)
    elif name == "square":
        points = _parallelogram(1.0, math.pi / 2)
    elif name == "rectangle":
        points = _parallelogram(rng.uniform(*RECTANGLE_RATIO), math.pi / 2)
    elif name == "rhombus":
        points = _parallelogram(1.0, rng.uniform(*RHOMBUS_ACUTE_ANGLE))
    elif name in ("pentagon", "hexagon", "octagon"):
        corners = {"pentagon": 5, "hexagon": 6, "octagon": 8}[name]
        points = [
            (math.cos(2 * math.pi * i / corners), math.sin(2 * math.pi * i / corners)) for i in range(corners)
        ]
    else:
        raise ValueError(f"unknown shape class {name!r}; the classes are {CLASSES}")
    return _scaled(_centred(points), size)


def _triangle(rng: random.Random) -> list[tuple[float, float]]:
    """Any triangle whose three corners are all at least TRIANGLE_MIN_ANGLE."""
    while True:
        a = rng.uniform(TRIANGLE_MIN_ANGLE, math.pi - 2 * TRIANGLE_MIN_ANGLE)
        b = rng.uniform(TRIANGLE_MIN_ANGLE, math.pi - 2 * TRIANGLE_MIN_ANGLE)
        if math.pi - a - b >= TRIANGLE_MIN_ANGLE:
            break
    # Base of length 1 along x; the apex is where the lines at angles a and b meet.
    apex_x = math.tan(b) / (math.tan(a) + math.tan(b))
    return [(0.0, 0.0), (1.0, 0.0), (apex_x, apex_x * math.tan(a))]


def _parallelogram(ratio: float, angle: float) -> list[tuple[float, float]]:
    """Sides of ``ratio`` and 1, meeting at ``angle``. Squares, rectangles and rhombuses are all this."""
    dx, dy = math.cos(angle), math.sin(angle)
    return [(0.0, 0.0), (ratio, 0.0), (ratio + dx, dy), (dx, dy)]


def _centred(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cx, cy = polygon_centroid(points)
    return [(x - cx, y - cy) for x, y in points]


def _scaled(points: list[tuple[float, float]], size: float) -> list[tuple[float, float]]:
    scale = size / widest(points)
    return [(x * scale, y * scale) for x, y in points]


def widest(points: list[tuple[float, float]]) -> float:
    """The largest distance between any two corners."""
    return max(math.dist(p, q) for p in points for q in points)


def polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """The centre of mass of the flat shape, not the average of its corners."""
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (3 * area), cy / (3 * area)


def narrowest(points: list[tuple[float, float]]) -> float:
    """The smallest width of the shape, over every direction it could be measured in.

    For a convex outline the narrowest width is always measured square to one
    of its own edges, so trying each edge is enough.
    """
    best = math.inf
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        length = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / length, (x1 - x0) / length
        offsets = [(x - x0) * nx + (y - y0) * ny for x, y in points]
        best = min(best, max(offsets) - min(offsets))
    return best


def stable_edges(points: list[tuple[float, float]]) -> list[int]:
    """The edges the block can stand on without tipping over.

    Standing on edge ``i`` (from corner ``i`` to corner ``i + 1``) is stable
    when the centroid sits above that edge, not beyond one end of it. Regular
    shapes are stable on every edge; a lopsided triangle is not.
    """
    cx, cy = polygon_centroid(points)
    stable = []
    for i, ((x0, y0), (x1, y1)) in enumerate(zip(points, points[1:] + points[:1], strict=True)):
        along = ((cx - x0) * (x1 - x0) + (cy - y0) * (y1 - y0)) / ((x1 - x0) ** 2 + (y1 - y0) ** 2)
        if 0.0 < along < 1.0:
            stable.append(i)
    return stable


def standing_on_edge(points: list[tuple[float, float]], edge: int) -> list[tuple[float, float]]:
    """The outline turned so that ``edge`` lies along y = 0 with the rest of the shape above it.

    The x values stay centred on the centroid, so the block stands over the
    same spot it was placed at.
    """
    (x0, y0), (x1, y1) = points[edge], points[(edge + 1) % len(points)]
    angle = -math.atan2(y1 - y0, x1 - x0)
    c, s = math.cos(angle), math.sin(angle)
    turned = [(x * c - y * s, x * s + y * c) for x, y in points]
    floor = min(y for _, y in turned)
    return [(x, y - floor) for x, y in turned]
