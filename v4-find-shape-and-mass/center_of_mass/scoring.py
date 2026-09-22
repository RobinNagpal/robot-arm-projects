"""Matching the model's guesses to the true blocks, and how far off each guess is.

No Ultralytics in here, so the tests can check it on made-up guesses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .scene import unproject


@dataclass(frozen=True)
class Guess:
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in pixels
    class_id: int
    confidence: float
    point: tuple[float, float]  # the centre of mass, in pixels


@dataclass(frozen=True)
class Truth:
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in pixels
    class_id: int
    point: tuple[float, float]  # the labelled point on the top face, in pixels
    centre_of_mass: tuple[float, float, float]  # on the table, metres
    height: float  # of the block's top face, metres


@dataclass(frozen=True)
class Scored:
    truth: Truth
    guess: Guess | None  # None when the model did not find the block
    pixels: float | None = None  # model's point to true point
    millimetres: float | None = None  # the same, on the table
    box_centre_pixels: float | None = None  # middle of the model's box to true point
    box_centre_millimetres: float | None = None


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return 0.0
    overlap = width * height
    return overlap / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap)


def match(truths: list[Truth], guesses: list[Guess], min_iou: float) -> tuple[list[Scored], list[Guess]]:
    """Each true block paired with at most one guess, and the guesses left over.

    The surest guesses pick first, each taking the free true block its box
    overlaps most. The class is not part of matching, so a block found with
    the wrong class still has its point scored; the class is reported apart.
    """
    free = set(range(len(truths)))
    paired: dict[int, Guess] = {}
    extra = []
    for guess in sorted(guesses, key=lambda g: -g.confidence):
        best = max(free, key=lambda i: iou(truths[i].box, guess.box), default=None)
        if best is not None and iou(truths[best].box, guess.box) >= min_iou:
            paired[best] = guess
            free.remove(best)
        else:
            extra.append(guess)
    return [score(truth, paired.get(i)) for i, truth in enumerate(truths)], extra


def score(truth: Truth, guess: Guess | None) -> Scored:
    if guess is None:
        return Scored(truth, None)
    x0, y0, x1, y1 = guess.box
    box_centre = ((x0 + x1) / 2, (y0 + y1) / 2)
    return Scored(
        truth,
        guess,
        pixels=math.dist(guess.point, truth.point),
        millimetres=on_table_error(guess.point, truth),
        box_centre_pixels=math.dist(box_centre, truth.point),
        box_centre_millimetres=on_table_error(box_centre, truth),
    )


def on_table_error(pixel: tuple[float, float], truth: Truth) -> float:
    """How far, in millimetres on the table, ``pixel`` is from the true centre of mass.

    The pixel is taken back to the height of the block's top face, since the
    point marks the top face. What an arm needs is where on the table to
    reach, so only the across-the-table distance counts.
    """
    x, y = unproject(pixel, truth.height)
    return 1000 * math.dist((x, y), truth.centre_of_mass[:2])


def summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "mean": sum(ordered) / len(ordered),
        "median": ordered[len(ordered) // 2],
        "90%": ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))],
        "max": ordered[-1],
    }
