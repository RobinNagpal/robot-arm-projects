"""Diagrams for solution 10 — amodal masks for the hidden part.

Seven pictures, each carrying one step of the argument: what modal and amodal
masks are, why a mask cut short gives a footprint that is wrong in a way every
check accepts, where the amodal training label comes from, how little of the
model changes, why the extra pixels are a prediction rather than a measurement,
how to score such a prediction, and the one case the whole idea cannot reach.

Every silhouette here is a real overhead projection of one of the shared cast of
glasses in ``diagram_style``, built from ``splay_circles``, and every pixel is
assigned to a glass by comparing heights along the ray, so a glass covers
another only when the geometry says it does. The numbers in the labels are
measured off those rasters rather than typed in: the visible fractions, the
areas, the fitted circles, the overlaps and the errors are all computed when
this script runs.

Run from the project root:

    pixi run python images/generators/02-segment-glasses/make_10_images.py
"""

from __future__ import annotations

import cv2
import numpy as np
from diagram_style import (
    CAST,
    GLASS,
    GOOD,
    INK,
    KIND_SHORTEST,
    KIND_TALLEST,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
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
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

RNG = np.random.default_rng(20250930)

NADIR = np.array([0.0, 0.0])     # the point on the table directly below the camera
MIN_APART = 150.0                # mm centre to centre, the closest two glasses ever stand
SLICES = 80                      # how finely a glass is sliced when it is projected
BASE_FRACTION = 0.45             # base radius over rim radius, the default splay_circles uses

# The width the cell treats as agreement between two measurements of the same
# glass, from 02-segment-glasses/01-rules-on-the-table/measure.py. It is a rule about the sensors
# rather than a fact about any glass, so it belongs here: the fit error and the
# displacement of a fitted centre are compared against it.
TOLERANCE = 6.0

# How a stand-in prediction differs from the truth, for the figure about scoring.
# The model in that figure completes most of the hidden part but stops short of
# its far edge, and is a little tight on the visible part as well.
VISIBLE_SLACK = 1.5     # mm the prediction pulls back from the edge it can see
HIDDEN_SHORTFALL = 7.0  # mm the prediction stops short of the hidden part's far edge

# --------------------------------------------------------------------------- #
# the scene
# --------------------------------------------------------------------------- #
#
# Four glasses of one kind, which is the shared cast: two near the tall end of
# this kind's range and two near the short end. The mixture is the whole point,
# because splay throws a tall glass's outline much further out than a short
# one's and that difference is what lets one outline sweep across another.
#
# Two of the four are partly covered, at separations the cell guarantees:
#
#   S1 loses a little of itself to T1. That is the quiet case: the circle fitted
#      to what is left is wrong and every check still passes.
#   S2 loses a third of itself to T2. That is the case the mask pictures use,
#      because the hidden part is large enough to see.
#
# The positions are checked rather than trusted: check_legal asserts that no two
# centres are closer than the guaranteed gap.
OCCLUDER_NEAR = ("T1", np.array([185.0, -40.0]), TALL_A)
QUIET = ("S1", np.array([293.8, -173.1]), SHORT_B)
OCCLUDER_FAR = ("T2", np.array([-120.0, 120.0]), TALL_B)
BITTEN = ("S2", np.array([-252.0, 243.0]), SHORT_A)
SCENE = (OCCLUDER_NEAR, QUIET, OCCLUDER_FAR, BITTEN)

# The limiting case, for the last figure: a tall glass whose outline swallows a
# short one whole. splay_covers decides it, not the eye.
HIDING_TALL = ("T1", np.array([185.0, -40.0]), TALL_A)
HIDING_SHORT = ("S3", np.array([335.0, -70.0]), SHORT_A)


def check_legal(scene) -> float:
    """Assert the arrangement is one the cell allows, and return the tightest gap."""
    gaps = []
    for i, (_, first, _) in enumerate(scene):
        for _, second, _ in scene[i + 1:]:
            gaps.append(float(np.hypot(*(second - first))))
    tightest = min(gaps)
    assert tightest >= MIN_APART, f"centres {tightest:.0f} mm apart, closer than the guaranteed gap"
    return tightest


assert sorted(size for _, _, size in SCENE) == sorted(CAST), "the scene must be the shared cast"


# --------------------------------------------------------------------------- #
# geometry: what the overhead camera makes of a standing glass
# --------------------------------------------------------------------------- #

def stack_of(centre, size, slices: int = SLICES):
    """A glass as the stack of circles it draws from above, with each circle's height.

    ``splay_circles`` does the projection: a slice at height z is scaled about
    the point below the camera by H / (H - z). Keeping the heights alongside is
    what lets one glass be tested against another, because the surface nearer
    the lens along a ray is the higher one.
    """
    circles = splay_circles(NADIR, centre, size[0], size[1], slices=slices)
    return circles, np.linspace(0.0, size[0], slices)


def height_field(stack, grid_x, grid_y):
    """How high this glass's surface is at each point of the picture, or -1 for none."""
    circles, heights = stack
    field = np.full(grid_x.shape, -1.0)
    for (centre, radius), height in zip(circles, heights, strict=True):
        inside = (grid_x - centre[0]) ** 2 + (grid_y - centre[1]) ** 2 <= radius * radius
        field[inside] = np.maximum(field[inside], height)
    return field


def scene_masks(step: float, window=None, scene=SCENE):
    """The modal and amodal mask of every glass in the scene, as rasters.

    The amodal mask of a glass is its whole silhouette. Its modal mask is the
    part of that silhouette where its own surface is the highest thing along the
    ray, which is exactly the part the camera sees of it.
    """
    stacks = {name: stack_of(pos, size) for name, pos, size in scene}
    if window is None:
        lows, highs = [], []
        for circles, _ in stacks.values():
            lows.append([min(c[i] - r for c, r in circles) for i in (0, 1)])
            highs.append([max(c[i] + r for c, r in circles) for i in (0, 1)])
        low = np.min(np.array(lows), axis=0) - 24.0
        high = np.max(np.array(highs), axis=0) + 24.0
        window = (low[0], high[0], low[1], high[1])
    grid_x, grid_y = np.meshgrid(np.arange(window[0], window[1], step),
                                 np.arange(window[2], window[3], step))
    fields = [height_field(stacks[name], grid_x, grid_y) for name, _, _ in scene]
    stacked = np.stack(fields)
    owner = np.argmax(stacked, axis=0)
    lit = stacked.max(axis=0) > -1.0
    masks = {}
    for index, (name, _, _) in enumerate(scene):
        amodal = fields[index] > -1.0
        modal = amodal & lit & (owner == index)
        masks[name] = (amodal, modal)
    extent = (grid_x.min(), grid_x.max(), grid_y.min(), grid_y.max())
    return grid_x, grid_y, extent, masks, step


def mask_window(mask, grid_x, grid_y, pad: float = 26.0):
    """A drawing window around everything the mask covers."""
    return (grid_x[mask].min() - pad, grid_x[mask].max() + pad,
            grid_y[mask].min() - pad, grid_y[mask].max() + pad)


def area_of(mask, step: float) -> float:
    """How much table a raster covers, in square millimetres."""
    return float(mask.sum()) * step * step


# --------------------------------------------------------------------------- #
# geometry: the footprint, which is what the circle is fitted to
# --------------------------------------------------------------------------- #

def wall_height(radius, size):
    """How high up the glass its own wall reaches that far out from its axis.

    A tapered glass is a straight wall from a base of BASE_FRACTION of the rim
    radius up to the rim, so a point of the footprint that far out from the axis
    is seen at that height. Inside the base radius the reading comes from the
    bottom, which is at the table.
    """
    height, rim = size
    rim_radius = rim / 2.0
    base_radius = rim_radius * BASE_FRACTION
    return np.clip((radius - base_radius) / (rim_radius - base_radius), 0.0, 1.0) * height


def footprint_masks(target, occluders, step: float = 0.35):
    """The target's whole footprint, and the part of it the camera still reaches.

    Every pixel of a mask carries a depth reading, so it becomes a point in the
    room, and dropping the height turns it into a point on the table. This runs
    that backwards: for each point of the footprint, work out the height at
    which the glass's own surface stands above it, project that point into the
    picture, and ask whether something else is nearer the lens there.
    """
    _, centre, size = target
    rim_radius = size[1] / 2.0
    xs = np.arange(centre[0] - rim_radius - step, centre[0] + rim_radius + step, step)
    ys = np.arange(centre[1] - rim_radius - step, centre[1] + rim_radius + step, step)
    grid_x, grid_y = np.meshgrid(xs, ys)
    out = np.hypot(grid_x - centre[0], grid_y - centre[1])
    whole = out <= rim_radius
    height = wall_height(out, size)
    lift = SURVEY_H / (SURVEY_H - height)
    seen_x = NADIR[0] + (grid_x - NADIR[0]) * lift
    seen_y = NADIR[1] + (grid_y - NADIR[1]) * lift
    visible = whole.copy()
    for _, other_centre, other_size in occluders:
        above = height_field(stack_of(other_centre, other_size), seen_x, seen_y)
        visible &= above < height
    return grid_x, grid_y, whole, visible, step


def moment_fit(grid_x, grid_y, patch, step: float):
    """The circle that explains a patch of flattened points, and how well it does.

    The centre is where the points balance and the width is the width of the
    disc with the same area, which is what a fit to a disc of points comes to.
    The error is how far the points reach outside that disc, which is the number
    whose job is to say "this group is not one glass".
    """
    points = np.column_stack([grid_x[patch], grid_y[patch]])
    centre = points.mean(axis=0)
    radius = float(np.sqrt(area_of(patch, step) / np.pi))
    beyond = np.clip(np.hypot(*(points - centre).T) - radius, 0.0, None)
    return centre, radius, float(np.sqrt(np.mean(beyond ** 2)))


def rim_visibility(target, occluders, samples: int = 720):
    """Which parts of the rim ring the camera still sees, angle by angle.

    The rim is the widest ring of the glass, so it is the part a footprint width
    comes from. A rim point is imaged at its own splayed position, and it
    survives when nothing stands higher along that ray.
    """
    _, centre, size = target
    height, rim = size
    angles = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    on_table = centre + rim / 2.0 * np.column_stack([np.cos(angles), np.sin(angles)])
    lift = SURVEY_H / (SURVEY_H - height)
    seen = NADIR + (on_table - NADIR) * lift
    visible = np.ones(samples, dtype=bool)
    for _, other_centre, other_size in occluders:
        above = height_field(stack_of(other_centre, other_size), seen[:, 0], seen[:, 1])
        visible &= above < height
    return angles, visible


def runs_of(flags):
    """The contiguous stretches of a closed loop of flags, as (start, stop) index pairs."""
    edges = np.flatnonzero(flags.astype(int) - np.roll(flags, 1).astype(int) == 1)
    if not len(edges):
        return [(0, len(flags))] if flags.all() else []
    out = []
    for start in edges:
        stop = start
        while flags[stop % len(flags)]:
            stop += 1
        out.append((int(start), int(stop)))
    return out


def erode_mm(mask, millimetres: float, step: float):
    """Pull a raster back from its own edge by a distance in millimetres."""
    distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    return mask & (distance * step > millimetres)


# --------------------------------------------------------------------------- #
# small shared drawing helpers
# --------------------------------------------------------------------------- #

def paint(axis, mask, colour, extent, alpha: float = 1.0, zorder: int = 2) -> None:
    """Draw a boolean raster as a flat wash of one colour."""
    rgba = np.zeros((*mask.shape, 4), dtype=float)
    rgba[mask] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest", extent=extent, origin="lower", zorder=zorder)


def outline(axis, mask, grid_x, grid_y, colour, lw: float = 1.2, ls="dashed", zorder: int = 6) -> None:
    """The boundary of a raster, drawn as a line rather than a wash."""
    axis.contour(grid_x, grid_y, mask.astype(float), [0.5], colors=[colour], linewidths=lw,
                 linestyles=ls, zorder=zorder)


def dots_in(axis, mask, grid_x, grid_y, colour, count: int = 240, size: float = 2.0,
            zorder: int = 5) -> None:
    """A scatter of points over a raster, as a flattened cloud looks."""
    xs, ys = grid_x[mask], grid_y[mask]
    if not len(xs):
        return
    pick = RNG.choice(len(xs), size=min(count, len(xs)), replace=False)
    axis.scatter(xs[pick], ys[pick], s=size, color=colour, linewidths=0, zorder=zorder)


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, ha="left", va="top", weight="normal") -> None:
    axis.text(x, y, text, fontsize=size, color=colour, ha=ha, va=va, zorder=8, weight=weight)


