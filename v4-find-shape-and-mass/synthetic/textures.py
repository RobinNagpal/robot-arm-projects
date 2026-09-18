"""Pictures to paint the table and the floor with.

A plain grey table teaches a model that a shape is whatever is not grey. Real
tables have grain, stains, joints and printed patterns, and some of those
have straight edges and corners of their own. So the table and the floor are
painted with a pattern.

A texture is fixed by its pattern and its number: the number seeds both the
pattern and its two colours. It is written to a PNG once, and the table's
model points at that file.
"""

from __future__ import annotations

import colorsys
from pathlib import Path

import cv2
import numpy as np

from .randomization import Surface

SIDE = 512  # pixels


def texture(pattern: str, number: int) -> np.ndarray:
    """Texture ``number`` of ``pattern`` as an RGB image, SIDE by SIDE pixels, values 0 to 255."""
    rng = np.random.default_rng([_pattern_id(pattern), number])
    a, b = _two_colours(rng)
    mix = PATTERNS[pattern](rng)  # 0 means colour a, 1 means colour b
    image = a * (1 - mix[..., None]) + b * mix[..., None]
    return np.clip(image * 255, 0, 255).astype(np.uint8)


def texture_file(surface: Surface, folder: Path) -> Path | None:
    """The PNG to paint ``surface`` with, written the first time it is asked for. None for a plain surface."""
    if surface.pattern == "plain":
        return None
    path = folder / f"{surface.pattern}-{surface.texture:02d}.png"
    if not path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), cv2.cvtColor(texture(surface.pattern, surface.texture), cv2.COLOR_RGB2BGR))
    return path


def _pattern_id(pattern: str) -> int:
    # Python's hash() of a string changes between runs, so it cannot seed anything.
    return sorted(PATTERNS).index(pattern)


def _two_colours(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    hue = rng.random()
    # Close hues most of the time, like wood or stone; sometimes not, like a printed cloth.
    other_hue = (hue + (rng.uniform(-0.08, 0.08) if rng.random() < 0.7 else rng.random())) % 1.0
    a = colorsys.hsv_to_rgb(hue, rng.uniform(0.0, 0.6), rng.uniform(0.3, 0.9))
    b = colorsys.hsv_to_rgb(other_hue, rng.uniform(0.0, 0.6), rng.uniform(0.15, 0.9))
    return np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)


def _blurred_noise(rng: np.random.Generator, cells: int) -> np.ndarray:
    """Smooth random values between 0 and 1, varying over about ``cells`` blobs across."""
    small = rng.random((cells, cells)).astype(np.float32)
    return cv2.resize(small, (SIDE, SIDE), interpolation=cv2.INTER_CUBIC).clip(0, 1)


def _wood(rng: np.random.Generator) -> np.ndarray:
    y = np.linspace(0, 1, SIDE, dtype=np.float32)[:, None]
    wobble = 0.08 * _blurred_noise(rng, 5)
    rings = rng.uniform(15, 40)
    return 0.5 + 0.5 * np.sin(2 * np.pi * rings * (y + wobble))


def _checker(rng: np.random.Generator) -> np.ndarray:
    squares = int(rng.integers(4, 16))
    y, x = np.mgrid[0:SIDE, 0:SIDE] * squares // SIDE
    return ((x + y) % 2).astype(np.float32)


def _speckle(rng: np.random.Generator) -> np.ndarray:
    dots = (rng.random((SIDE, SIDE)) < rng.uniform(0.05, 0.3)).astype(np.float32)
    return 0.8 * dots + 0.2 * _blurred_noise(rng, 8)


def _stripes(rng: np.random.Generator) -> np.ndarray:
    stripes = rng.uniform(4, 20)
    angle = rng.uniform(0, np.pi)
    y, x = np.mgrid[0:SIDE, 0:SIDE].astype(np.float32) / SIDE
    along = x * np.cos(angle) + y * np.sin(angle)
    return (np.sin(2 * np.pi * stripes * along) > 0).astype(np.float32)


def _tiles(rng: np.random.Generator) -> np.ndarray:
    # Only in the unseen test set: a grid of grout lines, full of straight
    # edges and right-angled corners that are not a square.
    tiles = int(rng.integers(3, 8))
    grout = max(3, SIDE // (tiles * 25))
    y, x = np.mgrid[0:SIDE, 0:SIDE]
    lines = ((x % (SIDE // tiles)) < grout) | ((y % (SIDE // tiles)) < grout)
    return 0.9 * lines.astype(np.float32) + 0.1 * _blurred_noise(rng, 10)


def _marble(rng: np.random.Generator) -> np.ndarray:
    # Only in the unseen test set: soft veins that run in no one direction.
    y, x = np.mgrid[0:SIDE, 0:SIDE].astype(np.float32) / SIDE
    turbulence = _blurred_noise(rng, 4) + 0.5 * _blurred_noise(rng, 12)
    return (0.5 + 0.5 * np.sin(2 * np.pi * (3 * x + 2 * y + 2.5 * turbulence))) ** 3


PATTERNS = {
    "wood": _wood,
    "checker": _checker,
    "speckle": _speckle,
    "stripes": _stripes,
    "tiles": _tiles,
    "marble": _marble,
}
