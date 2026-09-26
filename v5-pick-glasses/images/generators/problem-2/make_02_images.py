"""Diagrams for solution 2 — cluster on the table.

Ten pictures, each carrying one point of the argument: how a pixel becomes a
point in the room, why the room beats the picture, the four steps, why the
points are flattened onto the table first, how the one grouping distance is
chosen, how the circle fit vetoes an impossible footprint, why two stations are
asked to agree, where the whole idea stops working, and the two ways a glass
comes to be hidden completely.

Every silhouette drawn here is a real projection of one of the project's own
glass outlines, taken from ``work_cell.glasses.shapes``, through the cell's own
camera. A standing glass is a circle only in its footprint, which no camera in
this cell ever sees straight on, so nothing here is drawn as one.

Run from the project root:

    pixi run python images/generators/problem-2/make_02_images.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    TITLE_SIZE,
    KIND_NARROWEST,
    KIND_WIDEST,
    SHORT_A,
    SHORT_B,
    TALL_A,
    TALL_B,
    WARN,
    bare,
    new,
    save,
    splay_circles,
    splay_covers,
    splay_patch,
    splay_width,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import family  # noqa: E402

RNG = np.random.default_rng(20250925)

# The zone the objects stand in, in millimetres from the arm's base.
ZONE = (320.0, 640.0, -440.0, -80.0)

SURVEY_HEIGHT = 450.0   # mm above the table top
VIEW_HEIGHT = 120.0     # mm above the table, the height the level view looks from
STANDOFF = 380.0        # mm back from the glass the level view stands
FX = 277.1              # pixels; the camera's focal length
MIN_APART = 150.0       # mm centre to centre, the closest two glasses ever stand
OBJECT_HEIGHT = 205.0   # mm, the one glass the pixel-to-point figure draws

# Two of the project's own glasses, drawn from the two ends of this kind's range
# by the same spawner the run uses. The hiding pictures need real outlines rather
# than the plain heights and widths the other pictures work from, because whether
# one glass covers another depends on the shape of the wall between base and rim.
_FAMILY = [outline for outline, _ in family("tapered_glass", 40, 2)]
TALL_GLASS = max(_FAMILY, key=lambda outline: outline.total_height)
SHORT_GLASS = min(_FAMILY, key=lambda outline: outline.total_height)
TALL_HEIGHT = TALL_GLASS.total_height * 1000.0
SHORT_HEIGHT = SHORT_GLASS.total_height * 1000.0
TALL_RIM = TALL_GLASS.max_diameter * 1000.0
SHORT_RIM = SHORT_GLASS.max_diameter * 1000.0
TALL_LIFT = SURVEY_HEIGHT / (SURVEY_HEIGHT - TALL_HEIGHT)
SHORT_LIFT = SURVEY_HEIGHT / (SURVEY_HEIGHT - SHORT_HEIGHT)

# The pair most of these pictures use, taken from the two ends of this kind's
# range rather than from the middle. Drawing two glasses of a similar size would
# show a pair this cell can produce but would hide the case that makes problem 2
# hard, so the default pair here is one large glass and one of the smallest the
# kind allows.
FOOTPRINT_A = TALL_A[1]
FOOTPRINT_B = SHORT_A[1]
HEIGHT_A = TALL_A[0]
HEIGHT_B = SHORT_A[0]


# --------------------------------------------------------------------------- #
# small shared drawing helpers
# --------------------------------------------------------------------------- #

def disc_dots(centre, diameter, count):
    """Points scattered evenly over a footprint, as the flattened cloud looks."""
    radius = diameter / 2.0
    angle = RNG.random(count) * 2.0 * np.pi
    reach = radius * np.sqrt(RNG.random(count))
    return centre[0] + reach * np.cos(angle), centre[1] + reach * np.sin(angle)


def footprint(axis, centre, diameter, colour=GLASS, dots=170, edge=True):
    """A footprint drawn as its dots, with the outline behind them."""
    if edge:
        axis.add_patch(
            Circle(centre, diameter / 2.0, facecolor=colour, alpha=0.13, edgecolor="none", zorder=1)
        )
    x, y = disc_dots(centre, diameter, dots)
    axis.scatter(x, y, s=2.0, color=colour, zorder=3, linewidths=0)


def glass_side(axis, centre_x, base, height, diameter, taper=0.80, colour=GLASS, alpha=0.22):
    """An upright object seen from the side: a gently tapered outline."""
    half_top = diameter / 2.0
    half_base = half_top * taper
    poly = [
        (centre_x - half_base, base),
        (centre_x - half_top, base + height),
        (centre_x + half_top, base + height),
        (centre_x + half_base, base),
    ]
    axis.add_patch(
        Polygon(poly, closed=True, facecolor=colour, alpha=alpha, edgecolor=INK, lw=1.0, zorder=2)
    )
    return poly


def span(axis, start, end, text, colour=INK, above=True, pad=6.0, size=NOTE_SIZE):
    """A double-headed arrow with a label, for stating a distance."""
    axis.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={"arrowstyle": "<->", "color": colour, "lw": 1.1, "shrinkA": 0, "shrinkB": 0},
        zorder=6,
    )
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    axis.text(
        mid[0],
        mid[1] + (pad if above else -pad),
        text,
        ha="center",
        va="bottom" if above else "top",
        fontsize=size,
        color=colour,
        zorder=6,
    )


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, ha="left", va="top", weight="normal"):
    axis.text(x, y, text, fontsize=size, color=colour, ha=ha, va=va, zorder=7, weight=weight)


def panel_title(axis, text, colour=INK):
    axis.set_title(text, fontsize=LABEL_SIZE + 0.6, color=colour, pad=8)


def plan_axis(axis, pad=30.0):
    """A plan view of the object zone, in millimetres from the arm's base."""
    x0, x1, y0, y1 = ZONE
    axis.add_patch(
        Rectangle(
            (x0, y0), x1 - x0, y1 - y0, facecolor=MUTED, alpha=0.07, edgecolor=MUTED,
            lw=0.8, ls=(0, (4, 3)), zorder=0,
        )
    )
    axis.set_xlim(x0 - pad, x1 + pad)
    axis.set_ylim(y0 - pad, y1 + pad)
    axis.set_aspect("equal")
    bare(axis)


# --------------------------------------------------------------------------- #
# 1. one pixel becomes a ray becomes a point
# --------------------------------------------------------------------------- #

