"""Diagrams for solution 7 — a learned change-verifier.

Every glass drawn here is one the project's own code drew. Two sources, and
nothing else: ``family("tapered_glass", HOW_MANY, SEED)`` from
``work_cell.glasses.shapes`` for the measurements across the kind's range, and
``scene(seed)`` from ``problem-3-sim/bench.py`` for the crowded tables, because
that is the authoritative generator for this problem. No size in this file was
chosen to make a picture work.

A toppled glass is drawn as the real outline laid over, not as a rectangle. The
lean is a parameter, so the same arithmetic draws a glass upright, a glass at
the bench's own STANDING_TILT_DEG, and a glass flat on its wall. A tapered glass
lying down rests on one slant line of its own wall, so its axis is tilted, and
the tilt changes both the length it covers on the table and how tall it stands.

    pixi run python images/generators/problem-3/make_07_images.py
"""

from __future__ import annotations

import importlib.util
import math
import sys
import types
from pathlib import Path

import numpy as np
from diagram_style import (
    CAST,
    GLASS,
    GOOD,
    GRIP_ROOM,
    INK,
    JAW_TOP,
    LABEL_SIZE,
    LOWEST_GRIP,
    MU_HIGH,
    MU_LOW,
    MUTED,
    NOTE_SIZE,
    STURDY,
    TABLE_FRICTION,
    TIPPY,
    WARN,
    bare,
    base_width,
    glass_from_above,
    glass_from_the_side,
    has_room,
    new,
    push_arrow,
    pushable,
    save,
    tips,
    topple_height,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "work_cell"))

from work_cell.arm.dimensions import SURVEY_HEIGHT  # noqa: E402
from work_cell.glasses.shapes import KIND_RANGES, family  # noqa: E402


def _bench():
    """``problem-3-sim/bench.py``: the crowded tables, the jaw, and the real friction.

    Imported for ``scene`` and for its constants. None of the physics is touched
    here, so when MuJoCo is not installed a placeholder stands in for it just
    long enough to load the module.
    """
    sys.path.insert(0, str(ROOT / "problem-3-sim"))
    if importlib.util.find_spec("mujoco") is None:
        sys.modules["mujoco"] = types.ModuleType("mujoco")
    import bench

    return bench


BENCH = _bench()

KIND = "tapered_glass"
HOW_MANY = 400
SEED = 0

SURVEY_UP = SURVEY_HEIGHT * 1000.0       # mm above the table, looking straight down

# The jaw. The middle of it rides at LOWEST_GRIP; its top edge is 15 mm higher,
# and a tapered glass is wider higher up, so the top edge is where a tapered
# glass meets it and therefore the height it is really pushed at. Both numbers
# come from diagram_style, and the assertions below keep them in step with the
# bench they were copied from.
JAW_MIDDLE = LOWEST_GRIP

# The simulator's own friction between glass and table. Ground truth a run is
# scored against, never an input to any decision the arm makes.
TRUE_FRICTION = TABLE_FRICTION

assert JAW_MIDDLE == BENCH.PUSH_HEIGHT * 1000.0, "diagram_style and bench.py disagree on the jaw"
assert JAW_TOP == BENCH.JAW_TOP * 1000.0, "diagram_style and bench.py disagree on the jaw"
assert TRUE_FRICTION == BENCH.TABLE_FRICTION, "diagram_style and bench.py disagree on the friction"
assert GRIP_ROOM == BENCH.GRIP_ROOM * 1000.0, "diagram_style and bench.py disagree on the room"

# The project's own definition of toppled, from bench.py: a glass leaning
# further than this from upright has fallen over.
STANDING_TILT = BENCH.STANDING_TILT_DEG

# Tables from here up are the test set; the kind cycles with the seed, and
# tapered glasses come round one seed in four.
TAPERED_SEEDS = [s for s in range(BENCH.TEST_SEEDS, BENCH.TEST_SEEDS + 1200)
                 if BENCH.KINDS[s % len(BENCH.KINDS)] == KIND]
HOW_MANY_TABLES = 200

# The one table the outcome pictures are drawn on: the table holding the
# crowded glass of this kind whose topple the overhead view hides best.
DRAWN_TABLE = 11117
DRAWN_GLASS, DRAWN_NEIGHBOUR = 0, 4


# --------------------------------------------------------------------------- #
# The glass, in millimetres, standing, leaning and lying down.
# --------------------------------------------------------------------------- #

