"""The whole UR5e, standing at the table, as a MuJoCo model.

Problem 3's examiner and problem 4's examiner both push with a hand that floats: a
box-shaped jaw that a script moves wherever it likes. That is the right model
of a hand and the wrong model of a cell, because a real hand is on the end of
an arm, and an arm has joints that run out, links that sweep through the
space beside the hand, and a wrist that has to be somewhere. This module builds
the arm those examiners leave out, so that a path is not only a path for a hand
but a motion for six joints, planned by MoveIt and followed by a servo.

**One description of the arm, shared with MoveIt.** The kinematics are read
from the very URDF that MoveIt plans on (``moveit_connection.generate_urdf`` writes
it), not typed in again here. If the link lengths in this file were copies,
the arm MoveIt thinks it is steering and the arm the physics moves would
disagree by exactly as much as the copies had drifted, and the disagreement
would show up as a hand that arrives somewhere other than where it was sent.

**The hand is problem 3's hand.** The fingers are the same stack of boxes the
other examiners push with, so a result here and a result there differ in the arm
and not in the fingertip. Only the arm's own links are meshes, and they are
the collision meshes Universal Robots publish.

Axes, because they are the one thing here that is easy to get backwards. The
Robotiq opens along the tool's x axis and points along its z axis. Rolled for
a push, the fingers stack one above the other, so the tool's x axis is the
world's vertical and the tool's z axis is the way the hand pushes. ``tool_pose``
builds exactly that and nothing else.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ARM_JOINTS = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)

# The chain from the world to the flange, in the order the URDF nests it.
_CHAIN = (
    "base_link_inertia",
    "shoulder_link",
    "upper_arm_link",
    "forearm_link",
    "wrist_1_link",
    "wrist_2_link",
    "wrist_3_link",
)

# How far the fingertips stand in front of the flange (tool0): the gripper's
# base is 48.5 mm out and the pads' far edge another 149 mm beyond that. It is
# the figure ``work_cell.arm.dimensions`` computes from Robotiq's description;
# it is read from there when the cell package is importable and falls back to
# the same number otherwise, so this file can be tested without the cell.
try:
    from work_cell.arm.dimensions import FINGERTIP_OFFSET
except Exception:  # pragma: no cover - only when the cell package is absent
    FINGERTIP_OFFSET = 0.1979


def _rotation(rpy: tuple[float, float, float]) -> np.ndarray:
    """URDF's roll-pitch-yaw: rotate about fixed x, then y, then z."""
    r, p, y = rpy
    rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    return rz @ ry @ rx


def _quaternion(matrix: np.ndarray) -> np.ndarray:
    """A rotation matrix as MuJoCo's (w, x, y, z)."""
    w = math.sqrt(max(0.0, 1.0 + matrix[0, 0] + matrix[1, 1] + matrix[2, 2])) / 2.0
    if w > 1e-6:
        x = (matrix[2, 1] - matrix[1, 2]) / (4 * w)
        y = (matrix[0, 2] - matrix[2, 0]) / (4 * w)
        z = (matrix[1, 0] - matrix[0, 1]) / (4 * w)
    else:
        x = math.sqrt(max(0.0, 1 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2])) / 2.0
        y = math.copysign(
            math.sqrt(max(0.0, 1 - matrix[0, 0] + matrix[1, 1] - matrix[2, 2])) / 2.0, matrix[0, 1]
        )
        z = math.copysign(
            math.sqrt(max(0.0, 1 - matrix[0, 0] - matrix[1, 1] + matrix[2, 2])) / 2.0, matrix[0, 2]
        )
    return np.array([w, x, y, z])


def _floats(text: str | None, default: str = "0 0 0") -> tuple[float, float, float]:
    a, b, c = (float(v) for v in (text or default).split())
    return a, b, c