def panel_title(axis, text, colour=INK) -> None:
    axis.set_title(text, fontsize=LABEL_SIZE + 0.6, color=colour, pad=8)


def span(axis, start, end, text, colour=INK, above=True, pad=6.0, size=NOTE_SIZE) -> None:
    """A double-headed arrow with a label, for stating a distance."""
    axis.annotate("", xy=end, xytext=start,
                  arrowprops={"arrowstyle": "<->", "color": colour, "lw": 1.1,
                              "shrinkA": 0, "shrinkB": 0}, zorder=7)
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    axis.text(mid[0], mid[1] + (pad if above else -pad), text, ha="center",
              va="bottom" if above else "top", fontsize=size, color=colour, zorder=7)


def box(axis, x, y, w, h, text, edge=INK, face="#ffffff", size=NOTE_SIZE, colour=INK,
        weight="normal") -> None:
    """A rounded box with centred text, given its centre."""
    axis.add_patch(
        FancyBboxPatch((x - w / 2.0, y - h / 2.0), w, h,
                       boxstyle="round,pad=1.6,rounding_size=2.4", linewidth=1.2,
                       edgecolor=edge, facecolor=face, zorder=3)
    )
    axis.text(x, y, text, ha="center", va="center", fontsize=size, color=colour, zorder=4,
              weight=weight)


