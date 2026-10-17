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
   refuse, and one the solution can account for: the rule has a third answer,
   "it depends on the friction", and a glass it gives that answer for may be
   *probed* safely but not driven at the task until something has watched it
   move. **And the glass it names has to have somewhere to go**: a shove that
   drives its own glass into a neighbour knocks the neighbour over, and the hand
   is never anywhere near the glass that breaks, so nothing about the hand can
   catch it.

   **Travelling at any height in between is what the first walk was lost on.**
   The borrowed model learned the teacher's travelling height and swept across
   the table at it, which puts the fingers at the height of the glasses'
   shoulders and rims. Such a path meets one glass and nothing else, so a check
   that only counted glasses would pass it, and it knocks that glass over
   instead of sliding it. So the rule is about the shape of a path: across the
   table high, or across the table low, and nothing between.

**A drawn path is pulled onto those two heights before it is judged.** This
step exists because of a measurement, and without it a fitted model can never
push anything. A solution that computes its answer puts its waypoints at
exactly the pushing height, because that is the number it worked from. A
solution that *draws* its answer predicts the height, and it is out by a
centimetre or two, so every push it draws travels at a height between the two
safe ones and the rule above refuses all of them. The first walk of the fitted
imitation solution measured this exactly: its gate asked for between forty-five
and a hundred and nine shoves over twenty tables, and every single one was
refused for travelling at the height of the rims.

So an answer that fails is first tried again in the shape the rule asks for.
Every waypoint below travel height is put at the pushing height, every waypoint
near travel height is put at travel height, and where a stretch both moves
across the table and changes height a corner is inserted so that the hand
travels at the upper height and then comes straight down. The result can only
travel at one of the two safe heights, by construction, and it is then put
through the same checks as the path the solution drew: it still has to reach the
glass it names and meet no other. Pulling a waypoint onto one of those heights
can only make the hand safer, because those are the two heights the cell has an
account of, and squaring the corner removes exactly the motion the project's
own rule warns about -- a jaw moving sideways while it is still coming down.

An answer that fails even in that shape — a path that comes down low while
naming no glass, or one that would sweep a second glass on its way — is turned
into a look by raising every waypoint. That costs the same arm time as the path
the solution asked for, because the crossing and the legs are the same length,
so the solution is not charged differently for being made safe. What it loses is
the chance to have moved a glass it could not show was safe to touch.

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
from typing import NamedTuple

import numpy as np

from open_run import hand_meets, solution_one, tips
from partners import (
    JAW_HALF_HEIGHT,
    MAX_WAYPOINTS,
    PUSH_HEIGHT,
    TRAVEL_HEIGHT,
    Chunk,
    Seen,
    Waypoint,
    has_room,
    segment_distance,
)
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
UNTESTED = "the glass it names may tip rather than slide, and nothing has tested it"
MISSES_ITS_GLASS = "it comes down without reaching the glass it names"
MEETS_ANOTHER = "the hand would meet a glass it is not aimed at"
BETWEEN_THE_HEIGHTS = "it travels across the table at the height of the glasses' rims"
DRIVES_INTO_ANOTHER = "it would drive the glass it names into another glass"


