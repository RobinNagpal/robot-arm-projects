"""Every instance mask turned into a place on the table and a rough width.

This is the same arithmetic as ../problem-2-programmed/find.py and
../problem-2-learned/pipeline.py, and all three solutions here call it. That is
deliberate twice over. Between the folders it means a difference in the
scorecard belongs to how the mask was drawn and not to what was done with the
mask afterwards. Inside this folder it means solutions 8, 9 and 10 differ only
where they are meant to differ.

Each pixel of a mask carries a depth reading, so it becomes a point in the room.
The axis comes from the points at the top of the glass rather than from all of
them: seen from above a rim leans outwards from the point below the camera, so
the middle of the whole cloud sits off to one side of where the glass stands
while the middle of the rim sits over it. The width is twice how far the cloud
reaches from that axis, taken as a percentile so that one stray point at the
edge cannot widen it.

**A mask may claim pixels the camera did not see it at**, which is what solution
10 does on purpose, and those pixels have to be named before the arithmetic runs
rather than after. The depth reading at such a pixel belongs to whatever stood
in front, so the point it gives sits on that other object. Feeding them in with
the rest drags the fitted centre onto the glass in front, and it was measured:
with exact masks and no model at all, the whole outline gives a place 45 mm out
where the visible pixels give 11 mm. So ``asserted`` says which pixels those are
and their depth readings are left out. Nothing is inferred in their place; what
they are worth is a question about geometry, and a guess about it would be this
module's own private arithmetic.

Nothing here knows how large a glass is, and nothing here rejects anything. A
width that no glass of the kind could have is for the caller to refuse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from render import Picture, to_world

# The top of a glass: points within this of the highest one in the mask. Their
# middle is the glass's axis, whichever side the camera saw it from.
RIM_BAND = 0.008

# How far out the cloud is taken to reach, as a percentile of the distances
# from the axis, rather than the largest of them.
SPREAD = 95

# A mask with fewer usable pixels than this is not enough to fit anything to.
MIN_PIXELS = 100


@dataclass(frozen=True)
class Found:
    """One glass as a solution reports it: where it stands, and how wide."""

    x: float
    y: float
    width: float
    pixels: np.ndarray  # (row, column) of every pixel whose depth reading was used


def one_glass(picture: Picture, mask: np.ndarray, asserted: np.ndarray | None = None) -> Found | None:
    """The place and width of the glass a mask covers, or None if there is too little of it.

    ``mask`` is one boolean picture, true on the pixels of this glass.
    ``asserted`` is the pixels of it the camera did not see this glass at, whose
    depth readings therefore belong to something else.
    """
    if asserted is not None:
        mask = mask & ~asserted
    rows, columns = np.nonzero(mask)
    if rows.size == 0:
        return None
    points = to_world(picture, rows, columns)

    # A pixel where the ray hit nothing has no point in the room, so it cannot
    # say anything about where the glass stands.
    usable = np.isfinite(points).all(1)
    rows, columns, points = rows[usable], columns[usable], points[usable]
    if rows.size < MIN_PIXELS:
        return None

    top = points[points[:, 2] >= points[:, 2].max() - RIM_BAND]
    x, y = top[:, :2].mean(0)
    reach = float(np.percentile(np.linalg.norm(points[:, :2] - [x, y], axis=1), SPREAD))
    return Found(float(x), float(y), 2.0 * reach, np.stack([rows, columns], 1))


def to_glasses(picture: Picture, masks: list[np.ndarray]) -> list[Found]:
    """The same, for a whole picture's worth of masks. Masks too small to use are dropped."""
    found = [one_glass(picture, mask) for mask in masks]
    return [item for item in found if item is not None]


def one_per_place(found: list[Found], narrowest: float) -> list[Found]:
    """One report per place on the table, keeping the first of any that share one.

    Two glasses of one kind standing side by side have their centres at least the
    narrowest of them apart, so a second report closer than that is the same
    glass arriving twice. It arrives twice for two reasons here. Within one
    picture, a glass seen from above is mostly its own mouth, and the mouth is a
    region in its own right whose footprint is the glass's footprint: legal
    width, round, and in the right place. Across the stations of a survey, the
    same glass is in more than one picture by design, and counting it once per
    picture would be counting it three times.

    ``narrowest`` is a limit on the kind of glass, not the size of any one of
    them. The order matters: the first report of a place is the one kept, so a
    caller that wants its surest or best-placed report to win sorts first.
    """
    taken: list[Found] = []
    for one in found:
        if not any(math.dist((one.x, one.y), (other.x, other.y)) < narrowest for other in taken):
            taken.append(one)
    return taken
