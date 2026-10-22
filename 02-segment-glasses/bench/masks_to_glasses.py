"""Every instance mask turned into a place on the table and a rough width.

Every solution in this folder calls it, and that is deliberate: a difference
in the scorecard then belongs to how the mask was drawn and never to what was
done with the mask afterwards, so the six differ only where they are meant to
differ.

Each pixel of a mask carries a depth reading, so it becomes a point in the room.
The axis comes from the points at the top of the glass rather than from all of
them: seen from above a rim leans outwards from the point below the camera, so
the middle of the whole cloud sits off to one side of where the glass stands
while the middle of the rim sits over it. The width is twice how far the cloud
reaches from that axis, taken as a percentile so that one stray point at the
edge cannot widen it.

**A mask may claim pixels the camera did not see it at**, which is what the
amodal rung of 06-rf-detr-fine-tuned does on purpose, and those pixels have to
be named before the arithmetic runs
rather than after. The depth reading at such a pixel belongs to whatever stood
in front, so the point it gives sits on that other object. Feeding them in with
the rest drags the fitted centre onto the glass in front, and it was measured:
with exact masks and no model at all, the whole outline gives a place 45 mm out
where the visible pixels give 11 mm. So ``asserted`` says which pixels those are
and their depth readings are left out. Nothing is inferred in their place; what
they are worth is a question about geometry, and a guess about it would be this
module's own private arithmetic.

**A picture may not hold the whole glass.** At the cell's own survey height one
picture does not cover the glass zone, so a glass near the edge of a station's
frame is cut off and the footprint fitted to what is left is part of a
footprint. That is a fact about the view and not about the mask, so ``cut_off``
reports it and nothing here acts on it: every report says whether the mask it
was measured from reaches the edge of the picture, and the same question can be
asked of any mask on its own. What the fact is worth was measured: handed the
renderer's exact masks, one station at a time over 20 held-out spawned scenes,
the kind's own range of footprints refuses 66 of 297 glass sightings, and
**every one of those 66 reaches the frame edge**. So a caller that refuses a
report on its width without reading ``cut_off`` is refusing the view rather than
the mask.

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


def cut_off(mask: np.ndarray) -> bool:
    """Whether a mask reaches the edge of its picture, so the glass may continue outside it.

    An observation about a mask and not a judgement about it. What a report
    whose evidence ran out at the frame edge is worth is the caller's own
    business, and this module's description says what it was measured to be.
    """
    return bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any())


@dataclass(frozen=True)
class Found:
    """One glass as a solution reports it: where it stands, how wide, and how much was in frame."""

    x: float
    y: float
    width: float
    pixels: np.ndarray  # (row, column) of every pixel whose depth reading was used
    cut_off: bool  # its mask reached the picture's edge, so the glass may continue outside it


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
    # Asked of the mask rather than of the pixels left at the end: a pixel the
    # camera got no reading for is still a pixel of this glass running up
    # against the frame edge, and it is dropped from the arithmetic below.
    ran_out = cut_off(mask)
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
    return Found(float(x), float(y), 2.0 * reach, np.stack([rows, columns], 1), ran_out)


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
