"""Diagrams for solution 9 — self-supervised from the arm's own movement.

Eight pictures, each carrying its own point: where the training labels come
from, what the parallax signal is, what an embedding is, the arithmetic of how
much slide buys how much separation, the deliberate-motion loop, the case where
the whole idea has nothing to work with, and the two geometries in which a glass
can contribute no pixels at all.

The last two draw silhouettes rather than schematics, and every silhouette in
them is a real projection of one of the project's own glass outlines, taken from
``work_cell.glasses.shapes``, through the cell's own camera. A standing glass is
a circle only in its footprint, which neither of this cell's camera poses ever
sees straight on, and drawing it as one is what the first version of these two
pictures got wrong.

Run from the project root:

    pixi run python images/generators/problem-2/make_09_images.py
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
    SURVEY_H,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
    splay_covers,
    splay_width,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import build, family  # noqa: E402

FX = 277.1            # pixels; the camera's focal length, the same in both axes
SURVEY_SLIDE = 120.0  # mm; the sideways slide between a station's two pictures
FRAME_W, FRAME_H = 320, 240   # the camera's picture, in pixels
VIEW_HEIGHT = 120.0   # mm above the table, the height the level view looks from
STANDOFF = 380.0      # mm from the near glass, the distance the level view stands back
MM_PER_PX = SURVEY_H / FX     # how much table one pixel of a survey picture covers


def shift_px(depth_mm: float, slide_mm: float = SURVEY_SLIDE) -> float:
    """How far a surface at this depth moves across the image when the camera slides."""
    return slide_mm * FX / depth_mm


def box(axis, x, y, w, h, text, *, edge=INK, face="#ffffff", size=LABEL_SIZE, weight="normal"):
    """A rounded box with centred text, given its centre."""
    axis.add_patch(
        FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.12,rounding_size=0.18",
            linewidth=1.3,
            edgecolor=edge,
            facecolor=face,
            zorder=2,
        )
    )
    axis.text(x, y, text, ha="center", va="center", fontsize=size, color=INK, zorder=3, weight=weight)


def arrow(axis, start, end, *, colour=INK, style="-|>", width=1.3, dashed=False):
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=11,
            linewidth=width,
            color=colour,
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=2,
            shrinkB=2,
            zorder=4,
        )
    )


def tumbler(axis, x, base, height, width, *, colour=GLASS, face=None, alpha=0.35, lw=1.6, z=2):
    """A glass seen side-on: a slightly tapered outline."""
    half_top = width / 2
    half_bottom = width / 2 * 0.78
    axis.add_patch(
        Polygon(
            [
                (x - half_bottom, base),
                (x - half_top, base + height),
                (x + half_top, base + height),
                (x + half_bottom, base),
            ],
            closed=True,
            facecolor=colour if face is None else face,
            edgecolor=colour,
            alpha=alpha,
            linewidth=lw,
            zorder=z,
        )
    )


# ---------------------------------------------------------------------------
# The two camera poses, projected properly, from the project's own outlines.
# ---------------------------------------------------------------------------

# The kind's own extremes, straight out of KIND_RANGES["tapered_glass"]: 90 to
# 230 mm tall and 65 to 105 mm across the rim. The taper is the middle of its
# range. These are the two glasses between which the overhead view can hide one
# entirely, and no pair closer together in size can do it.
TALLEST = build("tapered_glass", height=0.230, rim_diameter=0.105, base_fraction=0.45)
SMALLEST = build("tapered_glass", height=0.090, rim_diameter=0.065, base_fraction=0.45)

# Two ordinary glasses of the kind, drawn by the project's own spawner, for the
# level view. The near one is shorter than the far one, which is the point.
_FAMILY = [outline for outline, _ in family("tapered_glass", 12, 1)]
NEAR_GLASS, FAR_GLASS = _FAMILY[2], _FAMILY[6]


def profile_mm(outline) -> tuple[np.ndarray, np.ndarray]:
    """One side of a glass, in millimetres: heights up the glass, and radii."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def rim_size(outline) -> tuple[float, float]:
    """How tall the glass is and how wide across its rim, in millimetres."""
    z, r = profile_mm(outline)
    return float(z.max()), float(2.0 * r.max())


def overhead_circles(nadir, centre, outline, slices: int = 60):
    """The stack of circles a standing glass draws in a picture taken from above.

    A horizontal slice of the glass stays a circle when the camera looks straight
    down, but the slice at height z is nearer the lens than the table is, so it is
    imaged as though it had been scaled about the point directly below the camera
    by SURVEY_H / (SURVEY_H - z). The silhouette is the union of those circles.

    The format is the one diagram_style's splay_covers, splay_patch and
    splay_width take, so those can be used on it unchanged. Everything is in
    millimetres on the table, measured from ``nadir``.
    """
    z, r = profile_mm(outline)
    index = np.linspace(0, len(z) - 1, slices).astype(int)
    offset = np.asarray(centre, dtype=float) - np.asarray(nadir, dtype=float)
    out = []
    for i in index:
        k = SURVEY_H / (SURVEY_H - z[i])
        out.append((offset * k, r[i] * k))
    return out


def escaping_points(big, small, angles: int = 180) -> np.ndarray:
    """The points of ``small``'s outline that ``big``'s silhouette does not cover.

    This is splay_covers opened up: the same test, point by point, returning the
    points that fail rather than one verdict. Those points are where the hidden
    glass's first pixels come from.
    """
    free = []
    for centre, radius in small:
        for angle in np.linspace(0.0, 2.0 * np.pi, angles, endpoint=False):
            point = centre + radius * np.array([np.cos(angle), np.sin(angle)])
            if not any(np.hypot(*(point - cb)) <= rb + 1e-9 for cb, rb in big):
                free.append(point)
    return np.array(free) if free else np.empty((0, 2))


