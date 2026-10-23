"""The held-out queue, and the one way a solution's result is recorded.

Every solution in problem 4 is marked the same way: the same ordered list of
tables, the same arm minutes for the whole list, and however far down the list
it gets. This module holds that arrangement so that no solution can quietly
mark itself on a kinder list, which is the fault problem 3 found in its own
push budget when two runners disagreed about it.

Two rules are built in rather than left to each solution to remember.

**The held-out tables are measured once.** Tables numbered below ``HELD_OUT``
are for building and choosing on, and anything may be tried on them as often
as patience allows. Tables from ``HELD_OUT`` upwards are the measurement, and a
solution that is tuned by watching them stops being measured by them at all.
Problem 4 draws its own tables, seeded from its own name, so its table ten
thousand is not problem 3's table ten thousand and the two hold-outs are
separate.

**A result that is not the full measurement is not written to the result
file.** A short run during building would otherwise overwrite a committed
number with something that looks exactly like it, and nothing downstream could
tell. So the committed name is used only when the whole arrangement matches,
and every other run goes to a scratch name beside it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from contract import Solution
from open_run import ARM_BUDGET, clear_queue
from partners import TEST_SEEDS
from scoring import Repeats

# Where the held-out tables begin. The same number problem 3 uses, for the same
# reason and with no coordination needed: it is the line between the tables a
# method is built on and the tables it is judged on.
HELD_OUT = TEST_SEEDS

# How long the queue is. It is deliberately longer than any solution can finish
# inside the budget, because the throughput reading only means something while
# a solution runs out of time rather than out of tables.
QUEUE = 50

# How many times the whole queue is walked. A solution that draws its answer
# rather than computing it gives a different run each time, and one run is not
# a measurement.
RUNS = 3


def queue(first: int = HELD_OUT, tables: int = QUEUE) -> list[int]:
    """The ordered list of tables every solution is given, in that order.

    The order matters as much as the membership: two solutions are only
    comparable on the tables they both reached, and that is a prefix of this
    list rather than a sample from it.
    """
    return list(range(first, first + tables))


def judge(
    build: Callable[[], Solution],
    save: Path,
    first: int = HELD_OUT,
    tables: int = QUEUE,
    runs: int = RUNS,
    budget: float = ARM_BUDGET,
) -> dict:
    """Walk the queue ``runs`` times and write the result beside the solution.

    ``build`` makes a fresh solution for each run rather than taking one, so
    that nothing a solution learned on one run can reach the next. A solution
    that remembers tables between runs would be marking itself on the second
    walk of a list it has already seen.
    """
    full = first == HELD_OUT and tables == QUEUE and runs == RUNS and budget == ARM_BUDGET
    where = save if full else save.with_name("partial.json")
    if not full:
        print(f"not the full measurement, so this goes to {where.name} and not to {save.name}")

    repeats = Repeats()
    for walk in range(runs):
        card = repeats.run()
        started = time.perf_counter()
        run = clear_queue(build(), queue(first, tables), budget=budget)
        for result in run.results:
            card.table(result)
        print(
            f"run {walk + 1}/{runs}: {run.attempted} tables attempted, "
            f"{'the list ran out' if run.finished_the_queue else 'the clock stopped it'}, "
            f"{time.perf_counter() - started:.0f}s of laptop time"
        )

    repeats.report(where)
    return repeats.summary()
