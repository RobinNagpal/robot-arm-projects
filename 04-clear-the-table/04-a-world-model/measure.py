"""What this solution does with twenty tables, beside what the geometry reference does.

    pixi run python measure.py                       # the same twenty the reference used
    pixi run python measure.py --predicting          # and without a look between pushes
    pixi run python measure.py --judge               # the held-out queue, once, at the end
    pixi run python measure.py --toppled --first 5300 --tables 300   # which glass goes over

**The twenty tables are seeds 0 to 19**, which are the tables the geometry
reference's own calibration run used, so the two sets of numbers are about the
same tables. They are below ``TEST_SEEDS`` and they are not the measurement:
the held-out tables are walked once, by the owner of the problem, with
``--judge``, which hands the whole arrangement to ``examiner/judging.py`` rather
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


def which_glass(first: int, count: int) -> None:
    """Which glass goes over: the one the fingers touch, or one standing beside it.

    ``measurement.json`` says what the model believed about the push that broke
    a glass, but it cannot say *which* glass broke, because the examiner ends
    the table the moment one goes over, so the look that would show it is never
    taken. The examiner knows, and asking the examiner is allowed in a diagnosis
    because nothing here decides a push. The answer separates two very
    different faults: a neighbour going over means the clearance arithmetic let
    the hand pass too close, and the pushed glass going over means that glass
    tipped instead of sliding, which is the model's account of toppling and not
    the arithmetic.
    """
    import collect

    from contract import GLASS_OVER
    from open_run import STANDING_TILT_DEG, clear_table

    pushed = neighbour = 0
    believed = []
    for seed in range(first, first + count):
        solution = learned.WorldModel()
        cell = collect.blind_cell(seed)
        if clear_table(solution, seed, ROOM_TO_WORK, cell=cell).ended_by != GLASS_OVER:
            continue
        over = [i for i in cell.simulator.on_table() if cell.simulator.tilt(i) >= STANDING_TILT_DEG]
        last = solution.risked[-1] if solution.risked else None
        target = last["glass"] if last else None
        pushed += target in over
        neighbour += bool([i for i in over if i != target])
        believed.append(last["chance_of_a_topple"] if last else None)
        print(f"  table {seed}: pushed {target}, over {over}, believed {believed[-1]}")
    chances = sorted(c for c in believed if c is not None)
    print(f"{count} tables from {first}: {len(believed)} ended with a glass over")
    print(f"  the glass being pushed went over: {pushed}")
    print(f"  a glass not being pushed went over: {neighbour}")
    if chances:
        print(
            f"  the model's own chance on those pushes: {chances[len(chances) // 2]} "
            f"in the middle, {chances[-1]} at worst"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=TABLES)
    parser.add_argument("--first", type=int, default=0)
    parser.add_argument("--predicting", action="store_true", help="no look between pushes; believe the model")
    parser.add_argument(
        "--judge", action="store_true", help="the held-out queue, through examiner/judging.py"
    )
    parser.add_argument(
        "--select",
        type=int,
        default=0,
        help="a clocked queue of fifty tables from here, for choosing on: the score's own shape",
    )
    parser.add_argument("--save", type=str, default="", help="write the numbers to this file")
    parser.add_argument("--seed", type=int, default=0, help="the search's own draws, for repeatability")
    parser.add_argument("--show", action="store_true", help="print why each table ended")
    parser.add_argument(
        "--toppled",
        action="store_true",
        help="for every table a glass went over on, say whether it was the pushed glass or a neighbour",
    )
    arguments = parser.parse_args()

    if arguments.judge or arguments.select:
        import judging

        # A clocked queue below the held-out line, for choosing on. The plain
        # ``--tables`` measurement gives every table as much arm time as it
        # wants, so it says whether a table *can* be separated; the score gives
        # fifteen arm minutes for fifty tables, so it says how much gets done
        # before the clock stops. A change that trades time for thoroughness
        # wins the first and can lose the second, which is what two of this
        # solution's changes did, so a choice is made on this instead.
        # ``judging.judge`` refuses to write a partial run to ``results.json``.
        first = judging.HELD_OUT if arguments.judge else arguments.select
        if arguments.select and arguments.select >= judging.HELD_OUT:
            raise SystemExit(f"tables {judging.HELD_OUT} and up are the score; choose below them")
        judging.judge(
            lambda: learned.WorldModel(predicting=arguments.predicting),
            Path(__file__).parent / "results.json",
            first=first,
        )
        return

    last = arguments.first + arguments.tables - 1
    if last >= TEST_SEEDS:
        raise SystemExit(
            f"seeds {arguments.first}..{last} reach the held-out tables, which start at {TEST_SEEDS}. "
            f"They are walked once, through judging.py: pixi run python measure.py --judge"
        )

    if arguments.toppled:
        which_glass(arguments.first, arguments.tables)
        return

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
