"""Diagrams for solution 6 — learn which viewpoints pay off.

Run from the project root:

    pixi run python images/generators/problem-2/make_06_images.py

Every picture here is drawn from the numbers in
``docs/problem-2/06-learn-which-viewpoints-pay-off.md``. Nothing is measured
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

import cv2
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
    new,
    save,
    splay_circles,
    splay_covers,
    splay_patch,
    splay_width,
)
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle, Wedge

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


def the_rule_cannot_tell_them_apart() -> None:
    """The failure this solution is aimed at.

    Reach depends only on the angle between the standoff direction and the
    line out from the base, so every candidate has a mirror image with exactly
    the same reach. A rule that prefers least reach is blind to the
    difference, and here one of the pair resolves the cluster and the other
    hides it.
    """
    figure, panels = plt.subplot_mosaic(
        [["plan", "bad"], ["plan", "good"]],
        figsize=(13.4, 6.8),
        gridspec_kw={"width_ratios": [1.5, 1.0], "wspace": 0.16, "hspace": 0.34},
    )
    figure.patch.set_facecolor(PAPER)
    for axis in panels.values():
        axis.set_facecolor(PAPER)

    plan = panels["plan"]
    _plan(plan, xlim=(-170, 960), ylim=(-150, 860))
    _reach_band(plan)
    _base(plan)

    plan.add_patch(Circle(CLUSTER, 79, fill=False, ec=WARN, lw=1.4, ls=(0, (4, 3))))
    plan.text(
        CLUSTER[0] - 170, CLUSTER[1] + 215, "one circle fits at 158 mm —\nno glass of this kind is",
        ha="center", fontsize=NOTE_SIZE, color=WARN,
    )
    for centre, radius in ((GLASS_A, RADIUS_A), (GLASS_B, RADIUS_B)):
        plan.add_patch(Circle(centre, radius, fc=GLASS, alpha=0.65, ec=GLASS, lw=1.4, zorder=4))
    plan.plot(
        [GLASS_A[0], GLASS_B[0]], [GLASS_A[1], GLASS_B[1]],
        color=INK, lw=1.1, ls=(0, (2, 2)), zorder=5,
    )
    plan.text(
        GLASS_A[0] + 40, GLASS_A[1] + 95, "the pair, 168 mm apart",
        ha="center", fontsize=NOTE_SIZE, color=GLASS,
    )
    plan.add_patch(Circle(NEIGHBOUR, NEIGHBOUR_RADIUS, fc=MUTED, alpha=0.45, ec=MUTED, zorder=3))
    plan.text(
        NEIGHBOUR[0] - 66, NEIGHBOUR[1] + 34, "a neighbour", fontsize=NOTE_SIZE, color=MUTED,
    )

    seen, bad, good = _pose(SEEN_FROM), _pose(-135), _pose(135)
    _camera(plan, seen, CLUSTER, MUTED, style=(0, (4, 3)))
    plan.text(
        seen[0] + 4, seen[1] + 46, "the survey already\nlooked from here",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )
    _camera(plan, bad, CLUSTER, WARN, lw=1.8)
    plan.text(
        bad[0] + 14, bad[1] - 46,
        "minus 135 degrees:\n15 degrees off the join line",
        ha="center", va="top", fontsize=NOTE_SIZE, color=WARN,
    )
    _camera(plan, good, CLUSTER, GOOD, lw=1.8)
    plan.text(
        good[0] - 4, good[1] - 46,
        "plus 135 degrees:\nsquare across it",
        ha="center", va="top", fontsize=NOTE_SIZE, color=GOOD,
    )
    plan.annotate(
        "", xy=(bad[0] + 24, bad[1] - 2), xytext=(good[0] - 24, good[1] - 2),
        arrowprops={"arrowstyle": "<|-|>", "color": INK, "lw": 1.0, "shrinkA": 0, "shrinkB": 0},
    )
    plan.text(
        430, bad[1] - 105,
        f"both {_reach_of(bad):.0f} mm from the base, both with a clear\n"
        "line of sight: the rule scores them the same",
        ha="center", va="center", fontsize=NOTE_SIZE, color=INK,
    )
    plan.set_title(
        "Two candidate looks a least-reach rule cannot tell apart",
        fontsize=TITLE_SIZE, color=INK, pad=10,
    )

    for key, pose, accent, title in (
        ("bad", bad, WARN, "from minus 135 degrees"),
        ("good", good, GOOD, "from plus 135 degrees"),
    ):
        _frame(panels[key], title, accent)
        far = _silhouette(panels[key], pose, GLASS_A, RADIUS_A, accent, alpha=0.55)
        near = _silhouette(panels[key], pose, GLASS_B, RADIUS_B, accent)
        gap = abs(near[0] - far[0]) - near[1] - far[1]
        if gap < GAP_NEEDED_PX:
            width = max(near[0] + near[1], far[0] + far[1]) - min(near[0] - near[1], far[0] - far[1])
            note = f"still one blob, {width:.0f} px across — the look is spent"
        else:
            note = f"two silhouettes, {gap:.0f} px of table between them"
        panels[key].text(160, 214, note, ha="center", fontsize=NOTE_SIZE, color=accent)
        panels[key].text(
            160, 22, f"the pair projects {abs(near[0] - far[0]):.0f} px apart",
            ha="center", fontsize=NOTE_SIZE - 0.4, color=MUTED,
        )

    save(figure, "06-the-rule-cannot-tell-them-apart.png")



# ------------------------------------------------ 2. three scorers, one scene
#
# The eight candidates that survive the veto in this arrangement, and what
# each of the three scorers makes of them. The payoff and uncertainty numbers
# are illustrative: they are what each scorer is *for*, not a measurement.

SURVIVORS = [60.0, 75.0, 90.0, 105.0, 120.0, 135.0, -120.0, -135.0]

PAYOFF = {120.0: 0.88, 135.0: 0.81, 105.0: 0.79, 90.0: 0.62,
          75.0: 0.44, -120.0: 0.21, 60.0: 0.12, -135.0: 0.07}
DOUBT_DROP = {-135.0: 0.71, 120.0: 0.58, 105.0: 0.52, 135.0: 0.44,
              90.0: 0.39, 75.0: 0.30, -120.0: 0.22, 60.0: 0.19}

GAP_NEEDED_PX = 10.0        # a fit needs daylight between the two, not a touching pair


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


def three_scorers() -> None:
    """Rule, expected doubt drop, predicted payoff — on one arrangement."""
    figure, panels = plt.subplot_mosaic(
        [["rule", "doubt", "payoff"], ["order", "order", "order"]],
        figsize=(13.6, 7.8),
        gridspec_kw={"height_ratios": [1.0, 0.62], "hspace": 0.12, "wspace": 0.06},
    )
    figure.patch.set_facecolor(PAPER)
    for axis in panels.values():
        axis.set_facecolor(PAPER)

    reach = {t: _reach_of(_pose(t)) for t in SURVIVORS}
    worst, best_reach = max(reach.values()), min(reach.values())
    rule_scores = {t: (worst - reach[t]) / (worst - best_reach) for t in SURVIVORS}

    _mini_plan(
        panels["rule"], rule_scores, MUTED,
        "solution 3 — a rule somebody wrote",
        "score = least reach, once the line\nof sight is clear",
    )
    _mini_plan(
        panels["doubt"], DOUBT_DROP, GLASS,
        "solution 4 — expected drop in doubt",
        "score = how far the segmenter's\nper-pixel doubt should fall",
    )
    _mini_plan(
        panels["payoff"], PAYOFF, GOOD,
        "solution 6 — predicted payoff",
        "score = the chance this picture\nsplits the cluster in two",
    )

    order = panels["order"]
    bare(order)
    order.set_xlim(0, 10.6)
    order.set_ylim(-0.4, 3.9)
    rows = [
        ("least reach", sorted(SURVIVORS, key=lambda t: reach[t]), MUTED),
        ("expected doubt drop", sorted(SURVIVORS, key=lambda t: -DOUBT_DROP[t]), GLASS),
        ("predicted payoff", sorted(SURVIVORS, key=lambda t: -PAYOFF[t]), GOOD),
    ]
    for row, (name, ordering, accent) in enumerate(rows):
        y = 2.6 - row * 0.95
        order.text(2.35, y + 0.22, name, ha="right", va="center", fontsize=LABEL_SIZE, color=accent)
        for slot, theta in enumerate(ordering):
            x = 2.5 + slot * 1.0
            good = _resolves(theta)
            order.add_patch(
                Rectangle(
                    (x, y - 0.06), 0.88, 0.56,
                    fc=GOOD if good else WARN, alpha=0.82, ec="none",
                )
            )
            order.text(
                x + 0.44, y + 0.22, f"{theta:+.0f}",
                ha="center", va="center", fontsize=LABEL_SIZE, color=PAPER, fontweight="bold",
            )
    order.plot([2.52, 4.46], [2.52, 2.52], color=INK, lw=1.0)
    order.text(
        3.49, 2.40, "tied on reach — the rule tosses a coin",
        ha="center", va="top", fontsize=NOTE_SIZE - 0.4, color=INK,
    )
    order.text(2.94, 3.32, "taken first", ha="center", fontsize=NOTE_SIZE, color=INK)
    order.add_patch(
        FancyArrowPatch((3.5, 3.3), (10.2, 3.3), arrowstyle="-|>", mutation_scale=11, color=MUTED, lw=0.9)
    )
    order.text(10.3, 3.3, "last", ha="left", va="center", fontsize=NOTE_SIZE, color=MUTED)
    order.text(
        0.0, -0.15,
        "Each box is one candidate, by its angle off the radial. Green: the pair really does come "
        "apart from there.\nRed: it does not. Only the third ordering puts both useless looks at the end.",
        ha="left", va="center", fontsize=NOTE_SIZE, color=INK,
    )
    figure.suptitle(
        "Three ways to score the same eight viewpoints", fontsize=TITLE_SIZE + 1, color=INK, y=0.99,
    )
    save(figure, "06-three-scorers.png")



# ------------------------------------------ 3. how one training example is made
#
# A second arrangement, unrelated to the one above, because the point of this
# picture is that the simulator makes a fresh one every time.

ZONE = (270.0, 300.0, 320.0, 360.0)      # the 320 x 360 mm zone the glasses stand in
SPAWNED = [
    ((290.0, 330.0), 30.0),
    ((560.0, 330.0), 38.0),
    ((330.0, 600.0), 34.0),
    ((430.0, 430.0), 36.0),              # these last two merge from the survey's line
    ((500.0, 565.0), 33.0),
]
MERGED = ((465.0, 497.5), 110.0)         # what the one-circle fit returns for the pair


def _zone(axis) -> None:
    left, bottom, width, height = ZONE
    axis.add_patch(Rectangle((left, bottom), width, height, fill=False, ec=MUTED, lw=0.8, ls=(0, (3, 3))))


def _spawned(axis, alpha=0.65) -> None:
    for centre, radius in SPAWNED:
        axis.add_patch(Circle(centre, radius, fc=GLASS, alpha=alpha, ec=GLASS, lw=1.2, zorder=4))


def one_training_example() -> None:
    """Spawn, find the ambiguity, take the picture, write down what happened."""
    figure, axes = plt.subplots(1, 5, figsize=(17.0, 4.6))
    figure.patch.set_facecolor(PAPER)
    for axis in axes:
        axis.set_facecolor(PAPER)

    steps = [
        "1. spawn",
        "2. fit, and find the ambiguity",
        "3. pick a candidate the veto allows",
        "4. render from it",
        "5. write the row",
    ]
    for axis in axes[:3]:
        _plan(axis, xlim=(60, 820), ylim=(20, 910))
        _zone(axis)

    _spawned(axes[0])
    axes[0].text(
        440, 95, "five glasses of one kind, at random,\n150 mm apart, inside the 320 x 360 mm zone",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )

    _spawned(axes[1], alpha=0.35)
    for centre, radius in SPAWNED[:3]:
        axes[1].add_patch(Circle(centre, radius, fill=False, ec=GOOD, lw=1.6, zorder=5))
    axes[1].add_patch(Circle(MERGED[0], MERGED[1], fill=False, ec=WARN, lw=1.8, ls=(0, (4, 3)), zorder=5))
    axes[1].text(
        440, 95, "three circles inside the kind's range.\nOne fits at 220 mm: ambiguous",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )

    _spawned(axes[2], alpha=0.35)
    join = np.array([SPAWNED[4][0][0] - SPAWNED[3][0][0], SPAWNED[4][0][1] - SPAWNED[3][0][1]])
    join /= np.hypot(*join)
    chosen = (MERGED[0][0] + STANDOFF * join[1], MERGED[0][1] - STANDOFF * join[0])
    for angle in range(0, 360, 15):
        radians = math.radians(angle)
        spot = (MERGED[0][0] + STANDOFF * math.cos(radians), MERGED[0][1] + STANDOFF * math.sin(radians))
        axes[2].plot(*spot, marker="o", ms=3.5, color=MUTED, alpha=0.55, zorder=5)
    _camera(axes[2], chosen, MERGED[0], GOOD, lw=1.6)
    axes[2].text(chosen[0] - 10, chosen[1] + 46, "pose P", ha="center", fontsize=NOTE_SIZE, color=GOOD)
    axes[2].text(
        440, 95,
        "24 directions, minus the ones out of reach,\nblocked, or unplannable. No arm motion:\n"
        "Gazebo renders from wherever it is asked",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )

    _frame(axes[3], "", INK)
    axes[3].set_xlim(-8, 328)
    axes[3].set_ylim(-118, 252)
    axes[3].set_aspect("equal")
    left = _silhouette(axes[3], chosen, SPAWNED[3][0], SPAWNED[3][1], GOOD, target=MERGED[0])
    right = _silhouette(axes[3], chosen, SPAWNED[4][0], SPAWNED[4][1], GOOD, alpha=0.6, target=MERGED[0])
    gap = abs(left[0] - right[0]) - left[1] - right[1]
    axes[3].text(
        160, 216, f"two silhouettes, {gap:.0f} px apart", ha="center", fontsize=NOTE_SIZE, color=GOOD,
    )
    axes[3].text(
        160, -48, "the fit now returns 72 mm and 66 mm,\nboth inside the kind's range",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )

    board = axes[4]
    bare(board)
    board.set_xlim(0, 15)
    board.set_ylim(0, 16.5)
    board.set_aspect("equal")
    reach = math.hypot(chosen[0] - BASE[0], chosen[1] - BASE[1])
    board.add_patch(Rectangle((0.3, 9.0), 14.4, 6.4, fc=GLASS, alpha=0.10, ec=GLASS, lw=1.2))
    board.text(7.5, 16.3, "features: about 20 numbers", ha="center", fontsize=LABEL_SIZE, color=GLASS)
    board.text(
        7.5, 12.2,
        "angle to the join line       90 deg\n"
        "separation                      4.4 radii\n"
        "nearest other cluster     3.1 radii\n"
        f"reach                              {reach:.0f} mm\n"
        "angle from nearest view  62 deg",
        ha="center", va="center", fontsize=NOTE_SIZE, color=INK, linespacing=1.7,
    )
    board.add_patch(
        FancyArrowPatch((7.5, 8.7), (7.5, 7.3), arrowstyle="-|>", mutation_scale=13, color=MUTED, lw=1.2)
    )
    board.add_patch(Rectangle((3.3, 4.7), 8.4, 2.3, fc=GOOD, alpha=0.18, ec=GOOD, lw=1.4))
    board.text(
        7.5, 5.85, "label:  resolved = 1",
        ha="center", va="center", fontsize=LABEL_SIZE + 1, color=GOOD,
    )
    board.text(
        7.5, 2.6,
        "read from the simulator's own record.\nNo reward. No episode. Nobody labelling.",
        ha="center", va="center", fontsize=NOTE_SIZE, color=INK,
    )

    for axis, step in zip(axes, steps, strict=True):
        axis.set_title(step, fontsize=LABEL_SIZE + 0.6, color=INK, pad=8)
    figure.suptitle(
        "One row of training data, start to finish", fontsize=TITLE_SIZE + 1, color=INK, y=1.03,
    )
    save(figure, "06-one-training-example.png")



# ------------------------------------------------ 4. what the model is shown


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


def the_features() -> None:
    """The twenty-odd numbers a candidate is turned into, drawn where they live."""
    figure, (plan, sheet) = plt.subplots(
        1, 2, figsize=(14.6, 7.4), gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.04},
    )
    figure.patch.set_facecolor(PAPER)
    for axis in (plan, sheet):
        axis.set_facecolor(PAPER)

    _plan(plan, xlim=(-40, 900), ylim=(-120, 880))
    _base(plan)
    candidate, seen = _pose(120), _pose(SEEN_FROM)

    plan.add_patch(Circle(CLUSTER, 79, fill=False, ec=WARN, lw=1.2, ls=(0, (4, 3))))
    for centre, radius in ((GLASS_A, RADIUS_A), (GLASS_B, RADIUS_B)):
        plan.add_patch(Circle(centre, radius, fc=GLASS, alpha=0.6, ec=GLASS, lw=1.3, zorder=4))
    plan.add_patch(Circle(NEIGHBOUR, NEIGHBOUR_RADIUS, fc=MUTED, alpha=0.4, ec=MUTED, zorder=3))

    # the join line, and the separation in radii
    plan.plot(
        [GLASS_A[0], GLASS_B[0]], [GLASS_A[1], GLASS_B[1]], color=INK, lw=1.2, ls=(0, (2, 2)), zorder=5,
    )
    plan.text(
        GLASS_B[0] - 130, GLASS_B[1] - 72, "the join line:\n168 mm, 4.6 fitted radii",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )

    # the candidate's ray, the angle it makes with the join line, and the standoff
    _camera(plan, candidate, CLUSTER, GOOD, lw=1.7)
    plan.add_patch(
        Wedge(CLUSTER, 100, -30.0, 60.0, fc=GOOD, alpha=0.18, ec="none", zorder=2)
    )
    plan.text(
        CLUSTER[0] + 150, CLUSTER[1] - 20, "angle to the\njoin line: 90 deg",
        ha="left", fontsize=NOTE_SIZE, color=GOOD,
    )
    midpoint = ((CLUSTER[0] + candidate[0]) / 2, (CLUSTER[1] + candidate[1]) / 2)
    plan.text(
        midpoint[0] - 25, midpoint[1] - 52, "standoff 380 mm",
        ha="center", fontsize=NOTE_SIZE, color=GOOD,
    )

    # reach
    plan.plot([BASE[0], candidate[0]], [BASE[1], candidate[1]], color=MUTED, lw=1.0, ls=(0, (3, 3)))
    plan.text(
        (BASE[0] + candidate[0]) / 2 + 92, (BASE[1] + candidate[1]) / 2 - 70,
        f"reach {_reach_of(candidate):.0f} mm\n(limits 300 and 780)",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )

    # how close the ray passes to the neighbour, in that neighbour's radii
    look = np.array([candidate[0] - CLUSTER[0], candidate[1] - CLUSTER[1]]) / STANDOFF
    behind = (CLUSTER[0] - 250 * look[0], CLUSTER[1] - 250 * look[1])
    plan.plot(
        [CLUSTER[0], behind[0]], [CLUSTER[1], behind[1]], color=GOOD, lw=1.0, ls=(0, (2, 3)), zorder=2,
    )
    to_neighbour = np.array([NEIGHBOUR[0] - CLUSTER[0], NEIGHBOUR[1] - CLUSTER[1]])
    foot = CLUSTER + look * float(to_neighbour @ look)
    plan.plot(
        [NEIGHBOUR[0], foot[0]], [NEIGHBOUR[1], foot[1]], color=MUTED, lw=1.0, ls=(0, (2, 2)), zorder=4,
    )
    plan.text(
        NEIGHBOUR[0] - 24, NEIGHBOUR[1] + 96,
        "0.9 of its own radii off the line of sight —\n"
        "but on the far side of the cluster,\nso it blocks nothing",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )

    # the view already taken, and the angle from it
    _camera(plan, seen, CLUSTER, MUTED, style=(0, (4, 3)))
    plan.text(
        seen[0] + 10, seen[1] + 56, "the nearest view already\ntaken: 60 deg away",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )
    plan.text(
        CLUSTER[0] + 40, CLUSTER[1] - 214, "the fit: one circle at 158 mm",
        ha="center", fontsize=NOTE_SIZE, color=WARN,
    )
    plan.set_title(
        "Everything the model is given, drawn where it lives", fontsize=TITLE_SIZE, color=INK, pad=10,
    )

    bare(sheet)
    sheet.set_xlim(0, 10)
    sheet.set_ylim(0, 10)
    y = 9.5
    for name, count, lines in FEATURE_GROUPS:
        sheet.text(0.1, y, f"{name}", fontsize=LABEL_SIZE + 0.5, color=INK, va="top")
        sheet.text(9.9, y, f"{count}", fontsize=LABEL_SIZE + 0.5, color=GLASS, va="top", ha="right")
        y -= 0.42
        for line in lines:
            sheet.text(0.45, y, line, fontsize=NOTE_SIZE, color=MUTED, va="top")
            y -= 0.38
        y -= 0.28
    sheet.plot([0.1, 9.9], [y + 0.22, y + 0.22], color=MUTED, lw=0.8)
    sheet.text(
        0.1, y - 0.05, "twenty numbers, all of them millimetres,",
        fontsize=NOTE_SIZE, color=INK, va="top",
    )
    sheet.text(0.1, y - 0.43, "degrees or counts", fontsize=NOTE_SIZE, color=INK, va="top")
    sheet.text(
        0.1, y - 1.15,
        "Not in the list: the picture.\nWhen the score is wanted, it does not exist yet.",
        fontsize=NOTE_SIZE + 0.3, color=WARN, va="top",
    )
    save(figure, "06-the-features.png")



# ------------------------------------- 5. the veto first, the ordering after


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
    save(figure, "06-veto-then-ordering.png")



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


def supervised_against_reinforcement() -> None:
    """The same job, framed two ways, and what each framing costs."""
    figure, axis = plt.subplots(figsize=(13.4, 7.2))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    bare(axis)
    axis.set_xlim(0, 30)
    axis.set_ylim(-2.2, 9.6)

    axis.add_patch(Rectangle((10.4, -0.45), 9.2, 8.4, fc=GOOD, alpha=0.08, ec=GOOD, lw=1.2))
    axis.add_patch(Rectangle((20.2, -0.45), 9.4, 8.4, fc=MUTED, alpha=0.10, ec=MUTED, lw=1.2))
    axis.text(15.0, 9.0, "supervised, as here", ha="center", fontsize=LABEL_SIZE + 2, color=GOOD)
    axis.text(24.9, 9.0, "reinforcement learning", ha="center", fontsize=LABEL_SIZE + 2, color=MUTED)
    axis.text(
        15.0, 8.35, "predict whether this one picture pays off",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )
    axis.text(
        24.9, 8.35, "learn a looking policy from its own attempts",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )

    for row, (name, left, right) in enumerate(COMPARISON):
        y = 7.2 - row * 1.16
        if row % 2 == 0:
            axis.add_patch(Rectangle((0.2, y - 0.46), 29.4, 0.94, fc=MUTED, alpha=0.06, ec="none"))
        axis.text(0.5, y, name, fontsize=LABEL_SIZE, color=INK, va="center")
        axis.text(15.0, y, left, fontsize=NOTE_SIZE + 0.3, color=INK, va="center", ha="center")
        axis.text(24.9, y, right, fontsize=NOTE_SIZE + 0.3, color=MUTED, va="center", ha="center")

    axis.text(
        0.5, -1.85,
        "Why this job is the supervised one: the label for a single look — did the cluster come apart — "
        "does not depend\non what the arm does next. That is what removes the episode, the reward, "
        "and most of the machine time.",
        fontsize=NOTE_SIZE + 0.6, color=INK, va="center",
    )
    axis.set_title(
        "The same question asked two ways", fontsize=TITLE_SIZE + 1, color=INK, pad=14,
    )
    save(figure, "06-supervised-against-reinforcement.png")


# --------------------------------------------- 7. the loop, and what it buys


def improves_with_use() -> None:
    """The run-time loop, and the shape — not the size — of what logging buys."""
    figure, (loop, curve) = plt.subplots(
        1, 2, figsize=(14.2, 6.4), gridspec_kw={"width_ratios": [1.05, 1.0], "wspace": 0.12},
    )
    figure.patch.set_facecolor(PAPER)
    for axis in (loop, curve):
        axis.set_facecolor(PAPER)

    bare(loop)
    loop.set_xlim(-1.1, 10.7)
    loop.set_ylim(0, 10)
    steps = [
        ("fit", "a cluster outside the\nkind's range is ambiguous", GLASS),
        ("generate and veto", "24 candidates, filtered for\nreach, occlusion and IK", GLASS),
        ("predict and order", "score each survivor,\ntake the highest", GOOD),
        ("move and photograph", "seconds for the move, then five\npictures along the 120 mm slide", GLASS),
        ("observe", "re-fit. Two in-range\ncircles, or not?", GLASS),
        ("record", "one row: the features,\nand what happened", GOOD),
    ]
    positions = [(2.4, 8.6), (7.0, 8.6), (8.6, 5.4), (7.0, 2.2), (2.4, 2.2), (0.9, 5.4)]
    for (name, note, colour), (x, y) in zip(steps, positions, strict=True):
        loop.add_patch(
            Rectangle((x - 1.75, y - 0.85), 3.5, 1.7, fc=colour, alpha=0.12, ec=colour, lw=1.3)
        )
        loop.text(x, y + 0.42, name, ha="center", va="center", fontsize=LABEL_SIZE, color=colour)
        loop.text(x, y - 0.32, note, ha="center", va="center", fontsize=NOTE_SIZE - 0.8, color=INK)
    order = [0, 1, 2, 3, 4, 5, 0]
    for start, end in zip(order[:-1], order[1:], strict=True):
        x0, y0 = positions[start]
        x1, y1 = positions[end]
        loop.add_patch(
            FancyArrowPatch(
                (x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, color=MUTED, lw=1.1,
                shrinkA=52, shrinkB=52, connectionstyle="arc3,rad=0.18",
            )
        )
    loop.text(
        4.7, 5.4,
        "the run-time label needs\nno ground truth:\nnot 'was it right'\nbut 'did it change'",
        ha="center", va="center", fontsize=NOTE_SIZE + 0.4, color=INK,
    )
    loop.set_title("Every look taken is another labelled row", fontsize=TITLE_SIZE, color=INK, pad=10)

    looks = np.linspace(0, 4000, 400)
    learned = 0.72 + 0.16 * (1 - np.exp(-looks / 950.0))
    curve.plot(looks, learned, color=GOOD, lw=2.0)
    curve.axhline(0.58, color=MUTED, lw=2.0, ls=(0, (5, 4)))
    curve.text(
        3950, learned[-1] - 0.028, "the predictor, retrained on the log",
        ha="right", fontsize=LABEL_SIZE, color=GOOD,
    )
    curve.text(3950, 0.592, "the hand-written rule", ha="right", fontsize=LABEL_SIZE, color=MUTED)
    curve.set_xlim(-60, 4100)
    curve.set_ylim(0.5, 0.95)
    curve.set_xlabel("looks recorded in normal running", fontsize=LABEL_SIZE, color=INK)
    curve.set_ylabel("how often the first pick resolves the cluster", fontsize=LABEL_SIZE, color=INK)
    curve.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
    for side in ("top", "right"):
        curve.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        curve.spines[side].set_color(MUTED)
        curve.spines[side].set_linewidth(0.8)
    curve.grid(axis="y", color=MUTED, alpha=0.18, lw=0.7)
    curve.set_axisbelow(True)
    curve.annotate(
        "where the overnight sweep leaves it",
        xy=(0, learned[0]), xytext=(700, 0.665),
        arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 0.9},
        fontsize=NOTE_SIZE, color=INK,
    )
    curve.text(
        0.03, 0.04, "ILLUSTRATIVE — the shape of the claim, not a measurement. Nothing here\n"
        "has been run. The flat line is the point: a rule does not improve with use.",
        transform=curve.transAxes, ha="left", va="bottom", fontsize=NOTE_SIZE, color=WARN,
    )
    curve.set_title("What the log is for", fontsize=TITLE_SIZE, color=INK, pad=10)
    save(figure, "06-improves-with-use.png")



# ----------------------------------------------------- 8. where it stops working


EIGHT = [
    ((300.0, 340.0), 30.0), ((470.0, 315.0), 34.0), ((620.0, 360.0), 37.0),
    ((330.0, 490.0), 32.0), ((480.0, 470.0), 36.0), ((610.0, 520.0), 33.0),
    ((370.0, 640.0), 35.0), ((540.0, 645.0), 31.0),
]


def where_it_stops_working() -> None:
    """Two ways the predictor runs out: a table it was not trained on, and an empty list."""
    figure, axes = plt.subplots(1, 3, figsize=(15.2, 5.8))
    figure.patch.set_facecolor(PAPER)
    for axis in axes:
        axis.set_facecolor(PAPER)

    for axis in axes[:2]:
        _plan(axis, xlim=(20, 900), ylim=(60, 1050))
        _zone(axis)

    _spawned(axes[0])
    axes[0].text(
        460, 95, "five glasses: two or three clusters near\nthe candidate, separations of 150 to 300 mm",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )
    axes[0].set_title("what it was trained on", fontsize=LABEL_SIZE + 1.5, color=GOOD, pad=8)

    for centre, radius in EIGHT:
        axes[1].add_patch(Circle(centre, radius, fc=WARN, alpha=0.45, ec=WARN, lw=1.2, zorder=4))
    axes[1].text(
        460, 95, "eight: six clusters near the candidate,\nand separations the training set never held",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )
    axes[1].set_title("what problem 3 might hand it", fontsize=LABEL_SIZE + 1.5, color=WARN, pad=8)
    axes[1].text(
        460, 1000, "a tree asked about a feature value off the end of its\n"
        "range does not say so: it answers anyway",
        ha="center", fontsize=NOTE_SIZE, color=WARN,
    )

    empty = axes[2]
    _plan(empty, xlim=(20, 900), ylim=(60, 1050))
    _zone(empty)
    tight = [((330.0, 420.0), 36.0), ((430.0, 560.0), 34.0), ((600.0, 430.0), 38.0),
             ((560.0, 640.0), 33.0)]
    for centre, radius in tight:
        empty.add_patch(Circle(centre, radius, fc=GLASS, alpha=0.4, ec=GLASS, lw=1.1, zorder=4))
    target = (430.0, 560.0)
    for angle in range(0, 360, 15):
        radians = math.radians(angle)
        spot = (target[0] + STANDOFF * math.cos(radians), target[1] + STANDOFF * math.sin(radians))
        empty.plot(*spot, marker="x", ms=7, mew=1.6, color=WARN, alpha=0.75, zorder=5)
    empty.add_patch(Circle(target, 52, fill=False, ec=WARN, lw=1.8, ls=(0, (4, 3)), zorder=6))
    empty.text(
        460, 95, "all 24 out of reach, blocked or unplannable.\n"
        "There is nothing for the model to put in order",
        ha="center", fontsize=NOTE_SIZE, color=INK,
    )
    empty.set_title("the list the veto empties", fontsize=LABEL_SIZE + 1.5, color=WARN, pad=8)
    empty.text(
        460, 1000, "not a perception failure: a fact about where the\n"
        "glasses stand, and the handover to problem 3",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )

    figure.suptitle(
        "Two limits, and only one of them is the model's fault",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.02,
    )
    save(figure, "06-where-it-stops-working.png")



# ------------------------------------- 9. the glass that contributes no pixels
#
# These last two pictures are about a glass that appears in no picture at all,
# so nothing in them may be drawn to look convincing. Both glasses are real
# outlines drawn by the project's own spawner, and every silhouette is that
# outline put through the cell's own camera.

_FAMILY = family("tapered_glass", 60, 7)
_BY_HEIGHT = sorted(_FAMILY, key=lambda item: item[0].total_height)
SHORT_GLASS, SHORT_PROPS = _BY_HEIGHT[0]
TALL_GLASS, TALL_PROPS = _BY_HEIGHT[-1]


def _outline_mm(outline) -> tuple[np.ndarray, np.ndarray]:
    """The outline's heights and radii, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def _height_mm(outline) -> float:
    return outline.total_height * 1000.0


