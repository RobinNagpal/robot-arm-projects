"""One table, run as a conversation, and the queue of tables it belongs to.

This is the loop problem 4 is named after. The bench shows the solution what the
camera on the arm can see from where the jaw is standing, the solution answers
with a path for the jaw or with ``Done``, the bench carries the path out, and
the bench shows it the table again.

**A table ends in exactly three ways**, and ``TableResult.ended_by`` says which.

1. ``SAID_DONE`` — the solution answered ``Done``. Whether the table was really
   finished is a question for the scorecard, not for this loop.
2. ``RAN_OUT`` — the next path the solution asked for does not fit in the arm
   time that is left, so it is not carried out and the table stops there. A path
   is never cut short to fit.
3. ``GLASS_OVER`` — a glass went over. The table stops at once. It ends that
   table and nothing larger, and there is no free breakage.

**The budget belongs to the queue, not to one table.** Every solution is given
the same ordered list of tables and the same ``ARM_BUDGET`` of arm seconds, and
gets as far down the list as it gets. So ``clear_table`` is told the arm time
left in the whole budget, and ``clear_queue`` walks the list until there is none
left. Two numbers come out of that: how the solutions did on the tables they all
reached, which is comparable, and how many tables each attempted, which is the
throughput. A solution that clears a table in half the time of another is not
better by a smaller number; it is better by one more table.

**There is no push budget and no per-push marking, and that is the point.**
Problem 3 handed a push over one at a time, counted it, and refused one that
broke a rule. None of that is here. A path aimed badly is carried out and
whatever happens, happens, which is what makes "say when you are done" a real
part of the job rather than a formality.

**The one thing the cell still refuses is a glass that would tip.** A real cell
keeps its safety interlocks, so this one will not drive the jaw into a glass the
physics says would topple rather than slide. The arithmetic is solution 1's
``slides``, borrowed rather than rewritten, and it works from the glass's
measured foot and the plausible *range* of friction, both of which anybody could
work out. The cell's real friction stays hidden, so the interlock is not a
hidden advantage. It refuses only the glasses that rule answers "no" to; a glass
it answers "try" to is for the solution to settle with the same small test push
problem 3 uses, and that push costs arm time like any other motion. A refused
path is simply not carried out: the arm never moves, nothing is charged for it,
and the solution is shown the same table again. ``TableResult.interlocks``
counts it.

**Arm time is charged for the motion that really happened, and for all of it.**
An answer costs three things: the crossing from where the jaw was standing to
above the first waypoint, the path itself, and the lift home. A leg can stop
early, because the jaw came down on a glass or jammed against one, and the arm
only spends the seconds it really moved, so the path and the lift are charged
from the record the bench wrote rather than from the path that was commanded.

The crossing is charged here because nothing else can charge it. The bench
parks the jaw off the table and then re-places it above the next first waypoint
with no physics at all, so a move a real arm would spend seconds on leaves no
record to read. Leaving it free would be the one mistake that empties this
problem out: if crossing the table costs nothing, looking from the far corner
costs the same as looking from where the jaw already stands, and the trade that
putting the camera on the arm exists to measure disappears.

Before a path is made, what is left is weighed against the estimate — the
crossing plus what ``clock.py`` prices the commanded path at — because an
estimate is the only honest answer before the fact. A solution plans with the
same estimate.

**The jaw's pose is the runner's to carry.** The bench parks its own jaw off
the table between answers, at a height no path may use, so it cannot be asked
where the jaw "is". ``Look.jaw`` is therefore the last waypoint of the last
path carried out, and ``HOME`` at the start of a table. ``HOME`` is named once,
here, because a start pose chosen by each solution would have each one paying a
different crossing to its first path.

**A path that is only for looking still has to name a glass.** ``Chunk.glass``
is an index the bench records every action against, and it raises on one that
is not on the table. In problem 4 that index is bookkeeping and nothing scores
it, so a path made only to see from somewhere may name any glass still there.

**Arm time and thinking time are different clocks.** Thinking is wall time,
measured the way problem 3 measures it: the clock runs over the whole table and
the bench's own share, ``Bench.seconds``, is taken off, so what is left is the
solution deciding rather than the physics stepping.

**Why there is a cap on answers as well as a budget.** An answer the interlock
refuses never moves the arm, so it costs no arm time and brings the clock no
closer; a solution that never says ``Done`` and keeps answering with refused
paths would run forever. ``most_answers`` is the guard. It is read off the time
left rather than chosen, so it cannot quietly limit a solution that is spending
its arm time, and ``Tally.out_of_answers`` reports when it bound.

The loop talks to the cell through the ``Cell`` protocol below rather than to a
``Bench`` directly. That is what lets the loop be tested on its own, and it is
also where the one thing problem 3's bench does differently is handled: between
actions the bench parks the jaw off the table, so where a look is taken from is
where the solution drove the jaw to, which the loop keeps for itself.
"""

