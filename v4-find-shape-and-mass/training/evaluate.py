"""Score a trained model on test and on test-unseen, side by side.

    python -m training.evaluate --weights runs/shapes/weights/best.pt

The two scores together say more than either alone. A model that has only
learned Gazebo scores well on test and much worse on test-unseen. The scores
are printed and written to ``evaluation.json`` in the run's folder, with
Ultralytics' plots, confusion matrix included, under ``test/`` and
``test-unseen/`` next to it.

A model trained on a subset is scored on that run's own smaller test sets,
from the lists in ``runs/<name>/data/``, so its score is never mixed up with
one from the full sets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .settings import TRAINING
from .train import pick_device

TEST_SETS = {"test": "data.yaml", "test-unseen": "data-unseen.yaml"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data/shapes"), help="folder with the yaml files")
    parser.add_argument("--batch", type=int, default=TRAINING["batch"])
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    run = args.weights.resolve().parent.parent
    data = run / "data" if (run / "data" / "data.yaml").exists() else args.data
    print(f"test sets from {data}")
    scores = {}
    for name, yaml in TEST_SETS.items():
        metrics = model.val(
            data=str((data / yaml).resolve()),
            # Both yaml files call their test pictures "test"; data-unseen.yaml points it at test-unseen.
            split="test",
            imgsz=TRAINING["imgsz"],
            batch=args.batch,
            device=args.device or pick_device(),
            project=str(run),
            name=name,
            exist_ok=True,
        )
        scores[name] = {
            "box mAP50": metrics.box.map50,
            "box mAP50-95": metrics.box.map,
            "mask mAP50": metrics.seg.map50,
            "mask mAP50-95": metrics.seg.map,
            "mask mAP50-95 per class": {metrics.names[i]: float(v) for i, v in enumerate(metrics.seg.maps)},
        }

    report(scores)
    (run / "evaluation.json").write_text(json.dumps(scores, indent=1))
    print(f"\nwritten to {run / 'evaluation.json'}")


def report(scores: dict) -> None:
    seen, unseen = scores["test"], scores["test-unseen"]
    print(f"\n{'':26}{'test':>10}{'unseen':>10}{'gap':>10}")
    for key in ("box mAP50", "box mAP50-95", "mask mAP50", "mask mAP50-95"):
        print(f"{key:26}{seen[key]:>10.3f}{unseen[key]:>10.3f}{seen[key] - unseen[key]:>10.3f}")
    print("\nmask mAP50-95 per class")
    for name, value in seen["mask mAP50-95 per class"].items():
        other = unseen["mask mAP50-95 per class"][name]
        print(f"  {name:24}{value:>10.3f}{other:>10.3f}{value - other:>10.3f}")


if __name__ == "__main__":
    main()
