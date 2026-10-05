"""Run the borrowed model over the held-out tables, and score it.

The same tables, first looks, budget and scorecard as the other solutions, so
the results files can be set side by side.

    pixi run python run.py                    # 3 runs over 50 held-out tables
    pixi run python run.py --tables 3 --show
    pixi run python run.py --runs 1 --tables 5
    pixi run python run.py --tables 3 --film 3   # videos of the first 3 in videos/

``--upside-down`` turns over the one convention of the join the checkpoint
does not settle, which is how much of the result hangs on it. It never writes
``results.json``.

The policy draws its answer rather than computing it, so one run is not a
measurement: ``Repeats`` holds several and reports the spread. There is no
training seed to vary, because nothing is trained — the only randomness is
the noise the flow matching starts from, which ``--runs`` varies.

The wall time of each table goes to the scorecard, which takes the bench's own
physics and rendering off it, so the compute column is what the forward passes
cost and nothing else.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from clear import Tally, clear
from joining import UP_HIGHER
from policy import Downloaded, device_for

from bench import TEST_SEEDS, Bench
from film import FilmedBench
from scoring import Repeats
from top_view import TopCamera

VIDEOS = Path(__file__).parent / "videos"
HERE = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=50)
    parser.add_argument("--runs", type=int, default=3, help="evaluation runs, for the spread")
    parser.add_argument("--first", type=int, default=TEST_SEEDS, help="first table's seed")
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    parser.add_argument(
        "--upside-down",
        action="store_true",
        help="turn the height slot of the join over; a sensitivity check, never the scored result",
    )
    arguments = parser.parse_args()

    where = arguments.device or device_for()
    print(f"loading {Downloaded.__module__}: smolvla_base on {where}")
    model = Downloaded.load(where, up=-UP_HIGHER if arguments.upside_down else UP_HIGHER)
    runs = Repeats()
    spent = Tally()

    started = time.time()
    for run in range(arguments.runs):
        # The noise the policy denoises from is the only thing that varies
        # between runs, so seeding it is what makes a run repeatable.
        torch.manual_seed(run)
        card = runs.run()
        for i, seed in enumerate(range(arguments.first, arguments.first + arguments.tables)):
            filmed = i < arguments.film and run == 0
            table = FilmedBench(seed, "smolvla as it downloads") if filmed else Bench(seed)
            camera = TopCamera(table)
            if arguments.show:
                print(f"run {run} seed {seed} {table.glasses[0].kind}, {len(table.glasses)} glasses")
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

    print(f"\n{time.time() - started:.0f}s for {arguments.runs} runs of {arguments.tables} tables")
    print("asking   " + ", ".join(f"{k} {v}" for k, v in spent.summary().items() if v != {}))
    # Only the full held-out run is the result; anything shorter must not overwrite it.
    full = (
        arguments.first == TEST_SEEDS
        and arguments.tables == 50
        and arguments.runs == 3
        and not arguments.upside_down
    )
    name = "results.json" if full else "partial.json"
    runs.report(HERE / name)
    (HERE / ("asking.json" if full else "asking-partial.json")).write_text(
        json.dumps(spent.summary(), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
