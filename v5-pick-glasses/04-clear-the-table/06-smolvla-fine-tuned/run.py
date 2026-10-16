"""What the fitted model achieves on problem 4's tables, and what it spends getting there.

    pixi run python -u 06-smolvla-fine-tuned/run.py                       # the measurement
    pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables 8 --runs 1
    pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables 8 --runs 1 --quiet-for 3
    pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables 20 --room 120 \
        --save pair-fitted.json
    pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables 20 --room 120 \
        --as-it-downloads --save pair-untrained.json

**The measurement is the held-out queue**, and ``bench/judging.py`` is what
holds it: the same fifty tables from table ten thousand, in the same order, with
the same fifteen arm minutes for the whole list, walked three times. Every
solution in problem 4 is marked that way, and nothing about the arrangement is
this folder's to choose -- a run that is not the full arrangement is written to a
scratch file beside the result and cannot overwrite it.

**``--room`` is the other arrangement, and it is not the measurement.** It gives
every table that much arm time on its own instead of sharing one budget down a
queue, which is how solution 5 reports itself: what one table costs this
solution, rather than how far down a list it gets. The pair is only readable
side by side, so this folder can be run that way too. It is refused on the
held-out tables.

**One walk a fitted seed.** The fit varies with its seed and the policy draws
its chunk from fresh noise, so two things vary and both have to. Three
corrections were fitted; walk ``n`` is walked by correction ``n`` with the noise
seeded at ``n``, so the spread the scorecard reports covers both.

**Below ten thousand is where anything was compared.** How long a quiet spell
is taken as the policy saying it is finished is the bench's own number, and
``--quiet-for`` is how it was compared against two shorter ones on the tables
below the held-out line. The held-out tables were walked once, afterwards.

**``--as-it-downloads`` is the pair, measured rather than read across.** It
walks the same tables with the same weights uncorrected, under this solution's
own stopping count, so that the training is the only difference between the two
columns. Solution 5's published numbers stop after three quiet answers, which
this solution does not, and two different stopping counts are two arrangements.

**What the solution itself keeps** is written beside the scorecard: the shape of
its answers, its own split of the arm time between paths that could have touched
a glass and paths that could not, and why the cell would not carry a path out.
None of it is scored. The scorecard looks at the table rather than at the policy,
which is what tells a tidy table from a lucky one.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path

import torch
import weights
from fine_tuned import FineTuned, as_it_downloads, load

from judging import HELD_OUT, QUEUE, RUNS, judge
from open_run import ARM_BUDGET, Tally, clear_queue
from partners import TEST_SEEDS
from scoring import Repeats
from stopping import QUIET_ANSWERS

HERE = Path(__file__).resolve().parent


def nothing_fitted(folder: Path, device: str | None):
    """The same weights with nothing fitted. ``folder`` is a label and is not read."""
    return as_it_downloads(device)


class Walks:
    """A fresh solution for each walk of the queue, each on its own fitted correction.

    ``judge`` asks for a solution rather than taking one, so that nothing a
    solution learned on one walk reaches the next. This is what it asks, and it
    does two more things on the way. It seeds the noise the policy denoises
    from, so a walk can be repeated. And it lets go of the last walk's model
    before it loads the next, because three of these weigh six gigabytes and
    only one of them is ever answering.
    """

    def __init__(
        self,
        folders: list[Path],
        device: str | None,
        quiet_for: int,
        make: Callable = load,
    ) -> None:
        self.folders = folders
        self.device = device
        self.quiet_for = quiet_for
        # How a correction becomes a model. Named rather than called directly so
        # that the walking can be tested without two gigabytes of weights.
        self.make = make
        self.walks = 0
        self.name = ""
        self.solution: FineTuned | None = None
        self.each: list[dict] = []

    def __call__(self) -> FineTuned:
        self.finish()
        folder = self.folders[self.walks % len(self.folders)]
        print(f"\nwalk {self.walks + 1}: loading {folder.name}", flush=True)
        torch.manual_seed(self.walks)
        self.solution = FineTuned(self.make(folder, self.device), quiet_for=self.quiet_for)
        self.name = folder.name
        self.walks += 1
        return self.solution

    def finish(self) -> None:
        """Keep what the last walk's solution counted, and let go of its model."""
        if self.solution is not None:
            self.each.append({"correction": self.name, **self.solution.summary()})
            self.solution = None
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

    def summaries(self) -> list[dict]:
        self.finish()
        return self.each


