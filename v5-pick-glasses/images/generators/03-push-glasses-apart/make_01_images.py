"""Diagrams for solution 1 — do not drag at all.

Every glass drawn here is one the project's own spawner drew, at a position the
spawner chose, and every rim and foot is measured off that glass's outline
rather than typed in. That matters more in this document than in most, because
the whole argument is about *which* glasses on a particular table are already
grippable, and a picture drawn with invented sizes could be made to say either
answer.

The script also prints every number the document quotes. Run it from the project
root:

    pixi run python images/generators/03-push-glasses-apart/make_01_images.py
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
    grip_ring,
    grippable,
    in_reach,
    new,
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

# The four kinds, in the order 03-push-glasses-apart/bench/bench.py cycles them.
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

# What the peel is actually worth, measured on the examiner's own crowded tables
# by 03-push-glasses-apart/01-one-fixed-nudge/measure_peel.py over bench.scene seeds 10000-10999 —
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
    # The same sweep with the 5 mm take margin 03-push-glasses-apart/01-one-fixed-nudge/run.py
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
    crowded table at all. The rates in the document come from the examiner's own
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

    # Three of the four distances are set by the rims, so only the fourth may be
    # written down: the guaranteed separation belongs to the cell. The other
    # three are named by the relation that puts them where they are.
    panels = (
        (touching, "the rims touch", "rim against rim"),
        (wide_needs, "the wide one has its room",
         "the narrow one's edge\nreaches the wide one's ring"),
        (narrow_needs, "the narrow one has it too",
         "the wide one's edge\nreaches the narrow one's ring"),
        (guarantee, f"{guarantee:.0f} mm \u2014 what problem 2 guarantees",
         f"{guarantee:.0f} mm"),
    )

    figure, axes = new(12.6, 3.6, columns=4)
    for axis, (distance, title, span) in zip(axes, panels, strict=True):
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
        _span(axis, 0.0, distance, -95.0, span)
        axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=6)
    _note(axes[3], 0.0, 100.0, "the wider of the pair", colour=INK, ha="center")
    _note(axes[3], guarantee, 100.0, "the narrower", colour=INK, ha="center")

    figure.suptitle("One pair of glasses, and why what each one needs is set by how wide the other is",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    figure.text(
        0.5, 0.01,
        f"The dashed ring is the {GRIP_ROOM:.0f} mm of clear room the open jaw needs round a glass's middle, "
        f"and a glass is blocked when another glass's edge reaches inside that ring. So the test is not the "
        f"same for both of\nthem: the narrow glass's edge reaches less far out from its own middle, so the "
        f"wide one comes free first, and it comes free sooner by half of however much the two rims differ. "
        f"Every one of these\ndistances is below the {guarantee:.0f} mm problem 2 hands over.",
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
          f"(measured by 03-push-glasses-apart/01-one-fixed-nudge/measure_peel.py, copied in above):")
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
if __name__ == "__main__":
    main()
