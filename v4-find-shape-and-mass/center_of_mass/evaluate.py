"""Score a trained model on the test pictures: how far its centre of mass is from the true one.

    python -m center_of_mass.evaluate --weights runs/com/weights/best.pt

The true centre of mass of every test block is known exactly, from the
outline it was built from. Each block the model finds is scored by the
distance from its point to that true point, in pixels and in millimetres on
the table. Next to it, the same distance for the middle of the model's own
box: a model that only learned to find blocks would score that. The gap
between the two is what the model learned about mass.

Written into the run's folder:

    evaluation.json             every number printed
    test-pictures/000123.jpg    each test picture, true and guessed points drawn on
    test-samples.jpg            the first 12 of those on one sheet
    test/                       Ultralytics' own scores and plots
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from training.train import pick_device

from .polygons import CLASSES
from .scoring import Guess, Scored, Truth, match, summary
from .settings import CONFIDENCE, MATCH_IOU, TRAINING

GREEN, RED, WHITE, GREY = (60, 220, 60), (60, 60, 255), (255, 255, 255), (170, 170, 170)
SHEET_PICTURES, SHEET_COLUMNS, TILE_WIDTH = 12, 4, 480


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data/center-of-mass"), help="the rendered dataset")
    parser.add_argument("--split", default="test")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    from ultralytics import YOLO

    run = args.weights.resolve().parent.parent
    device = args.device or pick_device()
    model = YOLO(str(args.weights))

    metrics = model.val(
        data=str(run / "data.yaml"),
        split=args.split,
        imgsz=TRAINING["imgsz"],
        batch=TRAINING["batch"],
        device=device,
        project=str(run),
        name=args.split,
        exist_ok=True,
        verbose=False,
    )

    pictures = sorted((args.data / "images" / args.split).glob("*.jpg"))
    drawn = run / f"{args.split}-pictures"
    drawn.mkdir(exist_ok=True)
    scored: list[Scored] = []
    extra = 0
    tiles = []
    results = model.predict(
        [str(p) for p in pictures],
        imgsz=TRAINING["imgsz"],
        conf=CONFIDENCE,
        device=device,
        stream=True,
        verbose=False,
    )
    for picture, result in zip(pictures, results, strict=True):
        truths = read_truths(args.data / "scenes" / args.split / f"{picture.stem}.json")
        found, left_over = match(truths, read_guesses(result), MATCH_IOU)
        scored += found
        extra += len(left_over)
        image = draw(cv2.imread(str(picture)), found, left_over)
        cv2.imwrite(str(drawn / picture.name), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if len(tiles) < SHEET_PICTURES:
            tiles.append(image)

    scores = {
        "pictures": len(pictures),
        "ultralytics": {
            "box mAP50": float(metrics.box.map50),
            "box mAP50-95": float(metrics.box.map),
            "pose mAP50": float(metrics.pose.map50),
            "pose mAP50-95": float(metrics.pose.map),
        },
        "extra guesses": extra,
        "all": group(scored),
        "per class": {
            name: group([s for s in scored if s.truth.class_id == i]) for i, name in enumerate(CLASSES)
        },
    }
    report(scores)
    (run / "evaluation.json").write_text(json.dumps(scores, indent=1))
    write_sheet(tiles, run / f"{args.split}-samples.jpg")
    print(f"\nwritten to {run / 'evaluation.json'}, pictures in {drawn}")


def read_truths(scene: Path) -> list[Truth]:
    record = json.loads(scene.read_text())
    truths = []
    for seen in record["visible"]:
        x, y, w, h = seen["box"]
        truths.append(
            Truth(
                box=(x, y, x + w, y + h),
                class_id=CLASSES.index(seen["shape"]),
                point=tuple(seen["point"]),
                centre_of_mass=tuple(seen["centre_of_mass"]),
                height=record["blocks"][seen["block"]]["thickness"],
            )
        )
    return truths


def read_guesses(result) -> list[Guess]:
    boxes = result.boxes.xyxy.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy().astype(int)
    confidences = result.boxes.conf.cpu().numpy()
    points = result.keypoints.xy.cpu().numpy()[:, 0, :]
    return [
        Guess(tuple(map(float, box)), int(c), float(conf), (float(p[0]), float(p[1])))
        for box, c, conf, p in zip(boxes, classes, confidences, points, strict=True)
    ]


def group(scored: list[Scored]) -> dict:
    found = [s for s in scored if s.guess is not None]
    return {
        "blocks": len(scored),
        "found": len(found),
        "right class": sum(s.guess.class_id == s.truth.class_id for s in found),
        "model, pixels": summary([s.pixels for s in found]),
        "model, mm": summary([s.millimetres for s in found]),
        "box centre, pixels": summary([s.box_centre_pixels for s in found]),
        "box centre, mm": summary([s.box_centre_millimetres for s in found]),
    }


def report(scores: dict) -> None:
    u = scores["ultralytics"]
    print(
        f"\n{scores['pictures']} pictures. box mAP50 {u['box mAP50']:.3f}, "
        f"pose mAP50 {u['pose mAP50']:.3f}, pose mAP50-95 {u['pose mAP50-95']:.3f}"
    )
    print(f"guesses that matched no block: {scores['extra guesses']}\n")
    print(
        f"{'':15}{'blocks':>7}{'found':>7}{'class':>7}   "
        f"{'model mm: mean  median  90%':>28}   {'box centre mm: mean':>19}"
    )
    rows = [("all", scores["all"]), *scores["per class"].items()]
    for name, g in rows:
        mm, box = g["model, mm"], g["box centre, mm"]
        if not mm:
            print(f"{name:15}{g['blocks']:>7}{g['found']:>7}")
            continue
        print(
            f"{name:15}{g['blocks']:>7}{g['found']:>7}{g['right class']:>7}   "
            f"{mm['mean']:>17.1f}{mm['median']:>8.1f}{mm['90%']:>6.1f}   {box['mean']:>19.1f}"
        )
    px = scores["all"]["model, pixels"]
    if px:
        print(
            f"\nin pixels, all blocks: mean {px['mean']:.1f}, median {px['median']:.1f}, 90% {px['90%']:.1f}"
        )


def draw(image: np.ndarray, found: list[Scored], extra: list[Guess]) -> np.ndarray:
    """Green: the true centre of mass. Red: the model's. The number is the distance on the table."""
    for s in found:
        true = _pixel(s.truth.point)
        if s.guess is None:
            x0, y0, x1, y1 = map(int, s.truth.box)
            cv2.rectangle(image, (x0, y0), (x1, y1), RED, 1)
            cv2.putText(image, "missed", (x0, max(y0 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, RED, 1)
            cv2.circle(image, true, 4, GREEN, -1, cv2.LINE_AA)
            continue
        x0, y0, x1, y1 = map(int, s.guess.box)
        cv2.rectangle(image, (x0, y0), (x1, y1), GREY, 1)
        text = f"{CLASSES[s.guess.class_id]} {s.millimetres:.1f} mm"
        cv2.putText(image, text, (x0, max(y0 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1, cv2.LINE_AA)
        guess = _pixel(s.guess.point)
        cv2.line(image, true, guess, WHITE, 1, cv2.LINE_AA)
        cv2.circle(image, true, 4, GREEN, -1, cv2.LINE_AA)
        cv2.circle(image, guess, 3, RED, -1, cv2.LINE_AA)
    for guess in extra:
        x0, y0, x1, y1 = map(int, guess.box)
        cv2.rectangle(image, (x0, y0), (x1, y1), RED, 1)
        cv2.putText(image, "no block here", (x0, max(y0 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, RED, 1)
    return image


def write_sheet(tiles: list[np.ndarray], path: Path) -> None:
    if not tiles:
        return
    small = [
        cv2.resize(t, (TILE_WIDTH, TILE_WIDTH * t.shape[0] // t.shape[1]), interpolation=cv2.INTER_AREA)
        for t in tiles
    ]
    small = [cv2.copyMakeBorder(t, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=WHITE) for t in small]
    while len(small) % SHEET_COLUMNS:
        small.append(np.full_like(small[0], 255))
    rows = [np.hstack(small[i : i + SHEET_COLUMNS]) for i in range(0, len(small), SHEET_COLUMNS)]
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])


def _pixel(point: tuple[float, float]) -> tuple[int, int]:
    return (round(point[0]), round(point[1]))


if __name__ == "__main__":
    main()
