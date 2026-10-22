"""One episode in Gazebo, with the same interface as the MuJoCo one.

The policy and the scripted expert both run on it unchanged: it gives the
same state and environment state, and takes the same actions.

Two things are worked out here rather than read from Gazebo, as a real arm's
controller would work them out:

- **where the fingertips are**, from the joint angles and the arm's known
  geometry (MuJoCo's model of the same arm is used as the calculator);
- **how closed the gripper is**, from the gap between its fingers, on the
  Robotiq's 0 to 1 scale the policy was trained with.

The block is found the same way as in MuJoCo: one depth picture from the
overhead camera, and the same geometry code.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..env import SETTLE_SECONDS, Episode, Task, pinch_phi
from ..kinematics import Solver
from ..locate import depth_to_points, locate_block
from ..scene import ARM_JOINTS, build
from ..settings import CAMERA, FPS, HOME
from .models import (
    FINGER_JOINTS,
    OPEN_GAP,
    from_gazebo,
    gap_for_command,
    quat_to_matrix,
    reading_from_gap,
    to_gazebo,
    world_sdf,
    write_block_mesh,
)
from .sim import GazeboSim

# The overhead camera points straight down with the picture's right towards
# +x and its top towards +y: in MuJoCo's camera convention, no rotation.
CAMERA_MATRIX = np.eye(3)


def write_world(episode: Episode, folder: Path) -> Path:
    """The SDF world for ``episode``, and the block's mesh beside it."""
    mesh = write_block_mesh(episode.block, folder / "block.obj")
    world = folder / "world.sdf"
    world.write_text(world_sdf(episode.block, episode.target, mesh))
    return world


class GazeboEnv(Task):
    def __init__(self, episode: Episode, sim: GazeboSim):
        self.episode = episode
        self.sim = sim
        # MuJoCo's model of the same arm: the expert plans with it, and the
        # fingertip position is calculated with it.
        self.model = build(episode.block, episode.target)
        self.solver = Solver(self.model)
        self.step_absolute(np.append(HOME, 0.0), seconds=SETTLE_SECONDS)
        depth = sim.depth_picture(after=sim.time)
        points = depth_to_points(depth, np.array(CAMERA.pos), CAMERA_MATRIX, CAMERA.fovy)
        self.set_goals(locate_block(points))

    def arm_angles(self) -> np.ndarray:
        joints = self.sim.joints()
        return from_gazebo([joints[name] for name in ARM_JOINTS])

    def gripper_reading(self) -> float:
        joints = self.sim.joints()
        gap = OPEN_GAP - sum(joints[name] for name in FINGER_JOINTS)
        return reading_from_gap(gap)

    def pinch(self) -> tuple[np.ndarray, float]:
        pos, rot = self.solver.pinch_pose(self.arm_angles())
        return pos, pinch_phi(rot)

    def step_absolute(self, command: np.ndarray, seconds: float = 1 / FPS) -> None:
        gripper = float(np.clip(command[6], 0.0, 1.0))
        finger_travel = (OPEN_GAP - gap_for_command(gripper)) / 2
        self.sim.command(to_gazebo(command[:6]), finger_travel)
        self.sim.step(seconds)

    def block_centre(self) -> np.ndarray:
        pos, quat = self.sim.block_pose()
        # The block's origin is the middle of its bottom face; its centre of
        # mass is half its thickness above that, in the block's own frame.
        return pos + quat_to_matrix(quat) @ np.array([0.0, 0.0, self.episode.block.thickness / 2])

    def block_up(self) -> np.ndarray:
        _, quat = self.sim.block_pose()
        return quat_to_matrix(quat)[:, 2]
