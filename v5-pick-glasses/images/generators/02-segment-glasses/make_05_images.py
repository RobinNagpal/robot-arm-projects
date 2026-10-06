"""Diagrams for solution 5 — SAM 2 with a keeper.

Seven pictures, each carrying one point of the document:

    05-what-promptable-means.png     a fixed class list against a prompt, and
                                     the same picture prompted at two points
    05-the-prompt-grid.png           a regular grid of prompt points over the
                                     top view, and what each point returns
    05-everything-is-proposed.png    the pile that comes back: glasses, table,
                                     a rim on its own, two glasses as one
    05-the-keeper.png                the keeper as a funnel: proposals in, three answers out
    05-the-keeper-thresholds.png     the two thresholds, and the band of doubt between them
    05-the-keeper-trees.png          one shallow tree, and what boosting adds to it
                                     and as three answers with a doubtful band
    05-the-domain-gap.png            photographs against a grey picture shaded
                                     from depth, which is the honest risk
    05-borrowed-against-trained.png  what SAM 2 brings against what is fitted here,
                                     and against solution 2, which fits it all
    05-where-it-stops.png            a glass covered completely: no pixels, so
                                     no prompt point, so no proposal

Run from the project root:

    pixi run python images/generators/02-segment-glasses/make_05_images.py

Every number that appears as a label is computed from the constants at the top
of this file, so none of it can drift. The scenes are built from the shared cast
in ``diagram_style``, and their silhouettes come from ``splay_circles``, so the
geometry is the cell's own: which glass covers which is decided by
``splay_covers`` and checked before anything is drawn, and every arrangement is
asserted to be a legal one, with centres at least the guaranteed gap apart.

The two weight counts in the borrowed-against-fitted picture are arithmetic on
the published widths and depths of the models, not measurements of a file on
disk. They are the right size and within a few percent of it. The keeper's own
size is counted in its own terms, because it is boosted decision trees and a
tree has no weights: what is fitted there is a threshold per split and a value
per leaf.
"""

from __future__ import annotations

import numpy as np
from diagram_style import (
    FX,
    GLASS,
    GOOD,
    INK,
    KIND_NARROWEST,
    KIND_SHORTEST,
    KIND_TALLEST,
    KIND_WIDEST,
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
    splay_patch,
    splay_width,
)
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from matplotlib.patches import Circle, FancyBboxPatch, Polygon

RNG = np.random.default_rng(20250930)

# --------------------------------------------------------------------------- #
# the cell's own numbers
# --------------------------------------------------------------------------- #

MIN_APART = 150.0        # mm centre to centre, the closest two glasses ever stand
MM_PER_PIXEL = SURVEY_H / FX

# The prompt grid. SAM 2 is prompted with points laid out regularly in the
# picture; the table is flat and square to the camera, so a regular grid of
# pixels is a regular grid of millimetres on the table plane as well.
GRID_PIXELS = 24.0
GRID_MM = GRID_PIXELS * MM_PER_PIXEL

# SAM 2 answers one point with more than one mask, at more than one scale, and the
# same object is therefore proposed several times over.
MASKS_PER_POINT = 3

SLICES = 40               # slices per silhouette, as splay_circles uses

# The keeper: boosted decision trees over each proposal, which is the shape a
# short table of widths, errors, heights, ratios and counts asks for. Boosting
# fits a weak tree, then fits the next one to what the ones before it got wrong,
# and adds them up; for three answers it fits one set of trees per answer. This
# is the only thing fitted in the whole solution.
ANSWERS = ("keep", "more than one glass", "drop")
ROUNDS = 60             # boosting rounds
TREE_DEPTH = 3          # threshold questions asked on the way to a leaf

# The borrowed model, by its published shape.
VIT_LAYERS, VIT_WIDTH, VIT_PATCH, VIT_MLP = 12, 768, 16, 4
VIT_INPUT, VIT_CHANNELS = 1024, 3
NECK_WIDTH = 256
DECODER_LAYERS, DECODER_WIDTH, DECODER_MLP = 2, 256, 2048
DECODER_MASKS = 4

# Solution 2's network, for the comparison: a small U-Net with two heads, one
# per-pixel class map and two channels of votes for the centre.
UNET_WIDTHS = (16, 32, 64, 128)
UNET_INPUT_CHANNELS = 4


# --------------------------------------------------------------------------- #
# drawing helpers, in the style the other generators in this folder use
# --------------------------------------------------------------------------- #

def tint(colour: str, amount: float) -> tuple[float, float, float, float]:
    """A pale version of a palette colour: 1.0 is the colour, 0.0 is paper."""
    near = np.array(to_rgba(colour))
    far = np.array(to_rgba(PAPER))
    return tuple(far + (near - far) * amount)


GREY_PICTURE = LinearSegmentedColormap.from_list("depth", [INK, PAPER])
HALO = {"facecolor": PAPER, "edgecolor": "none", "alpha": 0.88, "pad": 2.4}


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, ha="left", va="top", weight="normal",
         halo=False):
    axis.text(x, y, text, fontsize=size, color=colour, ha=ha, va=va, zorder=8, weight=weight,
              bbox=HALO if halo else None)


def panel_title(axis, text, colour=INK, size=LABEL_SIZE + 0.6):
    axis.set_title(text, fontsize=size, color=colour, pad=8)


def box(axis, x, y, width, height, text, face, edge=MUTED, size=NOTE_SIZE, colour=INK, weight="normal"):
    """A rounded box with centred text, in axis fractions."""
    axis.add_patch(
        FancyBboxPatch(
            (x - width / 2.0, y - height / 2.0), width, height,
            boxstyle="round,pad=0.006,rounding_size=0.012",
            facecolor=face, edgecolor=edge, lw=1.0, zorder=4,
        )
    )
    axis.text(x, y, text, ha="center", va="center", fontsize=size, color=colour, zorder=6, weight=weight)


def arrow(axis, start, end, colour=INK, lw=1.3, style="->"):
    axis.annotate(
        "", xy=end, xytext=start,
        arrowprops={"arrowstyle": style, "color": colour, "lw": lw, "shrinkA": 2, "shrinkB": 2},
        zorder=7,
    )


# --------------------------------------------------------------------------- #
# the geometry: silhouettes, rasters and prompt points
# --------------------------------------------------------------------------- #

NADIR = np.array([0.0, 0.0])


def stack(centre, size, slices: int = SLICES):
    """The silhouette of one standing glass in the top view, as its circles."""
    return splay_circles(NADIR, np.asarray(centre, dtype=float), *size, slices=slices)


def stack_with_height(centre, size, slices: int = SLICES):
    """The same circles, each with the height of the slice that drew it."""
    height = size[0]
    return [
        (circle_centre, radius, height * index / (slices - 1))
        for index, (circle_centre, radius) in enumerate(stack(centre, size, slices))
    ]


def build(scene):
    """A name-to-silhouette map for a scene, checked for legality as it goes."""
    names = [name for name, _, _ in scene]
    for index, (name, centre, _) in enumerate(scene):
        for other_name, other_centre, _ in scene[index + 1:]:
            apart = float(np.hypot(*(np.asarray(centre) - np.asarray(other_centre))))
            assert apart >= MIN_APART - 1e-6, f"{name} and {other_name} stand {apart:.0f} mm apart"
    for _, _, size in scene:
        assert KIND_SHORTEST <= size[0] <= KIND_TALLEST, "a height outside this kind's range"
        assert KIND_NARROWEST <= size[1] <= KIND_WIDEST, "a width outside this kind's range"
    return names, {name: stack(centre, size) for name, centre, size in scene}


