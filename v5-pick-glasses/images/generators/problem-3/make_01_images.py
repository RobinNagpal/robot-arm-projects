"""Diagrams for solution 1 — do not drag at all.

Every glass drawn here is one the project's own spawner drew, at a position the
spawner chose, and every rim and foot is measured off that glass's outline
rather than typed in. That matters more in this document than in most, because
the whole argument is about *which* glasses on a particular table are already
grippable, and a picture drawn with invented sizes could be made to say either
answer.

The script also prints every number the document quotes. Run it from the project
root:

    pixi run python images/generators/problem-3/make_01_images.py
"""

from __future__ import annotations

import math
import random
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from diagram_style import (
    GLASS,
    GLASS_ZONE,
    GOOD,
    GRIP_ROOM,
    GRIPPABLE_APART,
    INK,
    LABEL_SIZE,
    LOWEST_GRIP,
    MU_HIGH,
    MU_LOW,
    MUTED,
    NOTE_SIZE,
    PAPER,
    TITLE_SIZE,
    WARN,
    bare,
    crowded_pairs,
    glass_from_above,
    glass_from_the_side,
    grip_ring,
    grippable,
    in_reach,
    new,
    push_arrow,
    pushable,
    room_around,
    save,
    topple_height,
)
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses import spawn  # noqa: E402
from work_cell.glasses.shapes import KIND_RANGES, family  # noqa: E402

# How many seeds each sweep runs, and at how many glasses. The problem allows
# four to six.
SEEDS = 500
COUNTS = (4, 5, 6)

# The four kinds, in the order problem-3-sim/bench.py cycles them.
KINDS = ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass")

# The top edge of the closed jaw, 65 mm above the table: bench.py builds it from
# the gripper's own declared finger height, and a glass that flares out above
# the fingertips meets the jaw here rather than at LOWEST_GRIP. A gripper
# dimension, not a glass one.
JAW_TOP = 65.0

# The two guesses this problem brackets with, and the value the simulator
# actually gives the table. Nothing tells the arm which it is.
BENCH_FRICTION = 0.35
FRICTIONS = (MU_LOW, BENCH_FRICTION, MU_HIGH)

# The level view, from the cell's own description: 380 mm back from the glass,
# and nine places on the circle round it, 40 degrees apart.
STANDOFF = 380.0
DIRECTIONS = tuple(40.0 * step for step in range(9))

# The floor this document lowers the spawner to when it needs a crowded table.
# It is the widest rim the kind is drawn at, so two glasses may end up touching
# and can never end up overlapping. Taken from the kind's declared range, which
# is a rule about what may be drawn rather than any glass's size.
TOUCHING_FLOOR = KIND_RANGES["tapered_glass"]["rim_diameter"][1]

# What the peel is actually worth, measured on the bench's own crowded tables
# by problem-3-programmed/measure_peel.py over bench.scene seeds 10000-10999 —
# the held-out half of the scene space — using bench.has_room as the test.
#
# They are copied here rather than computed, because bench.py imports MuJoCo and
# this environment does not have it. Nothing in here is a glass measurement:
# every entry is a count of scenes or of glasses.
BENCH = {
    "seeds": (10_000, 10_999),
    "scenes": 1000,
    "glasses": 5000,
    "without_room": 3731,              # glasses with no room at the start
    "closest": (54.2, 86.7, 121.1),    # closest pair per scene: min, median, max, mm
    "emptied": 36,                     # scenes the peel cleared on its own
    "residue": 712,                    # scenes where it racked some and left the rest
    "nothing_free": 252,               # scenes where nothing qualified at all
    "rounds": {0: 252, 1: 634, 2: 111, 3: 3},
    "residues": {0: 36, 1: 0, 2: 186, 3: 218, 4: 299, 5: 189, 6: 72},
    "pairs_before": 4.05,              # pairs inside GRIPPABLE_APART, per scene
    "pairs_after": 3.21,
    "racked": 1401,                    # glasses racked with no push aimed at them
    "left": 3599,
    "picks": 1.40,                     # free picks per scene
    "disagreed": 0,                    # scenes where a random pick order changed the residue
    "unpushable": {0.3: 48, 0.35: 185, 0.5: 1311},   # of the 3599 left
    # The same sweep with the 5 mm take margin problem-3-programmed/run.py
    # applies, which is three standard deviations of the measurement error in
    # the gap between two glasses.
    "margin": {"racked": 1073, "emptied": 8, "nothing_free": 338, "cascades": 36},
}

# The two tables walked through in the document, as (count, seed).
CASCADE = (4, 2)
STALL = (4, 8)