def _rim_mm(outline) -> float:
    return outline.max_diameter * 1000.0


def _splayed(nadir, centre, outline, props):
    """Where the overhead camera puts this glass's outline, in table millimetres."""
    return splay_circles(
        nadir, centre, _height_mm(outline), _rim_mm(outline),
        base_fraction=props["base_fraction"],
    )


def _overhead_mask(glasses, nadir) -> np.ndarray:
    """One survey frame, looking straight down from SURVEY_H onto ``nadir``.

    A horizontal slice at height z is a circle still, but it is nearer the lens
    than the table is, so it is drawn larger and further out from the nadir.
    """
    mask = np.zeros((FRAME_H, FRAME_W), np.uint8)
    for x, y, outline in glasses:
        heights, radii = _outline_mm(outline)
        for z, radius in zip(heights, radii, strict=True):
            away = SURVEY_H - z
            cv2.circle(
                mask,
                (int(round(FRAME_W / 2 + FX * (x - nadir[0]) / away)),
                 int(round(FRAME_H / 2 + FX * (y - nadir[1]) / away))),
                max(1, int(round(FX * radius / away))), 255, -1,
            )
    return mask


def _level_mask(glasses, camera, target, horizon_row=None) -> np.ndarray:
    """One frame from VIEW_HEIGHT, looking level at ``target``.

    A horizontal slice seen edge-on is a line, so a glass fills the band
    between the left and right walls of its outline.
    """
    look = np.array([target[0] - camera[0], target[1] - camera[1]], dtype=float)
    look /= np.hypot(*look)
    side = np.array([-look[1], look[0]])
    horizon = FRAME_H / 2.0 if horizon_row is None else horizon_row
    mask = np.zeros((FRAME_H, FRAME_W), np.uint8)
    for x, y, outline in glasses:
        offset = np.array([x - camera[0], y - camera[1]], dtype=float)
        depth, lateral = float(offset @ look), float(offset @ side)
        if depth <= 1.0:
            continue
        heights, radii = _outline_mm(outline)
        rows = horizon - FX * (heights - VIEW_HEIGHT) / depth
        left = FRAME_W / 2 + FX * (lateral - radii) / depth
        right = FRAME_W / 2 + FX * (lateral + radii) / depth
        wall = np.vstack([
            np.stack([left, rows], axis=1),
            np.stack([right, rows], axis=1)[::-1],
        ])
        cv2.fillPoly(mask, [np.round(wall).astype(np.int32)], 255)
    return mask


