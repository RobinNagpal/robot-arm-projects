"""Save pictures of what SideNet is taught, and of what it answers.

    pixi run python show_side_net.py train   # one side picture per training scene, and its 17 true values
    pixi run python show_side_net.py test    # each measured glass of the held-out scenes: true beside said

Each gets a .png to look at, a .json with the 17 values in millimetres, and a
.npz with the numbers exactly as SideNet has them, in saved/side-net/. Nothing
here trains anything: ``test`` uses the weights that ``make train`` left.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2
import models
import numpy as np
import pipeline
import torch
import train
from drawing import WHITE, above, beside, foot, grey, panel, write
from models import HEIGHT_SCALE, SHRINK, WIDTH_SCALE
from show_ranker import judge, place_number
from work_cell.table.layout import TABLE_TOP_Z

import render
import scoring
from scoring import FRACTIONS

SAVED = Path(__file__).parent / "saved" / "side-net"

# Pictures are drawn this many times the size SideNet sees them at.
ZOOM = 3

# True values are green and SideNet's are orange, everywhere.
TRUE, SAID = (90, 255, 90), (0, 165, 255)

# The panel holding the to-scale drawing and the table of numbers.
CHART_WIDTH, CHART_HEIGHT = 560, 120 * ZOOM
ROW = 19


# ------------------------------------------------------------ drawing


def given_picture(net_input: np.ndarray) -> np.ndarray:
    """SideNet's one input picture: nearer is brighter, nothing there is black."""
    image = grey((2.0 - net_input[0]) / 4.0)
    return cv2.resize(image, None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)


def draw_on(image: np.ndarray, pose: np.ndarray, shape: tuple[float, np.ndarray], colour) -> np.ndarray:
    """The 17 values laid over a side picture, where they are on the glass.

    The glass is taken to stand where the camera is aimed, which is the
    middle of the picture. A thick line at the height, and a thin one across
    the glass at each of the 16 levels, as long as the width there.
    """
    image, (height, widths) = image.copy(), shape
    right, aim = pose[:3, 0], pose[:3, 3] + render.STANDOFF * pose[:3, 2]

    def at(level: float, across: float) -> tuple[int, int]:
        point = np.array([aim[0], aim[1], TABLE_TOP_Z + level]) + across * right
        column, row = render.project(pose, point)
        return round(column * ZOOM / SHRINK), round(row * ZOOM / SHRINK)

    for level, width in zip(FRACTIONS * height, widths, strict=True):
        cv2.line(image, at(level, -width / 2), at(level, width / 2), colour, 1, cv2.LINE_AA)
    reach = 0.8 * float(widths.max())
    cv2.line(image, at(height, -reach), at(height, reach), colour, 2, cv2.LINE_AA)
    column, row = at(height, reach)
    write(image, "height", (column + 4, row + 4), colour, 0.4)
    return image


def chart(true: tuple[float, np.ndarray], said: tuple[float, np.ndarray] | None = None) -> np.ndarray:
    """The 17 values as a drawing to scale, and as a table in millimetres."""
    image = np.zeros((CHART_HEIGHT, CHART_WIDTH, 3), np.uint8)
    shapes = [(true, TRUE)] + ([(said, SAID)] if said else [])

    # The drawing, on the left: the table, and each glass's outline standing on it.
    scale = min(310 / max(h for (h, _), _ in shapes), 200 / max(float(w.max()) for (_, w), _ in shapes))
    centre, floor = 115, CHART_HEIGHT - 20
    cv2.line(image, (5, floor), (225, floor), (120, 120, 120), 1)
    for (height, widths), colour in shapes:
        levels = floor - FRACTIONS * height * scale
        sides = [np.stack([centre + side * widths / 2 * scale, levels], 1) for side in (-1, 1)]
        for side in sides:
            cv2.polylines(image, [side.round().astype(np.int32)], False, colour, 1, cv2.LINE_AA)
        if colour == TRUE:
            for left, right in zip(*sides, strict=True):
                cv2.line(image, left.round().astype(int), right.round().astype(int), (50, 130, 50), 1)
        top = round(floor - height * scale)
        cv2.line(image, (centre - 105, top), (centre + 105, top), colour, 2, cv2.LINE_AA)

    # The table, on the right: the height, then the widths from the rim down.
    columns = (240, 330, 410, 490)
    write(image, "value", (columns[0], 14), WHITE, 0.4)
    write(image, "true mm", (columns[1], 14), TRUE, 0.4)
    if said:
        write(image, "said mm", (columns[2], 14), SAID, 0.4)
        write(image, "off by", (columns[3], 14), WHITE, 0.4)
    rows = [("height", true[0], said[0] if said else None)]
    for index in reversed(range(len(FRACTIONS))):
        name = f"width at {100 * FRACTIONS[index]:.0f}%"
        rows.append((name, true[1][index], said[1][index] if said else None))
    for number, (name, truth, answer) in enumerate(rows, start=1):
        base = 14 + ROW * number
        write(image, name, (columns[0], base), WHITE, 0.4)
        write(image, f"{1000 * truth:6.1f}", (columns[1], base), TRUE, 0.4)
        if answer is not None:
            write(image, f"{1000 * answer:6.1f}", (columns[2], base), SAID, 0.4)
            write(image, f"{1000 * (answer - truth):+6.1f}", (columns[3], base), WHITE, 0.4)
    return image