# --------------------------------------------------------------------------- #
# What problem 2 hands over, and what this solution does with it
# --------------------------------------------------------------------------- #

def seen(glass) -> dict:
    """One glass as problem 2 reports it: where it stands, how wide, how tall.

    Millimetres, because every other number in these documents is. The rim is
    the flattened disc — the widest part dropped straight down — because that is
    what the gripper has to get round. The base is the foot it stands on, which
    is what decides whether a push slides it or tips it, and the two are not the
    same circle.
    """
    return {
        "at": (glass.position[0] * 1000.0, glass.position[1] * 1000.0),
        "rim": glass.outline.max_diameter * 1000.0,
        "base": glass.outline.diameter_at(0.0) * 1000.0,
        "height": glass.outline.total_height * 1000.0,
    }


@contextmanager
def separation_floor(metres: float):
    """Draw layouts with the spawner's own minimum separation lowered, then put it back.

    Problem 2's spawner guarantees 150 mm between centres, which is further
    apart than any of this problem's crowding thresholds, so it cannot produce a
    crowded table at all. The rates in the document come from the bench's own
    scene generator instead; this is only for the two tables the pictures are
    drawn from, which have to be built here so that every glass in them is a
    real outline rather than a size written down. It is done in one place so
    that the document can say exactly what was changed.
    """
    original = spawn.MIN_SEPARATION
    spawn.MIN_SEPARATION = metres
    try:
        yield
    finally:
        spawn.MIN_SEPARATION = original


def layout(count: int, seed: int) -> list[dict]:
    """One table of ``count`` tapered glasses, as problem 2 would report it."""
    return [seen(glass) for glass in spawn.random_glasses(count, seed, kinds=["tapered_glass"])]


def blockers(table: list[dict], target: int, live) -> list[int]:
    """Which of the glasses still on the table are in the way of gripping this one.

    The open jaw needs GRIP_ROOM clear of *material* measured out from the
    target's middle, and a neighbour's material reaches half its own rim out
    from its own middle. So the test is not the same for both glasses of a pair:
    a wide neighbour blocks from further away than a narrow one.
    """
    here = table[target]["at"]
    return [
        other for other in live
        if other != target
        and math.dist(here, table[other]["at"]) < GRIP_ROOM + table[other]["rim"] / 2.0
    ]


def peel_one_at_a_time(table: list[dict], rng: random.Random) -> list[int]:
    """The same peel, racking one glass at a time in a random order. Returns the residue.

    Here to check the claim the method rests on rather than to be used: if the
    residue depended on the order, it could not be worked out before the first
    glass was touched.
    """
    live = set(range(len(table)))
    while True:
        free = [index for index in sorted(live) if not blockers(table, index, live)]
        if not free:
            return sorted(live)
        live.discard(rng.choice(free))


def peel(table: list[dict]) -> tuple[list[list[int]], list[int]]:
    """Rack everything already grippable, recompute, repeat. Returns the rounds and the residue.

    Racking a glass cannot put another glass in the way, so a glass that is free
    stays free and the order within a round makes no difference to what is left
    at the end. The residue is what the pushing solutions have to deal with.
    """
    live = set(range(len(table)))
    rounds: list[list[int]] = []
    while True:
        free = [index for index in sorted(live) if not blockers(table, index, live)]
        if not free:
            return rounds, sorted(live)
        rounds.append(free)
        live -= set(free)


def clear_views(table: list[dict], target: int, live) -> list[float]:
    """Which of the nine level-view directions are clear for this glass.

    A direction is no good if the arm cannot stand there, or if another glass
    still on the table shares the frame with the target — a glass behind the
    target joins it in the mask and the two measure as one wide glass.

    This is a deliberately crude stand-in for what problem 2 actually does, and
    the document says so where it quotes the result.
    """
    here = table[target]["at"]
    usable = []
    for degrees in DIRECTIONS:
        angle = math.radians(degrees)
        along = (math.cos(angle), math.sin(angle))
        camera = (here[0] + STANDOFF * along[0], here[1] + STANDOFF * along[1])
        if not in_reach(camera):
            continue
        shared = False
        for other in live:
            if other == target:
                continue
            offset = (table[other]["at"][0] - here[0], table[other]["at"][1] - here[1])
            forward = offset[0] * along[0] + offset[1] * along[1]
            sideways = abs(-offset[0] * along[1] + offset[1] * along[0])
            if forward < STANDOFF and sideways < (table[target]["rim"] + table[other]["rim"]) / 2.0:
                shared = True
                break
        if not shared:
            usable.append(degrees)
    return usable


# --------------------------------------------------------------------------- #
# The measurements
# --------------------------------------------------------------------------- #

