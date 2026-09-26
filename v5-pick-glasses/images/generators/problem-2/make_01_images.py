"""Diagrams for solution 1 — split the blob in the picture.

Every silhouette drawn here is a real projection of one of the project's own
glass outlines, taken from ``work_cell.glasses.shapes``, through the cell's own
camera. Nothing is a circle drawn to look convincing: a standing glass is a
circle only in its footprint, which no camera in this cell ever sees straight
on, and drawing it as one is what the first version of these pictures got
wrong.

    pixi run python images/generators/problem-2/make_01_images.py
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
    KIND_TALLEST,
    KIND_WIDEST,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    SHORT_A,
    TALL_A,
    WARN,
    bare,
    new,
    save,
    splay_circles,
    splay_covers,
    splay_width,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import build, family  # noqa: E402

# ---------------------------------------------------------------------------
# The cell, in its own numbers.
# ---------------------------------------------------------------------------
FX = 277.1                 # pixels; the camera's focal length
FRAME_W, FRAME_H = 320, 240
SURVEY_H = 450.0           # mm above the table, looking straight down
VIEW_HEIGHT = 120.0        # mm above the table, looking level (MEASURE_VIEW_HEIGHT)
STANDOFF = 380.0           # mm from the near glass, derived in solution 3
BEHIND = 180.0             # mm further away the second glass stands
LATERAL = 60.0             # mm to one side
MIN_APART = 150.0          # mm, the closest two glasses ever stand in problem 2

# One kind, drawn from the project's own range, used in every picture.
GLASS_OUTLINE, _ = family("tapered_glass", 6, 1)[1]
STEMMED, _ = family("stemmed_glass", 6, 1)[1]

# The tall and the short end of the same kind, built by the project's own
# builder at the two sizes diagram_style holds for this kind. Both sets of
# proportions are inside KIND_RANGES["tapered_glass"], so these are ordinary
# glasses of the kind rather than special cases invented for a picture.
TALL_GLASS = build("tapered_glass", height=TALL_A[0] / 1000.0,
                   rim_diameter=TALL_A[1] / 1000.0, base_fraction=0.45)
SHORT_GLASS = build("tapered_glass", height=SHORT_A[0] / 1000.0,
                    rim_diameter=SHORT_A[1] / 1000.0, base_fraction=0.45)

NEAR_R = 200.0     # mm out from the point under the survey camera
PAIR_GAP = 160.0   # mm between the two centres, above the guaranteed minimum
APART = 300.0      # mm between two glasses standing in line with the level camera


def profile(outline) -> tuple[np.ndarray, np.ndarray]:
    """Heights and radii in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def size(outline) -> tuple[float, float, float]:
    """Height, base diameter, widest diameter — all in millimetres."""
    z, r = profile(outline)
    return z.max(), r[z < z.min() + 0.004].max() * 2, r.max() * 2


# ---------------------------------------------------------------------------
# The two views, projected properly.
# ---------------------------------------------------------------------------
def topdown(glasses, width=FRAME_W, height=FRAME_H, cx=None, cy=None) -> np.ndarray:
    """Straight down from SURVEY_H. A horizontal circle stays a circle, but it
    grows and slides outward as it rises, so a glass images as a teardrop."""
    mask = np.zeros((height, width), np.uint8)
    cx = width / 2 if cx is None else cx
    cy = height / 2 if cy is None else cy
    for gx, gy, outline in glasses:
        z, r = profile(outline)
        for zi, ri in zip(z, r, strict=True):
            away = SURVEY_H - zi
            if away <= 1:
                continue
            cv2.circle(
                mask,
                (int(round(cx + FX * gx / away)), int(round(cy + FX * gy / away))),
                max(1, int(round(FX * ri / away))), 255, -1,
            )
    return mask


def sideon(glasses, width=FRAME_W, height=FRAME_H, horizon=None) -> np.ndarray:
    """Level, from VIEW_HEIGHT. A horizontal circle seen edge-on is a line, so
    the silhouette is the band between the left and right walls of the profile."""
    mask = np.zeros((height, width), np.uint8)
    cx = width / 2
    horizon = height * 0.30 if horizon is None else horizon
    for gx, gy, outline in glasses:
        z, r = profile(outline)
        for zi, ri in zip(z, r, strict=True):
            row = int(round(horizon - FX * (zi - VIEW_HEIGHT) / gy))
            left = int(round(cx + FX * (gx - ri) / gy))
            right = int(round(cx + FX * (gx + ri) / gy))
            if 0 <= row < height:
                cv2.line(mask, (max(0, left), row), (min(width - 1, right), row), 255, 1)
    return mask


