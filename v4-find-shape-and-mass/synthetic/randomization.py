"""Drawing one random scene: which blocks, where, how they look, and how they are seen.

This is domain randomization. Everything that is not the shape itself is
drawn at random for every picture: size, thickness, colour, which way the
block faces, whether it lies flat or stands on an edge, the table, the floor,
the lights and where the camera is. A model trained on these pictures cannot
lean on any of those to tell the classes apart, because none of them stays
the same long enough to learn. The only thing that is always true about a
hexagon is that it is a hexagon.

All the ranges are in ``Ranges``. There are two sets of them: ``SEEN`` for the
training, validation and test pictures, and ``UNSEEN`` for a second test set
drawn from conditions the model never trains on. How well the model does on
``UNSEEN`` compared with ``test`` is the measure of how much it generalises
rather than memorises. [`docs/yolo-classification/dataset.md`](../docs/yolo-classification/dataset.md)
explains every range and the reason for it.

A scene is only a description. Nothing here talks to Gazebo, so the tests can
draw thousands of scenes and check them quickly.
"""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass

from .shapes import CLASSES, narrowest, outline, stable_edges, standing_on_edge

Colour = tuple[float, float, float]


@dataclass(frozen=True)
class Ranges:
    # The blocks.
    blocks: tuple[int, int] = (1, 5)
    size: tuple[float, float] = (0.04, 0.12)  # widest distance across the outline, metres
    # Thickness as a fraction of the shape's narrowest width. Kept under 0.6
    # so the outline faces are always the biggest faces of the block: a square
    # block thicker than it is wide is a rectangle block from the side, and
    # then no one could say which class it is.
    thickness: tuple[float, float] = (0.15, 0.6)
    on_edge_chance: float = 0.2
    # Saturation and brightness of block colours. Low saturation gives grey
    # blocks, so colour against a grey table is not something to rely on.
    saturation: tuple[float, float] = (0.0, 1.0)
    brightness: tuple[float, float] = (0.25, 1.0)
    # Hues are drawn from these bands, as fractions of the colour wheel.
    hue_bands: tuple[tuple[float, float], ...] = ((0.0, 0.42), (0.58, 1.0))
    shininess: tuple[float, float] = (0.0, 0.6)

    # Things on the table that are not a class: balls, capsules, eggs.
    distractors: tuple[int, int] = (0, 2)

    # The surfaces.
    table_patterns: tuple[str, ...] = ("plain", "wood", "checker", "speckle", "stripes")
    floor_patterns: tuple[str, ...] = ("plain", "speckle", "checker")

    # The camera, relative to the point it looks at.
    distance: tuple[float, float] = (0.3, 0.9)  # metres
    elevation: tuple[float, float] = (35.0, 90.0)  # degrees above the table; 90 is straight down
    roll: tuple[float, float] = (-15.0, 15.0)  # degrees of tilt about the line of sight
    aim_jitter: float = 0.06  # metres the aim point wanders off the middle of the blocks

    # The lights.
    sun_elevation: tuple[float, float] = (25.0, 90.0)  # degrees
    sun_strength: tuple[float, float] = (0.5, 1.2)
    fill_strength: tuple[float, float] = (0.0, 0.5)
    shadows_chance: float = 0.8
    # How far the light's colour leans warm (positive) or cool (negative).
    tint: tuple[float, float] = (-0.15, 0.15)


SEEN = Ranges()

# Conditions the model never trains on. Each one pushes a different weakness:
# a hue it has never seen, a table pattern it has never seen, a lower camera
# that squashes shapes more, a farther camera that shrinks them to a few
# pixels, and dim, low light with long shadows.
UNSEEN = Ranges(
    hue_bands=((0.42, 0.58),),
    table_patterns=("tiles", "marble"),
    floor_patterns=("tiles",),
    distance=(0.9, 1.3),
    elevation=(22.0, 35.0),
    sun_elevation=(12.0, 25.0),
    sun_strength=(0.3, 0.6),
)

