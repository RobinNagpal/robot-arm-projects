"""Pictures for solution 9 — a fine-tuned instance segmenter.

Seven figures, each carrying one point of the document:

    09-class-map-against-instances.png  one label per pixel against one mask per glass
    09-the-two-stages.png               propose regions, then classify and cut a mask
    09-what-a-backbone-brings.png       what arrives already fitted, and why it transfers
    09-fine-tune-against-scratch.png    how many labelled scenes each start needs
    09-boxes-scores-masks.png           what one pass returns, and what the score is for
    09-overlapping-proposals.png        many boxes for one glass, collapsed by overlap
    09-where-it-stops.png               a glass with no pixels is in no output

Run from the project root:

    pixi run python images/generators/problem-2/make_09_images.py

Every scene here is a legal arrangement of the shared cast of glasses: a couple
of large ones and a couple of the smallest this kind allows, with every pair of
centres at least the guaranteed gap apart. The arrangement is checked in code
rather than trusted, and every silhouette is a real splayed projection through
this cell's overhead camera, from ``diagram_style.splay_circles``, so the
overlaps and the one complete cover are geometry rather than drawing.

Every number that appears as a label is arithmetic on those silhouettes, on the
camera's own numbers, or on the constants at the top of this file. The two
training curves are the exception that says so on its own face: they are the
shape of a claim, not a measurement of a trained network.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
from diagram_style import (
    CAST,
    FX,
    GLASS,
    GOOD,
    INK,
    KIND_NARROWEST,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PAPER,
    SHORT_A,
    SHORT_B,
    SURVEY_H,
    TALL_A,
    TALL_B,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
    splay_circles,
    splay_covers,
    splay_width,
)
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, to_rgba
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle

# --------------------------------------------------------------------------- #
# the cell's own numbers, and the few this solution adds
# --------------------------------------------------------------------------- #

FRAME_W, FRAME_H = 320, 240        # the camera's picture, in pixels
MM_PER_PX = SURVEY_H / FX          # how much table one pixel covers, from 450 mm up
MIN_APART = 150.0                  # mm centre to centre, the closest two glasses ever stand

GRID_MM = 2.0                      # the cell size every area and region count is measured on

# The two thresholds this kind of model is steered by. Both are the standard
# ones: boxes overlapping the best box by more than NMS_IOU are dropped, and a
# detection scoring below SCORE_KEEP is not reported.
NMS_IOU = 0.5
SCORE_KEEP = 0.5

# The feature levels a ResNet-and-FPN backbone hands to the two stages. A level
# of stride s turns a picture of W x H pixels into a grid of W/s x H/s.
STRIDES = (4, 8, 16, 32)

# A score is a model output, so no arithmetic here can produce a real one. What
# these pictures show instead is stated on their face: a score read off how much
# of each glass the camera can see and how many pixels it covers, running
# between these two ends.
SCORE_FLOOR = 0.52
SCORE_CEILING = 0.99

# The two training curves. A saturating curve with the same ceiling for both
# starts, because the architecture and the labels are the same either way; only
# the number of labelled scenes it takes to get there differs.
QUALITY_CEILING = 0.88
BORROWED_HALF = 60.0
SCRATCH_HALF = 600.0
CURVE_SHARPNESS = 1.15
USABLE = 0.75                      # the mask quality counted as usable

DEPTH_MAP = LinearSegmentedColormap.from_list("depth", [INK, PAPER])
FILTER_MAP = LinearSegmentedColormap.from_list("filter", [PAPER, INK])

# --------------------------------------------------------------------------- #
# the two scenes these figures share
# --------------------------------------------------------------------------- #

NADIR = np.array([0.0, 0.0])

# Four glasses, two large and two of the smallest the kind allows. One pair
# merges into a single patch in the overhead picture; nothing is covered.
MIXED_PLACES = ((170.0, 60.0), (60.0, -130.0), (-95.0, 150.0), (-205.0, 265.0))

# The same cast, arranged so that the large glass's splayed outline swallows the
# small one whole. This is the case solution 9 has no answer to.
COVER_PLACES = ((185.0, -40.0), (335.0, -70.0), (-95.0, 150.0), (-215.0, 275.0))

NAMES = ("large A", "small A", "large B", "small B")

# How wide the range of sizes in that cast is. The whole difficulty of problem 2
# comes from this ratio, so the figures that lean on it work it out rather than
# stating it.
HEIGHT_SPREAD = max(TALL_A[0], TALL_B[0]) / min(SHORT_A[0], SHORT_B[0])


def scene(places) -> list[dict]:
    """The cast stood at these places, with its silhouettes and boxes worked out."""
    built = []
    for name, place, size in zip(NAMES, places, CAST, strict=True):
        height, rim = size
        circles = splay_circles(NADIR, np.array(place), height, rim)
        built.append(
            {
                "name": name,
                "place": np.array(place, dtype=float),
                "height": height,
                "rim": rim,
                "circles": circles,
                "box": box_of(circles),
                "patch_mm": splay_width(circles),
            }
        )
    check_legal(built)
    return built


def check_legal(built: list[dict]) -> None:
    """Every pair of centres at least the guaranteed gap apart, or this is not a scene."""
    for i, one in enumerate(built):
        for other in built[i + 1 :]:
            apart = float(np.hypot(*(one["place"] - other["place"])))
            if apart < MIN_APART - 1e-9:
                raise ValueError(
                    f"{one['name']} and {other['name']} stand {apart:.0f} mm apart, "
                    f"closer than the guaranteed {MIN_APART:.0f} mm"
                )


# --------------------------------------------------------------------------- #
# arithmetic on the silhouettes
# --------------------------------------------------------------------------- #

def box_of(circles) -> tuple[float, float, float, float]:
    """The smallest upright box round a silhouette, in millimetres of table."""
    left = min(c[0] - r for c, r in circles)
    right = max(c[0] + r for c, r in circles)
    bottom = min(c[1] - r for c, r in circles)
    top = max(c[1] + r for c, r in circles)
    return float(left), float(bottom), float(right), float(top)


def box_area(box) -> float:
    left, bottom, right, top = box
    return max(0.0, right - left) * max(0.0, top - bottom)


def box_overlap(one, other) -> tuple[float, float, float]:
    """Intersection, union and their ratio for two boxes, in square millimetres."""
    left = max(one[0], other[0])
    bottom = max(one[1], other[1])
    right = min(one[2], other[2])
    top = min(one[3], other[3])
    inter = box_area((left, bottom, right, top))
    union = box_area(one) + box_area(other) - inter
    return inter, union, (inter / union if union > 0 else 0.0)


def limits_of(built: list[dict], pad: float = 34.0):
    """A window that holds every silhouette in the scene, and the nadir with it."""
    boxes = [one["box"] for one in built]
    left = min(box[0] for box in boxes)
    bottom = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    top = max(box[3] for box in boxes)
    return (
        min(left, 0.0) - pad,
        max(right, 0.0) + pad,
        min(bottom, 0.0) - pad,
        max(top, 0.0) + pad,
    )


def grid_of(limits):
    """The cell centres a raster of this window sits on."""
    left, right, bottom, top = limits
    xs = np.arange(left + GRID_MM / 2.0, right, GRID_MM)
    ys = np.arange(bottom + GRID_MM / 2.0, top, GRID_MM)
    return np.meshgrid(xs, ys)


def raster(circles, mesh) -> np.ndarray:
    """Which cells of the window a silhouette covers."""
    gx, gy = mesh
    covered = np.zeros(gx.shape, dtype=bool)
    for centre, radius in circles:
        covered |= (gx - centre[0]) ** 2 + (gy - centre[1]) ** 2 <= radius * radius
    return covered


def region_count(mask: np.ndarray) -> int:
    """How many separate patches a mask falls into."""
    count, _ = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return count - 1


def regions_of(mask: np.ndarray):
    """The separate patches a mask falls into, as a label image."""
    count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    return count - 1, labels


def middle_of(mask: np.ndarray, mesh) -> tuple[float, float]:
    """The middle of a set of cells, in millimetres of table."""
    gx, gy = mesh
    return float(gx[mask].mean()), float(gy[mask].mean())


def height_map(built: list[dict], mesh) -> np.ndarray:
    """How high above the table the nearest surface is, cell by cell.

    This is what the cell's renderer hands over, turned the way round the model
    is fed: the depth reading shaded into a grey picture. A tall glass's rim is
    nearest the lens, so it comes out brightest.
    """
    gx, gy = mesh
    tallest = np.zeros(gx.shape)
    for one in built:
        circles = one["circles"]
        last = len(circles) - 1
        for index, (centre, radius) in enumerate(circles):
            z = one["height"] * index / last
            inside = (gx - centre[0]) ** 2 + (gy - centre[1]) ** 2 <= radius * radius
            tallest = np.where(inside & (z > tallest), z, tallest)
    return tallest


def own_pixels(masks: list[np.ndarray], heights: list[float]) -> list[np.ndarray]:
    """The cells each glass keeps once the taller glasses in front have taken theirs."""
    kept = []
    for index, mask in enumerate(masks):
        blocked = np.zeros(mask.shape, dtype=bool)
        for other, other_mask in enumerate(masks):
            if other != index and heights[other] > heights[index]:
                blocked |= other_mask
        kept.append(mask & ~blocked)
    return kept


def score_of(visible: float, pixels: float) -> float:
    """A stand-in score: more of the glass in view, and more pixels to go on, means surer.

    A real score comes out of the model, so nothing here can produce one. This
    is arithmetic on the silhouettes instead, and every figure that shows a
    score says so. The pixel count is compared against the patch the narrowest
    glass of this kind would cover on its own.
    """
    return (
        SCORE_FLOOR
        + (SCORE_CEILING - SCORE_FLOOR) * visible * pixels / (pixels + EVIDENCE_PX)
    )


def as_pixels(area_mm2: float) -> float:
    """Square millimetres of table turned into pixels of an overhead picture."""
    return area_mm2 / (MM_PER_PX**2)


EVIDENCE_PX = as_pixels(math.pi * (KIND_NARROWEST / 2.0) ** 2)


def quality(scenes, half: float) -> np.ndarray:
    """Mask quality against the number of labelled scenes trained on."""
    power = np.asarray(scenes, dtype=float) ** CURVE_SHARPNESS
    return QUALITY_CEILING * power / (power + half**CURVE_SHARPNESS)


def scenes_for(level: float, half: float) -> float:
    """How many labelled scenes this start needs to reach a given mask quality."""
    ratio = level / (QUALITY_CEILING - level)
    return half * ratio ** (1.0 / CURVE_SHARPNESS)


def nms(boxes, scores, threshold=NMS_IOU):
    """Keep the best box, drop what overlaps it too much, repeat."""
    order = sorted(range(len(boxes)), key=lambda index: -scores[index])
    kept, dropped = [], []
    while order:
        best = order.pop(0)
        kept.append(best)
        survivors = []
        for index in order:
            if box_overlap(boxes[best], boxes[index])[2] > threshold:
                dropped.append((index, best))
            else:
                survivors.append(index)
        order = survivors
    return kept, dropped


# --------------------------------------------------------------------------- #
# small shared drawing helpers
# --------------------------------------------------------------------------- #

def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, ha="left", va="top", **kwargs) -> None:
    axis.text(x, y, text, color=colour, fontsize=size, ha=ha, va=va, zorder=9, **kwargs)


def panel_title(axis, text, colour=INK) -> None:
    axis.set_title(text, fontsize=LABEL_SIZE + 0.6, color=colour, pad=8)


def rounded(axis, left, bottom, width, height, label="", face=None, edge=INK,
            size=LABEL_SIZE, text_colour=INK, lw=1.1, alpha=1.0, zorder=3):
    """A rounded box with a label in the middle of it."""
    axis.add_patch(
        FancyBboxPatch(
            (left, bottom),
            width,
            height,
            boxstyle="round,pad=0.0,rounding_size=0.018",
            facecolor=to_rgba(face, alpha) if face is not None else "none",
            edgecolor=edge,
            lw=lw,
            zorder=zorder,
        )
    )
    if label:
        axis.text(
            left + width / 2.0,
            bottom + height / 2.0,
            label,
            ha="center",
            va="center",
            fontsize=size,
            color=text_colour,
            zorder=zorder + 1,
        )
    return left + width / 2.0, bottom + height / 2.0


def arrow(axis, start, end, colour=INK, lw=1.2, dashed=False, zorder=6, shrink=2.0) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            color=colour,
            lw=lw,
            linestyle=(0, (4, 3)) if dashed else "solid",
            shrinkA=shrink,
            shrinkB=shrink,
            zorder=zorder,
        )
    )


def between_panels(figure, left_axis, right_axis, height=0.5, colour=INK) -> None:
    """One arrow from the right edge of one panel to the left edge of the next."""
    left = left_axis.get_position()
    right = right_axis.get_position()
    figure.add_artist(
        FancyArrowPatch(
            (left.x1 + 0.006, left.y0 + height * (left.y1 - left.y0)),
            (right.x0 - 0.006, right.y0 + height * (right.y1 - right.y0)),
            transform=figure.transFigure,
            arrowstyle="-|>",
            mutation_scale=15,
            color=colour,
            lw=1.5,
            shrinkA=0,
            shrinkB=0,
        )
    )


def table_axis(axis, limits, nadir=True) -> None:
    """A plan view of the table in millimetres, with the point below the camera marked."""
    bare(axis)
    axis.set_aspect("equal")
    axis.set_xlim(limits[0], limits[1])
    axis.set_ylim(limits[2], limits[3])
    if nadir:
        axis.scatter([0], [0], s=36, color=WARN, marker="x", zorder=10, linewidths=1.4)


def silhouette(axis, circles, colour=GLASS, alpha=0.30, zorder=3) -> None:
    """A splayed outline drawn as the stack of circles it really is."""
    for centre, radius in circles:
        axis.add_patch(
            Circle(tuple(centre), radius, facecolor=to_rgba(colour, alpha),
                   edgecolor="none", zorder=zorder)
        )


def footprint(axis, place, rim, colour=GLASS, alpha=0.55, zorder=3) -> None:
    """What a glass really occupies on the table: the circle its base stands in."""
    axis.add_patch(
        Circle(tuple(place), rim / 2.0, facecolor=to_rgba(colour, 0.22),
               edgecolor=colour, lw=1.2, zorder=zorder)
    )
    axis.add_patch(
        Circle(tuple(place), rim / 2.0 * 0.45, facecolor=to_rgba(colour, alpha),
               edgecolor="none", zorder=zorder + 1)
    )


def draw_box(axis, box, colour=INK, lw=1.3, dashed=False, zorder=7) -> None:
    left, bottom, right, top = box
    axis.add_patch(
        Rectangle(
            (left, bottom),
            right - left,
            top - bottom,
            facecolor="none",
            edgecolor=colour,
            lw=lw,
            linestyle=(0, (4, 3)) if dashed else "solid",
            zorder=zorder,
        )
    )


def show_mask(axis, mask, limits, colour, alpha=0.85, zorder=4) -> None:
    axis.imshow(
        np.ma.masked_where(~mask, mask.astype(float)),
        cmap=ListedColormap([to_rgba(colour, alpha)]),
        extent=(limits[0], limits[1], limits[2], limits[3]),
        origin="lower",
        interpolation="nearest",
        vmin=0.0,
        vmax=1.0,
        zorder=zorder,
    )


def grey_picture(axis, built, limits, mesh) -> np.ndarray:
    """The picture the model is actually fed: depth shaded into grey."""
    tallest = height_map(built, mesh)
    axis.imshow(
        tallest,
        cmap=DEPTH_MAP,
        extent=(limits[0], limits[1], limits[2], limits[3]),
        origin="lower",
        interpolation="nearest",
        vmin=-0.45 * max(one["height"] for one in built),
        vmax=max(one["height"] for one in built),
        zorder=1,
    )
    return tallest


def crop(axis, rect, circles, colour=GLASS, alpha=0.75, box_colour=INK, margin=0.10):
    """Draw one silhouette scaled to fit a rectangle of the axis, with its box."""
    left, bottom, width, height = rect
    box = box_of(circles)
    span = max(box[2] - box[0], box[3] - box[1])
    scale = min(width, height) * (1.0 - 2.0 * margin) / span
    mid_x = (box[0] + box[2]) / 2.0
    mid_y = (box[1] + box[3]) / 2.0
    to_x = left + width / 2.0
    to_y = bottom + height / 2.0
    for centre, radius in circles:
        axis.add_patch(
            Circle(
                (to_x + (centre[0] - mid_x) * scale, to_y + (centre[1] - mid_y) * scale),
                radius * scale,
                facecolor=to_rgba(colour, alpha),
                edgecolor="none",
                zorder=5,
            )
        )
    axis.add_patch(
        Rectangle(
            (to_x + (box[0] - mid_x) * scale, to_y + (box[1] - mid_y) * scale),
            (box[2] - box[0]) * scale,
            (box[3] - box[1]) * scale,
            facecolor="none",
            edgecolor=box_colour,
            lw=1.1,
            zorder=6,
        )
    )
    return to_x, to_y, scale


# --------------------------------------------------------------------------- #
# 1. one label per pixel, against one mask per glass
# --------------------------------------------------------------------------- #

def figure_class_map_against_instances() -> None:
    """The difference the whole solution rests on, on one scene."""
    built = scene(MIXED_PLACES)
    limits = limits_of(built)
    mesh = grid_of(limits)
    masks = [raster(one["circles"], mesh) for one in built]
    heights = [one["height"] for one in built]
    everything = np.logical_or.reduce(masks)
    patches = region_count(everything)
    kept = own_pixels(masks, heights)

    # which pair ran together, and by how many cells
    merged = []
    for i in range(len(masks)):
        for j in range(i + 1, len(masks)):
            shared = int((masks[i] & masks[j]).sum())
            if shared:
                merged.append((built[i]["name"], built[j]["name"], shared))

    figure, axes = new(14.6, 5.1, columns=3)
    for axis in axes:
        table_axis(axis, limits)

    # ------------------------------------------------ the picture that goes in
    grey_picture(axes[0], built, limits, mesh)
    panel_title(axes[0], "What goes in: one grey picture from the top")
    paper_box = {"boxstyle": "round,pad=0.30", "facecolor": PAPER,
                 "edgecolor": "none", "alpha": 0.88}
    note(axes[0], limits[0] + 12, limits[3] - 10,
         f"{len(built)} glasses of one kind: two large, two of the\n"
         f"smallest the kind allows, the tall end {HEIGHT_SPREAD:.1f} times\n"
         f"the height of the short end. No two centres are\n"
         f"closer than {MIN_APART:.0f} mm.", colour=INK, bbox=paper_box)
    note(axes[0], limits[0] + 12, limits[2] + 12,
         "The renderer gives depth, not colour, so the picture is\n"
         "that depth shaded into grey and repeated across three\n"
         "channels. Brighter is nearer the lens, which is why the\n"
         "tall rims glow.",
         colour=WARN, va="bottom", bbox=paper_box)
    note(axes[0], 14, -14, "camera", colour=WARN, bbox=paper_box)

    # ------------------------------------------------------------ the class map
    show_mask(axes[1], everything, limits, WARN, alpha=0.80)
    panel_title(axes[1], f"A class map: {patches} regions for {len(built)} glasses", colour=WARN)
    _, labelled = regions_of(everything)
    for region in range(1, patches + 1):
        spot = middle_of(labelled == region, mesh)
        axes[1].text(spot[0], spot[1], "glass", ha="center", va="center",
                     fontsize=LABEL_SIZE, color=PAPER, zorder=8)
    pair = merged[0]
    junction = middle_of(masks[2] & masks[3], mesh)
    # a line under the merged region, so the note never lies on top of it
    under_pair = min(built[2]["box"][1], built[3]["box"][1]) - 34.0
    axes[1].annotate(
        f"{pair[0]} and {pair[1]} run together: one region,\ntwo glasses, one word over both of them.\n"
        "A class label has no room in it for which glass.",
        xy=junction,
        xytext=(limits[0] + 14, under_pair),
        fontsize=NOTE_SIZE, color=WARN, ha="left", va="top",
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )
    note(axes[1], limits[1] - 12, limits[3] - 10,
         "Every glass pixel carries\nthe same one word, so the\ntwo that touch cannot be\ntold apart.",
         colour=WARN, ha="right")

    # -------------------------------------------------------- instance masks
    instance_colours = (GLASS, GOOD, GLASS, GOOD)
    instance_alphas = (0.88, 0.88, 0.48, 0.48)
    panel_title(axes[2], f"Instance masks: {len(kept)} masks for {len(built)} glasses", colour=GOOD)
    for index, (one, mask) in enumerate(zip(built, kept, strict=True)):
        show_mask(axes[2], mask, limits, instance_colours[index], alpha=instance_alphas[index])
        draw_box(axes[2], one["box"], colour=INK, lw=0.9, dashed=True)
        spot = middle_of(mask, mesh)
        axes[2].text(spot[0], spot[1], f"#{index + 1}", ha="center", va="center",
                     fontsize=LABEL_SIZE + 1, color=INK, zorder=8,
                     bbox={"boxstyle": "round,pad=0.18", "facecolor": PAPER,
                           "edgecolor": "none", "alpha": 0.80})
    axes[2].annotate(
        f"the same pair, separated: the {pair[2] * GRID_MM**2 / 100.0:.0f} cm2 the two\n"
        "outlines share goes to the glass in front, and\neach glass keeps a mask and a box of its own.",
        xy=junction,
        xytext=(limits[0] + 14, under_pair),
        fontsize=NOTE_SIZE, color=GOOD, ha="left", va="top",
        arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 1.0},
    )
    note(axes[2], limits[1] - 12, limits[3] - 10,
         "One mask per glass, each with\nits own box. This is what\nproblem 2 asks for.",
         colour=GOOD, ha="right")

    figure.suptitle(
        "Why an instance segmenter and not a class map: the arm has to pick one glass, "
        "not a region of glass",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.01,
    )
    figure.tight_layout()
    print(f"  scene: {patches} regions, {len(built)} glasses, merged pairs {merged}")
    save(figure, "09-class-map-against-instances.png")


# --------------------------------------------------------------------------- #
# 2. the two stages
# --------------------------------------------------------------------------- #

def proposals_over(built, limits, count_per_glass=2, spread=0.22, seed=20260930):
    """Boxes near each glass, plus a few over bare table: what stage one suggests."""
    rng = np.random.default_rng(seed)
    boxes = []
    for one in built:
        left, bottom, right, top = one["box"]
        width, height = right - left, top - bottom
        for _ in range(count_per_glass):
            shift_x = rng.normal(0.0, spread * width)
            shift_y = rng.normal(0.0, spread * height)
            grow = 1.0 + rng.normal(0.0, spread)
            half_w, half_h = width * grow / 2.0, height * grow / 2.0
            mid_x, mid_y = (left + right) / 2.0 + shift_x, (bottom + top) / 2.0 + shift_y
            boxes.append((mid_x - half_w, mid_y - half_h, mid_x + half_w, mid_y + half_h))
    for _ in range(3):
        mid_x = rng.uniform(limits[0] + 60.0, limits[1] - 60.0)
        mid_y = rng.uniform(limits[2] + 60.0, limits[3] - 60.0)
        half = rng.uniform(40.0, 70.0)
        boxes.append((mid_x - half, mid_y - half, mid_x + half, mid_y + half))
    return boxes


def figure_the_two_stages() -> None:
    """Stage one proposes, stage two decides and cuts a mask inside each box."""
    built = scene(MIXED_PLACES)
    limits = limits_of(built)
    mesh = grid_of(limits)
    masks = [raster(one["circles"], mesh) for one in built]
    heights = [one["height"] for one in built]
    kept_masks = own_pixels(masks, heights)
    boxes = proposals_over(built, limits)
    on_glass = [
        box for box in boxes
        if any(box_overlap(box, one["box"])[2] > 0.25 for one in built)
    ]
    empty = len(boxes) - len(on_glass)

    scores = []
    for mask, kept in zip(masks, kept_masks, strict=True):
        visible = float(kept.sum()) / float(mask.sum())
        scores.append(score_of(visible, as_pixels(float(kept.sum()) * GRID_MM**2)))

    paper_box = {"boxstyle": "round,pad=0.30", "facecolor": PAPER,
                 "edgecolor": "none", "alpha": 0.88}
    figure, axes = new(17.4, 4.5, columns=4)
    for axis in [axes[0], axes[1], axes[3]]:
        table_axis(axis, limits)

    # ----------------------------------------------------------- the picture in
    grey_picture(axes[0], built, limits, mesh)
    panel_title(axes[0], "the picture, from the top")
    note(axes[0], limits[0] + 12, limits[2] + 12,
         f"{FRAME_W} x {FRAME_H} pixels of shaded depth.\nNo boxes, no labels, nothing found yet.",
         colour=INK, va="bottom", bbox=paper_box)
    note(axes[0], 14, -14, "camera", colour=WARN, bbox=paper_box)

    # ------------------------------------------------- stage one: propose boxes
    for one in built:
        silhouette(axes[1], one["circles"], colour=MUTED, alpha=0.18, zorder=2)
    for box in boxes:
        on = any(box_overlap(box, one["box"])[2] > 0.25 for one in built)
        draw_box(axes[1], box, colour=INK if on else MUTED, lw=0.9, dashed=not on, zorder=5)
    panel_title(axes[1], "stage one: where might something be?")
    note(axes[1], limits[1] - 12, limits[3] - 10,
         f"{len(boxes)} boxes leave this stage:\n"
         f"{len(on_glass)} on a glass, {empty} on bare table.\n"
         "The only question asked of each\n"
         "is \"object or table?\" — never\nwhich object.",
         colour=INK, ha="right", bbox=paper_box)
    note(axes[1], limits[0] + 12, limits[2] + 12,
         "Several boxes for the same glass is\nnormal here, and the next figure\nclears it up.",
         colour=MUTED, va="bottom", bbox=paper_box)

    # ---------------------------------- stage two: classify, and cut a mask
    bare(axes[2])
    axes[2].set_xlim(0, 1)
    axes[2].set_ylim(0, 1)
    panel_title(axes[2], "stage two: one kept box at a time")
    order = sorted(range(len(built)), key=lambda index: -scores[index])[:3]
    for row, index in enumerate(order):
        bottom = 0.735 - row * 0.215
        rounded(axes[2], 0.03, bottom, 0.94, 0.185, face=MUTED, edge=MUTED, alpha=0.07, lw=0.8)
        crop(axes[2], (0.05, bottom + 0.012, 0.185, 0.162), built[index]["circles"],
             colour=GLASS, alpha=0.75)
        axes[2].text(0.27, bottom + 0.124, f"class: glass, score {scores[index]:.2f}",
                     fontsize=NOTE_SIZE, color=INK, va="center", zorder=7)
        axes[2].text(0.27, bottom + 0.058,
                     f"a mask cut inside this box: "
                     f"{as_pixels(box_area(built[index]['box'])):.0f} pixels to decide",
                     fontsize=NOTE_SIZE, color=MUTED, va="center", zorder=7)
    note(axes[2], 0.03, 0.03,
         "Each kept box is cropped out of the shared feature map and asked\n"
         "two questions: what is in it, and which of its pixels belong to\n"
         "that thing. Because every mask is cut inside one box, two glasses\n"
         "that touch in the picture get one mask each, with no rule written\nfor it anywhere.",
         colour=INK, va="bottom")

    # ------------------------------------------------------------- the output
    ceiling = (max(heights) + min(heights)) / 2.0
    for index, (one, mask) in enumerate(zip(built, kept_masks, strict=True)):
        show_mask(axes[3], mask, limits, GLASS if index % 2 == 0 else GOOD, alpha=0.80)
        draw_box(axes[3], one["box"], colour=INK, lw=0.9, dashed=True)
        above = one["height"] > ceiling
        axes[3].text(
            one["box"][0], one["box"][3] + 8.0 if above else one["box"][1] - 8.0,
            f"{scores[index]:.2f}", ha="left", va="bottom" if above else "top",
            fontsize=NOTE_SIZE, color=INK, zorder=9, bbox=paper_box,
        )
    panel_title(axes[3], f"out: {len(built)} boxes, scores and masks", colour=GOOD)
    note(axes[3], limits[0] + 12, limits[2] + 12,
         "One pass. No clustering,\nno circle fit, no grouping\ndistance anywhere.",
         colour=GOOD, va="bottom", bbox=paper_box)

    figure.suptitle(
        "Mask R-CNN in two stages: propose regions, then classify each one and cut a mask inside it",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.04,
    )
    figure.tight_layout()
    # the drawing panels keep a square aspect, so the schematic one is pulled to
    # the same height and its title lines up with theirs
    reference = axes[0].get_position()
    place = axes[2].get_position()
    axes[2].set_position([place.x0, reference.y0, place.width, reference.height])
    for left_axis, right_axis in zip(axes[:-1], axes[1:], strict=True):
        between_panels(figure, left_axis, right_axis)
    figure.text(
        0.5, -0.02,
        "The scores in this picture are not a measurement of a trained network. Each one is read off how "
        "much of that glass the camera can see and how many pixels it covers,\n"
        f"between {SCORE_FLOOR:.2f} and {SCORE_CEILING:.2f}, so that the shape of the output is honest "
        "even though the numbers in it are arithmetic on the silhouettes.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    print(f"  stages: {len(boxes)} proposals, {len(on_glass)} on a glass, "
          f"scores {[round(s, 2) for s in scores]}")
    save(figure, "09-the-two-stages.png")


# --------------------------------------------------------------------------- #
# 3. what a backbone brings
# --------------------------------------------------------------------------- #

def edge_tile(angle_deg: float, softness: float = 0.16, size: int = 56) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    angle = math.radians(angle_deg)
    along = x * math.cos(angle) + y * math.sin(angle)
    return 1.0 / (1.0 + np.exp(-along / softness))


def grating_tile(angle_deg: float, cycles: float = 3.5, size: int = 56) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    angle = math.radians(angle_deg)
    along = x * math.cos(angle) + y * math.sin(angle)
    return 0.5 + 0.5 * np.sin(cycles * math.pi * along)


def corner_tile(size: int = 56) -> np.ndarray:
    return np.minimum(edge_tile(20.0, size=size), edge_tile(115.0, size=size))


def arc_tile(size: int = 56) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    radius = np.hypot(x + 0.35, y + 0.35)
    return np.clip(1.0 - np.abs(radius - 0.95) / 0.22, 0.0, 1.0)


def ring_tile(size: int = 56) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    radius = np.hypot(x, y)
    return np.clip(1.0 - np.abs(radius - 0.62) / 0.18, 0.0, 1.0) * 0.9 + 0.1 * (radius < 0.62)


def taper_tile(size: int = 56) -> np.ndarray:
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    half = 0.34 + 0.30 * (y + 1.0) / 2.0
    return np.where(np.abs(x) <= half, 0.85, 0.06)


def scene_tile(size: int = 56) -> np.ndarray:
    """A stand-in for an everyday photograph: several things, several edges."""
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    out = np.full(x.shape, 0.30)
    out = np.where(y < -0.45, 0.62, out)
    out = np.where((np.abs(x + 0.45) < 0.28) & (y < 0.30), 0.86, out)
    out = np.where(np.hypot(x - 0.42, y - 0.18) < 0.30, 0.10, out)
    out = np.where((np.abs(x - 0.05) < 0.10) & (np.abs(y - 0.62) < 0.22), 0.70, out)
    return out


def depth_tile(size: int = 56) -> np.ndarray:
    """A stand-in for this cell's picture: grey shaded from depth, no colour in it."""
    axis = np.linspace(-1.0, 1.0, size)
    x, y = np.meshgrid(axis, axis)
    out = np.full(x.shape, 0.22)
    for centre_x, centre_y, radius, level in (
        (-0.40, -0.10, 0.34, 0.92),
        (0.38, 0.30, 0.24, 0.62),
        (0.20, -0.58, 0.20, 0.50),
    ):
        out = np.where(np.hypot(x - centre_x, y - centre_y) < radius, level, out)
    return out


