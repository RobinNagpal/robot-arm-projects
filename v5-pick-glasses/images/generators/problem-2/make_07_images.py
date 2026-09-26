"""Pictures for solution 7 — a segmenter trained from scratch.

Eight figures, each carrying one point of the document:

    07-what-is-asked-for.png          picture in, one probability per pixel out
    07-scratch-or-fine-tune.png       two ways to start, and why one is barred here
    07-the-u-net-shape.png            the down path, the bottleneck, the up path, the skips
    07-where-the-weights-are.png      the parameter arithmetic, and what a fourth level costs
    07-most-pixels-are-table.png      the class imbalance, and what it does to a score
    07-domain-randomisation.png       one scene many ways, and what stays fixed
    07-semantic-against-instance.png  what a per-pixel class map cannot say
    07-confidence-map.png             doubt, and the picture it asks for
    07-hidden-from-above.png          a glass with no pixels, from 450 mm up
    07-hidden-from-the-side.png       a glass with no pixels, from the level view

Run from the project root:

    pixi run python images/generators/problem-2/make_07_images.py

Every number here is arithmetic on channel widths, on image sizes, or on the
discs in these drawings. None of it is a measurement of a trained network, and
the document says so where it quotes these figures.

The last two figures are different in one way that matters. They are not
drawings: every silhouette in them is a real projection of one of the project's
own glass outlines, taken from ``work_cell.glasses.shapes``, through this cell's
own camera. A standing glass is a circle only in its footprint, which neither of
this cell's two views ever sees straight on, so the discs the earlier figures use
would misstate the very thing those two figures are about.
"""

from __future__ import annotations

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
    splay_covers,
    splay_width,
)
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, to_rgba
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import family  # noqa: E402

# The camera, from the cell's own numbers.
WIDE, TALL = 320, 240
FOCAL = 277.1
SURVEY_HEIGHT_MM = 450.0
MM_PER_PIXEL = SURVEY_HEIGHT_MM / FOCAL

# The level view, from the cell: 120 mm above the table, 380 mm back from the
# glass it is measuring, looking level rather than down.
VIEW_HEIGHT_MM = 120.0
STANDOFF_MM = 380.0
BEHIND_MM = 300.0

# The closest two glasses ever stand in problem 2, centre to centre.
MIN_APART_MM = 150.0

# The gap the two hiding pictures are drawn at. A little inside the widest gap
# that hides completely, so that the tall glass's silhouette does not run right
# up against the edge of the frame.
DRAWN_GAP_MM = 80.0

# Where the horizon sits in the level view, chosen so that the tallest glass
# this kind allows fits between the table and the top of the frame at 380 mm.
HORIZON_ROW = 140.0

# The scene these pictures share: three glasses on their own, and a pair in line
# with the camera. Radii in pixels; 24 px is a 78 mm footprint at survey height.
LONE = [(60.0, 70.0, 24.0), (250.0, 62.0, 24.0), (95.0, 186.0, 24.0)]
PAIR = [(175.0, 150.0, 24.0), (205.0, 150.0, 24.0)]
ALL_DISCS = LONE + PAIR

TABLE_GREY = "#eef1f4"
PROB_CMAP = LinearSegmentedColormap.from_list("prob", ["#f6f8fa", "#cfe0f2", GLASS, "#1f4d7a"])
DOUBT_CMAP = ListedColormap([WARN])


# --------------------------------------------------------------------------- #
# arithmetic
# --------------------------------------------------------------------------- #
def conv_weights(kernel: int, channels_in: int, channels_out: int) -> int:
    """Weights in one convolution, including one bias per output channel."""
    return kernel * kernel * channels_in * channels_out + channels_out


def unet_blocks(widths: tuple[int, ...], channels_in: int = 4) -> list[tuple[str, int]]:
    """Weights per block of a U-Net with these channel widths. Pure arithmetic."""
    blocks: list[tuple[str, int]] = []
    previous = channels_in
    for index, width in enumerate(widths):
        count = conv_weights(3, previous, width) + conv_weights(3, width, width)
        name = f"bottleneck, {width} ch" if index == len(widths) - 1 else f"down {index + 1}, {width} ch"
        blocks.append((name, count))
        previous = width
    for index in range(len(widths) - 2, -1, -1):
        width = widths[index]
        count = conv_weights(2, previous, width)
        count += conv_weights(3, width * 2, width) + conv_weights(3, width, width)
        blocks.append((f"up {index + 1}, {width} ch", count))
        previous = width
    blocks.append(("1x1 head, 1 ch", conv_weights(1, widths[0], 1)))
    return blocks


def unet_weights(widths: tuple[int, ...], channels_in: int = 4) -> int:
    return sum(count for _, count in unet_blocks(widths, channels_in))


def unet_macs(widths: tuple[int, ...], channels_in: int = 4) -> int:
    """Multiply-accumulates in one forward pass over a 320 x 240 picture."""
    total = 0
    previous = channels_in
    for index, width in enumerate(widths):
        pixels = (WIDE >> index) * (TALL >> index)
        total += (9 * previous * width + 9 * width * width) * pixels
        previous = width
    for index in range(len(widths) - 2, -1, -1):
        width = widths[index]
        pixels = (WIDE >> index) * (TALL >> index)
        total += (4 * previous * width + 9 * 2 * width * width + 9 * width * width) * pixels
        previous = width
    return total + widths[0] * WIDE * TALL


def encoder_receptive_field(blocks: int) -> int:
    """Input pixels one bottleneck unit sees: two 3x3 convolutions per block, 2x2 pools between."""
    field, stride = 1, 1
    for index in range(blocks):
        if index:
            field += stride
            stride *= 2
        field += 4 * stride
    return field


NARROW = (16, 32, 64, 128)
DEEPER = (16, 32, 64, 128, 256)


# --------------------------------------------------------------------------- #
# synthetic probability maps
# --------------------------------------------------------------------------- #
def probability_map(discs: list[tuple[float, float, float]], softness: float = 1.3) -> np.ndarray:
    """A soft-edged mask over these discs, with doubt where one rim runs inside another disc."""
    rows, columns = np.mgrid[0:TALL, 0:WIDE]
    probability = np.zeros((TALL, WIDE))
    distances = []
    for centre_x, centre_y, radius in discs:
        distance = np.hypot(columns - centre_x, rows - centre_y)
        distances.append((distance, radius))
        probability = np.maximum(probability, 1.0 / (1.0 + np.exp((distance - radius) / softness)))
    seam = np.zeros((TALL, WIDE), dtype=bool)
    for index, (distance, radius) in enumerate(distances):
        on_rim = np.abs(distance - radius) < 2.2
        inside_another = np.zeros((TALL, WIDE), dtype=bool)
        for other, (other_distance, other_radius) in enumerate(distances):
            if other != index:
                inside_another |= other_distance < other_radius - 2.0
        seam |= on_rim & inside_another
    # Just above 0.5, so the seam still counts as part of the region while being
    # squarely inside the 0.3 to 0.7 band that means "cannot tell".
    return np.where(seam, 0.54, probability)


def erode(mask: np.ndarray, radius: float) -> np.ndarray:
    """Binary erosion by a disc, by intersecting shifted copies. No SciPy in this environment."""
    reach = int(np.ceil(radius))
    out = mask.copy()
    for shift_y in range(-reach, reach + 1):
        for shift_x in range(-reach, reach + 1):
            if shift_y * shift_y + shift_x * shift_x <= radius * radius:
                out &= np.roll(np.roll(mask, shift_y, axis=0), shift_x, axis=1)
    return out


def region_doubt(discs: list[tuple[float, float, float]], collar: float = 3.0) -> tuple[float, float, int]:
    """Doubtful fraction of a region, counted over all of it and over its interior only."""
    probability = probability_map(discs)
    region = probability > 0.5
    doubtful = (probability >= 0.3) & (probability <= 0.7)
    interior = erode(region, collar)
    whole = doubtful[region].mean()
    inner = doubtful[interior].mean() if interior.any() else 0.0
    return float(whole), float(inner), int(region.sum())


# --------------------------------------------------------------------------- #
# drawing helpers
# --------------------------------------------------------------------------- #
def picture_axes(axis, background: str = TABLE_GREY) -> None:
    """A 320 x 240 picture frame, image coordinates, y downwards."""
    bare(axis)
    axis.set_xlim(0, WIDE)
    axis.set_ylim(TALL, 0)
    axis.set_aspect("equal")
    axis.add_patch(Rectangle((0, 0), WIDE, TALL, facecolor=background, edgecolor=INK, lw=0.9, zorder=0))


