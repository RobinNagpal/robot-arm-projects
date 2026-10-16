"""The fitted policy, written to problem 4's contract.

The model is shown what problem 4 shows every solution -- the picture from the
camera on the arm, the readings of the glasses that picture caught, and where
the jaw is standing -- and answers with a chunk of waypoints. That is the whole
of it. There is no tour, no belief, no ranging push and no rule: those are
solution 1's, and this solution exists to find out how much of that work a
fitted model picks up from watching it.

Three things happen around the model, and none of them chooses anything.

**A chunk is pulled inside the jaw's limits.** A network can answer with any
number. ``chunks.to_waypoints`` clips the positions and heights to what the jaw
can reach and counts how often it had to. That is a limit on the actuator, not
a second attempt at the answer.

**A path has to name a glass.** ``Chunk.glass`` is an index the bench records
every action against and raises on an invalid one. Nothing in problem 4 scores
it, so this names whichever glass the path ends up nearest, out of the ones in
the picture, and zero when the camera caught nothing. ``aim`` is the end of the
path for the same reason: problem 3's scorecard measured how far a glass ended
from where it was aimed, and problem 4's does not.

**Saying "done" is read out of what the model does**, by ``bench/stopping.py``,
which explains why reading it out of the behaviour is the fair choice and why
the alternatives are not. Nothing is added to that rule and nothing in it is
overridden: the number of quiet answers is the bench's own, so every solution
reads the same one. ``teacher.py`` beside this file is the measurement that
number was set from, and ``teacher-quiet-spells.json`` is what it measured.

The rule wants one thing from the solution, and that is the tallest glass it has
*measured* on this table. A path can clear the height the jaw works at and still
sweep through a glass standing taller than it, so without that number a policy
knocking glasses over would be recorded as proposing nothing. It is a single
number read off the looks, kept for the length of a table and forgotten with it.
That is not a belief about the table: the model is never shown it, and nothing
chooses anything with it.

**``Look.refused`` is unusable by a model, and that is worth saying plainly.**
The contract does tell a solution why its last path was not carried out, and it
tells it in a sentence of English. A geometry solution reads that and tries
somewhere else; a fitted policy cannot read it at all, and nothing in the
demonstrations would have taught it what to do if it could. So a refused path
leaves this solution answering the same way again: the arm has not moved, the
clock has not advanced, the picture is the same, and the model is deterministic.
Only the bench's cap on answers breaks that loop, which is why a measurement run
must leave the clock switched on. See ``run.py``.
"""

from __future__ import annotations

import math

import chunks
import readings

from contract import Answer, Done, Look
from partners import Chunk
from stopping import Quiet, is_a_push


class Imitation:
    """A fitted chunked policy as a problem 4 solution. One table at a time."""

    name = "imitation from demonstrations"

    def __init__(self, model) -> None:
        self.model = model
        # What the wrapping around the model had to do, over every table since
        # this was built. Diagnosis rather than score; ``run.py`` reports it.
        # ``asked`` rather than ``chunks`` because ``chunks`` is the module that
        # says what a chunk is, and one name for two things reads badly.
        self.asked = 0
        self.waypoints = 0
        self.pulled_in = 0
        self.chunks_pulled_in = 0
        self.looks = 0
        self.pushes = 0
        self.begin(0)

    @property
    def quiet_for(self) -> int:
        """How many quiet answers the bench takes as "done". Read, never chosen."""
        return self.quiet.enough

    def begin(self, seed: int) -> None:
        """Forget the last table. There is nothing to forget but the quiet spell.

        The model is answered from one look and holds no belief about the table,
        which is the whole difference between this and solution 1. So the seed
        is not used, and there are only two things to reset.

        The count of quiet answers has to go, because a quiet spell at the end of
        one table would otherwise end the next one before it had started. And the
        tallest glass has to go, because it is a measurement of this table.
        """
        self.quiet = Quiet()
        self.tallest = 0.0

    def answer(self, look: Look) -> Answer:
        # The tallest glass measured so far on this table, which is what the
        # stopping rule is asked against. Taller than anything seen before only
        # grows it: a glass that has gone out of the picture is still standing.
        self.tallest = max(self.tallest, *(glass.height for glass in look.seen), 0.0)

        action = self.model.chunk(look.picture, readings.to_state(look.jaw, look.seen))
        waypoints, pulled = chunks.to_waypoints(action)
        chunk = Chunk(glass=_glass(waypoints, look), waypoints=waypoints, aim=_aim(waypoints))

        self.asked += 1
        self.waypoints += len(waypoints)
        self.pulled_in += pulled
        self.chunks_pulled_in += pulled > 0
        if is_a_push(chunk, self.tallest):
            self.pushes += 1
        else:
            self.looks += 1
        self.quiet.saw(chunk, self.tallest)

        if self.quiet.finished:
            # The model has gone quiet for long enough to be taken at its word.
            # This last path is not carried out: it is the one that completed the
            # spell, and following it would spend arm time on an answer already
            # read as "there is nothing here to move".
            return Done(self.quiet.why)
        return chunk

    def summary(self) -> dict:
        """What the wrapping did, for a run's record."""
        return {
            "chunks": self.asked,
            "looking_answers": self.looks,
            "pushing_answers": self.pushes,
            "waypoints_a_chunk": round(self.waypoints / self.asked, 1) if self.asked else 0.0,
            "chunks_pulled_inside_the_limits": self.chunks_pulled_in,
            "waypoints_pulled_inside_the_limits": self.pulled_in,
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
