"""Train a YOLO pose model to find each block and point at its centre of mass.

    python -m center_of_mass.train
    python -m center_of_mass.train --model yolo26m-pose.pt --name com-m
    python -m center_of_mass.train --resume runs/com/weights/last.pt

Everything the run writes goes to ``runs/<name>/``: the trained model
(``weights/best.pt``), a CSV of every epoch, Ultralytics' own plots, and the
``data.yaml`` it trained from.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from training.train import RUNS, camera_effects, pick_device

from .settings import AUGMENTATION, KEYPOINT_SIGMA, MODEL, TRAINING


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=Path("data/center-of-mass"), help="the rendered dataset")
    parser.add_argument("--model", default=MODEL, help="starting weights, e.g. yolo26m-pose.pt")
    parser.add_argument("--epochs", type=int, default=TRAINING["epochs"])
    parser.add_argument("--batch", type=int, default=TRAINING["batch"])
    parser.add_argument("--device", default=None, help="mps, cpu or 0; picked if left out")
    parser.add_argument("--name", default="com")
    parser.add_argument("--resume", type=Path, help="a last.pt to carry on from")
    args = parser.parse_args()

    from ultralytics import YOLO

    if args.resume:
        YOLO(str(args.resume)).train(resume=True)
        return

    if not (args.data / "data.yaml").exists():
        raise SystemExit(f"{args.data / 'data.yaml'} not found; make the dataset first with `make com-data`")
    run = RUNS / args.name
    if run.exists():
        # Ultralytics would quietly train into com2 instead, and evaluate
        # would then score the wrong model.
        raise SystemExit(f"{run} already exists; delete it or pick another name")
    run.mkdir(parents=True)
    data_yaml = write_data_yaml(args.data, run)

    model = YOLO(args.model)
    settings = {
        **TRAINING,
        **AUGMENTATION,
        "data": str(data_yaml),
        "epochs": args.epochs,
        "batch": args.batch,
        "device": args.device or pick_device(),
        "project": str(RUNS),
        "name": args.name,
        "exist_ok": True,  # the folder holds data.yaml already
        "augmentations": camera_effects(),
    }
    model.train(**settings)
    print(f"\nthe trained model: {model.trainer.best}")


def write_data_yaml(data: Path, run: Path) -> Path:
    """The dataset's data.yaml, plus the keypoint sigma, into the run's folder.

    The sigma is a training setting, not a fact about the pictures, so it is
    added here rather than by the generator. Ultralytics reads it from the
    data file both for the loss and for the pose score.
    """
    text = (data / "data.yaml").read_text()
    path = run / "data.yaml"
    path.write_text(
        text + f"\n# Added by center_of_mass/train.py; see settings.py.\nkpt_oks_sigmas: [{KEYPOINT_SIGMA}]\n"
    )
    return path


if __name__ == "__main__":
    main()