def tool_pose(x: float, y: float, z: float, heading: float) -> tuple[np.ndarray, np.ndarray]:
    """Where the flange (tool0) must be for the fingertips to be at (x, y, z) pointing along ``heading``.

    ``z`` is the world height of the fingertips' middle. The returned matrix
    has the tool's z axis along the push and the tool's x axis straight up,
    which is the rolled hand, and the translation is backed off along the push
    by the fingertip offset.
    """
    push = np.array([math.cos(heading), math.sin(heading), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    rotation = np.column_stack([up, np.cross(push, up), push])
    return np.array([x, y, z]) - FINGERTIP_OFFSET * push, rotation


class ArmDescription:
    """The UR5e's links and joints, read out of the URDF MoveIt plans on."""

    def __init__(self, urdf: Path, meshes: Path) -> None:
        self.root = ET.parse(urdf).getroot()
        self.meshes = meshes
        self.joints = {j.get("name"): j for j in self.root.findall("joint")}
        self.links = {link.get("name"): link for link in self.root.findall("link")}
        self.by_parent: dict[str, list[ET.Element]] = {}
        for joint in self.joints.values():
            self.by_parent.setdefault(joint.find("parent").get("link"), []).append(joint)

    def base_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """The base link inertia frame in the world: bolted to the table, turned half a circle."""
        up = self.joints["base_joint"].find("origin")
        flip = self.joints["base_link-base_link_inertia"].find("origin")
        return (
            np.array(_floats(up.get("xyz"))),
            _rotation(_floats(up.get("rpy"))) @ _rotation(_floats(flip.get("rpy"))),
        )

    def mesh_assets(self) -> str:
        names = []
        for link in _CHAIN:
            collision = self.links[link].find("collision")
            path = collision.find("geometry/mesh").get("filename")
            stem = Path(path).stem
            names.append(f'<mesh name="{stem}" file="{self.meshes / Path(path).name}"/>')
        return "\n    ".join(names)

    def chain_xml(self, hand: str, gravcomp: bool = True) -> str:
        """The arm as nested MuJoCo bodies, with ``hand`` hung on the flange."""
        position, rotation = self.base_pose()
        xml = ""
        closing = ""
        for depth, link in enumerate(_CHAIN):
            element = self.links[link]
            if depth == 0:
                pos, quat = position, _quaternion(rotation)
                joint_xml = ""
            else:
                joint = self.joints[ARM_JOINTS[depth - 1]]
                origin = joint.find("origin")
                pos = np.array(_floats(origin.get("xyz")))
                quat = _quaternion(_rotation(_floats(origin.get("rpy"))))
                limit = joint.find("limit")
                joint_xml = (
                    f'<joint name="{joint.get("name")}" type="hinge" axis="0 0 1" '
                    f'range="{float(limit.get("lower")):.5f} {float(limit.get("upper")):.5f}" '
                    f'damping="2" armature="0.05"/>'
                )
            inertial = element.find("inertial")
            mass = float(inertial.find("mass").get("value"))
            centre = _floats(inertial.find("origin").get("xyz"))
            inertia = inertial.find("inertia")
            full = " ".join(inertia.get(k) for k in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"))
            collision = element.find("collision")
            c_origin = collision.find("origin")
            c_pos = _floats(c_origin.get("xyz"))
            c_quat = _quaternion(_rotation(_floats(c_origin.get("rpy"))))
            stem = Path(collision.find("geometry/mesh").get("filename")).stem
            # contype 2: an arm link strikes glasses and the table, which are
            # type 1, and does not strike its own other links, which are also
            # type 2. The base is left out of the table entirely, since it sits
            # on it.
            contype = 'contype="0" conaffinity="0"' if depth == 0 else 'contype="2" conaffinity="1"'
            xml += (
                f'<body name="{link}" pos="{pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}" '
                f'quat="{quat[0]:.8f} {quat[1]:.8f} {quat[2]:.8f} {quat[3]:.8f}"'
                f"{' gravcomp="1"' if gravcomp else ''}>"
                f"{joint_xml}"
                f'<inertial pos="{centre[0]:.6f} {centre[1]:.6f} {centre[2]:.6f}" '
                f'mass="{mass}" fullinertia="{full}"/>'
                f'<geom type="mesh" mesh="{stem}" {contype} rgba="0.55 0.6 0.7 1" '
                f'pos="{c_pos[0]:.6f} {c_pos[1]:.6f} {c_pos[2]:.6f}" '
                f'quat="{c_quat[0]:.8f} {c_quat[1]:.8f} {c_quat[2]:.8f} {c_quat[3]:.8f}"/>'
            )
            closing += "</body>"
        # The flange: wrist_3_link -> flange -> tool0, two fixed joints. Their
        # product is the rotation that turns wrist 3's axes into the tool's.
        flange = self.joints["wrist_3-flange"].find("origin")
        tool = self.joints["flange-tool0"].find("origin")
        turn = _rotation(_floats(flange.get("rpy"))) @ _rotation(_floats(tool.get("rpy")))
        q = _quaternion(turn)
        xml += (
            f'<body name="tool0" pos="0 0 0" quat="{q[0]:.8f} {q[1]:.8f} {q[2]:.8f} {q[3]:.8f}"'
            f"{' gravcomp="1"' if gravcomp else ''}>{hand}</body>"
        )
        return xml + closing

    def actuators(self, kp: float, kv: float) -> str:
        rows = []
        for name in ARM_JOINTS:
            limit = self.joints[name].find("limit")
            rows.append(
                f'<position name="{name}" joint="{name}" kp="{kp}" kv="{kv}" '
                f'ctrlrange="{float(limit.get("lower")):.5f} {float(limit.get("upper")):.5f}" '
                f'forcerange="-{limit.get("effort")} {limit.get("effort")}"/>'
            )
        return "\n    ".join(rows)
