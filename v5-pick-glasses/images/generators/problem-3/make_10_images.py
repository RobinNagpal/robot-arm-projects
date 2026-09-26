"""Diagrams for solution 10 — learn a forward model, then plan against it.

Five pictures, and every number printed as it is drawn so that the document can
quote it rather than guess it.

Three rules were kept while writing this.

**Every glass is a real glass.** Its rim, its foot and its height come from
``work_cell.glasses.shapes``, drawn inside ``KIND_RANGES["tapered_glass"]`` by
the project's own ``family`` and ``random_glasses``. No size is typed in.

**Every arrangement is a real layout**, in the sense that the positions come
from ``random_glasses``, which places glasses one at a time wherever the ones
already down leave room. It has to be crowded afterwards, and that is the
awkward part worth stating in the open: ``spawn.MIN_SEPARATION`` is 150 mm and
no pair is ever closer, while a glass loses its room somewhere below 123 mm, so
**the shipped spawner cannot produce a crowded table at all.** The crowding
here is made by sliding a glass in along the line towards a neighbour until the
pair sits between having the room the jaw needs and touching, which is what
``problem-3-sim/bench.py`` does to its own tables. Every picture that uses a
crowded table says so.

The authoritative crowded-table generator is ``bench.scene``, not this file.
It is not imported here because it imports MuJoCo, which this project's root
environment does not carry, and every generator in this repository has to run
from the root. What ``bench`` was measured for instead is written down as the
``BENCH_*`` constants below, with the script that produced them named.

**Whether a glass has room is the asymmetric test**, ``diagram_style.has_room``:
a neighbour's *edge* has to be outside 70 mm of this glass's middle, so what
decides is how wide the neighbour is. The round 140 mm in ``problem.md`` is the
worst case of that, for two of the widest glasses the kind allows.

**Nothing here is a trained model's output.** There is no model in this file.
Where a picture needs a prediction, the prediction is a stand-in stated in the
caption: the glass slides the full length of the push along the push, and the
error between prediction and outcome is the 4.5 mm median that
``problem-3-learned``'s README records for its own model on unseen tables.

    pixi run python images/generators/problem-3/make_10_images.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from diagram_style import (
    GLASS,
    GLASS_ZONE,
    GOOD,
    GRIP_ROOM,
    GRIPPABLE_APART,
    INK,
    JAW_TOP,
    LABEL_SIZE,
    LOWEST_GRIP,
    MU_HIGH,
    MU_LOW,
    MUTED,
    NOTE_SIZE,
    TABLE_FRICTION,
    WARN,
    bare,
    glass_from_above,
    glass_from_the_side,
    grippable,
    has_room,
    in_reach,
    in_zone,
    new,
    push_arrow,
    pushable,
    save,
    topple_height,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import family  # noqa: E402
from work_cell.glasses.spawn import MIN_SEPARATION, random_glasses  # noqa: E402

PROJECT = Path(__file__).resolve().parents[3]

# How far in a glass is slid to crowd it, as a fraction of the way from having
# the room the jaw needs to touching its neighbour. problem-3-sim/bench.py
# draws uniformly across that whole span; half way in is the middle of it, and
# it leaves a pair that is clearly crowded and clearly not touching.
CROWD_PART = 0.5

# How far inside the zone's edge a glass is aimed, because it will not land
# exactly where it was aimed. problem-3-learned/plan.py uses 12 mm.
ZONE_MARGIN = 12.0

# The search, as problem-3-learned/plan.py runs it: draws per round, how many
# of the best are kept to aim the next round, and rounds.
DRAWS, ELITES, ROUNDS = 300, 30, 4

# How far a push may travel, from problem-3-learned/features.py TRAVEL.
TRAVEL_RANGE = (10.0, 100.0)

# Each millimetre of push costs this much of a millimetre of missing room, so
# the shortest push that does the job wins. plan.py TRAVEL_COST.
TRAVEL_COST = 0.1

# What problem-3-learned's README records for its own model on tables it was
# not trained on: the pushed glass lands this far from where the model said it
# would, median. It is train.py's ``landing_mm_median``, printed at the end of
# a training run; it is in that README and nowhere else, and it was not
# re-derived here, because the training data is not kept in the repository.
MEASURED_ONE_PUSH_ERROR = 4.5

# The same question asked of the geometry, which predicts a slide instead of
# learning one: how far from its aim a pushed glass really stopped. Measured
# here, by running problem-3-programmed's planner over bench tables 10100 to
# 10349 and comparing every push's ``aim`` with the simulator's record of where
# the glass landed. 564 pushes that ran their full length, median 1.07 mm,
# 3.00 mm at the ninetieth percentile, 34.40 mm at worst. The throwaway script
# is measure_programmed.py; re-run it from problem-3-programmed.
MEASURED_GEOMETRY_ERROR = 1.07

# What that README records about the training set. These are read here rather
# than recomputed, because collecting them again takes a physics engine this
# environment does not have.
ROUND_ONE = (4_000, 24_759)      # tables, pushes
ROUND_TWO = (5_000, 13_253)
PUSHES_PER_TABLE = 12            # problem-3-learned/collect.py

# Measured against problem-3-sim/bench.py, which is the crowded-table generator
# and the physics for this whole problem. It imports MuJoCo, which is not in
# this project's root environment, so the measurements were taken by a
# throwaway script run from problem-3-learned (which has MuJoCo) over the first
# 300 seeds whose kind is the tapered glass — that is, seed % 4 == 1 — and the
# numbers are written here rather than recomputed. Re-measure by building a
# Bench and timing Bench.push on those seeds.
BENCH_TABLES = 300
BENCH_GLASSES = 1_500
BENCH_WITHOUT_ROOM = 1_083       # 72.2 per cent, 3.61 a table, between 1 and 6
BENCH_BUILD_MS = 5.0             # building one table's model
BENCH_PUSH_MS = 78.0             # one push, median, one core
BENCH_PUSH_STEPS = 4_331         # physics steps in that push, median
BENCH_PUSH_SECONDS = 8.66        # what those steps are, as simulated time

RESULTS = PROJECT / "problem-3-learned" / "results.json"


# --------------------------------------------------------------------------- #
# Glasses, and tables to stand them on.
# --------------------------------------------------------------------------- #
def measured(glass) -> dict:
    """One spawned glass as the four numbers problem 2 hands over, in millimetres."""
    outline = glass.outline
    rim = outline.max_diameter * 1000.0
    foot = 2.0 * float(outline.radius[0]) * 1000.0
    return {
        "x": glass.position[0] * 1000.0,
        "y": glass.position[1] * 1000.0,
        "rim": rim,
        "foot": foot,
        "fraction": foot / rim,
        "height": outline.total_height * 1000.0,
    }


def table(count: int, seed: int) -> list[dict]:
    """A real layout of ``count`` tapered glasses, in millimetres."""
    return [measured(g) for g in random_glasses(count, seed, kinds=["tapered_glass"])]


def points(glasses: list[dict]) -> list[tuple[float, float]]:
    return [(g["x"], g["y"]) for g in glasses]


def moved(glasses: list[dict], index: int, where: tuple[float, float]) -> list[dict]:
    out = [dict(g) for g in glasses]
    out[index]["x"], out[index]["y"] = where
    return out


def needs(glass: dict, neighbour: dict) -> float:
    """How far apart two glasses' middles have to be before ``glass`` can be gripped.

    The open jaw needs GRIP_ROOM clear of the glass's middle, and what has to
    be outside that is the *neighbour's* edge, so the answer depends on how
    wide the neighbour is and not on how wide this glass is. That asymmetry is
    the project's own test, in diagram_style.has_room; the round 140 mm in
    problem.md is the worst case of it, for two of the widest glasses the kind
    allows.
    """
    return GRIP_ROOM + neighbour["rim"] / 2.0


def both_need(a: dict, b: dict) -> float:
    """How far apart two glasses have to be before *either* can be gripped."""
    return max(needs(a, b), needs(b, a))


def has_its_room(glasses: list[dict], index: int, where: tuple[float, float] | None = None) -> bool:
    """Whether one glass has the room the jaw needs, at its place or at ``where``."""
    here = where or (glasses[index]["x"], glasses[index]["y"])
    return has_room(here, [(g["x"], g["y"], g["rim"]) for k, g in enumerate(glasses) if k != index])


def crowded_glasses(glasses: list[dict]) -> list[int]:
    """Every glass on the table that cannot be picked up where it stands."""
    return [i for i in range(len(glasses)) if not has_its_room(glasses, i)]


def pull_closest_pair(glasses: list[dict], part: float) -> tuple[list[dict], tuple[int, int]]:
    """Slide the closest pair together until neither can be gripped, moving one glass.

    ``part`` says how far in, as a fraction of the way from having room to
    touching. The spawner leaves at least 150 mm between centres, so a table it
    produces has nothing to push; this is the smallest change that turns one
    into a problem-3 table. One glass slides straight in towards its nearest
    neighbour, so its distance to everything else only grows.
    """
    spans = [
        (math.dist((a["x"], a["y"]), (b["x"], b["y"])), i, j)
        for i, a in enumerate(glasses)
        for j, b in enumerate(glasses)
        if i < j
    ]
    _, i, j = min(spans)
    here, anchor = glasses[i], glasses[j]
    room, touch = both_need(here, anchor), (here["rim"] + anchor["rim"]) / 2.0 + 5.0
    gap = room - part * (room - touch)
    span = math.dist((here["x"], here["y"]), (anchor["x"], anchor["y"]))
    unit = ((here["x"] - anchor["x"]) / span, (here["y"] - anchor["y"]) / span)
    return moved(glasses, i, (anchor["x"] + unit[0] * gap, anchor["y"] + unit[1] * gap)), (i, j)


def pull_every_glass(glasses: list[dict], rng: random.Random) -> list[dict]:
    """Crowd a whole table, the way problem-3-sim/bench.py crowds its own.

    Each glass after the first is slid in towards one already placed until the
    pair sits between touching and having room. A slide that would put two
    glasses through each other, or outside the zone, is abandoned and the glass
    stays where the spawner put it.
    """
    out = [dict(glasses[0])]
    for glass in glasses[1:]:
        anchor = out[rng.randrange(len(out))]
        span = math.dist((glass["x"], glass["y"]), (anchor["x"], anchor["y"]))
        touch = (glass["rim"] + anchor["rim"]) / 2.0 + 5.0
        gap = rng.uniform(touch, both_need(glass, anchor))
        unit = ((glass["x"] - anchor["x"]) / span, (glass["y"] - anchor["y"]) / span)
        where = (anchor["x"] + unit[0] * gap, anchor["y"] + unit[1] * gap)
        through = any(
            math.dist(where, (o["x"], o["y"])) < (glass["rim"] + o["rim"]) / 2.0 + 5.0 for o in out
        )
        if through or not in_zone(where, ZONE_MARGIN):
            out.append(dict(glass))
            continue
        out.append({**glass, "x": where[0], "y": where[1]})
    return out


def worst_gap(glasses: list[dict]) -> float:
    """The closest two glasses on the table are, between centres."""
    spots = points(glasses)
    return min(math.dist(a, b) for i, a in enumerate(spots) for j, b in enumerate(spots) if i < j)


# --------------------------------------------------------------------------- #
# The stand-in for a forward model, and the search that uses it.
#
# There is no trained model in this file. Everything below is the *mechanism*:
# what a search against a model does with the answers it gets. The stand-in
# prediction is the simplest one that is not a lie about the geometry — the
# glass slides the length of the push, along the push — and every picture that
# leans on it says so.
# --------------------------------------------------------------------------- #
def predict(glass: dict, heading: float, travel: float) -> tuple[float, float]:
    """Where the stand-in says the pushed glass ends up."""
    return (glass["x"] + travel * math.cos(heading), glass["y"] + travel * math.sin(heading))


def room_missing(glasses: list[dict]) -> float:
    """How much room the table is short of, in millimetres, summed over every glass.

    Each neighbour whose edge is inside a glass's GRIP_ROOM adds how far inside
    it is. Zero when every glass can be gripped. This is the shortfall
    problem-3-learned/plan.py minimises, written out here.
    """
    return sum(
        max(0.0, needs(a, b) - math.dist((a["x"], a["y"]), (b["x"], b["y"])))
        for i, a in enumerate(glasses)
        for j, b in enumerate(glasses)
        if i != j
    )


def allowed(glasses: list[dict], index: int, where: tuple[float, float]) -> bool:
    """The hard constraints, which are arithmetic and come before the model.

    Inside the zone with a margin, inside the arm's comfortable reach, the
    moved glass has the room the jaw needs once it is there, and no glass that
    already had room loses it. Moving one glass out of a crowd and into a
    different crowd is the mistake the last of those prevents. A candidate that
    fails any of them is gone before it is scored.
    """
    if not in_zone(where, ZONE_MARGIN) or not in_reach(where):
        return False
    after = moved(glasses, index, where)
    if not has_its_room(after, index):
        return False
    return all(
        has_its_room(after, k)
        for k in range(len(after))
        if k != index and has_its_room(glasses, k)
    )


def search(glasses: list[dict], index: int, rng: np.random.Generator) -> dict:
    """The cross-entropy method over (heading, travel), against the stand-in.

    Draw candidates from a broad Gaussian, throw away the ones the arithmetic
    refuses, score the rest by the room still missing plus a small cost per
    millimetre pushed, keep the best ELITES, refit the Gaussian to those, and
    draw again. The record it returns is what the pictures are drawn from.
    """
    glass = glasses[index]
    nearest = min(
        (g for k, g in enumerate(glasses) if k != index),
        key=lambda g: math.dist((g["x"], g["y"]), (glass["x"], glass["y"])),
    )
    away = math.atan2(glass["y"] - nearest["y"], glass["x"] - nearest["x"])
    mean = np.array([away, sum(TRAVEL_RANGE) / 2.0])
    spread = np.array([math.pi, (TRAVEL_RANGE[1] - TRAVEL_RANGE[0]) / 2.0])

    rounds = []
    for _ in range(ROUNDS):
        draws = rng.normal(mean, spread, size=(DRAWS, 2))
        draws[:, 1] = np.clip(draws[:, 1], *TRAVEL_RANGE)
        kept, dropped = [], []
        for heading, travel in draws:
            where = predict(glass, float(heading), float(travel))
            if allowed(glasses, index, where):
                after = moved(glasses, index, where)
                kept.append((room_missing(after) + TRAVEL_COST * float(travel), float(heading),
                             float(travel), where))
            else:
                dropped.append((float(heading), float(travel), where))
        if not kept:
            break
        kept.sort(key=lambda row: row[0])
        elite = kept[:ELITES]
        rounds.append({"kept": kept, "dropped": dropped, "elite": elite})
        mean = np.array([np.mean([e[1] for e in elite]), np.mean([e[2] for e in elite])])
        spread = np.maximum(
            np.array([np.std([e[1] for e in elite]), np.std([e[2] for e in elite])]),
            np.array([0.02, 1.0]),
        )
    best = rounds[-1]["elite"][0]
    return {"rounds": rounds, "cost": best[0], "heading": best[1], "travel": best[2], "aim": best[3]}


# --------------------------------------------------------------------------- #
# One push at a time, against a pair of pushes planned together.
# --------------------------------------------------------------------------- #
HEADINGS = np.linspace(0.0, 2.0 * math.pi, 36, endpoint=False)
TRAVELS = np.arange(TRAVEL_RANGE[0], TRAVEL_RANGE[1] + 1.0, 10.0)

# Two glasses cannot be pushed within this of each other, whatever the plan:
# the widest tapered glass is 105 mm across, so this leaves daylight.
NO_CLOSER = 110.0


def possible_pushes(glasses: list[dict], index: int) -> list[tuple[float, float, tuple[float, float]]]:
    """Every push of this glass the arm could physically make and would not regret.

    In the zone, in reach, and not into another glass. It does *not* require
    the glass to end up with room, which is the difference that matters below.
    """
    others = [(g["x"], g["y"]) for k, g in enumerate(glasses) if k != index]
    out = []
    for heading in HEADINGS:
        for travel in TRAVELS:
            where = predict(glasses[index], float(heading), float(travel))
            if not in_zone(where, ZONE_MARGIN) or not in_reach(where):
                continue
            if any(math.dist(where, o) < NO_CLOSER for o in others):
                continue
            out.append((float(heading), float(travel), where))
    return out


def one_at_a_time(glasses: list[dict], limit: int = 8) -> list[tuple[int, tuple[float, float]]]:
    """Solution 3's loop, written out: give one crowded glass room, then look again.

    At each step it considers only the glasses that are crowded, keeps the
    destinations that leave the moved glass with full room, and takes the
    shortest push among them. Then it measures the table again and repeats.
    Returns the pushes it made, or an empty list if it had to refuse.
    """
    here = [dict(g) for g in glasses]
    made = []
    for _ in range(limit):
        if not crowded_glasses(here):
            return made
        crowded = set(crowded_glasses(here))
        best = None
        for index in crowded:
            for _heading, travel, where in possible_pushes(here, index):
                if not allowed(here, index, where):
                    continue
                if best is None or travel < best[0]:
                    best = (travel, index, where)
        if best is None:
            return []
        _, index, where = best
        here = moved(here, index, where)
        made.append((index, where))
    return []


def planned_pair(glasses: list[dict]) -> tuple[list[tuple[int, tuple[float, float]]], float] | None:
    """The shortest two pushes that between them leave every glass grippable.

    Neither push has to leave the glass it moved with room. Only the pair of
    them has to finish the table, and working that out needs to know where the
    first push lands — which is what a forward model is for.
    """
    best = None
    for index, travel, where in (
        (i, t, w) for i in range(len(glasses)) for _h, t, w in possible_pushes(glasses, i)
    ):
        first = moved(glasses, index, where)
        for other, travel_two, where_two in (
            (k, t, w) for k in range(len(first)) for _h, t, w in possible_pushes(first, k)
        ):
            second = moved(first, other, where_two)
            if crowded_glasses(second):
                continue
            total = travel + travel_two
            if best is None or total < best[1]:
                best = ([(index, where), (other, where_two)], total)
    return best


# --------------------------------------------------------------------------- #
# Drawing helpers.
# --------------------------------------------------------------------------- #
def stage(axis, title: str) -> None:
    bare(axis)
    axis.set_aspect("equal")
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)


def note(axis, x, y, text, colour=MUTED, **kwargs) -> None:
    kwargs.setdefault("ha", "center")
    axis.text(x, y, text, fontsize=NOTE_SIZE, color=colour, clip_on=True, **kwargs)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.012, text, fontsize=NOTE_SIZE, color=INK, ha="center")


def under(figure, column: int, columns: int, text: str, y: float = 0.295) -> None:
    """A note beneath one panel, clear of everything drawn inside it."""
    figure.text((column + 0.5) / columns, y, text, fontsize=NOTE_SIZE, color=INK,
                ha="center", va="top")


def zone(axis, label: bool = True) -> None:
    """The rectangle the glasses may stand in, and the margin inside its edge."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                             facecolor=to_rgba(MUTED, 0.06), edgecolor=MUTED, lw=1.0, zorder=0))
    axis.add_patch(Rectangle((x_from + ZONE_MARGIN, y_from + ZONE_MARGIN),
                             x_to - x_from - 2 * ZONE_MARGIN, y_to - y_from - 2 * ZONE_MARGIN,
                             facecolor="none", edgecolor=MUTED, lw=0.8, ls=(0, (2, 3)), zorder=0))
    if label:
        note(axis, (x_from + x_to) / 2, y_to + 26, "the glass zone, 320 by 360 mm", MUTED)


