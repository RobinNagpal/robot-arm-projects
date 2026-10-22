"""The small drawing helpers show_top_net.py and show_ranker.py share."""

from __future__ import annotations

import cv2
import numpy as np

TITLE_HEIGHT = 26
LINE_HEIGHT = 22
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def write(image: np.ndarray, text: str, at: tuple[int, int], colour=WHITE, size: float = 0.5) -> None:
    cv2.putText(image, text, at, cv2.FONT_HERSHEY_SIMPLEX, size, colour, 1, cv2.LINE_AA)


def tag(image: np.ndarray, text: str, at: tuple[int, int], colour=WHITE) -> None:
    """Text on a black patch, for a label that has to be read over a busy drawing."""
    (width, height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(image, (at[0] - 2, at[1] - height - 3), (at[0] + width + 2, at[1] + 4), BLACK, -1)
    write(image, text, at, colour)


def grey(values: np.ndarray) -> np.ndarray:
    """A picture of numbers between 0 and 1."""
    return cv2.cvtColor(np.clip(values * 255, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def panel(title: str, image: np.ndarray) -> np.ndarray:
    strip = np.zeros((TITLE_HEIGHT, image.shape[1], 3), np.uint8)
    write(strip, title, (6, 18))
    return np.vstack([strip, image])


def beside(*images: np.ndarray) -> np.ndarray:
    """Side by side, the shorter ones padded with black underneath."""
    tall = max(image.shape[0] for image in images)
    return np.hstack([cv2.copyMakeBorder(i, 0, tall - i.shape[0], 0, 0, cv2.BORDER_CONSTANT) for i in images])


def above(*images: np.ndarray) -> np.ndarray:
    """One over the other, the narrower ones padded with black on the right."""
    wide = max(image.shape[1] for image in images)
    return np.vstack([cv2.copyMakeBorder(i, 0, 0, 0, wide - i.shape[1], cv2.BORDER_CONSTANT) for i in images])


def grid(rows: list[list[tuple[str, np.ndarray]]]) -> np.ndarray:
    return above(*[beside(*[panel(title, image) for title, image in row]) for row in rows])


def foot(lines: list, width: int) -> np.ndarray:
    """Lines of text to go under a picture. A line may be (colour, text) to get a swatch."""
    strip = np.zeros((LINE_HEIGHT * len(lines) + 8, width, 3), np.uint8)
    for number, line in enumerate(lines):
        base = LINE_HEIGHT * (number + 1) - 4
        if isinstance(line, tuple):
            colour, line = line
            cv2.rectangle(strip, (6, base - 12), (20, base + 2), colour, -1)
            write(strip, line, (28, base))
        else:
            write(strip, line, (6, base))
    return strip
