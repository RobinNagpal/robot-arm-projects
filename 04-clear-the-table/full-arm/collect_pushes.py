"""Push glasses at random with the full arm, and write down exactly what happened.

``python collect_pushes.py --first 0 --tables 40 --out data/pushes-a.jsonl [--workers 4]``

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

import cell as C
import features as F
import numpy as np
from features import RANGES, TRAVEL
from moveit_link import MoveItLink
from pusher import Box, Request, Settings

from partners import STANDING_TILT_DEG, has_room
from scoring import pickable

PUSHES_PER_TABLE = 4


def draw_settings(rng: random.Random) -> Settings:
    lo, hi = RANGES["stroke_speed"]
    return Settings(
        push_height=rng.uniform(*RANGES["push_height"]),
        stroke_speed=math.exp(rng.uniform(math.log(lo), math.log(hi))),
        approach_speed=rng.uniform(*RANGES["approach_speed"]),
        padding=rng.uniform(*RANGES["padding"]),
        standoff=rng.uniform(*RANGES["standoff"]),
        overreach=rng.uniform(*RANGES["overreach"]),
    )


def layout(bench) -> list[dict]:
    """Every glass on the table as the simulator knows it. Never shown to a solution; it is the record."""
    rows = []
    for i, glass in enumerate(bench.glasses):
        x, y = bench.position(i)
        outline = glass.outline
        rows.append(
            {
                "x": float(x),
                "y": float(y),
                "radius": float(outline.max_diameter / 2),
                "height": float(outline.total_height),
                "foot": float(outline.radius[0]),
                "tilt": float(bench.tilt(i)),
                "pickable": bool(pickable(bench, i)),
                "kind": glass.kind,
            }
        )
    return rows


def draw_request(rng: random.Random, bench) -> tuple[Request, list[Box]]:
    state = layout(bench)
    boxes = [Box(g["x"], g["y"], g["radius"], g["height"], g["foot"]) for g in state]
    crowded = [i for i, g in enumerate(state) if not g["pickable"]]
    k = rng.choice(crowded) if crowded and rng.random() < 0.7 else rng.randrange(len(state))
    if rng.random() < 0.5 and len(state) > 1:
        # Away from the nearest neighbour, with a spread.
        here = np.array([state[k]["x"], state[k]["y"]])
        others = [np.array([g["x"], g["y"]]) for j, g in enumerate(state) if j != k]
        nearest = min(others, key=lambda p: np.linalg.norm(p - here))
        away = here - nearest
        heading = math.atan2(away[1], away[0]) + rng.gauss(0.0, 0.5)
    else:
        heading = rng.uniform(-math.pi, math.pi)
    heading = (heading + math.pi) % (2 * math.pi) - math.pi
    travel = rng.uniform(*TRAVEL)
    # Most pushes are proposed only if the hand's own shape fits between the
    # glasses. Drawn blindly, nine pushes in ten were refused by MoveIt before
    # the arm moved, which teaches little about everything that happens after.
    # One in five is left unfiltered, so the models also see what a hopeless
    # push looks like.
    if rng.random() < 0.8:
        for _ in range(60):
            if F.hand_clear(boxes, k, heading, travel):
                break
            k = rng.choice(crowded) if crowded and rng.random() < 0.7 else rng.randrange(len(state))
            heading = rng.uniform(-math.pi, math.pi)
            travel = rng.uniform(*TRAVEL)
    return Request(k, heading, travel, draw_settings(rng)), boxes


def guided_request(rng: random.Random, boxes: list[Box], guide) -> Request | None:
    """The push the world model likes best, shaken a little, or None if it likes none.

    Pushes drawn at random are mostly wasted: nine in ten fail and only one in
    twenty frees a glass. A model fitted on them knows where *not* to push but
    has seen few good pushes to learn what makes one. So a share of the next
    round is drawn from the model's own best guesses, which both yields more good
    pushes and puts the model's mistakes -- pushes it was sure of that went wrong
    -- into the data it learns from next.
    """
    usable = [k for k in range(len(boxes)) if k < F.SLOTS]
    if F.pickable_count(boxes) == len(boxes) or not usable:
        return None
    score, glass, vector = guide.search(boxes, usable)
    if score <= getattr(guide, "THRESHOLD", 0.0):
        return None
    vector = vector.copy()
    angle = math.atan2(vector[1], vector[0]) + rng.gauss(0.0, 0.15)
    vector[0], vector[1] = math.cos(angle), math.sin(angle)
    vector[2:] = np.clip(
        vector[2:] + np.array([rng.gauss(0.0, 0.06) for _ in range(len(vector) - 2)]), 0.0, 1.0
    )
    return F.request_from(glass, vector)


def informed_request(rng: random.Random, boxes: list[Box], tries: int = 400) -> Request | None:
    """A push that, if it went as asked, would give a crowded glass room, with settings drawn at random.

    Round one found that one random push in twenty-eight freed a glass, which
    is too few to learn what a good push is from. This draws a glass that is
    short of room, a heading and a distance, and keeps the draw only if the hand
    fits between the glasses on the way (``hand_clear``) and the glass would end
    with room (``has_room``) -- problem 3's own two tests of a push. It says
    nothing about the arm, or about whether the glass tips, or about MoveIt: those
    are what the pushes are made to find out. The settings are as random as ever.
    """
    crowded = [k for k in range(len(boxes)) if F.room_short(boxes, k) > 0]
    if not crowded:
        return None
    for _ in range(tries):
        k = rng.choice(crowded)
        heading = rng.uniform(-math.pi, math.pi)
        travel = rng.uniform(0.03, 0.12)
        if not F.hand_clear(boxes, k, heading, travel):
            continue
        g = boxes[k]
        end = (g.x + travel * math.cos(heading), g.y + travel * math.sin(heading))
        if has_room(*end, [(o.x, o.y, 2 * o.radius) for j, o in enumerate(boxes) if j != k], 0.005):
            return Request(k, heading, travel, draw_settings(rng))
    return None


def run_table(
    seed: int,
    link: MoveItLink,
    rng: random.Random,
    guide=None,
    guided_share: float = 0.0,
    informed_share: float = 0.0,
) -> list[dict]:
    cell = C.ArmCell(seed, link, camera=False)
    records = []
    try:
        for step in range(PUSHES_PER_TABLE):
            request, boxes = draw_request(rng, cell.bench)
            how = "random"
            if informed_share and rng.random() < informed_share:
                chosen = informed_request(rng, boxes)
                if chosen is not None:
                    request, how = chosen, "informed"
            elif guide is not None and rng.random() < guided_share:
                chosen = guided_request(rng, boxes, guide)
                if chosen is not None:
                    request, how = chosen, "guided"
            before = layout(cell.bench)
            seconds_before = cell.arm_seconds
            result = cell.push(boxes, request)
            after = layout(cell.bench)
            records.append(
                {
                    "seed": seed,
                    "step": step,
                    "how": how,
                    "before": before,
                    "request": {
                        "glass": request.glass,
                        "heading": request.heading,
                        "travel": request.travel,
                        "settings": request.settings.__dict__,
                    },
                    "feasible": result.ok,
                    "why": result.why,
                    "after": after if result.ok else before,
                    "arm_seconds": cell.arm_seconds - seconds_before,
                    "peak_force": result.peak_force if result.ok else 0.0,
                    "touched": bool(result.touched),
                    "toppled": sum(g["tilt"] >= STANDING_TILT_DEG for g in after) if result.ok else 0,
                    "stages": result.stages if result.ok else [],
                }
            )
            if result.ok and records[-1]["toppled"]:
                break
    finally:
        cell.close()
    return records


def work(
    first: int,
    tables: int,
    out: Path,
    worker: int,
    guide_weights: Path | None = None,
    guided_share: float = 0.0,
    informed_share: float = 0.0,
) -> None:
    rng = random.Random(first * 1009 + worker)
    guide = None
    if guide_weights is not None:
        import torch

        torch.set_num_threads(1)
        from world_model import PlanningSolution

        guide = PlanningSolution(guide_weights, seed=first * 7 + worker)
    started = time.perf_counter()
    done = feasible = 0
    with MoveItLink(domain=worker) as link, open(out, "w") as handle:
        for seed in range(first, first + tables):
            for record in run_table(seed, link, rng, guide, guided_share, informed_share):
                handle.write(json.dumps(record) + "\n")
                done += 1
                feasible += record["feasible"]
            handle.flush()
            if (seed - first + 1) % 10 == 0:
                print(
                    f"[{worker}] {seed - first + 1}/{tables} tables, {done} pushes ({feasible} feasible), "
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
        work(
            arguments.first,
            arguments.tables,
            arguments.out,
            arguments.worker,
            arguments.guide,
            arguments.guided_share,
            arguments.informed_share,
        )
        return
    share = math.ceil(arguments.tables / arguments.workers)
    children = []
    for w in range(arguments.workers):
        first = arguments.first + w * share
        count = min(share, arguments.first + arguments.tables - first)
        if count <= 0:
            continue
        part = arguments.out.with_suffix(f".part{w}.jsonl")
        extra = (
            ["--guide", str(arguments.guide), "--guided-share", str(arguments.guided_share)]
            if arguments.guide
            else []
        )
        extra += ["--informed-share", str(arguments.informed_share)]
        children.append(
            (
                part,
                subprocess.Popen(
                    [
                        sys.executable,
                        __file__,
                        "--first",
                        str(first),
                        "--tables",
                        str(count),
                        "--out",
                        str(part),
                        "--worker",
                        str(w),
                        *extra,
                    ]
                ),
            )
        )
    for _, child in children:
        child.wait()
    with open(arguments.out, "w") as joined:
        for part, _ in children:
            joined.write(part.read_text())
            part.unlink()
    print("wrote", arguments.out)


if __name__ == "__main__":
    main()
