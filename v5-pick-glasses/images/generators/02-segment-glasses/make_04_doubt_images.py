"""Pictures for solution 4 — learned doubt steers the next picture.

Ten diagrams, each carrying one point:

1. the three cases a doubt number has to tell apart, and the one that matters
2. wrong is not the same thing as unusual
3. the five ways to get a doubt number, and what each costs
4. the ordering: geometry generates and vetoes, the model only sorts
5. the loop, drawn as a loop, with the budget as the way out
6. the same seven viewpoints ordered by the rule and by the model
7. what a calibration check looks like, and what a bad one looks like
8. where the seconds go, and what the cap on looks is for
9. how a glass goes missing from a picture taken straight down
10. how a glass goes missing from a picture taken level

The last two draw silhouettes rather than bars, and every one of those
silhouettes is a real projection of one of the project's own glass outlines,
taken from ``work_cell.glasses.shapes`` through the cell's own camera. A
standing glass is a circle only in its footprint, which neither of the cell's
two camera poses ever sees straight on, and drawing it as one is what the first
version of these two pictures got wrong.

Run from the project root:

    pixi run python images/generators/02-segment-glasses/make_04_images.py
"""

from __future__ import annotations

import math
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
    PAPER,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
    splay_covers,
    splay_patch,
    splay_width,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import KIND_RANGES, family  # noqa: E402

# ---------------------------------------------------------------------------
# Small drawing helpers. Nothing here knows anything about the cell.



STANDOFF_MM = 380.0
FX = 277.1
GAP_MM = 155.0
SEPARATION_THETA = 120.0  # the direction the two glasses lie along, relative to the radial line
KEPT = [75.0, 90.0, 105.0, 120.0, -75.0, -90.0, -105.0]
DROPPED = [(135.0, "sight line"), (-120.0, "sight line"), (-135.0, "no IK")]
SURVEY_H = 450.0            # mm above the table; SURVEY_HEIGHT
VIEW_HEIGHT = 120.0         # mm above the table; MEASURE_VIEW_HEIGHT
FRAME_W, FRAME_H = 320, 240
HALF_X = SURVEY_H * (FRAME_W / 2) / FX   # how much bare table one survey picture reaches
HALF_Y = SURVEY_H * (FRAME_H / 2) / FX
APART = 150.0               # mm between centres; MIN_SEPARATION
BEHIND = 300.0              # mm further from the camera the far glass stands
CAST = [outline for outline, _ in family("tapered_glass", 12, 3)]
TALL, SHORT, MIDDLING = CAST[4], CAST[2], CAST[1]

def _tint(colour: str, alpha: float):
    return to_rgba(colour, alpha)


def _frame(axis, xlim, ylim) -> None:
    axis.set_xlim(*xlim)
    axis.set_ylim(*ylim)
    bare(axis)


def _title(axis, text: str, colour: str = INK, size: float = TITLE_SIZE) -> None:
    axis.set_title(text, fontsize=size, color=colour, pad=9)


def _box(
    axis,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    edge: str = INK,
    face: str = PAPER,
    size: float = NOTE_SIZE,
    ink: str | None = None,
    align: str = "center",
    lw: float = 1.1,
) -> None:
    """A rounded box with text in it, positioned by its bottom-left corner."""
    axis.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.04,rounding_size=0.14",
            linewidth=lw,
            edgecolor=edge,
            facecolor=face,
        )
    )
    tx = x + width / 2 if align == "center" else x + 0.22
    axis.text(
        tx,
        y + height / 2,
        text,
        ha=align,
        va="center",
        fontsize=size,
        color=ink or INK,
        linespacing=1.5,
    )


def _arrow(axis, start, end, colour: str = INK, lw: float = 1.2, style: str = "-") -> None:
    axis.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "color": colour,
            "linewidth": lw,
            "linestyle": style,
            "shrinkA": 0,
            "shrinkB": 0,
            "mutation_scale": 13,
        },
    )


