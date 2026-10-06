"""Diagrams for solution 3 — imitation from demonstrations.

Five pictures. Every one of them draws something the project has measured, and
the four rules below are what keep them honest.

**No glass's size is written down here.** The two tables these pictures are
drawn on are ``bench.scene(1001)`` and ``bench.scene(10000)``, the examiner's own
generator, so every rim, foot and height is redrawn from the project's own
drawer at the same table number. What is written down is where the jaw went,
which is a policy's output and a push's parameters, never a glass.

**The two worked pushes are real and are rebuilt rather than copied.** The
teacher's push on each table is reconstructed from its glass, its heading and
its travel through ``01-one-fixed-nudge/plan.py``'s own arithmetic — the
fingertips come down ``APPROACH_GAP`` clear of the widest part of the glass —
and ``check_the_examples`` asserts the rebuilt start against the one the examiner
really recorded. A silent drift between this file and the solution shows up as
a failed check rather than as a wrong picture.

**The numbers that need the fitted weights or the collected demonstrations are
written down, with the script that measured them.** ``data/`` and ``weights/``
are not in git — a fresh checkout makes them again with ``make collect`` and
``make train`` — so nothing here imports them. ``results.json`` is in git and
is read. The throwaway scripts that produced the rest are described beside each
block; each one runs from ``03-push-glasses-apart`` in that folder's
environment, which is the only one with MuJoCo, PyTorch and LeRobot in it.

**Nothing here runs the policy.** There is no model in this file. Where a
picture shows what the policy produced, the waypoints are the ones it really
produced, captured once and named as such.

    cd 03-push-glasses-apart && pixi run python ../images/generators/03-push-glasses-apart/make_03_images.py

Everything the document quotes is printed by ``report()`` at the end, so a
number in the prose can be checked against a number on the terminal.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import types
from pathlib import Path
from textwrap import fill

import numpy as np
from diagram_style import (
    FEEL_SPEED,
    GLASS,
    GLASS_ZONE,
    GOOD,
    GRIP_ROOM,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PUSH_HEIGHT,
    PUSH_SPEED,
    TOP_SPEED,
    TRAVEL_HEIGHT,
    WARN,
    WAYPOINT_PERIOD,
    bare,
    glass_from_above,
    has_room,
    new,
    save,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "work_cell"))

SOLUTION = ROOT / "03-push-glasses-apart" / "03-imitation-from-demonstrations"
RESULTS = SOLUTION / "results.json"


def _bench():
    """``03-push-glasses-apart/bench/bench.py``: the crowded tables and the jaw's own sizes.

    Imported for ``scene`` and for its constants. No physics is touched here,
    so when MuJoCo is missing a placeholder stands in for it long enough to
    load the module, and the pictures can still be drawn from the root
    environment.
    """
    sys.path.insert(0, str(ROOT / "03-push-glasses-apart" / "bench"))
    if importlib.util.find_spec("mujoco") is None:
        sys.modules["mujoco"] = types.ModuleType("mujoco")
    import bench

    return bench


BENCH = _bench()

# The jaw, from bench.py, in millimetres. All three are the gripper's own
# sizes. FINGER is how far back from the fingertips the fingers run and THICK
# is how wide they are; TOOL is how far back the whole tool reaches and BODY
# how wide it is behind the fingers. 01-one-fixed-nudge/plan.py checks a
# candidate push against every other glass along exactly these two segments,
# which is the check nothing in a cloned policy reproduces.
FINGER = BENCH.FINGER_LENGTH * 1000.0
THICK = BENCH.JAW_THICKNESS * 1000.0
TOOL = BENCH.TOOL_LENGTH * 1000.0
BODY = BENCH.BODY_SIZE * 1000.0
RETREAT = BENCH.RETREAT * 1000.0
# How far clear of the widest part of a glass the fingertips come down, and
# how far past that the jaw keeps feeling. 01-one-fixed-nudge/plan.py.
APPROACH_GAP = 10.0
CLEARANCE = 8.0

# How far a rebuilt push may land from the one the examiner recorded before the
# check below fails. The teacher planned from ``look()``, which carries the
# examiner's own measurement error, and the fingertips are put down a measured
# half-width behind the glass, so three standard deviations of the position
# error and of the half-width error is the room a faithful rebuild needs.
REBUILD_TOLERANCE = 3.0 * (BENCH.POSITION_NOISE + BENCH.WIDTH_NOISE / 2.0) * 1000.0

assert PUSH_HEIGHT == BENCH.PUSH_HEIGHT * 1000.0, "diagram_style and bench.py disagree on the jaw"
assert TRAVEL_HEIGHT == BENCH.TRAVEL_HEIGHT * 1000.0, "diagram_style and bench.py disagree on travel"
assert WAYPOINT_PERIOD == BENCH.WAYPOINT_PERIOD, "diagram_style and bench.py disagree on the rate"
assert FEEL_SPEED == BENCH.FEEL_SPEED * 1000.0, "diagram_style and bench.py disagree on feeling"
assert PUSH_SPEED == BENCH.PUSH_SPEED * 1000.0, "diagram_style and bench.py disagree on pushing"
assert TOP_SPEED == BENCH.TOP_SPEED * 1000.0, "diagram_style and bench.py disagree on the top speed"
assert GRIP_ROOM == BENCH.GRIP_ROOM * 1000.0, "diagram_style and bench.py disagree on the room"

# How far apart the waypoints of a recorded path are, by leg: the rate is
# fixed, so a speed *is* a spacing. The cap is what follow() will not exceed.
FEEL_STEP = FEEL_SPEED * WAYPOINT_PERIOD        # 0.5 mm
PUSH_STEP = PUSH_SPEED * WAYPOINT_PERIOD        # 1.0 mm
STEP_CAP = TOP_SPEED * WAYPOINT_PERIOD          # 10 mm

# The chunk, from 03-imitation-from-demonstrations/chunks.py.
CHUNK = 120
ACTION_WIDTH = 5
ACTION_COLUMNS = ("x", "y", "z", "cos heading", "sin heading")

# --------------------------------------------------------------------------- #
# The demonstration set, from
# 03-imitation-from-demonstrations/data/collection.json, which `make collect`
# writes and git does not keep. Counts of pushes, never a measurement of a
# glass.
# --------------------------------------------------------------------------- #
COLLECTED = {
    "tables": 5_200,
    "first_table": 1_000,
    "pushes": 22_846,
    "kept": 12_656,
    "glasses_refused": 5_389,
    "minutes": 14,
    "dropped": [
        ("a 5 mm test push, not a push at the task", 9_783),
        ("the table gained no room", 263),
        ("a glass toppled", 125),
        ("a glass left the glass zone", 18),
        ("blocked on the way down", 1),
    ],
    # Tables above the fitting band and below the dividing line, kept back to
    # say how far the student is from the teacher on pictures it never saw.
    "check_tables": 300,
    "check_kept": 728,
    # What push_segment leaves, over the whole set, in waypoints.
    "waypoints_least": 25,
    "waypoints_median": 112,
    "waypoints_most": 246,
}
# Everything but the test pushes is a real push at the task.
REAL_PUSHES = COLLECTED["pushes"] - COLLECTED["dropped"][0][1]
DROPPED_REAL = REAL_PUSHES - COLLECTED["kept"]

# --------------------------------------------------------------------------- #
# The three fits, from 03-imitation-from-demonstrations/weights/act-training.json,
# which `make train` writes and git does not keep. ``loss`` is the last of the
# twenty the file records, and the two distances are that seed's own diagnostic:
# how far its chunk is from the teacher's, per waypoint, on tables it was fitted
# on and on tables it never saw.
# --------------------------------------------------------------------------- #
FITS = [
    {"seed": 0, "minutes": 53.5, "loss": 0.2485, "fitted_mm": 53.3, "unseen_mm": 55.1,
     "unseen_heading_deg": 26.3},
    {"seed": 1, "minutes": 53.7, "loss": 0.2895, "fitted_mm": 64.4, "unseen_mm": 63.8,
     "unseen_heading_deg": 38.0},
    {"seed": 2, "minutes": 53.2, "loss": 0.1684, "fitted_mm": 36.7, "unseen_mm": 54.8,
     "unseen_heading_deg": 21.3},
]
FIT_STEPS, FIT_BATCH = 10_000, 16

# The fit this folder's README records and threw away, because it is the
# clearest thing in the whole solution: a quarter of the demonstrations, four
# times as many passes over them, a training loss six times lower, and useless.
# The weights were not kept, so these four numbers are the README's and are
# quoted rather than re-measured.
EARLY_FIT = {"demonstrations": 3_144, "tables": 1_300, "passes": 51, "loss": 0.04,
             "fitted_mm": 11.0, "unseen_mm": 62.0}

# --------------------------------------------------------------------------- #
# Measured here, because the document and the README quote none of it.
#
# Script one — the chunk against the teacher's, on the 200 held-back
# demonstrations of ``data/validation.npz`` (tables 8000 to 8299, never fitted
# on), for each of the three fitted seeds. For every picture it asked the
# policy for a chunk and compared it with the teacher's chunk stored beside
# that picture:
#
#   * ``first_mm`` — how far the chunk's first waypoint is from the teacher's,
#     which is where the jaw comes down and so what decides whether the descent
#     is clear;
#   * ``net_mm`` / ``path_mm`` — how far the chunk gets from where it started,
#     against how far the jaw travels doing it. The teacher's chunks are
#     straight: 87.2 mm of path for 87.2 mm of displacement, every one of them.
#   * ``pulled`` — the chunks with a waypoint outside what the jaw can reach,
#     of 200, and which column it was.
# --------------------------------------------------------------------------- #
HELD_BACK = {
    "chunks": 200,
    "tables": (8_000, 8_299),
    "teacher_net_mm": 87.2,
    "teacher_path_mm": 87.2,
    "teacher_net_least_mm": 22.9,
    "teacher_net_most_mm": 155.3,
    "seeds": [
        {"seed": 0, "first_mm": 66.2, "first_90th_mm": 130.0, "net_mm": 60.8, "path_mm": 160.4,
         "pulled": 112, "worst_z_mm": 0.82},
        {"seed": 1, "first_mm": 78.5, "first_90th_mm": 136.7, "net_mm": 39.8, "path_mm": 152.7,
         "pulled": 59, "worst_z_mm": 0.43},
        {"seed": 2, "first_mm": 67.7, "first_90th_mm": 149.6, "net_mm": 84.1, "path_mm": 186.3,
         "pulled": 137, "worst_z_mm": 1.67},
    ],
    # Every waypoint that had to be pulled in was pulled in on the height
    # column alone. Not one chunk, of the 600 asked for, put x or y outside
    # the table.
    "pulled_column": "z",
    "pulled_x_or_y": 0,
}

# Script two — the first chunk on each of the fifty held-out tables, for each
# fitted seed: how far the chunk's first waypoint is from the nearest glass's
# measured edge, and what the examiner felt when it followed the chunk. The
# teacher's first push on the same fifty, measured the same way, is the row
# below. A negative gap means the fingertips came down inside a glass.
FIRST_CHUNK = {
    "tables": 50,
    "seeds": [
        {"seed": 0, "gap_mm": 6.3, "worst_gap_mm": -32.8, "inside_a_glass": 13, "blocked": 34},
        {"seed": 1, "gap_mm": 11.0, "worst_gap_mm": -32.7, "inside_a_glass": 14, "blocked": 36},
        {"seed": 2, "gap_mm": 14.3, "worst_gap_mm": -30.0, "inside_a_glass": 8, "blocked": 22},
    ],
    "teacher": {"gap_mm": 10.2, "worst_gap_mm": 5.4, "inside_a_glass": 0, "blocked": 0},
}

# --------------------------------------------------------------------------- #
# The two worked tables. Only the choices are written down — which glass, which
# heading, how far — because those belong to the teacher and to the policy. The
# glasses are redrawn from ``bench.scene`` at the same table number, and
# ``check_the_examples`` asserts the rebuilt pushes against what the examiner
# recorded.
#
# Script three captured both: it ran the fitted teacher on table 1001 and kept
# its first push with the path the jaw really followed, then ran seed 0 of the
# fitted policy on table 10000, took its first chunk, and followed it.
# --------------------------------------------------------------------------- #
DEMO = {
    "table": 1_001,
    "glass": 4,
    "heading_deg": 20.0,
    "travel": 48.0,
    # What the examiner recorded: how far the jaw felt forward before it touched,
    # where the fingertips came down, how far the glass ended from the aim, and
    # the path's own shape.
    "felt_forward": 20.3,
    "start": (406.3, -308.9),
    "landed_from_aim": 2.6,
    "waypoints": 159,
    "coming_down": 25,
    "at_push_height": 109,
    "kept": 90,
    "net": 67.9,
}
EXAMPLE = {
    "table": 10_000,
    "seed": 0,
    # The teacher, on this table.
    "teacher_glass": 1,
    "teacher_heading_deg": 260.0,
    "teacher_travel": 66.0,
    "teacher_start": (445.1, -157.9),
    "teacher_pushed": 66.0,
    # The policy, on the same table, from the same picture. ``waypoints`` is
    # every tenth waypoint of the chunk it returned, in millimetres, with the
    # heading it asked for at that waypoint: the policy's own output, as
    # captured. The chunk is 120 waypoints long.
    "charged_to": 1,
    "waypoints": [
        (446.4, -214.8, 50.3, -82.1),
        (453.1, -214.5, 50.2, -82.0),
        (452.0, -216.2, 50.1, -82.9),
        (451.6, -217.8, 50.1, -82.0),
        (452.1, -220.2, 50.1, -81.7),
        (455.9, -218.5, 50.0, -82.9),
        (453.2, -222.0, 50.0, -81.4),
        (452.4, -224.9, 49.9, -83.1),
        (456.6, -227.1, 49.8, -81.8),
        (457.6, -230.5, 49.9, -81.1),
        (460.8, -230.0, 49.8, -82.0),
        (463.3, -234.2, 49.8, -82.3),
    ],
    "last": (466.8, -234.8, 49.8, -82.2),
    # The whole chunk's shape, over all 120 waypoints rather than the twelve
    # drawn: how far the jaw walks, and how far it gets from where it started.
    "path_mm": 262.2,
    "net_mm": 28.5,
    "pulled_in": 61,
    "blocked": True,
    "peak_newtons": 3.86,
}


# What run.py's own wrapping tally reported over the three held-out runs: how
# many chunks were asked for, and how many had at least one waypoint outside
# what the jaw can reach and were pulled back inside. Both are in this folder's
# README; they are not in results.json, because they are not a score.
CHUNKS_ASKED = 1_900
PULLED_CHUNKS = 814

# What the teacher scored on the same fifty tables, read from
# 03-push-glasses-apart/02-geometry-ranked/results.json, which is in git.
TEACHER = json.loads(
    (ROOT / "03-push-glasses-apart" / "02-geometry-ranked" / "results.json").read_text()
)

# --------------------------------------------------------------------------- #
# The tables, from the examiner's own generator.
# --------------------------------------------------------------------------- #
def table(seed: int) -> list[dict]:
    """One of the examiner's crowded tables, in millimetres, with its room test."""
    glasses = [
        {
            "id": i,
            "x": glass.position[0] * 1000.0,
            "y": glass.position[1] * 1000.0,
            "widest": glass.outline.max_diameter * 1000.0,
            "fraction": 2.0 * float(glass.outline.radius[0]) / glass.outline.max_diameter,
            "height": glass.outline.total_height * 1000.0,
        }
        for i, glass in enumerate(BENCH.scene(seed))
    ]
    for i, here in enumerate(glasses):
        others = [(g["x"], g["y"], g["widest"]) for j, g in enumerate(glasses) if j != i]
        here["room"] = has_room((here["x"], here["y"]), others)
    return glasses


