"""Where to stand the camera to photograph one glass from the side.

Geometry lists the places and throws out the ones that cannot work: out of the
arm's comfortable reach, or with another glass square in the line of sight.
What is left goes to the learned ranker, which only puts them in order. So a
bad ranking costs a wasted look, never an unsafe move.

The features are numbers about the arrangement, not pixels, because the
picture from a candidate place does not exist until the arm goes there.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.table.layout import ROBOT_BASE

from render import HORIZONTAL_FOV, STANDOFF, Glass

# Directions tried round each glass.
DIRECTIONS = 24

# How far past the glass being measured another glass still matters. Beyond
# this the depth band drops it from the mask anyway.
BEHIND = 0.35

# A camera nearer than this to another glass's edge would be standing in it.
CAMERA_CLEARANCE = 0.05

FEATURES = (
    "reach",
    "facing_base",
    "gap_in_front",
    "gap_behind",
    "others_in_frame",
    "radius",
    "nearest_neighbour",
)


@dataclass(frozen=True)
class Seen:
    """A glass as the arm knows it after the overhead picture."""

    x: float
    y: float
    radius: float


def seen(glass: Glass) -> Seen:
    return Seen(glass.x, glass.y, glass.max_radius)


def angles() -> np.ndarray:
    return np.arange(DIRECTIONS) * (2 * math.pi / DIRECTIONS)


def _eye(target: Seen, angle: float) -> np.ndarray:
    return np.array([target.x, target.y]) + STANDOFF * np.array([math.cos(angle), math.sin(angle)])


def allowed(target: Seen, others: list[Seen], angle: float) -> bool:
    """The veto: reachable, and no glass squarely between camera and target."""
    eye = _eye(target, angle)
    if not COMFORTABLE_REACH[0] <= np.linalg.norm(eye - ROBOT_BASE[:2]) <= COMFORTABLE_REACH[1]:
        return False
    toward = -np.array([math.cos(angle), math.sin(angle)])
    for other in others:
        offset = np.array([other.x, other.y]) - eye
        if np.linalg.norm(offset) < other.radius + CAMERA_CLEARANCE:
            return False
        along = offset @ toward
        across = abs(offset[0] * toward[1] - offset[1] * toward[0])
        if 0.0 < along < STANDOFF and across < other.radius:
            return False
    return True


def features(target: Seen, others: list[Seen], angle: float) -> np.ndarray:
    """What the ranker is shown about one candidate place. See FEATURES."""
    eye = _eye(target, angle)
    toward = -np.array([math.cos(angle), math.sin(angle)])
    out_from_base = np.array([target.x, target.y]) - ROBOT_BASE[:2]

    gap_front, gap_behind, in_frame = 0.3, 0.3, 0
    for other in others:
        offset = np.array([other.x, other.y]) - eye
        along = offset @ toward
        across = abs(offset[0] * toward[1] - offset[1] * toward[0])
        # How much room there is between the two in the picture, roughly.
        gap = across - other.radius - target.radius
        if 0.0 < along < STANDOFF:
            gap_front = min(gap_front, gap)
        elif STANDOFF <= along < STANDOFF + BEHIND:
            gap_behind = min(gap_behind, gap)
        if along > 0 and math.atan2(across, along) < HORIZONTAL_FOV / 2:
            in_frame += 1

    nearest = min((math.dist((target.x, target.y), (o.x, o.y)) for o in others), default=0.5)
    return np.array(
        [
            np.linalg.norm(eye - ROBOT_BASE[:2]),
            toward @ out_from_base / np.linalg.norm(out_from_base),
            np.clip(gap_front, -0.1, 0.3),
            np.clip(gap_behind, -0.1, 0.3),
            in_frame,
            target.radius,
            nearest,
        ],
        dtype=np.float32,
    )
