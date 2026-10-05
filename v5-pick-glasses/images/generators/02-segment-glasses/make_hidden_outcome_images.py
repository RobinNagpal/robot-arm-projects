"""Diagrams for solution 6 — learn which viewpoints pay off.

Run from the project root:

    pixi run python images/generators/02-segment-glasses/make_hidden_outcome_images.py

Every picture here is drawn from the numbers in
``docs/02-segment-glasses/06-learn-which-viewpoints-pay-off.md``. Nothing is measured
from a run, and the accuracy panel is marked illustrative on the picture
itself, because it is the shape of an argument rather than a result.

Plan views are drawn with the table's y axis flipped, so the working zone sits
above the arm base on the page. The cell's own y values are negative.

The two hidden-glass pictures are the exception to "drawn from the numbers in
the document": every silhouette in them is a real projection of one of the
project's own glass outlines, taken from ``work_cell.glasses.shapes``, through
the cell's own camera. The numbers those two functions print are the numbers
the document quotes.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PAPER,
    TITLE_SIZE,
    WARN,
    bare,
    save,
)
from matplotlib.patches import Circle, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import family  # noqa: E402

# The cell, in millimetres. The arm base is the origin; the drawings put it at
# the bottom of the page and measure upwards.
REACH_MIN = 300.0
REACH_MAX = 780.0
STANDOFF = 380.0
FX = 277.1

# The two places the camera works from, and the frame it works in.
SURVEY_H = 450.0            # looking straight down, from 450 mm up
VIEW_HEIGHT = 120.0         # looking level, from 120 mm up
FRAME_W, FRAME_H = 320, 240
MIN_SEPARATION = 150.0      # centre to centre, from glasses/spawn.py

# How much table one survey frame holds, measured out from the nadir.
FRAME_HALF_X = FRAME_W / 2 * SURVEY_H / FX
FRAME_HALF_Y = FRAME_H / 2 * SURVEY_H / FX



SURVIVORS = [60.0, 75.0, 90.0, 105.0, 120.0, 135.0, -120.0, -135.0]
PAYOFF = {120.0: 0.88, 135.0: 0.81, 105.0: 0.79, 90.0: 0.62,
          75.0: 0.44, -120.0: 0.21, 60.0: 0.12, -135.0: 0.07}
DOUBT_DROP = {-135.0: 0.71, 120.0: 0.58, 105.0: 0.52, 135.0: 0.44,
              90.0: 0.39, 75.0: 0.30, -120.0: 0.22, 60.0: 0.19}
GAP_NEEDED_PX = 10.0        # a fit needs daylight between the two, not a touching pair
ZONE = (270.0, 300.0, 320.0, 360.0)      # the 320 x 360 mm zone the glasses stand in
SPAWNED = [
    ((290.0, 330.0), 30.0),
    ((560.0, 330.0), 38.0),
    ((330.0, 600.0), 34.0),
    ((430.0, 430.0), 36.0),              # these last two merge from the survey's line
    ((500.0, 565.0), 33.0),
]
MERGED = ((465.0, 497.5), 110.0)         # what the one-circle fit returns for the pair
FEATURE_GROUPS = [
    ("the pair the fit proposed", 5, [
        "diameter of the one-circle fit",
        "the two diameters of the two-circle fit",
        "their separation, in fitted radii",
        "how much worse the one circle fits",
    ]),
    ("the candidate against the pair", 4, [
        "angle between the line of sight and the join line",
        "the sine of that angle",
        "predicted separation, in pixels",
        "predicted overlap, in pixels",
    ]),
    ("the candidate against everything else", 5, [
        "how close the ray passes to each of the three",
        "nearest clusters, in that cluster's own radii",
        "how many clusters fall inside the wedge",
    ]),
    ("the arm", 3, [
        "reach: camera to base, against 300 and 780 mm",
        "standoff, and height above the table",
    ]),
    ("what has already been looked at", 3, [
        "angle from the nearest view already taken",
        "how many views this cluster has",
        "how many looks the budget has left",
    ]),
]
EIGHT = [
    ((300.0, 340.0), 30.0), ((470.0, 315.0), 34.0), ((620.0, 360.0), 37.0),
    ((330.0, 490.0), 32.0), ((480.0, 470.0), 36.0), ((610.0, 520.0), 33.0),
    ((370.0, 640.0), 35.0), ((540.0, 645.0), 31.0),
]
_FAMILY = family("tapered_glass", 60, 7)
_BY_HEIGHT = sorted(_FAMILY, key=lambda item: item[0].total_height)
SHORT_GLASS, SHORT_PROPS = _BY_HEIGHT[0]
TALL_GLASS, TALL_PROPS = _BY_HEIGHT[-1]
TALL_OUT = 280.0
SHORT_OUT = TALL_OUT + MIN_SEPARATION

def _plan(axis, xlim=(-40, 900), ylim=(-120, 820)) -> None:
    """A bare, equal-aspect panel in table millimetres."""
    bare(axis)
    axis.set_xlim(*xlim)
    axis.set_ylim(*ylim)
    axis.set_aspect("equal")


def _base(axis, x=430.0, y=0.0, label=True) -> None:
    axis.plot(x, y, marker="^", ms=9, color=INK, zorder=6)
    if label:
        axis.text(x, y - 38, "arm base", ha="center", fontsize=NOTE_SIZE, color=INK)


def _reach_band(axis, x=430.0, y=0.0, label=True) -> None:
    for radius in (REACH_MIN, REACH_MAX):
        axis.add_patch(Circle((x, y), radius, fill=False, ec=MUTED, lw=0.9, ls=(0, (5, 4))))
    if label:
        axis.text(
            x, y + REACH_MAX + 14, "comfortable reach, 300 to 780 mm",
            ha="center", fontsize=NOTE_SIZE, color=MUTED,
        )


def _camera(axis, at, target, colour, style="-", lw=1.3, ms=8) -> None:
    axis.plot([at[0], target[0]], [at[1], target[1]], color=colour, lw=lw, ls=style, zorder=3)
    axis.plot(*at, marker="s", ms=ms, color=colour, zorder=6)


# ---------------------------------------------------------------- the scene
#
# One arrangement, used by several of the pictures below so that the reader
# can carry the geometry from one to the next.
#
# The ambiguous cluster stands 470 mm from the base. Two glasses hide inside
# it, 168 mm apart along a line running up and to the left. One neighbour
# stands off to the side and blocks a few of the candidate rays.

BASE = (430.0, 0.0)
CLUSTER = (430.0, 470.0)
JOIN_DEG = 30.0                                   # the join line, in degrees off the radial
JOIN = (math.sin(math.radians(JOIN_DEG)), math.cos(math.radians(JOIN_DEG)))
GLASS_A = (CLUSTER[0] + 84 * JOIN[0], CLUSTER[1] + 84 * JOIN[1])   # 76 mm across
GLASS_B = (CLUSTER[0] - 84 * JOIN[0], CLUSTER[1] - 84 * JOIN[1])   # 71 mm across
RADIUS_A, RADIUS_B = 38.0, 35.5

# One neighbour, 185 mm from the cluster and centred on the minus-75-degree
# candidate. It subtends 15.7 degrees either side, so it blocks exactly three
# of the 24 directions.
NEIGHBOUR = (
    CLUSTER[0] + 185 * math.sin(math.radians(-75.0)),
    CLUSTER[1] + 185 * math.cos(math.radians(-75.0)),
)
NEIGHBOUR_RADIUS = 52.0

# The 24 standoff directions, and what happens to each of them.
ALL_THETAS = [float(t) for t in range(-180, 180, 15)]
BLOCKED = (-60.0, -75.0, -90.0)          # the ray passes through the neighbour
NO_IK = (-105.0,)                        # setFromIK finds no arm pose
SEEN_FROM = 60.0                         # the survey already looked from here

GLASS_HEIGHT = 160.0


def _pose(theta_deg: float):
    """Camera position for a standoff direction ``theta`` degrees off the radial."""
    theta = math.radians(theta_deg)
    return (CLUSTER[0] + STANDOFF * math.sin(theta), CLUSTER[1] + STANDOFF * math.cos(theta))


def _reach_of(pose) -> float:
    return math.hypot(pose[0] - BASE[0], pose[1] - BASE[1])


def _silhouette(axis, pose, glass, radius, colour, alpha=0.9, target=None):
    """Draw one glass as the camera at ``pose`` would see it, in a 320 x 240 frame.

    Returns the centre column and half width in pixels, so the caller can say
    whether two silhouettes touch.
    """
    aim = CLUSTER if target is None else target
    look = np.array([aim[0] - pose[0], aim[1] - pose[1]], dtype=float)
    look /= np.hypot(*look)
    side = np.array([-look[1], look[0]])
    offset = np.array([glass[0] - pose[0], glass[1] - pose[1]], dtype=float)
    depth = float(offset @ look)
    lateral = float(offset @ side)
    column = 160.0 + FX * lateral / depth
    half = FX * radius / depth
    height = FX * GLASS_HEIGHT / depth
    axis.add_patch(
        Rectangle(
            (column - half, 60), 2 * half, height,
            fc=colour, ec=colour, alpha=alpha, lw=1.2, zorder=4,
        )
    )
    return column, half


def _frame(axis, title, colour):
    bare(axis)
    axis.set_xlim(-8, 328)
    axis.set_ylim(0, 250)
    axis.add_patch(Rectangle((0, 0), 320, 240, fill=False, ec=MUTED, lw=1.0))
    axis.plot([0, 320], [60, 60], color=MUTED, lw=1.0)
    axis.text(4, 46, "table top", fontsize=NOTE_SIZE - 0.6, color=MUTED)
    axis.set_title(title, fontsize=LABEL_SIZE, color=colour, pad=6)


# ------------------------------------------- 1. what goes wrong without this


def _gap_px(theta: float) -> float:
    """Pixels of table between the two silhouettes from this standoff direction."""
    pose = _pose(theta)
    look = np.array([CLUSTER[0] - pose[0], CLUSTER[1] - pose[1]], dtype=float)
    look /= np.hypot(*look)
    side = np.array([-look[1], look[0]])
    edges = []
    for glass, radius in ((GLASS_A, RADIUS_A), (GLASS_B, RADIUS_B)):
        offset = np.array([glass[0] - pose[0], glass[1] - pose[1]], dtype=float)
        depth = float(offset @ look)
        edges.append((160.0 + FX * float(offset @ side) / depth, FX * radius / depth))
    (c0, h0), (c1, h1) = edges
    return abs(c0 - c1) - h0 - h1


def _resolves(theta: float) -> bool:
    return _gap_px(theta) >= GAP_NEEDED_PX


def _mini_plan(axis, scores, accent, title, subtitle) -> None:
    """One scorer's view of the same eight candidates."""
    _plan(axis, xlim=(-130, 990), ylim=(-70, 1010))
    axis.add_patch(Circle(CLUSTER, STANDOFF, fill=False, ec=MUTED, lw=0.7, ls=(0, (2, 4))))
    for centre, radius in ((GLASS_A, RADIUS_A), (GLASS_B, RADIUS_B)):
        axis.add_patch(Circle(centre, radius, fc=GLASS, alpha=0.5, ec=GLASS, lw=1.0, zorder=4))
    axis.add_patch(Circle(NEIGHBOUR, NEIGHBOUR_RADIUS, fc=MUTED, alpha=0.35, ec=MUTED, zorder=3))
    _base(axis, label=False)

    top = max(scores.values())
    bests = [t for t in SURVIVORS if scores[t] >= top - 1e-9]
    for theta in SURVIVORS:
        pose, score = _pose(theta), scores[theta]
        axis.plot(*pose, marker="o", ms=3.5 + 13 * score, color=accent, alpha=0.30 + 0.6 * score, zorder=5)
        out = ((pose[0] - CLUSTER[0]) / STANDOFF, (pose[1] - CLUSTER[1]) / STANDOFF)
        axis.text(
            pose[0] + 74 * out[0], pose[1] + 74 * out[1], f"{score:.2f}",
            ha="center", va="center", fontsize=NOTE_SIZE - 0.6,
            color=accent if score > 0.4 else MUTED,
        )
    for theta in bests:
        pose = _pose(theta)
        _camera(axis, pose, CLUSTER, accent, lw=1.6, ms=0)
        axis.plot(*pose, marker="*", ms=17, color=accent, zorder=7)
    lead = _pose(bests[0])
    out = ((lead[0] - CLUSTER[0]) / STANDOFF, (lead[1] - CLUSTER[1]) / STANDOFF)
    axis.text(
        lead[0] - 140 * out[0] - 78 * out[1], lead[1] - 140 * out[1] + 78 * out[0],
        "tied for first" if len(bests) > 1 else "its first pick",
        ha="center", va="center", fontsize=NOTE_SIZE, color=accent, zorder=7,
    )
    axis.set_title(title, fontsize=LABEL_SIZE + 0.6, color=accent, pad=4)
    axis.text(
        430, 930, subtitle, ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )


