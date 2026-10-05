"""Save pictures of what TopNet is taught, and of what it answers.

    pixi run python show_top_net.py train    # the training scenes: what goes in, and the right answer
    pixi run python show_top_net.py test     # the held-out scenes: what goes in, and what TopNet says

Each scene gets a .png to look at, a .npz holding every number behind it, and
a .json with a few pixels written out in full, in saved/top-net/. Nothing here
trains anything: ``test`` uses the weights that ``make train`` left.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import models
import numpy as np
import pipeline
import torch
from drawing import LINE_HEIGHT, WHITE, foot, grey, grid, write
from models import SHRINK, SMALL, VOTE_SCALE
from train import WEIGHTS

import render

SAVED = Path(__file__).parent / "saved" / "top-net"

# Pictures are drawn this many times the size the network sees them at, so
# that one network pixel is a square big enough to see.
ZOOM = 4

# One arrow is drawn per this many pixels each way. Every glass pixel has an
# arrow, and drawn all at once they are a solid smear.
ARROW_EVERY = 3

# Arrow errors of this many pixels or more get the brightest colour.
WORST_ERROR = 4.0

CYAN, MAGENTA = (255, 255, 0), (255, 0, 255)

# One per found glass, blue-green-red as OpenCV wants them.
COLOURS = [
    (80, 80, 255),
    (80, 220, 80),
    (255, 160, 60),
    (60, 220, 255),
    (230, 90, 230),
    (240, 240, 90),
    (150, 150, 255),
    (160, 255, 200),
]


# ------------------------------------------------------------ drawing


def _zoom(image: np.ndarray) -> np.ndarray:
    return cv2.resize(image, None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)


def _place(column: float, row: float) -> tuple[int, int]:
    """Where the middle of a network pixel is in a zoomed picture."""
    return round((column + 0.5) * ZOOM), round((row + 0.5) * ZOOM)


def _cross(image: np.ndarray, column: float, row: float) -> None:
    cv2.drawMarker(image, _place(column, row), WHITE, cv2.MARKER_CROSS, 14, 1, cv2.LINE_AA)


def height_picture(net_input: np.ndarray) -> np.ndarray:
    """The first of TopNet's three input pictures: height above the table.

    The other two hold each pixel's row and column, which are the same ramps
    in every scene, so they are not drawn.
    """
    # The square root lifts a short glass out of the dark without changing
    # which pixel is higher than which.
    return grey(np.sqrt(np.clip(net_input[0], 0.0, 1.0)))


def _direction_colours(across: np.ndarray, down: np.ndarray) -> np.ndarray:
    """A colour for the way each arrow points: the hue goes round with the angle."""
    hue = ((np.arctan2(down, across) + math.pi) / (2 * math.pi) * 179).astype(np.uint8)
    full = np.full_like(hue, 255)
    return cv2.cvtColor(np.stack([hue, full, full], -1), cv2.COLOR_HSV2BGR)


def direction_picture(glass: np.ndarray, across: np.ndarray, down: np.ndarray) -> np.ndarray:
    """Every glass pixel, coloured by the way its arrow points."""
    image = _direction_colours(across, down)
    image[~glass] = 0
    image = _zoom(image)

    # The key, bottom left: the colour a pixel gets for each of four ways.
    ways = [("left", -1, 0), ("right", 1, 0), ("above", 0, -1), ("below", 0, 1)]
    for number, (name, across_, down_) in enumerate(ways):
        colour = _direction_colours(np.float32([[across_]]), np.float32([[down_]]))[0, 0].tolist()
        top = image.shape[0] - LINE_HEIGHT * (len(ways) - number) - 4
        cv2.rectangle(image, (8, top), (22, top + 14), colour, -1)
        write(image, f"the middle is {name if across_ == 0 else 'to the ' + name}", (30, top + 12))
    return image


def arrow_picture(
    net_input: np.ndarray, glass: np.ndarray, across: np.ndarray, down: np.ndarray
) -> np.ndarray:
    """Some of the glass pixels' arrows, drawn over a dimmed height picture."""
    image = _zoom(height_picture(net_input) // 2)
    colours = _direction_colours(across, down)
    for row in range(0, SMALL[0], ARROW_EVERY):
        for column in range(0, SMALL[1], ARROW_EVERY):
            if glass[row, column]:
                tip = _place(column + across[row, column], row + down[row, column])
                colour = colours[row, column].tolist()
                cv2.arrowedLine(image, _place(column, row), tip, colour, 1, cv2.LINE_AA, tipLength=0.2)
    return image


# ------------------------------------------------- a few pixels in full


def _arrow(across: float, down: float, row: int, column: int) -> dict:
    """One pixel's arrow, as stored and as the pixel it ends on."""
    return {
        "across": round(float(across), 3),
        "down": round(float(down), 3),
        "in_pixels": {
            "right": round(float(across) * VOTE_SCALE, 1),
            "down": round(float(down) * VOTE_SCALE, 1),
        },
        "so_the_middle_is_at": {
            "row": round(row + float(down) * VOTE_SCALE, 1),
            "column": round(column + float(across) * VOTE_SCALE, 1),
        },
    }


def sample_pixels(picture: render.Picture, net_input: np.ndarray, target: np.ndarray, out=None) -> list[dict]:
    """A few pixels written out in full, so that the grids can be read by eye.

    Three on glass and one off it, the same ones every time. ``out`` is
    TopNet's answer, if there is one to set beside the true answer.
    """
    glass, other = np.argwhere(target[0] > 0.5), np.argwhere(target[0] < 0.5)
    chosen = [glass[len(glass) * part // 4] for part in (1, 2, 3)] + [other[len(other) // 2]]
    pixels = []
    for number, (row, column) in enumerate(chosen, start=1):
        row, column = int(row), int(column)
        depth = picture.depth[row * SHRINK, column * SHRINK]
        is_glass = bool(target[0, row, column] > 0.5)
        pixel = {
            "pixel": number,
            "row": row,
            "column": column,
            "given_to_topnet": {
                "height": round(float(net_input[0, row, column]), 3),
                "row": round(float(net_input[1, row, column]), 3),
                "column": round(float(net_input[2, row, column]), 3),
                "height_in_mm": round(1000 * (render.TOP_HEIGHT - depth)) if np.isfinite(depth) else None,
            },
            "true_answer": {
                "glass": int(is_glass),
                # Off the glass the arrow is never marked, so it is left out.
                "arrow": _arrow(target[1, row, column], target[2, row, column], row, column)
                if is_glass
                else None,
            },
        }
        if out is not None:
            pixel["topnet_said"] = {
                "glass_score": round(float(out[0, row, column]), 3),
                "glass_chance": round(float(1 / (1 + np.exp(-out[0, row, column]))), 3),
                "arrow": _arrow(out[1, row, column], out[2, row, column], row, column),
            }
        pixels.append(pixel)
    return pixels


def _number(image: np.ndarray, pixels: list[dict]) -> np.ndarray:
    """Ring and number the sample pixels, so the .json can be matched to the picture."""
    for pixel in pixels:
        column, row = _place(pixel["column"], pixel["row"])
        cv2.circle(image, (column, row), 5, (0, 0, 255), 1, cv2.LINE_AA)
        cv2.putText(
            image, str(pixel["pixel"]), (column + 7, row + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1
        )
    return image


GIVEN = "given: height, brighter is higher. red rings: the pixels in the .json"


# ------------------------------------------------------- the two pictures


def taught_picture(seed: int) -> tuple[np.ndarray, dict, list[dict]]:
    """One training scene: what TopNet is given, and the answer it is marked against."""
    glasses = render.scene(seed)
    picture = render.render(glasses, render.top_pose())
    net_input, target = models.top_input(picture), models.top_target(picture, glasses)
    glass = target[0] > 0.5
    across, down = target[1] * VOTE_SCALE, target[2] * VOTE_SCALE
    pixels = sample_pixels(picture, net_input, target)

    arrows = arrow_picture(net_input, glass, across, down)
    for one in glasses:
        _cross(arrows, *models.rim_middle(picture, one))
    image = grid(
        [
            [
                (GIVEN, _number(_zoom(height_picture(net_input)), pixels)),
                ("answer 1: is this pixel glass? white is yes", _zoom(grey(target[0]))),
            ],
            [
                (
                    "answer 2: which way its glass's middle is, as a colour",
                    direction_picture(glass, across, down),
                ),
                ("answer 2 again, as arrows. crosses: the true middles", arrows),
            ],
        ]
    )
    numbers = {"depth": picture.depth, "ids": picture.ids, "input": net_input, "target": target}
    return image, numbers, pixels


def answered_picture(seed: int, top_net) -> tuple[np.ndarray, dict, list[dict]]:
    """One held-out scene: what TopNet is given, what it says, and what is made of that."""
    glasses = render.scene(seed)
    picture = render.render(glasses, render.top_pose())
    net_input, target = models.top_input(picture), models.top_target(picture, glasses)
    votes = pipeline.cast_votes(picture, top_net)
    found = pipeline.gather(picture, votes)

    out = votes.out
    said, truly = out[0] > 0, target[0] > 0.5
    across, down = out[1] * VOTE_SCALE, out[2] * VOTE_SCALE
    pixels = sample_pixels(picture, net_input, target, out)

    tally = cv2.applyColorMap(
        np.clip(votes.tally / max(votes.tally.max(), 1.0) * 255, 0, 255).astype(np.uint8),
        cv2.COLORMAP_INFERNO,
    )
    tally = _zoom(tally)
    for row, column in votes.middles:
        cv2.circle(tally, _place(column, row), pipeline.MIDDLE_RADIUS * ZOOM, WHITE, 1, cv2.LINE_AA)

    glasses_found = height_picture(net_input) // 3
    for index, one in enumerate(found):
        rows, columns = (one.pixels // SHRINK).T
        glasses_found[rows, columns] = COLOURS[index % len(COLOURS)]
    glasses_found = _zoom(glasses_found)
    for index, one in enumerate(found):
        row, column = (one.pixels // SHRINK).mean(0)
        column, row = _place(column, row)
        cv2.putText(
            glasses_found, str(index + 1), (column - 5, row + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2
        )
    for one in glasses:
        _cross(glasses_found, *models.rim_middle(picture, one))

    miss = np.hypot(across - target[1] * VOTE_SCALE, down - target[2] * VOTE_SCALE)
    error = cv2.applyColorMap(
        np.clip(miss / WORST_ERROR * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO
    )
    error[~truly] = 0
    error[said & ~truly] = CYAN
    error[truly & ~said] = MAGENTA
    error_title = f"arrow error: black 0, yellow {WORST_ERROR:.0f}+ px. cyan: wrongly glass, magenta: missed"

    image = grid(
        [
            [
                (GIVEN, _number(_zoom(height_picture(net_input)), pixels)),
                ("TopNet says: the chance each pixel is glass", _zoom(grey(1 / (1 + np.exp(-out[0]))))),
                (
                    "TopNet says: the way to the middle, for pixels it calls glass",
                    arrow_picture(net_input, said, across, down),
                ),
            ],
            [
                ("where the arrows land. circles: the middles picked", tally),
                ("the glasses found, one colour each. crosses: the true middles", glasses_found),
                (error_title, _zoom(error)),
            ],
        ]
    )

    # Under the pictures: each found glass beside the true glass nearest to it.
    lines = [f"scene {seed}: {len(glasses)} {glasses[0].kind} put out, {len(found)} found"]
    for index, one in enumerate(found):
        true = min(glasses, key=lambda g, one=one: math.dist((g.x, g.y), (one.seen.x, one.seen.y)))
        off = 1000 * math.dist((true.x, true.y), (one.seen.x, one.seen.y))
        seen = one.seen
        lines.append(
            f"glass {index + 1}: at x {seen.x:.3f} y {seen.y:.3f} m, {2000 * seen.radius:.0f} mm wide."
            f"   true: x {true.x:.3f} y {true.y:.3f} m, {2000 * true.max_radius:.0f} mm wide."
            f"   {off:.1f} mm from the true place"
        )
    numbers = {
        "input": net_input,
        "output": out,
        "target": target,
        "tally": votes.tally,
        "middles": np.array(votes.middles).reshape(-1, 2),
        "found": np.array([[f.seen.x, f.seen.y, f.seen.radius] for f in found]).reshape(-1, 3),
        "truth": np.array([[g.x, g.y, g.max_radius] for g in glasses]),
    }
    return np.vstack([image, foot(lines, image.shape[1])]), numbers, pixels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=["train", "test"])
    parser.add_argument("--scenes", type=int, help="how many; 200 for train and 50 for test if not given")
    arguments = parser.parse_args()

    if arguments.which == "train":
        first, count, draw = 0, arguments.scenes or 200, taught_picture
    else:
        top_net = models.TopNet()
        top_net.load_state_dict(torch.load(WEIGHTS / "top_net.pt"))
        first, count = render.TEST_SEEDS, arguments.scenes or 50

        def draw(seed):
            return answered_picture(seed, top_net)

    folder = SAVED / arguments.which
    folder.mkdir(parents=True, exist_ok=True)
    for seed in range(first, first + count):
        image, numbers, pixels = draw(seed)
        cv2.imwrite(str(folder / f"scene-{seed:05d}.png"), image)
        np.savez_compressed(folder / f"scene-{seed:05d}.npz", **numbers)
        (folder / f"scene-{seed:05d}.json").write_text(json.dumps(pixels, indent=2) + "\n")
    print(f"{count} scenes saved to {folder}")


if __name__ == "__main__":
    main()
