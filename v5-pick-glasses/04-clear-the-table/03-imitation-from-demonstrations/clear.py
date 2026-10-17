"""The fitted gate and the fitted policy, written to problem 4's contract.

Two models answer here, each with one job. The **gate** is shown what problem 4
shows every solution -- the picture from the camera on the arm, the readings of
the glasses it caught, and where the jaw is standing -- plus three numbers this
solution keeps about its own behaviour on this table, and it says which of four
kinds of answer to give and which glass to give it at. The **policy** is then
shown the same thing plus that decision, and draws the path. ``gate.py`` says
why the two are apart: fitted as one model, the average of a look and a push is
a look, and the first held-out walk of this solution freed no glasses at all.

Four things happen around the two models, and none of them chooses what to do.

**A chunk is pulled inside the jaw's limits.** A network can answer with any
number. ``chunks.to_waypoints`` clips the positions and heights to what the jaw
can reach and counts how often it had to. That is a limit on the actuator, not
a second attempt at the answer.

**A push is drawn in its own glass's frame.** The gate names the glass, so the
policy draws the path measured from it and this adds the glass's place back on.
``chunks.py`` says why: measured from the glass, one shove is one answer
wherever the glass stands.

**An answer that cannot be shown to be safe is raised to travel height.** That
is ``keeping_clear``, which every solution in this problem can run over its own
answer, and the reason it is here is measured: of the glasses this problem broke
on its first walks, most were broken by a hand travelling at the height of the
glasses' rims rather than by a push aimed badly. A raised answer costs the same
arm time and touches nothing, so the model still chooses every answer and only
the ones nobody can account for are carried out differently from how they were
drawn.

**Saying "done" is the gate's to say, with the bench's rule left as a backstop.**
The teacher's own declarations are in the demonstrations, so the gate is fitted
on them, and a table ends when the gate says it is finished. ``bench/stopping.py``
is still consulted, because a gate that never says "done" would otherwise spend
the whole queue's budget on one table; it now ends a table far less often than
the gate does, and the two reasons are counted apart.

The rule wants one thing from the solution, and that is the tallest glass it has
*measured* on this table. A path can clear the height the jaw works at and still
sweep through a glass standing taller than it, so without that number a policy
knocking glasses over would be recorded as proposing nothing. It is a single
number read off the looks, kept for the length of a table and forgotten with it.

**``Look.refused`` is unusable by a model, and that is worth saying plainly.**
The contract does tell a solution why its last path was not carried out, and it
tells it in a sentence of English. A geometry solution reads that and tries
somewhere else; a fitted policy cannot read it at all, and nothing in the
demonstrations would have taught it what to do if it could. What breaks the loop
that would otherwise follow is the three numbers the gate is given about this
solution's own behaviour: an answer that moved the arm nowhere still counts as an
answer, so the gate's input changes even when the picture does not.
"""

from __future__ import annotations

import math
from collections import Counter

import chunks
import readings

from contract import Answer, Done, Look
from keeping_clear import kept_clear
from partners import Chunk
from stopping import Quiet, is_a_push


