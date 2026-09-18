"""Run a trained model on any pictures and draw the centre of mass it finds on each block.

    python -m center_of_mass.predict --weights runs/com/weights/best.pt --source picture.jpg
    python -m center_of_mass.predict --weights runs/com/weights/best.pt --source some/folder --output out/

No truth is needed, so this works on a picture from anywhere. For each block
it prints the class, how sure the model is, and the centre of mass in pixels.
The pictures go to ``--output``, ``predictions/`` in the run's folder by default.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from training.train import pick_device

from .evaluate import GREY, RED, WHITE, read_guesses
from .polygons import CLASSES
from .settings import CONFIDENCE, TRAINING

PICTURE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="a picture, or a folder of them")
    parser.add_argument("--output", type=Path, help="where to write the drawn pictures")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    from ultralytics import YOLO

    if args.source.is_dir():
        pictures = sorted(p for p in args.source.iterdir() if p.suffix.lower() in PICTURE_SUFFIXES)
    else:
        pictures = [args.source]
    output = args.output or args.weights.resolve().parent.parent / "predictions"
    output.mkdir(parents=True, exist_ok=True)

    model = YOLO(str(args.weights))
    results = model.predict(
        [str(p) for p in pictures],
        imgsz=TRAINING["imgsz"],
        conf=CONFIDENCE,
        device=args.device or pick_device(),
        stream=True,
        verbose=False,
    )
    for picture, result in zip(pictures, results, strict=True):
        image = cv2.imread(str(picture))
        print(picture.name)
        for guess in read_guesses(result):
            x, y = guess.point
            print(
                f"  {CLASSES[guess.class_id]:14} {guess.confidence:.2f}  centre of mass at ({x:.1f}, {y:.1f})"
            )
            x0, y0, x1, y1 = map(int, guess.box)
            cv2.rectangle(image, (x0, y0), (x1, y1), GREY, 1)
            text = f"{CLASSES[guess.class_id]} {guess.confidence:.2f}"
            cv2.putText(
                image, text, (x0, max(y0 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1, cv2.LINE_AA
            )
            cv2.circle(image, (round(x), round(y)), 4, RED, -1, cv2.LINE_AA)
        cv2.imwrite(str(output / f"{picture.stem}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"\npictures written to {output}")


if __name__ == "__main__":
    main()
