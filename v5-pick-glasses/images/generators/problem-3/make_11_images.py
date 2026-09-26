"""Diagrams for solution 11 — search a push strategy.

Four pictures, and the numbers under all four are printed as the script runs, so
that the document can be checked against them rather than trusted.

    pixi run python images/generators/problem-3/make_11_images.py

Three of the four are arithmetic on measurements. The friction picture is
computed over four hundred glasses the project's own spawner drew. The
arrangements are the real tables problem 3 runs on, taken from ``scene(seed)``
in ``problem-3-sim/bench.py``, which is the reference implementation for this
problem: four to six glasses of one kind, every table holding at least one
glass without room. The sample budget is arithmetic on timings measured in that
same bench. The one picture that is an illustration rather than a result is the
reward-shaping trap, because it shows what a policy trained on a shaped reward
would be paid for doing, and no such policy has been trained here. It says so on
the picture itself.

No glass's size is written down anywhere in this file. Every outline comes from
``work_cell.glasses.shapes.draw`` by way of the bench's own scene generator, and
every width quoted is read back off the outline that was drawn.

Whether a push slides or topples a glass is asked at ``JAW_TOP`` and not at
``LOWEST_GRIP``. The middle of the jaw rides at 50 mm, but the jaw is 30 mm tall
and a tapered glass is wider higher up, so it meets the jaw's top edge at 65 mm
first, and 65 mm is the height it is really pushed at. ``bench.py`` says so in a
comment beside ``JAW_TOP`` and its ``slides()`` uses that height.

Whether a glass has room is asked with ``has_room``, the project's own test, and
that test is asymmetric: the room a glass needs depends on how wide its
*neighbour* is. A narrow glass beside a wide one can be without room while the
wide one beside it has plenty.

Running this from the root environment
--------------------------------------
Every generator in this repository runs from the project root under the root
pixi environment, and this one does too:

    pixi run python images/generators/problem-3/make_11_images.py

``problem-3-sim/bench.py`` imports MuJoCo for its physics, and the root
environment has no MuJoCo. Its scene generator needs no physics at all — it
draws outlines and places them — so a stand-in module is registered before the
import and the real ``scene(seed)`` is reached without it. That is worth one
line of awkwardness, because the alternative is either to write the layout rule
out a second time and let the two drift apart, or to paste this project's glass
sizes into a file, which is the one thing this repository does not do.

Where the timings came from
---------------------------
``problem-3-sim/bench.py`` is the physics this project already pushes glasses
in, and it is MuJoCo rather than Gazebo. The timings below were measured by
driving that bench from the ``problem-3-programmed`` environment, which is the
one with MuJoCo installed: build ``bench.Bench(seed)`` for the twenty tapered
tables among the first two hundred held-out seeds, push on them, and divide wall
clock by pushes. They are constants here because the environment this script
runs in has no MuJoCo, and the bench's scene generator is imported without it.
Everything derived from them is computed.
"""

from __future__ import annotations

import math
import sys
import types
from pathlib import Path

import matplotlib.pyplot as plt
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
    PAPER,
    TABLE_FRICTION,
    TITLE_SIZE,
    WARN,
    bare,
    crowded_pairs,
    destination_ok,
    glass_from_above,
    glass_from_the_side,
    grippable,
    has_room,
    new,
    push_arrow,
    pushable,
    save,
    topple_height,
)
from matplotlib.patches import Circle, Rectangle

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "work_cell"))
sys.path.insert(0, str(ROOT / "problem-3-sim"))

# bench.py imports MuJoCo for its physics, and this environment has none. The
# scene generator needs no physics at all — it draws outlines and places them —
# so a stand-in module is enough to reach it, and using the real one is better
# than writing the layout rule out a second time and having it drift.
sys.modules.setdefault("mujoco", types.ModuleType("mujoco"))

import bench  # noqa: E402
from work_cell.glasses.shapes import draw  # noqa: E402

KIND = "tapered_glass"
TAPERED_SEED = bench.KINDS.index(KIND)   # scene(seed) picks its kind by seed % 4

# ---------------------------------------------------------------------------
# What a push and an episode cost, measured in problem-3-sim/bench.py on this
# machine: an Apple M4 with four performance cores and six efficiency cores.
# ---------------------------------------------------------------------------
# All four come from the same twenty tapered held-out tables.
WALL_PER_PUSH = 0.1398             # s of wall clock for one push, over 300 pushes
SIM_PER_PUSH = 7.8                 # s of arm motion that one push represents
WALL_PER_PLANNED_EPISODE = 0.401   # s, the programmed planner clearing one table
SIM_PER_PLANNED_EPISODE = 26.9     # s of arm motion in that episode
PUSHES_PER_PLANNED_EPISODE = 3.55  # 71 pushes over the same twenty tables
WORKERS = 4                        # performance cores, so four simulators at once

# What the held-out run of the programmed approach scored, read from
# problem-3-programmed/results.json: 50 tables, 251 glasses, 212 pushes.
SCORED_PUSHES = 212
SCORED_SCENES = 50
AIM_ERROR_MEDIAN = 1.0             # mm between where a push aimed and where the glass landed

# The search, as the solution describes it.
FREE_PARAMETERS = 8
TUNING_TABLES = 12                 # the same frozen arrangements for every candidate
RANDOM_CANDIDATES = 100
CMA_GENERATIONS = 40

# What reinforcement learning of this kind is quoted as needing. This is the one
# figure on the pictures that is not measured here, and the document says so: it
# is the episode count learned-with-hardware.md settled on, which is itself the
# low end of what contact-rich policies are trained on.
RL_EPISODES = 50_000
REWARD_ATTEMPTS = 5                # how many tries a reward function takes
FRICTION_LEVELS = 3                # training across a range of mu rather than at one value

DRAWN = 400                        # how many glasses the friction picture is computed over
DRAW_SEED = 11

SEEDS_SCANNED = 200                # how many consecutive seeds an arrangement is chosen from
TRAP_PUSHES = 4
TRAP_STEP = 30.0                   # mm per push, well inside what one guarded move covers
LABEL_GAP = 12.0                   # mm of drawing between two labels that must both be read


# ---------------------------------------------------------------------------
# The real tables, from the bench's own scene generator
# ---------------------------------------------------------------------------
def tapered_seeds(start: int, how_many: int) -> list[int]:
    """The seeds inside a run of ``how_many`` that give a table of tapered glasses."""
    return [s for s in range(start, start + how_many) if bench.KINDS[s % 4] == KIND]