class Shoves:
    """What a solution has already done to each glass on this table, and what came of it.

    One of these is kept for the length of a table and thrown away with it. It
    holds two things about each glass: **how many answers have been aimed at
    it**, and **how far it has moved since it was first measured**. Both are
    facts about this solution's own actions and about readings it has taken
    itself, so a solution is allowed to keep them, and nothing here is told to it
    by the examiner.

    They are what settles the question the tipping rule leaves open. Every glass
    this cell draws is one the rule answers "it depends on the friction" for, so
    the only way to know a glass slides is to shove it gently and watch. A glass
    this has seen move is a glass that may then be pushed at the task.

    It lives here rather than in a solution because three solutions need it and
    two of them also need the clearance rule to agree with it. An earlier version
    had the same bookkeeping written twice, and the two copies counted by
    different rules, so one of the models was shown a number at run time that
    meant something else than the number it had been fitted on.
    """

    def __init__(self) -> None:
        self.aimed: dict[int, int] = {}
        self.first_at: dict[int, tuple[float, float]] = {}

    def saw(self, glasses: tuple[Seen, ...] | list[Seen]) -> None:
        """Remember where each glass stood the first time this table showed it."""
        for glass in glasses:
            self.first_at.setdefault(glass.id, (glass.x, glass.y))

    def aimed_at(self, glass: int) -> None:
        """Count one answer aimed at this glass, whatever came of it."""
        self.aimed[glass] = self.aimed.get(glass, 0) + 1

    def shoves_at(self, glass: int) -> int:
        """How many answers have been aimed at this glass on this table."""
        return self.aimed.get(glass, 0)

    def moved(self, glass: Seen) -> float:
        """How far this glass has come since it was first measured, in metres."""
        was = self.first_at.get(glass.id)
        return 0.0 if was is None else math.dist(was, (glass.x, glass.y))

    def tested(
        self, glasses: tuple[Seen, ...] | list[Seen], room: float = CLEAR_ROOM
    ) -> tuple[int, ...]:
        """Which of these glasses this solution has watched move under its own shove.

        Moving further than the camera's own error is the evidence, because a
        reading that differs by less than that has not been shown to differ at
        all.
        """
        return tuple(
            glass.id
            for glass in glasses
            if self.shoves_at(glass.id) and self.moved(glass) > room
        )


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


def may_tip(glass: Seen) -> bool:
    """Whether the tipping rule's answer for this glass is "it depends".

    The rule gives three answers, and the cell refuses only the flat no. A glass
    it answers "try" for is one whose behaviour turns on a friction nothing in
    this cell can see, and the rule's own words say what to do about it: a probe
    is safe, and a push at the task is a gamble. So the cell lets such a glass be
    pushed, and whether it was worth pushing is the solution's to settle.

    The reference solution settles it by probing the glass and watching whether
    it moved. A solution that drives one at the task without having done that is
    gambling with the one mistake this problem cannot absorb, and the measured
    runs of the fitted solutions are what put this here: once their shoves were
    being carried out, they knocked four or five glasses over in twenty tables.
    """
    return solution_one().slides(glass) == "try"


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


def squared_off(chunk: Chunk, aimed: Seen | None = None) -> Chunk:
    """The same path with its heights pulled onto the two the cell accounts for.

    Two things happen to it, and both are repairs a solution is entitled to make
    to its own answer. Every waypoint goes to one of the two safe heights, so the
    hand can only ever be above everything or down where a shove slides a glass.
    Then, wherever one waypoint is at a different height *and* a different place
    from the one before it, a corner is put in: the hand travels at the upper of
    the two heights and comes straight down at the end of it.

    **Which of the two heights a waypoint goes to is decided by the hand and not
    by splitting the difference.** A waypoint whose fingers would come below the
    top of the glass the answer names is a waypoint the solution meant as
    contact, however badly it placed it, so it goes down to the height a shove
    works at. A waypoint whose fingers clear that glass was travelling, so it
    goes up to travel height. An answer that names no glass is all travelling and
    every waypoint goes up, which is the same thing as raising it.

    Both moves are safe in the direction that matters. A hand at one of the two
    accounted heights is a hand the cell has a rule for -- above everything, or
    down at the foot where the public tipping rule is worked out -- and a hand
    that finishes its sideways movement before it descends is what the project's
    own rule asks for, because a jaw moving sideways while it comes down is how a
    rim gets clipped. What this cannot do is make a badly aimed push well aimed,
    and it does not try: the squared path goes back through the same checks.
    """
    pulled = tuple(
        Waypoint(point.x, point.y, _height_for(point.z, aimed), point.heading)
        for point in chunk.waypoints
    )
    squared: list[Waypoint] = [pulled[0]]
    for point in pulled[1:]:
        last = squared[-1]
        moved = math.dist((last.x, last.y), (point.x, point.y)) > A_WHISKER
        dropped = abs(point.z - last.z) > A_WHISKER
        if moved and dropped:
            # Across first, at whichever height is the higher of the two, and
            # then straight down or straight up at the end of it.
            squared.append(Waypoint(point.x, point.y, max(last.z, point.z), point.heading))
        squared.append(point)
    return replace(chunk, waypoints=_in_one_line(tuple(squared)))


