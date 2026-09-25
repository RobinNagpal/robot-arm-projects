"""Diagrams for solution 1 — split the blob in the picture.

Every mask, distance transform, marker set, watershed and GrabCut result drawn
here is computed by OpenCV on a real 320x240 mask, at the survey scale of
1.6 mm per pixel. Nothing is hand-drawn to look convincing, so the numbers
printed on the pictures are the numbers the method actually produces.

    pixi run python docs/problem-2/make_01_images.py
"""

from __future__ import annotations

import cv2
import numpy as np
from diagram_style import GLASS, GOOD, INK, LABEL_SIZE, MUTED, NOTE_SIZE, WARN, bare, new, save
from matplotlib.colors import to_rgba
from matplotlib.patches import Arc, Circle, Rectangle

# The cell, in the numbers problem 2 uses.
MM_PER_PX = 1.6        # survey height 450 mm: 520 mm of table across 320 pixels
FX = 277.1             # pixels, the camera's focal length
WIDEST_MM = 105.0      # the widest footprint the known kind can have
R_PX = 33              # 105 mm across is 66 pixels, so 33 pixels of radius
FRAME = (240, 320)
CENTRE = (160, 120)    # column, row
MARKER_FRACTION = 0.7  # markers are the pixels deeper than this much of the peak

# Where the two silhouettes land in the worked example, and in the failure.
SPLIT_APART = 50
SPLIT_CLOSE = 20

# The crop every picture of the blob uses, so they can be read side by side.
CROP = (86, 234, 60, 180)   # left, right, top, bottom in pixels
CROP_W = CROP[1] - CROP[0]
CROP_H = CROP[3] - CROP[2]
MID_ROW = CENTRE[1] - CROP[2]
MID_COL = CENTRE[0] - CROP[0]