def draw_table(axis, glasses: list[dict], names: bool = True, faded: bool = False,
               rings: list[int] | None = None) -> None:
    """Every glass from above, with its foot, and a name beside it."""
    for index, glass in enumerate(glasses):
        glass_from_above(axis, (glass["x"], glass["y"]), glass["rim"], glass["fraction"],
                         alpha=0.14 if faded else 0.30, zorder=3)
        if names:
            axis.text(glass["x"], glass["y"] - glass["rim"] / 2 - 16, "ABCDEF"[index],
                      fontsize=NOTE_SIZE, color=MUTED if faded else INK, ha="center", va="top",
                      clip_on=True)
    for index in rings or []:
        axis.add_patch(Circle((glasses[index]["x"], glasses[index]["y"]), GRIP_ROOM,
                              facecolor="none", edgecolor=WARN, lw=1.1, ls=(0, (4, 3)), zorder=2))


def frame_on(axis, glasses: list[dict], pad: float = 46.0) -> None:
    """Fit the panel round every glass, its rim included, plus a margin."""
    axis.set_xlim(min(g["x"] - g["rim"] / 2 for g in glasses) - pad,
                  max(g["x"] + g["rim"] / 2 for g in glasses) + pad)
    axis.set_ylim(min(g["y"] - g["rim"] / 2 for g in glasses) - pad - 22,
                  max(g["y"] + g["rim"] / 2 for g in glasses) + pad)


