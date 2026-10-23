"""What the model is shown about a push, and what it is asked to predict.

Everything is in the push's own frame: ``along`` is the way the jaw moves,
``across`` is to its left. A push to the north and the same push to the east
are one example rather than two, because the table is the same everywhere. That
also makes a push and its mirror image two examples for the price of one.

The inputs are only what the arm has: what the camera measured of each glass,
and the push being considered. No friction, no tipping rule, no mass. Whether a
push slides a glass, topples it or misses it altogether is for the model to
learn from the pushes it has seen.

**The push has four numbers here and three in problem 3, and the fourth is the
whole difference between the two problems' actions.** Problem 3 hands the examiner
a ``Push`` and the simulator feels its way in: it creeps forward from the touchdown
point until its force sensor finds the glass, and only then pushes the distance
it was asked for. Problem 4 hands over a ``Chunk`` of waypoints, and a chunk
cannot feel. So how far the fingertips travel before they meet the glass --
``reach`` -- is part of the action and has to be chosen, not discovered. The
geometry reference measures it, with a ranging push and a look, and pays arm
seconds for every five millimetres; here it is an input the model has an
opinion about.

That is why problem 3's solution 4's ``features.py`` is written out again
rather than borrowed. Its encoding has no room for ``reach``, and it has a
column this problem cannot fill: the table's one glass kind, which problem 3's
runner is told and problem 4's contract never mentions.

**The outputs are read from two looks and nothing else**, as problem 3's are:
where the pushed glass went, where each neighbour went, and whether anything
went over. The simulator's own record is never read. A look only reaches as far
as the camera does, though, so a glass can be missing from the second look, and
then there is no label for it rather than a label of zero. ``MASKED`` is how an
example says so.
"""

from __future__ import annotations

import math

import numpy as np

import tables
from partners import Push, Seen

import plan

# How many other glasses the model is shown, nearest first. Read off the draw
# rather than written down, so that everyone on the fullest table has a slot
# whatever the draw is changed to. The draw was changed once already, from four
# to seven glasses down to three to five, and a model whose widest table was
# narrower than the draw's would quietly stop seeing a glass.
OTHERS = tables.MOST - 1

# Push lengths the search may choose and the model is trained on. The long end
# is problem 3's; the short end is a nudge that barely moves a glass.
TRAVEL = (0.01, 0.10)

# How far across the glass the fingertips may meet it, as a share of its half
# width. Problem 3's figure. A push dead through the middle is one choice out
# of this range rather than the only one on offer.
OFFSET = 0.7

# Distances in the inputs and movements in the outputs are divided by these so
# that the numbers the network sees sit near 1.
PLACE_SCALE = 0.10
MOVE_SCALE = 0.05

# Per other glass: along, across, widest, height, and whether there is a glass
# in this slot at all.
_PER_OTHER = 5

# The pushed glass's height, widest width and foot; then the push: how far
# across the glass the jaw meets it, how far it pushes, and how far it reaches
# in before it expects to touch.
_TARGET, _PUSH = 3, 3
INPUTS = _TARGET + _PUSH + OTHERS * _PER_OTHER

# The pushed glass's movement, then each other glass's, then one yes-or-no:
# something on the table went over.
MOVES = 2 + 2 * OTHERS
OUTPUTS = MOVES + 1
TOPPLED = OUTPUTS - 1

# A label that was never measured, in a mask row. Nothing is learned from it.
MASKED = 0.0