def table_at(seed: int):
    """One real table as (x, y, widest, foot, height, outline), all in millimetres."""
    out = []
    for glass in bench.scene(seed):
        outline = glass.outline
        out.append((
            1000.0 * glass.position[0],
            1000.0 * glass.position[1],
            1000.0 * outline.max_diameter,
            2000.0 * float(outline.radius[0]),
            1000.0 * outline.total_height,
            outline,
        ))
    return out


def spots(table):
    return [(g[0], g[1]) for g in table]


def neighbours(table, skip: int, moved=None):
    """Every other glass as (x, y, widest), with one optionally moved somewhere else."""
    out = []
    for index, glass in enumerate(table):
        if index == skip:
            continue
        here = moved[index] if moved is not None else (glass[0], glass[1])
        out.append((here[0], here[1], glass[2]))
    return out


def lacks_room(table, at=None):
    """Which glass lacks room because of which neighbour, as (short, blamed) pairs.

    Asymmetric on purpose, because ``has_room`` is: a narrow glass beside a wide
    one is crowded while the wide one beside it is not.
    """
    here = at if at is not None else spots(table)
    out = []
    for i in range(len(table)):
        for j in range(len(table)):
            if i != j and not has_room(here[i], [(here[j][0], here[j][1], table[j][2])]):
                out.append((i, j))
    return out


def short_glasses(table, at=None) -> set[int]:
    """Every glass on the table that has no room, whoever is to blame."""
    return {i for i, _ in lacks_room(table, at)}


def landing_ok(table, mover: int, spot, at=None) -> bool:
    """Whether a glass could be pushed to ``spot`` and leave the table no worse.

    Three things have to hold. The spot is inside the zone with the whole glass
    in it and inside the arm's reach, which ``destination_ok`` answers with no
    neighbours passed to it. The moved glass has room where it lands. And no
    neighbour is left without room by the arrival, which is the second half of
    the asymmetric test and the half that is easy to forget.
    """
    here = at if at is not None else spots(table)
    others = neighbours(table, mover, here)
    if not destination_ok(spot, [], table[mover][2] / 2.0):
        return False
    if not has_room(spot, others):
        return False
    return all(has_room((ox, oy), [(spot[0], spot[1], table[mover][2])]) for ox, oy, _ in others)


def separation(at) -> float:
    """The naive shaped score: the total distance between every pair, in millimetres."""
    return sum(math.dist(at[i], at[j]) for i in range(len(at)) for j in range(i + 1, len(at)))


def shortfall(table, at) -> float:
    """How many millimetres of separation the table still owes, over its short glasses.

    This is the task written as a number. It counts only glasses that lack room,
    so moving a glass that already had plenty changes it by nothing, which is
    exactly the property the naive shaped score lacks.
    """
    total = 0.0
    for i, j in lacks_room(table, at):
        total += GRIP_ROOM + table[j][2] / 2.0 - math.dist(at[i], at[j])
    return total


def separating_push(table, mover_first: int | None = None):
    """The shortest legal push that gives one glass without room the room it needs.

    Searched rather than chosen: every heading on a five degree circle, every
    travel in 5 mm steps, keeping the first that passes ``landing_ok``. Both the
    glass that is short and the neighbour taking its room are tried as the one
    to move, because the asymmetric test means they are not interchangeable.
    """
    here = spots(table)
    short = lacks_room(table)
    if not short:
        raise RuntimeError("this table has nothing to separate")
    tightest = min(short, key=lambda p: math.dist(here[p[0]], here[p[1]]))
    order = [tightest[0], tightest[1]] if mover_first is None else [mover_first]
    for mover in order:
        for travel in np.arange(10.0, 161.0, 5.0):
            for degrees in range(0, 360, 5):
                angle = math.radians(degrees)
                spot = (here[mover][0] + travel * math.cos(angle),
                        here[mover][1] + travel * math.sin(angle))
                moved = [spot if k == mover else p for k, p in enumerate(here)]
                if landing_ok(table, mover, spot) and len(short_glasses(table, moved)) < len(
                        short_glasses(table)):
                    other = tightest[1] if mover == tightest[0] else tightest[0]
                    return mover, other, spot, float(travel), angle
    raise RuntimeError("no legal push helps the tightest pair on this table")


# ---------------------------------------------------------------------------
# Panel furniture
# ---------------------------------------------------------------------------
def _zone(axis, label: bool = True) -> None:
    """The glass zone, with the table's y axis flipped so the zone sits the right way up."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, -y_to), x_to - x_from, y_to - y_from,
                             fc=MUTED, alpha=0.07, ec=MUTED, lw=1.0))
    if label:
        axis.text(x_to, -y_to - 9,
                  f"the glass zone, {x_to - x_from:.0f} by {y_to - y_from:.0f} mm",
                  fontsize=NOTE_SIZE - 0.4, color=MUTED, va="top", ha="right")
    axis.set_xlim(x_from - 40, x_to + 40)
    axis.set_ylim(-y_to - 52, -y_from + 40)
    axis.set_aspect("equal")
    bare(axis)


def _draw_table(axis, table, names, faded=(), rings=(), at=None) -> None:
    """Every glass from above, at the size it was drawn, with its foot dashed."""
    here = at if at is not None else spots(table)
    for index, glass in enumerate(table):
        x, y = here[index]
        widest, foot = glass[2], glass[3]
        pale = index in faded
        glass_from_above(axis, (x, -y), widest, base_fraction=foot / widest,
                         colour=MUTED if pale else GLASS, alpha=0.14 if pale else 0.30)
        if index in rings:
            axis.add_patch(Circle((x, -y), GRIP_ROOM + widest / 2.0, fc="none", ec=MUTED,
                                  lw=1.0, ls=(0, (4, 3)), alpha=0.9))
        axis.text(x, -y, names[index], ha="center", va="center", fontsize=LABEL_SIZE,
                  color=MUTED if pale else INK, zorder=9)


def _mark_short(axis, table, names, at=None):
    """Join each glass that lacks room to the neighbour taking it, and say by how much."""
    here = at if at is not None else spots(table)
    pairs = lacks_room(table, here)
    drawn = set()
    for i, j in pairs:
        if (j, i) in drawn:
            continue
        drawn.add((i, j))
        ax, ay = here[i][0], -here[i][1]
        bx, by = here[j][0], -here[j][1]
        axis.plot([ax, bx], [ay, by], color=WARN, lw=1.6, zorder=7)
        span = math.hypot(bx - ax, by - ay) or 1.0
        across = (-(by - ay) / span, (bx - ax) / span)
        both = (j, i) in pairs
        axis.text((ax + bx) / 2 + across[0] * 14.0, (ay + by) / 2 + across[1] * 14.0,
                  f"{math.dist(here[i], here[j]):.0f} mm"
                  + ("" if both else f"\n{names[i]} is short, {names[j]} is not"),
                  ha="center", va="center", fontsize=NOTE_SIZE - 0.8, color=WARN, zorder=10,
                  bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.8, pad=1.0))
    return pairs


def _population(parameters: int) -> int:
    """CMA-ES's default batch size: 4 + floor(3 ln n)."""
    return 4 + int(3 * math.log(parameters))