def one(glasses: list[dict], which: int) -> dict:
    return next(g for g in glasses if g["id"] == which)


def unit(heading_deg: float) -> tuple[float, float]:
    angle = math.radians(heading_deg)
    return math.cos(angle), math.sin(angle)


def fingertips(glass: dict, heading_deg: float) -> tuple[float, float]:
    """Where plan.py puts the fingertips down for a push of this glass along this heading."""
    ahead = unit(heading_deg)
    back = glass["widest"] / 2.0 + APPROACH_GAP
    return glass["x"] - ahead[0] * back, glass["y"] - ahead[1] * back


def gap_to_the_nearest_glass(point: tuple[float, float], glasses: list[dict]) -> tuple[float, int]:
    """Millimetres from the nearest glass's edge, and which glass. Negative is inside it."""
    best, which = math.inf, -1
    for glass in glasses:
        gap = math.dist((glass["x"], glass["y"]), point) - glass["widest"] / 2.0
        if gap < best:
            best, which = gap, glass["id"]
    return best, which


def spread_of(key: str, rows: list[dict]) -> tuple[float, float]:
    return min(row[key] for row in rows), max(row[key] for row in rows)


# --------------------------------------------------------------------------- #
# Drawing helpers.
# --------------------------------------------------------------------------- #
def stage(axis, title: str) -> None:
    bare(axis)
    # datalim rather than box: the panel keeps its size and the drawing grows
    # into it, so every panel's title sits at the same height on the page.
    axis.set_aspect("equal", adjustable="datalim")
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)


