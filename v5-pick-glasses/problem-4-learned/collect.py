"""Push glasses about at random on mixed training tables, and write down what happened.

Problem 3's round 1 (problem-3-learned/collect.py), on mixed tables, with one
addition. Before each push some glasses have their kind hidden, so the model
also learns what a push does to a glass it was not told about. The simulator
still knows the kind and still pushes the glass for real; only the model's
input says NOT_MEASURED. At run time those are the glasses nobody has
photographed from the side yet.

The labels come from look(), before and after, the same noisy readings the arm
has. The simulator's own record is never read here.

    pixi run python collect.py                 # 9000 tables, about 10 minutes
    pixi run python collect.py --tables 500
"""

from __future__ import annotations

import argparse
import math
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import push_features as features
import tables
from bench import Push, has_room

DATA = Path(__file__).parent / "data"

PUSHES_PER_TABLE = 12

# Validation tables start here: never trained on, and not the held-out ones.
VALIDATION_SEEDS = 9000

# The share of glasses whose kind is hidden before each push. About the share
# a run meets: glasses are measured before they are pushed wherever a side
# view exists, and most crowded glasses have one.
HIDDEN_SHARE = 0.3

# As in problem 3: how often the push goes to a glass without room, how often
# it heads roughly away from its nearest neighbour, and how often a glass with
# room is taken off first.
CROWDED_SHARE = 0.7
AWAY_SHARE = 0.5
AWAY_SPREAD = math.radians(50)
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
    bench = tables.mixed_bench(seed)
    inputs, outputs = [], []
    for _ in range(PUSHES_PER_TABLE):
        seen = bench.look()
        if len(seen) < 2 or not all(s.standing for s in seen):
            break
        roomy = [s for s in seen if not crowded(seen, s)]
        if roomy and rng.random() < TAKE_SHARE:
            bench.take(rng.choice(roomy).id)
            continue
        kinds = {s.id: bench.glasses[s.id].kind for s in seen if rng.random() >= HIDDEN_SHARE}
        target, heading, offset, travel = random_push(rng, seen)
        start = features.jaw_start(target, heading, offset)
        felt = bench.push(
            Push(target.id, start, heading, features.jaw_reach(target), travel, (target.x, target.y))
        )
        inputs.append(features.encode(seen, target, kinds, heading, offset, travel)[0])
        outputs.append(features.outcome(seen, bench.look(), target, heading, felt.blocked))
    if not inputs:
        return np.zeros((0, features.INPUTS), np.float32), np.zeros((0, features.OUTPUTS), np.float32)
    return np.stack(inputs), np.stack(outputs)


def collect(seeds: list[int], save: Path, workers: int) -> None:
    started = time.time()
    with Pool(workers) as pool:
        parts = pool.map(table, seeds, chunksize=4)
    inputs = np.concatenate([p[0] for p in parts])
    outputs = np.concatenate([p[1] for p in parts])
    np.savez_compressed(
        save, inputs=inputs, outputs=outputs, seeds=np.repeat(seeds, [len(p[0]) for p in parts])
    )
    print(
        f"{len(seeds)} tables, {len(inputs)} pushes in {time.time() - started:.0f}s: "
        f"{int(outputs[:, features.TOPPLED].sum())} toppled something, "
        f"{int(outputs[:, features.BLOCKED].sum())} blocked on the way down -> {save.name}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=9000)
    parser.add_argument("--validation", type=int, default=200)
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args()
    assert arguments.tables <= VALIDATION_SEEDS
    DATA.mkdir(exist_ok=True)
    collect(list(range(arguments.tables)), DATA / "pushes.npz", arguments.workers)
    collect(
        list(range(VALIDATION_SEEDS, VALIDATION_SEEDS + arguments.validation)),
        DATA / "pushes_validation.npz",
        arguments.workers,
    )


if __name__ == "__main__":
    main()
