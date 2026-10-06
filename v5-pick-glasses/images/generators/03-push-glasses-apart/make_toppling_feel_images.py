"""Diagrams and measurements for solution 3 — plan, feel, look again.

Solution 3 is built. ``03-push-glasses-apart/01-one-fixed-nudge/plan.py`` chooses the pushes and
``03-push-glasses-apart/bench/bench.py`` makes the tables and the physics, so this script
does not invent either. It mirrors both:

* ``scene(seed)`` here reproduces ``bench.scene(seed)`` exactly — the same kind,
  the same count, the same outlines and the same positions. A throwaway script
  under ``03-push-glasses-apart/01-one-fixed-nudge`` checked that against the real thing on 80
  seeds and found no disagreement at all; the check is quoted in the document.
* ``slides``, ``along``, ``choose`` and ``shortfall`` here are the same
  arithmetic as ``plan.py``, in millimetres instead of metres.

The mirror exists for one reason. ``bench.py`` imports MuJoCo, which is not in
the root environment, and every diagram generator in this repository has to run
from the project root under that environment. Anything that needs the physics
rather than the geometry is therefore *recorded* rather than recomputed:
``STORY`` below holds a real run of ``03-push-glasses-apart/01-one-fixed-nudge`` on table 10001,
and ``SCORED`` holds the numbers from its ``results.json``.

No glass size is written down here. Every outline comes from
``work_cell.glasses.shapes.draw`` inside its kind's declared range, which is
what ``bench.scene`` calls.

    pixi run python images/generators/03-push-glasses-apart/make_toppling_feel_images.py
"""

from __future__ import annotations

import math
import random
import statistics as st
import sys
from collections import Counter
from dataclasses import dataclass
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
    glass_from_the_side,
    grip_ring,
    has_room,
    in_reach,
    in_zone,
    new,
    push_arrow,
    save,
    topple_height,
)
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.arm.dimensions import FINGERTIP_OFFSET  # noqa: E402
from work_cell.glasses.shapes import KIND_RANGES, draw  # noqa: E402
from work_cell.rack.layout import GLASS_ZONE as ZONE_M  # noqa: E402

# --------------------------------------------------------------------------- #
# The jaw, from 03-push-glasses-apart/bench/bench.py, in millimetres. These are the arm's own
# numbers, taken from arm/gripper.urdf.xacro by the examiner.
# --------------------------------------------------------------------------- #

FINGER_LENGTH = 120.0                   # bench.FINGER_LENGTH
JAW_THICKNESS = 2 * (10.0 + 4.0)        # bench.JAW_THICKNESS: two fingers and two pads
BODY_SIZE = 90.0                        # bench.BODY_SIZE: the body behind the fingers
BODY_LENGTH = 50.0                      # bench.BODY_LENGTH
WRIST_LENGTH = 100.0                    # bench.WRIST_LENGTH
TOOL_LENGTH = FINGER_LENGTH + BODY_LENGTH + WRIST_LENGTH   # bench.TOOL_LENGTH
TIP_TO_FLANGE = FINGERTIP_OFFSET * 1000.0                  # arm/dimensions.py

# JAW_TOP comes from diagram_style: the middle of the jaw rides at LOWEST_GRIP
# and the jaw is FINGER_HEIGHT tall, so its top edge is 15 mm higher, and that
# top edge is what a glass which flares outwards meets first.

# What the examiner measures and what it hides, from bench.py.
POSITION_NOISE = 0.5                    # bench.POSITION_NOISE, one standard deviation
WIDTH_NOISE = 2.5                       # bench.WIDTH_NOISE
FEEL_SPEED = 10.0                       # bench.FEEL_SPEED, mm/s
TOUCH_FORCE = 0.1                       # bench.TOUCH_FORCE, newtons
CROWD_SHARE = 0.6                       # bench.CROWD_SHARE
START_GAP = 5.0                         # bench.START_GAP
KINDS = ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass")
TEST_SEEDS = 10_000                     # bench.TEST_SEEDS: held-out tables start here

# --------------------------------------------------------------------------- #
# The planner, from 03-push-glasses-apart/01-one-fixed-nudge/plan.py, in millimetres.
# --------------------------------------------------------------------------- #

MU_LOWEST = 0.2                         # plan.MU_LOWEST
MU_HIGHEST = 0.5                        # plan.MU_HIGHEST
PROBE = 5.0                             # plan.PROBE: the length of a test push
PROBE_MOVED = 1.5                       # plan.PROBE_MOVED: a probe counts as a slide over this
PROBE_LEAN_SHARE = 0.7                  # plan.PROBE_LEAN_SHARE
CENTRE_OF_MASS_SHARE = 2 / 3            # plan.CENTRE_OF_MASS_SHARE
AIM_MARGIN = 10.0                       # plan.AIM_MARGIN
APPROACH_GAP = 10.0                     # plan.APPROACH_GAP
FEEL_BEYOND = 30.0                      # plan.FEEL_BEYOND
CLEARANCE = 8.0                         # plan.CLEARANCE
LEAST_EASING = 10.0                     # plan.LEAST_EASING
HEADINGS = 72                           # plan.HEADINGS
STEP = 2.0                              # plan.STEP
LONGEST_PUSH = 150.0                    # plan.LONGEST_PUSH

# --------------------------------------------------------------------------- #
# What only the physics can say. Both blocks are recorded output, not guesses.
# --------------------------------------------------------------------------- #

# 03-push-glasses-apart/01-one-fixed-nudge/results.json, the full held-out run of 50 tables.
SCORED = dict(scenes=50, glasses=251, crowded_at_start=190, done=35, incomplete=15, wrong=0,
              racked=199, refused=52, toppled=0, out_of_zone=0, picked_without_room=0,
              pushes=212, repeats=90, aim_median=1.0, aim_worst=3.9,
              refused_because="nowhere clear to push it to")

# One real run of 03-push-glasses-apart/01-one-fixed-nudge on table 10001, six tapered glasses,
# recorded by the throwaway measurement script under that directory. Positions
# and landings are the simulator's own record, in millimetres.
STORY = dict(
    seed=10001,
    taken_first=[0, 2, 4],
    pushes=[
        dict(glass=3, probe_moved=4.08, before=(484.74, -167.71), travel=54.0,
             aim=(431.27, -171.88), landed=(432.11, -172.33), miss=0.95,
             touched=19.36, peak=0.95),
        dict(glass=1, probe_moved=1.93, before=(525.03, -255.67), travel=46.0,
             aim=(510.28, -211.74), landed=(510.16, -214.85), miss=3.11,
             touched=24.52, peak=1.82),
    ],
    racked=6,
    refused={},
)

