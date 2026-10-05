"""Solution 2: one picture through TopNet, and its votes gathered into masks.

    one station's picture --TopNet--> per pixel: glass or not, and the way to
                                      the middle of its own glass
    the votes             --tally--> one pile per glass
    the pixels of a pile  --the bench--> a place on the table and a width

At every pixel it calls glass, the network predicts a short arrow pointing at
the middle of that pixel's own glass. Adding the arrow to the pixel's own place
is a vote, one glass's pixels all vote for the same middle, so counting glasses
is counting piles and splitting a blob is asking which pile each of its pixels
voted into. Nothing has to find a boundary, so nothing can get a boundary wrong.

**What this hands back is a boolean mask per glass**, and nothing else. Turning
a mask into a place and a width is `masks_to_glasses`, which is the bench's
arithmetic and the same for all six solutions, so a difference in the scorecard
belongs to how the mask was drawn.

**The kind of glass is handed in and is not used.** The document prescribes a
check here: fit a circle to the pixels of a pile, and refuse a pile whose width
falls outside the range this kind of glass can be. It is not built, and a
refusal was measured and thrown out: the bench's own exact masks, one station at
a time, give a footprint outside the kind's range for 66 of 297 glass sightings,
because a glass clipped at the edge of one station's frame shows only part of
its footprint. The station that saw a glass squarely is chosen afterwards by
`marking.survey`, where a solution has no say, so the check belongs after the
survey rather than inside one picture.

**`rank_views` and `measure` are not part of problem 2.** The bench stops at a
mask, a place and a width; choosing a viewpoint and reading a glass's profile
from the side are the steps after that, and nothing in `run.py` calls either.
They are kept because
`docs/problem-4/solutions/learned/08-the-learned-pipelines-retrained.md` names
this folder's Ranker and SideNet as two of the parts its pipeline reuses.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import models
import numpy as np
from models import SHRINK, SMALL, VOTE_SCALE
from viewpoints import Seen, allowed, angles, features
from work_cell.glasses.profile import Profile

import masks_to_glasses
from masks_to_glasses import Found
from render import Picture
from scoring import FRACTIONS

# How many pixels have to vote for one middle before it counts as a glass.
# A glass from above covers a few hundred pixels at half size; a stray patch
# of wrong votes covers a handful.
MIN_VOTES = 30

# How far apart, in half-size pixels, two middles have to be to be two
# glasses, and how far a vote may land from a middle and still count for it.
MIDDLE_RADIUS = 8

# Below this, the ranker's best place is not worth the move.
MIN_SCORE = 0.5

# The two reasons a pile is handed over instead of reported. Fixed strings,
# because the scorecard counts the doubts by reason.
TOO_FEW_VOTES = "a pile built from too few votes to be a whole glass"
TOO_LITTLE = "a pile with too few depth readings to place"


# The offsets of one half-size pixel's block, as (row, column) pairs.
_STEPS = np.arange(SHRINK)
_BLOCK = np.stack(np.meshgrid(_STEPS, _STEPS, indexing="ij"), -1).reshape(-1, 2)


@dataclass(frozen=True)
class Votes:
    """TopNet's answer for one picture, and where its votes landed.

    Kept apart from the glasses made out of it, so that show.py can draw it.
    """

    out: np.ndarray  # three half-size pictures: glass score, offset across, offset down
    rows: np.ndarray  # the pixels TopNet called glass
    columns: np.ndarray
    landed: np.ndarray  # the (row, column) each of those pixels votes for
    tally: np.ndarray  # votes landing near each pixel
    middles: list[tuple[int, int]]  # (row, column), most votes first


def cast_votes(picture: Picture, top_net) -> Votes:
    """Run TopNet, let each glass pixel vote for a middle, and pick the middles."""
    out = models.predict(top_net, models.top_input(picture)[None])[0]
    rows, columns = np.nonzero(out[0] > 0)
    landed = np.stack(
        [rows + out[2][rows, columns] * VOTE_SCALE, columns + out[1][rows, columns] * VOTE_SCALE], 1
    )

    tally = np.zeros(SMALL, dtype=np.float32)
    whole = np.round(landed).astype(int)
    inside = (whole[:, 0] >= 0) & (whole[:, 0] < SMALL[0]) & (whole[:, 1] >= 0) & (whole[:, 1] < SMALL[1])
    np.add.at(tally, (whole[inside, 0], whole[inside, 1]), 1.0)
    tally = cv2.boxFilter(tally, -1, (5, 5), normalize=False)

    # Picking a middle rubs out the votes round it, so that is done on a copy
    # and the tally is kept as it was counted.
    middles, left = [], tally.copy()
    while left.max() >= MIN_VOTES:
        row, column = np.unravel_index(int(left.argmax()), SMALL)
        middles.append((int(row), int(column)))
        cv2.circle(left, (int(column), int(row)), 2 * MIDDLE_RADIUS, 0.0, -1)
    return Votes(out, rows, columns, landed, tally, middles)


def pile_mask(picture: Picture, votes: Votes, middle) -> np.ndarray | None:
    """The pixels that voted for one middle, as a boolean mask, or None if too few did.

    The net works at half size, so each pixel it calls glass stands for a whole
    block of the picture, and the block is what the mask means. The block is
    therefore what the mask claims. Handing back only the one sampled pixel of
    each block would describe the same outline while appearing to cover a
    quarter of the glass, and the bench measures how much of a glass a mask
    covered.
    """
    mine = np.linalg.norm(votes.landed - middle, axis=1) < MIDDLE_RADIUS
    if mine.sum() < MIN_VOTES:
        return None
    corners = np.stack([votes.rows[mine], votes.columns[mine]], 1) * SHRINK
    pixels = (corners[:, None, :] + _BLOCK[None, :, :]).reshape(-1, 2)
    pixels = np.clip(pixels, 0, np.array(picture.depth.shape) - 1)
    mask = np.zeros(picture.depth.shape, dtype=bool)
    mask[pixels[:, 0], pixels[:, 1]] = True
    return mask


def gather(picture: Picture, votes: Votes) -> tuple[list[Found], list[str]]:
    """One glass per middle, from the pixels that voted for it, and what was doubted.

    A pile built from a small fraction of the votes a whole glass should cast is
    doubtful however tight it looks: a glass reduced to a crescent down one edge
    votes only from that crescent, and those votes agree closely with each other
    while being wrong together. So a short pile is reported rather than kept.
    """
    found: list[Found] = []
    doubts: list[str] = []
    for middle in votes.middles:
        mask = pile_mask(picture, votes, middle)
        if mask is None:
            doubts.append(TOO_FEW_VOTES)
            continue
        one = masks_to_glasses.one_glass(picture, mask)
        if one is None:
            doubts.append(TOO_LITTLE)
        else:
            found.append(one)
    return found, doubts


def find_glasses(picture: Picture, top_net) -> tuple[list[Found], list[str]]:
    """TopNet's votes, gathered into one glass per middle, and what was doubted."""
    return gather(picture, cast_votes(picture, top_net))


@dataclass(frozen=True)
class Finder:
    """TopNet, ready to be handed pictures."""

    top_net: object  # a models.TopNet holding the fitted weights

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The glasses in one picture, and what could not be settled.

        ``kind`` is accepted because every solution here is handed it, and is
        unused for the reason this module's own description gives.
        """
        return find_glasses(picture, self.top_net)


def rank_views(target: Seen, others: list[Seen], ranker) -> list[tuple[float, float]]:
    """(score, angle) for every allowed place, best first."""
    options = [angle for angle in angles() if allowed(target, others, angle)]
    if not options:
        return []
    scores = 1 / (
        1 + np.exp(-models.predict(ranker, np.stack([features(target, others, a) for a in options])))
    )
    return sorted(zip(scores.tolist(), options, strict=True), reverse=True)


def measure(picture: Picture, side_net) -> Profile:
    """SideNet's reading of the glass in the middle of a side picture."""
    height, widths = models.side_output(models.predict(side_net, models.side_input(picture)[None])[0])
    return Profile(FRACTIONS * height, widths)
