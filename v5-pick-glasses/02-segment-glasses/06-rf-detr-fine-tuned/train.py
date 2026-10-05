"""Continue RF-DETR-Seg's training on this cell's pictures, and save the result.

    pixi run python 06-rf-detr-fine-tuned/train.py --target modal  --scenes 120
    pixi run python 06-rf-detr-fine-tuned/train.py --target amodal --scenes 120

**What is being fitted.** The whole model, starting from the weights Roboflow
publishes, with the borrowed list of everyday categories cut down to the single
class "glass". Almost all of the weights are in the part that reads the picture,
so what is borrowed is mostly a general answer to "what is in this part of this
picture" and the fitting here only has to adjust it.

**What ``--target`` chooses** is the one difference between this solution's two
rungs, and it is a difference in the target and not in the model:

``modal``    each mask is trained against the pixels the camera can see of a
             glass.
``amodal``   each mask is trained against the glass's whole silhouette, which
             the bench renders by drawing the scene again with the other
             glasses taken away.

**Where it saves.** ``weights/fitted-<target>.pth``, one file per target,
because the two rungs are two fits of the same model and one name for both
would let a run score the first rung and call it the second. The dataset, the
logs and the run's own checkpoints go to ``weights/training-<target>/``.

**Which scenes.** ``data.training`` only ever draws seeds below the bench's
held-out line, half of them crowded, so the edge of the specification sits in
the middle of the training set and no scene here is one ``run.py`` scores on.
"""

from __future__ import annotations

import argparse
import time

import rf_detr_seg
import weights

import data

TARGETS = ("modal", "amodal")

# The default scene count. Each scene is one picture from each of the survey's
# three stations, so this is a few hundred pictures, which is the size a
# fine-tune of a model this size is reasonable on.
SCENES = 120


def command() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=TARGETS, required=True, help="what the masks are trained against")
    parser.add_argument("--scenes", type=int, default=SCENES, help="how many scenes to fit on")
    parser.add_argument("--epochs", type=int, default=rf_detr_seg.EPOCHS, help="how many passes over them")
    parser.add_argument("--batch", type=int, default=rf_detr_seg.BATCH, help="pictures per training step")
    return parser


def main() -> None:
    given = command().parse_args()
    if given.scenes < 1 or given.epochs < 1 or given.batch < 1:
        raise SystemExit("--scenes, --epochs and --batch all have to be at least 1")

    amodal = given.target == "amodal"
    save = weights.fitted(given.target)
    hard = data.how_many_crowded(given.scenes)
    print(
        f"{given.target}: fine-tuning {rf_detr_seg.SIZE} on {given.scenes} scenes "
        f"({given.scenes - hard} spawned, {hard} crowded), {len(data.stations())} pictures each"
    )
    started = time.time()
    fitted = rf_detr_seg.fit(
        data.training(given.scenes),
        amodal=amodal,
        save=save,
        epochs=given.epochs,
        batch=given.batch,
    )
    spent = time.time() - started

    for measure, value in fitted.items():
        print(f"  {measure}: {value}")
    print(f"{given.target}: fitted in {spent:.0f}s, saved to {save}")


if __name__ == "__main__":
    main()
