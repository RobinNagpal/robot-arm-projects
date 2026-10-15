"""The arm's own clock: what a path is expected to cost, and what it really cost.

Problem 4's budget is arm time and not laptop time. A budget in laptop seconds
would compare machines instead of solutions, because the same policy on a
faster laptop would be allowed more motion. Simulated arm seconds belong to the
path and the cell, so they mean the same thing on every machine.

An answer costs three things, and this module has one function for each: the
move from where the jaw was standing to above the first waypoint, which the
cell does not simulate; the path itself, which it does; and, inside that, the
difference between the path that was asked for and the path that happened.

**Three jobs, and keeping them apart is the point of this module.**

``path_seconds`` is the estimate. It prices a path a solution has written but
the arm has not carried out yet, which is what a solution plans with and what
the runner asks before it hands a path to the bench. The rule is not this
module's invention: it is ``Bench.follow()``'s own timing, read out of the
source, so that the estimate cannot slowly disagree with the cell —

- the jaw is placed one TRAVEL_HEIGHT above the first waypoint and comes down
  onto it at DESCEND_SPEED, and
- every leg after that takes ``max(WAYPOINT_PERIOD, length / TOP_SPEED)``: one
  waypoint period, unless the waypoints are so far apart that the jaw would
  have to beat its own top speed to arrive on time.

``followed_seconds`` is the charge, and it is what the budget is spent on. It
reads the path the bench wrote down as followed rather than the path that was
asked for, because the arm only ever spends the seconds it really moved.

The two differ in both directions, and both differences are the truth rather
than slack in the model:

- **An action can stop early.** The jaw comes down on a glass, or jams against
  one, and the cell stops it where it stands. Nothing after that happened, so
  nothing after that is charged. A path commanded across the whole table and
  blocked on the way down costs a fraction of its estimate.
- **An action carries its own ending.** When the path is done the cell lifts the
  jaw back to travel height, and backs it off by RETREAT first if it jammed.
  That is real motion the arm really made, so it is in the record and it is
  charged, which makes a path carried out in full cost a little more than it was
  estimated at — roughly the drop over again.
- The record is written one WAYPOINT_PERIOD apart, so the charge is the real
  seconds rounded down to that grid.

``crossing_seconds`` is the third number, and the one piece of an answer that
no record holds. Between answers the cell parks the jaw off the table and then
re-places it above the next first waypoint with no physics at all, so a move
that a real arm would spend seconds on leaves no trace to read. The clock works
it out from the two waypoints instead.

**Looking has no price of its own.** The camera is carried by the arm, so a
solution that wants a better view answers with a path that takes the jaw
somewhere it can see from, and that path is estimated and charged exactly like
any other. Moving to see is moving, and that is what it would cost on a real
robot.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from partners import DESCEND_SPEED, TOP_SPEED, TRAVEL_HEIGHT, WAYPOINT_PERIOD, Chunk, Record, Waypoint

# Either a chunk, as a solution answers with one, or the bare waypoints of a
# path — the trace inside a Record, for instance, which is a real path the jaw
# has already followed.
Path = Chunk | Sequence[Waypoint]

# The longest leg the jaw can still cover inside one waypoint period. Past it
# the waypoints are further apart than the arm can keep up with.
LEG_AT_TOP_SPEED = WAYPOINT_PERIOD * TOP_SPEED

# Where the jaw stands before a table begins, and so what the first crossing of
# a table is measured from. It is named here because it has to be named once:
# the runner carries the jaw's pose itself, since the bench parks its own jaw at
# a height no path may use, and a pose invented separately by each solution
# would make the first move cost a different amount for each of them.
#
# The flat spot is problem 3's own: the cell stands and parks the jaw over
# (0, 0.5), off the near edge of the table. That lives in problem 3 as a
# literal, in the world XML and again in _lift, so it cannot be imported and is
# restated here — test_clock.py checks this pair against where the bench really
# puts its jaw, so the copy cannot drift. The height is given as travel height
# rather than the parked height, because a solution reads this pose in
# ``Look.jaw`` and may write a path from it, and no path may start that high.
HOME = Waypoint(0.0, 0.5, TRAVEL_HEIGHT, 0.0)


def leg_seconds(length: float) -> float:
    """What one leg of a path costs: a waypoint period, or longer if the jaw cannot keep up.

    A controller eats waypoints at a fixed rate, so how far apart they are is
    how fast the jaw goes — up to the point where the arm runs out of speed to
    give, after which the leg simply takes longer.
    """
    return max(WAYPOINT_PERIOD, length / TOP_SPEED)


def path_seconds(path: Path) -> float:
    """What ``follow()`` would spend on this path if nothing stopped it. The estimate.

    This is the number to plan with and the number to check a budget against
    before an answer is carried out. It is not what the budget is charged:
    see ``followed_seconds``.

    The loop below is the shape of ``follow()``'s own loop, including the two
    places where that loop is easy to get wrong by reading the rule alone. The
    jaw turns to a leg's heading as the leg starts, so a turn costs nothing on
    its own; and a leg of no length is skipped, which matters for the leg after
    it (see the comment inside).
    """
    points = _waypoints(path)
    if not points:
        raise ValueError("an empty path costs nothing because the jaw cannot follow one; follow() refuses it")

    # Where follow() puts the jaw before anything moves: directly over the
    # first waypoint, at the height nothing on the table reaches.
    at = (points[0].x, points[0].y, TRAVEL_HEIGHT)
    total, lead_in = 0.0, True
    for point in points:
        target = (point.x, point.y, point.z)
        length = math.dist(at, target)
        if length < 1e-12:
            # follow() skips a leg of no length, and skips it before it stops
            # calling legs the lead-in. So a path whose first waypoint already
            # sits at travel height pays nothing for the drop, and its first
            # real leg is charged as the drop instead: at DESCEND_SPEED, with
            # no waypoint period under it. Short first legs are cheaper there.
            continue
        total += length / DESCEND_SPEED if lead_in else leg_seconds(length)
        lead_in = False
        at = target
    return total


def crossing_seconds(start: Waypoint, end: Waypoint) -> float:
    """The seconds to carry the jaw from where it stands to the start of its next path.

    Worked out from the two waypoints rather than read from a record, because
    there is no record of it. ``follow()`` puts the jaw above its first
    waypoint with no physics, so the cell teleports between answers and the
    move leaves nothing behind to count. A real arm would spend the time, and
    the distance at the top speed is what it would spend.

    This matters far more in problem 4 than it would in problem 3, because the
    camera is carried by the arm. If crossing the table were free, a look from
    the far corner would cost exactly what a look from where the jaw already
    stands costs, and the trade this problem exists to measure would disappear.

    Flat distance only, and nothing at all for staying put. The jaw crosses at
    travel height: the climb up to it belongs to the path that just ended and
    the drop back down belongs to the path about to start, both already
    charged, so counting either waypoint's height here would charge it twice.
    """
    return math.dist((start.x, start.y), (end.x, end.y)) / TOP_SPEED


def followed_seconds(record: Record) -> float:
    """What the arm really spent on one action, out of the bench's own record. The charge.

    ``Record.waypoints`` is where the jaw was told to be, written down one
    WAYPOINT_PERIOD apart, from the first step of the action to the last. So it
    is not only the path: it is the path as far as the jaw got, and then the
    cell's retreat and lift home. Counting the gaps between its entries is
    therefore counting the arm's own seconds, which is what the budget is for.
    """
    # The first entry is where the jaw started, so it is the gaps that are
    # time. An action the cell never stepped at all moved the arm no seconds.
    return max(len(record.waypoints) - 1, 0) * WAYPOINT_PERIOD


@dataclass
class Clock:
    """A queue of tables' arm time: what has gone, and what is left of it.

    The budget belongs to the whole ordered list of tables and not to one
    table, so one of these is kept for a run and handed down: a table ends when
    what is left reaches zero, and how far down the list a solution got is one
    of the numbers reported. ``left`` is also what a solution is told in
    ``Look.seconds_left``, and what it has to plan the rest of the table inside.

    Asking and charging are different calls on purpose. ``enough_for`` weighs a
    path the solution has just answered with, which can only be estimated;
    ``charge`` takes the record of what the bench then really did, and ``cross``
    the move to the path's start, which the bench never simulated.
    """

    budget: float
    spent: float = 0.0

    @property
    def left(self) -> float:
        """Arm time still in the budget. Never below zero: an action cannot overdraw time that is gone."""
        return max(0.0, self.budget - self.spent)

    def enough_for(self, path: Path, frm: Waypoint | None = None) -> bool:
        """Whether this answer is expected to fit in what is left, which the runner asks before following it.

        An estimate, because the only honest answer before the fact is an
        estimate. A path that is refused here never happens and costs nothing.
        ``frm`` is where the jaw is standing, and leaving it out asks about the
        path alone — which under-counts an answer that first has to cross the
        table, so the runner passes the jaw's pose.
        """
        # The path is priced first, so that a path the jaw could not follow at
        # all is refused by its own error rather than by an index.
        wanted = path_seconds(path)
        crossing = 0.0 if frm is None else crossing_seconds(frm, _waypoints(path)[0])
        return crossing + wanted <= self.left

    def cross(self, start: Waypoint, end: Waypoint) -> float:
        """Charge the move to where the next path begins, and return those seconds."""
        cost = crossing_seconds(start, end)
        self.spent += cost
        return cost

    def charge(self, record: Record) -> float:
        """Charge what the arm really did in one action, and return those seconds."""
        cost = followed_seconds(record)
        self.spent += cost
        return cost


def _waypoints(path: Path) -> tuple[Waypoint, ...]:
    return tuple(path.waypoints) if isinstance(path, Chunk) else tuple(path)
