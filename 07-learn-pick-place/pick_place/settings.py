"""Every number that describes the room, the blocks and the recording, in one place.

The arm's base is at the origin, bolted to the table, and the table top is
the plane z = 0. x points away from the arm, y to its left.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MENAGERIE = ROOT / "assets" / "menagerie"
ARM_XML = MENAGERIE / "universal_robots_ur5e" / "ur5e.xml"
GRIPPER_XML = MENAGERIE / "robotiq_2f85" / "2f85.xml"

# The arm starts every episode here: the pinch point 28 cm in front of the
# base and 35 cm up, gripper open and pointing straight down, between the two
# zones and clear of the camera's view of them. Found with kinematics.Solver.
HOME = (-3.6406, -2.1591, 1.9294, -1.3411, -1.5708, -2.0698)


@dataclass(frozen=True)
class Zone:
    x: tuple[float, float]
    y: tuple[float, float]


# The block starts somewhere in the pick zone and has to end in the place
# zone. They are side by side, so every episode has the arm carry the block
# across, never just lift it and put it back down.
PICK_ZONE = Zone(x=(0.40, 0.58), y=(0.10, 0.30))
PLACE_ZONE = Zone(x=(0.40, 0.58), y=(-0.30, -0.10))


@dataclass(frozen=True)
class BlockRanges:
    sides: tuple[int, ...] = (3, 4, 5, 6)
    # Widest distance across the outline, metres.
    size: tuple[float, float] = (0.07, 0.12)
    # The Robotiq 2F-85 opens to 85 mm. The block's width along the line the
    # fingers close on must leave room either side of the open fingers.
    max_grip_width: float = 0.065
    min_grip_width: float = 0.03
    # Thickness in metres. The finger pads are 37 mm tall, and a block
    # thinner than about 2 cm leaves the fingertips on the table when they
    # close on it.
    thickness: tuple[float, float] = (0.025, 0.04)
    density: tuple[float, float] = (400.0, 900.0)  # kg/m^3: light wood to hard plastic


BLOCK = BlockRanges()


@dataclass(frozen=True)
class OverheadCamera:
    """A depth camera fixed above the table, looking straight down."""

    pos: tuple[float, float, float] = (0.49, 0.0, 1.0)
    fovy: float = 45.0  # degrees
    width: int = 640
    height: int = 480


CAMERA = OverheadCamera()

# Control and recording rate. Physics runs at MuJoCo's 2 ms step underneath.
FPS = 20
TIMESTEP = 0.002

# A placed block counts as on target when its centre of mass is this close
# to the target's middle.
SUCCESS_RADIUS = 0.015