def _spell(hours: float) -> str:
    if hours < 1.0:
        return f"{hours * 60:.0f} minutes"
    if hours < 48.0:
        return f"{hours:.1f} hours"
    return f"{hours / 24:.1f} days"


# ---------------------------------------------------------------------------
# 1. what the search costs, against what reinforcement learning costs
# ---------------------------------------------------------------------------
def the_sample_budget(push_cap: int) -> None:
    """One episode's measured cost, multiplied out by each method's appetite."""
    per_episode = push_cap * WALL_PER_PUSH
    population = _population(FREE_PARAMETERS)
    rows = [
        (f"random search first\n{RANDOM_CANDIDATES} settings x {TUNING_TABLES} tables",
         RANDOM_CANDIDATES * TUNING_TABLES, GOOD),
        (f"CMA-ES, {FREE_PARAMETERS} parameters\n{CMA_GENERATIONS} generations x "
         f"{population} x {TUNING_TABLES} tables",
         CMA_GENERATIONS * population * TUNING_TABLES, GOOD),
        ("reinforcement learning\none reward function", RL_EPISODES, WARN),
        (f"reinforcement learning\n{REWARD_ATTEMPTS} tries at the reward",
         RL_EPISODES * REWARD_ATTEMPTS, WARN),
        (f"reinforcement learning\n{REWARD_ATTEMPTS} tries, {FRICTION_LEVELS} frictions",
         RL_EPISODES * REWARD_ATTEMPTS * FRICTION_LEVELS, WARN),
    ]

    figure, (cost, total) = plt.subplots(
        1, 2, figsize=(14.8, 6.8), gridspec_kw={"width_ratios": [0.80, 1.0], "wspace": 0.26})
    figure.patch.set_facecolor(PAPER)
    for axis in (cost, total):
        axis.set_facecolor(PAPER)

    bare(cost)
    cost.set_xlim(0, 10)
    cost.set_ylim(0, 10)
    cost.set_title("What one episode costs here", fontsize=TITLE_SIZE, color=INK, pad=12)
    lines = [
        ("one push: jaw down, feel forward, push, back off, lift",
         f"{SIM_PER_PUSH:.1f} s of arm motion", f"{WALL_PER_PUSH:.3f} s of wall clock"),
        (f"one episode the planner finishes, {PUSHES_PER_PLANNED_EPISODE:.2f} pushes",
         f"{SIM_PER_PLANNED_EPISODE:.1f} s of arm motion",
         f"{WALL_PER_PLANNED_EPISODE:.3f} s of wall clock"),
        (f"one episode that spends its whole budget, {push_cap} pushes",
         f"{push_cap * SIM_PER_PUSH:.0f} s of arm motion", f"{per_episode:.2f} s of wall clock"),
    ]
    for row, (what, sim, wall) in enumerate(lines):
        y = 8.8 - row * 2.3
        if row % 2 == 0:
            cost.add_patch(Rectangle((0.1, y - 0.96), 9.8, 1.94, fc=MUTED, alpha=0.06, ec="none"))
        cost.text(0.4, y + 0.50, what, fontsize=NOTE_SIZE + 0.4, color=INK)
        cost.text(0.85, y - 0.08, sim, fontsize=NOTE_SIZE, color=MUTED)
        cost.text(0.85, y - 0.62, wall, fontsize=NOTE_SIZE + 0.7, color=GOOD)
    cost.text(0.4, 1.55,
              f"The bench runs about {SIM_PER_PUSH / WALL_PER_PUSH:.0f} times faster than the arm\n"
              "would move. That ratio is what the whole budget turns on, and it\n"
              "is why these figures are not the ones a Gazebo run at the speed\n"
              "of real time would give.\n\n"
              "The planner finishes a table well inside the cap. A policy that\n"
              "has learned nothing yet spends the cap every time, so the third\n"
              "line is the one an episode count should be multiplied by.",
              fontsize=NOTE_SIZE + 0.4, color=INK, va="top")

    hours = [count * per_episode / 3600.0 for _, count, _ in rows]
    y = np.arange(len(rows))[::-1]
    total.barh(y, hours, height=0.5, color=[c for _, _, c in rows], alpha=0.75)
    total.set_yticks(y)
    total.set_yticklabels([name for name, _, _ in rows], fontsize=NOTE_SIZE + 0.2, color=INK)
    total.set_xscale("log")
    total.set_xlim(0.25, 40_000)
    total.set_ylim(-1.75, len(rows) - 0.35)
    total.set_xlabel("hours of continuous simulation, one process",
                     fontsize=NOTE_SIZE + 0.6, color=INK)
    total.set_xticks([1, 10, 100, 1000])
    total.set_xticklabels(["1 h", "10 h", "100 h", "1000 h"])
    total.grid(axis="x", color=MUTED, alpha=0.25, lw=0.7)
    total.set_axisbelow(True)
    for side in ("top", "right", "left"):
        total.spines[side].set_visible(False)
    total.spines["bottom"].set_color(MUTED)
    total.tick_params(colors=MUTED, labelsize=NOTE_SIZE - 0.2)
    for mark, name in ((8.0, "one working day"), (168.0, "one week")):
        # Drawn only across the bars, so the rule does not run through its
        # own label the way a full-height line does.
        total.plot([mark, mark], [-0.42, len(rows) - 0.4], color=INK, lw=0.9, ls=(0, (4, 3)),
                   zorder=1)
        total.text(mark, -1.68, name, rotation=90, fontsize=NOTE_SIZE - 0.6, color=INK,
                   va="bottom", ha="center")
    for position, (_label, count, _), hour in zip(y, rows, hours, strict=True):
        total.text(hour * 1.18, position,
                   f"{count:,} episodes · {_spell(hour)}\n"
                   f"{_spell(hour / WORKERS)} across {WORKERS} processes",
                   va="center", fontsize=NOTE_SIZE - 0.2, color=INK)
    total.set_title("What each method's appetite comes to, at that cost",
                    fontsize=TITLE_SIZE, color=INK, pad=12)

    figure.text(0.5, 0.02,
                "Every wall-clock figure is the measured cost of one push in this project's own "
                f"bench, {WALL_PER_PUSH:.3f} s, multiplied by the pushes each method asks for. The "
                f"episode counts for the two searches follow from {FREE_PARAMETERS} free "
                f"parameters; the {RL_EPISODES:,} for reinforcement learning is quoted, not "
                "measured.",
                ha="center", fontsize=NOTE_SIZE + 0.4, color=INK)
    figure.subplots_adjust(bottom=0.14, top=0.90, left=0.03, right=0.99)
    save(figure, "11-the-sample-budget.png")

    print(f"  one episode at the push cap: {push_cap} x {WALL_PER_PUSH:.4f} s "
          f"= {per_episode:.3f} s of wall clock")
    print(f"  the bench runs {SIM_PER_PUSH / WALL_PER_PUSH:.1f} times faster than real time")
    print(f"  CMA-ES population for {FREE_PARAMETERS} parameters: {population}")
    for (name, count, _), hour in zip(rows, hours, strict=True):
        print(f"    {name.replace(chr(10), ' / '):<58} {count:>9,} episodes  {hour:9.2f} h  "
              f"({hour / 24:6.2f} days)   {hour / WORKERS:8.2f} h on {WORKERS}")


