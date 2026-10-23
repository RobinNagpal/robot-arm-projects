"""What problem 4 takes from problem 3, gathered in one place.

Problem 4 is problem 3's task with the overhead camera and the push-by-push
hand-over taken away. The cell itself — the physics, the glasses, the jaw, the
tipping arithmetic — is the same cell. Problem 3 keeps that cell in
``common_bench.py``, apart from what belongs to problem 3 alone, and problem 4
keeps an exact copy of it in ``from-problem-3/``, so that the two problems share
no code and still push with the same physics.

Everything taken from the copy passes through this one module, so that a reader
can see the whole debt to problem 3 on one page. Problem 4's own ``simulator.py``
extends the common simulator with problem 4's own draw.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROBLEM = Path(__file__).resolve().parent.parent
# This problem's copy of the parts of problem 3 it is built on.
PUSHING = PROBLEM / "from-problem-3"
GEOMETRY = PUSHING / "01-one-fixed-nudge"

# The copy of the common examiner is already on the path through pixi.toml.
# Solution 1 is not, because its folder name starts with a digit and so cannot
# be a package name; problem 3's own solutions reach it the same way. It is
# appended, so that nothing in it can stand in front of this problem's modules.
if str(GEOMETRY) not in sys.path:
    sys.path.append(str(GEOMETRY))

# Problem 3's classes, under the names this problem uses for them. Problem 3
# calls a table in the physics engine a bench; here it is a simulator, run by
# the examiner.
from common_bench import (  # noqa: E402
    CROWD_SHARE,
    DESCEND_SPEED,
    FEEL_SPEED,
    GRIP_ROOM,
    JAW_FRICTION,
    JAW_HALF_HEIGHT,
    JAW_PARTS,
    JAW_SEGMENTS,
    JAW_THICKNESS,
    JAW_TOP,
    MAX_WAYPOINTS,
    PUSH_HEIGHT,
    PUSH_SPEED,
    SETTLE,
    STANDING_TILT_DEG,
    TABLE_FRICTION,
    TEST_SEEDS,
    TIMESTEP,
    TOOL_LENGTH,
    TOP_SPEED,
    TOUCH_FORCE,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    WRIST_ACROSS,
    WRIST_LENGTH,
    Chunk,
    Felt,
    Push,
    Record,
    Seen,
    SpawnedGlass,
    Waypoint,
    _glass_xml,
    has_room,
    in_zone,
    segment_distance,
)
from common_bench import CommonBench as CommonSimulator  # noqa: E402

# Reporting several runs, and the rows kept per table, so that a spread reads
# the same in both problems' reports; and the recording a film is made with.
from common_film import FPS, HOLD, LINE_LENGTH  # noqa: E402
from common_film import CommonFilmedBench as CommonFilmedSimulator  # noqa: E402
from common_scoring import _band as band  # noqa: E402
from common_scoring import save_tables, spread  # noqa: E402

# The size and lens of problem 3's overhead camera. Problem 4 has no overhead
# camera, but its wrist camera takes pictures of the same size through the same
# lens, so that a learned solution can reuse the shapes it was built around.
from top_view import TOP_VIEW_FOVY_DEG, TOP_VIEW_SIZE  # noqa: E402

# The cell's own numbers, which `examiner` itself reads from here. A draw and a
# camera both need them, so they are re-exported rather than imported twice by
# two different routes and allowed to disagree.
from work_cell.glasses.shapes import KIND_RANGES  # noqa: E402
from work_cell.rack.layout import GLASS_ZONE  # noqa: E402
from work_cell.table.layout import TABLE_TOP_Z  # noqa: E402

KINDS = tuple(KIND_RANGES)

__all__ = [
    "CROWD_SHARE",
    "DESCEND_SPEED",
    "FPS",
    "HOLD",
    "LINE_LENGTH",
    "GLASS_ZONE",
    "KINDS",
    "KIND_RANGES",
    "TABLE_TOP_Z",
    "FEEL_SPEED",
    "GEOMETRY",
    "GRIP_ROOM",
    "PUSHING",
    "PUSH_HEIGHT",
    "PUSH_SPEED",
    "JAW_HALF_HEIGHT",
    "JAW_SEGMENTS",
    # How close a straight stretch comes to a point. The shape of the hand and
    # the shape of a glass are both the examiner's, so everything that has to ask
    # whether one would be dragged through the other asks it the same way.
    "segment_distance",
    # How many waypoints one path may hold. Any solution that writes its own
    # paths rather than borrowing them has to check against it, because the
    # simulator rejects a longer path and the arm never moves.
    "MAX_WAYPOINTS",
    "JAW_FRICTION",
    "JAW_PARTS",
    "JAW_THICKNESS",
    "JAW_TOP",
    "SETTLE",
    "STANDING_TILT_DEG",
    "TABLE_FRICTION",
    "TEST_SEEDS",
    "TIMESTEP",
    "TOUCH_FORCE",
    "TOOL_LENGTH",
    "TOP_SPEED",
    "TOP_VIEW_FOVY_DEG",
    "TOP_VIEW_SIZE",
    "TRAVEL_HEIGHT",
    "WRIST_ACROSS",
    "WRIST_LENGTH",
    "WAYPOINT_PERIOD",
    "Chunk",
    "CommonFilmedSimulator",
    "CommonSimulator",
    "Felt",
    "Push",
    "Record",
    "Seen",
    "SpawnedGlass",
    "Waypoint",
    "has_room",
    "band",
    "glass_xml",
    "save_tables",
    "spread",
    "in_zone",
]

# One glass as MuJoCo XML, for a world that is not the common simulator's own: the
# whole arm's cell builds its own world round the same glasses.
glass_xml = _glass_xml

# The copies of problem 3's solution files import these same names from a
# module they call ``bench``, which is problem 3's name for it. Problem 4 has no
# module of that name, so this one answers to it, and the copies stay exactly as
# problem 3 has them.
sys.modules.setdefault("bench", sys.modules[__name__])
