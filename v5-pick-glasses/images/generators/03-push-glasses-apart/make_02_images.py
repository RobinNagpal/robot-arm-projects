"""Diagrams for solution 2 — one fixed nudge.

Every glass drawn here is a real glass, and every arrangement is a real table.
The outlines come from ``work_cell.glasses.shapes`` at sizes drawn from
``KIND_RANGES["tapered_glass"]``, and the places they stand in come from the
layout rule in ``03-push-glasses-apart/bench/bench.py``, which is the generator the real runs
are scored against. No glass's size is written down in this file.

**Why the layout rule is copied rather than imported.** ``bench.py`` imports
MuJoCo, which is installed in ``03-push-glasses-apart/01-one-fixed-nudge`` and
``03-push-glasses-apart/04-a-world-model`` but not in the root environment every generator in this
repository runs from. ``scene`` and ``_crowded_layout`` need none of it, so
they are mirrored below, in metres, exactly as they are written there. The copy
was checked against the original over 2399 seeds — every tapered test seed this
script uses, and 399 more covering all four kinds — and it produced the same
glasses in the same places every time.

**Why not ``spawn.random_glasses``.** Problem 2's spawner keeps
``MIN_SEPARATION`` = 150 mm between centres, which is above every crowding
threshold in problem 3, so no table it draws has a glass without room and the
problem never starts. ``bench.scene`` stands 60 per cent of its glasses
deliberately close to one already down, which is what makes a crowded table.

**Which test decides crowding.** ``has_room`` from ``diagram_style``, which is
``bench.py``'s own and is not symmetric: a glass has room when every other
glass's *edge* is at least 70 mm from its middle, so what a glass needs depends
on how wide its neighbour is. ``GRIPPABLE_APART`` (140 mm) is the conservative
symmetric bound, and is used here only to price the rule the overview wrote
down in those terms.

Every number this script prints is a number the document quotes.

    pixi run python images/generators/03-push-glasses-apart/make_02_images.py
"""

from __future__ import annotations

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
    RACK_AREA,
    TABLE_FRICTION,
    TITLE_SIZE,
    WARN,
    bare,
    glass_from_above,
    grip_ring,
    has_room,
    in_reach,
    in_zone,
    save,
    topple_height,
)
from diagram_style import (
    new as new_figure,
)
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import draw, family  # noqa: E402
from work_cell.rack.layout import GLASS_ZONE as ZONE_M  # noqa: E402

# --------------------------------------------------------------------------- #
# 03-push-glasses-apart/bench/bench.py, mirrored. Metres, as it is written there.
# --------------------------------------------------------------------------- #
KINDS = ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass")
TEST_SEEDS = 10_000     # scenes from here up are for testing; training draws below
CROWD_SHARE = 0.6       # the share of glasses stood deliberately close to one already down
START_GAP = 0.005       # the least daylight between two glasses at the start
ROOM_M = GRIP_ROOM / 1000.0


def _has_room_m(x: float, y: float, others) -> bool:
    return all(math.dist((x, y), (ox, oy)) >= ROOM_M + width / 2 for ox, oy, width in others)


def _in_zone_m(x: float, y: float) -> bool:
    x_min, x_max, y_min, y_max = ZONE_M
    return x_min <= x <= x_max and y_min <= y <= y_max


def _crowded_layout(rng: random.Random, outlines):
    x_min, x_max, y_min, y_max = ZONE_M
    placed: list[tuple[float, float, float]] = []
    for outline in outlines:
        width = outline.max_diameter
        for _ in range(300):
            if placed and rng.random() < CROWD_SHARE:
                px, py, pwidth = rng.choice(placed)
                near = rng.uniform((width + pwidth) / 2 + START_GAP,
                                   ROOM_M + max(width, pwidth) / 2)
                angle = rng.uniform(-math.pi, math.pi)
                x, y = px + near * math.cos(angle), py + near * math.sin(angle)
            else:
                x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
            if _in_zone_m(x, y) and all(
                math.dist((x, y), (qx, qy)) >= (width + qwidth) / 2 + START_GAP
                for qx, qy, qwidth in placed
            ):
                placed.append((x, y, width))
                break
        else:
            return None
    crowded = [not _has_room_m(x, y, [q for q in placed if q is not p])
               for p in placed for x, y in [p[:2]]]
    return [(x, y) for x, y, _ in placed] if any(crowded) else None


