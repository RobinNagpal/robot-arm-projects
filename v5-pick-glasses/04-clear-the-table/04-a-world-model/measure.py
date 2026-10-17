"""What this solution does with twenty tables, beside what the geometry reference does.

    pixi run python measure.py                       # the same twenty the reference used
    pixi run python measure.py --predicting          # and without a look between pushes
    pixi run python measure.py --judge               # the held-out queue, once, at the end

**The twenty tables are seeds 0 to 19**, which are the tables the geometry
reference's own calibration run used, so the two sets of numbers are about the
same tables. They are below ``TEST_SEEDS`` and they are not the measurement:
the held-out tables are walked once, by the owner of the problem, with
``--judge``, which hands the whole arrangement to ``bench/judging.py`` rather
than deciding any of it here.

**The clock is turned up out of the way for the twenty.** ``ARM_BUDGET``
belongs to a queue of fifty held-out tables and would stop this run partway
down the list, and a solution measured on the tables it happened to reach is
not being compared with one measured on all twenty. So each table is given more
arm time than it can spend, and what it spent is the number reported.

**The split between looking and pushing is the solution's own accounting**, as
it is in the reference's calibration run. The cell charges arm seconds without
caring why a path was asked for, so the split comes from what ``clock.py``
estimates each path at as it is answered. The two totals differ a little, in
the way ``clock.py`` describes, so the split is a share and not a
reconciliation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import learned

from open_run import Tally, clear_queue
from partners import TEST_SEEDS
from scoring import Scorecard

# Arm seconds for the queue while measuring: far more than the solution can
# spend, so that nothing here is cut short by the clock.
ROOM_TO_WORK = 100_000.0

# The tables the geometry reference's calibration run used.
TABLES = 20


def measure(solution, first: int, count: int) -> tuple[Scorecard, list[tuple], Tally]:
    """Walk the tables one at a time, and read the looking off between them."""
    card, split, tally = Scorecard(), [], Tally()
    for seed in range(first, first + count):
        looked, pushed = solution.look_seconds, solution.push_seconds
        # A queue of one, so that the solution's own running totals can be read
        # between tables. The real runner still runs each of them.
        result = clear_queue(solution, [seed], ROOM_TO_WORK, tally=tally).results[0]
        card.table(result)
        split.append((result, solution.look_seconds - looked, solution.push_seconds - pushed))
        print(
            f"seed {seed}: {result.glasses} glasses, pickable {result.pickable_at_start}"
            f"->{result.pickable_at_end}, {result.arm_seconds:6.1f} arm s "
            f"({split[-1][1]:5.1f} looking, {split[-1][2]:5.1f} pushing), "
            f"{result.answers} answers, {result.toppled} over, ended by {result.ended_by}"
        )
    return card, split, tally


def headline(card: Scorecard, split: list[tuple]) -> dict:
    """The six numbers the README sets beside the geometry reference's."""
    summary = card.summary()
    arm = sorted(row["arm_seconds"] for row in card.tables)
    looking = sum(row[1] for row in split)
    pushing = sum(row[2] for row in split)
    return {
        "tables": summary["tables_attempted"],
        "glasses": summary["glasses"],
        "separated": summary["outcome"]["separated"],
        "pickable_at_end": summary["glasses_end"]["pickable"],
        "pickable_at_start": summary["glasses_end"]["pickable_at_start"],
        "pickable_share": summary["glasses_end"]["pickable_share"],
        "gain": summary["glasses_end"]["gain"],
        "toppled": summary["glasses_end"]["broken"],
        "arm_seconds_a_table": round(sum(arm) / len(arm), 2),
        "arm_seconds_middling": arm[len(arm) // 2],
        "arm_seconds_most": arm[-1],
        "arm_seconds_for_the_queue": round(sum(arm), 2),
        "looking_share": round(looking / (looking + pushing), 3) if looking + pushing else 0.0,
        "said_done": summary["ended_by"]["said_done"],
        "said_done_while_crowded": summary["said_done_while_crowded"],
        "interlocks": summary["interlocks"],
        "answers": summary["answers"],
        "thinking_seconds": summary["thinking_seconds"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=TABLES)
    parser.add_argument("--first", type=int, default=0)
    parser.add_argument("--predicting", action="store_true", help="no look between pushes; believe the model")
    parser.add_argument("--judge", action="store_true", help="the held-out queue, through bench/judging.py")
    parser.add_argument("--save", type=str, default="", help="write the numbers to this file")
    parser.add_argument("--seed", type=int, default=0, help="the search's own draws, for repeatability")
    parser.add_argument("--show", action="store_true", help="print why each table ended")
    arguments = parser.parse_args()

    if arguments.judge:
        import judging

        judging.judge(
            lambda: learned.WorldModel(predicting=arguments.predicting),
            Path(__file__).parent / "results.json",
        )
        return

    last = arguments.first + arguments.tables - 1
    if last >= TEST_SEEDS:
        raise SystemExit(
            f"seeds {arguments.first}..{last} reach the held-out tables, which start at {TEST_SEEDS}. "
            f"They are walked once, through judging.py: pixi run python measure.py --judge"
        )

    # Seeded, so that the numbers this prints can be printed again. The
    # held-out run is not seeded, because three identical walks of the queue
    # would report a spread of zero for a solution that really does vary.
    solution = learned.WorldModel(predicting=arguments.predicting, seed=arguments.seed)
    card, split, tally = measure(solution, arguments.first, arguments.tables)
    numbers = headline(card, split)
    print()
    print(
        f"{numbers['tables']} tables, {numbers['glasses']} glasses: "
        f"separated {numbers['separated']}, pickable {numbers['pickable_at_end']} "
        f"(from {numbers['pickable_at_start']}, so {numbers['gain']:+d}), over {numbers['toppled']}"
    )
    print(
        f"arm {numbers['arm_seconds_a_table']} s a table on average, "
        f"{numbers['arm_seconds_middling']} in the middle, {numbers['arm_seconds_most']} at worst; "
        f"{100 * numbers['looking_share']:.0f}% of it looking"
    )
    print(
        f"said done {numbers['said_done']} of {numbers['tables']} times, "
        f"{numbers['said_done_while_crowded']} of them while the table was still crowded; "
        f"{numbers['interlocks']} pushes the cell refused"
    )
    if arguments.show:
        for reason, count in tally.done_because.items():
            print(f"  said done {count}x: {reason}")

    if arguments.save:
        where = Path(arguments.save)
        where.write_text(
            json.dumps(
                {
                    "predicting": arguments.predicting,
                    "summary": numbers,
                    "tables": card.tables,
                    "looking_seconds": [round(row[1], 2) for row in split],
                    "pushing_seconds": [round(row[2], 2) for row in split],
                    "tally": tally.summary(),
                    # What the model believed about every push it answered with,
                    # beside what the table did. The solution's own page asks
                    # for exactly this: it is what says whether the pushes that
                    # topple a glass are the ones the model was confident about.
                    # It costs no arm time, because it is all on the laptop's
                    # side of the fence.
                    "believed": solution.risked,
                    "pushes_dropped_for_clearance": dict(solution.dropped),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"written to {where}")


if __name__ == "__main__":
    main()
