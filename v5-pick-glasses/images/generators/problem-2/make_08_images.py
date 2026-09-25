"""Diagrams for solution 8 — per-pixel votes for the centre.

Run from the project root:

    pixi run python images/generators/problem-2/make_08_images.py

Every number drawn here comes from the cell: fx = fy = 277.1 pixels, survey
height 450 mm, footprints 45 to 105 mm across, and the worked example's pair of
glasses 90 mm apart with footprints of 76 and 73 mm.
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
    PAPER,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
)
from matplotlib.patches import Circle, Polygon, Rectangle

RNG = np.random.default_rng(8)

MM_PER_PIXEL = 450.0 / 277.1  # 1.624 mm on the table, one pixel wide, at survey height


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


if __name__ == "__main__":
    print(f"one pixel covers {MM_PER_PIXEL:.3f} mm at survey height")
    one_region_not_two()
    the_voting_idea()
    image_space_against_table_space()
    the_five_stages()
    vote_cloud_and_mean_shift()
    spread_as_confidence()
    too_few_votes()