def scene(seed: int):
    """Table number ``seed``, as ``bench.scene`` builds it: outlines and places."""
    rng = random.Random(seed)
    kind, count = KINDS[seed % len(KINDS)], 4 + seed % 3
    for _ in range(200):
        outlines = [draw(kind, rng)[0] for _ in range(count)]
        spots = _crowded_layout(rng, outlines)
        if spots is not None:
            return list(zip(outlines, spots, strict=True))
    raise RuntimeError(f"no crowded layout for scene {seed}")


# --------------------------------------------------------------------------- #
# The tables this document measures, in millimetres
# --------------------------------------------------------------------------- #
# bench.scene cycles the four kinds by seed, and the tapered kind is the one
# problem 3's arithmetic is worked out on in these documents, so this takes the
# seeds where scene draws it. They are test seeds rather than training seeds:
# nothing here is trained, and a score belongs on the test set anyway.
FIRST_SEED = 10_001
HOW_MANY_TABLES = 2000

# The two tables the pictures are drawn from. Both are ordinary four-glass
# scenes; they are named so that anyone can regenerate them.
EASY_SEED = 23841
HARD_SEED = 11229

LETTERS = "PQRSTU"


def table(seed: int) -> dict:
    """One table from the spawner, with every measurement the nudge is allowed."""
    glasses = scene(seed)
    return {
        "seed": seed,
        "n": len(glasses),
        "at": [(spot[0] * 1000.0, spot[1] * 1000.0) for _, spot in glasses],
        "widest": [outline.max_diameter * 1000.0 for outline, _ in glasses],
        "base": [outline.diameter_at(0.0) * 1000.0 for outline, _ in glasses],
        "height": [outline.total_height * 1000.0 for outline, _ in glasses],
    }


def all_tables() -> list[dict]:
    return [table(FIRST_SEED + 4 * n) for n in range(HOW_MANY_TABLES)]


def neighbours_of(t: dict, skip: int, at=None):
    """Every other glass as (x, y, widest width), which is what has_room takes."""
    at = at or t["at"]
    return [(at[k][0], at[k][1], t["widest"][k]) for k in range(t["n"]) if k != skip]


def room(t: dict, k: int, at=None) -> bool:
    """Whether glass ``k`` has the room the open jaw needs."""
    at = at or t["at"]
    return has_room(at[k], neighbours_of(t, k, at))


def intrusion(t: dict, crowded: int, other: int) -> float:
    """How far another glass's edge reaches inside this glass's 70 mm ring."""
    return GRIP_ROOM + t["widest"][other] / 2.0 - math.dist(t["at"][crowded], t["at"][other])


def blocking(t: dict, crowded: int) -> int:
    """The neighbour reaching furthest inside the ring: the one to push away from."""
    return max((k for k in range(t["n"]) if k != crowded), key=lambda k: intrusion(t, crowded, k))


def every_crowded_glass(tables: list[dict]) -> list[tuple[dict, int, int]]:
    """Every glass on every table that has no room, with the neighbour to blame."""
    return [(t, c, blocking(t, c)) for t in tables for c in range(t["n"]) if not room(t, c)]


# --------------------------------------------------------------------------- #
# The method itself, which is four lines
# --------------------------------------------------------------------------- #
def pushed_first(t: dict, crowded: int, neighbour: int) -> tuple[int, int]:
    """Which of the two gets pushed: the wider foot, which has more room to topple in."""
    return ((crowded, neighbour) if t["base"][crowded] >= t["base"][neighbour]
            else (neighbour, crowded))