def frame(heading: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors along the push and to its left, one row per heading."""
    along = np.stack([np.cos(heading), np.sin(heading)], -1)
    return along, np.stack([-along[..., 1], along[..., 0]], -1)


def others_of(seen: list[Seen], target: Seen) -> list[Seen]:
    """The other glasses on the table, nearest first.

    Nearest first, and cut at ``OTHERS``, so that the slot a glass lands in
    means something: slot 0 is always the neighbour most likely to be hit.
    """
    rest = [glass for glass in seen if glass.id != target.id]
    return sorted(rest, key=lambda glass: math.dist((glass.x, glass.y), (target.x, target.y)))[:OTHERS]


def encode(seen: list[Seen], target: Seen, heading, offset, travel, reach) -> np.ndarray:
    """One input row per candidate push on ``target``.

    ``heading``, ``offset`` (metres across the glass, left positive),
    ``travel`` and ``reach`` are arrays of the same length, one entry per
    candidate, so that a whole round of the search is encoded at once.
    """
    heading, offset, travel, reach = (
        np.atleast_1d(np.asarray(value, dtype=np.float64)) for value in (heading, offset, travel, reach)
    )
    along, left = frame(heading)
    rows = np.zeros((len(heading), INPUTS), dtype=np.float32)
    rows[:, 0:3] = np.array([target.height, target.widest, target.foot]) / PLACE_SCALE
    rows[:, 3] = offset / PLACE_SCALE
    rows[:, 4] = travel / MOVE_SCALE
    rows[:, 5] = reach / PLACE_SCALE
    middle = np.array([target.x, target.y])
    for slot, other in enumerate(others_of(seen, target)):
        away = np.array([other.x, other.y]) - middle
        column = _TARGET + _PUSH + slot * _PER_OTHER
        rows[:, column] = along @ away / PLACE_SCALE
        rows[:, column + 1] = left @ away / PLACE_SCALE
        rows[:, column + 2] = other.widest / PLACE_SCALE
        rows[:, column + 3] = other.height / PLACE_SCALE
        rows[:, column + 4] = 1.0
    return rows


def present(inputs: np.ndarray) -> np.ndarray:
    """Which other-glass slots hold a glass, one column per slot.

    Read back out of the inputs rather than carried beside them, because the
    answer is already written there and two copies of it could disagree.
    """
    return inputs[:, _TARGET + _PUSH + _PER_OTHER - 1 :: _PER_OTHER]


def mirror(inputs: np.ndarray, outputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The same pushes seen in a mirror: left and right swap, nothing else changes.

    A true example of the physics for free, which doubles a small set. The mask
    needs no mirroring: which labels were measured does not change.
    """
    inputs, outputs = inputs.copy(), outputs.copy()
    inputs[:, 3] *= -1
    inputs[:, _TARGET + _PUSH + 1 :: _PER_OTHER] *= -1
    outputs[:, 1:MOVES:2] *= -1
    return inputs, outputs


def outcome(
    before: list[Seen], after: dict[int, Seen], target: Seen, heading: float, toppled: bool
) -> tuple[np.ndarray, np.ndarray]:
    """The output row for one push that was really made, and which of it was measured.

    ``after`` is the belief once the push has been looked at, by glass number.
    A glass that is not in it was not seen again -- the camera reaches only so
    far -- so its slot is masked rather than filled with a zero movement, which
    would teach the model that a push it could not see did nothing.
    """
    along, left = frame(np.array(heading))
    row = np.zeros(OUTPUTS, dtype=np.float32)
    mask = np.zeros(OUTPUTS, dtype=np.float32)
    for slot, glass in enumerate([target, *others_of(before, target)]):
        moved = after.get(glass.id)
        if moved is None:
            continue
        away = np.array([moved.x - glass.x, moved.y - glass.y])
        row[2 * slot] = along @ away / MOVE_SCALE
        row[2 * slot + 1] = left @ away / MOVE_SCALE
        mask[2 * slot : 2 * slot + 2] = 1.0
    row[TOPPLED] = float(toppled)
    # Always measured. A glass that goes over ends the table, so the runner's
    # own ending says it happened whether or not the camera was pointing at it.
    mask[TOPPLED] = 1.0
    return row, mask


def push_of(target: Seen, heading: float, offset: float, travel: float, aim: tuple[float, float]) -> Push:
    """One candidate push, written the way ``jaw_paths.to_push`` wants it.

    The touchdown point is the geometry reference's own: outside the glass's
    widest part by ``APPROACH_GAP``, and then moved across the push by
    ``offset``. ``aim`` is where the glass is expected to end up, which for
    this solution is the model's own prediction -- so the landing error of a
    run can be read straight out of the record.
    """
    along, left = frame(np.array(heading))
    start = np.array([target.x, target.y]) - (target.widest / 2 + plan.APPROACH_GAP) * along + offset * left
    return Push(
        glass=target.id,
        start=(float(start[0]), float(start[1])),
        heading=float(heading),
        # The jaw's whole travel across the table, which is what a chunk has
        # instead of problem 3's feel-then-push split.
        reach=float(target.widest / 2 + plan.APPROACH_GAP),
        travel=float(travel),
        aim=aim,
    )


def angle_wrap(angle: np.ndarray) -> np.ndarray:
    return (angle + math.pi) % (2 * math.pi) - math.pi