def _in_mm(shape: tuple[float, np.ndarray]) -> dict:
    height, widths = shape
    return {
        "height_mm": round(1000 * height, 1),
        "widths_mm_bottom_to_top": [round(1000 * float(width), 1) for width in widths],
    }


def _as_stored(numbers: np.ndarray) -> dict:
    """The 17 numbers as SideNet has them: divided down so they sit near 1."""
    return {
        f"height_over_{1000 * HEIGHT_SCALE:.0f}_mm": round(float(numbers[0]), 3),
        f"widths_over_{1000 * WIDTH_SCALE:.0f}_mm": [round(float(number), 3) for number in numbers[1:]],
    }


LEVELS = [f"{100 * fraction:.0f}%" for fraction in FRACTIONS]


# ------------------------------------------------------- the two pictures


def taught(count: int):
    """Each training example: (name, picture, record, numbers). The same ones train.py draws."""
    rng = random.Random(0)
    for seed in range(count):
        glasses = render.scene(seed)
        picked = train.pick_view(glasses, seed, rng)
        if picked is None:
            continue
        index, target, _, angle = picked
        pose = render.side_pose(target.x, target.y, angle)
        side = render.render(glasses, pose)
        net_input, stored = models.side_input(side), models.side_target(glasses[index])
        true = models.side_output(stored)

        given = given_picture(net_input)
        pictures = beside(
            panel("given: the side picture. nearer is brighter", given),
            panel("the 17 true values, drawn where they are", draw_on(given, pose, true, TRUE)),
            panel("the 17 true values to scale, and as numbers", chart(true)),
        )
        lines = [
            f"scene {seed}: glass {index + 1} of {len(glasses)}, a {glasses[index].kind}, seen from place "
            f"{place_number(angle)}. the glass in the middle of the picture is the one to measure",
            (
                TRUE,
                "true answer: the height (thick line), and the width at 16 levels of it (thin lines)",
            ),
        ]
        record = {
            "scene": seed,
            "glass": index + 1,
            "kind": glasses[index].kind,
            "place": place_number(angle),
            "given_to_sidenet": "one 160 x 120 picture: `input` in the .npz beside this file",
            "levels_bottom_to_top": LEVELS,
            "true_answer": _in_mm(true) | {"as_stored": _as_stored(stored)},
        }
        numbers = {"depth": side.depth, "input": net_input, "target": stored}
        yield f"scene-{seed:05d}", above(pictures, foot(lines, pictures.shape[1])), record, numbers


