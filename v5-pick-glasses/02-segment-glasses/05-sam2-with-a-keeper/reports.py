"""The arithmetic that has the last word, and it is the same on both rungs.

Both rungs of this solution end here. Something decides that a region is a
glass — on the lower rung the keeper fitted in this cell, on the upper rung the
borrowed weights' own idea of a word — and then two pieces of arithmetic nobody
fitted decide whether that report is believable.

**The width check.** The kind of glass on the table is known, and so is the
range of footprints that kind can have. A measured width outside that range is
not one glass of this kind, whatever named it one, and the report becomes a
doubt carrying its reason instead of a glass.

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
TOO_WIDE = "kept, but its width is outside what this kind can be"


def legal(found: Found, widths: tuple[float, float]) -> bool:
    """Whether one glass of this kind could really have been measured this wide."""
    low, high = widths
    return low <= found.width <= high


def believable(picture, masks: list[np.ndarray], kind: str) -> tuple[list[Found], list[str]]:
    """Masks into reports: the place and width of each, then both checks.

    A mask the shared arithmetic cannot fit a footprint to is not a report at
    all, because there is nothing to report about it. A mask it can fit but
    whose width this kind cannot have is a doubt, which is a result rather than
    a failure.

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
            doubts.append(TOO_WIDE)
    return masks_to_glasses.one_per_place(kept, widths[0]), doubts