def draw_glass(axis, centre_x, centre_y, radius, face=GLASS, alpha=0.8, shadow=None) -> None:
    """One glass seen from above: the bowl, and the rim opening inside it."""
    if shadow is not None:
        offset_x, offset_y = shadow
        axis.add_patch(
            Circle(
                (centre_x + offset_x, centre_y + offset_y),
                radius * 1.03,
                facecolor=MUTED,
                alpha=0.28,
                lw=0,
                zorder=2,
            )
        )
    axis.add_patch(
        Circle((centre_x, centre_y), radius, facecolor=face, edgecolor=INK, lw=0.9, alpha=alpha, zorder=3)
    )
    axis.add_patch(
        Circle(
            (centre_x, centre_y), radius * 0.6, facecolor=PAPER, edgecolor=INK, lw=0.7, alpha=0.85, zorder=4
        )
    )


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, **kwargs) -> None:
    axis.text(x, y, text, color=colour, fontsize=size, **kwargs)


def box(axis, x, y, width, height, label, face, edge=INK, size=LABEL_SIZE, text_colour=INK) -> None:
    axis.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            facecolor=face,
            edgecolor=edge,
            lw=1.0,
            zorder=3,
        )
    )
    axis.text(
        x + width / 2,
        y + height / 2,
        label,
        ha="center",
        va="center",
        fontsize=size,
        color=text_colour,
        zorder=4,
    )


def arrow(axis, start, end, colour=INK, style="-|>", lw=1.2, dashed=False) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=11,
            color=colour,
            lw=lw,
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=2,
            shrinkB=2,
            zorder=5,
        )
    )



# --------------------------------------------------------------------------- #
# the cell's own glasses, projected through the cell's own camera
#
# The two figures about complete hiding cannot use the discs above. Hiding
# depends on the exact shape of a silhouette, so the silhouettes have to be real
# projections of real outlines. Everything below works in millimetres on the
# table and returns a mask in the 320 x 240 frame.
# --------------------------------------------------------------------------- #
def profile(outline) -> tuple[np.ndarray, np.ndarray]:
    """One glass's heights and radii, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def extreme_pair(draws: int = 1200, seed: int = 11):
    """The tallest, widest glass of the kind and the shortest, narrowest one.

    Complete hiding only happens between two glasses at opposite corners of one
    kind's range, so the pair has to be drawn from the corners. The spawner
    draws height and width independently, so a large number of draws is what it
    takes to reach a corner; 1200 costs a hundredth of a second.
    """
    drawn = [outline for outline, _ in family("tapered_glass", draws, seed)]
    heights = np.array([profile(outline)[0].max() for outline in drawn])
    widths = np.array([2.0 * profile(outline)[1].max() for outline in drawn])
    tall = drawn[int(np.argmax(heights / heights.max() + widths / widths.max()))]
    short = drawn[int(np.argmin(heights / heights.max() + widths / widths.max()))]
    return tall, short


def survey_mask(glasses, nadir_x: float = WIDE / 2, nadir_y: float = TALL / 2) -> np.ndarray:
    """Straight down from 450 mm. Each horizontal slice stays a circle, but a
    slice at height z is scaled about the nadir by 450 / (450 - z), because it is
    that much nearer the lens than the table is. Glasses are (x, y, outline) in
    millimetres from the point directly below the camera."""
    mask = np.zeros((TALL, WIDE), np.uint8)
    for glass_x, glass_y, outline in glasses:
        heights, radii = profile(outline)
        for height, radius in zip(heights, radii, strict=True):
            away = SURVEY_HEIGHT_MM - height
            cv2.circle(
                mask,
                (int(round(nadir_x + FOCAL * glass_x / away)), int(round(nadir_y + FOCAL * glass_y / away))),
                max(1, int(round(FOCAL * radius / away))),
                255,
                -1,
            )
    return mask


def level_mask(glasses) -> np.ndarray:
    """Level, from 120 mm up. A horizontal circle seen edge-on is a line, so the
    silhouette is the band between the two walls of the profile. Glasses are
    (sideways offset, distance from the camera, outline) in millimetres."""
    mask = np.zeros((TALL, WIDE), np.uint8)
    for sideways, distance, outline in glasses:
        heights, radii = profile(outline)
        for height, radius in zip(heights, radii, strict=True):
            row = int(round(HORIZON_ROW - FOCAL * (height - VIEW_HEIGHT_MM) / distance))
            left = int(round(WIDE / 2 + FOCAL * (sideways - radius) / distance))
            right = int(round(WIDE / 2 + FOCAL * (sideways + radius) / distance))
            if 0 <= row < TALL:
                cv2.line(mask, (max(0, left), row), (min(WIDE - 1, right), row), 255, 1)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))


def splay_stack(centre, outline, step: int = 8):
    """The stack of circles a standing glass draws in an overhead picture, built
    from the glass's own outline rather than from a straight-sided guess.

    The shape of the list matches what diagram_style.splay_covers and
    splay_width expect, so the covering test and the width measurement here are
    the same ones the rest of these diagrams use. The rim is always included,
    however coarse the sampling, because the rim is the widest part and the most
    magnified, and leaving it out understates every silhouette.
    """
    heights, radii = profile(outline)
    chosen = list(range(0, len(heights), step))
    if chosen[-1] != len(heights) - 1:
        chosen.append(len(heights) - 1)
    offset = np.asarray(centre, dtype=float)
    stack = []
    for index in chosen:
        factor = SURVEY_HEIGHT_MM / (SURVEY_HEIGHT_MM - heights[index])
        stack.append((offset * factor, radii[index] * factor))
    return stack


def covers_quickly(big, small, samples: int = 72) -> bool:
    """The same test as diagram_style.splay_covers, done in one array operation.

    Searching for the widest gap that still hides needs the test thousands of
    times, and the plain loop is too slow for that. The scene the figures are
    drawn from is checked against splay_covers itself, so the two are known to
    agree where it matters.
    """
    big_centres = np.array([centre for centre, _ in big])
    big_radii = np.array([radius for _, radius in big])
    angles = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    ring = np.stack([np.cos(angles), np.sin(angles)], axis=1)
    points = np.concatenate([centre + radius * ring for centre, radius in small])
    gaps = np.linalg.norm(points[:, None, :] - big_centres[None, :, :], axis=2) - big_radii[None, :]
    return bool((gaps.min(axis=1) <= 1e-9).all())


def inside_the_frame(centre, outline) -> bool:
    """Is the whole of this glass's splayed silhouette inside the 320 x 240 frame?"""
    for middle, radius in splay_stack(centre, outline):
        column = WIDE / 2 + middle[0] / MM_PER_PIXEL
        row = TALL / 2 + middle[1] / MM_PER_PIXEL
        reach = radius / MM_PER_PIXEL
        if column - reach < 0 or column + reach > WIDE or row - reach < 0 or row + reach > TALL:
            return False
    return True


def covering_radius(tall, short, gap: float, step: float = 2.0) -> float | None:
    """How far out from the nadir the tall glass has to stand before its
    silhouette has splayed far enough to swallow a short glass standing ``gap``
    millimetres further out along the same radius.

    Standing further out than that keeps the covering, so this is the only
    radius worth testing for any question about whether a gap can hide at all.
    """
    for candidate in np.arange(0.0, 420.0, step):
        if covers_quickly(splay_stack((candidate, 0.0), tall), splay_stack((candidate + gap, 0.0), short)):
            return float(candidate)
    return None


def widest_hiding_gap(tall, short, step: float = 2.0) -> tuple[float, float]:
    """The largest centre-to-centre gap at which the tall glass can hide the
    short one completely, with both of them wholly inside one overhead frame."""
    best = (0.0, 0.0)
    for gap in np.arange(30.0, 200.0, step):
        radius = covering_radius(tall, short, float(gap), step)
        if radius is None:
            break
        if inside_the_frame((radius, 0.0), tall) and inside_the_frame((radius + gap, 0.0), short):
            best = (float(gap), radius)
    return best


def widest_gap_on_table(tall, short, step: float = 2.0) -> tuple[float, float]:
    """The same, but asking only that both glasses stand on table the picture
    covers, and allowing the tall glass's own silhouette to run off the edge."""
    half_width = WIDE / 2 * MM_PER_PIXEL
    best = (0.0, 0.0)
    for gap in np.arange(30.0, 200.0, step):
        radius = covering_radius(tall, short, float(gap), step)
        if radius is None:
            break
        if radius + gap <= half_width:
            best = (float(gap), radius)
    return best


def paint_mask(axis, mask: np.ndarray, colour: str, alpha: float = 1.0, zorder: int = 3) -> None:
    """Show one mask in one colour, leaving everything else transparent."""
    rgba = np.zeros((*mask.shape, 4), float)
    rgba[mask > 0] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest", extent=(0, WIDE, TALL, 0), zorder=zorder)