def note(axis, x, y, text, colour=MUTED, **kwargs) -> None:
    kwargs.setdefault("ha", "center")
    axis.text(x, y, text, fontsize=NOTE_SIZE, color=colour, **kwargs)


def footer(figure, text: str, width: int = 170) -> None:
    figure.text(0.5, 0.012, fill(text, width), fontsize=NOTE_SIZE, color=INK, ha="center")


def under(figure, column: int, columns: int, text: str, y: float = 0.295,
          width: int = 66) -> None:
    """A note beneath one panel, wrapped so that neighbouring panels never collide."""
    figure.text((column + 0.5) / columns, y, fill(text, width), fontsize=NOTE_SIZE, color=INK,
                ha="center", va="top")


def zone(axis) -> None:
    """The rectangle the glasses may stand in."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                             facecolor=to_rgba(MUTED, 0.06), edgecolor=MUTED, lw=1.0, zorder=0))


def draw_table(axis, glasses: list[dict], names: bool = True, faded: bool = False,
               rings: bool = False) -> None:
    """Every glass from the top, with the foot it stands on, and a name beside it."""
    for glass in glasses:
        if rings and not glass["room"]:
            axis.add_patch(Circle((glass["x"], glass["y"]), GRIP_ROOM, facecolor="none",
                                  edgecolor=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=2))
        glass_from_above(axis, (glass["x"], glass["y"]), glass["widest"], glass["fraction"],
                         alpha=0.14 if faded else 0.30, zorder=3)
        if names:
            axis.text(glass["x"], glass["y"] - glass["widest"] / 2 - 7, "ABCDEF"[glass["id"]],
                      fontsize=NOTE_SIZE, color=MUTED if faded else INK, ha="center", va="top",
                      clip_on=True)


def frame_on(axis, points, pad: float = 30.0) -> None:
    """Fit the panel round every point handed to it, plus a margin."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    axis.set_xlim(min(xs) - pad, max(xs) + pad)
    axis.set_ylim(min(ys) - pad, max(ys) + pad)


def table_corners(glasses: list[dict]) -> list[tuple[float, float]]:
    return [(g["x"] + dx * g["widest"] / 2, g["y"] + dy * g["widest"] / 2)
            for g in glasses for dx, dy in ((-1, -1), (1, 1))]


def jaw_corners(tip, heading_deg: float) -> list[tuple[float, float]]:
    """The outline of the closed jaw seen from the top, fingertips to wrist.

    Two rectangles, because that is how the geometry models it: the fingers run
    FINGER back from the fingertips and are THICK across, and the body behind
    them runs to TOOL and is BODY across. The descent comes straight down on
    this whole shape, so anything standing under any of it stops the jaw.
    """
    ahead = unit(heading_deg)
    side = (-ahead[1], ahead[0])
    out = []
    for front, back, half in ((0.0, FINGER, THICK / 2.0), (FINGER, TOOL, BODY / 2.0)):
        out.append([
            (tip[0] - ahead[0] * along + side[0] * across,
             tip[1] - ahead[1] * along + side[1] * across)
            for along, across in ((front, half), (back, half), (back, -half), (front, -half))
        ])
    return out


def jaw_from_above(axis, tip, heading_deg: float, colour=INK, alpha: float = 0.16,
                   lw: float = 1.0, zorder: int = 7) -> list[tuple[float, float]]:
    for block in jaw_corners(tip, heading_deg):
        axis.add_patch(Polygon(block, closed=True, facecolor=to_rgba(colour, alpha),
                               edgecolor=colour, lw=lw, zorder=zorder))
    return [corner for block in jaw_corners(tip, heading_deg) for corner in block]


def bars(axis, labels, values, colours, texts=None, room: float = 0.62) -> None:
    """Horizontal bars with the label inside the panel and the count at the end.

    ``room`` is how much of the panel's width is left of zero for the labels,
    so that a long label never runs into the panel beside it.
    """
    places = np.arange(len(labels))[::-1]
    widest = max(values)
    axis.set_aspect("auto")
    axis.barh(places, values, height=0.6, color=colours, zorder=3)
    for place, value, label, text in zip(places, values, labels,
                                         texts or [f"{v:,.0f}" for v in values], strict=True):
        axis.text(-widest * 0.02, place, label, fontsize=NOTE_SIZE, color=INK, ha="right",
                  va="center")
        axis.text(value + widest * 0.015, place, text, fontsize=NOTE_SIZE, color=INK, ha="left",
                  va="center")
    axis.set_xlim(-widest * room, widest * 1.18)
    axis.set_ylim(-0.7, len(labels) - 0.3)
    bare(axis)


def chart(axis, title: str, left: bool = True) -> None:
    """A panel that is a plot rather than a drawing: it keeps its ticks."""
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)
    plain(axis, left)


def plain(axis, left: bool = True) -> None:
    """A plotting axis rather than a drawing: no box, muted ticks."""
    axis.set_aspect("auto")
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        axis.spines[side].set_color(MUTED)
    if not left:
        axis.spines["left"].set_visible(False)
        axis.set_yticks([])
    axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED, length=3)
    for label in axis.get_xticklabels() + axis.get_yticklabels():
        label.set_color(INK)


