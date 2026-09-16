"""Where the tool goes to pick the top up, carry it, and turn it flat.

These check the geometry the arm relies on but cannot see: that the fingers
come down either side of the board at the middle of its edge, that a board
carried round still hangs straight down, and that both turns leave it flat,
sticking out away from the arm.
"""

import math

import numpy as np
import pytest
from synthetic import spawned_box
from turn_top_flat.arm.dimensions import FINGERTIP_OFFSET
from turn_top_flat.assembly.grasps import (
    EDGE_BELOW_TOOL,
    TOP_INSERTION,
    carried_tool_pose,
    carry_round,
    down_tool_pose,
    edge_pick_poses,
    flat_turn,
    gripped_edge,
    hanging_tool_poses,
    hold,
    shifted,
    swing_about_edge,
    turned_about,
    upright_edge,
    wrist_spin,
)
from turn_top_flat.geometry import Box
from turn_top_flat.transforms import WORLD_Z, frame, rotation_z
from turn_top_flat.world.spawn import random_room

BASE = np.zeros(3)
STEP = math.radians(5.0)


def upright_top(yaw=1.62, size=(0.28, 0.18, 0.018), centre=(0.05, 0.52, 0.091)):
    """A board standing on its long edge, its faces towards and away from the arm."""
    along = rotation_z(yaw)[:, 0]
    return Box(np.array(centre), np.column_stack((along, WORLD_Z, np.cross(along, WORLD_Z))), size)


TOP = upright_top()


def test_the_tool_goes_where_the_hold_says_for_any_pose_of_the_part():
    tool = frame(np.array([0.4, 0.1, 0.3]), rotation_z(0.7))
    part = Box(np.array([0.5, 0.0, 0.1]), rotation_z(-0.2), (0.1, 0.1, 0.1))
    held = hold(part, tool)
    # Put the part back where it was, with the tool as it was: same tool pose.
    assert carried_tool_pose(held, tool[:3, :3], part.centre) == pytest.approx(tool)


def test_the_upper_edge_is_found_whichever_way_the_fit_labels_the_board():
    edge, along, _ = upright_edge(TOP)
    # The same board with its first two axes swapped, as the fit may hand it back.
    swapped = Box(TOP.centre, np.column_stack((WORLD_Z, -TOP.axis(0), TOP.axis(2))), TOP.size[[1, 0, 2]])
    edge_2, along_2, _ = upright_edge(swapped)
    assert edge == pytest.approx(TOP.centre + WORLD_Z * 0.09)
    assert edge_2 == pytest.approx(edge)
    assert abs(float(along @ along_2)) == pytest.approx(1.0)


@pytest.mark.parametrize("pick", edge_pick_poses(TOP))
def test_the_top_is_gripped_from_above_at_the_middle_of_its_upper_edge(pick):
    assert pick[:3, 2] == pytest.approx(-WORLD_Z)
    # A right-handed tool frame.
    assert np.cross(pick[:3, 0], pick[:3, 1]) == pytest.approx(pick[:3, 2])
    # The fingers close along the tool's y axis, square to the board's faces,
    # and its x axis runs along the edge.
    assert abs(float(pick[:3, 1] @ TOP.axis(2))) == pytest.approx(1.0)
    assert abs(float(pick[:3, 0] @ TOP.axis(0))) == pytest.approx(1.0)
    fingertips = pick[:3, 3] + pick[:3, 2] * FINGERTIP_OFFSET
    assert fingertips == pytest.approx(TOP.centre + WORLD_Z * (0.09 - TOP_INSERTION))
    assert gripped_edge(pick) == pytest.approx(TOP.centre + WORLD_Z * 0.09)


@pytest.mark.parametrize("seed", range(1, 21))
def test_the_fingers_come_down_clear_of_the_holders(seed):
    room = random_room(seed)
    top = spawned_box(room.top)
    for pick in edge_pick_poses(top):
        tip = pick[:3, 3] + pick[:3, 2] * FINGERTIP_OFFSET
        for spawned in room.holders:
            block = spawned_box(spawned)
            # Along the edge, the fingers are 3 cm wide.
            along = (block.corners() - tip) @ pick[:3, 0]
            gap = max(along.min(), -along.max(), 0.0)
            assert gap > 0.015 + 0.02


def hanging_at(edge, direction):
    return down_tool_pose(edge + WORLD_Z * EDGE_BELOW_TOOL, direction)


AXIS = np.array([0.0, 1.0, 0.0])
SPOT = np.array([0.50, 0.0, 0.40])


@pytest.mark.parametrize("hanging", hanging_tool_poses(SPOT, AXIS))
def test_the_board_hangs_at_the_turning_spot_with_its_edge_along_the_axis(hanging):
    assert gripped_edge(hanging) == pytest.approx(SPOT)
    assert abs(float(hanging[:3, 0] @ AXIS)) == pytest.approx(1.0)
    assert hanging[:3, 2] == pytest.approx(-WORLD_Z)


