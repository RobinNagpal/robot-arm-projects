"""Solution 1: the glasses in one picture, by grouping dots on the table.

Every pixel that stands above the table becomes a point in the room. The
points are then grouped where they stand on the table, not where they fall in
the picture. Two glasses can overlap in a picture when the camera is in line
with both; on the table they are plainly apart.

**What this hands back is a boolean mask per glass**, and nothing else. Turning
a mask into a place and a width is `masks_to_glasses`, which is the bench's
arithmetic and the same for all six solutions, so a difference in the scorecard
belongs to how the mask was drawn. The only number this file contributes is
which pixels fed which group.

**The masks are a consequence of the grouping rather than a drawn outline.** No
step here ever asks where a glass ends: one step decides which pixels stand
above the table and a quite different step decides which of those belong
together, so the edge of every mask was fixed before the grouping began. What
follows is in [the document](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md):
the masks lose the band at the base of a glass, where the wall is too close to
the table to be told from it, and they almost never claim a pixel that is not
glass.

**The kind of glass is handed in and is not used.** The document prescribes a
check here: fit a circle to a group, and a group too wide to be one glass of
this kind is split in two rather than reported. The split is not built, and a
refusal without it was measured and thrown out: the bench's own exact masks,
one station at a time, give a footprint outside the kind's range for 66 of 297
glass sightings, because a glass clipped at the edge of one station's frame
shows only part of its footprint. So a refusal on width at one station would
throw away correct answers, and the station that saw the glass squarely is
chosen afterwards by `marking.survey`, where a solution has no say. The check
belongs after the survey rather than inside one picture, and nothing here
pretends to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from work_cell.glasses.detect import standing_on_the_table
from work_cell.table.layout import TABLE_TOP_Z

import masks_to_glasses
from masks_to_glasses import Found
from render import LENS, TALLEST_GLASS, Picture, to_world

# The table is cut into squares this size, and a square with any point in it
# is marked. Much finer than the gap between two glasses.
CELL = 0.005

# Marked squares closer than this are one group. The cell's own layout stands
# glasses 150 mm apart, so this cannot join two of those; it only closes gaps
# inside one glass. The bench's crowded arrangements stand them closer than the
# layout allows on purpose, and there it can join two, which is a measurement
# of the rule rather than a setting to tune away.
GROUPING = 0.025

# A group with fewer points than this is noise, not a glass.
MIN_POINTS = 100

# The one reason a group is handed over instead of reported. A fixed string,
# because the scorecard counts the doubts by reason.
TOO_LITTLE = "a group with too few depth readings to place"


def glass_masks(picture: Picture) -> list[np.ndarray]:
    """One boolean mask per group of dots, true on the pixels that fed the group.

    The grouping happens on the table: the points are dropped straight down,
    the squares of table under them are marked, marks closer than ``GROUPING``
    are joined, and each joined region is one group.
    """
    standing = standing_on_the_table(
        picture.depth, LENS, picture.camera_to_world, TABLE_TOP_Z, tallest=TALLEST_GLASS
    )
    rows, columns = np.nonzero(standing)
    if rows.size == 0:
        return []
    points = to_world(picture, rows, columns)

    corner = points[:, :2].min(0)
    square = np.floor((points[:, :2] - corner) / CELL).astype(int)
    marked = np.zeros(square.max(0) + 1, dtype=np.uint8)
    marked[square[:, 0], square[:, 1]] = 1
    reach = int(round(GROUPING / CELL))
    joined = cv2.dilate(marked, np.ones((reach, reach), np.uint8))
    _, groups = cv2.connectedComponents(joined, connectivity=8)
    group = groups[square[:, 0], square[:, 1]]

    masks = []
    for label in np.unique(group):
        mine = group == label
        if mine.sum() < MIN_POINTS:
            continue
        mask = np.zeros(picture.depth.shape, dtype=bool)
        mask[rows[mine], columns[mine]] = True
        masks.append(mask)
    return masks


@dataclass(frozen=True)
class Finder:
    """The written rules, ready to be handed pictures. It holds no fitted state."""

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The glasses in one picture, and what could not be settled.

        ``kind`` is accepted because every solution here is handed it, and is
        unused for the reason this module's own description gives.

        The groups are disjoint patches of table, so no two of them are reports
        of one place and there is nothing to collapse here. Bringing the
        stations of a survey together is ``marking.survey``'s job.
        """
        found: list[Found] = []
        doubts: list[str] = []
        for mask in glass_masks(picture):
            one = masks_to_glasses.one_glass(picture, mask)
            if one is None:
                doubts.append(TOO_LITTLE)
            else:
                found.append(one)
        return found, doubts


def load(save: Path | None = None) -> Finder:
    """A finder. ``save`` is accepted for the shared interface and there is nothing in it."""
    return Finder()
