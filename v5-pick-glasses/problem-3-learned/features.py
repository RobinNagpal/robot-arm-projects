"""What the model is shown about a push, and what it is asked to predict.

Everything is in the push's own frame: ``along`` is the way the jaw moves,
``across`` is to its left. A push to the north and the same push to the east
are one example, not two, because the table's friction is the same everywhere.

The inputs are only what the arm has: the camera's readings of every glass
(bench.Seen) and the push it is thinking of making. No friction, no tipping
rule, no mass. Whether a push slides or topples a glass is for the model to
learn from the pushes it has seen.
"""

from __future__ import annotations

import math

import numpy as np

from bench import KINDS

# How far behind the glass's widest edge the fingertips come down. Enough to
# clear it with the camera's error; not a fact about any glass.
STANDOFF = 0.02
# How far past the glass's middle the jaw feels before giving up. A stemmed
# glass is met at its stem, well inside its widest edge, so the feel has to
# reach the middle; a jaw that misses and lifts under the bowl tips it.
FEEL_PAST = 0.01

# Push lengths the planner may choose, and the model is trained on.
TRAVEL = (0.01, 0.10)
# Where across the glass the jaw may meet it, as a share of its half width.
OFFSET = 0.7

# The model sees this many other glasses, nearest first. Six on a table is the
# most, so five others is everyone.
OTHERS = 5

# Distances in the inputs, and movements in the outputs, are divided by these
# so they sit near 1.
PLACE_SCALE = 0.10
MOVE_SCALE = 0.05

# Per glass: along, across, widest, height, there or not.
_PER_OTHER = 5
INPUTS = len(KINDS) + 3 + 2 + OTHERS * _PER_OTHER
# Pushed glass (along, across), each other glass (along, across), then two
# yes-or-no logits: something toppled, the jaw was blocked on the way down.
OUTPUTS = 2 + 2 * OTHERS + 2
TOPPLED, BLOCKED = OUTPUTS - 2, OUTPUTS - 1


def frame(heading: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors along the push and to its left, one row per heading."""
    along = np.stack([np.cos(heading), np.sin(heading)], -1)
    return along, np.stack([-along[..., 1], along[..., 0]], -1)


def others_of(seen: list, target) -> list:
    """The other glasses on the table, nearest first."""
    rest = [s for s in seen if s.id != target.id]
    return sorted(rest, key=lambda s: math.dist((s.x, s.y), (target.x, target.y)))[:OTHERS]


def encode(seen: list, target, kind: str, heading, offset, travel) -> np.ndarray:
    """One input row per candidate push on ``target``.

    ``kind`` is the table's one known kind. ``heading``, ``offset`` (metres across, left positive) and ``travel`` are
    arrays of the same length, one entry per candidate.
    """
    heading, offset, travel = (np.atleast_1d(np.asarray(v, dtype=np.float64)) for v in (heading, offset, travel))
    n = len(heading)
    along, left = frame(heading)
    rows = np.zeros((n, INPUTS), dtype=np.float32)
    rows[:, KINDS.index(kind)] = 1.0
    k = len(KINDS)
    rows[:, k : k + 3] = np.array([target.height, target.widest, target.foot]) / PLACE_SCALE
    rows[:, k + 3] = offset / PLACE_SCALE
    rows[:, k + 4] = travel / MOVE_SCALE
    base = k + 5
    middle = np.array([target.x, target.y])
    for slot, other in enumerate(others_of(seen, target)):
        d = np.array([other.x, other.y]) - middle
        column = base + slot * _PER_OTHER
        rows[:, column] = along @ d / PLACE_SCALE
        rows[:, column + 1] = left @ d / PLACE_SCALE
        rows[:, column + 2] = other.widest / PLACE_SCALE
        rows[:, column + 3] = other.height / PLACE_SCALE
        rows[:, column + 4] = 1.0
    return rows


def mirror(inputs: np.ndarray, outputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The same pushes seen in a mirror: left and right swap, nothing else changes.

    A true example of the physics for free, which doubles a small set.
    """
    inputs, outputs = inputs.copy(), outputs.copy()
    k = len(KINDS)
    inputs[:, k + 3] *= -1
    inputs[:, k + 5 + 1 :: _PER_OTHER] *= -1
    outputs[:, 1 : 2 + 2 * OTHERS : 2] *= -1
    return inputs, outputs


def outcome(before: list, after: list, target, heading: float, blocked: bool) -> np.ndarray:
    """The output row for one push that was really made.

    Read from two looks, before and after: the arm learns from its own camera,
    not from the simulator's record. A glass that is no longer standing, on
    either side, is ``toppled``.
    """
    along, left = frame(np.array(heading))
    now = {s.id: s for s in after}
    row = np.zeros(OUTPUTS, dtype=np.float32)
    for slot, glass in enumerate([target, *others_of(before, target)]):
        moved = now[glass.id]
        d = np.array([moved.x - glass.x, moved.y - glass.y])
        row[2 * slot] = along @ d / MOVE_SCALE
        row[2 * slot + 1] = left @ d / MOVE_SCALE
    row[TOPPLED] = float(not all(s.standing for s in after))
    row[BLOCKED] = float(blocked)
    return row


def jaw_start(target, heading: float, offset: float) -> tuple[float, float]:
    """Where the fingertips come down for a push on ``target``."""
    along, left = frame(np.array(heading))
    back = target.widest / 2 + STANDOFF
    return tuple(np.array([target.x, target.y]) - back * along + offset * left)


def jaw_reach(target) -> float:
    """How far forward the jaw feels for ``target`` before giving up."""
    return target.widest / 2 + STANDOFF + FEEL_PAST


def angle_wrap(a: np.ndarray) -> np.ndarray:
    return (a + math.pi) % (2 * math.pi) - math.pi
