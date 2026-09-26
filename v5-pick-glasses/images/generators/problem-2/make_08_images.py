"""Diagrams for solution 8 — per-pixel votes for the centre.

Run from the project root:

    pixi run python images/generators/problem-2/make_08_images.py

Every number drawn here comes from the cell: fx = fy = 277.1 pixels, survey
height 450 mm, footprints 45 to 105 mm across, and the worked example's pair of
glasses 90 mm apart with footprints of 76 and 73 mm.

The two hidden-glass pictures at the end go further than the rest. Their
silhouettes are real projections of the project's own glass outlines, taken from
``work_cell.glasses.shapes`` through the cell's own camera, and their vote maps
are computed from the pixels those projections leave visible. Nothing in them is
drawn to look convincing.
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
    splay_circles,
    splay_covers,
    splay_width,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import family  # noqa: E402

RNG = np.random.default_rng(8)

MM_PER_PIXEL = SURVEY_H / FX  # 1.624 mm on the table, one pixel wide, at survey height

# The rest of the cell, for the two views the hidden-glass pictures are about.
VIEW_HEIGHT = 120.0   # mm above the table, looking level (arm/dimensions MEASURE_VIEW_HEIGHT)
STANDOFF = 380.0      # mm from the near glass, the measuring standoff derived in solution 3
MIN_SEP = 150.0       # mm centre to centre, the closest two glasses ever stand (glasses/spawn)
HELD_OUT_RMS = 6.0    # mm, what a pile's spread comes to when the answer is right
WINDOW = 18.0         # mm, the mean-shift window radius this solution chose
SEEDS = 300           # how many votes the windows are started from
FAR = 1.0e9           # a depth no surface is at

# One kind, drawn from the project's own range. The tall member is near the top of
# tapered_glass's height range and the short one near the bottom, which is the pair
# the wide range exists to allow.
TALL = family("tapered_glass", 8, 2)[0][0]
SHORT = family("tapered_glass", 8, 2)[7][0]


# --------------------------------------------------------------------------- helpers


def tumbler(centre_x: float, base: float, height: float, bottom_r: float, top_r: float) -> np.ndarray:
    """The silhouette of an upright glass, as polygon points."""
    t = np.linspace(0.0, 1.0, 48)
    radius = bottom_r + (top_r - bottom_r) * t**0.6
    y = base + height * t
    right = np.column_stack([centre_x + radius, y])
    left = np.column_stack([centre_x - radius[::-1], y[::-1]])
    return np.vstack([right, left])


def frame(axis, x_limits: tuple[float, float], y_limits: tuple[float, float]) -> None:
    """A bare, square-scaled panel with fixed limits."""
    bare(axis)
    axis.set_xlim(*x_limits)
    axis.set_ylim(*y_limits)
    axis.set_aspect("equal")


def cloud(centre: tuple[float, float], spread: float, count: int) -> np.ndarray:
    """A round blob of votes about a centre, in millimetres."""
    return RNG.normal(loc=centre, scale=spread, size=(count, 2))


def disc(centre: tuple[float, float], radius: float, count: int) -> np.ndarray:
    """Points spread evenly over a footprint, in millimetres."""
    angle = RNG.uniform(0.0, 2.0 * np.pi, count)
    spread = radius * np.sqrt(RNG.uniform(0.0, 1.0, count))
    return np.column_stack([centre[0] + spread * np.cos(angle), centre[1] + spread * np.sin(angle)])


def density(points: np.ndarray, grid_x: np.ndarray, grid_y: np.ndarray, bandwidth: float) -> np.ndarray:
    """How thick the votes are at every point of a grid. A sum of soft bumps, nothing more."""
    mesh_x, mesh_y = np.meshgrid(grid_x, grid_y)
    total = np.zeros_like(mesh_x)
    for chunk in np.array_split(points, 8):
        dx = mesh_x[:, :, None] - chunk[:, 0]
        dy = mesh_y[:, :, None] - chunk[:, 1]
        total += np.exp(-(dx**2 + dy**2) / (2 * bandwidth**2)).sum(axis=2)
    return total / total.max()


def mean_shift_path(points: np.ndarray, start: tuple[float, float], radius: float) -> np.ndarray:
    """Slide a circular window to the average of the votes inside it, until it stops moving."""
    here = np.array(start, dtype=float)
    path = [here.copy()]
    for _ in range(60):
        inside = points[np.linalg.norm(points - here, axis=1) <= radius]
        if len(inside) == 0:
            break
        moved = inside.mean(axis=0)
        path.append(moved.copy())
        if np.linalg.norm(moved - here) < 0.05:
            here = moved
            break
        here = moved
    return np.array(path)


def votes_to(points: np.ndarray, target: tuple[float, float], keep: int) -> np.ndarray:
    """A thinned selection of arrow tails, so the arrows stay countable."""
    index = RNG.choice(len(points), size=min(keep, len(points)), replace=False)
    picked = points[index]
    return np.column_stack([picked, np.full(len(picked), target[0]), np.full(len(picked), target[1])])


def arrows(axis, tails: np.ndarray, colour: str, width: float = 0.9) -> None:
    for x, y, target_x, target_y in tails:
        axis.annotate(
            "",
            xy=(target_x, target_y),
            xytext=(x, y),
            arrowprops={"arrowstyle": "-|>", "color": colour, "lw": width, "shrinkA": 0, "shrinkB": 7},
        )


# --------------------------------------------------------------------------- 1. the problem


def one_region_not_two() -> None:
    figure, axes = new(14.6, 5.0, columns=3)
    left, middle, right = axes
    limits = ((-130, 130), (-108, 95))
    white = {"facecolor": PAPER, "edgecolor": "none", "pad": 1.5}

    # On the table the two glasses are plainly separate.
    left.set_title("On the table: two glasses, 15 mm apart", fontsize=TITLE_SIZE, color=INK)
    frame(left, *limits)
    for centre_x, radius, name in ((-45, 38, "76 mm"), (45, 36.5, "73 mm")):
        left.add_patch(Circle((centre_x, 0), radius, facecolor=GLASS, alpha=0.30, edgecolor=GLASS, lw=1.6))
        left.add_patch(Circle((centre_x, 0), radius + 25, facecolor="none", edgecolor=MUTED, lw=1.0, ls=":"))
        left.plot([centre_x], [0], marker="x", color=INK, ms=6, mew=1.6)
        left.text(centre_x, -radius - 13, name, ha="center", fontsize=NOTE_SIZE, color=INK, bbox=white)
    left.annotate(
        "",
        xy=(8.5, 0),
        xytext=(-7, 0),
        arrowprops={"arrowstyle": "<|-|>", "color": WARN, "lw": 1.4},
    )
    left.text(0, 15, "15 mm", ha="center", fontsize=NOTE_SIZE, color=WARN, bbox=white)
    left.text(
        0,
        -88,
        "dotted rings: the 25 mm grouping distance.\nThey touch, so clustering makes one group.",
        ha="center",
        fontsize=NOTE_SIZE,
        color=MUTED,
    )

    # In the picture the class map has no room to say which glass.
    middle.set_title('In the picture: every pixel says "glass"', fontsize=TITLE_SIZE, color=INK)
    frame(middle, *limits)
    middle.plot([-118, -6], [-58, -58], color=MUTED, lw=1.2)
    middle.plot([2, 118], [-44, -44], color=MUTED, lw=1.2, alpha=0.6)
    for centre_x, base, bottom_r, top_r, height in ((22, -44, 27, 34, 74), (-24, -58, 30, 38, 90)):
        middle.add_patch(
            Polygon(tumbler(centre_x, base, height, bottom_r, top_r), closed=True, facecolor=GLASS, lw=0)
        )
    merged_note = (
        "the near glass covers part of the far one.\n"
        "One region, and a class label has no field\n"
        "for which glass it belongs to."
    )
    middle.text(
        0,
        -88,
        merged_note,
        ha="center",
        fontsize=NOTE_SIZE,
        color=MUTED,
    )

    # What the next step in the pipeline is handed.
    right.set_title("What downstream is handed: one object", fontsize=TITLE_SIZE, color=INK)
    frame(right, *limits)

    def at(millimetres: float) -> float:
        """Place a width, in millimetres, on the panel's own scale."""
        return -110.0 + millimetres * (220.0 / 180.0)

    axis_arrow = {"arrowstyle": "-|>", "color": INK, "lw": 1.2}
    right.annotate("", xy=(118, 45), xytext=(-115, 45), arrowprops=axis_arrow)
    right.add_patch(
        Rectangle((at(60), 38), at(90) - at(60), 14, facecolor=GOOD, alpha=0.35, edgecolor=GOOD, lw=1.4)
    )
    right.text(at(75), 60, "60 to 90 mm", ha="center", fontsize=NOTE_SIZE, color=INK)
    right.text(at(75), 22, "what this kind of\nglass can be", ha="center", fontsize=NOTE_SIZE, color=MUTED)
    right.plot([at(165)], [45], marker="v", color=WARN, ms=12)
    right.text(at(165), 60, "164.5 mm", ha="center", fontsize=NOTE_SIZE, color=WARN)
    right.text(at(165), 22, "what the one\nregion measures", ha="center", fontsize=NOTE_SIZE, color=WARN)
    sum_line = "90 + 76/2 + 73/2 = 164.5 mm, or 101 pixels"
    right.text(0, -18, sum_line, ha="center", fontsize=NOTE_SIZE, color=INK)
    right.text(
        0,
        -60,
        "The check notices. It cannot fix it:\nnothing in a class map says where to cut.",
        ha="center",
        fontsize=LABEL_SIZE,
        color=WARN,
    )

    figure.tight_layout()
    save(figure, "08-one-region-not-two.png")


