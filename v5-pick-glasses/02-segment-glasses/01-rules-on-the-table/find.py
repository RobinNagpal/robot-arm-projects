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

**The kind of glass decides what a group's width is allowed to be.** A circle is
fitted to each group, and the width it gives is held against the range of
footprints this kind of glass can have, which the cell is told. A group too wide
for one glass of the kind is not one glass, so it is split in two with k-means —
and **the same question is then asked of each part**, so a part still too wide is
split again. The repetition is the point: the bench's crowded family stands
three glasses to a line, so one split into two necessarily leaves a part holding
two. **The fitted width decides only the split.** The width that goes into the
record is the bench's, measured from the pixels handed back.

**A group too narrow for the kind is refused only when the whole of it was in
frame.** At the cell's own survey height one picture does not hold the glass
zone, so a glass near the edge of a station's frame shows part of its footprint
and a circle fitted to that part is small through no fault of the grouping. That
was measured on masks that cannot be improved on: the bench's own exact masks,
one station at a time over 20 held-out spawned scenes, give a footprint outside
the kind's range for 66 of 297 glass sightings, and every one of those 66
reaches the frame edge. So `masks_to_glasses` says whether the mask a report was
measured from reached the picture's edge, and the narrow refusal reads it.

**The wide refusal does not read it**, because the two sides of the range mean
different things here. A frame that cuts a patch short takes dots away, which
makes the circle round it smaller. Over 20 held-out spawned scenes, where the
layout keeps every glass 150 mm from the next, 73 groups holding one glass read
too narrow and every one of them reached the frame edge, against 4 that read too
wide. Over 20 crowded scenes every one of the 72 groups that held more than one
glass read too wide. So a narrow reading is about the view and a wide one is
about the grouping, and the wide one is the merge this check exists to catch.

The document also names a third number from the fit, the residual, as a measure
of how well a circle explains a group's dots. None of the four outcomes it
prescribes uses the residual, so nothing here computes one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from work_cell.glasses.detect import standing_on_the_table
from work_cell.table.layout import TABLE_TOP_Z

import data
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

# How many rounds the split is allowed before it is called settled. It stops
# moving in a handful of rounds from the seeds `halve` starts it at; the cap is
# only there so a tie cannot swap two dots back and forth for ever.
SPLIT_ROUNDS = 20

# The three reasons a group is handed over instead of reported. Fixed strings,
# because the scorecard counts the doubts by reason.
TOO_LITTLE = "a group with too few depth readings to place"
TOO_WIDE = "a group too wide for one glass of this kind, and it did not come apart"
TOO_NARROW = "a group too narrow for any glass of this kind, with the whole of it in frame"


def circle_width(dots: np.ndarray) -> float:
    """How wide the circle through a ring of dots is, in one solve and with no starting guess.

    Written out, the equation of a circle is not linear in its centre and its
    radius. Multiplied out it is: ``x^2 + y^2 = D x + E y + F`` is linear in D, E
    and F, the centre is half of D and E, and the radius comes back at the end.
    So the fit is a least squares solve rather than an iterative search.

    The centre falls out of the same solve and is not returned, because nothing
    here needs it: the place that goes into the record is the bench's, read off
    the mask's own pixels, and the only thing this fit is asked for is a width to
    hold against the kind's range.
    """
    terms = np.column_stack([dots, np.ones(len(dots))])
    solved = np.linalg.lstsq(terms, (dots**2).sum(1), rcond=None)[0]
    x, y = solved[0] / 2.0, solved[1] / 2.0
    return 2.0 * float(np.sqrt(max(solved[2] + x * x + y * y, 0.0)))


def footprint(dots: np.ndarray) -> float:
    """How wide the circle round the patch of table a group of dots marks is.

    Only the dots on the **outside** of the patch are fitted, and not every dot
    in it. A group is a filled disc rather than a ring, and a circle fitted to a
    filled disc of dots comes back about one over the square root of two of the
    disc's own radius: measured here, a straight glass 53 mm across gives 38 mm
    fitted from all of its dots. The convex hull is what the outside of the
    patch is, and over the 289 whole glasses of 20 held-out spawned scenes a
    circle fitted to the hull reads 0.3 mm over the true width at the median.
    """
    return circle_width(cv2.convexHull(dots.astype(np.float32)).reshape(-1, 2).astype(float))