def two_discs(separation: int, radius: int = R_PX) -> np.ndarray:
    """A mask with two circular footprints whose centres are `separation` pixels apart."""
    mask = np.zeros(FRAME, np.uint8)
    column, row = CENTRE
    cv2.circle(mask, (column - separation // 2, row), radius, 255, -1)
    cv2.circle(mask, (column + separation // 2, row), radius, 255, -1)
    return mask


def distance(mask: np.ndarray) -> np.ndarray:
    """For every yes pixel, how far to the nearest no pixel."""
    return cv2.distanceTransform(mask, cv2.DIST_L2, 5)


def markers_from_distance(field: np.ndarray, fraction: float = MARKER_FRACTION) -> np.ndarray:
    """The deep pixels, which is where the flooding is allowed to start."""
    return (field > fraction * field.max()).astype(np.uint8)


def flood(mask: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    """Watershed: rise from every seed at once, build a wall where two floods meet."""
    _, labels = cv2.connectedComponents(seeds)
    labels = labels + 1                        # 1 becomes the background label
    labels[(mask > 0) & (seeds == 0)] = 0      # 0 means "nobody has claimed this yet"
    return cv2.watershed(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), labels.astype(np.int32))


def crop(image: np.ndarray) -> np.ndarray:
    left, right, top, bottom = CROP
    return image[top:bottom, left:right]


def paint(axis, region: np.ndarray, colour: str, alpha: float = 1.0) -> None:
    """Fill the true pixels of `region` with one colour and leave the rest clear."""
    rgba = np.zeros((*region.shape, 4), float)
    rgba[region] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest")


def outline(axis, mask: np.ndarray, colour: str = INK, width: float = 1.4) -> None:
    axis.contour(mask.astype(float), [0.5], colors=[colour], linewidths=width)


def stage(axis, title: str) -> None:
    """A panel holding a drawing: no ticks, no frame, pinned to the top of its box."""
    bare(axis)
    axis.set_anchor("N")
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)


def plot_frame(axis, title: str, xlabel: str, ylabel: str) -> None:
    """A panel holding a plot: two spines, small grey ticks."""
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)
    axis.set_xlabel(xlabel, fontsize=NOTE_SIZE, color=INK)
    axis.set_ylabel(ylabel, fontsize=NOTE_SIZE, color=INK)
    axis.tick_params(labelsize=NOTE_SIZE - 0.6, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)


def note(axis, x: float, y: float, text: str, colour: str = MUTED, **kwargs) -> None:
    axis.text(x, y, text, fontsize=NOTE_SIZE, color=colour, ha="center", **kwargs)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.02, text, fontsize=NOTE_SIZE, color=INK, ha="center")


# --------------------------------------------------------------------------
# 1. The problem: one patch of pixels, two objects.
# --------------------------------------------------------------------------
def picture_one_blob() -> None:
    mask = two_discs(SPLIT_APART)
    cut = crop(mask) > 0
    columns = np.where(mask.any(axis=0))[0]
    rows = np.where(mask.any(axis=1))[0]
    wide = columns[-1] - columns[0] + 1
    tall = rows[-1] - rows[0] + 1
    count, _ = cv2.connectedComponents(mask)
    left_edge, _, top_edge, _ = CROP

    figure, axes = new(10.6, 4.2, columns=2)
    truth, found = axes
    for axis in axes:
        stage(axis, "")
        axis.set_aspect("equal")
        axis.set_xlim(0, CROP_W)
        axis.set_ylim(CROP_H, 0)

    stage(truth, "What is on the table")
    for sign, name in ((-1, "glass A"), (+1, "glass B")):
        centre = (MID_COL + sign * SPLIT_APART // 2, MID_ROW)
        truth.add_patch(Circle(centre, R_PX, facecolor=to_rgba(GLASS, 0.30), edgecolor=GLASS, lw=1.6))
        truth.text(centre[0], centre[1] - 4, name, fontsize=NOTE_SIZE, color=INK, ha="center")
    left = MID_COL - SPLIT_APART // 2
    right = MID_COL + SPLIT_APART // 2
    truth.annotate(
        "", xy=(left, MID_ROW + 6), xytext=(right, MID_ROW + 6),
        arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.0},
    )
    note(
        truth, MID_COL, MID_ROW + 20,
        f"centres {SPLIT_APART} px = {SPLIT_APART * MM_PER_PX:.0f} mm apart", INK,
    )
    note(truth, MID_COL, CROP_H - 5, "two footprints, each 66 px = 105 mm across")

    stage(found, "What connected components returns")
    paint(found, cut, MUTED, 0.55)
    outline(found, cut)
    found.add_patch(Rectangle(
        (columns[0] - left_edge, rows[0] - top_edge), wide, tall,
        fill=False, edgecolor=WARN, lw=1.5, linestyle=(0, (4, 3)),
    ))
    note(
        found, MID_COL, rows[0] - top_edge - 6,
        f"{wide} x {tall} px = {wide * MM_PER_PX:.0f} x {tall * MM_PER_PX:.0f} mm", WARN,
    )
    note(found, MID_COL, MID_ROW + 2, f"{count - 1} label", INK)
    note(
        found, MID_COL, CROP_H - 5,
        f"{wide * MM_PER_PX:.0f} mm long, and no glass of this kind exceeds {WIDEST_MM:.0f} mm",
    )

    footer(
        figure,
        "Connected components answers one question — are these pixels joined? They are. It never asks "
        "how wide the patch is, so the mistake is not in the answer, it is in the question.",
    )
    figure.subplots_adjust(bottom=0.14, top=0.90, wspace=0.05)
    save(figure, "01-one-blob-two-glasses.png")


# --------------------------------------------------------------------------
# 2. The distance transform, built up from one pixel to a landscape.
# --------------------------------------------------------------------------
def picture_distance_transform() -> None:
    mask = two_discs(SPLIT_APART)
    field = distance(mask)
    cut_mask = crop(mask) > 0
    cut_field = crop(field)
    peak = field.max()
    waist = float(cut_field[:, MID_COL].max())

    figure, axes = new(13.4, 4.6, columns=3)
    one, whole, upside = axes

    # (a) the definition, on four pixels.
    stage(one, "For each yes pixel: how far to the nearest no pixel")
    paint(one, cut_mask, GLASS, 0.16)
    outline(one, cut_mask, GLASS)
    background = np.argwhere(crop(mask) == 0)
    samples = (
        (MID_ROW, MID_COL - 55, (-9, 0), "right"),
        (MID_ROW, MID_COL - 25, (0, -7), "center"),
        (MID_ROW - 14, MID_COL + 25, (9, -2), "left"),
        (MID_ROW, MID_COL, (0, 10), "center"),
    )
    for row, column, (dx, dy), align in samples:
        gaps = background - np.array([row, column])
        nearest = background[np.argmin((gaps ** 2).sum(axis=1))]
        one.plot([column], [row], "o", color=INK, ms=3.6)
        one.annotate(
            "", xy=(nearest[1], nearest[0]), xytext=(column, row),
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.9},
        )
        one.text(
            column + dx, row + dy, f"{cut_field[row, column]:.0f}",
            fontsize=NOTE_SIZE, color=INK, ha=align, va="center",
        )
    note(one, MID_COL, CROP_H - 5, "one number per pixel, and nothing else")

    # (b) all of them at once.
    stage(whole, "All of them at once, shaded")
    whole.imshow(np.ma.masked_where(~cut_mask, cut_field), cmap="Blues", vmin=0, vmax=peak,
                 interpolation="nearest")
    whole.contour(cut_field, levels=[6, 12, 18, 24, 30], colors=[MUTED], linewidths=0.6)
    outline(whole, cut_mask)
    for sign in (-1, +1):
        whole.plot([MID_COL + sign * SPLIT_APART / 2], [MID_ROW], "o", color=WARN, ms=5)
    whole.annotate(
        f"peak {peak:.1f} px", xy=(MID_COL - SPLIT_APART / 2, MID_ROW),
        xytext=(MID_COL - SPLIT_APART / 2 - 6, 12), fontsize=NOTE_SIZE, color=WARN, ha="center",
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 0.9},
    )
    whole.annotate(
        f"waist {waist:.0f} px", xy=(MID_COL, MID_ROW),
        xytext=(MID_COL + 30, CROP_H - 16), fontsize=NOTE_SIZE, color=INK, ha="center",
        arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.9},
    )
    note(whole, MID_COL, CROP_H - 5, "darkest deep inside, 1 next to the edge")

    # (c) the same thing upside down.
    profile = -cut_field[MID_ROW]
    x = np.arange(profile.size)
    inside = cut_mask[MID_ROW]
    upside.plot(x[inside], profile[inside], color=GLASS, lw=1.8)
    upside.fill_between(x[inside], profile[inside], 0, color=GLASS, alpha=0.16)
    upside.axhline(0, color=MUTED, lw=0.8)
    for sign in (-1, +1):
        column = MID_COL + sign * SPLIT_APART / 2
        upside.annotate(
            "valley", xy=(column, -peak), xytext=(column, -peak + 12),
            fontsize=NOTE_SIZE, color=INK, ha="center",
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.9},
        )
    upside.annotate(
        "the col between them", xy=(MID_COL, -waist), xytext=(MID_COL, -waist + 13),
        fontsize=NOTE_SIZE, color=WARN, ha="center",
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 0.9},
    )
    plot_frame(upside, "Upside down, it is a landscape", "pixels across the blob", "minus the distance")
    upside.set_ylim(-peak - 4, 8)
    upside.set_xlim(0, CROP_W)

    footer(
        figure,
        "One valley per object, because the deepest pixel of each footprint is the point furthest from "
        "any edge. The col between them is the narrow place, and it is the place to cut.",
    )
    figure.subplots_adjust(bottom=0.16, top=0.90, wspace=0.18)
    save(figure, "01-distance-transform.png")


