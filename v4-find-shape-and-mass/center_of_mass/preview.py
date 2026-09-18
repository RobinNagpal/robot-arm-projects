"""A contact sheet: pictures with their boxes and centre-of-mass points drawn on.

    python -m center_of_mass.preview --split train --output figures/center-of-mass-samples.jpg

Green dot: the labelled centre of mass. Blue cross: the middle of the block's
mask. They should nearly meet, since from straight above the mask is almost
all top face. A green dot away from its block means the projection is wrong.
Orange cross: the middle of the box, to show how far it is from the real
centre of mass on an irregular shape.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from synthetic import sdf

from .polygons import CLASSES

TILE_WIDTH = 480
GREEN, BLUE, ORANGE, WHITE = (60, 220, 60), (255, 120, 40), (0, 150, 255), (255, 255, 255)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", default="train")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--data", type=Path, default=Path("data/center-of-mass"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pictures = sorted((args.data / "images" / args.split).glob("*.jpg"))[: args.count]
    if not pictures:
        raise SystemExit(f"no pictures in {args.data / 'images' / args.split}; make them first")
    tiles = [labelled(p, args.data, args.split) for p in pictures]
    while len(tiles) % args.columns:
        tiles.append(np.full_like(tiles[0], 255))
    rows = [np.hstack(tiles[i : i + args.columns]) for i in range(0, len(tiles), args.columns)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"wrote {args.output}")


def labelled(picture: Path, data: Path, split: str) -> np.ndarray:
    image = cv2.imread(str(picture))
    height, width = image.shape[:2]
    mask = cv2.imread(str(data / "masks" / split / f"{picture.stem}.png"), cv2.IMREAD_UNCHANGED)
    lines = (data / "labels" / split / f"{picture.stem}.txt").read_text().splitlines()
    # The scene record lists the labelled blocks in the same order as the label file.
    visible = json.loads((data / "scenes" / split / f"{picture.stem}.json").read_text())["visible"]
    for line, seen in zip(lines, visible, strict=True):
        numbers = line.split()
        class_id = int(numbers[0])
        bx, by, bw, bh, px, py = (float(v) for v in numbers[1:7])
        x0, y0 = int((bx - bw / 2) * width), int((by - bh / 2) * height)
        x1, y1 = int((bx + bw / 2) * width), int((by + bh / 2) * height)
        cv2.rectangle(image, (x0, y0), (x1, y1), WHITE, 1)
        cv2.putText(image, CLASSES[class_id], (x0, max(y0 - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1)
        _cross(image, (bx * width, by * height), ORANGE)
        _cross(image, mask_centre(mask, sdf.block_label(seen["block"])), BLUE)
        cv2.circle(image, _pixel((px * width, py * height)), 4, GREEN, -1, cv2.LINE_AA)
    image = cv2.resize(image, (TILE_WIDTH, TILE_WIDTH * height // width), interpolation=cv2.INTER_AREA)
    return cv2.copyMakeBorder(image, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))


def mask_centre(mask: np.ndarray, label: int) -> tuple[float, float]:
    """The middle of the pixels painted ``label``, in the same pixel units as the labels."""
    moments = cv2.moments((mask == label).astype(np.uint8), binaryImage=True)
    # Pixel i covers i to i + 1, and its middle is at i + 0.5.
    return (moments["m10"] / moments["m00"] + 0.5, moments["m01"] / moments["m00"] + 0.5)


def _pixel(point: tuple[float, float]) -> tuple[int, int]:
    return (round(point[0]), round(point[1]))


def _cross(image: np.ndarray, point: tuple[float, float], colour) -> None:
    cv2.drawMarker(image, _pixel(point), colour, cv2.MARKER_CROSS, 10, 2, cv2.LINE_AA)


if __name__ == "__main__":
    main()