def trace_mask(axis, mask: np.ndarray, colour: str = INK, width: float = 1.2, dashed: bool = False) -> None:
    """Draw a mask's outline only."""
    contours, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for contour in contours:
        points = contour[:, 0, :].astype(float)
        closed = np.vstack([points, points[:1]])
        axis.plot(
            closed[:, 0] + 0.5,
            closed[:, 1] + 0.5,
            color=colour,
            lw=width,
            ls=(0, (4, 2.5)) if dashed else "solid",
            zorder=6,
        )

# --------------------------------------------------------------------------- #
# figure 1 — what the network is asked for
# --------------------------------------------------------------------------- #
def figure_what_is_asked_for() -> None:
    figure = plt.figure(figsize=(11.4, 6.9))
    figure.patch.set_facecolor(PAPER)
    grid = figure.add_gridspec(
        2, 3, width_ratios=[1.0, 0.44, 1.0], height_ratios=[2.0, 1.0], hspace=0.45, wspace=0.12
    )
    left = figure.add_subplot(grid[0, 0])
    middle = figure.add_subplot(grid[0, 1])
    right = figure.add_subplot(grid[0, 2])
    strip = figure.add_subplot(grid[1, :])
    for axis in (left, middle, right):
        axis.set_facecolor(PAPER)

    picture_axes(left)
    for centre_x, centre_y, radius in ALL_DISCS:
        draw_glass(left, centre_x, centre_y, radius, shadow=(7, 5))
    left.set_title("in: one picture, four channels", fontsize=TITLE_SIZE, color=INK, pad=9)
    note(left, 4, 252, "320 x 240 pixels. red, green, blue, depth.", size=NOTE_SIZE)
    left.plot([20, 100], [70, 70], color=INK, lw=1.1, ls=(0, (3, 2)), zorder=6)
    note(left, 102, 72, "the line plotted below", colour=INK, size=NOTE_SIZE, va="center")

    bare(middle)
    middle.set_xlim(0, 1)
    middle.set_ylim(0, 1)
    box(middle, 0.02, 0.40, 0.96, 0.22, "a U-Net", "#e8eef5")
    note(middle, 0.5, 0.345, "about 482,000 weights,", size=NOTE_SIZE, ha="center")
    note(middle, 0.5, 0.29, "fitted to examples", size=NOTE_SIZE, ha="center")
    arrow(middle, (0.02, 0.73), (0.98, 0.73))
    note(middle, 0.5, 0.79, "the same function,", size=NOTE_SIZE, ha="center")
    note(middle, 0.5, 0.74, "every time", size=NOTE_SIZE, ha="center")

    probability = probability_map(ALL_DISCS)
    bare(right)
    image = right.imshow(probability, cmap=PROB_CMAP, vmin=0, vmax=1, interpolation="nearest")
    right.set_aspect("equal")
    right.set_title("out: one number per pixel", fontsize=TITLE_SIZE, color=INK, pad=9)
    right.plot([20, 100], [70, 70], color=INK, lw=1.1, ls=(0, (3, 2)))
    bar = figure.colorbar(image, ax=right, fraction=0.042, pad=0.03)
    bar.set_label("probability this pixel is glass", fontsize=NOTE_SIZE, color=INK)
    bar.ax.tick_params(labelsize=NOTE_SIZE - 0.6, colors=INK)
    note(right, 4, 252, "same width, same height, one channel.", size=NOTE_SIZE)

    columns = np.arange(20, 101)
    values = probability[70, 20:101]
    strip.axhspan(0.3, 0.7, color=WARN, alpha=0.13, zorder=0)
    strip.axhline(0.5, color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=1)
    strip.plot(columns, values, color=GLASS, lw=1.8, zorder=3)
    strip.scatter(columns[::6], values[::6], s=14, color=GLASS, zorder=4)
    strip.set_xlim(20, 100)
    strip.set_ylim(-0.06, 1.12)
    strip.set_xlabel("pixel across the picture", fontsize=NOTE_SIZE, color=INK)
    strip.set_ylabel("probability", fontsize=NOTE_SIZE, color=INK)
    strip.tick_params(labelsize=NOTE_SIZE - 0.6, colors=INK)
    for side in ("top", "right"):
        strip.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        strip.spines[side].set_color(MUTED)
    strip.set_title(
        "the output along that line: certain table, a two-pixel rim of doubt, certain glass",
        fontsize=LABEL_SIZE,
        color=INK,
        pad=7,
    )
    note(strip, 27, 0.80, "table:\nnear 0", size=NOTE_SIZE, ha="center")
    note(strip, 60, 0.84, "glass: near 1", size=NOTE_SIZE, ha="center")
    strip.annotate(
        "0.3 to 0.7: the band\nthat cannot tell",
        xy=(84.5, 0.5),
        xytext=(97, 0.98),
        ha="right",
        fontsize=NOTE_SIZE,
        color=WARN,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 1.0},
    )

    figure.suptitle(
        "What the network is asked for: a picture in, a probability per pixel out",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=0.98,
    )
    save(figure, "07-what-is-asked-for.png")


# --------------------------------------------------------------------------- #
# figure 2 — from scratch, or fine-tuned
# --------------------------------------------------------------------------- #
def figure_scratch_or_fine_tune() -> None:
    figure, axis = new(11.4, 6.2)
    bare(axis)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)

    rows = [
        (
            "where the weights start",
            "copied from somebody\nelse's trained network",
            "random noise",
        ),
        (
            "what those weights saw",
            "millions of real photographs\n(ImageNet, COCO-style sets)",
            "nothing yet",
        ),
        (
            "labels it needs",
            "a few hundred, drawn\nround objects by hand",
            "as many as Gazebo renders,\nexact and free",
        ),
        (
            "hardware it assumes",
            "an NVIDIA card,\nusually compiled CUDA",
            "whatever runs PyTorch;\nApple's MPS will do",
        ),
        (
            "what it costs here",
            "barred: no real photographs,\nno NVIDIA card",
            "an afternoon of rendering\nand training",
        ),
    ]
    top, row_height = 0.735, 0.125
    box(axis, 0.30, 0.885, 0.32, 0.075, "fine-tune a borrowed backbone", "#f6e4de", edge=WARN)
    box(axis, 0.65, 0.885, 0.32, 0.075, "train from random initialisation", "#e2efe4", edge=GOOD)
    for index, (question, left_text, right_text) in enumerate(rows):
        y = top - index * row_height
        axis.text(0.28, y + 0.042, question, ha="right", va="center", fontsize=LABEL_SIZE, color=INK)
        bad = index == len(rows) - 1
        box(
            axis,
            0.30,
            y,
            0.32,
            0.085,
            left_text,
            "#fdf4f1" if not bad else "#f6ddd4",
            edge=WARN if bad else MUTED,
            size=NOTE_SIZE,
        )
        box(
            axis,
            0.65,
            y,
            0.32,
            0.085,
            right_text,
            "#f3f9f4" if not bad else "#dcecdf",
            edge=GOOD if bad else MUTED,
            size=NOTE_SIZE,
        )
        if index < len(rows) - 1:
            axis.plot([0.03, 0.97], [y - 0.014, y - 0.014], color="#e3e6ea", lw=0.8, zorder=0)

    note(
        axis,
        0.02,
        0.165,
        "Fine-tuning is the standard advice because hand-drawn labels are scarce.\n"
        "In this cell they are not scarce — they are free, and that removes the reason.",
        colour=INK,
        size=LABEL_SIZE,
        va="top",
    )
    note(
        axis,
        0.02,
        0.065,
        "And the left column is barred outright: every borrowable backbone was fitted to real\n"
        "photographs, which this project's rule excludes.",
        colour=WARN,
        size=LABEL_SIZE,
        va="top",
    )
    axis.set_title(
        "Two ways to start a network, and why only one of them is open here",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        pad=12,
    )
    save(figure, "07-scratch-or-fine-tune.png")


