"""Draw the diagrams for solution 5 — a learned verifier over the clusters.

Seven pictures, each carrying one point:

1. the problem — one number, and the one place a rule has to put a step in it;
2. where the verifier sits in a pipeline that already works without it;
3. what the model is actually shown, drawn on an ambiguous cluster;
4. learning the whole task against learning the one decision;
5. calibration, and the two thresholds that give three answers;
6. the abstain path as a loop, and where abstaining says to look;
7. what happens when the weights file is not there;
8. what the verifier is given when a glass is hidden in an overhead picture;
9. what it is given when a glass is hidden in a level one.

Run from the project root:

    pixi run python images/generators/problem-2/make_05_images.py

The cluster in pictures 3 and 6 is not drawn by hand. It is generated from the
cell's own geometry — two glasses of one kind, a camera in line with both, and
the near one shadowing the far one — and the circles are fitted to it in code,
so the numbers printed in the document are the numbers the fit returns.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from diagram_style import (
    FX,
    GLASS,
    GOOD,
    INK,
    KIND_NARROWEST,
    KIND_WIDEST,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PAPER,
    SURVEY_H,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
    splay_covers,
    splay_patch,
    splay_width,
)
from matplotlib import pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import family  # noqa: E402

# ------------------------------------------------------------------ the cell
#
# Every number here is from the cell description and nowhere else.

PIXEL_MM = 450.0 / 277.1          # one pixel on the table at survey height, mm
PIXEL_AREA = PIXEL_MM**2          # the table area one pixel covers, mm^2
PICTURES_PER_STATION = 2          # two pictures 120 mm apart
KIND_MIN, KIND_MAX = 60.0, 90.0   # this kind's footprint range, mm
KIND_MEAN = 0.5 * (KIND_MIN + KIND_MAX)

# The two glasses that will be drawn: diameters inside the kind's range, standing
# 88 mm apart, which is close enough to merge at a 25 mm grouping distance.
NEAR = (-44.0, 0.0, 36.0)
FAR = (44.0, 0.0, 34.5)
CAMERA = (-520.0, -95.0)          # the station, in the same table millimetres


# ------------------------------------------------------------------- helpers


def _panels(width: float, height: float, ratios: list[float]):
    """A row of panels with uneven widths, on white."""
    figure, axes = plt.subplots(1, len(ratios), figsize=(width, height), gridspec_kw={"width_ratios": ratios})
    figure.patch.set_facecolor(PAPER)
    for axis in np.atleast_1d(axes):
        axis.set_facecolor(PAPER)
    return figure, axes


def _sheet(width: float, height: float):
    """One panel with a 0-100 by 0-100 drawing space and no decoration."""
    figure, axis = plt.subplots(figsize=(width, height))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    axis.set_xlim(0, 120)
    axis.set_ylim(0, 100)
    bare(axis)
    return figure, axis


def _box(axis, x, y, w, h, text, *, face=PAPER, edge=INK, ink=INK, size=LABEL_SIZE, dashed=False, bold=False):
    axis.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.0,rounding_size=1.6",
            linewidth=1.6 if dashed else 1.1,
            facecolor=face,
            edgecolor=edge,
            linestyle=(0, (4, 2)) if dashed else "-",
            zorder=3,
        )
    )
    axis.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=size,
        color=ink,
        zorder=4,
        weight="bold" if bold else "normal",
    )


def _arrow(axis, start, end, *, colour=INK, curve=0.0, width=1.3, style="-|>"):
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=11,
            linewidth=width,
            color=colour,
            connectionstyle=f"arc3,rad={curve}",
            shrinkA=2,
            shrinkB=2,
            zorder=2,
        )
    )


def _note(axis, x, y, text, *, colour=MUTED, size=NOTE_SIZE, ha="left", va="center", style="normal"):
    axis.text(x, y, text, ha=ha, va=va, fontsize=size, color=colour, style=style, zorder=5)


# ------------------------------------------- the cluster, and the circle fits


def _disc(rng, centre_x, centre_y, radius, count):
    """Dots spread evenly over a disc — one glass's footprint, seen from above."""
    angle = rng.uniform(0, 2 * np.pi, count)
    radial = radius * np.sqrt(rng.uniform(0, 1, count))
    return np.column_stack([centre_x + radial * np.cos(angle), centre_y + radial * np.sin(angle)])


def _shadowed(dots, blocker):
    """Drop the dots whose line of sight to the camera passes through the near glass."""
    bx, by, br = blocker
    camera = np.array(CAMERA)
    blocker_centre = np.array([bx, by])
    along = dots - camera
    length = np.linalg.norm(along, axis=1)
    unit = along / length[:, None]
    reach = (blocker_centre - camera) @ unit.T
    closest = camera + unit * reach[:, None]
    miss = np.linalg.norm(closest - blocker_centre, axis=1)
    hidden = (miss < br) & (reach > 0) & (reach < length)
    return dots[~hidden]


def _cluster(seed: int = 7):
    """The one group of dots two glasses make when the camera is in line with both.

    The dot counts are not chosen for looks. One pixel covers PIXEL_AREA of table
    at survey height, and a station takes two pictures, so a footprint of area A
    arrives as 2A / PIXEL_AREA dots.
    """
    rng = np.random.default_rng(seed)
    dots = []
    for centre_x, centre_y, radius in (NEAR, FAR):
        count = int(round(PICTURES_PER_STATION * np.pi * radius**2 / PIXEL_AREA))
        disc = _disc(rng, centre_x, centre_y, radius, count)
        dots.append(disc if (centre_x, centre_y, radius) == NEAR else _shadowed(disc, NEAR))
    both = np.vstack(dots)
    return both + rng.normal(0.0, 1.2, both.shape)      # depth noise, about one pixel


def _outline(dots, bins: int = 72):
    """The boundary of a dot cloud: the farthest dot in each of `bins` directions."""
    centre = dots.mean(axis=0)
    offset = dots - centre
    angle = np.arctan2(offset[:, 1], offset[:, 0])
    radius = np.linalg.norm(offset, axis=1)
    edges = np.linspace(-np.pi, np.pi, bins + 1)
    which = np.clip(np.digitize(angle, edges) - 1, 0, bins - 1)
    picked = []
    for bin_index in range(bins):
        inside = np.flatnonzero(which == bin_index)
        if inside.size:
            picked.append(dots[inside[np.argmax(radius[inside])]])
    return np.array(picked)


def _fit_circle(points):
    """Least-squares circle through a set of points: x^2 + y^2 = a x + b y + c."""
    x, y = points[:, 0], points[:, 1]
    design = np.column_stack([x, y, np.ones_like(x)])
    a, b, c = np.linalg.lstsq(design, x**2 + y**2, rcond=None)[0]
    centre = np.array([a / 2.0, b / 2.0])
    radius = float(np.sqrt(max(c + centre @ centre, 1e-9)))
    residual = np.linalg.norm(points - centre, axis=1) - radius
    return centre, radius, float(np.sqrt(np.mean(residual**2))), float(np.max(np.abs(residual)))


def _split_in_two(dots, rounds: int = 40):
    """Two-means along the cloud's long axis — the cheapest two-object hypothesis."""
    centred = dots - dots.mean(axis=0)
    _, _, directions = np.linalg.svd(centred, full_matrices=False)
    long_axis = directions[0]
    projection = centred @ long_axis
    seeds = np.array(
        [
            dots.mean(axis=0) + long_axis * np.percentile(projection, 10),
            dots.mean(axis=0) + long_axis * np.percentile(projection, 90),
        ]
    )
    label = np.zeros(len(dots), dtype=int)
    for _ in range(rounds):
        distance = np.stack([np.linalg.norm(dots - seed, axis=1) for seed in seeds])
        label = np.argmin(distance, axis=0)
        for side in (0, 1):
            if np.any(label == side):
                seeds[side] = dots[label == side].mean(axis=0)
    return label