# --------------------------------------------------------------------------- #
# 1. Where the demonstrations come from.
# --------------------------------------------------------------------------- #
def picture_the_demonstrations() -> dict:
    glasses = table(DEMO["table"])
    pushed = one(glasses, DEMO["glass"])
    ahead = unit(DEMO["heading_deg"])
    start = fingertips(pushed, DEMO["heading_deg"])
    touch = (start[0] + ahead[0] * DEMO["felt_forward"], start[1] + ahead[1] * DEMO["felt_forward"])
    end = (touch[0] + ahead[0] * DEMO["travel"], touch[1] + ahead[1] * DEMO["travel"])
    backed = (end[0] - ahead[0] * RETREAT, end[1] - ahead[1] * RETREAT)
    feeling = round(DEMO["felt_forward"] / FEEL_STEP)
    pushing = round(DEMO["travel"] / PUSH_STEP)
    backing = round(RETREAT / PUSH_STEP)

    figure, axes = new(13.6, 5.8, columns=3)
    seen, path, set_of_them = axes

    stage(seen, f"In: the table from the top, table {DEMO['table']:,}")
    zone(seen)
    draw_table(seen, glasses, rings=True)
    seen.plot(*start, marker="o", ms=3.4, color=GOOD, zorder=8)
    seen.annotate("", xy=end, xytext=start, zorder=7,
                  arrowprops={"arrowstyle": "-|>", "color": GOOD, "lw": 1.6})
    frame_on(seen, table_corners(glasses), pad=26.0)
    short = sum(1 for glass in glasses if not glass["room"])
    under(figure, 0, 3,
          f"{len(glasses)} glasses, {short} of them without the room the jaw needs — the dashed "
          f"rings. One picture of this, 192 by 192 pixels, is the whole of what the policy is "
          f"ever shown. The arrow is the push the teacher chose here: glass "
          f"{'ABCDEF'[DEMO['glass']]}, pushed at {DEMO['heading_deg']:.0f}°.")

    stage(path, "Out: the path the jaw really followed")
    landed = (pushed["x"] + ahead[0] * DEMO["travel"], pushed["y"] + ahead[1] * DEMO["travel"])
    glass_from_above(path, (pushed["x"], pushed["y"]), pushed["widest"], pushed["fraction"],
                     alpha=0.12)
    glass_from_above(path, landed, pushed["widest"], pushed["fraction"])
    note(path, pushed["x"], pushed["y"] + pushed["widest"] / 2 + 4, "where it stood", MUTED,
         va="bottom")
    note(path, landed[0], landed[1] + pushed["widest"] / 2 + 4,
         f"where it ended, {DEMO['landed_from_aim']:.1f} mm from the aim", GLASS, va="bottom")
    for first, last, step, colour, name in (
        (start, touch, FEEL_STEP, MUTED, f"feeling, {feeling} waypoints {FEEL_STEP:.1f} mm apart"),
        (touch, end, PUSH_STEP, GOOD, f"pushing, {pushing} waypoints {PUSH_STEP:.1f} mm apart"),
        (end, backed, PUSH_STEP, WARN, f"backing off, {backing}, which is trimmed off"),
    ):
        count = max(int(math.dist(first, last) / step), 1)
        points = [(first[0] + (last[0] - first[0]) * k / count,
                   first[1] + (last[1] - first[1]) * k / count) for k in range(count + 1)]
        path.plot([p[0] for p in points], [p[1] for p in points], color=colour, lw=0.9,
                  marker="o", ms=1.8, mew=0.0, zorder=8, label=name)
    path.plot(*start, marker="o", ms=3.4, color=INK, zorder=9)
    note(path, start[0] - 3, start[1] - 7, "the jaw reaches\npush height here", INK, ha="right",
         va="top")
    path.legend(loc="lower right", fontsize=NOTE_SIZE - 0.6, frameon=False, borderpad=0.0,
                handlelength=1.6, labelcolor=INK)
    frame_on(path, [start, end, (pushed["x"], pushed["y"]), landed], pad=56.0)
    under(figure, 1, 3,
          f"the examiner writes the jaw's own path down on every action, one waypoint every "
          f"{WAYPOINT_PERIOD * 1000:.0f} ms, so how far apart they are is how fast it was going. "
          f"{DEMO['waypoints']} in all: {DEMO['coming_down']} coming down, "
          f"{DEMO['at_push_height']} at push height. push_segment keeps the {DEMO['kept']} from "
          f"where it reached push height to the furthest it got; the examiner does the rest itself.")

    stage(set_of_them, "The set: every push the teacher made, kept or dropped")
    labels = ["kept, and fitted on"] + [name for name, _ in COLLECTED["dropped"]]
    values = [COLLECTED["kept"]] + [count for _, count in COLLECTED["dropped"]]
    bars(set_of_them, labels, values, [GOOD, MUTED, WARN, WARN, WARN, WARN], room=0.95)
    under(figure, 2, 3,
          f"{COLLECTED['pushes']:,} pushes on {COLLECTED['tables']:,} tables, in "
          f"{COLLECTED['minutes']} minutes of arm time. Only the ones that worked are kept, "
          f"because a cloned policy copies a bad label as readily as a good one. Almost "
          f"everything dropped is the teacher's own 5 mm test push, which is not a push at the "
          f"task: of the {REAL_PUSHES:,} real pushes only {DROPPED_REAL} were dropped, "
          f"{100 * DROPPED_REAL / REAL_PUSHES:.0f} per cent.")

    footer(figure,
           f"The teacher is solution 2, in the folder next door, run unchanged on tables "
           f"{COLLECTED['first_table']:,} to "
           f"{COLLECTED['first_table'] + COLLECTED['tables'] - 1:,} — all below the examiner's "
           f"dividing line at {BENCH.TEST_SEEDS:,}, so no policy here is ever marked on a table "
           f"it learned from. A demonstration is the pair in the first two panels: the picture, "
           f"and the path. Nothing in it was driven by a person, and "
           f"{COLLECTED['glasses_refused']:,} glasses the teacher refused are counted beside the "
           f"demonstrations rather than dropped in silence. The counts are collect.py's own, from "
           f"data/collection.json; the table and the push are bench.scene({DEMO['table']:,}) and "
           f"the first push the fitted teacher made on it, rebuilt here from its glass, heading "
           f"and travel.")
    figure.subplots_adjust(bottom=0.34, top=0.92, wspace=0.10)
    save(figure, "03-where-the-demonstrations-come-from.png")
    return {"start": start, "touch": touch, "end": end, "feeling": feeling, "pushing": pushing,
            "backing": backing, "at_push_height": feeling + pushing + backing,
            "kept": feeling + pushing + 1, "net": math.dist(start, end)}