# --------------------------------------------------------------------------- #
# figure 3 — the U-Net shape
# --------------------------------------------------------------------------- #
def figure_u_net_shape() -> None:
    figure, axis = new(11.4, 7.0)
    bare(axis)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)

    levels = [
        ("320 x 240 x 16", "320 x 240 x 16", 0.80),
        ("160 x 120 x 32", "160 x 120 x 32", 0.63),
        ("80 x 60 x 64", "80 x 60 x 64", 0.46),
    ]
    width, height = 0.20, 0.083
    down_x, up_x = 0.13, 0.60
    for index, (down_label, up_label, y) in enumerate(levels):
        box(axis, down_x, y, width, height, down_label, "#dce8f5", size=NOTE_SIZE)
        box(axis, up_x, y, width, height, up_label, "#dce8f5", size=NOTE_SIZE)
        arrow(axis, (down_x + width + 0.005, y + height / 2), (up_x - 0.005, y + height / 2),
              colour=GOOD, lw=1.5, dashed=True)
        axis.text(
            (down_x + width + up_x) / 2,
            y + height / 2 + 0.028,
            "skip: copy this level across",
            ha="center",
            fontsize=NOTE_SIZE,
            color=GOOD,
        )
        if index < len(levels) - 1:
            next_y = levels[index + 1][2]
            arrow(axis, (down_x + 0.04, y), (down_x + 0.04, next_y + height))
            axis.text(down_x + 0.052, (y + next_y + height) / 2, "max pool 2x2", va="center",
                      fontsize=NOTE_SIZE, color=INK)
            arrow(axis, (up_x + width - 0.04, next_y + height), (up_x + width - 0.04, y))
            axis.text(up_x + width - 0.052, (y + next_y + height) / 2, "up 2x2", fontsize=NOTE_SIZE,
                      color=INK, va="center", ha="right")

    bottom_y = 0.27
    arrow(axis, (down_x + 0.04, levels[-1][2]), (0.355, bottom_y + height * 0.55))
    axis.text(down_x + 0.030, (levels[-1][2] + bottom_y + height) / 2 - 0.02, "max pool 2x2",
              fontsize=NOTE_SIZE, color=INK, va="center", ha="right")
    box(axis, 0.355, bottom_y, 0.245, height, "bottleneck  40 x 30 x 128", "#b9d3ec", size=LABEL_SIZE)
    arrow(axis, (0.60, bottom_y + height / 2), (up_x + width - 0.04, levels[-1][2]))

    box(axis, up_x, 0.80 + 0.115, width, 0.072, "1x1 convolution  ->  320 x 240 x 1", "#e2efe4",
        edge=GOOD, size=NOTE_SIZE)
    arrow(axis, (up_x + width / 2, 0.80 + height), (up_x + width / 2, 0.80 + 0.115), colour=GOOD)
    box(axis, down_x, 0.80 + 0.115, width, 0.072, "320 x 240 x 4  (R G B depth)", "#f0f2f4", size=NOTE_SIZE)
    arrow(axis, (down_x + width / 2, 0.80 + 0.115), (down_x + width / 2, 0.80 + height))

    note(axis, 0.025, 0.63, "down the path\n\nhalf the pixels,\ntwice the channels.\nEach unit sees more\n"
         "of the table and\nknows less exactly\nwhere it is looking.",
         colour=INK, size=NOTE_SIZE, va="center", ha="center")
    note(axis, 0.955, 0.63, "up the path\n\ndouble the pixels,\nhalf the channels,\nback to full size.\n"
         "The skips hand back\nthe sharp edges the\npooling threw away.",
         colour=INK, size=NOTE_SIZE, va="center", ha="center")

    field = encoder_receptive_field(len(NARROW))
    note(
        axis,
        0.5,
        0.13,
        f"At the bottleneck one unit's answer depends on a {field} x {field} patch of the input.\n"
        f"At survey height one pixel is {MM_PER_PIXEL:.2f} mm, so that patch is about "
        f"{field * MM_PER_PIXEL:.0f} mm of table —\n"
        "less than the 150 mm the glasses are guaranteed to be apart. See the next picture.",
        colour=INK,
        size=LABEL_SIZE,
        ha="center",
        va="center",
    )
    axis.set_title(
        "The U-Net: down to a small wide summary, up to a full-size answer, with the levels copied across",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        pad=12,
    )
    save(figure, "07-the-u-net-shape.png")


# --------------------------------------------------------------------------- #
# figure 4 — where the weights are
# --------------------------------------------------------------------------- #
def figure_where_the_weights_are() -> None:
    figure, axes = new(11.8, 5.4, columns=2)
    left, right = axes

    blocks = unet_blocks(NARROW)
    labels = [name for name, _ in blocks][::-1]
    counts = [count for _, count in blocks][::-1]
    total = sum(counts)
    colours = [WARN if count > 100_000 else GLASS for count in counts]
    positions = np.arange(len(counts))
    left.barh(positions, counts, color=colours, alpha=0.85, edgecolor=INK, lw=0.6, height=0.68)
    left.set_yticks(positions)
    left.set_yticklabels(labels, fontsize=NOTE_SIZE, color=INK)
    left.set_xlabel("weights in this block", fontsize=NOTE_SIZE, color=INK)
    left.tick_params(axis="x", labelsize=NOTE_SIZE - 0.6, colors=INK)
    left.xaxis.set_major_formatter(lambda value, _: f"{value:,.0f}")
    left.set_xlim(0, max(counts) * 1.32)
    for position, count in zip(positions, counts, strict=True):
        left.text(count + max(counts) * 0.02, position, f"{count:,}", va="center", fontsize=NOTE_SIZE,
                  color=INK)
    for side in ("top", "right"):
        left.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        left.spines[side].set_color(MUTED)
    deep = sum(count for name, count in blocks if "bottleneck" in name or "up 3" in name)
    left.set_title(
        f"Where the {total:,} weights sit\n"
        f"the two deepest blocks alone hold {100 * deep / total:.0f} per cent of them",
        fontsize=LABEL_SIZE + 0.6,
        color=INK,
        pad=9,
    )

    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    narrow_field = encoder_receptive_field(len(NARROW)) * MM_PER_PIXEL
    deeper_field = encoder_receptive_field(len(DEEPER)) * MM_PER_PIXEL
    narrow_total = unet_weights(NARROW)
    deeper_total = unet_weights(DEEPER)
    right.set_title(
        "What a fourth halving buys, and what it costs",
        fontsize=LABEL_SIZE + 0.6,
        color=INK,
        pad=9,
    )
    scale = 0.62 / max(narrow_field, deeper_field, 260.0)
    base_y = 0.30
    for index, (name, field, weights, colour) in enumerate(
        [
            ("three halvings\n40 x 30 bottleneck", narrow_field, narrow_total, GLASS),
            ("four halvings\n20 x 15 bottleneck", deeper_field, deeper_total, GOOD),
        ]
    ):
        y = base_y + index * 0.30
        right.add_patch(
            Rectangle((0.30, y), field * scale, 0.14, facecolor=colour, alpha=0.8, edgecolor=INK, lw=0.7)
        )
        right.text(0.28, y + 0.07, name, ha="right", va="center", fontsize=NOTE_SIZE, color=INK)
        right.text(
            0.315,
            y + 0.165,
            f"{field:.0f} mm of table seen at the bottleneck  -  {weights:,} weights",
            va="center",
            fontsize=NOTE_SIZE,
            color=INK,
        )
    gap_x = 0.30 + 150.0 * scale
    right.plot([gap_x, gap_x], [0.26, 0.72], color=WARN, lw=1.4, ls=(0, (5, 3)), zorder=0)
    right.text(gap_x, 0.215, "150 mm — the closest\ntwo glasses ever stand", ha="center", va="top",
               fontsize=NOTE_SIZE, color=WARN)
    ratio = deeper_total / narrow_total
    right.text(
        0.5,
        0.08,
        f"Four halvings cost {ratio:.1f} times the weights and are the only version\n"
        "whose deepest unit can see two glasses at once. Which one is needed is uncertain.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=INK,
    )
    figure.suptitle(
        "The parameter count is arithmetic on the channel widths, not a measurement",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=1.0,
    )
    save(figure, "07-where-the-weights-are.png")


