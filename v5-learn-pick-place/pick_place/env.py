"""One pick-and-place episode: the scene, what the policy is shown, and whether it worked.

The camera looks once, at the start, and from what it finds come two goal
points for the pinch point between the fingertips: where to grasp the block,
and where to let go of it so its centre of mass lands on the target.

The policy is shown two things every step, as vectors:

- ``state``: the six arm joint angles and how closed the gripper is, 0 to 1;
- ``environment_state``: the vector from the pinch point to each goal point,
  how far the wrist still has to turn to line the fingers up with the grasp,
  and how thick the block is. The pinch point's position comes from the joint
  angles, as a real arm's controller reports its tool position.

It answers with an ``action``: how much to move each of the six joints from
where it is now, and the gripper, 0 open or 1 closed.

Goals relative to the gripper, and moves relative to the joints, are what
make the policy precise. Given absolute positions and asked for absolute
joint angles, it has to learn the arm's inverse kinematics to a millimetre
from a few hundred examples, and a first run landed the fingers 2 to 3 cm
beside the block. Relative inputs turn the job into closing a gap it can see,
and relative outputs are small numbers, so the same relative error in the
network is a much smaller error in the arm.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import mujoco
import numpy as np

from .locate import Located, OverheadDepth, locate_block
from .scene import GRIPPER_CLOSED_CTRL, PINCH_SITE, BlockSpec, arm_joint_ids, build, reset_to_home
from .settings import BLOCK, FPS, PICK_ZONE, PLACE_ZONE, SUCCESS_RADIUS, TIMESTEP
from .shapes import canonical_phi, random_block_outline

STATE_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow",
    "wrist_1",
    "wrist_2",
    "wrist_3",
    "gripper",
]
ENVIRONMENT_NAMES = [
    "to_grasp_x",
    "to_grasp_y",
    "to_grasp_z",
    "to_place_x",
    "to_place_y",
    "to_place_z",
    "turn_to_grasp",
    "thickness",
]
ACTION_NAMES = [f"move_{name}" for name in STATE_NAMES[:6]] + ["gripper"]
SUBSTEPS = round(1 / (FPS * TIMESTEP))
# How long a block is left to settle on the table before the camera looks.
SETTLE_SECONDS = 0.3
# The gripper's driver joint runs from 0 (open) to 0.8 rad (closed).
DRIVER_RANGE = 0.8
# The finger pads reach from about 33 mm above the pinch point to just below
# it. Holding the pinch point 25 mm below the block's top face keeps the pads
# on the block's upper part. For thin blocks it stops at 15 mm: any lower and
# the open fingertips land on the table and the arm stops short.
GRIP_BELOW_TOP = 0.025
LOWEST_PINCH = 0.015
# Let the block go this far above the table, so it is set down, not pushed.
RELEASE_GAP = 0.003


@dataclass(frozen=True)
class Episode:
    block: BlockSpec
    target: tuple[float, float]


def random_episode(seed: int) -> Episode:
    rng = random.Random(seed)
    outline = random_block_outline(rng)
    hue = rng.random()
    block = BlockSpec(
        outline=outline,
        thickness=rng.uniform(*BLOCK.thickness),
        density=rng.uniform(*BLOCK.density),
        x=rng.uniform(*PICK_ZONE.x),
        y=rng.uniform(*PICK_ZONE.y),
        yaw=rng.uniform(-math.pi, math.pi),
        rgba=(*hsv_to_rgb(hue, 0.7, 0.85), 1.0),
    )
    target = (rng.uniform(*PLACE_ZONE.x), rng.uniform(*PLACE_ZONE.y))
    return Episode(block=block, target=target)


class Task:
    """What every simulator's episode shares: the goals, what the policy is shown, and the score.

    A simulator fills in how to read the arm and the block, and how to move
    the arm. MuJoCo's is ``PickPlaceEnv`` below; Gazebo's is in
    ``gazebo/env.py``.
    """

    episode: Episode
    located: Located

    def set_goals(self, located: Located) -> None:
        self.located = located
        g = located.grasp
        grip_z = max(located.thickness - GRIP_BELOW_TOP, LOWEST_PINCH)
        self.grasp_point = np.array([g.x, g.y, grip_z])
        # The block is held a fixed distance from its centre of mass, so the
        # pinch point lets go that same distance from the target.
        self.place_point = np.array(
            [
                self.episode.target[0] + g.x - located.x,
                self.episode.target[1] + g.y - located.y,
                grip_z + RELEASE_GAP,
            ]
        )
        self.grasp_phi = g.phi

    # What a simulator provides.

    def arm_angles(self) -> np.ndarray:
        raise NotImplementedError

    def gripper_reading(self) -> float:
        """How closed the gripper is, 0 open to 1 closed, on the Robotiq's scale."""
        raise NotImplementedError

    def pinch(self) -> tuple[np.ndarray, float]:
        """Where the pinch point is, and the direction the fingers close along, in (-pi/2, pi/2]."""
        raise NotImplementedError

    def step_absolute(self, command: np.ndarray) -> None:
        """Send joint angles ``command[:6]`` and gripper ``command[6]``, and run one control step."""
        raise NotImplementedError

    def block_centre(self) -> np.ndarray:
        raise NotImplementedError

    def block_up(self) -> np.ndarray:
        """The block's own up direction, in the room."""
        raise NotImplementedError

    # The same for every simulator.

    def state(self) -> np.ndarray:
        return np.append(self.arm_angles(), self.gripper_reading()).astype(np.float32)

    def environment_state(self) -> np.ndarray:
        pos, phi = self.pinch()
        return np.concatenate(
            [
                self.grasp_point - pos,
                self.place_point - pos,
                [canonical_phi(self.grasp_phi - phi), self.located.thickness],
            ]
        ).astype(np.float32)

    def relative(self, command: np.ndarray) -> np.ndarray:
        """An action with absolute joint angles, as moves from where the joints are now."""
        action = np.array(command, dtype=np.float32)
        action[:6] -= self.arm_angles()
        return action

    def step(self, action: np.ndarray) -> None:
        """Move each joint by ``action[:6]`` from where it is, and set the gripper to ``action[6]``."""
        self.step_absolute(np.append(self.arm_angles() + action[:6], action[6]))

    def distance_to_target(self) -> float:
        c = self.block_centre()
        return math.hypot(c[0] - self.episode.target[0], c[1] - self.episode.target[1])

    def succeeded(self) -> bool:
        """The block is on the target, lying flat on the table, and the gripper has let go of it."""
        c = self.block_centre()
        resting = abs(c[2] - self.episode.block.thickness / 2) < 0.003 and self.block_up()[2] > 0.99
        released = self.gripper_reading() < 0.2
        return self.distance_to_target() < SUCCESS_RADIUS and resting and released