def level_mask(glasses, width: int = FRAME_W, height: int = FRAME_H, horizon=None) -> np.ndarray:
    """What the camera sees from VIEW_HEIGHT, looking level.

    A horizontal circle seen edge-on is a line, so a glass's silhouette is the
    region between the left and right walls of its outline. Each glass is given
    as (sideways offset, depth, outline), all in millimetres, and a nearer glass
    is drawn larger because its depth divides into the focal length.
    """
    mask = np.zeros((height, width), np.uint8)
    middle = width / 2.0
    horizon = height * 0.62 if horizon is None else horizon
    for offset, depth, outline in glasses:
        z, r = profile_mm(outline)
        left, right = [], []
        for zi, ri in zip(z, r, strict=True):
            row = horizon - FX * (zi - VIEW_HEIGHT) / depth
            left.append((middle + FX * (offset - ri) / depth, row))
            right.append((middle + FX * (offset + ri) / depth, row))
        polygon = np.round(np.array(left + right[::-1])).astype(np.int32)
        cv2.fillPoly(mask, [polygon], 255)
    return mask


def paint(axis, region: np.ndarray, colour: str, alpha: float = 1.0) -> None:
    """Show a boolean mask in one colour, leaving the rest of the frame clear."""
    rgba = np.zeros((*region.shape, 4), float)
    rgba[region] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest")


def edge_of(axis, mask: np.ndarray, colour: str = INK, width: float = 1.1) -> None:
    axis.contour(mask.astype(float), [0.5], colors=[colour], linewidths=width)


# ---------------------------------------------------------------------------
# 1. Where the training labels come from, across the three learned solutions.
# ---------------------------------------------------------------------------


def labels_come_from() -> None:
    figure, axis = new(11.0, 5.4)
    bare(axis)
    axis.set_xlim(0, 11)
    axis.set_ylim(0, 5.4)

    axis.text(
        5.5,
        5.15,
        "Three ways to get the right answer written beside each picture",
        ha="center",
        va="center",
        fontsize=TITLE_SIZE,
        color=INK,
        weight="bold",
    )

    lanes = [
        (1.9, "Hand labels", MUTED,
         "A person draws round\nevery glass in every\npicture, by hand",
         "the usual recipe\noutside this project",
         "Costs: a human, thousands of\ntimes over. And with identical\n"
         "glasses overlapping, the human\nis guessing at the boundary too."),
        (5.5, "Simulator labels", GLASS,
         "Gazebo already knows\nwhich mesh each\npixel came from",
         "solutions 7 and 8",
         "Costs: nothing, in simulation.\nBut the supervision exists only\n"
         "inside Gazebo, so the network\ncannot retrain on a real cell."),
        (9.1, "No labels at all", GOOD,
         "The joint encoders say\nhow the camera moved;\ngeometry does the rest",
         "solution 9 — this one",
         "Costs: nothing, and it keeps\ncosting nothing on real\n"
         "hardware, because an arm has\nencoders and a camera there too."),
    ]

    for x, title, colour, middle, who, note in lanes:
        box(axis, x, 4.58, 2.9, 0.48, title, edge=colour, size=LABEL_SIZE + 1, weight="bold")
        axis.text(x, 4.00, who, ha="center", va="center", fontsize=NOTE_SIZE, color=MUTED, style="italic",
                  linespacing=1.5)
        arrow(axis, (x, 3.78), (x, 3.58), colour=colour)
        box(axis, x, 3.20, 3.0, 0.84, middle, edge=colour, size=NOTE_SIZE)
        arrow(axis, (x, 2.64), (x, 2.44), colour=colour)
        box(axis, x, 2.20, 3.0, 0.44, "training examples", edge=colour, face="#f6f8fa", size=NOTE_SIZE)
        axis.text(x, 1.25, note, ha="center", va="center", fontsize=NOTE_SIZE, color=INK, linespacing=1.55)

    axis.text(
        5.5,
        0.28,
        "Only the third column needs nothing that the simulator alone can provide — "
        "which is why it is the one that would transfer to hardware unchanged.",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
    )

    save(figure, "09-where-the-labels-come-from.png")


# ---------------------------------------------------------------------------
# 2. The signal: known camera motion over a still scene gives correspondence.
# ---------------------------------------------------------------------------