def frame_close(axis, centre: tuple[float, float], half: float) -> None:
    """A square window of ``half`` millimetres either side of a point."""
    axis.set_xlim(centre[0] - half, centre[0] + half)
    axis.set_ylim(centre[1] - half, centre[1] + half)


def gap_line(axis, a: dict, b: dict, colour: str, above: float = 0.0) -> float:
    """Draw the distance between two glasses' middles, and return it."""
    span = math.dist((a["x"], a["y"]), (b["x"], b["y"]))
    axis.annotate("", xy=(a["x"], a["y"]), xytext=(b["x"], b["y"]),
                  arrowprops={"arrowstyle": "<->", "color": colour, "lw": 1.0}, zorder=7)
    axis.text((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2 + above + 6, f"{span:.0f} mm",
              fontsize=NOTE_SIZE, color=colour, ha="center", va="bottom", zorder=8,
              bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.0})
    return span


# --------------------------------------------------------------------------- #
# The example table every picture but the last two is drawn on.
# --------------------------------------------------------------------------- #
def can_be_pushed(glass: dict, mu: float = TABLE_FRICTION) -> bool:
    """Whether this glass has any height the jaw can reach and still slide it.

    The height that matters is the jaw's *top* edge, not the middle of it. A
    tapered glass is wider higher up, so it meets the top edge of the 30 mm jaw
    before it meets the middle, and that is where the push is applied.
    """
    return pushable(glass["foot"], mu, JAW_TOP)


