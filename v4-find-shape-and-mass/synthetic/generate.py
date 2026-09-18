"""Make one split of the dataset: draw scenes, render them in Gazebo, write pictures and labels.

    python -m synthetic.generate --split train --count 6000

What comes out, under ``--out`` (``data/shapes`` by default):

    images/<split>/000123.jpg   the picture
    labels/<split>/000123.txt   one YOLO outline per visible block
    masks/<split>/000123.png    the label mask the outlines came from
    scenes/<split>/000123.json  everything that was drawn for that picture
    textures/                   the table and floor textures, shared by every split
    data.yaml                   the dataset description YOLO trains on
    data-unseen.yaml            the same, with the unseen test set as its test split

Every picture has its own random seed, made from the split's name, ``--seed``
and the picture's number. So any one picture can be made again on its own,
and no two splits ever share a scene.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict
from pathlib import Path

import cv2

from . import sdf
from .gazebo import Gazebo
from .labels import instances, yolo_line
from .randomization import SEEN, UNSEEN, Scene, draw_scene
from .shapes import CLASSES
from .textures import texture_file

SPLITS = {"train": SEEN, "val": SEEN, "test": SEEN, "test-unseen": UNSEEN}

# Gazebo's memory grows by about 0.4 MB per picture and is not given back when
# the blocks are removed, most likely the mesh it builds for every outline.
# Starting a fresh server every so often keeps a long run from filling memory,
# for the price of a few seconds' start-up.
PICTURES_PER_SERVER = 1500
MAX_FAILURES_IN_A_ROW = 3


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("data/shapes"))
    parser.add_argument("--first", type=int, default=0, help="number of the first picture, to add to a split")
    parser.add_argument("--verbose", action="store_true", help="show Gazebo's own output")
    args = parser.parse_args()

    out = args.out.resolve()
    folders = {kind: out / kind / args.split for kind in ("images", "labels", "masks", "scenes")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    write_dataset_files(out)

    end = args.first + args.count
    number = args.first  # the next picture to make
    failures_in_a_row = 0
    started = time.monotonic()
    while number < end:
        try:
            with Gazebo(verbose=args.verbose) as gazebo:
                for _ in range(PICTURES_PER_SERVER):
                    if number == end:
                        break
                    rng = random.Random(f"{args.split}-{args.seed}-{number}")
                    scene = draw_scene(rng, SPLITS[args.split])
                    rgb, mask = render(gazebo, scene, number, out / "textures")
                    save(folders, f"{number:06d}", scene, rgb, mask)
                    number += 1
                    failures_in_a_row = 0

                    done = number - args.first
                    if done % 100 == 0 or done == args.count:
                        rate = done / (time.monotonic() - started)
                        left = (args.count - done) / rate
                        print(
                            f"{args.split}: {done}/{args.count} pictures, "
                            f"{rate:.1f} per second, {left / 60:.0f} min left",
                            flush=True,
                        )
        except (RuntimeError, TimeoutError) as error:
            # Once in several thousand pictures the simulator stops answering
            # in time. The same picture on a fresh server renders fine, so try
            # that. A picture that keeps failing is a real fault, and stops the run.
            failures_in_a_row += 1
            if failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
                raise
            print(f"picture {number} failed ({error}); trying it again on a fresh Gazebo", flush=True)


def render(gazebo: Gazebo, scene: Scene, number: int, texture_folder: Path):
    models = {
        sdf.table_name(number): sdf.table_sdf(scene.table, texture_file(scene.table, texture_folder), number),
        sdf.floor_name(number): sdf.floor_sdf(scene.floor, texture_file(scene.floor, texture_folder), number),
    }
    for index, block in enumerate(scene.blocks):
        models[sdf.block_name(number, index)] = sdf.block_sdf(block, number, index)
    for index, distractor in enumerate(scene.distractors):
        models[sdf.distractor_name(number, index)] = sdf.distractor_sdf(distractor, number, index)

    gazebo.replace_models(models)
    camera = scene.camera
    gazebo.move_camera(camera.position, camera.roll, camera.pitch, camera.yaw)
    gazebo.set_light("sun", scene.sun.direction, scene.sun.colour, scene.sun.shadows)
    gazebo.set_light("fill", scene.fill.direction, scene.fill.colour, scene.fill.shadows)
    rgb, mask = gazebo.take_picture()

    # Every label number in the mask must belong to a block in this scene. One
    # that does not would mean the picture shows a scene other than the one
    # its labels were written from, and the whole split would be suspect.
    known = {sdf.block_label(i) for i in range(len(scene.blocks))} | {0}
    stray = {int(v) for v in set(mask.flat)} - known
    if stray:
        raise RuntimeError(f"the mask holds label numbers {sorted(stray)} that no block in this scene has")
    return rgb, mask


def save(folders: dict[str, Path], name: str, scene: Scene, rgb, mask) -> None:
    height, width = mask.shape
    found = instances(mask, [CLASSES.index(b.shape) for b in scene.blocks], sdf.block_label)

    cv2.imwrite(
        str(folders["images"] / f"{name}.jpg"),
        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, 95],
    )
    cv2.imwrite(str(folders["masks"] / f"{name}.png"), mask)
    (folders["labels"] / f"{name}.txt").write_text("".join(yolo_line(i, width, height) + "\n" for i in found))

    record = asdict(scene)
    record["visible"] = [
        {"block": i.block, "shape": CLASSES[i.class_id], "pixels": i.pixels, "box": i.box} for i in found
    ]
    (folders["scenes"] / f"{name}.json").write_text(json.dumps(record, indent=1))


def write_dataset_files(out: Path) -> None:
    """The two files that tell YOLO where the pictures are and what the classes are called."""
    names = "".join(f"  {i}: {name}\n" for i, name in enumerate(CLASSES))
    for file, test in (("data.yaml", "test"), ("data-unseen.yaml", "test-unseen")):
        (out / file).write_text(
            f"# Written by synthetic/generate.py.\npath: {out}\ntrain: images/train\nval: images/val\n"
            f"test: images/{test}\n\nnames:\n{names}"
        )


if __name__ == "__main__":
    main()