def two_views_parallax() -> None:
    figure, axis = new(12.0, 6.0)
    bare(axis)
    axis.set_xlim(0, 12.0)
    axis.set_ylim(0, 6.0)

    axis.text(
        6.0,
        5.78,
        "The scene stands still; only the camera moves, and by a distance the arm chose",
        ha="center",
        va="center",
        fontsize=TITLE_SIZE,
        color=INK,
        weight="bold",
    )

    # --- left: the cell seen from above -----------------------------------
    axis.text(2.45, 5.32, "Seen from above", ha="center", fontsize=LABEL_SIZE, color=INK, weight="bold")

    near_xy, far_xy = (2.45, 3.05), (2.85, 4.45)
    axis.add_patch(Circle(near_xy, 0.30, facecolor=GLASS, edgecolor=GLASS, alpha=0.35, linewidth=1.6))
    axis.add_patch(Circle(far_xy, 0.26, facecolor=WARN, edgecolor=WARN, alpha=0.30, linewidth=1.6))
    axis.text(2.45, 3.05, "A", ha="center", va="center", fontsize=LABEL_SIZE, color=INK, weight="bold")
    axis.text(2.85, 4.45, "B", ha="center", va="center", fontsize=LABEL_SIZE, color=INK, weight="bold")
    axis.text(2.90, 2.78, "380 mm away", ha="left", va="center", fontsize=NOTE_SIZE, color=INK)
    axis.text(3.22, 4.45, "560 mm away", ha="left", va="center", fontsize=NOTE_SIZE, color=INK)

    for x, name in ((1.75, "picture 1"), (3.15, "picture 2")):
        axis.add_patch(
            Polygon(
                [(x - 0.20, 0.86), (x + 0.20, 0.86), (x + 0.20, 1.14), (x - 0.20, 1.14)],
                closed=True,
                facecolor="#ffffff",
                edgecolor=INK,
                linewidth=1.4,
                zorder=3,
            )
        )
        axis.text(x, 0.68, name, ha="center", va="center", fontsize=NOTE_SIZE, color=INK)
        for target, colour in ((near_xy, GLASS), (far_xy, WARN)):
            axis.plot([x, target[0]], [1.16, target[1]], color=colour, linewidth=0.8, alpha=0.65, zorder=1)

    arrow(axis, (1.75, 1.42), (3.15, 1.42), colour=GOOD, style="<|-|>")
    axis.text(2.45, 1.62, "slide 120 mm", ha="center", va="center", fontsize=NOTE_SIZE, color=GOOD,
              weight="bold")
    axis.text(
        2.45,
        0.28,
        "the slide is commanded, not estimated —\nit is read straight off the joint encoders",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.5,
    )

    axis.plot([4.75, 4.75], [0.40, 5.45], color=MUTED, linewidth=0.9, alpha=0.5)

    # --- right: the two pictures, with the shifts drawn to the frame's scale
    axis.text(8.35, 5.32, "What the two pictures hold", ha="center", fontsize=LABEL_SIZE, color=INK,
              weight="bold")

    frame_width = 2.40          # units across, standing for the picture's 320 pixels
    per_pixel = frame_width / 320.0
    a_at, b_at = 1.62, 1.95     # where A and B sit in picture 1, in frame units

    for index, (left, title) in enumerate(((5.25, "picture 1"), (8.15, "picture 2"))):
        axis.add_patch(
            Polygon(
                [(left, 3.10), (left + frame_width, 3.10), (left + frame_width, 4.70), (left, 4.70)],
                closed=True,
                facecolor="#f6f8fa",
                edgecolor=MUTED,
                linewidth=1.2,
                zorder=1,
            )
        )
        axis.text(left + frame_width / 2, 2.44, title, ha="center", va="center", fontsize=NOTE_SIZE,
                  color=INK)

        moved_a = 0.0 if index == 0 else -shift_px(380.0) * per_pixel
        moved_b = 0.0 if index == 0 else -shift_px(560.0) * per_pixel
        x_a, x_b = left + a_at + moved_a, left + b_at + moved_b
        tumbler(axis, x_a, 3.24, 1.02, 0.46, colour=GLASS)
        tumbler(axis, x_b, 3.52, 0.78, 0.38, colour=WARN, alpha=0.30)
        axis.text(x_a, 3.14, "A", ha="center", va="center", fontsize=NOTE_SIZE, color=INK, weight="bold")
        axis.text(x_b, 4.44, "B", ha="center", va="center", fontsize=NOTE_SIZE, color=INK, weight="bold")

        gap = (b_at - a_at + moved_b - moved_a) / per_pixel
        arrow(axis, (x_a, 2.92), (x_b, 2.92), colour=INK, style="<|-|>", width=1.1)
        axis.text((x_a + x_b) / 2, 2.70, f"{gap:.0f} px apart", ha="center", va="center",
                  fontsize=NOTE_SIZE, color=INK)

    second = 8.15
    arrow(axis, (second + a_at, 5.06), (second + a_at - shift_px(380.0) * per_pixel, 5.06),
          colour=GLASS, width=1.6)
    axis.text(second + a_at + 0.12, 5.06, "A moves 87 px", ha="left", va="center", fontsize=NOTE_SIZE,
              color=GLASS, weight="bold")
    arrow(axis, (second + b_at, 4.84), (second + b_at - shift_px(560.0) * per_pixel, 4.84),
          colour=WARN, width=1.6)
    axis.text(second + b_at + 0.12, 4.84, "B moves 59 px", ha="left", va="center", fontsize=NOTE_SIZE,
              color=WARN, weight="bold")

    axis.text(
        8.35,
        1.55,
        "Every pixel of A moves by the same 87 px; every pixel of B by the same 59 px.\n"
        "So the gap between them grows by 15 px — and moving together is the only thing that\n"
        "marks them as two objects, because their colour is identical.\n"
        "That agreement is the label, and neither a human nor the simulator wrote it.",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.6,
    )

    save(figure, "09-two-views-parallax.png")


# ---------------------------------------------------------------------------
# 3. What an embedding is, and what contrastive training does to it.
# ---------------------------------------------------------------------------


