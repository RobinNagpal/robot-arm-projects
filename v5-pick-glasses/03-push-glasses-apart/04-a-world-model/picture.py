"""One still picture of one step, for trace_table.py.

On the left, the table as the film sees it. On the right, the same table from
above as the arm knows it: the camera's readings, and whatever the model said.
Underneath, in words, what was decided or done.

Everything here is drawn from the dictionaries trace_table.py writes into
trace.json, so lengths are millimetres and angles are degrees.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from bench import FINGER_LENGTH, GLASS_ZONE, GRIP_ROOM, JAW_THICKNESS

WIDTH, HEIGHT = 640, 480
LINE_HEIGHT = 26
MARGIN = 14

# Colours are blue, green, red.
PAPER = (245, 243, 240)
INK = (45, 35, 23)
FAINT = (150, 140, 130)
WOOD = (203, 223, 233)
ROOM = (147, 127, 29)
ROOM_FILL = (241, 236, 211)
CROWDED = (10, 102, 169)
CROWDED_FILL = (195, 228, 246)
MODEL = (79, 32, 179)
JAW = (145, 135, 124)

# The part of the table the drawing shows, in millimetres: the glass zone, and
# room on the arm's side for the jaw to stand behind a glass.
_X = (1000 * GLASS_ZONE[0] - 140, 1000 * GLASS_ZONE[1] + 40)
_Y = (1000 * GLASS_ZONE[2] - 50, 1000 * GLASS_ZONE[3] + 50)
_SCALE = min(WIDTH / (_Y[1] - _Y[0]), HEIGHT / (_X[1] - _X[0]))


def _at(x: float, y: float) -> tuple[int, int]:
    """Table millimetres to a pixel. The arm is at the bottom, its left is on the left."""
    across = (WIDTH - _SCALE * (_Y[1] - _Y[0])) / 2 + _SCALE * (_Y[1] - y)
    return round(across), round(_SCALE * (_X[1] - x))


def _write(image, text: str, at: tuple[int, int], colour=INK, size: float = 0.55, thick: int = 1) -> None:
    cv2.putText(image, text, at, cv2.FONT_HERSHEY_SIMPLEX, size, colour, thick, cv2.LINE_AA)


def _dashed_circle(image, centre: tuple[int, int], radius: int, colour, thick: int = 2) -> None:
    for start in range(0, 360, 30):
        cv2.ellipse(image, centre, (radius, radius), 0, start, start + 18, colour, thick, cv2.LINE_AA)


def _glass(image, glass: dict, outline, fill, thick: int = 2) -> None:
    centre, radius = _at(glass["x"], glass["y"]), round(_SCALE * glass["widest"] / 2)
    if fill is not None:
        cv2.circle(image, centre, radius, fill, -1, cv2.LINE_AA)
    cv2.circle(image, centre, radius, outline, thick, cv2.LINE_AA)
    (wide, tall), _ = cv2.getTextSize(str(glass["id"]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    _write(image, str(glass["id"]), (centre[0] - wide // 2, centre[1] + tall // 2), INK, 0.6, 2)


def _jaw(image, tip: list[float], heading: float) -> None:
    """The closed fingers, behind their tip, pointing the way they push."""
    along = np.array([math.cos(math.radians(heading)), math.sin(math.radians(heading))])
    left = np.array([-along[1], along[0]])
    tip, long, half = np.array(tip), 1000 * FINGER_LENGTH, 1000 * JAW_THICKNESS / 2
    corners = [
        tip + half * left,
        tip - half * left,
        tip - long * along - half * left,
        tip - long * along + half * left,
    ]
    cv2.fillPoly(image, [np.array([_at(*c) for c in corners], np.int32)], JAW, cv2.LINE_AA)


def above(
    glasses: list[dict],
    *,
    rings: bool = False,
    taking: int | None = None,
    pushes: list[tuple[dict, list[float], bool]] = (),
    jaw: tuple[list[float], float] | None = None,
    was: dict | None = None,
) -> np.ndarray:
    """The table from above.

    ``pushes`` are (glass, where the model says it lands, whether it is the
    one chosen). ``was`` is a glass where it stood before the push, drawn
    faint. ``rings`` draws the room each crowded glass needs.
    """
    image = np.full((HEIGHT, WIDTH, 3), PAPER, np.uint8)
    x_min, x_max, y_min, y_max = (1000 * v for v in GLASS_ZONE)
    cv2.rectangle(image, _at(x_max, y_max), _at(x_min, y_min), WOOD, -1)
    _write(image, "the table from above, as the arm knows it", (MARGIN, 20), FAINT, 0.5)
    _write(image, "the arm stands on this side", (MARGIN, HEIGHT - 10), FAINT, 0.5)

    if jaw is not None:
        _jaw(image, *jaw)
    if was is not None:
        _dashed_circle(image, _at(was["x"], was["y"]), round(_SCALE * was["widest"] / 2), FAINT, 1)
    for glass in glasses:
        if rings and not glass["has_room"]:
            _dashed_circle(image, _at(glass["x"], glass["y"]), round(_SCALE * 1000 * GRIP_ROOM), CROWDED, 1)
    for glass in glasses:
        roomy = glass["has_room"]
        _glass(image, glass, ROOM if roomy else CROWDED, ROOM_FILL if roomy else CROWDED_FILL,
               5 if glass["id"] == taking else 2)  # fmt: skip
    for glass, lands, chosen in pushes:
        colour = MODEL if chosen else FAINT
        start = _at(was["x"], was["y"]) if was is not None else _at(glass["x"], glass["y"])
        _dashed_circle(image, _at(*lands), round(_SCALE * glass["widest"] / 2), colour, 2 if chosen else 1)
        cv2.arrowedLine(image, start, _at(*lands), colour, 2 if chosen else 1, cv2.LINE_AA, tipLength=0.18)
    return image


def picture(scene: np.ndarray, drawing: np.ndarray, title: str, lines: list[str]) -> np.ndarray:
    """The film's view and the drawing side by side, with what happened written underneath."""
    words = np.full(
        (MARGIN + LINE_HEIGHT * (1 + len(lines)), scene.shape[1] + drawing.shape[1], 3), PAPER, np.uint8
    )
    _write(words, title, (MARGIN, LINE_HEIGHT), INK, 0.7, 2)
    for row, line in enumerate(lines):
        _write(words, line, (MARGIN, LINE_HEIGHT * (2 + row)), INK, 0.55)
    return np.vstack([np.hstack([scene, drawing]), words])
