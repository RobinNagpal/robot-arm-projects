"""Run the policy on the held-out tables, and score it.

The same tables, first looks, budget and scorecard as the other solutions, so
the results files can be set side by side. The policy reads the straight-down
picture and returns one chunk per push; the bench carries the waypoints out as
given, because a chunk is already a jaw trajectory and there is nothing to
expand.

Every fitted seed is run, and ``Repeats`` reports the spread across them,
because training varies with its own seed and a method that wins by less than
its own spread has not been shown to win.

    pixi run python 03-imitation-from-demonstrations/run.py        # 50 held-out tables
    pixi run python 03-imitation-from-demonstrations/run.py --rung diffusion
    pixi run python 03-imitation-from-demonstrations/run.py --tables 5 --show
    pixi run python 03-imitation-from-demonstrations/run.py --tables 3 --film 3
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import loop
from policy import KINDS, Imitator
from train import WEIGHTS, folder

from bench import KINDS as GLASS_KINDS
from bench import TEST_SEEDS, Bench
from film import FilmedBench
from scoring import Repeats
from top_view import TopCamera

HERE = Path(__file__).parent
VIDEOS = HERE / "videos"
HELD_OUT = 50


def fitted(name: str) -> list[int]:
    """The seeds that have been trained under this name, in order.

    The tail has to be all digits, because ``act-readings-0`` also begins with
    ``act-`` and counting it as seed 0 of the plain rung would silently run the
    wrong weights.
    """
    seeds = []
    for path in WEIGHTS.glob(f"{name}-*"):
        tail = path.name[len(name) + 1 :]
        if path.is_dir() and tail.isdigit():
            seeds.append(int(tail))
    return sorted(seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rung", choices=KINDS, default="act")
    parser.add_argument("--tables", type=int, default=HELD_OUT)
    parser.add_argument("--first", type=int, default=TEST_SEEDS, help="first table's number")
    parser.add_argument("--seeds", type=int, nargs="*", help="which fitted seeds to run; all by default")
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    parser.add_argument(
        "--readings",
        action="store_true",
        help="run the fits that were given the camera's readings beside the picture",
    )
    arguments = parser.parse_args()

    # The name the weights were saved under, which is also what the result is
    # filed as, so the two variants can never overwrite one another.
    name = f"{arguments.rung}-readings" if arguments.readings else arguments.rung
    seeds = arguments.seeds if arguments.seeds else fitted(name)
    if not seeds:
        raise FileNotFoundError(
            f"nothing fitted under {name}. Train it first: "
            f"`pixi run python 03-imitation-from-demonstrations/train.py --rung {arguments.rung}"
            f"{' --readings' if arguments.readings else ''}`."
        )

    runs = Repeats()
    tally = loop.Tally()
    started = time.time()
    for seed in seeds:
        model = Imitator.load(folder(arguments.rung, seed, arguments.readings))
        card = runs.run()
        for i, number in enumerate(range(arguments.first, arguments.first + arguments.tables)):
            filmed = i < arguments.film
            table = FilmedBench(number, f"{name} seed {seed}") if filmed else Bench(number)
            camera = TopCamera(table)
            clock = time.perf_counter()
            refused = loop.clear(table, camera, model, tally, arguments.show)
            # The scorecard takes the bench's own physics and rendering off
            # this, so what is reported per push is the forward pass.
            outcome = card.scene(table, refused, seconds=time.perf_counter() - clock)
            camera.close()
            if filmed:
                racked = sum(table.taken.values())
                table.save(
                    VIDEOS / f"{name}-{seed}-table-{number}.mp4",
                    f"{outcome}: racked {racked}, refused {len(refused)}",
                )
            if arguments.show:
                print(
                    f"seed {seed} table {number} {GLASS_KINDS[number % len(GLASS_KINDS)]:20s} "
                    f"{len(table.glasses)} glasses, {len(table.records)} chunks, "
                    f"racked {sum(table.taken.values())}: {outcome}  {refused or ''}"
                )

    print(f"\n{time.time() - started:.0f}s for {len(seeds)} fitted seeds over {arguments.tables} tables")
    print(f"wrapping  {json.dumps(tally.summary())}")
    if arguments.film:
        print(f"videos of the first {min(arguments.film, arguments.tables)} in {VIDEOS}/")

    # Only a full held-out run over more than one fitted seed is the result.
    # A single seed has no spread, and a spread is what makes it a result.
    # Tables 9500 on are neither fitted on nor held out; anything run there is
    # a check and goes to its own file, so a result can never be overwritten
    # by one.
    result = "results.json" if name == "act" else f"results-{name}.json"
    if arguments.first != TEST_SEEDS:
        name = "tuning.json"
    elif arguments.tables == HELD_OUT and len(seeds) > 1:
        name = result
    else:
        name = "partial.json"
    runs.report(HERE / name)


if __name__ == "__main__":
    main()