NAMES = "ABCDEFGHI"


# --------------------------------------------------------------------------- #
# The tables. An exact mirror of bench.scene, which is why it is written in
# metres: the rejection sampler has to make the same comparisons in the same
# order on the same random numbers, or it produces a different table.
# --------------------------------------------------------------------------- #

def _room_in_metres(x, y, others) -> bool:
    return all(math.dist((x, y), (ox, oy)) >= GRIP_ROOM / 1000.0 + width / 2
               for ox, oy, width in others)


def _crowded_layout(rng, widths):
    """Mirror of bench._crowded_layout. Metres in, metres out, or None."""
    x_min, x_max, y_min, y_max = ZONE_M
    gap = START_GAP / 1000.0
    room = GRIP_ROOM / 1000.0
    placed: list[tuple[float, float, float]] = []
    for width in widths:
        for _ in range(300):
            if placed and rng.random() < CROWD_SHARE:
                px, py, pwidth = rng.choice(placed)
                near = rng.uniform((width + pwidth) / 2 + gap, room + max(width, pwidth) / 2)
                angle = rng.uniform(-math.pi, math.pi)
                x, y = px + near * math.cos(angle), py + near * math.sin(angle)
            else:
                x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
            if (x_min <= x <= x_max and y_min <= y <= y_max) and all(
                    math.dist((x, y), (qx, qy)) >= (width + qwidth) / 2 + gap
                    for qx, qy, qwidth in placed):
                placed.append((x, y, width))
                break
        else:
            return None
    crowded = [not _room_in_metres(p[0], p[1], [q for q in placed if q is not p]) for p in placed]
    return [(x, y) for x, y, _ in placed] if any(crowded) else None


@dataclass(frozen=True)
class Glass:
    """One glass on the table, in millimetres, as the arm would see it measured."""

    id: int
    x: float
    y: float
    height: float
    widest: float
    foot: float
    outline: object

    @property
    def spot(self) -> tuple[float, float]:
        return (self.x, self.y)


def scene(seed: int) -> list[Glass]:
    """Mirror of bench.scene(seed): four to six glasses, at least one without room."""
    rng = random.Random(seed)
    kind, count = KINDS[seed % len(KINDS)], 4 + seed % 3
    for _ in range(200):
        outlines = [draw(kind, rng)[0] for _ in range(count)]
        spots = _crowded_layout(rng, [o.max_diameter for o in outlines])
        if spots is not None:
            return [Glass(id=i, x=1000 * x, y=1000 * y,
                          height=1000 * outline.total_height,
                          widest=1000 * outline.max_diameter,
                          foot=2000 * float(outline.radius[0]),
                          outline=outline)
                    for i, (outline, (x, y)) in enumerate(zip(outlines, spots, strict=True))]
    raise RuntimeError(f"no crowded layout for scene {seed}")


def tapered_seeds(count: int, start: int = TEST_SEEDS) -> list[int]:
    """The held-out tables of the tapered kind. bench.scene cycles the four kinds."""
    out, seed = [], start
    while len(out) < count:
        if seed % len(KINDS) == KINDS.index("tapered_glass"):
            out.append(seed)
        seed += 1
    return out


def layout_of(glasses) -> list[tuple[float, float, float]]:
    """(x, y, widest) per glass, which is what has_room takes."""
    return [(g.x, g.y, g.widest) for g in glasses]


def with_margin(others, margin: float) -> list[tuple[float, float, float]]:
    """``others`` with every width inflated so that has_room applies a margin.

    diagram_style.has_room has no margin argument and bench.has_room does, and
    adding ``margin`` to the threshold is the same as adding twice it to the
    neighbour's width. This is how plan.py's AIM_MARGIN is applied here.
    """
    return [(x, y, width + 2.0 * margin) for x, y, width in others]


def crowded(glasses) -> list[Glass]:
    """The glasses the gripper cannot get round, by the project's own asymmetric test."""
    return [g for g in glasses
            if not has_room(g.spot, [o for o in layout_of(glasses) if o != (g.x, g.y, g.widest)])]


# --------------------------------------------------------------------------- #
# The planner. A mirror of plan.py.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Push:
    """One push, as plan.py proposes it."""

    glass: int
    start: tuple[float, float]
    heading: float
    travel: float
    aim: tuple[float, float]


# Why a candidate push was rejected. plan.py does not label these; the labels
# are here so that a picture can show which comparison stopped which push.
SAFE_WITH_ROOM, SAFE_NO_ROOM, OUT_OF_ZONE, OUT_OF_REACH = range(4)
GLASS_CLASH, JAW_CLASH, BODY_CLASH = range(4, 7)

WHY = {
    SAFE_WITH_ROOM: "safe, and gives the glass room",
    SAFE_NO_ROOM: "safe, but the glass still has no room there",
    OUT_OF_ZONE: "outside the glass zone",
    OUT_OF_REACH: "the flange would be outside the comfortable reach",
    GLASS_CLASH: "the glass would close on another glass",
    JAW_CLASH: "the fingers would hit another glass",
    BODY_CLASH: "the body or the wrist would hit another glass",
}

COLOURS = {
    SAFE_WITH_ROOM: GOOD,
    SAFE_NO_ROOM: "#c9a227",
    OUT_OF_ZONE: MUTED,
    OUT_OF_REACH: "#3f6f8f",
    GLASS_CLASH: WARN,
    JAW_CLASH: "#7a5ea8",
    BODY_CLASH: "#b2538c",
}


def slides(glass: Glass) -> str:
    """Mirror of plan.slides: "yes", "no" or "try".

    A push slides the glass while it is lower than a / mu, half the foot over
    the friction, and the height that counts is the jaw's top edge, because a
    glass that is wider higher up meets the jaw there first. "try" means the
    answer depends on a number nobody has, and that a 5 mm probe is safe: safe
    because the lean a 5 mm push could cause is well short of the angle the
    glass would have to pass to fall.
    """
    half_foot = glass.foot / 2.0
    if half_foot / MU_HIGHEST > JAW_TOP:
        return "yes"
    if half_foot / MU_LOWEST <= JAW_TOP:
        return "no"
    falls_past = math.atan2(half_foot, CENTRE_OF_MASS_SHARE * glass.height)
    return "try" if math.atan2(PROBE, JAW_TOP) < PROBE_LEAN_SHARE * falls_past else "no"


