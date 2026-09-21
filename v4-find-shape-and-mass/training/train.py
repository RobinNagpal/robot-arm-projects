"""Train a YOLO segmentation model on the rendered dataset.

    python -m training.train                          every picture
    python -m training.train --pictures 250           a random 250 from train, the other splits cut to match
    python -m training.train --resume runs/shapes/weights/last.pt

Everything the run writes goes to ``runs/<name>/``: the trained model
(``weights/best.pt``), a CSV of every epoch, Ultralytics' own plots, and for
a subset the picture lists it used (``data/``).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .settings import AUGMENTATION, CAMERA_EFFECTS, MODEL, TRAINING
from .subset import write_subset

RUNS = Path(__file__).resolve().parent.parent / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=Path("data/shapes"), help="the rendered dataset")
    parser.add_argument("--pictures", type=int, help="train on this many; every split is cut to match")
    parser.add_argument("--model", default=MODEL, help="starting weights, e.g. yolo26m-seg.pt")
    parser.add_argument("--epochs", type=int, default=TRAINING["epochs"])
    parser.add_argument("--batch", type=int, default=TRAINING["batch"])
    parser.add_argument("--device", default=None, help="mps, cpu or 0; picked if left out")
    parser.add_argument("--name", default="shapes")
    parser.add_argument("--resume", type=Path, help="a last.pt to carry on from")
    args = parser.parse_args()

    from ultralytics import YOLO

    if args.resume:
        # Every setting comes back from the run itself, the subset included.
        YOLO(str(args.resume)).train(resume=True)
        return

    if not (args.data / "data.yaml").exists():
        raise SystemExit(f"{args.data / 'data.yaml'} not found; make the dataset first with `make data`")
    run = RUNS / args.name
    if run.exists() and {p.name for p in run.iterdir()} == {"data"}:
        # Only the picture lists of a run that failed before training began.
        shutil.rmtree(run)
    if run.exists():
        # Ultralytics would quietly train into shapes2 instead, and evaluate
        # would then score the wrong model.
        raise SystemExit(f"{run} already exists; delete it or pick another name")

    data_yaml = args.data.resolve() / "data.yaml"
    if args.pictures:
        kept = write_subset(args.data, run / "data", args.pictures)
        print("subset: " + ", ".join(f"{split} {count}" for split, count in kept.items()))
        data_yaml = run / "data" / "data.yaml"

    settings = {
        **TRAINING,
        **AUGMENTATION,
        "data": str(data_yaml),
        "epochs": args.epochs,
        "batch": args.batch,
        "device": args.device or pick_device(),
        "project": str(RUNS),
        "name": args.name,
        "exist_ok": True,  # the folder may hold the subset already
        "augmentations": camera_effects(),
    }
    model = YOLO(args.model)
    model.train(**settings)
    print(f"\nthe trained model: {model.trainer.best}")


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def camera_effects() -> list:
    import albumentations as A

    # Colour and sharpness only, nothing that moves pixels, so the outlines
    # in the labels still fit the picture without being transformed.
    return [
        A.GaussianBlur(blur_limit=(3, 7), p=CAMERA_EFFECTS["blur"]),
        A.MotionBlur(blur_limit=(3, 9), p=CAMERA_EFFECTS["motion_blur"]),
        A.GaussNoise(std_range=(0.02, 0.08), p=CAMERA_EFFECTS["noise"]),
        A.ImageCompression(quality_range=(40, 95), p=CAMERA_EFFECTS["jpeg"]),
        A.ToGray(p=CAMERA_EFFECTS["grey"]),
        A.CLAHE(p=CAMERA_EFFECTS["contrast"]),
    ]


if __name__ == "__main__":
    main()
