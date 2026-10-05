"""The join between what SmolVLA emits and what this cell's jaw is.

The model's document says somebody has to choose this reading and that the
choice must be held still across solutions 5 and 6. This module is that
choice, written down once. Nothing here is fitted, measured or tuned on the
bench; every number below is read off the model's own configuration or off
the cell's own constants.

**What the model's action space actually is.** ``lerobot/smolvla_base``
declares ``action`` of shape 6 and ``observation.state`` of shape 6, with both
normalised MEAN_STD. The statistics shipped with the checkpoint are three sets
of SO-100 joint angles in degrees, keyed ``so100``, ``so100-blue`` and
``so100-red``. So the six slots are an SO-100 follower arm's five joints and
its gripper: shoulder pan, shoulder lift, elbow flex, wrist flex, wrist roll,
gripper.

**And those statistics do not apply themselves.** They are saved under keys
like ``so100.buffer.action.mean``, while the normaliser looks for ``action``
and ``observation.state``. A key it cannot find is passed through unchanged,
so with the released checkpoint both the normaliser and the un-normaliser are
no-ops: the state goes in as a z-score and the actions come out as z-scores.
Picking one of the three arms to un-normalise against would only compose a
fixed affine map onto what follows, so this module works in the normalised
space the model really speaks and says what one standard deviation means here.

**The reading.** Four of the six slots are used, chosen by what the joint
does on the arm the statistics came from:

- *shoulder pan* swings the whole arm across the bench, so it is the jaw's x;
- *shoulder lift* reaches out and back, so it is the jaw's y;
- *elbow flex* raises and lowers the hand, so it is the jaw's height;
- *wrist roll* turns the hand about the vertical, so it is the jaw's heading.

*Wrist flex* and *gripper* are dropped: this bench holds the jaw level and
closed and offers no way to change either.

**What one standard deviation is worth.** A z-score is not a length, so
something has to set the scale, and only one thing in this solution has both a
metric extent and is seen by the model: the frame of the straight-down
picture. So ``ACTION_SPAN`` standard deviations span that frame exactly. That
is the reading that lets the model put the jaw anywhere it can see and nowhere
it cannot, which is the one property a join has to have if the score is to be
about the model rather than about the join.

It has a price, and it is worth naming because it is not obvious. A waypoint's
position and the jaw's speed are the same number here — the bench consumes
waypoints a fixed period apart, so how far apart they are *is* how fast the
jaw goes. Fixing the box therefore fixes the speed too, and the two cannot be
chosen separately. Nothing is clipped to a gentler speed, because a speed
limit would be a number fitted to this bench and this solution fits nothing.

**The state is the same reading backwards**, so the model is handed its own
pose in the same units it answers in. The checkpoint ships no statistics for
``observation.state`` at all, only for ``action``, so nothing says what scale
that input expects and this is the only self-consistent answer available.
"""

from __future__ import annotations

import math

import numpy as np

from bench import JAW_THICKNESS, PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Seen, Waypoint
from top_view import TOP_VIEW_HALF_FRAME, VIEW_CENTRE

# Which of SmolVLA's six slots carries what, in the reading above.
ACROSS, OUT, UP, TURN = 0, 1, 2, 4
SLOTS = 6

# How many standard deviations of the model's own action space the picture's
# frame covers. Two, because a z-score of two is the edge of what a normally
# spread quantity does, so the whole frame is reachable without the great
# majority of the model's output pinning itself against the edges.
ACTION_SPAN = 2.0

# The instruction, the same on every table and every push. Solution 6 uses
# this exact string, because the pair is only clean while it is held still.
INSTRUCTION = "the glasses are too close together, push them apart"

# Which way each slot runs. A joint angle's sign is a convention of the arm it
# was recorded on, and the checkpoint carries a mean and a spread but nothing
# that says which way the joint turns, so this cannot be read off it and had
# to be fixed: larger is further along the cell's own axis, and on the height
# slot that means larger is higher. ``run.py --upside-down`` turns the height
# slot over, which is how the solution measures what this one undetermined
# convention is worth. The scored result is always this one.
UP_HIGHER = 1.0


