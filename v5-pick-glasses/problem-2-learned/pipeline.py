"""Problem 2, run with the three learned parts.

    overhead picture --TopNet--> each glass: where it stands, how wide
    each glass       --geometry veto, then Ranker--> where to stand the camera
    side picture     --SideNet--> height, and width at 16 fractions of it

A glass with no allowed place, or whose best place the ranker doubts, is
reported rather than measured: that is the handover to problem 3.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from work_cell.glasses.profile import Profile

import models
from models import SHRINK, SMALL, VOTE_SCALE
from render import Picture, to_world
from scoring import FRACTIONS
from viewpoints import Seen, allowed, angles, features

# How many pixels have to vote for one middle before it counts as a glass.
# A glass from above covers a few hundred pixels at half size; a stray patch
# of wrong votes covers a handful.
MIN_VOTES = 30

# How far apart, in half-size pixels, two middles have to be to be two
# glasses, and how far a vote may land from a middle and still count for it.
MIDDLE_RADIUS = 8

# Height band at the top of a glass whose points give its middle.
RIM_BAND = 0.008

# Below this, the ranker's best place is not worth the move.
MIN_SCORE = 0.5


@dataclass(frozen=True)
class Found:
    seen: Seen
    pixels: np.ndarray  # (row, column) at full size, one per half-size pixel


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


def gather(picture: Picture, votes: Votes) -> list[Found]:
    """One glass per middle, from the pixels that voted for it."""
    rows, columns = votes.rows, votes.columns
    found = []
    for middle in votes.middles:
        mine = np.linalg.norm(votes.landed - middle, axis=1) < MIDDLE_RADIUS
        if mine.sum() < MIN_VOTES:
            continue
        pixels = np.stack([rows[mine], columns[mine]], 1) * SHRINK
        points = to_world(picture, pixels[:, 0], pixels[:, 1])
        points = points[np.isfinite(points).all(1)]
        top = points[points[:, 2] >= points[:, 2].max() - RIM_BAND]
        x, y = top[:, :2].mean(0)
        radius = float(np.percentile(np.linalg.norm(points[:, :2] - [x, y], axis=1), 95))
        found.append(Found(Seen(float(x), float(y), radius), pixels))
    return found


def find_glasses(picture: Picture, top_net) -> list[Found]:
    """TopNet's votes, gathered into one glass per middle."""
    return gather(picture, cast_votes(picture, top_net))


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