def embedding_space() -> None:
    figure, axis = new(11.0, 4.6)
    bare(axis)
    axis.set_xlim(0, 11)
    axis.set_ylim(0.60, 5.0)

    axis.text(
        5.5,
        4.75,
        "An embedding: every pixel becomes a point, and distance between points means "
        '"same object or not"',
        ha="center",
        va="center",
        fontsize=TITLE_SIZE,
        color=INK,
        weight="bold",
    )

    # --- left: the picture, with sample pixels marked ----------------------
    axis.add_patch(
        Polygon(
            [(0.55, 1.35), (3.85, 1.35), (3.85, 3.95), (0.55, 3.95)],
            closed=True,
            facecolor="#f6f8fa",
            edgecolor=MUTED,
            linewidth=1.2,
        )
    )
    axis.text(2.20, 4.15, "one picture, 320 x 240", ha="center", fontsize=NOTE_SIZE, color=INK)
    tumbler(axis, 1.75, 1.50, 1.70, 0.90, colour=GLASS)
    tumbler(axis, 2.65, 1.95, 1.35, 0.72, colour=WARN, alpha=0.30)

    marks = [
        (1.55, 2.00, "1", GLASS),
        (1.90, 2.90, "2", GLASS),
        (2.55, 2.40, "3", WARN),
        (2.80, 3.05, "4", WARN),
    ]
    for x, y, name, colour in marks:
        axis.add_patch(Circle((x, y), 0.14, facecolor="#ffffff", edgecolor=colour, linewidth=1.6, zorder=5))
        axis.text(x, y, name, ha="center", va="center", fontsize=NOTE_SIZE, color=INK, zorder=6,
                  weight="bold")

    axis.text(
        2.20,
        0.98,
        "pixels 1 and 2 shift by 87 px;\npixels 3 and 4 shift by 59 px",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.5,
    )

    arrow(axis, (4.05, 2.65), (5.05, 2.65), colour=INK, width=1.6)
    axis.text(4.55, 2.90, "network", ha="center", va="center", fontsize=NOTE_SIZE, color=INK)
    axis.text(4.55, 2.40, "16 numbers\nper pixel", ha="center", va="center", fontsize=NOTE_SIZE,
              color=MUTED, linespacing=1.5)

    # --- right: the embedding space ---------------------------------------
    axis.add_patch(
        Polygon(
            [(5.30, 1.35), (8.55, 1.35), (8.55, 3.95), (5.30, 3.95)],
            closed=True,
            facecolor="#ffffff",
            edgecolor=MUTED,
            linewidth=1.2,
        )
    )
    axis.text(6.92, 4.15, "embedding space (2 of the 16 shown)", ha="center", fontsize=NOTE_SIZE, color=INK)

    rng = np.random.default_rng(9)
    cluster_a = np.array([6.15, 3.32]) + rng.normal(0, 0.15, (22, 2))
    cluster_b = np.array([7.85, 2.02]) + rng.normal(0, 0.15, (22, 2))
    axis.scatter(cluster_a[:, 0], cluster_a[:, 1], s=16, color=GLASS, alpha=0.55, zorder=3)
    axis.scatter(cluster_b[:, 0], cluster_b[:, 1], s=16, color=WARN, alpha=0.55, zorder=3)

    for x, y, name, colour in ((6.00, 3.50, "1", GLASS), (6.30, 3.16, "2", GLASS),
                               (7.70, 2.20, "3", WARN), (8.00, 1.86, "4", WARN)):
        axis.add_patch(Circle((x, y), 0.13, facecolor="#ffffff", edgecolor=colour, linewidth=1.6, zorder=5))
        axis.text(x, y, name, ha="center", va="center", fontsize=NOTE_SIZE, color=INK, zorder=6,
                  weight="bold")

    arrow(axis, (6.00, 3.50), (6.30, 3.16), colour=GOOD, style="<|-|>", width=1.4)
    axis.text(5.42, 3.78, "pull together", ha="left", va="center", fontsize=NOTE_SIZE, color=GOOD)
    axis.plot([5.78, 6.02], [3.72, 3.60], color=GOOD, linewidth=0.8)
    arrow(axis, (6.55, 2.95), (7.45, 2.45), colour=WARN, style="<|-|>", width=1.4, dashed=True)
    axis.text(7.20, 3.02, "push apart", ha="center", va="center", fontsize=NOTE_SIZE, color=WARN)

    axis.text(
        6.92,
        1.05,
        "The loss is low only when a pixel's geometric\npartner is nearer to it than the distractors are.",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.5,
    )

    # --- right margin: the honest limit -----------------------------------
    box(
        axis,
        9.95,
        2.65,
        1.95,
        1.70,
        "Nothing here\nnames a glass.\n\nThe vectors carry\nonly same or\n"
        "different —\naffinity, not a\ncount.",
        edge=MUTED,
        face="#f6f8fa",
        size=NOTE_SIZE,
    )

    save(figure, "09-embedding-space.png")


# ---------------------------------------------------------------------------
# 4. The arithmetic: how much slide buys how much separation.
# ---------------------------------------------------------------------------