def nudged_to(t: dict, moved: int, away_from: int, distance: float) -> tuple[float, float]:
    """Where the nudge puts the glass: straight away from the other one, that far."""
    here, there = t["at"][moved], t["at"][away_from]
    apart = math.dist(here, there)
    return (here[0] + distance * (here[0] - there[0]) / apart,
            here[1] + distance * (here[1] - there[1]) / apart)


def _to_segment(start, end, point) -> float:
    """How near a point comes to a line segment."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = dx * dx + dy * dy
    along = 0.0 if length == 0.0 else max(0.0, min(1.0, ((point[0] - start[0]) * dx
                                                        + (point[1] - start[1]) * dy) / length))
    return math.dist((start[0] + along * dx, start[1] + along * dy), point)


def into_the_rack(point) -> bool:
    x_from, x_to, y_from, y_to = RACK_AREA
    return (x_from - GRIP_ROOM <= point[0] <= x_to + GRIP_ROOM
            and y_from - GRIP_ROOM <= point[1] <= y_to + GRIP_ROOM)


FAULTS = ("the glass still has no room", "took room from a glass that had it",
          "touches another glass", "sweeps through another glass",
          "outside the glass zone", "outside the arm's reach", "into the rack")


def faults(t: dict, crowded: int, moved: int, landing) -> dict[str, bool]:
    """Everything wrong with where this nudge left the table.

    Read as a list of independent complaints rather than one verdict: a push
    can leave the glass short of room and outside the zone at the same time.
    """
    after = list(t["at"])
    after[moved] = landing
    rest = [k for k in range(t["n"]) if k != moved]
    width = t["widest"]
    return {
        "the glass still has no room": not room(t, crowded, after),
        "took room from a glass that had it": any(room(t, k) and not room(t, k, after)
                                                  for k in range(t["n"]) if k != crowded),
        "touches another glass": any(math.dist(landing, t["at"][k])
                                     < (width[moved] + width[k]) / 2.0 for k in rest),
        "sweeps through another glass": any(_to_segment(t["at"][moved], landing, t["at"][k])
                                            < (width[moved] + width[k]) / 2.0 for k in rest),
        "outside the glass zone": not in_zone(landing),
        "outside the arm's reach": not in_reach(landing),
        "into the rack": into_the_rack(landing),
    }


def went_wrong(t: dict, crowded: int, moved: int, landing) -> bool:
    return any(faults(t, crowded, moved, landing).values())


def nudge(t: dict, crowded: int, neighbour: int, distance: float):
    """The whole method: pick the glass, push it, and say what happened."""
    moved, away_from = pushed_first(t, crowded, neighbour)
    landing = nudged_to(t, moved, away_from, distance)
    return moved, away_from, landing, faults(t, crowded, moved, landing)


# --------------------------------------------------------------------------- #
# The sweep, which is the heart of the document
# --------------------------------------------------------------------------- #
# Three of the seven complaints are one failure told three ways: the push met a
# glass that was already standing there. They are counted together as well as
# separately, because a document that quoted the largest of the three would
# understate how often it happens.
MET_A_GLASS = ("took room from a glass that had it", "touches another glass",
               "sweeps through another glass")


def sweep(jobs, distances) -> list[dict]:
    """The share of crowded glasses each nudge distance gets wrong, and why."""
    rows = []
    for distance in distances:
        tally = dict.fromkeys(FAULTS, 0)
        wrong = met = 0
        for t, crowded, neighbour in jobs:
            trouble = nudge(t, crowded, neighbour, float(distance))[3]
            for name, hit in trouble.items():
                tally[name] += hit
            wrong += any(trouble.values())
            met += any(trouble[name] for name in MET_A_GLASS)
        rows.append({"distance": float(distance), "wrong": 100.0 * wrong / len(jobs),
                     "met another glass": 100.0 * met / len(jobs),
                     **{name: 100.0 * count / len(jobs) for name, count in tally.items()}})
    return rows


def met_a_glass(row: dict) -> float:
    """The share of pushes that met a glass, by any of the three complaints."""
    return row["met another glass"]


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
def zone(axis, label: bool = True) -> None:
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                             facecolor="none", edgecolor=MUTED, lw=1.0, ls=(0, (6, 4)),
                             zorder=1))
    if label:
        axis.text(x_from + 5, y_from + 7, "the glass zone", fontsize=NOTE_SIZE - 0.6,
                  color=MUTED, ha="left", va="bottom")


def draw_table(axis, t: dict, rings=(), faded=()) -> None:
    """Every glass on one table from straight above, with rings only where wanted.

    A ring is drawn round a named glass. Four overlapping rings is the fastest
    way to make one of these pictures unreadable, and the room test is about
    one glass's ring at a time anyway.
    """
    for k, centre in enumerate(t["at"]):
        rim = t["widest"][k]
        pale = k in faded
        glass_from_above(axis, centre, rim, base_fraction=t["base"][k] / rim,
                         colour=GLASS, alpha=0.12 if pale else 0.30,
                         edge=MUTED if pale else GLASS)
        if k in rings:
            grip_ring(axis, centre, colour=MUTED, alpha=0.85)


def name_glass(axis, centre, text, colour=INK) -> None:
    axis.text(centre[0], centre[1], text, fontsize=LABEL_SIZE, color=colour,
              ha="center", va="center", zorder=9)


def panel(axis, title: str) -> None:
    bare(axis)
    axis.set_aspect("equal")
    axis.set_title(title, fontsize=TITLE_SIZE, color=INK, pad=8)


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, **kwargs) -> None:
    axis.text(x, y, text, fontsize=size, color=colour, **kwargs)


def lead(axis, text, point, at, colour, size=NOTE_SIZE, **kwargs) -> None:
    """A label placed in clear space, with a thin line back to what it names."""
    axis.annotate(text, xy=tuple(point), xytext=tuple(at), fontsize=size, color=colour,
                  arrowprops=dict(arrowstyle="-", color=colour, lw=0.9,
                                  shrinkA=2, shrinkB=2), **kwargs)


def plain(axis) -> None:
    axis.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for edge in ("top", "right"):
        axis.spines[edge].set_visible(False)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.012, text, ha="center", va="bottom", fontsize=NOTE_SIZE, color=MUTED)


# --------------------------------------------------------------------------- #
# Picture 1 — the test, the nudge, and the height the push is stuck at
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Picture 2 — the sweep, and why no single distance can be right
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Picture 3 — the failure that separates this from solution 3
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Picture 4 — the region the method never works out
# --------------------------------------------------------------------------- #
def _legal_map(t: dict, crowded: int, moved: int, step: float = 3.0):
    """Every spot in and around the zone this glass could legally be pushed to."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    xs = np.arange(x_from - 40.0, x_to + 40.0 + step, step)
    ys = np.arange(y_from - 40.0, y_to + 40.0 + step, step)
    good = np.zeros((len(ys), len(xs)), bool)
    for row, y in enumerate(ys):
        for column, x in enumerate(xs):
            good[row, column] = not went_wrong(t, crowded, moved, (float(x), float(y)))
    return xs, ys, good