def profile(outline) -> tuple[np.ndarray, np.ndarray]:
    """Heights and radii of one outline, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def standing(outline) -> tuple[float, float, float]:
    """Height, widest diameter, base diameter — the three numbers used throughout."""
    z, r = profile(outline)
    return float(z.max()), float(2.0 * r.max()), float(2.0 * r[0])


def wall_angle(outline) -> float:
    """The angle between the glass's wall and its axis, in degrees.

    A tapered glass is a cone, and a cone laid on a flat table touches along one
    slant line of its surface. So the glass comes to rest leaning this much
    short of flat, and its axis is not level even when it is fully over.
    """
    z, r = profile(outline)
    return math.degrees(math.atan2(r[-1] - r[0], z[-1] - z[0]))


def topple_lean(outline) -> float:
    """How far from upright the glass leans once it is lying on its wall."""
    return 90.0 - wall_angle(outline)


def _slices(outline, lean_deg: float, fine: int = 4):
    """Every horizontal slice of the standing glass, after leaning it over.

    The glass pivots about the edge of its foot. Returns, for each slice, where
    its middle lands on the table, how far it reaches along the lean, and how
    wide it is across the lean.
    """
    z, r = profile(outline)
    # The stored outline has a few hundred samples. The ellipses below are thin
    # when the glass lies nearly level, so the union is walked on a finer set of
    # slices than that, or its edge comes out serrated.
    grid = np.linspace(z.min(), z.max(), fine * len(z))
    z, r = grid, np.interp(grid, z, r)
    lean = math.radians(lean_deg)
    foot = r[0]
    along = z * math.sin(lean) - foot * math.cos(lean)
    return along, r * math.cos(lean), r


def from_above(outline, lean_deg: float, samples: int = 900) -> np.ndarray:
    """The silhouette of the glass seen from straight above, leaning ``lean_deg``.

    Worked out rather than sketched. Every slice of a standing glass is a circle
    about the axis; once the axis leans, each circle projects onto the table as
    an ellipse, as wide as the circle across the lean and narrower along it. The
    silhouette is the union of those ellipses, so this walks a grid along the
    table and takes the widest ellipse reaching each point. At a lean of zero it
    returns the circle of the glass's widest slice, which is what it should.

    The frame is the table, with the edge of the foot the glass tips over at
    x = 0, so the middle of the standing glass sits at minus half its base. That
    is what makes the blob's middle comparable before and after.
    """
    middle, reach, wide = _slices(outline, lean_deg)
    x = np.linspace((middle - reach).min(), (middle + reach).max(), samples)
    half = np.zeros_like(x)
    for centre, thin, across in zip(middle, reach, wide, strict=True):
        if thin <= 0.0:
            half = np.maximum(half, np.where(np.isclose(x, centre), across, 0.0))
            continue
        offset = (x - centre) / thin
        lifted = across * np.sqrt(np.clip(1.0 - offset**2, 0.0, 1.0))
        half = np.maximum(half, np.where(np.abs(offset) <= 1.0, lifted, 0.0))
    return np.concatenate([np.column_stack([x, half]),
                           np.column_stack([x[::-1], -half[::-1]])])


def from_the_side(outline, lean_deg: float) -> np.ndarray:
    """The same glass seen level, leaning ``lean_deg``, as a closed polygon.

    The profile has two walls, one either side of the axis. The whole shape is
    turned about the edge of the foot it tips over, which is what lifts the base
    and, at full lean, lays one wall flat on the table.
    """
    z, r = profile(outline)
    foot = r[0]
    points = np.concatenate([np.column_stack([-r - foot, z]),
                             np.column_stack([r[::-1] - foot, z[::-1]])])
    lean = math.radians(lean_deg)
    turn = np.array([[math.cos(lean), -math.sin(lean)], [math.sin(lean), math.cos(lean)]])
    turned = points @ turn
    turned[:, 0] -= turned[:, 0].min()
    turned[:, 1] -= turned[:, 1].min()
    return turned


def measure(outline) -> dict[str, float]:
    """Everything the two views can measure about one glass, at every lean that matters."""
    height, widest, base = standing(outline)
    over = topple_lean(outline)
    out: dict[str, float] = {
        "height": height, "widest": widest, "base": base,
        "wall": wall_angle(outline), "topple_lean": over,
        "standing_area": float(math.pi * (widest / 2.0) ** 2),
        # How far out the overhead view throws each outline, from the cell's own
        # survey height. The widest part of a standing glass is its rim; the
        # widest part of a lying one is level with its tilted axis.
        "splay_standing": SURVEY_UP / (SURVEY_UP - height),
    }
    for name, lean in (("tilted", STANDING_TILT), ("over", over)):
        above = from_above(outline, lean)
        half = above[: len(above) // 2]
        side = from_the_side(outline, lean)
        on_table = side[side[:, 1] < 0.5]
        out[f"{name}_long"] = float(above[:, 0].max() - above[:, 0].min())
        out[f"{name}_short"] = float(2.0 * half[:, 1].max())
        out[f"{name}_area"] = float(np.trapezoid(2.0 * half[:, 1], half[:, 0]))
        out[f"{name}_top"] = float(side[:, 1].max())
        out[f"{name}_run"] = (float(on_table[:, 0].max() - on_table[:, 0].min())
                              if len(on_table) else 0.0)
        # Where the middle of the blob ends up, measured from where the glass
        # stood: the standing glass's middle is at minus half its base.
        out[f"{name}_jump"] = float(np.trapezoid(half[:, 0] * half[:, 1], half[:, 0])
                                    / np.trapezoid(half[:, 1], half[:, 0])) + base / 2.0
    out["splay_over"] = SURVEY_UP / (SURVEY_UP - out["over_top"] / 2.0)
    return out


FAMILY = [outline for outline, _ in family(KIND, HOW_MANY, SEED)]
MEASURED = [measure(outline) for outline in FAMILY]

# The three glasses the pictures follow, picked out of the family by a property
# rather than chosen: the one whose blob changes least when it goes over, the
# one whose blob changes most, and the middle one.
_ORDER = sorted(range(HOW_MANY), key=lambda i: MEASURED[i]["over_long"] - MEASURED[i]["widest"])
HARDEST, MIDDLING, EASIEST = _ORDER[0], _ORDER[HOW_MANY // 2], _ORDER[-1]


# --------------------------------------------------------------------------- #
# The crowded tables, from the bench's own generator.
# --------------------------------------------------------------------------- #

def table(seed: int) -> list[dict[str, float]]:
    """One of the bench's tables, in millimetres, with each glass's shortfall.

    The shortfall is how much closer a glass is to its worst neighbour than the
    room test allows. Positive means it cannot be gripped, and it is the
    distance a push has to make up. The room test is ``has_room`` from the
    bench, and it is asymmetric: what a glass needs depends on how wide its
    neighbour is, not on how wide it is.
    """
    glasses = []
    for glass in BENCH.scene(seed):
        glasses.append({
            "x": glass.position[0] * 1000.0, "y": glass.position[1] * 1000.0,
            "height": glass.outline.total_height * 1000.0,
            "widest": glass.outline.max_diameter * 1000.0,
            "base": 2.0 * float(glass.outline.radius[0]) * 1000.0,
            "outline": glass.outline,
        })
    for i, here in enumerate(glasses):
        others = [(g["x"], g["y"], g["widest"]) for j, g in enumerate(glasses) if j != i]
        here["room"] = has_room((here["x"], here["y"]), others)
        here["shortfall"] = max(GRIP_ROOM + width / 2.0
                                - float(np.hypot(here["x"] - ox, here["y"] - oy))
                                for ox, oy, width in others)
        here["binding"] = max(range(len(others)),
                              key=lambda k: others[k][2] / 2.0
                              - float(np.hypot(here["x"] - others[k][0], here["y"] - others[k][1])))
    return glasses


def every_shortfall() -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Every crowded glass on the first ``HOW_MANY_TABLES`` tapered test tables."""
    short, crowded, counts = [], [], []
    for seed in TAPERED_SEEDS[:HOW_MANY_TABLES]:
        glasses = table(seed)
        counts.append(len(glasses))
        crowded.append(sum(1 for g in glasses if not g["room"]))
        short += [g["shortfall"] for g in glasses if not g["room"]]
    return np.array(short), np.array(crowded), counts


# --------------------------------------------------------------------------- #
# Drawing helpers, local to this script.
# --------------------------------------------------------------------------- #

def stage(axis, title: str) -> None:
    bare(axis)
    axis.set_aspect("equal")
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)


def plot_frame(axis, title: str, xlabel: str, ylabel: str) -> None:
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)
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
    figure.text(0.5, 0.012, text, fontsize=NOTE_SIZE, color=INK, ha="center")


def span(axis, x_from, x_to, y, text, colour=INK, above=8.0) -> None:
    """A double-headed arrow across the picture with its measurement above it."""
    axis.annotate("", xy=(x_from, y), xytext=(x_to, y),
                  arrowprops={"arrowstyle": "<->", "color": colour, "lw": 1.0})
    axis.text((x_from + x_to) / 2.0, y + above, text,
              fontsize=NOTE_SIZE, color=colour, ha="center", va="bottom")