# ---------------------------------------------------------------------------
# 2. what the policy maps from and to
# ---------------------------------------------------------------------------
def what_the_policy_maps() -> int:
    """The observation and the action, on one real table. Returns its seed."""
    seed, table, push = _policy_table()
    here = spots(table)
    short = [chr(ord("A") + i) for i in range(len(table))]
    inputs = 6 * len(table)
    weights = _weights(inputs)

    figure, (left, right) = plt.subplots(1, 2, figsize=(14.6, 9.8),
                                         gridspec_kw={"wspace": 0.04})
    figure.patch.set_facecolor(PAPER)
    for axis in (left, right):
        axis.set_facecolor(PAPER)
        _zone(axis)

    involved = {i for pair in lacks_room(table) for i in pair}
    _draw_table(left, table, short, rings=involved)
    pairs = _mark_short(left, table, short)
    left.set_title(f"What goes in: {inputs} numbers", fontsize=TITLE_SIZE, color=INK, pad=10)

    mover, other, spot, travel, heading = push
    _draw_table(right, table, short, faded=[i for i in range(len(table)) if i != mover])
    widest, foot = table[mover][2], table[mover][3]
    glass_from_above(right, (spot[0], -spot[1]), widest, base_fraction=foot / widest,
                     colour=GOOD, alpha=0.30)
    right.add_patch(Circle((spot[0], -spot[1]), GRIP_ROOM + widest / 2.0, fc="none", ec=GOOD,
                           lw=1.1, ls=(0, (4, 3))))
    push_arrow(right, (here[mover][0], -here[mover][1]), (spot[0], -spot[1]), colour=INK)
    right.set_title("What comes out: three numbers", fontsize=TITLE_SIZE, color=INK, pad=10)

    rows = []
    for index, glass in enumerate(table):
        rows.append(f"{short[index]}   {glass[0]:6.1f} {glass[1]:7.1f}   {glass[4]:5.1f} "
                    f"{glass[2]:5.1f} {glass[3]:5.1f}    yes")
    figure.text(0.145, 0.255,
                "         x       y      tall  wide  foot  upright\n" + "\n".join(rows),
                fontsize=NOTE_SIZE + 0.2, color=INK, family="monospace", va="top")
    moved = [spot if k == mover else p for k, p in enumerate(here)]
    figure.text(0.585, 0.255,
                f"which glass       {short[mover]}\n"
                f"heading        {math.degrees(heading):6.1f} deg\n"
                f"travel         {travel:6.1f} mm\n\n"
                f"the push height is not the policy's to choose: the jaw's\n"
                f"middle rides at {LOWEST_GRIP:.0f} mm because it cannot go lower,\n"
                f"and a tapered glass meets its top edge at {JAW_TOP:.0f} mm.\n\n"
                f"{short[mover]} needs "
                f"{GRIP_ROOM + table[other][2] / 2.0:.0f} mm from {short[other]} and had "
                f"{math.dist(here[mover], here[other]):.0f};\n"
                f"after the push it has {math.dist(spot, here[other]):.0f}. Glasses without room "
                f"go from\n{len(short_glasses(table))} to {len(short_glasses(table, moved))}.",
                fontsize=NOTE_SIZE + 0.2, color=INK, family="monospace", va="top")

    figure.text(0.5, 0.045,
                f"A real table: seed {seed} of the bench's own scene generator, {len(table)} "
                f"tapered glasses, each drawn at its own size, standing in the real glass zone. "
                f"A dashed ring is drawn round each glass that is involved in a crowding: it "
                f"is where a neighbour's middle would have to stay for that glass to be "
                f"grippable,\nand it is a different size round every one, because the test "
                f"depends on the neighbour's width. A policy has to turn "
                f"the left-hand numbers into the right-hand ones. The two ways of doing that "
                f"differ in how many free numbers stand between them: a small network of this "
                f"shape holds {weights:,}, and the strategy this solution searches over holds "
                f"{FREE_PARAMETERS}.",
                ha="center", fontsize=NOTE_SIZE + 0.4, color=INK)
    figure.subplots_adjust(bottom=0.29, top=0.95, left=0.02, right=0.98)
    save(figure, "11-what-the-policy-maps.png")

    print(f"  table: seed {seed}, {len(table)} glasses, "
          f"{len(short_glasses(table))} of them without room")
    for index, glass in enumerate(table):
        print(f"    {short[index]}  at ({glass[0]:6.1f}, {glass[1]:7.1f})  {glass[4]:5.1f} mm "
              f"tall, {glass[2]:5.1f} mm widest, {glass[3]:5.1f} mm foot")
    print("  who lacks room because of whom: "
          f"{[(short[i], short[j], round(math.dist(here[i], here[j]), 1)) for i, j in pairs]}")
    print(f"  the push drawn: {short[mover]} away from {short[other]}, "
          f"{math.degrees(heading):.1f} deg, {travel:.1f} mm; "
          f"{math.dist(here[mover], here[other]):.1f} mm becomes "
          f"{math.dist(spot, here[other]):.1f} mm, against the "
          f"{GRIP_ROOM + table[other][2] / 2.0:.1f} mm it needs")
    print(f"  glasses without room: {len(short_glasses(table))} before, "
          f"{len(short_glasses(table, moved))} after")
    print(f"  observation {inputs} numbers; a {inputs}-64-64-8 network holds {weights:,} "
          f"weights and biases; the searched strategy holds {FREE_PARAMETERS} numbers")
    return seed


