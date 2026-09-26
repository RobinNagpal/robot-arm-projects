"""Shared look for the problem-2 diagrams.

One module so that nine separately written scripts produce pictures that sit
beside each other without looking like nine different documents. Import it,
call ``new``/``save``, and use the colour names rather than literals.

    from diagram_style import GLASS, GOOD, INK, MUTED, WARN, bare, new, save

Every script in this folder writes into ``images/problem-2/`` and is run from
the project root:

    pixi run python images/generators/problem-2/make_01_images.py
"""

from __future__ import annotations

import numpy as np

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

IMAGES = Path(__file__).resolve().parents[3] / "images" / "problem-2"

# The palette the rest of the project's diagrams use.
INK = "#22272e"      # text, and anything structural
MUTED = "#8b949e"    # captions, and things in the background
GLASS = "#4c8fd6"    # the object being reasoned about
WARN = "#d9694b"     # the failure, the thing going wrong
GOOD = "#5aa469"     # the fix, the thing going right
PAPER = "#ffffff"

# The cast of glasses these diagrams draw, in millimetres.
#
# Problem 2 puts several glasses of ONE kind on the table, and the whole
# difficulty comes from how wide that kind's range of sizes is: the tall end is
# more than twice the height of the short end. A diagram drawn with glasses of
# similar size shows a problem this cell does not have, so every scene here is
# built from a mixture — a couple of large glasses and a couple of the smallest
# the kind allows.
#
# These follow glasses/shapes.py KIND_RANGES["tapered_glass"]: 90-230 mm tall
# and 65-105 mm across the rim. TALL_A and TALL_B sit near the top of that
# range, SHORT_A and SHORT_B near the bottom, and none of them is outside it.
TALL_A = (225.0, 102.0)      # height, width across the rim
TALL_B = (208.0, 96.0)
SHORT_A = (95.0, 67.0)
SHORT_B = (108.0, 71.0)

# The kind's own limits, for anything that draws the range itself.
KIND_TALLEST = 230.0
KIND_SHORTEST = 90.0
KIND_WIDEST = 105.0
KIND_NARROWEST = 65.0

# A scene with a couple of each, which is what most of these pictures want.
CAST = (TALL_A, SHORT_A, TALL_B, SHORT_B)

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


# --------------------------------------------------------------------------- #
# splay: what a camera looking straight down does to a standing glass
# --------------------------------------------------------------------------- #

SURVEY_H = 450.0     # mm above the table, the height the survey looks from
FX = 277.1           # pixels; the camera's focal length


def splay_circles(nadir, centre, height, rim, base_fraction=0.45, slices=40, survey_h=SURVEY_H):
    """The stack of circles a standing glass draws in an overhead picture.

    A slice of the glass at height z is imaged as if it were scaled about the
    point directly below the camera by H / (H - z), because that slice is nearer
    the lens than the table is. The silhouette is the union of those circles, so
    returning them as a list is enough to draw it, to test whether one glass
    covers another, and to measure how wide the patch is.

    Everything is in millimetres on the table, measured from ``nadir``.
    """
    offset = np.asarray(centre, dtype=float) - np.asarray(nadir, dtype=float)
    rim_r, base_r = rim / 2.0, rim / 2.0 * base_fraction
    out = []
    for i in range(slices):
        z = height * i / (slices - 1)
        k = survey_h / (survey_h - z)
        r = base_r + (rim_r - base_r) * (i / (slices - 1))
        out.append((offset * k, r * k))
    return out


def splay_covers(big, small):
    """Is every point of ``small``'s silhouette inside ``big``'s?

    Both arguments are lists from splay_circles. This is the test behind the
    headline difficulty of problem 2: when it is true, the short glass appears
    in no picture at all.
    """
    for c, r in small:
        for angle in np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False):
            p = c + r * np.array([np.cos(angle), np.sin(angle)])
            if not any(np.hypot(*(p - cb)) <= rb + 1e-9 for cb, rb in big):
                return False
    return True


def splay_patch(axis, circles, colour=None, alpha=0.30, edge=None, lw=0.0, zorder=3, scale=1.0):
    """Draw a splayed silhouette as its stack of circles."""
    from matplotlib.patches import Circle as _Circle
    colour = colour or GLASS
    for c, r in circles:
        axis.add_patch(_Circle(tuple(c * scale), r * scale, facecolor=colour, alpha=alpha,
                               edgecolor=edge or "none", lw=lw, zorder=zorder))


def splay_width(circles):
    """How wide the silhouette is, in millimetres of table."""
    xs = [c[0] - r for c, r in circles] + [c[0] + r for c, r in circles]
    ys = [c[1] - r for c, r in circles] + [c[1] + r for c, r in circles]
    return max(max(xs) - min(xs), max(ys) - min(ys))
