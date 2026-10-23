"""Tests for the film: that it changes no result, and that it says the right thing.

A film exists to be looked at, so most of what makes one good cannot be
tested: whether the arm's own picture is readable in the corner, whether the
writing is short enough, whether a viewer can follow what happened. Those are
checked by making a film and watching it.

Two things can be tested, and both would be wrong silently.

**A film must not change the table.** The whole claim a film makes is that it
shows the run that was scored. If filming moved the physics, or advanced the
measurement noise, or spent arm time, then every film would be of a different
run from the one in the results file and nothing in either would say so. So the
first test runs one table twice, once with the plain cell and once with the
filmed one, and asks for the same result.

**A film's last picture must agree with the scorecard.** It is the one place a
film states a number, so it is read off the result the loop handed back, and
the second test holds the words against the three ways a table can end.

The first test needs the physics and a graphics context, which is why the rest
of this folder's tests use a cell of their own. It is worth it here: what is
being checked is exactly that the real cell and the filmed real cell agree, and
no stand-in for either could show that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from contract import GLASS_OVER, RAN_OUT, SAID_DONE, Done, Look, TableResult
from film import filmed_cell, outcome_lines
from open_run import HOME, clear_table, open_cell
from partners import PUSH_HEIGHT, Chunk, Waypoint

# The table both runs are done on, and how long they are given. One table below
# the held-out band, because a test is not a measurement, and enough arm time
# for the two answers below and no more than that.
TABLE = 7
ROOM = 60.0


@dataclass
class Scripted:
    """A solution that answers from a list. The film is what is being tested, not a solution."""

    answers: list[object]
    name: str = "scripted"

    def begin(self, seed: int) -> None:
        self.asked = 0

    def answer(self, look: Look) -> object:
        at = min(self.asked, len(self.answers) - 1)
        self.asked += 1
        return self.answers[at]


def a_push() -> Chunk:
    """A short push across the middle of the glass zone, from where the jaw starts."""
    start, across = (HOME.x, HOME.y), 0.04
    steps = max(1, round(across / 0.005))
    points = tuple(
        Waypoint(start[0] + across * i / steps, start[1], PUSH_HEIGHT, 0.0) for i in range(steps + 1)
    )
    return Chunk(glass=0, waypoints=points, aim=(start[0] + across, start[1]))


def scripted() -> Scripted:
    """The same two answers both runs are given: one push, and then "finished"."""
    return Scripted([a_push(), Done("seen enough")])


def test_filming_a_table_changes_nothing_about_it(tmp_path):
    """The same table, run plainly and run filmed, comes out the same.

    Everything the scorecard reads is compared. Thinking time is not, because
    it is wall time and no two runs of anything agree on it.
    """
    plain = open_cell(TABLE)
    try:
        without = clear_table(scripted(), TABLE, ROOM, cell=plain)
    finally:
        plain.camera.close()

    filmed = filmed_cell(TABLE, "a test")
    try:
        with_film = clear_table(scripted(), TABLE, ROOM, cell=filmed)
    finally:
        filmed.simulator.save(tmp_path / "film.mp4")
        filmed.close()

    for field_name in (
        "seed",
        "glasses",
        "pickable_at_start",
        "pickable_at_end",
        "toppled",
        "ended_by",
        "answers",
        "interlocks",
    ):
        assert getattr(without, field_name) == getattr(with_film, field_name), field_name
    # Arm time is a sum over the motions that happened, so it is the reading
    # that would move first if a frame were written inside one.
    assert math.isclose(without.arm_seconds, with_film.arm_seconds, rel_tol=1e-9)
    assert (tmp_path / "film.mp4").stat().st_size > 0


def test_the_film_reads_a_table_the_way_the_scorecard_does():
    """The last picture says what happened, and its numbers are the result's own."""

    def result(**changes) -> TableResult:
        fields = dict(
            seed=TABLE,
            glasses=4,
            pickable_at_start=1,
            pickable_at_end=1,
            toppled=0,
            ended_by=SAID_DONE,
            arm_seconds=28.4,
            thinking_seconds=0.1,
            answers=26,
        )
        return TableResult(**{**fields, **changes})

    over, spent = outcome_lines(result(toppled=1, ended_by=GLASS_OVER))
    assert "1 glass went over" in over and "forfeit" in over

    separated, _ = outcome_lines(result(pickable_at_end=4))
    assert separated.startswith("separated")

    said_done, _ = outcome_lines(result())
    assert "said done" in said_done and "3 of 4" in said_done

    clock, _ = outcome_lines(result(ended_by=RAN_OUT))
    assert "clock" in clock

    # The one place a film prints numbers, so they come from the result itself.
    assert "28 arm s" in spent and "26 answers" in spent and "1 of 4" in spent