from __future__ import annotations

import math
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from types import ModuleType
from typing import Protocol

import numpy as np
from work_cell.rack.layout import GLASS_ZONE

from clock import Clock
from contract import GLASS_OVER, RAN_OUT, SAID_DONE, Done, Look, Solution, TableResult
from partners import (
    DESCEND_SPEED,
    PUSH_HEIGHT,
    STANDING_TILT_DEG,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    Bench,
    Chunk,
    Record,
    Seen,
    Waypoint,
)
from scoring import pickable_on_table

# The arm seconds a solution is given for the whole queue of tables. Ten arm
# minutes. Measured on this bench, one push-like path costs the arm a median of
# 3.9 seconds all in -- 1.2 of that the crossing to it -- so ten minutes is
# about 150 paths, which is roughly ten tables. That is enough for how far a
# solution got to be a number with some resolution in it, while a run still
# finishes in seconds of laptop time.
#
# It lives here, as one constant, rather than as an argument each solution
# defaults for itself. Problem 3 learned that the hard way: its push budget
# started life in each runner, the two that existed disagreed, and the push
# counts were not comparable until it moved into the bench.
#
# **This value is not measured yet.** It is a starting figure from the
# arithmetic above, and it is to be set from what the geometry reference really
# needs on tables below TEST_SEEDS once that solution exists.
ARM_BUDGET = 10 * 60.0

# The least arm time any action on a table can cost. The jaw rides at travel
# height between actions, so before it can touch anything it has to come down,
# and that drop is the floor under every path the bench will accept.
#
# It is what the queue stops at. A table handed over with less than this left
# could not have been acted on whatever the solution answered, so attempting it
# would make "tables attempted" say more than it knows -- and worse, a solution
# that answered ``Done`` to each of them would collect the tables that happened
# to be uncrowded already.
LEAST_ACTION = (TRAVEL_HEIGHT - PUSH_HEIGHT) / DESCEND_SPEED

# Where the jaw stands at the start of every table, named once here rather than
# by each solution, so that every solution pays the same crossing to its first
# path and is shown the same first picture.
#
# Over the middle of the glass zone, at the height the jaw crosses the table at,
# pointing away from the arm's base. Nothing in it is a measurement: the zone is
# the cell's own and travel height is the cell's own.
HOME = Waypoint(
    x=(GLASS_ZONE[0] + GLASS_ZONE[1]) / 2,
    y=(GLASS_ZONE[2] + GLASS_ZONE[3]) / 2,
    z=TRAVEL_HEIGHT,
    heading=0.0,
)


def solution_one() -> ModuleType:
    """Solution 1's geometry, imported on use rather than at the top of the file.

    Its tipping rule is borrowed rather than worked out again, because a second
    copy would be free to drift away from the one problem 3's solutions use, and
    then the two problems would refuse different glasses.

    The import is here and not with the others for a mechanical reason, the same
    one ``tables.py`` gives. ``partners`` is what puts solution 1's folder on the
    path -- that folder's name starts with a digit, so it cannot be a package and
    cannot be imported by name -- and the import sorter files a bare ``plan``
    above ``partners``, so a ``plan`` import at the top of the file would be
    reached before the path it needs existed.
    """
    import plan

    return plan


def most_answers(seconds_left: float) -> int:
    """How many answers one table may be given, as a guard against a loop.

    It is the arm time left, counted in waypoint periods, because a waypoint
    period is the least any leg of a path can cost. A solution that is really
    moving the arm therefore runs out of budget before it runs out of answers,
    so this only ever binds on answers that moved the arm nowhere.
    """
    return 1 + int(seconds_left / WAYPOINT_PERIOD)


