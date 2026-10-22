"""A crowded table, a real arm, and the physics to push glasses with it.

This is problem 3's bench with its one simplification taken out. There, the
hand is a box that a script teleports along a path. Here, the hand is on a
UR5e whose six joints are driven by position servos, and a path is a joint
trajectory that MoveIt planned. The glasses, the table, the friction, the
measurement error and the scoring are the same objects, from this problem's copy
of problem 3's bench, so a number from here can be set beside a number from the
top-down solutions.

The class inherits ``Bench`` for everything that is about the *table*: the
glasses, ``look()``, ``position()``, ``tilt()``, ``take()``, ``on_table()``.
What it replaces is everything about the *hand*: it builds a different world,
and it moves the hand by running joint trajectories instead of mocap legs.

**The arm is driven, not teleported.** Each joint has a stiff position servo
and gravity is compensated, so the arm follows a commanded trajectory closely
in free air and yields a little under load. That is what a real arm does, and
it is why a push can be felt: the hand cannot be forced through a glass by a
script that does not care.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import arm_model
import bench as problem_three  # noqa: E402  (problem 3's bench module, by its own name)
import mujoco
import numpy as np
from arm_model import ARM_JOINTS, FINGERTIP_OFFSET
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

from partners import (
    STANDING_TILT_DEG,
    Bench,
    SpawnedGlass,  # noqa: F401  (re-exported for callers)
    Waypoint,
)

TIMESTEP = problem_three.TIMESTEP
SETTLE = problem_three.SETTLE
TABLE_FRICTION = problem_three.TABLE_FRICTION
JAW_FRICTION = problem_three.JAW_FRICTION
JAW_PARTS = problem_three.JAW_PARTS
WRIST_ACROSS = problem_three.WRIST_ACROSS
WRIST_LENGTH = problem_three.WRIST_LENGTH

# Stiffness of each joint's servo, and the damping that stops it ringing. The
# wrist joints carry far less inertia than the shoulder, so one pair of numbers
# for all six would be either sluggish at the shoulder or unstable at the wrist.
#
# The ratio of damping to stiffness is the servo's lag: a joint moving at
# w rad/s trails its command by about (kv / kp) * w. A ratio of 0.1 left the
# hand 0.15 rad behind during a fast move and a ratio of 0.008 leaves it about
# a hundredth of a radian behind, measured in proto_gains.py. Going stiffer
# than this bought nothing further.
KP = tuple(3.0 * k for k in (4000.0, 6000.0, 3000.0, 800.0, 800.0, 400.0))
KV = tuple(0.008 * k for k in KP)

# Where the arm waits, and where it starts every table: out of the way of the
# glass zone with the hand pointing at the zone, a posture MoveIt can leave in
# any direction. It is not a measurement; it is where the arm is parked.
READY = (-0.9, -1.45, 1.75, -1.85, -1.5708, -0.9)

# A trajectory is sampled at the servo's own rate, and the arm is then given
# this long to arrive at the last point before the next thing happens.
HOLD_AFTER = 0.25


def _hand_xml(skin: str) -> str:
    """The shut, rolled hand as boxes in the tool's own axes.

    The tool's z axis is the way the fingers point and its x axis is the way
    they would open. Problem 3 draws the hand in its own axes (x forward, z
    tall), so each box is moved across: forward becomes tool z, tall becomes
    tool x, and across stays tool y.
    """
    boxes = []
    pieces = list(JAW_PARTS) + [
        {
            "name": "wrist",
            "back": max(p["back"] + p["depth"] for p in JAW_PARTS),
            "depth": WRIST_LENGTH,
            "across": WRIST_ACROSS,
            "tall": WRIST_ACROSS,
        }
    ]
    for part in pieces:
        along = FINGERTIP_OFFSET - (part["back"] + part["depth"] / 2.0)
        boxes.append(
            f'<geom name="hand_{part["name"]}" type="box" '
            f'size="{part["tall"] / 2:.5f} {part["across"] / 2:.5f} {part["depth"] / 2:.5f}" '
            f'pos="0 0 {along:.5f}" {skin}/>'
        )
    return "\n      ".join(boxes)


def world_xml(glasses: list, urdf, meshes, draw_arm: bool = True) -> str:
    """The table, the glasses, the arm and its hand, as one MuJoCo world."""
    description = arm_model.ArmDescription(urdf, meshes)
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    skin = f'friction="{JAW_FRICTION} 0.005 0.0001" contype="2" conaffinity="1" rgba="0.6 0.6 0.62 1"'
    glass_xml = "".join(problem_three._glass_xml(i, g) for i, g in enumerate(glasses))
    return f"""
<mujoco model="crowded table with an arm">
  <compiler angle="radian"/>
  <option timestep="{TIMESTEP}" cone="elliptic" impratio="10" integrator="implicitfast"/>
  <asset>
    {description.mesh_assets()}
  </asset>
  <worldbody>
    <light pos="0.4 0 2.5"/>
    <geom name="table" type="plane" size="{half_x} {half_y} 0.01"
          pos="{TABLE_CENTRE_XY[0]} {TABLE_CENTRE_XY[1]} {TABLE_TOP_Z}"
          friction="{TABLE_FRICTION} 0.005 0.0001" priority="1" rgba="0.75 0.6 0.45 1"/>
    {glass_xml}
    {description.chain_xml(_hand_xml(skin))}
  </worldbody>
  <actuator>
    {description.actuators(1.0, 1.0)}
  </actuator>
