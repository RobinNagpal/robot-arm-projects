"""Checks on the Gazebo port that need no Gazebo server: the files it writes and the conversions it makes."""

import math
import subprocess

import mujoco
import numpy as np
import pytest

from pick_place.env import random_episode
from pick_place.gazebo.env import CAMERA_MATRIX, write_world
from pick_place.gazebo.models import (
    GRIPPER_GAP,
    GRIPPER_READING,
    PINCH_AXES_IN_WRIST,
    PINCH_IN_WRIST,
    from_gazebo,
    gap_for_command,
    reading_from_gap,
    to_gazebo,
    write_block_mesh,
)
from pick_place.gazebo.run import RUNS
from pick_place.scene import PINCH_SITE, build, reset_to_home
from pick_place.settings import HOME


def test_the_world_file_is_valid_sdf(tmp_path):
    world = write_world(random_episode(RUNS[1]), tmp_path)
    check = subprocess.run(["gz", "sdf", "-k", str(world)], capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    assert "Valid" in check.stdout


def test_every_face_of_the_block_mesh_faces_outwards(tmp_path):
    block = random_episode(RUNS[2]).block
    lines = write_block_mesh(block, tmp_path / "block.obj").read_text().splitlines()
    vertices = np.array([[float(v) for v in line.split()[1:]] for line in lines if line.startswith("v ")])
    normals = np.array([[float(v) for v in line.split()[1:]] for line in lines if line.startswith("vn ")])
    middle = np.array([0.0, 0.0, block.thickness / 2])  # the outline is centred on its centroid
    faces = [line.split()[1:] for line in lines if line.startswith("f ")]
    assert len(faces) == 2 * (len(block.outline) - 2) + 2 * len(block.outline)
    for face in faces:
        corners = [vertices[int(c.split("//")[0]) - 1] for c in face]
        normal = normals[int(face[0].split("//")[1]) - 1]
        winding = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        assert np.dot(winding, normal) > 0, "corners must go anticlockwise seen from outside"
        assert np.dot(np.mean(corners, axis=0) - middle, normal) > 0, "normal must point away from the middle"


def test_the_gripper_reading_matches_the_robotiq_both_ways():
    for reading, gap in zip(GRIPPER_READING, GRIPPER_GAP, strict=True):
        assert reading_from_gap(gap) == pytest.approx(reading, abs=1e-6)
        assert gap_for_command(reading) == pytest.approx(gap, abs=1e-6)
    assert np.all(np.diff(GRIPPER_GAP) < 0), "closing further must always narrow the gap"


def test_gazebo_joint_angles_are_measured_from_home():
    angles = np.array([0.1, -0.2, 0.3, -0.4, 0.5, -0.6])
    assert np.allclose(from_gazebo(to_gazebo(angles)), angles)
    assert np.allclose(to_gazebo(HOME), 0.0)


def test_the_pinch_point_is_where_the_mujoco_gripper_has_it():
    """The Gazebo gripper is built around these numbers; check them against MuJoCo in another pose."""
    model = build(random_episode(0).block, (0.5, -0.2))
    data = mujoco.MjData(model)
    reset_to_home(model, data)
    data.qpos[:6] = [0.3, -1.2, 1.1, -0.7, 0.9, 0.4]
    mujoco.mj_kinematics(model, data)
    wrist = model.body("wrist_3_link").id
    rot = data.xmat[wrist].reshape(3, 3)
    site = model.site(PINCH_SITE).id
    assert np.allclose(rot.T @ (data.site_xpos[site] - data.xpos[wrist]), PINCH_IN_WRIST, atol=1e-4)
    assert np.allclose(rot.T @ data.site_xmat[site].reshape(3, 3), PINCH_AXES_IN_WRIST, atol=1e-4)


def test_the_gazebo_camera_looks_down_with_the_picture_the_right_way_round():
    """Gazebo's camera is posed roll 0, pitch 90°, yaw 90°; in MuJoCo's convention that is no rotation.

    A Gazebo camera looks along its x with the picture's up along its z; a
    MuJoCo camera looks along its -z with the picture's right along its x
    and up along its y.
    """
    c, s = math.cos(math.pi / 2), math.sin(math.pi / 2)
    rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    ry = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    gazebo = rz @ ry
    look, up, right = gazebo[:, 0], gazebo[:, 2], -gazebo[:, 1]
    assert np.allclose(np.column_stack([right, up, -look]), CAMERA_MATRIX, atol=1e-9)