def parallax_arithmetic() -> None:
    figure, axes = new(11.4, 4.6, columns=2)
    left, right = axes

    # --- left: apparent shift against depth, for the 120 mm slide ---------
    depth = np.linspace(200, 800, 400)
    left.plot(depth, shift_px(depth), color=GLASS, linewidth=2.0)
    left.set_xlim(200, 800)
    left.set_ylim(0, 175)
    left.set_xlabel("depth of the surface, mm", fontsize=LABEL_SIZE, color=INK)
    left.set_ylabel("apparent shift, pixels", fontsize=LABEL_SIZE, color=INK)
    left.set_title("Slide the camera 120 mm: how far a surface moves", fontsize=TITLE_SIZE, color=INK)
    left.grid(True, color=MUTED, alpha=0.25, linewidth=0.7)
    left.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for side in ("top", "right"):
        left.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        left.spines[side].set_color(MUTED)

    easy = [(500.0, GLASS, (228, 38)), (650.0, GOOD, (626, 92))]
    for z, colour, where in easy:
        left.plot([z], [shift_px(z)], "o", color=colour, markersize=6, zorder=5)
        left.annotate(
            f"{z:.0f} mm  ->  {shift_px(z):.1f} px",
            xy=(z, shift_px(z)),
            xytext=where,
            fontsize=NOTE_SIZE,
            color=colour,
            arrowprops={"arrowstyle": "-", "color": colour, "linewidth": 0.9},
        )
    left.annotate(
        "",
        xy=(462, shift_px(500.0)),
        xytext=(462, shift_px(650.0)),
        arrowprops={"arrowstyle": "<|-|>", "color": INK, "linewidth": 1.2},
    )
    left.text(452, 59, "15.3 px\napart", ha="right", va="center", fontsize=NOTE_SIZE, color=INK,
              linespacing=1.4)

    left.plot([520.0], [shift_px(520.0)], "o", color=WARN, markersize=6, zorder=5)
    left.annotate(
        "520 mm -> 63.9 px:\nonly 2.6 px from the 500 mm glass.\nThis is the hard case.",
        xy=(520, shift_px(520.0)),
        xytext=(560, 118),
        fontsize=NOTE_SIZE,
        color=WARN,
        linespacing=1.5,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.0},
    )
    left.text(
        740,
        14,
        "shift = slide x 277.1 / depth",
        ha="right",
        va="center",
        fontsize=NOTE_SIZE,
        color=MUTED,
    )

    # --- right: separation against slide, for the 500/520 mm pair ---------
    slide = np.linspace(0, 500, 400)
    separation = slide * FX * (1 / 500.0 - 1 / 520.0)
    right.plot(slide, separation, color=INK, linewidth=2.0)
    right.set_xlim(0, 500)
    right.set_ylim(0, 12)
    right.set_xlabel("how far the arm slides the camera, mm", fontsize=LABEL_SIZE, color=INK)
    right.set_ylabel("separation between the two glasses, pixels", fontsize=LABEL_SIZE, color=INK)
    right.set_title("Two glasses 20 mm apart in depth: the slide is a dial", fontsize=TITLE_SIZE, color=INK)
    right.grid(True, color=MUTED, alpha=0.25, linewidth=0.7)
    right.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for side in ("top", "right"):
        right.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        right.spines[side].set_color(MUTED)

    right.axhspan(0, 3.0, color=WARN, alpha=0.10)
    right.text(492, 0.40, "too close to call", ha="right", va="center", fontsize=NOTE_SIZE, color=WARN)

    for mm, colour in ((120.0, WARN), (141.0, MUTED), (375.0, GOOD)):
        px = mm * FX * (1 / 500.0 - 1 / 520.0)
        right.plot([mm, mm], [0, px], color=colour, linewidth=1.0, linestyle=(0, (3, 3)))
        right.plot([mm], [px], "o", color=colour, markersize=6, zorder=5)
    right.text(158, 2.15, "120 mm — the survey's slide: 2.6 px", ha="left", va="center",
               fontsize=NOTE_SIZE, color=WARN)
    right.text(158, 1.30, "141 mm — the least that gives 3 px", ha="left", va="center",
               fontsize=NOTE_SIZE, color=INK)
    right.annotate(
        "375 mm -> 8 px",
        xy=(375, 8.0),
        xytext=(250, 9.8),
        fontsize=NOTE_SIZE,
        color=GOOD,
        arrowprops={"arrowstyle": "-|>", "color": GOOD, "linewidth": 1.0},
    )
    right.text(
        20,
        11.0,
        "0.0213 pixels per millimetre of slide — a straight line,\n"
        "so the arm can price any separation it wants.",
        ha="left",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.5,
    )

    figure.tight_layout()
    save(figure, "09-depth-against-shift.png")


# ---------------------------------------------------------------------------
# 5. The loop: a measurement chosen to settle one named doubt.
# ---------------------------------------------------------------------------


def deliberate_motion_loop() -> None:
    figure, axis = new(11.9, 5.3)
    bare(axis)
    axis.set_xlim(0, 11.9)
    axis.set_ylim(0, 5.3)

    axis.text(
        5.95,
        5.08,
        "When the embedding is unsure, the arm does not think harder — it moves further",
        ha="center",
        va="center",
        fontsize=TITLE_SIZE,
        color=INK,
        weight="bold",
    )

    stations = [
        (1.55, "Station's own pair", "slide 120 mm", "separation 2.6 px", WARN,
         "below the matcher's\nprecision: the two\npixel populations\noverlap"),
        (4.40, "Name the doubt", "this pair, 20 mm\napart in depth", "need 8 px", INK,
         "8 px / 0.0213 px per mm\n= 375 mm of slide"),
        (7.25, "Slide 375 mm", "one arm move,\na few seconds", "separation 8.0 px", GOOD,
         "the two populations\nno longer overlap"),
        (10.10, "Settled, or handed on", "two regions, each\nchecked against the\nkind's 45-105 mm width",
         "or: report the pair", GOOD, "past a few hundred mm,\nthe glasses leave the\nframe — that is\n"
         "solution 3's next station"),
    ]

    for x, title, middle, verdict, colour, note in stations:
        box(axis, x, 4.40, 2.30, 0.44, title, edge=colour, size=LABEL_SIZE, weight="bold")
        box(axis, x, 3.35, 2.30, 0.70, middle, edge=MUTED, face="#f6f8fa", size=NOTE_SIZE)
        axis.text(x, 2.68, verdict, ha="center", va="center", fontsize=NOTE_SIZE, color=colour, weight="bold")
        axis.text(x, 2.05, note, ha="center", va="center", fontsize=NOTE_SIZE, color=INK, linespacing=1.5)

    for start, end in ((1.55, 4.40), (4.40, 7.25), (7.25, 10.10)):
        arrow(axis, (start + 1.29, 3.35), (end - 1.29, 3.35), colour=INK)

    arrow(axis, (10.10, 1.30), (1.55, 1.30), colour=WARN, dashed=True)
    axis.text(
        5.85,
        1.05,
        "still unsure, and budget left: slide further again",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=WARN,
    )

    axis.text(
        5.95,
        0.42,
        "The arm is not taking another picture in the hope that it helps. It has worked out how far it must "
        "move\nfor this particular pair to separate by a chosen number of pixels, and it moves exactly "
        "that far.",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.6,
    )

    save(figure, "09-deliberate-motion-loop.png")


# ---------------------------------------------------------------------------
# 6. The limit: equal depth, identical kind, and no object motion.
# ---------------------------------------------------------------------------


