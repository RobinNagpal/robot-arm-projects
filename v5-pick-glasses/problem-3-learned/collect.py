"""Push glasses about at random on training tables, and write down what happened.

Each training table gets up to PUSHES_PER_TABLE pushes in a row, the state
after one being the start of the next, so a table's build and settle are paid
once for a dozen examples. A table stops early once anything has fallen over.

The labels come from look(), before and after, the same noisy readings the arm
has at run time. The simulator's own record is never read here.

There are two rounds. The first pushes at random. The second lets the planner
choose, using the model trained on the first, with a share of random pushes
still mixed in. The planner searches thousands of pushes and finds the few
where the model is wrong in its favour; the second round makes exactly those
pushes and writes down what really happened, which is the data that closes
the holes.

    pixi run python collect.py                     # round 1: random pushes
    pixi run python collect.py --planned           # round 2: the planner's own
"""

from __future__ import annotations

import argparse
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import features
from bench import KINDS, Bench, Push, has_room

DATA = Path(__file__).parent / "data"

PUSHES_PER_TABLE = 12

# Validation tables start here: below the test seeds, never trained on.
VALIDATION_SEEDS = 9000

# How often the push goes to a glass without room, and how often it heads
# roughly away from its nearest neighbour, which is what the planner will ask
# about most. The rest are uniform, so the model also sees pushes into things.
CROWDED_SHARE = 0.7
AWAY_SHARE = 0.5
AWAY_SPREAD = math.radians(50)

# How often a glass with room is taken off first, so the model also sees
# tables with fewer glasses than they started with.
TAKE_SHARE = 0.15


def crowded(seen: list, glass) -> bool:
    return not has_room(glass.x, glass.y, [(s.x, s.y, s.widest) for s in seen if s.id != glass.id])


def random_push(rng: random.Random, seen: list):
    squeezed = [s for s in seen if crowded(seen, s)]
    target = rng.choice(squeezed if squeezed and rng.random() < CROWDED_SHARE else seen)
    others = features.others_of(seen, target)
    if others and rng.random() < AWAY_SHARE:
        near = others[0]
        heading = math.atan2(target.y - near.y, target.x - near.x) + rng.gauss(0.0, AWAY_SPREAD)
    else:
        heading = rng.uniform(-math.pi, math.pi)
    offset = rng.uniform(-features.OFFSET, features.OFFSET) * target.widest / 2
    travel = rng.uniform(*features.TRAVEL)
    return target, heading, offset, travel


def table(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Every push made on one table: input rows and output rows."""
    rng = random.Random(seed)
    bench = Bench(seed)
    kind = KINDS[seed % len(KINDS)]
    inputs, outputs = [], []
    for _ in range(PUSHES_PER_TABLE):
        seen = bench.look()
        if len(seen) < 2 or not all(s.standing for s in seen):
            break
        roomy = [s for s in seen if not crowded(seen, s)]
        if roomy and rng.random() < TAKE_SHARE:
            bench.take(rng.choice(roomy).id)
            continue
        target, heading, offset, travel = random_push(rng, seen)
        start = features.jaw_start(target, heading, offset)
        reach = features.jaw_reach(target)
        felt = bench.push(Push(target.id, start, heading, reach, travel, (target.x, target.y)))
        inputs.append(features.encode(seen, target, kind, heading, offset, travel)[0])
        outputs.append(features.outcome(seen, bench.look(), target, heading, felt.blocked))
    if not inputs:
        return np.zeros((0, features.INPUTS), np.float32), np.zeros((0, features.OUTPUTS), np.float32)
    return np.stack(inputs), np.stack(outputs)


# Round 2: how often the planner's choice is swapped for a random push, so the
# model keeps seeing pushes the planner would not make.
EXPLORE = 0.25
# Round 2 tables start here, after round 1's, so no table is used twice.
PLANNED_SEEDS = 4000

_model = None


def _load_model() -> None:
    global _model
    import torch

    from model import Ensemble
    from train import WEIGHTS

    torch.set_num_threads(1)
    _model = Ensemble.load(WEIGHTS)


def planned_table(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Like ``table``, but the planner chooses most of the pushes."""
    import plan

    rng = random.Random(seed)
    generator = np.random.default_rng(seed)
    bench = Bench(seed)
    kind = KINDS[seed % len(KINDS)]
    inputs, outputs = [], []
    for _ in range(PUSHES_PER_TABLE):
        seen = bench.look()
        if len(seen) < 2 or not all(s.standing for s in seen):
            break
        roomy = [s for s in seen if not crowded(seen, s)]
        if roomy:
            bench.take(roomy[0].id)
            continue
        choices = [] if rng.random() < EXPLORE else [plan.best_push(_model, seen, s, kind, generator).choice for s in seen]
        choices = [c for c in choices if c is not None]
        if choices:
            best = min(choices, key=lambda c: c.cost)
            target = next(s for s in seen if s.id == best.target)
            heading, offset, travel = best.heading, best.offset, best.travel
        else:
            target, heading, offset, travel = random_push(rng, seen)
        start = features.jaw_start(target, heading, offset)
        felt = bench.push(Push(target.id, start, heading, features.jaw_reach(target), travel, (target.x, target.y)))
        inputs.append(features.encode(seen, target, kind, heading, offset, travel)[0])
        outputs.append(features.outcome(seen, bench.look(), target, heading, felt.blocked))
    if not inputs:
        return np.zeros((0, features.INPUTS), np.float32), np.zeros((0, features.OUTPUTS), np.float32)
    return np.stack(inputs), np.stack(outputs)


def collect(seeds: list[int], save: Path, workers: int, planned: bool = False) -> None:
    started = time.time()
    with Pool(workers, initializer=_load_model if planned else None) as pool:
        parts = pool.map(planned_table if planned else table, seeds, chunksize=4)
    inputs = np.concatenate([p[0] for p in parts])
    outputs = np.concatenate([p[1] for p in parts])
    np.savez_compressed(save, inputs=inputs, outputs=outputs)
    toppled = int(outputs[:, features.TOPPLED].sum())
    blocked = int(outputs[:, features.BLOCKED].sum())
    print(
        f"{len(seeds)} tables, {len(inputs)} pushes in {time.time() - started:.0f}s: "
        f"{toppled} toppled something, {blocked} blocked on the way down -> {save.name}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=2600)
    parser.add_argument("--validation", type=int, default=200)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--planned", action="store_true", help="round 2: the planner chooses the pushes")
    arguments = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    if arguments.planned:
        seeds = range(PLANNED_SEEDS, PLANNED_SEEDS + arguments.tables)
        assert seeds[-1] < VALIDATION_SEEDS
        collect(list(seeds), DATA / "train_planned.npz", arguments.workers, planned=True)
        return
    assert arguments.tables <= PLANNED_SEEDS
    collect(list(range(arguments.tables)), DATA / "train.npz", arguments.workers)
    collect(
        list(range(VALIDATION_SEEDS, VALIDATION_SEEDS + arguments.validation)),
        DATA / "validation.npz",
        arguments.workers,
    )


if __name__ == "__main__":
    main()
