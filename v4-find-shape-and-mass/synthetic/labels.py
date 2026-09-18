"""From a label mask to the labels a YOLO model trains on.

The segmentation camera hands back a mask the size of the picture, where each
pixel holds the label number of the block covering it, or 0. This file turns
that into one outline per visible block, in the text format Ultralytics YOLO
reads:

    <class number> x1 y1 x2 y2 x3 y3 ...

with every x and y divided by the image width and height, so they run from 0
to 1. That one format trains a segmentation model directly, and a detection
model too: Ultralytics takes the box around each outline. An oriented box, if
one is wanted later, can be fitted to the same outline, so nothing has to be
rendered again.

No Gazebo in here, so the tests can check it on masks drawn by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# A block showing fewer pixels than this, because it is far away, cut off by
# the edge of the picture, or hidden behind another block, is not labelled.
# Twenty-odd pixels are not enough to name a shape by, and a label the model
# cannot possibly get right teaches it nothing useful.
MIN_PIXELS = 40
# How far, in pixels, a simplified outline may stray from the true edge of the
# mask. Straight edges lose their thousands of stair-step points and keep
# their corners.
OUTLINE_TOLERANCE = 0.7


@dataclass(frozen=True)
class Instance:
    block: int  # index into the scene's blocks
    class_id: int
    pixels: int
    box: tuple[int, int, int, int]  # x, y, width, height in pixels
    outline: list[tuple[float, float]]  # in pixels


def instances(mask: np.ndarray, class_ids: list[int], label_of) -> list[Instance]:
    """One Instance for each block visible enough to label.

    ``class_ids[i]`` is the class number of block ``i``, and ``label_of(i)``
    the number block ``i`` paints into the mask.
    """
    found = []
    for index, class_id in enumerate(class_ids):
        region = (mask == label_of(index)).astype(np.uint8)
        pixels = int(region.sum())
        if pixels < MIN_PIXELS:
            continue
        found.append(
            Instance(
                block=index,
                class_id=class_id,
                pixels=pixels,
                box=tuple(int(v) for v in cv2.boundingRect(region)),
                outline=outline(region),
            )
        )
    return found


def outline(region: np.ndarray) -> list[tuple[float, float]]:
    """The boundary of the non-zero pixels in ``region`` as one closed list of points.

    A block half hidden behind another can show as two separate pieces. YOLO
    takes one outline per object, so the pieces are joined into one: each is
    stitched onto the outline so far at the two points closest to each other,
    by a seam of zero width that goes out and comes back the same way.
    """
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    pieces = [cv2.approxPolyDP(c, OUTLINE_TOLERANCE, True).reshape(-1, 2) for c in contours]
    pieces = [p for p in pieces if len(p) >= 3]
    pieces.sort(key=lambda p: -cv2.contourArea(p.astype(np.float32)))

    joined = pieces[0]
    for piece in pieces[1:]:
        gaps = np.linalg.norm(joined[:, None, :] - piece[None, :, :], axis=2)
        i, j = np.unravel_index(np.argmin(gaps), gaps.shape)
        loop = np.concatenate([piece[j:], piece[: j + 1]])
        joined = np.concatenate([joined[: i + 1], loop, joined[i:]])
    return [(float(x), float(y)) for x, y in joined]


def yolo_line(instance: Instance, width: int, height: int) -> str:
    points = " ".join(f"{x / width:.6f} {y / height:.6f}" for x, y in instance.outline)
    return f"{instance.class_id} {points}"
