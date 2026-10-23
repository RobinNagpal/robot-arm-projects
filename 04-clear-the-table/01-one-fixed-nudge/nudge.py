"""Problem 4 by geometry alone: look around, remember, push, say when it is done.

This is problem 3's solution 1 written to problem 4's contract. The part that
decides *which* glass to push, from where, which way and how far is not written
again: it is imported from problem 3's ``plan``, unchanged. What is new is
everything the overhead camera used to make unnecessary.

**Three things, and only the third is borrowed.**

1. ``tour`` -- where to stand to see the table, worked out from the camera's
   own geometry rather than guessed, and from every side rather than the
   fewest, because a glass can hide behind a glass.
2. ``remembered`` -- what has been seen, merged across looks, because one look
   is not the table.
3. ``plan`` -- problem 3's push chooser, imported. Note that ``plan`` means
   *problem 3's* planner: ``partners`` puts problem 3's solution 1 on the path,
   and this folder has the same name as that one, so a file called ``plan.py``
   here would shadow it depending on where pytest was started. Hence the names
   in this folder.

**The loop it runs.** Sweep the ring of stands; decide; push; look again; and
sweep once more before saying the table is finished.

The two kinds of looking are different on purpose, and the difference is what
the arm time goes on. After a push, one stand is enough: only one glass moved,
and the stand it should be least hidden from can be worked out from what is
already believed about the rest. Before saying a table needs nothing, one stand
is not enough, because that is a claim about every glass on the table including
the ones that were behind another glass the whole time. So the claim costs a
walk round the whole ring and the work in between does not.

**The test push is kept, and it is what makes this solution safe.** Problem 3
measured that with the hand rolled on its side almost no real glass is certainly
safe to push: the tipping rule answers "try" nearly every time. Its answer is
to shove the glass 5 mm and look -- a glass that slid has moved, one that leaned
came back -- and to refuse the glass if it cannot tell. That refusal is why
problem 3's solution 1 broke one glass in 251, and problem 4 punishes a broken
glass harder than anything else, so it is kept exactly as it was.

**The test push has a second job here, and problem 4 is what gives it one.**
Problem 3's simulator feels its way in: it creeps forward from the touchdown point
until the force sensor says it has met the glass, and only then pushes the
distance it was asked for. Thirty millimetres of ``FEEL_BEYOND`` is the
allowance for that, and it is needed, because the jaw meets a glass at the
jaw's own height where the glass can be far narrower than at its widest -- on a
stemmed glass it meets the stem. A chunk cannot feel. So the distance to the
glass has to be *measured*, and the only sense problem 4 leaves for measuring it
is the camera: push a little, look, and see how far the glass went.

That is the test push, so the test push does both jobs at once. If the glass
moved, the distance to it is now known -- the fingertips went that far and the
glass went this far -- and every later push of it is written to land it where
the planner aimed. If it did not move, there are two reasons and not one: it
leaned, or the fingertips never reached it. So the test is made again, five
millimetres deeper, until either the glass moves or the fingertips have reached
its measured middle, past which there is nothing left to be short of. Only then
is it refused. Reaching deeper costs arm time, and that is the right price: it
is the force sensor's job being done by the camera.

**Saying "done" means: every glass the arm has found has room, or the ones that
do not cannot safely be helped.** It never means the clock is nearly out. That
ending belongs to the clock, and a solution that called it "done" would be
claiming it knew when to stop when really it had run out of road.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import jaw_paths
import tour
from remembered import Remembered

from clock import crossing_seconds, path_seconds
from contract import Answer, Done, Look
from partners import in_zone

import plan

# A glass is treated as having room when it has this much more than it needs.
# Problem 3's solution 1 uses the same figure for the same reason: three
# standard deviations of the error in a measured gap, which is two positions at
# 0.5 mm and half a neighbour's width at 1.25 mm. Averaging looks makes the
# real error smaller than that, so this is the cautious side.
ROOM_MARGIN = 0.005

# How often one glass may be pushed before it is left alone. Problem 4 has no
# push budget -- the clock is the budget -- so this is not a budget either. It
# is a guard against pushing one glass round in circles when the table has
# others worth the time, and the figure is problem 3's for the same guard.
PUSHES_PER_GLASS = 4

def _furthest(glass) -> float:
    """The deepest the fingertips may be driven while feeling for this glass.

    Two bounds, and the tighter one wins.

    **Its own measured middle.** A glass is a solid of revolution, so there is
    something at its axis at every height, and fingertips at the axis have met
    it whatever its profile. That bound is also inside the corridor
    ``plan.along`` cleared for the hand, which reaches to where the glass's
    middle is meant to end up, so feeling this far never takes the hand
    anywhere the planner did not check.

    **Problem 3's own guard on the test push, which is what really binds.**
    Reaching deeper is only safe while the glass is not yet touched, and a
    camera cannot tell "not touched yet" from "touched, and leaning" -- the
    glass does not move either way. So every millimetre deeper has to be
    treated as a millimetre of lean, and ``plan`` already says how much lean is
    allowed: the angle the shove implies must stay under ``PROBE_LEAN_SHARE``
    of the angle the glass would fall past, which is set by its measured foot
    and height. Problem 3 applies that to one 5 mm probe, where it never binds.
    Here it is exactly the right bound, and it binds on every family: measured,
    it stops the fingertips 18 to 43 mm past the touchdown point where the
    glass's middle would allow 35 to 62.

    Reaching deeper than this is what put four glasses on their sides before
    the bound was here. It costs the glasses whose profile at the jaw's height
    is further in than the bound allows -- they are refused unreached, which is
    problem 3's own bias and the safe direction to be wrong in.
    """
    falls_past = math.atan2(glass.foot / 2, plan.CENTRE_OF_MASS_SHARE * glass.height)
    leaning = plan.JAW_TOP * math.tan(plan.PROBE_LEAN_SHARE * falls_past)
    return min(glass.widest / 2, leaning) + plan.APPROACH_GAP


# How far the glass has to go under the test push to count as sliding.
#
# Problem 3 asks only whether it moved at all, by ``PROBE_MOVED``, and that is
# right there: its test push is made on a glass nothing has touched, so the
# first half to two and a half millimetres go into taking up the contact and
# letting the glass settle onto its far edge, and a glass that slides still only
# creeps during the test.
#
# Here the test push is made on a glass the ranging push has already pressed
# against, so that slack is already taken up. A glass that is sliding now tracks
# the fingertips, and one that is leaning does not, so the question becomes
# whether it kept up rather than whether it budged. Measured on the stemmed
# family, a glass that answers a five-millimetre test with two millimetres is
# one a forty-millimetre push puts on its side.
#
# The tolerance is problem 3's own "it moved" figure and not a new number: keep
# up with the test push to within the distance problem 3 calls standing still.
KEPT_UP = plan.PROBE - plan.PROBE_MOVED


# How many free frames to spend trying to get a good enough look at one glass
# before giving up on it. Twice what the test push needs, so a glass that the
# camera keeps losing is let go rather than chased.
FRAMES_ALLOWED = 2 * plan.LOOKS_PER_PROBE


def _costs(jaw, path) -> float:
    """What an answer is expected to cost: the crossing to it, then the path itself.

    The same two halves the runner adds up, so that this solution's own split of
    its arm time into looking and pushing can be set beside the total the cell
    charged. It is the estimate and not the charge: nothing but the cell can say
    what really happened, and a path stopped early costs less than this.
    """
    return crossing_seconds(jaw, path.waypoints[0]) + path_seconds(path)


# The three things a path at push height can be, which is one more than problem
# 3 needed. ``RANGING`` is the one problem 4 adds: it is not an experiment about
# the glass at all, only the search for where the fingertips meet it, which
# problem 3's examiner does with its force sensor on the way in.
RANGING, TESTING, PUSHING = "ranging", "testing", "pushing"


@dataclass
class _Pushed:
    """A push that has been made and not yet looked at."""

    glass: int
    was_at: tuple[float, float]
    aim: tuple[float, float]
    doing: str  # RANGING, TESTING or PUSHING
    reach: float  # how far past the touchdown point the fingertips were driven before pushing
    asked: float  # how far the glass was meant to go once met
    furthest: float  # the deepest reach worth trying on this glass


class OneFixedNudge:
    """The geometry reference for problem 4. One table at a time; ``begin`` forgets the last."""

    name = "one fixed nudge"

    # How far the glass has to go under the test push to count as sliding. It is
    # an attribute rather than the module's constant read straight out so that a
    # solution built on this loop can say what its own test push means: this one
    # pokes a glass before testing it, so the slack is already taken up and the
    # glass has to keep up, while a solution that tests a glass nothing has
    # touched yet has to allow for the slack and ask only whether it moved.
    kept_up = KEPT_UP

    def __init__(self) -> None:
        self.begin(0)
        # Arm seconds this solution asked for, split by what it asked for them
        # for. Added up over every table since it was built, which is what the
        # calibration run reads.
        self.look_seconds = 0.0
        self.push_seconds = 0.0
        self.looks = 0
        self.pushes = 0

    # ------------------------------------------------------------ the contract

    def begin(self, seed: int) -> None:
        self.table = Remembered()
        self.to_visit: list[tour.Stand] | None = None
        self.pushed: _Pushed | None = None
        self.proven: set[int] = set()  # glasses the test push has shown really slide
        # How far past the touchdown point to drive the fingertips before the
        # push proper. It starts at the planner's own gap, grows while the
        # ranging push is still looking for the glass, and settles on what was
        # measured once the glass has been met. Not a size written down: it is
        # read off what the glass did when it was poked, during the run, and it
        # is forgotten with the table.
        self.reach_for: dict[int, float] = {}
        self.found: set[int] = set()  # glasses whose distance has been measured
        self.leave: set[int] = set()  # glasses to stop trying, with the reason below
        self.why: dict[int, str] = {}
        self.tries: Counter[int] = Counter()
        self.waited = 0
        # Whether the whole ring has been walked since the last push. Saying
        # "done" is a claim about the whole table, so it is not made until it is
        # true; working on one glass does not need it.
        self.swept = False

    def answer(self, look: Look) -> Answer:
        self.table.merge(look.seen)
        if self.to_visit is None:
            # The first thing done on a table is to walk the whole ring, because
            # nothing is known about it yet and one picture is not the table.
            return self._sweep(look)

        if self.table.down():
            # Nothing in this project stands a glass back up, and the arm does
            # not reach past one lying down. The examiner ends the table anyway;
            # saying so is for the record.
            return Done("a glass went over")

        if self.to_visit:
            return self._drive_to(look, self.to_visit.pop(0))

        if self.pushed is not None:
            waiting = self._read_the_push(look)
            if waiting is not None:
                return waiting

        return self._decide(look)

    # ------------------------------------------------------------- the deciding

    def _decide(self, look: Look) -> Answer:
        glasses = self.table.glasses()
        # "Nothing more to do about this one": it has room, and it is somewhere
        # the arm could pick it up from. Both halves are the scorecard's own
        # test, asked of the measurements instead of of the simulator, because
        # the measurements are all the arm has. ``room`` is solution 1's.
        settled = {
            glass.id
            for glass in glasses
            if in_zone(glass.x, glass.y) and plan.room(glass, glasses, ROOM_MARGIN)
        }
        # A glass that already has room must be put out of reach of the chooser.
        # It was problem 3's examiner that kept them out of the way, by racking
        # each one as soon as it had room; nothing is racked here, so without
        # this the chooser would answer with a two-millimetre nudge of a glass
        # that needed nothing, over and over, until the clock stopped it.
        push, chooser_says = self._choose(glasses, settled | self.leave)
        if push is None:
            if not self.swept:
                # Nothing left worth pushing, going by a table last looked at
                # from one side. Before saying a table needs nothing, look at it
                # from every side: a glass hidden behind a nearer one is not in
                # the picture, and the last push may have uncovered one.
                return self._sweep(look)
            return Done(self._nothing_more(glasses, settled, chooser_says))

        glass = next(each for each in glasses if each.id == push.glass)
        if plan.needs_probe(glass, self.proven):
            frame = self._another_frame(look, glass.id)
            if frame is not None:
                return frame
            if glass.id not in self.found:
                # Where the fingertips meet this glass is not known yet, and
                # until it is, nothing can be concluded from a short push: a
                # glass that did not move may not have been touched. So this
                # push is only the search for it.
                return self._make(look, plan.probe(push), RANGING)
            # Now the experiment proper: friction decides this one and nothing
            # in the cell measures it, so push the glass five millimetres and
            # look. One that is sliding keeps up with the fingertips; one that
            # is leaning does not.
            return self._make(look, plan.probe(push), TESTING)
        return self._make(look, push, PUSHING)

    def _choose(self, glasses: list, skip: set[int]) -> tuple:
        """The push to make next, and why the glasses with none have none.

        Problem 3's printed rule, imported. It is a method and not a call to
        ``plan.choose`` written into ``_decide`` because the next solution in
        this problem is this same loop with a different chooser, and this is the
        one line it has to replace. Everything around it -- the sweep, the
        belief, the ranging push, the test push, the saying done -- is the same
        work whoever picks.
        """
        return plan.choose(glasses, skip)

    def _nothing_more(self, glasses: list, settled: set[int], chooser_says: dict[int, str]) -> str:
        """Why the table is being left as it is. For the record; nothing scores it."""
        if not glasses:
            return "the whole zone was surveyed and no glass was seen"
        if len(settled) == len(glasses):
            return f"every one of the {len(glasses)} glasses has room"
        reasons = Counter(
            self.why.get(glass.id) or chooser_says.get(glass.id, "no safe push left")
            for glass in glasses
            if glass.id not in settled
        )
        spread = ", ".join(f"{count} {reason}" for reason, count in sorted(reasons.items()))
        return f"{len(settled)} of {len(glasses)} have room; the rest left alone: {spread}"

    # -------------------------------------------------------------- the looking

    def _read_the_push(self, look: Look) -> Answer | None:
        """Judge the last push once it has been looked at properly, or go on looking.

        Returns a path while it still wants another look, and None once it has
        made up its mind, so that the same answer can go on to decide.
        """
        made = self.pushed
        seen_enough = self.table.looks_of(made.glass) >= plan.LOOKS_PER_PROBE
        if not seen_enough:
            frame = self._another_frame(look, made.glass)
            if frame is not None:
                return frame
            if self.table.looks_of(made.glass) == 0:
                # Pushed, and then never seen again. Whatever happened to it,
                # pushing it again blind is the one thing not to do.
                self._leave(made.glass, "lost sight of it after pushing")
                self.pushed = None
                return None

        now = self.table.where(made.glass)
        moved = math.dist(made.was_at, now) if now is not None else 0.0
        if made.doing == RANGING:
            self._read_the_ranging(made, moved)
        elif made.doing == TESTING:
            if moved >= self.kept_up:
                self.proven.add(made.glass)
            else:
                self._leave(made.glass, "tipped when tried")
        elif moved < plan.PROBE_MOVED and self.tries[made.glass] >= PUSHES_PER_GLASS:
            # The real push moved nothing, and this glass has had its tries. The
            # cell's interlock refuses a path that would reach a tipping glass,
            # and the arm can also be stopped by jamming against one, and
            # neither is reported to a solution. A glass that will not move is
            # the same answer either way.
            self._leave(made.glass, "pushed and did not move")
        self.pushed = None
        return None

    def _another_frame(self, look: Look, glass: int) -> Answer | None:
        """One more look at a glass, or None when there is no more to gain.

        A frame from where the jaw is standing is free, so this is the cheap
        way to beat down the measurement error before trusting a 1.5 mm
        difference. If the glass is not in the current picture the arm has to
        go to a stand that can see it, which is not free.
        """
        if self.table.looks_of(glass) >= plan.LOOKS_PER_PROBE or self.waited >= FRAMES_ALLOWED:
            self.waited = 0
            return None
        self.waited += 1
        if any(each.id == glass for each in look.seen):
            return self._still(look)
        where = self.table.where(glass) or (self.pushed.aim if self.pushed else None)
        return self._drive_to(look, tour.nearest(*where)) if where else self._still(look)

    # ------------------------------------------------- the three kinds of answer

    def _sweep(self, look: Look) -> Answer:
        """Start a walk round the whole ring of stands."""
        self.to_visit = tour.ordered(look.jaw)
        self.swept = True
        return self._drive_to(look, self.to_visit.pop(0))

    def _drive_to(self, look: Look, stand: tour.Stand) -> Answer:
        path = jaw_paths.to_look(stand, self._any_glass())
        self.look_seconds += _costs(look.jaw, path)
        self.looks += 1
        return path

    def _still(self, look: Look) -> Answer:
        path = jaw_paths.stay(look.jaw, self._any_glass())
        self.look_seconds += _costs(look.jaw, path)
        self.looks += 1
        return path

    def _make(self, look: Look, push, doing: str) -> Answer:
        """Answer with a push, and set up to look at what it did."""
        moved = next(glass for glass in self.table.glasses() if glass.id == push.glass)
        reach = self.reach_for.get(push.glass, plan.APPROACH_GAP)
        path = jaw_paths.to_push(look.jaw, push, reach)
        self.push_seconds += _costs(look.jaw, path)
        self.pushes += 1
        if doing == PUSHING:
            # Only a push meant to move the glass somewhere counts against its
            # tries. Ranging and testing are questions, not attempts.
            self.tries[push.glass] += 1
        self.pushed = _Pushed(
            push.glass, self.table.where(push.glass), push.aim, doing, reach, push.travel, _furthest(moved)
        )
        # Everything measured about this glass up to now is about where it was.
        self.table.forget(push.glass)
        # A push is carried out open-loop, so the glass has to be looked at
        # again. The jaw ends up standing right behind it and facing it, so most
        # of the time it is already in the picture and the look is free; when it
        # is not, ``_another_frame`` drives to a side it should not be hidden
        # from. The whole ring is what it costs to claim the table is finished,
        # and that claim is not being made yet.
        self.to_visit = []
        self.swept = False
        self.waited = 0
        return path

    def _read_the_ranging(self, made: _Pushed, moved: float) -> None:
        """What the search for the glass found, which is a distance and never a verdict.

        A ranging push says nothing about whether the glass slides. Problem 3's
        examiner finds the glass with its force sensor on the way in and then makes
        the five-millimetre experiment from there; a chunk cannot feel, so the
        finding and the experiment have to be two separate pushes, and this is
        the first of them. Reading a verdict out of it was the bug this solution
        was built with: a glass that had not been touched looks exactly like a
        glass that leaned, and calling that "it tipped" left every stemmed glass
        on the table alone for ever.
        """
        if moved >= plan.PROBE_MOVED:
            # Met. The fingertips went ``reach + asked`` past the touchdown
            # point and the glass went ``moved`` of that, so the rest is the
            # distance to it. Every later push of this glass is written from
            # here, and lands it where the planner aimed instead of short.
            self._reach(made.glass, made.reach + made.asked - moved, made.furthest)
            self.found.add(made.glass)
        elif made.reach + plan.PROBE <= made.furthest:
            # Not met yet. Reach five millimetres deeper and look again. The
            # step is the length of the test push on purpose: whatever happens,
            # the glass cannot be shoved further than one test push by the step
            # that first touches it.
            self._reach(made.glass, made.reach + plan.PROBE, made.furthest)
        else:
            # The fingertips have been to the glass's own measured middle, and a
            # glass has something at its middle at every height, so they met it
            # and it did not move. That is problem 3's answer: it leaned.
            self._leave(made.glass, "tipped when tried")

    def _reach(self, glass: int, reach: float, furthest: float) -> None:
        """Note how far past the touchdown point the fingertips have to go to meet this glass.

        Held under ``furthest``, the glass's own measured middle, and that bound
        is what keeps the hand inside the corridor ``plan.along`` cleared: the
        fingertips then stop at or before where the planner expects the glass's
        middle to end up, which is exactly the point the planner checked the
        hand against.
        """
        self.reach_for[glass] = min(max(0.0, reach), furthest)

    def _leave(self, glass: int, why: str) -> None:
        self.leave.add(glass)
        self.why[glass] = why

    def _any_glass(self) -> int:
        """A glass index for a path that is only a look. Bookkeeping; nothing scores it."""
        return min(self.table.glasses(), key=lambda glass: glass.id).id if len(self.table) else 0