def a_table_at_a_time(
    walks: Walks,
    seeds: range,
    room: float,
    runs: int,
    show: bool = True,
    cell_for: Callable | None = None,
) -> tuple[Repeats, int]:
    """Every table given ``room`` arm seconds of its own, which is how solution 5 reports itself.

    A queue of one table at a time. The real runner still runs each of them and
    every table gets the same allowance, so what comes out is what one table
    costs this solution rather than how far down a list it got. ``ended_by``
    still says when the allowance was what stopped a table.

    A queue of one can come back empty, which is why the result is not simply
    read off the front of it. The runner drops a table the arm never moved on at
    all, and a table can end that way even with a full allowance: a policy whose
    every answer the cell refuses spends nothing, so the table ends on the
    answer guard with no motion against it. Such a table is skipped here too,
    for the runner's own reason -- every glass on it would otherwise count as a
    glass left crowded.
    """
    repeats = Repeats()
    tally = Tally()
    skipped = 0
    for _ in range(runs):
        solution = walks()
        card = repeats.run()
        for seed in seeds:
            reached = clear_queue(solution, [seed], room, tally=tally, cell_for=cell_for).results
            if not reached:
                skipped += 1
                print(f"  seed {seed}: the arm never moved on this table, so it is not counted")
                continue
            result = reached[0]
            card.table(result)
            if show:
                print(
                    f"  seed {seed}: {result.glasses} glasses, pickable "
                    f"{result.pickable_at_start}->{result.pickable_at_end}, {result.toppled} broken, "
                    f"{result.arm_seconds:6.1f} arm s, {result.answers} answers, "
                    f"ended by {result.ended_by}",
                    flush=True,
                )
    print("\nthe conversation: " + ", ".join(f"{k} {v}" for k, v in tally.summary().items() if v != {}))
    if skipped:
        print(f"{skipped} tables the arm never moved on, which the runner drops")
    return repeats, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=int, default=HELD_OUT, help="first table of the queue")
    parser.add_argument("--tables", type=int, default=QUEUE, help="how long the queue is")
    parser.add_argument("--runs", type=int, default=RUNS, help="walks of the whole queue")
    parser.add_argument("--budget", type=float, default=ARM_BUDGET, help="arm seconds for the queue")
    parser.add_argument("--seeds", type=int, default=3, help="how many fitted corrections to walk with")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--quiet-for", type=int, default=QUIET_ANSWERS, help="quiet answers taken as done")
    parser.add_argument(
        "--room",
        type=float,
        default=0.0,
        help="arm seconds for every table on its own, instead of one budget down a queue",
    )
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    parser.add_argument(
        "--save",
        default="",
        help="name the file a --room run writes, so two such runs can sit side by side",
    )
    parser.add_argument(
        "--as-it-downloads",
        action="store_true",
        help="the same model with nothing fitted, under this solution's own stopping count",
    )
    arguments = parser.parse_args()

    held_out = arguments.first >= TEST_SEEDS
    if held_out and arguments.room:
        raise SystemExit(
            f"tables from {TEST_SEEDS} up are the measurement, and the measurement is the queue. "
            "--room is for the tables below it."
        )
    if held_out and arguments.as_it_downloads:
        raise SystemExit(
            "the held-out tables are solution 5's to walk with its own weights, not this folder's. "
            "--as-it-downloads is the matched pair on the tables below them."
        )
    # The pair, measured here rather than read across from solution 5's own
    # numbers, because solution 5 stops after three quiet answers and this
    # solution does not. Running the uncorrected weights under this solution's
    # own stopping count is what leaves the training as the only difference.
    if arguments.as_it_downloads:
        folders = [Path("smolvla as it downloads")]
        make = nothing_fitted
    else:
        folders = weights.fitted(arguments.seeds, arguments.first_seed)
        make = load
    print(
        f"{arguments.runs} walks of {arguments.tables} tables from {arguments.first}, "
        f"{arguments.room:g} arm seconds a table"
        if arguments.room
        else f"{arguments.runs} walks of {arguments.tables} tables from {arguments.first}, "
        f"{arguments.budget:g} arm seconds for the whole queue"
    )
    print(
        f"with {', '.join(folder.name for folder in folders)}; "
        f"{arguments.quiet_for} quiet answers taken as done"
    )
    if not held_out:
        print("these tables are below the held-out line, so this is a run made while building")

    walks = Walks(folders, arguments.device, arguments.quiet_for, make=make)
    started = time.perf_counter()
    skipped = 0
    if arguments.room:
        tables = range(arguments.first, arguments.first + arguments.tables)
        repeats, skipped = a_table_at_a_time(walks, tables, arguments.room, arguments.runs)
        save = HERE / (arguments.save or "measurement.json")
        repeats.report(save)
    else:
        judge(
            walks,
            HERE / "results.json",
            first=arguments.first,
            tables=arguments.tables,
            runs=arguments.runs,
            budget=arguments.budget,
        )
    print(f"\n{(time.perf_counter() - started) / 60:.1f} minutes of laptop time")

    # Beside the scorecard, and never inside it: what the solution asked for is
    # diagnosis, and the same name tells a reader which of the two a file is.
    full = (
        not arguments.room
        and arguments.first == HELD_OUT
        and arguments.tables == QUEUE
        and arguments.runs == RUNS
    )
    # One name a run, so that the two halves of the pair and the three stopping
    # counts do not overwrite each other's record of what was asked.
    if full:
        beside = HERE / "asking.json"
    elif arguments.room and arguments.save:
        beside = save.with_name(save.stem + "-asking.json")
    else:
        beside = HERE / "asking-partial.json"
    beside.write_text(
        json.dumps(
            {
                "weights": [folder.name for folder in folders],
                "walks": arguments.runs,
                "first_table": arguments.first,
                "tables": arguments.tables,
                "arm_budget": arguments.budget,
                "quiet_answers_taken_as_done": arguments.quiet_for,
                "tables_the_arm_never_moved_on": skipped,
                "each_walk": walks.summaries(),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"what it asked for is in {beside}")


if __name__ == "__main__":
    main()