class Cell(Protocol):
    """What the loop needs of the work cell, and nothing else.

    ``OpenCell`` below is the real one. A test, or anything replaying a saved
    table, can pass its own without a physics engine or a graphics context.
    """

    def glasses(self) -> int:
        """How many glasses were stood on this table."""

    def view(self, jaw: Waypoint) -> tuple[np.ndarray, tuple[Seen, ...]]:
        """The picture from the jaw's pose, and the glasses inside that picture."""

    def truth(self) -> tuple[Seen, ...]:
        """Every glass on the table, exactly, for the cell's own interlock."""

    def follow(self, chunk: Chunk) -> Record:
        """Carry a path out and hand back the cell's own record of the motion.

        Raises ValueError for a path the jaw cannot follow at all, in which case
        nothing moved.
        """

    def toppled(self) -> int:
        """How many glasses on the table are no longer standing."""

    def pickable(self) -> int:
        """How many glasses on the table the open hand could get round."""

    def charged(self) -> float:
        """Wall seconds the cell itself has spent so far, to take off the thinking."""


@dataclass
class Tally:
    """What the conversation cost over a run, beside what ``TableResult`` holds.

    Everything a table is marked on is in its ``TableResult``. This is the rest,
    which is diagnosis rather than score: a path the bench would not take at
    all, a table stopped by the answer guard rather than by the clock -- the two
    read alike in ``ended_by``, and they are not the same thing -- and the
    reasons, in the solution's own words, for every ``Done`` and every refusal.
    ``Done.why`` is not scored and belongs in a log, which is this.
    """

    tables: int = 0
    followed: int = 0
    refused_by_bench: int = 0  # paths ``follow()`` would not take at all
    out_of_answers: int = 0  # tables stopped by ``most_answers`` rather than by the clock
    done_because: Counter = field(default_factory=Counter)
    refused_because: Counter = field(default_factory=Counter)

    def add(self, other: Tally) -> None:
        self.tables += other.tables
        self.followed += other.followed
        self.refused_by_bench += other.refused_by_bench
        self.out_of_answers += other.out_of_answers
        self.done_because += other.done_because
        self.refused_because += other.refused_because

    def summary(self) -> dict:
        return {
            "tables": self.tables,
            "paths_followed": self.followed,
            "refused_by_the_bench": self.refused_by_bench,
            "tables_that_ran_out_of_answers": self.out_of_answers,
            "said_done_because": dict(self.done_because),
            "refused_because": dict(self.refused_because),
        }


def tips(glasses: Iterable[Seen]) -> tuple[Seen, ...]:
    """The glasses the physics says would topple rather than slide if the jaw met them.

    Solution 1's ``slides`` answers it. Only a flat "no" is refused: "try" means
    the answer depends on a friction nothing in the cell measures, and that is
    the solution's to settle with a test push, not the cell's to decide.
    """
    slides = solution_one().slides
    return tuple(glass for glass in glasses if slides(glass) == "no")


def hand_meets(chunk: Chunk, glass: Seen) -> bool:
    """Whether following this path would drag any part of the hand into this glass.

    The hand is not one shape -- rolled, it stays narrow for the first 132 mm and
    then widens to the body -- so it is checked stretch by stretch against
    ``JAW_SEGMENTS``, which is how solution 1 checks its own pushes. Nothing is
    added for luck: the question here is contact, not clearance.

    ``follow()`` turns the hand to a leg's own heading as that leg starts, and
    measures ``z`` to the middle of the jaw, so a leg is only in the way while it
    is low enough to reach the glass at all.
    """
    nudge = solution_one()
    centre = np.array([glass.x, glass.y])
    room = glass.widest / 2
    points = chunk.waypoints
    # The first pair is the first waypoint against itself: the jaw comes down
    # onto it, so it stands there before any leg moves it anywhere.
    for start, end in zip((points[0], *points[:-1]), points, strict=True):
        if min(start.z, end.z) > glass.height:
            continue
        u = np.array([math.cos(end.heading), math.sin(end.heading)])
        tip_from, tip_to = np.array([start.x, start.y]), np.array([end.x, end.y])
        # A stretch of the hand sits between ``near`` and ``far`` behind the
        # fingertips, so while the tips go from ``tip_from`` to ``tip_to`` that
        # stretch sweeps the table from ``tip_from - far`` to ``tip_to - near``.
        if any(
            nudge.segment_distance(centre, tip_from - far * u, tip_to - near * u) < half + room
            for near, far, half in nudge.JAW_SEGMENTS
        ):
            return True
    return False