# --------------------------------------------------------------------------- #
# Picture 5 — the number nobody has
# --------------------------------------------------------------------------- #
def picture_the_friction_ceiling(jobs) -> None:
    drawn = [outline.diameter_at(0.0) * 1000.0 for outline, _ in family("tapered_glass", 400, 0)]
    chosen = [t["base"][pushed_first(t, c, n)[0]] for t, c, n in jobs]

    figure, (line, bars) = new_figure(13.8, 5.8, columns=2)

    width = np.linspace(min(drawn) - 2.0, max(drawn) + 2.0, 400)
    for mu, colour, style in ((MU_LOW, GOOD, "-"), (TABLE_FRICTION, MUTED, (0, (4, 3))),
                              (MU_HIGH, WARN, "-")):
        line.plot(width, (width / 2.0) / mu, color=colour, lw=2.0, ls=style,
                  label=f"mu {mu}" + (", the simulator's own" if mu == TABLE_FRICTION else ""))
    line.axhline(LOWEST_GRIP, color=INK, lw=1.0, ls=(0, (2, 2)))
    line.axhline(JAW_TOP, color=INK, lw=1.8)
    line.text(max(drawn) + 1, JAW_TOP + 3.0, f"the jaw's top edge, {JAW_TOP:.0f} mm",
              fontsize=NOTE_SIZE, color=INK, ha="right", va="bottom")
    line.text(max(drawn) + 1, LOWEST_GRIP - 3.0, f"the jaw's middle, {LOWEST_GRIP:.0f} mm",
              fontsize=NOTE_SIZE, color=INK, ha="right", va="top")
    # Where each friction's line crosses the push height is the narrowest foot
    # that still slides. Marked at the crossing rather than labelled off to one
    # side, so that no leader has to cross another curve. The crossing is left
    # unnumbered, and so is the axis below it: a figure for the foot here would
    # put a scale on the histogram and so publish the range this kind draws.
    for mu, colour in ((MU_LOW, GOOD), (TABLE_FRICTION, MUTED), (MU_HIGH, WARN)):
        needed = 2.0 * JAW_TOP * mu
        if needed > max(width):
            continue
        line.plot([needed], [JAW_TOP], "o", color=colour, ms=6, zorder=6)
    line.text(max(drawn) + 1, 29.0,
              f"at mu {MU_HIGH} a glass would need a wider foot than this\n"
              f"kind draws, so its crossing is off the chart to the right",
              fontsize=NOTE_SIZE, color=WARN, ha="right", va="center")
    counts, edges = np.histogram(drawn, bins=26)
    line.bar(edges[:-1], 13.0 * counts / counts.max(), width=np.diff(edges), align="edge",
             color=GLASS, alpha=0.40, zorder=0)
    line.text(min(drawn), 15.0, "where the 400 drawn feet actually are", fontsize=NOTE_SIZE,
              color=GLASS, ha="left", va="bottom")
    line.set_xlabel("the foot the glass stands on, from the narrowest this kind draws to the widest",
                    fontsize=LABEL_SIZE, color=INK)
    line.set_xticks([])
    line.set_ylabel("the height a push starts tipping it, mm", fontsize=LABEL_SIZE, color=INK)
    line.set_title("Whether a glass can be pushed at all", fontsize=TITLE_SIZE, color=INK, pad=8)
    line.set_ylim(0, 125)
    line.legend(fontsize=NOTE_SIZE, loc="upper left", frameon=False)
    plain(line)

    shares = {}
    for label, feet in (("400 glasses drawn from the kind", drawn),
                        (f"the {len(chosen)} the nudge picks", chosen)):
        for height in (LOWEST_GRIP, JAW_TOP):
            for mu in (MU_LOW, TABLE_FRICTION, MU_HIGH):
                shares[(label, height, mu)] = (
                    100.0 * sum(topple_height(f, mu) > height for f in feet) / len(feet))

    mus = (MU_LOW, TABLE_FRICTION, MU_HIGH)
    spots = np.arange(len(mus), dtype=float)
    label = "400 glasses drawn from the kind"
    for offset, height, colour, tag in ((-0.18, LOWEST_GRIP, MUTED,
                                         f"if the push were at {LOWEST_GRIP:.0f} mm"),
                                        (0.18, JAW_TOP, WARN,
                                         f"at the real {JAW_TOP:.0f} mm")):
        heights = [shares[(label, height, mu)] for mu in mus]
        bars.bar(spots + offset, heights, color=colour, alpha=0.75, width=0.34, label=tag)
        for spot, share in zip(spots + offset, heights, strict=True):
            bars.text(spot, share + 2.0, f"{share:.1f}%", ha="center", va="bottom",
                      fontsize=NOTE_SIZE, color=colour)
    bars.set_xticks(spots)
    bars.set_xticklabels([f"mu {mu}" for mu in mus], fontsize=LABEL_SIZE, color=INK)
    bars.set_yticks([0, 20, 40, 60, 80, 100])
    bars.set_ylabel("share that can be pushed at all, per cent", fontsize=LABEL_SIZE, color=INK)
    bars.set_title("The 400 drawn glasses, and 15 mm of jaw",
                   fontsize=TITLE_SIZE, color=INK, pad=8)
    bars.set_ylim(0, 118)
    bars.legend(fontsize=NOTE_SIZE, loc="upper right", frameon=False)
    plain(bars)

    footer(figure, (
        "A push at height h slides a glass while h is under a / mu, where a is half the foot and mu "
        f"is the friction with the table. The jaw's middle rides at {LOWEST_GRIP:.0f} mm, but a "
        f"tapered glass is wider higher up and meets the jaw's top edge first, so the push lands at "
        f"{JAW_TOP:.0f} mm and the foot has to be wider than 2 x {JAW_TOP:.0f} x mu. Each dot is "
        f"where a friction's line crosses that height: the narrowest foot that still slides at "
        f"it.\nThose 15 mm cost more than they look. The simulator uses {TABLE_FRICTION} and "
        f"scores the run against it; the arm is never told it and nothing in the cell measures "
        f"it. At {MU_HIGH} the rule asks for a wider foot than this kind ever draws, so at the "
        f"real {JAW_TOP:.0f} mm not one of the 400 may be pushed at all."))
    figure.subplots_adjust(bottom=0.26, top=0.90, wspace=0.24)
    save(figure, "02-the-friction-ceiling.png")
    for (label, height, mu), share in shares.items():
        print(f"  {label}, mu {mu}, pushed at {height:.0f} mm: {share:.1f}% can be pushed at all")
    print(f"  the foot a glass needs at {JAW_TOP:.0f} mm: "
          + ", ".join(f"{2 * JAW_TOP * mu:.1f} mm at mu {mu}" for mu in mus)
          + f"; the kind draws feet {min(drawn):.1f} to {max(drawn):.1f} mm across")


