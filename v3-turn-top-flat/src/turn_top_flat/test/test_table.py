"""Reading the legs, and tilting the top down onto them.

These check what the arm cannot see while it works: that the top's lower edge
comes down on the far legs, that it turns about that edge without sliding on
them, and that it ends up lying on all four, just above the near ones.
"""

import math

import numpy as np
import pytest
from synthetic import spawned_box
from turn_top_flat.assembly.grasps import (
    board_point,
    edge_pick_poses,
    hanging_tool_poses,
    hold,
    resting_edge,
    shifted,
    tilt_axis,
    tilt_steps,
    turned_about,
    upright_size,
)
from turn_top_flat.assembly.table import landing_angle, misfit, read_legs
from turn_top_flat.geometry import Box
from turn_top_flat.transforms import WORLD_Z
from turn_top_flat.world import spec
from turn_top_flat.world.spawn import random_room

BASE = np.zeros(3)
SEEDS = range(1, 21)
LEAN = math.radians(30.0)
DROP = 0.003


def legs_of(room):
    return read_legs([spawned_box(leg) for leg in room.legs], BASE)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_far_legs_and_the_line_the_top_rests_on_are_found(seed):
    room = random_room(seed)
    legs = legs_of(room)
    far = [spawned_box(leg) for leg in room.legs[:2]]
    assert {tuple(np.round(leg.centre, 6)) for leg in legs.far} == {
        tuple(np.round(leg.centre, 6)) for leg in far
    }
    # The line runs over the far legs' middles, at their tops, halfway along.
    assert legs.hinge[:2] == pytest.approx(np.mean([leg.centre[:2] for leg in far], axis=0))
    assert legs.hinge[2] == pytest.approx(far[0].top_z)
    # Towards the arm, and square to the far row.
    assert float(legs.toward @ -legs.hinge) > 0.0
    assert float(legs.toward @ legs.along) == pytest.approx(0.0, abs=1e-9)
    assert legs.rows == pytest.approx(room.top.size[1] - spec.LEG_INSET - room.legs[0].size[0] / 2.0)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_top_fits_the_legs_it_was_made_for_and_not_a_narrower_one(seed):
    room = random_room(seed)
    legs = legs_of(room)
    length, width = room.top.size[0], room.top.size[1]
    assert misfit(legs, length, width) is None
    assert "wide" in misfit(legs, length, width - 0.02)
    assert "past the end" in misfit(legs, length - 0.03, width)


def test_it_is_let_go_of_just_short_of_flat():
    legs = legs_of(random_room(1))
    short = math.pi / 2.0 - landing_angle(legs, DROP)
    assert legs.rows * math.sin(short) == pytest.approx(DROP)


def tilt(seed):
    """Everything about tilting one room's top down onto its legs, as the task works it out."""
    room = random_room(seed)
    legs = legs_of(room)
    top = spawned_box(room.top)
    pick = edge_pick_poses(top)[0]
    held = hold(top, pick)
    hanging = hanging_tool_poses(np.array([0.2, -0.4, 0.4]), legs.along)[0]
    edge = resting_edge(hanging, held, top.size, legs.toward)
    axis = tilt_axis(legs.toward)
    standing = shifted(hanging, legs.hinge - board_point(hanging, held, edge))
    touch = turned_about(standing, legs.hinge, axis, LEAN)
    landing = landing_angle(legs, DROP)
    steps = tilt_steps(touch, legs.hinge, axis, landing - LEAN, math.radians(3.0))
    return room, legs, top, held, edge, touch, steps


def lying(pose, held, top):
    """The top as a box, for the tool at ``pose``."""
    board = pose @ np.linalg.inv(held)
    return Box(board[:3, 3], board[:3, :3], top.size)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_top_comes_down_on_the_far_legs_leaning_towards_the_arm(seed):
    _, legs, top, held, edge, touch, _ = tilt(seed)
    board = lying(touch, held, top)
    # Its resting edge is on the line over the far legs, and nothing of it is
    # lower than that edge.
    assert board_point(touch, held, edge) == pytest.approx(legs.hinge)
    assert board.bottom_z == pytest.approx(legs.hinge[2], abs=1e-9)
    # Leaning 30 degrees, its upper edge towards the arm. Axis 1 is the one
    # that pointed up when it stood in its holders.
    assert math.degrees(math.acos(float(board.axis(1) @ WORLD_Z))) == pytest.approx(30.0, abs=1e-6)
    assert float(board.axis(1) @ legs.toward) > 0.0


@pytest.mark.parametrize("seed", SEEDS)
def test_tilted_down_it_turns_on_that_edge_and_ends_on_all_four_legs(seed):
    _, legs, top, held, edge, _, steps = tilt(seed)
    # The edge it rests on does not move, so nothing slides on the leg tops.
    for pose in steps:
        assert board_point(pose, held, edge) == pytest.approx(legs.hinge, abs=1e-9)

    board = lying(steps[-1], held, top)
    # Almost flat: its faces within a degree or two of looking straight up.
    assert math.degrees(math.acos(abs(float(board.axis(2)[2])))) < 2.0
    # Lying from the far legs' middles towards the arm, and over all four.
    _, width = upright_size(top)
    assert float((board.centre - legs.hinge) @ legs.toward) == pytest.approx(width / 2.0, abs=0.003)
    for leg in legs.all:
        assert board.footprint_distance(leg.centre[None, :2])[0] == pytest.approx(0.0)
    # Just above the near legs.
    underside_at_near = legs.hinge[2] + legs.rows * math.sin(math.pi / 2.0 - landing_angle(legs, DROP))
    assert underside_at_near == pytest.approx(max(leg.top_z for leg in legs.near) + DROP)
    # The tool ends level, reaching away from the arm into the top's near edge.
    assert float(steps[-1][:3, 2] @ -legs.toward) > math.cos(math.radians(2.0))