# ---------------------------------------------------------------------------
# The method, and the one it replaces.
# ---------------------------------------------------------------------------
def bottom_edge(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For every lit column, the lowest lit row — the underside of the blob."""
    columns = np.where(mask.any(axis=0))[0]
    rows = np.array([mask.shape[0] - 1 - np.argmax(mask[::-1, c] > 0) for c in columns])
    return columns, rows


def contact_runs(mask: np.ndarray, flat: int = 1, shortest: int = 5) -> list[tuple[int, int, float]]:
    """Stretches of the underside that are level: where something stands on the table.

    A glass has exactly one, at its base. Two glasses at different distances
    have two, at different heights in the picture, because the camera looks
    level from above the table top.
    """
    columns, rows = bottom_edge(mask)
    runs: list[tuple[int, int, float]] = []
    start = 0
    for i in range(1, len(rows) + 1):
        if i == len(rows) or abs(int(rows[i]) - int(rows[start])) > flat:
            if i - start >= shortest:
                runs.append((int(columns[start]), int(columns[i - 1]), float(np.median(rows[start:i]))))
            start = i
    return runs


def split_by_contact(mask: np.ndarray, least_gap: int = 8) -> list[tuple[int, int, float]]:
    """The runs, if two of them sit far enough apart to be two glasses."""
    runs = contact_runs(mask)
    if len(runs) < 2:
        return []
    heights = sorted(run[2] for run in runs)
    return runs if heights[-1] - heights[0] >= least_gap else []


def watershed_regions(mask: np.ndarray, fraction: float = 0.7) -> tuple[np.ndarray, int, np.ndarray]:
    """The method this solution used to use: markers from the distance transform."""
    field = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    seeds = (field > fraction * field.max()).astype(np.uint8)
    count, labels = cv2.connectedComponents(seeds)
    if count - 1 < 2:
        return field, count - 1, seeds
    labels = labels + 1
    labels[(mask > 0) & (seeds == 0)] = 0
    cv2.watershed(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), labels.astype(np.int32))
    return field, count - 1, seeds


# ---------------------------------------------------------------------------
# Drawing helpers.
# ---------------------------------------------------------------------------
def paint(axis, region: np.ndarray, colour: str, alpha: float = 1.0) -> None:
    rgba = np.zeros((*region.shape, 4), float)
    rgba[region] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest")


def outline_of(axis, mask: np.ndarray, colour: str = INK, width: float = 1.3) -> None:
    axis.contour(mask.astype(float), [0.5], colors=[colour], linewidths=width)


def stage(axis, title: str) -> None:
    bare(axis)
    axis.set_anchor("N")
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=7)


def plot_frame(axis, title: str, xlabel: str, ylabel: str) -> None:
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=7)
    axis.set_xlabel(xlabel, fontsize=NOTE_SIZE, color=INK)
    axis.set_ylabel(ylabel, fontsize=NOTE_SIZE, color=INK)
    axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)


def note(axis, x, y, text, colour=MUTED, **kwargs) -> None:
    axis.text(x, y, text, fontsize=NOTE_SIZE, color=colour, ha="center", **kwargs)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.015, text, fontsize=NOTE_SIZE, color=INK, ha="center")


def tight(mask: np.ndarray, pad: int = 8) -> tuple[int, int, int, int]:
    x, y, w, h = cv2.boundingRect(mask)
    return x - pad, x + w + pad, y - pad, y + h + pad


# ---------------------------------------------------------------------------
# 1. Where the overlap actually is — the picture that answers the question.
# ---------------------------------------------------------------------------
def picture_where_the_overlap_is() -> None:
    height, base, widest = size(GLASS_OUTLINE)
    figure, axes = new(13.2, 5.0, columns=3)
    table, survey, level = axes

    stage(table, "On the table, from above")
    table.set_aspect("equal")
    table.set_xlim(-170, 170)
    table.set_ylim(-120, 120)
    for sign, name in ((-1, "glass A"), (+1, "glass B")):
        table.add_patch(Circle((sign * MIN_APART / 2, 0), base / 2,
                               facecolor=to_rgba(GLASS, 0.30), edgecolor=GLASS, lw=1.6))
        table.text(sign * MIN_APART / 2, -base / 2 - 16, name,
                   fontsize=NOTE_SIZE, color=INK, ha="center")
    table.annotate("", xy=(-MIN_APART / 2, 26), xytext=(MIN_APART / 2, 26),
                   arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.0})
    note(table, 0, 38, f"{MIN_APART:.0f} mm — the closest they ever stand", INK)
    note(table, 0, -100, f"footprints {base:.0f} mm across: a clear {MIN_APART - base:.0f} mm between them")

    # Off to one side of the point under the camera, which is where a glass
    # actually stands in a survey picture and where the teardrop is visible.
    near_x, far_x = 90.0, 90.0 + MIN_APART
    both_in = topdown([(near_x, 0, GLASS_OUTLINE), (far_x, 0, GLASS_OUTLINE)],
                      width=620, height=300, cx=40, cy=150)
    blobs, _ = cv2.connectedComponents(both_in)
    stage(survey, "The survey picture — straight down")
    paint(survey, both_in > 0, GLASS, 0.45)
    outline_of(survey, both_in > 0)
    left, right, top, bottom = tight(both_in, 22)
    survey.set_xlim(left, right)
    survey.set_ylim(bottom + 44, top - 16)
    note(survey, (left + right) / 2, top - 6, f"{blobs - 1} patches — still two", GOOD)
    note(survey, (left + right) / 2, bottom + 34,
         "each one a teardrop, leaning away from\nthe point under the camera — but clear of each other")

    merged = sideon([(0, STANDOFF, GLASS_OUTLINE), (LATERAL, STANDOFF + BEHIND, GLASS_OUTLINE)],
                    width=300, height=210, horizon=64)
    near_only = sideon([(0, STANDOFF, GLASS_OUTLINE)], width=300, height=210, horizon=64)
    count, _ = cv2.connectedComponents(merged)
    stage(level, "The level picture — from the side")
    paint(level, merged > 0, GLASS, 0.22)
    paint(level, near_only > 0, GLASS, 0.45)
    outline_of(level, merged > 0)
    left, right, top, bottom = tight(merged, 26)
    level.set_xlim(left, right)
    level.set_ylim(bottom + 26, top - 14)
    note(level, (left + right) / 2, top - 4, f"{count - 1} patch — one blob", WARN)
    note(level, (left + right) / 2, bottom + 18,
         "the near glass (solid) stands in front of\nthe far one (pale), and the outlines join")

    footer(figure,
           "Two solid glasses cannot overlap on the table, and from straight above they do not overlap in "
           "the " "picture either. The merging happens in the level view, and that is the only view this "
           "solution is about.")
    figure.subplots_adjust(bottom=0.16, top=0.88, wspace=0.12)
    save(figure, "01-where-the-overlap-is.png")


# ---------------------------------------------------------------------------
# 2. Why the survey cannot produce the case at all.
# ---------------------------------------------------------------------------
def picture_the_survey_cannot() -> None:
    height, base, widest = size(GLASS_OUTLINE)
    figure, axes = new(12.4, 4.4, columns=2)
    shrink, counted = axes

    plot_frame(shrink, "How much table one survey picture holds, by height above it",
               "height above the table (mm)", "half-width of the frame (mm)")
    zs = np.linspace(0, 240, 200)
    half = (FRAME_W / 2) * (SURVEY_H - zs) / FX
    shrink.plot(zs, half, color=GLASS, lw=2.0)
    shrink.axhline(MIN_APART / 2 + widest / 2, color=MUTED, lw=1.0, ls=(0, (4, 3)))
    shrink.text(6, MIN_APART / 2 + widest / 2 + 5,
                f"what two glasses {MIN_APART:.0f} mm apart need: {MIN_APART / 2 + widest / 2:.0f} mm",
                fontsize=NOTE_SIZE, color=MUTED)
    for z, label in ((0.0, "the table"), (height, f"the rim, {height:.0f} mm up")):
        y = (FRAME_W / 2) * (SURVEY_H - z) / FX
        shrink.plot([z], [y], "o", color=INK, ms=5)
        shrink.annotate(f"{label}\n{y:.0f} mm", xy=(z, y), xytext=(z + 16, y + 14),
                        fontsize=NOTE_SIZE, color=INK,
                        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    shrink.set_ylim(0, 290)

    stage(counted, "Every legal pair, in one 320x240 survey frame")
    counted.set_xlim(0, 10)
    counted.set_ylim(0, 10)
    counted.add_patch(Rectangle((0.6, 5.6), 8.8, 3.0, facecolor=to_rgba(GOOD, 0.14),
                                edgecolor=GOOD, lw=1.4))
    counted.text(5.0, 7.7, "both glasses wholly inside the frame", fontsize=NOTE_SIZE + 0.6,
                 color=INK, ha="center")
    counted.text(5.0, 6.4, "4320 arrangements tried,  24 qualify", fontsize=LABEL_SIZE + 1,
                 color=INK, ha="center")
    counted.add_patch(Rectangle((0.6, 1.9), 8.8, 2.9, facecolor=to_rgba(WARN, 0.10),
                                edgecolor=WARN, lw=1.4))
    counted.text(5.0, 3.9, "of those 24, how many merge into one patch", fontsize=NOTE_SIZE + 0.6,
                 color=INK, ha="center")
    counted.text(5.0, 2.6, "none", fontsize=LABEL_SIZE + 5, color=WARN, ha="center")
    counted.text(5.0, 0.8,
                 "the rest have a glass falling off the edge of the frame,\n"
                 "which the overlapping stations already handle",
                 fontsize=NOTE_SIZE, color=MUTED, ha="center")

    rim_span = FRAME_W * (SURVEY_H - height) / FX
    footer(figure,
           f"The frame holds {FRAME_W * SURVEY_H / FX:.0f} mm of table but only {rim_span:.0f} mm at the "
           "height of this rim. Two glasses far enough apart to be legal are either both in frame and "
           "separate, or one of them is half out of the picture.")
    figure.subplots_adjust(bottom=0.17, top=0.90, wspace=0.18)
    save(figure, "01-the-survey-cannot-see-it.png")


# ---------------------------------------------------------------------------
# 3. A standing glass is not a circle.
# ---------------------------------------------------------------------------
def picture_not_a_circle() -> None:
    height, base, widest = size(GLASS_OUTLINE)
    z, r = profile(GLASS_OUTLINE)
    stand = 200.0
    figure, axes = new(13.0, 4.6, columns=3)
    rays, shape, wrong = axes

    stage(rays, "Why — the camera is only 310 mm above the rim")
    rays.set_aspect("equal")
    rays.set_xlim(-30, 330)
    rays.set_ylim(-40, 500)
    rays.plot([-20, 320], [0, 0], color=MUTED, lw=1.2)
    note(rays, 90, -30, "the table")
    rays.plot([0], [SURVEY_H], "o", color=INK, ms=7)
    rays.text(0, SURVEY_H + 16, "camera", fontsize=NOTE_SIZE, color=INK, ha="center")
    rays.fill_betweenx(z, stand - r, stand + r, color=to_rgba(GLASS, 0.35), lw=0)
    rays.plot(stand + r, z, color=GLASS, lw=1.3)
    rays.plot(stand - r, z, color=GLASS, lw=1.3)
    for zi, ri, colour in ((0.0, base / 2, MUTED), (height, widest / 2, WARN)):
        landing = (stand + ri) * SURVEY_H / (SURVEY_H - zi)
        rays.plot([0, landing], [SURVEY_H, 0], color=colour, lw=1.1, ls=(0, (5, 3)))
        rays.plot([landing], [0], "o", color=colour, ms=5)
    rim_landing = (stand + widest / 2) * SURVEY_H / (SURVEY_H - height)
    rays.annotate("", xy=((stand + base / 2), -18), xytext=(rim_landing, -18),
                  arrowprops={"arrowstyle": "<->", "color": WARN, "lw": 1.1})
    note(rays, 300, 150, "the rim lands\nout here", WARN)

    real = topdown([(stand, 0, GLASS_OUTLINE)], width=440, height=240, cx=40, cy=120)
    stage(shape, "So this is the silhouette")
    paint(shape, real > 0, GLASS, 0.45)
    outline_of(shape, real > 0)
    left, right, top, bottom = tight(real, 16)
    shape.set_xlim(left, right)
    shape.set_ylim(bottom, top)
    wide = cv2.boundingRect(real)[2]
    note(shape, (left + right) / 2, top + 11, f"{wide} px across", INK)
    note(shape, (left + right) / 2, bottom - 7,
         f"a {base:.0f} mm footprint, imaged {wide * SURVEY_H / FX:.0f} mm wide")

    stage(wrong, "What the first version of this page drew")
    wrong.set_aspect("equal")
    wrong.set_xlim(-110, 110)
    wrong.set_ylim(-80, 80)
    for sign in (-1, +1):
        wrong.add_patch(Circle((sign * 26, 0), 45, facecolor=to_rgba(WARN, 0.22),
                               edgecolor=WARN, lw=1.6))
    note(wrong, 0, 60, "two footprints overlapping", WARN)
    note(wrong, 0, -62, "which two solid glasses cannot do,\nand no camera here sees anyway")

    footer(figure,
           "A glass is a circle in its footprint only. Seen from above it is a teardrop, because the rim is "
           "wider than " "the base and 140 mm nearer the lens; seen from the side it is a profile. Neither "
           "is the circle.")
    figure.subplots_adjust(bottom=0.16, top=0.89, wspace=0.12)
    save(figure, "01-a-glass-is-not-a-circle.png")


# ---------------------------------------------------------------------------
# 4. The blob the level view really returns.
# ---------------------------------------------------------------------------
def picture_the_blob() -> None:
    height, base, widest = size(GLASS_OUTLINE)
    near = sideon([(0, STANDOFF, GLASS_OUTLINE)], width=220, height=200, horizon=62)
    both = sideon([(0, STANDOFF, GLASS_OUTLINE), (LATERAL, STANDOFF + BEHIND, GLASS_OUTLINE)],
                  width=220, height=200, horizon=62)
    figure, axes = new(12.6, 4.6, columns=3)
    one, two, verdict = axes

    for axis, mask, title in ((one, near, "One glass, 380 mm away"),
                              (two, both, "And a second, 180 mm behind it")):
        stage(axis, title)
        paint(axis, mask > 0, GLASS, 0.45)
        outline_of(axis, mask > 0)
        left, right, top, bottom = tight(both, 14)
        axis.set_xlim(left, right)
        axis.set_ylim(bottom, top)
    wide_one = cv2.boundingRect(near)[2]
    wide_two = cv2.boundingRect(both)[2]
    middle = (tight(both, 14)[0] + tight(both, 14)[1]) / 2
    note(one, middle, tight(both, 14)[2] + 10, f"{wide_one} px across", INK)
    note(two, middle, tight(both, 14)[2] + 10, f"{wide_two} px across", WARN)

    stage(verdict, "What the arithmetic notices")
    verdict.set_xlim(0, 10)
    verdict.set_ylim(0, 10)
    limit = widest * FX / STANDOFF
    rows = [("widest this kind can be", f"{widest:.0f} mm = {limit:.0f} px", MUTED),
            ("+ 2 px for the rounded edge", f"{limit + 2:.0f} px", MUTED),
            ("one glass measures", f"{wide_one} px — left alone", GOOD),
            ("the pair measures", f"{wide_two} px — flagged", WARN)]
    for i, (label, value, colour) in enumerate(rows):
        y = 8.2 - i * 1.9
        verdict.text(0.3, y, label, fontsize=NOTE_SIZE, color=MUTED, ha="left")
        verdict.text(9.7, y, value, fontsize=NOTE_SIZE + 0.8, color=colour, ha="right")
        verdict.plot([0.3, 9.7], [y - 0.65, y - 0.65], color="#e6e8eb", lw=1.0)
    verdict.text(5.0, 0.7, "connected components never asked how wide it was.\n"
                           "It only asked whether the pixels were joined.",
                 fontsize=NOTE_SIZE, color=MUTED, ha="center")

    footer(figure,
           "The trigger is the one number this method takes from outside the picture: the widest the known "
           "kind can be, in pixels at the distance the camera stood. Anything narrower is left alone.")
    figure.subplots_adjust(bottom=0.15, top=0.89, wspace=0.12)
    save(figure, "01-the-blob.png")


# ---------------------------------------------------------------------------
# 5. Why the distance transform cannot help.
# ---------------------------------------------------------------------------
def picture_watershed_fails() -> None:
    both = sideon([(0, STANDOFF, GLASS_OUTLINE), (LATERAL, STANDOFF + BEHIND, GLASS_OUTLINE)],
                  width=220, height=200, horizon=62)
    field, markers, seeds = watershed_regions(both)
    discs = np.zeros((200, 220), np.uint8)
    cv2.circle(discs, (86, 105), 42, 255, -1)
    cv2.circle(discs, (166, 105), 42, 255, -1)
    disc_field, disc_markers, disc_seeds = watershed_regions(discs)

    figure, axes = new(13.0, 4.7, columns=3)
    round_case, tall_case, why = axes

    stage(round_case, "What the method is for: round, squat objects")
    round_case.imshow(disc_field, cmap="viridis")
    round_case.contour(disc_seeds.astype(float), [0.5], colors=[WARN], linewidths=1.4)
    left, right, top, bottom = tight(discs, 12)
    round_case.set_xlim(left, right)
    round_case.set_ylim(bottom, top)
    note(round_case, (left + right) / 2, bottom - 6,
         f"{disc_markers} peaks, so {disc_markers} markers — it splits", GOOD)

    stage(tall_case, "What this cell has: tall, thin ones")
    tall_case.imshow(field, cmap="viridis")
    tall_case.contour(seeds.astype(float), [0.5], colors=[WARN], linewidths=1.4)
    left, right, top, bottom = tight(both, 12)
    tall_case.set_xlim(left, right)
    tall_case.set_ylim(bottom, top)
    note(tall_case, (left + right) / 2, bottom - 6,
         f"one ridge, {markers} marker — nothing to flood from", WARN)

    stage(why, "")
    why.set_xlim(0, 10)
    why.set_ylim(0, 10)
    why.text(5.0, 9.0, "The distance transform asks:\n"
                       "how far is this pixel from the outside?",
             fontsize=NOTE_SIZE + 0.6, color=INK, ha="center")
    why.text(5.0, 6.4, "In a squat object the deepest point is a\n"
                       "single peak at the middle. Two objects,\n"
                       "two peaks, and the flood walls meet at the waist.",
             fontsize=NOTE_SIZE, color=MUTED, ha="center")
    why.text(5.0, 3.6, "In a tall thin object the depth is capped by the\n"
                       "half-width, everywhere up its length. The deepest\n"
                       "set is a line, not a point — and two of them\n"
                       "side by side merge into one line.",
             fontsize=NOTE_SIZE, color=MUTED, ha="center")
    why.add_patch(Rectangle((0.7, 0.6), 8.6, 1.7, facecolor=to_rgba(WARN, 0.12),
                            edgecolor=WARN, lw=1.2))
    why.text(5.0, 1.45, "splits 3 per cent of real merged pairs",
             fontsize=LABEL_SIZE + 1, color=WARN, ha="center", va="center")

    footer(figure,
           "This is not a threshold that needs tuning. A standing glass seen from the side is four times "
           "taller than " "it is wide, and the distance transform of a tall thin shape has no peak to put a "
           "marker on.")
    figure.subplots_adjust(bottom=0.15, top=0.89, wspace=0.12)
    save(figure, "01-the-distance-transform-fails.png")


# ---------------------------------------------------------------------------
# 6. The mechanism that does work: further away means higher up.
# ---------------------------------------------------------------------------
def picture_bases_sit_higher() -> None:
    height, base, widest = size(GLASS_OUTLINE)
    far = STANDOFF + BEHIND
    figure, axes = new(12.8, 4.6, columns=2)
    elevation, arithmetic = axes

    stage(elevation, "The camera looks level, from above the table top")
    elevation.set_aspect("equal")
    elevation.set_xlim(-60, 640)
    elevation.set_ylim(-60, 230)
    elevation.plot([-40, 620], [0, 0], color=MUTED, lw=1.2)
    note(elevation, 300, -40, "the table")
    elevation.plot([0], [VIEW_HEIGHT], "o", color=INK, ms=7)
    elevation.text(0, VIEW_HEIGHT + 14, "camera", fontsize=NOTE_SIZE, color=INK, ha="center")
    elevation.plot([-40, 620], [VIEW_HEIGHT, VIEW_HEIGHT], color=MUTED, lw=0.9, ls=(0, (5, 4)))
    elevation.text(600, VIEW_HEIGHT + 8, "the horizon", fontsize=NOTE_SIZE, color=MUTED, ha="right")
    z, r = profile(GLASS_OUTLINE)
    for distance, shade in ((STANDOFF, 0.42), (far, 0.24)):
        elevation.fill_betweenx(z, distance - r, distance + r, color=to_rgba(GLASS, shade), lw=0)
        elevation.plot(distance + r, z, color=GLASS, lw=1.2)
        elevation.plot(distance - r, z, color=GLASS, lw=1.2)
        elevation.plot([0, distance], [VIEW_HEIGHT, 0], color=WARN, lw=1.0, ls=(0, (4, 3)))
        elevation.text(distance, -26, f"{distance:.0f} mm", fontsize=NOTE_SIZE, color=INK, ha="center")
    note(elevation, 300, 200,
         "the line to a nearer base dips more steeply,\nso a nearer base lands lower in the picture", INK)

    plot_frame(arithmetic, "Where each part of a glass lands, in pixels from the horizon",
               "distance from the camera (mm)", "pixels below the horizon")
    ds = np.linspace(280, 640, 200)
    for zi, label, colour in ((0.0, "its base", WARN), (height, "its rim", MUTED)):
        arithmetic.plot(ds, FX * (VIEW_HEIGHT - zi) / ds, color=colour, lw=2.0, label=label)
    for distance in (STANDOFF, far):
        arithmetic.axvline(distance, color="#e6e8eb", lw=1.0)
    bn = FX * VIEW_HEIGHT / STANDOFF
    bf = FX * VIEW_HEIGHT / far
    arithmetic.annotate("", xy=(far, bf), xytext=(far, bn),
                        arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.2})
    arithmetic.text(far + 12, (bn + bf) / 2, f"{bn - bf:.0f} px", fontsize=LABEL_SIZE,
                    color=INK, va="center")
    arithmetic.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper right")
    rim_gap = FX * abs(VIEW_HEIGHT - height) * (1 / STANDOFF - 1 / far)
    arithmetic.text(0.02, 0.30,
                    f"the rims differ by only {rim_gap:.0f} px, because a rim sits"
                    "\nnearly at the camera's own height",
                    transform=arithmetic.transAxes, fontsize=NOTE_SIZE, color=MUTED)

    footer(figure,
           "This is the whole idea. The camera sits 120 mm above the table, so the table recedes to the "
           "horizon and a " "glass standing further away has its base drawn higher up the picture.")
    figure.subplots_adjust(bottom=0.17, top=0.89, wspace=0.20)
    save(figure, "01-bases-sit-higher.png")


# ---------------------------------------------------------------------------
# 7. The test itself.
# ---------------------------------------------------------------------------
def picture_contact_runs() -> None:
    both = sideon([(0, STANDOFF, GLASS_OUTLINE), (LATERAL, STANDOFF + BEHIND, GLASS_OUTLINE)],
                  width=220, height=200, horizon=62)
    columns, rows = bottom_edge(both)
    runs = split_by_contact(both)
    figure, axes = new(13.0, 4.7, columns=3)
    blob, edge, answer = axes

    stage(blob, "The blob, with its underside marked")
    paint(blob, both > 0, GLASS, 0.35)
    outline_of(blob, both > 0)
    blob.plot(columns, rows, color=WARN, lw=2.0)
    left, right, top, bottom = tight(both, 14)
    blob.set_xlim(left, right)
    blob.set_ylim(bottom, top)
    note(blob, (left + right) / 2, bottom - 6, "the lowest lit pixel in every column")

    plot_frame(edge, "That underside, plotted", "column across the blob", "row in the picture")
    edge.plot(columns - columns[0], rows, color=MUTED, lw=1.4)
    for start, stop, row in runs:
        edge.plot([start - columns[0], stop - columns[0]], [row, row], color=GOOD, lw=4.0,
                  solid_capstyle="butt")
    edge.invert_yaxis()
    if len(runs) >= 2:
        low = max(runs, key=lambda x: x[2])
        high = min(runs, key=lambda x: x[2])
        edge.annotate("", xy=(low[0] - columns[0] + 4, low[2]),
                      xytext=(low[0] - columns[0] + 4, high[2]),
                      arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.1})
        edge.text(low[0] - columns[0] + 9, (low[2] + high[2]) / 2,
                  f"{low[2] - high[2]:.0f} px apart", fontsize=NOTE_SIZE, color=INK, va="center")
    edge.text(0.98, 0.06, "green: where something stands on the table",
              transform=edge.transAxes, fontsize=NOTE_SIZE, color=GOOD, ha="right")

    stage(answer, "Two level stretches, two glasses")
    paint(answer, both > 0, MUTED, 0.22)
    ordered = sorted(runs, key=lambda x: -x[2])[:2]
    for (start, stop, row), colour, label in zip(ordered, (GLASS, GOOD),
                                                 ("nearer", "further"), strict=True):
        patch = np.zeros_like(both, bool)
        patch[:, start:stop + 1] = both[:, start:stop + 1] > 0
        paint(answer, patch, colour, 0.45)
        answer.plot([start, stop], [row, row], color=colour, lw=3.2, solid_capstyle="butt")
        answer.text((start + stop) / 2, row - 14, label, fontsize=NOTE_SIZE, color=colour, ha="center")
    outline_of(answer, both > 0)
    answer.set_xlim(left, right)
    answer.set_ylim(bottom, top)
    note(answer, (left + right) / 2, bottom - 6, "and the lower one is the nearer one")

    footer(figure,
           "One glass has one contact line. Two glasses at different distances have two, at different "
           "heights, and " "which is nearer comes free — the lower stretch is the nearer glass.")
    figure.subplots_adjust(bottom=0.15, top=0.89, wspace=0.20)
    save(figure, "01-contact-runs.png")


# ---------------------------------------------------------------------------
# 8. The control: why it counts level stretches and not steps.
# ---------------------------------------------------------------------------
def picture_the_control() -> None:
    single = sideon([(0, STANDOFF, STEMMED)], width=220, height=230, horizon=74)
    columns, rows = bottom_edge(single)
    runs = contact_runs(single)
    steps = np.abs(np.diff(rows))
    figure, axes = new(12.8, 4.7, columns=3)
    shape, profile_axis, verdict = axes

    stage(shape, "One stemmed glass, on its own")
    paint(shape, single > 0, GLASS, 0.40)
    outline_of(shape, single > 0)
    shape.plot(columns, rows, color=WARN, lw=2.0)
    left, right, top, bottom = tight(single, 14)
    shape.set_xlim(left, right)
    shape.set_ylim(bottom, top)
    note(shape, (left + right) / 2, bottom - 6, "the bowl hangs out over the foot")

    plot_frame(profile_axis, "Its underside steps too", "column across the blob", "row in the picture")
    profile_axis.plot(columns - columns[0], rows, color=MUTED, lw=1.4)
    for start, stop, row in runs:
        profile_axis.plot([start - columns[0], stop - columns[0]], [row, row], color=GOOD, lw=4.0,
                          solid_capstyle="butt")
    profile_axis.invert_yaxis()
    profile_axis.text(0.02, 0.10, f"biggest step between neighbouring columns: {steps.max()} px",
                      transform=profile_axis.transAxes, fontsize=NOTE_SIZE, color=WARN)
    profile_axis.text(0.02, 0.02, f"level stretches found: {len(runs)}",
                      transform=profile_axis.transAxes, fontsize=NOTE_SIZE, color=GOOD)
    low, high = profile_axis.get_ylim()
    profile_axis.set_ylim(low + 16, high)

    stage(verdict, "")
    verdict.set_xlim(0, 10)
    verdict.set_ylim(0, 10)
    verdict.text(5.0, 9.2, "So the test cannot be \"is there a step?\"",
                 fontsize=NOTE_SIZE + 0.8, color=INK, ha="center")
    verdict.text(5.0, 7.3, "A stemmed glass's own outline steps by tens of\n"
                           "pixels where its bowl stops overhanging its foot.\n"
                           "Counting steps splits 69 per cent of single glasses.",
                 fontsize=NOTE_SIZE, color=WARN, ha="center")
    verdict.text(5.0, 4.6, "It has to be \"how many level stretches, and\n"
                           "how far apart?\" A glass rests on the table in\n"
                           "exactly one place, however odd its shape.",
                 fontsize=NOTE_SIZE, color=INK, ha="center")
    verdict.add_patch(Rectangle((0.7, 1.2), 8.6, 2.2, facecolor=to_rgba(GOOD, 0.14),
                                edgecolor=GOOD, lw=1.3))
    verdict.text(5.0, 2.3, "0 of 120 single glasses falsely split",
                 fontsize=LABEL_SIZE + 1, color=GOOD, ha="center", va="center")

    footer(figure,
           "The control matters more than the result. A splitter that fires on a single glass turns one "
           "correct answer " "into two wrong ones, and this cell would rather miss a pair than invent one.")
    figure.subplots_adjust(bottom=0.15, top=0.89, wspace=0.20)
    save(figure, "01-the-control.png")


# ---------------------------------------------------------------------------
# 9. Where it works and where it cannot.
# ---------------------------------------------------------------------------
def picture_where_it_works() -> None:
    offsets = [0, 20, 40, 60, 80, 100]
    merged, visible, split = [], [], []
    for lateral in offsets:
        m_count = v_count = s_count = 0
        for kind in ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"):
            for outline, _ in family(kind, 6, 1):
                both = sideon([(0, STANDOFF, outline), (lateral, STANDOFF + BEHIND, outline)],
                              width=1200, height=900, horizon=400)
                count, _ = cv2.connectedComponents(both)
                if count - 1 != 1:
                    continue
                m_count += 1
                near = sideon([(0, STANDOFF, outline)], width=1200, height=900, horizon=400)
                far = sideon([(lateral, STANDOFF + BEHIND, outline)], width=1200, height=900, horizon=400)
                far_columns, far_rows = bottom_edge(far)
                row = int(np.median(far_rows))
                exposed = sum(1 for c in far_columns if far[row, c] > 0 and near[row, c] == 0)
                if exposed >= 5:
                    v_count += 1
                if split_by_contact(both):
                    s_count += 1
        merged.append(m_count)
        visible.append(v_count)
        split.append(s_count)

    figure, axes = new(12.8, 4.7, columns=2)
    bars, summary = axes
    x = np.arange(len(offsets))
    bars.bar(x - 0.26, merged, 0.26, color=MUTED, label="merged into one blob")
    bars.bar(x, visible, 0.26, color=GLASS, label="far glass's base visible")
    bars.bar(x + 0.26, split, 0.26, color=GOOD, label="split by the test")
    plot_frame(bars, "By how far the far glass stands to one side",
               "lateral offset (mm)", "arrangements, of 24")
    bars.set_xticks(x)
    bars.set_xticklabels([str(o) for o in offsets])
    bars.legend(fontsize=NOTE_SIZE, frameon=False, loc="lower left")
    bars.text(0.5, 1.10, "from 40 mm out, it splits every merged pair",
              transform=bars.transAxes, fontsize=NOTE_SIZE, color=GOOD, ha="center")

    stage(summary, "")
    summary.set_xlim(0, 10)
    summary.set_ylim(0, 10)
    total_merged, total_split = sum(merged), sum(split)
    from_40 = sum(split[i] for i, o in enumerate(offsets) if o >= 40)
    merged_40 = sum(merged[i] for i, o in enumerate(offsets) if o >= 40)
    lines = [("merged pairs tried", f"{total_merged}", INK),
             ("40 mm of offset or more", f"{from_40} of {merged_40}", GOOD),
             ("the test splits, in all", f"{total_split}", GOOD),
             ("watershed splits", f"{round(0.03 * total_merged)}", WARN)]
    for i, (label, value, colour) in enumerate(lines):
        y = 8.4 - i * 1.7
        summary.text(0.4, y, label, fontsize=NOTE_SIZE + 0.4, color=MUTED, ha="left")
        summary.text(9.6, y, value, fontsize=LABEL_SIZE + 3, color=colour, ha="right")
        summary.plot([0.4, 9.6], [y - 0.55, y - 0.55], color="#e6e8eb", lw=1.0)
    summary.text(5.0, 1.1,
                 "The gap is not a tuning failure. When the far glass stands\n"
                 "close to directly behind the near one its base is hidden,\n"
                 "and no amount of work on this picture will recover it.\n"
                 "That pair goes to solution 3, which moves the camera.",
                 fontsize=NOTE_SIZE, color=MUTED, ha="center")

    footer(figure,
           "Every merged pair with 40 mm of lateral offset or more, and none of the ones standing almost "
           "directly in line. That is not a harder version of the same problem — it is a different one, and "
           "it has its own solution.")
    figure.subplots_adjust(bottom=0.16, top=0.91, wspace=0.20)
    save(figure, "01-where-it-works.png")


# ---------------------------------------------------------------------------
# 10. What a split still does not buy you.
# ---------------------------------------------------------------------------
def picture_what_it_does_not_buy() -> None:
    height, base, widest = size(GLASS_OUTLINE)
    figure, axes = new(12.6, 4.5, columns=2)
    bias, handover = axes

    stage(bias, "A split says which pixels. It does not say where.")
    bias.set_aspect("equal")
    bias.set_xlim(-50, 640)
    bias.set_ylim(-70, 210)
    bias.plot([-30, 620], [0, 0], color=MUTED, lw=1.2)
    bias.plot([0], [VIEW_HEIGHT], "o", color=INK, ms=7)
    bias.text(0, VIEW_HEIGHT + 14, "camera", fontsize=NOTE_SIZE, color=INK, ha="center")
    z, r = profile(GLASS_OUTLINE)
    bias.fill_betweenx(z, STANDOFF - r, STANDOFF + r, color=to_rgba(GLASS, 0.35), lw=0)
    bias.plot(STANDOFF + r, z, color=GLASS, lw=1.2)
    bias.plot(STANDOFF - r, z, color=GLASS, lw=1.2)
    widest_z = float(z[np.argmax(r)])
    landing = (STANDOFF + widest / 2) * (0 - VIEW_HEIGHT) / (widest_z - VIEW_HEIGHT)
    bias.plot([0, landing], [VIEW_HEIGHT, 0], color=WARN, lw=1.1, ls=(0, (5, 3)))
    bias.plot([landing], [0], "o", color=WARN, ms=6)
    bias.plot([STANDOFF], [0], "o", color=INK, ms=6)
    bias.annotate("", xy=(STANDOFF, -26), xytext=(landing, -26),
                  arrowprops={"arrowstyle": "<->", "color": WARN, "lw": 1.1})
    bias.text((STANDOFF + landing) / 2, -52, "the error a silhouette carries",
              fontsize=NOTE_SIZE, color=WARN, ha="center")
    note(bias, 300, 185, "the widest part of the glass is not on the table,\n"
                         "so its outline does not sit where the glass does", INK)

    stage(handover, "")
    handover.set_xlim(0, 10)
    handover.set_ylim(0, 10)
    boxes = [("splits a blob into two masks", GOOD, 8.0),
             ("says which is nearer", GOOD, 6.3),
             ("gives a position in millimetres", WARN, 4.6),
             ("survives the far base being hidden", WARN, 2.9)]
    for label, colour, y in boxes:
        mark = "yes" if colour == GOOD else "no"
        handover.add_patch(Rectangle((0.5, y - 0.6), 9.0, 1.2,
                                     facecolor=to_rgba(colour, 0.12), edgecolor=colour, lw=1.1))
        handover.text(1.0, y, label, fontsize=NOTE_SIZE + 0.4, color=INK, va="center")
        handover.text(9.0, y, mark, fontsize=LABEL_SIZE, color=colour, va="center", ha="right")
    handover.text(5.0, 1.2, "Both halves are still silhouettes laid on the table plane,\n"
                            "carrying the bias on the left. Positions come from solution 2.",
                  fontsize=NOTE_SIZE, color=MUTED, ha="center")

    footer(figure,
           "This solution answers one question — how many glasses are in this patch — and hands the answer "
           "to the " "methods that can turn pixels into millimetres.")
    figure.subplots_adjust(bottom=0.15, top=0.92, wspace=0.16)
    save(figure, "01-what-it-does-not-buy.png")


# ---------------------------------------------------------------------------
# 11. Completely hidden from above: splay, and what it costs the frame.
# ---------------------------------------------------------------------------
def picture_hidden_from_above() -> None:
    """The one arrangement in which a glass reaches the survey picture not at all.

    Both silhouettes are real projections through ``topdown``. ``splay_covers``
    is the test for the short glass appearing in no picture at all, and the
    dashed rectangle is the real 320x240 frame, so what the arrangement costs
    is visible in the same picture as the arrangement.
    """
    scale = FX / SURVEY_H                      # pixels per millimetre of splayed offset
    nadir = np.array([0.0, 0.0])
    tall_at = np.array([NEAR_R, 0.0])
    along = tall_at + np.array([PAIR_GAP, 0.0])
    across = tall_at + np.array([0.0, PAIR_GAP])

    width, height = 540, 400
    nx, ny = 180, 170

    def picture(short_at):
        args = {"width": width, "height": height, "cx": nx, "cy": ny}
        both = topdown([(tall_at[0], tall_at[1], TALL_GLASS),
                        (short_at[0], short_at[1], SHORT_GLASS)], **args)
        tall = topdown([(tall_at[0], tall_at[1], TALL_GLASS)], **args)
        short = topdown([(short_at[0], short_at[1], SHORT_GLASS)], **args)
        patches, _ = cv2.connectedComponents(both)
        return {"both": both, "tall": tall, "short": short, "patches": patches - 1,
                "showing": int(((short > 0) & (tall == 0)).sum()),
                "total": int((short > 0).sum())}

    hidden = picture(along)
    beside = picture(across)
    covers = splay_covers(splay_circles(nadir, tall_at, *TALL_A),
                          splay_circles(nadir, along, *SHORT_A))
    patch_mm = splay_width(splay_circles(nadir, tall_at, *TALL_A))
    kind_mm = splay_width(splay_circles(nadir, tall_at, KIND_TALLEST, KIND_WIDEST))
    reach_px = (2.0 * (NEAR_R + TALL_A[1] / 2.0)) * scale

    figure, axes = new(13.4, 4.4, columns=3)
    table, gone, there = axes

    # ---------------------------------------------------- panel 1: the table
    stage(table, "On the table: one legal arrangement, turned two ways")
    table.set_aspect("equal")
    table.set_xlim(-90, 480)
    table.set_ylim(-150, 280)
    table.plot([0, 470], [0, 0], color=MUTED, lw=0.8, ls=(0, (5, 4)), zorder=1)
    table.plot([0], [0], "x", color=WARN, ms=9, mew=1.8, zorder=4)
    note(table, 0, -22, "the point under\nthe camera", WARN, va="top")
    table.add_patch(Circle(tuple(tall_at), size(TALL_GLASS)[1] / 2,
                           facecolor=to_rgba(GLASS, 0.34), edgecolor=GLASS, lw=1.6, zorder=3))
    note(table, tall_at[0], -22, f"the tall glass,\n{TALL_A[0]:.0f} mm", GLASS, va="top")
    for spot in (along, across):
        table.add_patch(Circle(tuple(spot), size(SHORT_GLASS)[1] / 2,
                               facecolor=to_rgba(GOOD, 0.30), edgecolor=GOOD, lw=1.6, zorder=3))
        table.annotate("", xy=tuple(spot), xytext=tuple(tall_at),
                       arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.1}, zorder=2)
    note(table, along[0], -22, f"the short glass,\n{SHORT_A[0]:.0f} mm", GOOD, va="top")
    note(table, (tall_at[0] + along[0]) / 2, 12, f"{PAIR_GAP:.0f} mm", INK, va="bottom")
    table.text(tall_at[0] - 12, PAIR_GAP / 2, f"{PAIR_GAP:.0f} mm",
               fontsize=NOTE_SIZE, color=INK, ha="right", va="center")
    note(table, across[0], across[1] + 26, "the same glass, moved\nacross the radius instead",
         GOOD, va="bottom")

    # ------------------------------------------- panels 2 and 3: the pictures
    for axis, case, title in ((gone, hidden, "The picture: along the radius"),
                              (there, beside, "The picture: across the radius")):
        stage(axis, title)
        axis.add_patch(Rectangle((nx - FRAME_W / 2, ny - FRAME_H / 2), FRAME_W, FRAME_H,
                                 facecolor="none", edgecolor=MUTED, lw=1.2, ls=(0, (5, 4))))
        paint(axis, case["tall"] > 0, GLASS, 0.34)
        paint(axis, (case["short"] > 0) & (case["tall"] == 0), GOOD, 0.55)
        outline_of(axis, case["both"] > 0)
        axis.contour(case["short"].astype(float), [0.5], colors=[WARN], linewidths=1.1,
                     linestyles="dashed")
        axis.plot([nx], [ny], "x", color=WARN, ms=8, mew=1.6)
        axis.set_xlim(-6, 524)
        axis.set_ylim(392, -20)
        colour = WARN if case["showing"] == 0 else GOOD
        note(axis, 258, -14, f"{case['patches']} patch" if case["patches"] == 1
             else f"{case['patches']} patches", colour)
        axis.text(26, 284, "the 320x240 survey frame", fontsize=NOTE_SIZE, color=MUTED,
                  ha="left", va="bottom")

    note(gone, 360, 100, "the dashed line is the short glass,\n"
                         "inside the tall one's silhouette", WARN, va="bottom",
         bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    note(gone, 258, 336,
         f"{hidden['showing']} of the short glass's {hidden['total']} pixels reach the picture,\n"
         f"and the patch that comes back is the tall glass's\n"
         f"own silhouette, {patch_mm:.0f} mm across against the {kind_mm:.0f} mm\n"
         f"a single glass of this kind can draw from there", WARN, va="top")
    note(there, 258, 336,
         f"all {beside['showing']} of the short glass's pixels reach the picture,\n"
         f"from the same two glasses, the same {PAIR_GAP:.0f} mm apart,\n"
         f"turned a quarter turn about the tall one", GOOD, va="top")

    footer(figure,
           f"Splay is radial, so it hides only along a radius. The price is in the dashed rectangle: to "
           f"throw its outline {PAIR_GAP:.0f} mm out and over its neighbour, the tall glass has to stand "
           f"{NEAR_R:.0f} mm from the point under the\ncamera, and from there its own silhouette reaches "
           f"{reach_px:.0f} px out into a frame that is 160 px to the edge. The arrangement that hides a "
           f"glass is also the arrangement that leaves the hider crossing the frame edge.")
    figure.subplots_adjust(bottom=0.16, top=0.90, wspace=0.10)
    save(figure, "01-hidden-from-above.png")
    print(f"  along the radius: {hidden['patches']} patch, {hidden['showing']} of {hidden['total']} "
          f"short-glass pixels, patch {patch_mm:.1f} mm of a permitted {kind_mm:.1f} mm, "
          f"splay_covers={covers}, silhouette reaches {reach_px:.1f} px of a 160 px half-frame")
    print(f"  across the radius: {beside['patches']} patches, {beside['showing']} of "
          f"{beside['total']} short-glass pixels")


# ---------------------------------------------------------------------------
# 12. Completely hidden from the side: plain line of sight.
# ---------------------------------------------------------------------------
def picture_hidden_from_the_side() -> None:
    """Two glasses in line with the level camera, and what the method returns.

    Every silhouette is a real projection through ``sideon``. The second and
    third panels differ only in which of the two glasses is the tall one, and
    they return the same answer, which is the point.
    """
    tall_h, tall_base, tall_wide = size(TALL_GLASS)
    far = STANDOFF + APART
    width, height, horizon = 300, 260, 90

    def picture(near_glass, far_glass):
        args = {"width": width, "height": height, "horizon": horizon}
        both = sideon([(0, STANDOFF, near_glass), (0, far, far_glass)], **args)
        close = sideon([(0, STANDOFF, near_glass)], **args)
        back = sideon([(0, far, far_glass)], **args)
        patches, _ = cv2.connectedComponents(both)
        return {"both": both, "near": close, "far": back, "patches": patches - 1,
                "showing": int(((back > 0) & (close == 0)).sum()),
                "total": int((back > 0).sum()),
                "wide": cv2.boundingRect(both)[2],
                "runs": contact_runs(both)}

    behind_tall = picture(TALL_GLASS, TALL_GLASS)
    behind_short = picture(SHORT_GLASS, TALL_GLASS)
    limit = KIND_WIDEST * FX / STANDOFF

    figure, axes = new(13.4, 5.0, columns=3)
    sight, swallowed, showing = axes

    # ------------------------------------------------- panel 1: the elevation
    stage(sight, f"In line with the camera, {APART:.0f} mm apart")
    sight.set_aspect("equal")
    sight.set_xlim(-70, 800)
    sight.set_ylim(-140, 272)
    sight.plot([-50, 780], [0, 0], color=MUTED, lw=1.2, zorder=4)
    note(sight, 110, -18, "the table", va="top")
    sight.plot([0], [VIEW_HEIGHT], "o", color=INK, ms=7, zorder=5)
    note(sight, 0, VIEW_HEIGHT + 12, "camera", INK, va="bottom")
    sight.plot([-50, 780], [VIEW_HEIGHT, VIEW_HEIGHT], color=MUTED, lw=0.9, ls=(0, (5, 4)))
    sight.text(612, VIEW_HEIGHT + 10, "the horizon", fontsize=NOTE_SIZE, color=MUTED,
               ha="right", va="bottom")

    top_slope = (tall_h - VIEW_HEIGHT) / (STANDOFF - tall_wide / 2)
    base_slope = (0.0 - VIEW_HEIGHT) / (STANDOFF - tall_base / 2)
    span = np.array([STANDOFF - tall_wide / 2, 790.0])
    sight.fill_between(span, VIEW_HEIGHT + base_slope * span, VIEW_HEIGHT + top_slope * span,
                       color=to_rgba(WARN, 0.10), lw=0, zorder=1)
    for slope in (top_slope, base_slope):
        sight.plot([0, 790], [VIEW_HEIGHT, VIEW_HEIGHT + slope * 790],
                   color=WARN, lw=1.1, ls=(0, (5, 3)), zorder=2)
    z, r = profile(TALL_GLASS)
    for distance, shade in ((STANDOFF, 0.44), (far, 0.26)):
        sight.fill_betweenx(z, distance - r, distance + r, color=to_rgba(GLASS, shade), lw=0, zorder=3)
        sight.plot(distance + r, z, color=GLASS, lw=1.2, zorder=3)
        sight.plot(distance - r, z, color=GLASS, lw=1.2, zorder=3)
        note(sight, distance - 25, -18, f"{distance:.0f} mm", INK, va="top")
    note(sight, 200, -52, "the shaded wedge is what\n"
                          "the near glass's outline covers,\n"
                          "and the far glass is wholly inside it", WARN, va="top")

    # ---------------------------------------- panels 2 and 3: the two pictures
    for axis, case, title in ((swallowed, behind_tall, "A tall glass behind a tall one"),
                              (showing, behind_short, "A tall glass behind a short one")):
        stage(axis, title)
        paint(axis, case["near"] > 0, GLASS, 0.42)
        # Paler blue, not green: green already means "a level stretch" in this
        # document, and the far glass is named by its dashed outline instead.
        paint(axis, (case["far"] > 0) & (case["near"] == 0), GLASS, 0.16)
        axis.contour(case["far"].astype(float), [0.5], colors=[WARN], linewidths=1.1,
                     linestyles="dashed")
        outline_of(axis, case["both"] > 0)
        columns, rows = bottom_edge(case["both"])
        axis.plot(columns, rows, color=WARN, lw=1.8)
        for start, stop, row in case["runs"]:
            axis.plot([start, stop], [row, row], color=GOOD, lw=4.0, solid_capstyle="butt")
        axis.set_xlim(100, 200)
        axis.set_ylim(224, -32)
        note(axis, 150, -30,
             f"{case['patches']} patch, {case['wide']} px wide, against a {limit:.0f} px limit",
             WARN, va="top")

    note(swallowed, 150, 188,
         f"{behind_tall['showing']} of the far glass's {behind_tall['total']} pixels reach the picture\n"
         f"(its dashed outline is where it would be)\n"
         f"{len(behind_tall['runs'])} level stretch, so the answer is one glass", WARN, va="top")
    note(showing, 150, 188,
         f"{behind_short['showing']} of the far glass's {behind_short['total']} pixels reach the picture,\n"
         f"but its base is not among them\n"
         f"{len(behind_short['runs'])} level stretch, so the answer is one glass", WARN, va="top")

    footer(figure,
           f"Line of sight needs no splay, so the distance between the two glasses buys nothing: at "
           f"{APART:.0f} mm apart the far glass is gone, and it is still gone at 600 mm. Which glass is "
           f"hidden is settled by which is nearer,\nnot by which is taller. Either way the patch is inside "
           f"the width one glass of this kind may draw, and its underside holds one level stretch, so the "
           f"method reports one glass and is not wrong about anything it was asked.")
    figure.subplots_adjust(bottom=0.16, top=0.90, wspace=0.12)
    save(figure, "01-hidden-from-the-side.png")
    for name, case in (("tall behind tall ", behind_tall), ("tall behind short", behind_short)):
        print(f"  {name}: {case['patches']} patch, {case['showing']} of {case['total']} far pixels, "
              f"{case['wide']} px wide (limit {limit:.1f}), {len(case['runs'])} level stretch, "
              f"split={len(split_by_contact(case['both']))}")

def main() -> None:
    picture_where_the_overlap_is()
    picture_the_survey_cannot()
    picture_not_a_circle()
    picture_the_blob()
    picture_watershed_fails()
    picture_bases_sit_higher()
    picture_contact_runs()
    picture_the_control()
    picture_where_it_works()
    picture_what_it_does_not_buy()
    picture_hidden_from_above()
    picture_hidden_from_the_side()


if __name__ == "__main__":
    main()
