"""Does pushing more slowly topple fewer glasses? Measured, because the limit says not.

The same push, on the same table, carried out at several speeds. The push is
chosen once from the first look, which is seeded, so every speed is given an
identical push and the only thing that varies is how fast the jaw drives it.

The limit in ``pushing-without-toppling.md`` has no speed term in it, so the
arithmetic predicts that speed changes nothing. This is the check on that
prediction, and the numbers it prints are the ones that document quotes.

Nothing here trains anything and nothing is chosen by the result. Tables are
drawn from below the bench's dividing line.

    pixi run python 02-geometry-ranked/measure_push_speed.py
    pixi run python 02-geometry-ranked/measure_push_speed.py --tables 25
"""

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

# ``teacher`` is solution 3's loader for solution 2's chooser. It is borrowed
# rather than copied, so that the push measured here is the push the teacher
# really makes. The path is taken from this file rather than from wherever the
# script was run.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "03-imitation-from-demonstrations"))

import teacher  # noqa: E402

import bench  # noqa: E402
from bench import STANDING_TILT_DEG, Bench  # noqa: E402, I001

p = argparse.ArgumentParser()
p.add_argument("--tables", type=int, default=300)
p.add_argument("--first", type=int, default=1000)
p.add_argument("--speeds", type=str, default="0.005,0.01,0.02,0.04,0.08")
a = p.parse_args()

speeds = [float(s) for s in a.speeds.split(",")]
pick = teacher.pick_pushes()
was = bench.PUSH_SPEED
print(f"bench PUSH_SPEED is {was} m/s; trying {speeds}", flush=True)


def chosen(seed):
    """The push solution 2 makes on its first look at this table."""
    table = Bench(seed)
    try:
        push, _ = pick(table.look(), set())
        return push
    finally:
        if hasattr(table, "close"):
            table.close()


def carried_out(seed, push, speed):
    """That push at this speed. Returns whether a glass fell and how far the target moved."""
    bench.PUSH_SPEED = speed
    table = Bench(seed)
    try:
        before = table.position(push.glass)
        felt = table.push(push)
        after = table.position(push.glass)
        fell = any(table.tilt(i) >= STANDING_TILT_DEG for i in table.on_table())
        both = before is not None and after is not None
        moved = 1000 * math.dist(before[:2], after[:2]) if both else 0.0
        return fell, moved, felt
    finally:
        if hasattr(table, "close"):
            table.close()


tally = {s: Counter() for s in speeds}
moved_mm = {s: [] for s in speeds}
tried = 0
for seed in range(a.first, a.first + a.tables):
    push = chosen(seed)
    if push is None:
        continue
    tried += 1
    for speed in speeds:
        fell, moved, felt = carried_out(seed, push, speed)
        tally[speed]["toppled" if fell else "stayed up"] += 1
        tally[speed]["touched nothing"] += felt.touched is None
        moved_mm[speed].append(moved)

bench.PUSH_SPEED = was
print(f"\n{tried} tables with a push to make, of {a.tables} looked at\n")
print(f"{'speed m/s':>10}  {'toppled':>8}  {'of':>5}  {'share':>6}  {'median mm moved':>16}")
out = {}
for speed in speeds:
    t = tally[speed]
    n = t["toppled"] + t["stayed up"]
    mid = sorted(moved_mm[speed])[len(moved_mm[speed]) // 2]
    print(f"{speed:>10}  {t['toppled']:>8}  {n:>5}  {t['toppled'] / n:>6.1%}  {mid:>16.1f}")
    out[str(speed)] = {"toppled": t["toppled"], "pushes": n, "median_mm_moved": round(mid, 1),
                       "touched_nothing": t["touched nothing"]}
print(json.dumps(out))
