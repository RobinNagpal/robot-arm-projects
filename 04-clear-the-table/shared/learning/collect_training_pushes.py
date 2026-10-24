"""Push glasses at random with the full arm, and write down exactly what happened.

``python collect_training_pushes.py --first 0 --tables 40 --out data/pushes-a.jsonl [--workers 4]``

This is the experience the learned solutions are built from. Each record is one
push that MoveIt was asked to make: the layout before it, the request (which
glass, which way, how far, and the settings given to MoveIt), whether MoveIt could
plan it, and if it could, what the physics did -- where every glass ended up, which
leaned over, how long the arm took, how hard the hand pushed -- and how many glasses
the table could be picked from before and after.

**The pushes are random on purpose, and not wildly so.** A solution that learns
from a teacher learns the teacher's habits, and the point of these records is to
show what the cell really does, including the settings nobody would choose. Half
the headings point away from the nearest neighbour, because a push towards one is
almost never worth anything and a dataset made only of those teaches little. The
rest are uniform. Settings are drawn across the whole range a learned model is
allowed to choose from.

**A table is pushed up to four times in a row, so layouts are the ones a real
run meets** -- tables with a glass already moved -- and not only tables as drawn.
A table stops when a glass goes over.
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

import numpy as np

from examiner.examining import one_table_cell
from examiner.examining.table_scoring import glass_is_pickable
from examiner.motion.moveit_connection import MoveItConnection
from examiner.motion.push_motions import GlassBox, MoveItSettings, PushRequest
from examiner.simulation.taken_from_problem_3 import STANDING_TILT_DEG, has_room
from shared.learning import table_and_push_encoding
from shared.learning.table_and_push_encoding import SETTING_RANGES, TRAVEL_RANGE

PUSHES_PER_TABLE = 4


def draw_random_settings(rng: random.Random) -> MoveItSettings:
    lowest, highest = SETTING_RANGES["stroke_speed"]
    return MoveItSettings(
        push_height=rng.uniform(*SETTING_RANGES["push_height"]),
        stroke_speed=math.exp(rng.uniform(math.log(lowest), math.log(highest))),
        approach_speed=rng.uniform(*SETTING_RANGES["approach_speed"]),
        padding=rng.uniform(*SETTING_RANGES["padding"]),
        standoff=rng.uniform(*SETTING_RANGES["standoff"]),
        overreach=rng.uniform(*SETTING_RANGES["overreach"]),
    )


def true_layout(simulator) -> list[dict]:
    """Every glass on the table as the simulator knows it. Never shown to a solution; it is the record."""
    layout = []
    for i, glass in enumerate(simulator.glasses):
        x, y = simulator.position(i)
        outline = glass.outline
        layout.append(
            {
                "x": float(x),
                "y": float(y),
                "radius": float(outline.max_diameter / 2),
                "height": float(outline.total_height),
                "foot": float(outline.radius[0]),
                "tilt": float(simulator.tilt(i)),
                "pickable": bool(glass_is_pickable(simulator, i)),
                "kind": glass.kind,
            }
        )
    return layout


def draw_random_push(rng: random.Random, simulator) -> tuple[PushRequest, list[GlassBox]]:
    layout = true_layout(simulator)
    boxes = [GlassBox(row["x"], row["y"], row["radius"], row["height"], row["foot"]) for row in layout]
    crowded = [i for i, row in enumerate(layout) if not row["pickable"]]
    glass = rng.choice(crowded) if crowded and rng.random() < 0.7 else rng.randrange(len(layout))
    if rng.random() < 0.5 and len(layout) > 1:
        # Away from the nearest neighbour, with a spread.
        this_glass = np.array([layout[glass]["x"], layout[glass]["y"]])
        other_glasses = [np.array([row["x"], row["y"]]) for j, row in enumerate(layout) if j != glass]
        nearest = min(other_glasses, key=lambda point: np.linalg.norm(point - this_glass))
        away_from_neighbour = this_glass - nearest
        heading = math.atan2(away_from_neighbour[1], away_from_neighbour[0]) + rng.gauss(0.0, 0.5)
    else:
        heading = rng.uniform(-math.pi, math.pi)
    heading = (heading + math.pi) % (2 * math.pi) - math.pi
    travel = rng.uniform(*TRAVEL_RANGE)
    # Most pushes are proposed only if the hand's own shape fits between the
    # glasses. Drawn blindly, nine pushes in ten were refused by MoveIt before
    # the arm moved, which teaches little about everything that happens after.
    # One in five is left unfiltered, so the models also see what a hopeless
    # push looks like.
    if rng.random() < 0.8:
        for _ in range(60):
            if table_and_push_encoding.hand_fits_along_push(boxes, glass, heading, travel):
                break
            glass = rng.choice(crowded) if crowded and rng.random() < 0.7 else rng.randrange(len(layout))
            heading = rng.uniform(-math.pi, math.pi)
            travel = rng.uniform(*TRAVEL_RANGE)
    return PushRequest(glass, heading, travel, draw_random_settings(rng)), boxes


def push_guided_by_world_model(rng: random.Random, boxes: list[GlassBox], world_model) -> PushRequest | None:
    """The push the world model likes best, shaken a little, or None if it likes none.

    Pushes drawn at random are mostly wasted: nine in ten fail and only one in
    twenty frees a glass. A model fitted on them knows where *not* to push but
    has seen few good pushes to learn what makes one. So a share of the next
    round is drawn from the model's own best guesses, which both yields more good
    pushes and puts the model's mistakes -- pushes it was sure of that went wrong
    -- into the data it learns from next.
    """
    glasses_allowed = [k for k in range(len(boxes)) if k < table_and_push_encoding.GLASS_SLOTS]
    if table_and_push_encoding.count_pickable_boxes(boxes) == len(boxes) or not glasses_allowed:
        return None
    score, glass, numbers = world_model.search_for_best_push(boxes, glasses_allowed)
    if score <= getattr(world_model, "LEAST_WORTHWHILE_SCORE", 0.0):
        return None
    numbers = numbers.copy()
    angle = math.atan2(numbers[1], numbers[0]) + rng.gauss(0.0, 0.15)
    numbers[0], numbers[1] = math.cos(angle), math.sin(angle)
    numbers[2:] = np.clip(
        numbers[2:] + np.array([rng.gauss(0.0, 0.06) for _ in range(len(numbers) - 2)]), 0.0, 1.0
    )
    return table_and_push_encoding.decode_push(glass, numbers)


def push_that_would_free_a_glass(
    rng: random.Random, boxes: list[GlassBox], tries: int = 400
) -> PushRequest | None:
    """A push that, if it went as asked, would give a crowded glass room, with settings drawn at random.

    Round one found that one random push in twenty-eight freed a glass, which
    is too few to learn what a good push is from. This draws a glass that is
    short of room, a heading and a distance, and keeps the draw only if the hand
    fits between the glasses on the way (``hand_fits_along_push``) and the glass would end
    with room (``has_room``) -- problem 3's own two tests of a push. It says
    nothing about the arm, or about whether the glass tips, or about MoveIt: those
    are what the pushes are made to find out. The settings are as random as ever.
    """
    crowded = [
        glass
        for glass in range(len(boxes))
        if table_and_push_encoding.room_shortfall_of_glass(boxes, glass) > 0
    ]
    if not crowded:
        return None
    for _ in range(tries):
        glass = rng.choice(crowded)
        heading = rng.uniform(-math.pi, math.pi)
        travel = rng.uniform(0.03, 0.12)
        if not table_and_push_encoding.hand_fits_along_push(boxes, glass, heading, travel):
            continue
        box = boxes[glass]
        end = (box.x + travel * math.cos(heading), box.y + travel * math.sin(heading))
        if has_room(
            *end,
            [
                (other.x, other.y, 2 * other.radius)
                for other_index, other in enumerate(boxes)
                if other_index != glass
            ],
            0.005,
        ):
            return PushRequest(glass, heading, travel, draw_random_settings(rng))
    return None


def push_one_table_at_random(
    seed: int,
    moveit: MoveItConnection,
    rng: random.Random,
    world_model=None,
    guided_share: float = 0.0,
    informed_share: float = 0.0,
) -> list[dict]:
    cell = one_table_cell.OneTableCell(seed, moveit, with_wrist_camera=False)
    records = []
    try:
        for push_number in range(PUSHES_PER_TABLE):
            request, boxes = draw_random_push(rng, cell.simulator)
            drawn_how = "random"
            if informed_share and rng.random() < informed_share:
                drawn = push_that_would_free_a_glass(rng, boxes)
                if drawn is not None:
                    request, drawn_how = drawn, "informed"
            elif world_model is not None and rng.random() < guided_share:
                drawn = push_guided_by_world_model(rng, boxes, world_model)
                if drawn is not None:
                    request, drawn_how = drawn, "guided"
            layout_before = true_layout(cell.simulator)
            arm_seconds_before = cell.arm_seconds
            pusher_result = cell.push_glass(boxes, request)
            layout_after = true_layout(cell.simulator)
            records.append(
                {
                    "seed": seed,
                    "step": push_number,
                    "how": drawn_how,
                    "before": layout_before,
                    "request": {
                        "glass": request.glass,
                        "heading": request.heading,
                        "travel": request.travel,
                        "settings": request.settings.__dict__,
                    },
                    "feasible": pusher_result.made,
                    "why": pusher_result.refusal_reason,
                    "after": layout_after if pusher_result.made else layout_before,
                    "arm_seconds": cell.arm_seconds - arm_seconds_before,
                    "peak_force": pusher_result.peak_force if pusher_result.made else 0.0,
                    "touched": bool(pusher_result.hand_touched_a_glass),
                    "toppled": sum(g["tilt"] >= STANDING_TILT_DEG for g in layout_after)
                    if pusher_result.made
                    else 0,
                    "stages": pusher_result.motion_stages if pusher_result.made else [],
                }
            )
            if pusher_result.made and records[-1]["toppled"]:
                break
    finally:
        cell.close()
    return records


def collect_pushes_as_worker(
    first_table: int,
    table_count: int,
    output_file: Path,
    worker_number: int,
    world_model_weights: Path | None = None,
    guided_share: float = 0.0,
    informed_share: float = 0.0,
) -> None:
    rng = random.Random(first_table * 1009 + worker_number)
    world_model = None
    if world_model_weights is not None:
        import torch

        torch.set_num_threads(1)
        from world_model import WorldModelSolution

        world_model = WorldModelSolution(world_model_weights, seed=first_table * 7 + worker_number)
    started = time.perf_counter()
    pushes_written = pushes_feasible = 0
    with MoveItConnection(ros_domain=worker_number) as moveit, open(output_file, "w") as output:
        for seed in range(first_table, first_table + table_count):
            for record in push_one_table_at_random(
                seed, moveit, rng, world_model, guided_share, informed_share
            ):
                output.write(json.dumps(record) + "\n")
                pushes_written += 1
                pushes_feasible += record["feasible"]
            output.flush()
            if (seed - first_table + 1) % 10 == 0:
                print(
                    f"[{worker_number}] {seed - first_table + 1}/{table_count} tables, "
                    f"{pushes_written} pushes ({pushes_feasible} feasible), "
                    f"{time.perf_counter() - started:.0f} s",
                    flush=True,
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--tables", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker", type=int, default=-1, help="internal: this process is worker N")
    parser.add_argument(
        "--guide", type=Path, default=None, help="world-model weights to draw some pushes from"
    )
    parser.add_argument("--guided-share", type=float, default=0.5)
    parser.add_argument(
        "--informed-share",
        type=float,
        default=0.0,
        help="share of pushes drawn so that, as asked, they would free a glass",
    )
    arguments = parser.parse_args()
    if arguments.worker >= 0:
        collect_pushes_as_worker(
            arguments.first,
            arguments.tables,
            arguments.out,
            arguments.worker,
            arguments.guide,
            arguments.guided_share,
            arguments.informed_share,
        )
        return
    tables_per_worker = math.ceil(arguments.tables / arguments.workers)
    running_workers = []
    for worker_number in range(arguments.workers):
        first_table = arguments.first + worker_number * tables_per_worker
        table_count = min(tables_per_worker, arguments.first + arguments.tables - first_table)
        if table_count <= 0:
            continue
        part_file = arguments.out.with_suffix(f".part{worker_number}.jsonl")
        extra_arguments = (
            ["--guide", str(arguments.guide), "--guided-share", str(arguments.guided_share)]
            if arguments.guide
            else []
        )
        extra_arguments += ["--informed-share", str(arguments.informed_share)]
        running_workers.append(
            (
                part_file,
                subprocess.Popen(
                    [
                        sys.executable,
                        __file__,
                        "--first",
                        str(first_table),
                        "--tables",
                        str(table_count),
                        "--out",
                        str(part_file),
                        "--worker",
                        str(worker_number),
                        *extra_arguments,
                    ]
                ),
            )
        )
    for _, process in running_workers:
        process.wait()
    with open(arguments.out, "w") as output:
        for part_file, _ in running_workers:
            output.write(part_file.read_text())
            part_file.unlink()
    print("wrote", arguments.out)


if __name__ == "__main__":
    main()