def tile(axis, array, left, bottom, width, height, cmap=FILTER_MAP, edge=INK, lw=0.7) -> None:
    """A small picture at this place on a 0-to-1 axis, with a frame round it."""
    axis.imshow(array, cmap=cmap, extent=(left, left + width, bottom, bottom + height),
                origin="lower", aspect="auto", vmin=0.0, vmax=1.0, zorder=4)
    axis.add_patch(Rectangle((left, bottom), width, height, facecolor="none",
                             edgecolor=edge, lw=lw, zorder=5))


def figure_what_a_backbone_brings() -> None:
    """The early layers are the part worth borrowing, whatever the pictures are of."""
    wide, high = 14.2, 6.6
    square = high / wide          # a fraction of the width, as a fraction of the height
    figure, axis = new(wide, high)
    bare(axis)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)

    sizes = [(math.ceil(FRAME_W / stride), math.ceil(FRAME_H / stride)) for stride in STRIDES]
    blocks = (
        ("early", "edges and simple\ntexture", (edge_tile(25.0), grating_tile(70.0)), GOOD),
        ("next", "corners and\nshort curves", (corner_tile(), arc_tile()), GOOD),
        ("later", "parts: a rim,\na tapering wall", (ring_tile(), taper_tile()), GLASS),
        ("last", "whole objects,\nand where they sit", (depth_tile(), scene_tile()), GLASS),
    )

    # the two kinds of picture that can be fed to the same early layers
    thumb_w = 0.105
    thumb_h = thumb_w * FRAME_H / FRAME_W / square
    inputs = (
        (0.700, scene_tile(),
         "photographs of everyday\nthings: what the\nweights were fitted on", MUTED),
        (0.315, depth_tile(),
         f"this cell's picture: depth shaded\ninto grey, {FRAME_W} x {FRAME_H}, three channels", WARN),
    )
    for bottom, array, caption, colour in inputs:
        tile(axis, array, 0.030, bottom, thumb_w, thumb_h, edge=colour, lw=1.0)
        axis.text(0.030, bottom - 0.018, caption, ha="left", va="top",
                  fontsize=NOTE_SIZE, color=colour, zorder=6)

    block_left = 0.265
    block_width = 0.115
    block_gap = 0.058
    block_bottom, block_height = 0.450, 0.140
    tile_w = 0.050
    tile_h = tile_w / square
    tile_bottom = 0.660
    for index, (name, responds, tiles, colour) in enumerate(blocks):
        left = block_left + index * (block_width + block_gap)
        across, down = sizes[index]
        rounded(
            axis, left, block_bottom, block_width, block_height,
            label=f"{name}\n{across} x {down}\nstride {STRIDES[index]}",
            face=colour, edge=colour, alpha=0.13, size=NOTE_SIZE + 0.3,
        )
        for which, array in enumerate(tiles):
            tile(axis, array, left + 0.004 + which * (tile_w + 0.007), tile_bottom, tile_w, tile_h)
        axis.text(left + block_width / 2.0, tile_bottom + tile_h + 0.022, responds,
                  ha="center", va="bottom", fontsize=NOTE_SIZE, color=INK, zorder=6)
        if index:
            previous_left = block_left + (index - 1) * (block_width + block_gap)
            arrow(axis,
                  (previous_left + block_width + 0.004, block_bottom + block_height / 2.0),
                  (left - 0.004, block_bottom + block_height / 2.0), colour=INK, lw=1.3)

    for bottom, _, _, _ in inputs:
        arrow(axis, (0.030 + thumb_w + 0.006, bottom + thumb_h / 2.0),
              (block_left - 0.006, block_bottom + block_height / 2.0), colour=MUTED, lw=1.1)

    # the two halves of the claim, bracketed under the blocks
    borrowed_right = block_left + 2 * block_width + block_gap
    refitted_left = block_left + 2 * (block_width + block_gap)
    refitted_right = block_left + 4 * block_width + 3 * block_gap
    bands = (
        (block_left, borrowed_right, GOOD,
         "worth reusing whatever the pictures are of:\nan edge is an edge in a photograph and in\n"
         "a grey depth picture alike"),
        (refitted_left, refitted_right, GLASS,
         "what fine-tuning mostly changes:\nthese layers have to learn this kind\n"
         "of glass, from this height"),
    )
    for left, right, colour, caption in bands:
        axis.plot([left, right], [0.412, 0.412], color=colour, lw=2.0, zorder=5)
        for end in (left, right):
            axis.plot([end, end], [0.412, 0.430], color=colour, lw=2.0, zorder=5)
        axis.text((left + right) / 2.0, 0.392, caption, ha="center", va="top",
                  fontsize=NOTE_SIZE, color=colour, zorder=6)

    axis.text(
        0.030, 0.205,
        "A backbone is the stack of layers every box and every mask is read out of. Borrowing one means "
        "starting from\nweights somebody else fitted to a very large set of photographs, instead of "
        "starting from random numbers.",
        ha="left", va="top", fontsize=LABEL_SIZE, color=INK, zorder=6,
    )
    axis.text(
        0.030, 0.118,
        "The early layers are the bargain. What they respond to — a step in brightness, a repeating "
        "texture — is in every\npicture ever taken, so those weights are already right here and are "
        "barely moved by training.",
        ha="left", va="top", fontsize=LABEL_SIZE, color=GOOD, zorder=6,
    )
    axis.text(
        0.030, 0.031,
        "The honest part: the weights were fitted on colour photographs and this cell has no colour, only "
        "depth shaded\ninto grey. The later layers carry most of that mismatch, and they are exactly the "
        "ones fine-tuning re-fits.",
        ha="left", va="top", fontsize=LABEL_SIZE, color=WARN, zorder=6,
    )
    axis.set_title(
        "What a borrowed backbone brings: layers that already respond to edges, before any glass is seen",
        fontsize=TITLE_SIZE + 1, color=INK, pad=12,
    )
    print(f"  backbone: feature grids {sizes} from {FRAME_W} x {FRAME_H}")
    save(figure, "09-what-a-backbone-brings.png")