# --------------------------------------------------------------------------
# 3. Markers: two ways to get them, which turn out to be one way.
# --------------------------------------------------------------------------
def picture_markers() -> None:
    mask = two_discs(SPLIT_APART)
    field = distance(mask)
    level = MARKER_FRACTION * field.max()
    radius = int(round(level))
    deep = markers_from_distance(field)
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    eroded = cv2.erode(mask, disc)
    agreement = 100.0 * ((eroded > 0) == (field > radius)).mean()
    cut_mask = crop(mask) > 0

    figure, axes = new(13.4, 4.6, columns=3)
    maxima, shave, same = axes

    stage(maxima, f"Keep the deep pixels: distance > {MARKER_FRACTION} x peak")
    paint(maxima, cut_mask, MUTED, 0.22)
    outline(maxima, cut_mask, MUTED)
    paint(maxima, crop(deep) > 0, GOOD, 0.85)
    note(maxima, MID_COL, 12, f"{MARKER_FRACTION} x {field.max():.1f} px = {level:.1f} px", INK)
    note(maxima, MID_COL, CROP_H - 5, "two patches survive — one per object")

    stage(shave, f"Or ask whether a disc of radius {radius} px fits")
    paint(shave, cut_mask, MUTED, 0.22)
    outline(shave, cut_mask, MUTED)
    paint(shave, crop(eroded) > 0, GOOD, 0.85)
    shave.add_patch(Circle((MID_COL - SPLIT_APART / 2, MID_ROW), radius,
                           fill=False, edgecolor=GOOD, lw=1.3, linestyle=(0, (3, 2))))
    shave.add_patch(Circle((MID_COL, MID_ROW), radius,
                           fill=False, edgecolor=WARN, lw=1.3, linestyle=(0, (3, 2))))
    shave.text(MID_COL - SPLIT_APART / 2 - 6, MID_ROW - R_PX - 8, "fits: keep the centre",
               fontsize=NOTE_SIZE, color=GOOD, ha="center")
    shave.text(MID_COL + 14, MID_ROW + R_PX + 12, "pokes out: drop the centre",
               fontsize=NOTE_SIZE, color=WARN, ha="center")
    note(shave, MID_COL, CROP_H - 5, "the bridge is eaten away, two lumps are left")

    row = crop(field)[MID_ROW]
    x = np.arange(row.size)
    inside = cut_mask[MID_ROW]
    same.plot(x[inside], row[inside], color=GLASS, lw=1.8)
    same.axhline(radius, color=GOOD, lw=1.4)
    same.fill_between(x, radius, np.maximum(row, radius), where=inside, color=GOOD, alpha=0.25)
    same.text(CROP_W - 3, radius + 1.8, f"the line at {radius} px",
              fontsize=NOTE_SIZE, color=GOOD, ha="right")
    same.annotate(
        "the bridge sits under it", xy=(MID_COL, row[MID_COL]), xytext=(MID_COL, radius - 12),
        fontsize=NOTE_SIZE, color=WARN, ha="center",
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 0.9},
    )
    plot_frame(same, "Why those are the same thing", "pixels across the blob",
               "distance to the nearest no pixel (px)")
    same.set_ylim(0, field.max() + 6)
    same.set_xlim(0, CROP_W)

    footer(
        figure,
        "Eroding by a disc of radius r keeps exactly the pixels whose distance exceeds r, so the two "
        f"drawings are one idea. On this mask the two sets agree on {agreement:.0f} per cent of pixels.",
    )
    figure.subplots_adjust(bottom=0.16, top=0.90, wspace=0.18)
    save(figure, "01-markers-two-ways.png")


