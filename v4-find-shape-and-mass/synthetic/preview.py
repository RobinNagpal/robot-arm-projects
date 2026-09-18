"""A contact sheet: some pictures from a split, with their labels drawn on top.

    python -m synthetic.preview --split train --count 12 --output figures/train-samples.jpg

Looking at the labels on the pictures is the only real check that they are
right. A label that is shifted, mirrored or on the wrong block shows at a
glance here, and nowhere else until a model trains badly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from .shapes import CLASSES

# One colour per class, picked to be told apart easily, in BGR for OpenCV.
PALETTE = [
    (56, 56, 255),
    (151, 157, 255),
    (31, 112, 255),
    (29, 178, 255),
    (49, 210, 207),
    (10, 249, 72),
    (187, 212, 0),
]
TILE_WIDTH = 480


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", default="train")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--data", type=Path, default=Path("data/shapes"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pictures = sorted((args.data / "images" / args.split).glob("*.jpg"))[: args.count]
    if not pictures:
        raise SystemExit(
            f"no pictures in {args.data / 'images' / args.split}; make them with `make data` first"
        )
    tiles = [labelled(p, args.data / "labels" / args.split / f"{p.stem}.txt") for p in pictures]
    while len(tiles) % args.columns:
        tiles.append(np.full_like(tiles[0], 255))
    rows = [np.hstack(tiles[i : i + args.columns]) for i in range(0, len(tiles), args.columns)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"wrote {args.output}")


def labelled(picture: Path, labels: Path) -> np.ndarray:
    image = cv2.imread(str(picture))
    height, width = image.shape[:2]
    for line in labels.read_text().splitlines():
        numbers = line.split()
        class_id = int(numbers[0])
        points = (np.array(numbers[1:], dtype=np.float32).reshape(-1, 2) * (width, height)).astype(np.int32)
        colour = PALETTE[class_id % len(PALETTE)]
        cv2.polylines(image, [points], True, colour, 2, cv2.LINE_AA)
        x, y = points.min(axis=0)
        text = CLASSES[class_id]
        (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        y = max(y, text_h + 4)
        cv2.rectangle(image, (x, y - text_h - 4), (x + text_w + 4, y), colour, -1)
        cv2.putText(image, text, (x + 2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    image = cv2.resize(image, (TILE_WIDTH, TILE_WIDTH * height // width), interpolation=cv2.INTER_AREA)
    return cv2.copyMakeBorder(image, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))


if __name__ == "__main__":
    main()