class Imitation:
    """A fitted gate and a fitted chunked policy as a problem 4 solution."""

    name = "imitation from demonstrations"

    def __init__(self, model, decider) -> None:
        self.model = model
        self.decider = decider
        # What the wrapping around the two models had to do, over every table
        # since this was built. Diagnosis rather than score; ``run.py`` reports
        # it. ``asked`` rather than ``chunks`` because ``chunks`` is the module
        # that says what a chunk is, and one name for two things reads badly.
        self.asked = 0
        self.waypoints = 0
        self.pulled_in = 0
        self.chunks_pulled_in = 0
        self.looks = 0
        self.pushes = 0
        self.raised: Counter = Counter()
        self.decided: Counter = Counter()
        self.said_done = 0
        self.went_quiet = 0
        self.begin(0)

    @property
    def quiet_for(self) -> int:
        """How many quiet answers the bench takes as "done". Read, never chosen."""
        return self.quiet.enough

    def begin(self, seed: int) -> None:
        """Forget the last table, which is the quiet spell and what it has been doing.

        The models are answered from one look and hold no belief about the table,
        which is the whole difference between this and solution 1. So the seed is
        not used, and what is reset is this solution's own history: the count of
        quiet answers, the tallest glass measured, and the three numbers the gate
        is given about how this table has gone so far.
        """
        self.quiet = Quiet()
        self.tallest = 0.0
        self.answers = 0
        self.since_touch = 0
        self.travelled = 0.0
        self.jaw_was: tuple[float, float] | None = None

    def answer(self, look: Look) -> Answer:
        # The tallest glass measured so far on this table, which is what the
        # stopping rule is asked against. Taller than anything seen before only
        # grows it: a glass that has gone out of the picture is still standing.
        self.tallest = max(self.tallest, *(glass.height for glass in look.seen), 0.0)

        state = readings.to_state(look.jaw, look.seen)
        itself = readings.about_itself(self.answers, self.since_touch, self.travelled)
        kind, slot = self.decider.decide(look.picture, readings.to_gate(state, itself))
        slots = readings.in_slots(look.seen)
        target = slots[slot] if slot < len(slots) else None
        if kind in (readings.PROBE, readings.PUSH) and target is None:
            # The gate asked for a push at a glass that is not in this picture.
            # Nothing can be aimed at a glass nobody can see, so the answer is
            # taken as a look, which is what the solution does when it has
            # nothing to act on. Counted, because a gate doing this often is a
            # gate that has not learned the slots.
            self.decided["asked for a glass that is not in the picture"] += 1
            kind, target = readings.LOOK, None
        self.decided[readings.KINDS[kind]] += 1
        if kind == readings.DONE:
            self.said_done += 1
            return Done("the gate says this table needs nothing more")

        condition = readings.conditioning(kind, target)
        action = self.model.chunk(look.picture, readings.to_asked(state, itself, condition))
        origin = (target.x, target.y) if target is not None else (0.0, 0.0)
        waypoints, pulled = chunks.to_waypoints(action, origin)
        chunk = Chunk(
            glass=target.id if target is not None else _glass(waypoints, look),
            waypoints=waypoints,
            aim=_aim(waypoints),
        )
        # The answer the gate called a look is checked as a look, which is to say
        # it has to ride at travel height; the answer it aimed at a glass is
        # checked as a push at that glass. So the check asks of each answer what
        # the solution itself claimed it was.
        chunk, why = kept_clear(chunk, look.seen, target=None if kind == readings.LOOK else chunk.glass)
        if why:
            self.raised[why] += 1

        self.asked += 1
        self.waypoints += len(chunk.waypoints)
        self.pulled_in += pulled
        self.chunks_pulled_in += pulled > 0
        touched = is_a_push(chunk, self.tallest)
        if touched:
            self.pushes += 1
        else:
            self.looks += 1
        self._count(chunk, touched)
        self.quiet.saw(chunk, self.tallest)

        if self.quiet.finished:
            # The gate has not said the table is finished and the answers have
            # stopped touching anything for long enough that the bench's rule
            # takes the solution at its word. This last path is not carried out:
            # following it would spend arm time on an answer already read as
            # "there is nothing here to move".
            self.went_quiet += 1
            return Done(self.quiet.why)
        return chunk

    def _count(self, chunk: Chunk, touched: bool) -> None:
        """Keep the three numbers the gate is given about this solution's own behaviour.

        The same three the demonstrations were recorded with, kept the same way:
        answers on this table, answers since the last one that could touch a
        glass, and how far the jaw has travelled since then.
        """
        self.answers += 1
        last = chunk.waypoints[-1]
        if self.jaw_was is not None:
            self.travelled += math.dist(self.jaw_was, (last.x, last.y))
        self.jaw_was = (last.x, last.y)
        if touched:
            self.since_touch = 0
            self.travelled = 0.0
        else:
            self.since_touch += 1

    def summary(self) -> dict:
        """What the wrapping did, for a run's record."""
        return {
            "chunks": self.asked,
            "looking_answers": self.looks,
            "pushing_answers": self.pushes,
            "waypoints_a_chunk": round(self.waypoints / self.asked, 1) if self.asked else 0.0,
            "chunks_pulled_inside_the_limits": self.chunks_pulled_in,
            "waypoints_pulled_inside_the_limits": self.pulled_in,
            "the_gate_decided": dict(self.decided.most_common()),
            "answers_raised_to_travel_height": dict(self.raised.most_common()),
            "tables_the_gate_finished": self.said_done,
            "tables_the_quiet_rule_finished": self.went_quiet,
            "quiet_answers_taken_as_done": self.quiet_for,
            "tallest_glass_measured": round(self.tallest, 4),
        }


def _glass(waypoints: tuple, look: Look) -> int:
    """A glass index for the bench's bookkeeping. Nothing in problem 4 scores it.

    The nearest glass by its measured edge to where the path ends, which is
    problem 3's own convention for reading a glass back off a chunk. Zero when
    the camera caught nothing, because an index still has to be valid and a
    table always has a glass numbered zero.
    """
    if not look.seen:
        return 0
    last = waypoints[-1]
    return min(look.seen, key=lambda g: math.dist((g.x, g.y), (last.x, last.y)) - g.widest / 2).id


def _aim(waypoints: tuple) -> tuple[float, float]:
    """Where the path ends, flat. The bench wants an aim and problem 4 never reads one."""
    return (waypoints[-1].x, waypoints[-1].y)