def tall_span(axis, x, y_from, y_to, text, colour=INK) -> None:
    """The same, upright, with its measurement to the right of it."""
    axis.annotate("", xy=(x, y_from), xytext=(x, y_to),
                  arrowprops={"arrowstyle": "<->", "color": colour, "lw": 1.0})
    axis.text(x + 6, (y_from + y_to) / 2.0, text,
              fontsize=NOTE_SIZE, color=colour, ha="left", va="center")


def lying_patch(axis, polygon, offset=(0.0, 0.0), colour=WARN, alpha=0.30, lw=1.4) -> np.ndarray:
    moved = np.asarray(polygon) + np.asarray(offset)
    axis.add_patch(Polygon(moved, closed=True, facecolor=to_rgba(colour, alpha),
                           edgecolor=colour, lw=lw, zorder=3))
    return moved


# --------------------------------------------------------------------------- #
# 1. The same glass, standing and toppled, from above.
# --------------------------------------------------------------------------- #

def picture_the_same_glass_twice() -> None:
    figure, axes = new(13.4, 6.3, columns=3)
    chosen = (HARDEST, MIDDLING, EASIEST)
    titles = ("The hardest of the four hundred",
              "The middle one",
              "The easiest of the four hundred")
    limit = max(MEASURED[i]["over_long"] for i in chosen) / 2.0 + 30.0
    height_limit = 186.0

    for axis, index, title in zip(axes, chosen, titles, strict=True):
        glass = MEASURED[index]
        stage(axis, title)
        axis.set_xlim(-limit, limit)
        axis.set_ylim(-height_limit, height_limit)

        rim = glass["widest"]
        top_row, bottom_row = rim / 2.0 + 22.0, -(rim / 2.0 + 22.0)
        glass_from_above(axis, (0.0, top_row), rim,
                         base_fraction=glass["base"] / rim,
                         colour=GLASS, alpha=0.32, lw=1.4)
        span(axis, -rim / 2.0, rim / 2.0, top_row + rim / 2.0 + 8.0,
             f"standing: {rim:.0f} mm, round", GLASS)

        lying = from_above(FAMILY[index], glass["topple_lean"])
        lying = lying_patch(axis, lying,
                            offset=(-(lying[:, 0].min() + lying[:, 0].max()) / 2.0, bottom_row))
        axis.annotate("", xy=(lying[:, 0].min(), bottom_row - rim / 2.0 - 10.0),
                      xytext=(lying[:, 0].max(), bottom_row - rim / 2.0 - 10.0),
                      arrowprops={"arrowstyle": "<->", "color": WARN, "lw": 1.0})
        note(axis, 0, bottom_row - rim / 2.0 - 17.0,
             f"toppled: {glass['over_long']:.0f} by {glass['over_short']:.0f} mm", WARN, va="top")

        grew = glass["over_long"] - rim
        note(axis, 0, -height_limit + 4,
             f"{glass['height']:.0f} mm tall, rim {rim:.0f} mm\n"
             f"the blob grows by {grew:.0f} mm in one direction",
             WARN if grew < 20.0 else INK, va="bottom")

    footer(figure,
           f"Three of the {HOW_MANY} glasses the spawner drew for this kind, picked out by how "
           "much the overhead blob changes when the glass goes over. Toppling stretches one "
           "extent and leaves the other alone, so the whole difference is the glass's own ratio "
           "of height to width — and this kind is allowed to be almost as wide as it is tall.")
    figure.subplots_adjust(bottom=0.075, top=0.95, wspace=0.05)
    save(figure, "07-the-same-glass-twice.png")


# --------------------------------------------------------------------------- #
# 2. Where in the kind's range the confusion is real.
# --------------------------------------------------------------------------- #

