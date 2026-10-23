"""What problem 4 takes from problem 3, gathered in one place.

Problem 4 is problem 3's task with the overhead camera and the push-by-push
hand-over taken away, and with the whole arm doing the pushing. The physics,
the glasses, the gripper's shape and the tipping arithmetic are problem 3's.
Problem 3 keeps them in ``common_bench.py``, apart from what belongs to problem
3 alone, and problem 4 keeps an exact copy of it in ``from-problem-3/``, so that
the two problems share no code and still push with the same physics.

Everything taken from the copy passes through this one module, so that a reader
can see the whole debt to problem 3 on one page. Problem 4's own
``table_simulator.py`` extends the common simulator with problem 4's own draw.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROBLEM = Path(__file__).resolve().parents[2]
# This problem's copy of the parts of problem 3 it is built on.
PUSHING = PROBLEM / "from-problem-3"
GEOMETRY = PUSHING / "01-one-fixed-nudge"

# The copy of the common examiner is already on the path through pixi.toml.
# Problem 3's solution 1, whose planner the geometry reference uses, is not,
# because its folder name starts with a digit and so cannot be a package name.
# It is appended, so that nothing in it can stand in front of this problem's
# modules.
if str(GEOMETRY) not in sys.path:
    sys.path.append(str(GEOMETRY))

# Problem 3's classes, under the names this problem uses for them. Problem 3
# calls a table in the physics engine a bench; here it is a simulator, run by
# the examiner.
from common_bench import (  # noqa: E402
    GRIP_ROOM,
    JAW_FRICTION,
    JAW_PARTS,
    JAW_SEGMENTS,
    JAW_TOP,
    SETTLE,
    STANDING_TILT_DEG,
    TABLE_FRICTION,
    TEST_SEEDS,
    TIMESTEP,
    TOUCH_FORCE,
    WRIST_ACROSS,
    WRIST_LENGTH,
    Push,
    Seen,
    SpawnedGlass,
    Waypoint,
    _glass_xml,
    has_room,
    in_zone,
    segment_distance,
)
from common_bench import CommonBench as CommonSimulator  # noqa: E402

# How several runs are reported, so that a spread reads the same in both
# problems' reports.
from common_scoring import spread  # noqa: E402

# The size and lens of problem 3's overhead camera. Problem 4 has no overhead
# camera, but its wrist camera takes pictures of the same size through the same
# lens.
from top_view import TOP_VIEW_FOVY_DEG, TOP_VIEW_SIZE  # noqa: E402

# The glass zone, from the cell's own layout. Problem 3's ranked solution reads
# it from the same module the planner's other names come from.
from work_cell.rack.layout import GLASS_ZONE  # noqa: E402

__all__ = [
    "GEOMETRY",
    "GLASS_ZONE",
    "GRIP_ROOM",
    "PUSHING",
    # The gripper's own shape, which problem 3's planner checks a push against.
    "JAW_FRICTION",
    "JAW_PARTS",
    "JAW_SEGMENTS",
    "JAW_TOP",
    "SETTLE",
    "STANDING_TILT_DEG",
    "TABLE_FRICTION",
    "TEST_SEEDS",
    "TIMESTEP",
    "TOUCH_FORCE",
    "TOP_VIEW_FOVY_DEG",
    "TOP_VIEW_SIZE",
    "WRIST_ACROSS",
    "WRIST_LENGTH",
    "CommonSimulator",
    "Push",
    "Seen",
    "SpawnedGlass",
    "Waypoint",
    "glass_xml",
    "has_room",
    "in_zone",
    # How close a straight stretch comes to a point, which problem 3's planner
    # asks of the hand and every glass.
    "segment_distance",
    "spread",
]

# One glass as MuJoCo XML, for a world that is not the common simulator's own:
# the arm's simulator builds its own world round the same glasses.
glass_xml = _glass_xml

# The copies of problem 3's planner and ranked solution import these same names
# from a module they call ``bench``, which is problem 3's name for it. Problem 4
# has no module of that name, so this one answers to it, and the copies stay
# exactly as problem 3 has them.
sys.modules.setdefault("bench", sys.modules[__name__])