# --------------------------------------------------------------------------- 2. the idea


def the_voting_idea() -> None:
    figure, axes = new(12.6, 4.4, columns=2)
    left, right = axes
    limits = ((-92, 92), (-64, 48))

    def pixels_of(centre_x: float, radius: float) -> np.ndarray:
        blob = cloud((centre_x, 0.0), 16.0, 900)
        return blob[np.linalg.norm(blob - (centre_x, 0.0), axis=1) < radius]

    left.set_title("One glass: every arrow ends in the same place", fontsize=TITLE_SIZE, color=INK)
    frame(left, *limits)
    disc = pixels_of(0.0, 36.0)
    left.scatter(disc[:, 0], disc[:, 1], s=4, color=GLASS, alpha=0.30, lw=0)
    far = disc[np.linalg.norm(disc, axis=1) > 20]
    arrows(left, votes_to(far, (0.0, 0.0), 16), GLASS, width=1.1)
    left.plot([0], [0], marker="*", color=GOOD, ms=14, zorder=5)
    left.text(0, -50, "one peak = one glass", ha="center", fontsize=LABEL_SIZE, color=GOOD)

    right.set_title("Two touching glasses: two places", fontsize=TITLE_SIZE, color=INK)
    frame(right, *limits)
    for centre_x, colour in ((-36.0, GLASS), (36.0, WARN)):
        blob = pixels_of(centre_x, 36.0)
        right.scatter(blob[:, 0], blob[:, 1], s=4, color=colour, alpha=0.30, lw=0)
        outer = blob[np.linalg.norm(blob - (centre_x, 0.0), axis=1) > 20]
        arrows(right, votes_to(outer, (centre_x, 0.0), 16), colour, width=1.1)
        right.plot([centre_x], [0], marker="*", color=GOOD, ms=14, zorder=5)
    right.plot([0, 0], [-36, 36], color=INK, lw=1.0, ls="--")
    seam_note = (
        "the seam is not a gap. It is a change of direction,\n"
        "and direction is what the network predicts."
    )
    right.text(0, -52, seam_note, ha="center", fontsize=LABEL_SIZE, color=INK)

    figure.tight_layout()
    save(figure, "08-the-voting-idea.png")


# --------------------------------------------------------------------------- 3. where to vote


def image_space_against_table_space() -> None:
    figure, axes = new(13.2, 5.2, columns=2)
    left, right = axes

    left.set_title("Voting in the picture: the answer moves with range", fontsize=TITLE_SIZE, color=WARN)
    frame(left, (-100, 100), (-70, 70))
    near_far = ((-50, 34.6, "300 mm away", "35 px"), (50, 17.3, "600 mm away", "17 px"))
    for centre_x, radius, depth, offset in near_far:
        left.add_patch(Circle((centre_x, 8), radius, facecolor=GLASS, alpha=0.28, edgecolor=GLASS, lw=1.5))
        left.annotate(
            "",
            xy=(centre_x, 8),
            xytext=(centre_x + radius, 8),
            arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 1.8},
        )
        label_y = 8 + radius * 0.25 + 5
        left.text(centre_x + radius / 2, label_y, offset, ha="center", fontsize=NOTE_SIZE, color=WARN)
        left.text(centre_x, -48, depth, ha="center", fontsize=NOTE_SIZE, color=INK)
    left.text(
        0,
        -62,
        "the same glass, the same 37.5 mm of real offset.\nTo predict pixels, learn the camera too.",
        ha="center",
        fontsize=LABEL_SIZE,
        color=WARN,
    )

    right.set_title("Voting on the table: one number at every range", fontsize=TITLE_SIZE, color=GOOD)
    frame(right, (-100, 100), (-70, 70))
    for centre_x, depth in ((-50, "seen from 300 mm"), (50, "seen from 600 mm")):
        right.add_patch(Circle((centre_x, 8), 26, facecolor=GLASS, alpha=0.28, edgecolor=GLASS, lw=1.5))
        right.annotate(
            "",
            xy=(centre_x, 8),
            xytext=(centre_x + 26, 8),
            arrowprops={"arrowstyle": "-|>", "color": GOOD, "lw": 1.8},
        )
        right.text(centre_x + 13, 20, "37.5 mm", ha="center", fontsize=NOTE_SIZE, color=GOOD)
        right.text(centre_x, -48, depth, ha="center", fontsize=NOTE_SIZE, color=INK)
    table_note = (
        "depth and the known table height put each pixel on the\n"
        "table first. Scale is gone before it starts."
    )
    right.text(
        0,
        -62,
        table_note,
        ha="center",
        fontsize=LABEL_SIZE,
        color=GOOD,
    )

    figure.tight_layout()
    save(figure, "08-image-space-against-table-space.png")