def the_limit() -> None:
    figure, axis = new(11.0, 5.0)
    bare(axis)
    axis.set_xlim(0, 11)
    axis.set_ylim(0, 5.0)

    axis.text(
        5.5,
        4.75,
        "Where the signal runs out: two identical glasses the same distance away",
        ha="center",
        va="center",
        fontsize=TITLE_SIZE,
        color=INK,
        weight="bold",
    )

    # --- left panel: equal depth -----------------------------------------
    axis.text(2.60, 4.32, "Side by side, both 500 mm away", ha="center", fontsize=LABEL_SIZE,
              color=INK, weight="bold")
    axis.plot([0.60, 4.55], [3.82, 3.82], color=MUTED, linewidth=1.0, linestyle=(0, (4, 3)))
    axis.text(4.62, 3.82, "500 mm", ha="left", va="center", fontsize=NOTE_SIZE, color=MUTED)
    glasses = ((2.15, 3.82), (3.15, 3.82))
    for centre in glasses:
        axis.add_patch(Circle(centre, 0.28, facecolor=GLASS, edgecolor=GLASS, alpha=0.35, linewidth=1.6))

    for x in (1.30, 4.00):
        axis.add_patch(
            Polygon(
                [(x - 0.20, 2.35), (x + 0.20, 2.35), (x + 0.20, 2.63), (x - 0.20, 2.63)],
                closed=True,
                facecolor="#ffffff",
                edgecolor=INK,
                linewidth=1.3,
                zorder=3,
            )
        )
        for centre in glasses:
            axis.plot([x, centre[0]], [2.65, centre[1]], color=GLASS, linewidth=0.8, alpha=0.5, zorder=1)

    arrow(axis, (1.30, 2.10), (4.00, 2.10), colour=MUTED, style="<|-|>")
    axis.text(2.65, 1.92, "slide as far as you like", ha="center", va="center", fontsize=NOTE_SIZE,
              color=MUTED)

    box(
        axis,
        2.60,
        1.05,
        4.30,
        1.10,
        "Both shift by 66.5 px, whatever the slide.\n"
        "Separation is 0 px at every baseline, because\n"
        "0.0213 px per mm came from the depth gap —\nand here the depth gap is zero.",
        edge=WARN,
        face="#fdf2ef",
        size=NOTE_SIZE,
    )
    axis.text(
        2.60,
        0.16,
        "Appearance cannot break the tie: the glasses are one kind.",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=WARN,
    )

    # --- right panel: affinity is not a count ----------------------------
    axis.text(8.40, 4.32, "And affinity is still not a count", ha="center", fontsize=LABEL_SIZE,
              color=INK, weight="bold")

    centres = [(7.25, 3.55), (8.05, 3.85), (7.60, 2.95), (9.15, 3.35), (9.50, 2.85)]
    for index, (x, y) in enumerate(centres):
        colour = GLASS if index < 3 else WARN
        axis.add_patch(Circle((x, y), 0.17, facecolor=colour, edgecolor=colour, alpha=0.5, linewidth=1.4,
                              zorder=3))
    for a, b in ((0, 1), (0, 2), (1, 2), (3, 4)):
        axis.plot(
            [centres[a][0], centres[b][0]],
            [centres[a][1], centres[b][1]],
            color=GOOD,
            linewidth=1.5,
            alpha=0.85,
            zorder=2,
        )
    axis.plot([centres[2][0], centres[3][0]], [centres[2][1], centres[3][1]], color=MUTED,
              linewidth=1.0, linestyle=(0, (3, 3)), zorder=2)
    axis.text(8.40, 2.42, "green: alike.  grey: unalike.  Pixel by pixel, and nothing more.",
              ha="center", va="center", fontsize=NOTE_SIZE, color=INK)
    axis.text(8.40, 2.10, "No line in the picture says how many groups there are.", ha="center",
              va="center", fontsize=NOTE_SIZE, color=MUTED)

    box(
        axis,
        8.40,
        1.05,
        4.30,
        1.10,
        "The network never says four glasses.\n"
        "Something downstream must still cluster the\nvectors and choose how many groups there are —\n"
        "and choosing too few is the merge again.",
        edge=MUTED,
        face="#f6f8fa",
        size=NOTE_SIZE,
    )
    axis.text(
        8.40,
        0.16,
        "That job goes to solution 2's circle fit, which checks the width.",
        ha="center",
        va="center",
        fontsize=NOTE_SIZE,
        color=INK,
    )

    axis.plot([5.90, 5.90], [0.05, 4.45], color=MUTED, linewidth=0.9, alpha=0.6)

    save(figure, "09-the-limit.png")


# ---------------------------------------------------------------------------
# 7. Completely hidden, looking straight down: splay, and where it happens.
# ---------------------------------------------------------------------------

OVERHEAD_TALL_OUT = 200.0     # mm from the point below the camera to the tall glass
OVERHEAD_GAP = 150.0          # mm between the two centres: the cell's own smallest