def segment_distance(point, a, b) -> float:
    """How close a line from a to b comes to a point. Mirror of plan.segment_distance."""
    point, a, b = np.asarray(point, float), np.asarray(a, float), np.asarray(b, float)
    along = b - a
    fraction = float(np.clip((point - a) @ along / max(along @ along, 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(point - (a + fraction * along)))


def shortfall(layout) -> float:
    """How much room the table is short of, summed over its glasses. Mirror of plan.shortfall."""
    total = 0.0
    for i, (x, y, _width) in enumerate(layout):
        worst = max((GRIP_ROOM + w / 2.0 - math.dist((x, y), (ox, oy))
                     for j, (ox, oy, w) in enumerate(layout) if j != i), default=0.0)
        total += max(0.0, worst)
    return total


def along(glass: Glass, others, heading: float, trace: list | None = None) -> list[Push]:
    """Every safe push of ``glass`` along ``heading``, shortest first. Mirror of plan.along.

    ``trace`` collects (point, why) for every length tried, which is what the
    search pictures draw. plan.py stops a heading at its first clash, because a
    clash at one length is still there at every longer one, so the trace stops
    there too.
    """
    unit = np.array([math.cos(heading), math.sin(heading)])
    middle = np.array(glass.spot, float)
    radius = glass.widest / 2.0
    start = middle - (radius + APPROACH_GAP) * unit
    wrist = start - TOOL_LENGTH * unit
    if not (in_reach(start - TIP_TO_FLANGE * unit) and in_reach(middle - TIP_TO_FLANGE * unit)):
        return []

    rest = layout_of(others)
    safe: list[Push] = []
    for travel in np.arange(STEP, LONGEST_PUSH + 1e-9, STEP):
        end = middle + travel * unit
        spot = (float(end[0]), float(end[1]))
        if not in_zone(spot):
            if trace is not None:
                trace.append((spot, OUT_OF_ZONE))
            break
        if not in_reach(end - TIP_TO_FLANGE * unit):
            if trace is not None:
                trace.append((spot, OUT_OF_REACH))
            break
        clash = None
        for other in others:
            centre, other_radius = np.array(other.spot, float), other.widest / 2.0
            # A glass may already stand closer to a neighbour than CLEARANCE.
            # Moving it is fine as long as it comes no closer.
            passing = min(radius + other_radius + CLEARANCE,
                          float(np.linalg.norm(centre - middle)) - 1.0)
            if segment_distance(centre, middle, end) < passing:
                clash = GLASS_CLASH
            elif (segment_distance(centre, start - FINGER_LENGTH * unit, end)
                  < JAW_THICKNESS / 2.0 + other_radius + CLEARANCE):
                clash = JAW_CLASH
            elif (segment_distance(centre, wrist, end - FINGER_LENGTH * unit)
                  < BODY_SIZE / 2.0 + other_radius + CLEARANCE):
                clash = BODY_CLASH
            if clash is not None:
                break
        if clash is not None:
            if trace is not None:
                trace.append((spot, clash))
            break
        frees = has_room(spot, with_margin(rest, AIM_MARGIN))
        if trace is not None:
            trace.append((spot, SAFE_WITH_ROOM if frees else SAFE_NO_ROOM))
        safe.append(Push(glass=glass.id, start=(float(start[0]), float(start[1])),
                         heading=heading, travel=float(travel), aim=spot))
        if frees:
            break
    return safe


def search(glass: Glass, others, trace: list | None = None) -> list[Push]:
    """Every safe push of one glass, over all 72 headings. Mirror of plan.choose's inner loop."""
    out = []
    for index in range(HEADINGS):
        out.extend(along(glass, others, index * (2 * math.pi / HEADINGS), trace))
    return out


def choose(glasses, skip: set[int]):
    """The push to make next, and why the rest have none. Mirror of plan.choose."""
    freeing: list[Push] = []
    easing: list[tuple[float, float, Push]] = []
    why: dict[int, str] = {}
    before = shortfall(layout_of(glasses))
    for glass in glasses:
        if glass.id in skip:
            continue
        if slides(glass) == "no":
            why[glass.id] = "tips before it slides"
            continue
        others = [o for o in glasses if o.id != glass.id]
        rest = layout_of(others)
        pushes = search(glass, others)
        for push in pushes:
            if has_room(push.aim, with_margin(rest, AIM_MARGIN)):
                freeing.append(push)
            else:
                eased = before - shortfall([*rest, (*push.aim, glass.widest)])
                if eased >= LEAST_EASING:
                    easing.append((eased, -push.travel, push))
        if not pushes:
            why[glass.id] = "nowhere clear to push it to"
    if freeing:
        return min(freeing, key=lambda p: p.travel), why
    if easing:
        return max(easing, key=lambda e: e[:2])[2], why
    for glass in glasses:
        if glass.id not in skip and glass.id not in why:
            why[glass.id] = "nowhere clear to push it to"
    return None, why


def fixed_nudge(glasses, moving: Glass, staying: Glass):
    """Solution 2's push: straight along the line joining the pair, away from it.

    The distance is the shortfall in the room the moving glass needs from its
    neighbour, plus solution 2's 20 mm of margin.
    """
    away = np.array(moving.spot, float) - np.array(staying.spot, float)
    gap = float(np.linalg.norm(away))
    unit = away / gap
    needed = GRIP_ROOM + staying.widest / 2.0
    travel = max(needed - gap, 0.0) + 20.0
    end = np.array(moving.spot, float) + unit * travel
    return (float(end[0]), float(end[1])), (float(unit[0]), float(unit[1])), travel


def run_loop(glasses, cap_per_glass: int = 3, cap_per_table: int = 15):
    """The whole loop, with the push assumed to land where it was aimed.

    That assumption is not a guess: over the 212 pushes of the scored run the
    glass stopped a median of 1.0 mm from its aim and 3.9 mm from it at worst,
    both far inside the 10 mm the planner aims past the line by. What this
    cannot model is the probe, which needs the physics, so every "try" glass is
    treated as sliding. Both simplifications are stated in the document.
    """
    standing = list(glasses)
    racked: list[int] = []
    pushes: list[Push] = []
    worn: Counter = Counter()
    while True:
        ready = [g for g in standing
                 if has_room(g.spot, with_margin([o for o in layout_of(standing)
                                                  if o != (g.x, g.y, g.widest)], 5.0))]
        if ready:
            racked.extend(g.id for g in ready)
            standing = [g for g in standing if g not in ready]
            if not standing:
                return "cleared", racked, pushes, {}
            continue
        skip = {g for g, n in worn.items() if n >= cap_per_glass}
        push, why = choose(standing, skip)
        if push is None or len(pushes) >= cap_per_table:
            return "refused", racked, pushes, why
        mover = next(g for g in standing if g.id == push.glass)
        standing = [Glass(g.id, *push.aim, g.height, g.widest, g.foot, g.outline)
                    if g.id == mover.id else g for g in standing]
        worn[push.glass] += 1
        pushes.append(push)


# --------------------------------------------------------------------------- #
# The study. Every number the document quotes is printed here.
# --------------------------------------------------------------------------- #

MEASURED: dict[str, object] = {}


def heading_line(text: str) -> None:
    print()
    print(text)
    print("-" * len(text))


def study_the_tables(count: int = 60) -> None:
    heading_line(f"1. The held-out tables, from seed {TEST_SEEDS}")
    seeds = list(range(TEST_SEEDS, TEST_SEEDS + count))
    glasses = 0
    without = 0
    gaps: list[float] = []
    feet: list[float] = []
    per_table: Counter = Counter()
    for seed in seeds:
        table = scene(seed)
        per_table[len(table)] += 1
        glasses += len(table)
        without += len(crowded(table))
        feet.extend(g.foot for g in table)
        for i in range(len(table)):
            for j in range(i + 1, len(table)):
                gaps.append(math.dist(table[i].spot, table[j].spot))
    print(f"   {count} tables, {glasses} glasses, {per_table[4]} of four, {per_table[5]} of "
          f"five and {per_table[6]} of six")
    print(f"   {without} of {glasses} glasses start without room = "
          f"{100 * without / glasses:.1f}%, by the asymmetric has_room test")
    print(f"   centre to centre, the {len(gaps)} pairs run {min(gaps):.0f} to {max(gaps):.0f} mm, "
          f"median {st.median(gaps):.0f}")
    print(f"   feet {min(feet):.1f} to {max(feet):.1f} mm, median {st.median(feet):.1f}")

    tapered = tapered_seeds(40)
    t_glasses = t_without = 0
    t_feet: list[float] = []
    t_gaps: list[float] = []
    for seed in tapered:
        table = scene(seed)
        t_glasses += len(table)
        t_without += len(crowded(table))
        t_feet.extend(g.foot for g in table)
        for i in range(len(table)):
            for j in range(i + 1, len(table)):
                t_gaps.append(math.dist(table[i].spot, table[j].spot))
    print(f"   the {len(tapered)} tapered tables: {t_without} of {t_glasses} without room = "
          f"{100 * t_without / t_glasses:.1f}%, feet {min(t_feet):.1f} to {max(t_feet):.1f} mm, "
          f"closest pair {min(t_gaps):.0f} mm")
    print(f"   the symmetric shorthand would use {GRIPPABLE_APART:.0f} mm; the asymmetric test "
          f"asks for {GRIP_ROOM:.0f} + half the neighbour's width, which here is "
          f"{GRIP_ROOM + min(g.widest for g in scene(TEST_SEEDS + 1)) / 2:.0f} to "
          f"{GRIP_ROOM + max(g.widest for g in scene(TEST_SEEDS + 1)) / 2:.0f} mm on one table")
    MEASURED.update(tables=count, glasses=glasses, without=without, gaps=gaps, feet=feet,
                    tapered_glasses=t_glasses, tapered_without=t_without, tapered_feet=t_feet)


def study_the_gate(count: int = 100) -> None:
    heading_line("2. The tipping gate, and the number nobody has")
    populations = {
        "all four kinds": [g.foot for seed in range(TEST_SEEDS, TEST_SEEDS + count)
                           for g in scene(seed)],
        "tapered only": [g.foot for seed in tapered_seeds(count) for g in scene(seed)],
    }
    rows = {}
    for label, feet in populations.items():
        print(f"   {len(feet)} real feet over {count} tables, {label}: "
              f"{min(feet):.1f} to {max(feet):.1f} mm, median {st.median(feet):.1f}")
        for height, name in ((LOWEST_GRIP, "the middle of the jaw, LOWEST_GRIP"),
                             (JAW_TOP, "the jaw's top edge, JAW_TOP, what touches first")):
            line = []
            for mu in (MU_LOWEST, MU_LOW, TABLE_FRICTION, 0.4, MU_HIGH):
                share = 100.0 * sum(1 for f in feet if topple_height(f, mu) > height) / len(feet)
                rows[(label, height, mu)] = share
                line.append(f"mu {mu}: {share:.1f}%")
            print(f"      pushed at {height:.0f} mm ({name}): " + ", ".join(line))
    feet = populations["all four kinds"]
    limits = KIND_RANGES["tapered_glass"]
    widest_foot = 1000 * limits["rim_diameter"][1] * limits["base_fraction"][1]
    narrowest_foot = 1000 * limits["rim_diameter"][0] * limits["base_fraction"][0]
    print(f"   the tapered kind's own range allows a foot from {narrowest_foot:.1f} to "
          f"{widest_foot:.1f} mm")
    print(f"      \"yes\" needs a foot over {2 * MU_HIGHEST * JAW_TOP:.0f} mm, which the kind "
          f"cannot reach, so no tapered glass is ever cleared without a probe")
    print(f"      \"no\" needs a foot under {2 * MU_LOWEST * JAW_TOP:.0f} mm, which only the "
          f"very narrowest of the kind reaches")
    print(f"   the simulator uses mu = {TABLE_FRICTION} and never tells the arm, so the arm "
          f"brackets it at {MU_LOWEST} to {MU_HIGHEST}")

    verdicts: Counter = Counter()
    tapered: Counter = Counter()
    for seed in range(TEST_SEEDS, TEST_SEEDS + count):
        for glass in scene(seed):
            verdicts[slides(glass)] += 1
    for seed in tapered_seeds(40):
        for glass in scene(seed):
            tapered[slides(glass)] += 1
    print(f"   plan.slides over those {count} tables: {dict(verdicts)}")
    print(f"   over the 40 tapered tables: {dict(tapered)}")
    MEASURED.update(gate=rows, gate_feet=feet, verdicts=verdicts,
                    tapered_verdicts=tapered, tapered_feet_all=populations["tapered only"],
                    kind_foot=(narrowest_foot, widest_foot))


def study_the_optimistic_gate(sample: int = 400) -> None:
    """What the overview's version of the gate costs when both its inputs are wrong.

    Not what plan.py does. plan.py brackets the friction and uses the jaw's top
    edge. This measures the gate as the overview states it — one guessed
    friction, and the height the jaw aims at — against the simulator's own
    friction and the height a flaring glass really meets.
    """
    heading_line(f"3. The optimistic gate, over {sample} drawn tapered glasses")
    feet: list[float] = []
    seed = TEST_SEEDS
    while len(feet) < sample:
        if seed % len(KINDS) == KINDS.index("tapered_glass"):
            feet.extend(g.foot for g in scene(seed))
        seed += 1
    feet = feet[:sample]
    allowed = [f for f in feet if topple_height(f, MU_LOW) > LOWEST_GRIP]
    over = [f for f in allowed if topple_height(f, TABLE_FRICTION) <= JAW_TOP]
    print(f"   checked at {LOWEST_GRIP:.0f} mm, the height the jaw aims at, with a guessed "
          f"mu of {MU_LOW}: {len(allowed)} of {sample} are declared safe")
    print(f"   of those, {len(over)} go over at the simulator's own mu of {TABLE_FRICTION} and "
          f"the {JAW_TOP:.0f} mm a flaring glass really meets = "
          f"{100.0 * len(over) / len(allowed):.0f}% of the ones it allowed, "
          f"{100.0 * len(over) / sample:.0f}% of the population")
    print("   the two errors push the same way: the optimistic friction raises the limit and "
          "the wrong height lowers what has to clear it")
    print(f"   the same {sample} feet judged as plan.py judges them, at {JAW_TOP:.0f} mm and "
          f"mu {MU_LOWEST} to {MU_HIGHEST}: "
          f"{sum(1 for f in feet if topple_height(f, MU_HIGHEST) > JAW_TOP)} safe outright, "
          f"{sum(1 for f in feet if topple_height(f, MU_LOWEST) <= JAW_TOP)} refused outright, "
          f"the rest left to the probe")
    MEASURED.update(optimistic=(len(allowed), len(over), sample), optimistic_feet=feet)


def study_the_nudge(count: int = 50) -> None:
    heading_line("4. Solution 2's fixed nudge, checked against the whole table")
    faults = Counter()
    total = 0
    angles: list[float] = []
    straight_away_possible = straight_away_tried = 0
    for seed in range(TEST_SEEDS, TEST_SEEDS + count):
        table = scene(seed)
        rest_of = {g.id: [o for o in table if o.id != g.id] for g in table}
        for glass in crowded(table):
            others = rest_of[glass.id]
            worst = min(others, key=lambda o: math.dist(glass.spot, o.spot))
            total += 1
            destination, unit, travel = fixed_nudge(table, glass, worst)
            rest = layout_of(others)
            if not in_zone(destination) or not in_reach(destination):
                faults["leaves the zone or the reach"] += 1
            elif not has_room(destination, rest):
                faults["lands inside another glass's room"] += 1
            else:
                faults["the landing spot itself is fine"] += 1
            straight_away_tried += 1
            straight_away_possible += bool(
                along(glass, others, math.atan2(unit[1], unit[0])))
            found = search(glass, others)
            freeing = [p for p in found if has_room(p.aim, with_margin(rest, AIM_MARGIN))]
            if freeing:
                best = min(freeing, key=lambda p: p.travel)
                chosen = np.array([math.cos(best.heading), math.sin(best.heading)])
                angles.append(math.degrees(math.acos(
                    float(np.clip(np.dot(np.asarray(unit, float), chosen), -1.0, 1.0)))))
    print(f"   {total} crowded glasses over {count} tables, each nudged straight away from its "
          f"nearest neighbour:")
    for name, value in faults.most_common():
        print(f"      {name:<40} {value:4d} = {100.0 * value / total:5.1f}%")
    print("   but the arm has to stand behind the glass to push it that way, and that is "
          "where the neighbour is:")
    print(f"      {straight_away_possible} of {straight_away_tried} crowded glasses have any "
          f"safe push straight away at all = "
          f"{100.0 * straight_away_possible / straight_away_tried:.1f}%")
    print(f"      the fingers are {JAW_THICKNESS:.0f} mm thick, the body behind them "
          f"{BODY_SIZE:.0f} mm, and there is {TOOL_LENGTH:.0f} mm of tool in all")
    print(f"   the direction the planner picks instead, as an angle from straight away: "
          f"{min(angles):.0f} to {max(angles):.0f} degrees, median {st.median(angles):.0f}")
    print(f"      {100.0 * sum(1 for a in angles if a >= 45) / len(angles):.0f}% of them are at "
          f"least a quarter turn round")
    MEASURED.update(nudge=faults, nudge_total=total, angles=angles,
                    straight_away=(straight_away_possible, straight_away_tried))


def study_the_search(count: int = 40) -> None:
    heading_line("5. What the search rejects, and what it leaves")
    tally = Counter()
    first_travel: list[float] = []
    kinds = Counter()
    no_push = 0
    tables = 0
    for seed in tapered_seeds(count):
        table = scene(seed)
        tables += 1
        for glass in crowded(table):
            others = [o for o in table if o.id != glass.id]
            trace: list = []
            search(glass, others, trace)
            for _spot, why in trace:
                tally[why] += 1
        push, _why = choose(table, set())
        if push is None:
            no_push += 1
            continue
        first_travel.append(push.travel)
        mover = next(g for g in table if g.id == push.glass)
        rest = layout_of([o for o in table if o.id != mover.id])
        kinds["frees a glass" if has_room(push.aim, with_margin(rest, AIM_MARGIN))
              else "only loosens the group"] += 1
    considered = sum(tally.values())
    print(f"   over {tables} tapered tables, the search tried {considered} candidate pushes and "
          f"ended each heading at its first clash:")
    for why in (SAFE_WITH_ROOM, SAFE_NO_ROOM, GLASS_CLASH, JAW_CLASH, BODY_CLASH, OUT_OF_ZONE,
                OUT_OF_REACH):
        print(f"      {WHY[why]:<48} {tally[why]:5d} = {100.0 * tally[why] / considered:5.1f}%")
    print(f"   tables where the first decision found no safe push at all: {no_push} of {tables}")
    print(f"   the first push chosen: {min(first_travel):.0f} to {max(first_travel):.0f} mm, "
          f"median {st.median(first_travel):.0f} mm")
    print(f"   what it is for: {dict(kinds)}")
    MEASURED.update(tally=tally, first_travel=first_travel, first_kinds=kinds, no_push=no_push)


def straight_away(mover: Glass, neighbour: Glass) -> float:
    """The heading that takes ``mover`` directly away from ``neighbour``."""
    return math.atan2(mover.y - neighbour.y, mover.x - neighbour.x)


def push_faults(mover: Glass, target: Glass, others, heading: float, travel: float,
                with_tool: bool = True) -> set[str]:
    """Everything independently wrong with one push, as a set of names.

    ``mover`` is the glass being pushed and ``target`` is the glass the push is
    meant to free, which may be the same one. ``others`` is every other glass
    on the table, ``mover`` excluded.
    """
    unit = np.array([math.cos(heading), math.sin(heading)])
    middle = np.array(mover.spot, float)
    radius = mover.widest / 2.0
    start = middle - (radius + APPROACH_GAP) * unit
    wrist = start - TOOL_LENGTH * unit
    end = middle + travel * unit
    landed = (float(end[0]), float(end[1]))
    faults: set[str] = set()

    after = [(o.x, o.y, o.widest) for o in others] + [(*landed, mover.widest)]
    if target.id == mover.id:
        if not has_room(landed, [(o.x, o.y, o.widest) for o in others]):
            faults.add("the glass still has no room")
    elif not has_room(target.spot, [q for q in after if q[:2] != target.spot]):
        faults.add("the glass still has no room")

    before = [(o.x, o.y, o.widest) for o in others] + [(mover.x, mover.y, mover.widest)]
    for other in others:
        mine = (other.x, other.y, other.widest)
        had = has_room(other.spot, [q for q in before if q != mine])
        keeps = has_room(other.spot, [q for q in after if q != mine])
        if had and not keeps:
            faults.add("it takes the room from a glass that had it")
            break

    for other in others:
        centre, other_radius = np.array(other.spot, float), other.widest / 2.0
        passing = min(radius + other_radius + CLEARANCE,
                      float(np.linalg.norm(centre - middle)) - 1.0)
        if segment_distance(centre, middle, end) < passing:
            faults.add("the glass sweeps through another glass")
        if with_tool and (segment_distance(centre, start - FINGER_LENGTH * unit, end)
                          < JAW_THICKNESS / 2.0 + other_radius + CLEARANCE
                          or segment_distance(centre, wrist, end - FINGER_LENGTH * unit)
                          < BODY_SIZE / 2.0 + other_radius + CLEARANCE):
            faults.add("the tool meets another glass")

    if not in_zone(landed):
        faults.add("it leaves the glass zone")
    if not all(in_reach(point - TIP_TO_FLANGE * unit) for point in (start, middle, end)):
        faults.add("it leaves the comfortable reach")
    if (RACK_AREA[0] <= landed[0] <= RACK_AREA[1]
            and RACK_AREA[2] <= landed[1] <= RACK_AREA[3]):
        faults.add("it puts the glass in the rack")
    return faults


def study_the_ladder(count: int = 120) -> None:
    """What each freedom the planner has is worth, against a fixed nudge.

    Run twice: once with the arm treated as a point, which is how a push is
    usually scored, and once with the arm's own 270 mm of tool in the test.
    """
    heading_line(f"7. The fixed nudge, and what each freedom is worth, over {count} tapered "
                 f"tables")
    cases = []
    for seed in tapered_seeds(count):
        table = scene(seed)
        for glass in crowded(table):
            others = [o for o in table if o.id != glass.id]
            neighbour = min(others, key=lambda o: math.dist(glass.spot, o.spot))
            cases.append((table, glass, others, neighbour))
    print(f"   {len(cases)} glasses without room")
    steps = list(np.arange(STEP, LONGEST_PUSH + 1e-9, STEP))

    for with_tool in (False, True):
        label = ("with the arm's own body in the test" if with_tool
                 else "with the arm treated as a point, which is how a push is usually scored")
        print(f"   {label}:")
        sweep = {}
        for distance in np.arange(4.0, 150.1, 4.0):
            wrong = sum(1 for _t, g, o, n in cases
                        if push_faults(g, g, o, straight_away(g, n), distance, with_tool))
            sweep[float(distance)] = 100.0 * wrong / len(cases)
        best = min(sweep, key=lambda d: sweep[d])
        print(f"      the best fixed nudge is {best:.0f} mm, and it is still wrong "
              f"{sweep[best]:.1f}% of the time")
        for distance in sorted({4.0, best, 120.0}):
            tally: Counter = Counter()
            for _t, g, o, n in cases:
                for fault in push_faults(g, g, o, straight_away(g, n), distance, with_tool):
                    tally[fault] += 1
            print(f"         at {distance:5.0f} mm, wrong {sweep[distance]:5.1f}%: " + ", ".join(
                f"{name} {100.0 * n / len(cases):.1f}%" for name, n in tally.most_common()))
        formula = sum(1 for _t, g, o, n in cases
                      if push_faults(g, g, o, straight_away(g, n),
                                     max(GRIPPABLE_APART - math.dist(g.spot, n.spot) + 20.0,
                                         STEP), with_tool))
        print(f"      the overview's own formula, 140 - d + 20, is wrong "
              f"{100.0 * formula / len(cases):.1f}% of the time")

        def works(mover, target, others, heading, travel, tool=with_tool) -> bool:
            return not push_faults(mover, target, others, heading, travel, tool)

        fixed = either = distance_free = both = anything = 0
        for table, glass, others, neighbour in cases:
            swapped = [o for o in table if o.id != neighbour.id]
            mine = straight_away(glass, neighbour)
            theirs = straight_away(neighbour, glass)
            a = works(glass, glass, others, mine, best)
            b = a or works(neighbour, glass, swapped, theirs, best)
            c = a or any(works(glass, glass, others, mine, d) for d in steps)
            d_ = c or b or any(works(neighbour, glass, swapped, theirs, d) for d in steps)
            fixed += a
            either += b
            distance_free += c
            both += d_
            if d_:
                anything += 1
                continue
            found = False
            for mover, target, rest in ((glass, glass, others), (neighbour, glass, swapped)):
                for index in range(HEADINGS):
                    angle = index * (2 * math.pi / HEADINGS)
                    if any(works(mover, target, rest, angle, travel) for travel in steps):
                        found = True
                        break
                if found:
                    break
            anything += found
        ladder = {}
        for name, wins in ((f"a fixed nudge of {best:.0f} mm, straight away", fixed),
                           ("free to push either glass of the pair", either),
                           ("free to choose any distance", distance_free),
                           ("both of those", both),
                           ("free to choose any direction as well", anything)):
            ladder[name] = 100.0 * wins / len(cases)
            print(f"         {name:<44} {ladder[name]:5.1f}%")
        MEASURED[f"ladder_tool_{with_tool}"] = dict(sweep=sweep, best=best, ladder=ladder)
    MEASURED["ladder_cases"] = len(cases)


def study_the_loop(count: int = 40) -> None:
    heading_line("6. The loop, with the push landing where it was aimed")
    outcomes = Counter()
    pushes: list[int] = []
    broke = 0
    total_pushes = 0
    for seed in tapered_seeds(count):
        table = scene(seed)
        outcome, racked, made, _why = run_loop(table)
        outcomes[outcome] += 1
        if outcome == "cleared":
            pushes.append(len(made))
        # Did any push leave a glass that had room without it?
        standing = list(table)
        for push in made:
            had = {g.id for g in standing if g not in crowded(standing)}
            standing = [Glass(g.id, *push.aim, g.height, g.widest, g.foot, g.outline)
                        if g.id == push.glass else g for g in standing]
            now = {g.id for g in standing if g not in crowded(standing)}
            broke += len(had - now - {push.glass}) > 0
            total_pushes += 1
    print(f"   {count} tapered tables: {dict(outcomes)}")
    if pushes:
        spread = {k: pushes.count(k) for k in sorted(set(pushes))}
        print(f"   pushes to clear a table: mean {st.mean(pushes):.2f}, median "
              f"{st.median(pushes):.0f}, most {max(pushes)}; {spread}")
    print(f"   pushes that took the room away from a glass that had it: {broke} of "
          f"{total_pushes} = {100.0 * broke / total_pushes:.1f}%")
    print("   the scored run of the real thing, from 03-push-glasses-apart/01-one-fixed-nudge/results.json:")
    print(f"      {SCORED['scenes']} tables, {SCORED['glasses']} glasses, "
          f"{SCORED['crowded_at_start']} without room at the start")
    print(f"      {SCORED['done']} done, {SCORED['incomplete']} incomplete, "
          f"{SCORED['wrong']} wrong")
    print(f"      {SCORED['racked']} racked, {SCORED['refused']} refused, "
          f"{SCORED['toppled']} toppled, {SCORED['out_of_zone']} pushed out of the zone")
    print(f"      {SCORED['pushes']} pushes, of which {SCORED['repeats']} were repeats")
    print(f"      the glass stopped {SCORED['aim_median']} mm from its aim (median), "
          f"{SCORED['aim_worst']} mm at worst")
    MEASURED.update(loop=outcomes, loop_pushes=pushes, broke=broke, total_pushes=total_pushes)


def study_the_feel() -> None:
    heading_line("8. Why the last millimetres are felt")
    table = scene(STORY["seed"])
    wall_error = math.hypot(POSITION_NOISE, WIDTH_NOISE / 2.0)
    print(f"   the examiner measures a position to {POSITION_NOISE} mm and a width to "
          f"{WIDTH_NOISE} mm, one standard deviation each")
    print(f"   the wall is the middle minus half the width, so its error is "
          f"hypot({POSITION_NOISE}, {WIDTH_NOISE / 2}) = {wall_error:.2f} mm, and three of "
          f"those is {3 * wall_error:.2f} mm")
    print(f"   the fingers come down {APPROACH_GAP:.0f} mm outside the widest part and feel up "
          f"to {FEEL_BEYOND:.0f} mm further, at {FEEL_SPEED:.0f} mm/s, stopping over "
          f"{TOUCH_FORCE} N")
    for push in STORY["pushes"]:
        glass = table[push["glass"]]
        expected = glass.widest / 2.0 + APPROACH_GAP - glass.outline.diameter_at(
            JAW_TOP / 1000.0) * 1000.0 / 2.0
        print(f"      glass {NAMES[push['glass']]}: the jaw felt it after "
              f"{push['touched']:.1f} mm of creeping; the widest part is "
              f"{glass.widest / 2.0:.1f} mm out and the wall at the jaw's top edge is "
              f"{glass.outline.diameter_at(JAW_TOP / 1000.0) * 1000.0 / 2.0:.1f} mm out, so a "
              f"straight drive to the widest part would have stopped {expected:.1f} mm short")
    MEASURED["wall_error"] = wall_error


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #

def zone_frame(axis, pad: float = 70.0) -> None:
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from, facecolor="none",
                             edgecolor=INK, lw=1.1, ls=(0, (5, 3)), zorder=1))
    axis.set_xlim(x_from - pad, x_to + pad)
    axis.set_ylim(y_from - pad, y_to + pad)
    axis.set_aspect("equal")
    bare(axis)