def extent_of(shapes, pad: float = 55.0, with_nadir: bool = True):
    """The drawn region a set of silhouettes needs, in millimetres."""
    xs, ys = ([0.0], [0.0]) if with_nadir else ([], [])
    for circles in shapes.values():
        for centre, radius in circles:
            xs += [centre[0] - radius, centre[0] + radius]
            ys += [centre[1] - radius, centre[1] + radius]
    return (min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad)


def topmost(point, scene):
    """Which glass a prompt point lands on, or None for bare table.

    The glass whose slice is highest at that point is the one nearest the lens,
    so that is the surface the point is on and the mask that comes back.
    """
    best_name, best_height = None, -1.0
    for name, centre, size in scene:
        for circle_centre, radius, height in stack_with_height(centre, size):
            if height > best_height and np.hypot(*(np.asarray(point) - circle_centre)) <= radius:
                best_name, best_height = name, height
    return best_name


def prompt_grid(extent, spacing: float = GRID_MM):
    """Prompt points, regular in the picture and so regular on the table."""
    x0, x1, y0, y1 = extent
    xs = np.arange(np.ceil(x0 / spacing) * spacing, x1 + 1e-9, spacing)
    ys = np.arange(np.ceil(y0 / spacing) * spacing, y1 + 1e-9, spacing)
    return [(float(x), float(y)) for y in ys for x in xs]


def height_raster(scene, extent, step: float = 3.0):
    """The height of the nearest surface at every cell of the drawn region.

    This is what the cell's renderer hands over, one number per pixel, and it is
    what the grey picture in the domain-gap figure is shaded from.
    """
    x0, x1, y0, y1 = extent
    xs = np.arange(x0, x1, step)
    ys = np.arange(y0, y1, step)
    grid_x, grid_y = np.meshgrid(xs, ys)
    heights = np.zeros(grid_x.shape)
    for _, centre, size in scene:
        for circle_centre, radius, height in stack_with_height(centre, size):
            inside = (grid_x - circle_centre[0]) ** 2 + (grid_y - circle_centre[1]) ** 2 <= radius ** 2
            heights = np.where(inside & (height > heights), height, heights)
    return xs, ys, heights


def merged(first, second) -> bool:
    """Do two silhouettes touch in the picture, so that they form one patch?"""
    for centre_a, radius_a in first:
        for centre_b, radius_b in second:
            if np.hypot(*(centre_a - centre_b)) <= radius_a + radius_b:
                return True
    return False


def label_spot(shapes, name, out: float = 30.0):
    """Just outside the far tip of a silhouette, where a name can be read."""
    centre, radius = shapes[name][-1]
    reach = float(np.hypot(*centre)) or 1.0
    return tuple(centre + centre / reach * (radius + out))


