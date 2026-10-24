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

from examiner.motion.moveit_connection import MoveItConnection
from examiner.tools import ceiling_search

ARM_SECONDS_PER_TABLE = (
    120.0  # arm seconds one table may take; the search's answers are capped at ten as well
)


def collect_lessons_as_worker(
    first_table: int, table_count: int, output_file: Path, worker_number: int, tries_per_turn: int
) -> None:
    rng = random.Random(first_table * 1013 + worker_number)
    started = time.perf_counter()
    lessons_written = 0
    with MoveItConnection(ros_domain=worker_number) as moveit, open(output_file, "w") as output:
        for seed in range(first_table, first_table + table_count):
            lessons: list = []
            try:
                ceiling_search.clear_table_by_trying_pushes(
                    seed, moveit, ARM_SECONDS_PER_TABLE, tries_per_turn, rng, lessons=lessons
                )
            except Exception as error:  # one bad table is skipped, not the whole run
                print(f"[{worker_number}] table {seed} failed: {error}", flush=True)
                continue
            for lesson in lessons:
                output.write(json.dumps(lesson) + "\n")
            output.flush()
            lessons_written += len(lessons)
            if (seed - first_table + 1) % 5 == 0:
                print(
                    f"[{worker_number}] {seed - first_table + 1}/{table_count} tables, "
                    f"{lessons_written} lessons, "
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
    arguments = parser.parse_args()
    if arguments.first + arguments.tables > 10_000:
        raise SystemExit("tables from 10,000 up are held out and are never taught on")
    if arguments.worker >= 0:
        collect_lessons_as_worker(
            arguments.first, arguments.tables, arguments.out, arguments.worker, arguments.candidates
        )
        return
    tables_per_worker = math.ceil(arguments.tables / arguments.workers)
    workers = []
    for worker_number in range(arguments.workers):
        first_table = arguments.first + worker_number * tables_per_worker
        table_count = min(tables_per_worker, arguments.first + arguments.tables - first_table)
        if table_count <= 0:
            continue
        part_file = arguments.out.with_suffix(f".part{worker_number}.jsonl")
        command = [sys.executable, __file__, "--first", str(first_table), "--tables", str(table_count)]
        command += [
            "--out",
            str(part_file),
            "--worker",
            str(worker_number),
            "--candidates",
            str(arguments.candidates),
        ]
        workers.append((part_file, subprocess.Popen(command)))
    with open(arguments.out, "w") as output:
        for part_file, process in workers:
            process.wait()
            if part_file.exists():
                output.write(part_file.read_text())
                part_file.unlink()
    print("wrote", arguments.out, len(arguments.out.read_text().splitlines()), "lessons")


if __name__ == "__main__":
    main()