# --------------------------------------------------------------------------- 4. the stages


def the_five_stages() -> None:
    figure, axes = new(17.0, 4.2, columns=5)
    near = disc((-45.0, 0.0), 38.0, 620)
    far = disc((45.0, 0.0), 36.5, 560)
    both = np.vstack([near, far])
    glasses = ((22, -44, 27, 34, 74), (-24, -58, 30, 38, 90))

    # 1. the picture
    axes[0].set_title("1. the picture", fontsize=TITLE_SIZE, color=INK)
    frame(axes[0], (-100, 100), (-108, 92))
    axes[0].add_patch(Rectangle((-92, -74), 184, 150, facecolor="#eef2f6", edgecolor=MUTED, lw=1.0))
    for centre_x, base, bottom_r, top_r, height in glasses:
        axes[0].add_patch(
            Polygon(tumbler(centre_x, base, height, bottom_r, top_r), closed=True, facecolor=GLASS, lw=0)
        )
    axes[0].text(0, -94, "RGB and depth, 320 x 240", ha="center", fontsize=NOTE_SIZE, color=MUTED)

    # 2. the mask, from the table height alone
    axes[1].set_title("2. the mask — no network", fontsize=TITLE_SIZE, color=GOOD)
    frame(axes[1], (-100, 100), (-108, 92))
    axes[1].add_patch(Rectangle((-92, -74), 184, 150, facecolor="#f6f6f6", edgecolor=MUTED, lw=1.0))
    for centre_x, base, bottom_r, top_r, height in glasses:
        axes[1].add_patch(
            Polygon(tumbler(centre_x, base, height, bottom_r, top_r), closed=True, facecolor=GOOD)
        )
    axes[1].text(0, -94, "5 to 260 mm above the table top", ha="center", fontsize=NOTE_SIZE, color=GOOD)

    # 3. every mask pixel dropped onto the table
    axes[2].set_title("3. on the table, in mm", fontsize=TITLE_SIZE, color=INK)
    frame(axes[2], (-100, 100), (-108, 92))
    axes[2].scatter(both[:, 0], both[:, 1], s=3.5, color=MUTED, alpha=0.7, lw=0)
    axes[2].annotate(
        "",
        xy=(8.5, 0),
        xytext=(-7, 0),
        arrowprops={"arrowstyle": "<|-|>", "color": WARN, "lw": 1.3},
    )
    axes[2].text(
        0, 14, "15 mm", ha="center", fontsize=NOTE_SIZE, color=WARN,
        bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 1.5},
    )
    axes[2].text(0, -94, "one group at 25 mm — merged", ha="center", fontsize=NOTE_SIZE, color=WARN)

    # 4. the network moves each point by its predicted offset
    axes[3].set_title("4. each point votes", fontsize=TITLE_SIZE, color=INK)
    frame(axes[3], (-100, 100), (-108, 92))
    axes[3].scatter(both[:, 0], both[:, 1], s=3.5, color="#dfe4e9", lw=0)
    for blob, centre_x in ((near, -45.0), (far, 45.0)):
        landed = cloud((centre_x, 0.0), 6.5, len(blob))
        axes[3].scatter(landed[:, 0], landed[:, 1], s=3.5, color=GLASS, alpha=0.55, lw=0, zorder=4)
        outer = blob[np.linalg.norm(blob - (centre_x, 0.0), axis=1) > 22]
        arrows(axes[3], votes_to(outer, (centre_x, 0.0), 9), GLASS, width=0.8)
    axes[3].text(0, -94, "dx, dy in millimetres", ha="center", fontsize=NOTE_SIZE, color=GLASS)

    # 5. peaks, and the masks that follow
    axes[4].set_title("5. two peaks, two masks", fontsize=TITLE_SIZE, color=GOOD)
    frame(axes[4], (-100, 100), (-108, 92))
    axes[4].scatter(near[:, 0], near[:, 1], s=3.5, color=GLASS, alpha=0.6, lw=0)
    axes[4].scatter(far[:, 0], far[:, 1], s=3.5, color=WARN, alpha=0.6, lw=0)
    for centre_x in (-45.0, 45.0):
        axes[4].plot([centre_x], [0], marker="*", color=GOOD, ms=16, zorder=5)
    axes[4].text(0, -94, "76 mm and 73 mm — both in range", ha="center", fontsize=NOTE_SIZE, color=GOOD)

    figure.tight_layout()
    save(figure, "08-the-five-stages.png")


# --------------------------------------------------------------------------- 5. votes to objects


def vote_cloud_and_mean_shift() -> None:
    figure, axes = new(14.4, 4.4, columns=3)
    grid = np.linspace(-85, 85, 111)
    levels = np.linspace(0.07, 1.0, 8)
    limits = ((-85, 85), (-78, 52))
    radius = 18.0

    single = cloud((0.0, 0.0), 6.5, 1700)
    pair = np.vstack([cloud((-45.0, 0.0), 7.0, 850), cloud((45.0, 2.0), 7.0, 820)])

    panels = (
        (axes[0], single, "One glass: one thick patch", "1,700 votes, spread 6 mm RMS"),
        (axes[1], pair, "Two glasses: two patches", "90 mm between the peaks"),
    )
    for axis, points, title, note in panels:
        axis.set_title(title, fontsize=TITLE_SIZE, color=INK)
        frame(axis, *limits)
        field = density(points, grid, grid, 7.0)
        axis.contourf(grid, grid, field, levels=levels, cmap="Blues", alpha=0.9)
        axis.scatter(points[:, 0], points[:, 1], s=2, color=INK, alpha=0.12, lw=0)
        axis.text(0, -52, note, ha="center", fontsize=NOTE_SIZE, color=MUTED)

    axes[2].set_title("The window slides uphill and stops", fontsize=TITLE_SIZE, color=GOOD)
    frame(axes[2], *limits)
    axes[2].scatter(pair[:, 0], pair[:, 1], s=2, color=MUTED, alpha=0.35, lw=0)
    for centre in ((-45.0, 0.0), (45.0, 2.0)):
        away = np.linalg.norm(pair - centre, axis=1)
        for rank in (0, 1, 2, 3):
            begin = pair[np.argsort(-away)[rank * 3]]
            path = mean_shift_path(pair, tuple(begin), radius)
            axes[2].plot(path[:, 0], path[:, 1], color=INK, lw=1.2)
            axes[2].plot(path[0, 0], path[0, 1], marker="o", color=INK, ms=3.5)
            axes[2].plot(path[-1, 0], path[-1, 1], marker="*", color=GOOD, ms=16, zorder=5)
        axes[2].add_patch(Circle(path[-1], radius, facecolor="none", edgecolor=GOOD, lw=1.3, ls="--"))
    shift_note = (
        "every vote is a starting point; eight are drawn. Move the\n"
        "18 mm window to the average of the votes inside it, and\n"
        "repeat. Starts that stop together are one glass."
    )
    axes[2].text(0, -46, shift_note, ha="center", fontsize=NOTE_SIZE, color=INK, va="top")

    figure.tight_layout()
    save(figure, "08-vote-cloud-and-mean-shift.png")


