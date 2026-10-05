"""Step 1: find each glass from one overhead depth picture.

Every pixel that stands above the table becomes a point in the room. The
points are then grouped where they stand on the table, not where they fall in
the picture. Two glasses can overlap in a picture when the camera is in line
with both; on the table they are plainly apart.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from work_cell.glasses.detect import standing_on_the_table
from work_cell.table.layout import TABLE_TOP_Z

from render import LENS, TALLEST_GLASS, Picture, to_world

# The table is cut into squares this size, and a square with any point in it
# is marked. Much finer than the gap between two glasses.
CELL = 0.005

# Marked squares closer than this are one group. Glasses stand 150 mm apart,
# so this cannot join two; it only closes gaps inside one glass.
GROUPING = 0.025

# A group with fewer points than this is noise, not a glass.
MIN_POINTS = 100

# The top of a glass: points within this of its highest one. Their middle is
# the glass's axis, whichever way the camera saw it from.
RIM_BAND = 0.008


@dataclass(frozen=True)
class Seen:
    """A glass as the arm knows it after the overhead picture."""

    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Found:
    seen: Seen
    pixels: np.ndarray  # (row, column) of every pixel in this glass


def find_glasses(picture: Picture) -> list[Found]:
    standing = standing_on_the_table(
        picture.depth, LENS, picture.camera_to_world, TABLE_TOP_Z, tallest=TALLEST_GLASS
    )
    rows, columns = np.nonzero(standing)
    points = to_world(picture, rows, columns)

    # Mark the squares of table under the points, join marks closer than
    # GROUPING, and number the groups.
    corner = points[:, :2].min(0)
    square = np.floor((points[:, :2] - corner) / CELL).astype(int)
    marked = np.zeros(square.max(0) + 1, dtype=np.uint8)
    marked[square[:, 0], square[:, 1]] = 1
    reach = int(round(GROUPING / CELL))
    joined = cv2.dilate(marked, np.ones((reach, reach), np.uint8))
    _, groups = cv2.connectedComponents(joined, connectivity=8)
    group = groups[square[:, 0], square[:, 1]]

    found = []
    for label in np.unique(group):
        mine = group == label
        if mine.sum() < MIN_POINTS:
            continue
        cloud = points[mine]
        top = cloud[cloud[:, 2] >= cloud[:, 2].max() - RIM_BAND]
        x, y = top[:, :2].mean(0)
        # The widest the glass gets, seen from above. A percentile rather than
        # the maximum, so one stray point at the edge does not widen it.
        radius = float(np.percentile(np.linalg.norm(cloud[:, :2] - [x, y], axis=1), 95))
        found.append(Found(Seen(float(x), float(y), radius), np.stack([rows[mine], columns[mine]], 1)))
    return found
