"""Diagrams for solution 2 — one fixed nudge.

Every glass drawn here is a real glass, and every arrangement is a real table.
The outlines come from ``work_cell.glasses.shapes`` at sizes drawn from
``KIND_RANGES["tapered_glass"]``, and the places they stand in come from the
layout rule in ``problem-3-sim/bench.py``, which is the generator the real runs
are scored against. No glass's size is written down in this file.

**Why the layout rule is copied rather than imported.** ``bench.py`` imports
MuJoCo, which is installed in ``problem-3-programmed`` and
``problem-3-learned`` but not in the root environment every generator in this
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

    pixi run python images/generators/problem-3/make_02_images.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from diagram_style import (
    FINGER_HEIGHT,
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
    glass_from_the_side,
    grip_ring,
    has_room,
    in_reach,
    in_zone,
    push_arrow,
    save,
    topple_height,
)
from diagram_style import (
    new as new_figure,
)
from matplotlib.patches import Circle, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import draw, family  # noqa: E402
from work_cell.rack.layout import GLASS_ZONE as ZONE_M  # noqa: E402

# --------------------------------------------------------------------------- #
# problem-3-sim/bench.py, mirrored. Metres, as it is written there.
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
def picture_the_nudge_on_a_real_table(best: float) -> None:
    t = table(EASY_SEED)
    crowded, = (k for k in range(t["n"]) if not room(t, k))
    neighbour = blocking(t, crowded)
    moved, away_from, landing, trouble = nudge(t, crowded, neighbour, best)
    apart = math.dist(t["at"][crowded], t["at"][neighbour])
    reaches_in = intrusion(t, crowded, neighbour)
    after = list(t["at"])
    after[moved] = landing

    figure, (plan, side) = new_figure(13.8, 6.8, columns=2)

    panel(plan, f"Why {LETTERS[crowded]} has no room, and what the nudge does about it")
    zone(plan)
    draw_table(plan, t, rings=(crowded,),
               faded=[k for k in range(t["n"]) if k not in (crowded, neighbour)])
    push_arrow(plan, t["at"][moved], landing, colour=GOOD, lw=2.2)
    glass_from_above(plan, landing, t["widest"][moved],
                     base_fraction=t["base"][moved] / t["widest"][moved],
                     colour=GOOD, alpha=0.22, edge=GOOD)
    for k in range(t["n"]):
        name_glass(plan, t["at"][k], LETTERS[k])
    # Both labels live in the empty column to the right of every glass, so that
    # neither one, and neither leader, has to cross anything.
    lead(plan, f"{LETTERS[crowded]} needs {GRIP_ROOM:.0f} mm of\nclear table all round.\n"
               f"{LETTERS[neighbour]}'s rim reaches\n{reaches_in:.1f} mm inside it",
         (t["at"][crowded][0] + GRIP_ROOM, t["at"][crowded][1]), (700, -250), WARN,
         ha="left", va="center")
    lead(plan, f"{LETTERS[moved]} has the wider foot,\nso {LETTERS[moved]} is the one pushed\n"
               f"{best:.0f} mm away from {LETTERS[crowded]}:\n"
               f"now {math.dist(landing, t['at'][crowded]):.1f} mm apart",
         ((t["at"][moved][0] + landing[0]) / 2.0, (t["at"][moved][1] + landing[1]) / 2.0),
         (700, -80), GOOD, ha="left", va="center")
    plan.set_xlim(250, 815)
    plan.set_ylim(-475, -15)

    panel(side, "The height the push is really made at")
    side.axhspan(LOWEST_GRIP - FINGER_HEIGHT / 2.0, JAW_TOP, facecolor=MUTED, alpha=0.20,
                 zorder=1)
    side.axhline(JAW_TOP, color=INK, lw=1.7, zorder=7)
    places = {crowded: 0.0, neighbour: 200.0}
    for k, offset in places.items():
        rim = t["widest"][k]
        glass_from_the_side(side, offset, t["height"][k], rim,
                            base_fraction=t["base"][k] / rim, colour=GLASS, alpha=0.24,
                            edge=GLASS)
        note(side, offset, -14, f"{LETTERS[k]}: a foot {t['base'][k]:.1f} mm across", INK,
             ha="center", va="top")
        on_the_left = offset == 0.0
        for mu, colour, style in ((MU_LOW, GOOD, "-"), (MU_HIGH, WARN, (0, (5, 3)))):
            h = topple_height(t["base"][k], mu)
            side.plot([offset - rim * 0.62, offset + rim * 0.62], [h, h], color=colour,
                      lw=1.6, ls=style, zorder=8)
            # A topple height within a few millimetres of the jaw's top edge
            # would print its label over that line, so it is nudged clear.
            near = JAW_TOP - 9.0 < h < JAW_TOP + 9.0
            side.text(offset + (-rim * 0.66 if on_the_left else rim * 0.66),
                      h - 14.0 if near else h,
                      f"{h:.1f} mm, mu {mu}", fontsize=NOTE_SIZE, color=colour,
                      ha="right" if on_the_left else "left", va="center")
    lead(side, f"the closed jaw is {FINGER_HEIGHT:.0f} mm tall and its middle rides at\n"
               f"{LOWEST_GRIP:.0f} mm, so a glass that flares outwards meets its\n"
               f"top edge first, at {JAW_TOP:.0f} mm. That is the push height",
         (100, JAW_TOP), (100, 300), INK, ha="center", va="bottom")
    note(side, -138, 412,
         "green: the height a push starts tipping the glass over, if the friction is 0.3\n"
         "red: the same height if it is 0.5, and nothing in the cell tells the arm which",
         MUTED, ha="left", va="top")
    side.set_xlim(-140, 340)
    side.set_ylim(-60, 420)

    footer(figure, (
        f"Table {EASY_SEED} from the spawner, four tapered glasses. {LETTERS[crowded]} is the narrow "
        f"one and it has no room, because room is measured to a neighbour's edge and "
        f"{LETTERS[neighbour]} is wide. {LETTERS[neighbour]} itself has room at the same "
        f"{apart:.1f} mm, because its neighbour is only {t['widest'][crowded]:.1f} mm "
        f"across.\nThe nudge pushes whichever of the two has the wider foot, which here is "
        f"{LETTERS[neighbour]}, and that is lucky: at a friction of {MU_LOW} it is the only one of "
        f"the two that slides rather than tipping.\nOn the right is the part the nudge cannot "
        f"choose. The push lands at {JAW_TOP:.0f} mm, and whether that slides a glass or tips it "
        f"over turns on a friction the arm is never told."))
    figure.subplots_adjust(bottom=0.17, top=0.92, wspace=0.08)
    save(figure, "02-the-nudge-on-a-real-table.png")
    print(f"  table {EASY_SEED}: {LETTERS[crowded]} has no room; {LETTERS[neighbour]}'s rim reaches "
          f"{reaches_in:.1f} mm inside its {GRIP_ROOM:.0f} mm ring, at {apart:.1f} mm between "
          f"middles")
    print(f"    {LETTERS[neighbour]} needs {GRIP_ROOM + t['widest'][crowded] / 2:.1f} mm and has "
          f"{apart:.1f}, so it has room while {LETTERS[crowded]} does not")
    print(f"    pushed {LETTERS[moved]} {best:.0f} mm; {LETTERS[crowded]} now "
          f"{math.dist(landing, t['at'][crowded]):.1f} mm off and "
          f"{'has room' if room(t, crowded, after) else 'still has none'}; faults "
          f"{[n for n, hit in trouble.items() if hit] or 'none'}")
    for k in range(t["n"]):
        heights = {mu: topple_height(t["base"][k], mu) for mu in (MU_LOW, TABLE_FRICTION, MU_HIGH)}
        print(f"    {LETTERS[k]}: height {t['height'][k]:.1f} mm, widest {t['widest'][k]:.1f} mm, "
              f"foot {t['base'][k]:.1f} mm, tips above "
              + ", ".join(f"{h:.1f} mm at mu {mu}" for mu, h in heights.items())
              + f"; pushable at {JAW_TOP:.0f} mm for mu "
              + ", ".join(str(mu) for mu, h in heights.items() if h > JAW_TOP))


# --------------------------------------------------------------------------- #
# Picture 2 — the sweep, and why no single distance can be right
# --------------------------------------------------------------------------- #
def picture_the_sweep(rows: list[dict], jobs, best: float) -> None:
    figure, (curve, spread) = new_figure(13.8, 5.4, columns=2)

    distance = [r["distance"] for r in rows]
    curve.plot(distance, [r["wrong"] for r in rows], color=INK, lw=2.4,
               label="anything at all wrong")
    curve.plot(distance, [r["the glass still has no room"] for r in rows], color=GLASS, lw=1.7,
               label="the glass still has no room")
    curve.plot(distance, [r["outside the glass zone"] for r in rows], color=WARN, lw=1.7,
               label="outside the glass zone")
    curve.plot(distance, [met_a_glass(r) for r in rows], color=WARN, lw=1.7, ls=(0, (5, 3)),
               label="met another glass")
    low = min(rows, key=lambda r: r["wrong"])
    curve.axvline(low["distance"], color=GOOD, lw=1.3, ls=(0, (4, 3)), zorder=1)
    curve.plot([low["distance"]], [low["wrong"]], "o", color=GOOD, ms=6, zorder=6)
    lead(curve, f"the best a fixed distance can do:\n{low['distance']:.0f} mm, and still "
                f"{low['wrong']:.1f}% wrong",
         (low["distance"], low["wrong"]), (low["distance"] + 6, low["wrong"] + 26), GOOD,
         ha="left", va="bottom")
    curve.set_xlabel("how far the nudge pushes, mm", fontsize=LABEL_SIZE, color=INK)
    curve.set_ylabel("share of glasses without room, per cent", fontsize=LABEL_SIZE, color=INK)
    curve.set_title("Every nudge distance is wrong in one of two ways",
                    fontsize=TITLE_SIZE, color=INK, pad=8)
    curve.set_xlim(0, max(distance))
    curve.set_ylim(0, 100)
    curve.legend(fontsize=NOTE_SIZE - 0.4, loc="lower right", frameon=False)
    plain(curve)

    needed = sorted(intrusion(t, c, n) for t, c, n in jobs)
    spread.hist(needed, bins=32, color=GLASS, alpha=0.55, edgecolor=GLASS)
    middle = needed[len(needed) // 2]
    top = spread.get_ylim()[1] * 1.24
    spread.set_ylim(0, top)
    spread.axvline(best, color=GOOD, lw=1.7)
    spread.axvline(middle, color=INK, lw=1.2, ls=(0, (4, 3)))
    spread.text(best + 0.6, top * 0.97, f"the one nudge,\n{best:.0f} mm", fontsize=NOTE_SIZE,
                color=GOOD, ha="left", va="top")
    spread.text(middle - 0.6, top * 0.97, f"the middle glass\nneeds {middle:.1f} mm",
                fontsize=NOTE_SIZE, color=INK, ha="right", va="top")
    spread.set_xlabel("how far the glass has to move to clear its own ring, mm",
                      fontsize=LABEL_SIZE, color=INK)
    spread.set_ylabel("glasses without room", fontsize=LABEL_SIZE, color=INK)
    spread.set_title("What the glasses actually need", fontsize=TITLE_SIZE, color=INK, pad=8)
    plain(spread)

    footer(figure, (
        f"{len(jobs)} glasses without room, on {HOW_MANY_TABLES} tables. Left: a short nudge leaves "
        f"the glass where it was, a long one carries it out of the zone or into another glass, and "
        f"the two curves cross at {low['distance']:.0f} mm.\nRight: what one glass has to move to "
        f"clear its own ring runs from {needed[0]:.1f} to {needed[-1]:.1f} mm, so one distance "
        f"overshoots most of them and falls short for the rest. That is the case against a fixed "
        f"number."))
    figure.subplots_adjust(bottom=0.25, top=0.90, wspace=0.22)
    save(figure, "02-the-nudge-distance-sweep.png")
    print(f"  sweep over {len(jobs)} glasses without room: best {low['distance']:.0f} mm at "
          f"{low['wrong']:.1f}% wrong")
    for r in rows:
        if r["distance"] in (4.0, 10.0, 16.0, low["distance"], 30.0, 40.0, 60.0, 90.0, 120.0):
            print(f"    {r['distance']:5.0f} mm: wrong {r['wrong']:5.1f}%  still no room "
                  f"{r['the glass still has no room']:5.1f}%  met a glass {met_a_glass(r):5.1f}%  "
                  f"out of the zone {r['outside the glass zone']:5.1f}%  out of reach "
                  f"{r['outside the arm\'s reach']:4.1f}%  rack {r['into the rack']:4.1f}%")
    print(f"    the move each glass needs: {needed[0]:.1f} to {needed[-1]:.1f} mm, "
          f"middle {middle:.1f} mm")


# --------------------------------------------------------------------------- #
# Picture 3 — the failure that separates this from solution 3
# --------------------------------------------------------------------------- #
def picture_into_another_glass(best: float) -> None:
    t = table(HARD_SEED)
    crowded = max(range(t["n"]),
                  key=lambda c: sum(intrusion(t, c, k) > 0 for k in range(t["n"]) if k != c))
    blockers = [k for k in range(t["n"]) if k != crowded and intrusion(t, crowded, k) > 0]
    spare = [k for k in range(t["n"]) if k != crowded and k not in blockers]

    figure, axes = new_figure(13.8, 6.0, columns=2)
    for axis, neighbour in zip(axes, blockers, strict=True):
        other = next(k for k in blockers if k != neighbour)
        apart = math.dist(t["at"][crowded], t["at"][neighbour])
        panel(axis, f"{LETTERS[crowded]} pushed away from {LETTERS[neighbour]}, "
                    f"which stands {apart:.1f} mm off")
        draw_table(axis, t, faded=spare)
        moved, away_from, landing, trouble = nudge(t, crowded, neighbour, best)
        glass_from_above(axis, landing, t["widest"][moved],
                         base_fraction=t["base"][moved] / t["widest"][moved],
                         colour=WARN, alpha=0.34, edge=WARN)
        push_arrow(axis, t["at"][moved], landing, colour=WARN, lw=2.2)
        overlap = ((t["widest"][moved] + t["widest"][other]) / 2.0
                   - math.dist(landing, t["at"][other]))
        for k in range(t["n"]):
            name_glass(axis, t["at"][k], LETTERS[k])
        note(axis, landing[0] + 74, landing[1],
             f"lands {overlap:.1f} mm\ninside {LETTERS[other]}", WARN, ha="left", va="center")
        print(f"  table {HARD_SEED}: {LETTERS[crowded]} pushed {best:.0f} mm away from "
              f"{LETTERS[neighbour]} ({apart:.1f} mm off, reaching "
              f"{intrusion(t, crowded, neighbour):.1f} mm into the ring) lands {overlap:.1f} mm "
              f"inside {LETTERS[other]}; faults {[n for n, hit in trouble.items() if hit]}")
        axis.set_xlim(300, 730)
        axis.set_ylim(-437, -113)
    for k in range(t["n"]):
        print(f"    {LETTERS[k]}: widest {t['widest'][k]:.1f} mm, foot {t['base'][k]:.1f} mm, "
              f"tips above {topple_height(t['base'][k], MU_LOW):.1f} mm at mu {MU_LOW} and "
              f"{topple_height(t['base'][k], MU_HIGH):.1f} mm at mu {MU_HIGH}")

    footer(figure, (
        f"Table {HARD_SEED} from the spawner, with {LETTERS[spare[0]]} faded because no push here "
        f"goes near it. {LETTERS[crowded]} has {LETTERS[blockers[0]]} inside its ring on one side "
        f"and {LETTERS[blockers[1]]} on the other, and it has the wider foot in both pairs, so it "
        f"is the glass the method picks both times.\nThe nudge has only two directions to offer and "
        f"each one drives {LETTERS[crowded]} into the glass on the other side. Nothing in the method "
        f"looks at the third glass, so nothing stops either push."))
    figure.subplots_adjust(bottom=0.15, top=0.91, wspace=0.06)
    save(figure, "02-into-another-glass.png")


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


def picture_where_a_glass_may_land(best: float) -> None:
    figure, axes = new_figure(13.8, 6.0, columns=2)
    numbers = []
    for axis, seed in zip(axes, (EASY_SEED, HARD_SEED), strict=True):
        t = table(seed)
        crowded = max(range(t["n"]),
                      key=lambda c: (not room(t, c),
                                     sum(intrusion(t, c, k) > 0 for k in range(t["n"]) if k != c)))
        neighbour = blocking(t, crowded)
        moved, away_from, landing, trouble = nudge(t, crowded, neighbour, best)
        xs, ys, good = _legal_map(t, crowded, moved)
        wrong = any(trouble.values())

        panel(axis, f"Table {seed}: everywhere {LETTERS[moved]} may legally land")
        axis.pcolormesh(xs, ys, np.ma.masked_where(~good, good.astype(float)),
                        cmap="Greens", vmin=0.0, vmax=2.0, shading="nearest", zorder=0)
        zone(axis, label=False)
        draw_table(axis, t)
        for k in range(t["n"]):
            name_glass(axis, t["at"][k], LETTERS[k])
        here = t["at"][moved]
        axis.add_patch(Circle(here, best, facecolor="none", edgecolor=INK, lw=1.3,
                              ls=(0, (5, 3)), zorder=6))
        axis.plot([landing[0]], [landing[1]], marker="X", ms=11,
                  color=WARN if wrong else GOOD, zorder=8)
        rows, columns = np.nonzero(good)
        shortest = (min(math.dist(here, (float(xs[c]), float(ys[r])))
                        for r, c in zip(rows, columns, strict=True)) if len(rows) else math.inf)
        numbers.append((seed, moved, shortest, wrong, float(good.mean())))
        # The label goes to the right of the landing, which is the one side
        # that is clear on both of these tables.
        note(axis, landing[0] + 56, landing[1],
             "the nudge lands here,\nand it is not legal" if wrong
             else "the nudge lands here,\nand it is legal",
             WARN if wrong else GOOD, ha="left", va="center")
        note(axis, 180, -500,
             f"the dashed circle is every spot {best:.0f} mm away.\n"
             f"the shortest legal push for {LETTERS[moved]} is {shortest:.0f} mm", INK,
             ha="left", va="bottom")
        axis.set_xlim(170, 830)
        axis.set_ylim(-510, -35)

    footer(figure, (
        "The green is every spot where the crowded glass ends with the room the jaw needs, nothing "
        "that had room loses it, no glass is struck on the way, and the landing is inside the zone "
        f"and the reach.\nThe dashed circle is the one distance the nudge ever pushes. On table "
        f"{numbers[0][0]} it crosses the green and the nudge lands in it. On table {numbers[1][0]} "
        f"the nearest legal spot is {numbers[1][2]:.0f} mm away, so no nudge of {best:.0f} mm in "
        "any direction could have worked. The method never works this region out, which is the "
        "whole difference between it and solution 3."))
    figure.subplots_adjust(bottom=0.13, top=0.94, wspace=0.06)
    save(figure, "02-where-a-glass-may-land.png")
    for seed, moved, shortest, wrong, share in numbers:
        print(f"  table {seed}: pushing {LETTERS[moved]}, shortest legal push {shortest:.1f} mm, "
              f"the {best:.0f} mm nudge is {'wrong' if wrong else 'legal'}, "
              f"{100 * share:.1f}% of the drawn area is legal")


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
    # side, so that no leader has to cross another curve.
    for mu, colour in ((MU_LOW, GOOD), (TABLE_FRICTION, MUTED), (MU_HIGH, WARN)):
        needed = 2.0 * JAW_TOP * mu
        if needed > max(width):
            continue
        line.plot([needed], [JAW_TOP], "o", color=colour, ms=6, zorder=6)
        line.text(needed, JAW_TOP - 4.0, f"{needed:.1f}", fontsize=NOTE_SIZE, color=colour,
                  ha="center", va="top")
    line.text(max(drawn) + 1, 22.0,
              f"at mu {MU_HIGH} the foot would have to be {2 * JAW_TOP * MU_HIGH:.0f} mm,\n"
              f"off this chart to the right", fontsize=NOTE_SIZE, color=WARN,
              ha="right", va="center")
    counts, edges = np.histogram(drawn, bins=26)
    line.bar(edges[:-1], 13.0 * counts / counts.max(), width=np.diff(edges), align="edge",
             color=GLASS, alpha=0.40, zorder=0)
    line.text(min(drawn), 15.0, "where the 400 drawn feet actually are", fontsize=NOTE_SIZE,
              color=GLASS, ha="left", va="bottom")
    line.set_xlabel("the foot the glass stands on, mm across", fontsize=LABEL_SIZE, color=INK)
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
        f"{JAW_TOP:.0f} mm and the foot has to be wider than 2 x {JAW_TOP:.0f} x mu.\nThose 15 mm "
        f"cost more than they look. The simulator uses {TABLE_FRICTION} and scores the run against "
        f"it; the arm is never told it and nothing in the cell measures it. At {MU_HIGH} the foot "
        f"would have to be {2 * JAW_TOP * MU_HIGH:.0f} mm across, which is wider than the widest "
        f"this kind draws."))
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

    picture_the_nudge_on_a_real_table(best)
    picture_the_sweep(rows, jobs, best)
    picture_into_another_glass(best)
    picture_where_a_glass_may_land(best)
    picture_the_friction_ceiling(jobs)
    report(tables, jobs, rows, best)


if __name__ == "__main__":
    main()