def interlocked(chunk: Chunk, glasses: Iterable[Seen]) -> int | None:
    """Which tipping glass this path would reach, or None if it keeps clear of all of them.

    A glass that tips stays on the table and stays in the picture, so a solution
    can still aim at it and nothing it was trained on would warn it off. The one
    mistake problem 4 cannot absorb is a toppled glass, so a path that would
    reach one is not carried out at all.
    """
    for glass in tips(glasses):
        if hand_meets(chunk, glass):
            return glass.id
    return None


def clear_table(
    solution: Solution,
    seed: int,
    seconds_left: float,
    *,
    cell: Cell | None = None,
    tally: Tally | None = None,
) -> TableResult:
    """Run one table and report how it was left.

    ``seconds_left`` is the arm time left in the whole queue's budget, not a
    share of it set aside for this table. ``cell`` is the work cell, built from
    the draw and the camera on the arm when it is not given. ``tally``, if it is
    given, collects the diagnosis that is not part of the score.
    """
    cell = open_cell(seed) if cell is None else cell
    tally = Tally() if tally is None else tally
    clock = Clock(seconds_left)
    cap = most_answers(seconds_left)
    glasses = cell.glasses()
    pickable_at_start = cell.pickable()

    # Everything from here to the matching reading below is the table. The
    # bench's own share of it is taken off, as problem 3 takes it off, so what is
    # left is the solution thinking rather than the physics stepping.
    began, bench_had = time.perf_counter(), cell.charged()
    solution.begin(seed)

    jaw = HOME
    answers, interlocks = 0, 0
    ended_by = RAN_OUT
    while True:
        picture, seen = cell.view(jaw)
        answer = solution.answer(Look(picture=picture, seen=seen, jaw=jaw, seconds_left=clock.left))
        answers += 1

        if isinstance(answer, Done):
            ended_by = SAID_DONE
            tally.done_because[answer.why or "no reason given"] += 1
            break
        if not isinstance(answer, Chunk):
            raise TypeError(f"{solution.name} answered with {type(answer).__name__}, not a Chunk or Done")

        # What the answer is expected to cost: the crossing to it and then the
        # path, which is what ``enough_for`` weighs when it is told where the
        # jaw is standing. Both halves are estimates, because the only honest
        # answer before the fact is an estimate. A path is never cut short to
        # fit: half a push leaves the jaw standing against a glass, which is
        # worse than never starting it, so the table stops here with the path
        # never made.
        if not clock.enough_for(answer, jaw):
            break

        if interlocked(answer, cell.truth()) is not None:
            interlocks += 1
        else:
            try:
                record = cell.follow(answer)
            except ValueError as refusal:
                # Off the table, outside the heights the jaw rides at, or too
                # long. The arm never moved, so nothing is charged and nothing is
                # decided for the solution: it is shown the same table again.
                tally.refused_by_bench += 1
                tally.refused_because[str(refusal)] += 1
            else:
                # The crossing really happened and no record holds it, so it
                # is charged beside the record. The record covers the drop, the
                # legs as far as the jaw got, and the lift home, so a path
                # stopped partway through costs only what it moved.
                clock.cross(jaw, answer.waypoints[0])
                clock.charge(record)
                tally.followed += 1
                # Where the solution drove the jaw to, which is what the next
                # look is taken from. The bench's own pose cannot be used: it
                # parks the jaw off the table at a height no path may use, and
                # every look would then be from the same place, so moving to see
                # would buy nothing.
                jaw = answer.waypoints[-1]
                if cell.toppled():
                    ended_by = GLASS_OVER
                    break

        if clock.left <= 0.0:
            break
        if answers >= cap:
            tally.out_of_answers += 1
            break

    thinking = max(0.0, (time.perf_counter() - began) - (cell.charged() - bench_had))
    tally.tables += 1
    return TableResult(
        seed=seed,
        glasses=glasses,
        pickable_at_start=pickable_at_start,
        pickable_at_end=cell.pickable(),
        toppled=cell.toppled(),
        ended_by=ended_by,
        arm_seconds=clock.spent,
        thinking_seconds=thinking,
        answers=answers,
        interlocks=interlocks,
    )