def _clear_of(behind: np.ndarray, in_front: np.ndarray) -> int:
    """How many pixels of ``behind`` the nearer glass leaves showing."""
    return int(((behind > 0) & (in_front == 0)).sum())


def _paint_mask(axis, mask: np.ndarray, colour: str, alpha: float = 1.0) -> None:
    from matplotlib.colors import to_rgba
    rgba = np.zeros((*mask.shape, 4), float)
    rgba[mask > 0] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest", zorder=4)


# The pair that hides, from above: on one radius out from the nadir, the taller
# glass inboard. TALL_OUT is far enough out that the covering has margin in it.
TALL_OUT = 280.0
SHORT_OUT = TALL_OUT + MIN_SEPARATION


def _covers_from(nadir) -> bool:
    return splay_covers(
        _splayed(nadir, (TALL_OUT, 0.0), TALL_GLASS, TALL_PROPS),
        _splayed(nadir, (SHORT_OUT, 0.0), SHORT_GLASS, SHORT_PROPS),
    )


def _short_pixels_from(nadir) -> int:
    """Pixels of the short glass this station's picture actually shows."""
    tall = _overhead_mask([(TALL_OUT, 0.0, TALL_GLASS)], nadir)
    short = _overhead_mask([(SHORT_OUT, 0.0, SHORT_GLASS)], nadir)
    return _clear_of(short, tall)


