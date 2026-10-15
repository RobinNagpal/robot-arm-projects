"""How a problem 4 run is marked: by the arrangement each table was left in.

Nothing here is used by a solution to decide anything, only to judge it
afterwards. Four things make this different from problem 3's scoring.

**The table is marked once, at the end.** There is no push-by-push hand-over in
problem 4, so there is nothing to mark push by push. The card takes the
``TableResult``s the bench produced and adds them up.

**The budget belongs to the queue of tables, not to one table.** Every solution
is given the same ordered list of tables and the same arm minutes, and gets as
far down the list as it gets. So how many tables were attempted is itself one
of the numbers, and the card never assumes it saw the whole list.

**Credit is counted by the glass, not only by the table.** A table counts as
separated only when every glass on it has room, which is a hard line to reach
and tells two bad solutions apart badly: one that leaves a single glass
touching on every table and one that never moved the arm both score zero
tables. So the glasses with room at the end are counted too, against every
glass on every table attempted, and against how many already had room when the
table was drawn. That is where the resolution comes from, and it is the number
that improves first while a method is being developed.

**A table that lost a glass pays no partial credit.** Its glasses are left out
of the pickable total altogether while every glass on it still counts in the
denominator. Otherwise a risky shove would become profitable, which is the one
thing the no-free-breakage rule exists to prevent.

Pickable is read from the simulator after the run, not from what the arm
measured, exactly as problem 3's scorer reads it. A score computed from noisy
measurements would move with measurement luck and with how often a solution
happened to look, and neither is the thing being marked. The rule itself is
problem 3's: ``has_room`` against the gripper's own reach, with a glass that
has gone over or left the zone simply not pickable.

What is borrowed from problem 3's scoring, and what is not: ``spread`` and
``save_tables`` are about reporting several runs and about writing rows beside
a result, and neither knows anything about pushes, so both are taken as they
are. Its ``Scorecard`` counts pushes, repeat pushes, aim error and racked
glasses. Problem 4 has none of those — it never racks a glass — so its card is
written here instead.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from contract import GLASS_OVER, RAN_OUT, SAID_DONE, TableResult
from partners import PUSHING, STANDING_TILT_DEG, Bench, has_room, in_zone

# Problem 3's scoring module, loaded from its own file rather than imported by
# name. Both problems have a module called scoring, so a bare ``import
# scoring`` is answered by whichever bench happens to be ahead on the path, and
# the answer changes with how the tests are started. Loading it by path settles
# which module is meant. Copying the two functions instead would let problem 3
# and problem 4 drift into quoting their numbers differently.
_spec = importlib.util.spec_from_file_location("pushing_scoring", PUSHING / "bench" / "scoring.py")
_pushing = importlib.util.module_from_spec(_spec)
sys.modules["pushing_scoring"] = _pushing
_spec.loader.exec_module(_pushing)

spread = _pushing.spread
save_tables = _pushing.save_tables
# The spread's own printing, borrowed with it so that a band reads the same in
# both problems' reports.
_band = _pushing._band


def pickable(bench: Bench, glass: int, margin: float = 0.0) -> bool:
    """Whether the gripper could now pick glass ``glass`` off the table.

    Three things have to hold. The glass is standing, because the hand cannot
    pick up what is lying on its side. It is inside the glass zone, because
    outside it the arm cannot reach. And it has room, by problem 3's
    ``has_room``: every neighbour's nearest edge further away than the open
    fingers of the real 2F-85 reach from the middle of the hand. Both of the
    numbers in that last test belong to the gripper, and the widths come off
    the glasses standing in the simulator. No size is written down anywhere.

    A glass that has gone over or left the zone is still an obstacle to its
    neighbours, because on a real table it, or its pieces, would be.
    """
    if bench.tilt(glass) >= STANDING_TILT_DEG:
        return False
    x, y = (float(v) for v in bench.position(glass))
    if not in_zone(x, y):
        return False
    others = [
        (*(float(v) for v in bench.position(j)), bench.glasses[j].outline.max_diameter)
        for j in bench.on_table()
        if j != glass
    ]
    return has_room(x, y, others, margin)


def pickable_on_table(bench: Bench, margin: float = 0.0) -> int:
    """How many glasses on this table could be picked, each judged against all the rest.

    Room is not a property of a pair. A narrow glass standing beside a wide one
    is crowded before the wide one is, so one touching pair can still leave one
    pickable glass, and that half step has to be visible in the count.
    """
    return sum(pickable(bench, i, margin) for i in bench.on_table())


def outcome(result: TableResult) -> str:
    """One of ``separated``, ``failed`` or ``unfinished``. The three are exclusive."""
    if result.failed:
        return "failed"
    return "separated" if result.separated else "unfinished"


class Scorecard:
    """The tables of one run, marked by the arrangement each was left in."""

    def __init__(self) -> None:
        self.results: list[TableResult] = []

    def table(self, result: TableResult) -> str:
        """Add one finished table. Returns its outcome, for a runner to print as it goes."""
        self.results.append(result)
        return outcome(result)

    @property
    def tables(self) -> list[dict]:
        """One row per table, in the order they were attempted, for ``save_tables``.

        A run's totals do not say which table a film should be made of, and a
        single table either finishes or it does not, so a film of an unusual
        table misrepresents the solution however honestly it was made.
        """
        return [
            {
                "seed": r.seed,
                "glasses": r.glasses,
                "outcome": outcome(r),
                "pickable_at_start": r.pickable_at_start,
                "pickable_at_end": r.pickable_at_end,
                "broken": r.toppled,
                "ended_by": r.ended_by,
                "interlocks": r.interlocks,
                "arm_seconds": round(r.arm_seconds, 2),
                "answers": r.answers,
            }
            for r in self.results
        ]

    def summary(self) -> dict:
        """Every number the run reports, in the shape problem 4's results.json keeps.

        Two numbers are left out rather than written as zero, because the mean
        of nothing is not zero: the arm time of a separated table when none was
        separated, and the thinking per answer when nothing was answered.
        ``spread`` drops a key that only some runs report, which is the right
        thing to happen to both.

        ``ended_by`` sums to the tables attempted, and its ``glass_over`` is
        the same count as ``outcome.failed`` reached from the other side: one
        says how the table ended, the other says what was left on it.
        """
        rows = self.results
        # A table that lost a glass is left out of both ends of the pickable
        # count, so breaking a glass pays nothing at all. Every glass on it is
        # still counted in ``glasses``, which is what the share is out of.
        clean = [r for r in rows if not r.failed]
        glasses = sum(r.glasses for r in rows)
        started = sum(r.pickable_at_start for r in clean)
        ended = sum(r.pickable_at_end for r in clean)
        separated = [r for r in rows if r.separated]
        answers = sum(r.answers for r in rows)
        result = {
            "tables_attempted": len(rows),
            "glasses": glasses,
            "outcome": {
                "separated": len(separated),
                "failed": sum(1 for r in rows if r.failed),
                "unfinished": sum(1 for r in rows if r.unfinished),
            },
            "glasses_end": {
                "pickable": ended,
                "pickable_at_start": started,
                # The honest reading, because some glasses are drawn with room
                # already. It can be negative: a solution is free to push a
                # glass into its neighbour, and clamping this would hide that.
                "gain": ended - started,
                "pickable_share": _share(ended, glasses),
                # The toppled glasses, under the name they have on a real
                # floor. The same number is not counted anywhere else.
                "broken": sum(r.toppled for r in rows),
            },
            "ended_by": {
                "said_done": sum(1 for r in rows if r.ended_by == SAID_DONE),
                "ran_out": sum(1 for r in rows if r.ended_by == RAN_OUT),
                "glass_over": sum(1 for r in rows if r.ended_by == GLASS_OVER),
            },
            # Knowing when to stop is part of the job, and stopping early is a
            # different mistake from running out of time. Neither of the two
            # groups above says this on its own.
            "said_done_while_crowded": sum(1 for r in rows if r.said_done and r.unfinished),
            # How often the cell refused to drive the jaw into a glass it
            # judged would tip. Not a fault of the solution, but a solution
            # that keeps asking for refused pushes is spending its budget on
            # nothing, and that only shows up here.
            "interlocks": sum(r.interlocks for r in rows),
            "answers": answers,
            "arm_seconds": {"total": round(sum(r.arm_seconds for r in rows), 2)},
            "thinking_seconds": round(sum(r.thinking_seconds for r in rows), 3),
        }
        if separated:
            mean = sum(r.arm_seconds for r in separated) / len(separated)
            result["arm_seconds"]["separated_mean"] = round(mean, 2)
        if answers:
            result["thinking_seconds_per_answer"] = round(result["thinking_seconds"] / answers, 4)
        return result

    def report(self, save: Path) -> None:
        """Print the summary and save it, so two solutions can be set side by side."""
        result = self.summary()
        out, end = result["outcome"], result["glasses_end"]
        ended, arm = result["ended_by"], result["arm_seconds"]
        print(f"\n{result['tables_attempted']} tables attempted, {result['glasses']} glasses\n")
        print(
            f"tables   separated {out['separated']}, failed by a topple {out['failed']}, "
            f"unfinished {out['unfinished']}"
        )
        print(
            f"glasses  pickable {end['pickable']} of {result['glasses']} "
            f"({end['pickable_share']:g}); {end['pickable_at_start']} had room at the start, "
            f"so {end['gain']:+d}; broken {end['broken']}"
        )
        print(
            f"ended    said done {ended['said_done']}, the clock {ended['ran_out']}, "
            f"a glass went over {ended['glass_over']}; "
            f"{result['said_done_while_crowded']} said done while still crowded"
        )
        print(
            f"refused  {result['interlocks']} times, at a glass the cell judged would tip rather than slide"
        )
        mean = f"{arm['separated_mean']:g} s mean" if "separated_mean" in arm else "nothing separated"
        print(f"arm      {mean} on a separated table, {arm['total']:g} s over the whole run")
        if "thinking_seconds_per_answer" in result:
            print(f"compute  {1000 * result['thinking_seconds_per_answer']:.1f} ms of thinking per answer")
        save.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nsaved to {save}")
        save_tables(save, [self.tables])


class Repeats:
    """Several evaluation runs of one solution, and the spread across them.

    Every number in this project is quoted with a spread, because one run is
    not a measurement for a solution that draws its action rather than
    computing it, and the variation between runs is sometimes wider than the
    gap between two methods::

        runs = Repeats()
        for attempt in range(5):
            card = runs.run()
            for result in walk_the_queue(solution):
                card.table(result)
        runs.report(Path("results.json"))

    A solution that answers the same way twice has nothing to repeat and uses
    ``Scorecard`` on its own.
    """

    def __init__(self) -> None:
        self.cards: list[Scorecard] = []

    def run(self) -> Scorecard:
        """A fresh scorecard for the next evaluation run."""
        self.cards.append(Scorecard())
        return self.cards[-1]

    def summary(self) -> dict:
        """Every run in full, and the spread of every number across them."""
        each = [card.summary() for card in self.cards]
        return {"runs": len(each), "spread": spread(each) if each else {}, "each": each}

    def report(self, save: Path) -> None:
        """Print the headline numbers with their spread, and save every run."""
        result = self.summary()
        wide = result["spread"]
        attempted = result["each"][0]["tables_attempted"]
        print(f"\n{result['runs']} evaluation runs, {attempted} tables attempted in the first\n")
        for line, keys in (
            ("tables ", ("outcome.separated", "outcome.failed", "outcome.unfinished")),
            ("glasses", ("glasses_end.pickable_share", "glasses_end.gain", "glasses_end.broken")),
            ("ended  ", ("ended_by.said_done", "ended_by.ran_out", "said_done_while_crowded")),
            ("run    ", ("tables_attempted", "arm_seconds.separated_mean", "thinking_seconds_per_answer")),
        ):
            shown = [f"{key.split('.')[-1]} {_band(wide[key])}" for key in keys if key in wide]
            print(f"{line}  " + ", ".join(shown))
        save.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nsaved to {save}")
        save_tables(save, [card.tables for card in self.cards])


def _share(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0
