"""Score a solution on the held-out tables, the way problem 4 scores one.

``python evaluate_solution.py SOLUTION --tables 20 --runs 1``

Every solution is shown the same ordered list of tables from 10,000 up, given the
same fifteen arm minutes for the whole list, and gets as far down it as it gets.
A solution is handed an arm with a wrist camera and a clock (``table_examiner.py``), and
what it sees is the pictures it chooses to take. Nothing from the simulator reaches it.
"""

from __future__ import annotations

import argparse
import importlib
import json
import time
from pathlib import Path

from examiner.examining import table_examiner
from examiner.examining.table_examiner import ARM_SECONDS_FOR_TABLE_LIST
from examiner.motion.moveit_connection import MoveItConnection

RESULTS_FOLDER = Path(__file__).resolve().parents[1] / "results"

SOLUTIONS = {
    "geometry": ("geometry_reference", "GeometryReference"),
    "geometry-ranked": ("geometry_ranked", "GeometryRanked"),
    "imitation": ("imitation", "ImitationSolution"),
    "world-model": ("world_model", "WorldModelSolution"),
    "reinforcement": ("reinforcement_learning", "ReinforcementLearningSolution"),
    "vla": ("smolvla_fine_tuned", "SmolVLASolution"),
    "imitation-checked": ("safety_check", "checked_imitation"),
    "reinforcement-checked": ("safety_check", "checked_reinforcement_learning"),
    "vla-checked": ("safety_check", "checked_smolvla"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("solution", choices=sorted(SOLUTIONS))
    parser.add_argument("--first", type=int, default=10_000)
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--budget", type=float, default=ARM_SECONDS_FOR_TABLE_LIST)
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="KEY=VALUE set on the solution, for tuning on training tables",
    )
    arguments = parser.parse_args()

    module_name, factory_name = SOLUTIONS[arguments.solution]
    make_solution = getattr(importlib.import_module(module_name), factory_name)

    def build_solution():
        solution = make_solution(arguments.weights) if arguments.weights else make_solution()
        for setting in arguments.param:
            attribute, value = setting.split("=")
            setattr(solution, attribute, int(value) if value.lstrip("-").isdigit() else float(value))
        return solution

    started = time.perf_counter()
    with MoveItConnection() as moveit:
        summary, arm_activity, rows_per_run = table_examiner.score_solution_on_tables(
            build_solution, moveit, arguments.first, arguments.tables, arguments.runs, arguments.budget
        )
    print(arguments.solution, "|", table_examiner.one_line_summary(summary))
    print(arm_activity)
    RESULTS_FOLDER.mkdir(exist_ok=True)
    name = arguments.name or f"{arguments.solution}-{arguments.first}-{arguments.tables}x{arguments.runs}"
    (RESULTS_FOLDER / f"{name}.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "tables": rows_per_run,
                "arm_activity": arm_activity.__dict__,
                "wall_seconds": round(time.perf_counter() - started),
            },
            indent=1,
            default=str,
        )
    )
    print("wrote", RESULTS_FOLDER / f"{name}.json")


if __name__ == "__main__":
    main()