# --------------------------------------------------------------------------- #
# Numbers the prose quotes that no picture carries
# --------------------------------------------------------------------------- #
PUSH_BUDGET = 8

# The complaints that mean a push did physical harm, as against leaving a glass
# where it was. These are the ones problem.md calls a wrong run.
HARM = ("touches another glass", "sweeps through another glass", "outside the glass zone",
        "outside the arm's reach", "into the rack")


def _any_direction_works(t: dict, crowded: int, neighbour: int) -> bool:
    for moved in (crowded, neighbour):
        here = t["at"][moved]
        for degrees in range(0, 360, 10):
            angle = math.radians(degrees)
            for length in range(4, 161, 4):
                landing = (here[0] + length * math.cos(angle), here[1] + length * math.sin(angle))
                if not went_wrong(t, crowded, moved, landing):
                    return True
    return False


def _clear_the_table(t: dict, best: float, guarded: bool):
    """Nudge one crowded glass at a time until the table is clear or the budget runs out.

    The glass is assumed to land where it was aimed, which is the best case: a
    real push does not.
    """
    working = dict(t)
    working["at"] = list(t["at"])
    pushes = 0
    harmed = False
    while pushes < PUSH_BUDGET:
        crowded = [c for c in range(working["n"]) if not room(working, c)]
        if not crowded:
            break
        choice = None
        for c in crowded:
            first = pushed_first(working, c, blocking(working, c))
            for moved, away_from in (first, first[::-1]):
                landing = nudged_to(working, moved, away_from, best)
                if not guarded or not went_wrong(working, c, moved, landing):
                    choice = (c, moved, landing)
                    break
            if choice:
                break
        if choice is None:
            if guarded:
                return pushes, "refused", harmed
            c = crowded[0]
            moved, away_from = pushed_first(working, c, blocking(working, c))
            choice = (c, moved, nudged_to(working, moved, away_from, best))
        c, moved, landing = choice
        trouble = faults(working, c, moved, landing)
        harmed = harmed or any(trouble[name] for name in HARM)
        working["at"][moved] = landing
        pushes += 1
    clear = all(room(working, c) for c in range(working["n"]))
    return pushes, ("done" if clear else "gave up"), harmed