def _polygon_area(outline):
    """Shoelace area of an outline, used for the dot-density feature."""
    centre = outline.mean(axis=0)
    offset = outline - centre
    order = np.argsort(np.arctan2(offset[:, 1], offset[:, 0]))
    x, y = outline[order, 0], outline[order, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _dip(dots, centre_a, centre_b, bins: int = 22):
    """How bimodal the spread is along the line joining the two candidate centres."""
    axis_unit = (centre_b - centre_a) / np.linalg.norm(centre_b - centre_a)
    position = (dots - centre_a) @ axis_unit
    counts, edges = np.histogram(position, bins=bins)
    peak_left = int(np.argmax(counts[: bins // 2]))
    peak_right = bins // 2 + int(np.argmax(counts[bins // 2 :]))
    valley = counts[peak_left : peak_right + 1].min()
    shorter = min(counts[peak_left], counts[peak_right])
    return position, counts, edges, float(1.0 - valley / shorter)


def features():
    """Every number the verifier is shown, measured on the generated cluster."""
    dots = _cluster()
    outline = _outline(dots)
    one_centre, one_radius, one_rms, one_worst = _fit_circle(outline)

    label = _split_in_two(dots)
    parts = []
    for side in (0, 1):
        side_dots = dots[label == side]
        parts.append((side_dots, *_fit_circle(_outline(side_dots, bins=48))))
    parts.sort(key=lambda part: part[1][0])
    left_dots, left_centre, left_radius, left_rms, _ = parts[0]
    right_dots, right_centre, right_radius, right_rms, _ = parts[1]

    gap = float(np.linalg.norm(right_centre - left_centre))
    two_rms = float(np.sqrt((left_rms**2 * len(left_dots) + right_rms**2 * len(right_dots)) / len(dots)))
    area = _polygon_area(outline)
    density = len(dots) / area
    predicted = PICTURES_PER_STATION / PIXEL_AREA
    position, counts, edges, dip = _dip(dots, left_centre, right_centre)

    return {
        "dots": dots,
        "outline": outline,
        "one": (one_centre, one_radius, one_rms, one_worst),
        "two": ((left_centre, left_radius), (right_centre, right_radius), two_rms),
        "gap": gap,
        "clearance": (gap - left_radius - right_radius) / (left_radius + right_radius),
        "area": area,
        "density": density,
        "predicted": predicted,
        "dip": dip,
        "profile": (position, counts, edges),
    }


# ------------------------------------------------- 1. the band the rule fails


def ambiguous_band(measured) -> None:
    """The problem: one measured number, and one place a rule has to put a step."""
    figure, axis = plt.subplots(figsize=(11.6, 4.8))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    rng = np.random.default_rng(3)

    single = np.clip(rng.normal(KIND_MEAN, 6.2, 90), 57, 101)
    # A merged pair usually fits far too wide. It only lands near the range when
    # the camera is in line with both and the far one is mostly hidden.
    wide = 108.0 + 88.0 * rng.beta(2.2, 1.7, 66)
    eclipsed = 78.0 + 26.0 * rng.beta(1.6, 1.4, 24)
    pairs = np.concatenate([wide, eclipsed])

    axis.axvspan(KIND_MIN, KIND_MAX, color=GOOD, alpha=0.10, zorder=0)
    axis.axvspan(78, 101, color=MUTED, alpha=0.22, zorder=1)
    axis.axvline(KIND_MAX, color=INK, linewidth=1.4, linestyle=(0, (5, 3)), zorder=4)

    axis.scatter(single, rng.uniform(6.2, 8.8, single.size), s=17, color=GLASS, alpha=0.85, zorder=3)
    axis.scatter(pairs, rng.uniform(1.6, 4.2, pairs.size), s=17, color=WARN, alpha=0.85, zorder=3)

    example = 88.6
    axis.scatter([example], [3.0], s=120, facecolor="none", edgecolor=INK, linewidth=1.4, zorder=6)

    axis.text(KIND_MAX, 11.0, "the rule's step, at 90 mm", ha="center", fontsize=NOTE_SIZE, color=INK)
    _note(axis, 54, 9.6, "really one glass", colour=GLASS, size=LABEL_SIZE)
    _note(axis, 54, 5.2, "really two glasses, grouped as one", colour=WARN, size=LABEL_SIZE)
    _note(axis, KIND_MIN + 1.0, 0.6, f"the kind's range: {KIND_MIN:.0f} to {KIND_MAX:.0f} mm", colour=GOOD)

    axis.annotate(
        "the band where both are possible",
        xy=(95, 9.8),
        xytext=(152, 9.9),
        fontsize=NOTE_SIZE,
        color=INK,
        va="center",
        arrowprops={"arrowstyle": "-|>", "color": INK, "linewidth": 1.0},
    )
    axis.annotate(
        "split: one glass called two\n— it looks wrong at once",
        xy=(96.4, 8.3),
        xytext=(124, 7.4),
        fontsize=NOTE_SIZE,
        color=INK,
        va="center",
        arrowprops={"arrowstyle": "-|>", "color": GLASS, "linewidth": 1.1},
    )
    axis.annotate(
        "merged: two glasses called one\n— the failure that does not announce itself.\n"
        "The worked example is the ringed one, at 89 mm.",
        xy=(89.4, 3.2),
        xytext=(124, 5.2),
        fontsize=NOTE_SIZE,
        color=INK,
        va="center",
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )

    axis.set_xlim(52, 208)
    axis.set_ylim(0, 11.6)
    axis.set_yticks([])
    axis.set_xticks([60, 75, 90, 105, 120, 140, 160, 180, 200])
    axis.set_xlabel("diameter of the one circle fitted to the group's footprint, mm", fontsize=LABEL_SIZE)
    axis.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(MUTED)
    axis.set_title(
        "The geometry settles almost everything. The residue is one narrow band.",
        fontsize=TITLE_SIZE,
        color=INK,
        pad=14,
    )
    _note(
        axis,
        52,
        -2.1,
        "One glass fits near 75 mm and a merged pair usually fits far too wide, so a step at 90 mm is\n"
        "right nearly every time. Only the shaded band holds both kinds of case. The same picture could\n"
        "be drawn for the residual, or the dot density, or any other single number — and the verifier is\n"
        "shown thirteen of them at once.",
        size=NOTE_SIZE,
        va="top",
    )
    save(figure, "05-the-ambiguous-band.png")


# ------------------------------------------------- 2. where the verifier sits


def where_it_sits() -> None:
    """The mechanism: one small box added to a pipeline that already works."""
    figure, axis = _sheet(12.6, 5.8)

    stages = [
        (14, "depth pictures\n320 x 240, two per station"),
        (36, "points above the table\n5 to 260 mm up"),
        (58, "project straight down,\ngroup at 25 mm"),
        (80, "fit one circle,\ncheck 60 to 90 mm"),
    ]
    for x, text in stages:
        _box(axis, x, 86, 19, 12, text, face="#f3f5f7", edge=MUTED, size=NOTE_SIZE)
    for left, right in zip([14, 36, 58], [36, 58, 80], strict=True):
        _arrow(axis, (left + 9.5, 86), (right - 9.5, 86), colour=MUTED)
    _box(axis, 103, 86, 16, 12, "settled?", face=PAPER, edge=INK, size=LABEL_SIZE, bold=True)
    _arrow(axis, (89.5, 86), (95, 86), colour=MUTED)

    _box(axis, 103, 64, 22, 13, "mask, position\nand width\nper glass", face=PAPER, edge=GOOD, ink=GOOD,
         size=NOTE_SIZE)
    _arrow(axis, (103, 80), (103, 70.5), colour=GOOD)
    _note(axis, 105.5, 75.5, "yes", colour=GOOD, size=NOTE_SIZE)

    _box(
        axis,
        36,
        50,
        34,
        17,
        "THE VERIFIER\nis this one object or two?\n13 numbers in, one probability out",
        face="#eaf1f9",
        edge=GLASS,
        ink=INK,
        size=NOTE_SIZE,
        dashed=True,
    )
    _arrow(axis, (95.5, 80), (53, 58), colour=GLASS, curve=0.10)
    _note(axis, 36, 64, "no — the doubtful ones", colour=GLASS, size=NOTE_SIZE, ha="center")

    outputs = [(58, "one object", GOOD), (46, "two objects", GOOD), (34, "cannot tell", WARN)]
    for y, text, colour in outputs:
        _box(axis, 78, y, 21, 9, text, face=PAPER, edge=colour, ink=colour, size=NOTE_SIZE)
        _arrow(axis, (53, 50), (67.5, y), colour=colour)
    _arrow(axis, (88.5, 58), (92, 61), colour=GOOD)
    _arrow(axis, (88.5, 46), (93, 57.5), colour=GOOD)

    _box(axis, 78, 16, 32, 11, "take another picture\nand ask again", face=PAPER, edge=WARN, ink=WARN,
         size=NOTE_SIZE)
    _arrow(axis, (78, 29.5), (78, 21.5), colour=WARN)
    axis.plot([62, 2, 2, 58], [16, 16, 97, 97], color=WARN, linewidth=1.3, zorder=1)
    _arrow(axis, (58, 97), (58, 92.3), colour=WARN)
    _note(axis, 4, 55, "the loop", colour=WARN, size=NOTE_SIZE)

    axis.set_title(
        "Everything grey is already built. Only the dashed box is new.",
        fontsize=TITLE_SIZE,
        color=INK,
        pad=10,
    )
    _note(
        axis,
        0,
        6.5,
        "The verifier is asked nothing about pixels, positions or widths. It answers one question,\n"
        "about groups the geometry could not settle, and it may answer “I cannot tell”.",
        size=NOTE_SIZE,
        va="top",
    )
    save(figure, "05-where-the-verifier-sits.png")


# ---------------------------------------------------- 3. what the model sees


def the_features(measured) -> None:
    """The input: an ambiguous cluster, its two candidate readings, and the row of numbers."""
    figure, axes = _panels(14.0, 5.0, [1.22, 0.9, 1.15])
    left, middle, right = axes

    dots = measured["dots"]
    one_centre, one_radius, one_rms, one_worst = measured["one"]
    (centre_a, radius_a), (centre_b, radius_b), two_rms = measured["two"]

    left.scatter(dots[:, 0], dots[:, 1], s=2.0, color=GLASS, alpha=0.40, linewidths=0)
    for point in measured["outline"][::3]:
        offset = point - one_centre
        on_circle = one_centre + offset / np.linalg.norm(offset) * one_radius
        left.plot([point[0], on_circle[0]], [point[1], on_circle[1]], color=WARN, linewidth=0.9, alpha=0.85)
    left.add_patch(
        Circle(tuple(one_centre), one_radius, facecolor="none", edgecolor=WARN, linewidth=1.8,
               linestyle=(0, (5, 3)))
    )
    for centre, radius in ((centre_a, radius_a), (centre_b, radius_b)):
        left.add_patch(Circle(tuple(centre), radius, facecolor="none", edgecolor=INK, linewidth=1.5))
    for centre_x, centre_y, radius in (NEAR, FAR):
        left.add_patch(
            Circle(
                (centre_x, centre_y),
                radius,
                facecolor="none",
                edgecolor=GOOD,
                linewidth=1.3,
                linestyle=(0, (1, 2)),
            )
        )
    for centre in (centre_a, centre_b):
        left.plot([centre[0], centre[0]], [centre[1], -64], color=MUTED, linewidth=0.7, linestyle=(0, (2, 2)))
    _arrow(left, (float(centre_a[0]), -64.0), (float(centre_b[0]), -64.0), colour=INK, style="<|-|>",
           width=1.0)
    left.text(
        0.5 * (centre_a[0] + centre_b[0]),
        -78,
        f"{measured['gap']:.0f} mm between the two candidate centres",
        ha="center",
        fontsize=NOTE_SIZE,
        color=INK,
    )
    sight = np.array([NEAR[0], NEAR[1]]) - np.array(CAMERA)
    sight = sight / np.linalg.norm(sight)
    _arrow(left, tuple(np.array(CAMERA) + sight * 398), tuple(np.array(CAMERA) + sight * 448),
           colour=MUTED, width=1.2)
    _note(left, -128, -38, "the camera,\nthis station", colour=MUTED)
    left.annotate(
        "the far glass, all but hidden\nbehind the near one",
        xy=(float(centre_b[0]), float(centre_b[1]) + 16),
        xytext=(52, 62),
        fontsize=NOTE_SIZE,
        color=INK,
        ha="center",
        arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.0},
    )
    left.set_xlim(-130, 116)
    left.set_ylim(-96, 82)
    left.set_aspect("equal")
    bare(left)
    left.set_title("One group of dots, two readings", fontsize=LABEL_SIZE, color=INK)
    handles = [
        Line2D([], [], marker="o", linestyle="none", color=GLASS, markersize=4, label=f"{len(dots):,} dots"),
        Line2D([], [], color=WARN, linestyle=(0, (5, 3)),
               label=f"one circle: {2 * one_radius:.0f} mm across"),
        Line2D([], [], color=INK, label=f"two circles: {2 * radius_a:.0f} and {2 * radius_b:.0f} mm"),
        Line2D([], [], color=GOOD, linestyle=(0, (1, 2)), label="what was really there: 72 and 69 mm"),
        Line2D([], [], color=WARN, linewidth=0.9,
               label=f"residuals of the one-circle fit: {one_rms:.1f} mm RMS"),
    ]
    left.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        frameon=False,
        fontsize=NOTE_SIZE - 0.4,
        labelcolor=INK,
        handlelength=2.2,
    )

    position, counts, edges = measured["profile"]
    centres = 0.5 * (edges[:-1] + edges[1:])
    middle.bar(centres, counts, width=(edges[1] - edges[0]) * 0.92, color=GLASS, alpha=0.75, linewidth=0)
    trough = counts[3:-3].argmin() + 3
    middle.annotate(
        f"a dip between two humps\ndip depth {measured['dip']:.2f}",
        xy=(centres[trough], counts[trough]),
        xytext=(85, max(counts) * 0.72),
        fontsize=NOTE_SIZE,
        color=INK,
        ha="center",
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )
    middle.set_xlabel("position along the line between\nthe two candidate centres, mm", fontsize=NOTE_SIZE)
    middle.set_ylabel("dots", fontsize=NOTE_SIZE)
    middle.tick_params(labelsize=NOTE_SIZE - 0.6, colors=INK)
    for side in ("top", "right"):
        middle.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        middle.spines[side].set_color(MUTED)
    middle.set_ylim(0, max(counts) * 1.32)
    middle.set_title("How the dots are spread", fontsize=LABEL_SIZE, color=INK)

    rows = [
        ("fitted diameter / kind's mean", f"{2 * one_radius / KIND_MEAN:.2f}"),
        ("one circle: RMS residual", f"{one_rms:.1f} mm"),
        ("one circle: worst residual", f"{one_worst:.1f} mm"),
        ("two circles: RMS residual", f"{two_rms:.1f} mm"),
        ("residual ratio, one / two", f"{one_rms / two_rms:.1f}"),
        ("larger candidate / kind's mean", f"{2 * radius_a / KIND_MEAN:.2f}"),
        ("smaller candidate / kind's mean", f"{2 * radius_b / KIND_MEAN:.2f}"),
        ("centre gap / larger radius", f"{measured['gap'] / max(radius_a, radius_b):.2f}"),
        ("clearance between the two rims", f"{measured['clearance']:+.2f}"),
        ("dip depth along the centre line", f"{measured['dip']:.2f}"),
        ("dot density / predicted", f"{measured['density'] / measured['predicted']:.2f}"),
        ("height / footprint width", f"{152.0 / (2 * one_radius):.2f}"),
        ("stations that saw it", "1 of 3"),
    ]
    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    right.set_title("What the model is shown", fontsize=LABEL_SIZE, color=INK)
    top = 0.945
    step = 0.068
    for index, (name, value) in enumerate(rows):
        y = top - index * step
        if index % 2 == 0:
            right.add_patch(
                FancyBboxPatch(
                    (0.0, y - step * 0.42),
                    1.0,
                    step * 0.84,
                    boxstyle="round,pad=0.0",
                    facecolor="#f3f5f7",
                    edgecolor="none",
                )
            )
        right.text(0.02, y, name, fontsize=NOTE_SIZE, color=INK, va="center")
        right.text(0.99, y, value, fontsize=NOTE_SIZE, color=GLASS, va="center", ha="right", weight="bold")
    right.text(
        0.0,
        top - len(rows) * step - 0.03,
        "Thirteen numbers, in millimetres and ratios.\nNot 76,800 pixels.",
        fontsize=NOTE_SIZE,
        color=MUTED,
        va="top",
    )

    figure.suptitle(
        "The model is shown what the geometry already measured, not the picture it came from",
        fontsize=TITLE_SIZE,
        color=INK,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    save(figure, "05-the-features.png")


# --------------------------------------- 4. the whole task, or one decision


def whole_task_or_one_decision() -> None:
    """The trade-off: what each way of learning costs, and what a mistake costs."""
    figure, axis = _sheet(12.4, 6.0)
    axis.set_xlim(0, 100)

    left_x, right_x = 47.0, 79.0
    axis.add_patch(
        FancyBboxPatch(
            (32.0, 12.0),
            30.0,
            72.0,
            boxstyle="round,pad=0.0,rounding_size=1.4",
            facecolor=WARN,
            alpha=0.07,
            edgecolor="none",
        )
    )
    axis.add_patch(
        FancyBboxPatch(
            (64.0, 12.0),
            30.0,
            72.0,
            boxstyle="round,pad=0.0,rounding_size=1.4",
            facecolor=GOOD,
            alpha=0.09,
            edgecolor="none",
        )
    )
    _note(axis, left_x, 92, "Learn the whole task", colour=WARN, size=LABEL_SIZE + 0.6, ha="center")
    _note(axis, left_x, 87, "“find all the objects”", colour=MUTED, ha="center", style="italic")
    _note(axis, right_x, 92, "Learn the one decision", colour=GOOD, size=LABEL_SIZE + 0.6, ha="center")
    _note(axis, right_x, 87, "“one object or two?”", colour=MUTED, ha="center", style="italic")

    rows = [
        ("What it is shown", "a 320 x 240 picture", "13 numbers the fit already made"),
        ("What it must produce", "a mask per object,\nfrom nothing", "one probability,\nor an abstention"),
        ("Labelled examples", "tens of thousands", "a few thousand rows"),
        ("Training", "hours to a day,\nand it wants a GPU", "seconds to minutes,\non a laptop CPU"),
        ("When it is wrong", "the wrong answer\nIS the answer",
         "one extra picture,\nor a pair left unseparated"),
        ("Can you read why", "no", "yes — print the 13 numbers"),
        ("If the file is missing", "no perception at all", "the geometry answers,\nexactly as before"),
    ]
    y = 78.0
    for index, (label, whole, narrow) in enumerate(rows):
        height = 10.0
        if index:
            axis.plot([2, 94], [y + height / 2, y + height / 2], color=MUTED, linewidth=0.5, alpha=0.5)
        _note(axis, 2, y, label, colour=INK, size=NOTE_SIZE)
        _note(axis, left_x, y, whole, colour=INK, ha="center")
        _note(axis, right_x, y, narrow, colour=INK, ha="center")
        y -= height

    axis.set_title(
        "Not a choice between learning and not learning. A choice about how much to learn.",
        fontsize=TITLE_SIZE,
        color=INK,
        pad=10,
    )
    _note(
        axis,
        0,
        1.0,
        "The example counts and times are orders of magnitude for a cell like this one, not measurements. "
        "The rows that matter are the last three.",
        size=NOTE_SIZE,
    )
    save(figure, "05-whole-task-or-one-decision.png")


# ------------------------------- 5. calibration, and the two thresholds


def calibration_and_bands() -> None:
    """The numbers: what a probability has to mean before a threshold can use it."""
    figure, axes = _panels(12.8, 4.9, [1.0, 1.3])
    reliability, bands = axes

    reliability.plot([0, 1], [0, 1], color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2,
                     label="what 0.9 should mean")
    honest_x = np.array([0.03, 0.12, 0.27, 0.40, 0.52, 0.63, 0.78, 0.89, 0.97])
    honest_y = np.array([0.05, 0.10, 0.29, 0.37, 0.54, 0.60, 0.79, 0.86, 0.95])
    reliability.plot(honest_x, honest_y, color=GOOD, marker="o", markersize=4, linewidth=1.6,
                     label="calibrated")
    sure_x = np.array([0.03, 0.12, 0.27, 0.40, 0.52, 0.63, 0.78, 0.89, 0.97])
    sure_y = np.array([0.21, 0.25, 0.32, 0.40, 0.47, 0.54, 0.62, 0.68, 0.72])
    reliability.plot(sure_x, sure_y, color=WARN, marker="o", markersize=4, linewidth=1.6,
                     label="over-confident")
    reliability.annotate(
        "it says 0.89 and is right\n0.68 of the time — which is\nhow a merged pair gets\nacted on",
        xy=(0.90, 0.665),
        xytext=(1.0, 0.16),
        fontsize=NOTE_SIZE,
        color=INK,
        ha="right",
        va="bottom",
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )
    reliability.set_xlim(0, 1)
    reliability.set_ylim(0, 1)
    reliability.set_xlabel("the probability the model reports", fontsize=NOTE_SIZE)
    reliability.set_ylabel("how often it was really two objects", fontsize=NOTE_SIZE)
    reliability.tick_params(labelsize=NOTE_SIZE - 0.6, colors=INK)
    for side in ("top", "right"):
        reliability.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        reliability.spines[side].set_color(MUTED)
    reliability.legend(loc="upper left", frameon=False, fontsize=NOTE_SIZE - 0.6, labelcolor=INK)
    reliability.set_title("First, make the number mean something", fontsize=LABEL_SIZE, color=INK)

    bare(bands)
    bands.set_xlim(-0.10, 1.12)
    bands.set_ylim(0, 1)
    regions = [
        (0.0, 0.25, GLASS, 0.22, "one object", "act on it"),
        (0.25, 0.75, MUTED, 0.30, "cannot tell", "take another picture"),
        (0.75, 1.0, GLASS, 0.55, "two objects", "act on it"),
    ]
    for start, end, colour, alpha, name, action in regions:
        bands.add_patch(
            FancyBboxPatch(
                (start, 0.60),
                end - start,
                0.16,
                boxstyle="round,pad=0.0",
                facecolor=colour,
                alpha=alpha,
                edgecolor="none",
            )
        )
        bands.text(0.5 * (start + end), 0.68, name, ha="center", va="center", fontsize=LABEL_SIZE, color=INK)
        bands.text(0.5 * (start + end), 0.52, action, ha="center", va="center", fontsize=NOTE_SIZE,
                   color=MUTED)
    for threshold in (0.25, 0.75):
        bands.plot([threshold, threshold], [0.58, 0.80], color=INK, linewidth=1.4)
        bands.text(threshold, 0.835, f"{threshold:.2f}", ha="center", fontsize=NOTE_SIZE, color=INK)
    bands.text(0.0, 0.92, "0", fontsize=NOTE_SIZE, color=MUTED, ha="center")
    bands.text(1.0, 0.92, "1", fontsize=NOTE_SIZE, color=MUTED, ha="center")
    bands.text(0.5, 0.92, "probability the group is two objects", fontsize=NOTE_SIZE, color=MUTED,
               ha="center")
    bands.annotate(
        "the worked example: 0.62",
        xy=(0.62, 0.585),
        xytext=(0.62, 0.38),
        fontsize=NOTE_SIZE,
        color=WARN,
        ha="center",
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )
    _arrow(bands, (0.25, 0.25), (0.08, 0.25), colour=GOOD, width=1.1)
    _arrow(bands, (0.75, 0.25), (0.92, 0.25), colour=GOOD, width=1.1)
    bands.text(0.5, 0.25, "widen the band", fontsize=NOTE_SIZE, color=GOOD, ha="center", va="center")
    bands.text(
        0.5,
        0.14,
        "wider: fewer wrong calls, and more arm time spent",
        fontsize=NOTE_SIZE,
        color=GOOD,
        ha="center",
    )
    bands.text(
        0.5,
        0.06,
        "narrower: fewer extra looks, and more merged pairs believed",
        fontsize=NOTE_SIZE,
        color=WARN,
        ha="center",
    )
    bands.set_title("Then, two thresholds give three answers", fontsize=LABEL_SIZE, color=INK)

    figure.suptitle(
        "A threshold on a number that does not mean what it says is a threshold on nothing",
        fontsize=TITLE_SIZE,
        color=INK,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    save(figure, "05-calibration-and-the-bands.png")


# ---------------------------------------------- 6. the abstain path as a loop


def abstain_loop(measured) -> None:
    """The feedback loop: what an abstention asks for, and where it says to look."""
    figure, axes = _panels(13.2, 5.6, [1.3, 1.0])
    flow, plan = axes

    flow.set_xlim(0, 116)
    flow.set_ylim(0, 100)
    bare(flow)
    _box(flow, 54, 88, 36, 11, "group the dots, fit the circles", face="#f3f5f7", edge=MUTED, size=NOTE_SIZE)
    _box(flow, 54, 66, 36, 11, "the verifier answers", face="#eaf1f9", edge=GLASS, size=NOTE_SIZE,
         dashed=True)
    _box(flow, 54, 44, 36, 11, "cannot tell", face=PAPER, edge=WARN, ink=WARN, size=NOTE_SIZE)
    _box(
        flow,
        54,
        20,
        42,
        13,
        "move the camera, take one picture\nseconds — the only expensive step",
        face=PAPER,
        edge=WARN,
        size=NOTE_SIZE,
    )
    _arrow(flow, (54, 82.5), (54, 71.5), colour=MUTED)
    _arrow(flow, (54, 60.5), (54, 49.5), colour=WARN)
    _arrow(flow, (54, 38.5), (54, 26.5), colour=WARN)
    flow.plot([33, 12, 12, 48], [20, 20, 95, 95], color=WARN, linewidth=1.3, zorder=1)
    _arrow(flow, (48, 95), (48, 93.5), colour=WARN)
    _note(flow, 14, 57, "budget:\ntwo extra\nlooks", colour=WARN, size=NOTE_SIZE)

    _box(flow, 96, 66, 30, 11, "one object / two", face=PAPER, edge=GOOD, ink=GOOD, size=NOTE_SIZE)
    _arrow(flow, (72, 66), (81, 66), colour=GOOD)
    _box(flow, 96, 44, 30, 14, "budget spent:\nreported unseparated,\nhanded to problem 3", face=PAPER,
         edge=MUTED, ink=INK, size=NOTE_SIZE)
    _arrow(flow, (72, 44), (81, 44), colour=MUTED)
    flow.set_title("Abstaining is not a shrug. It is a request.", fontsize=LABEL_SIZE, color=INK)

    for centre_x, centre_y, radius in (NEAR, FAR):
        plan.add_patch(
            Circle((centre_x, centre_y), radius, facecolor=GLASS, alpha=0.18, edgecolor=GLASS, linewidth=1.3)
        )
        plan.scatter([centre_x], [centre_y], s=14, color=INK, zorder=4)
    plan.plot([NEAR[0] - 40, FAR[0] + 40], [0, 0], color=INK, linestyle=(0, (4, 3)), linewidth=1.2)
    plan.text(0, 62, "the line between the two centres", ha="center", fontsize=NOTE_SIZE, color=INK)

    _arrow(plan, (-232, -44), (-100, -12), colour=WARN, width=1.6)
    plan.text(
        -244,
        -84,
        "this station: in line with\nboth, so the far one is hidden",
        fontsize=NOTE_SIZE,
        color=WARN,
        ha="left",
    )
    _arrow(plan, (0, -196), (0, -58), colour=GOOD, width=1.6)
    plan.text(
        16,
        -124,
        "look along the perpendicular:\n380 mm back, 120 mm above the\n"
        "table. No search is needed —\nthe two centres name the direction.",
        fontsize=NOTE_SIZE,
        color=GOOD,
        ha="left",
        va="center",
    )
    plan.set_xlim(-258, 262)
    plan.set_ylim(-220, 110)
    plan.set_aspect("equal")
    bare(plan)
    plan.set_title("The abstention says where to look", fontsize=LABEL_SIZE, color=INK)

    figure.suptitle(
        "The third answer is what turns a classifier into a loop",
        fontsize=TITLE_SIZE,
        color=INK,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    save(figure, "05-the-abstain-loop.png")


# ------------------------------------------- 7. what happens with no weights


def degrades_to_geometry() -> None:
    """The limit, and the consolation: the worst case is the previous behaviour."""
    figure, axis = _sheet(12.4, 5.4)
    axis.set_xlim(0, 118)

    for y, tint in ((72.0, GOOD), (30.0, MUTED)):
        axis.add_patch(
            FancyBboxPatch(
                (2.0, y - 15.0),
                72.0,
                30.0,
                boxstyle="round,pad=0.0,rounding_size=1.4",
                facecolor=tint,
                alpha=0.07,
                edgecolor="none",
            )
        )

    _note(axis, 4, 89, "the weights file is there", colour=GOOD, size=LABEL_SIZE)
    _box(axis, 16, 72, 20, 11, "a doubtful\ngroup", face=PAPER, edge=MUTED, size=NOTE_SIZE)
    _box(axis, 43, 72, 22, 11, "the verifier", face="#eaf1f9", edge=GLASS, size=NOTE_SIZE, dashed=True)
    _box(axis, 68, 79, 18, 9, "one / two", face=PAPER, edge=GOOD, ink=GOOD, size=NOTE_SIZE)
    _box(axis, 68, 64, 18, 9, "cannot tell", face=PAPER, edge=WARN, ink=WARN, size=NOTE_SIZE)
    _arrow(axis, (26, 72), (32, 72), colour=MUTED)
    _arrow(axis, (54, 74), (59, 78), colour=GOOD)
    _arrow(axis, (54, 70), (59, 66), colour=WARN)

    _note(axis, 4, 47, "it is missing, corrupt, or its feature list no longer matches", colour=MUTED,
          size=LABEL_SIZE)
    _box(axis, 16, 30, 20, 11, "a doubtful\ngroup", face=PAPER, edge=MUTED, size=NOTE_SIZE)
    _box(axis, 43, 30, 22, 11, "the verifier", face="#f3f5f7", edge=MUTED, ink=MUTED, size=NOTE_SIZE,
         dashed=True)
    axis.plot([34.5, 51.5], [24.5, 35.5], color=WARN, linewidth=2.0, zorder=5)
    axis.plot([34.5, 51.5], [35.5, 24.5], color=WARN, linewidth=2.0, zorder=5)
    _box(axis, 68, 30, 18, 9, "cannot tell", face=PAPER, edge=WARN, ink=WARN, size=NOTE_SIZE)
    _arrow(axis, (26, 30), (32, 30), colour=MUTED)
    axis.plot([16, 16, 63], [24.5, 18, 18], color=WARN, linewidth=1.3, zorder=1)
    _arrow(axis, (63, 18), (68, 25.5), colour=WARN)
    _note(axis, 20, 9, "every time — the caller catches the failure and abstains", colour=WARN,
          size=NOTE_SIZE)

    axis.add_patch(
        FancyBboxPatch(
            (78.0, 12.0),
            38.0,
            78.0,
            boxstyle="round,pad=0.0,rounding_size=1.4",
            facecolor="#f3f5f7",
            edgecolor=MUTED,
            linewidth=0.8,
        )
    )
    _note(axis, 81, 85, "what changes", colour=INK, size=LABEL_SIZE)
    changes = [
        ("extra pictures per run", "more", WARN),
        ("pairs reported unseparated", "more", WARN),
        ("wrong answers", "none new", GOOD),
        ("masks, positions, widths", "identical", GOOD),
        ("where they come from", "depth, not a model", GOOD),
        ("who notices", "the clock", MUTED),
    ]
    y = 74.0
    for name, value, colour in changes:
        _note(axis, 81, y, name, colour=INK, size=NOTE_SIZE)
        _note(axis, 113, y, value, colour=colour, size=NOTE_SIZE, ha="right")
        y -= 10.0
    _note(axis, 81, 17, "This is solutions 2 and 3,\nrunning as they do today.", colour=MUTED, size=NOTE_SIZE)

    axis.set_title(
        "A learned component whose worst case is the previous behaviour",
        fontsize=TITLE_SIZE,
        color=INK,
        pad=10,
    )
    save(figure, "05-degrades-to-geometry.png")


# ----------------------------------------------- the two geometries of hiding
#
# Both pictures below are real projections of the project's own glass outlines,
# taken from work_cell.glasses.shapes and put through the cell's own camera. A
# standing glass is a circle only in its footprint, and neither of the cell's
# two views ever sees that footprint straight on.

# SURVEY_H, FX and the kind's rim limits come from diagram_style, so that these
# pictures and the ones the other scripts draw cannot drift apart.
VIEW_HEIGHT = 120.0       # mm above the table; the height the level view looks from
STANDOFF = 380.0          # mm back from the glass the level view is measuring
MIN_SEPARATION = 150.0    # mm centre to centre; the closest two glasses ever stand
ZONE_DEPTH = 360.0        # mm; the glass zone is 320 by 360, from rack/layout.py
FRAME_W, FRAME_H = 320, 240

_SPREAD_A = family("tapered_glass", 8, 2)
_SPREAD_B = family("tapered_glass", 8, 1)
TALLEST = _SPREAD_A[5][0]     # 229 mm tall, 103 mm across the rim
SHORTEST = _SPREAD_A[7][0]    # 94 mm tall, 84 mm across
NARROWEST = _SPREAD_B[4][0]   # 197 mm tall, 65 mm across, the narrowest rim allowed

TALL_AT = 200.0               # mm from the point below the camera, in the overhead picture
BEHIND = 300.0                # mm further from the camera, in the level picture


def _profile(outline):
    """One glass's outline as heights and radii, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def _sizes(outline):
    """Height and rim diameter, in millimetres."""
    z, r = _profile(outline)
    return float(z.max()), float(2.0 * r.max())


def _splayed(centre, outline, slices=64):
    """The circles a standing glass draws in a picture taken straight down.

    The arithmetic is the one diagram_style.splay_circles documents: a slice at
    height z is scaled about the point below the camera by SURVEY_H / (SURVEY_H
    - z), because that slice is nearer the lens than the table is. The
    difference is that this runs over the project's own outline rather than a
    cone, so the silhouette is a real projection. The list it returns is what
    splay_covers, splay_patch and splay_width take, and the point below the
    camera is the origin.
    """
    z, r = _profile(outline)
    pick = np.linspace(0, len(z) - 1, slices).round().astype(int)
    offset = np.asarray(centre, dtype=float)
    circles = []
    for zi, ri in zip(z[pick], r[pick], strict=True):
        k = SURVEY_H / (SURVEY_H - zi)
        circles.append((offset * k, ri * k))
    return circles


def _level(glasses, scale=1.0, horizon_fraction=0.30):
    """What the level view sees, filled in, at `scale` times the real frame.

    The camera is VIEW_HEIGHT above the table and points level, so a horizontal
    circle is seen edge-on and images as a line. The silhouette is the band
    between the left and right walls of the outline, and filling each column
    between its highest and lowest lit row closes the rim.
    """
    width, height = int(round(FRAME_W * scale)), int(round(FRAME_H * scale))
    mask = np.zeros((height, width), np.uint8)
    centre_x = width / 2.0
    horizon = height * horizon_fraction
    for across, away, outline in glasses:
        z, r = _profile(outline)
        for zi, ri in zip(z, r, strict=True):
            row = int(round(horizon - scale * FX * (zi - VIEW_HEIGHT) / away))
            left = int(round(centre_x + scale * FX * (across - ri) / away))
            right = int(round(centre_x + scale * FX * (across + ri) / away))
            if 0 <= row < height:
                cv2.line(mask, (max(0, left), row), (min(width - 1, right), row), 255, 1)
    for column in np.flatnonzero(mask.any(axis=0)):
        lit = np.flatnonzero(mask[:, column])
        mask[lit.min() : lit.max() + 1, column] = 255
    return mask


def _packed(blind, grid_x, grid_y, radius):
    """Where the kind's smallest footprint really fits inside a blind patch.

    Dividing one area by the other overstates it, because circles do not tile.
    This places them greedily, roomiest spot first, and never lets two overlap.
    """
    room = cv2.distanceTransform(blind.astype(np.uint8), cv2.DIST_L2, 5)
    rows, columns = np.nonzero(room >= radius)
    order = np.argsort(-room[rows, columns])
    placed: list[tuple[float, float]] = []
    for index in order:
        x = float(grid_x[rows[index], columns[index]])
        y = float(grid_y[rows[index], columns[index]])
        if all((x - px) ** 2 + (y - py) ** 2 >= (2 * radius) ** 2 for px, py in placed):
            placed.append((x, y))
    return placed


def hiding():
    """Every number the two hiding pictures state, measured rather than assumed."""
    tall_h, tall_w = _sizes(TALLEST)
    short_h, short_w = _sizes(SHORTEST)
    narrow_h, narrow_w = _sizes(NARROWEST)

    tall = _splayed((TALL_AT, 0.0), TALLEST)
    along = _splayed((TALL_AT + MIN_SEPARATION, 0.0), SHORTEST)
    across = _splayed((TALL_AT, MIN_SEPARATION), SHORTEST)

    reaches = [(float(np.hypot(*c) - r), float(np.hypot(*c) + r)) for c, r in tall]
    inner = min(near for near, _ in reaches)
    outer = max(far for _, far in reaches)
    half_angle = float(np.degrees(np.arcsin(tall_w / 2.0 / TALL_AT)))

    # The hidden area, counted on a one-millimetre grid: the table the silhouette
    # covers, less the table the glass itself stands on.
    axis_x = np.arange(-60.0, outer + 60.0, 1.0)
    axis_y = np.arange(-260.0, 260.0, 1.0)
    grid_x, grid_y = np.meshgrid(axis_x, axis_y)
    covered = np.zeros(grid_x.shape, bool)
    for c, r in tall:
        covered |= (grid_x - c[0]) ** 2 + (grid_y - c[1]) ** 2 <= r * r
    stands_on = (grid_x - TALL_AT) ** 2 + grid_y**2 <= (tall_w / 2.0) ** 2
    blind = covered & ~stands_on
    blind_area = float(blind.sum())
    smallest_footprint = float(np.pi * (KIND_NARROWEST / 2.0) ** 2)
    fits = _packed(blind, grid_x, grid_y, KIND_NARROWEST / 2.0)

    # How far out the tall glass has to stand before it swallows the short one.
    reach_needed = {}
    for separation in (150.0, 200.0, 250.0):
        found = None
        for distance in range(60, 520, 2):
            if splay_covers(_splayed((float(distance), 0.0), TALLEST, slices=48),
                            _splayed((distance + separation, 0.0), SHORTEST, slices=48)):
                found = distance
                break
        reach_needed[separation] = found

    # The level view, at the real frame size and at three times it for drawing.
    lone = _level([(0.0, STANDOFF, NARROWEST)])
    both = _level([(0.0, STANDOFF, NARROWEST), (0.0, STANDOFF + BEHIND, TALLEST)])
    alone = _level([(0.0, STANDOFF + BEHIND, TALLEST)])
    differ = int(np.count_nonzero((both > 0) != (lone > 0)))
    far_area = int(np.count_nonzero(alone))
    twins = {
        gap: int(
            np.count_nonzero(
                (_level([(0.0, STANDOFF, TALLEST), (0.0, STANDOFF + gap, TALLEST)]) > 0)
                != (_level([(0.0, STANDOFF, TALLEST)]) > 0)
            )
        )
        for gap in (150.0, 200.0, 300.0)
    }
    # The shortest near glass that still covers the far one completely. The near
    # glass may be shorter than the one it hides, but not by any amount.
    shortest_cover = None
    for height, outline in sorted((_sizes(o)[0], o) for o, _ in _SPREAD_A + _SPREAD_B):
        near = _level([(0.0, STANDOFF, outline)])
        pair = _level([(0.0, STANDOFF, outline), (0.0, STANDOFF + BEHIND, TALLEST)])
        if not np.count_nonzero((pair > 0) != (near > 0)):
            shortest_cover = height
            break

    blocked_half = float(np.degrees(np.arcsin(narrow_w / 2.0 / STANDOFF)))
    strip = 2.0 * (STANDOFF + BEHIND) * np.tan(np.radians(blocked_half))
    strip_105_at = KIND_WIDEST / (2.0 * np.tan(np.radians(blocked_half)))

    # The strip of table the near glass blocks, from its own far side out to the
    # far edge of the glass zone, counted on the same one-millimetre grid.
    starts, stops = STANDOFF + narrow_w / 2.0, STANDOFF + ZONE_DEPTH
    strip_x = np.arange(starts - 40.0, stops + 40.0, 1.0)
    strip_y = np.arange(-140.0, 140.0, 1.0)
    strip_gx, strip_gy = np.meshgrid(strip_x, strip_y)
    inside_strip = (
        (np.abs(strip_gy) <= strip_gx * np.tan(np.radians(blocked_half)))
        & (strip_gx >= starts)
        & (strip_gx <= stops)
    )
    strip_area = float(inside_strip.sum())
    strip_fits = _packed(inside_strip, strip_gx, strip_gy, KIND_NARROWEST / 2.0)

    measured = {
        "tall": (tall_h, tall_w),
        "short": (short_h, short_w),
        "narrow": (narrow_h, narrow_w),
        "tall_k": SURVEY_H / (SURVEY_H - tall_h),
        "short_k": SURVEY_H / (SURVEY_H - short_h),
        "circles": (tall, along, across),
        "covers_along": splay_covers(tall, along),
        "covers_across": splay_covers(tall, across),
        "silhouette_width": splay_width(tall),
        "inner": inner,
        "outer": outer,
        "half_angle": half_angle,
        "blind_area": blind_area,
        "smallest_footprint": smallest_footprint,
        "fits": fits,
        "reach_needed": reach_needed,
        "level": (lone, both, alone),
        "differ": differ,
        "far_area": far_area,
        "twins": twins,
        "blocked_half": blocked_half,
        "strip": strip,
        "strip_105_at": strip_105_at,
        "strip_span": (starts, stops),
        "strip_area": strip_area,
        "strip_fits": strip_fits,
        "magnification": (STANDOFF + BEHIND) / STANDOFF,
        "shortest_cover": shortest_cover,
    }
    return measured


def report(measured) -> None:
    """Print every number the two hiding pictures and the document quote."""
    tall_h, tall_w = measured["tall"]
    short_h, short_w = measured["short"]
    narrow_h, narrow_w = measured["narrow"]
    print()
    print("looking straight down, from 450 mm:")
    print(f"  a slice 225 mm up is thrown out by {SURVEY_H / (SURVEY_H - 225.0):.3f}")
    print(f"  tall glass  {tall_h:.1f} mm tall, {tall_w:.1f} mm across, thrown out by "
          f"{measured['tall_k']:.3f}")
    print(f"  short glass {short_h:.1f} mm tall, {short_w:.1f} mm across, thrown out by "
          f"{measured['short_k']:.3f}")
    print(f"  the tall glass stands {TALL_AT:.0f} mm from the point below the camera; its outline")
    print(f"    runs from {measured['inner']:.0f} to {measured['outer']:.0f} mm out, is "
          f"{measured['silhouette_width']:.1f} mm across, and covers a wedge "
          f"{2 * measured['half_angle']:.1f} deg wide")
    print(f"  short glass {MIN_SEPARATION:.0f} mm further out along the same radius: covered "
          f"= {measured['covers_along']}")
    print(f"  the same glass {MIN_SEPARATION:.0f} mm across the radius instead: covered "
          f"= {measured['covers_across']}")
    print(f"  table hidden: {measured['blind_area']:.0f} mm2, which is "
          f"{measured['blind_area'] / measured['smallest_footprint']:.1f} times the "
          f"{measured['smallest_footprint']:.0f} mm2 footprint of the kind's smallest glass;")
    print(f"    packed without overlapping, {len(measured['fits'])} of them fit")
    for separation, distance in measured["reach_needed"].items():
        print(f"  {separation:.0f} mm apart: the tall glass must stand at least {distance} mm "
              "from the point below the camera")
    print("looking level, from 120 mm up and 380 mm back:")
    print(f"  near glass {narrow_h:.1f} mm tall, {narrow_w:.1f} mm across, at {STANDOFF:.0f} mm")
    print(f"  far glass  {tall_h:.1f} mm tall, {tall_w:.1f} mm across, {BEHIND:.0f} mm further back")
    print(f"  the far glass would fill {measured['far_area']} pixels of the {FRAME_W}x{FRAME_H} frame")
    print(f"  pixels that differ between the two glasses and the near one alone: {measured['differ']}")
    for gap, count in measured["twins"].items():
        print(f"  two glasses of the same size, {gap:.0f} mm apart in line: {count} pixels differ")
    print(f"  the near glass blocks a wedge {2 * measured['blocked_half']:.2f} deg wide, so the strip")
    print(f"    is {KIND_WIDEST:.0f} mm across at {measured['strip_105_at']:.0f} mm from the camera, "
          f"{measured['strip_105_at'] - STANDOFF:.0f} mm behind the near glass")
    print(f"  over the {ZONE_DEPTH:.0f} mm depth of the zone the strip is {measured['strip_area']:.0f} "
          f"mm2 of table, with room for {len(measured['strip_fits'])} of the smallest footprints")
    print(f"    nothing can see is {measured['strip']:.1f} mm across where the far glass stands, "
          f"against the kind's widest glass at {KIND_WIDEST:.0f} mm")
    print(f"  the near glass is {measured['magnification']:.3f} times nearer than the far one")
    print(f"  the shortest glass drawn that still covers the far one completely is "
          f"{measured['shortest_cover']:.1f} mm tall")
    print()


# ----------------------------------- 8. hidden from above, and the hint it leaves


def hidden_from_above(measured) -> None:
    """What the overhead geometry leaves the verifier: a patch it can measure."""
    tall_h, tall_w = measured["tall"]
    short_h, short_w = measured["short"]
    tall, along, _ = measured["circles"]
    figure, axes = new(13.6, 5.4, columns=3)
    scene, report_back, given = axes

    for axis in axes:
        axis.set_aspect("equal")
        axis.set_xlim(-95, 600)
        axis.set_ylim(-300, 290)
        bare(axis)
        axis.plot([0], [0], marker="+", markersize=13, markeredgewidth=1.7, color=INK, zorder=6)
        axis.plot([0, 590], [0, 0], color=MUTED, linewidth=0.8, linestyle=(0, (2, 3)), zorder=1)
        _note(axis, -92, -18, "the point below\nthe camera", colour=INK, va="top")

    # ---- what is really standing there
    splay_patch(scene, tall, colour=GLASS, alpha=0.20)
    splay_patch(scene, along, colour=WARN, alpha=0.55)
    scene.add_patch(Circle((TALL_AT, 0), tall_w / 2, facecolor="none", edgecolor=GLASS, linewidth=1.5,
                           zorder=5))
    scene.add_patch(Circle((TALL_AT + MIN_SEPARATION, 0), short_w / 2, facecolor="none", edgecolor=WARN,
                           linewidth=1.5, linestyle=(0, (3, 2)), zorder=5))
    scene.annotate(
        f"the tall glass stands here:\n{tall_h:.0f} mm tall, {tall_w:.0f} mm across",
        xy=(TALL_AT, tall_w / 2 + 4), xytext=(30, 200), fontsize=NOTE_SIZE, color=INK,
        arrowprops={"arrowstyle": "-|>", "color": GLASS, "linewidth": 1.0},
    )
    scene.annotate(
        f"the short glass stands here:\n{short_h:.0f} mm tall, {short_w:.0f} mm across",
        xy=(TALL_AT + MIN_SEPARATION, -short_w / 2 - 4), xytext=(398, -175), fontsize=NOTE_SIZE,
        color=INK, ha="center", arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.0},
    )
    for x in (TALL_AT, TALL_AT + MIN_SEPARATION):
        scene.plot([x, x], [-short_w / 2 - 6, -118], color=MUTED, linewidth=0.7, linestyle=(0, (2, 2)),
                   zorder=4)
    _arrow(scene, (TALL_AT, -118), (TALL_AT + MIN_SEPARATION, -118), colour=INK, style="<|-|>", width=1.0)
    _note(scene, TALL_AT + MIN_SEPARATION / 2, -105, f"{MIN_SEPARATION:.0f} mm", colour=INK, ha="center",
          va="bottom")
    _note(scene, 280, -240,
          f"The tall glass's outline is thrown out by {measured['tall_k']:.2f},\n"
          f"as far as {measured['outer']:.0f} mm. The short glass's is thrown\n"
          f"out by only {measured['short_k']:.2f}, so it ends up wholly inside.",
          colour=INK, ha="center")
    scene.set_title("On the table: what is really standing there", fontsize=LABEL_SIZE, color=INK, pad=8)

    # ---- what the survey hands back
    report_back.add_patch(Circle((TALL_AT, 0), tall_w / 2, facecolor=GLASS, alpha=0.32, edgecolor=GLASS,
                                 linewidth=1.6, zorder=5))
    report_back.add_patch(Circle((TALL_AT + MIN_SEPARATION, 0), short_w / 2, facecolor="none",
                                 edgecolor=MUTED, linewidth=1.2, linestyle=(0, (2, 3)), zorder=5))
    _arrow(report_back, (TALL_AT - tall_w / 2, 0), (TALL_AT + tall_w / 2, 0), colour=INK, style="<|-|>",
           width=1.0)
    _note(report_back, TALL_AT, tall_w / 2 + 10, f"{tall_w:.0f} mm", colour=INK, ha="center", va="bottom")
    report_back.annotate(
        f"one group, and the circle fitted to it is\n{tall_w:.0f} mm across \u2014 an ordinary width for "
        f"a kind\nwhose glasses run {KIND_NARROWEST:.0f} to {KIND_WIDEST:.0f} mm",
        xy=(TALL_AT - tall_w / 2 - 5, 16), xytext=(125, 200), fontsize=NOTE_SIZE, color=INK, ha="center",
        arrowprops={"arrowstyle": "-|>", "color": GLASS, "linewidth": 1.0},
    )
    report_back.annotate(
        "no group, no fitted width, no residual",
        xy=(TALL_AT + MIN_SEPARATION, -short_w / 2 - 6), xytext=(400, -150), fontsize=NOTE_SIZE,
        color=MUTED, ha="center", arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.0},
    )
    _note(report_back, 280, -240,
          "Nothing in this looks wrong, and nothing can. Every check\n"
          "this solution takes its inputs from is a check on something\n"
          "that was found, and the short glass was not found.",
          colour=INK, ha="center")
    report_back.set_title("What comes back: one group, one legal width", fontsize=LABEL_SIZE, color=INK,
                          pad=8)

    # ---- what the verifier is handed
    splay_patch(given, tall, colour=GLASS, alpha=0.18)
    given.add_patch(Circle((TALL_AT, 0), tall_w / 2, facecolor=PAPER, edgecolor=GLASS, linewidth=1.5,
                           zorder=5))
    for x, y in measured["fits"]:
        given.add_patch(Circle((x, y), KIND_NARROWEST / 2, facecolor="none", edgecolor=WARN,
                               linewidth=1.1, zorder=6))
    angle = np.radians(measured["half_angle"])
    for sign in (1, -1):
        given.plot([0, 590], [0, sign * 590 * np.tan(angle)], color=INK, linewidth=0.9,
                   linestyle=(0, (5, 3)), zorder=4)
    _arrow(given, (measured["inner"], -182), (measured["outer"], -182), colour=INK, style="<|-|>",
           width=1.0)
    _note(given, (measured["inner"] + measured["outer"]) / 2, -170,
          f"{measured['inner']:.0f} to {measured['outer']:.0f} mm out", colour=INK, ha="center",
          va="bottom")
    _note(given, 8, 232, f"a wedge {2 * measured['half_angle']:.1f}\u00b0 wide, which\nsplay leaves "
                         "unchanged\nwhatever the height", colour=INK, va="top")
    _note(given, 280, -248,
          f"{measured['blind_area'] / 1000:.1f} thousand mm\u00b2 of table nothing saw, with room for "
          f"{len(measured['fits'])}\nof the kind's smallest glasses, {KIND_NARROWEST:.0f} mm across. "
          "Every one of\nthose numbers was read off the outline in the picture.",
          colour=WARN, ha="center")
    given.set_title("What the verifier is handed", fontsize=LABEL_SIZE, color=INK, pad=8)

    figure.suptitle(
        "Looking straight down: the short glass leaves no pixels, and what is left is arithmetic",
        fontsize=TITLE_SIZE, color=INK, y=0.975,
    )
    figure.text(
        0.5, 0.015,
        f"Every outline here is one of the project's own glass profiles, projected from "
        f"{SURVEY_H:.0f} mm. A slice 225 mm up is thrown outwards by "
        f"{SURVEY_H / (SURVEY_H - 225.0):.1f}, which is what lets the tall glass reach over its "
        f"neighbour. Hiding this way needs\nboth closeness and a large difference in height: at "
        f"{MIN_SEPARATION:.0f} mm apart the tall glass must stand {measured['reach_needed'][150.0]} mm "
        f"out from the point below the camera, and at 250 mm apart, "
        f"{measured['reach_needed'][250.0]} mm. Turned across the radius\ninstead of along it, the same "
        f"pair at the same {MIN_SEPARATION:.0f} mm does not hide at all.",
        fontsize=NOTE_SIZE, color=INK, ha="center",
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.11, wspace=0.04)
    save(figure, "05-hidden-from-above.png")


# --------------------------------- 9. hidden from the side, and the hint it does not


def hidden_from_the_side(measured) -> None:
    """What the level geometry leaves the verifier: two identical pictures."""
    tall_h, tall_w = measured["tall"]
    narrow_h, narrow_w = measured["narrow"]
    figure, axes = _panels(13.6, 5.0, [1.0, 1.0, 1.72])
    with_far, without, given = axes

    # ---- the two pictures, which are the same picture
    scale = 3.0
    lone = _level([(0.0, STANDOFF, NARROWEST)], scale=scale)
    both = _level([(0.0, STANDOFF, NARROWEST), (0.0, STANDOFF + BEHIND, TALLEST)], scale=scale)
    alone = _level([(0.0, STANDOFF + BEHIND, TALLEST)], scale=scale)
    x, y, w, h = cv2.boundingRect(lone)
    pad_x, pad_y = int(0.95 * w), 34
    box = (max(0, x - pad_x), min(lone.shape[1], x + w + pad_x),
           max(0, y - pad_y), min(lone.shape[0], y + h + pad_y))
    crop = (slice(box[2], box[3]), slice(box[0], box[1]))
    wide, high = box[1] - box[0], box[3] - box[2]

    notes = (
        "The dashed line is where the far glass is.\nIt is drawn on. Nothing in the picture marks it.",
        f"Not one of the {FRAME_W} by {FRAME_H} frame's pixels\ndiffers from the picture beside it.",
    )
    for axis, mask, title, note_text, colour in (
        (with_far, both, "The level picture, both glasses standing", notes[0], WARN),
        (without, lone, "The level picture, the far glass taken away", notes[1], INK),
    ):
        bare(axis)
        axis.set_anchor("N")
        axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)
        rgba = np.zeros((*mask[crop].shape, 4), float)
        rgba[mask[crop] > 0] = to_rgba(GLASS, 0.50)
        axis.imshow(rgba, interpolation="nearest")
        axis.contour(mask[crop].astype(float), [0.5], colors=[GLASS], linewidths=1.4)
        axis.add_patch(Rectangle((0, 0), wide - 1, high - 1, facecolor="none", edgecolor=MUTED,
                                 linewidth=0.9))
        axis.set_xlim(-0.5, wide - 0.5)
        axis.set_ylim(high * 1.24, -0.5)
        _note(axis, wide / 2, high * 1.06, note_text, colour=colour, ha="center", va="top")
    with_far.contour(alone[crop].astype(float), [0.5], colors=[WARN], linewidths=1.3,
                     linestyles=[(0, (4, 3))])

    # ---- what the verifier is handed: the strip, measured from what was already known
    given.set_aspect("equal")
    given.set_anchor("N")
    given.set_xlim(-130, 810)
    given.set_ylim(-300, 300)
    bare(given)
    angle = np.radians(measured["blocked_half"])
    starts, stops = measured["strip_span"]
    given.plot([0, 790], [0, 0], color=MUTED, linewidth=0.8, linestyle=(0, (2, 3)), zorder=1)
    given.fill([starts, stops, stops, starts],
               [starts * np.tan(angle), stops * np.tan(angle),
                -stops * np.tan(angle), -starts * np.tan(angle)],
               facecolor=WARN, alpha=0.13, zorder=2)
    for sign in (1, -1):
        given.plot([0, stops], [0, sign * stops * np.tan(angle)], color=WARN, linewidth=1.0,
                   linestyle=(0, (5, 3)), zorder=3)
    for cx, cy in measured["strip_fits"]:
        given.add_patch(Circle((cx, cy), KIND_NARROWEST / 2, facecolor="none", edgecolor=WARN,
                               linewidth=1.1, zorder=6))
    given.add_patch(Circle((STANDOFF, 0), narrow_w / 2, facecolor=GLASS, alpha=0.30, edgecolor=GLASS,
                           linewidth=1.5, zorder=5))
    given.add_patch(Circle((STANDOFF + BEHIND, 0), tall_w / 2, facecolor=MUTED, alpha=0.22,
                           edgecolor=MUTED, linewidth=1.2, linestyle=(0, (2, 3)), zorder=4))
    given.plot([0], [0], marker="o", markersize=7, color=INK, zorder=6)
    _note(given, -122, -24, f"the camera,\n{VIEW_HEIGHT:.0f} mm up,\nlooking level", colour=INK,
          va="top")
    _arrow(given, (0, 118), (STANDOFF, 118), colour=INK, style="<|-|>", width=1.0)
    _note(given, STANDOFF / 2, 128, f"{STANDOFF:.0f} mm to the near glass", colour=INK, ha="center",
          va="bottom")
    given.annotate(
        "the far glass really stands here",
        xy=(STANDOFF + BEHIND, -tall_w / 2 - 5), xytext=(620, -150), fontsize=NOTE_SIZE, color=MUTED,
        ha="center", arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.0},
    )
    _note(given, 330, -238,
          f"{measured['strip_area'] / 1000:.1f} thousand mm\u00b2 of table nothing saw over the "
          f"{ZONE_DEPTH:.0f} mm depth of the zone,\nwith room for {len(measured['strip_fits'])} of the "
          f"kind's smallest glasses. Every one of those numbers\ncomes from the near glass's position "
          "and size, which were already known.\nThe level picture contributed none of it, and could not.",
          colour=WARN, ha="center")
    given.set_title("What the verifier is handed", fontsize=LABEL_SIZE, color=INK, pad=8)

    figure.suptitle(
        "Looking level: the far glass leaves no pixels either, and this time the picture says nothing",
        fontsize=TITLE_SIZE, color=INK, y=0.99,
    )
    figure.text(
        0.5, 0.015,
        f"The far glass would fill {measured['far_area']:,} pixels of the frame on its own, and fills none "
        f"of them here. The glass that loses is the further one, not the shorter one: the near glass is "
        f"{narrow_w:.0f} mm across\nand covers one {tall_w:.0f} mm across, because standing "
        f"{measured['magnification']:.2f} times nearer magnifies it by that much. Distance between them "
        f"buys nothing either \u2014 two glasses of the same size in line hide\neach other exactly at "
        f"{MIN_SEPARATION:.0f} mm apart and at {BEHIND:.0f} mm.",
        fontsize=NOTE_SIZE, color=INK, ha="center",
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.11, wspace=0.06)
    save(figure, "05-hidden-from-the-side.png")


def main() -> None:
    measured = features()
    one_centre, one_radius, one_rms, one_worst = measured["one"]
    (centre_a, radius_a), (centre_b, radius_b), two_rms = measured["two"]
    print(
        "one circle: "
        f"{2 * one_radius:.1f} mm, rms {one_rms:.2f} mm, worst {one_worst:.2f} mm, centre "
        f"({one_centre[0]:.1f}, {one_centre[1]:.1f})"
    )
    print(
        "two circles: "
        f"{2 * radius_a:.1f} and {2 * radius_b:.1f} mm, gap {measured['gap']:.1f} mm, rms {two_rms:.2f} mm, "
        f"clearance {measured['clearance']:+.2f}"
    )
    print(
        f"dots {len(measured['dots'])}, area {measured['area']:.0f} mm^2, "
        f"density {measured['density']:.3f} of {measured['predicted']:.3f} predicted "
        f"= {measured['density'] / measured['predicted']:.2f}, dip {measured['dip']:.2f}"
    )
    ambiguous_band(measured)
    where_it_sits()
    the_features(measured)
    whole_task_or_one_decision()
    calibration_and_bands()
    abstain_loop(measured)
    degrades_to_geometry()
    geometry = hiding()
    report(geometry)
    hidden_from_above(geometry)
    hidden_from_the_side(geometry)


if __name__ == "__main__":
    main()
