"""What the ranked chooser achieves on problem 4, and what it spends getting there.

The same twenty tables solution 1 was measured on, so the two columns in this
folder's README can be set beside each other. Unlike solution 1's
``calibrate.py`` this is not setting anything: ``open_run.ARM_BUDGET`` is
already fixed, and these tables are run with the clock turned up out of the way
so that what is reported is what the solution asks for rather than what the
budget allowed it.

    pixi run python measure.py                  # twenty tables, with the ranker
    pixi run python measure.py --rule           # the same, with the model deleted
    pixi run python measure.py --perfect         # the same tables with the arm taken away
    pixi run python measure.py --tables 3 --show

**It refuses to run on the held-out tables.** Seeds from ``TEST_SEEDS`` up are
scored once, and not by a measurement run that will be read while this folder
is being written.

**``--rule`` is the ablation that isolates the ordering.** It runs the identical
loop over the identical candidate set with problem 3's printed rule picking
instead of the trees. The gap between the two columns is the value of the sort
and nothing else -- not a different candidate set, not a different loop, and not
a different problem.

**``--perfect`` takes the arm away and leaves the chooser.** True positions,
every push landing exactly where it aimed, no clock and as many pushes as the
chooser wants. It is the question this solution exists to answer: whether these
tables can be separated at all, or whether a table that ends crowded ends that
way because of the draw. Solution 1 reports the same measurement for the
printed rule, so the two can be read together.

**The split between looking and pushing is the solution's own accounting**, as
it is in solution 1 and for the same reason: the cell charges arm seconds but
has no idea why a path was asked for, so the split comes from what ``clock.py``
estimates for each path as it is answered. It is a share, not a reconciliation.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from borrowed import nudge
from ranked import ByModel, Chooser, GeometryRanked, by_rule, load_ranker

import tables
from open_run import Tally, clear_queue
from partners import TEST_SEEDS, Seen, in_zone

import plan

# Arm seconds for the whole queue while measuring. Far more than the solution
# can spend on the tables asked for, on purpose: the point is to find out what
# it asks for, so the clock must not be the thing that stops it.
ROOM_TO_WORK = 100_000.0

# How many pushes a table gets in the perfect world. Not a budget -- there is
# no clock there -- but a guard against a chooser that walks one glass round in
# a circle for ever. Far above the twenty-odd pushes a real table takes.
PERFECT_PUSHES = 200


def true_table(seed: int) -> list[Seen]:
    """The table as it really is: every glass, with no measurement error.

    Read off the draw rather than out of the simulator, because nothing this is
    used for is a question about physics. These are the same four numbers
    ``open_run.OpenCell.truth`` reads from the bench.
    """
    return [
        Seen(
            id=i,
            x=float(glass.position[0]),
            y=float(glass.position[1]),
            height=glass.outline.total_height,
            widest=glass.outline.max_diameter,
            foot=2 * float(glass.outline.radius[0]),
            standing=True,
        )
        for i, glass in enumerate(tables.table(seed))
    ]


def left_because(tally: Tally) -> Counter:
    """How many glasses were left for each reason, over the whole queue.

    Read back out of the sentences the solution gave for saying "done", which
    is the only place they are. ``Done.why`` is deliberately not scored and the
    scorecard holds nothing per glass, so the alternative would be a second
    channel out of the solution for a number nothing marks. The sentence is a
    record, so this reads the record.

    The shape being read is ``_nothing_more``'s: "N of M have room; the rest
    left alone: 3 nowhere clear to push it to, 1 tipped when tried".
    """
    found: Counter = Counter()
    for sentence, tables_said_it in tally.done_because.items():
        _, _, rest = sentence.partition("the rest left alone: ")
        for piece in rest.split(", "):
            count, _, reason = piece.strip().partition(" ")
            if count.isdigit() and reason:
                found[reason] += int(count) * tables_said_it
    return found


class Perfect(NamedTuple):
    """One table cleared with the arm taken away."""

    separated: bool
    pushes: int
    with_room: int
    glasses: int
    why: dict[int, str]  # the reasons for the glasses left, in the chooser's own words


def perfect(seed: int, choose: Chooser) -> Perfect:
    """Clear one table with the arm taken away.

    The chooser is handed the true table, its push lands the glass exactly
    where it aimed, and it may go on until the table is separated or it runs
    out of pushes to suggest. A glass the geometry says tips before it slides is
    still refused, because that refusal is part of the chooser and not part of
    the arm.

    So a table that ends crowded here is a table that no amount of better
    seeing or steadier pushing would have saved. That is the whole point of
    running it.
    """
    glasses = true_table(seed)
    pushes = 0
    settled: set[int] = set()
    for _ in range(PERFECT_PUSHES):
        settled = {
            glass.id
            for glass in glasses
            if in_zone(glass.x, glass.y) and plan.room(glass, glasses, nudge.ROOM_MARGIN)
        }
        if len(settled) == len(glasses):
            return Perfect(True, pushes, len(settled), len(glasses), {})
        push, why, _ = choose(glasses, settled)
        if push is None:
            return Perfect(False, pushes, len(settled), len(glasses), why)
        pushes += 1
        glasses = [
            Seen(g.id, *push.aim, g.height, g.widest, g.foot, g.standing) if g.id == push.glass else g
            for g in glasses
        ]
    return Perfect(False, pushes, len(settled), len(glasses), {})


def measure_perfect(seeds: range, choose: Chooser, name: str) -> dict:
    """``--perfect`` over a queue of tables, printed and summarised."""
    rows = []
    left: Counter = Counter()
    for seed in seeds:
        table = perfect(seed, choose)
        left += Counter(table.why.values())
        rows.append(
            {
                "seed": seed,
                "glasses": table.glasses,
                "separated": table.separated,
                "pushes": table.pushes,
                "with_room": table.with_room,
                "why": {str(glass): reason for glass, reason in sorted(table.why.items())},
            }
        )
        print(
            f"seed {seed}: {table.glasses} glasses, {table.with_room} with room "
            f"after {table.pushes} perfect pushes{' -- separated' if table.separated else ''}"
        )
    summary = {
        "chooser": name,
        "world": "perfect: true positions, exact pushes, no clock",
        "tables": len(rows),
        "glasses": sum(row["glasses"] for row in rows),
        "separated": sum(row["separated"] for row in rows),
        "with_room": sum(row["with_room"] for row in rows),
        "pushes": sum(row["pushes"] for row in rows),
        "left_because": dict(left),
    }
    print()
    print(
        f"{summary['tables']} perfect tables with {name}: {summary['separated']} separated, "
        f"{summary['with_room']} of {summary['glasses']} glasses with room, "
        f"{summary['pushes']} pushes"
    )
    for reason, count in left.most_common():
        print(f"  {count} left: {reason}")
    return {"summary": summary, "tables": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=20)
    parser.add_argument("--first", type=int, default=0, help="first table's seed")
    parser.add_argument("--rule", action="store_true", help="the printed rule, over the same candidates")
    parser.add_argument("--perfect", action="store_true", help="the chooser alone, with the arm taken away")
    parser.add_argument("--show", action="store_true", help="print why each table ended")
    parser.add_argument("--save", type=str, default="", help="write the numbers to this file")
    arguments = parser.parse_args()

    last = arguments.first + arguments.tables - 1
    if last >= TEST_SEEDS:
        raise SystemExit(
            f"seeds {arguments.first}..{last} reach the held-out tables, which start at {TEST_SEEDS}. "
            "They are scored once, and not by a measurement run."
        )

    seeds = range(arguments.first, arguments.first + arguments.tables)
    name = "the printed rule" if arguments.rule else "the fitted ranker"
    if arguments.perfect:
        written = measure_perfect(seeds, by_rule if arguments.rule else ByModel(load_ranker()), name)
        if arguments.save:
            Path(arguments.save).write_text(json.dumps(written, indent=2) + "\n")
            print(f"written to {arguments.save}")
        return

    solution = GeometryRanked(by_rule if arguments.rule else None)
    tally = Tally()
    split = []
    for seed in seeds:
        looked, pushed = solution.look_seconds, solution.push_seconds
        # A queue of one, so that the solution's own running totals can be read
        # between tables. The real runner still runs each of them, and the
        # budget is wide enough that no table is cut short.
        result = clear_queue(solution, [seed], ROOM_TO_WORK, tally=tally, drop_unreached=False).results[0]
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
        "chooser": name,
        "tables": len(rows),
        "glasses": sum(row["glasses"] for row in rows),
        "arm_seconds_a_table": round(sum(arm) / len(arm), 2),
        "arm_seconds_middling": arm[len(arm) // 2],
        "arm_seconds_most": arm[-1],
        "arm_seconds_for_the_queue": round(sum(arm), 2),
        "looking_share": round(looking / (looking + pushing), 3) if looking + pushing else 0.0,
        "said_done": sum(1 for row in rows if row["ended_by"] == "said done"),
        "separated": sum(
            1 for row in rows if row["pickable_at_end"] == row["glasses"] and not row["toppled"]
        ),
        "pickable_at_start": sum(row["pickable_at_start"] for row in rows),
        "pickable_at_end": sum(row["pickable_at_end"] for row in rows),
        "glasses_made_pickable": sum(row["pickable_at_end"] - row["pickable_at_start"] for row in rows),
        "toppled": sum(row["toppled"] for row in rows),
        "interlocks": sum(row["interlocks"] for row in rows),
        "thinking_seconds": round(sum(row["thinking_seconds"] for row in rows), 1),
        # How wide the choice was. A ranking over one candidate is the printed
        # rule, so this is what says whether the ordering had anything to do.
        "decisions": solution.groups,
        "candidates": solution.candidates,
        "candidates_a_decision": round(solution.candidates / solution.groups, 1) if solution.groups else 0.0,
        "widest_group": solution.widest,
        "left_because": dict(left_because(tally)),
    }
    if isinstance(solution.choose, ByModel):
        summary["picked_what_the_rule_picks"] = solution.choose.agreed
        summary["picked_otherwise"] = solution.choose.differed
    print()
    print(
        f"{summary['tables']} tables with {summary['chooser']}: "
        f"{summary['separated']} separated, {summary['toppled']} toppled, "
        f"pickable {summary['pickable_at_start']}->{summary['pickable_at_end']} "
        f"of {summary['glasses']}"
    )
    print(
        f"{summary['arm_seconds_a_table']} arm s a table on average, "
        f"{summary['arm_seconds_middling']} in the middle, {summary['arm_seconds_most']} at worst; "
        f"{100 * summary['looking_share']:.0f}% of it looking"
    )
    print(
        f"{summary['decisions']} decisions over {summary['candidates']} candidates, "
        f"{summary['candidates_a_decision']} a decision, widest {summary['widest_group']}"
    )
    for reason, count in sorted(summary["left_because"].items(), key=lambda pair: -pair[1]):
        print(f"  {count} left: {reason}")
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
