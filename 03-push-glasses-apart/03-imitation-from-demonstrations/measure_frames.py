"""Is a chunk easier to learn when it is written relative to the glass it pushes?

A policy is fitted on the teacher's chunks. How hard that fit is depends on how
much the target varies, so this measures the same demonstrations written three
ways:

- **on the table** — the waypoint's own x and y, which is what solution 3 fits
  on today.
- **from the glass** — the same waypoint as an offset from the measured middle
  of the glass the push is for.
- **from the glass, in the push's own frame** — that offset rotated so that one
  number is along the push and the other across it.

The spread of each is reported as a radius: the square root of the summed
variances in the two directions, which is the typical distance from the middle
of the distribution. A smaller spread is a smaller thing to learn.

Nothing here trains anything and nothing is chosen by the result. The tables are
this solution's own demonstration band, below the bench's dividing line.

    pixi run python 03-imitation-from-demonstrations/measure_frames.py
    pixi run python 03-imitation-from-demonstrations/measure_frames.py --tables 20
"""

import argparse
import json

import numpy as np
import teacher
from chunks import push_segment
from collect import FIRST_TABLE, Watched, dropped_because

p = argparse.ArgumentParser()
p.add_argument("--tables", type=int, default=300)
p.add_argument("--first", type=int, default=FIRST_TABLE)
a = p.parse_args()

pick = teacher.pick_pushes()
rows = []
for seed in range(a.first, a.first + a.tables):
    table = Watched(seed)
    looks, probes = [], []
    try:
        # Bound as defaults rather than captured, because the lists are new on
        # every table and a captured name would be the last table's.
        def watch(seen, push, felt, probe, looks=looks, probes=probes):
            looks.append(seen)
            probes.append(probe)

        teacher.clear(table, pick, watch=watch)
        for record, before, probe, seen in zip(
            table.records, table.shortfalls, probes, looks, strict=True
        ):
            if dropped_because(record, probe, table, before) is not None:
                continue
            segment = push_segment(record.waypoints)
            if not segment:
                continue
            glass = next((g for g in seen if g.id == record.push.glass), None)
            if glass is None:
                continue
            rows.append(
                {
                    "first": (segment[0].x, segment[0].y),
                    "last": (segment[-1].x, segment[-1].y),
                    "glass": (glass.x, glass.y),
                    "heading": record.push.heading,
                }
            )
    finally:
        table.close()

print(f"{len(rows)} demonstrations from {a.tables} tables\n")


def spread(points: np.ndarray) -> float:
    """The typical distance from the middle of a cloud of points, in mm."""
    return 1000 * float(np.sqrt(points.var(axis=0).sum()))


def report(name: str, which: str) -> dict:
    point = np.array([r[which] for r in rows])
    glass = np.array([r["glass"] for r in rows])
    heading = np.array([r["heading"] for r in rows])
    offset = point - glass
    turn = np.stack(
        [
            np.stack([np.cos(-heading), -np.sin(-heading)], axis=1),
            np.stack([np.sin(-heading), np.cos(-heading)], axis=1),
        ],
        axis=1,
    )
    framed = np.einsum("nij,nj->ni", turn, offset)
    out = {
        "on the table": round(spread(point), 1),
        "from the glass": round(spread(offset), 1),
        "from the glass, in the push's frame": round(spread(framed), 1),
        "along the push, mean mm": round(1000 * float(framed[:, 0].mean()), 1),
        "along the push, sd mm": round(1000 * float(framed[:, 0].std()), 1),
        "across the push, sd mm": round(1000 * float(framed[:, 1].std()), 1),
    }
    print(f"--- {name}")
    for key, value in out.items():
        print(f"    {key:38s} {value:>8.1f}")
    return out


summary = {
    "demonstrations": len(rows),
    "tables": a.tables,
    "where the chunk starts": report("where the chunk starts (the descent)", "first"),
    "where the chunk ends": report("where the chunk ends (the aim)", "last"),
}
print()
print(json.dumps(summary))
