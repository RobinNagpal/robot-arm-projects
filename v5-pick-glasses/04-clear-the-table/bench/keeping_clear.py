"""Keeping the hand clear of a glass it was never aimed at, as a solution's own check.

A solution to problem 4 answers with a path for the jaw, and the cell carries
that path out whatever it runs into. This module is the arithmetic a solution
can run over its own answer **before** handing it over, so that the only glass
the hand can reach is the one the answer was aimed at. It exists because the
measured runs showed that most of the broken glasses in this problem were not
broken by a badly aimed push. They were broken while the arm was travelling.

**Why travelling breaks glasses.** A waypoint's ``z`` is the middle of the
hand, and the fingers hang ``JAW_HALF_HEIGHT`` below that middle. The glasses
this problem draws stand between about a hundred and about two hundred and
twenty millimetres tall. So a path whose waypoints sit well above the height a
push happens at can still drag the fingers through the top of every tall glass
it passes, and a solution reading its own answer back as "this did not come
down to pushing height, so it touched nothing" is reading it wrongly.

**Why the cell does not save a solution from this.** The cell keeps one
interlock, and it is narrow on purpose: it refuses a path that would reach a
glass the public tipping rule says would topple rather than slide. A glass that
rule allows may still be knocked over by a hand sweeping through it, and the
cell carries such a path out. Everything the interlock does not cover is the
solution's own to avoid, which is what this module is for. **Nothing in the
examiner calls anything here.** The bench holds it because every solution can
reach the bench's modules, and the arithmetic is the same arithmetic for all of
them.

**Two shapes of answer, and nothing else.** The rule this module applies is
that an answer is either of two things.

1. **A look.** Every waypoint rides at ``TRAVEL_HEIGHT``, which nothing on the
   table reaches, so the path cannot touch a glass however far it travels. Where
   it goes is the solution's business; that it is safe is arithmetic.
2. **A push at one named glass.** The path travels across the table only at the
   height the jaw pushes at, where a shove goes through a glass's foot and
   slides it; it comes down to that height straight, which the cell watches the
   force through; and the hand is then checked stretch by stretch against every
   glass the solution has measured, so that it reaches the glass it names and no
   other. The glass it names also has to be one the tipping rule does not flatly
   refuse.

   **Travelling at any height in between is what the first walk was lost on.**
   The borrowed model learned the teacher's travelling height and swept across
   the table at it, which puts the fingers at the height of the glasses'
   shoulders and rims. Such a path meets one glass and nothing else, so a check
   that only counted glasses would pass it, and it knocks that glass over
   instead of sliding it. So the rule is about the shape of a path: across the
   table high, or across the table low, and nothing between.

An answer that is neither — a path that comes down low while naming no glass,
or one that would sweep a second glass on its way — is turned into a look by
raising every waypoint. That costs the same arm time as the path the solution
asked for, because the crossing and the legs are the same length, so the
solution is not charged differently for being made safe. What it loses is the
chance to have moved a glass it could not show was safe to touch.

**The measured glasses are what the check can see, so it leaves room.** Every
reading carries the camera's error, about half a millimetre on a position and
two and a half on a width, so each glass is grown by ``CLEAR_ROOM`` before the
hand is checked against it. That is also why rule 1 is written against travel
height and not against the tallest glass seen so far: a glass the arm has not
looked at yet is in no list at all, and a path that keeps to a height belonging
to the cell is safe without appealing to any measurement.
"""

from __future__ import annotations

import math
from dataclasses import replace

from open_run import hand_meets, tips
from partners import PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Seen, Waypoint
from stopping import A_WHISKER

# How much a glass is grown by before the hand is checked against it, so that a
# path counted as clear is still clear when the reading was a little off. Four
# millimetres covers several standard deviations of a position reading and most
# of a width reading; it is a number about the camera and not about any glass.
CLEAR_ROOM = 0.004

# The five ways an answer fails the rule. They are written without a glass's
# number in them so that a solution can count them over a whole run and see
# which part of the rule its model keeps failing; a solution that wants to say
# which glass it was can read that off the answer it was about to give.
AIMED_AT_NOTHING = "it comes down from travel height while it is aimed at no glass"
NOT_MEASURED = "the glass it names has not been measured on this table"
WOULD_TIP = "the glass it names would tip rather than slide"
MISSES_ITS_GLASS = "it comes down without reaching the glass it names"
MEETS_ANOTHER = "the hand would meet a glass it is not aimed at"
BETWEEN_THE_HEIGHTS = "it travels across the table at the height of the glasses' rims"


def with_room(glass: Seen, room: float = CLEAR_ROOM) -> Seen:
    """The same glass, grown by ``room`` in every direction.

    The width is grown by twice the room because the check works from the
    glass's half-width, and the height by the room itself because the check
    compares the underside of the hand with the top of the glass.
    """
    return replace(glass, widest=glass.widest + 2 * room, height=glass.height + room)


