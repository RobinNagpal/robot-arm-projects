"""Shared look for the problem-2 diagrams.

One module so that nine separately written scripts produce pictures that sit
beside each other without looking like nine different documents. Import it,
call ``new``/``save``, and use the colour names rather than literals.

    from diagram_style import GLASS, GOOD, INK, MUTED, WARN, bare, new, save

Every script in this folder writes into ``images/problem-2/`` and is run from
the project root:

    pixi run python docs/problem-2/make_01_images.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

IMAGES = Path(__file__).resolve().parents[2] / "images" / "problem-2"

# The palette the rest of the project's diagrams use.
INK = "#22272e"      # text, and anything structural
MUTED = "#8b949e"    # captions, and things in the background
GLASS = "#4c8fd6"    # the object being reasoned about
WARN = "#d9694b"     # the failure, the thing going wrong
GOOD = "#5aa469"     # the fix, the thing going right
PAPER = "#ffffff"

TITLE_SIZE = 12
LABEL_SIZE = 9
NOTE_SIZE = 8.4


def new(width: float, height: float, columns: int = 1):
    """A figure with a white background, and one or more bare panels."""
    figure, axes = plt.subplots(1, columns, figsize=(width, height))
    figure.patch.set_facecolor(PAPER)
    for axis in (axes if columns > 1 else [axes]):
        axis.set_facecolor(PAPER)
    return figure, axes


def bare(axis) -> None:
    """No ticks, no frame. Most of these pictures are drawings, not plots."""
    axis.set_xticks([])
    axis.set_yticks([])
    for side in axis.spines.values():
        side.set_visible(False)


def save(figure, name: str) -> Path:
    """Write into images/problem-2/ and say where it went."""
    IMAGES.mkdir(parents=True, exist_ok=True)
    path = IMAGES / name
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor=PAPER)
    plt.close(figure)
    print(f"wrote images/problem-2/{name}")
    return path
