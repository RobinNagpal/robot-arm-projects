"""Run the fitted Evo-1 over the held-out tables, and score it.

The same tables, first looks, budget, loop and scorecard as [solution
5](../05-smolvla-as-it-downloads) and [solution
6](../06-smolvla-fine-tuned), because this solution exists to be compared
with those two and a comparison is only readable if nothing else moved. The
loop is solution 5's own ``clear``, imported rather than rewritten. The only
differences between this run and solution 6's are which model answers and
that its picture is scaled up to the size its checkpoint insists on.

    pixi run python 07-evo1-fine-tuned/run.py                  # 3 runs over 50 held-out tables
    pixi run python 07-evo1-fine-tuned/run.py --tables 3 --show
    pixi run python 07-evo1-fine-tuned/run.py --fit fitted-0 --fit fitted-1 --fit fitted-2 --runs 1
    pixi run python 07-evo1-fine-tuned/run.py --tables 3 --film 3   # videos of the first 3

Two things vary and both have to be run several times, which is what [the
bench](../../docs/03-push-glasses-apart/the-examiner.md) asks of a trained
policy. The model draws its chunk from fresh noise, so the same table asked
twice is answered twice; ``--runs`` varies that. And the fitting itself varies
with its seed, so the same recipe gives fits of different quality; ``--fit``
takes one folder per seed. The scorecard holds every run together and reports
the spread, and the file says how many of each went into it, because a spread
over one fitting seed is a narrower claim than a spread over several.

Anything shorter than the full held-out set writes ``partial.json`` and never
``results.json``, because one short run is not this solution's result.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from evo import FITTED, Fitted
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
    parser.add_argument("--runs", type=int, default=RUNS, help="evaluation runs per fit")
    parser.add_argument("--fit", action="append", default=None, help="a fitted folder, one per seed")
    parser.add_argument("--first", type=int, default=TEST_SEEDS, help="first table's seed")
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    arguments = parser.parse_args()

    where = arguments.device or device_for()
    fits = [HERE / name for name in arguments.fit] if arguments.fit else [FITTED]
    runs = Repeats()
    spent = Tally()

    started = time.time()
    for fitted, folder in enumerate(fits):
        print(f"loading evo-1 on {where}, with the action half from {folder.name}")
        model = Fitted.load(where, folder)
        for run in range(arguments.runs):
            # The noise the model draws from is what varies between runs of
            # one fit, so seeding it is what makes a run repeatable.
            torch.manual_seed(1000 * fitted + run)
            card = runs.run()
            for i, seed in enumerate(range(arguments.first, arguments.first + arguments.tables)):
                filmed = i < arguments.film and run == 0 and fitted == 0
                table = FilmedBench(seed, "evo-1 fine-tuned") if filmed else Bench(seed)
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
        f"\n{time.time() - started:.0f}s for {len(fits)} fit(s) "
        f"x {arguments.runs} runs of {arguments.tables} tables"
    )
    print("asking   " + ", ".join(f"{k} {v}" for k, v in spent.summary().items() if v != {}))
    # Only the full held-out run is the result; anything shorter must not overwrite it.
    full = arguments.first == TEST_SEEDS and arguments.tables == 50 and len(fits) * arguments.runs >= RUNS
    runs.report(HERE / ("results.json" if full else "partial.json"))
    (HERE / ("asking.json" if full else "asking-partial.json")).write_text(
        json.dumps(
            {
                "fits": [folder.name for folder in fits],
                "evaluation_runs_each": arguments.runs,
                **spent.summary(),
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
