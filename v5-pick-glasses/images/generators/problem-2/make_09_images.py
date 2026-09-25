"""Diagrams for solution 9 — self-supervised from the arm's own movement.

Six pictures, each carrying its own point: where the training labels come from,
what the parallax signal is, what an embedding is, the arithmetic of how much
slide buys how much separation, the deliberate-motion loop, and the case where
the whole idea has nothing to work with.

Run from the project root:

    pixi run python images/generators/problem-2/make_09_images.py
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
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon

FX = 277.1            # pixels; the camera's focal length, the same in both axes
SURVEY_SLIDE = 120.0  # mm; the sideways slide between a station's two pictures


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


def main() -> None:
    labels_come_from()
    two_views_parallax()
    embedding_space()
    parallax_arithmetic()
    deliberate_motion_loop()
    the_limit()


if __name__ == "__main__":
    main()