# --------------------------------------------------------------------------
# 4. Flooding, in four stages.
# --------------------------------------------------------------------------
def picture_flooding() -> None:
    mask = two_discs(SPLIT_APART)
    field = distance(mask)
    peak = field.max()
    filled = flood(mask, markers_from_distance(field))
    cut_mask = crop(mask) > 0
    cut_field = crop(field)
    cut_filled = crop(filled)
    inner = cv2.erode(crop(mask), np.ones((9, 9), np.uint8)) > 0
    wall = cv2.dilate((cut_filled == -1).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0

    levels = (30.0, 26.0, 22.2, 0.0)
    titles = ("water at 30 px", "water at 26 px", "water at 22 px", "water over the top")
    captions = (
        "a hole punched at the deepest\npoint of each valley",
        "each pool spreads, still nowhere\nnear the other",
        "the two floods reach the col\nwithin a pixel of each other",
        "a wall goes up where they meet,\nand that wall is the cut",
    )

    figure, axis = new(13.4, 5.6)
    axis.remove()
    grid = figure.add_gridspec(2, 4, height_ratios=[1.0, 1.9], hspace=0.06, wspace=0.08,
                               left=0.02, right=0.98, top=0.93, bottom=0.13)
    profile = -cut_field[MID_ROW]
    x = np.arange(profile.size)
    inside = cut_mask[MID_ROW]
    span = (int(x[inside].min()), int(x[inside].max()))

    for column, (level, title, caption) in enumerate(zip(levels, titles, captions, strict=True)):
        slice_axis = figure.add_subplot(grid[0, column])
        slice_axis.plot(x[inside], profile[inside], color=INK, lw=1.2)
        slice_axis.fill_between(x, profile, -level, where=inside & (profile <= -level),
                                color=GLASS, alpha=0.45)
        slice_axis.plot(span, [-level, -level], color=GLASS, lw=1.2)
        slice_axis.set_xlim(0, CROP_W)
        slice_axis.set_ylim(-peak - 4, 6)
        bare(slice_axis)
        slice_axis.set_title(title, fontsize=NOTE_SIZE + 0.4, color=INK, pad=4)

        plan = figure.add_subplot(grid[1, column])
        bare(plan)
        paint(plan, cut_mask, MUTED, 0.16)
        outline(plan, cut_mask, MUTED)
        reached = cut_field > level
        for label, colour in ((2, GLASS), (3, GOOD)):
            paint(plan, reached & (cut_filled == label), colour, 0.85)
        if level == 0.0:
            paint(plan, wall & inner, WARN, 1.0)
        plan.text(MID_COL, CROP_H - 2, caption, fontsize=NOTE_SIZE - 0.4, color=MUTED,
                  ha="center", va="top")

    footer(
        figure,
        "Watershed is a flood fill started from several places at once, which stops where the floods "
        "collide. Every pixel ends up belonging to one marker, and the wall between them is the cut.",
    )
    save(figure, "01-flooding.png")


# --------------------------------------------------------------------------
# 5. The numbers: how deep the waist is, and where the method gives out.
# --------------------------------------------------------------------------
def picture_waist_depth() -> None:
    separations = np.arange(2, 2 * R_PX + 1, 1.0)
    depth = np.sqrt(np.clip(1.0 - (separations / (2 * R_PX)) ** 2, 0.0, None))
    breaking = 2 * R_PX * np.sqrt(1.0 - MARKER_FRACTION ** 2)

    measured = []
    for separation in range(4, 2 * R_PX, 2):
        mask = two_discs(separation)
        field = distance(mask)
        count, _ = cv2.connectedComponents(markers_from_distance(field))
        measured.append((separation, field[:, CENTRE[0]].max() / field.max(), count - 1))

    figure, axes = new(12.6, 4.8, columns=2)
    curve, outcome = axes

    curve.axvspan(0, breaking, color=WARN, alpha=0.11)
    curve.plot(separations, depth, color=GLASS, lw=2.0, label="the geometry: sqrt(1 - (d/2R)^2)")
    curve.plot([m[0] for m in measured], [m[1] for m in measured], "o", color=INK, ms=3.0,
               label="measured by cv2.distanceTransform")
    curve.axhline(MARKER_FRACTION, color=GOOD, lw=1.4, linestyle=(0, (5, 3)))
    curve.text(1.5, MARKER_FRACTION + 0.03, f"the marker threshold, {MARKER_FRACTION}",
               fontsize=NOTE_SIZE, color=GOOD, ha="left")
    curve.axvline(breaking, color=WARN, lw=1.4)
    curve.text(breaking - 1.5, 0.30, f"{breaking:.0f} px = 1.43 radii = {breaking * MM_PER_PX:.0f} mm",
               fontsize=NOTE_SIZE, color=WARN, ha="right", va="center", rotation=90)
    curve.text(22, 0.22, "waist too shallow:\nthe markers merge",
               fontsize=NOTE_SIZE, color=WARN, ha="center")
    examples = ((SPLIT_CLOSE, "the failure", (3.0, 0.52), "left"),
                (SPLIT_APART, "worked example", (55.0, 0.38), "left"))
    for separation, name, where, align in examples:
        value = float(np.sqrt(1.0 - (separation / (2 * R_PX)) ** 2))
        curve.plot([separation], [value], "o", color=WARN if separation < breaking else GOOD, ms=7)
        curve.annotate(
            f"{name}\n{separation} px = {separation * MM_PER_PX:.0f} mm",
            xy=(separation, value), xytext=where, ha=align,
            fontsize=NOTE_SIZE, color=INK,
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.8},
        )
    plot_frame(curve, "How deep the waist is",
               "distance between the two silhouette centres (pixels)", "waist depth / peak depth")
    curve.set_xlim(0, 2 * R_PX)
    curve.set_ylim(0, 1.06)
    curve.legend(fontsize=NOTE_SIZE - 0.4, frameon=False, loc="upper right")

    for separation, _, count in measured:
        outcome.add_patch(Rectangle((separation - 1, 0), 2, 1,
                                    facecolor=GOOD if count == 2 else WARN, edgecolor="none"))
    for separation, name in ((SPLIT_CLOSE, "the failure"), (SPLIT_APART, "worked example")):
        outcome.annotate(
            name, xy=(separation, 1.0), xytext=(separation, 1.6),
            fontsize=NOTE_SIZE, color=INK, ha="center",
            arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.8},
        )
    outcome.plot([breaking, breaking], [-0.4, 1.4], color=INK, lw=1.0, linestyle=(0, (4, 3)))
    outcome.text(breaking - 1, -0.5, "1.43 radii", fontsize=NOTE_SIZE - 0.6, color=INK,
                 ha="right", va="top")
    outcome.set_xlim(0, 2 * R_PX)
    outcome.set_ylim(-1.9, 2.7)
    outcome.set_yticks([])
    plot_frame(outcome, "What comes back", "distance between the two silhouette centres (pixels)", "")
    outcome.spines["left"].set_visible(False)
    outcome.text(breaking / 2, 2.15, "one region", fontsize=NOTE_SIZE, color=WARN, ha="center")
    outcome.text((breaking + 2 * R_PX) / 2, 2.15, "two regions", fontsize=NOTE_SIZE, color=GOOD,
                 ha="center")
    outcome.text(
        R_PX, -1.05,
        "Below 1.43 radii the blob is still flagged as too wide.\n"
        "What is lost is the ability to say where to cut it —\n"
        "so one glass is reported, and no warning goes with it.",
        fontsize=NOTE_SIZE, color=INK, ha="center", va="top",
    )

    footer(
        figure,
        "Two circles of radius R whose centres are d apart pinch to a waist of sqrt(R^2 - d^2/4). That "
        f"drops below {MARKER_FRACTION} of R at d = 2R sqrt(1 - {MARKER_FRACTION}^2) = 1.43 R. The "
        "breaking point is not a second tuning constant; it follows from the first one.",
    )
    figure.subplots_adjust(bottom=0.22, top=0.90, wspace=0.16)
    save(figure, "01-waist-depth.png")


