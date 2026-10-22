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
from dataclasses import replace

import numpy as np
import pytest
from chunks import ACTION_WIDTH, CHUNK, length_of, to_action, to_waypoints
from readings import (
    ASKED_WIDTH,
    CONDITION_WIDTH,
    DONE,
    GATE_WIDTH,
    GLASSES,
    JAW_WIDTH,
    KINDS,
    LOOK,
    PER_GLASS,
    PER_SHOVE,
    PLACE_SCALE,
    PROBE,
    PUSH,
    SELF_WIDTH,
    SHOVE_SCALE,
    SHOVE_WIDTH,
    STATE_WIDTH,
    Shoves,
    about_itself,
    conditioning,
    to_asked,
    to_gate,
    to_state,
)

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


# --------------------------------------------- the frame a push is written in


@pytest.mark.parametrize("at", [(0.0, 0.55), (0.12, 0.42), (-0.14, 0.66)])
def test_a_push_written_from_its_glass_comes_back_where_it_started(at: tuple[float, float]) -> None:
    """The round trip, with the glass's place taken off on the way in and put back on.

    A push is stored measured from the glass it pushes, so that one shove is one
    answer wherever the glass stands. What has to hold is that the path the bench
    is handed is the path the teacher followed, whichever glass it was at.
    """
    path = a_push(0.04)
    action = to_action(path, at)
    back, pulled = to_waypoints(action, at)
    assert pulled == 0
    for before, after in zip(path, back, strict=True):
        assert after.x == pytest.approx(before.x, abs=1e-6)
        assert after.y == pytest.approx(before.y, abs=1e-6)
        assert after.z == pytest.approx(before.z, abs=1e-6)


def test_the_same_shove_at_two_glasses_is_one_stored_answer() -> None:
    """Which is the whole point of storing a push in its glass's frame.

    Two glasses standing in different places, each given the same shove. Measured
    from the table the two answers are different numbers; measured from the glass
    they are the same answer, so a model has one thing to learn instead of two.
    """
    here, there = (0.0, 0.55), (0.12, 0.42)
    at_one = [Waypoint(here[0] + p.x, here[1] + p.y, p.z, p.heading) for p in a_push(0.04)]
    at_other = [Waypoint(there[0] + p.x, there[1] + p.y, p.z, p.heading) for p in a_push(0.04)]
    assert np.allclose(to_action(at_one, here), to_action(at_other, there), atol=1e-6)
    assert not np.allclose(to_action(at_one), to_action(at_other), atol=1e-6)


# ------------------------------------------- what the gate and the policy see


def test_the_gate_and_the_policy_share_the_table_and_differ_after_it() -> None:
    """The gate cannot be shown the decision it is making, and the policy must be.

    Both rows start with the same two things, the table as measured and the three
    numbers the solution keeps about itself. After that they part: the gate is
    shown what has already been tried on each glass, because that is what its
    decision turns on, and the policy is shown the decision instead. A test,
    because the widths are easy to let drift apart and nothing would complain
    until a fitted model were handed a row of the wrong length.
    """
    jaw = Waypoint(0.0, 0.5, TRAVEL_HEIGHT, 0.0)
    glass = Seen(id=0, x=0.05, y=0.55, height=0.15, widest=0.07, foot=0.06, standing=True)
    state = to_state(jaw, [glass])
    itself = about_itself(7, 3, 1.25)
    shoves = Shoves()
    shoves.saw([glass])
    asked = to_asked(state, itself, conditioning(PUSH, glass))
    gate = to_gate(state, itself, shoves.row([glass]))
    assert len(gate) == GATE_WIDTH
    assert len(asked) == ASKED_WIDTH
    shared = STATE_WIDTH + SELF_WIDTH
    assert np.allclose(asked[:shared], gate[:shared])
    assert len(gate) - shared == SHOVE_WIDTH
    assert len(asked) - shared == CONDITION_WIDTH


def test_the_history_counts_the_shoves_and_how_far_the_glass_came() -> None:
    """Two numbers a glass: how many answers were aimed at it, and how far it moved.

    The second is measured from where the glass stood the first time this table
    showed it, so a glass that has not been touched reads zero however often the
    arm has driven past it.
    """
    glass = Seen(id=4, x=0.05, y=0.55, height=0.15, widest=0.07, foot=0.06, standing=True)
    shoves = Shoves()
    shoves.saw([glass])
    assert np.allclose(shoves.row([glass]), 0.0)

    shoves.aimed_at(glass.id)
    shoves.aimed_at(glass.id)
    moved = replace(glass, x=glass.x + 0.02)
    shoves.saw([moved])  # seeing it again must not move the place it started from
    row = shoves.row([moved])
    assert row[0] == pytest.approx(2 / SHOVE_SCALE)
    assert row[1] == pytest.approx(0.02 / PLACE_SCALE)


def test_a_glass_the_picture_does_not_hold_leaves_its_history_empty() -> None:
    """A slot is either entirely filled or entirely empty, as the readings are."""
    here = Seen(id=0, x=0.05, y=0.55, height=0.15, widest=0.07, foot=0.06, standing=True)
    gone = Seen(id=1, x=0.25, y=0.55, height=0.15, widest=0.07, foot=0.06, standing=True)
    shoves = Shoves()
    shoves.saw([here, gone])
    shoves.aimed_at(gone.id)
    row = shoves.row([here])
    assert np.allclose(row[PER_SHOVE:], 0.0)