# --------------------------------------------------------------------------- 6. spread as confidence


def spread_as_confidence() -> None:
    figure, axes = new(14.4, 4.8, columns=3)
    grid = np.linspace(-90, 90, 111)
    levels = np.linspace(0.07, 1.0, 8)

    tight = cloud((0.0, 0.0), 6.0, 1700)
    bimodal = np.vstack([cloud((-22.0, 0.0), 5.5, 800), cloud((22.0, 0.0), 5.5, 780)])
    smeared = RNG.normal(loc=(0.0, 0.0), scale=(18.0, 6.0), size=(340, 2))

    panels = (
        (axes[0], tight, "Tight — RMS 6 mm", GOOD, "One glass.\nAccept it, fit the circle, move on."),
        (
            axes[1],
            bimodal,
            "Two knots — RMS 23 mm",
            GLASS,
            "Two glasses, and it says where both are.\nSplit only if both fits land in range.",
        ),
        (
            axes[2],
            smeared,
            "Smeared — RMS 19 mm",
            WARN,
            "Unsure, and re-clustering will not\ninvent an answer.\nLook again, across the smear.",
        ),
    )
    for axis, points, title, colour, note in panels:
        axis.set_title(title, fontsize=TITLE_SIZE, color=colour)
        frame(axis, (-90, 90), (-82, 56))
        field = density(points, grid, grid, 6.5)
        axis.contourf(grid, grid, field, levels=levels, cmap="Blues", alpha=0.9)
        axis.scatter(points[:, 0], points[:, 1], s=2.5, color=INK, alpha=0.18, lw=0)
        axis.text(0, -56, note, ha="center", fontsize=LABEL_SIZE, color=colour)

    axes[2].annotate(
        "",
        xy=(0, 42),
        xytext=(0, 14),
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 2.0},
    )
    axes[2].text(5, 45, "look across it,\nfrom 380 mm back", fontsize=NOTE_SIZE, color=WARN, va="center")

    figure.tight_layout()
    save(figure, "08-spread-as-confidence.png")


# --------------------------------------------------------------------------- 7. the limit


def too_few_votes() -> None:
    figure, axes = new(13.0, 4.6, columns=2)
    left, right = axes
    visible = np.linspace(0.05, 1.0, 96)

    left.set_title("How many votes a glass gets", fontsize=TITLE_SIZE, color=INK)
    left.plot(visible * 100, 1700 * visible, color=GLASS, lw=2.0)
    left.axhline(300, color=WARN, lw=1.4, ls="--")
    left.text(52, 360, "below about 300 votes: doubtful on count alone", fontsize=NOTE_SIZE, color=WARN)
    left.plot([20], [340], marker="o", color=WARN, ms=8)
    left.annotate(
        "80 per cent hidden:\n340 votes, one crescent",
        xy=(20, 340),
        xytext=(27, 900),
        fontsize=NOTE_SIZE,
        color=WARN,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 1.0},
    )
    left.set_xlabel("how much of the glass the camera can see (%)", fontsize=LABEL_SIZE, color=INK)
    left.set_ylabel("votes", fontsize=LABEL_SIZE, color=INK)
    left.set_xlim(0, 100)
    left.set_ylim(0, 1900)
    left.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for side in ("top", "right"):
        left.spines[side].set_visible(False)

    right.set_title("And how much they disagree", fontsize=TITLE_SIZE, color=INK)
    spread = 6.0 + 25.4 * (1.0 - visible) ** 3
    right.plot(visible * 100, spread, color=GLASS, lw=2.0)
    right.axhline(8.0, color=GOOD, lw=1.4, ls="--")
    right.text(38, 4.4, "spread when the answer is right (held-out)", fontsize=NOTE_SIZE, color=GOOD)
    right.axhline(16.0, color=WARN, lw=1.4, ls="--")
    right.text(44, 17.4, "twice that: ask for another picture", fontsize=NOTE_SIZE, color=WARN)
    right.plot([20], [6.0 + 25.4 * 0.8**3], marker="o", color=WARN, ms=8)
    right.annotate(
        "19 mm, and the peak sits\n9 mm from the truth:\nthe votes agree and are\nwrong the same way",
        xy=(20, 6.0 + 25.4 * 0.8**3),
        xytext=(33, 24),
        fontsize=NOTE_SIZE,
        color=WARN,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 1.0},
    )
    right.set_xlabel("how much of the glass the camera can see (%)", fontsize=LABEL_SIZE, color=INK)
    right.set_ylabel("spread of the votes (mm RMS)", fontsize=LABEL_SIZE, color=INK)
    right.set_xlim(0, 100)
    right.set_ylim(0, 34)
    right.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for side in ("top", "right"):
        right.spines[side].set_visible(False)

    figure.text(
        0.5,
        -0.04,
        "Shapes, not measurements: only the two marked points come from the worked example. "
        "The curves say what to expect, and the thresholds are the ones to calibrate on held-out renders.",
        ha="center",
        fontsize=NOTE_SIZE,
        color=MUTED,
    )
    figure.tight_layout()
    save(figure, "08-too-few-votes.png")


# --------------------------------------------------------------------------- 8. hidden completely
#
# Everything below works from the project's own outlines rather than from drawn
# shapes, because the whole question is which pixels a real projection leaves.


