"""The bench's scenes written out in the shape Ultralytics reads a training set in.

Ultralytics does not take arrays. It reads a directory: the pictures as image
files on one side, one text file per picture on the other holding one line per
object, and a small YAML saying where both are and what the classes are called.
So fine-tuning needs this step, which draws the bench's scenes and writes them
out in that shape.

**One class.** The YAML names one class, "glass", in place of the borrowed list
of everyday categories. The model afterwards reports no kind at all, which is
what turns it from a describer of photographs into a finder of instances, and
it is the change the solution's document says comes with the training rather
than beside it.

**Only scenes from below the bench's dividing line.** ``render.TEST_SEEDS`` is
the line. ``data.training_seeds`` refuses to cross it and ``write`` refuses a
scene from above it as well, because a training set that reached a held-out
scene would leave no trace in the scorecard and every number after it would be
worthless.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Iterator
from pathlib import Path

import cv2
import numpy as np

import data
import masks_to_glasses
import render

# Where a training set is written. Beside the code rather than in a shared
# cache, so a run's input sits next to the run and the whole thing can be
# deleted to start again. Not committed: it is a few hundred pictures.
ROOT = Path(__file__).parent / "dataset"

# The one class: its number in a label file, and its name in the YAML.
GLASS, NAME = 0, "glass"

# The two parts of a written set, in Ultralytics' own words for them. Both come
# from below the dividing line: "val" here is the part the training run checks
# itself on while it is running, and it is not the bench's held-out half.
FIT, CHECK = "train", "val"

# A polygon needs three corners before it encloses anything.
CORNERS = 3


def outline(mask: np.ndarray) -> np.ndarray | None:
    """The largest piece of ``mask`` as a polygon of (column, row) pixels, or None.

    The largest piece and not every piece, because one line of a label file is
    one object: a glass whose visible pixels come apart into patches, because
    something stands in front of part of it, would otherwise be taught as
    several glasses standing in a row.
    """
    pieces, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not pieces:
        return None
    biggest = max(pieces, key=cv2.contourArea).reshape(-1, 2)
    return biggest if len(biggest) >= CORNERS else None


def label(sight: data.Sight) -> list[str]:
    """One line per glass in one picture: the class, then its outline, as Ultralytics wants it.

    **These labels cost nothing here, and on real pictures they would be the
    most expensive part of the whole exercise.** The renderer stamps every pixel
    with the glass it belongs to, so an exact outline is a selection over an
    array it produced anyway. On photographs somebody has to draw every outline
    by hand, the work is slow, and no two people draw the same outline. Any
    judgement about whether fine-tuning is worth its price has to carry that
    difference with it, because on real pictures the price is quite different.

    The outlines are the pixels the camera saw, so a glass standing partly
    behind another is labelled with the slice of it that showed. Training
    towards the whole silhouette instead is a different solution's choice, and
    ``data.Sight.whole`` is where that target lives.
    """
    lines = []
    for mask in sight.visible:
        # A glass the camera barely sees at this station is not something to
        # teach from: the same count the shared arithmetic calls too little of a
        # glass to fit anything to.
        if mask.sum() < masks_to_glasses.MIN_PIXELS:
            continue
        edge = outline(mask)
        if edge is None:
            continue
        across, down = edge[:, 0] / render.WIDTH, edge[:, 1] / render.HEIGHT
        corners = " ".join(f"{x:.6f} {y:.6f}" for x, y in zip(across, down, strict=True))
        lines.append(f"{GLASS} {corners}")
    return lines


def write(examples: Iterable[data.Example], root: Path, part: str) -> dict:
    """Write every station's picture of every scene, with its label, under ``root``.

    A picture holding no outline at all is still written. A station that can see
    no glass is a real picture of this cell, and a model has to be told that the
    answer there is nothing.
    """
    images, labels = root / "images" / part, root / "labels" / part
    for folder in (images, labels):
        folder.mkdir(parents=True, exist_ok=True)

    written = outlines = 0
    for example in examples:
        if example.seed >= render.TEST_SEEDS:
            raise ValueError(
                f"scene {example.seed} is at or above the held-out line {render.TEST_SEEDS}, so "
                f"training on it would leave the scorecard claiming a scene that was learned from"
            )
        family = "crowded" if example.crowded else "spawned"
        for station, sight in enumerate(example.sights):
            stem = f"{family}-{example.seed:05d}-station-{station}"
            # The same shaded grey every solution in this folder is shown, three
            # channels of it, written as PNG so that nothing is lost on the way.
            cv2.imwrite(str(images / f"{stem}.png"), sight.image)
            lines = label(sight)
            (labels / f"{stem}.txt").write_text("".join(f"{line}\n" for line in lines))
            written += 1
            outlines += len(lines)
    return {"pictures": written, "outlines": outlines}


def describe(root: Path) -> Path:
    """Write the YAML Ultralytics reads: where the pictures are, and the one class.

    An absolute path, so the set is found wherever the training run is started
    from rather than under Ultralytics' own idea of where datasets live.
    """
    where = root / f"{NAME}.yaml"
    where.write_text(
        "# Written by dataset.py. One class, which is the point of this solution.\n"
        f"path: {root.resolve()}\n"
        f"train: images/{FIT}\n"
        f"val: images/{CHECK}\n"
        "names:\n"
        f"  {GLASS}: {NAME}\n"
    )
    return where


def build(fitting, checking, root: Path = ROOT) -> tuple[Path, dict]:
    """Write a whole training set, and return its YAML and what went into it.

    The directory is emptied first. Ultralytics caches the labels it read beside
    them, so a set written over the top of an older one can be trained from the
    older labels without anything saying so.
    """
    if root.exists():
        shutil.rmtree(root)
    counts = {part: write(examples, root, part) for part, examples in ((FIT, fitting), (CHECK, checking))}
    return describe(root), counts


def scenes(count: int, start: int = 0, share: float = data.CROWDED_SHARE) -> Iterator[data.Example]:
    """``count`` scenes from seed ``start``, part of them crowded, all below the line.

    The crowded ones are drawn from seeds of their own rather than from the same
    ones the spawned scenes used, so that two calls asking for different stretches
    cannot be handed the same scene twice. ``data.training_seeds`` is what refuses
    a stretch that would cross into the held-out half.

    The share that is crowded is the bench's own, and it matters: the cell's
    placement rule keeps glasses a comfortable distance apart, so a training set
    of spawned scenes alone would never show the model a pair that was hard to
    separate. The edge of what the method will be asked to handle should sit in
    the middle of its training set.
    """
    hard = data.how_many_crowded(count, share)
    for seed in data.training_seeds(count - hard, start):
        yield data.spawned(seed)
    for seed in data.training_seeds(hard, start + count - hard):
        yield data.crowded(seed)