def answered(seed: int, top_net, ranker, side_net):
    """Each glass of one held-out scene that gets measured: (name, picture, record, numbers).

    The same steps run.py takes: find the glasses, rank the places round
    each, and measure from the best one unless the Ranker doubts it.
    """
    glasses = render.scene(seed)
    found = pipeline.find_glasses(render.render(glasses, render.top_pose()), top_net)
    for number, item in enumerate(found, start=1):
        target, others = item.seen, [f.seen for f in found if f is not item]
        ranked = pipeline.rank_views(target, others, ranker)
        if not ranked or ranked[0][0] < pipeline.MIN_SCORE:
            continue
        score, angle = ranked[0]
        index = int(np.argmin([np.hypot(g.x - target.x, g.y - target.y) for g in glasses]))
        side, _, good, _ = judge(glasses, index, target, angle)
        pose = render.side_pose(target.x, target.y, angle)

        net_input, stored = models.side_input(side), models.side_target(glasses[index])
        out = models.predict(side_net, net_input[None])[0]
        true, said = models.side_output(stored), models.side_output(out)
        height_off, width_off = scoring.profile_error(
            pipeline.measure(side, side_net), scoring.true_profile(glasses[index])
        )

        given = given_picture(net_input)
        pictures = beside(
            panel("given: the side picture. nearer is brighter", given),
            panel("the 17 true values, drawn where they are", draw_on(given, pose, true, TRUE)),
            panel("the 17 values SideNet said, drawn where they are", draw_on(given, pose, said, SAID)),
            panel("both to scale, and as numbers", chart(true, said)),
        )
        lines = [
            f"scene {seed}: glass {number} of {len(found)} found, a {glasses[index].kind}, seen from place "
            f"{place_number(angle)} (Ranker's score {score:.2f}). this side picture truly came out "
            f"{'unspoiled' if good else 'SPOILED'}",
            (TRUE, f"true: {1000 * true[0]:.1f} mm tall"),
            (
                SAID,
                f"SideNet said: {1000 * said[0]:.1f} mm tall, {1000 * (said[0] - true[0]):+.1f} mm from true",
            ),
            # pipeline.measure hands over the 16 levels as the profile, and a
            # profile's height is its top level, so the two heights differ.
            f"as run.py scores it: height off by {1000 * height_off:+.1f} mm, width off by "
            f"{1000 * width_off:.1f} mm (the median over the glass). the scored height is the top level, "
            f"{100 * FRACTIONS[-1]:.0f}% of what SideNet said",
        ]
        record = {
            "scene": seed,
            "glass": number,
            "kind": glasses[index].kind,
            "place": place_number(angle),
            "rankers_score": round(score, 3),
            "picture_truly_unspoiled": int(good),
            "given_to_sidenet": "one 160 x 120 picture: `input` in the .npz beside this file",
            "levels_bottom_to_top": LEVELS,
            "true_answer": _in_mm(true) | {"as_stored": _as_stored(stored)},
            "sidenet_said": _in_mm(said) | {"as_stored": _as_stored(out)},
            "off_by": {
                "height_mm": round(1000 * (said[0] - true[0]), 1),
                "widths_mm_bottom_to_top": [round(1000 * float(w), 1) for w in said[1] - true[1]],
                "as_the_run_is_scored": {
                    "height_mm": round(1000 * height_off, 1),
                    "width_mm_median": round(1000 * width_off, 1),
                },
            },
        }
        numbers = {"depth": side.depth, "input": net_input, "output": out, "target": stored}
        name = f"scene-{seed:05d}-glass-{number}"
        yield name, above(pictures, foot(lines, pictures.shape[1])), record, numbers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=["train", "test"])
    parser.add_argument("--scenes", type=int, help="how many; 200 for train and 50 for test if not given")
    arguments = parser.parse_args()
    folder = SAVED / arguments.which
    folder.mkdir(parents=True, exist_ok=True)

    if arguments.which == "train":
        drawn = taught(arguments.scenes or 200)
    else:
        nets = {"top_net": models.TopNet(), "ranker": models.Ranker(), "side_net": models.SideNet()}
        for name, net in nets.items():
            net.load_state_dict(torch.load(train.WEIGHTS / f"{name}.pt"))
        seeds = range(render.TEST_SEEDS, render.TEST_SEEDS + (arguments.scenes or 50))
        drawn = (one for seed in seeds for one in answered(seed, *nets.values()))

    count = 0
    for name, image, record, numbers in drawn:
        cv2.imwrite(str(folder / f"{name}.png"), image)
        (folder / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
        np.savez_compressed(folder / f"{name}.npz", **numbers)
        count += 1
    print(f"{count} pictures saved to {folder}")


if __name__ == "__main__":
    main()
