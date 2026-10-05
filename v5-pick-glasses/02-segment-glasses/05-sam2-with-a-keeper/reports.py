"""The arithmetic that has the last word, and it is the same on both rungs.

Both rungs of this solution end here. Something decides that a region is a
glass — on the lower rung the keeper fitted in this cell, on the upper rung the
borrowed weights' own idea of a word — and then two pieces of arithmetic nobody
fitted decide whether that report is believable.

**The width check.** The kind of glass on the table is known, and so is the
range of footprints that kind can have. A measured width outside that range is
not one glass of this kind, whatever named it one, and the report becomes a
doubt carrying its reason instead of a glass.

**Unless the picture ran out before the glass did.** At the cell's own survey
height one picture does not hold the glass zone, so a glass near the edge of a
station's frame shows part of its footprint and the width measured off it is
part of a width. Refusing on that is refusing the view rather than the region,
and it was measured on masks nothing can improve on: the bench's own exact
masks, one station at a time over 20 held-out spawned scenes, give a footprint
outside the kind's range for 66 of 297 glass sightings, and every one of those
66 reaches the frame edge. So a report whose pixels reach that edge is not
refused on its width. What answers it instead is the survey: three overlapping
stations, and `marking.survey` keeps the report from the station the glass stood
nearest the middle of.

**One report per place.** Two glasses of one kind standing side by side have
their centres at least the narrowest width that kind allows apart, so a report
landing nearer than that to one already kept is the same glass arriving twice.
That is geometry the cell guarantees rather than a number somebody tuned, and it
is what holds the count honest when a mouth and the glass below it are both
kept.

Nothing here is fitted, and nothing here knows how large any one glass is: the
range belongs to the kind, which the cell is told.
"""

from __future__ import annotations

import numpy as np

import data
import masks_to_glasses
from masks_to_glasses import Found

# Said the same way on both rungs, so the two scorecards count the same thing.
NO_SUCH_WIDTH = "its width is outside what this kind can be, with the whole of it in frame"


def legal(found: Found, widths: tuple[float, float]) -> bool:
    """Whether this report may be a glass of this kind as far as its width goes.

    True when the width is one the kind allows, and true as well when the
    report's pixels reach the edge of the picture, for the reason this module's
    own description gives: the width then belongs to the part of the glass that
    was in frame and says nothing about the glass.
    """
    low, high = widths
    return found.cut_off or low <= found.width <= high


def believable(picture, masks: list[np.ndarray], kind: str) -> tuple[list[Found], list[str]]:
    """Masks into reports: the place and width of each, then both checks.

    A mask the shared arithmetic cannot fit a footprint to is not a report at
    all, because there is nothing to report about it. A mask it can fit, whose
    width this kind cannot have and whose whole of it was in frame, is a doubt,
    which is a result rather than a failure.

    The order of ``masks`` decides which of two reports at one place survives,
    so a caller that wants its surest report to win sorts before calling.
    """
    widths = data.widths(kind)
    kept: list[Found] = []
    doubts: list[str] = []
    for mask in masks:
        found = masks_to_glasses.one_glass(picture, mask)
        if found is None:
            continue
        if legal(found, widths):
            kept.append(found)
        else:
            doubts.append(NO_SUCH_WIDTH)
    return masks_to_glasses.one_per_place(kept, widths[0]), doubts
