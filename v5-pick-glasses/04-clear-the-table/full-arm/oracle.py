"""A ceiling: what a search that is allowed to *try every push in the simulator first* can reach.

``python oracle.py --first 10000 --tables 20 --candidates 30``

No learned solution can do this, and it is not a solution: it works on the simulator itself, not
through the arm a solution is given. At every turn it draws ``candidates`` pushes, makes each
one in the physics from the table as it stands, scores what each one left, puts the table
back, and then makes the best of them for real. It is told the glasses' true boxes, so it
does not read a picture. It is marked by the same scorecard, on the same tables, with the
same arm time, which is charged for the push it really makes and not for the ones it tried.

It is a ceiling only for this search: thirty tries a turn, drawn the way ``collect_pushes``
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

import arm_camera  # noqa: F401
import cell as C
import collect_pushes as CP
import features as F
import mujoco
from arm_contract import FINISHED, GLASS_OVER, OUT_OF_TIME, TableResult
from examiner import ARM_BUDGET, scored
from moveit_link import MoveItLink
from pusher import Box

from scoring import Repeats


def snapshot(bench):
    return copy.deepcopy(bench.data)


def restore(bench, data) -> None:
    mujoco.mj_copyData(bench.data, bench.model, data)
    mujoco.mj_forward(bench.model, bench.data)


def worth(before: list[Box], after: list[Box], topple: bool, seconds: float) -> float:
    """What one try is worth: glasses made pickable, room gained, and a heavy charge for a topple."""
    value = (
        F.pickable_count(after)
        - F.pickable_count(before)
        + 0.5 * 100 * (F.shortfall(before) - F.shortfall(after))
    )
    return value - (5.0 if topple else 0.0) - 0.01 * seconds


def truth(cell) -> list[Box]:
    bench = cell.bench
    out = []
    for i, glass in enumerate(bench.glasses):
        x, y = bench.position(i)
        o = glass.outline
        out.append(
            Box(float(x), float(y), float(o.max_diameter / 2), float(o.total_height), float(o.radius[0]))
        )
    return out


def clear_table(
    seed: int,
    link: MoveItLink,
    seconds_left: float,
    candidates: int,
    rng: random.Random,
    chosen: list | None = None,
    lessons: list | None = None,
    *,
    cell: C.ArmCell | None = None,
) -> TableResult:
    """Clear one table by trying pushes first. ``lessons``, when given, gets one row per turn:
    the table as it stood and the push made, or ``None`` where the search chose to stop."""
    cell = C.ArmCell(seed, link, camera=False) if cell is None else cell
    started = time.perf_counter()
    ended, answers = OUT_OF_TIME, 0
    try:
        while True:
            left = seconds_left - cell.arm_seconds
            if left < 8.0 or answers >= 10:
                break
            boxes = truth(cell)
            before = CP.layout(cell.bench)
            if F.pickable_count(boxes) == len(boxes):
                ended = FINISHED
                if lessons is not None:
                    lessons.append({"seed": seed, "step": answers, "before": before, "request": None})
                break
            state = snapshot(cell.bench)
            was_seconds, was_total = cell.bench.arm_seconds, cell.bench.seconds
            best = None
            for _ in range(candidates):
                request = CP.informed_request(rng, boxes) if rng.random() < 0.8 else None
                if request is None:
                    request, _boxes = CP.draw_request(rng, cell.bench)
                result = cell.pusher.push(boxes, request, left)
                if result.ok:
                    after = truth(cell)
                    value = worth(boxes, after, cell.toppled() > 0, cell.bench.arm_seconds - was_seconds)
                    if best is None or value > best[0]:
                        best = (value, request)
                restore(cell.bench, state)
                cell.bench.arm_seconds, cell.bench.seconds = was_seconds, was_total
            answers += 1
            if best is None or best[0] <= 0.0:
                ended = FINISHED
                if lessons is not None:
                    lessons.append({"seed": seed, "step": answers - 1, "before": before, "request": None})
                break
            cell.pusher.push(boxes, best[1], left)
            if lessons is not None:
                q = best[1]
                lessons.append(
                    {
                        "seed": seed,
                        "step": answers - 1,
                        "before": before,
                        "request": {
                            "glass": q.glass,
                            "heading": q.heading,
                            "travel": q.travel,
                            "settings": q.settings.__dict__,
                        },
                        "worth": best[0],
                        "toppled": int(cell.toppled()),
                    }
                )
            if chosen is not None:
                request = best[1]
                chosen.append(
                    {
                        "seed": seed,
                        "glass": request.glass,
                        "kind": cell.bench.glasses[request.glass].kind,
                        "heading": request.heading,
                        "travel": request.travel,
                        "settings": request.settings.__dict__,
                        "worth": best[0],
                    }
                )
            if cell.toppled():
                ended = GLASS_OVER
                break
        return TableResult(
            table=seed,
            glasses=cell.glasses(),
            separated_at_start=cell.pickable_at_start,
            separated_at_end=cell.pickable(),
            fell_over=cell.toppled(),
            ended_by=ended,
            arm_seconds=cell.arm_seconds,
            pushes_asked=answers,
            thinking_seconds=time.perf_counter() - started,
        )
    finally:
        cell.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, default=10_000)
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--budget", type=float, default=ARM_BUDGET)
    parser.add_argument("--name", default="oracle")
    a = parser.parse_args()
    rng = random.Random(a.first)
    card = Repeats().run()
    spent = 0.0
    chosen: list = []
    with MoveItLink() as link:
        for seed in range(a.first, a.first + a.tables):
            if ARM_BUDGET - spent < 8.0:
                break
            result = clear_table(seed, link, a.budget - spent, a.candidates, rng, chosen)
            spent += result.arm_seconds
            card.table(scored(result))
            print(
                f"table {seed}: {result.separated_at_start}->{result.separated_at_end}/{result.glasses}, "
                f"{result.arm_seconds:.0f} arm s, {result.ended_by}, broken {result.fell_over}",
                flush=True,
            )
    out = Path(__file__).resolve().parent / "results" / f"{a.name}.json"
    out.write_text(json.dumps({"summary": {"runs": 1}, "tables": [card.tables], "chosen": chosen}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