def measure_pushing(count: int = 400, seed: int = 7) -> dict:
    """How many glasses of each kind can be pushed at all, at each guess at the friction.

    A glass can be pushed only if its topple height is above the height the jaw
    touches it at, and the topple height needs a friction nobody in this cell
    measures. So this is measured at three guesses, and at both of the heights
    the jaw can meet a glass at.
    """
    kinds = {}
    for kind in KINDS:
        feet = np.array([2.0 * float(outline.radius[0]) * 1000.0
                         for outline, _ in family(kind, count, seed)])
        kinds[kind] = {
            "feet": feet,
            "share": {(height, mu): float(np.mean(feet / 2.0 / mu > height))
                      for height in (LOWEST_GRIP, JAW_TOP) for mu in FRICTIONS},
        }
    return {
        "count": count,
        "kinds": kinds,
        "bases": kinds["tapered_glass"]["feet"],
        "low": int(sum(pushable(foot, MU_LOW) for foot in kinds["tapered_glass"]["feet"])),
        "high": int(sum(pushable(foot, MU_HIGH) for foot in kinds["tapered_glass"]["feet"])),
        "cliff_low": 2.0 * LOWEST_GRIP * MU_LOW,
        "cliff_high": 2.0 * LOWEST_GRIP * MU_HIGH,
    }


def measure_handover() -> dict:
    """How often the table the spawner actually draws has a crowded pair on it.

    The answer is the first thing this solution has to report, because if the
    handover guarantee is already above every crowding threshold then problem 3
    has nothing to work on.
    """
    closest, crowded, blocked, tables = [], 0, 0, 0
    for count in COUNTS:
        for seed in range(SEEDS):
            table = layout(count, seed)
            tables += 1
            places = [glass["at"] for glass in table]
            nearest = min(room_around(places, index) for index in range(len(places)))
            closest.append(nearest)
            if nearest < GRIPPABLE_APART:
                crowded += 1
            live = set(range(len(table)))
            if any(blockers(table, index, live) for index in range(len(table))):
                blocked += 1
    return {
        "tables": tables,
        "crowded": crowded,
        "blocked": blocked,
        "closest": np.array(closest),
    }


def measure_sightlines() -> dict:
    """How often a glass has a clear level view, at both separation floors.

    The peel's own test is about the room the jaw needs. A glass also needs a
    viewpoint before it can be measured and picked, and this asks how much of
    that second condition crowding is responsible for.
    """
    results = {}
    for floor, label in ((TOUCHING_FLOOR, "touching"), (spawn.MIN_SEPARATION, "handover")):
        tally: Counter = Counter()
        none_at_all = glasses = 0
        stalled = differs = crowded = 0
        with separation_floor(floor):
            for count in COUNTS:
                for seed in range(SEEDS):
                    table = layout(count, seed)
                    whole = set(range(len(table)))
                    for index in range(len(table)):
                        views = len(clear_views(table, index, whole))
                        tally[views] += 1
                        glasses += 1
                        if views == 0:
                            none_at_all += 1
                    if not crowded_pairs([glass["at"] for glass in table]):
                        continue
                    crowded += 1
                    _, plain = peel(table)
                    live, rounds = set(whole), 0
                    while True:
                        free = [
                            index for index in sorted(live)
                            if not blockers(table, index, live) and clear_views(table, index, live)
                        ]
                        if not free:
                            break
                        rounds += 1
                        live -= set(free)
                    if sorted(live) != plain:
                        differs += 1
                    if rounds == 0:
                        stalled += 1
        results[label] = {
            "glasses": glasses,
            "none": none_at_all,
            "tally": tally,
            "crowded": crowded,
            "differs": differs,
            "stalled": stalled,
        }
    return results


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #

def _note(axis, x, y, text, colour=INK, size=NOTE_SIZE, ha="left", va="center", box=False) -> None:
    """One line of text. ``box`` puts white behind it, for labels that cross a drawn line."""
    axis.text(x, y, text, fontsize=size, color=colour, ha=ha, va=va, zorder=9,
              bbox=dict(facecolor=PAPER, edgecolor="none", pad=1.2) if box else None)


def _span(axis, left, right, y, text, colour=INK) -> None:
    """A measured distance, drawn as a line with its length under it."""
    axis.annotate("", xy=(right, y), xytext=(left, y),
                  arrowprops=dict(arrowstyle="<|-|>", color=colour, lw=1.0, shrinkA=0, shrinkB=0))
    _note(axis, (left + right) / 2.0, y - 15.0, text, colour=colour, ha="center", va="top")