def hidden_from_above() -> None:
    """Four overhead pictures as the camera slides outward along the pair's radius.

    Everything drawn is measured, not placed by eye. The silhouettes are real
    projections of the kind's tallest and shortest glasses, the verdict on each
    panel comes from splay_covers, and the slide written on the third panel is
    the first half-millimetre step at which that verdict changes.
    """
    direction = np.array([1.0, 0.0])  # outward along the radius through the pair

    def pair(slide: float):
        nadir = direction * slide
        return (
            overhead_circles(nadir, (OVERHEAD_TALL_OUT, 0.0), TALLEST),
            overhead_circles(nadir, (OVERHEAD_TALL_OUT + OVERHEAD_GAP, 0.0), SMALLEST),
        )

    reveal = None
    for millimetres in np.arange(0.0, 300.5, 0.5):
        if not splay_covers(*pair(float(millimetres))):
            reveal = float(millimetres)
            break
    slides = (0.0, 24.0, reveal, 90.0)

    tall_h, tall_w = rim_size(TALLEST)
    short_h, short_w = rim_size(SMALLEST)
    hidden = pair(0.0)[1]
    out_px = max(c[0] + r for c, r in hidden) / MM_PER_PX
    in_px = min(c[0] - r for c, r in hidden) / MM_PER_PX
    corner_px = np.hypot(FRAME_W / 2, FRAME_H / 2)
    patch_mm = splay_width(pair(0.0)[0])

    figure, axes = new(15.0, 4.6, columns=4)
    half_w, half_h = FRAME_W / 2 * MM_PER_PX, FRAME_H / 2 * MM_PER_PX

    for index, (axis, slide) in enumerate(zip(axes, slides, strict=True)):
        bare(axis)
        axis.set_aspect("equal")
        axis.set_xlim(-330, 760)
        axis.set_ylim(-260, 260)

        big, small = pair(slide)
        nadir = direction * slide

        axis.add_patch(
            Rectangle(
                (nadir[0] - half_w, nadir[1] - half_h),
                2 * half_w,
                2 * half_h,
                facecolor=to_rgba(MUTED, 0.07),
                edgecolor=MUTED,
                linewidth=1.2,
                linestyle=(0, (5, 3)),
                zorder=1,
            )
        )
        axis.plot([nadir[0]], [nadir[1]], marker="x", color=WARN, markersize=7, zorder=8)

        for centre, radius in big:
            axis.add_patch(Circle(tuple(centre), radius, facecolor=GLASS, alpha=0.14,
                                  edgecolor="none", zorder=3))
        for centre, radius in small:
            axis.add_patch(Circle(tuple(centre), radius, facecolor="none",
                                  edgecolor=WARN, linewidth=0.5, alpha=0.55, zorder=4))

        free = escaping_points(big, small)
        if len(free):
            axis.scatter(free[:, 0], free[:, 1], s=22, color=GOOD, zorder=6, linewidths=0)

        verdict = (f"{len(free)} points of the short glass's\noutline are clear of the tall one's"
                   if len(free) else
                   "the short glass is inside the tall\none's outline: it contributes no pixels")
        heading = "where the camera already is" if index == 0 else f"slide {slide:.1f} mm"
        axis.set_title(f"{heading}\n{verdict}", fontsize=NOTE_SIZE, pad=7, linespacing=1.6,
                       color=GOOD if len(free) else WARN)

    axes[2].annotate(
        "the first pixels",
        xy=tuple(escaping_points(*pair(slides[2]))[0]), xytext=(700, -170),
        fontsize=NOTE_SIZE, color=GOOD, ha="right",
        arrowprops={"arrowstyle": "-|>", "color": GOOD, "linewidth": 1.0},
    )

    figure.suptitle(
        "Looking straight down, a glass can be hidden — but only out where the picture "
        "no longer reaches",
        fontsize=TITLE_SIZE, color=INK, y=0.99,
    )
    figure.tight_layout(rect=(0, 0.30, 1, 0.92))
    figure.text(
        0.5, 0.275,
        f"Blue is the tallest glass the kind allows, {tall_h:.0f} mm tall and {tall_w:.0f} mm across. "
        f"The red outline is the shortest, {short_h:.0f} mm tall and {short_w:.0f} mm across, standing "
        f"{OVERHEAD_GAP:.0f} mm further out along the same radius. The cross is the point directly "
        f"below the camera, and the dashed rectangle is how much table the 320 x 240 picture reaches.",
        fontsize=NOTE_SIZE, color=INK, ha="center", va="top", linespacing=1.8,
    )
    figure.text(
        0.5, 0.185,
        f"A slice at height z is imaged as though scaled about the point below the camera by "
        f"450 / (450 - z), so a 225 mm rim lands at twice its real offset and twice its real radius. "
        f"That splay is what lets the tall glass reach over the short one, and the\npatch that comes "
        f"back is {patch_mm:.0f} mm across — exactly the patch the tall glass would make standing "
        f"alone. Sliding the camera moves the point the splay radiates from, so {slides[2]:.1f} mm of "
        f"slide is enough to end it.",
        fontsize=NOTE_SIZE, color=INK, ha="center", va="top", linespacing=1.8,
    )
    figure.text(
        0.5, 0.075,
        f"But read the dashed rectangle. The hidden glass sits {in_px:.0f} to {out_px:.0f} pixels from "
        f"the centre of a picture whose own corner is only {corner_px:.0f} pixels out, so it is off "
        f"the edge of the frame in every panel. Across the kind's whole range the closest a\n"
        f"completely covered glass can ever sit to the centre is 258 pixels. This kind of hiding never "
        f"happens to a glass that was in the picture to begin with, which makes it a survey-coverage "
        f"problem rather than a parallax one.",
        fontsize=NOTE_SIZE, color=WARN, ha="center", va="top", linespacing=1.8,
    )
    save(figure, "09-hidden-from-above.png")


# ---------------------------------------------------------------------------
# 8. Completely hidden, looking level: line of sight, and the slide that ends it.
# ---------------------------------------------------------------------------

BEHIND = 300.0        # mm further back the far glass stands, along the line of sight


