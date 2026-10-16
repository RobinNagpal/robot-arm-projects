"""What a solution to problem 4 is, and what it is told.

This is the one file every other file in problem 4 agrees on, so it holds no
behaviour at all: only the shapes that pass between a solution and the bench.

The shape of problem 4 is a conversation rather than a question. The bench
shows the solution what the arm's own camera can see from where the jaw is
standing. The solution answers with either a path for the jaw to follow or the
statement that the table needs nothing more. Then the bench shows it what the
table looks like now. That repeats until the solution says it is done, or the
arm time runs out, or a glass goes over.

Two things follow from that shape, and both are deliberate.

**Moving to see and moving to push are the same action.** The camera is carried
by the arm, so a solution that wants a better look answers with a path that
takes the jaw somewhere it can see from. It costs arm time exactly as a push
does, which is what it would cost on a real robot.

**A look reaches only as far as the camera does.** ``seen`` holds the glasses
inside the current picture and nothing else, which is the whole difference
between this problem and problem 3. There is no call that hands over the whole
table, so a solution that wants to know what is in the far corner has to take
the arm there. Both kinds of solution are served by one look: the ones that
work from numbers read ``seen``, and the ones that work from pictures read
``picture``, and neither is given more of the table than the camera caught.

**A refusal is told to the solution, because silence is a lie.** The cell will
not drive the jaw into a glass the physics says would tip rather than slide,
and it will not follow a path it cannot follow. When either happens the arm
does not move, so without ``refused`` the next look would be identical to the
last one and the solution could not tell "my path was refused" from "my push
did nothing". Those call for opposite responses — try elsewhere, or try
harder — and a solution left guessing will waste its budget on one of them.

**Saying "done" is part of the job.** Nothing else decides when a table is
finished, so a solution that never says it is finished spends its whole budget,
and a solution that says it too early is marked on a table it left crowded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from partners import Chunk, Seen, Waypoint

# The three ways a table can end. Named rather than written out at each use,
# because two of them are failures of different kinds and the scorecard has to
# keep them apart.
SAID_DONE = "said done"
RAN_OUT = "the clock"
GLASS_OVER = "a glass went over"


@dataclass(frozen=True)
class Look:
    """Everything the arm can know at one moment."""

    picture: np.ndarray  # what the camera on the arm sees from where the jaw is now
    seen: tuple[Seen, ...]  # the glasses inside that picture, measured as problem 3 measures them
    jaw: Waypoint  # where the jaw is standing, in the same numbers a path is written in
    seconds_left: float  # arm time left in the budget
    refused: str = ""  # why the last path was not carried out, and empty when it was


@dataclass(frozen=True)
class Done:
    """The solution's own statement that the table needs nothing more.

    ``why`` is for the record and is never scored. A solution that stops
    because it cannot see what to do next should say so, because a table left
    crowded on purpose and one left crowded by mistake read identically in the
    numbers.
    """

    why: str = ""


# A solution answers with a path for the jaw, or with the end of the table.
# There is no third kind, because looking is a path like any other.
Answer = Chunk | Done


@dataclass(frozen=True)
class TableResult:
    """One table, as the bench found it when the solution stopped."""

    seed: int
    glasses: int
    pickable_at_start: int
    pickable_at_end: int
    toppled: int  # a glass that went over, which is the one kind of breakage there is
    ended_by: str  # "said done", "the clock" or "a glass went over"
    arm_seconds: float
    thinking_seconds: float
    answers: int
    interlocks: int = 0  # times the cell refused to drive the jaw into a glass that would tip

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
        pay for any path at all. Such a table is not a table the solution
        failed. It is a table the solution never got, and counting it would
        both overstate how far down the queue the solution reached and add
        every glass standing on it to the glasses it left crowded.
        """
        return self.ended_by == RAN_OUT and self.arm_seconds == 0.0


class Solution(Protocol):
    """What problem 4 asks of an approach. Four lines, and no more.

    ``name`` is what the scorecard prints. ``begin`` is called once a table,
    before anything is seen, so that a solution can forget the last table.
    ``answer`` is called with every look and returns the next path or Done.
    """

    name: str

    def begin(self, seed: int) -> None: ...

    def answer(self, look: Look) -> Answer: ...