def draw_table(axis, glasses, rings=True, labels=True, colour=GLASS) -> None:
    for glass in glasses:
        if rings:
            grip_ring(axis, glass.spot)
        glass_from_above(axis, glass.spot, glass.widest,
                         base_fraction=glass.foot / glass.widest, colour=colour)
        if labels:
            axis.text(glass.x, glass.y, NAMES[glass.id], ha="center", va="center",
                      fontsize=LABEL_SIZE, color=INK, zorder=9)


def note(axis, x, y, text, colour=INK, ha="left", va="bottom", size=NOTE_SIZE) -> None:
    axis.text(x, y, text, fontsize=size, color=colour, ha=ha, va=va, zorder=12, linespacing=1.45)


def legend_below(axis, entries, columns=2) -> None:
    handles = [Line2D([], [], color=colour, lw=7, alpha=0.55, label=label)
               for label, colour in entries]
    axis.legend(handles=handles, fontsize=NOTE_SIZE - 0.3, frameon=False, ncol=columns,
                loc="upper center", bbox_to_anchor=(0.5, -0.01), labelcolor=INK,
                handlelength=1.5, columnspacing=1.2, handletextpad=0.5)


def caption(axis, text, colour=INK, x=None, y=None) -> None:
    """A block of words under the picture, never over it.

    Every table picture puts its numbers here rather than beside the glass they
    belong to. Beside the glass they land on a neighbour's grip ring, which is
    the fault these pictures kept having.
    """
    x_from, _x_to, y_from, _y_to = GLASS_ZONE
    axis.text(x if x is not None else x_from - 40,
              y if y is not None else y_from - 22,
              text, fontsize=NOTE_SIZE, color=colour, ha="left", va="top", zorder=12,
              linespacing=1.5)