</mujoco>"""


@dataclass(frozen=True)
class Ran:
    """What happened while one joint trajectory was carried out."""

    seconds: float  # arm time: the length of the trajectory itself
    peak_force: float  # the largest contact force on the hand, newtons
    touched_at: float | None  # seconds into the trajectory when the hand first touched a glass
    tracking_error: float  # the worst gap between the commanded and the real joint angles, radians
    touch_at: Waypoint | None = None  # where the fingertips were at the first touch


class ArmBench(Bench):
    """One table, with the whole arm standing at it."""

    def __init__(self, seed: int, glasses: list | None = None, *, urdf, meshes, start=READY) -> None:
        self.seed = seed
        self.glasses = glasses if glasses is not None else problem_three.scene(seed)
        self.model = mujoco.MjModel.from_xml_string(world_xml(self.glasses, urdf, meshes))
        # The servo gains differ joint by joint; the xml carried placeholders.
        for k, name in enumerate(ARM_JOINTS):
            actuator = self.model.actuator(name)
            actuator.gainprm[0] = KP[k]
            actuator.biasprm[1] = -KP[k]
            actuator.biasprm[2] = -KV[k]
        self.data = mujoco.MjData(self.model)
        self.bodies = [self.model.body(f"glass_{i}").id for i in range(len(self.glasses))]
        self.joint_addresses = [self.model.joint(name).qposadr[0] for name in ARM_JOINTS]
        self.hand_geoms = {self.model.geom(f"hand_{part['name']}").id for part in JAW_PARTS} | {
            self.model.geom("hand_wrist").id
        }
        # Every arm link counts too: an elbow that strikes a glass is as much a
        # topple as a fingertip that does.
        arm_bodies = {self.model.body(name).id for name in arm_model._CHAIN} | {self.model.body("tool0").id}
        self.jaw_geoms = self.hand_geoms | {
            g for g in range(self.model.ngeom) if self.model.geom_bodyid[g] in arm_bodies
        }
        self.tool = self.model.body("tool0").id
        self.taken: dict[int, bool] = {}
        self.records: list = []
        self.looks = 0
        self.seconds = 0.0
        self.arm_seconds = 0.0
        self._steps = 0
        self.hooks: list = []
        self.set_joints(start)
        self._settle()
        self.start = [self.position(i) for i in range(len(self.glasses))]

    # ----------------------------------------------------------------- the arm

    def joints(self) -> np.ndarray:
        return np.array([self.data.qpos[a] for a in self.joint_addresses])

    def set_joints(self, q) -> None:
        """Put the arm at ``q`` with no motion, and hold it there."""
        for address, value in zip(self.joint_addresses, q, strict=True):
            self.data.qpos[address] = value
        self.data.ctrl[: len(ARM_JOINTS)] = q
        self.data.qvel[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def tcp(self) -> Waypoint:
        """Where the fingertips are, in the numbers a path is written in."""
        axes = self.data.xmat[self.tool].reshape(3, 3)
        push = axes[:, 2]
        tip = self.data.xpos[self.tool] + FINGERTIP_OFFSET * push
        return Waypoint(
            float(tip[0]), float(tip[1]), float(tip[2] - TABLE_TOP_Z), math.atan2(push[1], push[0])
        )

    def run(self, times: np.ndarray, positions: np.ndarray) -> Ran:
        """Carry out a joint trajectory: the arm is commanded along it and the physics follows.

        ``times`` are seconds from the start and ``positions`` the six joint
        angles at each. The command between two samples is the straight line
        between them, which at MoveIt's sampling is finer than the servo can
        resolve. The trajectory's length is the arm time it cost.
        """
        started = time.perf_counter()
        times = np.asarray(times, dtype=float)
        positions = np.asarray(positions, dtype=float)
        total = float(times[-1])
        steps = max(1, round((total + HOLD_AFTER) / TIMESTEP))
        peak, touched, worst, where = 0.0, None, 0.0, None
        wrench = np.zeros(6)
        glass_geoms = {g for g in range(self.model.ngeom) if self.model.geom_bodyid[g] in set(self.bodies)}
        for k in range(1, steps + 1):
            t = k * TIMESTEP
            command = np.array(
                [np.interp(min(t, total), times, positions[:, j]) for j in range(len(ARM_JOINTS))]
            )
            self.data.ctrl[: len(ARM_JOINTS)] = command
            mujoco.mj_step(self.model, self.data)
            self._steps += 1
            for hook in self.hooks:
                hook(self)
            if k % 5 == 0:
                worst = max(worst, float(np.abs(self.joints() - command).max()))
                force = self._hand_on_glass(glass_geoms, wrench)
                peak = max(peak, force)
                if touched is None and force > problem_three.TOUCH_FORCE:
                    touched, where = t, self.tcp()
        self.seconds += time.perf_counter() - started
        self.arm_seconds += total
        return Ran(total, peak, touched, worst, where)

    def _hand_on_glass(self, glass_geoms: set, wrench: np.ndarray) -> float:
        """The force between anything of the arm's and any glass, as a wrist sensor reads the push."""
        total = np.zeros(3)
        contacts = self.data.contact
        for k in range(self.data.ncon):
            a, b = contacts.geom1[k], contacts.geom2[k]
            if (a in self.jaw_geoms and b in glass_geoms) or (b in self.jaw_geoms and a in glass_geoms):
                mujoco.mj_contactForce(self.model, self.data, k, wrench)
                total += contacts.frame[k].reshape(3, 3).T @ wrench[:3]
        return float(np.linalg.norm(total))

    def hand_hits_table(self) -> bool:
        """Whether any part of the hand or the arm is pressing on the table top."""
        table = self.model.geom("table").id
        contacts = self.data.contact
        for k in range(self.data.ncon):
            pair = {contacts.geom1[k], contacts.geom2[k]}
            if table in pair and pair & self.jaw_geoms:
                return True
        return False

    def toppled(self) -> int:
        return sum(1 for i in self.on_table() if self.tilt(i) >= STANDING_TILT_DEG)
