"""Run the learned approach on the held-out tables, and score it.

The same tables, first looks and scorecard as problem-3-programmed/run.py, so
the two results files can be set side by side.

    pixi run python run.py              # 50 held-out tables
    pixi run python run.py --tables 5 --show
    pixi run python run.py --first 9500     # the tuning tables; results.json untouched
    pixi run python run.py --tables 3 --film 3   # videos of the first 3 in videos/

Tables 9500 on are never trained on and are not the held-out ones. The
planner's settings were chosen on them, so the held-out score is not tuned to.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch

from bench import KINDS, TEST_SEEDS, Bench
from film import FilmedBench
from model import Ensemble
from plan import clear
from scoring import Scorecard
from train import WEIGHTS

VIDEOS = Path(__file__).parent / "videos"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=50)
    parser.add_argument("--first", type=int, default=TEST_SEEDS, help="first table's seed")
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    arguments = parser.parse_args()
    torch.set_num_threads(4)
    model = Ensemble.load(WEIGHTS)
    card = Scorecard()

    started = time.time()
    for i, seed in enumerate(range(arguments.first, arguments.first + arguments.tables)):
        bench = FilmedBench(seed, "learned") if i < arguments.film else Bench(seed)
        kind = KINDS[seed % len(KINDS)]
        refused = clear(bench, model, kind, np.random.default_rng(seed))
        outcome = card.scene(bench, refused)
        if i < arguments.film:
            bench.save(VIDEOS / f"table-{seed}.mp4", f"{outcome}: racked {sum(bench.taken.values())}, "
                       f"refused {len(refused)}")
        if arguments.show:
            print(
                f"seed {seed} {kind:20s} {len(bench.glasses)} glasses, {len(bench.records)} pushes, "
                f"racked {sum(bench.taken.values())}: {outcome}  {refused or ''}"
            )
    print(f"\n{time.time() - started:.0f}s for {arguments.tables} tables")
    if arguments.film:
        print(f"videos of the first {min(arguments.film, arguments.tables)} in {VIDEOS}/")
    # Only the full held-out run is the result; anything shorter must not overwrite it.
    if arguments.first != TEST_SEEDS:
        name = "tuning.json"
    else:
        name = "results.json" if arguments.tables == 50 else "partial.json"
    card.report(Path(__file__).parent / name)


if __name__ == "__main__":
    main()