def arrow(axis, start, end, colour=INK, width=1.2) -> None:
    axis.add_patch(
        FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10, linewidth=width,
                        color=colour, shrinkA=2, shrinkB=2, zorder=5)
    )


def verdict(axis, x, y, text, passes: bool, size=NOTE_SIZE) -> None:
    """One line of a check, coloured by whether it lets the answer through."""
    axis.text(x, y, text, fontsize=size, color=GOOD if passes else WARN, ha="left", va="top",
              zorder=8)


def plan_panel(axis, window) -> None:
    bare(axis)
    axis.set_aspect("equal")
    axis.set_xlim(window[0], window[1])
    axis.set_ylim(window[2], window[3])


def camera_mark(axis, ha="left", va="top", dx=12.0, dy=-12.0) -> None:
    axis.scatter([0.0], [0.0], s=40, color=INK, marker="x", zorder=9)
    note(axis, dx, dy, "camera,\nstraight above here", colour=INK, ha=ha, va=va)


# --------------------------------------------------------------------------- #
# 1. modal against amodal
# --------------------------------------------------------------------------- #

def figure_modal_against_amodal() -> None:
    """One partly covered glass, shown as the pixels it gives and as its whole shape."""
    tightest = check_legal(SCENE)
    grid_x, grid_y, extent, masks, step = scene_masks(1.2)
    name, _, _ = BITTEN
    amodal, modal = masks[name]
    hidden = amodal & ~modal
    whole_area, seen_area, hidden_area = (area_of(m, step) for m in (amodal, modal, hidden))
    window = mask_window(amodal, grid_x, grid_y, pad=30.0)

    figure, (scene, left, right) = new(15.0, 5.2, columns=3)

    # ---- the whole picture ------------------------------------------------
    plan_panel(scene, (grid_x.min() - 10, grid_x.max() + 10, grid_y.min() - 110, grid_y.max() + 70))
    panel_title(scene, "The picture from the top: four glasses of one kind")
    for other, _, _ in SCENE:
        paint(scene, masks[other][1], GLASS, extent, alpha=0.30)
    paint(scene, hidden, WARN, extent, alpha=0.40, zorder=3)
    # each label above or below its own silhouette, so that no two of them meet
    above = {"T1": True, "S1": False, "T2": False, "S2": True}
    # A glass is named by which end of its kind's range it is drawn from rather
    # than by a measurement, because the mixture is what the picture is about
    # and no glass's size is written down anywhere in this project.
    middle = (KIND_SHORTEST + KIND_TALLEST) / 2.0
    for other, _, other_size in SCENE:
        tip = mask_window(masks[other][0], grid_x, grid_y, pad=0.0)
        over = above[other]
        end = "tall" if other_size[0] >= middle else "short"
        note(scene, (tip[0] + tip[1]) / 2.0, tip[3] + 46 if over else tip[2] - 16,
             f"{other}: near the {end} end of the kind",
             colour=INK, ha="center", va="bottom" if over else "top")
    scene.add_patch(Rectangle((window[0], window[2]), window[1] - window[0], window[3] - window[2],
                              facecolor="none", edgecolor=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=7))
    camera_mark(scene)
    note(scene, grid_x.min(), grid_y.min() - 54,
         f"Nearest pair of centres: {tightest:.0f} mm, so the arrangement is one the cell allows.",
         colour=MUTED, va="top")

    # ---- modal ------------------------------------------------------------
    plan_panel(left, window)
    panel_title(left, f"Modal mask of {name}: only what the camera sees", colour=GLASS)
    paint(left, masks[OCCLUDER_FAR[0]][1], MUTED, extent, alpha=0.30)
    paint(left, modal, GLASS, extent, alpha=0.62, zorder=3)
    outline(left, amodal, grid_x, grid_y, MUTED, ls="dashed")
    note(left, window[0] + 8, window[3] - 8,
         f"{seen_area:.0f} mm² of table.\n{OCCLUDER_FAR[0]} stands in front, in grey.",
         colour=INK)
    note(left, window[0] + 8, window[2] + 8,
         f"The dashed line is where the glass really ends.\nThe mask stops "
         f"{100.0 * hidden_area / whole_area:.0f}% short of it.", colour=MUTED, va="bottom")

    # ---- amodal -----------------------------------------------------------
    plan_panel(right, window)
    panel_title(right, f"Amodal mask of {name}: the whole silhouette", colour=GOOD)
    paint(right, masks[OCCLUDER_FAR[0]][1], MUTED, extent, alpha=0.18)
    paint(right, modal, GLASS, extent, alpha=0.62, zorder=3)
    paint(right, hidden, WARN, extent, alpha=0.45, zorder=4)
    outline(right, amodal, grid_x, grid_y, GOOD, ls="solid", lw=1.4)
    note(right, window[0] + 8, window[3] - 8,
         f"{whole_area:.0f} mm² of table: the {seen_area:.0f} mm² above\n"
         f"plus the {hidden_area:.0f} mm² in the covered part.", colour=INK)
    note(right, window[0] + 8, window[2] + 8,
         "Blue: this glass's own surface was seen here.\nOrange: the hidden part, which is the "
         "difference\nbetween the two masks.", colour=INK, va="bottom")

    figure.suptitle(
        "A modal mask reports the slices of glass the camera caught. An amodal mask reports the "
        "glass.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        f"All three panels hold the same scene. {name} is drawn from the short end of this kind's "
        f"range and {OCCLUDER_FAR[0]} from its tall end, more than twice the height, so splay "
        f"throws {OCCLUDER_FAR[0]}'s outline far enough out to cover part of {name}, which stands "
        f"{np.hypot(*(BITTEN[1] - OCCLUDER_FAR[1])):.0f} mm away.\nEvery pixel here was assigned "
        "by "
        "comparing heights along the ray, so a glass hides another only where its own surface is "
        f"nearer the lens. Of {name}'s silhouette, {100.0 * seen_area / whole_area:.0f}% survives "
        f"in the picture and {100.0 * hidden_area / whole_area:.0f}% does not.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    print(f"  modal/amodal: {name} amodal {whole_area:.0f} mm2, modal {seen_area:.0f} mm2, "
          f"hidden {hidden_area:.0f} mm2, tightest gap {tightest:.0f} mm")
    save(figure, "10-modal-against-amodal.png")


