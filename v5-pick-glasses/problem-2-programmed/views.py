"""Step 2: where to stand the camera to photograph one glass from the side.

Three stages, all geometry:

1. **List** 24 places round the glass, STANDOFF back, looking level.
2. **Veto** the ones out of the arm's comfortable reach, or with another glass
   squarely in the line of sight. The same veto as problem-2-learned, so the
   two choose from the same places.
3. **Order** the rest by a written rule: the widest gap, *in the picture*,
   between the target and any glass that would share the mask or cover it.

The veto alone lets through places where another glass clips the edge of the
target. That is what spoils about one side picture in eight, and it is what
the rule measures.
"""

from __future__ import annotations

import math

import numpy as np
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.table.layout import ROBOT_BASE

from find import Seen
from render import STANDOFF

DIRECTIONS = 24

# A camera nearer than this to another glass's edge would be standing in it.
CAMERA_CLEARANCE = 0.05

# How far the side measurement's depth band reaches past the target's axis.
# A glass behind the target and inside it joins the target's mask; one further
# back is dropped. Matches the band scoring.silhouette() uses.
DEPTH_BAND = 0.12

# Where in its reach the arm is most at ease, for breaking ties.
MIDDLE_REACH = sum(COMFORTABLE_REACH) / 2


def angles() -> np.ndarray:
    return np.arange(DIRECTIONS) * (2 * math.pi / DIRECTIONS)


def _geometry(target: Seen, angle: float):
    eye = np.array([target.x, target.y]) + STANDOFF * np.array([math.cos(angle), math.sin(angle)])
    return eye, -np.array([math.cos(angle), math.sin(angle)])


def allowed(target: Seen, others: list[Seen], angle: float) -> bool:
    """The veto: reachable, and no glass squarely between camera and target."""
    eye, toward = _geometry(target, angle)
    if not COMFORTABLE_REACH[0] <= np.linalg.norm(eye - ROBOT_BASE[:2]) <= COMFORTABLE_REACH[1]:
        return False
    for other in others:
        offset = np.array([other.x, other.y]) - eye
        if np.linalg.norm(offset) < other.radius + CAMERA_CLEARANCE:
            return False
        along = offset @ toward
        across = abs(offset[0] * toward[1] - offset[1] * toward[0])
        if 0.0 < along < STANDOFF and across < other.radius:
            return False
    return True


def gap(target: Seen, others: list[Seen], angle: float) -> float:
    """The narrowest gap in the picture between the target and a glass that matters.

    Measured as an angle at the camera: the angle between the two middles,
    less the half-width each one covers. Below zero, they overlap.

    A glass in front matters wherever it is: it covers part of the target.
    A glass behind matters only inside the depth band: further back, the
    measurement drops it.
    """
    eye, toward = _geometry(target, angle)
    target_half = math.asin(min(1.0, target.radius / STANDOFF))
    narrowest = math.pi
    for other in others:
        offset = np.array([other.x, other.y]) - eye
        along = offset @ toward
        if along <= 0:
            continue
        if along >= STANDOFF and along - other.radius > STANDOFF + DEPTH_BAND:
            continue
        across = abs(offset[0] * toward[1] - offset[1] * toward[0])
        between = math.atan2(across, along)
        other_half = math.asin(min(1.0, other.radius / math.hypot(along, across)))
        narrowest = min(narrowest, between - other_half - target_half)
    return narrowest


def ranked(target: Seen, others: list[Seen]) -> list[tuple[float, float]]:
    """(gap, angle) for every allowed place, widest gap first.

    Places with nothing near at all tie on the gap. Among those, the one
    nearest the middle of the arm's reach goes first.
    """
    options = []
    for angle in angles():
        if not allowed(target, others, angle):
            continue
        eye, _ = _geometry(target, angle)
        options.append(
            (gap(target, others, angle), -abs(np.linalg.norm(eye - ROBOT_BASE[:2]) - MIDDLE_REACH), angle)
        )
    options.sort(reverse=True)
    return [(g, a) for g, _, a in options]
