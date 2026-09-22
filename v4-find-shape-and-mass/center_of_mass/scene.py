"""One random scene for the centre-of-mass dataset, and where its points land in the picture.

The scene is the same kind of description ``synthetic/randomization.py``
draws, so the same renderer draws it. What changes:

- the blocks are irregular outlines from ``polygons.py``, always lying flat;
- the camera never moves: it looks straight down from a fixed height;
- nothing overlaps, and every block is fully inside the picture;
- nothing is on the table but the blocks.

Colours, table and floor patterns and lights are drawn from the
classification dataset's ``SEEN`` ranges, so the pictures still vary in
everything that is not the shape.

No Gazebo in here, so the tests can draw scenes and check the projection.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from synthetic.randomization import (
    SEEN,
    Block,
    Camera,
    Scene,
    _colour,
    _free_spot,
    _light,
    _surface,
)

from .polygons import CLASSES, irregular_outline


@dataclass(frozen=True)
class Ranges:
    blocks: tuple[int, int] = (2, 4)
    size: tuple[float, float] = (0.07, 0.14)  # widest distance across the outline, metres
    # Height in metres, drawn on its own and not tied to the outline's size,
    # so a small block can be tall and a big one flat. From straight above a
    # taller block shows more of its sides away from the middle of the
    # picture, and its top face is nearer the camera and looks bigger. Both
    # are things the model has to see past.
    thickness: tuple[float, float] = (0.01, 0.06)


RANGES = Ranges()

# Straight down from this height over the middle of the table. A pitch of a
# quarter turn points Gazebo's camera, which looks along its own x axis, at
# the floor; the top of the picture is then towards +x on the table.
CAMERA = Camera(position=(0.0, 0.0, 0.7), roll=0.0, pitch=math.pi / 2, yaw=0.0)
# Must match both cameras in synthetic/world.sdf.
IMAGE_WIDTH, IMAGE_HEIGHT = 640, 480
HORIZONTAL_FOV = 1.047


def draw_scene(rng: random.Random, number: int) -> Scene:
    """Scene ``number``, entirely decided by ``rng``.

    The number picks the classes: picture n starts with class n, then n + 1,
    and so on round the list. Every class then leads the same number of
    pictures and turns up about equally often overall.
    """
    area = _area_in_view()
    taken: list[tuple[float, float, float]] = []
    blocks = []
    for k in range(rng.randint(*RANGES.blocks)):
        block = _block(rng, CLASSES[(number + k) % len(CLASSES)], area, taken)
        if block is not None:
            blocks.append(block)
    return Scene(
        blocks=tuple(blocks),
        distractors=(),
        table=_surface(rng, SEEN.table_patterns),
        floor=_surface(rng, SEEN.floor_patterns),
        camera=CAMERA,
        sun=_light(rng, SEEN.sun_elevation, SEEN.sun_strength, SEEN.tint, rng.random() < SEEN.shadows_chance),
        fill=_light(rng, (20.0, 70.0), SEEN.fill_strength, SEEN.tint, False),
    )


def centre_of_mass(block: Block) -> tuple[float, float, float]:
    """Where the block's centre of mass is on the table, in metres.

    The outline is centred on its centroid, so turning it about its own
    origin and moving it to its position leaves the centroid at that
    position. Halfway up its thickness, for a block of even material.
    """
    x, y = block.position
    return (x, y, block.thickness / 2)


def top_of_centre_of_mass(block: Block) -> tuple[float, float, float]:
    """The point on the block's top face straight above its centre of mass.

    This is the point the dataset marks. The true centre of mass is inside
    the block, and from straight above both project to nearly the same pixel;
    this one is on a surface the camera actually sees.
    """
    x, y, _ = centre_of_mass(block)
    return (x, y, block.thickness)


def project(point: tuple[float, float, float], camera: Camera = CAMERA) -> tuple[float, float]:
    """The pixel (x to the right, y down, 0 to width and height) where ``point`` shows in the picture."""
    rotation = _rotation(camera.roll, camera.pitch, camera.yaw)
    offset = [p - c for p, c in zip(point, camera.position, strict=True)]
    # Into the camera's own frame: x forward, y left, z up.
    forward, left, up = (sum(rotation[r][c] * offset[r] for r in range(3)) for c in range(3))
    if forward <= 0:
        raise ValueError(f"{point} is behind the camera")
    focal = (IMAGE_WIDTH / 2) / math.tan(HORIZONTAL_FOV / 2)
    return (IMAGE_WIDTH / 2 - focal * left / forward, IMAGE_HEIGHT / 2 - focal * up / forward)


def unproject(pixel: tuple[float, float], height: float, camera: Camera = CAMERA) -> tuple[float, float]:
    """The point on the table, at ``height`` above it, that shows at ``pixel``. The reverse of ``project``."""
    rotation = _rotation(camera.roll, camera.pitch, camera.yaw)
    focal = (IMAGE_WIDTH / 2) / math.tan(HORIZONTAL_FOV / 2)
    # The ray through the pixel, in the camera's frame, then in the table's.
    left, up = (IMAGE_WIDTH / 2 - pixel[0]) / focal, (IMAGE_HEIGHT / 2 - pixel[1]) / focal
    ray = [rotation[r][0] + rotation[r][1] * left + rotation[r][2] * up for r in range(3)]
    if ray[2] >= 0:
        raise ValueError(f"the ray through {pixel} never comes down to the table")
    along = (height - camera.position[2]) / ray[2]
    return (camera.position[0] + along * ray[0], camera.position[1] + along * ray[1])


def _area_in_view() -> tuple[float, float, float, float]:
    """x_min, x_max, y_min, y_max: where a block's centre can go with the whole block in view.

    Worked out at the height of the thickest possible block's top, which is
    the nearest the camera any part of a block gets, so the view is narrowest.
    """
    top = RANGES.thickness[1]
    height = CAMERA.position[2] - top
    focal = (IMAGE_WIDTH / 2) / math.tan(HORIZONTAL_FOV / 2)
    # Image width runs along table y, image height along table x; see CAMERA.
    half_y = height * (IMAGE_WIDTH / 2) / focal
    half_x = height * (IMAGE_HEIGHT / 2) / focal
    # No point of a convex shape is farther from its centroid than two thirds
    # of its widest distance across, and lopsided triangles come close.
    reach = RANGES.size[1] * 2 / 3 + 0.01
    x, y = CAMERA.position[:2]
    return (x - half_x + reach, x + half_x - reach, y - half_y + reach, y + half_y - reach)


def _block(rng: random.Random, name: str, area, taken) -> Block | None:
    points = irregular_outline(name, rng.uniform(*RANGES.size), rng)
    spot = _free_spot(rng, area, taken, max(math.hypot(x, y) for x, y in points))
    if spot is None:
        return None
    return Block(
        shape=name,
        outline=tuple(points),
        thickness=rng.uniform(*RANGES.thickness),
        on_edge=False,
        position=spot,
        yaw=rng.uniform(-math.pi, math.pi),
        colour=_colour(rng, SEEN),
        shininess=rng.uniform(*SEEN.shininess),
    )


def _rotation(roll: float, pitch: float, yaw: float) -> list[list[float]]:
    """Roll about x, then pitch about y, then yaw about z, all about fixed axes, as Gazebo reads a pose.

    Its columns are the camera's own x, y and z axes in table coordinates.
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]