def _glass(axis, cx: float, base: float, height: float, bottom: float, top: float,
           colour: str = GLASS, alpha: float = 0.20, lw: float = 1.5) -> None:
    """A tapered silhouette standing on a table line, in panel units."""
    points = [
        (cx - bottom / 2, base),
        (cx - top / 2, base + height),
        (cx + top / 2, base + height),
        (cx + bottom / 2, base),
    ]
    axis.add_patch(
        Polygon(points, closed=False, facecolor=_tint(colour, alpha), edgecolor=colour, linewidth=lw)
    )


def _extent(axis, x0: float, x1: float, y: float, label: str, colour: str,
            beside: bool = False) -> None:
    """A bar under the picture saying how wide one reported object came out."""
    axis.plot([x0, x1], [y, y], color=colour, linewidth=2.6, solid_capstyle="butt")
    for x in (x0, x1):
        axis.plot([x, x], [y - 0.17, y + 0.17], color=colour, linewidth=1.6)
    if beside:
        axis.text(x1 + 0.25, y, label, ha="left", va="center", fontsize=NOTE_SIZE, color=colour)
    else:
        axis.text((x0 + x1) / 2, y - 0.5, label, ha="center", va="top", fontsize=NOTE_SIZE,
                  color=colour, linespacing=1.4)


# ---------------------------------------------------------------------------
# 1. Confident and right, unsure and right, confident and wrong.


def _apparent_gap_px(theta_deg: float) -> float:
    """How far apart the two glasses land in the picture, from a standoff at this angle."""
    across = abs(math.sin(math.radians(theta_deg - SEPARATION_THETA)))
    return GAP_MM * FX / STANDOFF_MM * across


def _camera_range_mm(theta_deg: float, cluster_mm: float = 530.0) -> float:
    return math.sqrt(
        cluster_mm**2 + STANDOFF_MM**2 + 2 * cluster_mm * STANDOFF_MM * math.cos(math.radians(theta_deg))
    )


def _unit(theta_deg: float) -> tuple[float, float]:
    """The standoff direction, with the line out from the base drawn as straight up."""
    rad = math.radians(theta_deg)
    return math.sin(rad), math.cos(rad)


