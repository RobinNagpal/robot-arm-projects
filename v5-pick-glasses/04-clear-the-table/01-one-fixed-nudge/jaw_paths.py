"""The paths this solution answers with: one to go and look, one to make a push.

Problem 3 asked for a ``Push`` -- a glass, a place to come down, a heading and
a distance -- and the bench turned that into motion itself. Problem 4's
contract takes a ``Chunk``: the jaw's own waypoints. So the shape of a push has
to be written out here, and that is most of this file.

**A path says nothing about getting to where it starts.** The cell puts the jaw
above a path's first waypoint without simulating the trip, and ``clock.py``
charges that crossing separately, at the top speed, from where the jaw was
standing. So there is no reason to write the drive across the table into the
waypoints: it would cost the same and step the physics for a second of nothing.
A path here begins at the point it is about to work at, and the trip to it is
the clock's business.

That is also why a path to go and look is one single waypoint. The whole cost
of a look somewhere else is the crossing, and the whole cost of another look
from where the jaw already stands is nothing at all.

**The waypoints are spaced so that one leg is one waypoint period.** A leg
takes ``max(WAYPOINT_PERIOD, length / TOP_SPEED)``, so putting the waypoints a
speed times a period apart is how a path asks to be carried out at that speed:
10 mm apart for coming down, 1 mm apart for pushing. ``clock.path_seconds`` is
still what prices a path; this is only why a path built here costs what its
length says it should.

**A push is a drop and one straight shove, and the shove has to be told how far
the glass is.** There is no feel-forward leg. ``follow()`` does not stop at a
touch once the jaw is moving across the table, so a slow approach would not find
the glass, it would only push it slowly; and a chunk has no feel-then-push split
to report either.

That is why ``reach`` is an argument here and not a constant. Problem 3's
planner puts the fingertips down ``APPROACH_GAP`` outside the glass's *widest*
part, and problem 3's bench then creeps forward until it feels the glass and
pushes from wherever that turned out to be -- which is what ``FEEL_BEYOND``, a
whole 30 mm of it, is for. The jaw meets a glass at the jaw's own height, and a
glass can be far narrower there than at its widest: measured across the four
families, the fingertips travel 10 to 30 mm from the touchdown point before they
meet anything, and on a stemmed glass it is the stem they meet. A chunk cannot
feel its way in, so that distance has to be known before the path is written,
and ``APPROACH_GAP`` is not it. The caller passes what it has measured by
poking the glass; see ``nudge.py``.

Coming down is its own leg and not part of the shove, and that matters: the
cell watches the force gently while the jaw is still only descending, and backs
it straight off if it meets anything. A path that moved sideways first would
have given that up.

**A path that is only a look still names a glass.** The bench records every
action against a glass index and would fail on an invalid one. In problem 4
nothing scores that index, so a look names any glass on the table; the caller
passes one.
"""

from __future__ import annotations

import math

from tour import Stand

from partners import (
    DESCEND_SPEED,
    PUSH_HEIGHT,
    PUSH_SPEED,
    TOP_SPEED,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    Chunk,
    Push,
    Waypoint,
)

from plan import APPROACH_GAP

# How far apart to put the waypoints to be carried out at each of the cell's
# speeds. A leg shorter than ``TOP_SPEED * WAYPOINT_PERIOD`` still takes a
# whole period, so a smaller step is a slower jaw.
TRAVEL_STEP = TOP_SPEED * WAYPOINT_PERIOD
DESCEND_STEP = DESCEND_SPEED * WAYPOINT_PERIOD
PUSH_STEP = PUSH_SPEED * WAYPOINT_PERIOD


def _legs(frm: Waypoint, to: tuple[float, float, float], step: float) -> list[Waypoint]:
    """The waypoints from ``frm`` to ``to``, ``step`` apart, keeping ``frm``'s heading.

    ``frm`` itself is not included, so the pieces of a path join without
    repeating a point.
    """
    length = math.dist((frm.x, frm.y, frm.z), to)
    count = max(1, math.ceil(length / step - 1e-9))
    return [
        Waypoint(
            frm.x + part * (to[0] - frm.x),
            frm.y + part * (to[1] - frm.y),
            frm.z + part * (to[2] - frm.z),
            frm.heading,
        )
        for part in (leg / count for leg in range(1, count + 1))
    ]


def to_look(stand: Stand, glass: int) -> Chunk:
    """Stand the jaw at a stand, so that the next look is taken from there.

    One waypoint, because arriving is the whole of it. The cell carries the jaw
    there, the clock charges the crossing, and the look happens from the pose
    the path ended at.
    """
    there = stand.jaw()
    return Chunk(glass=glass, waypoints=(there,), aim=(there.x, there.y))


def stay(jaw: Waypoint, glass: int) -> Chunk:
    """Stay where the jaw is, which is how to ask for one more frame of the same view.

    A waypoint at the pose the jaw is already in moves the arm nowhere, so it
    costs no arm time. That is not a trick played on the clock: a second camera
    frame from a standing arm really is free, and it is a fresh measurement
    because the bench draws new error on every look.
    """
    return Chunk(glass=glass, waypoints=(_at_travel_height(jaw),), aim=(jaw.x, jaw.y))


def to_push(jaw: Waypoint, push: Push, reach: float = APPROACH_GAP) -> Chunk:
    """Come down behind the glass and shove it.

    ``reach`` is how far past the touchdown point the fingertips have to travel
    before they meet the glass. The shove is that, plus the distance solution 1
    asked for, so the glass is given exactly what was asked for -- no more, and
    no less than ``reach`` is right.

    The default is ``APPROACH_GAP``, which is right for a glass as wide at the
    jaw's height as it is anywhere, and short for every other kind. A caller
    that has measured the glass should pass what it measured.
    """
    ahead = (math.cos(push.heading), math.sin(push.heading))
    shove = reach + push.travel
    over = Waypoint(push.start[0], push.start[1], TRAVEL_HEIGHT, push.heading)
    down = (push.start[0], push.start[1], PUSH_HEIGHT)
    end = (push.start[0] + shove * ahead[0], push.start[1] + shove * ahead[1], PUSH_HEIGHT)

    waypoints = [over, *_legs(over, down, DESCEND_STEP)]
    waypoints += _legs(waypoints[-1], end, PUSH_STEP)
    return Chunk(glass=push.glass, waypoints=tuple(waypoints), aim=push.aim)


def _at_travel_height(jaw: Waypoint) -> Waypoint:
    """The same pose, at the height the jaw travels at.

    Where the arm really is between actions: the cell lifts the jaw back to
    travel height when an action ends, and is charged for doing it, so a path
    that starts there starts where the arm stands and pays nothing to be placed.
    """
    return Waypoint(jaw.x, jaw.y, TRAVEL_HEIGHT, jaw.heading)
