"""The rule that lets a trained policy say it has finished."""

from __future__ import annotations

import pytest
from stopping import QUIET_ANSWERS, Quiet, is_a_push

from partners import PUSH_HEIGHT, TRAVEL_HEIGHT, Chunk, Waypoint


def _path(*heights: float) -> Chunk:
    """A path at one spot on the table, at the heights given."""
    return Chunk(0, tuple(Waypoint(0.48, -0.26, z, 0.0) for z in heights), (0.48, -0.26))


def test_a_path_that_comes_down_to_the_pushing_height_is_a_push():
    assert is_a_push(_path(TRAVEL_HEIGHT, PUSH_HEIGHT))


def test_a_path_that_stays_in_the_air_is_not_a_push():
    # This is solution 5's own failure in problem 3: the borrowed model never
    # brought the jaw down to the glasses, and a policy doing that is saying it
    # has nothing to do, whatever it believes it is doing.
    assert not is_a_push(_path(TRAVEL_HEIGHT, 0.25, 0.20))


def test_the_lowest_waypoint_decides_and_not_the_first():
    # A policy may come down part way along its path, and such a path can still
    # move a glass, so the first waypoint cannot be what the test looks at.
    assert is_a_push(_path(TRAVEL_HEIGHT, 0.20, PUSH_HEIGHT, 0.20))


@pytest.mark.parametrize("height", [PUSH_HEIGHT, PUSH_HEIGHT + 0.0005, PUSH_HEIGHT + 0.0009])
def test_a_millimetre_of_room_is_left_for_the_arithmetic(height: float):
    assert is_a_push(_path(height))


def test_one_quiet_answer_is_not_enough():
    # A policy that draws its answer rather than computing it will draw a stray
    # one, and ending a table on that would be ending it on noise.
    quiet = Quiet()
    quiet.saw(_path(TRAVEL_HEIGHT, 0.25))
    assert not quiet.finished


def test_enough_quiet_answers_in_a_row_end_the_table():
    quiet = Quiet()
    for _ in range(QUIET_ANSWERS):
        quiet.saw(_path(TRAVEL_HEIGHT, 0.25))
    assert quiet.finished
    assert str(QUIET_ANSWERS) in quiet.why


def test_a_push_resets_the_count():
    # The run has to be unbroken: a policy that pushes between quiet answers is
    # still working, and only a policy that has stopped pushing has stopped.
    quiet = Quiet()
    for _ in range(QUIET_ANSWERS - 1):
        quiet.saw(_path(TRAVEL_HEIGHT, 0.25))
    quiet.saw(_path(TRAVEL_HEIGHT, PUSH_HEIGHT))
    assert not quiet.finished
    for _ in range(QUIET_ANSWERS - 1):
        quiet.saw(_path(TRAVEL_HEIGHT, 0.25))
    assert not quiet.finished


def test_each_table_counts_on_its_own():
    # A fresh Quiet belongs to a fresh table, so a quiet spell at the end of one
    # table cannot end the next one before it starts.
    quiet = Quiet()
    for _ in range(QUIET_ANSWERS):
        quiet.saw(_path(TRAVEL_HEIGHT, 0.25))
    assert quiet.finished
    assert not Quiet().finished