def example_table() -> tuple[int, list[dict], list[dict], tuple[int, int]]:
    """A five-glass layout crowded into exactly one pair, one of which can be pushed.

    "Can be pushed" is asked at the simulator's own friction, which is the
    honest test even though the arm does not know that number: a worked example
    whose glass tips before it slides would be a worked example of a refusal.
    """
    for seed in range(400):
        glasses = table(5, seed)
        crowded, pair = pull_closest_pair(glasses, CROWD_PART)
        if sorted(crowded_glasses(crowded)) != sorted(pair):
            continue
        movable = [i for i in pair if can_be_pushed(crowded[i])]
        if not movable:
            continue
        other = next(i for i in pair if i != movable[0])
        return seed, glasses, crowded, (movable[0], other)
    raise RuntimeError("no five-glass layout crowded into one pair with a pushable glass in it")


# --------------------------------------------------------------------------- #
# 1. What a forward model takes in, and what it gives back.
# --------------------------------------------------------------------------- #
def picture_what_it_predicts(seed: int, crowded: list[dict], pair: tuple[int, int]) -> dict:
    index = pair[0]
    first, second = ("ABCDEF"[pair[0]], "ABCDEF"[pair[1]])
    glass = crowded[index]
    rng = np.random.default_rng(10)
    plan = search(crowded, index, rng)
    landing = predict(glass, plan["heading"], plan["travel"])
    after = moved(crowded, index, landing)
    middle = ((crowded[pair[0]]["x"] + crowded[pair[1]]["x"]) / 2,
              (crowded[pair[0]]["y"] + crowded[pair[1]]["y"]) / 2)
    close = 110.0

    figure, axes = new(13.4, 5.9, columns=3)
    state, action, result = axes

    stage(state, "In: the table, as the camera measured it")
    zone(state)
    draw_table(state, crowded, rings=list(pair))
    frame_on(state, crowded)
    span = gap_line(state, crowded[pair[0]], crowded[pair[1]], WARN)
    room = both_need(crowded[pair[0]], crowded[pair[1]])
    under(figure, 0, 3,
          f"five glasses, four numbers each: where it stands,\n"
          f"how wide at the rim, how wide at the foot.\n"
          f"{span:.0f} mm between {first} and {second}, where the jaw needs {room:.0f} —\n"
          f"70 mm clear of one middle, with the wider of the\n"
          f"two rims outside that. So neither can be picked up")

    stage(action, f"In: one push on {first}, as three numbers")
    draw_table(action, crowded, faded=True)
    glass_from_above(action, (glass["x"], glass["y"]), glass["rim"], glass["fraction"], alpha=0.30)
    reach = (glass["x"] - math.cos(plan["heading"]) * (glass["rim"] / 2 + 34),
             glass["y"] - math.sin(plan["heading"]) * (glass["rim"] / 2 + 34))
    touch = (glass["x"] - math.cos(plan["heading"]) * glass["rim"] / 2,
             glass["y"] - math.sin(plan["heading"]) * glass["rim"] / 2)
    push_arrow(action, reach, touch, INK)
    note(action, reach[0], reach[1] - 16, "the jaw comes down here", INK, va="top")
    push_arrow(action, (glass["x"], glass["y"]), landing, GOOD, lw=1.8)
    note(action, landing[0], landing[1] + glass["rim"] / 2 + 8,
         f"{plan['travel']:.0f} mm at {math.degrees(plan['heading']):.0f}°", GOOD, va="bottom")
    frame_close(action, middle, close)
    under(figure, 1, 3,
          f"which glass, which way and how far. The jaw feels forward until it\n"
          f"touches, so where it meets the glass is not a fourth number.\n"
          f"Drawn closer than the panel on the left: this window is {2 * close:.0f} mm across")

    stage(result, "Out: the table afterwards")
    draw_table(result, crowded, names=False, faded=True)
    draw_table(result, after, rings=[])
    push_arrow(result, (glass["x"], glass["y"]), (after[index]["x"], after[index]["y"]), GOOD, lw=1.8)
    note(result, crowded[pair[1]]["x"], crowded[pair[1]]["y"] + crowded[pair[1]]["rim"] / 2 + 8,
         "0 mm", GOOD, va="bottom")
    frame_close(result, middle, close)
    new_span = gap_line(result, after[pair[0]], after[pair[1]], GOOD)
    under(figure, 2, 3,
          f"a displacement for every glass on the table — {second} and the three out of shot\n"
          f"do not move — and two yes-or-no answers: did anything topple, was the jaw\n"
          f"blocked coming down. The pair ends {new_span:.0f} mm apart, past the {room:.0f} mm it needs")

    footer(figure,
           "The push and the two tables are real geometry on a real layout. The displacement in the "
           "third panel is NOT a trained model's output: it is the stand-in this script uses, which "
           "slides the glass\nthe full length of the push along the push. What the panel illustrates "
           "is the shape of the question a forward model answers — one table and one push in, one "
           "table out —\nnot how accurately any model answers it.")
    figure.subplots_adjust(bottom=0.36, top=0.93, wspace=0.10)
    save(figure, "10-what-a-forward-model-predicts.png")
    print(f"  crowded pair {first}{second} at {span:.1f} mm -> {new_span:.1f} mm (seed {seed})")
    print(f"  push: heading {math.degrees(plan['heading']):.1f} deg, travel {plan['travel']:.1f} mm")
    return plan


