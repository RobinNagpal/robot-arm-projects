"""Drawing this run's room: the table top standing upright between its two holders, and four legs.

This is the simulator's side. It knows exactly where everything is, because it
is the one putting it there, and the robot never gets to ask it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..transforms import WORLD_Z, rotation_z, rpy_from_matrix
from . import spec

PART_TEMPLATE = Path(__file__).parent / "part.sdf"
HOLDER_TEMPLATE = Path(__file__).parent / "holder.sdf"


@dataclass(frozen=True)
class SpawnedBox:
    """One box, as the simulator will be told to create it."""

    name: str
    size: tuple[float, float, float]
    centre: np.ndarray
    rotation: np.ndarray
    colour: tuple[float, float, float]
    density: float  # zero for something bolted down


@dataclass(frozen=True)
class Room:
    holders: tuple[SpawnedBox, ...]  # three blocks per holder: two jaws and an end wall
    top: SpawnedBox
    legs: tuple[SpawnedBox, ...]  # far two first

    def boxes(self) -> list[SpawnedBox]:
        return [*self.holders, self.top, *self.legs]


def random_room(
    seed: int,
    top_density: float = spec.TOP_DENSITY,
    leg_density: float = spec.LEG_DENSITY,
    scale: float = 1.0,
) -> Room:
    """This seed's room. ``scale`` sizes the top and the legs, and only them.

    The random draws are the same at any size, so a seed gives the same room,
    only with bigger or smaller parts. The legs still stand where the scaled
    top will rest on them.
    """
    rng = random.Random(seed)
    colour = rng.choice(spec.PALETTE)

    azimuth = math.radians(rng.uniform(*spec.TOP_AZIMUTH_DEG))
    distance = rng.uniform(*spec.TOP_DISTANCE)
    length, width, thickness = (
        rng.uniform(*spec.TOP_LENGTH) * scale,
        rng.uniform(*spec.TOP_WIDTH) * scale,
        rng.uniform(*spec.TOP_THICKNESS) * scale,
    )
    holder_height = rng.uniform(*spec.HOLDER_HEIGHT)

    # Standing on a long edge: its length runs across the line from the arm,
    # turned a little, its width points up, and its faces look towards the arm
    # and away from it.
    along = rotation_z(azimuth + math.pi / 2.0 + math.radians(rng.uniform(*spec.TOP_TURN_DEG)))[:, 0]
    normal = np.cross(along, WORLD_Z)
    rotation = np.column_stack((along, WORLD_Z, normal))
    centre = np.array([distance * math.cos(azimuth), distance * math.sin(azimuth), 0.0])

    top = SpawnedBox(
        name="table_top",
        size=(length, width, thickness),
        # A millimetre of air, so the board settles onto the floor rather than
        # starting inside it.
        centre=centre + WORLD_Z * (width / 2.0 + 0.001),
        rotation=rotation,
        colour=colour,
        density=top_density,
    )

    holders = []
    jaw_length = spec.HOLDER_DEPTH + spec.HOLDER_PLAY + spec.HOLDER_JAW
    across = thickness + 2.0 * (spec.HOLDER_PLAY + spec.HOLDER_JAW)
    for index, end in enumerate((-1.0, 1.0)):
        # Measured along the top from its centre: the jaws start HOLDER_DEPTH
        # in from its end, and the end wall stands just past it.
        jaw_middle = length / 2.0 - spec.HOLDER_DEPTH + jaw_length / 2.0
        wall_middle = length / 2.0 + spec.HOLDER_PLAY + spec.HOLDER_JAW / 2.0
        lift = WORLD_Z * holder_height / 2.0
        blocks = [
            (f"holder_{index}_front", (jaw_length, holder_height, spec.HOLDER_JAW), jaw_middle, -1.0),
            (f"holder_{index}_back", (jaw_length, holder_height, spec.HOLDER_JAW), jaw_middle, 1.0),
            (f"holder_{index}_end", (spec.HOLDER_JAW, holder_height, across), wall_middle, 0.0),
        ]
        for name, size, middle, side in blocks:
            offset = side * (thickness / 2.0 + spec.HOLDER_PLAY + spec.HOLDER_JAW / 2.0)
            holders.append(
                SpawnedBox(
                    name=name,
                    size=size,
                    centre=centre + along * end * middle + normal * offset + lift,
                    rotation=rotation,
                    colour=spec.HOLDER_COLOUR,
                    density=0.0,
                )
            )
    # Drawn last, so a seed gives the same top it did before there were legs.
    leg_colour = rng.choice([c for c in spec.PALETTE if c != colour])
    legs = _standing_legs(rng, leg_colour, length, width, leg_density, scale)
    return Room(holders=tuple(holders), top=top, legs=legs)


def _standing_legs(
    rng: random.Random, colour, top_length: float, top_width: float, density: float, scale: float
) -> tuple[SpawnedBox, ...]:
    """Four legs standing where a table with this top goes, far two first.

    The far legs stand where the top's far edge will lie across their middles
    once it has been tilted down onto them; the near legs stand just in from
    its near edge. Along the table, all four stand just in from its ends.
    """
    azimuth = math.radians(rng.uniform(*spec.TABLE_AZIMUTH_DEG))
    far = rng.uniform(*spec.TABLE_FAR_DISTANCE)
    length = rng.uniform(*spec.LEG_LENGTH) * scale
    thickness = rng.uniform(*spec.LEG_THICKNESS) * scale
    turn = rotation_z(azimuth + math.radians(rng.uniform(*spec.TABLE_TURN_DEG)))
    outward, along = turn[:, 0], turn[:, 1]

    far_middle = np.array([far * math.cos(azimuth), far * math.sin(azimuth), 0.0])
    rows = top_width - spec.LEG_INSET - thickness / 2.0
    half_along = top_length / 2.0 - spec.LEG_INSET - thickness / 2.0
    spots = [far_middle + along * side * half_along for side in (-1.0, 1.0)]
    spots += [far_middle - outward * rows + along * side * half_along for side in (-1.0, 1.0)]
    return tuple(
        SpawnedBox(
            name=f"leg_{index}",
            size=(thickness, thickness, length),
            # A millimetre of air, so the leg settles onto the floor.
            centre=spot + WORLD_Z * (length / 2.0 + 0.001),
            rotation=turn,
            colour=colour,
            density=density,
        )
        for index, spot in enumerate(spots)
    )


def box_sdf(box: SpawnedBox) -> str:
    """One box as the simulator's own model format."""
    length, width, height = box.size
    roll, pitch, yaw = rpy_from_matrix(box.rotation)
    red, green, blue = box.colour
    x, y, z = box.centre
    fields = dict(
        name=box.name,
        x=x,
        y=y,
        z=z,
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        length=length,
        width=width,
        height=height,
        red=red,
        green=green,
        blue=blue,
    )
    if box.density == 0.0:
        template = HOLDER_TEMPLATE
    else:
        template = PART_TEMPLATE
        mass = box.density * length * width * height
        # A solid box, about its own centre.
        fields.update(
            mass=mass,
            ixx=mass * (width**2 + height**2) / 12.0,
            iyy=mass * (length**2 + height**2) / 12.0,
            izz=mass * (length**2 + width**2) / 12.0,
        )
    return template.read_text().split("-->\n", 1)[1].format(**fields)
