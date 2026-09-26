"""Measure what solution 1's peel is worth on the bench's own crowded tables.

Throwaway, and kept here rather than in images/generators/problem-3/ because it
imports ``bench``, which imports MuJoCo, which the root environment does not
have. The numbers it prints are quoted in
docs/problem-3/solutions/01-do-not-drag-at-all.md and held as literals in
images/generators/problem-3/make_01_images.py.

    cd problem-3-programmed && pixi run python measure_peel.py
"""

from __future__ import annotations

import math
import random
from collections import Counter

from work_cell.glasses.shapes import KIND_RANGES, family

import bench
from bench import GRIP_ROOM, JAW_TOP, PUSH_HEIGHT, TABLE_FRICTION, has_room

# The held-out half of the scene space: bench.TEST_SEEDS says everything from
# 10,000 on is for testing, and training draws only below it.
FIRST, LAST = bench.TEST_SEEDS, bench.TEST_SEEDS + 1000

# What run.py actually takes a glass at: three standard deviations of the
# measurement error in the gap.
TAKE_MARGIN = 0.005

MU_LOW, MU_HIGH = 0.3, 0.5
GRIPPABLE_APART = 0.140


def table(seed: int) -> list[dict]:
    """One bench scene, in the terms problem 2 hands over, in millimetres."""
    return [
        {
            "kind": glass.kind,
            "at": (glass.position[0], glass.position[1]),
            "rim": glass.outline.max_diameter,
            "foot": 2.0 * float(glass.outline.radius[0]),
            "height": glass.outline.total_height,
        }
        for glass in bench.scene(seed)
    ]


def blockers(rows: list[dict], target: int, live, margin: float = 0.0) -> list[int]:
    """Which glasses still on the table are in the way, by the bench's own test."""
    here = rows[target]["at"]
    return [
        other for other in live
        if other != target
        and not has_room(here[0], here[1], [(*rows[other]["at"], rows[other]["rim"])], margin)
    ]


def peel(rows: list[dict], margin: float = 0.0) -> tuple[list[list[int]], list[int]]:
    live = set(range(len(rows)))
    rounds: list[list[int]] = []
    while True:
        free = [i for i in sorted(live) if not blockers(rows, i, live, margin)]
        if not free:
            return rounds, sorted(live)
        rounds.append(free)
        live -= set(free)


def peel_one_at_a_time(rows: list[dict], rng: random.Random, margin: float = 0.0) -> list[int]:
    live = set(range(len(rows)))
    while True:
        free = [i for i in sorted(live) if not blockers(rows, i, live, margin)]
        if not free:
            return sorted(live)
        live.discard(rng.choice(free))


def topple(foot: float, mu: float) -> float:
    return (foot / 2.0) / mu


def crowded_pairs(rows: list[dict], live) -> int:
    live = sorted(live)
    return sum(
        1 for a, i in enumerate(live) for j in live[a + 1:]
        if math.dist(rows[i]["at"], rows[j]["at"]) < GRIPPABLE_APART
    )