def picture_planning(crowded: list[dict], pair: tuple[int, int], plan: dict) -> None:
    index = pair[0]
    name = "ABCDEF"[index]
    glass = crowded[index]
    first, last = plan["rounds"][0], plan["rounds"][-1]

    figure, axes = new(13.4, 5.9, columns=3)
    wide, narrow, done = axes

    stage(wide, f"Round 1: {DRAWS} candidate pushes")
    zone(wide, label=False)
    draw_table(wide, crowded, faded=True)
    for _heading, _travel, where in first["dropped"]:
        wide.plot(*where, marker="x", ms=3.4, mew=0.9, color=WARN, zorder=4)
    for _cost, _heading, _travel, where in first["kept"]:
        wide.plot(*where, marker="o", ms=2.8, color=GLASS, zorder=5)
    frame_on(wide, crowded, pad=115.0)
    under(figure, 0, 3,
          f"each mark is where the push would leave glass {name}.\n"
          f"{len(first['dropped'])} of the {DRAWS} are struck out by arithmetic before\n"
          f"the model is asked: outside the zone, outside the arm's\n"
          f"reach, or too close to another glass")

    stage(narrow, f"Round {ROUNDS}: the best {ELITES} of the {DRAWS}")
    zone(narrow, label=False)
    draw_table(narrow, crowded, faded=True)
    for _cost, _heading, _travel, where in last["kept"]:
        narrow.plot(*where, marker="o", ms=2.8, color=GLASS, alpha=0.45, zorder=4)
    for _cost, _heading, _travel, where in last["elite"]:
        narrow.plot(*where, marker="o", ms=4.0, color=GOOD, zorder=5)
    frame_on(narrow, crowded, pad=115.0)
    elite_spread = max(math.dist(a[3], b[3]) for a in last["elite"] for b in last["elite"])
    under(figure, 1, 3,
          f"the draws have collapsed onto one spot {elite_spread:.0f} mm across.\n"
          f"The score is the room still missing on the table, plus\n"
          f"{TRAVEL_COST:.1f} mm of penalty per millimetre pushed, so the\n"
          f"shortest push that clears the pair wins")

    # The worst direction for the error to go: straight back towards the
    # neighbour the push was trying to get away from.
    landing = plan["aim"]
    towards = crowded[pair[1]]
    span_aimed = math.dist(landing, (towards["x"], towards["y"]))
    real = (landing[0] + MEASURED_ONE_PUSH_ERROR * (towards["x"] - landing[0]) / span_aimed,
            landing[1] + MEASURED_ONE_PUSH_ERROR * (towards["y"] - landing[1]) / span_aimed)
    stage(done, "How far out each kind of prediction is")
    for step in (1, 2, 3):
        radius = step * MEASURED_ONE_PUSH_ERROR
        done.add_patch(Circle((0, 0), radius, facecolor="none", edgecolor=WARN, lw=1.1,
                              ls=(0, (2, 2)), zorder=6))
        along = math.radians(118.0)
        done.text((radius + 0.6) * math.cos(along), (radius + 0.6) * math.sin(along),
                  f"{radius:.1f} mm", fontsize=NOTE_SIZE - 0.6, color=WARN, ha="right",
                  va="bottom", zorder=8)
    done.add_patch(Circle((0, 0), MEASURED_GEOMETRY_ERROR, facecolor=to_rgba(GOOD, 0.75),
                          edgecolor=GOOD, lw=1.0, zorder=7))
    done.plot(0, 0, marker="+", ms=10, mew=1.3, color=MUTED, zorder=8)
    done.annotate("", xy=(-MEASURED_GEOMETRY_ERROR * 0.7, -MEASURED_GEOMETRY_ERROR * 0.7),
                  xytext=(-6.0, -5.0),
                  arrowprops={"arrowstyle": "->", "color": GOOD, "lw": 0.8}, zorder=8)
    note(done, -2.6, -9.0, f"{MEASURED_GEOMETRY_ERROR:.2f} mm:\nthe geometry,\nno model at all",
         GOOD, ha="right", va="top")
    note(done, 0, 19.5, "+ is where the push was aimed", MUTED, va="bottom")
    frame_close(done, (0.0, 0.0), 23.0)

    neighbour = (crowded[pair[1]]["x"], crowded[pair[1]]["y"])
    span = math.dist(real, neighbour)
    aimed = math.dist(landing, neighbour)
    room = both_need(crowded[pair[0]], crowded[pair[1]])
    under(figure, 2, 3,
          f"the push aimed to leave {name} {aimed:.1f} mm from {'ABCDEF'[pair[1]]}, where the jaw "
          f"needs {room:.1f}.\nWith the learned model's median error in the worst direction it "
          f"lands\n{span:.1f} — {room - span:.1f} mm short, and the next survey has to catch that. "
          f"With the\ngeometry's it lands {aimed - MEASURED_GEOMETRY_ERROR:.1f}, which still has "
          f"room to spare. The glass is\n{glass['rim']:.0f} mm across and the window is "
          f"{2 * 23.0:.0f}, so the panel is drawn very close")

    footer(figure,
           f"The candidates, the filter and the scoring are the real search: {DRAWS} draws a round, "
           f"best {ELITES} kept, {ROUNDS} rounds, as problem-3-learned/plan.py runs it. The "
           f"{MEASURED_ONE_PUSH_ERROR:.1f} mm offset in\nthe third panel is the median one-push error "
           f"that project's README records for its own model on unseen tables. The three rings are an "
           f"illustration\nof why the horizon is one push: if that error simply added up, a plan "
           f"rolled three deep would start step three {3 * MEASURED_ONE_PUSH_ERROR:.1f} mm out. "
           f"Measuring again after every push sets it\nback to zero, which is what makes a mediocre "
           f"model useful — and the green disc is what the geometry, which predicts a slide instead "
           f"of learning one, does\nwithout a model at all: {MEASURED_GEOMETRY_ERROR:.2f} mm, "
           f"re-measured here over 564 pushes on 250 tables of this project's own bench.")
    figure.subplots_adjust(bottom=0.36, top=0.93, wspace=0.10)
    save(figure, "10-planning-against-the-model.png")
    print(f"  round 1: {len(first['kept'])} kept, {len(first['dropped'])} dropped of {DRAWS}")
    print(f"  round {ROUNDS}: {len(last['kept'])} kept, elite {len(last['elite'])}, "
          f"best cost {plan['cost']:.1f}")
    print(f"  landing aimed ({landing[0]:.1f}, {landing[1]:.1f}), reached ({real[0]:.1f}, {real[1]:.1f}), "
          f"pair {span:.1f} mm")


