"""Make one split of the centre-of-mass dataset: draw scenes, render them, write pictures and labels.

    python -m center_of_mass.generate --split train --count 250

What comes out, under ``--out`` (``data/center-of-mass`` by default):

    images/<split>/000123.jpg   the picture
    labels/<split>/000123.txt   one YOLO pose line per block: class, box, centre-of-mass point
    masks/<split>/000123.png    which block covers each pixel; where the boxes came from
    scenes/<split>/000123.json  everything drawn, and each block's true centre of mass
    textures/                   the table and floor textures
    data.yaml                   the dataset description YOLO trains on

A label line is

    <class> <box x> <box y> <box width> <box height> <point x> <point y> 2

all divided by the picture's width or height. The box comes from the mask.
The point is the true centre of mass, worked out from the outline the block
was built from and projected into the picture; see ``scene.py``. The 2 says
the point is visible.

Rendering is the classification generator's, unchanged.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict
from pathlib import Path

import cv2

from synthetic import sdf
from synthetic.gazebo import Gazebo
from synthetic.generate import MAX_FAILURES_IN_A_ROW, render
from synthetic.labels import instances

from .polygons import CLASSES
from .scene import IMAGE_HEIGHT, IMAGE_WIDTH, centre_of_mass, draw_scene, project, top_of_centre_of_mass

SPLITS = ("train", "val", "test")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("data/center-of-mass"))
    parser.add_argument("--verbose", action="store_true", help="show Gazebo's own output")
    args = parser.parse_args()

    out = args.out.resolve()
    folders = {kind: out / kind / args.split for kind in ("images", "labels", "masks", "scenes")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    write_dataset_file(out)

    number = 0
    failures_in_a_row = 0
    started = time.monotonic()
    while number < args.count:
        try:
            with Gazebo(verbose=args.verbose) as gazebo:
                while number < args.count:
                    # "com-" keeps these seeds apart from the classification dataset's.
                    rng = random.Random(f"com-{args.split}-{args.seed}-{number}")
                    scene = draw_scene(rng, number)
                    rgb, mask = render(gazebo, scene, number, out / "textures")
                    save(folders, f"{number:06d}", scene, rgb, mask)
                    number += 1
                    failures_in_a_row = 0
                    if number % 50 == 0 or number == args.count:
                        rate = number / (time.monotonic() - started)
                        print(
                            f"{args.split}: {number}/{args.count} pictures, {rate:.1f} per second", flush=True
                        )
        except (RuntimeError, TimeoutError) as error:
            # See synthetic/generate.py: a fresh server renders a stuck picture fine.
            failures_in_a_row += 1
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                raise
            print(f"picture {number} failed ({error}); trying it again on a fresh Gazebo", flush=True)


def save(folders: dict[str, Path], name: str, scene, rgb, mask) -> None:
    if mask.shape != (IMAGE_HEIGHT, IMAGE_WIDTH):
        raise RuntimeError(
            f"the picture is {mask.shape}, but scene.py projects onto {IMAGE_WIDTH} x {IMAGE_HEIGHT}"
        )
    found = instances(mask, [CLASSES.index(b.shape) for b in scene.blocks], sdf.block_label)

    lines, visible = [], []
    for instance in found:
        block = scene.blocks[instance.block]
        point = project(top_of_centre_of_mass(block))
        lines.append(pose_line(instance.class_id, instance.box, point))
        visible.append(
            {
                "block": instance.block,
                "shape": block.shape,
                "pixels": instance.pixels,
                "box": instance.box,
                "centre_of_mass": centre_of_mass(block),
                "point": point,
            }
        )

    cv2.imwrite(
        str(folders["images"] / f"{name}.jpg"),
        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, 95],
    )
    cv2.imwrite(str(folders["masks"] / f"{name}.png"), mask)
    (folders["labels"] / f"{name}.txt").write_text("".join(line + "\n" for line in lines))
    record = asdict(scene)
    record["visible"] = visible
    (folders["scenes"] / f"{name}.json").write_text(json.dumps(record, indent=1))


def pose_line(class_id: int, box: tuple[int, int, int, int], point: tuple[float, float]) -> str:
    x, y, w, h = box
    return (
        f"{class_id} {(x + w / 2) / IMAGE_WIDTH:.6f} {(y + h / 2) / IMAGE_HEIGHT:.6f} "
        f"{w / IMAGE_WIDTH:.6f} {h / IMAGE_HEIGHT:.6f} "
        f"{point[0] / IMAGE_WIDTH:.6f} {point[1] / IMAGE_HEIGHT:.6f} 2"
    )


def write_dataset_file(out: Path) -> None:
    names = "".join(f"  {i}: {name}\n" for i, name in enumerate(CLASSES))
    # One point per block. Flipping a picture left to right leaves it the
    # same point, so it maps to itself.
    (out / "data.yaml").write_text(
        f"# Written by center_of_mass/generate.py.\npath: {out}\ntrain: images/train\nval: images/val\n"
        f"test: images/test\n\nkpt_shape: [1, 3]\nflip_idx: [0]\n\nnames:\n{names}"
    )


if __name__ == "__main__":
    main()