def sweep(margin: float) -> dict:
    rng = random.Random(3)
    out = {
        "outcomes": Counter(), "residues": Counter(), "rounds": Counter(), "kinds": Counter(),
        "glasses": 0, "racked": 0, "left": 0, "without_room": 0, "disagreed": 0, "scenes": 0,
        "pairs_before": 0, "pairs_after": 0, "closest": [], "unpushable": Counter(),
        "residue_without_room": 0, "picks": [],
    }
    for seed in range(FIRST, LAST):
        rows = table(seed)
        whole = set(range(len(rows)))
        out["scenes"] += 1
        out["glasses"] += len(rows)
        out["kinds"][rows[0]["kind"]] += 1
        out["without_room"] += sum(1 for i in whole if blockers(rows, i, whole))
        out["pairs_before"] += crowded_pairs(rows, whole)
        out["closest"].append(min(
            math.dist(rows[i]["at"], rows[j]["at"])
            for i in whole for j in whole if j > i
        ))

        rounds, residue = peel(rows, margin)
        if peel_one_at_a_time(rows, rng, margin) != residue:
            out["disagreed"] += 1
        taken = sum(len(one) for one in rounds)
        out["rounds"][len(rounds)] += 1
        out["residues"][len(residue)] += 1
        out["racked"] += taken
        out["left"] += len(residue)
        out["picks"].append(taken)
        out["pairs_after"] += crowded_pairs(rows, residue)
        out["residue_without_room"] += sum(1 for i in residue if blockers(rows, i, set(residue)))
        for i in residue:
            for mu in (MU_LOW, TABLE_FRICTION, MU_HIGH):
                if topple(rows[i]["foot"], mu) <= PUSH_HEIGHT:
                    out["unpushable"][mu] += 1
        if not residue:
            out["outcomes"]["nothing left to push"] += 1
        elif taken == 0:
            out["outcomes"]["nothing was free"] += 1
        else:
            out["outcomes"]["a residue is left"] += 1
    return out


def show(name: str, found: dict) -> None:
    scenes, glasses = found["scenes"], found["glasses"]
    print(f"--- the peel on bench.scene, seeds {FIRST}..{LAST - 1}, take margin {name}")
    print(f"    {scenes} scenes, {glasses} glasses, kinds {dict(found['kinds'])}")
    print(f"    glasses without room at the start: {found['without_room']} "
          f"= {100 * found['without_room'] / glasses:.1f}%")
    closest = sorted(found["closest"])
    print(f"    closest pair per scene: min {1000 * closest[0]:.1f}, "
          f"median {1000 * closest[len(closest) // 2]:.1f}, max {1000 * closest[-1]:.1f} mm")
    for outcome, count in found["outcomes"].most_common():
        print(f"    {outcome}: {count} = {100 * count / scenes:.1f}%")
    print(f"    rounds: {dict(sorted(found['rounds'].items()))}, "
          f"more than one on {sum(v for k, v in found['rounds'].items() if k > 1)} "
          f"= {100 * sum(v for k, v in found['rounds'].items() if k > 1) / scenes:.1f}%")
    print(f"    residue sizes: {dict(sorted(found['residues'].items()))}")
    print(f"    a random one-at-a-time order disagreed on {found['disagreed']} scenes")
    print(f"    pairs inside 140 mm: {found['pairs_before']} before "
          f"({found['pairs_before'] / scenes:.2f} a scene), {found['pairs_after']} after "
          f"({found['pairs_after'] / scenes:.2f} a scene)")
    print(f"    glasses racked with no push: {found['racked']}/{glasses} "
          f"= {100 * found['racked'] / glasses:.1f}%, left {found['left']}")
    print(f"    free picks a scene: mean {sum(found['picks']) / scenes:.2f}")
    for mu in (MU_LOW, TABLE_FRICTION, MU_HIGH):
        count = found["unpushable"][mu]
        print(f"    of the {found['left']} left, {count} = {100 * count / found['left']:.1f}% "
              f"cannot be pushed at mu={mu}")