def report(tables, jobs, rows, best: float) -> None:
    print("\nthe population")
    print(f"  {len(tables)} tapered test tables mirrored from bench.scene, seeds {FIRST_SEED} to "
          f"{FIRST_SEED + 4 * (HOW_MANY_TABLES - 1)} step 4, {len(jobs)} glasses without room")
    counts = [sum(1 for c in range(t["n"]) if not room(t, c)) for t in tables]
    print(f"  glasses on a table: {min(t['n'] for t in tables)} to {max(t['n'] for t in tables)}; "
          f"without room: {min(counts)} to {max(counts)}, mean {sum(counts) / len(counts):.2f}")
    reach = sorted(intrusion(t, c, n) for t, c, n in jobs)
    print(f"  the blocking neighbour reaches {reach[0]:.1f} to {reach[-1]:.1f} mm inside the "
          f"{GRIP_ROOM:.0f} mm ring, middle {reach[len(reach) // 2]:.1f} mm")
    gaps = sorted(math.dist(t["at"][c], t["at"][n]) for t, c, n in jobs)
    print(f"  centre to centre for those pairs: {gaps[0]:.1f} to {gaps[-1]:.1f} mm, "
          f"middle {gaps[len(gaps) // 2]:.1f} mm")
    many = sum(1 for t, c, n in jobs
               if sum(intrusion(t, c, k) > 0 for k in range(t["n"]) if k != c) > 1)
    print(f"  crowded by more than one neighbour: {100 * many / len(jobs):.1f}% of them")
    narrow = sum(1 for t, c, n in jobs if t["widest"][c] < t["widest"][n])
    print(f"  the crowded glass is the narrower of the two: {100 * narrow / len(jobs):.1f}%")
    pushes_the_other = sum(1 for t, c, n in jobs if pushed_first(t, c, n)[0] != c)
    print(f"  the method pushes the neighbour rather than the crowded glass: "
          f"{100 * pushes_the_other / len(jobs):.1f}%")

    print("\nthe shortfall-plus-margin rules")
    for label, rule in (
        (f"the overview's {GRIPPABLE_APART:.0f} - d + 20",
         lambda t, c, n, d: GRIPPABLE_APART - d + 20.0),
        (f"the same on the real test, {GRIP_ROOM:.0f} + w/2 - d + 20",
         lambda t, c, n, d: intrusion(t, c, n) + 20.0),
    ):
        tally = dict.fromkeys(FAULTS, 0)
        wrong = 0
        for t, c, n in jobs:
            moved, away_from = pushed_first(t, c, n)
            apart = math.dist(t["at"][moved], t["at"][away_from])
            trouble = faults(t, c, moved,
                             nudged_to(t, moved, away_from, max(0.0, rule(t, c, n, apart))))
            for name, hit in trouble.items():
                tally[name] += hit
            wrong += any(trouble.values())
        print(f"  {label}: wrong on {100 * wrong / len(jobs):.1f}%")
        for name, count in tally.items():
            print(f"    {name}: {100 * count / len(jobs):.1f}%")
    fixed = min(rows, key=lambda r: r["wrong"])
    print(f"  the best fixed distance, {fixed['distance']:.0f} mm: wrong on {fixed['wrong']:.1f}%")
    enough = [(t, c, n) for t, c, n in jobs if intrusion(t, c, n) <= best]
    still = sum(1 for t, c, n in enough if any(nudge(t, c, n, best)[3].values()))
    print(f"  of the {len(enough)} where {best:.0f} mm is far enough on its own, "
          f"{100 * still / len(enough):.1f}% still go wrong for some other reason")

    print("\nwhat one push could manage if it were allowed to choose more")
    ladder = dict.fromkeys(
        ("the fixed nudge, wider foot", "the fixed nudge, either glass",
         "any distance, wider foot", "any distance, either glass",
         "any direction, either glass"), 0)
    for t, c, n in jobs:
        moved, away_from = pushed_first(t, c, n)
        if not went_wrong(t, c, moved, nudged_to(t, moved, away_from, best)):
            ladder["the fixed nudge, wider foot"] += 1
        if any(not went_wrong(t, c, a, nudged_to(t, a, b, best)) for a, b in ((c, n), (n, c))):
            ladder["the fixed nudge, either glass"] += 1
        if any(not went_wrong(t, c, moved, nudged_to(t, moved, away_from, float(d)))
               for d in range(2, 161, 2)):
            ladder["any distance, wider foot"] += 1
        if any(not went_wrong(t, c, a, nudged_to(t, a, b, float(d)))
               for a, b in ((c, n), (n, c)) for d in range(2, 161, 2)):
            ladder["any distance, either glass"] += 1
        if _any_direction_works(t, c, n):
            ladder["any direction, either glass"] += 1
    for name, count in ladder.items():
        print(f"  {name}: gives room to {100 * count / len(jobs):.1f}% of them")

    for mu in (MU_LOW, TABLE_FRICTION, MU_HIGH):
        can = sum(1 for t, c, n in jobs
                  if topple_height(t["base"][pushed_first(t, c, n)[0]], mu) > JAW_TOP)
        print(f"  of the glasses the nudge picks, {100 * can / len(jobs):.1f}% can be pushed at "
              f"{JAW_TOP:.0f} mm at mu {mu}")

    print(f"\nwhole tables, nudging until nothing lacks room, at most {PUSH_BUDGET} pushes")
    for guarded in (False, True):
        done = refused = harmed = 0
        used = []
        for t in tables:
            pushes, ended, harm = _clear_the_table(t, best, guarded)
            done += ended == "done"
            refused += ended == "refused"
            harmed += harm
            used.append(pushes)
        n = len(tables)
        print(f"  {'with the guards' if guarded else 'as written, no guards'}: "
              f"every glass has room on {100 * done / n:.1f}% of tables, "
              f"refused on {100 * refused / n:.1f}%, "
              f"at least one push did harm on {100 * harmed / n:.1f}%, "
              f"mean {sum(used) / n:.2f} pushes")


def main() -> None:
    print(f"building {HOW_MANY_TABLES} tapered test tables from seed {FIRST_SEED} ...")
    tables = all_tables()
    jobs = every_crowded_glass(tables)
    print(f"{len(tables)} tables, {len(jobs)} glasses without room")

    coarse = sweep(jobs, range(2, 162, 2))
    around = int(min(coarse, key=lambda r: r["wrong"])["distance"])
    fine = sweep(jobs, range(max(2, around - 9), around + 10))
    rows = sorted({r["distance"]: r for r in coarse + fine}.values(), key=lambda r: r["distance"])
    best = min(rows, key=lambda r: r["wrong"])["distance"]
    print(f"best nudge distance: {best:.0f} mm")

    picture_the_friction_ceiling(jobs)
    report(tables, jobs, rows, best)


if __name__ == "__main__":
    main()