class PickPlaceEnv(Task):
    """The episode in MuJoCo, where the policy was trained."""

    def __init__(self, episode: Episode):
        self.episode = episode
        self.model = build(episode.block, episode.target)
        self.data = mujoco.MjData(self.model)
        self.arm_qpos = arm_joint_ids(self.model)
        self.driver_qpos = self.model.joint("gripper/right_driver_joint").qposadr[0]
        self.block_body = self.model.body("block").id
        self.pinch_site = self.model.site(PINCH_SITE).id
        reset_to_home(self.model, self.data)
        for _ in range(round(SETTLE_SECONDS / TIMESTEP)):
            mujoco.mj_step(self.model, self.data)
        camera = OverheadDepth(self.model)
        try:
            self.set_goals(locate_block(camera.points(self.data)))
        finally:
            camera.close()

    def arm_angles(self) -> np.ndarray:
        return self.data.qpos[self.arm_qpos].copy()

    def gripper_reading(self) -> float:
        return float(self.data.qpos[self.driver_qpos] / DRIVER_RANGE)

    def pinch(self) -> tuple[np.ndarray, float]:
        rot = self.data.site_xmat[self.pinch_site].reshape(3, 3)
        return self.data.site_xpos[self.pinch_site].copy(), pinch_phi(rot)

    def step_absolute(self, command: np.ndarray) -> None:
        self.data.ctrl[:6] = command[:6]
        self.data.ctrl[6] = float(np.clip(command[6], 0.0, 1.0)) * GRIPPER_CLOSED_CTRL
        for _ in range(SUBSTEPS):
            mujoco.mj_step(self.model, self.data)

    def block_centre(self) -> np.ndarray:
        return self.data.xipos[self.block_body].copy()

    def block_up(self) -> np.ndarray:
        return self.data.xmat[self.block_body].reshape(3, 3)[:, 2].copy()


def pinch_phi(rot: np.ndarray) -> float:
    """The direction the fingers close along: the pinch frame's y axis, in the table plane."""
    return canonical_phi(math.atan2(rot[1, 1], rot[0, 1]))


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
    import colorsys

    return colorsys.hsv_to_rgb(h, s, v)