def profile(outline) -> tuple[np.ndarray, np.ndarray]:
    """Heights and radii of one glass's outline, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def rim_radius(outline) -> float:
    return float(profile(outline)[1].max())


def outline_splay(centre, outline, slices: int = 60):
    """The stack of circles a standing glass draws in an overhead picture.

    Same arithmetic as diagram_style.splay_circles, read off the glass's own
    outline rather than from a height and a rim diameter, so a taper the outline
    actually has is the taper that gets drawn.
    """
    z, r = profile(outline)
    heights = np.linspace(0.0, z.max(), slices)
    radii = np.interp(heights, z, r)
    offset = np.asarray(centre, dtype=float)
    out = []
    for zi, ri in zip(heights, radii, strict=True):
        k = SURVEY_H / (SURVEY_H - zi)
        out.append((offset * k, ri * k))
    return out


def top_depth(centre, outline, shape, cx, cy, slices: int = 400) -> np.ndarray:
    """The depth picture of one solid standing glass, straight down from survey height.

    The glass is drawn one horizontal slice at a time, nearest slice first, so a
    nearer slice always wins the pixel. A horizontal slice lies at one depth, so
    every pixel it wins has an exact depth.
    """
    height, width = shape
    depth = np.full((height, width), FAR)
    z, r = profile(outline)
    heights = np.linspace(0.0, z.max(), slices)[::-1]
    radii = np.interp(heights, z, r)
    for zi, ri in zip(heights, radii, strict=True):
        away = SURVEY_H - zi
        disc = np.zeros((height, width), np.uint8)
        cv2.circle(
            disc,
            (int(round(cx + FX * centre[0] / away)), int(round(cy + FX * centre[1] / away))),
            max(1, int(round(FX * ri / away))),
            1,
            -1,
        )
        fresh = (disc > 0) & (depth == FAR)
        depth[fresh] = away
    return depth


def level_depth(centre, outline, shape, cx, horizon, slices: int = 900) -> np.ndarray:
    """The depth picture of one solid standing glass, seen level from the measuring height.

    A horizontal slice seen edge-on is a row of the picture, and the front of that
    slice bulges towards the lens, so its depth across the row is the distance to
    the glass's axis less the part of the slice in front of it.
    """
    height, width = shape
    depth = np.full((height, width), FAR)
    glass_x, glass_y = centre
    z, r = profile(outline)
    heights = np.linspace(0.0, z.max(), slices)
    radii = np.interp(heights, z, r)
    across = (np.arange(width) + 0.5 - cx) * glass_y / FX - glass_x
    for zi, ri in zip(heights, radii, strict=True):
        row = int(round(horizon - FX * (zi - VIEW_HEIGHT) / glass_y))
        if not 0 <= row < height:
            continue
        on = np.abs(across) <= ri
        if not on.any():
            continue
        here = glass_y - np.sqrt(np.maximum(ri**2 - across**2, 0.0))
        nearer = on & (here < depth[row])
        depth[row][nearer] = here[nearer]
    if z.max() < VIEW_HEIGHT:
        # The lens is above the rim, so the mouth of the glass is a visible disc.
        angle = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
        edge_x = glass_x + r[-1] * np.cos(angle)
        edge_y = glass_y + r[-1] * np.sin(angle)
        ring = np.column_stack(
            [cx + FX * edge_x / edge_y, horizon - FX * (z.max() - VIEW_HEIGHT) / edge_y]
        )
        mouth = np.zeros((height, width), np.uint8)
        cv2.fillPoly(mouth, [np.round(ring).astype(np.int32)], 1)
        rows, columns = np.nonzero(mouth)
        below = rows + 0.5 - horizon
        keep = below > 1e-6
        here = FX * (VIEW_HEIGHT - z.max()) / below[keep]
        rows, columns = rows[keep], columns[keep]
        nearer = here < depth[rows, columns]
        depth[rows[nearer], columns[nearer]] = here[nearer]
    return depth


def owner_of(depths: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Which glass each pixel belongs to, and how far away it is. -1 is table."""
    stack = np.stack(depths)
    who = np.argmin(stack, axis=0)
    nearest = stack.min(axis=0)
    who[nearest >= FAR] = -1
    return who, nearest


def on_the_table(who: np.ndarray, depth: np.ndarray, label: int, view: str, cx, cy) -> np.ndarray:
    """Every pixel of one glass, dropped onto the table. Solution 2's own arithmetic.

    A pixel is a direction, and its depth reading says how far along that direction
    the surface is. Take the point that lands on, and throw its height away.
    """
    rows, columns = np.nonzero(who == label)
    away = depth[rows, columns]
    across = (columns + 0.5 - cx) * away / FX
    if view == "top":
        return np.column_stack([across, (rows + 0.5 - cy) * away / FX])
    return np.column_stack([across, away])


def votes_from(points: np.ndarray, centre, spread: float = HELD_OUT_RMS) -> np.ndarray:
    """What the network turns those pixels into.

    Each pixel votes at its own place on the table plus an arrow to its own glass's
    footprint centre. A perfect arrow puts every vote on the centre, so what is left
    is the arrow's error, and the size of that error is the held-out spread this
    document calibrates everything else against.
    """
    return np.asarray(centre, dtype=float) + RNG.normal(0.0, spread / np.sqrt(2.0), size=points.shape)


def settle(votes: np.ndarray, start, radius: float = WINDOW) -> np.ndarray:
    """Slide the window to the average of the votes inside it, until it stops."""
    here = np.asarray(start, dtype=float)
    for _ in range(80):
        inside = votes[np.linalg.norm(votes - here, axis=1) <= radius]
        if len(inside) == 0:
            return here
        moved = inside.mean(axis=0)
        if np.linalg.norm(moved - here) < 0.01:
            return moved
        here = moved
    return here


def stopping_places(votes: np.ndarray, seeds: int = SEEDS, radius: float = WINDOW) -> list[np.ndarray]:
    """The distinct places the windows come to rest, started from votes drawn at random."""
    picked = votes[RNG.choice(len(votes), size=min(seeds, len(votes)), replace=False)]
    found: list[np.ndarray] = []
    for start in picked:
        rest = settle(votes, start, radius)
        if not any(np.linalg.norm(rest - already) < radius for already in found):
            found.append(rest)
    return found


def footprint_width(points: np.ndarray) -> float:
    """How wide the pixels of one glass are once they are back on the table."""
    return 2.0 * cv2.minEnclosingCircle(points.astype(np.float32))[1]


def draw_votes(axis, votes: np.ndarray, colour: str, size: float = 1.6, alpha: float = 0.08) -> None:
    axis.scatter(votes[:, 0], votes[:, 1], s=size, color=colour, alpha=alpha, lw=0)


def mark_peaks(axis, places, radius: float = WINDOW) -> None:
    for place in places:
        axis.add_patch(Circle(tuple(place), radius, facecolor="none", edgecolor=GOOD, lw=1.2, ls="--"))
        axis.plot([place[0]], [place[1]], marker="*", color=GOOD, ms=15, zorder=6)


