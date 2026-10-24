"""How a problem 4 run is marked: by the arrangement each table was left in.

Nothing here is used by a solution to decide anything, only to judge it
afterwards. Four things make this different from problem 3's scoring.

**The table is marked once, at the end.** There is no push-by-push hand-over in
problem 4, so there is nothing to mark push by push. The card takes the
``ScoredTable``s the examiner produced and adds them up.

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

What is borrowed from problem 3's scoring, and what is not: ``spread`` reports
several runs and knows nothing about pushes, so problem 3 keeps it in
``common_scoring.py`` and it is taken from this problem's copy as it is.
Problem 3's own scorecard counts pushes, repeat pushes, aim error and racked
glasses. Problem 4 has none of those — it never racks a glass — so its card is
written here instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from examiner.simulation.table_simulator import TableSimulator
from examiner.simulation.taken_from_problem_3 import STANDING_TILT_DEG, has_room, in_zone, spread

# The three ways a table can end. Named rather than written out at each use,
# because two of them are failures of different kinds and the scorecard has to
# keep them apart.
SAID_DONE = "said done"
RAN_OUT_OF_TIME = "the clock"
GLASS_OVER = "a glass went over"


@dataclass(frozen=True)
class ScoredTable:
    """One table, as the examiner found it when the solution stopped."""

    seed: int
    glasses: int
    pickable_at_start: int
    pickable_at_end: int
    toppled: int  # a glass that went over, which is the one kind of breakage there is
    ended_by: str  # "said done", "the clock" or "a glass went over"
    arm_seconds: float
    thinking_seconds: float
    pushes_requested: int  # the pushes the solution asked for, refused ones included

    @property
    def said_done(self) -> bool:
        """Whether the solution stopped itself.

        This is kept apart from the other two endings because they are not the
        same failure. A solution stopped by the clock did not know when to
        stop; a solution stopped by a falling glass was never allowed to
        finish, and marking it as not knowing when to stop would be unfair.
        """
        return self.ended_by == SAID_DONE

    @property
    def separated(self) -> bool:
        """Every glass can be picked and none was broken, which is the only clean pass."""
        return self.toppled == 0 and self.pickable_at_end == self.glasses

    @property
    def failed(self) -> bool:
        """A glass went over. Unrecoverable, because broken glass leaves shards."""
        return self.toppled > 0

    @property
    def unfinished(self) -> bool:
        """Nothing was broken and the table is still crowded. Not the same as failing."""
        return not self.failed and not self.separated

    @property
    def never_reached(self) -> bool:
        """The clock ended this table before the arm moved on it even once.

        A queue's budget belongs to the whole queue, so the last table in a
        walk is handed whatever is left, and what is left can be too little to
        pay for any motion at all. Such a table is not a table the solution
        failed. It is a table the solution never got, and counting it would
        both overstate how far down the queue the solution reached and add
        every glass standing on it to the glasses it left crowded.
        """
        return self.ended_by == RAN_OUT_OF_TIME and self.arm_seconds == 0.0


def glass_is_pickable(simulator: TableSimulator, glass: int, margin: float = 0.0) -> bool:
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
    if simulator.tilt(glass) >= STANDING_TILT_DEG:
        return False
    x, y = (float(value) for value in simulator.position(glass))
    if not in_zone(x, y):
        return False
    others = [
        (
            *(float(value) for value in simulator.position(other)),
            simulator.glasses[other].outline.max_diameter,
        )
        for other in simulator.on_table()
        if other != glass
    ]
    return has_room(x, y, others, margin)


def count_pickable_glasses(simulator: TableSimulator, margin: float = 0.0) -> int:
    """How many glasses on this table could be picked, each judged against all the rest.

    Room is not a property of a pair. A narrow glass standing beside a wide one
    is crowded before the wide one is, so one touching pair can still leave one
    pickable glass, and that half step has to be visible in the count.
    """
    return sum(glass_is_pickable(simulator, i, margin) for i in simulator.on_table())


def table_outcome(table: ScoredTable) -> str:
    """One of ``separated``, ``failed`` or ``unfinished``. The three are exclusive."""
    if table.failed:
        return "failed"
    return "separated" if table.separated else "unfinished"


class RunScorecard:
    """The tables of one run, marked by the arrangement each was left in."""

    def __init__(self) -> None:
        self.scored_tables: list[ScoredTable] = []

    def add_table(self, table: ScoredTable) -> str:
        """Add one finished table. Returns its outcome, for a runner to print as it goes."""
        self.scored_tables.append(table)
        return table_outcome(table)

    @property
    def rows_per_table(self) -> list[dict]:
        """One row per table, in the order they were attempted, kept beside a result.

        A run's totals do not say which table a film should be made of, and a
        single table either finishes or it does not, so a film of an unusual
        table misrepresents the solution however honestly it was made.
        """
        return [
            {
                "seed": table.seed,
                "glasses": table.glasses,
                "outcome": table_outcome(table),
                "pickable_at_start": table.pickable_at_start,
                "pickable_at_end": table.pickable_at_end,
                "broken": table.toppled,
                "ended_by": table.ended_by,
                "arm_seconds": round(table.arm_seconds, 2),
                # Kept per table, and not only as a run total, because a walk
                # can be truncated afterwards -- a table the clock ended before
                # the arm moved is dropped from the queue -- and a total cannot
                # be truncated with it.
                "thinking_seconds": round(table.thinking_seconds, 3),
                "answers": table.pushes_requested,
            }
            for table in self.scored_tables
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
        tables = self.scored_tables
        # A table that lost a glass is left out of both ends of the pickable
        # count, so breaking a glass pays nothing at all. Every glass on it is
        # still counted in ``glasses``, which is what the share is out of.
        tables_without_breakage = [table for table in tables if not table.failed]
        glass_count = sum(table.glasses for table in tables)
        pickable_at_start = sum(table.pickable_at_start for table in tables_without_breakage)
        pickable_at_end = sum(table.pickable_at_end for table in tables_without_breakage)
        separated_tables = [table for table in tables if table.separated]
        pushes_requested = sum(table.pushes_requested for table in tables)
        summary = {
            "tables_attempted": len(tables),
            "glasses": glass_count,
            "outcome": {
                "separated": len(separated_tables),
                "failed": sum(1 for table in tables if table.failed),
                "unfinished": sum(1 for table in tables if table.unfinished),
            },
            "glasses_end": {
                "pickable": pickable_at_end,
                "pickable_at_start": pickable_at_start,
                # The honest reading, because some glasses are drawn with room
                # already. It can be negative: a solution is free to push a
                # glass into its neighbour, and clamping this would hide that.
                "gain": pickable_at_end - pickable_at_start,
                "pickable_share": _rounded_fraction(pickable_at_end, glass_count),
                # The toppled glasses, under the name they have on a real
                # floor. The same number is not counted anywhere else.
                "broken": sum(table.toppled for table in tables),
            },
            "ended_by": {
                "said_done": sum(1 for table in tables if table.ended_by == SAID_DONE),
                "ran_out": sum(1 for table in tables if table.ended_by == RAN_OUT_OF_TIME),
                "glass_over": sum(1 for table in tables if table.ended_by == GLASS_OVER),
            },
            # Knowing when to stop is part of the job, and stopping early is a
            # different mistake from running out of time. Neither of the two
            # groups above says this on its own.
            "said_done_while_crowded": sum(1 for table in tables if table.said_done and table.unfinished),
            "answers": pushes_requested,
            "arm_seconds": {"total": round(sum(table.arm_seconds for table in tables), 2)},
            "thinking_seconds": round(sum(table.thinking_seconds for table in tables), 3),
        }
        if separated_tables:
            mean = sum(table.arm_seconds for table in separated_tables) / len(separated_tables)
            summary["arm_seconds"]["separated_mean"] = round(mean, 2)
        if pushes_requested:
            summary["thinking_seconds_per_answer"] = round(summary["thinking_seconds"] / pushes_requested, 4)
        return summary


class ScorecardsOverRuns:
    """Several evaluation runs of one solution, and the spread across them.

    Every number in this project is quoted with a spread, because one run is
    not a measurement for a solution that draws its action rather than
    computing it, and the variation between runs is sometimes wider than the
    gap between two methods::

        scorecards = ScorecardsOverRuns()
        for run_index in range(3):
            scorecard = scorecards.new_scorecard()
            for result in run_solution_down_table_list(solution):
                scorecard.add_table(result)
        summary = scorecards.summary()
    """

    def __init__(self) -> None:
        self.scorecards: list[RunScorecard] = []

    def new_scorecard(self) -> RunScorecard:
        """A fresh scorecard for the next evaluation run."""
        self.scorecards.append(RunScorecard())
        return self.scorecards[-1]

    def summary(self) -> dict:
        """Every run in full, and the spread of every number across them."""
        summaries = [scorecard.summary() for scorecard in self.scorecards]
        return {"runs": len(summaries), "spread": spread(summaries) if summaries else {}, "each": summaries}


def _rounded_fraction(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0
