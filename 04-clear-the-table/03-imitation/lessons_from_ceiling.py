"""Lessons for imitation from the search that tries pushes first: distillation.

``python lessons_from_ceiling.py --first 5000 --tables 240 --out data/lessons-a.jsonl --workers 8``

The search in ``ceiling_search.py`` reaches far more than any learned solution, because before
each move it makes thirty pushes in the physics and keeps the best. A real cell cannot do
that, so it cannot be a solution. It can be a teacher. This runs it on training tables
and writes down, for every turn, the table as it stood and what the search did: the push
it made, or "finished" when no push it tried was worth making.

The second kind of lesson is the one imitation never had. Copying random pushes that
happened to work, it only learnt to stop on tables that were already clear. Here it is
also shown tables where every push the search tried would tip a glass or make things
worse, and the answer on those is to stop.

Imitation then copies these lessons (``imitation.py --lessons``). The fast network learns
to answer the way the slow search would; that is what "distillation" means.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

from examiner.motion.moveit_connection import MoveItLink
from examiner.tools import ceiling_search

PER_TABLE = 120.0  # arm seconds one table may take; the search's answers are capped at ten as well


def work(first: int, tables: int, out: Path, worker: int, candidates: int) -> None:
    rng = random.Random(first * 1013 + worker)
    started = time.perf_counter()
    count = 0
    with MoveItLink(domain=worker) as link, open(out, "w") as handle:
        for seed in range(first, first + tables):
            lessons: list = []
            try:
                ceiling_search.clear_table(seed, link, PER_TABLE, candidates, rng, lessons=lessons)
            except Exception as error:  # one bad table is skipped, not the whole run
                print(f"[{worker}] table {seed} failed: {error}", flush=True)
                continue
            for lesson in lessons:
                handle.write(json.dumps(lesson) + "\n")
            handle.flush()
            count += len(lessons)
            if (seed - first + 1) % 5 == 0:
                print(
                    f"[{worker}] {seed - first + 1}/{tables} tables, {count} lessons, "
                    f"{time.perf_counter() - started:.0f} s",
                    flush=True,
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--tables", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--worker", type=int, default=-1, help="internal: this process is worker N")
    a = parser.parse_args()
    if a.first + a.tables > 10_000:
        raise SystemExit("tables from 10,000 up are held out and are never taught on")
    if a.worker >= 0:
        work(a.first, a.tables, a.out, a.worker, a.candidates)
        return
    share = math.ceil(a.tables / a.workers)
    children = []
    for w in range(a.workers):
        first = a.first + w * share
        count = min(share, a.first + a.tables - first)
        if count <= 0:
            continue
        part = a.out.with_suffix(f".part{w}.jsonl")
        command = [sys.executable, __file__, "--first", str(first), "--tables", str(count)]
        command += ["--out", str(part), "--worker", str(w), "--candidates", str(a.candidates)]
        children.append((part, subprocess.Popen(command)))
    with open(a.out, "w") as handle:
        for part, child in children:
            child.wait()
            if part.exists():
                handle.write(part.read_text())
                part.unlink()
    print("wrote", a.out, len(a.out.read_text().splitlines()), "lessons")


if __name__ == "__main__":
    main()
