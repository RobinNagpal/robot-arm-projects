"""Turning the rack's measurements into a model the simulator can load.

The rack is fixed, so this reads its numbers from rack/layout.py rather than
holding any of its own. Only where it stands is passed in, and that is drawn
per run, because the arm is supposed to find the rack rather than be told.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2

from .layout import (
    MARKER_DICTIONARY,
    MARKER_ID,
    MARKER_SIZE,
    RACK_BASE_HEIGHT,
    SLOT_COUNT,
    SLOT_SPACING,
    TABLE_TOP_Z,
)

TEMPLATE = Path(__file__).parent / "rack.sdf"

# The pegs a glass is stood over. Short, because they only have to keep a glass
# from sliding sideways, not hold it up.
PEG_HEIGHT = 0.035
PEG_RADIUS = 0.005


def peg_sdf(index: int) -> str:
    """One peg, positioned along the rack from its middle."""
    first = -(SLOT_COUNT - 1) / 2.0
    y = (first + index) * SLOT_SPACING
    z = RACK_BASE_HEIGHT / 2.0 + PEG_HEIGHT / 2.0
    geometry = (
        f"<cylinder><radius>{PEG_RADIUS:.4f}</radius>"
        f"<length>{PEG_HEIGHT:.4f}</length></cylinder>"
    )
    return (
        f'        <collision name="peg_{index}_collision">\n'
        f"          <pose>0 {y:.4f} {z:.4f} 0 0 0</pose>\n"
        f"          <geometry>{geometry}</geometry>\n"
        f"        </collision>\n"
        f'        <visual name="peg_{index}_visual">\n'
        f"          <pose>0 {y:.4f} {z:.4f} 0 0 0</pose>\n"
        f"          <geometry>{geometry}</geometry>\n"
        f"          <material><ambient>0.7 0.7 0.75 1</ambient>"
        f"<diffuse>0.7 0.7 0.75 1</diffuse></material>\n"
        f"        </visual>"
    )


# Pixels per marker cell in the generated image. Nothing to do with what the
# camera sees; it only has to be large enough that the texture is not the thing
# blurring the marker.
MARKER_CELLS_PX = 40


def write_marker(path: Path) -> Path:
    """Draw the rack's marker to a PNG, and hand back where it landed.

    Drawn rather than shipped as a file, so that the marker the rack carries
    and the marker the camera looks for cannot drift apart: both come from
    MARKER_DICTIONARY and MARKER_ID in rack/layout.py.
    """
    dictionary = cv2.aruco.getPredefinedDictionary(MARKER_DICTIONARY)
    # Six cells across: four of payload and a one-cell quiet border, which the
    # detector needs in order to find the square at all.
    side = MARKER_CELLS_PX * 6
    image = cv2.aruco.generateImageMarker(dictionary, MARKER_ID, side)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    return path


def rack_sdf(x: float, y: float, yaw: float, marker_uri: str) -> str:
    """The whole rack, standing at (x, y) on the table and turned by ``yaw``."""
    # Long enough to hold every slot plus a little either end.
    length = (SLOT_COUNT - 1) * SLOT_SPACING + 0.08
    return (
        TEMPLATE.read_text()
        .split("-->\n", 1)[1]
        .format(
            x=x,
            y=y,
            z=TABLE_TOP_Z + RACK_BASE_HEIGHT / 2.0,
            yaw=yaw,
            length=length,
            base_height=RACK_BASE_HEIGHT,
            marker_z=RACK_BASE_HEIGHT / 2.0 + 0.0005,
            marker_size=MARKER_SIZE,
            marker_uri=marker_uri,
            pegs="\n".join(peg_sdf(i) for i in range(SLOT_COUNT)),
        )
    )


# The rack stands square to the table, with its row of slots running along x.
#
# Its slots run along its own y, so a quarter turn is what lays them out in a
# line beside the arm rather than pointing away from it. That keeps every slot
# at much the same distance from the base: a row running away along y has one
# end folded under the arm and the other at full stretch, and the far end of it
# was outside the reach in arm/dimensions.py.
RACK_YAW = math.pi / 2


def random_rack_pose(rng) -> tuple[float, float, float]:
    """Where the rack stands this run.

    The place is drawn rather than fixed, because the whole point of the marker
    is that the arm finds the rack instead of being told where it is. A test
    that always put the rack in the same place would never exercise that.

    The angle is not drawn. The rack is square to the table, on the arm's left,
    with the glasses on its right — far enough apart that a survey picture of
    the glasses has bare table behind it rather than the rack. What the arm
    still has to find is where along the table it is standing.

    The band it is drawn in keeps all six slots inside COMFORTABLE_REACH: the
    row is 580 mm long, so the middle may only wander about 30 mm before one
    end or the other leaves it.
    """
    return rng.uniform(0.32, 0.38), rng.uniform(0.34, 0.38), RACK_YAW
