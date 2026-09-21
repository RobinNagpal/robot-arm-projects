"""Irregular block outlines, and where two parallel fingers can hold one.

The outlines follow v4's centre-of-mass dataset: a set number of sides, no two
sides or corners forced equal, always convex. What is new here is that the
gripper has to be able to hold every one, so an outline only counts if it
has a grasp: a pair of opposite sides no wider apart than the open fingers.

Everything is plain geometry on lists of (x, y) corners, with no MuJoCo, so
the tests can check it directly.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .settings import BLOCK, BlockRanges

Point = tuple[float, float]

# The longest side is 1.4 to 3 times the shortest, so no shape comes out
# close to regular by chance.
SIDE_RATIO = (1.4, 3.0)
CORNER_ANGLE = (math.radians(30), math.radians(160))
DIRECTION_JITTER = 0.4  # fraction of the angle between two corners
DISTANCE_RANGE = (0.4, 1.0)
# Stretch one way, so shapes come out long and narrow rather than round, and
# most of them fit between the fingers across their short way.
STRETCH = (1.3, 2.5)

# Half the width of a finger pad, less a margin, metres. A pad centred more
# than this beyond the end of a side slips off the corner.
PAD_HALF_WIDTH = 0.008
# Corners this close to the extreme count as touching the pad. Only rounding
# error: a corner even a millimetre short is not what the pad meets first.
TOUCH = 1e-9


@dataclass(frozen=True)
class Grasp:
    """Where the pinch point goes and which way the fingers close, in the outline's own frame."""

    x: float
    y: float
    phi: float  # direction the fingers close along, radians
    width: float  # how far apart the two touching sides are, metres


def irregular_outline(sides: int, size: float, rng: random.Random) -> list[Point]:
    """Corners of one convex irregular outline, centred on its centre of mass.

    ``size`` is its widest distance across, in metres.
    """
    step = 2 * math.pi / sides
    while True:
        stretch = rng.uniform(*STRETCH)
        points = []
        for i in range(sides):
            direction = (i + rng.uniform(-DIRECTION_JITTER, DIRECTION_JITTER)) * step
            distance = rng.uniform(*DISTANCE_RANGE)
            points.append((stretch * distance * math.cos(direction), distance * math.sin(direction)))
        if is_irregular(points):
            break
    cx, cy = centroid(points)
    scale = size / widest(points)
    return [((x - cx) * scale, (y - cy) * scale) for x, y in points]


def random_block_outline(rng: random.Random, ranges: BlockRanges = BLOCK) -> list[Point]:
    """An irregular outline the gripper can hold, drawn until one fits."""
    while True:
        outline = irregular_outline(rng.choice(ranges.sides), rng.uniform(*ranges.size), rng)
        if best_grasp(outline, ranges.min_grip_width, ranges.max_grip_width) is not None:
            return outline


def best_grasp(outline: list[Point], min_width: float, max_width: float) -> Grasp | None:
    """The grasp that holds the block closest to its centre of mass, or None if there is none.

    One finger lies flat on a side, and the other closes straight towards
    it, meeting whatever is opposite: a side or a corner. Trying each side
    as the flat one covers every grasp worth having. The outline's centre of
    mass is at the origin, so the distance from the pinch point to the line
    through it along the fingers is how hard gravity twists the block.
    """
    best: tuple[float, Grasp] | None = None
    for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1], strict=True):
        length = math.hypot(x1 - x0, y1 - y0)
        # u points into the shape, square to this side; v runs along the side.
        ux, uy = -(y1 - y0) / length, (x1 - x0) / length
        vx, vy = -uy, ux
        across = [(x - x0) * ux + (y - y0) * uy for x, y in outline]
        along = [(x - x0) * vx + (y - y0) * vy for x, y in outline]
        width = max(across)
        if not min_width <= width <= max_width:
            continue
        near = [a for a, c in zip(along, across, strict=True) if c < TOUCH]
        far = [a for a, c in zip(along, across, strict=True) if c > width - TOUCH]
        # The pad on the flat side is centred on that side; the far pad has
        # to reach the far corner or side.
        low = max(min(near), min(far) - PAD_HALF_WIDTH)
        high = min(max(near), max(far) + PAD_HALF_WIDTH)
        if low > high:
            continue
        # Along the side, the point closest to the centre of mass.
        centre_of_mass_along = -(x0 * vx + y0 * vy)
        v = min(max(centre_of_mass_along, low), high)
        u = width / 2
        grasp = Grasp(
            x=x0 + u * ux + v * vx,
            y=y0 + u * uy + v * vy,
            phi=math.atan2(uy, ux),
            width=width,
        )
        score = abs(v - centre_of_mass_along)
        if best is None or score < best[0]:
            best = (score, grasp)
    return None if best is None else best[1]


def canonical_phi(phi: float) -> float:
    """The same closing direction, turned into (-pi/2, pi/2].

    The fingers are symmetric, so phi and phi + pi are the same grasp. Keeping
    to one half stops the wrist from ever turning more than a quarter turn
    from its home angle.
    """
    phi = math.remainder(phi, math.pi)
    return phi if phi > -math.pi / 2 else phi + math.pi


def is_irregular(points: list[Point]) -> bool:
    lengths = [math.dist(p, q) for p, q in zip(points, points[1:] + points[:1], strict=True)]
    angles = corner_angles(points)
    return (
        is_convex(points)
        and SIDE_RATIO[0] <= max(lengths) / min(lengths) <= SIDE_RATIO[1]
        and CORNER_ANGLE[0] <= min(angles)
        and max(angles) <= CORNER_ANGLE[1]
    )


def corner_angles(points: list[Point]) -> list[float]:
    """The inside angle at each corner, in radians, for a convex outline."""
    result = []
    for i, (x, y) in enumerate(points):
        (ax, ay), (bx, by) = points[i - 1], points[(i + 1) % len(points)]
        before, after = math.atan2(ay - y, ax - x), math.atan2(by - y, bx - x)
        angle = abs(before - after) % (2 * math.pi)
        result.append(min(angle, 2 * math.pi - angle))
    return result


def is_convex(points: list[Point]) -> bool:
    """Every corner turns left, which for an anticlockwise outline means convex."""
    for i in range(len(points)):
        (ax, ay), (bx, by), (cx, cy) = points[i - 1], points[i], points[(i + 1) % len(points)]
        if (bx - ax) * (cy - by) - (by - ay) * (cx - bx) <= 0:
            return False
    return True


def widest(points: list[Point]) -> float:
    return max(math.dist(p, q) for p in points for q in points)


def area(points: list[Point]) -> float:
    return 0.5 * sum(
        x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
    )


def centroid(points: list[Point]) -> Point:
    """The centre of mass of the flat shape, not the average of its corners."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (3 * a), cy / (3 * a)


def rotate(points: list[Point], angle: float) -> list[Point]:
    c, s = math.cos(angle), math.sin(angle)
    return [(c * x - s * y, s * x + c * y) for x, y in points]