# --------------------------------------------------------------------------- #
# 4. fine-tuning against a random start
# --------------------------------------------------------------------------- #

def figure_fine_tune_against_scratch() -> None:
    """How many labelled scenes each start needs before the masks are usable."""
    figure, axes = new(13.4, 5.6, columns=2)
    curve, bars = axes
    figure.patch.set_facecolor(PAPER)

    counts = np.linspace(1.0, 3000.0, 600)
    borrowed = quality(counts, BORROWED_HALF)
    scratch = quality(counts, SCRATCH_HALF)
    need_borrowed = scenes_for(USABLE, BORROWED_HALF)
    need_scratch = scenes_for(USABLE, SCRATCH_HALF)

    curve.plot(counts, borrowed, color=GOOD, lw=2.2, zorder=5)
    curve.plot(counts, scratch, color=GLASS, lw=2.2, zorder=5)
    curve.axhline(USABLE, color=MUTED, lw=1.4, ls=(0, (5, 4)), zorder=3)
    curve.axhline(QUALITY_CEILING, color=MUTED, lw=1.0, ls=(0, (2, 3)), zorder=3)
    for value, colour, side in ((need_borrowed, GOOD, 1.0), (need_scratch, GLASS, -1.0)):
        curve.plot([value, value], [0.0, USABLE], color=colour, lw=1.2, ls=(0, (3, 3)), zorder=4)
        curve.plot([value], [USABLE], marker="o", ms=6, color=colour, zorder=6)
        curve.text(value + side * 55.0, 0.60, f"{value:.0f} scenes",
                   ha="left" if side > 0 else "right", va="center",
                   fontsize=NOTE_SIZE, color=colour, zorder=7)
    curve.text(2960, borrowed[-1] - 0.045, "fine-tuned from borrowed weights",
               ha="right", va="top", fontsize=LABEL_SIZE, color=GOOD)
    curve.text(2960, scratch[-1] - 0.045, "trained from a random start",
               ha="right", va="top", fontsize=LABEL_SIZE, color=GLASS)
    curve.text(820, USABLE + 0.014, f"usable: an overlap of {USABLE:.2f}",
               ha="left", va="bottom", fontsize=NOTE_SIZE, color=MUTED)
    curve.text(30, QUALITY_CEILING + 0.012,
               f"the same ceiling for both: {QUALITY_CEILING:.2f}",
               ha="left", va="bottom", fontsize=NOTE_SIZE, color=MUTED)

    curve.set_xlim(-40, 3060)
    curve.set_ylim(0.0, 1.0)
    curve.set_xlabel("labelled scenes trained on", fontsize=LABEL_SIZE, color=INK)
    curve.set_ylabel("mask quality: mean overlap between predicted and true mask",
                     fontsize=LABEL_SIZE, color=INK)
    curve.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
    for side in ("top", "right"):
        curve.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        curve.spines[side].set_color(MUTED)
        curve.spines[side].set_linewidth(0.8)
    curve.grid(axis="y", color=MUTED, alpha=0.18, lw=0.7)
    curve.set_axisbelow(True)
    curve.set_title("Mask quality against the number of labelled scenes",
                    fontsize=TITLE_SIZE, color=INK, pad=10)
    curve.text(
        0.885, 0.02,
        "ILLUSTRATIVE — the shape of the claim, not a measurement. Both\n"
        "curves are one saturating formula with one number changed,\n"
        "and nothing here has been trained.",
        transform=curve.transAxes, ha="right", va="bottom", fontsize=NOTE_SIZE, color=WARN,
    )

    # -------------------------------------------------- the same thing as bars
    labels = ("fine-tuned from\nborrowed weights", "trained from\na random start")
    values = (need_borrowed, need_scratch)
    colours = (GOOD, GLASS)
    positions = (0.0, 1.0)
    bars.bar(positions, values, width=0.5, color=[to_rgba(c, 0.75) for c in colours],
             edgecolor=colours, lw=1.2, zorder=4)
    for position, value, colour in zip(positions, values, colours, strict=True):
        bars.text(position, value + need_scratch * 0.02, f"{value:.0f} scenes", ha="center",
                  va="bottom", fontsize=LABEL_SIZE, color=colour, zorder=6)
    bars.set_xticks(list(positions))
    bars.set_xticklabels(labels, fontsize=LABEL_SIZE, color=INK)
    bars.set_ylim(0, need_scratch * 1.22)
    bars.set_ylabel(f"labelled scenes needed to reach a mask quality of {USABLE:.2f}",
                    fontsize=LABEL_SIZE, color=INK)
    bars.tick_params(axis="y", labelsize=NOTE_SIZE, colors=MUTED)
    bars.tick_params(axis="x", length=0, colors=INK, labelsize=LABEL_SIZE)
    for side in ("top", "right"):
        bars.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        bars.spines[side].set_color(MUTED)
        bars.spines[side].set_linewidth(0.8)
    bars.grid(axis="y", color=MUTED, alpha=0.18, lw=0.7)
    bars.set_axisbelow(True)
    bars.set_title("The same two numbers, side by side", fontsize=TITLE_SIZE, color=INK, pad=10)
    bars.text(
        0.5, need_scratch * 0.60,
        f"{need_scratch / need_borrowed:.0f} times as many,\nfor the same answer",
        ha="center", va="center", fontsize=LABEL_SIZE + 1, color=INK, zorder=7,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": PAPER, "edgecolor": MUTED, "lw": 0.8},
    )
    bars.text(
        0.5, -0.30,
        "Both starts end at the same ceiling, because the architecture and the labels are the same "
        "either way.\nWhat the borrowed weights change is how quickly the climb happens. In this cell "
        "the labels are rendered\nby the simulator rather than drawn by hand, so the saving is in "
        "rendering and training time, not in labels.",
        transform=bars.transAxes, ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )

    figure.suptitle(
        "Fine-tuning against a random start: the same answer from far fewer examples",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.02,
    )
    figure.tight_layout()
    print(f"  curves: usable at {need_borrowed:.0f} scenes borrowed, {need_scratch:.0f} from scratch")
    save(figure, "09-fine-tune-against-scratch.png")


