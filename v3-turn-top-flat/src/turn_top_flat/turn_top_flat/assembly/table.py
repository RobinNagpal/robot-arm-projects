"""The four legs as the arm found them, and the line the top is tilted down about.

The top's lower edge comes down on the two far legs, and the top is then
tilted towards the arm about that edge until it lies on all four. So what the
arm needs from the legs is: which two are the far ones, the line across
their middles and tops that the edge rests on, and whether the near two will
be under the top once it is down.

Plain numpy, no ROS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..geometry import Box
from ..perception.room import leg_thickness

LEGS_NEEDED = 4

# How far inside the top's edges a leg's outer faces have to be, once the top
# is down, to count as under it. Legs are measured to within a couple of
# millimetres.
FIT_MARGIN = 0.005


@dataclass(frozen=True)
class TableLegs:
    """The four legs, and where the top has to come down on them."""

    far: tuple[Box, Box]
    near: tuple[Box, Box]
    along: np.ndarray  # level unit vector along the far row
    toward: np.ndarray  # level unit vector from the far row towards the near one, which is towards the arm
    hinge: np.ndarray  # halfway along the table, over the far legs' middles, at the height of their tops
    rows: float  # from the far row to the near one, middle to middle
    thickness: float  # the legs' thickness

    @property
    def all(self) -> list[Box]:
        return [*self.far, *self.near]


def read_legs(legs: list[Box], base: np.ndarray) -> TableLegs:
    """Which legs are which, from four standing legs.

    The far two are the two further out along the line from the base to the
    middle of all four. The top rests on whichever far leg is taller: the
    other one it clears by however much shorter it is, which is a millimetre
    at most for legs cut the same.
    """
    if len(legs) != LEGS_NEEDED:
        raise ValueError(f"found {len(legs)} legs, and a table needs {LEGS_NEEDED}")
    middle = np.mean([leg.centre for leg in legs], axis=0)
    out = _level(middle - base)
    ordered = sorted(legs, key=lambda leg: float(leg.centre @ out))
    near, far = ordered[:2], ordered[2:]

    far_middle = np.mean([leg.centre for leg in far], axis=0)
    near_middle = np.mean([leg.centre for leg in near], axis=0)
    along = _level(far[1].centre - far[0].centre)
    toward = near_middle - far_middle
    toward = _level(toward - (toward @ along) * along)

    # Halfway along the table, which is halfway along all four legs.
    offset = float(np.mean([(leg.centre - far_middle) @ along for leg in legs]))
    hinge = far_middle + along * offset
    hinge[2] = max(leg.top_z for leg in far)
    return TableLegs(
        far=(far[0], far[1]),
        near=(near[0], near[1]),
        along=along,
        toward=toward,
        hinge=hinge,
        rows=float((near_middle - far_middle) @ toward),
        thickness=float(np.median([leg_thickness(leg) for leg in legs])),
    )


def misfit(legs: TableLegs, length: float, width: float) -> str | None:
    """Why a top ``length`` by ``width`` cannot go on these legs this way, or ``None`` if it can.

    Tilted down about the far legs, the top lies from their middles towards
    the arm, ``width`` deep, centred along them. Every leg has to end up under
    it, and the near legs well enough in from its near edge to hold it up.
    """
    reach = legs.rows + legs.thickness / 2.0
    if reach > width - FIT_MARGIN:
        return (
            f"the near legs stand {reach * 100:.1f} cm from the far ones' middles, "
            f"and the top is only {width * 100:.1f} cm wide"
        )
    for leg in legs.all:
        sideways = abs(float((leg.centre - legs.hinge) @ legs.along)) + legs.thickness / 2.0
        if sideways > length / 2.0 - FIT_MARGIN:
            return f"a leg stands {sideways * 100:.1f} cm out from the middle, past the end of the top"
    return None


def landing_angle(legs: TableLegs, drop: float) -> float:
    """How far to tilt the top down about the far legs so it stops ``drop`` above the near ones.

    A quarter turn would put it straight down on them. Stopping just short and
    letting go lets it fall the last few millimetres onto them, rather than
    the arm driving it into them if they stand a hair taller than measured.
    """
    # Tilted a small angle short of flat, the top's underside stands above the
    # near legs by the rows' spacing times the sine of that angle.
    rise = max(leg.top_z for leg in legs.near) + drop - legs.hinge[2]
    return math.pi / 2.0 - math.asin(max(0.0, min(1.0, rise / legs.rows)))


def _level(vector: np.ndarray) -> np.ndarray:
    flat = np.array([vector[0], vector[1], 0.0])
    return flat / np.linalg.norm(flat)