def picture_four_distances(pair: tuple[dict, dict]) -> None:
    """One real pair of glasses at the four distances that mean something to it.

    The point of the picture is that a pair has three thresholds rather than
    one, that two of them are different from each other, and that all three are
    below what problem 2 guarantees.
    """
    wide, narrow = pair
    touching = (wide["rim"] + narrow["rim"]) / 2.0
    wide_needs = GRIP_ROOM + narrow["rim"] / 2.0
    narrow_needs = GRIP_ROOM + wide["rim"] / 2.0
    guarantee = spawn.MIN_SEPARATION * 1000.0

    panels = (
        (touching, f"{touching:.0f} mm \u2014 the rims touch"),
        (wide_needs, f"{wide_needs:.0f} mm \u2014 the wide one is grippable"),
        (narrow_needs, f"{narrow_needs:.0f} mm \u2014 the narrow one is too"),
        (guarantee, f"{guarantee:.0f} mm \u2014 what problem 2 guarantees"),
    )

    figure, axes = new(12.6, 3.6, columns=4)
    for axis, (distance, title) in zip(axes, panels, strict=True):
        bare(axis)
        axis.set_xlim(-100.0, 265.0)
        axis.set_ylim(-125.0, 135.0)
        axis.set_aspect("equal")
        # The colours are worked out from the same test the method uses, so that
        # the picture cannot disagree with the arithmetic beside it.
        free = (distance >= wide_needs, distance >= narrow_needs)
        for centre, glass, clear in (((0.0, 0.0), wide, free[0]),
                                     ((distance, 0.0), narrow, free[1])):
            colour = GOOD if clear else WARN
            grip_ring(axis, centre, colour=colour)
            glass_from_above(axis, centre, glass["rim"], glass["base"] / glass["rim"],
                             colour=colour, edge=colour)
        _span(axis, 0.0, distance, -95.0, f"{distance:.0f} mm")
        axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=6)
    _note(axes[3], 0.0, 100.0, f"wide: {wide['rim']:.0f} mm rim", colour=INK, ha="center")
    _note(axes[3], guarantee, 100.0, f"narrow: {narrow['rim']:.0f} mm rim", colour=INK, ha="center")

    figure.suptitle("One real pair of glasses, and the three distances that decide what can be picked up",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    figure.text(
        0.5, 0.01,
        f"The dashed ring is the {GRIP_ROOM:.0f} mm of clear room the open jaw needs round a glass's middle, "
        f"and a glass is blocked when that ring reaches another glass's material. So the test is not the "
        f"same for both of\nthem: the narrow glass reaches less far out from its own middle, so the wide one "
        f"comes free {narrow_needs - wide_needs:.0f} mm earlier. Every one of these distances is below the "
        f"{guarantee:.0f} mm problem 2 hands over.",
        fontsize=NOTE_SIZE, color=INK, ha="center",
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.84, bottom=0.14, wspace=0.05)
    save(figure, "01-four-distances-one-pair.png")


def _zone(axis) -> None:
    """The part of the table glasses may stand on, and nothing else."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                             facecolor="none", edgecolor=MUTED, lw=0.9, ls=(0, (5, 4)), zorder=1))
    axis.set_xlim(x_from - 90.0, x_to + 90.0)
    axis.set_ylim(y_from - 90.0, y_to + 100.0)
    axis.set_aspect("equal")


def picture_peel_in_rounds(table: list[dict], label: str) -> None:
    """The cascade: a glass that was blocked at the start, freed by racking its neighbour."""
    rounds, residue = peel(table)
    names = "ABCDEF"
    freed = rounds[1][0]
    by = blockers(table, freed, set(range(len(table))))[0]
    apart = math.dist(table[freed]["at"], table[by]["at"])
    figure, axes = new(12.0, 4.8, columns=3)

    first = [names[index] for index in rounds[0]]
    titles = (
        "What the survey shows",
        f"Round one racks {', '.join(first[:-1])} and {first[-1]} \u2014 {names[freed]} is now free",
        f"Round two racks {names[freed]}",
    )
    gone: set[int] = set()
    for step, (axis, title) in enumerate(zip(axes, titles, strict=True)):
        bare(axis)
        _zone(axis)
        live = set(range(len(table))) - gone
        for index, glass in enumerate(table):
            if index in gone:
                glass_from_above(axis, glass["at"], glass["rim"], glass["base"] / glass["rim"],
                                 colour=MUTED, alpha=0.08, edge=MUTED, lw=0.7, foot=False)
                continue
            free = not blockers(table, index, live)
            colour = GOOD if free else WARN
            # Only the pair being argued about carries a ring. Drawing all four
            # is what made the first version of this picture unreadable.
            ringed = index in (freed, by) if step == 0 else index == freed
            if ringed:
                grip_ring(axis, glass["at"], colour=colour)
            glass_from_above(axis, glass["at"], glass["rim"], glass["base"] / glass["rim"],
                             colour=colour, edge=colour)
            if ringed and index == by:
                # Beside the ring rather than above it: above is where the ring
                # of the glass it blocks already is.
                _note(axis, glass["at"][0] - GRIP_ROOM - 16.0, glass["at"][1],
                      names[index], colour=INK, size=LABEL_SIZE, ha="right")
            else:
                _note(axis, glass["at"][0], glass["at"][1] + glass["rim"] / 2.0 + 14.0,
                      names[index], colour=INK, size=LABEL_SIZE, ha="center", va="bottom")
        if step == 0:
            here, there = table[freed]["at"], table[by]["at"]
            axis.annotate("", xy=there, xytext=here, zorder=8,
                          arrowprops=dict(arrowstyle="<|-|>", color=WARN, lw=1.0,
                                          shrinkA=0, shrinkB=0))
            _, x_to, _, y_to = GLASS_ZONE
            _note(axis, x_to, y_to + 26.0,
                  f"{names[freed]} and {names[by]} stand {apart:.1f} mm apart",
                  colour=WARN, ha="right", va="bottom")
        if step == 2:
            _, x_to, _, y_to = GLASS_ZONE
            _note(axis, x_to, y_to + 26.0,
                  "the table is empty, and nothing was pushed", colour=GOOD, ha="right", va="bottom")
        gone |= set(rounds[step]) if step < len(rounds) else set()
        axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=6)

    figure.suptitle("Peeling one real table: nothing is pushed, and nothing needs to be",
                    fontsize=TITLE_SIZE, color=INK, y=0.99)
    figure.text(
        0.5, 0.015,
        f"{names[freed]} and {names[by]} stand {apart:.1f} mm apart. That is inside the "
        f"{GRIP_ROOM + table[by]['rim'] / 2.0:.1f} mm {names[freed]} needs from a neighbour "
        f"{table[by]['rim']:.1f} mm across, and outside the "
        f"{GRIP_ROOM + table[freed]['rim'] / 2.0:.1f} mm\n{names[by]} needs from one "
        f"{table[freed]['rim']:.1f} mm across. So {names[by]} is racked in the first round and its leaving "
        f"is what releases {names[freed]}. The residue is empty: this table needed no push at all."
        if not residue else "",
        fontsize=NOTE_SIZE, color=INK, ha="center",
    )
    figure.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.12, wspace=0.05)
    save(figure, f"01-{label}.png")


def picture_what_it_is_worth() -> None:
    """The measured payoff, over the bench's own held-out scenes.

    Every number drawn here comes from ``BENCH`` above, which was measured by
    problem-3-programmed/measure_peel.py. This environment cannot run the bench
    itself.
    """
    figure, axes = new(12.2, 3.9, columns=3)
    for axis in axes:
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(MUTED)
        axis.tick_params(colors=MUTED, labelsize=NOTE_SIZE)

    scenes = BENCH["scenes"]
    counts = (BENCH["emptied"], BENCH["residue"], BENCH["nothing_free"])
    share = [100.0 * value / scenes for value in counts]
    bars = axes[0].barh(range(3), share, color=(GOOD, GLASS, WARN), height=0.6)
    axes[0].set_yticks(range(3))
    axes[0].set_yticklabels(["the peel clears\nthe table", "it racks some and\nleaves a residue",
                            "nothing was free\nto start with"], fontsize=NOTE_SIZE, color=INK)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0.0, 100.0)
    axes[0].set_xlabel("per cent of scenes", fontsize=NOTE_SIZE, color=MUTED)
    for bar, value, number in zip(bars, share, counts, strict=True):
        axes[0].text(value + 2.0, bar.get_y() + bar.get_height() / 2.0,
                     f"{value:.1f}%  ({number})", fontsize=NOTE_SIZE, color=INK, va="center")
    axes[0].set_title(f"What happens to {scenes} bench scenes", fontsize=LABEL_SIZE, color=INK, pad=8)

    racked, left = BENCH["racked"], BENCH["left"]
    axes[1].bar(("racked with\nno push", "left for the\npushing logic"), (racked, left),
                color=(GOOD, WARN), width=0.5)
    for index, value in enumerate((racked, left)):
        axes[1].text(index, value + 60.0, f"{value}  ({100.0 * value / BENCH['glasses']:.0f}%)",
                     fontsize=NOTE_SIZE, color=INK, ha="center")
    axes[1].set_ylim(0.0, max(racked, left) * 1.2)
    axes[1].set_ylabel(f"glasses, of {BENCH['glasses']}", fontsize=NOTE_SIZE, color=MUTED)
    axes[1].set_title("Less than a third leave without a push",
                      fontsize=LABEL_SIZE, color=INK, pad=8)

    sizes = sorted(BENCH["residues"])
    heights = [BENCH["residues"][size] for size in sizes]
    axes[2].bar([str(size) for size in sizes], heights,
                color=[GOOD if size == 0 else WARN for size in sizes], width=0.6)
    for index, value in enumerate(heights):
        axes[2].text(index, value + 6.0, str(value), fontsize=NOTE_SIZE, color=INK, ha="center")
    axes[2].set_ylim(0.0, max(heights) * 1.18)
    axes[2].set_xlabel("glasses left for the pushing logic", fontsize=NOTE_SIZE, color=MUTED)
    axes[2].set_title("A residue is never one glass", fontsize=LABEL_SIZE, color=INK, pad=8)

    figure.suptitle("What racking the free glasses first is worth, on the bench's own crowded tables",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    figure.text(
        0.5, 0.005,
        f"Scenes {BENCH['seeds'][0]} to {BENCH['seeds'][1]} of problem-3-sim/bench.py, which is the "
        f"held-out half of its scene space: four to six glasses, the four kinds in turn, every table "
        f"guaranteed to have\nat least one glass without room. {BENCH['without_room']} of the "
        f"{BENCH['glasses']} glasses have no room at the start, and the closest pair on a scene runs from "
        f"{BENCH['closest'][0]:.1f} to {BENCH['closest'][2]:.1f} mm. A residue of one is impossible, "
        "because a single glass left on the table has nothing to block it.",
        fontsize=NOTE_SIZE, color=INK, ha="center",
    )
    figure.subplots_adjust(left=0.08, right=0.98, top=0.82, bottom=0.22, wspace=0.42)
    save(figure, "01-what-the-peel-is-worth.png")


def picture_residue_inherits(table: list[dict], residue: list[int], pushing: dict) -> None:
    """What the two glasses left over inherit: a limit that needs a number nobody has."""
    figure, axes = new(12.2, 4.4, columns=2)
    side, spread = axes
    names = "ABCDEF"
    label_box = dict(facecolor="#ffffff", edgecolor="none", pad=1.2)

    bare(side)
    side.set_xlim(-180.0, 620.0)
    side.set_ylim(-95.0, 250.0)
    side.set_aspect("equal")
    side.plot([-180.0, 620.0], [0.0, 0.0], color=INK, lw=1.2, zorder=2)
    side.plot([-180.0, 620.0], [LOWEST_GRIP, LOWEST_GRIP], color=INK, lw=0.9, ls=(0, (4, 3)), zorder=2)
    _note(side, -178.0, -14.0, "the table", colour=MUTED, va="top")
    _note(side, -178.0, -44.0,
          f"the dashed line is {LOWEST_GRIP:.0f} mm, the lowest the gripper can push without\n"
          "its own body going through the table; each coloured line is the height\n"
          "that glass tips above, for one guess at the friction", colour=INK, va="top")

    for slot, index in enumerate(residue):
        glass = table[index]
        x = slot * 330.0
        glass_from_the_side(side, x, glass["height"], glass["rim"], glass["base"] / glass["rim"],
                            colour=GLASS, edge=GLASS)
        _note(side, x, glass["height"] + 14.0,
              f"{names[index]}: a {glass['base']:.0f} mm foot", colour=INK, ha="center", va="bottom")
        for mu, colour in ((MU_LOW, GOOD), (MU_HIGH, WARN)):
            height = topple_height(glass["base"], mu)
            safe = pushable(glass["base"], mu)
            shown = colour if safe else WARN
            side.plot([x - glass["rim"] / 2.0 - 20.0, x + glass["rim"] / 2.0 + 20.0], [height, height],
                      color=shown, lw=1.5, zorder=5)
            side.text(x + glass["rim"] / 2.0 + 26.0, height,
                      f"{height:.0f} mm  (\u03bc = {mu})",
                      fontsize=NOTE_SIZE, color=shown, ha="left", va="center", zorder=9,
                      bbox=label_box)
            if not safe:
                _note(side, x, -14.0, f"no push is safe at \u03bc = {mu}",
                      colour=WARN, ha="center", va="top")
        push_arrow(side, (x - glass["rim"] / 2.0 - 74.0, LOWEST_GRIP),
                   (x - glass["base"] / 2.0 - 5.0, LOWEST_GRIP),
                   colour=INK if pushable(glass["base"], MU_HIGH) else WARN)
    side.set_title("The two glasses this table leaves behind", fontsize=LABEL_SIZE, color=INK, pad=8)

    spread.hist(pushing["bases"], bins=26, color=GLASS, alpha=0.55, edgecolor=GLASS)
    top = spread.get_ylim()[1]
    spread.set_ylim(0.0, top * 1.42)
    # No tick up where the two notes are written, or the topmost one is drawn over.
    spread.set_yticks([tick for tick in spread.get_yticks() if tick <= top])
    for cliff, colour, mu, kept, side_of in ((pushing["cliff_low"], GOOD, MU_LOW, pushing["low"], "right"),
                                             (pushing["cliff_high"], WARN, MU_HIGH, pushing["high"], "left")):
        spread.axvline(cliff, color=colour, lw=1.4)
        spread.text(cliff + (-0.8 if side_of == "right" else 0.8), top * 1.39,
                    f"\u03bc = {mu}\na foot under {cliff:.0f} mm cannot be pushed at all\n"
                    f"{100.0 * kept / pushing['count']:.1f}% of these glasses can be",
                    fontsize=NOTE_SIZE, color=colour, va="top",
                    ha="right" if side_of == "right" else "left")
    for name in ("top", "right"):
        spread.spines[name].set_visible(False)
    for name in ("left", "bottom"):
        spread.spines[name].set_color(MUTED)
    spread.tick_params(colors=MUTED, labelsize=NOTE_SIZE)
    spread.set_xlabel("the foot a glass stands on, mm", fontsize=NOTE_SIZE, color=MUTED)
    spread.set_ylabel(f"glasses, of {pushing['count']} drawn", fontsize=NOTE_SIZE, color=MUTED)
    spread.set_title("The same cliff across the tapered kind, the narrowest-footed of the four",
                     fontsize=LABEL_SIZE, color=INK, pad=8)

    margin = topple_height(table[residue[0]]["base"], MU_HIGH) - LOWEST_GRIP
    figure.suptitle("Every glass racked without a push is a glass whose friction never mattered",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    figure.text(
        0.5, 0.01,
        f"A push slides a glass while it is made below half the foot divided by the friction with the "
        f"table, and tips it above. Nothing in this cell measures that friction, though the simulator "
        f"gives the table {BENCH_FRICTION} and keeps it\nfrom the arm. At \u03bc = {MU_HIGH} one of these "
        f"two glasses has no safe push height at all and the other has {margin:.0f} mm of margin; at "
        f"\u03bc = {MU_LOW} both are comfortable. The peel took the other two glasses off this table "
        "without ever needing to know which case holds.",
        fontsize=NOTE_SIZE, color=INK, ha="center",
    )
    figure.subplots_adjust(left=0.03, right=0.98, top=0.85, bottom=0.17, wspace=0.14)
    save(figure, "01-what-the-residue-inherits.png")


# --------------------------------------------------------------------------- #

def main() -> None:
    pushing = measure_pushing()
    print(f"the friction cliff, {pushing['count']} drawn glasses of each kind, at the two heights "
          f"the jaw can touch at:")
    for kind, found in pushing["kinds"].items():
        feet = found["feet"]
        shares = "  ".join(
            f"{height:.0f} mm, mu={mu}: {100.0 * found['share'][(height, mu)]:.1f}%"
            for height in (LOWEST_GRIP, JAW_TOP) for mu in FRICTIONS
        )
        print(f"    {kind}: foot {feet.min():.1f}-{feet.max():.1f} mm, mean {feet.mean():.1f}; {shares}")

    handover = measure_handover()
    print(f"problem 2's spawner ({handover['tables']} tables, "
          f"{spawn.MIN_SEPARATION * 1000:.0f} mm floor):")
    print(f"    with a pair inside {GRIPPABLE_APART:.0f} mm: {handover['crowded']}")
    print(f"    with any glass blocked by the asymmetric test: {handover['blocked']}")
    print(f"    closest pair: min {handover['closest'].min():.1f}, "
          f"median {np.median(handover['closest']):.1f}, max {handover['closest'].max():.1f} mm")
    rims = KIND_RANGES["tapered_glass"]["rim_diameter"]
    widths = [KIND_RANGES[kind].get("rim_diameter") or KIND_RANGES[kind]["bowl_diameter"]
              for kind in KINDS]
    print(f"    the asymmetric threshold runs {GRIP_ROOM + rims[0] * 500:.1f} to "
          f"{GRIP_ROOM + rims[1] * 500:.1f} mm for the tapered kind, and "
          f"{GRIP_ROOM + min(w[0] for w in widths) * 500:.1f} to "
          f"{GRIP_ROOM + max(w[1] for w in widths) * 500:.1f} mm over all four")

    print(f"the peel on bench.scene, seeds {BENCH['seeds'][0]}-{BENCH['seeds'][1]} "
          f"(measured by problem-3-programmed/measure_peel.py, copied in above):")
    print(f"    {BENCH['scenes']} scenes, {BENCH['glasses']} glasses, "
          f"{BENCH['without_room']} = {100.0 * BENCH['without_room'] / BENCH['glasses']:.1f}% "
          f"without room at the start")
    for name in ("emptied", "residue", "nothing_free"):
        print(f"    {name}: {BENCH[name]} = {100.0 * BENCH[name] / BENCH['scenes']:.1f}%")
    print(f"    racked with no push: {BENCH['racked']}/{BENCH['glasses']} "
          f"= {100.0 * BENCH['racked'] / BENCH['glasses']:.1f}%, left {BENCH['left']}")
    print(f"    with run.py's 5 mm margin: racked {BENCH['margin']['racked']} "
          f"= {100.0 * BENCH['margin']['racked'] / BENCH['glasses']:.1f}%, "
          f"cleared {BENCH['margin']['emptied']} scenes")

    sightlines = measure_sightlines()
    for label, found in sightlines.items():
        print(f"the level view, {label} floor ({found['glasses']} glasses):")
        print(f"    no clear direction of nine: {found['none']} "
              f"= {100.0 * found['none'] / found['glasses']:.1f}%")

    with separation_floor(TOUCHING_FLOOR):
        cascade = layout(*CASCADE)
        stall = layout(*STALL)
    names = "ABCDEF"
    whole = set(range(len(cascade)))
    rounds, residue = peel(cascade)
    print(f"the table drawn for the pictures, count={CASCADE[0]} seed={CASCADE[1]}: "
          f"rounds {rounds}, residue {residue}")
    for index, glass in enumerate(cascade):
        print(f"    {names[index]} at ({glass['at'][0]:.0f}, {glass['at'][1]:.0f}), "
              f"rim {glass['rim']:.1f}, foot {glass['base']:.1f}, height {glass['height']:.1f}, "
              f"nearest neighbour {room_around([g['at'] for g in cascade], index):.1f} mm, "
              f"blocked by {[names[other] for other in blockers(cascade, index, whole)]}")
    for i in range(len(cascade)):
        for j in range(i + 1, len(cascade)):
            apart = math.dist(cascade[i]["at"], cascade[j]["at"])
            print(f"    {names[i]}-{names[j]}: {apart:.1f} mm apart, "
                  f"grippable pair {grippable(cascade[i]['at'], cascade[j]['at'])}")

    rounds_stall, residue_stall = peel(stall)
    everything = set(range(len(stall)))
    print(f"the second table drawn, count={STALL[0]} seed={STALL[1]}: "
          f"rounds {rounds_stall}, residue {residue_stall}")
    for index, glass in enumerate(stall):
        print(f"    {names[index]} at ({glass['at'][0]:.0f}, {glass['at'][1]:.0f}), "
              f"rim {glass['rim']:.1f}, foot {glass['base']:.1f}, height {glass['height']:.1f}, "
              f"blocked by {[names[other] for other in blockers(stall, index, everything)]}, "
              f"tips above {topple_height(glass['base'], MU_LOW):.1f} mm at mu={MU_LOW}, "
              f"{topple_height(glass['base'], BENCH_FRICTION):.1f} at mu={BENCH_FRICTION} and "
              f"{topple_height(glass['base'], MU_HIGH):.1f} at mu={MU_HIGH}")
    for i in range(len(stall)):
        for j in range(i + 1, len(stall)):
            gap = math.dist(stall[i]["at"], stall[j]["at"])
            if gap < GRIPPABLE_APART:
                print(f"    {names[i]}-{names[j]}: {gap:.1f} mm apart, "
                      f"{names[i]} needs {GRIP_ROOM + stall[j]['rim'] / 2.0:.1f}, "
                      f"{names[j]} needs {GRIP_ROOM + stall[i]['rim'] / 2.0:.1f}")

    pair = (cascade[3], cascade[0]) if cascade[3]["rim"] > cascade[0]["rim"] else (cascade[0], cascade[3])
    picture_four_distances(pair)
    picture_peel_in_rounds(cascade, "the-peel-in-rounds")
    picture_what_it_is_worth()
    picture_residue_inherits(stall, residue_stall, pushing)


if __name__ == "__main__":
    main()
