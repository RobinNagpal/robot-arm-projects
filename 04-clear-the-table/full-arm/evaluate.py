"""Score a solution on the held-out tables, the way problem 4 scores one.

``python evaluate.py SOLUTION --tables 20 --runs 1``

Every solution is shown the same ordered list of tables from 10,000 up, given the
same fifteen arm minutes for the whole list, and gets as far down it as it gets.
A solution is handed an arm with a wrist camera and a clock (``examiner.py``), and
what it sees is the pictures it chooses to take. Nothing from the simulator reaches it.
"""

from __future__ import annotations

import argparse
import importlib
import json
import time
from pathlib import Path

import arm_camera  # noqa: F401
import examiner
from examiner import ARM_BUDGET
from moveit_link import MoveItLink

RESULTS = Path(__file__).resolve().parent / "results"

SOLUTIONS = {
    "geometry": ("geometry", "Geometry"),
    "imitation": ("imitation", "Imitation"),
    "world-model": ("world_model", "PlanningSolution"),
    "reinforcement": ("reinforcement", "Learner"),
    "vla": ("vla", "FineTuned"),
    "imitation-checked": ("checked", "imitation"),
    "reinforcement-checked": ("checked", "reinforcement"),
    "vla-checked": ("checked", "vla"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("solution", choices=sorted(SOLUTIONS))
    parser.add_argument("--first", type=int, default=10_000)
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--budget", type=float, default=ARM_BUDGET)
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="KEY=VALUE set on the solution, for tuning on training tables",
    )
    arguments = parser.parse_args()

    module, cls = SOLUTIONS[arguments.solution]
    factory = getattr(importlib.import_module(module), cls)

    def build():
        solution = factory(arguments.weights) if arguments.weights else factory()
        for item in arguments.param:
            key, value = item.split("=")
            setattr(solution, key, int(value) if value.lstrip("-").isdigit() else float(value))
        return solution

    started = time.perf_counter()
    with MoveItLink() as link:
        summary, tally, rows = examiner.judge(
            build, link, arguments.first, arguments.tables, arguments.runs, arguments.budget
        )
    print(arguments.solution, "|", examiner.headline(summary))
    print(tally)
    RESULTS.mkdir(exist_ok=True)
    name = arguments.name or f"{arguments.solution}-{arguments.first}-{arguments.tables}x{arguments.runs}"
    (RESULTS / f"{name}.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "tables": rows,
                "tally": tally.__dict__,
                "wall_seconds": round(time.perf_counter() - started),
            },
            indent=1,
            default=str,
        )
    )
    print("wrote", RESULTS / f"{name}.json")


if __name__ == "__main__":
    main()
