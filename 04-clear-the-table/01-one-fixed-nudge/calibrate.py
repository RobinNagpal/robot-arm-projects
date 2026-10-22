"""What the geometry reference needs on a typical table, in simulated arm seconds.

Problem 4's budget is arm time, and ``open_run.ARM_BUDGET`` says in so many
words that its value is to be set from what this solution really needs. So this
is the measurement, not a score: it walks a queue of tables with the clock
turned up out of the way, adds up the arm seconds each table took, and splits
them into the time spent getting somewhere to see and the time spent pushing.

    pixi run python calibrate.py                 # twenty tables
    pixi run python calibrate.py --tables 5 --show

**It refuses to run on the held-out tables.** Seeds from ``TEST_SEEDS`` up are
the tables every solution is scored on, and they are measured on once. A budget
tuned against them would make every number that followed a measurement of the
tuning instead of of the solutions. So this runs below that line, and says so
if asked to do otherwise.

**The split between looking and pushing is this solution's own accounting.**
``TableResult.arm_seconds`` is what the cell charged, which is the truth and is
what the arm-seconds column reports. The cell has no idea *why* a path was
asked for, so the split comes from what ``clock.py`` estimates for each path as
it is answered -- the crossing to it plus the path itself -- added up under the
two headings. The two totals differ a little, in the way ``clock.py`` describes:
a path carries its own lift home, which an estimate made beforehand cannot
know about, and a path stopped early costs less than it was estimated at. So
the split is a share rather than a reconciliation, and the share is what the
budget wants.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nudge import OneFixedNudge

from open_run import ARM_BUDGET, Tally, clear_queue
from partners import TEST_SEEDS

# Arm seconds for the whole queue while measuring. Far more than the solution
# can spend on the tables asked for, on purpose: the point is to find out what
# it asks for, so the clock must not be the thing that stops it. The budget the
# run produces is the answer; this is only the room to find it in.
ROOM_TO_WORK = 100_000.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--first", type=int, default=0, help="first table's seed")
    parser.add_argument("--show", action="store_true", help="print why each table ended")
    parser.add_argument("--save", type=str, default="", help="write the numbers to this file")
    arguments = parser.parse_args()

    last = arguments.first + arguments.tables - 1
    if last >= TEST_SEEDS:
        raise SystemExit(
            f"seeds {arguments.first}..{last} reach the held-out tables, which start at {TEST_SEEDS}. "
            "They are measured on once, and not by a calibration run."
        )

    solution = OneFixedNudge()
    tally = Tally()
    split = []
    for seed in range(arguments.first, arguments.first + arguments.tables):
        looked, pushed = solution.look_seconds, solution.push_seconds
        # A queue of one, so that the solution's own running totals can be read
        # between tables. The real runner is still what runs each of them, and
        # the budget is wide enough that no table is cut short.
        result = clear_queue(solution, [seed], ROOM_TO_WORK, tally=tally).results[0]
        split.append((result, solution.look_seconds - looked, solution.push_seconds - pushed))
        print(
            f"seed {seed}: {result.glasses} glasses, pickable {result.pickable_at_start}"
            f"->{result.pickable_at_end}, {result.arm_seconds:6.1f} arm s "
            f"({split[-1][1]:5.1f} looking, {split[-1][2]:5.1f} pushing), "
            f"{result.answers} answers, ended by {result.ended_by}"
        )

    rows = [
        {
            "seed": result.seed,
            "glasses": result.glasses,
            "pickable_at_start": result.pickable_at_start,
            "pickable_at_end": result.pickable_at_end,
            "toppled": result.toppled,
            "ended_by": result.ended_by,
            "arm_seconds": round(result.arm_seconds, 2),
            "looking_seconds": round(looking, 2),
            "pushing_seconds": round(pushing, 2),
            "answers": result.answers,
            "interlocks": result.interlocks,
            "thinking_seconds": round(result.thinking_seconds, 1),
        }
        for result, looking, pushing in split
    ]
    arm = sorted(row["arm_seconds"] for row in rows)
    looking = sum(row["looking_seconds"] for row in rows)
    pushing = sum(row["pushing_seconds"] for row in rows)
    summary = {
        "tables": len(rows),
        "arm_seconds_a_table": round(sum(arm) / len(arm), 2),
        "arm_seconds_middling": arm[len(arm) // 2],
        "arm_seconds_most": arm[-1],
        "arm_seconds_for_the_queue": round(sum(arm), 2),
        "looking_share": round(looking / (looking + pushing), 3) if looking + pushing else 0.0,
        "said_done": sum(1 for row in rows if row["ended_by"] == "said done"),
        "separated": sum(1 for row in rows if row["pickable_at_end"] == row["glasses"]),
        "glasses_made_pickable": sum(row["pickable_at_end"] - row["pickable_at_start"] for row in rows),
        "toppled": sum(row["toppled"] for row in rows),
    }
    print()
    print(
        f"{summary['tables']} tables: {summary['arm_seconds_a_table']} arm s a table on average, "
        f"{summary['arm_seconds_middling']} in the middle, {summary['arm_seconds_most']} at worst; "
        f"{100 * summary['looking_share']:.0f}% of it looking"
    )
    print(
        f"the whole queue took {summary['arm_seconds_for_the_queue']} arm s, "
        f"against an ARM_BUDGET of {ARM_BUDGET}"
    )
    if arguments.show:
        for reason, count in tally.done_because.items():
            print(f"  said done {count}x: {reason}")

    if arguments.save:
        Path(arguments.save).write_text(
            json.dumps({"summary": summary, "tables": rows, "tally": tally.summary()}, indent=2) + "\n"
        )
        print(f"written to {arguments.save}")


if __name__ == "__main__":
    main()