# --------------------------------------------------------------------------- #
# 2. the truncated footprint
# --------------------------------------------------------------------------- #

def figure_labels_for_free() -> None:
    """Render the scene, render each glass alone, and subtract."""
    check_legal(SCENE)
    grid_x, grid_y, extent, masks, step = scene_masks(1.2)
    name, _, size = BITTEN
    amodal, modal = masks[name]
    hidden = amodal & ~modal
    window = mask_window(amodal, grid_x, grid_y, pad=30.0)

    figure, (whole_scene, alone, seen, difference) = new(17.0, 4.8, columns=4)

    plan_panel(whole_scene, (grid_x.min() - 8, grid_x.max() + 8,
                             grid_y.min() - 160, grid_y.max() + 46))
    panel_title(whole_scene, "1. Render the scene once")
    for index, (other, _, _size) in enumerate(SCENE):
        paint(whole_scene, masks[other][1], GLASS, extent, alpha=0.22 + 0.12 * (index % 2))
        note(whole_scene, grid_x[masks[other][1]].mean(), grid_y[masks[other][1]].mean(), other,
             colour=INK, ha="center", va="center", size=LABEL_SIZE, weight="bold")
    whole_scene.add_patch(Rectangle((window[0], window[2]), window[1] - window[0],
                                    window[3] - window[2], facecolor="none", edgecolor=MUTED,
                                    lw=0.9, ls=(0, (4, 3)), zorder=7))
    camera_mark(whole_scene)
    note(whole_scene, grid_x.min(), grid_y.min() - 24,
         "Every pixel comes back marked with the glass\nit belongs to. That is the identity map, "
         "and it is\nwhat the picture the model is trained on holds.", colour=INK, va="top")

    plan_panel(alone, window)
    panel_title(alone, f"2. Render {name} alone, same camera", colour=GOOD)
    paint(alone, amodal, GOOD, extent, alpha=0.45)
    outline(alone, amodal, grid_x, grid_y, GOOD, ls="solid", lw=1.4)
    note(alone, window[0] + 8, window[2] + 8,
         f"Nothing in front of it, so every pixel it would\noccupy is marked: "
         f"{area_of(amodal, step):.0f} mm² of table.\nThis is the amodal mask, exactly.",
         colour=INK, va="bottom")

    plan_panel(seen, window)
    panel_title(seen, f"3. Take {name}'s pixels from panel 1", colour=GLASS)
    paint(seen, masks[OCCLUDER_FAR[0]][1], MUTED, extent, alpha=0.24)
    paint(seen, modal, GLASS, extent, alpha=0.60, zorder=3)
    outline(seen, amodal, grid_x, grid_y, MUTED, ls="dashed")
    note(seen, window[0] + 8, window[2] + 8,
         f"The pixels the scene render gives to {name}:\n{area_of(modal, step):.0f} mm². This is "
         "the modal mask, and\nit is the target the first rung trains against.", colour=INK,
         va="bottom")

    plan_panel(difference, window)
    panel_title(difference, "4. Panel 2 minus panel 3 is the hidden part", colour=WARN)
    paint(difference, hidden, WARN, extent, alpha=0.55)
    outline(difference, amodal, grid_x, grid_y, MUTED, ls="dashed")
    note(difference, window[0] + 8, window[2] + 8,
         f"{area_of(hidden, step):.0f} mm², which is "
         f"{100.0 * area_of(hidden, step) / area_of(amodal, step):.0f}% of the whole\nsilhouette. "
         "This is the part the model has to\ninvent, and its edge is where the simulator's\ngeometry"
         " puts it, not where anyone drew it.", colour=INK, va="bottom")

    figure.suptitle(
        "The amodal label is a second render, not a second opinion: no line is ever drawn by hand.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.05,
        "On a real photograph the boundary of a hidden part has to be guessed by an annotator, two "
        "careful people guess differently, and there is no way to check who was right. Here the "
        "simulator holds the scene, so it can be\nasked to render it again with all the glasses but "
        f"one taken away, from the same camera pose. Every glass in the scene is labelled this way "
        f"in one pass: {name} keeps {100.0 * area_of(modal, step) / area_of(amodal, step):.0f}% of "
        f"itself, and dividing the size of one mask by the other\ngives the visible fraction of "
        "every glass in every scene for free, which is what makes the measurements later possible.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    print(f"  labels: {name} amodal {area_of(amodal, step):.0f} mm2, modal "
          f"{area_of(modal, step):.0f} mm2, hidden {area_of(hidden, step):.0f} mm2")
    save(figure, "10-labels-for-free.png")


