"""Fine-tune the borrowed model on this cell's own pictures, and save the weights.

    pixi run python 04-yolo-fine-tuned/train.py
    pixi run python 04-yolo-fine-tuned/train.py --scenes 120 --epochs 60

**What is fitted.** Every weight in Ultralytics YOLO26-seg, starting from the
file Ultralytics downloads rather than from random numbers, with the borrowed
list of everyday categories replaced by the single class "glass".

**Where it is saved.** ``weights/fine-tuned.pt``, beside the download. Not
committed: it is large, it has to be kept in step with the cell, and it is
bound by the download's AGPL-3.0 licence, because a file derived from an AGPL
work carries that licence with it.

**Two steps, and the first one is the interesting one.** Ultralytics trains from
a directory rather than from arrays, so the bench's scenes are rendered and
written out in that shape first: the pictures as image files, and one text file
per picture holding the outline of every glass in it under a single class.
``dataset.py`` is that step, and the outlines come from the renderer's own id
picture, which costs nothing here and would be the expensive part of the same
work on real pictures.

**The scenes come from below the bench's dividing line and nowhere else**, so
nothing here can be a scene ``run.py`` later claims a score on. Two separate
checks enforce it, in ``data.training_seeds`` and in ``dataset.write``.

The defaults are small, so that a short run finishes on this machine, which
trains through MPS. They are enough to see the method work and not enough to
judge it. ``--scenes`` and ``--epochs`` are what buy that, and both cost time.
"""

from __future__ import annotations

import argparse
import time

import dataset
import yolo_fine_tuned

import data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--scenes",
        type=int,
        default=yolo_fine_tuned.SCENES,
        help=f"scenes to draw, each one a picture from every station (default {yolo_fine_tuned.SCENES})",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=yolo_fine_tuned.EPOCHS,
        help=f"how many passes over the pictures (default {yolo_fine_tuned.EPOCHS})",
    )
    given = parser.parse_args()
    if given.scenes < yolo_fine_tuned.CHECK_EVERY or given.epochs < 1:
        raise SystemExit(
            f"--scenes {given.scenes} --epochs {given.epochs}: a run needs at least "
            f"{yolo_fine_tuned.CHECK_EVERY} scenes and one epoch to do anything"
        )

    hard = data.how_many_crowded(given.scenes)
    print(
        f"fine-tuning {yolo_fine_tuned.MODEL} on {given.scenes} scenes "
        f"({given.scenes - hard} spawned, {hard} crowded), {len(data.stations())} pictures each, "
        f"for {given.epochs} epochs"
    )

    save = yolo_fine_tuned.fitted()
    started = time.time()
    reported = yolo_fine_tuned.fit(
        dataset.scenes(given.scenes), amodal=False, save=save, epochs=given.epochs
    )
    spent = time.time() - started

    for measure, value in reported.items():
        print(f"  {measure}: {value}")
    if not save.exists():
        raise SystemExit(f"trained for {spent:.0f}s and wrote no {save.name}")
    print(f"fitted in {spent:.0f}s, saved to {save}")


if __name__ == "__main__":
    main()