# --------------------------------------------------------------------------- #
# 3. The number the model absorbs rather than measures.
# --------------------------------------------------------------------------- #
def picture_friction(draws: int = 400, seed: int = 11) -> None:
    drawn = family("tapered_glass", draws, seed)
    feet = np.array([2.0 * float(o.radius[0]) * 1000.0 for o, _ in drawn])
    rims = np.array([o.max_diameter * 1000.0 for o, _ in drawn])
    heights = np.array([o.total_height * 1000.0 for o, _ in drawn])
    share_low = float(np.mean([pushable(f, MU_LOW, JAW_TOP) for f in feet]))
    share_high = float(np.mean([pushable(f, MU_HIGH, JAW_TOP) for f in feet]))
    share_true = float(np.mean([pushable(f, TABLE_FRICTION, JAW_TOP) for f in feet]))
    middle_low = float(np.mean([pushable(f, MU_LOW, LOWEST_GRIP) for f in feet]))
    middle_true = float(np.mean([pushable(f, TABLE_FRICTION, LOWEST_GRIP) for f in feet]))
    middle_high = float(np.mean([pushable(f, MU_HIGH, LOWEST_GRIP) for f in feet]))

    widest, narrowest = int(np.argmax(feet)), int(np.argmin(feet))

    figure, axes = new(12.6, 5.9, columns=2)
    side, spread = axes

    stage(side, f"The window a push has to fit into, at μ = {TABLE_FRICTION}")
    gap = 250.0
    for column, which in enumerate((widest, narrowest)):
        slot = column * gap
        glass_from_the_side(side, slot, heights[which], rims[which], feet[which] / rims[which],
                            alpha=0.18)
        top = topple_height(feet[which], TABLE_FRICTION)
        usable = top > JAW_TOP
        colour = GOOD if usable else WARN
        if usable:
            side.add_patch(Rectangle((slot - 74, JAW_TOP), 148, top - JAW_TOP,
                                     facecolor=to_rgba(GOOD, 0.22), edgecolor="none", zorder=4))
        side.plot([slot - 74, slot + 74], [top, top], color=colour, lw=1.4, zorder=5)
        side.text(slot, top + (7 if usable else -7), f"tips above {top:.0f} mm",
                  fontsize=NOTE_SIZE, color=colour, ha="center",
                  va="bottom" if usable else "top")
        side.text(slot, -30, f"foot {feet[which]:.0f} mm across", fontsize=NOTE_SIZE, color=INK,
                  ha="center", va="top")
        side.text(slot, -80, f"{top - JAW_TOP:.0f} mm of room" if usable else "no safe height",
                  fontsize=NOTE_SIZE, color=colour, ha="center", va="top")
        side.text(slot, -118,
                  f"{top - LOWEST_GRIP:.0f} mm at the middle" if top > LOWEST_GRIP
                  else "none at the middle either",
                  fontsize=NOTE_SIZE, color=MUTED, ha="center", va="top")
    side.axhline(LOWEST_GRIP, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=6)
    side.axhline(JAW_TOP, color=INK, lw=1.3, zorder=6)
    side.text(-230, JAW_TOP + 10, f"{JAW_TOP:.0f} mm: the jaw's top edge,\nwhich a glass that is "
              f"wider\nhigher up meets first", fontsize=NOTE_SIZE, color=INK, ha="center",
              va="bottom")
    side.text(-230, LOWEST_GRIP - 10, f"{LOWEST_GRIP:.0f} mm: its middle",
              fontsize=NOTE_SIZE, color=MUTED, ha="center", va="top")
    side.set_xlim(-360, gap + 130)
    side.set_ylim(-190, max(heights[widest], heights[narrowest]) + 40)

    stage(spread, f"Every one of {draws} drawn glasses")
    spread.set_aspect("auto")
    order = np.argsort(feet)
    line = np.linspace(feet.min(), feet.max(), 200)
    bands = (
        (MU_LOW, GOOD, f"μ = {MU_LOW}, the optimistic guess", share_low),
        (TABLE_FRICTION, INK, f"μ = {TABLE_FRICTION}, what the simulator uses", share_true),
        (MU_HIGH, WARN, f"μ = {MU_HIGH}, the pessimistic guess", share_high),
    )
    for mu, colour, label, _share in bands:
        spread.plot(line, [topple_height(f, mu) for f in line], color=colour, lw=1.6)
        spread.text(feet.max(), topple_height(feet.max(), mu), f" {label}", fontsize=NOTE_SIZE,
                    color=colour, va="center")
        spread.plot(feet[order], [topple_height(f, mu) for f in feet[order]], ls="none",
                    marker="o", ms=2.2, color=colour, alpha=0.40)
    spread.axhline(LOWEST_GRIP, color=MUTED, lw=1.0, ls=(0, (4, 3)))
    spread.text(feet.max(), LOWEST_GRIP - 2, f"the jaw's middle, {LOWEST_GRIP:.0f} mm ",
                fontsize=NOTE_SIZE, color=MUTED, va="top", ha="right")
    spread.axhline(JAW_TOP, color=INK, lw=1.3)
    spread.text(feet.max(), JAW_TOP + 2, f"the jaw's top edge, {JAW_TOP:.0f} mm ",
                fontsize=NOTE_SIZE, color=INK, va="bottom", ha="right")
    spread.set_xlabel("width of the foot the glass stands on, mm", fontsize=NOTE_SIZE, color=INK)
    spread.set_ylabel("height at which a push stops sliding and tips, mm", fontsize=NOTE_SIZE, color=INK)
    spread.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for which in ("top", "right"):
        spread.spines[which].set_visible(False)
    for which in ("left", "bottom"):
        spread.spines[which].set_visible(True)
        spread.spines[which].set_color(MUTED)
    spread.set_xticks(np.arange(25, feet.max() + 5, 10))
    note(spread, (feet.min() + feet.max()) / 2 - 4, topple_height(feet.max(), MU_LOW) * 0.99,
         f"how many can be pushed at all, at the jaw's top edge:\n"
         f"{share_low * 100:.1f}% at μ = {MU_LOW},  {share_true * 100:.1f}% at μ = {TABLE_FRICTION},"
         f"  {share_high * 100:.1f}% at μ = {MU_HIGH}\n"
         f"fifteen millimetres lower it would be {middle_low * 100:.1f}%, "
         f"{middle_true * 100:.1f}% and {middle_high * 100:.1f}%", INK, va="top")

    footer(figure,
           f"The dividing line is h < a / μ: half the foot's width over the friction with the table. "
           f"Two unmeasured things decide it. The arm never measures μ, and between the two guesses "
           f"the share\nof these glasses that may be pushed at all moves from "
           f"{share_low * 100:.1f}% to {share_high * 100:.1f}%. And the height h is the jaw's top "
           f"edge rather than its middle, because a tapered glass is wider higher up and\nmeets the "
           f"top edge first; that fifteen millimetres alone takes the μ = {MU_LOW} share from "
           f"{middle_low * 100:.1f}% to {share_low * 100:.1f}%. A written-down push model gets that "
           f"wrong until somebody notices the jaw\nis 30 mm tall. A model fitted to real pushes "
           f"absorbs it without anybody noticing — and leaves it in the weights, where nobody can "
           f"read it back out again.")
    figure.subplots_adjust(bottom=0.27, top=0.93, wspace=0.18)
    save(figure, "10-the-friction-it-absorbs.png")
    print(f"  {draws} drawn tapered glasses, seed {seed}: feet {feet.min():.1f}-{feet.max():.1f} mm, "
          f"median {np.median(feet):.1f} mm")
    print(f"  pushable at the jaw's top edge ({JAW_TOP:.0f} mm): {share_low * 100:.1f}% at "
          f"mu={MU_LOW}, {share_true * 100:.1f}% at mu={TABLE_FRICTION}, {share_high * 100:.1f}% "
          f"at mu={MU_HIGH}")
    print(f"  at the jaw's middle ({LOWEST_GRIP:.0f} mm) it would be {middle_low * 100:.1f}%, "
          f"{middle_true * 100:.1f}% and {middle_high * 100:.1f}%")
    return share_low, share_high