def _policy_table():
    """The table the policy picture is drawn on, chosen by a stated rule, not by eye.

    The first held-out tapered table with six glasses — the largest count
    problem 3 handles — on which exactly two glasses lack room, which is few
    enough to read, and for which a legal separating push exists.
    """
    for seed in tapered_seeds(bench.TEST_SEEDS, SEEDS_SCANNED):
        table = table_at(seed)
        if len(table) != 6 or len(short_glasses(table)) != 2:
            continue
        try:
            return seed, table, separating_push(table)
        except RuntimeError:
            continue
    raise RuntimeError("no held-out table in the scanned range draws this picture")


def _weights(inputs: int) -> int:
    """Weights and biases in a small policy network on an observation of this size."""
    sizes = [inputs, 64, 64, 8]
    return sum(a * b + b for a, b in zip(sizes, sizes[1:], strict=False))


# ---------------------------------------------------------------------------
# 3. the reward-shaping trap
# ---------------------------------------------------------------------------
def _walk_away(table, mover: int, steps: int, step: float):
    """Walk one glass across open table, a step at a time, keeping every step legal.

    Each step passes the same tests the programmed planner applies: the whole
    glass inside the zone, inside the arm's reach, with room where it lands and
    taking nobody else's. Nothing here is a push the planner would refuse. It is
    a push the planner would allow and would never choose.
    """
    walk = [spots(table)]
    rest = np.mean([p for i, p in enumerate(walk[0]) if i != mover], axis=0)
    heading = math.atan2(walk[0][mover][1] - rest[1], walk[0][mover][0] - rest[0])
    for _ in range(steps):
        at = walk[-1]
        for turn in (0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75):
            angle = heading + math.radians(turn)
            spot = (at[mover][0] + step * math.cos(angle), at[mover][1] + step * math.sin(angle))
            if landing_ok(table, mover, spot, at):
                walk.append([spot if k == mover else p for k, p in enumerate(at)])
                break
        else:
            break
    return walk


def _trap_table():
    """The table the trap is drawn on, chosen by a stated rule rather than by eye.

    Over the held-out tapered tables in the scanned range, keep the one where a
    glass that has room can be walked the full TRAP_PUSHES steps, and where
    doing so collects the most shaped reward for each millimetre the useful push
    collects.
    """
    best = None
    for seed in tapered_seeds(bench.TEST_SEEDS, SEEDS_SCANNED):
        table = table_at(seed)
        here = spots(table)
        short = short_glasses(table)
        free = [i for i in range(len(table)) if i not in short]
        if not free:
            continue
        try:
            helpful = separating_push(table)
        except RuntimeError:
            continue
        after = [helpful[2] if k == helpful[0] else p for k, p in enumerate(here)]
        useful_gain = separation(after) - separation(here)
        if useful_gain <= 0.0:
            continue
        for mover in free:
            walk = _walk_away(table, mover, TRAP_PUSHES, TRAP_STEP)
            if len(walk) - 1 < TRAP_PUSHES:
                continue
            # A walk that doubles back into a corner is unreadable and is not
            # the behaviour being described, so require it to run outwards.
            if math.dist(walk[0][mover], walk[-1][mover]) < 0.85 * TRAP_PUSHES * TRAP_STEP:
                continue
            ratio = (separation(walk[-1]) - separation(walk[0])) / useful_gain
            if best is None or ratio > best[0]:
                best = (ratio, seed, table, mover, walk, helpful, useful_gain)
    if best is None:
        raise RuntimeError("no held-out table in the scanned range draws this picture")
    return best