def _in_one_line(points: tuple[Waypoint, ...]) -> tuple[Waypoint, ...]:
    """The same path with the stretch that drives along the table made straight.

    The reference solution's shove is a straight line at one heading, every time:
    measured over its own pushes it strays from that line by nothing at all and
    the hand turns by nothing between one waypoint and the next. A drawn shove is
    different. Measured over twenty tables the fitted solutions' shoves stray
    four to six millimetres from the line between their own ends, up to thirteen
    at worst, and the hand turns by two or three degrees between waypoints.

    That matters because of how the cell carries a path out: it turns the hand to
    each leg's own heading as that leg starts. So a wandering stretch turns the
    hand while the fingers are against the glass, and a glass twisted at the foot
    goes over rather than sliding. Every toppled glass left in the fitted
    solutions' runs was a push that had passed every other check here, which is
    what points at the shape of the stretch rather than at where it goes.

    So the stretch is replaced by evenly spaced points along the straight line
    between its own first and last, all at that line's own heading. The glass it
    is aimed at, the direction, the distance and the number of waypoints are all
    the solution's own and all kept -- and the number of waypoints matters, since
    in this cell how far apart they are is how fast the jaw goes.
    """
    low = [at for at, point in enumerate(points) if point.z <= PUSH_HEIGHT + A_WHISKER]
    if len(low) < 3 or low != list(range(low[0], low[-1] + 1)):
        return points
    first, last = points[low[0]], points[low[-1]]
    along = np.array([last.x - first.x, last.y - first.y])
    length = float(np.linalg.norm(along))
    if length <= A_WHISKER:
        return points
    heading = math.atan2(float(along[1]), float(along[0]))
    steps = len(low) - 1
    straight = tuple(
        Waypoint(
            first.x + (last.x - first.x) * step / steps,
            first.y + (last.y - first.y) * step / steps,
            PUSH_HEIGHT,
            heading,
        )
        for step in range(steps + 1)
    )
    # The waypoint the hand comes down at takes the same heading, so that the
    # hand is already turned the way it will push before it touches anything.
    before = tuple(
        replace(point, heading=heading) if at == low[0] - 1 else point
        for at, point in enumerate(points[: low[0]])
    )
    return before + straight + points[low[-1] + 1 :]


def _height_for(z: float, aimed: Seen | None) -> float:
    """Which of the two safe heights a waypoint at this height belongs at.

    The fingers hang ``JAW_HALF_HEIGHT`` below the number a waypoint carries, so
    the question "was this waypoint meant to touch the glass" is whether the
    fingers would be below the top of it.
    """
    if aimed is None:
        return TRAVEL_HEIGHT
    return PUSH_HEIGHT if z - JAW_HALF_HEIGHT < aimed.height else TRAVEL_HEIGHT


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


def where_it_would_land(chunk: Chunk, glass: Seen) -> tuple[float, float]:
    """Where the glass this path pushes would end up, if it moved with the hand.

    The model is the reference solution's own, so that the two cannot disagree
    about what a push does. While the fingers are down they drive the glass
    ahead of them along the line they travel, and the fingertips never get past
    where the glass's middle lands, so the glass's middle ends where the
    fingertips end -- measured along that line and never backwards, because a
    shove that stops short of the glass moves it nowhere.
    """
    low = [point for point in chunk.waypoints if point.z <= PUSH_HEIGHT + A_WHISKER]
    if len(low) < 2:
        return (glass.x, glass.y)
    start = np.array([low[0].x, low[0].y])
    end = np.array([low[-1].x, low[-1].y])
    along = end - start
    length = float(np.linalg.norm(along))
    if length <= A_WHISKER:
        return (glass.x, glass.y)
    way = along / length
    middle = np.array([glass.x, glass.y])
    advance = max(0.0, float((end - middle) @ way))
    landed = middle + advance * way
    return (float(landed[0]), float(landed[1]))