# --------------------------------------------------------------------------- #
# 4. What the data costs.
# --------------------------------------------------------------------------- #
def picture_the_data(crowded: list[dict]) -> None:
    results = json.loads(RESULTS.read_text())
    scenes = results["scenes"]
    run_pushes = results["pushes"]["total"]
    per_run = run_pushes / scenes
    rows = ROUND_ONE[1] + ROUND_TWO[1]
    runs_needed = rows / per_run

    figure, axes = new(12.6, 6.0, columns=2)
    training, real = axes
    rng = random.Random(4)

    stage(training, f"One training table gives up to {PUSHES_PER_TABLE} pushes")
    zone(training, label=False)
    draw_table(training, crowded, names=False, faded=True)
    here = [dict(g) for g in crowded]
    chain = 0
    for _ in range(PUSHES_PER_TABLE * 4):
        if chain >= PUSHES_PER_TABLE:
            break
        index = rng.randrange(len(here))
        options = possible_pushes(here, index)
        if not options:
            continue
        _heading, _travel, where = options[rng.randrange(len(options))]
        push_arrow(training, (here[index]["x"], here[index]["y"]), where, GLASS, lw=1.2)
        here = moved(here, index, where)
        chain += 1
    draw_table(training, here, names=False)
    frame_on(training, crowded, pad=90.0)
    under(figure, 0, 2,
          f"the table is built and settled once. The state after one push starts the next,\n"
          f"so {chain} examples share one reset. Nothing has to be useful: a push into a\n"
          f"neighbour is as good a row as a push that helps")

    made = one_at_a_time(crowded)
    stage(real, f"One real run of this table gives {len(made)}")
    zone(real, label=False)
    draw_table(real, crowded, faded=True)
    here = [dict(g) for g in crowded]
    for index, where in made:
        real.add_patch(Circle((here[index]["x"], here[index]["y"]), here[index]["rim"] / 2 + 16,
                              facecolor="none", edgecolor=GOOD, lw=1.2, zorder=6))
        push_arrow(real, (here[index]["x"], here[index]["y"]), where, GOOD, lw=1.8)
        here = moved(here, index, where)
    draw_table(real, here, names=False)
    frame_on(real, crowded, pad=90.0)
    under(figure, 1, 2,
          f"a run stops as soon as every glass has room, so it makes as few pushes as it can.\n"
          f"Over the {scenes} held-out tables problem-3-learned was scored on, {run_pushes} pushes "
          f"were made\nin all: {per_run:.2f} a table, and each one costs a survey and a plan")

    core_minutes = rows * BENCH_PUSH_MS / 1000.0 / 60.0
    real_time_hours = rows * BENCH_PUSH_SECONDS / 3600.0
    footer(figure,
           f"The two panels are the same table. Training pushes are cheap because the reset is "
           f"amortised and no push has to be a good one; run-time pushes are scarce because a run "
           f"makes as few\nas it can. The learned pipeline in this repository was fitted to "
           f"{ROUND_ONE[1]:,} pushes on {ROUND_ONE[0]:,} tables and then {ROUND_TWO[1]:,} more on "
           f"{ROUND_TWO[0]:,}: {rows:,} rows. At {per_run:.2f} rows a run, gathering that from\n"
           f"ordinary runs would take about {runs_needed:,.0f} of them. One push in this project's "
           f"own physics takes {BENCH_PUSH_MS:.0f} ms on one core, so the same {rows:,} rows cost "
           f"{core_minutes:.0f} core-minutes there —\nagainst {real_time_hours:.0f} hours if the same "
           f"pushes ran at the speed they happen, which is what a simulator of the arm would cost.")
    figure.subplots_adjust(bottom=0.36, top=0.93, wspace=0.14)
    save(figure, "10-the-data-it-takes.png")
    print(f"  results.json: {scenes} tables, {run_pushes} pushes, {per_run:.2f} a table")
    print(f"  training rows {rows:,}; runs to gather them at run-time rate: {runs_needed:,.0f}")
    print(f"  at the measured {BENCH_PUSH_MS:.0f} ms a push: {core_minutes:.0f} core-minutes, "
          f"{core_minutes / 8:.1f} minutes across eight; at real time {real_time_hours:.0f} hours")
    print(f"  one simulated push is {BENCH_PUSH_STEPS:,} steps = {BENCH_PUSH_SECONDS:.2f} s, so the "
          f"physics runs {BENCH_PUSH_SECONDS / (BENCH_PUSH_MS / 1000.0):.0f} times faster than real time")
    print(f"  one-at-a-time on the example table: {len(made)} pushes")
    return {"scenes": scenes, "run_pushes": run_pushes, "per_run": per_run, "rows": rows,
            "runs_needed": runs_needed, "core_minutes": core_minutes, "results": results}