def the_shaping_trap() -> None:
    """Pushes that a shaped reward pays for and that fix nothing."""
    ratio, seed, table, mover, walk, helpful, helpful_gain = _trap_table()
    here = spots(table)
    names = [chr(ord("A") + i) for i in range(len(table))]
    good_mover, good_other, good_spot = helpful[0], helpful[1], helpful[2]
    helped = [good_spot if k == good_mover else p for k, p in enumerate(here)]
    useless = len(walk) - 1
    gains = [separation(walk[k + 1]) - separation(walk[k]) for k in range(useless)]

    figure, (plan, curve) = plt.subplots(
        1, 2, figsize=(14.8, 7.6), gridspec_kw={"width_ratios": [1.0, 0.96], "wspace": 0.20})
    figure.patch.set_facecolor(PAPER)
    for axis in (plan, curve):
        axis.set_facecolor(PAPER)

    _zone(plan)
    _draw_table(plan, table, names, faded=[mover])
    _mark_short(plan, table, names)
    for index in range(useless):
        start = (walk[index][mover][0], -walk[index][mover][1])
        end = (walk[index + 1][mover][0], -walk[index + 1][mover][1])
        push_arrow(plan, start, end, colour=WARN, lw=1.5)
        span = math.dist(start, end) or 1.0
        across = (-(end[1] - start[1]) / span, (end[0] - start[0]) / span)
        plan.text((start[0] + end[0]) / 2 + across[0] * 15.0,
                  (start[1] + end[1]) / 2 + across[1] * 15.0,
                  f"+{gains[index]:.0f}", fontsize=NOTE_SIZE - 0.2, color=WARN,
                  ha="center", va="center")
    last = walk[-1][mover]
    glass_from_above(plan, (last[0], -last[1]), table[mover][2],
                     base_fraction=table[mover][3] / table[mover][2], colour=WARN, alpha=0.26)
    plan.text(last[0], -last[1], names[mover], ha="center", va="center", fontsize=LABEL_SIZE,
              color=INK, zorder=10)
    push_arrow(plan, (here[good_mover][0], -here[good_mover][1]),
               (good_spot[0], -good_spot[1]), colour=GOOD, lw=1.8)
    glass_from_above(plan, (good_spot[0], -good_spot[1]), table[good_mover][2],
                     base_fraction=table[good_mover][3] / table[good_mover][2],
                     colour=GOOD, alpha=0.22)
    span = math.dist(here[good_mover], good_spot) or 1.0
    sideways = (-(good_spot[1] - here[good_mover][1]) / span,
                -(good_spot[0] - here[good_mover][0]) / span)
    plan.text((here[good_mover][0] + good_spot[0]) / 2 + sideways[0] * 52.0,
              -(here[good_mover][1] + good_spot[1]) / 2 + sideways[1] * 52.0,
              f"the useful push: +{helpful_gain:.0f}", fontsize=NOTE_SIZE, color=GOOD,
              ha="center", va="center",
              bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.8, pad=1.0))
    plan.set_title(f"{useless} pushes the shaped score pays for, and one it barely notices",
                   fontsize=TITLE_SIZE, color=INK, pad=10)

    steps = np.arange(useless + 1)
    paid = np.concatenate(([0.0], np.cumsum(gains)))
    owed = np.array([shortfall(table, state) for state in walk])
    repaid = owed[0] - owed
    without = np.array([len(short_glasses(table, state)) for state in walk])
    curve.plot(steps, paid, color=WARN, lw=2.0, marker="o", ms=5,
               label="paid by the naive shaped score:\ntotal distance between every pair")
    curve.plot(steps, repaid, color=GOOD, lw=2.0, marker="s", ms=5,
               label="paid by the shortfall the table owes:\nonly glasses without room count")
    curve.legend(loc="upper left", fontsize=NOTE_SIZE - 0.2, frameon=True, framealpha=0.95,
                 edgecolor=MUTED)
    curve.set_xlabel("pushes taken", fontsize=NOTE_SIZE + 0.6, color=INK)
    curve.set_ylabel("reward collected, mm", fontsize=NOTE_SIZE + 0.6, color=INK)
    curve.set_xticks(steps)
    curve.set_xlim(-0.25, useless + 0.25)
    curve.set_ylim(-0.06 * paid[-1], 1.42 * paid[-1])
    curve.tick_params(colors=MUTED, labelsize=NOTE_SIZE - 0.2)
    for side in ("top", "right"):
        curve.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        curve.spines[side].set_color(MUTED)
    curve.grid(axis="y", color=MUTED, alpha=0.22, lw=0.7)
    curve.set_axisbelow(True)

    twin = curve.twinx()
    twin.step(steps, without, where="post", color=INK, lw=2.2)
    twin.set_ylabel("glasses still without room", fontsize=NOTE_SIZE + 0.6, color=INK)
    twin.set_ylim(0, max(int(without.max()) + 2, 3))
    twin.set_yticks(range(int(twin.get_ylim()[1]) + 1))
    twin.tick_params(colors=MUTED, labelsize=NOTE_SIZE - 0.2)
    for side in ("top", "left"):
        twin.spines[side].set_visible(False)
    twin.spines["right"].set_color(INK)
    twin.text(useless / 2.0, without[0] + 0.42,
              f"{without[0]} glasses without room at the start, and {without[-1]} at the end",
              fontsize=NOTE_SIZE + 0.2, color=INK, ha="center")
    curve.set_title("One score climbs; the other knows nothing happened",
                    fontsize=TITLE_SIZE, color=INK, pad=10)

    figure.text(0.5, 0.045,
                "An illustration, not a measurement: no policy has been trained here. The table is "
                f"seed {seed} of the bench's own scene generator and every width in it is real, "
                "and each push is assumed to land where it was aimed, which the programmed run's "
                f"{SCORED_PUSHES} pushes justify to within {AIM_ERROR_MEDIAN:.0f} mm at the "
                f"median.\nWalking the one glass that already had room out across empty table "
                f"collects {paid[-1]:.0f} mm of the naive score and repays none of the "
                f"{owed[0]:.0f} mm the table owes. The push that gives a glass its room collects "
                f"{helpful_gain:.0f} mm and repays {owed[0] - shortfall(table, helped):.0f}.",
                ha="center", fontsize=NOTE_SIZE + 0.4, color=INK)
    figure.subplots_adjust(bottom=0.19, top=0.92, left=0.03, right=0.95)
    save(figure, "11-the-shaping-trap.png")

    print(f"  table: seed {seed}, {len(table)} glasses, {len(short_glasses(table))} without room, "
          f"walking glass {names[mover]}, which has room")
    print(f"  shaped gains per {TRAP_STEP:.0f} mm push: {[round(g, 1) for g in gains]}, "
          f"total {paid[-1]:.1f} mm")
    print(f"  glasses without room after each push: {[int(c) for c in without]}")
    print(f"  the shortfall the table owes after each push: {[round(float(o), 1) for o in owed]}")
    print(f"  the useful push ({names[good_mover]} away from {names[good_other]}) collects "
          f"{helpful_gain:.1f} mm of the naive score and repays "
          f"{owed[0] - shortfall(table, helped):.1f} mm of the shortfall")
    print(f"  so the naive score prefers the useless walk by {ratio:.1f} to one, and the walk can "
          "be repeated for as long as the table has room")


