"""The bench's scenes, written out as the dataset the RF-DETR package trains from.

The package reads a Roboflow-style COCO folder: a ``train`` and a ``valid``
directory, each holding the pictures and one ``_annotations.coco.json`` beside
them. So this module's whole job is to turn ``data.Example`` into that, once,
before a fine-tune starts.

**One class.** Every annotation is category ``glass``, because the kind on the
table is already known and the model is being asked only whether it has found a
glass and which pixels it is.

**Two targets, one line apart.** ``amodal`` chooses which mask is written: the
pixels the camera can see of a glass, or the glass's whole silhouette. The bench
renders the second by drawing the scene again with the other glasses taken away,
in ``data.Sight.whole``, so the shape a hidden part would have is known exactly
rather than guessed. **That is only true in a simulator.** On real photographs
an amodal label has to be drawn by a person through a place nobody can see, two
careful annotators disagree, and there is no way to settle who was right. Here
it costs one more render and no judgement at all, which is the single reason the
second rung is cheap in this project.

**A mask is written as polygons**, which is what the package's COCO reader
scales when it resizes a picture; its run-length form cannot be scaled and would
be silently wrong at any resolution but the one it was written at.

**A glass with no pixels is not written.** With the visible target that is a
glass something hides completely, and with the whole-silhouette target it is a
glass outside this station's frame. Either way there is nothing to learn from
and an empty annotation would only teach the model to report nothing.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

import cv2
import numpy as np

import data

# The one class, and the id it is written under. One entry, so a query's class
# answer is a choice between "glass" and "nothing".
CLASS = "glass"
CLASS_ID = 1

# A contour shorter than this is a few stray pixels rather than an outline, and
# COCO cannot hold a polygon of fewer than three corners anyway.
SHORTEST_OUTLINE = 3

# How finely a contour is followed, in pixels. The package turns the polygon
# back into a mask before training on it, so this is how much of the outline is
# allowed to be lost on the way through the file.
OUTLINE_STEP = 1.0


def outlines(mask: np.ndarray) -> list[list[float]]:
    """One mask as COCO polygons: a flat [x, y, x, y, ...] per piece of it."""
    found, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []
    for contour in found:
        eased = cv2.approxPolyDP(contour, OUTLINE_STEP, True).reshape(-1, 2)
        if len(eased) >= SHORTEST_OUTLINE:
            polygons.append([float(value) for corner in eased for value in corner])
    return polygons


def box(mask: np.ndarray) -> list[float]:
    """The smallest rectangle round a mask, in COCO's [x, y, width, height].

    The model reports a rectangle beside every mask, so the training data has to
    carry one. It is a result of the mask here and never a container for it: on
    the whole-silhouette target this rectangle is larger than the evidence in the
    picture, which is exactly what an architecture with no rectangle round its
    masks is free to be trained on.
    """
    rows, columns = np.nonzero(mask)
    x, y = float(columns.min()), float(rows.min())
    return [x, y, float(columns.max()) - x + 1.0, float(rows.max()) - y + 1.0]


def _records(examples: Iterable[data.Example], amodal: bool, folder: Path) -> Iterator[dict]:
    """Write one picture per station and yield the annotations that go with it."""
    written = 0
    for example in examples:
        crowd = "crowded" if example.crowded else "spawned"
        for station, sight in enumerate(example.sights):
            name = f"{crowd}-{example.seed:06d}-{station}.png"
            # The model is shown the grey picture the bench shades from depth,
            # and never the id picture the masks below are read out of.
            cv2.imwrite(str(folder / name), sight.image)
            written += 1
            yield {
                "image": {
                    "id": written,
                    "file_name": name,
                    "height": int(sight.image.shape[0]),
                    "width": int(sight.image.shape[1]),
                },
                "masks": [mask for mask in sight.masks(amodal) if mask.any()],
            }


def write(examples: Iterable[data.Example], *, amodal: bool, folder: Path) -> dict:
    """Write one split, and say how much of it there is."""
    folder.mkdir(parents=True, exist_ok=True)
    images, annotations = [], []
    for record in _records(examples, amodal, folder):
        images.append(record["image"])
        for mask in record["masks"]:
            polygons = outlines(mask)
            if not polygons:
                continue
            annotations.append(
                {
                    "id": len(annotations) + 1,
                    "image_id": record["image"]["id"],
                    "category_id": CLASS_ID,
                    "bbox": box(mask),
                    "area": float(mask.sum()),
                    "segmentation": polygons,
                    "iscrowd": 0,
                }
            )
    written = {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": CLASS_ID, "name": CLASS, "supercategory": "none"}],
    }
    (folder / "_annotations.coco.json").write_text(json.dumps(written) + "\n")
    return {"pictures": len(images), "glasses": len(annotations)}