@dataclass
class Run:
    """One solution's whole queue: the tables it reached, and how far it got."""

    budget: float
    seeds: tuple[int, ...]
    results: list[TableResult] = field(default_factory=list)

    @property
    def attempted(self) -> int:
        """How many tables the solution got to. The throughput half of the score."""
        return len(self.results)

    @property
    def arm_seconds(self) -> float:
        return sum(result.arm_seconds for result in self.results)

    @property
    def left(self) -> float:
        """Arm time still in the budget. Under LEAST_ACTION, no table can be acted on."""
        return self.budget - self.arm_seconds

    @property
    def finished_the_queue(self) -> bool:
        """True when the list ran out before the budget did.

        Worth knowing: a solution that cleared every table it was given is not
        being measured on throughput any more, and the queue needs to be longer
        before two such solutions can be compared.
        """
        return self.attempted == len(self.seeds)


def clear_queue(
    solution: Solution,
    seeds: Sequence[int],
    budget: float = ARM_BUDGET,
    *,
    tally: Tally | None = None,
    cell_for: Callable[[int], Cell] | None = None,
) -> Run:
    """Walk the queue of tables until the arm time runs out, and report how far it got.

    Every solution is given the same ordered list and the same budget, so this is
    the only place a run's arm time is divided up, and it is not divided up: each
    table is told what is left and may spend as much of it as it needs.
    """
    build = open_cell if cell_for is None else cell_for
    run = Run(budget=budget, seeds=tuple(seeds))
    for seed in run.seeds:
        if run.left < LEAST_ACTION:
            break
        run.results.append(clear_table(solution, seed, run.left, cell=build(seed), tally=tally))
    return run


@dataclass
class OpenCell:
    """The real work cell: problem 3's bench, with the camera the arm carries.

    ``see`` is what narrows a look to the glasses inside the picture. It is held
    as a plain callable so that the loop depends on what ``wrist.py`` does and
    not on where it keeps it.
    """

    bench: Bench
    camera: object  # anything with ``view(jaw) -> picture``
    see: Callable[[Waypoint, list[Seen]], Iterable[Seen]]

    def glasses(self) -> int:
        return len(self.bench.glasses)

    def view(self, jaw: Waypoint) -> tuple[np.ndarray, tuple[Seen, ...]]:
        """One look: the picture from the jaw's pose, and the glasses in it.

        The measurement is problem 3's, unchanged -- one ``look()`` per look, so
        the noise still comes from (seed, number of looks) -- and all problem 4
        does is throw away the glasses the camera could not see.
        """
        return self.camera.view(jaw), tuple(self.see(jaw, self.bench.look()))

    def truth(self) -> tuple[Seen, ...]:
        """Every glass on the table, exactly, with no measurement error.

        The interlock is the cell's own and asks what the physics would do to a
        glass of this size, not what one noisy look made its size look like, so
        it is answered from the simulator. It must also not go through
        ``look()``: a look advances the noise the solution is shown, so one taken
        here would change what the solution sees.
        """
        standing = []
        for i in self.bench.on_table():
            outline = self.bench.glasses[i].outline
            x, y = self.bench.position(i)
            standing.append(
                Seen(
                    id=i,
                    x=float(x),
                    y=float(y),
                    height=outline.total_height,
                    widest=outline.max_diameter,
                    foot=2 * float(outline.radius[0]),
                    standing=self.bench.tilt(i) < STANDING_TILT_DEG,
                )
            )
        return tuple(standing)

    def follow(self, chunk: Chunk) -> Record:
        """Carry the path out, and hand back what the bench wrote down about it.

        The record holds the bench's own trace of the motion, sampled one
        waypoint period apart, so a path the jaw was stopped partway through
        comes back shorter than it was commanded, and the lift home that really
        happened comes back with it. That is what the clock is charged from.
        """
        self.bench.follow(chunk)
        return self.bench.records[-1]

    def toppled(self) -> int:
        return sum(1 for i in self.bench.on_table() if self.bench.tilt(i) >= STANDING_TILT_DEG)

    def pickable(self) -> int:
        return pickable_on_table(self.bench)

    def charged(self) -> float:
        return self.bench.seconds


def open_cell(seed: int) -> OpenCell:
    """The cell for one table: the draw, the physics, and the camera on the arm.

    The draw and the camera are imported here rather than at the top of the file,
    because the loop itself needs neither. A caller that brings its own cell gets
    no renderer and no graphics context, which is what lets the loop run and be
    tested where there is no display.
    """
    import tables
    import wrist

    bench = Bench(seed, glasses=tables.table(seed))
    return OpenCell(bench, wrist.WristCamera(bench), wrist.in_picture)