# ---------------------------------------------------------------------------
# 4. the friction a policy learns without being told
# ---------------------------------------------------------------------------
def the_friction_it_learned() -> None:
    """Which glasses can be pushed at all, at three values of a number the arm is never told."""
    import random

    rng = random.Random(DRAW_SEED)
    outlines = [draw(KIND, rng)[0] for _ in range(DRAWN)]
    bases = np.array([2000.0 * float(o.radius[0]) for o in outlines])
    heights = np.array([1000.0 * o.total_height for o in outlines])
    rims = np.array([1000.0 * o.max_diameter for o in outlines])
    frictions = ((MU_LOW, GOOD), (TABLE_FRICTION, INK), (MU_HIGH, WARN))
    # Decided at the jaw's top edge, which is the height a tapered glass is
    # really pushed at. The figures at the middle of the jaw are printed
    # beside them, because the difference is the whole point.
    ok = {mu: np.array([pushable(b, mu, JAW_TOP) for b in bases]) for mu, _ in frictions}
    ok_middle = {mu: np.array([pushable(b, mu, LOWEST_GRIP) for b in bases])
                 for mu, _ in frictions}

    figure, (side, spread) = new(15.2, 6.6, columns=2)

    widest_foot = int(np.argmax(bases))
    narrowest_foot = int(np.argmin(bases))
    bare(side)
    side.set_aspect("equal")
    stands = ((-150.0, widest_foot, "right"), (150.0, narrowest_foot, "left"))
    # The two jaw rules stop short of the right-hand labels rather than running
    # through them, which is the one collision this panel keeps producing.
    right_edge = stands[1][0] + rims[stands[1][1]] / 2 + 10
    side.plot([-290, right_edge], [LOWEST_GRIP, LOWEST_GRIP], color=MUTED, lw=1.0,
              ls=(0, (2, 3)))
    side.plot([-290, right_edge], [JAW_TOP, JAW_TOP], color=INK, lw=1.2, ls=(0, (5, 3)))
    for at, index, align in stands:
        rim, base = rims[index], bases[index]
        glass_from_the_side(side, at, heights[index], rim, base_fraction=base / rim)
        side.text(at, -20, f"foot {base:.0f} mm", ha="center", fontsize=NOTE_SIZE + 0.2, color=INK)
        edge = at - rim / 2 - 14 if align == "right" else at + rim / 2 + 14
        ordered = sorted(frictions, key=lambda m: topple_height(base, m[0]))
        limits = [topple_height(base, mu) for mu, _ in ordered]
        # Labels that sit closer together than they can be read are spread to a
        # minimum gap and then re-centred, so they stay in the same order and
        # nobody's label drifts far from its own rule.
        labels = list(limits)
        for k in range(1, len(labels)):
            labels[k] = max(labels[k], labels[k - 1] + LABEL_GAP)
        drift = (labels[-1] - limits[-1]) / 2.0
        labels = [value - drift for value in labels]
        for (mu, colour), limit, label in zip(ordered, limits, labels, strict=True):
            side.plot([at - rim / 2 - 10, at + rim / 2 + 10], [limit, limit], color=colour, lw=1.5)
            if abs(label - limit) > 0.5:
                side.plot([edge, at - rim / 2 - 10 if align == "right" else at + rim / 2 + 10],
                          [label, limit], color=colour, lw=0.7, alpha=0.8)
            side.text(edge - 4 if align == "right" else edge + 4, label,
                      f"tips above {limit:.0f} mm at mu {mu}",
                      fontsize=NOTE_SIZE, color=colour, va="center", ha=align)
        push_arrow(side, (at - rim / 2 - 46, JAW_TOP), (at - base / 2 - 3, JAW_TOP),
                   colour=GOOD if pushable(base, TABLE_FRICTION, JAW_TOP) else WARN, lw=1.6)
    side.plot([-290, 290], [0, 0], color=INK, lw=1.5)
    side.text(0, 152,
              f"the middle of the jaw rides at {LOWEST_GRIP:.0f} mm,\n"
              f"but a tapered glass meets its top edge\n"
              f"at {JAW_TOP:.0f} mm first, so {JAW_TOP:.0f} mm is the height\n"
              "it is really pushed at",
              ha="center", va="center", fontsize=NOTE_SIZE, color=INK)
    side.set_xlim(-300, 300)
    side.set_ylim(-58, 218)
    side.set_title("The widest foot drawn and the narrowest, at three frictions",
                   fontsize=TITLE_SIZE, color=INK, pad=10)

    bands = (
        (ok[TABLE_FRICTION], GOOD,
         f"pushable at the {TABLE_FRICTION} this bench is set to"),
        (ok[MU_LOW] & ~ok[TABLE_FRICTION], MUTED,
         f"pushable at mu {MU_LOW}, not at mu {TABLE_FRICTION}"),
        (~ok[MU_LOW], WARN, "pushable at neither: refuse it"),
    )
    for mask, colour, label in bands:
        spread.scatter(bases[mask], heights[mask], s=18, color=colour, alpha=0.75, lw=0,
                       label=f"{label} — {int(mask.sum())}")
    for mu, colour in frictions:
        edge = 2.0 * JAW_TOP * mu
        spread.axvline(edge, color=colour, lw=1.6, zorder=1)
        spread.text(edge - 0.7, heights.min() - 6,
                    f"mu {mu}: the foot must beat {edge:g} mm"
                    + ("  (this bench)" if mu == TABLE_FRICTION else ""),
                    fontsize=NOTE_SIZE, color=colour, va="bottom", ha="right", rotation=90,
                    bbox=dict(facecolor=PAPER, edgecolor="none", alpha=0.85, pad=1.0))
    spread.set_xlabel("foot diameter, mm", fontsize=NOTE_SIZE + 0.6, color=INK)
    spread.set_ylabel("height, mm", fontsize=NOTE_SIZE + 0.6, color=INK)
    spread.set_ylim(heights.min() - 30, heights.max() + 16)
    spread.tick_params(colors=MUTED, labelsize=NOTE_SIZE - 0.2)
    for sd in ("top", "right"):
        spread.spines[sd].set_visible(False)
    for sd in ("left", "bottom"):
        spread.spines[sd].set_color(MUTED)
    spread.grid(color=MUTED, alpha=0.2, lw=0.7)
    spread.set_axisbelow(True)
    spread.legend(loc="upper right", fontsize=NOTE_SIZE, frameon=True, framealpha=0.95,
                  edgecolor=MUTED)
    spread.set_title(f"{DRAWN} glasses the spawner drew, sorted by a number the arm is never told",
                     fontsize=TITLE_SIZE, color=INK, pad=10)

    figure.text(0.5, 0.035,
                "A push at height h slides a glass while h is below a / mu, where a is half the "
                f"foot and mu is the friction with the table. A tapered glass meets the jaw's "
                f"top edge at {JAW_TOP:.0f} mm, so the foot has to be wider than "
                f"2 x {JAW_TOP:.0f} x mu before any push is safe.\nAt mu {MU_LOW}, "
                f"{100.0 * ok[MU_LOW].mean():.1f} per cent of these glasses can be pushed; at the "
                f"{TABLE_FRICTION} this bench is set to, {100.0 * ok[TABLE_FRICTION].mean():.1f} "
                f"per cent; at mu {MU_HIGH}, {100.0 * ok[MU_HIGH].mean():.1f} per cent. A policy "
                f"trained in this bench has learned {TABLE_FRICTION}, and nothing in the policy "
                "says so.",
                ha="center", fontsize=NOTE_SIZE + 0.4, color=INK)
    figure.subplots_adjust(bottom=0.19, top=0.91, left=0.03, right=0.99, wspace=0.16)
    save(figure, "11-the-friction-it-learned.png")

    print(f"  {DRAWN} drawn {KIND}s from seed {DRAW_SEED}: foot {bases.min():.1f} to "
          f"{bases.max():.1f} mm, height {heights.min():.1f} to {heights.max():.1f} mm")
    for mu, _ in frictions:
        print(f"    mu {mu}: at the jaw's top edge, {JAW_TOP:.0f} mm, "
              f"{int(ok[mu].sum())}/{DRAWN} pushable = {100.0 * ok[mu].mean():.1f} per cent, "
              f"the foot has to beat {2.0 * JAW_TOP * mu:g} mm; at the middle of the jaw, "
              f"{LOWEST_GRIP:.0f} mm, it would be {int(ok_middle[mu].sum())}/{DRAWN} = "
              f"{100.0 * ok_middle[mu].mean():.1f} per cent")
    print(f"    the widest foot drawn is {bases.max():.1f} mm, so at mu {MU_HIGH} and "
          f"{JAW_TOP:.0f} mm no glass of this kind can be pushed at all")
    for label, index in (("widest foot", widest_foot), ("narrowest foot", narrowest_foot)):
        print(f"    the {label} drawn is {bases[index]:.1f} mm on a glass {heights[index]:.1f} mm "
              f"tall: tips above " + ", ".join(
                  f"{topple_height(bases[index], mu):.1f} mm at mu {mu}" for mu, _ in frictions))