def paint_owner(axis, who: np.ndarray, colours: dict, extent=None, origin: str = "upper") -> None:
    """Show a rendered picture as itself: one colour per glass, nothing where the table is."""
    painted = np.zeros((*who.shape, 4))
    for label, (colour, alpha) in colours.items():
        painted[who == label] = (*to_rgba(colour)[:3], alpha)
    axis.imshow(painted, extent=extent, origin=origin, interpolation="nearest", zorder=3)


def top_extent(shape, cx, cy) -> tuple[float, float, float, float]:
    """Where a picture taken straight down sits, in millimetres of table from the nadir."""
    height, width = shape
    scale = SURVEY_H / FX
    return ((0 - cx) * scale, (width - cx) * scale, (0 - cy) * scale, (height - cy) * scale)


def hidden_from_above() -> dict:
    """A tall glass's splayed outline swallowing a short one, and what the votes do about it.

    The pair is a legal one. They stand 150 mm apart, which is the closest two
    glasses ever stand, and both sizes are inside the kind's own range.
    """
    shape = (600, 1000)
    cx, cy = 140.0, 300.0
    tall_at = np.array([205.0, 0.0])
    swung = np.radians(12.0)
    places = {
        "inline": tall_at + np.array([MIN_SEP, 0.0]),
        "swung": tall_at + MIN_SEP * np.array([np.cos(swung), np.sin(swung)]),
    }

    tall_depth = top_depth(tall_at, TALL, shape, cx, cy)
    cases = {}
    for name, short_at in places.items():
        short_depth = top_depth(short_at, SHORT, shape, cx, cy)
        who, depth = owner_of([tall_depth, short_depth])
        alone, _ = owner_of([short_depth])
        cases[name] = {
            "at": short_at,
            "who": who,
            "alone": alone,
            "tall_pixels": on_the_table(who, depth, 0, "top", cx, cy),
            "short_pixels": on_the_table(who, depth, 1, "top", cx, cy),
            "whole": int((alone == 0).sum()),
            "covered": splay_covers(outline_splay(tall_at, TALL), outline_splay(short_at, SHORT)),
        }

    figure, axes = new(17.4, 5.6, columns=4)
    extent = top_extent(shape, cx, cy)
    picture_limits = ((150, 545), (-250, 200))
    vote_limits = ((150, 420), (-175, 130))
    white = {"facecolor": PAPER, "edgecolor": "none", "pad": 1.2}

    def picture(axis, case, title, colour) -> None:
        axis.set_title(title, fontsize=TITLE_SIZE, color=colour)
        frame(axis, *picture_limits)
        axis.plot(picture_limits[0], [0, 0], color=MUTED, lw=1.0, ls=":", zorder=2)
        axis.annotate(
            "", xy=(245, 178), xytext=(168, 178),
            arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 1.2},
        )
        axis.text(253, 178, "outwards from the camera", fontsize=NOTE_SIZE, color=MUTED, va="center")
        paint_owner(axis, case["who"], {0: (GLASS, 0.55), 1: (WARN, 0.9)}, extent=extent, origin="lower")
        axis.contour(
            (case["alone"] == 0).astype(float), [0.5], colors=[MUTED], linewidths=1.1, linestyles="--",
            extent=extent, origin="lower", zorder=4,
        )

    def table(axis, title, colour) -> None:
        axis.set_title(title, fontsize=TITLE_SIZE, color=colour)
        frame(axis, *vote_limits)

    # 1. the picture, with the short glass under the tall one's splayed outline.
    first = cases["inline"]
    picture(axes[0], first, "1. the overhead picture", WARN)
    axes[0].annotate(
        f"the short glass stands inside the dashes.\n{len(first['short_pixels'])} of its "
        f"{first['whole']:,} pixels reach the picture.",
        xy=(430, 46), xytext=(430, 108), ha="center", va="bottom",
        fontsize=NOTE_SIZE, color=WARN,
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )
    axes[0].text(
        350, -245,
        f"one patch, {len(first['tall_pixels']):,} pixels, and it back-projects\n"
        f"to a footprint {footprint_width(first['tall_pixels']):.0f} mm across — a legal width.",
        ha="center", va="bottom", fontsize=NOTE_SIZE, color=INK,
    )

    # 2. the votes that picture yields.
    tall_votes = votes_from(first["tall_pixels"], tall_at)
    table(axes[1], "2. every vote in it", WARN)
    draw_votes(axes[1], tall_votes, GLASS)
    mark_peaks(axes[1], stopping_places(tall_votes))
    axes[1].plot([first["at"][0]], [first["at"][1]], marker="x", color=WARN, ms=11, mew=2.0)
    axes[1].text(
        first["at"][0], first["at"][1] + 22, "a glass stands here.\nNo vote mentions it.",
        ha="center", fontsize=NOTE_SIZE, color=WARN, bbox=white,
    )
    axes[1].text(
        285, -170,
        "one peak, where two glasses stand.\nNothing in the vote map is wrong;\n"
        "the second glass is simply not in it.",
        ha="center", va="bottom", fontsize=NOTE_SIZE, color=WARN,
    )

    # 3. the same pair, swung off the line out from the camera.
    second = cases["swung"]
    picture(axes[2], second, "3. the pair swung 12 degrees", GOOD)
    axes[2].annotate(
        f"{len(second['short_pixels'])} pixels of the short glass",
        xy=(455, 78), xytext=(330, 150), ha="center", va="bottom",
        fontsize=NOTE_SIZE, color=GOOD,
        arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 1.0},
    )
    axes[2].text(
        350, -245,
        f"still {MIN_SEP:.0f} mm apart, still the same two glasses.\n"
        f"Splay runs outwards from the camera, so across\n"
        f"that direction the short glass keeps {len(second['short_pixels'])} pixels.",
        ha="center", va="bottom", fontsize=NOTE_SIZE, color=GOOD,
    )

    # 4. what that handful of pixels is worth.
    crescent = votes_from(second["short_pixels"], second["at"])
    both = np.vstack([votes_from(second["tall_pixels"], tall_at), crescent])
    table(axes[3], "4. and what they are worth", GOOD)
    draw_votes(axes[3], both, GLASS)
    axes[3].scatter(crescent[:, 0], crescent[:, 1], s=4, color=WARN, alpha=0.8, lw=0)
    peak = settle(both, crescent.mean(axis=0))
    mark_peaks(axes[3], [settle(both, tall_at), peak])
    axes[3].text(
        285, -170,
        f"{len(crescent)} votes — {100 * len(crescent) / second['whole']:.0f} per cent of the glass —\n"
        f"put the peak {np.linalg.norm(peak - second['at']):.1f} mm from where the\n"
        "glass really stands. Two peaks, two glasses.",
        ha="center", va="bottom", fontsize=NOTE_SIZE, color=GOOD,
    )

    figure.suptitle(
        "Looking straight down: a few pixels of a glass are worth a great deal, and no pixels are "
        "worth nothing.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        f"Panels 1 and 3 are the picture itself, in millimetres of table measured out from the point "
        f"directly below the camera; the dashes are where the short glass would have been on its own.\n"
        f"Panels 2 and 4 are the votes, in millimetres on the table, with the dashed rings marking the "
        f"{WINDOW:.0f} mm mean-shift window where it came to rest. The glass "
        f"{profile(TALL)[0].max():.0f} mm tall has its rim scaled by "
        f"{SURVEY_H / (SURVEY_H - profile(TALL)[0].max()):.2f} and the glass "
        f"{profile(SHORT)[0].max():.0f} mm tall by "
        f"{SURVEY_H / (SURVEY_H - profile(SHORT)[0].max()):.2f}, which is the whole of the effect.",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "08-hidden-from-above.png")
    return cases