def figure_pixel_to_point() -> None:
    figure, (left, right) = new(12.4, 5.6, columns=2)

    # ---- the picture -----------------------------------------------------
    bare(left)
    left.set_xlim(-30, 386)
    left.set_ylim(-150, 265)
    left.set_aspect("equal")
    panel_title(left, "1. What the camera hands over: a grid of numbers")

    left.add_patch(Rectangle((0, 0), 320, 240, facecolor="none", edgecolor=INK, lw=1.2))
    for column in range(0, 321, 20):
        left.plot([column, column], [0, 240], color=MUTED, lw=0.3, alpha=0.5, zorder=0)
    for row in range(0, 241, 20):
        left.plot([0, 320], [row, row], color=MUTED, lw=0.3, alpha=0.5, zorder=0)

    # the chosen pixel, u = 200 across and v = 169 down from the top-left
    pixel = Rectangle((200, 240 - 180), 20, 20, facecolor=GLASS, edgecolor=INK, lw=1.0, zorder=4)
    left.add_patch(pixel)
    left.plot([160, 160], [0, 240], color=WARN, lw=0.8, ls=(0, (3, 3)), zorder=2)
    left.plot([0, 320], [120, 120], color=WARN, lw=0.8, ls=(0, (3, 3)), zorder=2)
    note(left, 163, 250, "the middle of the picture: cx = 160, cy = 120", colour=WARN, va="bottom")

    left.annotate(
        "one pixel:\nu = 200, v = 169\ndepth = 0.245 m",
        xy=(220, 70),
        xytext=(262, 234),
        fontsize=NOTE_SIZE,
        color=INK,
        ha="left",
        va="top",
        arrowprops={"arrowstyle": "->", "color": INK, "lw": 1.0},
    )
    note(left, 0, -16, "320 x 240 pixels. Every pixel holds one number: how far away\nthe nearest"
         " surface is along the direction that pixel looks.", colour=MUTED)
    note(
        left, 0, -62,
        "In the camera's own frame:\n"
        "   X = (u - cx) x Z / fx = (200 - 160) x 0.245 / 277.1 = +0.0354 m\n"
        "   Y = (v - cy) x Z / fy = (169 - 120) x 0.245 / 277.1 = +0.0433 m\n"
        "   Z = 0.245 m, straight out along the lens axis",
        colour=INK,
    )

    # ---- the room --------------------------------------------------------
    bare(right)
    right.set_xlim(-470, 360)
    right.set_ylim(-235, 560)
    right.set_aspect("equal")
    panel_title(right, "2. What that means in the room, seen from the side")

    # table top
    right.plot([-460, 350], [0, 0], color=INK, lw=2.0, zorder=3)
    note(right, -460, -12, "table top, 750 mm off the floor", colour=MUTED)

    # camera
    camera = (0.0, SURVEY_HEIGHT)
    right.add_patch(
        Rectangle((-34, SURVEY_HEIGHT + 4), 68, 34, facecolor=INK, edgecolor="none", zorder=5)
    )
    right.scatter([0], [SURVEY_HEIGHT], s=18, color=WARN, zorder=6)
    note(right, 0, SURVEY_HEIGHT + 52, "wrist camera, 450 mm above the table", colour=INK, ha="center",
         va="bottom")

    # field of view: 60 degrees across, so +- 260 mm at the table
    for edge in (-260.0, 260.0):
        right.plot([camera[0], edge], [camera[1], 0], color=MUTED, lw=0.9, ls=(0, (5, 4)), zorder=1)
    note(right, -460, 500, "one picture covers\n520 mm of table", colour=MUTED)

    # the object the ray lands on
    glass_side(right, 56.0, 0.0, OBJECT_HEIGHT, 85.0)

    # the ray, and the point it ends at
    hit = (35.4, OBJECT_HEIGHT)
    right.annotate(
        "",
        xy=hit,
        xytext=camera,
        arrowprops={"arrowstyle": "-", "color": GLASS, "lw": 1.8},
        zorder=4,
    )
    right.scatter([hit[0]], [hit[1]], s=46, color=GOOD, zorder=7, edgecolors=INK, linewidths=0.6)
    right.annotate(
        "the point in the room:\nx = 0.515 m, y = -0.303 m,\n205 mm above the table",
        xy=hit,
        xytext=(120, 330),
        fontsize=NOTE_SIZE,
        color=INK,
        ha="left",
        va="center",
        arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 1.1},
    )

    span(right, (-190, 0), (-190, SURVEY_HEIGHT), "", colour=MUTED)
    right.text(
        -198, SURVEY_HEIGHT / 2.0, "450 mm", rotation=90, ha="right", va="center",
        fontsize=NOTE_SIZE, color=MUTED,
    )
    span(right, (-110, SURVEY_HEIGHT), (-110, OBJECT_HEIGHT), "", colour=INK)
    right.text(
        -116, (SURVEY_HEIGHT + OBJECT_HEIGHT) / 2.0, "Z = 0.245 m", rotation=90, ha="right",
        va="center", fontsize=NOTE_SIZE, color=INK,
    )
    span(right, (0, OBJECT_HEIGHT + 46), (35.4, OBJECT_HEIGHT + 46), "", colour=INK)
    note(right, -6, OBJECT_HEIGHT + 46, "X = 35.4 mm", colour=INK, va="center", ha="right")
    note(right, -460, -46, "the pixel gives the direction.\nthe depth gives how far along it.\n"
         "the arm's pose gives where it starts.", colour=INK)

    figure.suptitle(
        "A pixel is not a thing. It is a direction with a distance written on it.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    save(figure, "02-pixel-to-point.png")


# --------------------------------------------------------------------------- #
# 2. merged in the picture, plainly apart on the table
# --------------------------------------------------------------------------- #

def figure_picture_versus_table() -> None:
    """Four glasses of one kind: two large, two of the smallest the kind allows.

    The arrangement is a legal one. Every pair of centres is at least the
    guaranteed gap apart and every size is inside the kind's range. What the
    overhead picture does with it is the whole point of this solution.
    """
    figure, (left, right) = new(13.0, 4.8, columns=2)

    nadir = np.array([0.0, 0.0])
    scene = (
        ("T1", np.array([185.0, -40.0]), TALL_A),
        ("S1", np.array([335.0, -70.0]), SHORT_A),     # T1 covers this one entirely
        ("T2", np.array([-95.0, 150.0]), TALL_B),
        ("S2", np.array([-215.0, 275.0]), SHORT_B),    # T2's outline reaches this one
    )
    place = {name: pos for name, pos, _ in scene}
    size_of = {name: size for name, _, size in scene}
    shapes = {name: splay_circles(nadir, pos, *size) for name, pos, size in scene}

    covered = splay_covers(shapes["T1"], shapes["S1"])
    patch_mm = splay_width(shapes["T1"])
    limits = ((-400, 520), (-190, 430))

    for axis in (left, right):
        bare(axis)
        axis.set_aspect("equal")
        axis.set_xlim(*limits[0])
        axis.set_ylim(*limits[1])
        axis.scatter([0], [0], s=34, color=WARN, marker="x", zorder=9)

    # ------------------------------------------------- the picture, left panel
    panel_title(left, "What the overhead picture holds: two patches", colour=WARN)
    for name, _, _ in scene:
        hidden = name == "S1" and covered
        splay_patch(left, shapes[name], colour=MUTED if hidden else GLASS,
                    alpha=0.14 if hidden else 0.34, zorder=2 if hidden else 3)
    note(left, 14, -14, "camera", colour=WARN, va="top")
    tip = shapes["S1"][-1][0]
    left.annotate(
        "S1 is under here.\nNot one pixel of it\nreaches the picture.",
        xy=tuple(tip), xytext=(tip[0] - 40, 330), fontsize=NOTE_SIZE, color=WARN,
        ha="center", va="bottom",
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )
    note(left, -330, 430, "T2 and S2 run together:\none patch, two glasses",
         colour=WARN, va="top")

    # ---------------------------------------------------- the table, right panel
    panel_title(right, "What is actually on the table: four glasses, none touching", colour=GOOD)
    for name, pos, size in scene:
        colour = GOOD if name.startswith("T") else GLASS
        footprint(right, tuple(pos), size[1], colour=colour, dots=120)
    note(right, 14, -14, "camera", colour=WARN, va="top")
    for name, dx, dy, ha, va in (("T1", 0, -62, "center", "top"),
                                 ("S1", 46, 30, "left", "bottom"),
                                 ("T2", -66, 0, "right", "center"),
                                 ("S2", 0, 46, "center", "bottom")):
        pos, size = place[name], size_of[name]
        note(right, pos[0] + dx, pos[1] + dy,
             f"{name}\n{size[0]:.0f} mm tall, {size[1]:.0f} mm across",
             colour=INK, ha=ha, va=va)
    for a, b in (("T1", "S1"), ("T2", "S2")):
        right.annotate("", xy=tuple(place[b]), xytext=tuple(place[a]),
                       arrowprops={"arrowstyle": "<->", "color": GOOD, "lw": 1.5}, zorder=6)
        mid = (place[a] + place[b]) / 2.0
        note(right, mid[0] + 26, mid[1] + 8, f"{np.hypot(*(place[b] - place[a])):.0f} mm",
             colour=GOOD, size=LABEL_SIZE, weight="bold", ha="left", va="bottom")

    figure.suptitle(
        "One kind, a wide range of sizes: a tall glass's outline can cover a short one completely.",
        fontsize=TITLE_SIZE, color=INK, y=1.00,
    )
    figure.tight_layout()
    figure.text(
        0.06, -0.14,
        "Every pair of centres here is at least the guaranteed gap apart, and every size is inside "
        "the kind's range, so the arrangement is an ordinary one.\n"
        f"T1 is tall and close to the camera, so its outline is thrown a long way outwards — far "
        f"enough to cover S1 entirely. That outline runs across about {patch_mm:.0f} mm of table, but "
        "every dot under it back-projects to\nT1's own footprint, "
        f"{FOOTPRINT_A:.0f} mm across, which is an ordinary width for this kind, so the group that "
        "comes back looks perfectly normal. The merge of T2 and S2 is at least\nloud, because that "
        "group is wider than any one glass can be. The missing glass is silent.",
        fontsize=NOTE_SIZE, color=INK, ha="left", va="top",
    )
    save(figure, "02-merged-in-the-picture.png")


# --------------------------------------------------------------------------- #
# 3. the four steps
# --------------------------------------------------------------------------- #

def figure_four_steps() -> None:
    figure, axes = new(15.0, 4.6, columns=4)
    one, two, three, four = axes

    # ---- step 1: the depth picture ---------------------------------------
    bare(one)
    one.set_xlim(-20, 340)
    one.set_ylim(-150, 264)
    one.set_aspect("equal")
    panel_title(one, "1. A depth picture")
    one.add_patch(Rectangle((0, 0), 320, 240, facecolor=MUTED, alpha=0.06, edgecolor=INK, lw=1.1))
    for poly, shade in (([(96, 20), (104, 150), (168, 150), (160, 20)], 0.42),
                        ([(150, 52), (162, 196), (236, 196), (222, 52)], 0.22)):
        one.add_patch(Polygon(poly, closed=True, facecolor=GLASS, alpha=shade, edgecolor="none"))
    note(one, 0, -16, "Every pixel with a reading, turned into\na point in the room. Darker is nearer.",
         colour=INK)

    # ---- step 2: points above the table ----------------------------------
    bare(two)
    two.set_xlim(-60, 300)
    two.set_ylim(-150, 340)
    panel_title(two, "2. Keep what stands on the table")
    two.plot([-50, 290], [0, 0], color=INK, lw=1.8)
    two.plot([-50, 290], [5, 5], color=GOOD, lw=0.9, ls=(0, (4, 3)))
    two.plot([-50, 290], [260, 260], color=GOOD, lw=0.9, ls=(0, (4, 3)))
    note(two, 288, 264, "260 mm above the table", colour=GOOD, ha="right", va="bottom")
    note(two, -58, 12, "5 mm above the table", colour=GOOD, va="bottom")
    for centre_x, width in ((40.0, FOOTPRINT_A), (217.0, FOOTPRINT_B)):
        glass_side(two, centre_x, 0.0, OBJECT_HEIGHT, width, alpha=0.14)
        x = centre_x + (RNG.random(90) - 0.5) * width
        y = OBJECT_HEIGHT - np.abs(RNG.normal(0, 46, 90))
        two.scatter(x, np.clip(y, 6, OBJECT_HEIGHT), s=2.2, color=GLASS, zorder=5, linewidths=0)
    x = -40 + RNG.random(70) * 330
    two.scatter(x, RNG.normal(0, 1.4, 70), s=2.2, color=MUTED, zorder=4, linewidths=0)
    note(two, -58, -16, "Points on the table plane are dropped: the\nplane's height was measured at"
         " startup, so\nthis is a comparison, not a search.", colour=INK)

    # ---- step 3: flatten and group ---------------------------------------
    panel_title(three, "3. Flatten, then group by distance")
    plan_axis(three)
    centre_a = (420.0, -310.0)
    centre_b = (550.0, -190.0)
    footprint(three, centre_a, FOOTPRINT_A, colour=GOOD)
    footprint(three, centre_b, FOOTPRINT_B, colour=GLASS)
    three.add_patch(
        Circle(centre_a, FOOTPRINT_A / 2.0 + 25.0, facecolor="none", edgecolor=GOOD, lw=1.0,
               ls=(0, (3, 3)), zorder=4)
    )
    note(three, 336, -240, "25 mm", colour=GOOD, va="bottom")
    note(three, 336, -424,
         "Start at one point, take everything within\n25 mm, then everything within 25 mm of\nthose."
         " Two groups, not one.", colour=INK, va="bottom")

    # ---- step 4: fit a circle --------------------------------------------
    panel_title(four, "4. Fit a circle to each group")
    plan_axis(four)
    for centre, width in ((centre_a, FOOTPRINT_A), (centre_b, FOOTPRINT_B)):
        x, y = disc_dots(centre, width, 150)
        four.scatter(x, y, s=1.8, color=MUTED, zorder=2, linewidths=0)
        four.add_patch(
            Circle(centre, width / 2.0, facecolor="none", edgecolor=GOOD, lw=2.0, zorder=5)
        )
        four.scatter([centre[0]], [centre[1]], s=22, color=GOOD, marker="+", zorder=6)
    note(four, centre_a[0], centre_a[1] + 48, f"{FOOTPRINT_A:.0f} mm\n(0.420, -0.310)", colour=GOOD, ha="center",
         va="bottom")
    note(four, centre_b[0], centre_b[1] + 48, f"{FOOTPRINT_B:.0f} mm\n(0.550, -0.190)", colour=GOOD, ha="center",
         va="bottom")
    note(four, 336, -424, "A fit uses every dot, where a bounding box\nuses the two extreme ones."
         " The diameter is\nthen checked against what this kind can be.", colour=INK, va="bottom")

    figure.suptitle(
        "The whole method: points, then heights, then distance on the table, then one circle each.",
        fontsize=TITLE_SIZE, color=INK, y=1.04,
    )
    figure.tight_layout()
    save(figure, "02-four-steps.png")


# --------------------------------------------------------------------------- #
# 4. why flatten first
# --------------------------------------------------------------------------- #

def figure_why_flatten() -> None:
    figure, (left, right) = new(12.6, 5.4, columns=2)

    centres = (20.0, 205.0)
    widths = (FOOTPRINT_A, FOOTPRINT_B)
    heights = (HEIGHT_A, HEIGHT_B)
    tallest = max(heights)

    bare(left)
    left.set_xlim(-262, 430)
    left.set_ylim(-175, 300)
    left.set_aspect("equal")
    panel_title(left, "In full 3-D: no single distance works", colour=WARN)
    left.plot([-240, 420], [0, 0], color=INK, lw=1.8)

    for centre_x, width, height in zip(centres, widths, heights, strict=True):
        glass_side(left, centre_x, 0.0, height, width, alpha=0.12)
        cap_x = centre_x + (RNG.random(70) - 0.5) * width
        left.scatter(cap_x, height - RNG.random(70) * 8, s=2.4, color=GLASS, zorder=5,
                     linewidths=0)
        skirt_x = centre_x + np.sign(RNG.random(24) - 0.5) * (width / 2.0) * 0.82
        left.scatter(skirt_x, 8 + RNG.random(24) * 16, s=2.4, color=GLASS, zorder=5, linewidths=0)

    left.add_patch(
        Rectangle((-245, 30), 670, tallest - 45, facecolor=WARN, alpha=0.07, edgecolor="none",
                  zorder=0)
    )
    note(left, -244, tallest - 45, "no points up here: from almost\noverhead the wall is edge-on to\nthe"
         " camera, so nothing lands on it", colour=WARN)

    span(left, (272, 26), (272, heights[0] - 6), "", colour=WARN)
    left.text(282, heights[0] / 2.0, f"{heights[0]:.0f} mm\nthe tall glass,\ntop to base",
              ha="left", va="center", fontsize=NOTE_SIZE, color=WARN)

    # the gap between the two glasses at the height of the shorter one's rim
    gap_start = (centres[0] + widths[0] / 2.0, heights[1])
    gap_end = (centres[1] - widths[1] / 2.0, heights[1])
    apart = gap_end[0] - gap_start[0]
    left.annotate("", xy=gap_end, xytext=gap_start,
                  arrowprops={"arrowstyle": "<->", "color": GOOD, "lw": 1.4}, zorder=6)
    note(left, (gap_start[0] + gap_end[0]) / 2.0, heights[1] + 10,
         f"{apart:.0f} mm: different glasses", colour=GOOD, ha="center", va="bottom")
    note(
        left, -244, -32,
        f"Under {apart:.0f} mm and one glass breaks into a cap and a skirt.\n"
        f"Over {heights[0]:.0f} mm and the two glasses become one group.\n"
        f"{heights[0]:.0f} mm is more than {apart:.0f} mm, so there is no number that does both.",
        colour=INK,
    )

    panel_title(right, "Flattened onto the table: one distance does both jobs", colour=GOOD)
    plan_axis(right)
    centre_a = (420.0, -310.0)
    centre_b = (560.0, -180.0)
    footprint(right, centre_a, FOOTPRINT_A)
    footprint(right, centre_b, FOOTPRINT_B)
    direction = np.array(centre_b) - np.array(centre_a)
    unit = direction / np.hypot(*direction)
    start_pt = np.array(centre_a) + unit * (FOOTPRINT_A / 2.0)
    end_pt = np.array(centre_b) - unit * (FOOTPRINT_B / 2.0)
    clear = float(np.hypot(*(end_pt - start_pt)))
    right.annotate("", xy=tuple(end_pt), xytext=tuple(start_pt),
                   arrowprops={"arrowstyle": "<->", "color": GOOD, "lw": 1.6}, zorder=6)
    note(right, 446, -244, f"{clear:.0f} mm of bare table", colour=GOOD, size=LABEL_SIZE,
         weight="bold", ha="right", va="center")
    for centre, width in ((centre_a, FOOTPRINT_A), (centre_b, FOOTPRINT_B)):
        span(right, (centre[0] - width / 2.0, centre[1] - 54),
             (centre[0] + width / 2.0, centre[1] - 54),
             f"{int(width)} mm wide", colour=INK, above=False, pad=5)
    note(
        right, 336, -440,
        f"The height is gone: it was the one dimension that did not help.\n"
        f"Anything from about 10 mm up to {clear:.0f} mm now holds one footprint\n"
        "together and keeps two apart. 25 mm is the choice.",
        colour=INK, va="bottom",
    )

    figure.suptitle(
        f"One kind, two very different glasses: {heights[0]:.0f} mm tall and {widths[0]:.0f} mm "
        f"wide beside {heights[1]:.0f} mm tall and {widths[1]:.0f} mm wide.",
        fontsize=TITLE_SIZE, color=INK, y=1.03,
    )
    figure.tight_layout()
    save(figure, "02-why-flatten.png")


# --------------------------------------------------------------------------- #
# 5. the grouping distance window
# --------------------------------------------------------------------------- #

def figure_grouping_distance() -> None:
    # The upper end of the window: two glasses at the guaranteed gap, both of
    # them the widest this kind allows, leave this much bare table between their
    # rims. It is the worst case, because any narrower glass leaves more.
    worst_gap = MIN_APART - KIND_WIDEST

    figure, axis = new(11.6, 4.2)
    bare(axis)
    axis.set_xlim(-14, 176)
    axis.set_ylim(-1.55, 1.45)

    bar_low, bar_high = 0.0, 0.42
    axis.add_patch(Rectangle((0, bar_low), 10, bar_high, facecolor=WARN, alpha=0.30, edgecolor="none"))
    axis.add_patch(Rectangle((10, bar_low), worst_gap - 10, bar_high, facecolor=GOOD, alpha=0.38,
                             edgecolor="none"))
    axis.add_patch(Rectangle((worst_gap, bar_low), 160 - worst_gap, bar_high, facecolor=WARN,
                             alpha=0.30, edgecolor="none"))
    axis.add_patch(Rectangle((0, bar_low), 160, bar_high, facecolor="none", edgecolor=INK, lw=1.0))

    for tick in range(0, 161, 20):
        axis.plot([tick, tick], [-0.06, 0.0], color=INK, lw=1.0)
        axis.text(tick, -0.14, str(tick), ha="center", va="top", fontsize=NOTE_SIZE, color=INK)
    axis.text(80, -0.44, "grouping distance, mm", ha="center", va="top", fontsize=LABEL_SIZE,
              color=INK)

    axis.annotate(
        "25 mm: the choice",
        xy=(25, bar_high),
        xytext=(25, 1.02),
        ha="center",
        fontsize=LABEL_SIZE,
        color=GOOD,
        weight="bold",
        arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 1.4},
    )
    axis.text(35, 0.21, "works", ha="center", va="center", fontsize=NOTE_SIZE, color=INK)

    axis.annotate(
        "too small",
        xy=(5, bar_high + 0.02),
        xytext=(2, 0.70),
        ha="left",
        fontsize=NOTE_SIZE,
        color=WARN,
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )
    axis.text(
        108, 0.62,
        "too big: the chain hops from one footprint to the next,\nand two objects come back as one",
        ha="center", va="bottom", fontsize=NOTE_SIZE, color=WARN,
    )

    axis.text(
        0, -0.62,
        "Lower end, set by the scatter within one footprint:\n"
        "  one pixel is about 1.6 mm of table at survey height, and less than\n"
        "  that on the rim of a tall glass, which is nearer the camera;\n"
        "  depth noise adds a few mm. Below about 10 mm the chain breaks and\n"
        "  one object is reported as several.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    axis.text(
        88, -0.62,
        "Upper end, set by the smallest clear gap between two footprints:\n"
        f"  the glasses stand at least {MIN_APART:.0f} mm apart, but that is centre\n"
        f"  to centre. Clustering sees edge to edge, which is {MIN_APART:.0f} mm less the\n"
        f"  two radii. The worst case is two glasses of this kind's widest,\n"
        f"  {KIND_WIDEST:.0f} mm: {MIN_APART:.0f} - {KIND_WIDEST / 2:.0f} - {KIND_WIDEST / 2:.0f} "
        f"= {worst_gap:.0f} mm. Above that the gap can be crossed.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )

    axis.annotate(
        "",
        xy=(MIN_APART, 1.20),
        xytext=(0, 1.20),
        arrowprops={"arrowstyle": "<->", "color": MUTED, "lw": 1.0},
    )
    axis.text(75, 1.25, "150 mm: the closest two objects ever stand, measured centre to centre",
              ha="center", va="bottom", fontsize=NOTE_SIZE, color=MUTED)

    figure.suptitle("One parameter, and a wide window to put it in", fontsize=TITLE_SIZE, color=INK,
                    y=1.0)
    figure.tight_layout()
    save(figure, "02-grouping-distance.png")


# --------------------------------------------------------------------------- #
# 6. the circle fit as the safety net
# --------------------------------------------------------------------------- #

def figure_circle_fit() -> None:
    figure, (left, middle, right) = new(13.6, 5.4, columns=3)

    blob_a = (-88.0, 0.0)
    blob_b = (89.0, 0.0)
    # the one circle a fit would put round both blobs together
    whole = (blob_b[0] + FOOTPRINT_B / 2.0) - (blob_a[0] - FOOTPRINT_A / 2.0)
    for axis in (left, middle):
        bare(axis)
        axis.set_xlim(-190, 190)
        axis.set_ylim(-260, 150)
        axis.set_aspect("equal")
        for centre, width in ((blob_a, FOOTPRINT_A), (blob_b, FOOTPRINT_B)):
            x, y = disc_dots(centre, width, 150)
            axis.scatter(x, y, s=2.0, color=MUTED, zorder=2, linewidths=0)

    panel_title(left, f"One circle: {whole:.0f} mm across", colour=WARN)
    left.add_patch(Circle((0.5, 0), whole / 2.0, facecolor=WARN, alpha=0.10, edgecolor=WARN, lw=2.0))
    span(left, (-whole / 2.0, -136), (whole / 2.0, -136), f"{whole:.0f} mm", colour=WARN,
         above=False, pad=4)
    note(left, 0, -178, f"Fitted to the whole group, the one circle is\n{whole:.0f} mm across. Too wide "
         "to be one glass\nof this kind, so it is rejected.", colour=INK, ha="center", va="top")

    panel_title(middle, f"Two circles: {FOOTPRINT_A:.0f} and {FOOTPRINT_B:.0f} mm", colour=GOOD)
    for centre, width in ((blob_a, FOOTPRINT_A), (blob_b, FOOTPRINT_B)):
        middle.add_patch(
            Circle(centre, width / 2.0, facecolor=GOOD, alpha=0.12, edgecolor=GOOD, lw=2.0)
        )
        middle.scatter([centre[0]], [centre[1]], s=24, color=GOOD, marker="+", zorder=6)
    note(middle, blob_a[0], -46, f"{FOOTPRINT_A:.0f} mm", colour=GOOD, ha="center", va="top",
         size=LABEL_SIZE)
    note(middle, blob_b[0], -46, f"{FOOTPRINT_B:.0f} mm", colour=GOOD, ha="center", va="top",
         size=LABEL_SIZE)
    note(middle, 0, -178, "Two circles are tried instead. Both are inside\nthe range, and together they"
         " explain every\ndot, so the group was two glasses.", colour=INK, ha="center", va="top")

    # the ruler the decision is made against
    bare(right)
    right.set_xlim(-22, 300)
    right.set_ylim(-2.9, 2.0)
    panel_title(right, "What this kind is allowed to be")
    right.add_patch(Rectangle((KIND_NARROWEST, 0), KIND_WIDEST - KIND_NARROWEST, 0.34,
                              facecolor=GOOD, alpha=0.45, edgecolor=GOOD, lw=1.0))
    right.add_patch(Rectangle((0, 0), 280, 0.34, facecolor="none", edgecolor=INK, lw=1.0))
    for tick in range(0, 281, 40):
        right.plot([tick, tick], [-0.07, 0], color=INK, lw=0.9)
        right.text(tick, -0.15, str(tick), ha="center", va="top", fontsize=NOTE_SIZE, color=INK)
    right.text(140, -0.45, "footprint diameter, mm", ha="center", va="top", fontsize=LABEL_SIZE,
               color=INK)
    right.text(KIND_NARROWEST - 6, 0.40, f"{KIND_NARROWEST:.0f} to {KIND_WIDEST:.0f} mm:\nthis kind",
               ha="right", va="bottom", fontsize=NOTE_SIZE, color=GOOD)
    for value in (FOOTPRINT_B, FOOTPRINT_A):
        right.plot([value, value], [0, 0.34], color=GOOD, lw=1.4)
    right.plot([whole, whole], [0, 0.34], color=WARN, lw=1.4)
    right.annotate(
        f"{FOOTPRINT_A:.0f} mm and {FOOTPRINT_B:.0f} mm:\nboth inside",
        xy=(FOOTPRINT_A, 0.34),
        xytext=(112, 0.98),
        ha="right",
        va="top",
        fontsize=NOTE_SIZE,
        color=GOOD,
        arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 1.0},
    )
    right.annotate(
        f"{whole:.0f} mm: nothing\nof this kind",
        xy=(whole, 0.34),
        xytext=(whole - 8, 1.34),
        ha="right",
        va="top",
        fontsize=NOTE_SIZE,
        color=WARN,
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )
    right.text(
        -20, -0.80,
        "The rule, in full:\n"
        "  one circle in range: one object.\n"
        "  out of range, but two circles in range: two objects.\n"
        "  still out of range: reported doubtful, never guessed at.\n\n"
        "This check exists only because every object here is one\n"
        "known kind, so the range is a number the project holds.\n"
        "Problem 4, with four kinds on the table, takes it back.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )

    figure.suptitle(
        "The safety net: a footprint the kind cannot have is not one object, and that is arithmetic, "
        "not judgement.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    save(figure, "02-circle-fit-decides.png")


# --------------------------------------------------------------------------- #
# 7. two stations have to agree
# --------------------------------------------------------------------------- #

# Five glasses of one kind: two near the tall end of its range, three near the
# short end. The mixture is the point. A picture drawn with five glasses of a
# similar size shows a table this cell never produces, and it hides the effect
# the whole solution exists to deal with, which is that a tall glass reaches
# much further across the table in a picture than a short one does.
OBJECTS = (
    (350.0, -110.0),
    (560.0, -120.0),
    (460.0, -250.0),
    (541.0, -386.0),
    (330.0, -340.0),
)
SIZES = (SHORT_A, TALL_A, SHORT_B, TALL_B, SHORT_A)

# How far a glass throws its own shadow depends on its height: a glass H mm tall,
# seen from the survey height, hides a patch reaching 450 / (450 - H) times its
# own distance from the point straight below the camera. A tall glass therefore
# hides a great deal more table than a short one standing the same distance out.
def lift(height):
    return 450.0 / (450.0 - height)


LIFT = lift(OBJECT_HEIGHT)


def _shadow(axis, camera, centre, radius, clip=None, reach=None):
    """The patch of table an upright object hides from a camera straight above `camera`.

    ``reach`` is how far out the hidden patch runs, as a multiple of the object's
    own distance from the point below the camera. It comes from the object's
    height, so a tall glass hides far more table than a short one.
    """
    reach = LIFT if reach is None else reach
    camera = np.array(camera, dtype=float)
    centre = np.array(centre, dtype=float)
    away = centre - camera
    far_centre = camera + away * reach
    far_radius = radius * reach
    unit = away / np.hypot(*away)
    normal = np.array([-unit[1], unit[0]])
    corners = [
        centre + normal * radius,
        far_centre + normal * far_radius,
        far_centre - normal * far_radius,
        centre - normal * radius,
    ]
    wedge = Polygon(corners, closed=True, facecolor=INK, alpha=0.10, edgecolor="none", zorder=1)
    cap = Circle(far_centre, far_radius, facecolor=INK, alpha=0.10, edgecolor="none", zorder=1)
    for patch in (wedge, cap):
        axis.add_patch(patch)
        if clip is not None:
            patch.set_clip_path(clip)


def _half_footprint(axis, centre, camera, diameter, dots=110):
    """Only the dots on the side of the footprint the camera can still see."""
    x, y = disc_dots(centre, diameter, dots * 3)
    away = np.array(centre, dtype=float) - np.array(camera, dtype=float)
    unit = away / np.hypot(*away)
    along = (x - centre[0]) * unit[0] + (y - centre[1]) * unit[1]
    keep = along < 0.05 * diameter
    axis.scatter(x[keep][:dots], y[keep][:dots], s=2.0, color=WARN, zorder=3, linewidths=0)
    axis.add_patch(
        Circle(centre, diameter / 2.0, facecolor="none", edgecolor=WARN, lw=1.2, ls=(0, (3, 2)),
               zorder=4)
    )


def figure_two_stations() -> None:
    figure, (left, right) = new(12.6, 5.8, columns=2)

    stations = (
        (left, (380.0, -190.0), "Station A", WARN, OBJECTS[3],
         "From A, this one is 254 mm off to the side. Its top is\n"
         "thrown so far outwards that it leaves the picture, and\n"
         "only the near half of its footprint comes back. A circle\n"
         "fitted to half a disc sits on the half you have."),
        (right, (540.0, -310.0), "Station B, 200 mm away", GOOD, OBJECTS[0],
         "From B the same glass is much nearer to straight down,\n"
         "so the whole footprint comes back and the fit is\n"
         "clean. Now it is the top left one that is seen\n"
         "edge-on."),
    )

    for axis, camera, title, colour, awkward, body in stations:
        panel_title(axis, title, colour=colour)
        plan_axis(axis, pad=26.0)
        axis.set_ylim(-580, -54)
        x0, x1, y0, y1 = ZONE
        clip = Rectangle((x0, y0), x1 - x0, y1 - y0, transform=axis.transData, facecolor="none",
                         edgecolor="none")
        axis.add_patch(clip)
        for centre, size in zip(OBJECTS, SIZES, strict=True):
            _shadow(axis, camera, centre, size[1] / 2.0, clip=clip, reach=lift(size[0]))
        axis.add_patch(
            Circle(camera, 150.0, facecolor="none", edgecolor=colour, lw=1.0, ls=(0, (4, 3)),
                   zorder=2)
        )
        axis.scatter([camera[0]], [camera[1]], s=46, color=colour, marker="x", zorder=7)
        note(axis, camera[0] + 10, camera[1] + 6, "camera, straight\nabove here", colour=colour,
             va="bottom")
        for centre, size in zip(OBJECTS, SIZES, strict=True):
            if centre == awkward:
                _half_footprint(axis, centre, camera, size[1])
            else:
                footprint(axis, centre, size[1], dots=110)
        axis.annotate(
            "",
            xy=(awkward[0], awkward[1] - 44),
            xytext=(awkward[0] - 40, awkward[1] - 96),
            arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.1},
        )
        note(axis, 300, -462, body, colour=INK, va="top")

    figure.suptitle(
        "Every object is seen well from somewhere and badly from somewhere else, so the stations "
        "are asked to agree.",
        fontsize=TITLE_SIZE, color=INK, y=1.0,
    )
    figure.text(
        0.5, -0.02,
        "The grey patches are the table each object hides; the dashed circle is 150 mm from straight "
        "below the camera.\nThe rule: a group found in the same place from more than one station is a "
        "real object, and its width is taken from the station\nthat saw it nearest to straight down. A "
        "group found from one station only is reported as doubtful, not as an object.",
        ha="center", va="top", fontsize=LABEL_SIZE, color=INK,
    )
    figure.tight_layout()
    save(figure, "02-two-stations-agree.png")


# --------------------------------------------------------------------------- #
# 8. the limit: objects that touch
# --------------------------------------------------------------------------- #

def figure_the_limit() -> None:
    figure, axes = new(13.8, 4.6, columns=3)
    radii = FOOTPRINT_A / 2.0 + FOOTPRINT_B / 2.0
    settled, squeezed, touching = MIN_APART + 27.0, radii + 16.0, radii
    cases = (
        (settled, f"centres {settled:.0f} mm apart",
         f"{settled - radii:.0f} mm of clear table between\nthe two footprints. Two groups\n"
         "at a 25 mm grouping distance.\nDistance decides it, and nothing\nelse has to.",
         GOOD, "settled"),
        (squeezed, f"centres {squeezed:.0f} mm apart",
         f"{squeezed - radii:.0f} mm of clear table, which is\nless than 25 mm, so it comes back"
         f"\nas one group. The footprint is\n{squeezed + radii:.0f} mm, out of range, so two\n"
         f"circles are tried: {FOOTPRINT_A:.0f} and {FOOTPRINT_B:.0f} mm.\nRight answer — but "
         "from shape,\nnot from distance.", GLASS, "recovered by the circle fit"),
        (touching, "touching",
         "No gap at all, at any grouping\ndistance. The fit can suspect two\nfrom the width, but"
         " there is\nnothing left to measure, and with\nthree in a row it cannot say how\nmany."
         " Moving one of them is the\nonly way out, and that is\nproblem 3's job.", WARN,
         "not separable from here"),
    )
    for axis, (spacing, heading, body, colour, verdict) in zip(axes, cases, strict=True):
        bare(axis)
        axis.set_xlim(-135, 135)
        axis.set_ylim(-245, 140)
        axis.set_aspect("equal")
        panel_title(axis, heading, colour=colour)
        left_centre = (-spacing / 2.0, 0.0)
        right_centre = (spacing / 2.0, 0.0)
        footprint(axis, left_centre, FOOTPRINT_A, colour=colour, dots=130)
        footprint(axis, right_centre, FOOTPRINT_B, colour=colour, dots=130)
        gap = spacing - FOOTPRINT_A / 2.0 - FOOTPRINT_B / 2.0
        if gap > 4.0:
            if gap > 30.0:
                axis.annotate(
                    "",
                    xy=(spacing / 2.0 - FOOTPRINT_B / 2.0, 0),
                    xytext=(-spacing / 2.0 + FOOTPRINT_A / 2.0, 0),
                    arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.3},
                    zorder=7,
                )
            note(axis, 0, 52, f"{gap:.0f} mm of clear table", colour=INK, ha="center", va="bottom",
                 size=LABEL_SIZE)
        else:
            note(axis, 0, 52, "0 mm: no gap", colour=WARN, ha="center", va="bottom", size=LABEL_SIZE,
                 weight="bold")
        axis.add_patch(
            Rectangle((-130, 90), 260, 36, facecolor=colour, alpha=0.16, edgecolor="none")
        )
        axis.text(0, 108, verdict, ha="center", va="center", fontsize=LABEL_SIZE, color=INK)
        axis.text(-130, -58, body, ha="left", va="top", fontsize=NOTE_SIZE, color=INK)

    arrow = FancyArrowPatch(
        (0.10, 0.025), (0.92, 0.025), transform=figure.transFigure, arrowstyle="->",
        color=MUTED, lw=1.2, mutation_scale=14,
    )
    figure.patches.append(arrow)
    figure.text(0.51, 0.055, "objects getting closer together", ha="center", va="bottom",
                fontsize=NOTE_SIZE, color=MUTED)

    figure.suptitle(
        "Where it stops: distance separates objects only where there is distance left to measure.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout(rect=(0, 0.10, 1, 1))
    save(figure, "02-touching-is-the-limit.png")


# --------------------------------------------------------------------------- #
# 9. a glass that is completely hidden, seen the two ways the arm looks
# --------------------------------------------------------------------------- #

def outline_profile(outline):
    """One of the project's own glass outlines, as heights and radii in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def splay_from_outline(nadir, centre, outline, slices=80):
    """The stack of circles a real glass outline draws in an overhead picture.

    Same arithmetic as splay_circles — a slice at height z is scaled about the
    point below the camera by H / (H - z) — and the same list of (centre, radius)
    pairs, so splay_covers, splay_patch and splay_width all take it. The
    difference is that every slice comes from one of the project's own outlines
    rather than from a straight taper drawn here.
    """
    z, radii = outline_profile(outline)
    picks = np.linspace(0, len(z) - 1, slices).astype(int)
    offset = np.asarray(centre, dtype=float) - np.asarray(nadir, dtype=float)
    factors = SURVEY_HEIGHT / (SURVEY_HEIGHT - z[picks])
    return [(offset * k, r * k) for k, r in zip(factors, radii[picks], strict=True)]


def silhouette_overlap(first, second, step=2.0):
    """How much table two splayed silhouettes share, in square millimetres.

    Zero means the two glasses appear in the picture as two separate patches.
    """
    stacks = (first, second)
    lows = [min(c[i] - r for c, r in stack) for stack in stacks for i in (0, 1)]
    highs = [max(c[i] + r for c, r in stack) for stack in stacks for i in (0, 1)]
    x = np.arange(min(lows[0], lows[2]), max(highs[0], highs[2]) + step, step)
    y = np.arange(min(lows[1], lows[3]), max(highs[1], highs[3]) + step, step)
    grid_x, grid_y = np.meshgrid(x, y)
    inside = []
    for stack in stacks:
        covered = np.zeros(grid_x.shape, dtype=bool)
        for c, r in stack:
            covered |= (grid_x - c[0]) ** 2 + (grid_y - c[1]) ** 2 <= r * r
        inside.append(covered)
    return float((inside[0] & inside[1]).sum()) * step * step


def level_picture(glasses, width=420, height=300, horizon=96.0):
    """What the camera sees from the level view: 120 mm up, looking level.

    A horizontal circle seen edge-on is a line, so a glass images as the band
    between the left and right walls of its own profile. Every row of the band
    comes from one slice of one of the project's own outlines.
    """
    mask = np.zeros((height, width), np.uint8)
    middle = width / 2.0
    for across, away, outline in glasses:
        z, radii = outline_profile(outline)
        for zi, ri in zip(z, radii, strict=True):
            row = int(round(horizon - FX * (zi - VIEW_HEIGHT) / away))
            left = int(round(middle + FX * (across - ri) / away))
            right = int(round(middle + FX * (across + ri) / away))
            if 0 <= row < height:
                cv2.line(mask, (max(0, left), row), (min(width - 1, right), row), 255, 1)
    filled = mask.copy()
    for column in range(width):
        lit = np.where(filled[:, column] > 0)[0]
        if len(lit):
            filled[lit.min():lit.max() + 1, column] = 255
    return filled


def hidden_table(camera, centre, outline, grid_x, grid_y, steps=200):
    """Which cells of table no ray from `camera` reached, because the glass was in the way.

    `camera` is a position and a height. A cell is hidden when the straight line
    from the lens to that cell passes inside the glass, which is a solid of
    revolution, so the test at one point on the line is a distance from the
    glass's axis compared with the glass's own radius at that height.
    """
    z, radii = outline_profile(outline)
    lens = np.asarray(camera, dtype=float)
    axis_x, axis_y = centre
    blocked = np.zeros(grid_x.shape, dtype=bool)
    for fraction in np.linspace(0.02, 1.0, steps):
        along_x = lens[0] + (grid_x - lens[0]) * fraction
        along_y = lens[1] + (grid_y - lens[1]) * fraction
        height = lens[2] * (1.0 - fraction)
        if height > z[-1]:
            continue
        radius = float(np.interp(height, z, radii))
        blocked |= (along_x - axis_x) ** 2 + (along_y - axis_y) ** 2 <= radius * radius
    return blocked


def paint_mask(axis, region, colour, alpha=1.0, extent=None):
    """Draw a boolean mask as a flat wash of one colour."""
    rgba = np.zeros((*region.shape, 4), dtype=float)
    rgba[region] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest", extent=extent,
                origin="upper" if extent is None else "lower", zorder=2)


def silhouette_edge(axis, stack, colour, step=2.0, lw=1.3, ls="dashed", zorder=6):
    """The boundary of a splayed silhouette, drawn as a line rather than a wash."""
    low_x = min(c[0] - r for c, r in stack) - 4 * step
    high_x = max(c[0] + r for c, r in stack) + 4 * step
    low_y = min(c[1] - r for c, r in stack) - 4 * step
    high_y = max(c[1] + r for c, r in stack) + 4 * step
    grid_x, grid_y = np.meshgrid(np.arange(low_x, high_x, step), np.arange(low_y, high_y, step))
    covered = np.zeros(grid_x.shape, dtype=float)
    for c, r in stack:
        covered = np.maximum(covered, ((grid_x - c[0]) ** 2 + (grid_y - c[1]) ** 2 <= r * r) * 1.0)
    axis.contour(grid_x, grid_y, covered, [0.5], colors=[colour], linewidths=lw,
                 linestyles=ls, zorder=zorder)


def figure_hidden_from_above() -> None:
    """The same two glasses, the same distance apart, hiding and not hiding.

    Splay scales a slice outwards from the point below the camera, so it acts
    along a radius and not across one. That is what makes complete hiding a
    question about which direction the pair lies in as well as about height.
    """
    nadir = np.array([0.0, 0.0])
    ring = 275.0
    swing = np.arcsin(MIN_APART / 2.0 / ring)
    cases = (
        ("Along one radius: the short glass is gone",
         np.array([200.0, 0.0]), np.array([200.0 + MIN_APART, 0.0]),
         (150.0, -170.0), (185.0, -46.0), (430.0, -200.0), (352.0, -40.0)),
        ("Across it: the same two glasses, the same distance apart",
         np.array([ring * np.cos(-swing), ring * np.sin(-swing)]),
         np.array([ring * np.cos(swing), ring * np.sin(swing)]),
         (110.0, -250.0), (245.0, -100.0), (264.0, 232.0), (264.0, 120.0)),
    )

    figure, axes = new(13.4, 5.6, columns=2)
    measured = []
    for axis, (title, tall_at, short_at, tall_text, tall_head, short_text, short_head) in zip(
            axes, cases, strict=True):
        tall = splay_from_outline(nadir, tall_at, TALL_GLASS)
        short = splay_from_outline(nadir, short_at, SHORT_GLASS)
        covered = splay_covers(tall, short)
        shared = silhouette_overlap(tall, short)
        measured.append((covered, shared))

        panel_title(axis, title, colour=WARN if covered else GOOD)
        bare(axis)
        axis.set_aspect("equal")
        axis.set_xlim(-120, 700)
        axis.set_ylim(-310, 320)
        for centre in (tall_at, short_at):
            reach = centre / np.hypot(*centre) * 680.0
            axis.plot([0, reach[0]], [0, reach[1]], color=MUTED, lw=0.8, ls=(0, (7, 6)), zorder=1)
        splay_patch(axis, tall, colour=GLASS, alpha=0.30, zorder=2)
        if covered:
            silhouette_edge(axis, short, WARN)
        else:
            splay_patch(axis, short, colour=GOOD, alpha=0.34, zorder=3)
        for centre, rim, colour in ((tall_at, TALL_RIM, INK),
                                    (short_at, SHORT_RIM, WARN if covered else GOOD)):
            footprint(axis, tuple(centre), rim, colour=colour, dots=80, edge=False)
            axis.add_patch(Circle(tuple(centre), rim / 2.0, facecolor="none", edgecolor=colour,
                                  lw=1.0, zorder=5))
        axis.scatter([0.0], [0.0], s=40, color=INK, marker="x", zorder=9)
        note(axis, 0, -34, "camera, straight\nabove here", colour=INK, ha="center", va="top")

        for text, place, head, colour in (
                (f"the tall glass, {TALL_HEIGHT:.0f} mm tall", tall_text, tall_head, INK),
                (f"the short glass, {SHORT_HEIGHT:.0f} mm tall", short_text, short_head,
                 WARN if covered else GOOD)):
            axis.annotate(text, xy=head, xytext=place, fontsize=NOTE_SIZE, color=colour,
                          ha="center", va="center", zorder=8,
                          arrowprops={"arrowstyle": "->", "color": colour, "lw": 1.0})
        if covered:
            note(axis, 300, 300,
                 "Every point of the short glass's silhouette, dashed, is inside the\n"
                 "tall glass's. It contributes no pixels at all, and the group that\n"
                 f"comes back is the tall glass's own footprint, {TALL_RIM:.0f} mm across — "
                 "an\nordinary width for a kind whose glasses run "
                 f"{KIND_NARROWEST:.0f} to {KIND_WIDEST:.0f} mm.",
                 colour=INK, ha="center", va="top")
        else:
            note(axis, 300, 300,
                 f"The two silhouettes share {shared:.0f} mm² of table, so the picture holds\n"
                 "two patches and both glasses are found. Nothing about the pair\n"
                 "changed except the direction it lies in.",
                 colour=INK, ha="center", va="top")

    figure.suptitle(
        "Hiding from above is radial: it needs the pair to lie along a line out from the camera.",
        fontsize=TITLE_SIZE, color=INK, y=1.00,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.02,
        f"Both panels hold the same two glasses of one kind, {TALL_HEIGHT:.0f} mm and "
        f"{SHORT_HEIGHT:.0f} mm tall, with their centres {MIN_APART:.0f} mm apart, which is the "
        "closest this problem ever puts two glasses. The rings and dots are where they "
        "really stand.\nThe pale "
        f"shapes are what the camera draws from {SURVEY_HEIGHT:.0f} mm up: a slice at height z is "
        "moved out to H / (H - z) times its own distance from the point below the camera, so the tall "
        f"glass's rim goes out by {TALL_LIFT:.2f}\nand the short one's by {SHORT_LIFT:.2f}. Turning "
        "the pair about the camera, without moving either glass relative to the other, is enough to "
        "undo the hiding.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    straight = np.array([200.0, 0.0])
    checks = (
        ("tall, then the short one 150 mm further out", TALL_GLASS, SHORT_GLASS, MIN_APART),
        ("tall, then a second tall one 150 mm further out", TALL_GLASS, TALL_GLASS, MIN_APART),
        ("short, then the tall one 150 mm further out", SHORT_GLASS, TALL_GLASS, MIN_APART),
        ("tall, then the short one 200 mm further out", TALL_GLASS, SHORT_GLASS, 200.0),
    )
    print(f"  above: along a radius covered={measured[0][0]}, shared={measured[0][1]:.0f} mm2; "
          f"across covered={measured[1][0]}, shared={measured[1][1]:.0f} mm2")
    for at, lift, which in ((200.0, TALL_LIFT, "tall"), (350.0, SHORT_LIFT, "short")):
        print(f"    the {which} glass stands {at:.0f} mm out and its rim is drawn "
              f"{at * (lift - 1.0):.0f} mm further out")
    for label, near, far, gap in checks:
        covers = splay_covers(splay_from_outline(nadir, straight, near),
                              splay_from_outline(nadir, straight + (gap, 0.0), far))
        print(f"    {label}: hidden={covers}")
    save(figure, "02-hidden-from-above.png")


def figure_hidden_from_the_side() -> None:
    """Line-of-sight hiding, and the strip of table it leaves behind.

    From the level view there is no splay to help or hurt. The near glass stands
    in front of the far one, and the table it blocks is a strip that widens the
    further away it goes instead of stopping.
    """
    near_at, far_at = 370.0, 600.0
    apart = far_at - near_at
    lens = (near_at - STANDOFF, -260.0, VIEW_HEIGHT)

    near_only = level_picture([(0.0, STANDOFF, TALL_GLASS)])
    far_only = level_picture([(0.0, STANDOFF + apart, SHORT_GLASS)])
    both = level_picture([(0.0, STANDOFF, TALL_GLASS), (0.0, STANDOFF + apart, SHORT_GLASS)])
    left_out = int(((far_only > 0) & ~(near_only > 0)).sum())
    patches, _ = cv2.connectedComponents((both > 0).astype(np.uint8))
    near_px = int(cv2.boundingRect(near_only)[2])
    far_px = int(cv2.boundingRect(far_only)[2])
    far_rows = np.where((far_only > 0).any(axis=1))[0]

    figure, (picture, plan) = new(13.4, 5.6, columns=2)

    panel_title(picture, "The level picture: one patch, with two glasses in it", colour=WARN)
    bare(picture)
    paint_mask(picture, both > 0, GLASS, 0.40)
    picture.contour((both > 0).astype(float), [0.5], colors=[INK], linewidths=1.3)
    picture.contour((far_only > 0).astype(float), [0.5], colors=[WARN], linewidths=1.2,
                    linestyles="dashed")
    x, y, w, h = cv2.boundingRect(near_only)
    picture.set_xlim(x - 100, x + w + 280)
    picture.set_ylim(y + h + 52, y - 60)
    note(picture, x + w / 2, y - 18, f"the near glass, {near_px} px across",
         colour=INK, ha="center", va="bottom")
    picture.annotate(
        f"the far glass is in here, {far_px} px across,\n"
        f"and {left_out} of those pixels are its own",
        xy=(x + w / 2 + 16, float(far_rows.mean())), xytext=(x + w + 40, float(far_rows.mean())),
        fontsize=NOTE_SIZE, color=WARN, ha="left", va="center",
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )

    panel_title(plan, "The table that picture could not reach", colour=WARN)
    bare(plan)
    plan.set_aspect("equal")
    plan.set_xlim(-90, 1090)
    plan.set_ylim(-660, -20)
    step = 2.0
    grid_x, grid_y = np.meshgrid(np.arange(-90.0, 1090.0 + step, step),
                                 np.arange(-660.0, -20.0 + step, step))
    blocked = hidden_table(lens, (near_at, -260.0), TALL_GLASS, grid_x, grid_y)
    paint_mask(plan, blocked, WARN, 0.22,
               extent=(grid_x.min(), grid_x.max(), grid_y.min(), grid_y.max()))
    zone_x0, zone_x1, zone_y0, zone_y1 = ZONE
    plan.add_patch(Rectangle((zone_x0, zone_y0), zone_x1 - zone_x0, zone_y1 - zone_y0,
                             facecolor="none", edgecolor=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=4))
    note(plan, zone_x0 + 8, zone_y1 - 10, "the glass zone", colour=MUTED, va="top")
    footprint(plan, (near_at, -260.0), TALL_RIM, colour=GLASS, dots=110)
    footprint(plan, (far_at, -260.0), SHORT_RIM, colour=WARN, dots=70)
    plan.scatter([lens[0]], [lens[1]], s=46, color=INK, marker="x", zorder=9)
    note(plan, lens[0], lens[1] - 24, f"camera,\n{VIEW_HEIGHT:.0f} mm up,\nlooking level",
         colour=INK, ha="center", va="top")
    widths = []
    z, radii = outline_profile(TALL_GLASS)
    for beyond in (zone_x1 - near_at, 1020.0 - near_at):
        reach = VIEW_HEIGHT * (1.0 - STANDOFF / (STANDOFF + beyond))
        width = 2.0 * float(np.interp(reach, z, radii)) / (1.0 - reach / VIEW_HEIGHT)
        widths.append((beyond, width))
        at = near_at + beyond
        plan.plot([at, at], [-260.0 - width / 2, -260.0 + width / 2], color=INK, lw=1.3, zorder=6)
        note(plan, at - 10, -260.0 + width / 2 + 12, f"{width:.0f} mm",
             colour=INK, ha="right", va="bottom")
    note(plan, -70, -490,
         "The blue dots are the near glass, the orange dots the far one, both where they really stand, "
         "and the two marks are how wide\nthe blocked strip is there. The strip never closes. A ray "
         "that clears the rim of the near glass just under the camera's own\nheight lands a long way "
         "beyond it, so the further out the strip runs the wider it gets. Standing further back on the "
         "same line\nchanges none of it.",
         colour=INK, va="top")

    figure.suptitle(
        "From the side there is no splay to help: the near glass simply stands in front of the far one.",
        fontsize=TITLE_SIZE, color=INK, y=1.00,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.02,
        f"The near glass is {TALL_HEIGHT:.0f} mm tall and the far one {SHORT_HEIGHT:.0f} mm, standing "
        f"{apart:.0f} mm behind it and in line with the camera. Not one pixel of the far glass is its "
        "own, and being further back does not help it: the same\npair is covered just as completely "
        f"at {MIN_APART:.0f} mm apart as at 600 mm apart. What the arm can report is the strip of "
        f"table the near glass blocked, and at the far edge of the zone that strip is still "
        f"{widths[0][1]:.0f} mm wide,\nwhich is more than the {KIND_NARROWEST:.0f} mm footprint of "
        "the smallest glass this kind allows. So the strip stays open, and only moving the camera "
        "off this line closes it.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    other_way = level_picture([(0.0, STANDOFF, SHORT_GLASS)])
    tall_behind = level_picture([(0.0, STANDOFF + apart, TALL_GLASS)])
    still_out = int(((tall_behind > 0) & ~(other_way > 0)).sum())
    print(f"  side: far glass {far_px} px across, {left_out} pixels of its own, "
          f"{patches - 1} patch; strip widths {[(int(b), round(v, 1)) for b, v in widths]}")
    print(f"    the other way round, a short glass in front of a tall one: "
          f"{100 * (1 - still_out / (tall_behind > 0).sum()):.0f}% of the far glass covered, "
          f"near {int(cv2.boundingRect(other_way)[2])} px across against its "
          f"{int(cv2.boundingRect(tall_behind)[2])} px")
    save(figure, "02-hidden-from-the-side.png")


def main() -> None:
    figure_pixel_to_point()
    figure_picture_versus_table()
    figure_four_steps()
    figure_why_flatten()
    figure_grouping_distance()
    figure_circle_fit()
    figure_two_stations()
    figure_the_limit()
    figure_hidden_from_above()
    figure_hidden_from_the_side()


if __name__ == "__main__":
    main()
