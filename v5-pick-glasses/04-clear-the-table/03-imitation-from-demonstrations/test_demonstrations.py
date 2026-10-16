"""Checks on the convention a demonstration is written in.

Nothing here runs the physics or renders a picture, so the whole file is a
fraction of a second. What it checks is that a path survives the round trip
into a chunk and out again, because a target a policy cannot express is not a
target, and that the readings are the shape the model is told they are.

The tests run against families of glasses and families of paths rather than one
example, as everything in this project does: a convention that holds for one
push and fails for a longer one is the exact fault a single case cannot catch.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from chunks import ACTION_WIDTH, CHUNK, length_of, to_action, to_waypoints
from readings import GLASSES, JAW_WIDTH, PER_GLASS, STATE_WIDTH, to_state

import tables
from partners import PUSH_HEIGHT, TRAVEL_HEIGHT, Seen, Waypoint


def a_look(x: float = 0.0, y: float = 0.55, heading: float = 1.0) -> list[Waypoint]:
    """A path to go and stand somewhere: one waypoint at travel height, as solution 1 writes one."""
    return [Waypoint(x, y, TRAVEL_HEIGHT, heading)]


def a_push(across: float, heading: float = 0.3) -> list[Waypoint]:
    """A path that comes down and shoves, in the shape solution 1 writes one.

    A waypoint at travel height, a descent in ten-millimetre steps, then the
    shove in one-millimetre steps -- which is how a path asks to be carried out
    at the cell's descent and push speeds.
    """
    start = (0.0, 0.55)
    points = [Waypoint(*start, TRAVEL_HEIGHT, heading)]
    drops = math.ceil((TRAVEL_HEIGHT - PUSH_HEIGHT) / 0.01)
    for step in range(1, drops + 1):
        z = TRAVEL_HEIGHT - step * (TRAVEL_HEIGHT - PUSH_HEIGHT) / drops
        points.append(Waypoint(*start, z, heading))
    steps = max(1, round(across / 0.001))
    for step in range(1, steps + 1):
        gone = step * across / steps
        points.append(
            Waypoint(
                start[0] + gone * math.cos(heading),
                start[1] + gone * math.sin(heading),
                PUSH_HEIGHT,
                heading,
            )
        )
    return points


def some_glasses(count: int, seed: int = 0) -> list[Seen]:
    rng = np.random.default_rng(seed)
    return [
        Seen(
            id=i,
            x=float(rng.uniform(-0.1, 0.1)),
            y=float(rng.uniform(0.45, 0.65)),
            height=float(rng.uniform(0.07, 0.20)),
            widest=float(rng.uniform(0.045, 0.095)),
            foot=float(rng.uniform(0.03, 0.07)),
            standing=True,
        )
        for i in range(count)
    ]


# ------------------------------------------------------------------- the chunk


def test_a_chunk_is_always_the_same_shape():
    for path in (a_look(), a_push(0.005), a_push(0.04), a_push(0.12)):
        action = to_action(path)
        assert action.shape == (CHUNK, ACTION_WIDTH)
        assert action.dtype == np.float32


def test_a_path_comes_back_out_as_it_went_in():
    """The round trip is what makes a demonstration a target the policy can reach."""
    for path in (a_look(), a_look(0.08, 0.45, -2.0), a_push(0.002), a_push(0.03), a_push(0.1)):
        points, pulled = to_waypoints(to_action(path))
        assert pulled == 0
        assert len(points) == len(path)
        for was, now in zip(path, points, strict=True):
            assert math.dist((was.x, was.y, was.z), (now.x, now.y, now.z)) < 1e-6
            assert abs(math.atan2(math.sin(was.heading - now.heading), 1.0)) < 1e-6


def test_the_column_says_how_long_the_path_is():
    for across in (0.002, 0.01, 0.05, 0.11):
        path = a_push(across)
        assert length_of(to_action(path)) == len(path)
    assert length_of(to_action(a_look())) == 1


def test_a_path_longer_than_a_chunk_is_refused_rather_than_cut():
    """A cut path is half a push, which leaves the jaw standing against a glass."""
    long_enough = a_push(0.001 * (CHUNK + 20))
    assert len(long_enough) > CHUNK
    assert to_action(long_enough) is None


def test_the_padding_holds_the_end_of_the_path():
    action = to_action(a_push(0.02))
    kept = length_of(action)
    for row in action[kept:]:
        assert np.allclose(row[:5], action[kept - 1][:5])
        assert row[5] == 0.0


def test_a_chunk_a_network_might_answer_with_is_pulled_inside_the_jaw_s_limits():
    """A network can answer with any number, and the arm still only reaches so far."""
    action = to_action(a_push(0.03))
    action[:, 0] += 5.0  # five metres off the side of the table
    action[:, 2] = TRAVEL_HEIGHT + 1.0
    points, pulled = to_waypoints(action)
    assert pulled == len(points)
    for point in points:
        assert PUSH_HEIGHT - 1e-9 <= point.z <= TRAVEL_HEIGHT + 1e-9


def test_an_empty_path_is_an_error_and_not_a_chunk():
    with pytest.raises(ValueError):
        to_action([])


def test_a_chunk_of_the_wrong_width_is_refused():
    with pytest.raises(ValueError):
        to_waypoints(np.zeros((CHUNK, ACTION_WIDTH - 1)))


# ---------------------------------------------------------------- the readings


def test_the_readings_are_the_width_they_say_they_are():
    for count in range(0, GLASSES + 1):
        row = to_state(a_look()[0], some_glasses(count))
        assert row.shape == (STATE_WIDTH,)
        assert row.dtype == np.float32


def test_an_unused_slot_is_zero_and_says_so():
    row = to_state(a_look()[0], some_glasses(2))
    used = [row[JAW_WIDTH + slot * PER_GLASS + PER_GLASS - 1] for slot in range(GLASSES)]
    assert used[:2] == [1.0, 1.0]
    assert all(flag == 0.0 for flag in used[2:])
    for slot in range(2, GLASSES):
        at = JAW_WIDTH + slot * PER_GLASS
        assert np.allclose(row[at : at + PER_GLASS], 0.0)


def test_the_same_table_in_two_orders_is_one_reading():
    """A network is not permutation invariant, so the slots have to be sorted."""
    glasses = some_glasses(4, seed=7)
    jaw = a_look()[0]
    assert np.allclose(to_state(jaw, glasses), to_state(jaw, list(reversed(glasses))))


def test_two_stands_over_one_table_are_two_different_readings():
    """The pose is in the row because the camera moves with it."""
    glasses = some_glasses(3)
    here, there = a_look(0.0, 0.45, 1.0)[0], a_look(0.1, 0.7, -1.0)[0]
    assert not np.allclose(to_state(here, glasses), to_state(there, glasses))


def test_more_glasses_than_the_draw_makes_is_an_error():
    with pytest.raises(ValueError):
        to_state(a_look()[0], some_glasses(GLASSES + 1))


def test_the_slots_follow_the_draw():
    """The slot count is read off the draw, so a wider draw widens the row with it."""
    assert GLASSES == tables.MOST
    assert all(len(tables.table(seed)) <= GLASSES for seed in range(8))