# --------------------------------------------------------------------------- #
# 2. A chunk is not a push.
# --------------------------------------------------------------------------- #
def picture_a_chunk_is_not_a_push(demo: dict) -> None:
    figure, axes = new(13.0, 5.8, columns=2)
    macro, chunk = axes

    # --- the macro, from the side -------------------------------------------
    stage(macro, "What a parameterised push is: six numbers, and the examiner's macro")
    macro.set_aspect("auto")
    feel_to = DEMO["felt_forward"]
    push_to = feel_to + DEMO["travel"]
    corners = [(0.0, TRAVEL_HEIGHT), (0.0, PUSH_HEIGHT), (feel_to, PUSH_HEIGHT),
               (push_to, PUSH_HEIGHT), (push_to - RETREAT, PUSH_HEIGHT),
               (push_to - RETREAT, TRAVEL_HEIGHT)]
    # Each leg's colour and the spacing its own speed gives it.
    legs = ((MUTED, STEP_CAP), (GOOD, FEEL_STEP), (GOOD, PUSH_STEP), (WARN, PUSH_STEP),
            (MUTED, STEP_CAP))
    for leg, (colour, step) in enumerate(legs):
        first, last = corners[leg], corners[leg + 1]
        macro.plot([first[0], last[0]], [first[1], last[1]], color=colour, lw=1.8, zorder=5,
                   solid_capstyle="round")
        count = max(int(math.dist(first, last) / step), 1)
        macro.plot([first[0] + (last[0] - first[0]) * k / count for k in range(count + 1)],
                   [first[1] + (last[1] - first[1]) * k / count for k in range(count + 1)],
                   marker="o", ms=1.6, mew=0.0, ls="none", color=colour, zorder=6)
    macro.add_patch(Rectangle((0.0, PUSH_HEIGHT - 9.0), push_to, 18.0,
                              facecolor=to_rgba(GOOD, 0.10), edgecolor="none", zorder=1))
    for height, name in ((TRAVEL_HEIGHT, f"travel height, {TRAVEL_HEIGHT:.0f} mm"),
                         (PUSH_HEIGHT, f"push height, {PUSH_HEIGHT:.0f} mm")):
        macro.plot([-18, push_to + 18], [height, height], color=MUTED, lw=0.7, ls=(0, (2, 3)),
                   zorder=0)
        macro.text(push_to + 22, height, name, fontsize=NOTE_SIZE, color=MUTED, ha="left",
                   va="center")
    macro.text(-10, PUSH_HEIGHT + 0.62 * (TRAVEL_HEIGHT - PUSH_HEIGHT),
               f"coming down,\n{STEP_CAP:.0f} mm a waypoint:\nthe examiner's own move",
               fontsize=NOTE_SIZE, color=MUTED, ha="right", va="center")
    macro.text(push_to + 22, PUSH_HEIGHT + 0.62 * (TRAVEL_HEIGHT - PUSH_HEIGHT),
               "lifting:\nthe examiner's own move", fontsize=NOTE_SIZE, color=MUTED, ha="left",
               va="center")
    macro.annotate(f"feeling for the glass,\n{demo['feeling']} waypoints {FEEL_STEP:.1f} mm apart",
                   xy=(feel_to / 2, PUSH_HEIGHT), xytext=(-78, -26), textcoords="offset points",
                   fontsize=NOTE_SIZE, color=GOOD, ha="center", va="top",
                   arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.7})
    macro.annotate(f"pushing,\n{demo['pushing']} waypoints {PUSH_STEP:.1f} mm apart",
                   xy=(feel_to + DEMO["travel"] / 2, PUSH_HEIGHT), xytext=(96, -26),
                   textcoords="offset points", fontsize=NOTE_SIZE, color=GOOD, ha="center",
                   va="top", arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.7})
    macro.annotate(f"backing off, {demo['backing']} waypoints,\nand then lifting: the examiner's "
                   f"own moves again", xy=(push_to - RETREAT / 2, PUSH_HEIGHT),
                   xytext=(0, -72), textcoords="offset points", fontsize=NOTE_SIZE, color=WARN,
                   ha="center", va="top", arrowprops={"arrowstyle": "-", "color": WARN,
                                                      "lw": 0.7})
    macro.text(-10, PUSH_HEIGHT + 86,
               f"what push_segment keeps, and the\npolicy is fitted to: {demo['kept']} waypoints",
               fontsize=NOTE_SIZE, color=GOOD, ha="right", va="center")
    macro.set_xlim(-150, push_to + 150)
    macro.set_ylim(PUSH_HEIGHT - 150, TRAVEL_HEIGHT + 34)
    under(figure, 0, 2,
          "which glass, where to put the jaw down, which way to point, how far to feel, how far "
          "to push, and where the glass is expected to land. The examiner owns the macro that turns "
          "those six numbers into a motion, and it expands every parameterised push the same "
          "way. The descent, the back-off and the lift are the examiner's own, so a demonstration "
          "keeps only the shaded part.", width=92)

    # --- the chunk ----------------------------------------------------------
    stage(chunk, f"What an action chunk is: {CHUNK} waypoints by {ACTION_WIDTH} columns, at once")
    chunk.set_aspect("auto")
    rows_drawn = 13
    for row in range(rows_drawn):
        for column in range(ACTION_WIDTH):
            chunk.add_patch(Rectangle((column, -row), 0.86, 0.78,
                                      facecolor=to_rgba(GLASS, 0.20 if row < rows_drawn - 2
                                                        else 0.07),
                                      edgecolor=MUTED, lw=0.5, zorder=3))
    for column, name in enumerate(ACTION_COLUMNS):
        chunk.text(column + 0.43, 1.0, name, fontsize=NOTE_SIZE - 0.6, color=INK, ha="left",
                   va="bottom", rotation=30)
    chunk.text(-0.35, -(rows_drawn - 1) / 2,
               f"{CHUNK} waypoints,\none every {WAYPOINT_PERIOD * 1000:.0f} ms:\n"
               f"{CHUNK * WAYPOINT_PERIOD:.0f} seconds of arm time", fontsize=NOTE_SIZE,
               color=INK, ha="right", va="center")
    chunk.text(ACTION_WIDTH / 2.0, -rows_drawn - 0.4,
               "predicted together in one forward pass, and carried out as given:\n"
               "nothing re-plans part way through, and nothing is read while it runs",
               fontsize=NOTE_SIZE, color=INK, ha="center", va="top")

    # The resampling, on its own little axis of waypoint counts.
    strip = chunk.inset_axes([0.0, 0.14, 1.0, 0.11])
    plain(strip, left=False)
    strip.set_ylim(0, 2.2)
    strip.set_xlim(0, COLLECTED["waypoints_most"] + 20)
    for count, name in (
        (COLLECTED["waypoints_least"], "shortest"),
        (COLLECTED["waypoints_median"], "median"),
        (COLLECTED["waypoints_most"], "longest"),
    ):
        strip.plot([count, count], [0.0, 0.55], color=MUTED, lw=1.2)
        # The median mark is right beside the chunk's own length, so its label
        # is hung to the left rather than centred on top of it.
        strip.text(count - (6 if count == COLLECTED["waypoints_median"] else 0), 0.62,
                   f"{name}\n{count}", fontsize=NOTE_SIZE - 0.8, color=MUTED,
                   ha="right" if count == COLLECTED["waypoints_median"] else "center",
                   va="bottom")
    strip.plot([CHUNK, CHUNK], [0.0, 1.5], color=GLASS, lw=1.6)
    strip.text(CHUNK + 6, 1.2, f"every one resampled to {CHUNK}", fontsize=NOTE_SIZE - 0.8,
               color=GLASS, ha="left", va="bottom")
    strip.text(0.5, -0.9, "waypoints the teacher's own push left after trimming",
               transform=strip.transAxes, fontsize=NOTE_SIZE, color=INK, ha="center", va="top")
    chunk.set_xlim(-3.1, ACTION_WIDTH + 0.4)
    chunk.set_ylim(-rows_drawn - 9.0, 2.6)
    under(figure, 1, 2,
          f"a chunk is a fixed shape, so every demonstration is resampled to {CHUNK} waypoints, "
          f"which is set near the median of the teacher's own pushes so that a typical one "
          f"replays at about the speed it was made at. A longer one is replayed quicker than it "
          f"was made. The heading is carried as a cosine and a sine, because an angle wraps and "
          f"a fitted wrap is a cliff.", width=92)

    footer(figure,
           f"The legs and their waypoint spacings are the examiner's own: the rate is fixed at one "
           f"waypoint every {WAYPOINT_PERIOD * 1000:.0f} ms, so a speed is a spacing — "
           f"{FEEL_STEP:.1f} mm while feeling, {PUSH_STEP:.1f} mm while pushing, "
           f"{STEP_CAP:.0f} mm coming down, which is also the cap follow() holds a chunk to. "
           f"Resampling the longest demonstration, {COLLECTED['waypoints_most']} waypoints, into "
           f"{CHUNK} replays it about {COLLECTED['waypoints_most'] / CHUNK:.1f} times quicker "
           f"than it was made and leaves its legs near "
           f"{COLLECTED['waypoints_most'] * PUSH_STEP / CHUNK:.1f} mm, still far inside the cap. "
           f"The drawn push is table {DEMO['table']:,}'s, measured: {DEMO['felt_forward']:.0f} mm "
           f"of feeling and {DEMO['travel']:.0f} mm of pushing.")
    figure.subplots_adjust(bottom=0.33, top=0.92, wspace=0.16)
    save(figure, "03-a-chunk-is-not-a-push.png")


