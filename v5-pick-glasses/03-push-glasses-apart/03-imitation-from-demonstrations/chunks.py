"""The action chunk: a recorded jaw path in, a chunk the bench can follow out.

A demonstration is the path the jaw really followed, which the bench writes
down on every action as ``Record.waypoints``. A chunk is what the policy
emits. This module is the arithmetic between the two, and it holds no model
and no geometry of pushing.

Three decisions live here, and each one is a choice the document leaves open.

**The chunk is the push and nothing else.** A recorded path runs descend,
feel, push, back off, lift. ``Bench.follow`` already does the descent for
free --- it puts the jaw clear above the first waypoint and brings it down,
stopping if it touches something --- and lifts at the end. So the part worth
copying is the part at push height from where the jaw starts moving across
the table to the furthest point it reached. The back-off and the lift are
trimmed off; the bench does both.

**A chunk is a fixed number of waypoints.** The policy's output has a fixed
shape, so every demonstration is resampled to ``CHUNK`` points. Waypoints are
consumed one ``WAYPOINT_PERIOD`` apart, so the resampling is in time rather
than in distance: the shape of the demonstrated speed --- slow while feeling
for the glass, quicker once pushing --- is kept, and only the overall tempo
is stretched or squeezed. ``CHUNK`` is set near the median length of the
teacher's own pushes, so a typical demonstration replays close to the speed
it was made at. A long one runs faster than it did and a short one slower.

How much faster is bounded, and not by anything here. The bench gives a leg
``max(WAYPOINT_PERIOD, length / TOP_SPEED)`` seconds, so waypoints further
apart than ``TOP_SPEED * WAYPOINT_PERIOD`` --- 10 mm --- are simply taken
slower rather than at a speed the arm does not have. The teacher's own legs
are under 2 mm, and resampling the longest of its pushes into ``CHUNK``
points leaves them under 2 mm as well, so the cap does not bind on anything
copied from it. It would bind on a policy that learned to emit coarser
waypoints than its demonstrations, and the effect would be a slower push
rather than a faster one.

**Heading is carried as its cosine and sine.** An angle wraps at pi, and a
model fitted to a wrapping number learns the wrap as a cliff. Two numbers
that do not wrap cost one column and remove the problem. ``to_waypoints``
turns them back into an angle.
"""

from __future__ import annotations

import math

import numpy as np
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE

from bench import PUSH_HEIGHT, TRAVEL_HEIGHT, Seen, Waypoint

# One chunk's waypoints. Near the median of the teacher's own pushes measured
# at the bench's waypoint rate, so a typical demonstration is replayed at
# about the speed it was made at. At WAYPOINT_PERIOD each, a chunk is a few
# seconds of arm time.
CHUNK = 120
# x, y, z, cos heading, sin heading.
ACTION_WIDTH = 5

# A waypoint counts as being at push height within this. The recorded path is
# the jaw's commanded position, so the descent lands on PUSH_HEIGHT exactly,
# but floating point should not decide where the segment starts.
AT_PUSH_HEIGHT = 1e-6


def push_segment(waypoints: tuple[Waypoint, ...]) -> tuple[Waypoint, ...]:
    """The feeling-and-pushing part of a recorded path, with the back-off and lift off.

    The jaw only goes forward until the push ends, so the furthest point from
    where it reached push height is where the back-off starts. Returns an
    empty tuple for a path that never got down to push height, which is what
    a push blocked on the way down leaves behind.
    """
    low = [i for i, point in enumerate(waypoints) if point.z <= PUSH_HEIGHT + AT_PUSH_HEIGHT]
    if len(low) < 2:
        return ()
    start, end = low[0], low[-1]
    origin = waypoints[start]
    gone = [math.dist((p.x, p.y), (origin.x, origin.y)) for p in waypoints[start : end + 1]]
    furthest = start + int(np.argmax(gone))
    return tuple(waypoints[start : furthest + 1]) if furthest > start else ()


