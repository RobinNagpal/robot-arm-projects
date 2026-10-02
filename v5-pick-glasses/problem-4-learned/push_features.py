"""What the push model is shown, and what it is asked to predict.

Problem 3's features (problem-3-learned/features.py) with one change: the kind
belongs to each glass, not to the table. Problem 3's tables had one kind, so
it was given once. Here every glass, pushed or not, carries one of five: the
four kinds, or NOT_MEASURED for a glass nobody has photographed from the side
yet. A glass not measured has no foot either, so its foot goes in as zero.

Everything is in the push's own frame: ``along`` is the way the jaw moves,
``across`` is to its left. The outputs are problem 3's, unchanged.
"""

from __future__ import annotations

import math

import numpy as np

from bench import KINDS

# The fifth kind: not photographed from the side yet.
NOT_MEASURED = "not_measured"
LABELS = (*KINDS, NOT_MEASURED)

# The jaw, the push lengths and the frame are problem 3's.
STANDOFF = 0.02
FEEL_PAST = 0.01
TRAVEL = (0.01, 0.10)
OFFSET = 0.7
OTHERS = 5
PLACE_SCALE = 0.10
MOVE_SCALE = 0.05

# Per other glass: along, across, widest, height, there or not, then its kind.
_PER_OTHER = 5 + len(LABELS)
# Pushed glass: its kind, height, widest, foot; then the push's offset and travel.
_TARGET = len(LABELS) + 3 + 2
INPUTS = _TARGET + OTHERS * _PER_OTHER
OUTPUTS = 2 + 2 * OTHERS + 2
TOPPLED, BLOCKED = OUTPUTS - 2, OUTPUTS - 1


def frame(heading: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    along = np.stack([np.cos(heading), np.sin(heading)], -1)
    return along, np.stack([-along[..., 1], along[..., 0]], -1)


def others_of(seen: list, target) -> list:
    rest = [s for s in seen if s.id != target.id]
    return sorted(rest, key=lambda s: math.dist((s.x, s.y), (target.x, target.y)))[:OTHERS]


def label(kinds: dict[int, str], glass) -> str:
    return kinds.get(glass.id) or NOT_MEASURED


def encode(seen: list, target, kinds: dict[int, str], heading, offset, travel) -> np.ndarray:
    """One input row per candidate push on ``target``.

    ``kinds`` maps a glass's id to its measured kind; a glass missing from it
    is NOT_MEASURED.
    """
    heading, offset, travel = (
        np.atleast_1d(np.asarray(v, dtype=np.float64)) for v in (heading, offset, travel)
    )
    along, left = frame(heading)
    rows = np.zeros((len(heading), INPUTS), dtype=np.float32)
    mine = label(kinds, target)
    rows[:, LABELS.index(mine)] = 1.0
    k = len(LABELS)
    foot = target.foot if mine != NOT_MEASURED else 0.0
    rows[:, k : k + 3] = np.array([target.height, target.widest, foot]) / PLACE_SCALE
    rows[:, k + 3] = offset / PLACE_SCALE
    rows[:, k + 4] = travel / MOVE_SCALE
    middle = np.array([target.x, target.y])
    for slot, other in enumerate(others_of(seen, target)):
        d = np.array([other.x, other.y]) - middle
        column = _TARGET + slot * _PER_OTHER
        rows[:, column] = along @ d / PLACE_SCALE
        rows[:, column + 1] = left @ d / PLACE_SCALE
        rows[:, column + 2] = other.widest / PLACE_SCALE
        rows[:, column + 3] = other.height / PLACE_SCALE
        rows[:, column + 4] = 1.0
        rows[:, column + 5 + LABELS.index(label(kinds, other))] = 1.0
    return rows


def present(inputs) -> np.ndarray:
    """The "there or not" column of each other glass."""
    return inputs[:, _TARGET + 4 :: _PER_OTHER]


def mirror(inputs: np.ndarray, outputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The same pushes seen in a mirror: left and right swap, nothing else changes."""
    inputs, outputs = inputs.copy(), outputs.copy()
    inputs[:, len(LABELS) + 3] *= -1
    inputs[:, _TARGET + 1 :: _PER_OTHER] *= -1
    outputs[:, 1 : 2 + 2 * OTHERS : 2] *= -1
    return inputs, outputs


def outcome(before: list, after: list, target, heading: float, blocked: bool) -> np.ndarray:
    """The output row for one push that was really made, read from two looks."""
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
    along, left = frame(np.array(heading))
    back = target.widest / 2 + STANDOFF
    return tuple(np.array([target.x, target.y]) - back * along + offset * left)


def jaw_reach(target) -> float:
    return target.widest / 2 + STANDOFF + FEEL_PAST


def angle_wrap(a: np.ndarray) -> np.ndarray:
    return (a + math.pi) % (2 * math.pi) - math.pi