# --------------------------------------------------------------------------- #
# 3. The measured failure: blocked on the way down.
# --------------------------------------------------------------------------- #
def picture_blocked(results: dict) -> dict:
    glasses = table(EXAMPLE["table"])
    theirs = one(glasses, EXAMPLE["teacher_glass"])
    their_start = fingertips(theirs, EXAMPLE["teacher_heading_deg"])
    ahead = unit(EXAMPLE["teacher_heading_deg"])
    their_end = (theirs["x"] + ahead[0] * EXAMPLE["teacher_travel"],
                 theirs["y"] + ahead[1] * EXAMPLE["teacher_travel"])
    first = EXAMPLE["waypoints"][0]
    gap, hit = gap_to_the_nearest_glass((first[0], first[1]), glasses)
    their_gap, _ = gap_to_the_nearest_glass(their_start, glasses)
    off_by = abs(first[3] - (EXAMPLE["teacher_heading_deg"] - 360.0))
    spread = results["spread"]

    figure, axes = new(13.6, 6.0, columns=3)
    good, bad, counted = axes

    good_jaw = jaw_corners(their_start, EXAMPLE["teacher_heading_deg"])
    bad_jaw = jaw_corners((first[0], first[1]), first[3])
    everything = (table_corners(glasses)
                  + [corner for block in good_jaw + bad_jaw for corner in block])
    for axis, title in ((good, f"The teacher's push, table {EXAMPLE['table']:,}"),
                        (bad, "The policy's chunk, same table, same picture")):
        stage(axis, title)
        zone(axis)
        draw_table(axis, glasses)
        # Room for the jaw, and for the names written under the lowest glass.
        frame_on(axis, everything, pad=34.0)

    jaw_from_above(good, their_start, EXAMPLE["teacher_heading_deg"], colour=GOOD, alpha=0.14)
    good.plot(*their_start, marker="o", ms=3.6, color=GOOD, zorder=9)
    good.annotate("", xy=their_end, xytext=their_start, zorder=8,
                  arrowprops={"arrowstyle": "-|>", "color": GOOD, "lw": 1.6})
    good.annotate(f"the fingertips come down\n{their_gap:.0f} mm clear of the rim",
                  xy=their_start, xytext=(30, 34), textcoords="offset points",
                  fontsize=NOTE_SIZE, color=GOOD, ha="left", va="bottom",
                  arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.7})
    under(figure, 0, 3,
          f"the fingertips come down behind glass {'ABCDEF'[EXAMPLE['teacher_glass']]}, "
          f"{APPROACH_GAP:.0f} mm clear of its widest part, where the geometry puts them by "
          f"construction. The jaw is {TOOL:.0f} mm long behind its fingertips and {BODY:.0f} mm "
          f"wide, and it clears every other glass along its whole path, because solution 1's "
          f"enumerator tested exactly that. Not blocked: the glass moves "
          f"{EXAMPLE['teacher_pushed']:.0f} mm.")

    jaw_from_above(bad, (first[0], first[1]), first[3], colour=WARN, alpha=0.16)
    bad.plot(first[0], first[1], marker="o", ms=3.6, color=WARN, zorder=9)
    hit_glass = one(glasses, hit)
    bad.add_patch(Circle((hit_glass["x"], hit_glass["y"]), hit_glass["widest"] / 2.0,
                         facecolor="none", edgecolor=WARN, lw=1.4, zorder=6))
    bad.annotate(f"the fingertips come down\n{abs(gap):.0f} mm inside glass "
                 f"{'ABCDEF'[hit]}'s rim", xy=(first[0], first[1]), xytext=(34, -40),
                 textcoords="offset points", fontsize=NOTE_SIZE, color=WARN, ha="left",
                 va="top", arrowprops={"arrowstyle": "-", "color": WARN, "lw": 0.7})
    under(figure, 1, 3,
          f"the chunk's first waypoint is where the jaw is brought down, and this one is inside "
          f"the glass it means to push. follow() stops the descent the moment the jaw touches "
          f"anything, so the chunk comes back blocked at {EXAMPLE['peak_newtons']:.1f} N with "
          f"nothing moved. The heading is {off_by:.0f}° off the teacher's, and "
          f"{EXAMPLE['pulled_in']} of its {CHUNK} waypoints had to be pulled inside the jaw's "
          f"limits.")

    counted.set_title("Every push of the held-out run, by what the jaw felt",
                      fontsize=LABEL_SIZE, color=INK, pad=8)
    blocked = spread["pushes.blocked_on_the_way_down"]["median"]
    never = spread["pushes.never_touched"]["median"]
    total = spread["pushes.total"]["median"]
    repeats = spread["pushes.repeats"]["median"]
    touched = total - blocked - never
    bars(counted,
         ["blocked coming down", "never touched anything", "touched a glass", "of all of them,\n"
          "pushes at a glass\nalready pushed"],
         [blocked, never, touched, repeats],
         [WARN, WARN, GOOD, MUTED],
         texts=[f"{blocked:,.0f}", f"{never:,.0f}", f"{touched:,.0f}",
                f"{repeats:,.0f} of {total:,.0f}"],
         room=0.85)
    under(figure, 2, 3,
          f"{total:,.0f} pushes over the {spread['scenes']['median']:.0f} held-out tables, the "
          f"median of three fitted seeds. The teacher spends "
          f"{TEACHER['pushes']['total']} on the same tables and is blocked on none of them. "
          f"{blocked / total * 100:.0f} per cent of these end before a glass is touched, so the "
          f"table does not change, so the next picture is the same picture and the next chunk is "
          f"the same chunk — until the push budget is spent.")

    footer(figure,
           f"The table is bench.scene({EXAMPLE['table']:,}) and both pushes are real. The "
           f"teacher's is the first push it made here, rebuilt from its glass, heading and "
           f"travel; the policy's is the first chunk seed {EXAMPLE['seed']} returned from this "
           f"table's own straight-down picture, as captured, and blocked is the examiner's own "
           f"verdict on it. Across all fifty held-out tables the first chunk is blocked on "
           f"{', '.join(str(row['blocked']) for row in FIRST_CHUNK['seeds'])} of "
           f"{FIRST_CHUNK['tables']} for the three seeds, against none of fifty for the teacher, "
           f"and the fingertips come down inside a glass on "
           f"{', '.join(str(row['inside_a_glass']) for row in FIRST_CHUNK['seeds'])} of them. The "
           f"other blocked descents are the long body of the jaw over a neighbour rather than "
           f"the fingertips over the target, which is the same check made further back along the "
           f"jaw.")
    figure.subplots_adjust(bottom=0.34, top=0.92, wspace=0.10)
    save(figure, "03-blocked-on-the-way-down.png")
    return {"gap": gap, "hit": hit, "their_gap": their_gap, "blocked": blocked, "total": total,
            "off_by": off_by}


