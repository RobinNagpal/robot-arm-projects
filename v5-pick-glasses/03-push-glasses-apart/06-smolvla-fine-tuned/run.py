"""Run the fine-tuned model over the held-out tables, and score it.

The same tables, first looks, budget, loop and scorecard as [solution
5](../05-smolvla-as-it-downloads), because the gap between the two is the
whole point of this solution and a gap is only readable if nothing else
moved. The loop is solution 5's own ``clear``, imported; the only difference
between the two runs is which weights were loaded.

    pixi run python 06-smolvla-fine-tuned/run.py                  # 3 runs over 50 held-out tables
    pixi run python 06-smolvla-fine-tuned/run.py --tables 3 --show
    pixi run python 06-smolvla-fine-tuned/run.py --correction correction --correction correction-1
    pixi run python 06-smolvla-fine-tuned/run.py --tables 3 --film 3   # videos of the first 3

Two things vary and both have to be run several times, which is what [the
bench](../../docs/03-push-glasses-apart/the-bench.md) asks of a trained
policy. The policy draws its chunk from fresh noise, so the same table asked
twice is answered twice; ``--runs`` varies that. And the training itself
varies with its seed, so the same recipe gives two corrections of different
quality; ``--correction`` takes one folder per seed that was fitted. The
scorecard holds every run together and reports the spread, and the file says
how many of each went into it, because a spread over one training seed is a
narrower claim than a spread over several.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from correction import CORRECTION, Fitted
from partners import Tally, clear, device_for

from bench import TEST_SEEDS, Bench
from film import FilmedBench
from scoring import Repeats
from top_view import TopCamera

HERE = Path(__file__).parent
VIDEOS = HERE / "videos"
RUNS = 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=50)
    parser.add_argument("--runs", type=int, default=RUNS, help="evaluation runs per correction")
    parser.add_argument("--correction", action="append", default=None, help="a fitted correction's folder")
    parser.add_argument("--first", type=int, default=TEST_SEEDS, help="first table's seed")
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    arguments = parser.parse_args()

    where = arguments.device or device_for()
    corrections = [HERE / name for name in arguments.correction] if arguments.correction else [CORRECTION]
    runs = Repeats()
    spent = Tally()

    started = time.time()
    for fitted, folder in enumerate(corrections):
        print(f"loading smolvla_base on {where}, corrected by {folder.name}")
        model = Fitted.load(where, folder)
        for run in range(arguments.runs):
            # The noise the policy denoises from is what varies between runs
            # of one correction, so seeding it is what makes a run repeatable.
            torch.manual_seed(1000 * fitted + run)
            card = runs.run()
            for i, seed in enumerate(range(arguments.first, arguments.first + arguments.tables)):
                filmed = i < arguments.film and run == 0 and fitted == 0
                table = FilmedBench(seed, "smolvla fine-tuned") if filmed else Bench(seed)
                camera = TopCamera(table)
                if arguments.show:
                    print(f"{folder.name} run {run} seed {seed} {table.glasses[0].kind}")
                clock = time.time()
                refused, tally = clear(table, model, camera, arguments.show)
                outcome = card.scene(table, refused, time.time() - clock)
                camera.close()
                model.reset()
                spent.add(tally)
                if arguments.show:
                    print(f"  {outcome}; refused {refused or 'none'}")
                if filmed:
                    racked = sum(table.taken.values())
                    table.save(VIDEOS / f"table-{seed}.mp4", f"{outcome}: racked {racked}")
        del model

    print(
        f"\n{time.time() - started:.0f}s for {len(corrections)} correction(s) "
        f"x {arguments.runs} runs of {arguments.tables} tables"
    )
    print("asking   " + ", ".join(f"{k} {v}" for k, v in spent.summary().items() if v != {}))
    # Only the full held-out run is the result; anything shorter must not overwrite it.
    full = arguments.first == TEST_SEEDS and arguments.tables == 50 and arguments.runs == RUNS
    runs.report(HERE / ("results.json" if full else "partial.json"))
    (HERE / ("asking.json" if full else "asking-partial.json")).write_text(
        json.dumps(
            {
                "corrections": [folder.name for folder in corrections],
                "evaluation_runs_each": arguments.runs,
                **spent.summary(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