# --------------------------------------------------------------------------
# 6. GrabCut: it tightens, it does not split.
# --------------------------------------------------------------------------
def grabcut(colour_image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    state = np.zeros(FRAME, np.uint8)
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(colour_image, state, box, background_model, foreground_model, 4, cv2.GC_INIT_WITH_RECT)
    return np.isin(state, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)


def picture_grabcut() -> None:
    mask = two_discs(SPLIT_APART)
    scene = np.full((*FRAME, 3), 205, np.uint8)
    scene[mask > 0] = (60, 120, 200)
    scene = cv2.GaussianBlur(scene, (3, 3), 0)

    field = distance(mask)
    filled = flood(mask, markers_from_distance(field))
    half = (filled == 2).astype(np.uint8)

    columns = np.where(mask.any(axis=0))[0]
    rows = np.where(mask.any(axis=1))[0]
    half_columns = np.where(half.any(axis=0))[0]
    whole_box = (columns[0] - 9, rows[0] - 9, len(columns) + 18, len(rows) + 18)
    half_box = (half_columns[0] - 9, rows[0] - 9, len(half_columns) + 12, len(rows) + 18)

    from_clump = grabcut(scene, whole_box)
    from_half = grabcut(scene, half_box)
    clump_regions, _ = cv2.connectedComponents(from_clump)
    left_edge, _, top_edge, _ = CROP

    figure, axes = new(10.6, 4.4, columns=2)
    for axis, box, result, title, colour, text in (
        (axes[0], whole_box, from_clump, "GrabCut with a box round the whole clump", WARN,
         f"{clump_regions - 1} region, {int(from_clump.sum())} px against the mask's "
         f"{int((mask > 0).sum())}.\nA different outline. Still one object."),
        (axes[1], half_box, from_half, "GrabCut with a box round one half already cut out", GOOD,
         f"{int(from_half.sum())} px, and the edge now follows\nthe colour rather than the height step."),
    ):
        stage(axis, title)
        paint(axis, crop(mask) > 0, MUTED, 0.20)
        outline(axis, crop(mask) > 0, MUTED)
        paint(axis, crop(result) > 0, GOOD, 0.50)
        outline(axis, crop(result) > 0, GOOD, 1.8)
        axis.add_patch(Rectangle(
            (box[0] - left_edge, box[1] - top_edge), box[2], box[3],
            fill=False, edgecolor=INK, lw=1.2, linestyle=(0, (4, 3)),
        ))
        axis.text(MID_COL, CROP_H - 12, text, fontsize=NOTE_SIZE, color=colour, ha="center", va="top")

    footer(
        figure,
        "GrabCut sorts pixels into foreground and background by colour. Both halves of the clump are the "
        "same colour, so it has nothing to separate them with. It tidies an outline; it does not find one.",
    )
    figure.subplots_adjust(bottom=0.14, top=0.90, wspace=0.05)
    save(figure, "01-grabcut.png")


# --------------------------------------------------------------------------
# 7. The round-object relative: Hough circles, past the point watershed gives out.
# --------------------------------------------------------------------------
def hough(mask: np.ndarray, min_distance: int) -> np.ndarray:
    soft = cv2.GaussianBlur(mask, (7, 7), 0)
    found = cv2.HoughCircles(
        soft, cv2.HOUGH_GRADIENT, dp=1, minDist=min_distance,
        param1=80, param2=20, minRadius=24, maxRadius=44,
    )
    return np.zeros((0, 3)) if found is None else found[0]


def picture_hough() -> None:
    mask = two_discs(SPLIT_CLOSE)
    field = distance(mask)
    filled = flood(mask, markers_from_distance(field))
    circles = hough(mask, min_distance=15)
    coarse = hough(mask, min_distance=30)
    cut_mask = crop(mask) > 0
    left_edge, _, top_edge, _ = CROP
    waist = field[:, CENTRE[0]].max()

    figure, axes = new(13.4, 4.6, columns=3)
    broken, circled, tuned = axes

    stage(broken, f"Watershed, centres {SPLIT_CLOSE} px apart")
    paint(broken, cut_mask, MUTED, 0.18)
    outline(broken, cut_mask, MUTED)
    paint(broken, crop(filled) == 2, WARN, 0.50)
    broken.text(MID_COL, CROP_H - 14,
                f"waist {waist:.0f} px against a peak of {field.max():.1f} px:\n"
                "one marker, one region, and no complaint",
                fontsize=NOTE_SIZE, color=WARN, ha="center", va="top")

    stage(circled, "Hough circles on the same mask")
    paint(circled, cut_mask, MUTED, 0.18)
    outline(circled, cut_mask, MUTED)
    for column, row, radius in circles:
        circled.add_patch(Circle((column - left_edge, row - top_edge), radius,
                                 fill=False, edgecolor=GOOD, lw=1.8))
        circled.plot([column - left_edge], [row - top_edge], "+", color=GOOD, ms=9, mew=1.6)
    circled.text(MID_COL, CROP_H - 14,
                 f"{len(circles)} circles, radius {circles[0][2]:.1f} px, centres\n"
                 f"{SPLIT_CLOSE} px apart — both recovered",
                 fontsize=NOTE_SIZE, color=GOOD, ha="center", va="top")

    stage(tuned, "The same call, minDist raised to 30 px")
    paint(tuned, cut_mask, MUTED, 0.18)
    outline(tuned, cut_mask, MUTED)
    for column, row, radius in coarse:
        tuned.add_patch(Circle((column - left_edge, row - top_edge), radius,
                               fill=False, edgecolor=WARN, lw=1.8))
        tuned.plot([column - left_edge], [row - top_edge], "+", color=WARN, ms=9, mew=1.6)
    tuned.text(MID_COL, CROP_H - 14,
               f"{len(coarse)} circle. The tuning constant has\nmoved, it has not gone away.",
               fontsize=NOTE_SIZE, color=WARN, ha="center", va="top")

    footer(
        figure,
        "Fitting a shape you already know about uses the curve of the outline rather than the depth of "
        "the waist, so it survives heavier overlap — but only while minDist is set below the real gap.",
    )
    figure.subplots_adjust(bottom=0.14, top=0.90, wspace=0.05)
    save(figure, "01-hough-circles.png")


# --------------------------------------------------------------------------
# 8. The objection: the blob is a fact about the camera.
# --------------------------------------------------------------------------
def silhouette(lateral_mm: float, depth_mm: float, radius_mm: float) -> tuple[float, float, float]:
    """Where an upright cylinder lands: centre column, half width, and relative height."""
    centre = FX * lateral_mm / depth_mm
    half = FX * radius_mm / np.sqrt(depth_mm ** 2 - radius_mm ** 2)
    return centre, half, 380.0 / depth_mm


def picture_viewpoint() -> None:
    radius_mm = WIDEST_MM / 2
    near_mm, gap_mm = 380.0, 180.0
    turn = np.radians(60.0)

    straight = [silhouette(0.0, near_mm, radius_mm), silhouette(0.0, near_mm + gap_mm, radius_mm)]
    depth_far = near_mm + gap_mm * np.cos(turn)
    turned = [silhouette(0.0, near_mm, radius_mm),
              silhouette(-gap_mm * np.sin(turn), depth_far, radius_mm)]
    arc_mm = near_mm * turn

    figure, axes = new(13.4, 5.0, columns=3)
    plan, merged, apart = axes

    stage(plan, "Looking down on the table")
    plan.set_aspect("equal")
    for centre, name in (((0.0, 0.0), "glass A"), ((0.0, gap_mm), "glass B")):
        plan.add_patch(Circle(centre, radius_mm, facecolor=to_rgba(GLASS, 0.30), edgecolor=GLASS, lw=1.5))
        plan.text(centre[0], centre[1], name, fontsize=NOTE_SIZE, color=INK, ha="center", va="center")
    first = (0.0, -near_mm)
    second = (-near_mm * np.sin(turn), -near_mm * np.cos(turn))
    for spot, label, colour in ((first, "camera, in line", WARN),
                                (second, "camera, 60 deg round", GOOD)):
        plan.plot([spot[0]], [spot[1]], "s", color=colour, ms=7)
        plan.plot([spot[0], 0.0], [spot[1], 0.0], color=colour, lw=1.0, linestyle=(0, (4, 3)))
        plan.text(spot[0], spot[1] - 34, label, fontsize=NOTE_SIZE, color=colour,
                  ha="center", va="top")
    plan.add_patch(Arc((0.0, 0.0), 2 * near_mm, 2 * near_mm, theta1=210.0, theta2=270.0,
                       edgecolor=INK, lw=1.2))
    plan.annotate(
        "", xy=(radius_mm + 12, 0.0), xytext=(radius_mm + 12, gap_mm),
        arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.0},
    )
    plan.text(radius_mm + 20, gap_mm / 2, f"{gap_mm:.0f} mm\non the table",
              fontsize=NOTE_SIZE, color=INK, va="center")
    plan.text(-140, -250, f"{arc_mm:.0f} mm of\ncamera travel", fontsize=NOTE_SIZE, color=INK,
              ha="center")
    plan.set_xlim(-440, 210)
    plan.set_ylim(-560, 300)

    for axis, pair, title, colour, hidden in (
        (merged, straight, "The picture from in line", WARN, True),
        (apart, turned, "The picture from 60 degrees round", GOOD, False),
    ):
        stage(axis, title)
        axis.set_xlim(-165, 165)
        axis.set_ylim(-1.15, 1.75)
        axis.plot([-160, 160], [0, 0], color=MUTED, lw=1.0)
        note(axis, 0, -0.72, "320 pixels across")
        for index, ((centre, half, scale), name) in enumerate(zip(pair, ("A", "B"), strict=True)):
            behind = hidden and index == 1
            axis.add_patch(Rectangle(
                (centre - half, 0.0), 2 * half, 0.95 * scale,
                facecolor="none" if behind else to_rgba(GLASS, 0.40),
                edgecolor=GLASS, lw=1.4, linestyle=(0, (3, 2)) if behind else "solid",
            ))
            if behind:
                axis.annotate(
                    f"{name}: {2 * half:.0f} px wide, and entirely inside A",
                    xy=(centre, 0.95 * scale - 0.08), xytext=(centre, -0.34),
                    fontsize=NOTE_SIZE, color=INK, ha="center",
                    arrowprops={"arrowstyle": "->", "color": INK, "lw": 0.8},
                )
            else:
                axis.text(centre, 0.95 * scale + 0.07, f"{name}: {2 * half:.0f} px wide",
                          fontsize=NOTE_SIZE, color=INK, ha="center")
        overlap = min(c + h for c, h, _ in pair) - max(c - h for c, h, _ in pair)
        union = max(c + h for c, h, _ in pair) - min(c - h for c, h, _ in pair)
        note(
            axis, 0, 1.62,
            f"one patch, {union:.0f} px = {union * near_mm / FX:.0f} mm at A's distance" if overlap > 0
            else f"two patches, {-overlap:.0f} px of clear background between them",
            colour,
        )

    note(merged, 0, -0.98, "exactly one glass wide, so nothing is even flagged", WARN)
    note(apart, 0, -0.98, "connected components now returns two, unaided", GOOD)

    footer(
        figure,
        "Same two glasses, same table, same 180 mm between them. The left picture merges them and the "
        "right one does not, and no measurement taken inside either picture can say which is which.",
    )
    figure.subplots_adjust(bottom=0.13, top=0.90, wspace=0.08)
    save(figure, "01-viewpoint-artefact.png")


def main() -> None:
    picture_one_blob()
    picture_distance_transform()
    picture_markers()
    picture_flooding()
    picture_waist_depth()
    picture_grabcut()
    picture_hough()
    picture_viewpoint()


if __name__ == "__main__":
    main()