# --------------------------------------------------------------------------- #
# 5. boxes, scores and masks, all at once
# --------------------------------------------------------------------------- #

def figure_boxes_scores_masks() -> None:
    """What one pass returns for one scene, and what the score is good for."""
    built = scene(MIXED_PLACES)
    limits = limits_of(built)
    mesh = grid_of(limits)
    masks = [raster(one["circles"], mesh) for one in built]
    heights = [one["height"] for one in built]
    kept = own_pixels(masks, heights)

    rows = []
    for index, one in enumerate(built):
        visible = float(kept[index].sum()) / float(masks[index].sum())
        pixels = as_pixels(float(kept[index].sum()) * GRID_MM**2)
        rows.append(
            {
                "name": one["name"],
                "score": score_of(visible, pixels),
                "visible": visible,
                "box": one["box"],
                "across_mm": one["patch_mm"],
                "mask_px": pixels,
            }
        )
    order = sorted(range(len(rows)), key=lambda index: -rows[index]["score"])
    # neighbouring glasses get different colours, so the pair whose outlines
    # touch cannot be read as one mask
    colours = [GLASS if index % 2 == 0 else GOOD for index in range(len(built))]
    ceiling = (max(heights) + min(heights)) / 2.0

    figure, axes = new(14.0, 6.0, columns=2)
    left, right = axes
    table_axis(left, limits)

    for rank, index in enumerate(order):
        show_mask(left, kept[index], limits, colours[index], alpha=0.80)
        draw_box(left, rows[index]["box"], colour=INK, lw=1.3)
        box = rows[index]["box"]
        above = built[index]["height"] > ceiling
        left.text(
            box[0], box[3] + 9.0 if above else box[1] - 9.0,
            f"#{rank + 1}  glass  {rows[index]['score']:.2f}",
            ha="left", va="bottom" if above else "top", fontsize=NOTE_SIZE, color=INK, zorder=9,
            bbox={"boxstyle": "round,pad=0.22", "facecolor": PAPER, "edgecolor": INK, "lw": 0.6},
        )
    note(left, 14, -14, "camera", colour=WARN)
    panel_title(left, "One picture in, and this comes out in one pass")
    note(left, limits[0] + 12, limits[2] + 12,
         "The box says where. The score says how sure.\n"
         "The mask says which pixels. All three per glass,\nfrom the one forward pass.",
         colour=INK, va="bottom")

    # ---------------------------------------------------------- the list itself
    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    panel_title(right, "The same output written out as a list")

    columns = (0.055, 0.30, 0.47, 0.66, 0.86)
    headers = ("", "class", "score", "box, mm across", "mask, pixels")
    top = 0.855
    for x, header in zip(columns, headers, strict=True):
        right.text(x, top + 0.045, header, fontsize=NOTE_SIZE, color=MUTED,
                   ha="left" if x < 0.2 else "center", va="bottom", zorder=6)
    right.plot([0.03, 0.97], [top + 0.030, top + 0.030], color=MUTED, lw=0.9, zorder=5)
    for rank, index in enumerate(order):
        row = rows[index]
        y = top - rank * 0.105
        colour = colours[index]
        right.add_patch(
            Rectangle((0.03, y - 0.038), 0.94, 0.082, facecolor=to_rgba(colour, 0.08),
                      edgecolor="none", zorder=1)
        )
        right.text(columns[0], y, f"#{rank + 1}", fontsize=LABEL_SIZE, color=INK,
                   ha="left", va="center", zorder=6)
        right.text(columns[1], y, "glass", fontsize=LABEL_SIZE, color=INK,
                   ha="center", va="center", zorder=6)
        right.text(columns[2], y, f"{row['score']:.2f}", fontsize=LABEL_SIZE, color=colour,
                   ha="center", va="center", zorder=6)
        right.text(columns[3], y, f"{row['across_mm']:.0f}", fontsize=LABEL_SIZE, color=INK,
                   ha="center", va="center", zorder=6)
        right.text(columns[4], y, f"{row['mask_px']:.0f}", fontsize=LABEL_SIZE, color=INK,
                   ha="center", va="center", zorder=6)

    cut = top - len(order) * 0.105 + 0.048
    right.plot([0.03, 0.97], [cut, cut], color=WARN, lw=1.3, ls=(0, (4, 3)), zorder=5)
    right.text(0.97, cut - 0.012, f"anything scoring below {SCORE_KEEP:.2f} is dropped here",
               fontsize=NOTE_SIZE, color=WARN, ha="right", va="top", zorder=6)

    note(right, 0.03, 0.335,
         "What the score is good for:",
         colour=INK, size=LABEL_SIZE, va="top")
    note(right, 0.055, 0.285,
         "- a cut: below it, a detection is not reported at all, which is how the\n"
         "  boxes that landed on bare table are thrown away;\n"
         "- an order: the arm can go for the surest glass first and leave the\n"
         "  doubtful ones for a second look from another viewpoint;\n"
         "- a handle for doubt: a low score is a reason to photograph again.",
         colour=INK, va="top")
    note(right, 0.03, 0.105,
         "What it is not: the score says how sure the model is that the box holds a glass.\n"
         "It says nothing about whether the mask is the right shape, and nothing at all\n"
         "about a glass that was never proposed. The last figure is that case.",
         colour=WARN, va="top")

    figure.suptitle(
        "One forward pass returns a box, a score and a mask for every glass it finds",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.015,
        f"The scores here are arithmetic, not a trained network's output: each one is read off how much "
        f"of that glass the camera can see and how many pixels it covers, between "
        f"{SCORE_FLOOR:.2f} and {SCORE_CEILING:.2f}. "
        "The boxes, the widths and the pixel counts are measured from the silhouettes themselves.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    print(f"  output: {[(r['name'], round(r['score'], 2), round(r['across_mm'])) for r in rows]}")
    save(figure, "09-boxes-scores-masks.png")


# --------------------------------------------------------------------------- #
# 6. many proposals for one glass, collapsed by overlap
# --------------------------------------------------------------------------- #

def jittered_boxes(box, count=6, seed=10, spread=0.14):
    """Proposals round one true box: what stage one really hands over.

    The seed is fixed, and the arrangement it draws is checked below: six boxes
    that all overlap the best one by more than the threshold, so the figure
    shows the collapse it claims to show.
    """
    rng = np.random.default_rng(seed)
    left, bottom, right, top = box
    width, height = right - left, top - bottom
    mid_x, mid_y = (left + right) / 2.0, (bottom + top) / 2.0
    out = [box]
    for _ in range(count - 1):
        shift_x = rng.normal(0.0, spread * width)
        shift_y = rng.normal(0.0, spread * height)
        grow = 1.0 + rng.normal(0.0, spread)
        half_w, half_h = width * grow / 2.0, height * grow / 2.0
        out.append((mid_x + shift_x - half_w, mid_y + shift_y - half_h,
                    mid_x + shift_x + half_w, mid_y + shift_y + half_h))
    return out


def figure_overlapping_proposals() -> None:
    """Six boxes for one glass become one, and the small glass beside it survives."""
    tall_at, short_at = np.array([120.0, 20.0]), np.array([50.0, -140.0])
    apart = float(np.hypot(*(tall_at - short_at)))
    if apart < MIN_APART:
        raise ValueError(f"the two glasses stand {apart:.0f} mm apart, closer than {MIN_APART:.0f} mm")
    tall = splay_circles(NADIR, tall_at, *TALL_A)
    short = splay_circles(NADIR, short_at, *SHORT_B)

    truth = box_of(tall)
    neighbour = box_of(short)
    limits = (min(neighbour[0], truth[0]) - 130.0, max(neighbour[2], truth[2]) + 130.0,
              min(neighbour[1], truth[1]) - 80.0, max(neighbour[3], truth[3]) + 120.0)
    proposals = jittered_boxes(truth) + [neighbour]

    # A proposal's score follows how well it frames the glass, which is the one
    # honest way to put a number on it here. The small glass's own box is scored
    # the way the rest of these figures score a glass in full view.
    scores = [
        SCORE_FLOOR + (SCORE_CEILING - SCORE_FLOOR) * box_overlap(box, truth)[2]
        for box in proposals[:-1]
    ]
    small_pixels = as_pixels(float(raster(short, grid_of(limits)).sum()) * GRID_MM**2)
    scores.append(score_of(1.0, small_pixels))
    kept, dropped = nms(proposals, scores)
    winner = kept[0]
    if len(kept) != 2:
        raise ValueError(f"this arrangement was chosen to collapse to two boxes, not {len(kept)}")

    figure, axes = new(15.6, 5.6, columns=3)
    for axis in (axes[0], axes[2]):
        table_axis(axis, limits, nadir=False)
    paper_box = {"boxstyle": "round,pad=0.18", "facecolor": PAPER,
                 "edgecolor": "none", "alpha": 0.85}

    # ----------------------------------------------- many boxes for one glass
    silhouette(axes[0], tall, colour=GLASS, alpha=0.26)
    silhouette(axes[0], short, colour=GLASS, alpha=0.26)
    corners = (("left", "bottom", 0, 3, 4.0, 5.0), ("right", "bottom", 2, 3, -4.0, 5.0),
               ("left", "top", 0, 1, 4.0, -5.0), ("right", "top", 2, 1, -4.0, -5.0),
               ("center", "bottom", None, 3, 0.0, 5.0), ("center", "top", None, 1, 0.0, -5.0))
    for index, box in enumerate(proposals[:-1]):
        draw_box(axes[0], box, colour=INK, lw=1.0, dashed=True)
        ha, va, which_x, which_y, dx, dy = corners[index % len(corners)]
        x = (box[0] + box[2]) / 2.0 if which_x is None else box[which_x]
        axes[0].text(x + dx, box[which_y] + dy, f"{scores[index]:.2f}", ha=ha, va=va,
                     fontsize=NOTE_SIZE - 0.4, color=INK, zorder=9, bbox=paper_box)
    draw_box(axes[0], neighbour, colour=GLASS, lw=1.2, dashed=True)
    axes[0].text(neighbour[2] + 6.0, neighbour[1] + 6.0, f"{scores[-1]:.2f}", ha="left",
                 va="bottom", fontsize=NOTE_SIZE - 0.4, color=GLASS, zorder=9)
    panel_title(axes[0], f"stage one: {len(proposals) - 1} boxes for the large glass")
    note(axes[0], limits[0] + 10, limits[3] - 8,
         "The proposer fires wherever something looks\n"
         "like an object, so one glass collects several\n"
         "boxes that differ only a little. Each box\ncarries its own score.",
         colour=INK)
    note(axes[0], limits[0] + 10, limits[2] + 10,
         "The small glass beside it gets a box of its own.",
         colour=GLASS, va="bottom")

    # ----------------------------------------------------- what overlap means
    bare(axes[1])
    axes[1].set_aspect("equal")
    # the clearest rival to draw is one that sticks out of the winner rather than
    # sitting inside it, so that the shared part is plainly a part of both
    def sticks_out(index: int) -> bool:
        shared_area = box_overlap(proposals[index], proposals[winner])[0]
        return shared_area < 0.85 * min(box_area(proposals[index]), box_area(proposals[winner]))

    candidates = [index for index, _ in dropped if sticks_out(index)]
    rival = min(
        candidates or [index for index, _ in dropped],
        key=lambda index: box_overlap(proposals[index], proposals[winner])[2],
    )
    one, other = proposals[winner], proposals[rival]
    inter, union, ratio = box_overlap(one, other)
    union_box = (min(one[0], other[0]), min(one[1], other[1]),
                 max(one[2], other[2]), max(one[3], other[3]))
    # the same shape as the two drawing panels, so all three titles line up,
    # with room above the boxes for their labels and room below for the numbers
    head, foot = 70.0, 280.0
    span_y = (union_box[3] - union_box[1]) + head + foot
    span_x = span_y * (limits[1] - limits[0]) / (limits[3] - limits[2])
    corner_x = (union_box[0] + union_box[2]) / 2.0 - span_x / 2.0
    corner_y = union_box[1] - foot
    axes[1].set_xlim(corner_x, corner_x + span_x)
    axes[1].set_ylim(corner_y, corner_y + span_y)

    axes[1].add_patch(
        Rectangle((union_box[0], union_box[1]), union_box[2] - union_box[0],
                  union_box[3] - union_box[1], facecolor=to_rgba(MUTED, 0.12),
                  edgecolor=MUTED, lw=0.9, ls=(0, (3, 3)), zorder=2)
    )
    shared = (max(one[0], other[0]), max(one[1], other[1]),
              min(one[2], other[2]), min(one[3], other[3]))
    axes[1].add_patch(
        Rectangle((shared[0], shared[1]), shared[2] - shared[0], shared[3] - shared[1],
                  facecolor=to_rgba(GOOD, 0.30), edgecolor="none", zorder=3)
    )
    draw_box(axes[1], one, colour=GOOD, lw=1.8)
    draw_box(axes[1], other, colour=INK, lw=1.8)
    axes[1].text(one[0], one[3] + 8.0, f"the better box, {scores[winner]:.2f}", ha="left",
                 va="bottom", fontsize=NOTE_SIZE, color=GOOD, zorder=9)
    axes[1].text(other[2], other[1] - 8.0, f"the rival, {scores[rival]:.2f}", ha="right",
                 va="top", fontsize=NOTE_SIZE, color=INK, zorder=9)
    axes[1].text((shared[0] + shared[2]) / 2.0, (shared[1] + shared[3]) / 2.0, "shared",
                 ha="center", va="center", fontsize=NOTE_SIZE, color=INK, zorder=9)
    panel_title(axes[1], "the overlap measure: shared area over area covered")
    axes[1].text(
        union_box[0], union_box[1] - 46.0,
        f"shared area      {inter / 100.0:6.0f} cm2\n"
        f"area covered     {union / 100.0:6.0f} cm2\n"
        f"shared / covered {ratio:6.2f}",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK, family="monospace", zorder=9,
    )
    axes[1].text(
        union_box[0], union_box[1] - 150.0,
        f"That is over the threshold of {NMS_IOU:.2f}, so the two boxes\n"
        "are taken to be the same glass and the lower-scoring\n"
        "one goes. Nothing about what is inside them comes\ninto it: only how much area they share.",
        ha="left", va="top", fontsize=NOTE_SIZE,
        color=WARN if ratio > NMS_IOU else INK, zorder=9,
    )

    # --------------------------------------------------- what survives, and why
    silhouette(axes[2], tall, colour=GLASS, alpha=0.20)
    silhouette(axes[2], short, colour=GLASS, alpha=0.20)
    for index, _ in dropped:
        draw_box(axes[2], proposals[index], colour=MUTED, lw=0.9, dashed=True)
    draw_box(axes[2], proposals[winner], colour=GOOD, lw=2.0)
    highest = max(proposals[index][3] for index, _ in dropped + [(winner, winner)])
    axes[2].text(proposals[winner][0], highest + 12.0, f"kept: glass {scores[winner]:.2f}",
                 ha="left", va="bottom", fontsize=NOTE_SIZE, color=GOOD, zorder=9)
    for index in (place for place in kept if place != winner):
        draw_box(axes[2], proposals[index], colour=GOOD, lw=1.6)
        axes[2].text(proposals[index][2] + 8.0, proposals[index][3],
                     f"kept: glass {scores[index]:.2f}", ha="left", va="top",
                     fontsize=NOTE_SIZE, color=GOOD, zorder=9)
    with_winner = box_overlap(proposals[winner], neighbour)[2]
    panel_title(axes[2], f"after suppression: {len(kept)} boxes for {len(kept)} glasses", colour=GOOD)
    note(axes[2], limits[0] + 10, limits[3] - 8,
         f"{len(dropped)} boxes dropped, every one of them sharing\n"
         f"more than {NMS_IOU:.2f} of the area covered with the best one.",
         colour=MUTED)
    note(axes[2], limits[0] + 10, limits[2] + 10,
         f"The small glass's box shares only {with_winner:.2f} of the area\n"
         "covered with the winner, which is under the threshold,\n"
         "so it survives. That is why the rule does not delete a\n"
         "genuinely different glass standing close by.",
         colour=GOOD, va="bottom")

    figure.suptitle(
        "Several boxes for one glass collapse to one, and area shared over area covered is what decides",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.01,
    )
    figure.tight_layout()
    print(f"  nms: {len(proposals)} proposals, kept {len(kept)}, dropped {len(dropped)}, "
          f"rival overlap {ratio:.2f}, neighbour overlap {with_winner:.2f}")
    save(figure, "09-overlapping-proposals.png")


# --------------------------------------------------------------------------- #
# 7. where it stops: no pixels, no proposal, no row
# --------------------------------------------------------------------------- #

def figure_where_it_stops() -> None:
    """A glass covered completely leaves nothing for stage one to propose."""
    built = scene(COVER_PLACES)
    limits = limits_of(built)
    mesh = grid_of(limits)
    masks = [raster(one["circles"], mesh) for one in built]
    heights = [one["height"] for one in built]
    kept = own_pixels(masks, heights)

    tall, small = built[0], built[1]
    covered = splay_covers(tall["circles"], small["circles"])
    if not covered:
        raise ValueError("this scene was chosen for a complete cover and does not have one")
    apart = float(np.hypot(*(tall["place"] - small["place"])))
    own_cells = int(kept[1].sum())
    all_cells = int(masks[1].sum())

    found = [index for index in range(len(built)) if kept[index].sum() > 0]
    missing = [index for index in range(len(built)) if kept[index].sum() == 0]
    scores = {}
    for index in found:
        visible = float(kept[index].sum()) / float(masks[index].sum())
        scores[index] = score_of(visible, as_pixels(float(kept[index].sum()) * GRID_MM**2))

    figure, axes = new(15.8, 5.6, columns=3)
    for axis in axes[:2]:
        table_axis(axis, limits)
    paper_box = {"boxstyle": "round,pad=0.30", "facecolor": PAPER,
                 "edgecolor": "none", "alpha": 0.88}

    # ------------------------------------------------- what is on the table
    for index, one in enumerate(built):
        colour = WARN if index == 1 else GLASS
        footprint(axes[0], one["place"], one["rim"], colour=colour)
        axes[0].text(one["place"][0], one["place"][1] - one["rim"] / 2.0 - 12.0,
                     one["name"], ha="center", va="top", fontsize=NOTE_SIZE,
                     color=colour, zorder=9)
    axes[0].annotate(
        "", xy=tuple(small["place"]), xytext=tuple(tall["place"]),
        arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.1}, zorder=8,
    )
    axes[0].text(
        (tall["place"][0] + small["place"][0]) / 2.0,
        (tall["place"][1] + small["place"][1]) / 2.0 + 14.0,
        f"{apart:.0f} mm", ha="center", va="bottom", fontsize=NOTE_SIZE, color=INK, zorder=9,
    )
    note(axes[0], 14, -14, "camera", colour=WARN)
    panel_title(axes[0], "On the table: four glasses, none touching")
    note(axes[0], limits[0] + 12, limits[2] + 12,
         f"A legal arrangement. The\nclosest pair stands {apart:.0f} mm\n"
         f"apart, clearing the guaranteed\n{MIN_APART:.0f} mm, and every glass is\n"
         f"inside this kind's range of\nsizes, whose tall end is {HEIGHT_SPREAD:.1f}\n"
         "times its short end.",
         colour=INK, va="bottom", bbox=paper_box)

    # ---------------------------------------------- what the camera is given
    grey_picture(axes[1], built, limits, mesh)
    draw_box(axes[1], small["box"], colour=WARN, lw=1.2, dashed=True)
    panel_title(axes[1], "From the top: the small glass is under the large one", colour=WARN)
    axes[1].annotate(
        f"{small['name']} is in here, and contributes\n{own_cells} pixels of its own out of the "
        f"{all_cells * GRID_MM**2 / 100.0:.0f} cm2\nit would cover if it stood alone.",
        xy=((small["box"][0] + small["box"][2]) / 2.0, small["box"][1]),
        xytext=(limits[0] + 40.0, limits[2] + 80.0),
        fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom", bbox=paper_box,
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.1},
    )
    note(axes[1], 14, -14, "camera", colour=WARN, bbox=paper_box)
    note(axes[1], limits[0] + 12, limits[3] - 10,
         "The large glass stands nearer the camera, so its\n"
         "outline is thrown further out, and here it lands\n"
         "over the small one entirely. Checked in code, not\n"
         "drawn by eye.",
         colour=INK, bbox=paper_box)

    # ------------------------------------------------- the chain that breaks
    bare(axes[2])
    axes[2].set_xlim(0, 1)
    axes[2].set_ylim(0, 1)
    panel_title(axes[2], "So the chain has nothing to start from", colour=WARN)

    chain = (
        ("no pixels of its own", "nothing in the picture came from this glass"),
        ("so no region proposed", "stage one only fires where something is"),
        ("so nothing classified", "stage two is only ever given proposed boxes"),
        ("so no row in the output", "and no score, high or low, to inspect"),
    )
    for index, (step, why) in enumerate(chain):
        bottom = 0.900 - index * 0.122
        rounded(axes[2], 0.05, bottom, 0.90, 0.088, face=WARN, edge=WARN, alpha=0.10, lw=1.0)
        axes[2].text(0.085, bottom + 0.058, step, fontsize=LABEL_SIZE, color=WARN,
                     ha="left", va="center", zorder=6)
        axes[2].text(0.085, bottom + 0.022, why, fontsize=NOTE_SIZE, color=INK,
                     ha="left", va="center", zorder=6)
        if index < len(chain) - 1:
            arrow(axes[2], (0.50, bottom - 0.004), (0.50, bottom - 0.033), colour=WARN, lw=1.2)

    axes[2].text(0.05, 0.435, f"what the model returns: {len(found)} masks for {len(built)} glasses",
                 fontsize=LABEL_SIZE, color=INK, ha="left", va="top", zorder=6)
    for row, index in enumerate(sorted(found, key=lambda i: -scores[i])):
        y = 0.385 - row * 0.048
        axes[2].text(0.075, y, f"#{row + 1}   glass   {scores[index]:.2f}   "
                     f"{built[index]['patch_mm']:.0f} mm across",
                     fontsize=NOTE_SIZE, color=GOOD, ha="left", va="center",
                     family="monospace", zorder=6)
    y = 0.385 - len(found) * 0.048
    axes[2].text(0.075, y, f"--   {built[missing[0]]['name']}: no row at all",
                 fontsize=NOTE_SIZE, color=WARN, ha="left", va="center",
                 family="monospace", zorder=6)
    axes[2].text(
        0.05, y - 0.060,
        "The two glasses that merge into one patch still come back as two masks,\n"
        "which is what this kind of model is for. The covered glass is a different\n"
        "failure: every check in this project is a check on something that was\n"
        "found, and here there is nothing to check. Only another viewpoint puts\n"
        "pixels of that glass in a picture.",
        fontsize=NOTE_SIZE, color=INK, ha="left", va="top", zorder=6,
    )

    figure.suptitle(
        "Where this solution stops: a glass with no pixels is in no output, and no score reports it",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.01,
    )
    figure.tight_layout()
    # the two drawing panels keep a square aspect, so the chain panel is pulled
    # to the same height and its title lines up with theirs
    reference = axes[0].get_position()
    place = axes[2].get_position()
    axes[2].set_position([place.x0, reference.y0, place.width, reference.height])
    print(f"  cover: splay_covers={covered}, {apart:.0f} mm apart, "
          f"{own_cells} own cells, {len(found)} of {len(built)} found")
    save(figure, "09-where-it-stops.png")


def main() -> None:
    figure_class_map_against_instances()
    figure_the_two_stages()
    figure_what_a_backbone_brings()
    figure_fine_tune_against_scratch()
    figure_boxes_scores_masks()
    figure_overlapping_proposals()
    figure_where_it_stops()


if __name__ == "__main__":
    main()