def paint_trace(axis, trace, size=5.0) -> None:
    """One dot per candidate push, coloured by the comparison that judged it."""
    for why in (OUT_OF_ZONE, OUT_OF_REACH, SAFE_NO_ROOM, GLASS_CLASH, JAW_CLASH, BODY_CLASH,
                SAFE_WITH_ROOM):
        points = [spot for spot, code in trace if code == why]
        if not points:
            continue
        winner = why == SAFE_WITH_ROOM
        axis.scatter([p[0] for p in points], [p[1] for p in points],
                     s=3.2 * size if winner else size, color=COLOURS[why],
                     alpha=1.0 if winner else 0.55, linewidths=0,
                     zorder=6 if winner else 3)


def tool_outline(axis, spot, heading, travel, widest, colour, alpha=0.16):
    """The ground the tool covers: the fingers, and the body and wrist behind them."""
    unit = np.array([math.cos(heading), math.sin(heading)])
    across = np.array([-unit[1], unit[0]])
    middle = np.array(spot, float)
    tip = middle - (widest / 2.0 + APPROACH_GAP) * unit
    end = middle + travel * unit
    for back, front, half in ((tip - FINGER_LENGTH * unit, end, JAW_THICKNESS / 2.0),
                              (tip - TOOL_LENGTH * unit, end - FINGER_LENGTH * unit,
                               BODY_SIZE / 2.0)):
        corners = [back + across * half, front + across * half,
                   front - across * half, back - across * half]
        axis.fill([c[0] for c in corners], [c[1] for c in corners], facecolor=colour,
                  alpha=alpha, edgecolor=colour, lw=1.0, zorder=2)
    return tip - TOOL_LENGTH * unit




