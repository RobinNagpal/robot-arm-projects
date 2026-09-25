"""Diagrams for solution 2 — cluster on the table.

Eight pictures, each carrying one point of the argument: how a pixel becomes a
point in the room, why the room beats the picture, the four steps, why the
points are flattened onto the table first, how the one grouping distance is
chosen, how the circle fit vetoes an impossible footprint, why two stations are
asked to agree, and where the whole idea stops working.

Run from the project root:

    pixi run python docs/problem-2/make_02_images.py
"""

from __future__ import annotations

import numpy as np
from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
)
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

RNG = np.random.default_rng(20250925)

# The zone the objects stand in, in millimetres from the arm's base.
ZONE = (320.0, 640.0, -440.0, -80.0)

SURVEY_HEIGHT = 450.0   # mm above the table top
OBJECT_HEIGHT = 205.0   # mm, one drawn object
FOOTPRINT_A = 76.0      # mm across
FOOTPRINT_B = 73.0      # mm across


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
    figure, (left, right) = new(12.4, 5.2, columns=2)

    bare(left)
    left.set_xlim(-24, 344)
    left.set_ylim(-104, 268)
    left.set_aspect("equal")
    panel_title(left, "In the picture: one blob", colour=WARN)
    left.add_patch(Rectangle((0, 0), 320, 240, facecolor=MUTED, alpha=0.06, edgecolor=INK, lw=1.2))

    # two silhouettes that touch: the far object's top is thrown outwards
    near = [(96, 20), (104, 150), (168, 150), (160, 20)]
    far = [(150, 52), (162, 196), (236, 196), (222, 52)]
    for poly in (near, far):
        left.add_patch(Polygon(poly, closed=True, facecolor=GLASS, alpha=0.30, edgecolor="none"))
    union = [(96, 20), (104, 150), (162, 150), (162, 196), (236, 196), (222, 52), (160, 52), (160, 20)]
    left.add_patch(
        Polygon(union, closed=True, facecolor="none", edgecolor=WARN, lw=2.0, zorder=5)
    )
    span(left, (96, 212), (236, 212), "163 pixels across", colour=WARN, pad=5)
    note(
        left, 0, -14,
        "The two silhouettes touch, so a flood fill returns one patch.\n"
        "163 pixels at about 1.6 mm each is roughly 260 mm of table, and\n"
        "nothing of this kind is wider than 105 mm. So the picture can say\n"
        "that something is wrong. It cannot say which pixels were near and\n"
        "which were far, because the projection threw that away.",
        colour=INK,
    )

    panel_title(right, "On the table: two footprints, 102 mm of clear space between them", colour=GOOD)
    plan_axis(right)
    centre_a = (420.0, -310.0)
    centre_b = (550.0, -190.0)
    footprint(right, centre_a, FOOTPRINT_A)
    footprint(right, centre_b, FOOTPRINT_B)

    nadir = (342.0, -382.0)
    right.scatter([nadir[0]], [nadir[1]], s=30, color=WARN, marker="x", zorder=6)
    note(right, nadir[0] + 10, nadir[1] + 2, "camera, straight above here", colour=WARN, va="bottom")
    right.plot(
        [nadir[0], centre_b[0] + (centre_b[0] - nadir[0]) * 0.14],
        [nadir[1], centre_b[1] + (centre_b[1] - nadir[1]) * 0.14],
        color=WARN, lw=0.9, ls=(0, (4, 3)), zorder=2,
    )
    note(right, 336, -128, "both on one line from the camera:\nthat is why they merged above",
         colour=WARN)

    # the clear gap, along the line joining the two centres
    direction = np.array(centre_b) - np.array(centre_a)
    unit = direction / np.hypot(*direction)
    start = np.array(centre_a) + unit * (FOOTPRINT_A / 2.0)
    end = np.array(centre_b) - unit * (FOOTPRINT_B / 2.0)
    right.annotate(
        "",
        xy=tuple(end),
        xytext=tuple(start),
        arrowprops={"arrowstyle": "<->", "color": GOOD, "lw": 1.6},
        zorder=6,
    )
    note(right, 448, -238, "102 mm", colour=GOOD, size=LABEL_SIZE, weight="bold",
         ha="right", va="center")
    note(right, 336, -96, "centres 177 mm apart", colour=INK)
    note(right, 336, -424, "the zone the objects stand in, 320 x 360 mm", colour=MUTED, va="bottom")

    figure.suptitle(
        "Two objects a hand's width apart can land on top of each other in a photograph.\n"
        "They are still 177 mm apart in the room.",
        fontsize=TITLE_SIZE, color=INK, y=1.06,
    )
    figure.tight_layout()
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
    note(four, centre_a[0], centre_a[1] + 48, "76 mm\n(0.420, -0.310)", colour=GOOD, ha="center",
         va="bottom")
    note(four, centre_b[0], centre_b[1] + 48, "73 mm\n(0.550, -0.190)", colour=GOOD, ha="center",
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

    bare(left)
    left.set_xlim(-262, 430)
    left.set_ylim(-165, 300)
    left.set_aspect("equal")
    panel_title(left, "In full 3-D: no single distance works", colour=WARN)
    left.plot([-240, 420], [0, 0], color=INK, lw=1.8)

    centres = (20.0, 197.0)
    widths = (FOOTPRINT_A, FOOTPRINT_B)
    for centre_x, width in zip(centres, widths, strict=True):
        glass_side(left, centre_x, 0.0, OBJECT_HEIGHT, width, alpha=0.12)
        # a dense cap of points on the top, a thin skirt near the base, a hole between
        cap_x = centre_x + (RNG.random(70) - 0.5) * width
        left.scatter(cap_x, OBJECT_HEIGHT - RNG.random(70) * 8, s=2.4, color=GLASS, zorder=5,
                     linewidths=0)
        skirt_x = centre_x + np.sign(RNG.random(24) - 0.5) * (width / 2.0) * 0.82
        left.scatter(skirt_x, 8 + RNG.random(24) * 16, s=2.4, color=GLASS, zorder=5, linewidths=0)

    left.add_patch(
        Rectangle((-245, 30), 670, 160, facecolor=WARN, alpha=0.07, edgecolor="none", zorder=0)
    )
    note(left, -244, 160, "no points up here: from almost\noverhead the wall is edge-on to\nthe"
         " camera, so nothing lands on it", colour=WARN)

    span(left, (252, 26), (252, OBJECT_HEIGHT - 6), "", colour=WARN)
    left.text(262, 112, "205 mm\nsame object,\ntop to base", ha="left", va="center",
              fontsize=NOTE_SIZE, color=WARN)
    top_gap_start = (centres[0] + widths[0] / 2.0, OBJECT_HEIGHT)
    top_gap_end = (centres[1] - widths[1] / 2.0, OBJECT_HEIGHT)
    left.annotate(
        "",
        xy=top_gap_end,
        xytext=top_gap_start,
        arrowprops={"arrowstyle": "<->", "color": GOOD, "lw": 1.4},
        zorder=6,
    )
    note(left, 108, OBJECT_HEIGHT + 10, "102 mm: different objects", colour=GOOD, ha="center",
         va="bottom")
    note(
        left, -244, -22,
        "Under 102 mm and one object breaks into a cap and a skirt.\n"
        "Over 205 mm and the two objects become one group.\n"
        "205 mm is more than 102 mm, so there is no number that does both.",
        colour=INK,
    )

    panel_title(right, "Flattened onto the table: one distance does both jobs", colour=GOOD)
    plan_axis(right)
    centre_a = (420.0, -310.0)
    centre_b = (550.0, -190.0)
    footprint(right, centre_a, FOOTPRINT_A)
    footprint(right, centre_b, FOOTPRINT_B)
    direction = np.array(centre_b) - np.array(centre_a)
    unit = direction / np.hypot(*direction)
    right.annotate(
        "",
        xy=tuple(np.array(centre_b) - unit * (FOOTPRINT_B / 2.0)),
        xytext=tuple(np.array(centre_a) + unit * (FOOTPRINT_A / 2.0)),
        arrowprops={"arrowstyle": "<->", "color": GOOD, "lw": 1.6},
        zorder=6,
    )
    note(right, 446, -244, "102 mm apart", colour=GOOD, size=LABEL_SIZE, weight="bold",
         ha="right", va="center")
    for centre, width in ((centre_a, FOOTPRINT_A), (centre_b, FOOTPRINT_B)):
        span(right, (centre[0] - width / 2.0, centre[1] - 54), (centre[0] + width / 2.0, centre[1] - 54),
             f"{int(width)} mm wide", colour=INK, above=False, pad=5)
    note(
        right, 336, -430,
        "The 205 mm of height is gone: it was the one dimension that\n"
        "did not help. Anything from about 10 mm to 60 mm now holds one\n"
        "footprint together and keeps two apart. 25 mm is the choice.",
        colour=INK, va="bottom",
    )

    figure.suptitle(
        "A tall thin object is 205 mm tall and 76 mm wide. Height is what makes 3-D clustering "
        "ambiguous.",
        fontsize=TITLE_SIZE, color=INK, y=1.03,
    )
    figure.tight_layout()
    save(figure, "02-why-flatten.png")


# --------------------------------------------------------------------------- #
# 5. the grouping distance window
# --------------------------------------------------------------------------- #

def figure_grouping_distance() -> None:
    figure, axis = new(11.6, 4.2)
    bare(axis)
    axis.set_xlim(-14, 176)
    axis.set_ylim(-1.55, 1.45)

    bar_low, bar_high = 0.0, 0.42
    axis.add_patch(Rectangle((0, bar_low), 10, bar_high, facecolor=WARN, alpha=0.30, edgecolor="none"))
    axis.add_patch(Rectangle((10, bar_low), 50, bar_high, facecolor=GOOD, alpha=0.38, edgecolor="none"))
    axis.add_patch(Rectangle((60, bar_low), 100, bar_high, facecolor=WARN, alpha=0.30,
                             edgecolor="none"))
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
        "  one pixel is about 1.6 mm of table at survey height, and about\n"
        "  0.9 mm on the top of a 205 mm object, which is nearer the camera;\n"
        "  depth noise adds a few mm. Below about 10 mm the chain breaks and\n"
        "  one object is reported as several.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    axis.text(
        88, -0.62,
        "Upper end, set by the smallest clear gap between two footprints:\n"
        "  the objects stand at least 150 mm apart, but that is centre to\n"
        "  centre. Clustering sees edge to edge, which is 150 mm less the two\n"
        "  radii: for this kind's widest, 150 - 45 - 45 = 60 mm. Above that\n"
        "  the gap can be crossed.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )

    axis.annotate(
        "",
        xy=(150, 1.20),
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
    for axis in (left, middle):
        bare(axis)
        axis.set_xlim(-190, 190)
        axis.set_ylim(-260, 150)
        axis.set_aspect("equal")
        for centre, width in ((blob_a, FOOTPRINT_A), (blob_b, FOOTPRINT_B)):
            x, y = disc_dots(centre, width, 150)
            axis.scatter(x, y, s=2.0, color=MUTED, zorder=2, linewidths=0)

    panel_title(left, "One circle: 260 mm across", colour=WARN)
    left.add_patch(Circle((0.5, 0), 130, facecolor=WARN, alpha=0.10, edgecolor=WARN, lw=2.0))
    span(left, (-129.5, -136), (130.5, -136), "260 mm", colour=WARN, above=False, pad=4)
    note(left, 0, -178, "Fitted to the whole group, the one circle is\n260 mm across. Too wide to be one"
         " object\nof this kind, so it is rejected.", colour=INK, ha="center", va="top")

    panel_title(middle, "Two circles: 76 and 73 mm", colour=GOOD)
    for centre, width in ((blob_a, FOOTPRINT_A), (blob_b, FOOTPRINT_B)):
        middle.add_patch(
            Circle(centre, width / 2.0, facecolor=GOOD, alpha=0.12, edgecolor=GOOD, lw=2.0)
        )
        middle.scatter([centre[0]], [centre[1]], s=24, color=GOOD, marker="+", zorder=6)
    note(middle, blob_a[0], -46, "76 mm", colour=GOOD, ha="center", va="top", size=LABEL_SIZE)
    note(middle, blob_b[0], -46, "73 mm", colour=GOOD, ha="center", va="top", size=LABEL_SIZE)
    note(middle, 0, -178, "Two circles are tried instead. Both are inside\nthe range, and together they"
         " explain every\ndot, so the group was two objects.", colour=INK, ha="center", va="top")

    # the ruler the decision is made against
    bare(right)
    right.set_xlim(-22, 300)
    right.set_ylim(-2.9, 2.0)
    panel_title(right, "What this kind is allowed to be")
    right.add_patch(Rectangle((60, 0), 30, 0.34, facecolor=GOOD, alpha=0.45, edgecolor=GOOD, lw=1.0))
    right.add_patch(Rectangle((0, 0), 280, 0.34, facecolor="none", edgecolor=INK, lw=1.0))
    for tick in range(0, 281, 40):
        right.plot([tick, tick], [-0.07, 0], color=INK, lw=0.9)
        right.text(tick, -0.15, str(tick), ha="center", va="top", fontsize=NOTE_SIZE, color=INK)
    right.text(140, -0.45, "footprint diameter, mm", ha="center", va="top", fontsize=LABEL_SIZE,
               color=INK)
    right.text(56, 0.40, "60 to 90 mm:\nthis kind", ha="right", va="bottom", fontsize=NOTE_SIZE,
               color=GOOD)
    for value in (73.0, 76.0):
        right.plot([value, value], [0, 0.34], color=GOOD, lw=1.4)
    right.plot([260, 260], [0, 0.34], color=WARN, lw=1.4)
    right.annotate(
        "76 mm and 73 mm:\nboth inside",
        xy=(76, 0.34),
        xytext=(112, 0.98),
        ha="right",
        va="top",
        fontsize=NOTE_SIZE,
        color=GOOD,
        arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 1.0},
    )
    right.annotate(
        "260 mm: nothing\nof this kind",
        xy=(260, 0.34),
        xytext=(252, 1.34),
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

OBJECTS = (
    (350.0, -110.0),
    (560.0, -120.0),
    (460.0, -250.0),
    (541.0, -386.0),
    (330.0, -340.0),
)

# An object 205 mm tall, seen from 450 mm up, hides a patch of table 450 / (450 - 205)
# = 1.84 times its own distance from the point straight below the camera.
LIFT = 450.0 / (450.0 - OBJECT_HEIGHT)


def _shadow(axis, camera, centre, radius, clip=None):
    """The patch of table an upright object hides from a camera straight above `camera`."""
    camera = np.array(camera, dtype=float)
    centre = np.array(centre, dtype=float)
    away = centre - camera
    far_centre = camera + away * LIFT
    far_radius = radius * LIFT
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
         "From B the same object is 76 mm off to the side, near\n"
         "enough to straight down that the whole footprint comes\n"
         "back and the fit is clean. Now it is the top left one\n"
         "that is seen edge-on."),
    )

    for axis, camera, title, colour, awkward, body in stations:
        panel_title(axis, title, colour=colour)
        plan_axis(axis, pad=26.0)
        axis.set_ylim(-580, -54)
        x0, x1, y0, y1 = ZONE
        clip = Rectangle((x0, y0), x1 - x0, y1 - y0, transform=axis.transData, facecolor="none",
                         edgecolor="none")
        axis.add_patch(clip)
        for centre in OBJECTS:
            _shadow(axis, camera, centre, FOOTPRINT_A / 2.0, clip=clip)
        axis.add_patch(
            Circle(camera, 150.0, facecolor="none", edgecolor=colour, lw=1.0, ls=(0, (4, 3)),
                   zorder=2)
        )
        axis.scatter([camera[0]], [camera[1]], s=46, color=colour, marker="x", zorder=7)
        note(axis, camera[0] + 10, camera[1] + 6, "camera, straight\nabove here", colour=colour,
             va="bottom")
        for centre in OBJECTS:
            if centre == awkward:
                _half_footprint(axis, centre, camera, FOOTPRINT_A)
            else:
                footprint(axis, centre, FOOTPRINT_A, dots=110)
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
    cases = (
        (177.0, "centres 177 mm apart",
         "102 mm of clear table between\nthe two footprints. Two groups\nat a 25 mm grouping"
         " distance.\nDistance decides it, and nothing\nelse has to.", GOOD, "settled"),
        (90.0, "centres 90 mm apart",
         "16 mm of clear table, which is\nless than 25 mm, so it comes back\nas one group. The"
         " footprint is\n165 mm, out of range, so two\ncircles are tried: 76 and 73 mm.\nRight"
         " answer — but from shape,\nnot from distance.", GLASS, "recovered by the circle fit"),
        (74.6, "touching",
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


def main() -> None:
    figure_pixel_to_point()
    figure_picture_versus_table()
    figure_four_steps()
    figure_why_flatten()
    figure_grouping_distance()
    figure_circle_fit()
    figure_two_stations()
    figure_the_limit()


if __name__ == "__main__":
    main()