# --------------------------------------------------------------------------- #
# 5. Where planning a sequence beats pushing one at a time.
# --------------------------------------------------------------------------- #
def picture_a_sequence(count: int = 4, seed: int = 9) -> None:
    glasses = pull_every_glass(table(count, seed), random.Random(seed))
    greedy = one_at_a_time(glasses)
    pair = planned_pair(glasses)
    if pair is None:
        raise RuntimeError(f"no two-push plan for seed {seed}")
    plan, plan_travel = pair
    greedy_travel = 0.0
    here = [dict(g) for g in glasses]
    for index, where in greedy:
        greedy_travel += math.dist((here[index]["x"], here[index]["y"]), where)
        here = moved(here, index, where)

    figure, axes = new(12.6, 6.0, columns=2)
    one, two = axes

    ends = {}
    for axis, title, pushes in ((one, f"One at a time: {len(greedy)} pushes", greedy),
                                (two, f"Planned together: {len(plan)} pushes", plan)):
        stage(axis, title)
        zone(axis, label=False)
        draw_table(axis, glasses, faded=True)
        here = [dict(g) for g in glasses]
        for step, (index, where) in enumerate(pushes, start=1):
            colour = WARN if axis is one else GOOD
            push_arrow(axis, (here[index]["x"], here[index]["y"]), where, colour, lw=1.8)
            midway = ((here[index]["x"] + where[0]) / 2, (here[index]["y"] + where[1]) / 2)
            axis.text(midway[0] + 9, midway[1] + 9, str(step), fontsize=NOTE_SIZE, color=colour,
                      ha="left", va="bottom", zorder=8)
            here = moved(here, index, where)
        draw_table(axis, here, names=False)
        frame_on(axis, glasses, pad=80.0)
        ends[axis] = here
    assert not crowded_glasses(ends[one]) and not crowded_glasses(ends[two])

    under(figure, 0, 2,
          f"every glass has room afterwards, for {greedy_travel:.0f} mm of pushing in all.\n"
          f"Each push has to leave the glass it moved with full room by itself, so this rule\n"
          f"never makes a push whose only value is what it allows the next one to do")
    under(figure, 1, 2,
          f"every glass has room afterwards, for {plan_travel:.0f} mm of pushing in all.\n"
          f"Neither push has to finish anything on its own. Choosing the second one needs\n"
          f"to know where the first one lands, which is exactly what a forward model gives")

    footer(figure,
           f"A real four-glass layout, crowded by sliding each glass in towards a neighbour until the "
           f"pair is somewhere between having the room the jaw needs and touching. All four start "
           f"without room.\nPushing one at a time takes {len(greedy)} pushes and "
           f"{greedy_travel:.0f} mm; the best pair of pushes takes {len(plan)} and "
           f"{plan_travel:.0f} mm. The whole prize is {len(greedy) - len(plan)} pushes.\n"
           f"It is worth having only where a push costs something — a cost this cell does not have, "
           f"because a push here is cheap and the run finishes either way.")
    figure.subplots_adjust(bottom=0.36, top=0.93, wspace=0.14)
    save(figure, "10-when-a-sequence-beats-one-at-a-time.png")
    print(f"  sequence table: {count} glasses, seed {seed}, worst gap {worst_gap(glasses):.1f} mm, "
          f"crowded {crowded_glasses(glasses)}")
    print(f"  one at a time: {len(greedy)} pushes, {greedy_travel:.1f} mm; "
          f"planned pair: {len(plan)} pushes, {plan_travel:.1f} mm")
    return {"greedy": len(greedy), "greedy_travel": greedy_travel, "planned": len(plan),
            "planned_travel": plan_travel}


# --------------------------------------------------------------------------- #
# The measurements the document quotes but does not draw.
# --------------------------------------------------------------------------- #
def measure_the_spawner(runs: int = 400) -> None:
    """How crowded a table the shipped spawner can produce. The answer is none."""
    crowded_runs = 0
    nearest = []
    for seed in range(runs):
        glasses = table(4 + seed % 3, seed)
        spots = points(glasses)
        crowded_runs += bool(crowded_glasses(glasses))
        for i, here in enumerate(spots):
            nearest.append(min(math.dist(here, there) for j, there in enumerate(spots) if j != i))
    nearest = np.array(nearest)
    print(f"  {runs} spawned tables of 4 to 6 tapered glasses: {crowded_runs} with any pair under "
          f"{GRIPPABLE_APART:.0f} mm")
    print(f"  nearest neighbour: min {nearest.min():.1f} mm, median {np.median(nearest):.1f} mm "
          f"(MIN_SEPARATION is {MIN_SEPARATION * 1000:.0f} mm)")


def measure_when_a_sequence_pays(runs: int = 200) -> None:
    """How often one push at a time runs out of options on a crowded table."""
    tally = {"one": 0, "two": 0, "three or more": 0, "refused": 0}
    for seed in range(runs):
        glasses = pull_every_glass(table(4 + seed % 3, seed), random.Random(seed))
        if not crowded_glasses(glasses):
            continue
        made = one_at_a_time(glasses)
        if not made:
            tally["refused"] += 1
        elif len(made) == 1:
            tally["one"] += 1
        elif len(made) == 2:
            tally["two"] += 1
        else:
            tally["three or more"] += 1
    total = sum(tally.values())
    print(f"  {total} crowded tables, pushing one at a time: " +
          ", ".join(f"{name} {count}" for name, count in tally.items()))
    return tally, total


def main() -> None:
    seed, spawned, crowded, pair = example_table()
    print(f"the example table: seed {seed}, closest pair {pair}, "
          f"{worst_gap(spawned):.1f} mm before crowding, {worst_gap(crowded):.1f} mm after")
    for index, glass in enumerate(crowded):
        print(f"  {'ABCDEF'[index]}: ({glass['x']:.1f}, {glass['y']:.1f}) rim {glass['rim']:.1f} mm, "
              f"foot {glass['foot']:.1f} mm, {glass['height']:.1f} mm tall, "
              f"tips above {topple_height(glass['foot'], MU_LOW):.0f} mm at mu={MU_LOW} and "
              f"{topple_height(glass['foot'], TABLE_FRICTION):.0f} mm at mu={TABLE_FRICTION}; "
              f"pushable at the jaw's top edge: {pushable(glass['foot'], MU_LOW, JAW_TOP)} / "
              f"{pushable(glass['foot'], TABLE_FRICTION, JAW_TOP)}")
    spots = points(crowded)
    apart = sum(1 for i in range(5) for j in range(i + 1, 5) if grippable(spots[i], spots[j]))
    print(f"  grippable pairs at the start: {apart} of 10")

    plan = picture_what_it_predicts(seed, crowded, pair)
    picture_planning(crowded, pair, plan)
    picture_friction()
    picture_the_data(crowded)
    picture_a_sequence()
    measure_the_spawner()
    measure_when_a_sequence_pays()


if __name__ == "__main__":
    main()