def picture_feel_do_not_drive() -> None:
    """Driving to the measured wall, against creeping in until the force reads."""
    table = scene(STORY["seed"])
    record = STORY["pushes"][0]
    glass = table[record["glass"]]
    wall = glass.outline.diameter_at(JAW_TOP / 1000.0) * 1000.0 / 2.0
    widest = glass.widest / 2.0
    error = 3.0 * MEASURED["wall_error"]
    start = widest + APPROACH_GAP

    figure, (left, right) = new(13.4, 6.0, columns=2)
    for axis, title in ((left, "drive to the wall the camera reported"),
                        (right, "creep in until the force reads")):
        bare(axis)
        axis.set_aspect("equal")
        axis.axhline(0.0, color=INK, lw=1.4, zorder=1)
        glass_from_the_side(axis, 0.0, glass.height, glass.widest,
                            base_fraction=glass.foot / glass.widest)
        axis.plot([-start - 116, widest + 14], [JAW_TOP, JAW_TOP], color=MUTED, lw=0.9,
                  ls=(0, (4, 3)), zorder=2)
        axis.text(-start - 114, JAW_TOP + 5, f"the jaw's top edge, {JAW_TOP:.0f} mm",
                  fontsize=NOTE_SIZE, color=MUTED, ha="left", va="bottom")
        axis.plot([-widest - error, -widest + error], [JAW_TOP, JAW_TOP], color=WARN, lw=3.0,
                  solid_capstyle="butt", zorder=6)
        axis.plot([-widest, -widest], [0, JAW_TOP - 4], color=WARN, lw=0.8, ls=(0, (2, 2)),
                  zorder=2)
        axis.plot([-wall, -wall], [0, JAW_TOP - 4], color=GOOD, lw=0.8, ls=(0, (2, 2)),
                  zorder=2)
        axis.text(-widest - 2, -8, "the widest part", fontsize=NOTE_SIZE, color=WARN,
                  ha="right", va="top")
        axis.text(-wall + 4, -26, f"the wall at {JAW_TOP:.0f} mm", fontsize=NOTE_SIZE,
                  color=GOOD, ha="left", va="top")
        axis.set_xlim(-start - 120, widest + 20)
        axis.set_ylim(-196, glass.height + 26)
        axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)

    push_arrow(left, (-start, JAW_TOP), (-widest - error - 2.0, JAW_TOP), colour=INK, lw=1.7)
    left.text(-start - 118, -54,
              f"the camera says the widest part is {widest:.0f} mm out, give or take "
              f"{error:.1f} mm:\na position good to {POSITION_NOISE} mm and a width good to "
              f"{WIDTH_NOISE} mm, and the wall is\nthe middle minus half the width. Worse, the "
              f"wall the jaw meets at\n{JAW_TOP:.0f} mm is {wall:.0f} mm out, not {widest:.0f}, "
              f"because the glass is narrower low\ndown. A drive to the camera's number stops "
              f"{widest - wall:.0f} mm short and pushes air.",
              fontsize=NOTE_SIZE, color=WARN, ha="left", va="top", linespacing=1.5)

    for step, spot in enumerate(np.arange(-start, -wall + 0.5, 4.0)):
        right.plot([spot], [JAW_TOP], marker=">", ms=7, color=INK, zorder=6,
                   alpha=0.25 + 0.6 * step / 5.0)
    right.plot([-wall], [JAW_TOP], marker=">", ms=10, color=GOOD, zorder=8)
    right.text(-start - 118, -54,
               f"the fingers come down {APPROACH_GAP:.0f} mm outside the widest part and feel "
               f"forward at\n{FEEL_SPEED:.0f} mm/s, as far as {FEEL_BEYOND:.0f} mm past where "
               f"the glass should be, stopping the\nmoment the wrist reads {TOUCH_FORCE} N. On "
               f"table {STORY['seed']} it touched after {record['touched']:.1f} mm.\nWhere it "
               f"touched is a measurement of the wall, and a better one\nthan the camera's.",
               fontsize=NOTE_SIZE, color=GOOD, ha="left", va="top", linespacing=1.5)
    figure.suptitle("The last millimetres are felt, because the camera's numbers are both "
                    "uncertain and about the wrong part of the glass",
                    fontsize=TITLE_SIZE, color=INK, y=0.97)
    figure.subplots_adjust(left=0.02, right=0.98, top=0.87, bottom=0.03, wspace=0.08)
    save(figure, "toppling-feel-do-not-drive.png")
    print(f"   feel, do not drive: glass {NAMES[glass.id]} of table {STORY['seed']}, "
          f"{glass.height:.0f} mm tall, widest {glass.widest:.0f} mm, foot {glass.foot:.0f} mm; "
          f"the wall at {JAW_TOP:.0f} mm is {wall:.1f} mm out and the widest part "
          f"{widest:.1f} mm, so a drive to the widest part stops {widest - wall:.1f} mm short")
    MEASURED["feel_story"] = dict(wall=wall, widest=widest, error=error,
                                  touched=record["touched"], short=widest - wall)
# --------------------------------------------------------------------------- #

def main() -> None:
    print("Measurements for the shared pushing-without-toppling document")
    print("Tables and planner mirrored from 03-push-glasses-apart/bench/bench.py and "
          "03-push-glasses-apart/01-one-fixed-nudge/plan.py")
    study_the_tables()
    study_the_gate()
    study_the_optimistic_gate()
    study_the_nudge()
    study_the_search()
    study_the_loop()
    study_the_ladder()
    study_the_feel()
    heading_line("9. The pictures")
    picture_feel_do_not_drive()


if __name__ == "__main__":
    main()