# --------------------------------------------------------------------------- #
# figure 5 — most pixels are table
# --------------------------------------------------------------------------- #
def figure_most_pixels_are_table() -> None:
    figure, axes = new(11.8, 5.2, columns=2)
    left, right = axes

    pixels = WIDE * TALL
    per_glass = np.pi * 24.0**2
    glass_pixels = 5 * per_glass
    table_pixels = pixels - glass_pixels

    bare(left)
    left.set_xlim(0, 1)
    left.set_ylim(0, 1)
    left.add_patch(Rectangle((0.08, 0.34), 0.84, 0.30, facecolor=TABLE_GREY, edgecolor=INK, lw=0.9))
    share = glass_pixels / pixels
    left.add_patch(Rectangle((0.08, 0.34), 0.84 * share, 0.30, facecolor=GLASS, edgecolor=INK, lw=0.9))
    left.text(0.08 + 0.84 * share / 2, 0.68, f"glass\n{glass_pixels:,.0f} px\n{100 * share:.1f}%",
              ha="center", va="bottom", fontsize=NOTE_SIZE, color=GLASS)
    left.text(0.55, 0.68, f"table\n{table_pixels:,.0f} px\n{100 * (1 - share):.1f}%", ha="center",
              va="bottom", fontsize=NOTE_SIZE, color=INK)
    left.text(
        0.5,
        0.26,
        f"One picture is {WIDE} x {TALL} = {pixels:,} pixels.\n"
        "Five glasses, each about 48 pixels across at the table plane,\n"
        f"cover roughly {glass_pixels:,.0f} of them.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=INK,
    )
    share_value = glass_pixels / pixels
    flat = (1 - share_value) * -np.log(0.98) + share_value * -np.log(0.02)
    left.text(
        0.5,
        0.08,
        "A cross entropy averaged over pixels falls from\n"
        f"{-np.log(0.5):.3f} to {flat:.3f} the moment the network learns\n"
        "\"table everywhere\" and nothing else.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=WARN,
    )
    left.set_title("Most pixels are table", fontsize=LABEL_SIZE + 0.6, color=INK, pad=9)

    thin = np.pi * 21.0**2
    cases = [
        ("say \"table\"\neverywhere", 1 - share, 0.0),
        ("every mask\n3 px too thin", 1 - 5 * (per_glass - thin) / pixels, 2 * thin / (thin + per_glass)),
        ("exactly right", 1.0, 1.0),
    ]
    positions = np.arange(len(cases))
    accuracy = [value for _, value, _ in cases]
    dice = [value for _, _, value in cases]
    right.bar(positions - 0.19, accuracy, width=0.36, color=WARN, alpha=0.85, edgecolor=INK, lw=0.6,
              label="pixel accuracy")
    right.bar(positions + 0.19, dice, width=0.36, color=GOOD, alpha=0.85, edgecolor=INK, lw=0.6,
              label="Dice overlap")
    for position, (accuracy_value, dice_value) in enumerate(zip(accuracy, dice, strict=True)):
        right.text(position - 0.19, accuracy_value + 0.02, f"{accuracy_value:.3f}", ha="center",
                   fontsize=NOTE_SIZE, color=INK)
        right.text(position + 0.19, dice_value + 0.02, f"{dice_value:.3f}", ha="center", fontsize=NOTE_SIZE,
                   color=INK)
    right.set_xticks(positions)
    right.set_xticklabels([name for name, _, _ in cases], fontsize=NOTE_SIZE, color=INK)
    right.set_ylim(0, 1.38)
    right.set_ylabel("score", fontsize=NOTE_SIZE, color=INK)
    right.tick_params(axis="y", labelsize=NOTE_SIZE - 0.6, colors=INK)
    right.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper left", ncols=2)
    for side in ("top", "right"):
        right.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        right.spines[side].set_color(MUTED)
    right.set_title(
        "A score that counts pixels rewards saying nothing.\nA score that counts overlap does not.",
        fontsize=LABEL_SIZE + 0.6,
        color=INK,
        pad=9,
    )
    figure.suptitle(
        "The class imbalance, and why the loss has to be chosen around it",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=1.06,
    )
    save(figure, "07-most-pixels-are-table.png")