def hidden_from_the_side() -> None:
    """Four real level-view frames along one slide, and the count that marks it.

    The far glass's free pixels are counted in the frame itself: the pixels its
    own silhouette lights that the near glass's silhouette does not. The slides
    written on the panels are the first half-millimetre steps at which that count
    reaches one pixel, fifty pixels and half the glass.
    """
    near_h, near_w = rim_size(NEAR_GLASS)
    far_h, far_w = rim_size(FAR_GLASS)

    def frames(slide: float):
        near = level_mask([(-slide, STANDOFF, NEAR_GLASS)])
        far = level_mask([(-slide, STANDOFF + BEHIND, FAR_GLASS)])
        return near > 0, far > 0

    total = int(frames(0.0)[1].sum())
    counts = []
    for millimetres in np.arange(0.0, 160.5, 0.5):
        near, far = frames(float(millimetres))
        counts.append((float(millimetres), int((far & ~near).sum())))

    def first(threshold: int) -> float:
        return next(mm for mm, free in counts if free >= threshold)

    at_one, at_fifty, at_half = first(1), first(50), first(total // 2)

    shown = [0.0, 24.0, at_one, SURVEY_SLIDE]
    figure, axes = new(15.4, 4.4, columns=5)

    for axis, slide in zip(axes[:4], shown, strict=True):
        bare(axis)
        near, far = frames(slide)
        free = far & ~near
        axis.imshow(np.ones((FRAME_H, FRAME_W)), cmap="gray", vmin=0, vmax=1)
        paint(axis, far & ~free, MUTED, 0.16)
        paint(axis, near, GLASS, 0.40)
        paint(axis, free, GOOD, 0.95)
        axis.contour(far.astype(float), [0.5], colors=[MUTED], linewidths=1.0,
                     linestyles=[(0, (4, 3))])
        edge_of(axis, near.astype(np.uint8) * 255, INK, 1.1)
        axis.set_xlim(0, FRAME_W)
        axis.set_ylim(FRAME_H, 0)
        count = int(free.sum())
        if 0 < count < 200:
            rows, columns = np.nonzero(free)
            axis.add_patch(Circle((columns.mean(), rows.mean()), 22, facecolor="none",
                                  edgecolor=GOOD, linewidth=1.3, zorder=7))
        axis.set_title(
            f"slide {slide:.0f} mm\n{count} of the far glass's {total} pixels free",
            fontsize=NOTE_SIZE, color=GOOD if count else WARN, pad=6, linespacing=1.6,
        )

    axes[2].text(10, 26, "the first pixels appear low down,\nat the base, where the near\n"
                 "glass tapers in",
                 fontsize=NOTE_SIZE, color=GOOD, va="top", linespacing=1.6)

    count_axis = axes[4]
    millimetres = np.array([mm for mm, _ in counts])
    free_pixels = np.array([free for _, free in counts])
    count_axis.plot(millimetres, free_pixels, color=GOOD, linewidth=2.0)
    count_axis.set_xlim(0, 160)
    count_axis.set_ylim(0, total * 1.12)
    count_axis.set_xlabel("how far the camera has slid, mm", fontsize=NOTE_SIZE, color=INK)
    count_axis.set_ylabel("pixels of the far glass in the picture", fontsize=NOTE_SIZE, color=INK)
    count_axis.set_title("When the hidden glass arrives", fontsize=LABEL_SIZE, color=INK, pad=8)
    count_axis.grid(True, color=MUTED, alpha=0.25, linewidth=0.7)
    count_axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=INK)
    for side in ("top", "right"):
        count_axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        count_axis.spines[side].set_color(MUTED)
    count_axis.axvline(SURVEY_SLIDE, color=INK, linewidth=1.0, linestyle=(0, (4, 3)))
    count_axis.text(SURVEY_SLIDE + 4, total * 0.46, "the slide the\nstation already\nmakes",
                    fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom", linespacing=1.5)
    for millimetre, colour in ((at_one, WARN), (at_fifty, GOOD), (at_half, GOOD)):
        height = np.interp(millimetre, millimetres, free_pixels)
        count_axis.plot([millimetre], [height], "o", color=colour, markersize=6, zorder=5)
    count_axis.annotate(
        f"{at_one:.0f} mm:\nthe first pixel",
        xy=(at_one, 0), xytext=(4, total * 0.30), fontsize=NOTE_SIZE, color=WARN,
        linespacing=1.5, arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.0},
    )
    count_axis.annotate(
        f"{at_fifty:.0f} mm: fifty pixels",
        xy=(at_fifty, np.interp(at_fifty, millimetres, free_pixels)),
        xytext=(4, total * 0.55), fontsize=NOTE_SIZE, color=GOOD,
        arrowprops={"arrowstyle": "-|>", "color": GOOD, "linewidth": 1.0},
    )
    count_axis.annotate(
        f"{at_half:.0f} mm:\nhalf the glass",
        xy=(at_half, np.interp(at_half, millimetres, free_pixels)),
        xytext=(78, total * 0.13), fontsize=NOTE_SIZE, color=GOOD, linespacing=1.5,
        arrowprops={"arrowstyle": "-|>", "color": GOOD, "linewidth": 1.0},
    )

    figure.suptitle(
        "Looking level, the far glass is hidden by line of sight alone — and the slide the method "
        "already makes ends it",
        fontsize=TITLE_SIZE, color=INK, y=1.00,
    )
    figure.tight_layout(rect=(0, 0.20, 1, 0.92))
    figure.text(
        0.5, 0.175,
        f"Blue is the near glass, {near_h:.0f} mm tall and {near_w:.0f} mm across the rim, standing "
        f"{STANDOFF:.0f} mm from the camera. The dashed grey outline is the far glass, {far_h:.0f} mm "
        f"tall and {far_w:.0f} mm across, {BEHIND:.0f} mm further back on the same line of sight. "
        f"Green is whatever of it reaches the picture.",
        fontsize=NOTE_SIZE, color=INK, ha="center", va="top", linespacing=1.8,
    )
    figure.text(
        0.5, 0.085,
        f"The near glass is {near_h:.0f} mm tall and the far one {far_h:.0f} mm, so the far glass is "
        f"the taller of the two. It is hidden anyway, because at {STANDOFF:.0f} mm the near glass is "
        f"magnified and at {STANDOFF + BEHIND:.0f} mm the far one is not. Standing further back buys "
        f"the far glass nothing:\nit contributes no pixels at {BEHIND:.0f} mm behind and none at "
        f"500 mm behind either. Sliding sideways is what ends it, because the near glass's shift is "
        f"{FX * (1 / STANDOFF - 1 / (STANDOFF + BEHIND)):.2f} pixels per millimetre larger than the "
        f"far one's — the same one-over-the-depth difference this method already measures.",
        fontsize=NOTE_SIZE, color=INK, ha="center", va="top", linespacing=1.8,
    )
    save(figure, "09-hidden-from-the-side.png")


def main() -> None:
    labels_come_from()
    two_views_parallax()
    embedding_space()
    parallax_arithmetic()
    deliberate_motion_loop()
    the_limit()
    hidden_from_above()
    hidden_from_the_side()


if __name__ == "__main__":
    main()
