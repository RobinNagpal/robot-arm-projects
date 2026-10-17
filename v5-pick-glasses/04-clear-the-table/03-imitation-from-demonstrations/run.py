"""What the fitted policy achieves on problem 4, and what it spends getting there.

The same twenty tables solutions 1 and 2 were measured on, so the three columns
can be set beside each other, and every fitted seed over all twenty, because one
fit is not a measurement.

    pixi run python 03-imitation-from-demonstrations/run.py
    pixi run python 03-imitation-from-demonstrations/run.py --tables 2 --seeds 1
    pixi run python 03-imitation-from-demonstrations/run.py --save results.json

**It refuses to run on the held-out tables.** Seeds from ``TEST_SEEDS`` up are
scored once, and not by a measurement run that is read while this folder is
being written.

**Without ``--judge`` this is not a queue walk.** The real measurement gives a
solution one ordered list of held-out tables and one budget of arm minutes for
the whole list, and how far down it gets is half the score. ``--judge`` hands
that whole arrangement to ``bench/judging.py`` and takes none of it as an
argument, so this folder cannot mark itself on a kinder list; the three walks it
asks for are this solution's three fits, one each, which is where the spread
comes from. Without it, every table is handed the same allowance of its own, so
that twenty tables can be compared one against one with solutions 1 and 2, and
"tables attempted" is then always the whole list rather than a throughput
reading.

**Each table is given more arm time than it can use, and not an unlimited
amount.** Solution 2's measurement run turns the clock off altogether so that
what is reported is what the solution asks for rather than what the budget
allowed it, and this does the same thing with one difference. A fitted policy
can answer with a path the cell's tipping interlock refuses, and a refused path
moves the arm nowhere, so the clock does not advance and the same picture comes
back: a deterministic model then answers the same way for ever. The bench has a
guard for exactly that -- ``most_answers``, read off the arm time left -- and
turning the clock off turns the guard off with it. So the allowance is finite
and generous: four arm minutes a table, against the forty-four arm seconds the
teacher spends on one and the sixty-eight it spends on its worst.

**The split between looking and pushing is read off the answers**, as it is in
solutions 1 and 2 and for the same reason: the cell charges arm seconds but has
no idea why a path was asked for, so the split comes from what ``clock.py``
estimates for each path as it is answered. It is a share, not a reconciliation.
"Looking" means an answer that would not touch a glass, which is
``stopping.is_a_push`` read the other way round -- the same test the solution's
own "done" rule is built on, so the two cannot disagree.

**Only an answer the cell carried out is counted into that split**, and solutions
1 and 2 did not have to care. A path the tipping interlock refuses moves the arm
nowhere and is charged nothing, and a fitted policy asks for a great many of
them, so counting every answer would put thousands of estimated seconds against
a table that really spent eight. ``Look.refused`` is what says which: it carries
why the last path was not carried out and is empty when it was. There is one
answer a table whose fate nothing says, the one the table ended on, and
``unresolved`` counts it.

The solution itself cannot use that field -- it is a sentence of English and the
solution is a network -- which is the whole of the trouble those refusals cause.
``clear.py`` says what that means for a run.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import gate
from clear import Imitation
from wiring import pictures, policy

from clock import crossing_seconds, path_seconds
from contract import Done
from open_run import Tally, clear_queue
from partners import TEST_SEEDS
from scoring import Repeats, Scorecard
from stopping import is_a_push

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"

# Arm seconds one table is given while measuring. See the note above: generous
# enough that the clock never decides the result, finite so that the bench's own
# guard against an answer that moves the arm nowhere still binds.
ROOM_TO_WORK = 240.0

TABLES = 20
SEEDS = 3


def fits(first: int, count: int) -> list[Path]:
    """The fitted seeds on disk, in order, or a plain statement of what is missing.

    A fit is two files now: the gate that decides and the policy that draws. A
    seed is only usable when both are there, so both are looked for and a
    missing one is named.
    """
    found = [WEIGHTS / f"act-{seed}" for seed in range(first, first + count)]
    missing = [folder.name for folder in found if not folder.exists()]
    seeds = range(first, first + count)
    missing += [gate.saved(seed).name for seed in seeds if not gate.saved(seed).exists()]
    if missing:
        raise SystemExit(
            "these fits are not on disk: "
            + ", ".join(missing)
            + "\nFit them with `pixi run python -u 03-imitation-from-demonstrations/train.py`."
        )
    return found


def built(folder: Path) -> Imitation:
    """One fitted seed as a solution: its gate and its chunked policy together.

    The seed is read off the policy's folder name, because the two are fitted in
    one run under one seed and a gate from one seed with a policy from another
    would be a pair nothing was measured on.
    """
    seed = int(folder.name.rsplit("-", 1)[1])
    decider = gate.Decider.load(gate.saved(seed), pictures.shrink)
    return Imitation(policy.Imitator.load(folder), decider)


class Watched:
    """A solution, with what it asked its arm time for counted beside it.

    This belongs to the measurement and not to the policy: the policy answers
    with a path and has no interest in what the path was for, so counting it
    here is where the look the answer was made from is still to hand.

    An answer is counted only once the next look says it happened. See the note
    at the top of the file: a refused path is charged nothing, and a fitted
    policy asks for enough of them that counting the asking would swamp the
    spending.
    """

    def __init__(self, solution: Imitation) -> None:
        self.solution = solution
        self.name = solution.name
        self.looked = 0.0
        self.pushed = 0.0
        self.refused: Counter = Counter()
        self.unresolved = 0
        self.waiting: tuple[float, bool] | None = None

    def begin(self, seed: int) -> None:
        # Whatever the last table ended on, nothing will ever say whether it
        # happened, because no further look was taken on that table.
        if self.waiting is not None:
            self.unresolved += 1
            self.waiting = None
        self.solution.begin(seed)

    def answer(self, look):
        self._settle(look)
        answer = self.solution.answer(look)
        if not isinstance(answer, Done):
            cost = crossing_seconds(look.jaw, answer.waypoints[0]) + path_seconds(answer)
            # The same test the solution's own "done" rule is built on, asked
            # against the same tallest glass, so the two cannot disagree about
            # what counts as a push.
            self.waiting = (cost, is_a_push(answer, self.solution.tallest))
        return answer

    def split(self) -> tuple[float, float]:
        return self.looked, self.pushed

    def _settle(self, look) -> None:
        """Charge the answer before this look to looking or pushing, if it happened."""
        if self.waiting is None:
            return
        cost, pushing = self.waiting
        self.waiting = None
        if look.refused:
            self.refused[look.refused] += 1
        elif pushing:
            self.pushed += cost
        else:
            self.looked += cost


def one_fit(folder: Path, seeds: range, show: bool) -> tuple[Scorecard, dict]:
    """One fitted seed over every table in the list, one table at a time."""
    solution = built(folder)
    counted = Watched(solution)
    card = Scorecard()
    tally = Tally()
    rows = []
    for seed in seeds:
        before = counted.split()
        # A queue of one, so that the solution's running totals can be read
        # between tables. The real runner still runs each of them, every table
        # gets the same allowance, and ``ended_by`` says when the allowance was
        # what stopped a table.
        # ``drop_unreached`` is off because this is a queue of one. The rule it
        # turns off protects the tail of a real queue, where the clock can hand
        # a table over with too little left to act on; here the question is what
        # this solution does on this table, and a table it spent nothing on is
        # part of the answer rather than something to leave out. A policy whose
        # every answer the cell refuses spends no arm time and is stopped by the
        # answer guard, and that table has to come back.
        walk = clear_queue(counted, [seed], ROOM_TO_WORK, tally=tally, drop_unreached=False)
        result = walk.results[0]
        looking, pushing = (now - was for now, was in zip(counted.split(), before, strict=True))
        card.table(result)
        rows.append(
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
        )
        if show:
            print(
                f"  seed {seed}: {result.glasses} glasses, pickable {result.pickable_at_start}"
                f"->{result.pickable_at_end}, {result.arm_seconds:6.1f} arm s "
                f"({looking:5.1f} looking, {pushing:5.1f} pushing), "
                f"{result.answers} answers, ended by {result.ended_by}",
                flush=True,
            )
    return card, {
        "tables": rows,
        "wrapping": solution.summary()
        | {
            "answers_the_cell_would_not_carry_out": counted.refused.total(),
            "refused_because": dict(counted.refused.most_common(3)),
            "answers_whose_fate_nothing_says": counted.unresolved,
        },
        "tally": tally.summary(),
    }


def headline(rows: list[dict]) -> dict:
    """The numbers this folder's README quotes, over one fit's tables."""
    looking = sum(row["looking_seconds"] for row in rows)
    pushing = sum(row["pushing_seconds"] for row in rows)
    arm = sorted(row["arm_seconds"] for row in rows)
    return {
        "tables": len(rows),
        "glasses": sum(row["glasses"] for row in rows),
        "separated": sum(
            1 for row in rows if row["pickable_at_end"] == row["glasses"] and not row["toppled"]
        ),
        "pickable_at_start": sum(row["pickable_at_start"] for row in rows),
        "pickable_at_end": sum(row["pickable_at_end"] for row in rows),
        "toppled": sum(row["toppled"] for row in rows),
        "arm_seconds_a_table": round(sum(arm) / len(arm), 2),
        "arm_seconds_middling": arm[len(arm) // 2],
        "arm_seconds_most": arm[-1],
        "looking_share": round(looking / (looking + pushing), 3) if looking + pushing else 0.0,
        "said_done": sum(1 for row in rows if row["ended_by"] == "said done"),
        "interlocks": sum(row["interlocks"] for row in rows),
        "answers": sum(row["answers"] for row in rows),
        "thinking_seconds": round(sum(row["thinking_seconds"] for row in rows), 1),
    }


def _judge(folders: list[Path]) -> None:
    """Walk the held-out queue once a fit, through the bench's own arrangement.

    ``judging.judge`` asks for a fresh solution per walk so that nothing one
    walk learned can reach the next. Here each walk is a different fit of the
    same model, which is what makes the spread it reports a spread over fits
    rather than over three identical runs of one.
    """
    import judging

    if len(folders) != judging.RUNS:
        raise SystemExit(
            f"the held-out queue is walked {judging.RUNS} times, one a fit, "
            f"and {len(folders)} fits were asked for"
        )
    waiting = iter(folders)
    judging.judge(lambda: built(next(waiting)), HERE / "results.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=TABLES)
    parser.add_argument("--first", type=int, default=0, help="first table's seed")
    parser.add_argument("--seeds", type=int, default=SEEDS, help="how many fitted seeds to run")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument(
        "--save", type=str, default=str(HERE / "measurement.json"), help="where the numbers go"
    )
    parser.add_argument("--quiet", action="store_true", help="do not print every table")
    parser.add_argument("--judge", action="store_true", help="the held-out queue, through bench/judging.py")
    arguments = parser.parse_args()

    if arguments.judge:
        _judge(fits(arguments.first_seed, arguments.seeds))
        return

    last = arguments.first + arguments.tables - 1
    if last >= TEST_SEEDS:
        raise SystemExit(
            f"seeds {arguments.first}..{last} reach the held-out tables, which start at {TEST_SEEDS}. "
            "They are scored once, and not by a measurement run."
        )

    folders = fits(arguments.first_seed, arguments.seeds)
    tables = range(arguments.first, arguments.first + arguments.tables)
    repeats = Repeats()
    each = []
    for folder in folders:
        print(f"\n{folder.name}")
        card, extra = one_fit(folder, tables, not arguments.quiet)
        repeats.cards.append(card)
        headlines = headline(extra["tables"])
        each.append({"fit": folder.name, "headline": headlines, **extra})
        print(
            f"  {headlines['separated']} separated, {headlines['toppled']} toppled, "
            f"pickable {headlines['pickable_at_start']}->{headlines['pickable_at_end']} "
            f"of {headlines['glasses']}; {headlines['arm_seconds_a_table']} arm s a table, "
            f"{100 * headlines['looking_share']:.0f}% looking; "
            f"said done {headlines['said_done']}/{headlines['tables']}"
        )

    # The spread across the fits, printed and saved by the bench's own card, so
    # that a band reads the same here as in every other folder. One fit is not a
    # measurement, and this is the line that says so.
    save = Path(arguments.save)
    repeats.report(save)
    beside = save.with_name(save.stem + "-fits.json")
    beside.write_text(
        json.dumps({"room_to_work": ROOM_TO_WORK, "tables": list(tables), "fits": each}, indent=2) + "\n"
    )
    print(f"what each fit did, table by table, is in {beside}")


if __name__ == "__main__":
    main()