# The table the blocks are put on. Its top surface is at height 0.
TABLE_SIZE = (0.9, 0.7)
TABLE_THICKNESS = 0.03
FLOOR_HEIGHT = -0.75
# Blocks are gathered into a patch of this size, somewhere on the table, so a
# camera aimed at them has a chance of seeing them all.
PATCH_SIZE = (0.36, 0.30)
# Patterned surfaces are painted from a fixed bank of textures rather than a
# new one for every picture. A new texture each time would mean tens of
# thousands of image files, and Gazebo keeps every texture it has loaded in
# memory for as long as it runs. Each texture is seen under many different
# lights, so it never looks the same twice anyway.
TEXTURES_PER_PATTERN = 50
# The gap left between any two things on the table, so no two start out touching.
GAP = 0.01


@dataclass(frozen=True)
class Block:
    shape: str
    outline: tuple[tuple[float, float], ...]  # the corners as the block is built, see shapes.py
    thickness: float
    on_edge: bool
    position: tuple[float, float]  # on the table
    yaw: float
    colour: Colour
    shininess: float


@dataclass(frozen=True)
class Distractor:
    kind: str  # sphere, capsule or ellipsoid
    dimensions: tuple[float, float, float]
    position: tuple[float, float]
    yaw: float
    colour: Colour


@dataclass(frozen=True)
class Surface:
    pattern: str
    # Which of that pattern's textures. The texture's own colours come from
    # this number too, so the same number always gives the same picture.
    texture: int
    # Only "plain" surfaces use this; a patterned one has its colours in the texture.
    colour: Colour


@dataclass(frozen=True)
class Camera:
    position: tuple[float, float, float]
    roll: float
    pitch: float
    yaw: float


@dataclass(frozen=True)
class Light:
    direction: tuple[float, float, float]
    colour: Colour
    shadows: bool


@dataclass(frozen=True)
class Scene:
    blocks: tuple[Block, ...]
    distractors: tuple[Distractor, ...]
    table: Surface
    floor: Surface
    camera: Camera
    sun: Light
    fill: Light


def draw_scene(rng: random.Random, ranges: Ranges) -> Scene:
    """One random scene, entirely decided by ``rng``."""
    patch = _patch(rng)
    taken: list[tuple[float, float, float]] = []  # (x, y, radius) of everything placed

    blocks = []
    for _ in range(rng.randint(*ranges.blocks)):
        block = _block(rng, ranges, patch, taken)
        if block is not None:
            blocks.append(block)

    distractors = []
    for _ in range(rng.randint(*ranges.distractors)):
        distractor = _distractor(rng, ranges, patch, taken)
        if distractor is not None:
            distractors.append(distractor)

    return Scene(
        blocks=tuple(blocks),
        distractors=tuple(distractors),
        table=_surface(rng, ranges.table_patterns),
        floor=_surface(rng, ranges.floor_patterns),
        camera=_camera(rng, ranges, [(b.position[0], b.position[1]) for b in blocks]),
        sun=_light(
            rng, ranges.sun_elevation, ranges.sun_strength, ranges.tint, rng.random() < ranges.shadows_chance
        ),
        # The fill light never casts shadows: two sets of shadows from two
        # directional lights look like nothing in a real room.
        fill=_light(rng, (20.0, 70.0), ranges.fill_strength, ranges.tint, False),
    )


def _patch(rng: random.Random) -> tuple[float, float, float, float]:
    """x_min, x_max, y_min, y_max of the part of the table the blocks go on."""
    # A block centred on the edge of the patch reaches up to half its size
    # beyond it, so the patch keeps that far in from the edge of the table.
    margin = SEEN.size[1] / 2
    half_x = (TABLE_SIZE[0] - PATCH_SIZE[0]) / 2 - margin
    half_y = (TABLE_SIZE[1] - PATCH_SIZE[1]) / 2 - margin
    cx, cy = rng.uniform(-half_x, half_x), rng.uniform(-half_y, half_y)
    return (cx - PATCH_SIZE[0] / 2, cx + PATCH_SIZE[0] / 2, cy - PATCH_SIZE[1] / 2, cy + PATCH_SIZE[1] / 2)


def _free_spot(rng, patch, taken, radius) -> tuple[float, float] | None:
    x_min, x_max, y_min, y_max = patch
    for _ in range(100):
        x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
        if all(math.dist((x, y), (tx, ty)) >= radius + tr + GAP for tx, ty, tr in taken):
            taken.append((x, y, radius))
            return x, y
    # The patch is full. Fewer blocks in this picture is better than blocks
    # that overlap, which the simulator would draw inside each other.
    return None