def hidden_from_the_side() -> dict:
    """Plain line of sight at the measuring standoff, and what the votes do about it."""
    shape = (240, 320)
    cx, horizon = 160.0, 150.0
    apart = 300.0
    near_at = np.array([0.0, STANDOFF])
    places = {"behind": np.array([0.0, STANDOFF + apart]), "beside": np.array([30.0, STANDOFF + apart])}

    near_depth = level_depth(near_at, TALL, shape, cx, horizon)
    cases = {}
    for name, far_at in places.items():
        far_depth = level_depth(far_at, SHORT, shape, cx, horizon)
        who, depth = owner_of([near_depth, far_depth])
        alone, _ = owner_of([far_depth])
        cases[name] = {
            "at": far_at,
            "who": who,
            "alone": alone,
            "near_pixels": on_the_table(who, depth, 0, "level", cx, horizon),
            "far_pixels": on_the_table(who, depth, 1, "level", cx, horizon),
            "whole": int((alone == 0).sum()),
        }

    figure, axes = new(17.4, 5.6, columns=4)
    crop = ((98, 222), (252, 46))
    vote_limits = ((-150, 150), (290, 780))
    white = {"facecolor": PAPER, "edgecolor": "none", "pad": 1.2}

    def picture(axis, case, title, colour) -> None:
        axis.set_title(title, fontsize=TITLE_SIZE, color=colour)
        bare(axis)
        axis.set_aspect("equal")
        paint_owner(axis, case["who"], {0: (GLASS, 0.55), 1: (WARN, 0.95)})
        axis.contour(
            (case["alone"] == 0).astype(float), [0.5], colors=[MUTED], linewidths=1.1, linestyles="--"
        )
        axis.set_xlim(*crop[0])
        axis.set_ylim(*crop[1])

    def table(axis, title, colour) -> None:
        axis.set_title(title, fontsize=TITLE_SIZE, color=colour)
        frame(axis, *vote_limits)
        axis.annotate(
            "", xy=(-118, 362), xytext=(-118, 300),
            arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 1.2},
        )
        axis.text(-108, 320, "the camera\nlooks this way", fontsize=NOTE_SIZE, color=MUTED, va="center")

    # 1. the picture: the near glass's outline straight over the far one.
    first = cases["behind"]
    picture(axes[0], first, "1. the picture, looking level", WARN)
    axes[0].text(
        160, 64,
        f"dashed: where the far glass is.\n{len(first['far_pixels'])} of its "
        f"{first['whole']:,} pixels survive.",
        ha="center", fontsize=NOTE_SIZE, color=WARN,
    )
    axes[0].text(
        160, 248, f"{apart:.0f} mm between them, and it buys nothing.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )

    # 2. the votes that picture yields.
    near_votes = votes_from(first["near_pixels"], near_at)
    table(axes[1], "2. every vote in it", WARN)
    draw_votes(axes[1], near_votes, GLASS)
    mark_peaks(axes[1], stopping_places(near_votes))
    axes[1].plot([first["at"][0]], [first["at"][1]], marker="x", color=WARN, ms=11, mew=2.0)
    axes[1].text(
        first["at"][0] + 16, first["at"][1], "a glass stands here.\nNo vote mentions it.",
        ha="left", va="center", fontsize=NOTE_SIZE, color=WARN, bbox=white,
    )
    axes[1].text(
        0, 560,
        f"one peak, {len(near_votes):,} votes, and a fitted\nfootprint "
        f"{footprint_width(first['near_pixels']):.0f} mm across.\nNothing about it looks wrong.",
        ha="center", va="center", fontsize=NOTE_SIZE, color=WARN,
    )

    # 3. step the far glass to one side.
    second = cases["beside"]
    picture(axes[2], second, "3. the far glass 30 mm to one side", GOOD)
    axes[2].text(
        160, 64,
        f"{len(second['far_pixels'])} pixels survive, in a strip\ndown the edge of the near outline.",
        ha="center", fontsize=NOTE_SIZE, color=GOOD,
    )
    axes[2].text(
        160, 248, "The near glass did not move. The line of sight did.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )

    # 4. what the strip is worth.
    strip = votes_from(second["far_pixels"], second["at"])
    both = np.vstack([votes_from(second["near_pixels"], near_at), strip])
    table(axes[3], "4. and what they are worth", GOOD)
    draw_votes(axes[3], both, GLASS)
    axes[3].scatter(strip[:, 0], strip[:, 1], s=4, color=WARN, alpha=0.8, lw=0)
    peak = settle(both, strip.mean(axis=0))
    mark_peaks(axes[3], [settle(both, near_at), peak])
    axes[3].text(
        0, 560,
        f"{len(strip)} votes — {100 * len(strip) / second['whole']:.0f} per cent of the glass —\n"
        f"put the peak {np.linalg.norm(peak - second['at']):.1f} mm from where\nit really stands.",
        ha="center", va="center", fontsize=NOTE_SIZE, color=GOOD,
    )

    figure.suptitle(
        "Looking level: no splay is needed. The near outline simply covers the far one.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        f"Panels 1 and 3 are the picture, {shape[1]} by {shape[0]} pixels, cropped; the dashes are where "
        f"the far glass would have been on its own. Panels 2 and 4 are the votes, in millimetres on the "
        f"table, with the lens at the bottom.\nThe near glass stands at the {STANDOFF:.0f} mm measuring "
        f"standoff and the lens {VIEW_HEIGHT:.0f} mm above the table top, so the near glass is "
        f"{FX * 2 * rim_radius(TALL) / STANDOFF:.0f} pixels across in the picture and the far one "
        f"{FX * 2 * rim_radius(SHORT) / (STANDOFF + apart):.0f}.",
        ha="center", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "08-hidden-from-the-side.png")
    return cases


def hidden_case_numbers() -> None:
    """Print every figure the document's hidden-glass section quotes.

    The pictures only draw two arrangements. The section also states what happens
    at other separations, for the other order of the two glasses, and how few votes
    a pile needs, so those are worked out here rather than asserted.
    """
    tall_h, tall_r = profile(TALL)
    short_h, short_r = profile(SHORT)
    print("\n--- the two glasses, drawn from tapered_glass ---")
    for name, z, r in (("tall", tall_h, short_r * 0 + tall_r), ("short", short_h, short_r)):
        print(f"  {name:5s} {z.max():5.1f} mm tall, rim {2 * r.max():5.1f} mm across, "
              f"scaled by {SURVEY_H / (SURVEY_H - z.max()):.2f} at the rim")
    check = splay_circles((0.0, 0.0), (0.0, 120.0), 225.0, 100.0)
    print(f"  a rim exactly 225 mm up is scaled by {check[-1][1] / 50.0:.2f}")

    shape, cx, cy = (600, 1000), 140.0, 300.0
    tall_at = np.array([205.0, 0.0])
    tall_depth = top_depth(tall_at, TALL, shape, cx, cy)
    print(f"\n  the tall glass's outline in the picture spans "
          f"{splay_width(outline_splay(tall_at, TALL)):.0f} mm of table measured from the point below "
          f"the camera")
    print("\n--- looking straight down, the pair 150 mm apart ---")
    for degrees in (0, 8, 12, 16, 20, 30, 90):
        turn = np.radians(degrees)
        short_at = tall_at + MIN_SEP * np.array([np.cos(turn), np.sin(turn)])
        who, depth = owner_of([tall_depth, top_depth(short_at, SHORT, shape, cx, cy)])
        alone, _ = owner_of([top_depth(short_at, SHORT, shape, cx, cy)])
        seen = on_the_table(who, depth, 1, "top", cx, cy)
        whole = int((alone == 0).sum())
        print(f"  {degrees:3d} deg off the line out from the camera: covered="
              f"{splay_covers(outline_splay(tall_at, TALL), outline_splay(short_at, SHORT))!s:5s} "
              f"{len(seen):5d} of {whole:5d} pixels ({100 * len(seen) / whole:5.1f} per cent)")

    shape, cx, horizon = (240, 320), 160.0, 150.0
    near_at = np.array([0.0, STANDOFF])
    near_depth = level_depth(near_at, TALL, shape, cx, horizon)
    print("\n--- looking level, the far glass straight behind the near one ---")
    for apart in (150.0, 300.0, 600.0):
        far_at = np.array([0.0, STANDOFF + apart])
        who, depth = owner_of([near_depth, level_depth(far_at, SHORT, shape, cx, horizon)])
        alone, _ = owner_of([level_depth(far_at, SHORT, shape, cx, horizon)])
        seen = on_the_table(who, depth, 1, "level", cx, horizon)
        print(f"  {apart:5.0f} mm apart: {len(seen):4d} of {int((alone == 0).sum()):5d} pixels")
    swapped_near = level_depth(near_at, SHORT, shape, cx, horizon)
    far_at = np.array([0.0, STANDOFF + 300.0])
    who, depth = owner_of([swapped_near, level_depth(far_at, TALL, shape, cx, horizon)])
    alone, _ = owner_of([level_depth(far_at, TALL, shape, cx, horizon)])
    seen = on_the_table(who, depth, 1, "level", cx, horizon)
    whole = int((alone == 0).sum())
    print(f"  the short glass in front of the tall one instead: {len(seen)} of {whole} pixels survive, "
          f"so {100 * (1 - len(seen) / whole):.0f} per cent of it is covered")
    print(f"  in the picture the near short glass is {FX * 2 * rim_radius(SHORT) / STANDOFF:.0f} pixels "
          f"across and the far tall one {FX * 2 * rim_radius(TALL) / (STANDOFF + 300.0):.0f}")

    print("\n--- which pixels survive, and how far out on the glass they sit ---")
    shape, cx, cy = (600, 1000), 140.0, 300.0
    turn = np.radians(12.0)
    short_at = tall_at + MIN_SEP * np.array([np.cos(turn), np.sin(turn)])
    who, depth = owner_of(
        [top_depth(tall_at, TALL, shape, cx, cy), top_depth(short_at, SHORT, shape, cx, cy)]
    )
    alone, whole_depth = owner_of([top_depth(short_at, SHORT, shape, cx, cy)])
    seen = on_the_table(who, depth, 1, "top", cx, cy)
    every = on_the_table(alone, whole_depth, 0, "top", cx, cy)
    print(f"  from the top, rim radius {rim_radius(SHORT):.1f} mm: the survivors sit "
          f"{np.linalg.norm(seen - short_at, axis=1).mean():.1f} mm out from their own centre, "
          f"against {np.linalg.norm(every - short_at, axis=1).mean():.1f} mm over the whole glass")
    shape, cx, horizon = (240, 320), 160.0, 150.0
    far_at = np.array([30.0, STANDOFF + 300.0])
    who, depth = owner_of([level_depth(near_at, TALL, shape, cx, horizon),
                           level_depth(far_at, SHORT, shape, cx, horizon)])
    alone, whole_depth = owner_of([level_depth(far_at, SHORT, shape, cx, horizon)])
    seen = on_the_table(who, depth, 1, "level", cx, horizon)
    every = on_the_table(alone, whole_depth, 0, "level", cx, horizon)
    print(f"  from the side, rim radius {rim_radius(SHORT):.1f} mm: the survivors sit "
          f"{np.linalg.norm(seen - far_at, axis=1).mean():.1f} mm out from their own centre, "
          f"against {np.linalg.norm(every - far_at, axis=1).mean():.1f} mm over the whole glass")

    print("\n--- how few votes still place a centre ---")
    for count in (1, 2, 5, 10, 20, 50):
        errors = [
            np.linalg.norm(votes_from(np.zeros((count, 2)), (0.0, 0.0)).mean(axis=0))
            for _ in range(4000)
        ]
        print(f"  {count:3d} votes: the peak lands {np.median(errors):4.1f} mm from the centre, "
              f"and within {np.percentile(errors, 95):4.1f} mm nineteen times in twenty")
    print(f"\n--- and whether {SEEDS} windows started at random land in a pile that small ---")
    crowd = 16781
    for count in (20, 50, 100, 300, 850):
        chance = 1.0 - (1.0 - count / (crowd + count)) ** SEEDS
        print(f"  {count:4d} votes among {crowd + count:,}: {100 * count / (crowd + count):5.2f} per cent "
              f"of the picture's votes, found {100 * chance:5.1f} per cent of the time")


if __name__ == "__main__":
    print(f"one pixel covers {MM_PER_PIXEL:.3f} mm at survey height")
    one_region_not_two()
    the_voting_idea()
    image_space_against_table_space()
    the_five_stages()
    vote_cloud_and_mean_shift()
    spread_as_confidence()
    too_few_votes()
    hidden_from_above()
    hidden_from_the_side()
    hidden_case_numbers()