def _zone(axis) -> None:
    left, bottom, width, height = ZONE
    axis.add_patch(Rectangle((left, bottom), width, height, fill=False, ec=MUTED, lw=0.8, ls=(0, (3, 3))))


def _spawned(axis, alpha=0.65) -> None:
    for centre, radius in SPAWNED:
        axis.add_patch(Circle(centre, radius, fc=GLASS, alpha=alpha, ec=GLASS, lw=1.2, zorder=4))


def veto_then_ordering() -> None:
    """Why a wrong prediction costs a look and never an unsafe move."""
    figure, axis = plt.subplots(figsize=(13.0, 6.6))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    bare(axis)
    axis.set_xlim(-6.2, 28.8)
    axis.set_ylim(-1.4, 6.6)

    reach_ok = [t for t in ALL_THETAS if REACH_MIN <= _reach_of(_pose(t)) <= REACH_MAX]
    stages = [
        ("every standoff direction", "24 at 15-degree spacing", ALL_THETAS, None),
        ("reach", "the camera must land 300 to 780 mm from the base", reach_ok, "12 dropped"),
        ("line of sight", "no ray through another cluster's footprint",
         [t for t in reach_ok if t not in BLOCKED], "3 dropped"),
        ("inverse kinematics", "MoveIt 2 must find an arm pose that holds it",
         [t for t in reach_ok if t not in BLOCKED and t not in NO_IK], "1 dropped"),
    ]

    for row, (name, note, alive, dropped) in enumerate(stages):
        y = 5.6 - row * 1.15
        axis.text(-6.0, y + 0.12, name, fontsize=LABEL_SIZE + 0.6, color=INK, va="center")
        axis.text(-6.0, y - 0.38, note, fontsize=NOTE_SIZE - 0.4, color=MUTED, va="center")
        for index, theta in enumerate(ALL_THETAS):
            here = theta in alive
            axis.plot(
                9.0 + index * 0.72, y, marker="o", ms=8.5,
                color=GLASS if here else PAPER, mec=GLASS if here else MUTED,
                alpha=1.0 if here else 0.55, mew=1.0,
            )
        axis.text(
            28.6, y, f"{len(alive)} left", fontsize=LABEL_SIZE, color=INK, va="center", ha="right",
        )
        if dropped:
            axis.text(
                28.6, y - 0.42, dropped, fontsize=NOTE_SIZE - 0.4, color=WARN, va="center", ha="right",
            )

    axis.text(
        9.0, 5.02, "left to right: minus 180 to plus 165 degrees off the radial",
        fontsize=NOTE_SIZE - 0.4, color=MUTED, va="center",
    )

    y = 0.65
    axis.text(-6.0, y + 0.12, "the model", fontsize=LABEL_SIZE + 0.6, color=GOOD, va="center")
    axis.text(
        -6.0, y - 0.38, "puts the eight survivors in order",
        fontsize=NOTE_SIZE - 0.4, color=MUTED, va="center",
    )
    ordered = sorted(SURVIVORS, key=lambda t: -PAYOFF[t])
    for index, theta in enumerate(ordered):
        x = 9.0 + index * 1.35
        axis.plot(x, y, marker="o", ms=8.5 + 9 * PAYOFF[theta], color=GOOD, alpha=0.35 + 0.55 * PAYOFF[theta])
        axis.text(x, y - 0.52, f"{theta:+.0f}", ha="center", fontsize=NOTE_SIZE - 0.6, color=INK)
        axis.text(x, y + 0.52, f"{PAYOFF[theta]:.2f}", ha="center", fontsize=NOTE_SIZE - 0.6, color=GOOD)
    axis.text(28.6, y, "8 ordered", fontsize=LABEL_SIZE, color=GOOD, va="center", ha="right")

    axis.plot([8.2, 8.2], [1.55, 5.85], color=INK, lw=1.4)
    axis.text(
        7.9, 3.7, "geometry — may veto", rotation=90, va="center", ha="center",
        fontsize=LABEL_SIZE, color=INK,
    )
    axis.plot([8.2, 8.2], [0.05, 1.25], color=GOOD, lw=1.4)
    axis.text(
        7.9, 0.65, "may only reorder", rotation=90, va="center", ha="center",
        fontsize=LABEL_SIZE, color=GOOD,
    )
    axis.text(
        -6.0, -1.05,
        "Every pose the model can put first was already found reachable, unblocked and plannable. "
        "The worst a bad\nprediction can do is spend one look on a picture that changes nothing.",
        fontsize=NOTE_SIZE + 0.4, color=INK, va="center",
    )
    axis.set_title(
        "24 directions in, 8 scored: the geometry vetoes, the model only orders",
        fontsize=TITLE_SIZE + 1, color=INK, pad=14,
    )
    save(figure, "hidden-veto-then-ordering.png")


# --------------------------- 6. supervised against reinforcement, for this job


COMPARISON = [
    ("what one example is",
     "one arrangement, one candidate pose",
     "one episode: several looks, then an outcome"),
    ("where the label comes from",
     "the simulator's own record, exactly",
     "a reward somebody designs"),
    ("arm moves needed to collect it",
     "none — Gazebo renders from any pose",
     "the whole episode has to be played out"),
    ("working out which look helped",
     "not needed: the label is that look's",
     "the central difficulty of the method"),
    ("what has to be designed by hand",
     "a list of features",
     "reward, action space, exploration, discount"),
    ("rough wall-clock on this Mac",
     "hours, unattended — time it, do not trust it",
     "uncertain, and longer by a wide margin"),
    ("what comes out",
     "an ordering over the candidates",
     "a policy that also decides when to stop"),
]


def main() -> None:
    veto_then_ordering()
if __name__ == "__main__":
    main()