# --------------------------------------------------------------------------- #
# 4. What one chunk commits to.
# --------------------------------------------------------------------------- #
def picture_inside_one_chunk() -> dict:
    points = [(p[0], p[1]) for p in EXAMPLE["waypoints"]] + [
        (EXAMPLE["last"][0], EXAMPLE["last"][1])]
    figure, axes = new(13.6, 5.6, columns=3)
    drawn, measured, pulled = axes

    stage(drawn, "Two chunks, drawn on the same scale")
    # Both laid out from the same starting point, the teacher's above the
    # policy's, so that the only difference on the page is the shape.
    origin = (0.0, 0.0)
    straight = [(origin[0] + step, origin[1] + 44.0)
                for step in (0.0, HELD_BACK["teacher_net_mm"])]
    drawn.plot([p[0] for p in straight], [p[1] for p in straight], color=GOOD, lw=1.6,
               marker="o", ms=2.6, zorder=5)
    note(drawn, straight[0][0], straight[0][1] + 9,
         fill(f"the teacher's, every one of them: "
              f"{HELD_BACK['teacher_path_mm']:.0f} mm of path for "
              f"{HELD_BACK['teacher_net_mm']:.0f} mm of displacement", 46),
         GOOD, ha="left", va="bottom")
    moved = [(p[0] - points[0][0], p[1] - points[0][1]) for p in points]
    drawn.plot([p[0] for p in moved], [p[1] for p in moved], color=WARN, lw=1.3, marker="o",
               ms=2.6, zorder=6)
    note(drawn, moved[0][0], min(p[1] for p in moved) - 9,
         fill(f"the policy's, on table {EXAMPLE['table']:,}: {EXAMPLE['path_mm']:.0f} mm of path "
              f"for {EXAMPLE['net_mm']:.0f} mm of displacement, drawn at every tenth waypoint, "
              f"which straightens out most of the wandering", 46),
         WARN, ha="left", va="top")
    bar_at = HELD_BACK["teacher_net_mm"] - 20.0
    drawn.plot([bar_at, bar_at + 20.0], [16.0, 16.0], color=INK, lw=1.4, zorder=5)
    note(drawn, bar_at + 10.0, 13.0, "20 mm", INK, va="top")
    drawn.set_xlim(-14, HELD_BACK["teacher_net_mm"] + 14)
    drawn.set_ylim(-78, 86)
    under(figure, 0, 3,
          "a push moves a glass because the jaw keeps going one way while in contact. The "
          "teacher's chunk does that and nothing else. The policy's wanders, and the wandering "
          "is inside one chunk — the place where chunking was supposed to make that impossible, "
          "because the waypoints were produced together.")

    chart(measured, "How far a chunk walks, and how far it gets")
    rows = [("the teacher", HELD_BACK["teacher_path_mm"], HELD_BACK["teacher_net_mm"], GOOD)]
    rows += [(f"seed {row['seed']}", row["path_mm"], row["net_mm"], WARN)
             for row in HELD_BACK["seeds"]]
    places = np.arange(len(rows))
    width = 0.36
    measured.bar(places - width / 2, [row[1] for row in rows], width, color=MUTED, zorder=3,
                 label="path walked")
    measured.bar(places + width / 2, [row[2] for row in rows], width,
                 color=[row[3] for row in rows], zorder=3, label="displacement reached")
    for place, row in zip(places, rows, strict=True):
        measured.text(place - width / 2, row[1] + 3, f"{row[1]:.0f}", fontsize=NOTE_SIZE - 0.6,
                      color=INK, ha="center", va="bottom")
        measured.text(place + width / 2, row[2] + 3, f"{row[2]:.0f}", fontsize=NOTE_SIZE - 0.6,
                      color=INK, ha="center", va="bottom")
    measured.set_xticks(places)
    measured.set_xticklabels([row[0] for row in rows], fontsize=NOTE_SIZE, color=INK)
    measured.set_ylabel("millimetres, median of 200 chunks", fontsize=NOTE_SIZE, color=INK)
    measured.set_ylim(0, max(row[1] for row in rows) * 1.22)
    measured.legend(loc="upper left", fontsize=NOTE_SIZE - 0.6, frameon=False, labelcolor=INK)
    under(figure, 1, 3,
          f"the same {HELD_BACK['chunks']} held-back demonstrations, asked of each fitted seed. "
          f"Every one of the teacher's chunks walks exactly as far as it gets, because a "
          f"parameterised push is a straight line. The policy's walk two to four times as far as "
          f"they get.")

    chart(pulled, "What had to be pulled inside the jaw's limits")
    worst = max(row["worst_z_mm"] for row in HELD_BACK["seeds"])
    pulled.axhspan(PUSH_HEIGHT - worst, PUSH_HEIGHT, facecolor=to_rgba(WARN, 0.16),
                   edgecolor="none", zorder=1)
    pulled.axhline(PUSH_HEIGHT, color=INK, lw=1.2, zorder=4)
    for row, place in zip(HELD_BACK["seeds"], (1, 2, 3), strict=True):
        pulled.plot([place, place], [PUSH_HEIGHT, PUSH_HEIGHT - row["worst_z_mm"]], color=WARN,
                    lw=2.6, solid_capstyle="butt", zorder=5)
        pulled.text(place, PUSH_HEIGHT - row["worst_z_mm"] - 0.06,
                    f"{row['worst_z_mm']:.2f} mm\n{row['pulled']} chunks\nof "
                    f"{HELD_BACK['chunks']}", fontsize=NOTE_SIZE - 0.6, color=WARN, ha="center",
                    va="top")
    pulled.set_xticks([1, 2, 3])
    pulled.set_xticklabels([f"seed {row['seed']}" for row in HELD_BACK["seeds"]],
                           fontsize=NOTE_SIZE, color=INK)
    pulled.set_xlim(0.4, 3.6)
    pulled.set_ylim(PUSH_HEIGHT - worst - 1.1, PUSH_HEIGHT + 0.45)
    pulled.set_yticks([PUSH_HEIGHT - 2.0, PUSH_HEIGHT - 1.0, PUSH_HEIGHT])
    pulled.set_ylabel("height of the middle of the jaw, mm", fontsize=NOTE_SIZE, color=INK)
    pulled.text(0.5, PUSH_HEIGHT + 0.06,
                f"push height, {PUSH_HEIGHT:.0f} mm: the lowest the jaw's middle goes",
                fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    under(figure, 2, 3,
          f"a network can put out any number, so every chunk is pulled inside what the jaw can "
          f"reach before it is followed, and how often is reported rather than hidden: "
          f"{PULLED_CHUNKS:,} of the {CHUNKS_ASKED:,} chunks the three runs produced. This panel "
          f"is the honest size of it. Every waypoint pulled in was pulled in on the height "
          f"column, by the amount shown, and not one of the "
          f"{len(HELD_BACK['seeds']) * HELD_BACK['chunks']} measured chunks put x or y outside "
          f"the table at all.")

    footer(figure,
           f"All three panels are measurements. The drawn paths are real: the teacher's median "
           f"chunk over the {HELD_BACK['chunks']} held-back demonstrations, and every tenth "
           f"waypoint of the chunk seed {EXAMPLE['seed']} returned on table "
           f"{EXAMPLE['table']:,}. A chunk that walks three times as far as it gets is what the "
           f"document's own section on mode averaging predicts of a model fitted to name one "
           f"answer where several would have been good, and the second rung — Diffusion Policy, "
           f"which draws its chunk rather than naming it — is the experiment that would say so. "
           f"It has not been fitted.")
    figure.subplots_adjust(bottom=0.33, top=0.92, wspace=0.24)
    save(figure, "03-inside-one-chunk.png")
    return {"net": EXAMPLE["net_mm"], "walked": EXAMPLE["path_mm"]}


# --------------------------------------------------------------------------- #
# 5. A low loss was not a good score.
# --------------------------------------------------------------------------- #
def picture_loss_is_not_the_score(results: dict) -> None:
    each = results["each"]
    shipped_loss = spread_of("loss", FITS)
    shipped_fitted = spread_of("fitted_mm", FITS)
    shipped_unseen = spread_of("unseen_mm", FITS)
    early = f"{EARLY_FIT['demonstrations']:,} demonstrations,\n{EARLY_FIT['passes']} passes"
    late = (f"{COLLECTED['kept']:,} demonstrations,\n"
            f"{round(FIT_STEPS * FIT_BATCH / COLLECTED['kept'])} passes")

    figure, axes = new(13.6, 5.6, columns=3)
    loss, distance, outcome = axes

    chart(loss, "What the fitting was minimising")
    loss.bar([0], [EARLY_FIT["loss"]], 0.5, color=WARN, zorder=3)
    loss.bar([1], [sum(shipped_loss) / 2], 0.5, color=GOOD, zorder=3)
    loss.errorbar([1], [sum(shipped_loss) / 2],
                  yerr=[[(shipped_loss[1] - shipped_loss[0]) / 2],
                        [(shipped_loss[1] - shipped_loss[0]) / 2]],
                  fmt="none", ecolor=INK, elinewidth=1.0, capsize=4, zorder=5)
    loss.text(0, EARLY_FIT["loss"] + 0.012, f"{EARLY_FIT['loss']:.2f}", fontsize=NOTE_SIZE,
              color=WARN, ha="center", va="bottom")
    loss.text(1, shipped_loss[1] + 0.012, f"{shipped_loss[0]:.2f} to {shipped_loss[1]:.2f}",
              fontsize=NOTE_SIZE, color=GOOD, ha="center", va="bottom")
    loss.set_xticks([0, 1])
    loss.set_xticklabels(["the first fit", "the fit it shipped"], fontsize=NOTE_SIZE, color=INK)
    loss.set_xlim(-0.6, 1.6)
    loss.set_ylim(0, shipped_loss[1] * 1.3)
    loss.set_ylabel("training loss at the end of the fit", fontsize=NOTE_SIZE, color=INK)
    under(figure, 0, 3, y=0.26, text=
          f"the first fit drove the loss to {EARLY_FIT['loss']:.2f}, which is "
          f"{shipped_loss[0] / EARLY_FIT['loss']:.0f} to "
          f"{shipped_loss[1] / EARLY_FIT['loss']:.0f} times lower than the fit this solution "
          f"shipped. On the quantity the fitting was actually minimising, the useless fit is the "
          f"clear winner.")

    chart(distance, "What the fitted chunk was worth")
    places = np.arange(2)
    width = 0.34
    distance.bar(places - width / 2, [EARLY_FIT["fitted_mm"], EARLY_FIT["unseen_mm"]], width,
                 color=WARN, zorder=3, label=early.replace("\n", " "))
    distance.bar(places + width / 2,
                 [sum(shipped_fitted) / 2, sum(shipped_unseen) / 2], width, color=GOOD, zorder=3,
                 label=late.replace("\n", " "))
    for place, span in enumerate((shipped_fitted, shipped_unseen)):
        distance.errorbar([place + width / 2], [sum(span) / 2],
                          yerr=[[(span[1] - span[0]) / 2], [(span[1] - span[0]) / 2]],
                          fmt="none", ecolor=INK, elinewidth=1.0, capsize=4, zorder=5)
    for place, (left, right) in enumerate((
        (f"{EARLY_FIT['fitted_mm']:.0f}", f"{shipped_fitted[0]:.0f} to {shipped_fitted[1]:.0f}"),
        (f"{EARLY_FIT['unseen_mm']:.0f}", f"{shipped_unseen[0]:.0f} to {shipped_unseen[1]:.0f}"),
    )):
        distance.text(place - width / 2,
                      (EARLY_FIT["fitted_mm"] if place == 0 else EARLY_FIT["unseen_mm"]) + 1.6,
                      left, fontsize=NOTE_SIZE, color=WARN, ha="center", va="bottom")
        distance.text(place + width / 2,
                      (shipped_fitted[1] if place == 0 else shipped_unseen[1]) + 1.6, right,
                      fontsize=NOTE_SIZE, color=GOOD, ha="center", va="bottom")
    distance.set_xticks(places)
    distance.set_xticklabels(["on tables it was fitted on", "on tables it never saw"],
                             fontsize=NOTE_SIZE, color=INK)
    distance.set_ylabel("millimetres from the teacher's chunk, per waypoint", fontsize=NOTE_SIZE,
                        color=INK)
    distance.set_ylim(0, max(shipped_unseen[1], EARLY_FIT["unseen_mm"]) * 1.35)
    distance.legend(loc="upper left", fontsize=NOTE_SIZE - 0.8, frameon=False, labelcolor=INK)
    under(figure, 1, 3, y=0.26, text=
          f"the first fit was memorising: {EARLY_FIT['fitted_mm']:.0f} mm from the teacher on "
          f"tables it had seen and {EARLY_FIT['unseen_mm']:.0f} mm on tables it had not. Four "
          f"times the demonstrations removed the memorising and left the error on unseen tables "
          f"where it was. That is the number a push has to live with.")

    chart(outcome, "And what happened on the table")
    losses = [fit["loss"] for fit in FITS]
    racked = [run["glasses_end"]["racked"] for run in each]
    toppled = [run["glasses_end"]["toppled"] for run in each]
    outcome.scatter(losses, racked, s=42, color=GLASS, zorder=5)
    for fit, score, fell in zip(FITS, racked, toppled, strict=True):
        outcome.annotate(f"seed {fit['seed']}: {score} racked, {fell} toppled",
                         xy=(fit["loss"], score), xytext=(0, 13 if fell else -18),
                         textcoords="offset points", fontsize=NOTE_SIZE - 0.6, color=INK,
                         ha="center")
        if fell:
            outcome.scatter([fit["loss"]], [score], s=42 + 30 * fell, facecolor="none",
                            edgecolor=WARN, lw=1.2, zorder=6)
    outcome.axhline(TEACHER["glasses_end"]["racked"], color=GOOD, lw=1.0, ls=(0, (4, 3)),
                    zorder=2)
    outcome.text(max(losses), TEACHER["glasses_end"]["racked"] - 4,
                 f"the teacher: {TEACHER['glasses_end']['racked']} racked, none toppled",
                 fontsize=NOTE_SIZE, color=GOOD, ha="right", va="top")
    outcome.set_xlim(min(losses) - 0.04, max(losses) + 0.04)
    outcome.set_ylim(min(racked) - 14, TEACHER["glasses_end"]["racked"] + 16)
    outcome.set_xlabel("training loss at the end of the fit", fontsize=NOTE_SIZE, color=INK)
    outcome.set_ylabel(f"glasses racked, of {each[0]['glasses']}", fontsize=NOTE_SIZE, color=INK)
    under(figure, 2, 3,
          "the three shipped seeds, scored on the fifty held-out tables. The ring is how many "
          "glasses that seed knocked over. The seed that fitted closest racked the most and "
          "toppled the most, which is not a contradiction: a closer fit makes the pushes real, "
          "and a real push on a crowded table is the only thing here that can knock a glass "
          "over.")

    footer(figure,
           "The losses and the two distances are weights/act-training.json's, written by "
           "train.py; the racked and toppled counts are results.json's, written by run.py over "
           "the fifty held-out tables; the teacher's line is 02-geometry-ranked/results.json. "
           "The first fit's four numbers are this folder's README, which recorded them and "
           "threw the weights away, so they are quoted rather than re-measured. The distance "
           "from the teacher is a training diagnostic and not the score: it says how unlike the "
           "teacher's chunk this chunk is, while the score says what happened to the table. A "
           "solution marked on either of the first two panels would have preferred the fit that "
           "cleared nothing.")
    figure.subplots_adjust(bottom=0.33, top=0.92, wspace=0.30)
    save(figure, "03-the-loss-was-not-the-score.png")


# --------------------------------------------------------------------------- #
# The checks, and everything the document may quote.
# --------------------------------------------------------------------------- #
def check_the_examples(demo: dict, blocked: dict) -> None:
    """The rebuilt pushes against what the examiner recorded, and the path's own arithmetic."""
    assert math.dist(demo["start"], DEMO["start"]) < REBUILD_TOLERANCE, (
        f"the rebuilt fingertips {demo['start']} are not where the examiner recorded them "
        f"{DEMO['start']}")
    glasses = table(EXAMPLE["table"])
    their_start = fingertips(one(glasses, EXAMPLE["teacher_glass"]),
                             EXAMPLE["teacher_heading_deg"])
    assert math.dist(their_start, EXAMPLE["teacher_start"]) < REBUILD_TOLERANCE, (
        f"the rebuilt fingertips {their_start} are not where the examiner recorded them "
        f"{EXAMPLE['teacher_start']}")
    assert demo["at_push_height"] == DEMO["at_push_height"], (
        f"{demo['at_push_height']} waypoints at push height, and the examiner recorded "
        f"{DEMO['at_push_height']}")
    assert demo["kept"] == DEMO["kept"], (
        f"push_segment would keep {demo['kept']}, and it kept {DEMO['kept']}")
    assert abs(demo["net"] - DEMO["net"]) < REBUILD_TOLERANCE, (
        f"the rebuilt push travels {demo['net']:.1f} mm and the recorded one {DEMO['net']}")
    assert blocked["gap"] < 0.0, "the drawn chunk is supposed to come down inside a glass"
    print("checks passed: both worked pushes rebuild to what the examiner recorded")


def report(results: dict, demo: dict, blocked: dict, chunk: dict) -> None:
    spread = results["spread"]
    print("\nwhat the document may quote from these pictures")
    print(f"  the demonstration set: {COLLECTED['pushes']:,} pushes on "
          f"{COLLECTED['tables']:,} tables, {COLLECTED['kept']:,} kept, "
          f"{DROPPED_REAL} of {REAL_PUSHES:,} real pushes dropped "
          f"({100 * DROPPED_REAL / REAL_PUSHES:.1f} per cent)")
    print(f"  table {DEMO['table']:,}: {demo['feeling']} waypoints feeling at "
          f"{FEEL_STEP:.1f} mm, {demo['pushing']} pushing at {PUSH_STEP:.1f} mm, "
          f"{demo['backing']} backing off; {demo['kept']} kept of "
          f"{DEMO['waypoints']} recorded")
    print(f"  a chunk is {CHUNK} waypoints by {ACTION_WIDTH} columns, "
          f"{CHUNK * WAYPOINT_PERIOD:.0f} seconds of arm time; the teacher's own pushes run "
          f"{COLLECTED['waypoints_least']} to {COLLECTED['waypoints_most']} waypoints, median "
          f"{COLLECTED['waypoints_median']}")
    print(f"  table {EXAMPLE['table']:,}: the teacher comes down "
          f"{blocked['their_gap']:.1f} mm clear of the rim, the policy "
          f"{abs(blocked['gap']):.1f} mm inside glass {'ABCDEF'[blocked['hit']]}, "
          f"{blocked['off_by']:.0f} degrees off the teacher's heading")
    print(f"  the run: {blocked['total']:,.0f} pushes, {blocked['blocked']:,.0f} blocked coming "
          f"down ({100 * blocked['blocked'] / blocked['total']:.0f} per cent), "
          f"{spread['pushes.never_touched']['median']:,.0f} never touched anything, "
          f"{spread['pushes.repeats']['median']:,.0f} repeats")
    print(f"  the first chunk on each held-out table is blocked on "
          f"{[row['blocked'] for row in FIRST_CHUNK['seeds']]} of {FIRST_CHUNK['tables']}, "
          f"against {FIRST_CHUNK['teacher']['blocked']} for the teacher")
    print(f"  the drawn chunk walks {chunk['walked']:.0f} mm to get {chunk['net']:.0f} mm away; "
          f"the teacher's chunks walk {HELD_BACK['teacher_path_mm']:.0f} for "
          f"{HELD_BACK['teacher_net_mm']:.0f}")
    print(f"  pulled inside the limits: {PULLED_CHUNKS:,} of {CHUNKS_ASKED:,} chunks, every one "
          f"of them the height column, at most "
          f"{max(r['worst_z_mm'] for r in HELD_BACK['seeds']):.2f} mm below push height")
    print(f"  the fits: loss {EARLY_FIT['loss']:.2f} for the first against "
          f"{spread_of('loss', FITS)[0]:.2f}–{spread_of('loss', FITS)[1]:.2f} for the shipped "
          f"one, and {EARLY_FIT['unseen_mm']:.0f} mm from the teacher on unseen tables against "
          f"{spread_of('unseen_mm', FITS)[0]:.0f}–{spread_of('unseen_mm', FITS)[1]:.0f}")
    print(f"  the seeds: losses {[fit['loss'] for fit in FITS]}, racked "
          f"{[run['glasses_end']['racked'] for run in results['each']]}, toppled "
          f"{[run['glasses_end']['toppled'] for run in results['each']]}; the teacher racks "
          f"{TEACHER['glasses_end']['racked']} and topples "
          f"{TEACHER['glasses_end']['toppled']}")


def main() -> None:
    results = json.loads(RESULTS.read_text())
    print(f"table {DEMO['table']:,} and table {EXAMPLE['table']:,}, from the examiner's own "
          f"generator")
    for seed in (DEMO["table"], EXAMPLE["table"]):
        glasses = table(seed)
        crowded = [g["id"] for g in glasses if not g["room"]]
        print(f"  {seed:,}: {len(glasses)} glasses, {len(crowded)} without room "
              f"{[chr(65 + i) for i in crowded]}")

    demo = picture_the_demonstrations()
    picture_a_chunk_is_not_a_push(demo)
    blocked = picture_blocked(results)
    chunk = picture_inside_one_chunk()
    picture_loss_is_not_the_score(results)
    check_the_examples(demo, blocked)
    report(results, demo, blocked, chunk)


if __name__ == "__main__":
    main()