def _degrees(value: float) -> str:
    """5.0 prints as 5, 29.5 prints as 29.5."""
    return f"{value:g}"


def hidden_from_above() -> None:
    """The overhead case: splay covering, and which stations would break it.

    The left panel draws one survey station's picture in millimetres of table,
    so that the frame edge and the splayed outlines can share a scale. The
    right panel scores every station the survey could have used instead, by
    the one thing wanted here: pixels of the short glass.
    """
    tall_h, short_h = _height_mm(TALL_GLASS), _height_mm(SHORT_GLASS)
    k_tall = SURVEY_H / (SURVEY_H - tall_h)
    k_short = SURVEY_H / (SURVEY_H - short_h)
    print(f"  tall glass  {tall_h:.0f} mm high, {_rim_mm(TALL_GLASS):.0f} mm rim, k = {k_tall:.2f}")
    print(f"  short glass {short_h:.0f} mm high, {_rim_mm(SHORT_GLASS):.0f} mm rim, "
          f"k = {k_short:.2f}")
    print(f"  k for a 225 mm rim at 450 mm: {SURVEY_H / (SURVEY_H - 225.0):.2f}")

    nadir = (0.0, 0.0)
    big = _splayed(nadir, (TALL_OUT, 0.0), TALL_GLASS, TALL_PROPS)
    small = _splayed(nadir, (SHORT_OUT, 0.0), SHORT_GLASS, SHORT_PROPS)
    print(f"  pair on one radius at {TALL_OUT:.0f} and {SHORT_OUT:.0f} mm: "
          f"covered = {splay_covers(big, small)}")
    print(f"  the tall glass's splayed outline is {splay_width(big):.0f} mm across")

    onset = next(
        d for d in np.arange(40.0, 500.0, 1.0)
        if splay_covers(
            _splayed((0, 0), (d, 0.0), TALL_GLASS, TALL_PROPS),
            _splayed((0, 0), (d + MIN_SEPARATION, 0.0), SHORT_GLASS, SHORT_PROPS))
    )
    across = next(a for a in np.arange(0.0, 400.0, 1.0) if not _covers_from((0.0, a)))
    along = next(a for a in np.arange(0.0, 400.0, 1.0) if not _covers_from((a, 0.0)))
    first_pixel = next(
        a for a in np.arange(0.0, 500.0, 1.0) if _short_pixels_from((a, 0.0)) > 0
    )
    short_limit = FRAME_HALF_X / k_short - _rim_mm(SHORT_GLASS) / 2.0
    print(f"  covering starts with the tall glass {onset:.0f} mm out from the nadir")
    print(f"  {across:.0f} mm across the radius breaks it, or {along:.0f} mm along it")
    print(f"  a {short_h:.0f} mm glass is wholly in frame only within {short_limit:.0f} mm "
          "of the nadir")
    print(f"  the short glass first reaches the picture {first_pixel:.0f} mm along the radius")

    figure, (scene, payoff) = plt.subplots(
        1, 2, figsize=(15.8, 6.4), gridspec_kw={"width_ratios": [1.1, 1.0], "wspace": 0.08},
    )
    figure.patch.set_facecolor(PAPER)
    for axis in (scene, payoff):
        axis.set_facecolor(PAPER)

    # ---- left: the station that misses it
    bare(scene)
    scene.set_aspect("equal")
    scene.set_xlim(-320, 780)
    scene.set_ylim(-430, 300)
    scene.add_patch(
        Rectangle((-FRAME_HALF_X, -FRAME_HALF_Y), 2 * FRAME_HALF_X, 2 * FRAME_HALF_Y,
                  fill=False, ec=INK, lw=1.4)
    )
    scene.text(
        -FRAME_HALF_X + 8, FRAME_HALF_Y - 10,
        f"the frame holds {2*FRAME_HALF_X:.0f} by {2*FRAME_HALF_Y:.0f} mm of table",
        fontsize=NOTE_SIZE, color=INK, va="top",
    )
    scene.plot([-310, 770], [0, 0], color=MUTED, lw=0.9, ls=(0, (5, 4)), zorder=1)
    scene.text(-250, -12, "the radius the pair lies on", fontsize=NOTE_SIZE, color=MUTED,
               va="top")
    scene.plot(0, 0, marker="+", ms=14, mew=1.8, color=INK, zorder=7)
    scene.text(0, 20, "the nadir", ha="center", fontsize=NOTE_SIZE, color=INK)

    for centre, outline in (((TALL_OUT, 0.0), TALL_GLASS), ((SHORT_OUT, 0.0), SHORT_GLASS)):
        radii = _outline_mm(outline)[1]
        scene.add_patch(
            Circle(centre, radii[0], fill=False, ec=MUTED, lw=1.2, ls=(0, (2, 2)), zorder=6)
        )
    for centre in ((TALL_OUT, -26.0), (SHORT_OUT, -26.0)):
        scene.annotate(
            "", xy=centre, xytext=(80, -195),
            arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 0.9},
        )
    scene.text(
        80, -205,
        f"where the {tall_h:.0f} mm glass and the {short_h:.0f} mm glass\n"
        f"really stand, {MIN_SEPARATION:.0f} mm apart",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )

    splay_patch(scene, big, colour=GLASS, alpha=0.20, zorder=3)
    splay_patch(scene, small, colour=WARN, alpha=0.80, zorder=4)
    scene.annotate(
        f"the taller glass, thrown out to\n{k_tall:.2f} times its real offset",
        xy=(k_tall * TALL_OUT, 104), xytext=(k_tall * TALL_OUT - 30, 272), ha="center",
        fontsize=NOTE_SIZE, color=GLASS,
        arrowprops={"arrowstyle": "-|>", "color": GLASS, "lw": 0.9},
    )
    scene.annotate(
        "the shorter glass, wholly\ninside it. It contributes\nno pixels at all",
        xy=(k_short * SHORT_OUT + 20, -k_short * _rim_mm(SHORT_GLASS) / 2.0 - 2),
        xytext=(600, -160), ha="center", va="top",
        fontsize=NOTE_SIZE, color=WARN,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 0.9},
    )
    scene.text(
        -320, -330,
        f"Both outlines land past the frame edge too. A {short_h:.0f} mm glass is wholly inside "
        f"the frame only within\n{short_limit:.0f} mm of the nadir, and the covering needs it "
        f"{onset + MIN_SEPARATION:.0f} mm out or further, so in this cell the two\n"
        "never happen at the same station.",
        fontsize=NOTE_SIZE, color=INK, va="top",
    )
    scene.set_title(
        "Looking straight down: the short glass is inside the tall one's outline",
        fontsize=TITLE_SIZE, color=INK, pad=10,
    )

    # ---- right: score every station the survey could have stood at
    bare(payoff)
    payoff.set_aspect("equal")
    payoff.set_xlim(-230, 700)
    payoff.set_ylim(-430, 330)
    xs = np.arange(-160.0, 641.0, 40.0)
    ys = np.arange(-280.0, 281.0, 40.0)
    shown = np.array([[_short_pixels_from((float(x), float(y))) for x in xs] for y in ys],
                     dtype=float)
    best = shown.max()
    print(f"  best station in the sweep shows {best:.0f} pixels of the short glass")
    print(f"  {int((shown == 0).sum())} of {shown.size} candidate stations show none of it")
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            value = shown[j, i]
            if value == 0:
                payoff.plot(x, y, marker="x", ms=4.2, mew=1.0, color=WARN, alpha=0.55, zorder=3)
            else:
                payoff.plot(
                    x, y, marker="o", ms=3.0 + 8.0 * (value / best) ** 0.5,
                    color=GOOD, alpha=0.35 + 0.5 * value / best, zorder=4,
                )
    payoff.plot([-220, 690], [0, 0], color=MUTED, lw=0.8, ls=(0, (5, 4)), zorder=2)
    for centre, outline in (((TALL_OUT, 0.0), TALL_GLASS), ((SHORT_OUT, 0.0), SHORT_GLASS)):
        radii = _outline_mm(outline)[1]
        payoff.add_patch(Circle(centre, radii[0], fc=GLASS, alpha=0.9, ec=GLASS, zorder=6))
    payoff.text(
        SHORT_OUT, 54, "the pair", ha="center", fontsize=NOTE_SIZE, color=GLASS, zorder=7,
        bbox={"fc": PAPER, "ec": "none", "alpha": 0.9, "pad": 1.4},
    )
    payoff.plot(0, 0, marker="+", ms=14, mew=1.8, color=INK, zorder=7)
    payoff.text(
        -16, -30, "the station\nthat missed it", ha="right", va="top", fontsize=NOTE_SIZE,
        color=INK, zorder=7, bbox={"fc": PAPER, "ec": "none", "alpha": 0.9, "pad": 1.4},
    )
    payoff.plot([0, 0], [0, across], color=WARN, lw=1.4, zorder=7)
    payoff.plot(0, across, marker="v", ms=7, color=WARN, zorder=8)
    payoff.text(
        -16, across + 24, f"{across:.0f} mm across", ha="right", fontsize=NOTE_SIZE, color=WARN,
        zorder=8, bbox={"fc": PAPER, "ec": "none", "alpha": 0.9, "pad": 1.4},
    )
    payoff.plot([0, first_pixel], [-26, -26], color=GOOD, lw=1.4, zorder=7)
    payoff.plot(first_pixel, -26, marker=">", ms=7, color=GOOD, zorder=8)
    payoff.text(
        first_pixel / 2.0, -36, f"{first_pixel:.0f} mm along", ha="center", va="top",
        fontsize=NOTE_SIZE, color=GOOD, zorder=8,
        bbox={"fc": PAPER, "ec": "none", "alpha": 0.9, "pad": 1.4},
    )
    payoff.text(
        -230, -320,
        "One mark per candidate station, 40 mm apart, each scored by rendering its picture. "
        "A circle is a\nstation that shows some of the short glass, drawn larger the more of it "
        "it shows, and a cross is one\n"
        f"that shows none. Moving {across:.0f} mm across the radius ends the covering and still "
        f"shows nothing, because\nthe pair is outside the frame. It takes {first_pixel:.0f} mm "
        "along the radius before any of the short glass arrives.",
        fontsize=NOTE_SIZE, color=INK, va="top",
    )
    payoff.set_title(
        "Every station scored by the thing wanted: pixels of the short glass",
        fontsize=TITLE_SIZE, color=INK, pad=10,
    )
    save(figure, "06-hidden-from-above.png")


