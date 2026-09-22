"""Build the MuJoCo model for one episode: arm, gripper, table, one block and the target.

The block's shape changes every episode, and MuJoCo fixes a mesh's shape
when the model compiles, so each episode compiles a fresh model. That takes
a fraction of a second.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import mujoco
import numpy as np

from .settings import ARM_XML, CAMERA, GRIPPER_XML, HOME, TIMESTEP

ARM_JOINTS = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)
GRIPPER_PREFIX = "gripper/"
# The point halfway between the fingertips. Every position the expert plans
# is a position for this site.
PINCH_SITE = GRIPPER_PREFIX + "pinch"
# The gripper's own actuator takes 0 (open) to 255 (closed).
GRIPPER_CLOSED_CTRL = 255.0


@dataclass(frozen=True)
class BlockSpec:
    outline: list[tuple[float, float]]  # corners around the centre of mass, metres, anticlockwise
    thickness: float
    density: float
    x: float  # where the centre of mass starts
    y: float
    yaw: float
    rgba: tuple[float, float, float, float]


def build(block: BlockSpec, target: tuple[float, float]) -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(ARM_XML))
    spec.option.timestep = TIMESTEP
    # The gripper model's own settings; attaching it does not carry them over.
    # An elliptic friction cone with a high impratio keeps a pinched block
    # from creeping out of the fingers.
    spec.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    spec.option.impratio = 10

    gripper = mujoco.MjSpec.from_file(str(GRIPPER_XML))
    spec.attach(gripper, prefix=GRIPPER_PREFIX, site=spec.site("attachment_site"))

    # A real UR controller cancels gravity itself. The model's position
    # actuators do not, and without this the arm sags 5 to 10 mm below every
    # position it is sent to.
    for body in spec.bodies:
        if body.name != "world":
            body.gravcomp = 1.0

    world = spec.worldbody
    spec.visual.global_.offwidth = CAMERA.width
    spec.visual.global_.offheight = CAMERA.height
    world.add_light(pos=[0.5, 0, 2.0], dir=[0, 0, -1], diffuse=[0.45, 0.45, 0.45])
    world.add_geom(
        name="table",
        type=mujoco.mjtGeom.mjGEOM_PLANE,
        size=[1.5, 1.5, 0.05],
        rgba=[0.55, 0.5, 0.45, 1],
    )
    world.add_camera(name="overhead", pos=list(CAMERA.pos), fovy=CAMERA.fovy)

    # The target: a flat red ring, drawn only. It has no collision, and it is
    # thinner than the camera can resolve, so the depth picture never sees it.
    world.add_geom(
        name="target",
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        size=[0.02, 0.0005, 0],
        pos=[target[0], target[1], 0.0005],
        rgba=[0.85, 0.1, 0.1, 1],
        contype=0,
        conaffinity=0,
    )

    add_block(spec, block)
    model = spec.compile()
    return model


def add_block(spec: mujoco.MjSpec, block: BlockSpec) -> None:
    """The block is its outline pushed up into a solid, as a convex mesh."""
    corners = [(x, y, z) for z in (0.0, block.thickness) for x, y in block.outline]
    mesh = spec.add_mesh(name="block_mesh")
    mesh.uservert = [c for corner in corners for c in corner]
    body = spec.worldbody.add_body(
        name="block",
        pos=[block.x, block.y, 0.0],
        quat=[math.cos(block.yaw / 2), 0, 0, math.sin(block.yaw / 2)],
    )
    body.add_freejoint(name="block_joint")
    # condim 4 adds friction against turning about the contact normal, so a
    # block held off its centre of mass does not swing round in the fingers.
    body.add_geom(
        name="block",
        type=mujoco.mjtGeom.mjGEOM_MESH,
        meshname="block_mesh",
        density=block.density,
        rgba=list(block.rgba),
        friction=[1.0, 0.01, 0.001],
        condim=4,
    )


def arm_joint_ids(model: mujoco.MjModel) -> np.ndarray:
    return np.array([model.joint(name).qposadr[0] for name in ARM_JOINTS])


def reset_to_home(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[arm_joint_ids(model)] = HOME
    data.ctrl[:6] = HOME
    data.ctrl[6] = 0.0
    mujoco.mj_forward(model, data)