def board_after(tool_pose, held):
    return tool_pose @ np.linalg.inv(held)


def hanging_board(hanging):
    """A board hanging from ``hanging``, and how it is held."""
    board = Box(
        gripped_edge(hanging) - WORLD_Z * 0.09,
        np.column_stack((hanging[:3, 0], WORLD_Z, np.cross(hanging[:3, 0], WORLD_Z))),
        (0.28, 0.18, 0.018),
    )
    return board, hold(board, hanging)


@pytest.mark.parametrize("hanging", hanging_tool_poses(SPOT, AXIS))
@pytest.mark.parametrize("axis", [AXIS, -AXIS])
def test_turned_about_its_edge_the_board_ends_flat_and_away_from_the_arm(hanging, axis):
    board, held = hanging_board(hanging)
    angle = flat_turn(hanging, axis, BASE)
    steps = swing_about_edge(hanging, axis, angle, STEP)
    previous = hanging
    for pose in steps:
        # The gripped edge stays where it is.
        assert gripped_edge(pose) == pytest.approx(SPOT)
        # No step turns the board by more than a step.
        cosine = (np.trace(pose[:3, :3] @ previous[:3, :3].T) - 1.0) / 2.0
        assert math.acos(min(1.0, cosine)) <= STEP + 1e-9
        previous = pose
    flat = board_after(steps[-1], held)
    # Flat: its faces look straight up and down.
    assert abs(flat[2, 2]) == pytest.approx(1.0)
    # And it sticks out from the edge, away from the base.
    assert flat[0, 3] > SPOT[0] + 0.08
    assert flat[2, 3] == pytest.approx(SPOT[2])
    # The tool ends level, reaching away from the arm.
    assert steps[-1][:3, 2] == pytest.approx([1.0, 0.0, 0.0])


@pytest.mark.parametrize("hanging", hanging_tool_poses(SPOT, AXIS))
def test_turned_about_the_wrist_the_board_ends_just_as_flat_somewhere_else(hanging):
    # Turning wrist 1 turns the tool about a line parallel to the edge but
    # through the wrist, higher up and off to one side.
    board, held = hanging_board(hanging)
    wrist = gripped_edge(hanging) + np.array([-0.02, 0.10, 0.22])
    angle = flat_turn(hanging, AXIS, BASE)
    by_wrist = turned_about(hanging, wrist, AXIS, angle)
    by_arm = swing_about_edge(hanging, AXIS, angle, STEP)[-1]
    assert by_wrist[:3, :3] == pytest.approx(by_arm[:3, :3])
    assert abs(board_after(by_wrist, held)[2, 2]) == pytest.approx(1.0)
    assert np.linalg.norm(by_wrist[:3, 3] - by_arm[:3, 3]) > 0.1


def test_a_board_whose_edge_is_off_the_axis_does_not_end_flat():
    # Why the edge is lined up with wrist 1's axis before the turn.
    hanging = hanging_at(SPOT, rotation_z(math.radians(15.0)) @ AXIS)
    board, held = hanging_board(hanging)
    flat = board_after(turned_about(hanging, SPOT, AXIS, flat_turn(hanging, AXIS, BASE)), held)
    assert math.degrees(math.acos(abs(flat[2, 2]))) == pytest.approx(15.0, abs=0.01)


@pytest.mark.parametrize("pick", edge_pick_poses(TOP))
def test_the_top_is_carried_hanging_round_the_base_to_the_turning_spot(pick):
    held = hold(TOP, pick)
    lifted = shifted(pick, WORLD_Z * 0.22)
    hanging = min(hanging_tool_poses(SPOT, AXIS), key=lambda pose: wrist_spin(lifted, pose, BASE))
    poses = carry_round(held, lifted, hanging, 0.32, BASE)
    for pose in poses:
        board = pose @ np.linalg.inv(held)
        # Still hanging straight down from its edge the whole way.
        assert board[:3, 1] == pytest.approx(WORLD_Z)
        assert board[2, 3] == pytest.approx(0.32)
    assert poses[0][:2, 3] == pytest.approx(lifted[:2, 3])
    assert poses[-1][:2, 3] == pytest.approx(hanging[:2, 3])
    assert poses[-1][:3, :3] == pytest.approx(hanging[:3, :3])


def test_the_wrist_spin_leaves_out_what_the_base_turn_does():
    start = down_tool_pose(np.array([0.0, 0.5, 0.3]), np.array([1.0, 0.0, 0.0]))
    # A quarter turn of the base carries the tool round a quarter turn with it.
    carried = down_tool_pose(np.array([0.5, 0.0, 0.3]), np.array([0.0, -1.0, 0.0]))
    assert wrist_spin(start, carried, BASE) == pytest.approx(0.0, abs=1e-9)
    flipped = down_tool_pose(np.array([0.5, 0.0, 0.3]), np.array([0.0, 1.0, 0.0]))
    assert wrist_spin(start, flipped, BASE) == pytest.approx(math.pi)
