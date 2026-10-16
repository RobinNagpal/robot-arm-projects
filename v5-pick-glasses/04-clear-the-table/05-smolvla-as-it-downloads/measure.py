"""What the borrowed model does on problem 4's tables, measured three times.

    pixi run python 05-smolvla-as-it-downloads/measure.py --tables 20 \
        --save 05-smolvla-as-it-downloads/measurement.json
    pixi run python 05-smolvla-as-it-downloads/measure.py --tables 2 --runs 1 --show
    pixi run python 05-smolvla-as-it-downloads/measure.py --tables 20 --runs 1 --pinned

**Twenty tables, seeds 0 to 19, which are the twenty the geometry reference was
measured on.** That is the point of running them: the two numbers go side by
side, and a comparison against a different twenty tables would be a comparison
of the tables. It refuses to run on the held-out tables, for the reason
``calibrate.py`` next door gives: they are measured on once, and a number
produced while building is not that measurement.

**Three runs, because the answer is drawn and not computed.** The policy
denoises from fresh noise at every ask, so the same table asked twice gives two
different answers and one run is not a measurement. ``Repeats`` holds the three
and reports the spread of every number across them. The only thing that varies
between runs is that noise, seeded per run so a run can be repeated.

**A queue of one table at a time.** The budget in problem 4 belongs to a queue,
but what is wanted here is what one table costs this solution, as the geometry
reference's own measurement reports it, so each table is given the room on its
own and the throughput is worked out afterwards from the total against
``ARM_BUDGET``. ``--room`` is that room. It defaults to the whole queue's
budget rather than to something unbounded, which is deliberate: a table that
spent more arm time than the entire queue is given could never have been
reached in a real run, so the clock stopping it is both honest and a guard
against a policy that never says it is finished.

**The looking share is this solution's own accounting and is weaker than the
geometry reference's.** The reference moves the arm either to see or to push,
and knows which. This one answers with one path that is both. See
``as_downloaded.AsItDownloads._charge`` for the split that is left.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from as_downloaded import AsItDownloads, Shape
from borrowed import policy

from open_run import ARM_BUDGET, Tally, clear_queue
from partners import TEST_SEEDS
from scoring import Repeats

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--runs", type=int, default=3, help="evaluation runs, for the spread")
    parser.add_argument("--first", type=int, default=0, help="first table's seed")
    parser.add_argument("--room", type=float, default=ARM_BUDGET, help="arm seconds one table may spend")
    parser.add_argument("--show", action="store_true", help="print every table as it goes")
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    parser.add_argument(
        "--pinned",
        action="store_true",
        help="hand the model problem 3's parked jaw pose as its state; a sensitivity check",
    )
    parser.add_argument("--save", type=str, default="", help="write the numbers to this file")
    arguments = parser.parse_args()

    last = arguments.first + arguments.tables - 1
    if last >= TEST_SEEDS:
        raise SystemExit(
            f"seeds {arguments.first}..{last} reach the held-out tables, which start at {TEST_SEEDS}. "
            "They are measured on once, and not by a run made while building."
        )

    where = arguments.device or policy.device_for()
    print(f"loading {policy.WEIGHTS} on {where}")
    model = policy.Downloaded.load(where)

    repeats = Repeats()
    runs = []
    shapes = Shape()
    tally = Tally()
    started = time.perf_counter()
    for run in range(arguments.runs):
        # The noise the policy denoises from is the only thing that varies
        # between runs, so seeding it is what makes a run repeatable.
        torch.manual_seed(run)
        card = repeats.run()
        # A fresh solution each run, around the one loaded model. Nothing in it
        # is fitted, so there is nothing to carry over, and starting it again is
        # what keeps one run's totals out of the next one's.
        solution = AsItDownloads(model, pinned=arguments.pinned)
        for seed in range(arguments.first, arguments.first + arguments.tables):
            walk = clear_queue(
                solution, [seed], arguments.room, tally=tally, drop_unreached=False
            )
            result = walk.results[0]
            card.table(result)
            if arguments.show:
                print(
                    f"run {run} seed {seed}: {result.glasses} glasses, "
                    f"pickable {result.pickable_at_start}->{result.pickable_at_end}, "
                    f"{result.toppled} broken, {result.arm_seconds:6.1f} arm s, "
                    f"{result.answers} answers, ended by {result.ended_by}"
                )
        looking, pushing = solution.look_seconds, solution.push_seconds
        tables = card.summary()
        runs.append(
            {
                "run": run,
                "arm_seconds_a_table": round(tables["arm_seconds"]["total"] / arguments.tables, 2),
                "looking_share": round(looking / (looking + pushing), 3) if looking + pushing else 0.0,
                "tables_in_the_queue_budget": _reach(card, ARM_BUDGET),
                "shape": solution.shape.summary(),
            }
        )
        shapes.add(solution.shape)
        print(f"run {run + 1}/{arguments.runs}: {time.perf_counter() - started:.0f}s of laptop time so far")

    out = Path(arguments.save) if arguments.save else HERE / "partial.json"
    repeats.report(out)
    print()
    for row in runs:
        print(
            f"run {row['run']}: {row['arm_seconds_a_table']:g} arm s a table, "
            f"{100 * row['looking_share']:.0f}% of it on paths that could not touch a glass, "
            f"{row['tables_in_the_queue_budget']} tables inside the queue budget"
        )
    print("\nthe shape of its answers, over every run:")
    for name, value in shapes.summary().items():
        print(f"  {name:28} {value}")

    extra = {
        "room_a_table": arguments.room,
        "pinned_state": arguments.pinned,
        "runs": runs,
        "shape_over_every_run": shapes.summary(),
        "tally": tally.summary(),
    }
    out.with_name(out.stem + "-asking.json").write_text(json.dumps(extra, indent=2) + "\n")
    print(f"saved the asking to {out.with_name(out.stem + '-asking.json')}")


def _reach(card, budget: float) -> int:
    """How many of these tables, in order, would fit inside one queue budget.

    The throughput reading, worked out from tables measured one at a time
    rather than by walking a queue, because the per-table cost is what this
    script is for. It is the same arithmetic ``clear_queue`` does.
    """
    spent, reached = 0.0, 0
    for result in card.results:
        if spent + result.arm_seconds > budget:
            break
        spent += result.arm_seconds
        reached += 1
    return reached


if __name__ == "__main__":
    main()
