"""How long the teacher goes without touching a glass, which is where the examiner's number came from.

``examiner/stopping.py`` reads a trained policy's "done" out of its behaviour: so
many answers in a row that would not touch a glass, and the policy is taken at
its word. ``QUIET_ANSWERS`` is how many, and it is not a free choice. However
many answers in a row the geometry reference gives without touching a glass, a
learned policy has to be allowed at least as many before anyone calls it
finished, or every solution in this problem is declared done partway through its
first look round the table.

So this measures the teacher. It runs solution 2 over a band of tables, watches
every answer through ``stopping.is_a_push`` -- the same test the rule itself uses,
so the two cannot disagree -- and reports the quiet spells two ways.

* The spells that **ended in a push**. These are the ones that matter: the
  teacher was still working, and a threshold at or below the longest of them
  would have stopped it mid-job.
* The spell each table **ended with**, before the teacher said the table needed
  nothing more. A threshold above these costs a few arm seconds of waving at a
  table that is already finished, which is the cheap direction to be wrong in.

It is run on the demonstration band and not on the twenty tables a solution is
marked on, so that nothing about the constant was set by watching a score.

    pixi run python 03-imitation-from-demonstrations/teacher.py
    pixi run python 03-imitation-from-demonstrations/teacher.py --tables 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from loading import collected

from contract import Done
from open_run import clear_table, open_cell
from partners import TEST_SEEDS
from stopping import QUIET_ANSWERS, is_a_push

HERE = Path(__file__).resolve().parent
RECORD = HERE / "teacher-quiet-spells.json"

# Arm seconds the table is given. The same figure the collection uses, and for
# the same reason: what is being measured is what the teacher does, not what a
# budget let it finish.
ROOM_TO_WORK = 100_000.0

# How many tables to watch. Forty is enough for the longest spell to settle --
# it is eight on twenty tables and eleven on forty -- and cheap, at about a
# second and a half a table.
TABLES = 40


def teacher():
    """Solution 2, built as its own measurement run builds it.

    Its folder cannot be imported by name, because the name starts with a digit,
    so it joins the path here and only here.
    """
    folder = HERE.parent / "02-geometry-ranked"
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    import ranked

    return ranked.GeometryRanked()


class Counting:
    """The teacher, with the length of every quiet spell written down beside it."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name
        self.before_a_push: Counter = Counter()
        self.before_done: Counter = Counter()
        self.quiet = 0
        self.tallest = 0.0

    def begin(self, seed: int) -> None:
        self.inner.begin(seed)
        self.quiet = 0
        self.tallest = 0.0

    def answer(self, look):
        self.tallest = max(self.tallest, *(glass.height for glass in look.seen), 0.0)
        answer = self.inner.answer(look)
        if isinstance(answer, Done):
            self.before_done[self.quiet] += 1
        elif is_a_push(answer, self.tallest):
            self.before_a_push[self.quiet] += 1
            self.quiet = 0
        else:
            self.quiet += 1
        return answer


def measure(first: int, tables: int) -> dict:
    """Watch the teacher over a band of tables and report its quiet spells."""
    if first + tables > TEST_SEEDS:
        raise ValueError(f"tables {TEST_SEEDS} and up are the held-out ones and are not watched here")
    watched = Counting(teacher())
    started = time.time()
    for seed in range(first, first + tables):
        clear_table(watched, seed, ROOM_TO_WORK, cell=open_cell(seed))
    return {
        "band": {"first_table": first, "tables": tables},
        "teacher": watched.name,
        "spells_before_a_push": {
            "count": sum(watched.before_a_push.values()),
            "longest": max(watched.before_a_push, default=0),
            "middling": _middle(watched.before_a_push),
            "each": {str(k): v for k, v in sorted(watched.before_a_push.items())},
        },
        "spells_before_saying_done": {
            "count": sum(watched.before_done.values()),
            "longest": max(watched.before_done, default=0),
            "middling": _middle(watched.before_done),
            "each": {str(k): v for k, v in sorted(watched.before_done.items())},
        },
        "quiet_answers_in_the_examiner": QUIET_ANSWERS,
        "seconds": round(time.time() - started, 1),
    }


def _middle(spells: Counter) -> int:
    """The middling spell length, which says how a spell usually goes rather than at worst."""
    laid_out = sorted(spells.elements())
    return laid_out[len(laid_out) // 2] if laid_out else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=TABLES)
    parser.add_argument("--first", type=int, default=None, help="default: the demonstration band")
    parser.add_argument("--save", type=str, default=str(RECORD))
    arguments = parser.parse_args()

    first = arguments.first
    if first is None:
        first = collected()["fitted-on"]["band"]["first_table"]
    found = measure(first, arguments.tables)

    push, done = found["spells_before_a_push"], found["spells_before_saying_done"]
    print(
        f"{arguments.tables} tables from {first}, {found['seconds']:.0f}s\n"
        f"  quiet spells that ended in a push: {push['count']}, "
        f"longest {push['longest']}, middling {push['middling']}\n"
        f"  the spell each table ended with:   {done['count']}, "
        f"longest {done['longest']}, middling {done['middling']}\n"
        f"  the examiner takes {QUIET_ANSWERS} quiet answers as done, which is "
        f"{'above' if push['longest'] < QUIET_ANSWERS else 'NOT above'} the longest working spell"
    )
    Path(arguments.save).write_text(json.dumps(found, indent=2) + "\n")
    print(f"\nwritten to {arguments.save}")


if __name__ == "__main__":
    main()