def _mm(outline) -> tuple[np.ndarray, np.ndarray]:
    """One glass's outline as heights and radii in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def _size(outline) -> tuple[float, float]:
    """How tall the glass is and how wide across its widest part, in millimetres."""
    z, r = _mm(outline)
    return float(z.max()), float(r.max() * 2.0)


def _splay(outline, centre, nadir=(0.0, 0.0), slices: int = 48):
    """The stack of circles a standing glass draws in a picture taken straight down.

    The slice at height z is imaged as if it were scaled about the point below
    the camera by SURVEY_H / (SURVEY_H - z), because that slice is that much
    nearer the lens than the table is. Returned in the shape diagram_style's
    splay_covers, splay_patch and splay_width expect: millimetres of table,
    measured from the nadir.
    """
    z, r = _mm(outline)
    index = np.linspace(0, len(z) - 1, slices).astype(int)
    offset = np.asarray(centre, dtype=float) - np.asarray(nadir, dtype=float)
    return [
        (offset * SURVEY_H / (SURVEY_H - z[i]), r[i] * SURVEY_H / (SURVEY_H - z[i]))
        for i in index
    ]


def _covers(big, small) -> bool:
    """splay_covers, done with arrays so that a sweep of every pair is affordable.

    Checked against diagram_style's own version on the pair the picture draws,
    because a faster test that disagrees with the house one is worse than no
    test at all.
    """
    centres = np.array([c for c, _ in big])
    radii = np.array([r for _, r in big])
    angles = np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False)
    ring = np.stack([np.cos(angles), np.sin(angles)], axis=1)
    for c, r in small:
        points = np.asarray(c) + r * ring
        gaps = np.hypot(*(points[:, None, :] - centres[None, :, :]).T).T
        if not (gaps <= radii[None, :] + 1e-9).any(axis=1).all():
            return False
    return True


def _radial_span(circles) -> tuple[float, float, float]:
    """How far in, how far out, and how wide an angle a splayed silhouette covers."""
    inner = min(float(np.hypot(*c)) - r for c, r in circles)
    outer = max(float(np.hypot(*c)) + r for c, r in circles)
    half_angle = 0.0
    for c, r in circles:
        distance = float(np.hypot(*c))
        half_angle = max(half_angle, math.degrees(math.asin(min(1.0, r / max(distance, r)))))
    return max(inner, 0.0), outer, half_angle


def _first_covering_distance(hider, hidden, step: float = 5.0, furthest: float = 560.0):
    """How far out the hider has to stand before it covers the other one whole."""
    distance = 60.0
    while distance <= furthest:
        if _covers(_splay(hider, (distance, 0.0)), _splay(hidden, (distance + APART, 0.0))):
            return distance
        distance += step
    return None


def _level_mask(glasses, horizon: float) -> np.ndarray:
    """The mask a level picture from VIEW_HEIGHT returns, for glasses on the table.

    ``glasses`` are (across, along, outline) in millimetres: across the frame,
    and away from the lens. Each horizontal circle of the outline is projected
    as what it really is — an ellipse, wider than it is deep, and lower in the
    frame on its near side than on its far side — so the silhouette is the union
    of those ellipses rather than a stack of flat lines.
    """
    mask = np.zeros((FRAME_H, FRAME_W), np.uint8)
    centre_column = FRAME_W / 2.0
    for across, along, outline in glasses:
        z, r = _mm(outline)
        for height, radius in zip(z, r, strict=True):
            if radius <= 0.0 or radius >= along:
                continue
            half_width = FX * radius / math.sqrt(along**2 - radius**2)
            near = horizon - FX * (height - VIEW_HEIGHT) / (along - radius)
            far = horizon - FX * (height - VIEW_HEIGHT) / (along + radius)
            cv2.ellipse(
                mask,
                (int(round(centre_column + FX * across / along)), int(round((near + far) / 2.0))),
                (max(1, int(round(half_width))), max(1, int(round(abs(near - far) / 2.0)))),
                0, 0, 360, 255, -1,
            )
    return mask


def _paint(axis, mask: np.ndarray, colour: str, alpha: float = 1.0) -> None:
    """Show a mask as one flat colour over the paper, at the camera's own size."""
    rgba = np.zeros((*mask.shape, 4), dtype=float)
    rgba[mask > 0] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest")