def pushing() -> None:
    """The friction cliff, at the jaw's real height as well as the gripper's lowest."""
    for kind in bench.KINDS:
        feet = [2.0 * float(outline.radius[0]) for outline, _ in family(kind, 400, 7)]
        line = f"    {kind}: foot {1000 * min(feet):.1f}-{1000 * max(feet):.1f} mm"
        for height, label in ((PUSH_HEIGHT, "fingertip"), (JAW_TOP, "jaw top")):
            for mu in (MU_LOW, TABLE_FRICTION, MU_HIGH):
                ok = sum(1 for foot in feet if topple(foot, mu) > height)
                line += f"; {label} mu={mu}: {100 * ok / len(feet):.1f}%"
        print(line)
    rims = KIND_RANGES["tapered_glass"]["rim_diameter"]
    widest = max(KIND_RANGES[k].get("rim_diameter", KIND_RANGES[k].get("bowl_diameter"))[1]
                 for k in bench.KINDS)
    narrowest = min(KIND_RANGES[k].get("rim_diameter", KIND_RANGES[k].get("bowl_diameter"))[0]
                    for k in bench.KINDS)
    print(f"    tapered rim {1000 * rims[0]:.0f}-{1000 * rims[1]:.0f} mm; over all four kinds "
          f"{1000 * narrowest:.0f}-{1000 * widest:.0f} mm")
    print(f"    so the threshold runs {1000 * (GRIP_ROOM + narrowest / 2):.1f} to "
          f"{1000 * (GRIP_ROOM + widest / 2):.1f} mm over four kinds, and "
          f"{1000 * (GRIP_ROOM + rims[0] / 2):.1f} to {1000 * (GRIP_ROOM + rims[1] / 2):.1f} mm "
          f"for the tapered kind alone")
    print(f"    bench pushes at {1000 * PUSH_HEIGHT:.0f} mm, jaw top edge {1000 * JAW_TOP:.0f} mm, "
          f"table friction in the simulator {TABLE_FRICTION} (never told to the arm)")


def example(seed: int) -> None:
    rows = table(seed)
    names = "ABCDEF"
    whole = set(range(len(rows)))
    rounds, residue = peel(rows)
    rounds_m, residue_m = peel(rows, TAKE_MARGIN)
    print(f"--- scene {seed}: kind {rows[0]['kind']}, {len(rows)} glasses")
    print(f"    rounds {[[names[i] for i in one] for one in rounds]}, "
          f"residue {[names[i] for i in residue]}; "
          f"with the 5 mm margin, residue {[names[i] for i in residue_m]}")
    for i, row in enumerate(rows):
        print(f"    {names[i]} at ({1000 * row['at'][0]:.0f}, {1000 * row['at'][1]:.0f}), "
              f"rim {1000 * row['rim']:.1f}, foot {1000 * row['foot']:.1f}, "
              f"height {1000 * row['height']:.1f}, blocked by "
              f"{[names[o] for o in blockers(rows, i, whole)]}, tips above "
              f"{1000 * topple(row['foot'], MU_LOW):.1f}/{1000 * topple(row['foot'], TABLE_FRICTION):.1f}/"
              f"{1000 * topple(row['foot'], MU_HIGH):.1f} mm at mu=0.3/0.35/0.5")
    for i in sorted(whole):
        for j in sorted(whole):
            if j <= i:
                continue
            gap = math.dist(rows[i]["at"], rows[j]["at"])
            if gap < GRIPPABLE_APART:
                print(f"    {names[i]}-{names[j]}: {1000 * gap:.1f} mm apart, "
                      f"{names[i]} needs {1000 * (GRIP_ROOM + rows[j]['rim'] / 2):.1f}, "
                      f"{names[j]} needs {1000 * (GRIP_ROOM + rows[i]['rim'] / 2):.1f}")


def find_examples() -> None:
    """A scene the peel empties in more than one round, and one it stalls on."""
    cascade = stall = mutual = None
    for seed in range(FIRST, FIRST + 400):
        rows = table(seed)
        rounds, residue = peel(rows)
        if cascade is None and not residue and len(rounds) > 1 and len(rows) == 4:
            cascade = seed
        if mutual is None and len(residue) == 2 and rounds:
            mutual = seed
        if stall is None and not rounds:
            stall = seed
    print(f"--- examples: cascade {cascade}, two left {mutual}, nothing free {stall}")
    for seed in (cascade, mutual, stall):
        if seed is not None:
            example(seed)


if __name__ == "__main__":
    print("--- the friction cliff, 400 drawn glasses of each kind, seed 7")
    pushing()
    show("0 mm", sweep(0.0))
    show("5 mm, as run.py takes them", sweep(TAKE_MARGIN))
    find_examples()