def to_action(waypoints: tuple[Waypoint, ...]) -> np.ndarray:
    """A run of waypoints as the (n, 5) numbers a policy is fitted on."""
    return np.array(
        [[p.x, p.y, p.z, math.cos(p.heading), math.sin(p.heading)] for p in waypoints],
        dtype=np.float32,
    )


def resample(action: np.ndarray, count: int = CHUNK) -> np.ndarray:
    """``count`` waypoints spread evenly over the same path, in time rather than distance."""
    action = np.asarray(action, dtype=np.float32)
    if action.ndim != 2 or action.shape[1] != ACTION_WIDTH:
        raise ValueError(f"an action is (n, {ACTION_WIDTH}), not {action.shape}")
    if len(action) < 2:
        raise ValueError("a path needs two waypoints to be resampled")
    was = np.linspace(0.0, 1.0, len(action))
    now = np.linspace(0.0, 1.0, count)
    return np.stack([np.interp(now, was, column) for column in action.T], axis=1).astype(np.float32)


def to_waypoints(action: np.ndarray) -> tuple[tuple[Waypoint, ...], int]:
    """A policy's chunk as waypoints the bench will accept, and how many it had to pull in.

    Nothing stops a network producing a number outside the jaw's range, so
    each waypoint is pulled back inside it. That is a limit on the actuator
    and not a second try at a refused push: a chunk aimed off the table is
    still carried out, just along the edge, and the count returned says how
    often it happened so the number can be reported rather than hidden.
    """
    action = np.asarray(action, dtype=float)
    if action.ndim != 2 or action.shape[1] != ACTION_WIDTH:
        raise ValueError(f"a chunk is (n, {ACTION_WIDTH}), not {action.shape}")
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    inside = np.stack(
        [
            np.clip(action[:, 0], TABLE_CENTRE_XY[0] - half_x, TABLE_CENTRE_XY[0] + half_x),
            np.clip(action[:, 1], TABLE_CENTRE_XY[1] - half_y, TABLE_CENTRE_XY[1] + half_y),
            np.clip(action[:, 2], PUSH_HEIGHT, TRAVEL_HEIGHT),
        ],
        axis=1,
    )
    pulled = int(np.any(np.abs(inside - action[:, :3]) > 1e-9, axis=1).sum())
    headings = np.arctan2(action[:, 4], action[:, 3])
    points = tuple(
        Waypoint(float(x), float(y), float(z), float(heading))
        for (x, y, z), heading in zip(inside, headings, strict=True)
    )
    return points, pulled


def aimed_at(waypoints: tuple[Waypoint, ...], seen: list[Seen]) -> tuple[int, tuple[float, float]]:
    """Which glass a chunk pushes, and where it leaves it. Not part of the policy.

    The bench's ``Chunk`` carries a glass and an aim beside the waypoints,
    because the scorecard counts pushes per glass and measures how far each
    glass ended from where it was aimed. A policy that emits waypoints
    produces neither, so both are read back off the chunk here.

    The glass is the one the jaw ends up against: the smallest distance from
    the last fingertip position to a glass's measured edge. The aim is that
    fingertip, moved forward by half the glass's measured width, which is
    where the middle of a glass sits when the fingertip is against it. That
    is solution 1's own convention, and it carries solution 1's own
    approximation with it --- a glass narrower at jaw height than at its
    widest is left a little short of where the aim says.
    """
    if not seen:
        raise ValueError("a chunk has to be aimed at a glass, and the table is empty")
    last = waypoints[-1]
    tip = (last.x, last.y)
    forward = (math.cos(last.heading), math.sin(last.heading))
    glass = min(seen, key=lambda g: math.dist((g.x, g.y), tip) - g.widest / 2)
    reach = glass.widest / 2
    return glass.id, (tip[0] + reach * forward[0], tip[1] + reach * forward[1])