# --------------------------------------------------------------------------- #
# figure 6 — domain randomisation
# --------------------------------------------------------------------------- #
def figure_domain_randomisation() -> None:
    figure, axes = plt.subplots(2, 3, figsize=(11.6, 6.4))
    figure.patch.set_facecolor(PAPER)
    settings = [
        ("#e7eaee", "#4c8fd6", (7, 5), 0.85, 4, 0.010, "bright, from the left"),
        ("#cdd2d8", "#5f9bd8", (-6, 6), 0.72, 6, 0.030, "dim, from the right"),
        ("#f2ece2", "#7fa9cf", (2, 9), 0.62, 5, 0.018, "warm table, light overhead"),
        ("#dfe6ea", "#3f7ab8", (9, -3), 0.92, 4, 0.045, "noisy sensor, low light"),
        ("#e9e4ea", "#6d97c4", (-8, -5), 0.78, 6, 0.014, "tinted glass, camera rolled"),
        ("#d8ded4", "#508cc2", (5, 7), 0.68, 5, 0.026, "different table, exposure up"),
    ]
    generator = np.random.default_rng(7)
    for axis, (background, glass_colour, shadow, alpha, count, noise, caption) in zip(
        axes.ravel(), settings, strict=True
    ):
        axis.set_facecolor(PAPER)
        bare(axis)
        speckle = generator.normal(0.0, noise, size=(TALL // 2, WIDE // 2))
        axis.imshow(
            speckle,
            cmap=LinearSegmentedColormap.from_list("bg", [background, "#ffffff"]),
            extent=(0, WIDE, TALL, 0),
            vmin=-0.09,
            vmax=0.09,
            interpolation="bilinear",
            zorder=0,
        )
        axis.set_xlim(0, WIDE)
        axis.set_ylim(TALL, 0)
        axis.set_aspect("equal")
        axis.add_patch(Rectangle((0, 0), WIDE, TALL, facecolor="none", edgecolor=INK, lw=0.9, zorder=6))
        angle = generator.uniform(-0.22, 0.22)
        for index in range(count):
            base_x, base_y = 55 + (index % 3) * 100, 70 + (index // 3) * 95
            jitter_x = base_x + generator.uniform(-16, 16)
            jitter_y = base_y + generator.uniform(-14, 14)
            spun_x = WIDE / 2 + (jitter_x - WIDE / 2) * np.cos(angle) - (jitter_y - TALL / 2) * np.sin(angle)
            spun_y = TALL / 2 + (jitter_x - WIDE / 2) * np.sin(angle) + (jitter_y - TALL / 2) * np.cos(angle)
            radius = generator.uniform(16, 30)
            draw_glass(axis, spun_x, spun_y, radius, face=glass_colour, alpha=alpha, shadow=shadow)
        axis.set_title(caption, fontsize=NOTE_SIZE, color=INK, pad=4)

    figure.suptitle(
        "Domain randomisation: vary everything you are not teaching, so shape is all that is left to learn",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=1.0,
    )
    figure.text(
        0.5,
        0.055,
        "Varied every scene: light direction and strength, table and glass colour, exposure, sensor noise,\n"
        "how many glasses and where, each one's proportions inside its kind's range, and the camera pose.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=INK,
    )
    figure.text(
        0.5,
        -0.015,
        f"Held fixed on purpose: fx = fy = {FOCAL} px and {WIDE} x {TALL} pixels, because that is this "
        "camera, not a nuisance;\nand glasses upright on a flat table, because that is the task.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=GOOD,
    )
    figure.text(
        0.5,
        -0.085,
        "What no amount of randomising changes: all six came out of the same renderer.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=WARN,
    )
    figure.subplots_adjust(hspace=0.22, wspace=0.08, bottom=0.14)
    save(figure, "07-domain-randomisation.png")


# --------------------------------------------------------------------------- #
# figure 7 — semantic against instance
# --------------------------------------------------------------------------- #
def figure_semantic_against_instance() -> None:
    figure, axes = new(11.6, 4.0, columns=3)
    figure.subplots_adjust(top=0.84, bottom=0.03)
    pair = [(118.0, 98.0, 38.0), (166.0, 104.0, 38.0)]

    picture_axes(axes[0])
    for centre_x, centre_y, radius in pair:
        draw_glass(axes[0], centre_x, centre_y, radius, shadow=(8, 6))
    axes[0].set_title("two glasses, in line with the camera", fontsize=LABEL_SIZE + 0.6, color=INK, pad=8)
    note(axes[0], 10, 158, "180 mm apart on the table.\nThe camera is in line with\n"
         "both, so they overlap in\nthe picture.", colour=INK, size=NOTE_SIZE, va="top")

    picture_axes(axes[1], background=PAPER)
    probability = probability_map(pair)
    axes[1].imshow(
        np.ma.masked_where(probability <= 0.5, probability),
        cmap=ListedColormap([WARN]),
        extent=(0, WIDE, TALL, 0),
        vmin=0,
        vmax=1,
        interpolation="nearest",
        zorder=2,
    )
    axes[1].set_title("what a per-pixel class map says", fontsize=LABEL_SIZE + 0.6, color=INK, pad=8)
    note(axes[1], 144, 111, "glass", colour=PAPER, size=LABEL_SIZE + 1, ha="center", va="center", zorder=3)
    note(axes[1], 10, 158, "One region. Every pixel is\nlabelled \"glass\", and a class\n"
         "label has no field in it for\nwhich glass.", colour=WARN, size=NOTE_SIZE, va="top")

    picture_axes(axes[2], background=PAPER)
    for (centre_x, centre_y, radius), colour in zip(pair, (GOOD, GLASS), strict=True):
        axes[2].add_patch(Circle((centre_x, centre_y), radius, facecolor=colour, alpha=0.8,
                                 edgecolor=INK, lw=0.9, zorder=3))
    axes[2].set_title("what problem 2 actually wants", fontsize=LABEL_SIZE + 0.6, color=INK, pad=8)
    note(axes[2], 10, 158, "Two masks. The separating has\nto come from somewhere else:\n"
         "a boundary channel, or a vector\nat each pixel to its own centre.",
         colour=INK, size=NOTE_SIZE, va="top")
    note(axes[2], 10, 26, "Solution 8 is that idea in full.", colour=GOOD, size=LABEL_SIZE, va="top")

    figure.suptitle(
        "The gap this solution does not close on its own: semantic against instance",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=0.98,
    )
    save(figure, "07-semantic-against-instance.png")


# --------------------------------------------------------------------------- #
# figure 8 — the confidence map, and the loop
# --------------------------------------------------------------------------- #
def figure_confidence_map():
    figure, axes = new(12.2, 4.8, columns=3)
    figure.subplots_adjust(top=0.82, bottom=0.08, wspace=0.26)
    probability = probability_map(ALL_DISCS)

    bare(axes[0])
    axes[0].imshow(probability, cmap=PROB_CMAP, vmin=0, vmax=1, interpolation="nearest",
                   extent=(0, WIDE, TALL, 0))
    axes[0].set_xlim(0, WIDE)
    axes[0].set_ylim(TALL, 0)
    axes[0].set_aspect("equal")
    axes[0].add_patch(Rectangle((0, 0), WIDE, TALL, facecolor="none", edgecolor=INK, lw=0.9, zorder=5))
    axes[0].set_title("the confidence map", fontsize=LABEL_SIZE + 0.6, color=INK, pad=8)
    note(axes[0], 8, 200, "dark: sure it is glass\npale: sure it is not", colour=INK, size=NOTE_SIZE,
         va="top")

    doubtful = (probability >= 0.3) & (probability <= 0.7)
    region = probability > 0.5
    bare(axes[1])
    axes[1].imshow(
        np.ma.masked_where(~region, np.zeros_like(probability)),
        cmap=ListedColormap(["#e4ebf3"]),
        extent=(0, WIDE, TALL, 0),
        interpolation="nearest",
        zorder=1,
    )
    axes[1].imshow(
        np.ma.masked_where(~doubtful, np.ones_like(probability)),
        cmap=DOUBT_CMAP,
        extent=(0, WIDE, TALL, 0),
        interpolation="nearest",
        zorder=2,
    )
    axes[1].set_xlim(0, WIDE)
    axes[1].set_ylim(TALL, 0)
    axes[1].set_aspect("equal")
    axes[1].add_patch(Rectangle((0, 0), WIDE, TALL, facecolor="none", edgecolor=INK, lw=0.9, zorder=5))
    axes[1].set_title("only the pixels between 0.3 and 0.7", fontsize=LABEL_SIZE + 0.6, color=INK, pad=8)
    axes[1].annotate(
        "every rim is doubtful.\nThat is not news.",
        xy=(72, 48),
        xytext=(116, 34),
        fontsize=NOTE_SIZE,
        color=INK,
        va="center",
        arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 0.9},
    )
    axes[1].annotate(
        "a band of doubt across the\ninside of a region is.",
        xy=(190, 150),
        xytext=(150, 226),
        fontsize=NOTE_SIZE,
        color=WARN,
        va="bottom",
        arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 1.1},
    )

    groups = [("A", [LONE[0]]), ("B", [LONE[1]]), ("C", [LONE[2]]), ("D (the pair)", PAIR)]
    inner_scores, whole_scores, sizes = [], [], []
    for _, discs in groups:
        whole, inner, size = region_doubt(discs)
        whole_scores.append(100 * whole)
        inner_scores.append(100 * inner)
        sizes.append(size)
    positions = np.arange(len(groups))
    axes[2].bar(positions - 0.19, whole_scores, width=0.36, color=MUTED, alpha=0.75, edgecolor=INK,
                lw=0.6, label="all of the region")
    axes[2].bar(positions + 0.19, inner_scores, width=0.36, color=WARN, alpha=0.9, edgecolor=INK,
                lw=0.6, label="interior only, 3 px collar cut off")
    for position, (whole, inner) in enumerate(zip(whole_scores, inner_scores, strict=True)):
        axes[2].text(position - 0.19, whole + 0.4, f"{whole:.1f}", ha="center", fontsize=NOTE_SIZE,
                     color=INK)
        axes[2].text(position + 0.19, inner + 0.4, f"{inner:.1f}", ha="center", fontsize=NOTE_SIZE,
                     color=INK)
    axes[2].axhline(3.0, color=WARN, lw=1.2, ls=(0, (5, 3)), zorder=0)
    axes[2].text(-0.42, 3.4, "above this line, look again", fontsize=NOTE_SIZE, color=WARN,
                 bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 1.5})
    axes[2].set_xticks(positions)
    axes[2].set_xticklabels([name for name, _ in groups], fontsize=NOTE_SIZE, color=INK)
    axes[2].set_ylabel("doubtful pixels, per cent", fontsize=NOTE_SIZE, color=INK)
    axes[2].tick_params(axis="y", labelsize=NOTE_SIZE - 0.6, colors=INK)
    axes[2].set_ylim(0, max(whole_scores) * 1.55)
    axes[2].legend(fontsize=NOTE_SIZE - 0.4, frameon=False, loc="upper left")
    for side in ("top", "right"):
        axes[2].spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes[2].spines[side].set_color(MUTED)
    axes[2].set_title(
        "Counting the whole region hides it.\nCounting the interior does not.",
        fontsize=LABEL_SIZE + 0.6,
        color=INK,
        pad=8,
    )
    figure.suptitle(
        "The feedback loop: interior doubt marks the region to photograph again",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=0.96,
    )
    save(figure, "07-confidence-map.png")
    return whole_scores, inner_scores, sizes


# --------------------------------------------------------------------------- #
# figure 9 — a glass with no pixels at all, looking straight down
# --------------------------------------------------------------------------- #
def corner_note(axis, text: str, colour=INK, corner: str = "top") -> None:
    """A note in a picture frame's free corner, clear of the silhouettes."""
    if corner == "top":
        axis.text(8, 8, text, fontsize=NOTE_SIZE, color=colour, va="top", ha="left", zorder=8)
    else:
        axis.text(8, TALL - 8, text, fontsize=NOTE_SIZE, color=colour, va="bottom", ha="left", zorder=8)


