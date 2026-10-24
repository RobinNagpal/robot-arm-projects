"""A ceiling: what a search that is allowed to *try every push in the simulator first* can reach.

``python ceiling_search.py --first 10000 --tables 20 --candidates 30``

No learned solution can do this, and it is not a solution: it works on the simulator itself, not
through the arm a solution is given. At every turn it draws ``--candidates`` pushes, makes each
one in the physics from the table as it stands, scores what each one left, puts the table
back, and then makes the best of them for real. It is told the glasses' true boxes, so it
does not read a picture. It is marked by the same scorecard, on the same tables, with the
same arm time, which is charged for the push it really makes and not for the ones it tried.

It is a ceiling only for this search: thirty tries a turn, drawn the way ``collect_training_pushes``
draws its informed pushes. A better search would reach more. What it says is how much
there was to find, which is the number to read the learned solutions against.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import time
from pathlib import Path

import mujoco

from examiner.examining import one_table_cell
from examiner.examining.solution_contract import FINISHED, GLASS_OVER, OUT_OF_TIME, TableResult
from examiner.examining.table_examiner import ARM_SECONDS_FOR_TABLE_LIST, as_scored_table
from examiner.examining.table_scoring import ScorecardsOverRuns
from examiner.motion.moveit_connection import MoveItConnection
from examiner.motion.push_motions import GlassBox
from shared.learning import collect_training_pushes, table_and_push_encoding


def save_physics_state(simulator):
    return copy.deepcopy(simulator.data)


def restore_physics_state(simulator, saved_data) -> None:
    mujoco.mj_copyData(simulator.data, simulator.model, saved_data)
    mujoco.mj_forward(simulator.model, simulator.data)


def value_of_try(before: list[GlassBox], after: list[GlassBox], toppled: bool, arm_seconds: float) -> float:
    """What one try is worth: glasses made pickable, room gained, and a heavy charge for a topple."""
    glasses_freed = table_and_push_encoding.count_pickable_boxes(
        after
    ) - table_and_push_encoding.count_pickable_boxes(before)
    room_gained = table_and_push_encoding.total_room_shortfall(
        before
    ) - table_and_push_encoding.total_room_shortfall(after)
    value = glasses_freed + 0.5 * 100 * room_gained
    return value - (5.0 if toppled else 0.0) - 0.01 * arm_seconds


def true_boxes(cell) -> list[GlassBox]:
    simulator = cell.simulator
    boxes = []
    for i, glass in enumerate(simulator.glasses):
        x, y = simulator.position(i)
        outline = glass.outline
        boxes.append(
            GlassBox(
                float(x),
                float(y),
                float(outline.max_diameter / 2),
                float(outline.total_height),
                float(outline.radius[0]),
            )
        )
    return boxes


def push_as_record(request) -> dict:
    return {
        "glass": request.glass,
        "heading": request.heading,
        "travel": request.travel,
        "settings": request.settings.__dict__,
    }


def clear_table_by_trying_pushes(
    seed: int,
    moveit: MoveItConnection,
    arm_seconds_given: float,
    tries_per_turn: int,
    rng: random.Random,
    pushes_made: list | None = None,
    lessons: list | None = None,
    *,
    cell: one_table_cell.OneTableCell | None = None,
) -> TableResult:
    """Clear one table by trying pushes first.

    ``pushes_made``, when given, gets one row for every push the search really makes.
    ``lessons``, when given, gets one row per turn: the table as it stood and the push made,
    or ``None`` where the search chose to stop.
    """
    cell = one_table_cell.OneTableCell(seed, moveit, with_wrist_camera=False) if cell is None else cell
    started = time.perf_counter()
    ended_by, pushes_requested = OUT_OF_TIME, 0
    try:
        while True:
            arm_seconds_left = arm_seconds_given - cell.arm_seconds
            if arm_seconds_left < 8.0 or pushes_requested >= 10:
                break
            boxes = true_boxes(cell)
            layout_before = collect_training_pushes.true_layout(cell.simulator)
            if table_and_push_encoding.count_pickable_boxes(boxes) == len(boxes):
                ended_by = FINISHED
                if lessons is not None:
                    lessons.append(
                        {"seed": seed, "step": pushes_requested, "before": layout_before, "request": None}
                    )
                break
            saved_physics = save_physics_state(cell.simulator)
            arm_seconds_before, simulator_seconds_before = cell.simulator.arm_seconds, cell.simulator.seconds
            best = None  # (value, push) of the best try so far
            for _ in range(tries_per_turn):
                request = (
                    collect_training_pushes.push_that_would_free_a_glass(rng, boxes)
                    if rng.random() < 0.8
                    else None
                )
                if request is None:
                    request, _boxes = collect_training_pushes.draw_random_push(rng, cell.simulator)
                pusher_result = cell.pusher.plan_and_make_push(boxes, request, arm_seconds_left)
                if pusher_result.made:
                    value = value_of_try(
                        boxes,
                        true_boxes(cell),
                        cell.count_toppled_glasses() > 0,
                        cell.simulator.arm_seconds - arm_seconds_before,
                    )
                    if best is None or value > best[0]:
                        best = (value, request)
                restore_physics_state(cell.simulator, saved_physics)
                cell.simulator.arm_seconds, cell.simulator.seconds = (
                    arm_seconds_before,
                    simulator_seconds_before,
                )
            pushes_requested += 1
            if best is None or best[0] <= 0.0:
                ended_by = FINISHED
                if lessons is not None:
                    lessons.append(
                        {"seed": seed, "step": pushes_requested - 1, "before": layout_before, "request": None}
                    )
                break
            best_value, best_push = best
            cell.pusher.plan_and_make_push(boxes, best_push, arm_seconds_left)
            if lessons is not None:
                lessons.append(
                    {
                        "seed": seed,
                        "step": pushes_requested - 1,
                        "before": layout_before,
                        "request": push_as_record(best_push),
                        "worth": best_value,
                        "toppled": int(cell.count_toppled_glasses()),
                    }
                )
            if pushes_made is not None:
                pushes_made.append(
                    {
                        "seed": seed,
                        "glass": best_push.glass,
                        "kind": cell.simulator.glasses[best_push.glass].kind,
                        "heading": best_push.heading,
                        "travel": best_push.travel,
                        "settings": best_push.settings.__dict__,
                        "worth": best_value,
                    }
                )
            if cell.count_toppled_glasses():
                ended_by = GLASS_OVER
                break
        return TableResult(
            table_number=seed,
            glass_count=cell.glass_count(),
            pickable_at_start=cell.pickable_at_start,
            pickable_at_end=cell.pickable_glass_count(),
            glasses_toppled=cell.count_toppled_glasses(),
            ended_by=ended_by,
            arm_seconds=cell.arm_seconds,
            pushes_requested=pushes_requested,
            thinking_seconds=time.perf_counter() - started,
        )
    finally:
        cell.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, default=10_000)
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--budget", type=float, default=ARM_SECONDS_FOR_TABLE_LIST)
    parser.add_argument("--name", default="ceiling")
    arguments = parser.parse_args()
    rng = random.Random(arguments.first)
    scorecard = ScorecardsOverRuns().new_scorecard()
    arm_seconds_spent = 0.0
    pushes_made: list = []
    with MoveItConnection() as moveit:
        for seed in range(arguments.first, arguments.first + arguments.tables):
            if ARM_SECONDS_FOR_TABLE_LIST - arm_seconds_spent < 8.0:
                break
            result = clear_table_by_trying_pushes(
                seed, moveit, arguments.budget - arm_seconds_spent, arguments.candidates, rng, pushes_made
            )
            arm_seconds_spent += result.arm_seconds
            scorecard.add_table(as_scored_table(result))
            print(
                f"table {seed}: {result.pickable_at_start}->{result.pickable_at_end}/{result.glass_count}, "
                f"{result.arm_seconds:.0f} arm s, {result.ended_by}, broken {result.glasses_toppled}",
                flush=True,
            )
    out = Path(__file__).resolve().parents[1] / "results" / f"{arguments.name}.json"
    out.write_text(
        json.dumps(
            {"summary": {"runs": 1}, "tables": [scorecard.rows_per_table], "chosen": pushes_made}, indent=1
        )
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