def test_the_kind_of_answer_is_one_hot_and_a_look_is_aimed_at_nothing() -> None:
    glass = Seen(id=0, x=0.05, y=0.55, height=0.15, widest=0.07, foot=0.06, standing=True)
    for kind in range(len(KINDS)):
        row = conditioning(kind, glass if kind in (PROBE, PUSH) else None)
        assert row[: len(KINDS)].sum() == 1.0
        assert row[kind] == 1.0
        aimed = row[len(KINDS) :]
        assert (aimed != 0).any() if kind in (PROBE, PUSH) else not aimed.any()


def test_what_it_knows_about_itself_is_three_numbers_near_one() -> None:
    """A unit rather than a limit: a solution that goes further reports above one."""
    assert len(about_itself(0, 0, 0.0)) == SELF_WIDTH
    assert np.allclose(about_itself(0, 0, 0.0), 0.0)
    assert (about_itself(40, 40, 4.0) > 1.0).all()


def test_where_an_answer_was_aimed_is_read_back_out_of_the_row() -> None:
    """The set stores one place for the glass, not two, and this is the reading back.

    A push is stored in the cell's own numbers, because that is what the teacher
    really did and because solution 6 reads the same set. The reader that wants a
    push measured from its own glass needs to know where that glass stood, and
    the row the policy is shown already says: the decision at the end of it holds
    the glass's place. So there is nothing to keep in step by hand.
    """
    import loading

    jaw = Waypoint(0.0, 0.5, TRAVEL_HEIGHT, 0.0)
    for at in ((0.05, 0.55), (-0.12, 0.42), (0.14, 0.66)):
        glass = Seen(id=0, x=at[0], y=at[1], height=0.15, widest=0.07, foot=0.06, standing=True)
        row = to_asked(to_state(jaw, [glass]), about_itself(3, 1, 0.4), conditioning(PUSH, glass))
        read = loading.aimed_at(row)
        assert read[0] == pytest.approx(at[0], abs=1e-6)
        assert read[1] == pytest.approx(at[1], abs=1e-6)


def test_an_answer_aimed_at_no_glass_is_measured_from_nothing() -> None:
    """A look and a done are aimed at nothing, so subtracting their origin changes nothing."""
    import loading

    jaw = Waypoint(0.0, 0.5, TRAVEL_HEIGHT, 0.0)
    glass = Seen(id=0, x=0.05, y=0.55, height=0.15, widest=0.07, foot=0.06, standing=True)
    for kind in (LOOK, DONE):
        row = to_asked(to_state(jaw, [glass]), about_itself(3, 1, 0.4), conditioning(kind, None))
        assert loading.aimed_at(row) == (0.0, 0.0)


def test_the_cap_keeps_every_answer_that_touches_a_glass() -> None:
    """Thinning the looks must not thin the pushes, because the pushes are the scarce ones.

    The set is four looks to every push, so a fit on a wider band reads three
    times as many looks for nothing. ``loading.to_read`` is what makes the wider
    band affordable, and the one thing it may never do is drop an answer that
    touches a glass.
    """
    import loading

    kinds = np.array([LOOK] * 80 + [PROBE] * 10 + [PUSH] * 5 + [DONE] * 5)
    rows = loading.to_read(kinds, looks=20)
    kept = kinds[rows]
    assert (kept == LOOK).sum() == 20
    for touching in (PROBE, PUSH, DONE):
        assert (kept == touching).sum() == (kinds == touching).sum()


def test_the_cap_reads_the_frames_in_the_order_they_were_collected() -> None:
    """An episode's frames are its table's answers in order, so the order has to hold."""
    import loading

    kinds = np.array([LOOK, PUSH, LOOK, LOOK, PROBE, LOOK, DONE])
    rows = loading.to_read(kinds, looks=2)
    assert list(rows) == sorted(rows)
    assert len(set(rows)) == len(rows)


def test_a_cap_larger_than_the_set_reads_all_of_it() -> None:
    """A cap is a ceiling and not a target, so a small set is read whole."""
    import loading

    kinds = np.array([LOOK] * 5 + [PUSH] * 2)
    assert list(loading.to_read(kinds, looks=50)) == list(range(7))
    assert list(loading.to_read(kinds)) == list(range(7))


def test_two_runs_read_the_same_frames() -> None:
    """The draw is seeded, so a second fit sees the set the first one saw."""
    import loading

    kinds = np.array(([LOOK] * 9 + [PUSH]) * 10)
    assert list(loading.to_read(kinds, looks=12)) == list(loading.to_read(kinds, looks=12))


def test_the_smoke_test_cap_still_takes_the_first_few_frames() -> None:
    """``most`` is for a smoke test and reads the start of the set, cap or no cap."""
    import loading

    kinds = np.array([LOOK, PUSH, LOOK, PROBE, LOOK, LOOK])
    assert list(loading.to_read(kinds, most=3)) == [0, 1, 2]
    rows = loading.to_read(kinds, most=4, looks=1)
    assert set(rows) <= {0, 1, 2, 3}
    assert list(kinds[rows]).count(LOOK) == 1