def figure_hidden_from_above():
    """The overhead case: a tall glass's splayed silhouette swallows a short one."""
    tall, short = extreme_pair()
    widest, _ = widest_hiding_gap(tall, short)
    gap = DRAWN_GAP_MM
    radius = covering_radius(tall, short, gap)
    near, far_along, far_across = (radius, 0.0), (radius + gap, 0.0), (radius, gap)
    assert splay_covers(splay_stack(near, tall), splay_stack(far_along, short))

    tall_only = survey_mask([(*near, tall)])
    short_only = survey_mask([(*far_along, short)])
    both_along = survey_mask([(*near, tall), (*far_along, short)])
    short_across = survey_mask([(*far_across, short)])
    left_along = int(((short_only > 0) & (tall_only == 0)).sum())
    left_across = int(((short_across > 0) & (tall_only == 0)).sum())
    patch_px = splay_width(splay_stack(near, tall)) / MM_PER_PIXEL

    figure, axes = plt.subplots(1, 4, figsize=(14.0, 4.2))
    figure.patch.set_facecolor(PAPER)
    nadir = (WIDE / 2, TALL / 2)

    def frame(axis, title, background=PAPER):
        axis.set_facecolor(PAPER)
        picture_axes(axis, background=background)
        axis.set_title(title, fontsize=LABEL_SIZE + 0.4, color=INK, pad=7)

    # 1 — the picture that comes out of the camera, and nothing else.
    frame(axes[0], "what the camera records", background=TABLE_GREY)
    paint_mask(axes[0], both_along, GLASS, alpha=0.85)
    trace_mask(axes[0], both_along)
    axes[0].plot(*nadir, marker="+", color=INK, ms=9, mew=1.4, zorder=7)
    axes[0].text(nadir[0] - 14, nadir[1] + 14, "the nadir", fontsize=NOTE_SIZE, color=INK,
                 ha="right", va="top", zorder=8)
    corner_note(axes[0], f"one patch, {patch_px:.0f} px across.\nNothing about it is odd.")

    # 2 — the best label anything that labels pixels can return.
    frame(axes[1], "the best label a per-pixel network can give")
    paint_mask(axes[1], both_along, GLASS, alpha=0.8)
    trace_mask(axes[1], both_along)
    axes[1].text(nadir[0] + 78, nadir[1], "glass", color=PAPER, fontsize=LABEL_SIZE + 1,
                 ha="center", va="center", zorder=8)
    corner_note(axes[1], f"one region, {int((both_along > 0).sum()):,} pixels,\n"
                "every one of them correct")

    # 3 — the truth, with the footprints that show where the splay came from.
    frame(axes[2], "the truth, which is two glasses")
    paint_mask(axes[2], tall_only, MUTED, alpha=0.28)
    trace_mask(axes[2], tall_only, colour=MUTED)
    paint_mask(axes[2], short_only, WARN, alpha=0.55, zorder=4)
    trace_mask(axes[2], short_only, colour=WARN, dashed=True)
    axes[2].plot([nadir[0], nadir[0] + (radius + gap) / MM_PER_PIXEL * 1.35], [nadir[1], nadir[1]],
                 color=INK, lw=0.9, ls=(0, (4, 3)), zorder=7)
    axes[2].plot(*nadir, marker="+", color=INK, ms=9, mew=1.4, zorder=8)
    for centre, outline in ((near, tall), (far_along, short)):
        base_radius = profile(outline)[1][0]
        axes[2].add_patch(Circle((nadir[0] + centre[0] / MM_PER_PIXEL, nadir[1]),
                                 base_radius / MM_PER_PIXEL, facecolor="none", edgecolor=INK,
                                 lw=0.9, ls=(0, (2, 2)), zorder=8))
    corner_note(axes[2], "the dashed circles are where the\ntwo glasses really stand, and the\n"
                "dashed line is the direction the\nsplay pushes them")
    corner_note(axes[2], f"the short glass: {int((short_only > 0).sum()):,} pixels of its own,\n"
                f"and {left_along} of them anywhere in the picture", colour=WARN, corner="bottom")

    # 4 — the same pair, turned across the radius instead of along it.
    frame(axes[3], "the same pair, turned across the radius")
    paint_mask(axes[3], tall_only, MUTED, alpha=0.28)
    trace_mask(axes[3], tall_only, colour=MUTED)
    paint_mask(axes[3], (short_across > 0) & (tall_only == 0), GOOD, alpha=0.8, zorder=4)
    trace_mask(axes[3], short_across, colour=GOOD, dashed=True)
    axes[3].plot(*nadir, marker="+", color=INK, ms=9, mew=1.4, zorder=8)
    corner_note(axes[3], f"{left_across:,} of its {int((short_across > 0).sum()):,} pixels come back.\n"
                "Now there is something to label.", colour=GOOD)

    figure.suptitle(
        "Looking straight down: when the splayed silhouette swallows the short glass, "
        "no labelling of pixels can find it",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=0.97,
    )
    figure.text(
        0.5,
        0.085,
        f"Real projections of two of this kind's own glasses through this cell's own camera. The tall "
        f"one is {profile(tall)[0].max():.0f} mm high and {2 * profile(tall)[1].max():.0f} mm across the "
        f"rim and stands {radius:.0f} mm from the nadir; the short one is "
        f"{profile(short)[0].max():.0f} mm high and {2 * profile(short)[1].max():.0f} mm across.\n"
        f"Their centres are {gap:.0f} mm apart. The widest gap that hides completely with both glasses "
        f"inside one frame is {widest:.0f} mm, which is still {MIN_APART_MM - widest:.0f} mm closer than "
        "this cell ever lets two glasses stand.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=INK,
    )
    figure.subplots_adjust(top=0.84, bottom=0.17, wspace=0.07)
    save(figure, "07-hidden-from-above.png")
    return {"pair": (tall, short), "gap": gap, "radius": radius}