def halve(dots: np.ndarray) -> np.ndarray:
    """Which of two halves each dot belongs to, by k-means with two centres.

    Each dot goes to whichever seed is nearer, each seed moves to the middle of
    the dots it was given, and that repeats until nothing moves.

    The seeds are the two ends of the group's longest direction rather than two
    dots picked at random. Two glasses run together lie along that direction, so
    those two ends are one seed inside each glass, and starting from a rule
    rather than from a draw means the run repeats.
    """
    middle = dots.mean(0)
    along = (dots - middle) @ np.linalg.svd(dots - middle, full_matrices=False)[2][0]
    seeds = dots[[int(along.argmin()), int(along.argmax())]]
    mine = along > 0
    for _ in range(SPLIT_ROUNDS):
        nearer = np.linalg.norm(dots - seeds[1], axis=1) < np.linalg.norm(dots - seeds[0], axis=1)
        # A round that empties a half has nothing to move to, and a round that
        # moves nothing is the end of it.
        if not nearer.any() or nearer.all() or (nearer == mine).all():
            break
        mine = nearer
        seeds = np.stack([dots[~mine].mean(0), dots[mine].mean(0)])
    return mine


def dots_of(picture: Picture, pixels: np.ndarray) -> np.ndarray:
    """Where a report's own pixels stand on the table, with the height dropped."""
    return to_world(picture, pixels[:, 0], pixels[:, 1])[:, :2]


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


def as_glasses(picture: Picture, one: Found, widths: tuple[float, float]) -> list[Found] | None:
    """The glasses one patch of dots holds, or None if the fitted circles cannot say.

    The same rule for a whole group and for a part that came out of a split,
    which is what makes it repeat. A patch whose fitted width the kind allows is
    one glass. A patch wider than the kind allows is more than one, so it is
    split. A patch narrower than the kind allows cannot be helped by splitting,
    because both halves of a footprint are narrower than the footprint, so this
    is as far as the fit goes: it is a glass the picture did not hold all of when
    its pixels reach the frame edge, and a refusal when they do not.
    """
    width = footprint(dots_of(picture, one.pixels))
    if widths[0] <= width <= widths[1]:
        return [one]
    if width > widths[1]:
        return come_apart(picture, one, widths)
    return [one] if one.cut_off else None


def come_apart(picture: Picture, one: Found, widths: tuple[float, float]) -> list[Found] | None:
    """One patch halved with k-means, with the same rule asked again of each half.

    The repetition is what [the
    document](../../docs/02-segment-glasses/solutions/01-rules-on-the-table.md)
    prescribes, and the reason is the arrangements: the bench's crowded family
    stands three glasses to a line, so one split into two necessarily leaves a
    part still holding two. Measured over 20 held-out crowded arrangements,
    stopping after one split finds 17 of 101 glasses and hands 54 groups over,
    and repeating finds 71 and hands 3 over.

    Nothing counts the rounds. Each half has strictly fewer dots than the part it
    came from, so the splitting runs out on its own: on a part the halving will
    not divide, on a half the bench cannot place, or on a part the kind's widths
    settle either way. A group with any part left over is handed over whole,
    because reporting the parts that happened to fit would be claiming to know
    how many glasses it holds, and the fit has just said it cannot.

    Each half is measured by the bench like any other mask, so the fitted circles
    leave this file and only the split they decided reaches the record.
    """
    mine = halve(dots_of(picture, one.pixels))
    if mine.all() or not mine.any():
        return None
    parts: list[Found] = []
    for half in (~mine, mine):
        side = np.zeros(picture.depth.shape, dtype=bool)
        side[one.pixels[half, 0], one.pixels[half, 1]] = True
        measured = masks_to_glasses.one_glass(picture, side)
        if measured is None:
            return None
        got = as_glasses(picture, measured, widths)
        if got is None:
            return None
        parts.extend(got)
    return parts


@dataclass(frozen=True)
class Finder:
    """The written rules, ready to be handed pictures. It holds no fitted state."""

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The glasses in one picture, and what could not be settled.

        ``kind`` fixes the range of footprints a glass here can have, which is a
        limit on the kind and never the size of any one glass.

        The groups are disjoint patches of table, but the parts of a split are
        not: a group cut into several can leave two parts over one glass. Those
        are collapsed by ``masks_to_glasses.one_per_place`` in
        ``marking.survey``, which is where the stations of a survey are brought
        together too, and the scorecard counts what it collapses as a split.
        Doing it here as well would only take the choice of which report keeps a
        place away from the bench, which orders them by the station that saw the
        glass squarest.
        """
        widths = data.widths(kind)
        found: list[Found] = []
        doubts: list[str] = []
        for mask in glass_masks(picture):
            one = masks_to_glasses.one_glass(picture, mask)
            if one is None:
                doubts.append(TOO_LITTLE)
                continue
            parts = as_glasses(picture, one, widths)
            if parts is not None:
                found.extend(parts)
            else:
                # Which way the group's own width failed, which is what the
                # scorecard counts the doubts by. A part inside it may have
                # failed the other way; the group is handed over whole anyway.
                wide = footprint(dots_of(picture, one.pixels)) > widths[1]
                doubts.append(TOO_WIDE if wide else TOO_NARROW)
        return found, doubts


def load(save: Path | None = None) -> Finder:
    """A finder. ``save`` is accepted for the shared interface and there is nothing in it."""
    return Finder()