def _block(rng: random.Random, ranges: Ranges, patch, taken) -> Block | None:
    shape = rng.choice(CLASSES)
    points = outline(shape, rng.uniform(*ranges.size), rng)
    thickness = narrowest(points) * rng.uniform(*ranges.thickness)

    on_edge = rng.random() < ranges.on_edge_chance
    if on_edge:
        points = standing_on_edge(points, rng.choice(stable_edges(points)))
        # Standing up, the block covers its outline's width one way and its
        # thickness the other.
        half_width = max(abs(x) for x, _ in points)
        radius = math.hypot(half_width, thickness / 2)
    else:
        radius = max(math.hypot(x, y) for x, y in points)

    spot = _free_spot(rng, patch, taken, radius)
    if spot is None:
        return None
    return Block(
        shape=shape,
        outline=tuple(points),
        thickness=thickness,
        on_edge=on_edge,
        position=spot,
        yaw=rng.uniform(-math.pi, math.pi),
        colour=_colour(rng, ranges),
        shininess=rng.uniform(*ranges.shininess),
    )


def _distractor(rng: random.Random, ranges: Ranges, patch, taken) -> Distractor | None:
    kind = rng.choice(("sphere", "capsule", "ellipsoid"))
    a = rng.uniform(0.015, 0.035)
    if kind == "sphere":
        dimensions = (a, a, a)
    elif kind == "capsule":
        dimensions = (a, a, rng.uniform(0.03, 0.08))  # radius, radius, length of the straight part
    else:
        dimensions = (a * rng.uniform(1.2, 2.0), a, a)  # half-axes
    spot = _free_spot(rng, patch, taken, max(dimensions) + (a if kind == "capsule" else 0.0))
    if spot is None:
        return None
    return Distractor(kind, dimensions, spot, rng.uniform(-math.pi, math.pi), _colour(rng, ranges))


def _colour(rng: random.Random, ranges: Ranges) -> Colour:
    low, high = rng.choice(ranges.hue_bands)
    return colorsys.hsv_to_rgb(
        rng.uniform(low, high), rng.uniform(*ranges.saturation), rng.uniform(*ranges.brightness)
    )


def _surface(rng: random.Random, patterns: tuple[str, ...]) -> Surface:
    return Surface(
        pattern=rng.choice(patterns),
        texture=rng.randrange(TEXTURES_PER_PATTERN),
        colour=colorsys.hsv_to_rgb(rng.random(), rng.uniform(0.0, 0.6), rng.uniform(0.2, 0.9)),
    )


def _camera(rng: random.Random, ranges: Ranges, spots: list[tuple[float, float]]) -> Camera:
    """A camera somewhere above the table, looking at the middle of the blocks."""
    if spots:
        aim_x = sum(x for x, _ in spots) / len(spots)
        aim_y = sum(y for _, y in spots) / len(spots)
    else:
        aim_x = aim_y = 0.0
    aim_x += rng.uniform(-ranges.aim_jitter, ranges.aim_jitter)
    aim_y += rng.uniform(-ranges.aim_jitter, ranges.aim_jitter)

    distance = rng.uniform(*ranges.distance)
    elevation = math.radians(rng.uniform(*ranges.elevation))
    heading = rng.uniform(-math.pi, math.pi)  # which side of the table the camera is on
    position = (
        aim_x + distance * math.cos(elevation) * math.cos(heading),
        aim_y + distance * math.cos(elevation) * math.sin(heading),
        distance * math.sin(elevation),
    )
    # Gazebo's camera looks along its own x axis. Turned by yaw to face back
    # at the aim point, then pitched down by the elevation, it looks at it.
    return Camera(
        position=position,
        roll=math.radians(rng.uniform(*ranges.roll)),
        pitch=elevation,
        yaw=heading + math.pi,
    )


def _light(rng: random.Random, elevation_range, strength_range, tint_range, shadows: bool) -> Light:
    elevation = math.radians(rng.uniform(*elevation_range))
    heading = rng.uniform(-math.pi, math.pi)
    # Pointing down from the sky, towards the table.
    direction = (
        -math.cos(elevation) * math.cos(heading),
        -math.cos(elevation) * math.sin(heading),
        -math.sin(elevation),
    )
    strength = rng.uniform(*strength_range)
    tint = rng.uniform(*tint_range)
    colour = (strength * (1 + tint), strength, strength * (1 - tint))
    return Light(direction, colour, shadows)
