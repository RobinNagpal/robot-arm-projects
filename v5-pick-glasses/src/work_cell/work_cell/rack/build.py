"""Turning the rack's measurements into a model the simulator can load.

The rack is fixed, so this reads its numbers from rack/layout.py rather than
holding any of its own. Only where it stands is passed in, and that is drawn
per run, because the arm is supposed to find the rack rather than be told.
"""

from __future__ import annotations

import math
from pathlib import Path

from .layout import RACK_BASE_HEIGHT, SLOT_COUNT, SLOT_SPACING, TABLE_TOP_Z

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


def rack_sdf(x: float, y: float, yaw: float) -> str:
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
            pegs="\n".join(peg_sdf(i) for i in range(SLOT_COUNT)),
        )
    )


def random_rack_pose(rng) -> tuple[float, float, float]:
    """Where the rack stands this run.

    Drawn rather than fixed, because the whole point of the marker is that the
    arm finds the rack instead of being told where it is. A test that always
    put the rack in the same place would never exercise that.
    """
    return rng.uniform(0.40, 0.62), rng.uniform(0.26, 0.40), rng.uniform(-math.pi / 8, math.pi / 8)