def picture_where_the_confusion_is_real() -> None:
    figure, axes = new(12.8, 5.2, columns=2)
    heights = np.array([m["height"] for m in MEASURED])
    widest = np.array([m["widest"] for m in MEASURED])
    long_extent = np.array([m["over_long"] for m in MEASURED])
    over_top = np.array([m["over_top"] for m in MEASURED])

    rim_from, rim_to = (v * 1000.0 for v in KIND_RANGES[KIND]["rim_diameter"])
    height_from, height_to = (v * 1000.0 for v in KIND_RANGES[KIND]["height"])
    passes = long_extent <= rim_to

    range_axis, top_axis = axes

    plot_frame(range_axis, "Which glasses of the kind hide a topple from above",
               "height standing, mm", "widest diameter, mm")
    range_axis.add_patch(Rectangle((height_from, rim_from), height_to - height_from,
                                   rim_to - rim_from, facecolor="none",
                                   edgecolor=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=1))
    range_axis.scatter(heights[~passes], widest[~passes], s=11, color=GOOD, alpha=0.5,
                       linewidths=0, zorder=3)
    range_axis.scatter(heights[passes], widest[passes], s=30, color=WARN, alpha=0.95,
                       linewidths=0, zorder=4)
    range_axis.set_xlim(height_from - 8, height_to + 8)
    range_axis.set_ylim(rim_from - 42, rim_to + 34)
    range_axis.text(height_from + 2, rim_to + 30,
                    "the dashed box is the whole range this kind is drawn from",
                    fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top")
    range_axis.text(height_to - 2, rim_from - 30,
                    "green: the blob gets visibly longer",
                    fontsize=NOTE_SIZE, color=GOOD, ha="right", va="bottom")
    range_axis.annotate(f"{passes.sum()} of {HOW_MANY}: toppled, the blob is still no longer\n"
                        f"than the {rim_to:.0f} mm a standing one is allowed to be",
                        xy=(heights[passes].max() + 3, widest[passes].min() - 1),
                        xytext=(height_from + 46, rim_from - 12),
                        fontsize=NOTE_SIZE, color=WARN, ha="left", va="top",
                        arrowprops={"arrowstyle": "-", "color": WARN, "lw": 0.8})

    plot_frame(top_axis, "And what happens to the tallest point",
               "height standing, mm", "tallest point after toppling, mm")
    drop = heights - over_top
    taller = drop <= 0.0
    top_axis.plot([height_from - 8, height_to + 8], [height_from - 8, height_to + 8],
                  color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=1)
    top_axis.scatter(heights[~taller], over_top[~taller], s=11, color=GOOD, alpha=0.5,
                     linewidths=0, zorder=3)
    top_axis.scatter(heights[taller], over_top[taller], s=30, color=WARN, alpha=0.95,
                     linewidths=0, zorder=4)
    top_axis.set_xlim(height_from - 8, height_to + 8)
    top_axis.set_ylim(0, height_to + 40)
    top_axis.text(height_to + 4, height_to + 4, "no change at all",
                  fontsize=NOTE_SIZE, color=MUTED, ha="right", va="bottom")
    top_axis.text(height_from + 2, height_to + 34,
                  f"the tallest point falls by {np.median(drop):.0f} mm for the middle glass\n"
                  f"of the kind, and by {drop.max():.0f} mm for the tallest",
                  fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    top_axis.annotate(f"for {taller.sum()} of {HOW_MANY} it goes up instead: a wide glass\n"
                      "lying down stands taller than a short one upright",
                      xy=(heights[taller].max() + 2, over_top[taller].min() - 2),
                      xytext=(height_from + 30, 16),
                      fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom",
                      arrowprops={"arrowstyle": "-", "color": WARN, "lw": 0.8})

    footer(figure,
           f"Every point is one of the {HOW_MANY} glasses drawn from "
           f'KIND_RANGES["{KIND}"], seed {SEED}. Red marks the glasses whose topple that '
           "overhead reading cannot report as anything out of the ordinary.")
    figure.subplots_adjust(bottom=0.19, wspace=0.24)
    save(figure, "07-where-the-confusion-is-real.png")


# --------------------------------------------------------------------------- #
# 3. The three outcomes, on one of the bench's own crowded tables.
# --------------------------------------------------------------------------- #

def picture_what_the_overhead_view_reports() -> None:
    figure, axes = new(13.4, 5.8, columns=3)
    glasses = table(DRAWN_TABLE)
    target, neighbour = glasses[DRAWN_GLASS], glasses[DRAWN_NEIGHBOUR]
    measured = measure(target["outline"])

    here = np.array([target["x"], target["y"]])
    there = np.array([neighbour["x"], neighbour["y"]])
    apart = float(np.linalg.norm(here - there))
    away = (here - there) / apart
    daylight = apart - (target["widest"] + neighbour["widest"]) / 2.0
    push = target["shortfall"]

    # The toppled glass, turned so that it falls the way the jaw was pushing.
    lean = math.atan2(away[1], away[0])
    turn = np.array([[math.cos(lean), math.sin(lean)], [-math.sin(lean), math.cos(lean)]])
    lying = (from_above(target["outline"], measured["topple_lean"])
             + [target["base"] / 2.0, 0.0]) @ turn + here

    drawn = np.vstack([
        lying,
        here + push * away + target["widest"] / 2.0 * np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]]),
        there + daylight * away + neighbour["widest"] / 2.0 * np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]]),
        there + neighbour["widest"] / 2.0 * np.array([[1, 1], [1, -1], [-1, 1], [-1, -1]]),
        [here - (target["widest"] / 2.0 + 34.0) * away],
    ])
    left, right = drawn[:, 0].min() - 10.0, drawn[:, 0].max() + 10.0
    high = drawn[:, 1].max() + 10.0
    # A band under the drawing for the three lines of readout, in the same units.
    band = (right - left) * 0.19
    low = drawn[:, 1].min() - band

    def frame(axis, title):
        stage(axis, title)
        axis.set_xlim(left, right)
        axis.set_ylim(low, high)
        axis.plot([left + 4, right - 4], [low + band * 0.96, low + band * 0.96],
                  color=MUTED, lw=0.8, alpha=0.5)

    def was(axis, at, width):
        axis.add_patch(Circle(tuple(at), width / 2.0, facecolor="none", edgecolor=MUTED,
                              lw=1.2, ls=(0, (4, 3)), zorder=2))

    def readout(axis, lines, colour):
        axis.text(left + 6, low + 4, lines, fontsize=NOTE_SIZE, color=colour,
                  ha="left", va="bottom", linespacing=1.7)

    intended, knocked, fallen = axes

    frame(intended, "Moved as intended")
    was(intended, here, target["widest"])
    glass_from_above(intended, tuple(here + push * away), target["widest"],
                     base_fraction=target["base"] / target["widest"],
                     colour=GOOD, alpha=0.30, lw=1.4)
    glass_from_above(intended, tuple(there), neighbour["widest"],
                     base_fraction=neighbour["base"] / neighbour["widest"],
                     colour=GLASS, alpha=0.22, lw=1.1)
    push_arrow(intended, tuple(here - (target["widest"] / 2.0 + 32.0) * away),
               tuple(here + (push - target["widest"] / 2.0 - 3.0) * away))
    note(intended, *(here - (target["widest"] / 2.0 + 6.0) * np.array([0.0, 1.0])),
         "the pushed glass", MUTED, va="top")
    intended.text(there[0] + neighbour["widest"] / 2.0 + 6.0, there[1], "its neighbour",
                  fontsize=NOTE_SIZE, color=MUTED, ha="left", va="center")
    readout(intended,
            f"the middle moved {push:.0f} mm, which is what was asked\n"
            f"the blob is still {target['widest']:.0f} mm measured either way\n"
            f"the tallest point is still {target['height']:.0f} mm", GOOD)

    frame(knocked, "The neighbour moved too")
    was(knocked, here, target["widest"])
    glass_from_above(knocked, tuple(here + push * away), target["widest"],
                     base_fraction=target["base"] / target["widest"],
                     colour=GLASS, alpha=0.30, lw=1.4)
    push_arrow(knocked, tuple(here - (target["widest"] / 2.0 + 32.0) * away),
               tuple(here + (push - target["widest"] / 2.0 - 3.0) * away))
    was(knocked, there, neighbour["widest"])
    glass_from_above(knocked, tuple(there + daylight * away), neighbour["widest"],
                     base_fraction=neighbour["base"] / neighbour["widest"],
                     colour=WARN, alpha=0.30, lw=1.4)
    push_arrow(knocked, tuple(there), tuple(there + daylight * away), colour=WARN, lw=1.2)
    readout(knocked,
            "the pushed glass reports the three numbers\n"
            f"on the left, and every one of them is right\n"
            f"the neighbour closed its {daylight:.0f} mm of daylight", WARN)

    frame(fallen, "Fallen over")
    was(fallen, here, target["widest"])
    lying_patch(fallen, lying)
    glass_from_above(fallen, tuple(there), neighbour["widest"],
                     base_fraction=neighbour["base"] / neighbour["widest"],
                     colour=GLASS, alpha=0.22, lw=1.1)
    push_arrow(fallen, tuple(here - (target["widest"] / 2.0 + 32.0) * away),
               tuple(here + (target["base"] / 2.0 - 4.0) * away))
    readout(fallen,
            f"the middle moved {measured['over_jump']:.0f} mm, "
            f"{measured['over_jump'] / push:.0f} times the push\n"
            f"the blob is now {measured['over_long']:.0f} by {measured['over_short']:.0f} mm\n"
            f"the tallest point is {measured['over_top']:.0f} mm, "
            f"{measured['over_top'] - measured['height']:.0f} mm higher", WARN)

    footer(figure,
           f"Table {DRAWN_TABLE} from the bench's own generator, drawn on the table rather than "
           f"in the picture. The pushed glass is {target['height']:.0f} mm tall and "
           f"{target['widest']:.0f} mm across; its neighbour is {neighbour['widest']:.0f} mm "
           f"across and {apart:.0f} mm away, which the asymmetric room test leaves "
           f"{push:.0f} mm short. Displacement separates the first outcome from the third and "
           "says nothing at all about the second.")
    figure.subplots_adjust(bottom=0.15, wspace=0.05)
    save(figure, "07-what-the-overhead-view-reports.png")


