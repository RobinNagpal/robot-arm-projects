"""Irregular outlines: a set number of sides, but no two sides or corners forced equal.

For a regular shape the centre of mass is also the middle of its corners and
the middle of its bounding box, so a model can land on it without learning
anything about mass. For an irregular one it is not, which is the point of
this dataset.

Every outline is convex, goes anticlockwise, is centred on its own centroid,
and is scaled so its widest distance across is exactly ``size``, the same
meaning of size as in ``synthetic/shapes.py``.

No Gazebo in here, so the tests can check the geometry directly.
"""

from __future__ import annotations

import math
import random

from synthetic.shapes import polygon_centroid, widest

SIDES = {"triangle": 3, "quadrilateral": 4, "pentagon": 5, "hexagon": 6, "octagon": 8}
CLASSES = tuple(SIDES)

# The longest side is 1.6 to 3 times the shortest, so no shape comes out
# close to regular by chance.
SIDE_RATIO = (1.6, 3.0)
# A corner sharper than this looks like a spike; one flatter than the upper
# limit barely shows, and a hexagon with such a corner reads as a pentagon.
CORNER_ANGLE = (math.radians(30), math.radians(160))
# The widest corner is at least this much wider than the sharpest, so the
# corners are uneven too, not only the sides.
CORNER_SPREAD = math.radians(25)
# How far each corner's direction and distance from the middle may wander
# from a regular shape's, before the checks above accept or reject it.
DIRECTION_JITTER = 0.45  # fraction of the angle between two corners
DISTANCE_RANGE = (0.3, 1.0)
# The whole shape is then stretched one way by up to this much, so some
# shapes come out long and narrow rather than all roughly round.
STRETCH = (1.0, 2.5)


def irregular_outline(name: str, size: float, rng: random.Random) -> list[tuple[float, float]]:
    """The corners of one irregular shape of class ``name``, ``size`` metres across at its widest."""
    if name not in SIDES:
        raise ValueError(f"unknown class {name!r}; the classes are {CLASSES}")
    sides = SIDES[name]
    step = 2 * math.pi / sides
    # Rejection sampling: draw near a regular shape, keep the first that
    # passes. Octagons pass least often, about one draw in a thousand, which
    # still takes under a millisecond.
    while True:
        stretch = rng.uniform(*STRETCH)
        points = []
        for i in range(sides):
            direction = (i + rng.uniform(-DIRECTION_JITTER, DIRECTION_JITTER)) * step
            distance = rng.uniform(*DISTANCE_RANGE)
            points.append((stretch * distance * math.cos(direction), distance * math.sin(direction)))
        if is_accepted(points):
            break
    cx, cy = polygon_centroid(points)
    scale = size / widest(points)
    return [((x - cx) * scale, (y - cy) * scale) for x, y in points]


def is_accepted(points: list[tuple[float, float]]) -> bool:
    lengths = side_lengths(points)
    angles = corner_angles(points)
    return (
        is_convex(points)
        and SIDE_RATIO[0] <= max(lengths) / min(lengths) <= SIDE_RATIO[1]
        and CORNER_ANGLE[0] <= min(angles)
        and max(angles) <= CORNER_ANGLE[1]
        and max(angles) - min(angles) >= CORNER_SPREAD
    )


def side_lengths(points: list[tuple[float, float]]) -> list[float]:
    return [math.dist(p, q) for p, q in zip(points, points[1:] + points[:1], strict=True)]


def corner_angles(points: list[tuple[float, float]]) -> list[float]:
    """The inside angle at each corner, in radians, for a convex outline."""
    result = []
    for i, (x, y) in enumerate(points):
        (ax, ay), (bx, by) = points[i - 1], points[(i + 1) % len(points)]
        before, after = math.atan2(ay - y, ax - x), math.atan2(by - y, bx - x)
        angle = abs(before - after) % (2 * math.pi)
        result.append(min(angle, 2 * math.pi - angle))
    return result


def is_convex(points: list[tuple[float, float]]) -> bool:
    """Every corner turns left, which for an anticlockwise outline means convex."""
    for i in range(len(points)):
        (ax, ay), (bx, by), (cx, cy) = points[i - 1], points[i], points[(i + 1) % len(points)]
        if (bx - ax) * (cy - by) - (by - ay) * (cx - bx) <= 0:
            return False
    return True