# ---------------------------------------------------------------------------
# What the real tables look like, printed rather than drawn
# ---------------------------------------------------------------------------
def what_a_run_contains() -> tuple[int, float]:
    """How crowded the real tables are, and how much of the job one run is.

    Returns the push cap a run allows and the pushes the programmed planner
    actually takes, so the budget picture quotes the same two numbers.
    """
    print(f"  bench.py: GRIP_ROOM {1000.0 * bench.GRIP_ROOM:.0f} mm, so a glass needs that plus "
          f"half its neighbour's width, not a fixed {GRIPPABLE_APART:.0f} mm")
    print(f"  bench.py: TEST_SEEDS {bench.TEST_SEEDS:,} divides the training tables from the "
          f"held-out ones; TABLE_FRICTION {bench.TABLE_FRICTION}; a glass leaning more than "
          f"{bench.STANDING_TILT_DEG:.0f} degrees has fallen over; the jaw's middle rides at "
          f"{1000.0 * bench.PUSH_HEIGHT:.0f} mm and its top edge at {1000.0 * bench.JAW_TOP:.0f} mm")
    for label, start_seed in (("training", 0), ("held out", bench.TEST_SEEDS)):
        seeds = tapered_seeds(start_seed, SEEDS_SCANNED)
        glasses = lacking = ties = oneway = symmetric = 0
        closest = []
        for seed in seeds:
            table = table_at(seed)
            here = spots(table)
            glasses += len(table)
            pairs = lacks_room(table)
            lacking += len(short_glasses(table))
            ties += len({tuple(sorted(pair)) for pair in pairs})
            oneway += sum(1 for i, j in pairs if (j, i) not in pairs)
            symmetric += len(crowded_pairs(here))
            closest.append(min(math.dist(here[i], here[j])
                               for i in range(len(table)) for j in range(i + 1, len(table))))
        print(f"    {label}: {len(seeds)} tapered tables, {glasses} glasses, {lacking} of them "
              f"without room ({100.0 * lacking / glasses:.1f} per cent), "
              f"{lacking / len(seeds):.2f} a table")
        print(f"      {ties} crowded pairs, {oneway} of which are crowded one way only, because "
              f"the two glasses are not the same width")
        print(f"      the conservative symmetric test — {GRIPPABLE_APART:.0f} mm between middles "
              f"whatever the widths — would report {symmetric} pairs instead of {ties}")
        print(f"      closest pair: {min(closest):.1f} mm at worst, "
              f"{float(np.median(closest)):.1f} mm typical")
    # grippable() with the neighbour's real width is the two-glass form of the
    # same test, and this is what it says about the tightest pair on one table.
    sample = table_at(tapered_seeds(bench.TEST_SEEDS, SEEDS_SCANNED)[0])
    at = spots(sample)
    i, j = min(lacks_room(sample), key=lambda pair: math.dist(at[pair[0]], at[pair[1]]))
    print(f"      on the first of them, glass {i} is {math.dist(at[i], at[j]):.1f} mm from "
          f"glass {j}, which is {sample[j][2]:.1f} mm wide, so grippable says "
          f"{grippable(at[i], at[j], sample[j][2])}")
    cap = _push_cap()
    print(f"  problem-3-programmed/run.py caps a table at {cap} pushes; over its "
          f"{SCORED_SCENES} held-out tables it took {SCORED_PUSHES}, "
          f"{SCORED_PUSHES / SCORED_SCENES:.2f} a table")
    return cap, SCORED_PUSHES / SCORED_SCENES


def _push_cap() -> int:
    """PUSHES_PER_TABLE, read out of problem-3-programmed/run.py rather than copied."""
    text = (ROOT / "problem-3-programmed" / "run.py").read_text()
    for line in text.splitlines():
        if line.startswith("PUSHES_PER_TABLE"):
            return int(line.split("=")[1].strip())
    raise RuntimeError("PUSHES_PER_TABLE is no longer declared in problem-3-programmed/run.py")


def main() -> None:
    print("what a run contains:")
    cap, _per_run = what_a_run_contains()
    print("the sample budget:")
    the_sample_budget(cap)
    print("what the policy maps:")
    what_the_policy_maps()
    print("the reward-shaping trap:")
    the_shaping_trap()
    print("the friction a policy learns without being told:")
    the_friction_it_learned()


if __name__ == "__main__":
    main()