def meets(chunk: Chunk, glass: Seen, room: float = CLEAR_ROOM) -> bool:
    """Whether following this path would bring any part of the hand into this glass.

    The arithmetic is the cell's own ``hand_meets``, borrowed rather than
    written again, so a solution's check and the cell's interlock can never
    disagree about what the hand sweeps. The only difference is the room.
    """
    return hand_meets(chunk, with_room(glass, room))


def met_by(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    ignoring: tuple[int, ...] = (),
    room: float = CLEAR_ROOM,
) -> tuple[int, ...]:
    """Which of these glasses the path would reach, leaving out the ones named."""
    return tuple(
        glass.id for glass in glasses if glass.id not in ignoring and meets(chunk, glass, room)
    )


def would_tip(glasses: tuple[Seen, ...] | list[Seen]) -> tuple[int, ...]:
    """Which of these glasses the public tipping rule flatly refuses to have pushed."""
    return tuple(glass.id for glass in tips(glasses))


def a_look(chunk: Chunk) -> Chunk:
    """The same path with every waypoint raised to travel height.

    Where the path goes across the table and which way the hand points are kept,
    because they are what the solution asked for and they are what the next
    picture is taken from. Only the height changes, and at travel height the
    hand is above everything the draw can put on the table.
    """
    return replace(
        chunk,
        waypoints=tuple(
            Waypoint(point.x, point.y, TRAVEL_HEIGHT, point.heading) for point in chunk.waypoints
        ),
    )


def travels_between_the_heights(chunk: Chunk) -> bool:
    """Whether the hand moves across the table at any height between the two safe ones.

    This is the part of the rule that the first walk of the held-out queue was
    lost on, and it is a rule about the *shape* of a path rather than about what
    stands on the table. There are exactly two heights at which the hand may
    travel across the table. At travel height it is above everything. At the
    pushing height it is down where a shove goes through a glass's foot and
    slides it, which is the only contact the tipping rule is worked out for.
    Between the two the hand is at the height of the glasses' shoulders and
    rims, and a hand that arrives there sideways tips a glass over instead of
    moving it -- which is what the borrowed model's answers did twenty times in
    fifty tables.

    Going straight up or straight down is not travelling, so a descent onto a
    spot is allowed at any height: the cell watches the force while the jaw is
    coming down and backs it off the moment it touches anything.

    Why this has to be a rule about shape and not a check against the glasses:
    the hand-against-glass arithmetic treats the hand as a long box and a glass
    as a disc, and at the touchdown point of a perfectly ordinary push the box
    is already within a finger's width of the disc. So it cannot answer "would
    this path press on the glass up high"; only the shape of the path can.
    """
    for start, end in zip(chunk.waypoints, chunk.waypoints[1:], strict=False):
        if math.dist((start.x, start.y), (end.x, end.y)) <= A_WHISKER:
            continue
        lowest, highest = min(start.z, end.z), max(start.z, end.z)
        at_the_table = highest <= PUSH_HEIGHT + A_WHISKER
        in_the_air = lowest >= TRAVEL_HEIGHT - A_WHISKER
        if not at_the_table and not in_the_air:
            return True
    return False


def rides_high(chunk: Chunk) -> bool:
    """Whether every waypoint on this path is at the height the jaw travels at.

    This is the test for rule 1, and it is written against travel height rather
    than against the tallest glass measured so far on purpose. A glass the arm
    has not looked at yet is not in any list, and a glass it has looked at was
    measured with an error. Travel height is a number belonging to the cell
    which nothing on the table reaches, so a path that keeps to it is safe
    without any appeal to what has been seen.
    """
    return all(point.z >= TRAVEL_HEIGHT - A_WHISKER for point in chunk.waypoints)


def why_not_clear(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    target: int | None = None,
    room: float = CLEAR_ROOM,
) -> str:
    """Why this path cannot be shown to be safe, or the empty string when it can.

    ``target`` is the glass the answer is aimed at, and passing none says the
    answer is meant to be a look. The order of the tests is the order of the two
    rules: a path that rides high is a look and needs nothing else said about it,
    and anything lower has to be a push somebody can account for.
    """
    if rides_high(chunk):
        return ""
    if travels_between_the_heights(chunk):
        return BETWEEN_THE_HEIGHTS
    if target is None:
        return AIMED_AT_NOTHING
    aimed = next((glass for glass in glasses if glass.id == target), None)
    if aimed is None:
        return NOT_MEASURED
    if aimed.id in would_tip(glasses):
        return WOULD_TIP
    if not meets(chunk, aimed, room):
        return MISSES_ITS_GLASS
    if met_by(chunk, glasses, ignoring=(target,), room=room):
        return MEETS_ANOTHER
    return ""


def kept_clear(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    target: int | None = None,
    room: float = CLEAR_ROOM,
) -> tuple[Chunk, str]:
    """The path to answer with, and why it had to be changed if it did.

    A path that can be shown to be safe comes back as it was given, with an
    empty reason. Any other comes back as a look — the same path, raised — with
    the reason it could not be left alone, which the solution records.
    """
    why = why_not_clear(chunk, glasses, target, room)
    return (chunk, "") if not why else (a_look(chunk), why)