# The pair that hides from the side. The camera stands off the glass it can
# see, at the cell's own measuring standoff, and the second glass is behind it.
SIDE_SEPARATION = 300.0
NEAR_AT = (0.0, 0.0)
FAR_AT = (0.0, SIDE_SEPARATION)


def _side_camera(azimuth_deg: float):
    angle = math.radians(azimuth_deg)
    return (NEAR_AT[0] + STANDOFF * math.sin(angle), NEAR_AT[1] - STANDOFF * math.cos(angle))


def _side_masks(azimuth_deg: float) -> tuple[np.ndarray, np.ndarray]:
    camera = _side_camera(azimuth_deg)
    near = _level_mask([(*NEAR_AT, TALL_GLASS)], camera, NEAR_AT)
    far = _level_mask([(*FAR_AT, SHORT_GLASS)], camera, NEAR_AT)
    return near, far


def _columns(mask: np.ndarray) -> tuple[int, int] | None:
    lit = np.where(mask.any(axis=0))[0]
    return (int(lit.min()), int(lit.max())) if len(lit) else None


def hidden_from_the_side() -> None:
    """The level case: line-of-sight blocking, and how small a step undoes it.

    The plan says where the camera stands, the middle panel is the picture
    from straight along the pair, and the right-hand panel scores every
    azimuth by the pixels of the far glass it brings back.
    """
    depth_near = STANDOFF
    depth_far = STANDOFF + SIDE_SEPARATION
    print(f"  the near glass stands {depth_near:.0f} mm from the camera and the far one "
          f"{depth_far:.0f} mm")
    print(f"  a millimetre sideways moves the near one {FX/depth_near:.2f} px "
          f"and the far one {FX/depth_far:.2f} px")

    camera = _side_camera(0.0)
    for separation in (MIN_SEPARATION, SIDE_SEPARATION, 600.0):
        near = _level_mask([(*NEAR_AT, TALL_GLASS)], camera, NEAR_AT)
        far = _level_mask([(0.0, separation, SHORT_GLASS)], camera, NEAR_AT)
        far_tall = _level_mask([(0.0, separation, TALL_GLASS)], camera, NEAR_AT)
        near_short = _level_mask([(*NEAR_AT, SHORT_GLASS)], camera, NEAR_AT)
        print(f"  {separation:.0f} mm behind, the tall glass in front: the far glass has "
              f"{int((far > 0).sum())} pixels and {_clear_of(far, near)} of them show")
        total = max(1, int((far_tall > 0).sum()))
        covered = total - _clear_of(far_tall, near_short)
        print(f"  {separation:.0f} mm behind, the short glass in front: it hides "
              f"{100.0 * covered / total:.0f} per cent of a tall far glass")

    azimuths = np.arange(0.0, 60.5, 0.5)
    recovered, gaps = [], []
    for angle in azimuths:
        near, far = _side_masks(float(angle))
        recovered.append(_clear_of(far, near))
        a, b = _columns(near), _columns(far)
        gaps.append(max(b[0] - a[1], a[0] - b[1]) if a and b else float("nan"))
    recovered = np.array(recovered, dtype=float)
    gaps = np.array(gaps, dtype=float)
    first = float(azimuths[np.argmax(recovered > 0)])
    split = float(azimuths[np.argmax(gaps >= GAP_NEEDED_PX)])
    print(f"  the far glass first shows a pixel at {first:g} degrees of azimuth")
    print(f"  the two silhouettes stand {GAP_NEEDED_PX:.0f} px apart at {split:g} degrees")
    per_degree = FX * SIDE_SEPARATION * math.radians(1.0) / depth_far
    print(f"  one degree of azimuth swings the far glass {per_degree:.1f} px across the frame")

    figure, (plan, picture, curve) = new(15.8, 6.0, columns=3)

    # ---- the plan
    bare(plan)
    plan.set_aspect("equal")
    plan.set_xlim(-440, 540)
    plan.set_ylim(-560, 440)
    plan.add_patch(Circle(NEAR_AT, STANDOFF, fill=False, ec=MUTED, lw=0.8, ls=(0, (2, 4))))
    plan.text(
        -320, 300, f"the standoff:\n{STANDOFF:.0f} mm", ha="center",
        fontsize=NOTE_SIZE, color=MUTED,
    )
    for centre, outline, label, side in (
        (FAR_AT, SHORT_GLASS, f"the {_height_mm(SHORT_GLASS):.0f} mm glass, behind", 1),
        (NEAR_AT, TALL_GLASS, f"the {_height_mm(TALL_GLASS):.0f} mm glass, in front", -1),
    ):
        radii = _outline_mm(outline)[1]
        plan.add_patch(Circle(centre, radii[0], fc=GLASS, alpha=0.75, ec=GLASS, lw=1.2, zorder=5))
        plan.text(
            centre[0] + 56 * side, centre[1] + 26, label, va="center",
            ha="left" if side > 0 else "right", fontsize=NOTE_SIZE, color=GLASS,
        )
    plan.annotate(
        "", xy=(-80, FAR_AT[1] - 20), xytext=(-80, NEAR_AT[1] + 20),
        arrowprops={"arrowstyle": "<|-|>", "color": INK, "lw": 0.9},
    )
    plan.text(-92, SIDE_SEPARATION / 2, f"{SIDE_SEPARATION:.0f} mm apart", ha="right",
              va="center", fontsize=NOTE_SIZE, color=INK)

    for angle, colour, note, where, align in (
        (0.0, WARN, "straight along the pair:\nnothing of the far glass", (-40, -450), "right"),
        (first, GLASS, f"{_degrees(first)} degrees round: its\nfirst pixels come back",
         (70, -480), "left"),
        (split, GOOD, f"{_degrees(split)} degrees round: {GAP_NEEDED_PX:.0f} px\n"
                      "of table between them", (400, -300), "center"),
    ):
        spot = _side_camera(angle)
        _camera(plan, spot, NEAR_AT, colour, lw=1.4, ms=7)
        plan.annotate(
            note, xy=spot, xytext=where, ha=align, va="top",
            fontsize=NOTE_SIZE, color=colour,
            arrowprops={"arrowstyle": "-|>", "color": colour, "lw": 0.9,
                        "shrinkA": 3, "shrinkB": 8},
        )
    plan.set_title(
        "Looking level, from 120 mm up and 380 mm back",
        fontsize=LABEL_SIZE + 1.5, color=INK, pad=8,
    )

    # ---- the picture from straight along the pair
    near, far = _side_masks(0.0)
    bare(picture)
    picture.set_xlim(-10, 330)
    picture.set_ylim(FRAME_H + 128, -30)
    picture.set_aspect("equal")
    picture.add_patch(Rectangle((0, 0), FRAME_W, FRAME_H, fill=False, ec=MUTED, lw=1.0))
    picture.plot([0, FRAME_W], [FRAME_H / 2, FRAME_H / 2], color=MUTED, lw=0.8, ls=(0, (4, 4)))
    picture.text(
        4, FRAME_H / 2 - 5, "the horizon",
        fontsize=NOTE_SIZE - 0.6, color=MUTED, va="bottom",
    )
    _paint_mask(picture, near, GLASS, alpha=0.9)
    picture.contour(far.astype(float), [0.5], colors=[WARN], linewidths=1.4,
                    linestyles="dashed", zorder=6)
    columns = _columns(near)
    picture.annotate(
        "the far glass stands exactly here,\nand none of it reaches the lens",
        xy=(196, 156), xytext=(324, 254), ha="right", va="top",
        fontsize=NOTE_SIZE, color=WARN,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 0.9},
    )
    picture.text(
        160, 316,
        f"One silhouette, {columns[1] - columns[0]:.0f} px across, and a width the fit accepts.\n"
        f"The far glass would have had {int((far > 0).sum())} pixels. "
        f"{_clear_of(far, near)} of them show.\n"
        "The dashed line across the frame is the horizon, which a level camera\n"
        "puts on the middle row of the picture.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    picture.set_title(
        "What comes back from straight along the pair",
        fontsize=LABEL_SIZE + 1.5, color=WARN, pad=8,
    )

    # ---- the payoff against azimuth
    top = recovered.max()
    curve.plot(azimuths, recovered, color=GOOD, lw=2.0, zorder=4)
    curve.axvline(first, color=GLASS, lw=1.1, ls=(0, (4, 3)), zorder=2)
    curve.axvline(split, color=GOOD, lw=1.1, ls=(0, (4, 3)), zorder=2)
    curve.set_xlim(-1.5, 60)
    curve.set_ylim(-160, top * 1.5)
    curve.annotate(
        f"{_degrees(first)} degrees: the far glass's\nfirst pixel comes back",
        xy=(first, top * 1.10), xytext=(first + 3.2, top * 1.44), ha="left", va="top",
        fontsize=NOTE_SIZE, color=GLASS,
        arrowprops={"arrowstyle": "-|>", "color": GLASS, "lw": 0.9},
    )
    curve.annotate(
        f"{_degrees(split)} degrees: enough table between\nthem for two circles to fit",
        xy=(split, top * 0.30), xytext=(split + 3.0, top * 0.55), ha="left", va="top",
        fontsize=NOTE_SIZE, color=GOOD,
        arrowprops={"arrowstyle": "-|>", "color": GOOD, "lw": 0.9},
    )
    curve.set_xlabel("degrees of azimuth round the glass in front", fontsize=LABEL_SIZE, color=INK)
    curve.set_ylabel("pixels of the far glass the picture shows", fontsize=LABEL_SIZE, color=INK)
    curve.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
    for side in ("top", "right"):
        curve.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        curve.spines[side].set_color(MUTED)
        curve.spines[side].set_linewidth(0.8)
    curve.grid(axis="y", color=MUTED, alpha=0.18, lw=0.7)
    curve.set_axisbelow(True)
    curve.text(
        0.5, -0.16,
        f"One degree of azimuth swings the far glass {per_degree:.1f} px across the frame. "
        f"The near glass is\n{depth_near:.0f} mm from the lens and the far one {depth_far:.0f} mm, "
        "and the shift goes as one over the depth.",
        transform=curve.transAxes, ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    curve.set_title(
        "Every azimuth scored the same way", fontsize=LABEL_SIZE + 1.5, color=INK, pad=8,
    )

    figure.suptitle(
        "Looking level: the hiding is plain line of sight, and a small step undoes it",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.0,
    )
    save(figure, "06-hidden-from-the-side.png")


def main() -> None:
    the_rule_cannot_tell_them_apart()
    three_scorers()
    one_training_example()
    the_features()
    veto_then_ordering()
    supervised_against_reinforcement()
    improves_with_use()
    where_it_stops_working()
    hidden_from_above()
    hidden_from_the_side()


if __name__ == "__main__":
    main()