# --------------------------------------------------------------------------- #
# 4. What the low side-on look settles.
# --------------------------------------------------------------------------- #

def picture_the_side_on_look() -> None:
    figure, axes = new(13.4, 5.2, columns=3)
    glass = MEASURED[HARDEST]
    lying = from_the_side(FAMILY[HARDEST], glass["topple_lean"])
    rim, base_d, height = glass["widest"], glass["base"], glass["height"]

    left, right = -26.0, max(glass["over_run"], rim) + 58.0
    top = height + 30.0

    standing_axis, lying_axis, gap_axis = axes

    stage(standing_axis, "Standing, seen level from low down")
    standing_axis.set_xlim(left, right)
    standing_axis.set_ylim(-34, top)
    standing_axis.plot([left + 4, right - 4], [0, 0], color=INK, lw=1.2, zorder=1)
    glass_from_the_side(standing_axis, rim / 2.0 + 8.0, height, rim,
                        base_fraction=base_d / rim, colour=GLASS, alpha=0.32, lw=1.4)
    tall_span(standing_axis, rim + 30.0, 0.0, height, f"{height:.0f} mm tall", INK)
    span(standing_axis, 8.0, 8.0 + base_d, -26, f"{base_d:.0f} mm on the table", INK, above=4.0)

    stage(lying_axis, "The same glass, toppled, seen the same way")
    lying_axis.set_xlim(left, right)
    lying_axis.set_ylim(-34, top)
    lying_axis.plot([left + 4, right - 4], [0, 0], color=INK, lw=1.2, zorder=1)
    lying_patch(lying_axis, lying, offset=(8.0, 0.0))
    tall_span(lying_axis, glass["over_run"] + 20.0, 0.0, glass["over_top"],
              f"{glass['over_top']:.0f} mm tall", WARN)
    span(lying_axis, 8.0, 8.0 + glass["over_run"], -26,
         f"{glass['over_run']:.0f} mm on the table", WARN, above=4.0)
    note(lying_axis, (right + left) / 2.0, top - 4,
         "it rests on its wall, so the axis tilts\nand the rim end lifts clear", MUTED, va="top")

    on_table = np.array([m["over_run"] / m["over_top"] for m in MEASURED])
    upright = np.array([m["base"] / m["height"] for m in MEASURED])
    jitter = np.random.default_rng(SEED).normal(0, 0.05, HOW_MANY)
    plot_frame(gap_axis, "The ratio, over every glass of the kind",
               "what lies on the table, divided by how tall it stands", "")
    gap_axis.set_yticks([])
    gap_axis.axvspan(upright.max(), on_table.min(), color=to_rgba(GOOD, 0.16), zorder=0)
    gap_axis.scatter(upright, 1.0 + jitter, s=10, color=GLASS, alpha=0.5, linewidths=0)
    gap_axis.scatter(on_table, jitter, s=10, color=WARN, alpha=0.5, linewidths=0)
    gap_axis.set_ylim(-0.7, 2.2)
    gap_axis.set_xlim(0, on_table.max() * 1.08)
    gap_axis.text(0.02, 1.30, f"standing: {upright.min():.2f} to {upright.max():.2f}",
                  fontsize=NOTE_SIZE, color=GLASS, ha="left", va="bottom")
    gap_axis.text(on_table.max(), 0.30, f"toppled: {on_table.min():.2f} to {on_table.max():.2f}",
                  fontsize=NOTE_SIZE, color=WARN, ha="right", va="bottom")
    gap_axis.text((upright.max() + on_table.min()) / 2.0, 2.16,
                  f"{HOW_MANY} glasses,\nnone in the gap",
                  fontsize=NOTE_SIZE, color=GOOD, ha="center", va="top")

    footer(figure,
           f"The same {height:.0f} mm glass whose overhead blob barely changed. Seen level from "
           "low down, how much of the glass lies along the table divided by how tall it stands "
           f"separates standing from toppled across all {HOW_MANY} drawn glasses, with nothing "
           "in between. That is the measurement the second look is bought for.")
    figure.subplots_adjust(bottom=0.15, wspace=0.16)
    save(figure, "07-the-side-on-look-settles-it.png")


# --------------------------------------------------------------------------- #
# 5. The line the project draws, and what the overhead view sees at it.
# --------------------------------------------------------------------------- #

