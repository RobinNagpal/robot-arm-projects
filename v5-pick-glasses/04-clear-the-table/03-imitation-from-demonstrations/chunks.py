"""The action: a path the jaw followed in, a chunk a learned policy can emit out.

Problem 4's contract already asks for waypoints. The teacher answers with a
``Chunk`` and the bench carries it out, so a demonstration's action does not
have to be invented from push parameters the way problem 3's did -- it is the
path itself. What this module does is give that path a fixed shape, because a
network's output has one.

**Two kinds of path, one shape.** The teacher answers with a path to go and
stand somewhere, which is a single waypoint, and with a path that comes down
and shoves a glass, which is forty to a hundred and fifty. A fixed-width
output has to hold both. So a chunk is ``CHUNK`` rows, the path's own
waypoints at their own spacing, and then the last waypoint repeated to the
end. A sixth column says which rows are the path: one while it is still going,
zero once it has ended.

That sixth column is the only thing here that is not geometry, and it is worth
saying what it is not. It is **not** a channel for "this table is finished":
``bench/stopping.py`` explains why that would be a different experiment, and
nothing in these demonstrations says when a table is done. It says how long
*this path* is, which every demonstration labels, so it is learned from the
data like every other column.

**Nothing is resampled.** Problem 3 squeezed every push into a chunk's worth
of waypoints, which made the student push faster than its teacher. Padding
avoids that: a kept path reaches the bench with the spacing the teacher wrote,
so the student pushes at the teacher's speed and comes down at its descent
speed. It also keeps the corner at the bottom of the descent sharp. Resampling
a path that drops straight down and then drives straight forward rounds that
corner off, and a jaw that cuts it is a jaw moving sideways while it is still
coming down, which is how a glass gets clipped.

The price is padding: a path to go and look is one row of a hundred and sixty.
That padding is not wasted on the fit, because the row it repeats is the end of
the path, and where a path ends is the hardest and most useful thing about it.

**Heading is carried as its cosine and sine.** Problem 3's reason, unchanged: an
angle wraps at pi and a model fitted to a wrapping number learns the wrap as a
cliff. Two columns that do not wrap cost one number and remove the problem.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE

from partners import PUSH_HEIGHT, TRAVEL_HEIGHT, Waypoint

# How many rows a chunk holds. Measured on the teacher rather than chosen. Its
# paths are 1 waypoint when it goes to look and 39 to 190 when it pushes, with
# the median push at 44 and the ninety-ninth in a hundred at about 130; over the
# whole 300-table band the longest is 190 and nothing was turned away for being
# too long. The arithmetic allows a longer path -- a 150 mm push at one
# millimetre a waypoint, behind a descent and a reach, comes to about 234 -- so
# this is not a bound, and ``collect.py`` counts the paths that do not fit
# rather than cutting them. Half a push is worse than no push.
CHUNK = 200

# x, y, z, cos heading, sin heading, still going.
ACTION_WIDTH = 6

# Where the "still going" column is read, and the line it is read against. A
# network answers in floats, so the column is a number either side of a half
# rather than a flag.
STILL = 5
GOING = 0.5

# How far a waypoint has to be moved before it counts as having been pulled in.
# A micrometre, which is below anything the arm can do and above the resolution
# of the float32 a demonstration is stored in: at the table's own distances that
# is a few parts in a hundred million, so a tighter line would count the storage
# rather than the network. The clipping itself is exact; only the count is loose.
PULLED_BY = 1e-6


def to_action(waypoints: Sequence[Waypoint]) -> np.ndarray | None:
    """One path as a ``(CHUNK, ACTION_WIDTH)`` training target, or None if it will not fit.

    None rather than an error, because a path longer than a chunk is an
    ordinary thing to meet in a demonstration set and the collector counts it.
    """
    if not waypoints:
        raise ValueError("a path has at least one waypoint; follow() refuses an empty one")
    if len(waypoints) > CHUNK:
        return None
    rows = [
        [point.x, point.y, point.z, math.cos(point.heading), math.sin(point.heading), 1.0]
        for point in waypoints
    ]
    # The padding holds the last pose with the column turned off, so the target
    # after the path has ended is "stand still, and the path has ended".
    tail = [*rows[-1][:STILL], 0.0]
    rows += [tail] * (CHUNK - len(rows))
    return np.asarray(rows, dtype=np.float32)


def length_of(action: np.ndarray) -> int:
    """How many waypoints this chunk's own sixth column claims, at least one.

    At least one because the bench will not follow an empty path, and a chunk
    whose first row already says the path has ended is still the jaw being
    asked to stand somewhere.
    """
    going = np.asarray(action, dtype=float)[:, STILL] >= GOING
    ended = np.flatnonzero(~going)
    return len(going) if not len(ended) else max(1, int(ended[0]))


def to_waypoints(action: np.ndarray) -> tuple[tuple[Waypoint, ...], int]:
    """A policy's chunk as waypoints the bench will take, and how many had to be pulled in.

    Nothing stops a network answering with a number the jaw cannot reach, so
    each waypoint is pulled back inside the table and the heights the jaw rides
    between. That is a limit on the actuator and not a second attempt at the
    answer: a chunk aimed off the table is still carried out, along the edge,
    and the count returned is so the clipping can be reported rather than
    hidden. Problem 3's solution 3 does the same thing for the same reason.
    """
    action = np.asarray(action, dtype=float)
    if action.ndim != 2 or action.shape[1] != ACTION_WIDTH:
        raise ValueError(f"a chunk is (n, {ACTION_WIDTH}), not {action.shape}")
    rows = action[: length_of(action)]
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    inside = np.stack(
        [
            np.clip(rows[:, 0], TABLE_CENTRE_XY[0] - half_x, TABLE_CENTRE_XY[0] + half_x),
            np.clip(rows[:, 1], TABLE_CENTRE_XY[1] - half_y, TABLE_CENTRE_XY[1] + half_y),
            np.clip(rows[:, 2], PUSH_HEIGHT, TRAVEL_HEIGHT),
        ],
        axis=1,
    )
    pulled = int(np.any(np.abs(inside - rows[:, :3]) > PULLED_BY, axis=1).sum())
    headings = np.arctan2(rows[:, 4], rows[:, 3])
    points = tuple(
        Waypoint(float(x), float(y), float(z), float(heading))
        for (x, y, z), heading in zip(inside, headings, strict=True)
    )
    return points, pulled