# --------------------------------------------------------------------------- #
# 4. only the target changes
# --------------------------------------------------------------------------- #

def figure_measuring_whether_it_works() -> None:
    """Two ways of scoring one answer: the usual one, and the one that sees the point.

    Both numbers are counted over pixels, and deliberately so. No footprint is
    fitted to the prediction anywhere here, because the asserted pixels carry
    the near glass's depth readings and are excluded before any footprint is
    fitted, so a completion is scored on the masks it produces and not on a
    place it never supplied.
    """
    check_legal(SCENE)
    name, _, _ = BITTEN
    grid_x, grid_y, extent, masks, step = scene_masks(1.0, window=(-420.0, -120.0, 120.0, 400.0))
    amodal, modal = masks[name]
    hidden = amodal & ~modal
    window = mask_window(amodal, grid_x, grid_y, pad=24.0)

    # A stand-in for a model that completes most of the hidden part but stops
    # short of its far edge, and is a little tight on what it can see.
    predicted = erode_mm(modal, VISIBLE_SLACK, step) | (erode_mm(amodal, HIDDEN_SHORTFALL, step)
                                                       & hidden)
    # Overlap counted over one region at a time: how much of the pixels in that
    # region the prediction and the truth agree on, over how much either claims.
    visible_iou = (predicted & modal).sum() / ((predicted & modal) | modal).sum()
    hidden_iou = (predicted & hidden).sum() / ((predicted & hidden) | hidden).sum()

    figure, (picture, scores) = new(11.0, 5.4, columns=2)

    plan_panel(picture, window)
    panel_title(picture, "One prediction against the truth")
    paint(picture, predicted, GLASS, extent, alpha=0.55)
    paint(picture, amodal & ~predicted, WARN, extent, alpha=0.50, zorder=3)
    outline(picture, amodal, grid_x, grid_y, GOOD, ls="solid", lw=1.3)
    outline(picture, modal, grid_x, grid_y, INK, ls="dashed", lw=0.9)
    note(picture, window[0] + 8, window[3] - 8,
         "Green line: the whole silhouette, which is the truth.\n"
         "Black dashes: where the visible part ends.\n"
         "Blue: what the model claimed. Orange: what it missed.", colour=INK)

    bare(scores)
    scores.set_xlim(0, 1.32)
    scores.set_ylim(-1.5, 2.3)
    panel_title(scores, "The same answer, scored two ways")
    for index, (label, value, colour, verdict_text) in enumerate((
            ("overlap over the visible pixels\n(the part never in doubt)", visible_iou, MUTED,
             "looks like a good mask"),
            ("overlap over the hidden part\n(the part that was the point)", hidden_iou, WARN,
             "most of the completion is missing"))):
        y = 1.6 - index * 1.1
        scores.add_patch(Rectangle((0, y - 0.20), 1.0, 0.40, facecolor=MUTED, alpha=0.12,
                                   edgecolor=MUTED, lw=0.8))
        scores.add_patch(Rectangle((0, y - 0.20), value, 0.40, facecolor=colour, alpha=0.55,
                                   edgecolor=colour, lw=1.2))
        scores.text(value + 0.02, y, f"{value:.2f}", ha="left", va="center", fontsize=LABEL_SIZE,
                    color=colour, weight="bold")
        note(scores, 0, y + 0.26, label, colour=INK, va="bottom")
        note(scores, 0, y - 0.28, verdict_text, colour=colour, va="top")
    note(scores, 0, -0.62,
         "Nearly every pixel of a mask was never in question: the\n"
         "glass's own surface is right there in the picture. So an\n"
         "overlap counted over those pixels is dominated by the\n"
         "easy part of the answer and barely moves when the\n"
         "completion is wrong. Counted over the hidden part alone,\n"
         "the same answer scores what it deserves.", colour=INK, va="top")

    figure.suptitle(
        "The ordinary measure of a segmenter is the wrong measure here: it scores the part that was "
        "never in doubt.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        f"The prediction drawn here is a stand-in with a deliberate fault: it pulls back "
        f"{VISIBLE_SLACK:.1f} mm from the edge it can see and stops {HIDDEN_SHORTFALL:.0f} mm short "
        "of the far edge of the hidden part.\nScored over the pixels the camera saw it looks "
        f"{visible_iou:.2f} good; scored over the hidden part alone it is {hidden_iou:.2f}, and "
        "that second number is the one that says what the completion is worth.\nBeside it belong "
        "the counts of glasses found, missed and merged, because a completion that credits a slice "
        "to the glass it came off adds a glass to the answer.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    print(f"  scoring: visible overlap {visible_iou:.3f}, hidden overlap {hidden_iou:.3f}")
    save(figure, "10-measuring-whether-it-works.png")


# --------------------------------------------------------------------------- #
# 7. where it stops
# --------------------------------------------------------------------------- #

def figure_where_it_stops() -> None:
    """A glass covered completely leaves nothing to extend from."""
    partly = (OCCLUDER_FAR, BITTEN)
    wholly = (HIDING_TALL, HIDING_SHORT)
    check_legal(partly)
    check_legal(wholly)

    tall_stack = stack_of(HIDING_TALL[1], HIDING_TALL[2])
    short_stack = stack_of(HIDING_SHORT[1], HIDING_SHORT[2])
    covered = splay_covers(tall_stack[0], short_stack[0])
    assert covered, "this pair is supposed to be the complete-covering case"
    patch_mm = splay_width(tall_stack[0])

    near_x, near_y, near_extent, near_masks, near_step = scene_masks(
        1.0, window=(-420.0, -120.0, 120.0, 400.0), scene=partly)
    far_x, far_y, far_extent, far_masks, far_step = scene_masks(
        1.0, window=(120.0, 520.0, -260.0, 60.0), scene=wholly)

    amodal, modal = near_masks[BITTEN[0]]
    kept = area_of(modal, near_step) / area_of(amodal, near_step)
    gone_amodal, gone_modal = far_masks[HIDING_SHORT[0]]
    gone_area = area_of(gone_modal, far_step)

    figure, (works, stops, ladder) = new(16.2, 5.6, columns=3)

    window = mask_window(amodal, near_x, near_y, pad=26.0)
    plan_panel(works, window)
    panel_title(works, "Partly covered: there is something to extend from", colour=GOOD)
    paint(works, near_masks[OCCLUDER_FAR[0]][1], MUTED, near_extent, alpha=0.30)
    paint(works, modal, GLASS, near_extent, alpha=0.60, zorder=3)
    paint(works, amodal & ~modal, WARN, near_extent, alpha=0.45, zorder=4)
    outline(works, amodal, near_x, near_y, GOOD, ls="solid", lw=1.3)
    note(works, window[0] + 8, window[2] + 8,
         f"{100.0 * kept:.0f}% of {BITTEN[0]} reaches the picture. Those\npixels fill a slot of "
         "their own and leave an\nedge to carry on, so the covered part can\nbe completed.",
         colour=INK, va="bottom")

    far_window = mask_window(far_masks[HIDING_TALL[0]][0], far_x, far_y, pad=26.0)
    plan_panel(stops, far_window)
    panel_title(stops, "Covered completely: there is nothing to extend", colour=WARN)
    paint(stops, far_masks[HIDING_TALL[0]][1], GLASS, far_extent, alpha=0.32)
    outline(stops, gone_amodal, far_x, far_y, WARN, ls="dashed", lw=1.4)
    stops.scatter([HIDING_SHORT[1][0]], [HIDING_SHORT[1][1]], s=30, color=WARN, marker="+",
                  zorder=8)
    stops.annotate(f"{HIDING_SHORT[0]} is under here. Its outline is\ndashed, and "
                   f"{gone_area:.0f} mm² of it reaches\nthe picture.",
                   xy=tuple(HIDING_SHORT[1]), xytext=(far_window[0] + 12, far_window[2] + 16),
                   fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom",
                   arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.0}, zorder=8)
    note(stops, far_window[0] + 12, far_window[3] - 8,
         f"{HIDING_TALL[0]} is more than twice the height of\n{HIDING_SHORT[0]} and stands nearer "
         "the camera, so splay\nthrows its outline far enough across the\ntable to swallow "
         f"{HIDING_SHORT[0]}, which stands "
         f"{np.hypot(*(HIDING_SHORT[1] - HIDING_TALL[1])):.0f} mm away.", colour=INK)

    bare(ladder)
    ladder.set_xlim(0, 100)
    ladder.set_ylim(-34, 104)
    panel_title(ladder, "What each case gives the model to work with")
    rungs = (
        ("pixels in the picture", f"{100.0 * kept:.0f}% of the glass", "none at all"),
        ("a slot filled by it", "yes", "nothing fills a slot"),
        ("a mask to complete", "yes", "no mask to extend"),
        ("a place on the table", "from the pixels seen", "no glass is reported"),
    )
    ladder.text(46, 99, "partly covered", ha="center", va="bottom", fontsize=NOTE_SIZE, color=GOOD,
                weight="bold")
    ladder.text(84, 99, "covered completely", ha="center", va="bottom", fontsize=NOTE_SIZE,
                color=WARN, weight="bold")
    for index, (stage, good_text, bad_text) in enumerate(rungs):
        y = 86 - index * 21
        ladder.text(0, y, stage, ha="left", va="center", fontsize=NOTE_SIZE, color=INK)
        ladder.text(46, y, good_text, ha="center", va="center", fontsize=NOTE_SIZE, color=GOOD)
        ladder.text(84, y, bad_text, ha="center", va="center", fontsize=NOTE_SIZE, color=WARN)
        ladder.plot([0, 100], [y - 10.5, y - 10.5], color=MUTED, lw=0.6, alpha=0.6)
    note(ladder, 0, -6,
         "Completion extends evidence, so it needs evidence to\n"
         "extend. The first rung is where the completely covered\n"
         "glass fails, and no amount of training reaches a rung\n"
         "below the one it stands on.\n\n"
         "This is why the checks in this project are checks on\n"
         "something that was found, and why a glass that was\n"
         "never found is the dangerous case. The way out is not\n"
         "a better model but a second look from somewhere else,\n"
         "which is what moving the camera is for: turn the pair\n"
         "about the camera and the hiding is undone, because\n"
         "splay acts along the direction out from the camera and\n"
         "not across it.", colour=INK, va="top")

    figure.suptitle(
        "Amodal completion extends what was seen, so a glass that appears in no picture is beyond "
        "it.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        f"Both pairs are arrangements the cell allows: the centres are "
        f"{np.hypot(*(BITTEN[1] - OCCLUDER_FAR[1])):.0f} mm apart on the left and "
        f"{np.hypot(*(HIDING_SHORT[1] - HIDING_TALL[1])):.0f} mm apart on the right, and the cell "
        f"guarantees at least {MIN_APART:.0f} mm. Whether one silhouette covers another is decided "
        "by the same test the rest of these\ndiagrams use, which walks the boundary of the covered "
        "glass's silhouette and asks whether every point of it lies inside the covering one. On the "
        "right that test is true, so the short glass contributes no pixels, no slot is filled with "
        "it, and there is\nno mask to extend. The one glass that does come back is the tall glass "
        "itself, with a correct mask over its own pixels and a width this kind is allowed to have, "
        "so nothing anywhere says a glass is missing.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    print(f"  where it stops: partly covered keeps {100.0 * kept:.0f}%, "
          f"completely covered keeps {gone_area:.0f} mm2, splay_covers={covered}, "
          f"tall patch {patch_mm:.0f} mm")
    save(figure, "10-where-it-stops.png")


def main() -> None:
    figure_modal_against_amodal()
    figure_labels_for_free()
    figure_measuring_whether_it_works()
    figure_where_it_stops()


if __name__ == "__main__":
    main()