# --------------------------------------------------------------------------- #
# figure 10 — a glass with no pixels at all, looking level
# --------------------------------------------------------------------------- #
def figure_hidden_from_the_side(pair) -> None:
    """The level case: plain line of sight, and no splay needed."""
    tall, _ = pair
    near_distance, far_distance = STANDOFF_MM, STANDOFF_MM + BEHIND_MM

    near_only = level_mask([(0.0, near_distance, tall)])
    far_only = level_mask([(0.0, far_distance, tall)])
    both = level_mask([(0.0, near_distance, tall), (0.0, far_distance, tall)])
    left_over = int(((far_only > 0) & (near_only == 0)).sum())

    figure, axes = plt.subplots(1, 4, figsize=(14.0, 4.2))
    figure.patch.set_facecolor(PAPER)

    def frame(axis, title, background=PAPER):
        axis.set_facecolor(PAPER)
        picture_axes(axis, background=background)
        axis.set_title(title, fontsize=LABEL_SIZE + 0.4, color=INK, pad=7)

    # 1 — the picture.
    frame(axes[0], "what the camera records", background=TABLE_GREY)
    axes[0].plot([0, WIDE], [HORIZON_ROW, HORIZON_ROW], color=MUTED, lw=0.8, ls=(0, (5, 4)), zorder=1)
    axes[0].text(6, HORIZON_ROW + 5, "120 mm above\nthe table",
                 fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top", zorder=8)
    paint_mask(axes[0], both, GLASS, alpha=0.85)
    trace_mask(axes[0], both)
    corner_note(axes[0], "one patch, and one base\nstanding on the table")

    # 2 — the label.
    frame(axes[1], "the best label a per-pixel network can give")
    paint_mask(axes[1], both, GLASS, alpha=0.8)
    trace_mask(axes[1], both)
    axes[1].text(WIDE / 2, HORIZON_ROW + 45, "glass", color=PAPER, fontsize=LABEL_SIZE + 1,
                 ha="center", va="center", zorder=8)
    corner_note(axes[1], f"one region, {int((both > 0).sum()):,} pixels,\nevery one of them correct")

    # 3 — the truth.
    frame(axes[2], "the truth, which is two glasses")
    paint_mask(axes[2], near_only, MUTED, alpha=0.28)
    trace_mask(axes[2], near_only, colour=MUTED)
    paint_mask(axes[2], far_only, WARN, alpha=0.55, zorder=4)
    trace_mask(axes[2], far_only, colour=WARN, dashed=True)
    corner_note(axes[2], f"the far glass: {int((far_only > 0).sum()):,} pixels of its own,\n"
                f"and {left_over} of them anywhere in\nthe picture", colour=WARN)

    # 4 — the same arrangement in plan, which is where the reason is visible.
    axis = axes[3]
    axis.set_facecolor(PAPER)
    bare(axis)
    axis.set_aspect("equal")
    axis.set_xlim(-120, 780)
    axis.set_ylim(-400, 400)
    axis.set_title("the same arrangement in plan", fontsize=LABEL_SIZE + 0.4, color=INK, pad=7)
    rim = profile(tall)[1].max()
    half_angle = np.arcsin(rim / near_distance)
    reach = 780.0
    axis.fill([0.0, reach, reach], [0.0, reach * np.tan(half_angle), -reach * np.tan(half_angle)],
              facecolor=WARN, alpha=0.12, lw=0, zorder=1)
    for sign in (1, -1):
        axis.plot([0, reach], [0, sign * reach * np.tan(half_angle)], color=WARN, lw=0.9,
                  ls=(0, (4, 3)), zorder=2)
    axis.plot(0, 0, marker="o", color=INK, ms=6, zorder=5)
    axis.text(0, 56, "the camera", fontsize=NOTE_SIZE, color=INK, ha="center", va="bottom")
    for distance, colour in ((near_distance, GLASS), (far_distance, WARN)):
        axis.add_patch(Circle((distance, 0.0), rim, facecolor=colour, alpha=0.85,
                              edgecolor=INK, lw=0.9, zorder=4))
    axis.text(near_distance, -80, f"the near glass,\n{near_distance:.0f} mm away",
              fontsize=NOTE_SIZE, color=INK, ha="center", va="top")
    axis.text(far_distance, 150, f"the far glass,\n{far_distance:.0f} mm away",
              fontsize=NOTE_SIZE, color=WARN, ha="center", va="bottom")
    axis.annotate("", xy=(near_distance, -220), xytext=(far_distance, -220),
                  arrowprops={"arrowstyle": "<|-|>", "color": INK, "lw": 0.9})
    axis.text((near_distance + far_distance) / 2, -235, f"{BEHIND_MM:.0f} mm apart",
              fontsize=NOTE_SIZE, color=INK, ha="center", va="top")
    axis.text(380, 330, "anything standing in this wedge is behind\nthe near glass, however far away it is",
              fontsize=NOTE_SIZE, color=WARN, ha="center", va="center")

    figure.suptitle(
        "Looking level: the near glass covers the far one outright, and the distance between them "
        "makes no difference",
        fontsize=TITLE_SIZE + 1,
        color=INK,
        y=0.97,
    )
    figure.text(
        0.5,
        0.085,
        f"Real projections of the same glass twice, {profile(tall)[0].max():.0f} mm high and "
        f"{2 * rim:.0f} mm across the rim, standing {near_distance:.0f} mm and {far_distance:.0f} mm from "
        f"a camera {VIEW_HEIGHT_MM:.0f} mm above the table looking level.\n"
        "The plan draws the sideways half of the condition. The other half is that the far glass must "
        "reach no higher in the picture than the near one, which a plan cannot show.",
        ha="center",
        va="top",
        fontsize=NOTE_SIZE,
        color=INK,
    )
    figure.subplots_adjust(top=0.84, bottom=0.17, wspace=0.07)
    save(figure, "07-hidden-from-the-side.png")


# --------------------------------------------------------------------------- #
def hidden_report(pair) -> None:
    """Every number the section on complete hiding quotes, worked out from the
    same projections the two figures are drawn from."""
    tall, short = pair
    tall_height = profile(tall)[0].max()
    print()
    print("--- complete hiding, looking straight down ---")
    print(f"    the tall glass: {tall_height:.1f} mm high, {2 * profile(tall)[1].max():.1f} mm across")
    print(f"    the short glass: {profile(short)[0].max():.1f} mm high, "
          f"{2 * profile(short)[1].max():.1f} mm across")
    for height in (100.0, 225.0, tall_height):
        factor = SURVEY_HEIGHT_MM / (SURVEY_HEIGHT_MM - height)
        print(f"    scale factor at {height:6.1f} mm up: {factor:.3f}")
    print(f"    the frame covers {WIDE * MM_PER_PIXEL:.0f} x {TALL * MM_PER_PIXEL:.0f} mm of table at "
          f"{MM_PER_PIXEL:.3f} mm per pixel")
    widest, widest_radius = widest_hiding_gap(tall, short)
    print(f"    widest gap that hides completely, both glasses inside one frame: {widest:.0f} mm, "
          f"with the tall glass {widest_radius:.0f} mm from the nadir")
    on_table_gap, on_table_radius = widest_gap_on_table(tall, short)
    print(f"    widest gap that hides completely, allowing the tall silhouette off the frame's edge: "
          f"{on_table_gap:.0f} mm, tall glass {on_table_radius:.0f} mm out")
    at_minimum = covering_radius(tall, short, MIN_APART_MM)
    print(f"    at the {MIN_APART_MM:.0f} mm this cell guarantees, the tall glass would have to stand "
          f"{at_minimum:.0f} mm from the nadir and the short one {at_minimum + MIN_APART_MM:.0f} mm, "
          f"against a half-frame of {WIDE / 2 * MM_PER_PIXEL:.0f} mm")
    gap = DRAWN_GAP_MM
    radius = covering_radius(tall, short, gap)
    patch = splay_width(splay_stack((radius, 0.0), tall))
    print(f"    the pictures are drawn with the pair {gap:.0f} mm apart and the tall glass "
          f"{radius:.0f} mm from the nadir")
    print(f"    the tall glass's patch there: {patch:.0f} mm = {patch / MM_PER_PIXEL:.0f} px across")
    alone = survey_mask([(radius, 0.0, tall)])
    for degrees in (0, 15, 30, 45, 60, 90):
        angle = np.radians(degrees)
        moved = survey_mask([(radius + gap * np.cos(angle), gap * np.sin(angle), short)])
        print(f"    short glass swung {degrees:3d} degrees off the radius: "
              f"{int(((moved > 0) & (alone == 0)).sum()):5d} of {int((moved > 0).sum())} pixels visible")

    print("--- complete hiding, looking level ---")
    near = level_mask([(0.0, STANDOFF_MM, tall)])
    for behind in (MIN_APART_MM, BEHIND_MM, 600.0):
        far = level_mask([(0.0, STANDOFF_MM + behind, tall)])
        print(f"    the same glass {behind:5.0f} mm behind: "
              f"{int(((far > 0) & (near == 0)).sum())} of {int((far > 0).sum())} pixels visible")
    near_short = level_mask([(0.0, STANDOFF_MM, short)])
    for name, front, back in (
        ("the short glass behind the tall one", tall, short),
        ("the tall glass behind the short one", short, tall),
        ("a short glass behind a short one", short, short),
    ):
        front_mask = near if front is tall else near_short
        back_mask = level_mask([(0.0, STANDOFF_MM + BEHIND_MM, back)])
        print(f"    {name}, {BEHIND_MM:.0f} mm apart: "
              f"{int(((back_mask > 0) & (front_mask == 0)).sum())} of {int((back_mask > 0).sum())} "
              "pixels visible")
    threshold = VIEW_HEIGHT_MM + STANDOFF_MM / (STANDOFF_MM + BEHIND_MM) * (tall_height - VIEW_HEIGHT_MM)
    print(f"    to hide the tallest glass {BEHIND_MM:.0f} mm behind it, the near glass must be at least "
          f"{threshold:.0f} mm high")
    for sideways in (0.0, 20.0, 30.0, 35.0, 40.0):
        moved = level_mask([(sideways, STANDOFF_MM + BEHIND_MM, tall)])
        print(f"    far glass {sideways:4.0f} mm off the line of sight: "
              f"{int(((moved > 0) & (near == 0)).sum())} pixels visible")
    field = encoder_receptive_field(4)
    print(f"    a bottleneck unit sees {field} px: {field * MM_PER_PIXEL:.0f} mm of table from above, "
          f"{field * STANDOFF_MM / FOCAL:.0f} mm at the near glass in the level view")
    print(f"    the near glass is {2 * profile(tall)[1].max() / (STANDOFF_MM / FOCAL):.0f} px wide "
          "in the level view")


# --------------------------------------------------------------------------- #
def report() -> None:
    """Print the arithmetic the document quotes, so the two cannot drift apart."""
    total = unet_weights(NARROW)
    print()
    print(f"weights, widths {NARROW}: {total:,}  ({total * 4 / 1e6:.2f} MB as float32)")
    print(f"weights, widths {DEEPER}: {unet_weights(DEEPER):,}")
    for name, count in unet_blocks(NARROW):
        print(f"    {name:<22} {count:>9,}  {100 * count / total:5.1f}%")
    macs = unet_macs(NARROW)
    print(f"forward pass: {macs / 1e9:.2f} G multiply-accumulates = {2 * macs / 1e9:.2f} GFLOPs per picture")
    print(f"one epoch over 8,000 pictures, forward + backward ~ 3x: {3 * 2 * macs * 8000 / 1e12:.0f} TFLOPs")
    for blocks in (4, 5):
        field = encoder_receptive_field(blocks)
        print(f"{blocks} blocks: bottleneck unit sees {field} px = {field * MM_PER_PIXEL:.0f} mm of table")
    print(f"mm per pixel at survey height: {MM_PER_PIXEL:.3f}")
    edge = SURVEY_HEIGHT_MM / np.cos(np.radians(30.0)) / FOCAL
    extra = 100 * (edge / MM_PER_PIXEL - 1)
    print(f"mm per pixel at the frame's left and right edges: {edge:.3f}  ({extra:.0f}% more)")
    pixels = WIDE * TALL
    per_glass = np.pi * 24.0**2
    share = 5 * per_glass / pixels
    print(f"glass share of pixels, five glasses of 48 px: {100 * share:.1f}%")
    table_term = -np.log(0.98)
    glass_term = -np.log(0.02)
    print(f"cross entropy, p = 0.5 everywhere: {-np.log(0.5):.3f}")
    flat = (1 - share) * table_term + share * glass_term
    print(f"cross entropy, 'table everywhere' at p = 0.02: {flat:.3f}")


if __name__ == "__main__":
    figure_what_is_asked_for()
    figure_scratch_or_fine_tune()
    figure_u_net_shape()
    figure_where_the_weights_are()
    figure_most_pixels_are_table()
    figure_domain_randomisation()
    figure_semantic_against_instance()
    whole, inner, sizes = figure_confidence_map()
    above = figure_hidden_from_above()
    figure_hidden_from_the_side(above["pair"])
    print()
    for name, whole_value, inner_value, size in zip(
        ["A", "B", "C", "D (the pair)"], whole, inner, sizes, strict=True
    ):
        print(f"region {name:<12} {size:>5} px  whole {whole_value:5.1f}%  interior {inner_value:5.1f}%")
    report()
    hidden_report(above["pair"])