def _would_move(chunk: Chunk, glass: Seen) -> float:
    """How far this path would move the glass, in metres.

    A probe comes to rest against the glass and moves it by nothing worth
    measuring, so this is near zero for one; a push at the task drives it tens of
    millimetres. That is what tells the two apart here, and it is read off what
    the path would *do* rather than off how long it is, because a cap on a length
    was measured once in this problem and bought nothing.
    """
    return math.dist(where_it_would_land(chunk, glass), (glass.x, glass.y))


def drives_into_another(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    aimed: Seen,
    room: float = CLEAR_ROOM,
) -> tuple[int, ...]:
    """Which glasses the pushed glass would be driven into, if any.

    This is the half of the rule the hand cannot see. Everything above asks
    where the *hand* goes; this asks where the *glass* goes, because a shove
    that slides its own glass into a neighbour knocks the neighbour over and the
    hand was never anywhere near it. The measured runs of the fitted solutions
    are what put this here: once their shoves were being carried out at all,
    they freed glasses and toppled others in the same breath.

    **A glass that already stands close to another may still be moved**, as long
    as it gets no closer. The draw leaves some glasses nearly touching, so a
    rule written as a fixed gap would refuse to touch exactly the glasses the
    task is about. The reference solution's own rule is the one used here: the
    allowed distance is the gap two glasses need, or the gap these two already
    have, whichever is smaller.
    """
    landed = np.array(where_it_would_land(chunk, aimed))
    middle = np.array([aimed.x, aimed.y])
    if float(np.linalg.norm(landed - middle)) <= A_WHISKER:
        return ()
    radius = aimed.widest / 2 + room
    hit = []
    for other in glasses:
        if other.id == aimed.id:
            continue
        centre = np.array([other.x, other.y])
        needs = radius + other.widest / 2 + room
        # No closer than it needs to be, and no closer than it already is.
        allowed = min(needs, float(np.linalg.norm(centre - middle)) - A_WHISKER)
        if segment_distance(centre, middle, landed) < allowed:
            hit.append(other.id)
    return tuple(hit)