def hidden_from_above() -> None:
    """One glass swallowing another in a picture taken straight down.

    The left panel is the failure and the right panel is what the arithmetic can
    still say about it. Both are drawn in millimetres of table measured from the
    point directly below the camera, because that is the point splay is radial
    about.
    """
    tall_h, tall_w = _size(TALL)
    short_h, short_w = _size(SHORT)
    k_tall = SURVEY_H / (SURVEY_H - tall_h)
    k_short = SURVEY_H / (SURVEY_H - short_h)

    hider_at = _first_covering_distance(TALL, SHORT)
    assert hider_at is not None, "this pair never covers, so the picture has nothing to show"
    hidden_at = hider_at + APART

    hider = _splay(TALL, (hider_at, 0.0))
    hidden = _splay(SHORT, (hidden_at, 0.0))
    beside = _splay(SHORT, (hider_at, APART))
    assert _covers(hider, hidden) == splay_covers(hider, hidden)
    covered_across = splay_covers(hider, beside)
    patch_mm = splay_width(hider)
    inner, outer, half_angle = _radial_span(hider)

    pairs = [(i, j) for i in range(len(CAST)) for j in range(len(CAST)) if i != j]
    covering = [
        (i, j) for i, j in pairs if _first_covering_distance(CAST[i], CAST[j], step=10.0)
    ]
    shorter_hidden = all(_size(CAST[j])[0] < _size(CAST[i])[0] for i, j in covering)

    smallest_footprint = KIND_RANGES["tapered_glass"]["rim_diameter"][0] * 1000.0
    shortest = KIND_RANGES["tapered_glass"]["height"][0] * 1000.0
    off_frame_beyond = HALF_X * (SURVEY_H - shortest) / SURVEY_H

    print(
        f"  hidden from above: a {tall_h:.0f} mm glass covers a {short_h:.0f} mm one whole once "
        f"it stands {hider_at:.0f} mm from the nadir, putting the short one {hidden_at:.0f} mm out"
    )
    print(
        f"    splay factors {k_tall:.2f} and {k_short:.2f}; the covering patch is "
        f"{patch_mm:.0f} mm long and spans {inner:.0f} to {outer:.0f} mm from the nadir"
    )
    print(f"    the same pair turned across the radius: covered={covered_across}")
    print(
        f"    {len(covering)} of {len(pairs)} ordered pairs can cover at all; the hidden one is "
        f"always the shorter: {shorter_hidden}"
    )
    print(
        f"    one survey picture reaches {HALF_X:.0f} mm of bare table sideways and "
        f"{HALF_Y:.0f} mm the other way; a {shortest:.0f} mm glass is thrown past that edge "
        f"beyond {off_frame_beyond:.0f} mm from the nadir"
    )

    figure, (left, right) = new(13.8, 5.3, columns=2)
    for axis in (left, right):
        bare(axis)
        axis.set_aspect("equal")
        axis.set_anchor("N")
        axis.set_xlim(-330, 700)
        axis.set_ylim(-300, 400)
        axis.add_patch(
            Rectangle((-HALF_X, -HALF_Y), 2 * HALF_X, 2 * HALF_Y, facecolor="none",
                      edgecolor=MUTED, linewidth=1.0, linestyle="--", zorder=5)
        )
        axis.plot([0], [0], marker="x", markersize=8, color=INK, markeredgewidth=1.8, zorder=9)
        axis.text(-16, -16, "the point under the camera", ha="right", va="top",
                  fontsize=NOTE_SIZE, color=INK)
        axis.text(-HALF_X + 10, -HALF_Y + 10, "the table this one picture reaches",
                  fontsize=NOTE_SIZE, color=MUTED, va="bottom")

    # ------------------------------------------------------------- the failure
    _title(left, "along a radius: the short glass is swallowed", colour=WARN)
    splay_patch(left, hider, colour=GLASS, alpha=0.30, zorder=3)
    splay_patch(left, hidden, colour=WARN, alpha=0.75, zorder=4)
    for centre, width, colour in ((hider_at, tall_w, INK), (hidden_at, short_w, WARN)):
        left.add_patch(
            Circle((centre, 0.0), width / 2.0, facecolor="none", edgecolor=colour,
                   linewidth=1.3, linestyle=":", zorder=6)
        )
        left.plot([centre], [0.0], marker=".", markersize=4, color=colour, zorder=7)
    left.annotate(
        "", xy=(hidden_at, -105), xytext=(hider_at, -105),
        arrowprops={"arrowstyle": "<->", "color": INK, "linewidth": 1.2},
    )
    left.text(
        hider_at + 12, -128,
        f"where the two glasses really stand:\n{APART:.0f} mm apart, the closest two\n"
        "glasses in this problem ever stand",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK, linespacing=1.6,
    )
    left.text(
        -320, 395,
        f"Splay is radial, and it grows with height.\nThe rim of the {tall_h:.0f} mm glass is "
        f"drawn {k_tall:.2f}\ntimes further out than it stands, and the\n"
        f"{short_h:.0f} mm glass only {k_short:.2f} times.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=GLASS, linespacing=1.6,
    )
    left.annotate(
        f"the {short_h:.0f} mm glass's pixels\nwould land here, every one\n"
        "of them inside the tall glass's\noutline: it is in no picture",
        xy=(hidden_at * k_short, 58), xytext=(690, 395), fontsize=NOTE_SIZE, color=WARN,
        ha="right", va="top", linespacing=1.6,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )

    # ---------------------------------------------------- what can still be said
    _title(right, "what the arithmetic can still say: which table went unsearched",
           colour=GOOD)
    for x0, y0, width, height in (
        (-330, HALF_Y, 1030, 400 - HALF_Y),
        (-330, -300, 1030, 300 - HALF_Y),
        (-330, -HALF_Y, 330 - HALF_X, 2 * HALF_Y),
        (HALF_X, -HALF_Y, 700 - HALF_X, 2 * HALF_Y),
    ):
        right.add_patch(
            Rectangle((x0, y0), width, height, facecolor=to_rgba(GOOD, 0.11), edgecolor="none",
                      zorder=1)
        )
    right.add_patch(
        Wedge((0.0, 0.0), outer, -half_angle, half_angle, width=outer - inner,
              facecolor=to_rgba(GOOD, 0.30), edgecolor=GOOD, linewidth=1.1, zorder=2)
    )
    splay_patch(right, hider, colour=GLASS, alpha=0.22, zorder=3)
    right.add_patch(
        Circle((hidden_at, 0.0), short_w / 2.0, facecolor=to_rgba(WARN, 0.40), edgecolor=WARN,
               linewidth=1.3, zorder=6)
    )
    right.add_patch(
        Circle((360.0, 285.0), smallest_footprint / 2.0, facecolor="none", edgecolor=INK,
               linewidth=1.3, zorder=6)
    )
    right.text(
        360.0 + smallest_footprint / 2.0 + 14, 285.0,
        f"the smallest footprint this kind\nallows, {smallest_footprint:.0f} mm across. A patch "
        "of\nunsearched table narrower\nthan this one is dropped.",
        ha="left", va="center", fontsize=NOTE_SIZE, color=INK, linespacing=1.6,
    )
    right.text(
        690, 108, "the table the tall glass's\nown outline covers", ha="right", va="bottom",
        fontsize=NOTE_SIZE, color=GOOD, linespacing=1.5,
    )
    right.text(-320, 395, "everything shaded is table this picture could not have seen:\n"
                          "outside the frame, or underneath a taller glass's outline",
               ha="left", va="top", fontsize=NOTE_SIZE, color=GOOD, linespacing=1.6)
    right.annotate(
        "the glass that was really there.\nIt falls in both, which is why\n"
        "the question asked is not\n“was it hidden?” but “could I\n"
        "have seen it at all?”",
        xy=(hidden_at + 10, -short_w / 2.0 - 6), xytext=(690, -120), fontsize=NOTE_SIZE,
        color=WARN, ha="right", va="top", linespacing=1.6,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )

    figure.subplots_adjust(bottom=0.22, wspace=0.05)
    figure.text(
        0.5, 0.02,
        f"Of the {len(pairs)} ordered pairs these twelve drawn glasses make, {len(covering)} can "
        f"swallow the other whole at the guaranteed {APART:.0f} mm gap, and the hidden one is the "
        f"shorter every time. The nearest in is the pair\ndrawn here, and it still needs the hider "
        f"{hider_at:.0f} mm out from the point below the camera, which puts the hidden glass "
        f"{hidden_at:.0f} mm out — past the {HALF_X:.0f} mm of bare table the picture reaches. "
        f"So covering never takes\naway a glass the frame would have kept, the two causes arrive "
        f"together, and one sum answers both of them: which table could not have been seen, in "
        f"patches wide enough to hold a glass.",
        ha="center", fontsize=NOTE_SIZE, color=INK, linespacing=1.6,
    )
    save(figure, "04-hidden-from-above.png")