def to_jaw(action: np.ndarray, up: float = UP_HIGHER) -> np.ndarray:
    """One chunk of the model's actions, read as jaw waypoints: (n, 6) in, (n, 4) out.

    Columns out are x, y, z, heading, which is what ``Chunk.from_array`` takes.
    Everything is clipped into the box the bench will accept, so a chunk that
    comes back from here is one ``follow()`` can carry out.
    """
    action = np.asarray(action, dtype=float)
    if action.ndim != 2 or action.shape[1] != SLOTS:
        raise ValueError(f"a SmolVLA chunk is (n, {SLOTS}), not {action.shape}")
    unit = np.clip(action / ACTION_SPAN, -1.0, 1.0)
    return np.stack(
        [
            VIEW_CENTRE[0] + unit[:, ACROSS] * TOP_VIEW_HALF_FRAME,
            VIEW_CENTRE[1] + unit[:, OUT] * TOP_VIEW_HALF_FRAME,
            PUSH_HEIGHT + (up * unit[:, UP] + 1.0) / 2.0 * (TRAVEL_HEIGHT - PUSH_HEIGHT),
            unit[:, TURN] * math.pi,
        ],
        axis=1,
    )


def to_state(jaw: Waypoint, up: float = UP_HIGHER) -> np.ndarray:
    """Where the jaw is, as the six numbers the model takes for joint readings.

    The inverse of ``to_jaw`` on the four slots it uses, and zero on the two it
    does not, which is the middle of the model's own range for them.
    """
    state = np.zeros(SLOTS)
    state[ACROSS] = _unit((jaw.x - VIEW_CENTRE[0]) / TOP_VIEW_HALF_FRAME)
    state[OUT] = _unit((jaw.y - VIEW_CENTRE[1]) / TOP_VIEW_HALF_FRAME)
    state[UP] = _unit(up * (2.0 * (jaw.z - PUSH_HEIGHT) / (TRAVEL_HEIGHT - PUSH_HEIGHT) - 1.0))
    state[TURN] = _unit(_wrapped(jaw.heading) / math.pi)
    return state


def _unit(value: float) -> float:
    return float(np.clip(value, -1.0, 1.0) * ACTION_SPAN)


def _wrapped(heading: float) -> float:
    """The same heading, in -pi to pi."""
    return (heading + math.pi) % (2 * math.pi) - math.pi


def chunk_for(path: np.ndarray, seen: list[Seen]) -> Chunk:
    """The model's path, as a chunk the bench will take.

    ``Chunk`` wants a glass and an aim beside the waypoints. Neither is a
    decision this solution makes: the model was not asked which glass it meant
    and it has no notion of where a glass will end up. So the glass is read
    back off the path afterwards — the one the jaw comes nearest to while low
    enough to touch it — and the aim is where the path ends. Both are
    bookkeeping for the record, and nothing is planned with either.
    """
    waypoints = [Waypoint(*row) for row in path.tolist()]
    return Chunk(nearest(path, seen), tuple(waypoints), (float(path[-1, 0]), float(path[-1, 1])))


def nearest(path: np.ndarray, seen: list[Seen]) -> int:
    """Which glass the path comes closest to, counting only where the jaw is low enough to touch it."""
    best, best_gap = seen[0].id, math.inf
    for glass in seen:
        low = path[path[:, 2] <= glass.height]
        points = low if len(low) else path
        gap = float(np.min(np.hypot(points[:, 0] - glass.x, points[:, 1] - glass.y)))
        if gap < best_gap:
            best, best_gap = glass.id, gap
    return best


def hits_refused(path: np.ndarray, seen: list[Seen], refused: set[int]) -> int | None:
    """Which refused glass this path would touch, or None if it keeps clear of all of them.

    A glass refused for tipping stays in the picture, so the model can still
    aim at it, and nothing in its pretraining would warn it off. The one
    mistake this problem cannot absorb is a toppled glass, so a path that
    would reach one is not carried out at all.
    """
    for glass in seen:
        if glass.id not in refused:
            continue
        low = path[path[:, 2] <= glass.height]
        if not len(low):
            continue
        gap = float(np.min(np.hypot(low[:, 0] - glass.x, low[:, 1] - glass.y)))
        if gap <= glass.widest / 2 + JAW_THICKNESS / 2:
            return glass.id
    return None