def why_not_clear(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    target: int | None = None,
    room: float = CLEAR_ROOM,
    tested: tuple[int, ...] = (),
) -> str:
    """Why this path cannot be shown to be safe, or the empty string when it can.

    ``target`` is the glass the answer is aimed at, and passing none says the
    answer is meant to be a look. ``tested`` is the glasses this solution has
    itself watched move under a shove, which is the only thing that settles a
    glass the tipping rule is unsure about.

    The order of the tests is the order of the two rules: a path that rides high
    is a look and needs nothing else said about it, and anything lower has to be
    a push somebody can account for.
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
    # Asked after the two questions about what the path touches, because a path
    # that does not reach the glass it names, or that reaches another one, is not
    # yet a push at this glass and whether this glass may be pushed does not
    # arise. Then: may it be moved at all, and has it anywhere to go?
    if may_tip(aimed) and aimed.id not in tested and _would_move(chunk, aimed) > room:
        return UNTESTED
    if drives_into_another(chunk, glasses, aimed, room):
        return DRIVES_INTO_ANOTHER
    return ""


def driven_home(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    target: int,
    room: float = CLEAR_ROOM,
    tested: tuple[int, ...] = (),
) -> tuple[Chunk, float]:
    """The same shove carried on along its own line until the glass has room.

    ## Why a solution needs this, and what it does and does not decide

    This is the one repair here that changes how far an answer goes rather than
    where it goes, and it exists because of a measurement that nothing else can
    get round. **A single push moves a glass about thirteen millimetres**, which
    is what the reference solution's own pushes do, because that solution feels
    its way forward in small steps and frees a glass over a run of answers. A
    glass needs about seventy-six millimetres of clear space around it before the
    hand can be closed on it. And a chunked policy fitted on those pushes places
    its waypoints to within about twenty millimetres.

    Put those three numbers together and the thing a fitted policy is being asked
    to copy is smaller than its own accuracy. Measured over twenty tables, the
    shoves the fitted solution carried out moved their glass a median of **zero**
    millimetres: the drawn path stops at the near edge of the glass instead of
    driving past its middle, which is a mistake of about thirteen millimetres and
    well inside the policy's error. A shove that moves a glass nowhere frees
    nothing, however many of them are made.

    So the distance is arithmetic and the rest is not. **The model still chooses
    everything that is hard**: whether to act at all, which glass to act on, and
    which way to shove it. This takes that choice and carries the shove on along
    the model's own line, one step at a time, stopping at the first of two
    things: the glass has the room it needs, or the next step would fail one of
    the checks above. Nothing is added that is not then put through the whole
    rule again, so an extension that would sweep a second glass, drive this one
    into a neighbour, or leave the table is never made.

    It returns the answer and how far the glass would be moved by it, so that a
    run can record what the arithmetic added to what the model drew.
    """
    aimed = next((glass for glass in glasses if glass.id == target), None)
    if aimed is None or why_not_clear(chunk, glasses, target, room, tested):
        return chunk, 0.0
    low = [point for point in chunk.waypoints if point.z <= PUSH_HEIGHT + A_WHISKER]
    if len(low) < 2:
        return chunk, 0.0
    along = np.array([low[-1].x - low[0].x, low[-1].y - low[0].y])
    length = float(np.linalg.norm(along))
    if length <= A_WHISKER:
        return chunk, 0.0
    way = along / length
    # The spacing the solution itself asked for, because in this cell how far
    # apart the waypoints are is how fast the jaw goes, and a step of a
    # different size would be a push at a different speed.
    step = length / (len(low) - 1)
    best, moved = chunk, _would_move(chunk, aimed)
    carried = list(chunk.waypoints)
    last = carried[-1]
    while len(carried) < MAX_WAYPOINTS:
        if has_room(
            *where_it_would_land(best, aimed),
            [(other.x, other.y, other.widest) for other in glasses if other.id != target],
        ):
            break
        forward = np.array([last.x, last.y]) + step * way
        last = Waypoint(float(forward[0]), float(forward[1]), last.z, last.heading)
        carried.append(last)
        further = replace(chunk, waypoints=tuple(carried))
        if why_not_clear(further, glasses, target, room, tested):
            break
        best, moved = further, _would_move(further, aimed)
    return best, moved


class Kept(NamedTuple):
    """What a solution should answer with, and what had to be done to get there.

    ``why`` is empty when the answer still reaches the glass it was aimed at, and
    holds the reason it could not when the answer had to become a look. ``pulled``
    says the path was put into the shape the rule asks for rather than left as it
    was drawn. A solution counts both, because the two say different things about
    its model: a reason says the model proposed something nobody could account
    for, and a pull says the model had the right idea at the wrong height.
    """

    chunk: Chunk
    why: str
    pulled: bool


def kept_clear(
    chunk: Chunk,
    glasses: tuple[Seen, ...] | list[Seen],
    target: int | None = None,
    room: float = CLEAR_ROOM,
    tested: tuple[int, ...] = (),
) -> Kept:
    """The path to answer with, and what had to be done to it.

    Three outcomes, tried in that order. A path that can be shown to be safe as
    it was drawn comes back untouched. A path that cannot is pulled onto the two
    heights the cell accounts for and checked again, and comes back in that shape
    if the shape is enough. A path that fails even then comes back as a look —
    the same path, raised — with the reason it could not be left alone.
    """
    if not why_not_clear(chunk, glasses, target, room, tested):
        return Kept(chunk, "", False)
    aimed = next((glass for glass in glasses if glass.id == target), None)
    pulled = squared_off(chunk, aimed)
    # The reason reported is the one that finally stops the answer, and not the
    # one the drawn path failed on. Reporting the drawn one was tried first and
    # it hid what was happening: nearly every drawn shove fails on its height, so
    # every raised answer read "it travels at the height of the rims" however it
    # really came to be refused, and a run's record could not then say which rule
    # was costing a solution its pushes.
    why = why_not_clear(pulled, glasses, target, room, tested)
    return Kept(pulled, "", True) if not why else Kept(a_look(chunk), why, False)