def hidden_from_the_side() -> None:
    """A far glass behind a near one in a level picture, and the mask it leaves.

    The left panel is the arrangement seen from above. The middle and right
    panels are the masks themselves, at the camera's own 320 by 240, with and
    without the far glass standing on the table.
    """
    near_h, near_w = _size(TALL)
    far_h, far_w = _size(SHORT)
    middling_h, _ = _size(MIDDLING)
    horizon = FRAME_H * 0.34

    near_only = _level_mask([(0.0, STANDOFF_MM, TALL)], horizon)
    far_only = _level_mask([(0.0, STANDOFF_MM + BEHIND, SHORT)], horizon)
    both = _level_mask([(0.0, STANDOFF_MM + BEHIND, SHORT), (0.0, STANDOFF_MM, TALL)], horizon)
    surviving = int(((far_only > 0) & (near_only == 0)).sum())
    differ = int((both != near_only).sum())

    def survives(near, far, gap=BEHIND) -> int:
        blocker = _level_mask([(0.0, STANDOFF_MM, near)], horizon)
        behind = _level_mask([(0.0, STANDOFF_MM + gap, far)], horizon)
        return int(((behind > 0) & (blocker == 0)).sum())

    pairs = [(i, j) for i in range(len(CAST)) for j in range(len(CAST)) if i != j]
    hidden_pairs = [(i, j) for i, j in pairs if survives(CAST[i], CAST[j]) == 0]
    surprise = survives(MIDDLING, TALL)
    sweep = [(gap, survives(TALL, SHORT, gap)) for gap in (APART, 200.0, 250.0, BEHIND, 480.0)]

    print(
        f"  hidden from the side: a {far_h:.0f} mm glass {BEHIND:.0f} mm behind a {near_h:.0f} mm "
        f"one would have lit {int((far_only > 0).sum())} pixels on its own, and lights {surviving}"
    )
    print(
        f"    the near glass alone lights {int((near_only > 0).sum())} pixels, and the two masks "
        f"differ in {differ} of {FRAME_W * FRAME_H}"
    )
    print(
        f"    {len(hidden_pairs)} of {len(pairs)} ordered pairs leave the far glass with no "
        f"pixels at all"
    )
    print(
        f"    a {middling_h:.0f} mm glass in front of a {near_h:.0f} mm one: "
        f"{surprise} pixels of the taller, further glass survive"
    )
    for gap, left_over in sweep:
        print(f"    {gap:.0f} mm apart: {left_over} pixels of the far glass survive")

    figure, (plan, with_far, without) = new(13.8, 4.2, columns=3)

    # -------------------------------------------------- the arrangement, in plan
    bare(plan)
    plan.set_aspect("equal")
    plan.set_anchor("N")
    plan.set_xlim(-70, 870)
    plan.set_ylim(-330, 210)
    _title(plan, "the arrangement, seen from above", colour=INK, size=LABEL_SIZE)
    half_angle = math.degrees(math.asin(near_w / 2.0 / STANDOFF_MM))
    reach = 870.0
    edge = math.tan(math.radians(half_angle)) * reach
    plan.add_patch(
        Polygon([(0.0, 0.0), (reach, edge), (reach, -edge)], closed=True,
                facecolor=to_rgba(MUTED, 0.20), edgecolor="none", zorder=1)
    )
    for sign in (1, -1):
        plan.plot([0, reach], [0, sign * edge], color=MUTED, linewidth=0.9, linestyle="--",
                  zorder=2)
    plan.plot([0], [0], marker="o", markersize=8, color=INK, zorder=9)
    plan.text(-60, -34, f"the camera,\n{VIEW_HEIGHT:.0f} mm up,\nlooking level", ha="left",
              va="top", fontsize=NOTE_SIZE, color=INK, linespacing=1.5)
    plan.add_patch(
        Circle((STANDOFF_MM, 0.0), near_w / 2.0, facecolor=to_rgba(GLASS, 0.45), edgecolor=GLASS,
               linewidth=1.3, zorder=6)
    )
    plan.add_patch(
        Circle((STANDOFF_MM + BEHIND, 0.0), far_w / 2.0, facecolor=to_rgba(WARN, 0.40),
               edgecolor=WARN, linewidth=1.3, zorder=6)
    )
    plan.text(STANDOFF_MM, -95, f"the near glass,\n{near_h:.0f} mm tall", ha="center", va="top",
              fontsize=NOTE_SIZE, color=GLASS, linespacing=1.5)
    plan.text(STANDOFF_MM + BEHIND, -95, f"the far glass,\n{far_h:.0f} mm tall", ha="center",
              va="top", fontsize=NOTE_SIZE, color=WARN, linespacing=1.5)
    for start, end, label in (
        (0.0, STANDOFF_MM, f"{STANDOFF_MM:.0f} mm"),
        (STANDOFF_MM, STANDOFF_MM + BEHIND, f"{BEHIND:.0f} mm"),
    ):
        plan.annotate("", xy=(end, 150), xytext=(start, 150),
                      arrowprops={"arrowstyle": "<->", "color": INK, "linewidth": 1.1})
        plan.text((start + end) / 2.0, 160, label, ha="center", va="bottom",
                  fontsize=NOTE_SIZE, color=INK)
    plan.text(-60, -220, "No splay is needed here. The near glass simply\n"
                         "stands in the way, and the shaded wedge is what\nit stands in the way of.",
              ha="left", va="top", fontsize=NOTE_SIZE, color=INK, linespacing=1.6)

    # -------------------------------------------------------------- the masks
    for axis, title, colour in (
        (with_far, "the mask, with both glasses on the table", WARN),
        (without, "and with the far glass taken off the table", GOOD),
    ):
        bare(axis)
        axis.set_anchor("N")
        _title(axis, title, colour=colour, size=LABEL_SIZE)
        axis.add_patch(
            Rectangle((-0.5, -0.5), FRAME_W, FRAME_H, facecolor="none", edgecolor=MUTED,
                      linewidth=1.0)
        )
        axis.set_xlim(-0.5, FRAME_W - 0.5)
        axis.set_ylim(FRAME_H - 0.5, -0.5)

    _paint(with_far, both, GLASS, 0.55)
    with_far.contour((far_only > 0).astype(float), [0.5], colors=[WARN], linewidths=1.3)
    with_far.annotate(
        f"the far glass is inside this line.\nOn its own it would light "
        f"{int((far_only > 0).sum())} pixels.\nHere it lights {surviving}.",
        xy=(FRAME_W / 2.0 + 20, horizon + 40), xytext=(FRAME_W - 10, FRAME_H - 10),
        fontsize=NOTE_SIZE, color=WARN, ha="right", va="bottom", linespacing=1.6,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )
    _paint(without, near_only, GLASS, 0.55)
    without.text(FRAME_W - 10, FRAME_H - 10,
                 f"{int((near_only > 0).sum())} pixels, and they are the\nsame pixels. The two "
                 f"masks differ\nin {differ} of {FRAME_W * FRAME_H}.",
                 fontsize=NOTE_SIZE, color=GOOD, ha="right", va="bottom", linespacing=1.6)

    figure.subplots_adjust(bottom=0.28, wspace=0.10)
    figure.text(
        0.5, 0.02,
        f"{len(hidden_pairs)} of the {len(pairs)} ordered pairs these twelve drawn glasses make "
        f"leave the far one with no pixels at all at this spacing, and standing the two further "
        f"apart makes it worse rather than better:\n"
        + ", ".join(f"{gap:.0f} mm apart leaves {left_over}" for gap, left_over in sweep[:4])
        + f" pixels of the far glass. Height decides much less than it does from above, because "
        f"the near glass is the\nmagnified one: a {middling_h:.0f} mm glass in front hides a "
        f"{near_h:.0f} mm one behind it completely. And the two masks above are the same mask, "
        f"which is the part that matters — one level\npicture carries no trace at all of what "
        f"it failed to show.",
        ha="center", fontsize=NOTE_SIZE, color=INK, linespacing=1.6,
    )
    save(figure, "04-hidden-from-the-side.png")


def main() -> None:
    hidden_from_above()
    hidden_from_the_side()


if __name__ == "__main__":
    main()
