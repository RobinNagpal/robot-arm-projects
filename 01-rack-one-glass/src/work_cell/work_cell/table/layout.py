"""Where the table is, and where the arm stands on it.

The table top is the plane everything in this cell is measured against. The arm
is bolted to it, the glasses rest on it, the rack stands on it, and every height
in the code is a distance from it. That is why these numbers live in one place:
the world file, the glass spawner, the planning scene and the task all have to
agree on them, and the cheapest way to guarantee that is to give them one
source.

Nothing here is about a glass. A glass's size is measured during the run, never
written down.
"""

from __future__ import annotations

import numpy as np

WORLD_FRAME = "world"

# The table itself. Its top is at 75 cm, a normal bench height.
#
# It is wider than the arm can reach on purpose. The rack stands on one side of
# it and the glasses on the other, and the gap between the two is what stops a
# survey picture of the glasses having the rack in the back of it. Sizing the
# table to the arm's reach instead would put them back within touching
# distance.
TABLE_TOP_Z = 0.75
TABLE_SIZE = (1.60, 1.40, 0.05)
TABLE_CENTRE_XY = (0.40, 0.0)

# The arm stands at the near edge and reaches out along +x.
ROBOT_BASE = np.array([0.0, 0.0, TABLE_TOP_Z])
