"""What problem 4 takes from problem 3, gathered in one place.

Problem 4 is problem 3's task with the overhead camera and the push-by-push
hand-over taken away. The cell itself — the physics, the glasses, the jaw, the
tipping arithmetic — is the same cell. Problem 4 keeps its own copy of it in
``from-problem-3/``, so that the two problems share no code. The copy is kept
exactly as problem 3 has it, because the comparison between the two problems
means something only while the two cells agree.

Everything taken from the copy passes through this one module, so that a reader
can see the whole debt to problem 3 on one page.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROBLEM = Path(__file__).resolve().parent.parent
# This problem's copy of the parts of problem 3 it is built on.
PUSHING = PROBLEM / "from-problem-3"
GEOMETRY = PUSHING / "01-one-fixed-nudge"

# The bench itself is already on the path through pixi.toml. Solution 1 is not,
# because its folder name starts with a digit and so cannot be a package name;
# problem 3's own solutions reach it the same way.
#
# These are appended rather than put at the front, and that is not a detail.
# Both problems have a module called `scoring`, and problem 4's own folder is
# ahead of these on the path. Putting problem 3's bench first would quietly
# hand every `import scoring` to problem 3's push-by-push scorecard, and the
# tests would pass while measuring the wrong thing.
for folder in (PUSHING / "bench", GEOMETRY):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

from bench import (  # noqa: E402
    CROWD_SHARE,
    DESCEND_SPEED,
    FEEL_SPEED,
    GRIP_ROOM,
    JAW_HALF_HEIGHT,
    MAX_WAYPOINTS,
    PUSH_HEIGHT,
    PUSH_SPEED,
    STANDING_TILT_DEG,
    TEST_SEEDS,
    TOOL_LENGTH,
    TOP_SPEED,
    TOP_VIEW_FOVY_DEG,
    TOP_VIEW_SIZE,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    WRIST_ACROSS,
    WRIST_LENGTH,
    Bench,
    Chunk,
    Felt,
    Push,
    Record,
    Seen,
    SpawnedGlass,
    Waypoint,
    has_room,
    in_zone,
    scene,
    segment_distance,
)

# The cell's own numbers, which `bench` itself reads from here. A draw and a
# camera both need them, so they are re-exported rather than imported twice by
# two different routes and allowed to disagree.
from work_cell.glasses.shapes import KIND_RANGES  # noqa: E402
from work_cell.rack.layout import GLASS_ZONE  # noqa: E402
from work_cell.table.layout import TABLE_TOP_Z  # noqa: E402

KINDS = tuple(KIND_RANGES)

__all__ = [
    "CROWD_SHARE",
    "DESCEND_SPEED",
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
    # How close a straight stretch comes to a point. The shape of the hand and
    # the shape of a glass are both the bench's, so everything that has to ask
    # whether one would be dragged through the other asks it the same way.
    "segment_distance",
    # How many waypoints one path may hold. Any solution that writes its own
    # paths rather than borrowing them has to check against it, because the
    # bench rejects a longer path and the arm never moves.
    "MAX_WAYPOINTS",
    "STANDING_TILT_DEG",
    "TEST_SEEDS",
    "TOOL_LENGTH",
    "TOP_SPEED",
    "TOP_VIEW_FOVY_DEG",
    "TOP_VIEW_SIZE",
    "TRAVEL_HEIGHT",
    "WRIST_ACROSS",
    "WRIST_LENGTH",
    "WAYPOINT_PERIOD",
    "Bench",
    "Chunk",
    "Felt",
    "Push",
    "Record",
    "Seen",
    "SpawnedGlass",
    "Waypoint",
    "has_room",
    "in_zone",
    "scene",
]
