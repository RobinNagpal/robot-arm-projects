"""The ranges the simulated room is drawn from.

This is the simulator's side of the project, and nothing the robot runs may
import it. Every size and position here is what the robot has to *find out*;
if the task code could read these numbers, measuring them would be theatre.
A test enforces that boundary.

Every run draws a new room from these ranges, so the robot never sees the
same top twice. A seed makes any one room repeatable.
"""

from __future__ import annotations

# The table top. It stands upright on one long edge, on the floor, to the
# arm's left, with a face towards the arm, give or take a few degrees.
# Distances and angles are measured from the arm's base to the top's centre.
TOP_AZIMUTH_DEG = (80.0, 100.0)
TOP_DISTANCE = (0.50, 0.55)
TOP_TURN_DEG = (-8.0, 8.0)
TOP_LENGTH = (0.24, 0.30)
TOP_WIDTH = (0.16, 0.20)
TOP_THICKNESS = (0.016, 0.020)
# A light board: poplar plywood is about this. Held flat by one edge, every
# gram of it is a lever on the grip. The launch file can override it, to try
# a heavier top without making it bigger.
TOP_DENSITY = 400.0  # kg/m^3

# The two holders, one at each end of the top. Each is a U seen from above:
# two jaws, one each side of the board, and a wall across the end, so the top
# can neither tip over nor slide along its length. The only way out is
# straight up. They hold the ends only, so the middle of the upper edge is
# free for the fingers.
HOLDER_HEIGHT = (0.05, 0.06)
# How far along the top each holder grips it.
HOLDER_DEPTH = 0.035
HOLDER_JAW = 0.02  # thickness of each jaw and of the end wall
# The gap between a jaw and the board, each side. Enough that the board lifts
# out without catching, small enough that it stands close to upright.
HOLDER_PLAY = 0.0015

# The four legs. They already stand where the table goes, to the arm's right:
# the far two where the top's far edge will rest on their middles, the near
# two just in from where its near edge will be. Standing them there is what
# v2 does; this project starts from them standing. All four are the same, as
# they would be in a flat-pack table.
#
# The far row is 76-80 cm out, measured from the base to its middle. At 69 cm
# the arm, lowering the top's near edge onto the near legs, had to fold up so
# far that its joints could not follow the last few degrees smoothly.
TABLE_AZIMUTH_DEG = (-75.0, -65.0)
TABLE_FAR_DISTANCE = (0.76, 0.80)
TABLE_TURN_DEG = (-5.0, 5.0)
# At least 15 cm tall. The arm lets go of the top holding it level by its near
# edge, a finger above and a finger below, and with the top any lower than
# that the arm's wrist is down at the floor. Legs 13 cm tall could not be laid
# on.
LEG_LENGTH = (0.15, 0.17)
LEG_THICKNESS = (0.025, 0.035)
# How far in from the top's near edge and its ends a leg's outer faces stand.
LEG_INSET = 0.012
LEG_DENSITY = 500.0  # kg/m^3, about pine

# Saturated, well separated colours. The robot tells parts from the room by how
# colourful they are, so nothing here may be grey.
PALETTE = (
    (0.80, 0.12, 0.12),  # red
    (0.10, 0.65, 0.20),  # green
    (0.12, 0.28, 0.80),  # blue
    (0.85, 0.72, 0.08),  # yellow
    (0.72, 0.12, 0.66),  # magenta
    (0.06, 0.62, 0.70),  # cyan
)

# The room is grey on purpose, for the same reason.
HOLDER_COLOUR = (0.62, 0.62, 0.64)