def middle_spot(shapes, name):
    """A point squarely inside a silhouette, for a prompt mark to sit on."""
    return tuple(shapes[name][len(shapes[name]) // 2][0])


def draw_glasses(axis, shapes, scene, strong=(), dim=0.13, lit=0.40):
    """Every silhouette in a scene, shortest first so the nearest paints last."""
    order = sorted(scene, key=lambda entry: entry[2][0])
    for name, _, _ in order:
        chosen = name in strong
        splay_patch(
            axis, shapes[name],
            colour=GOOD if chosen else GLASS,
            alpha=lit if chosen else dim,
            zorder=4 if chosen else 3,
        )


def name_the_glasses(axis, shapes, colour=INK, strong=()):
    for name in shapes:
        spot = label_spot(shapes, name)
        note(axis, spot[0], spot[1], name,
             colour=colour if not strong or name in strong else MUTED,
             size=LABEL_SIZE, ha="center", va="center",
             weight="bold" if name in strong else "normal")


def plan_axis(axis, extent, mark_nadir: bool = True, label_nadir: bool = True):
    """A top view in millimetres of table, measured from below the camera."""
    bare(axis)
    axis.set_xlim(extent[0], extent[1])
    axis.set_ylim(extent[2], extent[3])
    axis.set_aspect("equal")
    if mark_nadir:
        axis.scatter([0], [0], s=34, color=WARN, marker="x", zorder=9, linewidths=1.6)
        if label_nadir:
            note(axis, 14, -8, "below the camera", colour=WARN, va="top", size=NOTE_SIZE - 0.6)


# --------------------------------------------------------------------------- #
# the scene the first five pictures share
# --------------------------------------------------------------------------- #

# Four glasses of one kind, two near the top of its range of sizes and two near
# the bottom, every pair of centres at least the guaranteed gap apart. B stands
# directly out from A along the line away from the camera, which is what makes
# their two silhouettes run into one patch in the picture.
SCENE = (
    ("A", (-150.0, -60.0), TALL_A),
    ("B", (-272.0, -182.0), SHORT_A),
    ("C", (130.0, 120.0), TALL_B),
    ("D", (25.0, -175.0), SHORT_B),
)
NAMES, SHAPES = build(SCENE)
EXTENT = extent_of(SHAPES)
GRID = prompt_grid(EXTENT)
HITS = [topmost(point, SCENE) for point in GRID]
ON_GLASS = {name: HITS.count(name) for name in NAMES}
ON_TABLE = HITS.count(None)
SMALLEST_PATCH = min(splay_width(SHAPES[name]) for name in NAMES)
A_AND_B_MERGE = merged(SHAPES["A"], SHAPES["B"])
NONE_COVERED = not any(
    splay_covers(SHAPES[big], SHAPES[small])
    for big in NAMES for small in NAMES if big != small
)
assert A_AND_B_MERGE, "the shared scene is meant to have one patch holding two glasses"
assert NONE_COVERED, "no glass in the shared scene may be hidden completely"
assert all(count > 0 for count in ON_GLASS.values()), "every glass needs at least one prompt point"

# Two patches of bare table, for the proposal pile. Both sit clear of every
# silhouette, which is checked rather than eyeballed.
TABLE_PATCHES = (
    ((-100.0, 20.0), (90.0, 62.0), (62.0, -110.0), (-92.0, -70.0)),
    ((252.0, -206.0), (332.0, -206.0), (332.0, 58.0), (252.0, 58.0)),
)
for patch in TABLE_PATCHES:
    for corner in patch:
        assert topmost(corner, SCENE) is None, "a table patch is standing on a glass"

# What SAM 2 hands back for this scene, and which of it is a glass. The pile is
# what the model proposes, not what anybody asked for.
PROPOSALS = (
    ("glass A,\nwhole", ("glass", "A"), "keep"),
    ("glass C,\nwhole", ("glass", "C"), "keep"),
    ("glass D,\nwhole", ("glass", "D"), "keep"),
    ("glass B, the part\nof it in view", ("glass", "B"), "keep"),
    ("A and B as\none object", ("pair", ("A", "B")), "more than one glass"),
    ("the rim of A,\nwithout the glass", ("rim", "A"), "drop"),
    ("a patch of\nbare table", ("table", 0), "drop"),
    ("the strip of table\nat the edge", ("table", 1), "drop"),
)
ANSWERED = {answer: [label for label, _, given in PROPOSALS if given == answer]
            for answer in ANSWERS}
KEPT = len(ANSWERED["keep"])
RAW_MASKS = sum(1 for hit in HITS if hit is not None) * MASKS_PER_POINT

# The features the keeper is shown. Everything about the keeper's size is
# derived from this list, so adding a feature changes the arithmetic too.
FEATURES = (
    "how wide the circle fitted to it is, against the range this kind allows",
    "how round it is: its area against the area its outline could enclose",
    "how far its surface stands above the table, from the depth reading",
    "how far it sits from the point directly below the camera",
    "how many prompt points returned this same mask",
    "whether another proposal contains it, or it contains one",
    "how much of its outline is a step in depth rather than a smooth run",
    "its area on the table, in square millimetres",
)


# --------------------------------------------------------------------------- #
# weight arithmetic for the borrowed-against-fitted picture
# --------------------------------------------------------------------------- #

def dense_weights(count_in: int, count_out: int) -> int:
    return count_in * count_out + count_out


def mlp_weights(sizes) -> int:
    return sum(dense_weights(a, b) for a, b in zip(sizes[:-1], sizes[1:], strict=False))


def conv_weights(kernel: int, count_in: int, count_out: int) -> int:
    return kernel * kernel * count_in * count_out + count_out


def attention_weights(width: int, rate: int = 1) -> int:
    """One attention block: three projections in, one out, biases included."""
    inner = width // rate
    return 3 * dense_weights(width, inner) + dense_weights(inner, width)


def norm_weights(width: int) -> int:
    return 2 * width


def image_encoder_weights() -> int:
    """A ViT-B image encoder plus the neck that narrows it, from its shape."""
    tokens = (VIT_INPUT // VIT_PATCH) ** 2
    patch_embedding = conv_weights(VIT_PATCH, VIT_CHANNELS, VIT_WIDTH)
    position = tokens * VIT_WIDTH
    per_layer = (
        attention_weights(VIT_WIDTH)
        + mlp_weights((VIT_WIDTH, VIT_WIDTH * VIT_MLP, VIT_WIDTH))
        + 2 * norm_weights(VIT_WIDTH)
    )
    neck = (
        conv_weights(1, VIT_WIDTH, NECK_WIDTH)
        + conv_weights(3, NECK_WIDTH, NECK_WIDTH)
        + 2 * norm_weights(NECK_WIDTH)
    )
    return patch_embedding + position + VIT_LAYERS * per_layer + neck


def promptable_head_weights() -> int:
    """The prompt encoder and the mask decoder, from their shape."""
    width, hidden = DECODER_WIDTH, DECODER_MLP
    per_layer = (
        attention_weights(width)                 # the tokens attend to each other
        + attention_weights(width, rate=2)       # the tokens attend to the picture
        + mlp_weights((width, hidden, width))
        + attention_weights(width, rate=2)       # the picture attends to the tokens
        + 4 * norm_weights(width)
    )
    final = attention_weights(width, rate=2) + norm_weights(width)
    upscale = conv_weights(2, width, width // 4) + conv_weights(2, width // 4, width // 8)
    mask_heads = DECODER_MASKS * mlp_weights((width, width, width // 8))
    quality_head = mlp_weights((width, width, DECODER_MASKS))
    tokens = (4 + 1 + DECODER_MASKS + 1 + 1) * width      # point types, masks, quality
    coarse_mask = (
        conv_weights(2, 1, DECODER_MASKS)
        + conv_weights(2, DECODER_MASKS, DECODER_MASKS * 4)
        + conv_weights(1, DECODER_MASKS * 4, width)
    )
    return DECODER_LAYERS * per_layer + final + upscale + mask_heads + quality_head + tokens + coarse_mask


def unet_weights(widths=UNET_WIDTHS, channels_in: int = UNET_INPUT_CHANNELS) -> int:
    """Solution 2's network: a U-Net down and up, with two heads on the end."""
    total, previous = 0, channels_in
    for width in widths:
        total += conv_weights(3, previous, width) + conv_weights(3, width, width)
        previous = width
    for index in range(len(widths) - 2, -1, -1):
        width = widths[index]
        total += conv_weights(2, previous, width)
        total += conv_weights(3, width * 2, width) + conv_weights(3, width, width)
        previous = width
    total += conv_weights(1, widths[0], 1)      # the class map
    total += conv_weights(1, widths[0], 2)      # the two channels of votes
    return total


ENCODER = image_encoder_weights()
HEAD = promptable_head_weights()
BORROWED = ENCODER + HEAD
SOLUTION_TWO = unet_weights()

# The keeper's size, in the only terms a tree has. A tree of this depth ends in
# 2**depth leaves and reaches them through one fewer split, and one number is
# fitted at each: a threshold at a split, a value at a leaf.
LEAVES_PER_TREE = 2 ** TREE_DEPTH
SPLITS_PER_TREE = LEAVES_PER_TREE - 1
TREES = ROUNDS * len(ANSWERS)
FITTED_THRESHOLDS = TREES * SPLITS_PER_TREE
FITTED_LEAVES = TREES * LEAVES_PER_TREE
FITTED_NUMBERS = FITTED_THRESHOLDS + FITTED_LEAVES
BORROWED_PER_FITTED = BORROWED / FITTED_NUMBERS


# --------------------------------------------------------------------------- #
# 1. what promptable means
# --------------------------------------------------------------------------- #

def figure_what_promptable_means() -> None:
    """A fixed class list answers a question chosen in advance; a prompt does not."""
    figure, (left, middle, right) = new(15.4, 6.0, columns=3)

    # ---- a model with a fixed list of classes ----------------------------
    bare(left)
    left.set_xlim(0, 1)
    left.set_ylim(0, 1)
    panel_title(left, "A model with a fixed list of classes", colour=WARN)

    box(left, 0.24, 0.80, 0.34, 0.13, "the picture", tint(GLASS, 0.14), edge=GLASS, size=LABEL_SIZE)
    box(left, 0.24, 0.58, 0.34, 0.13, "weights, as fitted", tint(MUTED, 0.18), edge=MUTED, size=LABEL_SIZE)
    arrow(left, (0.24, 0.735), (0.24, 0.648), colour=INK)
    arrow(left, (0.42, 0.58), (0.58, 0.58), colour=INK)

    listed = ("person", "chair", "dining table", "cup", "bowl", "bottle", "wine glass", "...")
    left.add_patch(
        FancyBboxPatch(
            (0.60, 0.20), 0.38, 0.55,
            boxstyle="round,pad=0.008,rounding_size=0.014",
            facecolor=tint(WARN, 0.07), edgecolor=WARN, lw=1.1, zorder=3,
        )
    )
    note(left, 0.79, 0.80, "one answer per name,\non a list decided in advance",
         colour=WARN, ha="center", va="bottom", size=NOTE_SIZE)
    for index, name in enumerate(listed):
        note(left, 0.67, 0.685 - index * 0.062, name, colour=INK, size=NOTE_SIZE, va="center")
    note(
        left, 0.02, 0.12,
        "The question was chosen when the weights were fitted, so the answer is\n"
        "a score for each of those names and nothing else. To ask about\n"
        "something the list does not hold, the weights have to be changed.",
        colour=INK, va="top",
    )

    # ---- the same picture, prompted twice --------------------------------
    for axis, target, ordinal in ((middle, "C", "first"), (right, "D", "second")):
        plan_axis(axis, EXTENT)
        draw_glasses(axis, SHAPES, SCENE, strong=(target,))
        point = middle_spot(SHAPES, target)
        axis.scatter([point[0]], [point[1]], s=130, color=WARN, marker="+", zorder=10, linewidths=2.2)
        panel_title(axis, f"A promptable model: the {ordinal} point", colour=GOOD)
        name_the_glasses(axis, SHAPES, strong=(target,))
        note(axis, EXTENT[0] + 14, EXTENT[3] - 14,
             f"prompt: this one point\nanswer: the mask of glass {target},\nand nothing about the rest",
             colour=GOOD, va="top")

    note(
        middle, EXTENT[0] + 14, EXTENT[3] - 120,
        "The picture goes through the large part of the\nmodel once. The prompt goes through a small part.",
        colour=INK, va="top",
    )
    note(
        right, EXTENT[0] + 14, EXTENT[3] - 120,
        "So a second point costs almost nothing, and it asks\na different question, not a retrained model.",
        colour=INK, va="top",
    )

    figure.suptitle(
        "Promptable means the question is asked when the picture arrives, not when the weights were fitted.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        "The same picture and the same weights give two different masks, because the prompt changed and "
        "nothing else did. That is the whole reason this\nsolution can use a model that was never shown a "
        "drinking glass of this kind: it is not asked what the object is, only which pixels belong to "
        "whatever\nthe point landed on. Deciding which of those masks is a glass is a separate job, and it "
        "is the only job this solution fits any weights for.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    save(figure, "05-what-promptable-means.png")


# --------------------------------------------------------------------------- #
# 2. the prompt grid
# --------------------------------------------------------------------------- #

def figure_the_prompt_grid() -> None:
    """A regular grid of points, and what each point returns."""
    figure, (left, right) = new(14.6, 6.8, columns=2)

    plan_axis(left, EXTENT)
    panel_title(left, f"A prompt point every {GRID_MM:.0f} mm, laid over the top view")
    draw_glasses(left, SHAPES, SCENE)
    on_glass_x = [point[0] for point, hit in zip(GRID, HITS, strict=False) if hit is not None]
    on_glass_y = [point[1] for point, hit in zip(GRID, HITS, strict=False) if hit is not None]
    on_table_x = [point[0] for point, hit in zip(GRID, HITS, strict=False) if hit is None]
    on_table_y = [point[1] for point, hit in zip(GRID, HITS, strict=False) if hit is None]
    left.scatter(on_table_x, on_table_y, s=9, facecolor=PAPER, edgecolor=MUTED, linewidths=0.7, zorder=6)
    left.scatter(on_glass_x, on_glass_y, s=16, color=GOOD, zorder=7, linewidths=0)
    name_the_glasses(left, SHAPES)
    note(left, EXTENT[0] + 14, EXTENT[3] - 14,
         "filled: the point landed on a glass\nhollow: the point landed on the table",
         colour=INK, va="top", halo=True)

    # ---- what comes back -------------------------------------------------
    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    panel_title(right, "What the grid gets back, counted")

    note(right, 0.075, 0.905, "prompt lands on", colour=MUTED, size=NOTE_SIZE, va="center")
    note(right, 0.475, 0.905, "points", colour=MUTED, size=NOTE_SIZE, va="center", ha="center")
    note(right, 0.755, 0.905, "masks that come back", colour=MUTED, size=NOTE_SIZE, va="center", ha="center")

    rows = [(f"glass {name}", ON_GLASS[name], "the same mask, every time") for name in NAMES]
    rows.append(("bare table", ON_TABLE, "a mask of table, every time"))
    top, step = 0.815, 0.108
    for index, (label, count, answer) in enumerate(rows):
        y = top - index * step
        glass_row = index < len(NAMES)
        face = tint(GOOD, 0.10) if glass_row else tint(MUTED, 0.12)
        edge = GOOD if glass_row else MUTED
        box(right, 0.505, y, 0.93, 0.082, "", face, edge=edge)
        note(right, 0.075, y, label, colour=INK, size=LABEL_SIZE, va="center")
        note(right, 0.475, y, f"{count}", colour=INK, size=LABEL_SIZE, va="center", ha="center",
             weight="bold")
        note(right, 0.755, y, answer, colour=INK if glass_row else MUTED, size=NOTE_SIZE,
             va="center", ha="center")

    note(
        right, 0.045, 0.245,
        f"The grid knows nothing about where the glasses are. It only has to be fine\n"
        f"enough that every glass gets at least one point: the spacing is {GRID_MM:.0f} mm,\n"
        f"comfortably finer than the smallest patch any glass in this scene leaves, so\n"
        f"no glass can be stepped over. Even B, which stands mostly behind A, collects\n"
        f"points of its own from the part of it in view.",
        colour=INK, va="top",
    )
    note(
        right, 0.045, 0.085,
        f"{len(GRID)} points in all: {len(GRID) - ON_TABLE} on glass and {ON_TABLE} on table. Most of the "
        f"work is wasted,\nand that is accepted, because nothing had to be told where to look.",
        colour=GOOD, va="top",
    )

    figure.suptitle(
        "Prompting on a grid: points on the same glass return the same mask, points on the table return "
        "table.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    save(figure, "05-the-prompt-grid.png")


# --------------------------------------------------------------------------- #
# 3. everything is proposed
# --------------------------------------------------------------------------- #

def draw_proposal(axis, kind) -> None:
    """One proposal drawn over a faint copy of the whole scene."""
    plan_axis(axis, EXTENT, mark_nadir=False)
    draw_glasses(axis, SHAPES, SCENE, dim=0.016)
    what, which = kind
    if what == "glass":
        splay_patch(axis, SHAPES[which], colour=GOOD, alpha=0.30, zorder=6)
    elif what == "pair":
        for name in which:
            splay_patch(axis, SHAPES[name], colour=WARN, alpha=0.30, zorder=6)
    elif what == "rim":
        centre, radius = SHAPES[which][-1]
        axis.add_patch(Circle(tuple(centre), radius, facecolor=WARN, alpha=0.75,
                              edgecolor=WARN, lw=1.0, zorder=6))
    else:
        axis.add_patch(Polygon(TABLE_PATCHES[which], closed=True, facecolor=MUTED, alpha=0.75,
                               edgecolor=MUTED, lw=1.0, zorder=6))


def figure_everything_is_proposed() -> None:
    """The pile of masks that comes back, and what is not in it: a name."""
    figure, (left, right) = new(15.2, 7.4, columns=2)

    plan_axis(left, EXTENT)
    panel_title(left, "The picture SAM 2 was given")
    draw_glasses(left, SHAPES, SCENE)
    name_the_glasses(left, SHAPES)
    note(left, EXTENT[0] + 14, EXTENT[3] - 14,
         "Four glasses stand on the table. In the picture\nA and B run together into one patch, because B\n"
         "stands directly out from A along the line away\nfrom the camera.",
         colour=INK, va="top", halo=True)
    note(left, 120, -70,
         f"{RAW_MASKS} masks come back from the {len(GRID) - ON_TABLE} points\nthat landed on something, at "
         f"{MASKS_PER_POINT} scales each.\nNear-duplicates collapse, and {len(PROPOSALS)} "
         f"distinct\nproposals "
         "are left. They are the eight\non the right.",
         colour=INK, va="top", halo=True)

    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    panel_title(right, f"The {len(PROPOSALS)} proposals, and not one of them carries a name")

    columns, cell_w, cell_h = 4, 0.225, 0.30
    gap_x = (1.0 - columns * cell_w) / (columns + 1)
    for index, (label, kind, _) in enumerate(PROPOSALS):
        column, row = index % columns, index // columns
        x = gap_x + column * (cell_w + gap_x)
        y = 0.615 - row * 0.44
        inset = right.inset_axes([x, y, cell_w, cell_h])
        draw_proposal(inset, kind)
        note(right, x + cell_w / 2.0, y - 0.022, label, colour=INK, size=NOTE_SIZE - 0.4,
             ha="center", va="top")

    figure.suptitle(
        "Segment anything means exactly that: everything is proposed, and nothing is named.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.015,
        "Whole glasses, patches of table, a part of one glass and a pair of glasses taken as one object all "
        "come back on the same footing. Nothing in the pile says\nwhich proposals are glasses, which are "
        "pieces of furniture, or which two of them are the same object proposed twice. The model was never "
        "told what a glass is,\nso it cannot say, and that is not a fault in it: it is what a promptable "
        "model is for. Somebody else has to do the deciding, and here that somebody is the keeper.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    save(figure, "05-everything-is-proposed.png")


# --------------------------------------------------------------------------- #
# 4. the keeper
# --------------------------------------------------------------------------- #

def tree_glyph(axis, x, y, width, height, colour=GOOD, lw=0.9) -> None:
    """A tiny two-level tree, for the row of weak trees."""
    top = (x, y + height / 2.0)
    middle = [(x - width / 4.0, y), (x + width / 4.0, y)]
    leaves = [
        (x - width / 2.0, y - height / 2.0), (x - width / 8.0, y - height / 2.0),
        (x + width / 8.0, y - height / 2.0), (x + width / 2.0, y - height / 2.0),
    ]
    for node in middle:
        axis.plot([top[0], node[0]], [top[1], node[1]], color=colour, lw=lw, zorder=4)
    for index, leaf in enumerate(leaves):
        parent = middle[index // 2]
        axis.plot([parent[0], leaf[0]], [parent[1], leaf[1]], color=colour, lw=lw, zorder=4)
    axis.scatter([top[0]] + [node[0] for node in middle], [top[1]] + [node[1] for node in middle],
                 s=11, color=colour, zorder=5, linewidths=0)
    axis.scatter([leaf[0] for leaf in leaves], [leaf[1] for leaf in leaves], s=13, color=colour,
                 marker="s", zorder=5, linewidths=0)


def figure_the_keeper() -> None:
    """Many proposals in, one of three answers out for each.

    One picture, one idea. What the keeper is made of and where its two
    thresholds sit used to share this figure; they are their own pictures now,
    and the sentences that were drawn under each of them are prose in the
    document, which is where the house rules put an explanation.
    """
    figure, left = new(8.6, 5.4)

    bare(left)
    left.set_xlim(0, 1)
    left.set_ylim(0, 1)
    panel_title(left, "Many proposals in, one of three answers out for each")

    note(left, 0.145, 0.995, f"{len(PROPOSALS)} proposals in", colour=INK, size=NOTE_SIZE,
         ha="center", va="center", weight="bold")
    top, step = 0.930, 0.105
    for index, (label, _, _) in enumerate(PROPOSALS):
        y = top - index * step
        box(left, 0.145, y, 0.25, 0.085, label.replace("\n", " "), tint(GLASS, 0.10), edge=GLASS,
            size=NOTE_SIZE - 1.8)
        arrow(left, (0.272, y), (0.305, 0.590 + (y - 0.562) * 0.72), colour=MUTED, lw=0.7)

    left.add_patch(
        Polygon(
            [(0.31, 0.960), (0.50, 0.680), (0.56, 0.680), (0.56, 0.500), (0.50, 0.500), (0.31, 0.220)],
            closed=True, facecolor=tint(GOOD, 0.10), edgecolor=GOOD, lw=1.2, zorder=2,
        )
    )
    note(left, 0.40, 0.620, "the keeper", colour=GOOD, size=LABEL_SIZE, ha="center", va="center",
         weight="bold")
    note(left, 0.40, 0.560, "boosted\ndecision trees", colour=INK, size=NOTE_SIZE - 1.0,
         ha="center", va="top")

    outcomes = (
        ("keep", f"{len(ANSWERED['keep'])} of the {len(PROPOSALS)}: one glass", GOOD),
        ("more than one glass", f"{len(ANSWERED['more than one glass'])}: prompt again inside it",
         WARN),
        ("drop", f"{len(ANSWERED['drop'])}: not a glass at all", MUTED),
    )
    for index, (heading, body, colour) in enumerate(outcomes):
        y = 0.830 - index * 0.280
        box(left, 0.800, y, 0.36, 0.165, "", tint(colour, 0.09), edge=colour)
        note(left, 0.800, y + 0.035, heading, colour=colour, size=NOTE_SIZE + 0.4, ha="center",
             va="center", weight="bold")
        note(left, 0.800, y - 0.015, body, colour=INK, size=NOTE_SIZE - 1.0, ha="center",
             va="center")
        arrow(left, (0.568, 0.590), (0.608, y), colour=colour, lw=1.0)

    figure.suptitle(
        "The keeper: the one thing fitted in this cell",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    save(figure, "05-the-keeper.png")


def figure_the_keeper_thresholds() -> None:
    """Two thresholds rather than one, and the band between them.

    Its own picture, because a band of doubt is a different idea from the funnel
    that feeds it, and a reader meets the two a few paragraphs apart.
    """
    figure, axis = new(8.6, 2.6)
    bare(axis)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    panel_title(axis, "How sure the keeper is that a proposal is one glass")

    line_y, height = 0.50, 0.26
    bands = (
        (0.02, 0.33, "drop", WARN),
        (0.33, 0.63, "I cannot tell:\ntake another picture", MUTED),
        (0.63, 0.98, "keep", GOOD),
    )
    for x0, x1, label, colour in bands:
        axis.add_patch(
            Polygon([(x0, line_y - height / 2.0), (x1, line_y - height / 2.0),
                     (x1, line_y + height / 2.0), (x0, line_y + height / 2.0)],
                    closed=True, facecolor=tint(colour, 0.16), edgecolor=colour, lw=1.0, zorder=3)
        )
        note(axis, (x0 + x1) / 2.0, line_y, label, colour=INK, size=NOTE_SIZE - 0.8, ha="center",
             va="center")
    for x, label in ((0.33, "the lower threshold"), (0.63, "the higher threshold")):
        axis.plot([x, x], [line_y - height * 0.8, line_y + height * 0.8], color=INK, lw=1.2,
                  zorder=6)
        note(axis, x, line_y + height * 0.8 + 0.04, label, colour=INK, size=NOTE_SIZE - 1.0,
             ha="center", va="bottom")
    note(axis, 0.02, line_y - height / 2.0 - 0.06, "certainly not one glass", colour=MUTED,
         size=NOTE_SIZE - 1.2, va="top")
    note(axis, 0.98, line_y - height / 2.0 - 0.06, "certainly one glass", colour=MUTED,
         size=NOTE_SIZE - 1.2, ha="right", va="top")

    figure.tight_layout()
    save(figure, "05-the-keeper-thresholds.png")


def figure_the_keeper_trees() -> None:
    """What one tree does, and what boosting adds to it.

    The eight numbers every question is asked about used to sit under this as a
    boxed list. A list is a list, so it is a table in the document now.
    """
    figure, right = new(10.4, 5.8)
    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    panel_title(right, "What the keeper is: shallow trees, each fitted to the last one's mistakes")

    note(right, 0.02, 0.960, "One tree", colour=INK, size=LABEL_SIZE, va="center", weight="bold")

    root = (0.50, 0.855)
    nodes = ((0.235, 0.690), (0.765, 0.690))
    leaves = (
        (0.130, 0.510, "towards\nmore than one glass", WARN),
        (0.370, 0.510, "towards\nnot a glass", MUTED),
        (0.630, 0.510, "towards not a glass:\nit is a part", MUTED),
        (0.870, 0.510, "towards\none glass", GOOD),
    )
    box(right, root[0], root[1], 0.36, 0.090,
        "is the fitted width inside the range this kind allows?",
        tint(GLASS, 0.12), edge=GLASS, size=NOTE_SIZE - 1.2)
    box(right, nodes[0][0], nodes[0][1], 0.30, 0.090,
        "is it wider than the widest\nthe kind allows?", tint(GLASS, 0.12), edge=GLASS,
        size=NOTE_SIZE - 1.2)
    box(right, nodes[1][0], nodes[1][1], 0.30, 0.090,
        "does another proposal\ncontain it?", tint(GLASS, 0.12), edge=GLASS, size=NOTE_SIZE - 1.2)
    for (node_x, node_y), answer in zip(nodes, ("no", "yes"), strict=False):
        right.plot([root[0], node_x], [root[1] - 0.050, node_y + 0.050], color=INK, lw=1.0, zorder=3)
        note(right, (root[0] + node_x) / 2.0, (root[1] + node_y) / 2.0, answer, colour=INK,
             size=NOTE_SIZE - 1.4, ha="center", va="center", halo=True)
    for index, (leaf_x, leaf_y, text, colour) in enumerate(leaves):
        parent_x, parent_y = nodes[index // 2]
        right.plot([parent_x, leaf_x], [parent_y - 0.050, leaf_y + 0.054], color=INK, lw=1.0,
                   zorder=3)
        note(right, (parent_x + leaf_x) / 2.0, (parent_y + leaf_y) / 2.0,
             "yes" if index % 2 == 0 else "no", colour=INK, size=NOTE_SIZE - 1.4, ha="center",
             va="center", halo=True)
        box(right, leaf_x, leaf_y, 0.19, 0.100, text, tint(colour, 0.13), edge=colour,
            size=NOTE_SIZE - 1.4)

    note(right, 0.02, 0.330, "Boosting: the next tree is fitted to what the ones before got wrong",
         colour=INK, size=LABEL_SIZE, va="center", weight="bold")
    glyph_y = 0.195
    spots = (0.085, 0.275, 0.465, 0.700)
    captions = ("the 1st", "the 2nd", "the 3rd", f"the {TREES}th")
    for index, x in enumerate(spots):
        tree_glyph(right, x, glyph_y, 0.105, 0.100)
        note(right, x, glyph_y - 0.082, captions[index], colour=INK, size=NOTE_SIZE - 1.0,
             ha="center", va="top")
    for x in (0.180, 0.370):
        note(right, x, glyph_y, "+", colour=GOOD, size=LABEL_SIZE + 2, ha="center", va="center")
    note(right, 0.583, glyph_y, "+  ...  +", colour=GOOD, size=LABEL_SIZE, ha="center", va="center")
    note(right, 0.790, glyph_y, "=", colour=GOOD, size=LABEL_SIZE + 2, ha="center", va="center")
    box(right, 0.898, glyph_y, 0.185, 0.140, "one score for each\nof the three answers",
        tint(GOOD, 0.14), edge=GOOD, size=NOTE_SIZE - 1.2)

    figure.tight_layout()
    save(figure, "05-the-keeper-trees.png")


# --------------------------------------------------------------------------- #
# 5. the domain gap
# --------------------------------------------------------------------------- #

def figure_the_domain_gap() -> None:
    """What the weights were fitted on, beside what this cell can render."""
    figure, (left, right) = new(14.0, 6.8, columns=2)

    x0, x1, y0, y1 = EXTENT
    span_x, span_y = x1 - x0, y1 - y0

    # ---- an everyday photograph -----------------------------------------
    bare(left)
    left.set_xlim(x0, x1)
    left.set_ylim(y0, y1)
    left.set_aspect("equal")
    panel_title(left, "What the weights were fitted on: ordinary photographs", colour=GOOD)

    rows, columns = 120, 150
    wall = np.linspace(0.0, 1.0, rows)[:, None] * np.ones((1, columns))
    picture = np.zeros((rows, columns, 3))
    high, low = np.array(tint(GLASS, 0.55))[:3], np.array(tint(MUTED, 0.55))[:3]
    for channel in range(3):
        picture[:, :, channel] = low[channel] + (high[channel] - low[channel]) * wall
    surface = int(rows * 0.42)
    wood = np.array(tint(WARN, 0.60))[:3]
    grain = 0.10 * np.sin(np.linspace(0, 26, columns))[None, :]
    for channel in range(3):
        picture[:surface, :, channel] = wood[channel] + grain[0]
    picture += RNG.normal(0.0, 0.035, picture.shape)
    left.imshow(np.clip(picture, 0.0, 1.0), extent=(x0, x1, y0, y1), origin="lower",
                interpolation="bilinear", zorder=0)

    for centre, radius, colour in (
        ((-0.26, -0.18), 0.115, GOOD),
        ((0.06, -0.24), 0.150, WARN),
        ((0.38, -0.14), 0.100, GLASS),
    ):
        middle = (x0 + span_x * (0.5 + centre[0]), y0 + span_y * (0.5 + centre[1]))
        size = span_y * radius
        left.add_patch(Circle(middle, size * 1.10, facecolor=INK, alpha=0.22, zorder=2))
        left.add_patch(Circle(middle, size, facecolor=colour, edgecolor=INK, lw=0.8, alpha=0.95,
                              zorder=3))
        left.add_patch(Circle((middle[0] - size * 0.32, middle[1] + size * 0.34), size * 0.24,
                              facecolor=PAPER, alpha=0.75, zorder=4))
    for x_fraction, width, colour in ((0.06, 0.10, GOOD), (0.74, 0.13, WARN)):
        left.add_patch(
            Polygon(
                [
                    (x0 + span_x * x_fraction, y0 + span_y * 0.44),
                    (x0 + span_x * (x_fraction + width), y0 + span_y * 0.44),
                    (x0 + span_x * (x_fraction + width), y0 + span_y * 0.80),
                    (x0 + span_x * x_fraction, y0 + span_y * 0.80),
                ],
                closed=True, facecolor=colour, alpha=0.55, edgecolor=INK, lw=0.7, zorder=2,
            )
        )
    note(left, x0 + span_x * 0.03, y0 + span_y * 0.96,
         "colour that separates one object from the next,\ntexture, highlights, cast shadows, clutter behind",
         colour=INK, va="top", halo=True)
    note(left, x0 + span_x * 0.03, y0 + span_y * 0.04,
         "Drawn here as a stand-in. What matters is what it has,\nand what the panel on the right does not.",
         colour=INK, va="bottom", size=NOTE_SIZE - 0.6, halo=True)

    # ---- what this cell renders -----------------------------------------
    bare(right)
    right.set_xlim(x0, x1)
    right.set_ylim(y0, y1)
    right.set_aspect("equal")
    panel_title(right, "What this cell can render: grey, shaded from depth", colour=WARN)

    xs, ys, heights = height_raster(SCENE, EXTENT)
    shade = 0.30 + 0.60 * heights / KIND_TALLEST
    right.imshow(shade, extent=(xs[0], xs[-1], ys[0], ys[-1]), origin="lower", cmap=GREY_PICTURE,
                 vmin=0.0, vmax=1.0, interpolation="nearest", zorder=0)
    note(right, x0 + span_x * 0.03, y0 + span_y * 0.96,
         "one number per pixel: how far away the nearest\nsurface is. Lighter is nearer the camera.",
         colour=INK, va="top", halo=True)

    swatch = span_y * 0.050
    base_x, base_y = x0 + span_x * 0.34, y0 + span_y * 0.08
    for index, channel in enumerate(("red", "green", "blue")):
        corner = base_x + index * swatch * 1.35
        right.add_patch(
            Polygon(
                [(corner, base_y), (corner + swatch, base_y),
                 (corner + swatch, base_y + swatch), (corner, base_y + swatch)],
                closed=True, facecolor=tint(INK, 0.45), edgecolor=INK, lw=0.7, zorder=5,
            )
        )
        note(right, corner + swatch / 2.0, base_y - swatch * 0.22, channel, colour=INK,
             size=NOTE_SIZE - 1.4, ha="center", va="top", halo=True)
    note(right, base_x, base_y + swatch * 1.30, "the same grey picture,\ncopied three times",
         colour=INK, va="bottom", size=NOTE_SIZE - 0.6, halo=True)

    figure.suptitle(
        "The honest risk: the borrowed weights have never seen a picture like the one this cell can give "
        "them.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.05,
        "The renderer gives a distance per pixel and an identity per pixel. It does not give colour, so the "
       "code shades the depth into a grey picture and repeats it\nacross the three channels the model "
       "expects. Every cue the weights were fitted with is then missing at once: there is no colour to "
       "separate one object from\nthe next, no texture inside a surface, no highlight on a rim, no shadow "
        "under a base and nothing behind the table. This is the largest risk in the solution, and it\ncannot "
        "be trained away, "
        "because the whole point of this solution is that the borrowed part is never trained.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    save(figure, "05-the-domain-gap.png")


# --------------------------------------------------------------------------- #
# 6. borrowed against trained
# --------------------------------------------------------------------------- #

def figure_borrowed_against_trained() -> None:
    """What SAM 2 brings, against what is fitted here, against solution 2."""
    figure, (left, right) = new(15.4, 7.2, columns=2)

    bars = (
        (
            "SAM 2, borrowed whole and never trained here",
            "weights in a neural network",
            BORROWED, MUTED,
        ),
        (
            "the keeper, the one thing fitted here",
            f"thresholds and leaf values in {TREES} shallow trees",
            FITTED_NUMBERS, GOOD,
        ),
        (
            "solution 2's network, fitted here from scratch",
            "weights in a neural network",
            SOLUTION_TWO, GLASS,
        ),
    )

    panel_title(left, "How much of each, on a scale where each step is ten times the last")
    low = 1.0
    high = 10.0 ** np.ceil(np.log10(max(value for _, _, value, _ in bars)))
    left.set_xscale("log")
    left.set_xlim(low, high * 4.0)
    left.set_ylim(-2.35, len(bars) - 0.05)
    bare(left)
    left.tick_params(which="both", bottom=False, top=False, left=False, right=False,
                     labelbottom=False, labelleft=False)

    decade = low
    while decade <= high:
        left.plot([decade, decade], [-0.62, len(bars) - 0.42], color=MUTED, lw=0.6,
                  ls=(0, (3, 4)), zorder=1)
        note(left, decade, -0.70, f"{decade:,.0f}", colour=MUTED, size=NOTE_SIZE - 1.4,
             ha="center", va="top")
        decade *= 10.0
    note(left, low, -0.94, "numbers fitted, or brought", colour=MUTED, size=NOTE_SIZE, va="top")

    for index, (label, kind, value, colour) in enumerate(bars):
        y = len(bars) - 1 - index
        left.barh([y], [value], left=low, height=0.40, color=tint(colour, 0.55),
                  edgecolor=colour, linewidth=1.1, zorder=3)
        note(left, value * 1.25, y, f"{value:,}", colour=colour, size=LABEL_SIZE, va="center",
             weight="bold")
        note(left, low * 1.4, y + 0.42, label, colour=INK, size=NOTE_SIZE, va="bottom", halo=True)
        note(left, low * 1.4, y + 0.24, kind, colour=MUTED, size=NOTE_SIZE - 1.2, va="bottom",
             halo=True)

    note(
        left, low * 1.4, -1.14,
        "The middle bar is not the same kind of number as the other two, and that is the point\n"
        "rather than a fault in the picture. A neural network fits a weight to every connection it\n"
        "has. A decision tree has no weights at all: what is fitted is one threshold at each split\n"
        f"and one value at each leaf, which here is {FITTED_THRESHOLDS:,} thresholds and "
        f"{FITTED_LEAVES:,} leaf values.\n"
        "The bars say how much was fitted. They do not say it is the same kind of thing.",
        colour=INK, va="top",
    )

    # ---- the two solutions side by side ---------------------------------
    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    panel_title(right, "The same question asked two ways")

    box(right, 0.37, 0.940, 0.36, 0.072, "solution 5\nborrow almost everything",
        tint(GOOD, 0.14), edge=GOOD, size=NOTE_SIZE, weight="bold")
    box(right, 0.79, 0.940, 0.36, 0.072, "solution 2\nfit everything from scratch",
        tint(GLASS, 0.14), edge=GLASS, size=NOTE_SIZE, weight="bold")

    rows = (
        (
            "what it brings in,\nfitted somewhere else",
            f"{BORROWED:,} weights, used\nexactly as downloaded",
            "nothing",
        ),
        (
            "what is fitted here",
            f"{TREES} shallow trees:\n{FITTED_NUMBERS:,} thresholds and leaf values",
            f"{SOLUTION_TWO:,} weights,\nevery one of them",
        ),
        (
            "what kind of thing\nis fitted",
            "threshold questions and leaves,\nfitted on the processor in seconds",
            "weights, fitted by following\na gradient through a picture",
        ),
        (
            "what the fitted part\nhas to learn",
            "which measurements of a\nproposal go with a glass",
            "which pixels are glass, and\nwhere each centre is",
        ),
        (
            "training scenes needed",
            "a few, because so little\nis being fitted",
            "many, because everything\nis being fitted",
        ),
        (
            "what it was fitted on",
            "everyday photographs, for\nthe part that finds objects",
            "this cell's own pictures,\nand nothing else",
        ),
        (
            "where the risk sits",
            "the borrowed part has never\nseen a picture like this one",
            "the fitted part has seen\nnothing but pictures like it",
        ),
    )
    top, step = 0.815, 0.121
    for index, (question, borrowing, fitting) in enumerate(rows):
        y = top - index * step
        note(right, 0.175, y, question, colour=INK, size=NOTE_SIZE, ha="right", va="center")
        box(right, 0.37, y, 0.36, 0.098, borrowing, tint(GOOD, 0.07), edge=GOOD,
            size=NOTE_SIZE - 1.0)
        box(right, 0.79, y, 0.36, 0.098, fitting, tint(GLASS, 0.07), edge=GLASS,
            size=NOTE_SIZE - 1.0)

    figure.suptitle(
        "This solution is the least trained and the most borrowed of them all.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.05,
       "The borrowed count is arithmetic on the model's published widths and depths, so it is the right size "
        " rather than a measurement of a file, and the keeper's count is\narithmetic on the shape of the set "
        "of trees. What the picture is for is the gap between them, and the gap is not close: for every "
        f"number fitted in this cell, about {BORROWED_PER_FITTED:,.0f} are brought in\nalready fitted from "
       "somewhere else. That is what buys the small training set, and it is also what buys the risk, because "
        " a borrowed weight cannot be corrected here.\nSolution 2 makes the opposite trade: nothing "
        "borrowed, "
        "nothing unexamined, and every one of its numbers paid for with rendered scenes.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    save(figure, "05-borrowed-against-trained.png")


# --------------------------------------------------------------------------- #
# 7. where it stops
# --------------------------------------------------------------------------- #

def figure_where_it_stops() -> None:
    """A glass covered completely: no pixels, so no prompt point, so no proposal."""
    hidden_scene = (
        ("the tall glass", (185.0, -40.0), TALL_A),
        ("the short glass", (335.0, -70.0), SHORT_A),
    )
    names, shapes = build(hidden_scene)
    tall, short = names
    covered = splay_covers(shapes[tall], shapes[short])
    assert covered, "this figure is only honest if the short glass really is covered"

    apart = float(np.hypot(*(np.asarray(hidden_scene[1][1]) - np.asarray(hidden_scene[0][1]))))
    patch_mm = splay_width(shapes[tall])
    extent = extent_of(shapes, pad=70.0)
    grid = prompt_grid(extent)
    hits = [topmost(point, hidden_scene) for point in grid]
    on_tall = hits.count(tall)
    on_short = hits.count(short)
    assert on_short == 0, "a covered glass must collect no prompt points at all"

    figure, (left, right) = new(14.8, 7.0, columns=2)

    plan_axis(left, extent)
    panel_title(left, "The top view: one silhouette, two glasses", colour=WARN)
    splay_patch(left, shapes[tall], colour=GLASS, alpha=0.20, zorder=3)
    for index, (centre, radius) in enumerate(shapes[short]):
        if index % 9 == 0 or index == len(shapes[short]) - 1:
            left.add_patch(
                Circle(tuple(centre), radius, facecolor="none", edgecolor=WARN, lw=1.0,
                       ls=(0, (3, 3)), alpha=0.85, zorder=5)
            )
    for point, hit in zip(grid, hits, strict=False):
        if hit is None:
            left.scatter([point[0]], [point[1]], s=8, facecolor=PAPER, edgecolor=MUTED,
                         linewidths=0.6, zorder=6)
        else:
            left.scatter([point[0]], [point[1]], s=15, color=GOOD, zorder=7, linewidths=0)
    short_tip = shapes[short][-1][0]
    left.annotate(
        f"the short glass is in here,\ndrawn dashed. Not one pixel\nof it reaches the picture, so\n"
        f"not one of the {len(grid)} prompt points\ncan land on it.",
        xy=tuple(short_tip), xytext=(extent[0] + (extent[1] - extent[0]) * 0.30, extent[3] - 24),
        fontsize=NOTE_SIZE, color=WARN, ha="left", va="top", zorder=9,
        bbox=dict(HALO, pad=4.0),
        arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0},
    )
    note(left, extent[0] + 14, extent[2] + 14,
         f"{on_tall} points landed on the tall glass and every one of them\nreturned the same mask. "
         f"{on_short} landed on the short glass.",
         colour=INK, va="bottom", halo=True)

    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    panel_title(right, "Why nothing in this solution can catch it")

    chain = (
        ("the geometry", f"the tall glass stands {apart:.0f} mm from the short one,\n"
                         "and splay has thrown its outline right over it", MUTED),
        ("the picture", "every pixel of the short glass is a pixel\nof the tall one instead", MUTED),
        ("the prompt", "a prompt point is a pixel, so no prompt\nexists that reaches the short glass", WARN),
        ("the proposal",
         "SAM 2 returns a mask for whatever the point\nlanded on, so no mask contains it", WARN),
        ("the keeper", "the keeper only ever sorts proposals,\nso it is never shown this glass at all", WARN),
    )
    top, step = 0.855, 0.153
    for index, (stage, text, colour) in enumerate(chain):
        y = top - index * step
        note(right, 0.075, y, stage, colour=colour, size=NOTE_SIZE, ha="right", va="center",
             weight="bold")
        box(right, 0.535, y, 0.86, 0.113, text, tint(colour, 0.09), edge=colour, size=NOTE_SIZE)
        if index < len(chain) - 1:
            arrow(right, (0.535, y - 0.058), (0.535, y - step + 0.058), colour=colour, lw=1.1)

    note(
        right, 0.075, 0.115,
        "So the glass is not reported wrongly. It is not reported at all, and there is no\n"
        "low score to notice, because a check in this solution is a check on a proposal.",
        colour=WARN, va="top", size=LABEL_SIZE - 0.4,
    )
    note(
        right, 0.075, 0.035,
        "Nothing about the borrowed weights or the keeper changes this. Only another\nlook, from somewhere "
        "the short glass is not behind the tall one, changes it.",
        colour=INK, va="top",
    )

    figure.suptitle(
        "Where this solution stops: a prompt is a pixel, and a glass with no pixels cannot be prompted.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        f"Both glasses here are of the one kind on the table, one near the tall end of its range of sizes "
        f"and "
        f"one near the short end, standing {apart:.0f} mm apart, "
        f"which is further\napart than the guaranteed gap of {MIN_APART:.0f} mm. The arrangement "
        "is an ordinary one, and the project's own coverage test confirms that every point of the short "
        "glass's\noutline falls inside the tall one's. This is the same "
        "limit every solution in this problem meets, and it is geometry, not a weakness of any model.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    save(figure, "05-where-it-stops.png")
    print(f"  hidden pair: {apart:.0f} mm apart, tall patch {patch_mm:.0f} mm across, "
          f"{on_tall} prompt points on the tall glass, {on_short} on the short one")


def main() -> None:
    print(
        f"scene: {len(SCENE)} glasses from the shared cast, {len(GRID)} prompt points, "
        f"{len(GRID) - ON_TABLE} on glass, {ON_TABLE} on table"
    )
    # Printed rather than drawn: the picture says the spacing is comfortably
    # finer than the smallest patch, and this is the check behind that claim.
    print(
        f"grid: {GRID_MM:.0f} mm spacing against the smallest patch in the scene, "
        f"{SMALLEST_PATCH:.0f} mm across"
    )
    print(
        f"borrowed: {BORROWED:,} weights ({ENCODER:,} encoder + {HEAD:,} head)"
    )
    print(
        f"fitted here: {TREES} trees, {FITTED_THRESHOLDS:,} thresholds + {FITTED_LEAVES:,} leaves "
        f"= {FITTED_NUMBERS:,} numbers; solution 2 fits {SOLUTION_TWO:,} weights"
    )
    figure_what_promptable_means()
    figure_the_prompt_grid()
    figure_everything_is_proposed()
    figure_the_keeper()
    figure_the_keeper_thresholds()
    figure_the_keeper_trees()
    figure_the_domain_gap()
    figure_borrowed_against_trained()
    figure_where_it_stops()


if __name__ == "__main__":
    main()