def picture_the_twenty_degree_line() -> None:
    figure, axes = new(12.8, 5.4, columns=2)
    glass = MEASURED[HARDEST]
    rim = glass["widest"]
    shapes_axis, curve_axis = axes

    stage(shapes_axis, "The same glass from above, at three leans")
    leans = ((0.0, "upright"),
             (STANDING_TILT, f"leaning {STANDING_TILT:.0f}°: the bench calls this fallen"),
             (glass["topple_lean"], f"flat on its wall, {glass['topple_lean']:.0f}°"))
    step = rim + 34.0
    limit = max(np.ptp(from_above(FAMILY[HARDEST], lean)[:, 0]) for lean, _ in leans) / 2.0 + 30.0
    shapes_axis.set_xlim(-limit, limit)
    shapes_axis.set_ylim(-2.0 * step - rim / 2.0 - 16.0, step * 0.62)
    for row, (lean, label) in enumerate(leans):
        shape = from_above(FAMILY[HARDEST], lean)
        shape = lying_patch(shapes_axis, shape,
                            offset=(-(shape[:, 0].min() + shape[:, 0].max()) / 2.0, -row * step),
                            colour=GLASS if row == 0 else WARN)
        long = shape[:, 0].max() - shape[:, 0].min()
        span(shapes_axis, shape[:, 0].min(), shape[:, 0].max(),
             -row * step + rim / 2.0 + 5.0, f"{long:.0f} mm — {label}",
             GLASS if row == 0 else WARN, above=5.0)

    plot_frame(curve_axis, "How long the blob gets, as the glass goes over",
               "lean from upright, degrees", "longest extent of the blob, mm")
    rim_to = KIND_RANGES[KIND]["rim_diameter"][1] * 1000.0
    for index, colour, label in ((HARDEST, WARN, "the hardest of the four hundred"),
                                 (MIDDLING, INK, "the middle one"),
                                 (EASIEST, GOOD, "the easiest")):
        over = MEASURED[index]["topple_lean"]
        leans = np.linspace(0.0, over, 40)
        long = [np.ptp(from_above(FAMILY[index], lean, samples=400)[:, 0]) for lean in leans]
        curve_axis.plot(leans, long, color=colour, lw=1.6, label=label)
    curve_axis.axvline(STANDING_TILT, color=INK, lw=1.2, ls=(0, (3, 2)))
    curve_axis.axhline(rim_to, color=MUTED, lw=1.0, ls=(0, (4, 3)))
    curve_axis.set_xlim(0, 80)
    curve_axis.set_ylim(0, 250)
    curve_axis.text(STANDING_TILT + 2, 242,
                    f"{STANDING_TILT:.0f}°: past this the bench\ncalls the glass fallen",
                    fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    curve_axis.annotate(f"{rim_to:.0f} mm: the widest a standing\nglass of this kind may be",
                        xy=(30, rim_to), xytext=(24, 56),
                        fontsize=NOTE_SIZE, color=MUTED, ha="left", va="bottom",
                        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    curve_axis.legend(fontsize=NOTE_SIZE, frameon=False, loc="lower right")

    footer(figure,
           f"The project's own test for a fallen glass is bench.py's STANDING_TILT_DEG: a lean of "
           f"more than {STANDING_TILT:.0f} degrees from upright. At exactly that lean the overhead "
           f"blob of the hardest glass has grown by "
           f"{np.ptp(from_above(FAMILY[HARDEST], STANDING_TILT)[:, 0]) - rim:.0f} mm, which is why "
           "the verdict cannot be reached from above.")
    figure.subplots_adjust(bottom=0.16, wspace=0.16)
    save(figure, "07-the-twenty-degree-line.png")


# --------------------------------------------------------------------------- #
# 6. The unmeasured number the verifier is the net under.
# --------------------------------------------------------------------------- #

def picture_the_safety_net() -> None:
    figure, axes = new(12.8, 5.4, columns=2)
    bases = np.array([m["base"] for m in MEASURED])
    caught = np.array([pushable(b, MU_LOW, JAW_MIDDLE) and tips(b, JAW_TOP, TRUE_FRICTION)
                       for b in bases])

    limit_axis, net_axis = axes

    plot_frame(limit_axis, "How high a glass may be pushed, and where the jaw touches it",
               "base diameter, mm", "highest safe push, mm above the table")
    order = np.argsort(bases)
    for mu, colour, label in ((MU_LOW, GOOD, f"friction {MU_LOW}, the guess"),
                              (TRUE_FRICTION, WARN, f"friction {TRUE_FRICTION}, the simulator's"),
                              (MU_HIGH, MUTED, f"friction {MU_HIGH}, also plausible")):
        limit_axis.plot(bases[order], [topple_height(b, mu) for b in bases[order]],
                        color=colour, lw=1.8, label=label)
    limit_axis.axhspan(0, JAW_MIDDLE, color=to_rgba(MUTED, 0.16), zorder=0)
    limit_axis.axhspan(JAW_MIDDLE, JAW_TOP, color=to_rgba(WARN, 0.10), zorder=0)
    limit_axis.axhline(JAW_MIDDLE, color=INK, lw=1.1, ls=(0, (3, 2)))
    limit_axis.axhline(JAW_TOP, color=INK, lw=1.4)
    limit_axis.text(bases.max() + 2, JAW_MIDDLE - 4,
                    f"{JAW_MIDDLE:.0f} mm: the middle of the jaw, where the arm aims",
                    fontsize=NOTE_SIZE, color=INK, ha="right", va="top")
    limit_axis.text(bases.max() + 2, JAW_TOP + 3,
                    f"{JAW_TOP:.0f} mm: the top edge, where a tapered glass really touches",
                    fontsize=NOTE_SIZE, color=INK, ha="right", va="bottom")
    placed = (("wide-footed", STURDY, -3.0, 30.0, "right"),
              ("narrow-footed", TIPPY, 4.0, -26.0, "left"))
    for label, (_height, rim, fraction), across, up, side in placed:
        base = base_width(rim, fraction)
        limit = topple_height(base, MU_LOW)
        limit_axis.plot([base], [limit], marker="o", ms=5, color=INK, zorder=5)
        limit_axis.annotate(f"the {label} glass of the cast,\nbase {base:.0f} mm across",
                            xy=(base, limit), xytext=(base + across, limit + up),
                            fontsize=NOTE_SIZE, color=INK, ha=side,
                            va="bottom" if up > 0 else "top",
                            arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    limit_axis.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper left")
    limit_axis.set_xlim(bases.min() - 3, bases.max() + 3)
    limit_axis.set_ylim(0, max(topple_height(b, MU_LOW) for b in bases) + 46)

    plot_frame(net_axis, "What the guess declares safe, and what the table does",
               f"glasses, out of the {HOW_MANY} drawn", "")
    bars = [
        (f"still slide at the real {TRUE_FRICTION}, touched at {JAW_TOP:.0f} mm",
         int(sum(not tips(b, JAW_TOP, TRUE_FRICTION) for b in bases)), GLASS),
        (f"declared safe by the guess, tipped by the real {TRUE_FRICTION}",
         int(caught.sum()), WARN),
        (f"declared safe: a guess of {MU_LOW}, checked at {JAW_MIDDLE:.0f} mm",
         int(sum(pushable(b, MU_LOW, JAW_MIDDLE) for b in bases)), GOOD),
    ]
    for index, (label, value, colour) in enumerate(bars):
        net_axis.barh(index, value, height=0.46, color=to_rgba(colour, 0.7), edgecolor=colour)
        net_axis.text(value + 6, index, f"{value} of {HOW_MANY}",
                      fontsize=NOTE_SIZE, color=colour, va="center")
        net_axis.text(4, index + 0.34, label, fontsize=NOTE_SIZE, color=INK, va="bottom")
    net_axis.set_yticks([])
    net_axis.set_xlim(0, HOW_MANY * 1.22)
    net_axis.set_ylim(-0.6, len(bars) - 0.15)

    footer(figure,
           "The arm works the push height out from the glass's measured base and a friction it "
           f"is never told. The simulator uses {TRUE_FRICTION}, which is ground truth for scoring "
           f"and not an input to anything. Guess {MU_LOW}, check it against the {JAW_MIDDLE:.0f} mm "
           f"the jaw aims at, and {int(caught.sum())} of the {HOW_MANY} drawn glasses go over. "
           "The verifier is what notices afterwards.")
    figure.subplots_adjust(bottom=0.21, wspace=0.14)
    save(figure, "07-the-safety-net.png")


# --------------------------------------------------------------------------- #
# Every number this document quotes, printed.
# --------------------------------------------------------------------------- #

def numbers() -> None:
    heights = np.array([m["height"] for m in MEASURED])
    widest = np.array([m["widest"] for m in MEASURED])
    bases = np.array([m["base"] for m in MEASURED])
    long_extent = np.array([m["over_long"] for m in MEASURED])
    short_extent = np.array([m["over_short"] for m in MEASURED])
    over_top = np.array([m["over_top"] for m in MEASURED])
    over_run = np.array([m["over_run"] for m in MEASURED])
    jumps = np.array([m["over_jump"] for m in MEASURED])
    areas = np.array([m["over_area"] / m["standing_area"] for m in MEASURED])
    rim_from, rim_to = (v * 1000.0 for v in KIND_RANGES[KIND]["rim_diameter"])

    print()
    print(f"--- {HOW_MANY} glasses of kind {KIND}, seed {SEED} ---")
    print(f"height {heights.min():.0f}-{heights.max():.0f} mm, "
          f"rim {widest.min():.0f}-{widest.max():.0f} mm, "
          f"base {bases.min():.0f}-{bases.max():.0f} mm")
    print(f"declared range: height {KIND_RANGES[KIND]['height']}, "
          f"rim {KIND_RANGES[KIND]['rim_diameter']}, "
          f"base fraction {KIND_RANGES[KIND]['base_fraction']}")

    print()
    print("the overhead blob, standing against lying on its wall")
    print(f"  standing: round, {widest.min():.0f} to {widest.max():.0f} mm")
    print(f"  toppled:  {long_extent.min():.0f}-{long_extent.max():.0f} mm long, "
          f"{short_extent.min():.0f}-{short_extent.max():.0f} mm wide")
    leans = np.array([m["topple_lean"] for m in MEASURED])
    print(f"  a glass comes to rest leaning {leans.min():.0f} to {leans.max():.0f} degrees "
          f"from upright, median {np.median(leans):.0f}")
    grew = long_extent - widest
    print(f"  the long extent grows by {grew.min():.0f} to {grew.max():.0f} mm, "
          f"median {np.median(grew):.0f}")
    legal = long_extent <= rim_to
    print(f"  toppled blob no longer than the kind's widest ({rim_to:.0f} mm): "
          f"{legal.sum()}/{HOW_MANY} = {100 * legal.mean():.1f}%")
    for tolerance in (10.0, 20.0, 30.0):
        close = grew <= tolerance
        print(f"  long extent grows by {tolerance:.0f} mm or less: "
              f"{close.sum()}/{HOW_MANY} = {100 * close.mean():.1f}%")
    roundness = short_extent / long_extent
    for bar in (0.8, 0.9):
        print(f"  toppled blob still rounder than {bar}: "
              f"{(roundness > bar).sum()}/{HOW_MANY} = {100 * (roundness > bar).mean():.1f}%")
    print(f"  toppled area / standing area {areas.min():.2f}-{areas.max():.2f}, "
          f"median {np.median(areas):.2f}; within a fifth of it: "
          f"{(np.abs(areas - 1) <= 0.2).sum()}/{HOW_MANY}")

    print()
    print(f"at the bench's own line for fallen, a lean of {STANDING_TILT:.0f} degrees")
    tilted_long = np.array([m["tilted_long"] for m in MEASURED])
    tilted_top = np.array([m["tilted_top"] for m in MEASURED])
    print(f"  the blob grows by {(tilted_long - widest).min():.0f} to "
          f"{(tilted_long - widest).max():.0f} mm, median {np.median(tilted_long - widest):.0f}")
    print(f"  the tallest point changes by {(tilted_top - heights).min():.0f} to "
          f"{(tilted_top - heights).max():.0f} mm, median {np.median(tilted_top - heights):.0f}")
    print(f"  blob still no longer than {rim_to:.0f} mm: "
          f"{(tilted_long <= rim_to).sum()}/{HOW_MANY}")
    print(f"  the hardest glass: blob {MEASURED[HARDEST]['tilted_long']:.0f} mm against "
          f"{MEASURED[HARDEST]['widest']:.0f} mm standing")
    sideways = heights * math.sin(math.radians(STANDING_TILT))
    print(f"  seen level, the rim's middle has swung {sideways.min():.0f} to "
          f"{sideways.max():.0f} mm sideways, median {np.median(sideways):.0f}, "
          f"against rims {widest.min():.0f}-{widest.max():.0f} mm across")

    print()
    print("the tallest point, once the glass is over")
    drop = heights - over_top
    print(f"  standing {heights.min():.0f}-{heights.max():.0f} mm, "
          f"toppled {over_top.min():.0f}-{over_top.max():.0f} mm")
    print(f"  it falls by {drop.min():.0f} to {drop.max():.0f} mm, median {np.median(drop):.0f}")
    print(f"  it rises instead: {(drop <= 0).sum()}/{HOW_MANY} = {100 * (drop <= 0).mean():.1f}%")
    print(f"  it changes by 10 mm or less: {(np.abs(drop) <= 10).sum()}/{HOW_MANY}")

    print()
    print("both overhead readings failing on the same glass")
    blind = (grew <= 20.0) & (np.abs(drop) <= 10.0)
    print(f"  blob grows 20 mm or less AND tallest point changes 10 mm or less: "
          f"{blind.sum()}/{HOW_MANY} = {100 * blind.mean():.1f}%")
    softer = (grew <= 30.0) & (np.abs(drop) <= 20.0)
    print(f"  the same, at 30 mm and 20 mm: {softer.sum()}/{HOW_MANY} = {100 * softer.mean():.1f}%")

    print()
    print(f"the bench's crowded tables: {HOW_MANY_TABLES} tapered tables from "
          f"seed {TAPERED_SEEDS[0]}")
    short, crowded, counts = every_shortfall()
    print(f"  {sum(counts)} glasses, {len(short)} of them without room "
          f"({100 * len(short) / sum(counts):.0f}%)")
    print(f"  glasses per table {min(counts)}-{max(counts)}; without room per table "
          f"{crowded.min()}-{crowded.max()}, median {np.median(crowded):.0f}")
    print(f"  how far each has to move to get room: {short.min():.1f} to {short.max():.1f} mm, "
          f"median {np.median(short):.1f}")
    for q in (90, 99):
        print(f"    {q}th percentile {np.percentile(short, q):.1f} mm")
    print(f"  the room test is asymmetric: against the narrowest of the kind it is "
          f"{GRIP_ROOM + rim_from / 2:.1f} mm between middles, against the widest "
          f"{GRIP_ROOM + rim_to / 2:.1f} mm")

    print()
    print("the apparent jump of the middle of the blob when a glass goes over")
    print(f"  on the table: {jumps.min():.0f} to {jumps.max():.0f} mm, median {np.median(jumps):.0f}")
    print(f"  the longest push any of those {HOW_MANY_TABLES} tables asks for: {short.max():.1f} mm")
    print(f"  topples whose jump is shorter than that: {(jumps < short.max()).sum()}/{HOW_MANY}")

    print()
    print(f"the same, read straight off the overhead picture at {SURVEY_UP:.0f} mm, uncorrected")
    splay_standing = np.array([m["splay_standing"] for m in MEASURED])
    splay_over = np.array([m["splay_over"] for m in MEASURED])
    seen_push = splay_standing * np.median(short)
    seen_jump = splay_over * jumps
    print(f"  a standing glass's outline is thrown out by {splay_standing.min():.2f} "
          f"to {splay_standing.max():.2f}; a lying one's by "
          f"{splay_over.min():.2f} to {splay_over.max():.2f}")
    print(f"  the median push looks like {seen_push.min():.0f}-{seen_push.max():.0f} mm")
    longest = splay_standing * short.max()
    print(f"  the longest push any of those tables asks for looks like "
          f"{longest.min():.0f}-{longest.max():.0f} mm")
    print(f"  a topple looks like {seen_jump.min():.0f}-{seen_jump.max():.0f} mm")
    print(f"  so even uncorrected the two do not overlap, but only by "
          f"{seen_jump.min() - longest.max():.0f} mm")

    print()
    print("the side-on ratio: what lies on the table, over how tall it stands")
    upright = bases / heights
    ratio = over_run / over_top
    print(f"  standing {upright.min():.2f}-{upright.max():.2f}, median {np.median(upright):.2f}")
    print(f"  toppled  {ratio.min():.2f}-{ratio.max():.2f}, median {np.median(ratio):.2f}")
    print(f"  the gap between them runs {upright.max():.2f} to {ratio.min():.2f}, "
          f"with {(ratio <= upright.max()).sum()} toppled glasses inside the standing range")

    print()
    print(f"the friction: the simulator uses {TRUE_FRICTION}, and tells nobody")
    print(f"  the jaw's middle rides at {JAW_MIDDLE:.0f} mm; its top edge, where a tapered "
          f"glass touches it, is at {JAW_TOP:.0f} mm")
    for height, label in ((JAW_MIDDLE, "the middle of the jaw"), (JAW_TOP, "the top edge")):
        for mu in (MU_LOW, TRUE_FRICTION, MU_HIGH):
            slides = np.array([not tips(b, height, mu) for b in bases])
            print(f"  contact at {height:.0f} mm ({label}), friction {mu}: "
                  f"{slides.sum()}/{HOW_MANY} slide = {100 * slides.mean():.1f}%")
    safe = np.array([pushable(b, MU_LOW, JAW_MIDDLE) for b in bases])
    caught = np.array([pushable(b, MU_LOW, JAW_MIDDLE) and tips(b, JAW_TOP, TRUE_FRICTION)
                       for b in bases])
    print(f"  guess {MU_LOW} checked at {JAW_MIDDLE:.0f} mm: {safe.sum()} declared safe; "
          f"of those, {caught.sum()} tip at the real {TRUE_FRICTION} acting at {JAW_TOP:.0f} mm "
          f"= {100 * caught.mean():.1f}% of {HOW_MANY}")
    honest = np.array([pushable(b, MU_LOW, JAW_TOP) for b in bases])
    honest_caught = np.array([pushable(b, MU_LOW, JAW_TOP) and tips(b, JAW_TOP, TRUE_FRICTION)
                              for b in bases])
    print(f"  if the arm checked against {JAW_TOP:.0f} mm instead: {honest.sum()} declared safe, "
          f"{honest_caught.sum()} of them still tip")
    for height in (JAW_MIDDLE, JAW_TOP):
        critical = bases / 2.0 / height
        print(f"  the friction at which each glass stops sliding, touched at {height:.0f} mm: "
              f"{critical.min():.2f}-{critical.max():.2f}, median {np.median(critical):.2f}")

    print()
    print(f"the cast in diagram_style, {len(CAST)} glasses, for reference")
    for label, (height, rim, fraction) in (("sturdy", STURDY), ("tippy", TIPPY)):
        base = base_width(rim, fraction)
        print(f"  {label}: {height:.0f} mm tall, rim {rim:.0f} mm, base {base:.0f} mm, "
              f"highest safe push {topple_height(base, MU_LOW):.0f} mm at friction {MU_LOW}")

    print()
    print("the three glasses the pictures follow, all out of the family")
    for name, index in (("hardest", HARDEST), ("middling", MIDDLING), ("easiest", EASIEST)):
        m = MEASURED[index]
        print(f"  {name}: {m['height']:.0f} mm tall, rim {m['widest']:.0f} mm, "
              f"base {m['base']:.0f} mm, comes to rest at {m['topple_lean']:.0f} degrees; "
              f"toppled blob {m['over_long']:.0f} by {m['over_short']:.0f} mm "
              f"(grew {m['over_long'] - m['widest']:.0f}), "
              f"tallest point {m['over_top']:.0f} mm, "
              f"{m['over_run']:.0f} mm on the table, middle jumps {m['over_jump']:.0f} mm")

    print()
    print(f"table {DRAWN_TABLE}, the one the outcome pictures are drawn on")
    for index, glass in enumerate(table(DRAWN_TABLE)):
        print(f"  glass {index}: at ({glass['x']:.0f}, {glass['y']:.0f}), "
              f"{glass['height']:.0f} mm tall, rim {glass['widest']:.0f} mm, "
              f"base {glass['base']:.0f} mm, "
              + ("has room" if glass["room"] else f"{glass['shortfall']:.1f} mm short"))
    drawn = table(DRAWN_TABLE)[DRAWN_GLASS]
    m = measure(drawn["outline"])
    neighbour = table(DRAWN_TABLE)[DRAWN_NEIGHBOUR]
    apart = float(np.hypot(drawn["x"] - neighbour["x"], drawn["y"] - neighbour["y"]))
    print(f"  the glass the worked example follows is glass {DRAWN_GLASS}: "
          f"{m['height']:.0f} mm tall, rim {m['widest']:.0f} mm, base {m['base']:.0f} mm")
    print(f"    its binding neighbour is glass {DRAWN_NEIGHBOUR}, {neighbour['widest']:.0f} mm "
          f"across and {apart:.0f} mm away; the room test wants "
          f"{GRIP_ROOM + neighbour['widest'] / 2:.0f} mm, so the push is "
          f"{drawn['shortfall']:.0f} mm")
    print(f"    leaning {STANDING_TILT:.0f} degrees: blob {m['tilted_long']:.0f} mm, "
          f"tallest point {m['tilted_top']:.0f} mm")
    print(f"    flat on its wall at {m['topple_lean']:.0f} degrees: blob {m['over_long']:.0f} by "
          f"{m['over_short']:.0f} mm, tallest point {m['over_top']:.0f} mm, "
          f"{m['over_run']:.0f} mm on the table, middle jumps {m['over_jump']:.0f} mm")
    print(f"    the side-on ratio: {m['base'] / m['height']:.2f} standing, "
          f"{m['over_run'] / m['over_top']:.2f} over")


if __name__ == "__main__":
    picture_the_same_glass_twice()
    picture_where_the_confusion_is_real()
    picture_what_the_overhead_view_reports()
    picture_the_side_on_look()
    picture_the_twenty_degree_line()
    picture_the_safety_net()
    numbers()
