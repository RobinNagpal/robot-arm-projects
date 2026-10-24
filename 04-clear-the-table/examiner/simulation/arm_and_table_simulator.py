"""A crowded table, a real arm, and the physics to push glasses with it.

Problem 3's simulator moves its hand as a box that a script carries along a path.
Here, the hand is on a UR5e whose six joints are driven by position servos, and a
path is a joint trajectory that MoveIt planned. The glasses, the table, the friction
and the measurement error are the same objects, from this problem's copy of problem
3's common simulator, so a push here meets the same glasses a push there does.

The class inherits problem 4's ``TableSimulator`` for everything that is about the
*table*: the glasses, ``look()``, ``position()``, ``tilt()``, ``on_table()``.
What it replaces is everything about the *hand*: it builds a different world,
and it moves the hand by running joint trajectories.

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

import mujoco
import numpy as np
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

from examiner.simulation import table_draw, ur5e_model
from examiner.simulation.table_simulator import TableSimulator
from examiner.simulation.taken_from_problem_3 import (  # noqa: F401  (the physics constants are re-exported for callers)
    JAW_FRICTION,
    JAW_PARTS,
    SETTLE,
    STANDING_TILT_DEG,
    TABLE_FRICTION,
    TIMESTEP,
    TOUCH_FORCE,
    WRIST_ACROSS,
    WRIST_LENGTH,
    SpawnedGlass,
    Waypoint,
    glass_xml,
)
from examiner.simulation.ur5e_model import ARM_JOINTS, FINGERTIP_OFFSET

# Stiffness of each joint's servo, and the damping that stops it ringing. The
# wrist joints carry far less inertia than the shoulder, so one pair of numbers
# for all six would be either sluggish at the shoulder or unstable at the wrist.
#
# The ratio of damping to stiffness is the servo's lag: a joint moving at
# w rad/s trails its command by about (kv / kp) * w. A ratio of 0.1 left the
# hand 0.15 rad behind during a fast move and a ratio of 0.008 leaves it about
# a hundredth of a radian behind, measured in proto_gains.py. Going stiffer
# than this bought nothing further.
JOINT_SERVO_STIFFNESS = tuple(3.0 * k for k in (4000.0, 6000.0, 3000.0, 800.0, 800.0, 400.0))
JOINT_SERVO_DAMPING = tuple(0.008 * k for k in JOINT_SERVO_STIFFNESS)

# Where the arm waits, and where it starts every table: out of the way of the
# glass zone with the hand pointing at the zone, a posture MoveIt can leave in
# any direction. It is not a measurement; it is where the arm is parked.
PARKED_JOINT_ANGLES = (-0.9, -1.45, 1.75, -1.85, -1.5708, -0.9)

# A trajectory is sampled at the servo's own rate, and the arm is then given
# this long to arrive at the last point before the next thing happens.
SETTLE_SECONDS_AFTER_MOTION = 0.25


def _hand_boxes_xml(skin: str) -> str:
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


def arm_table_and_glasses_world_xml(glasses: list, urdf, meshes, draw_arm: bool = True) -> str:
    """The table, the glasses, the arm and its hand, as one MuJoCo world."""
    description = ur5e_model.ArmDescriptionFromUrdf(urdf, meshes)
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    skin = f'friction="{JAW_FRICTION} 0.005 0.0001" contype="2" conaffinity="1" rgba="0.6 0.6 0.62 1"'
    glass_bodies = "".join(glass_xml(i, g) for i, g in enumerate(glasses))
    return f"""
<mujoco model="crowded table with an arm">
  <compiler angle="radian"/>
  <option timestep="{TIMESTEP}" cone="elliptic" impratio="10" integrator="implicitfast"/>
  <asset>
    {description.mesh_assets_xml()}
  </asset>
  <worldbody>
    <light pos="0.4 0 2.5"/>
    <geom name="table" type="plane" size="{half_x} {half_y} 0.01"
          pos="{TABLE_CENTRE_XY[0]} {TABLE_CENTRE_XY[1]} {TABLE_TOP_Z}"
          friction="{TABLE_FRICTION} 0.005 0.0001" priority="1" rgba="0.75 0.6 0.45 1"/>
    {glass_bodies}
    {description.link_chain_xml(_hand_boxes_xml(skin))}
  </worldbody>
  <actuator>
    {description.joint_servos_xml(1.0, 1.0)}
  </actuator>
</mujoco>"""


@dataclass(frozen=True)
class TrajectoryRunResult:
    """What happened while one joint trajectory was carried out."""

    arm_seconds: float  # arm time: the length of the trajectory itself
    peak_force: float  # the largest contact force on the hand, newtons
    first_touch_seconds: float | None  # seconds into the trajectory when the hand first touched a glass
    worst_joint_tracking_error: (
        float  # the worst gap between the commanded and the real joint angles, radians
    )
    first_touch_fingertips: Waypoint | None = None  # where the fingertips were at the first touch


class ArmAndTableSimulator(TableSimulator):
    """One table, with the whole arm standing at it."""

    def __init__(
        self, seed: int, glasses: list | None = None, *, urdf, meshes, start_joint_angles=PARKED_JOINT_ANGLES
    ) -> None:
        self.seed = seed
        self.glasses = glasses if glasses is not None else table_draw.draw_table(seed)
        self.model = mujoco.MjModel.from_xml_string(
            arm_table_and_glasses_world_xml(self.glasses, urdf, meshes)
        )
        # The servo gains differ joint by joint; the xml carried placeholders.
        for k, name in enumerate(ARM_JOINTS):
            actuator = self.model.actuator(name)
            actuator.gainprm[0] = JOINT_SERVO_STIFFNESS[k]
            actuator.biasprm[1] = -JOINT_SERVO_STIFFNESS[k]
            actuator.biasprm[2] = -JOINT_SERVO_DAMPING[k]
        self.data = mujoco.MjData(self.model)
        self.bodies = [self.model.body(f"glass_{i}").id for i in range(len(self.glasses))]
        self.joint_address_of_each_arm_joint = [self.model.joint(name).qposadr[0] for name in ARM_JOINTS]
        self.hand_geoms = {self.model.geom(f"hand_{part['name']}").id for part in JAW_PARTS} | {
            self.model.geom("hand_wrist").id
        }
        # Every arm link counts too: an elbow that strikes a glass is as much a
        # topple as a fingertip that does.
        arm_bodies = {self.model.body(name).id for name in ur5e_model._LINK_CHAIN} | {
            self.model.body("tool0").id
        }
        self.jaw_geoms = self.hand_geoms | {
            g for g in range(self.model.ngeom) if self.model.geom_bodyid[g] in arm_bodies
        }
        self.tool_body = self.model.body("tool0").id
        self.records: list = []
        self.looks = 0
        self.seconds = 0.0
        self.arm_seconds = 0.0
        self._physics_steps = 0
        self.after_each_physics_step: list = []  # functions called with the simulator after every step
        self.set_joint_angles(start_joint_angles)
        self._settle()
        self.start = [self.position(i) for i in range(len(self.glasses))]

    # ----------------------------------------------------------------- the arm

    def joint_angles(self) -> np.ndarray:
        return np.array([self.data.qpos[address] for address in self.joint_address_of_each_arm_joint])

    def set_joint_angles(self, joint_angles) -> None:
        """Put the arm at ``joint_angles`` with no motion, and hold it there."""
        for address, value in zip(self.joint_address_of_each_arm_joint, joint_angles, strict=True):
            self.data.qpos[address] = value
        self.data.ctrl[: len(ARM_JOINTS)] = joint_angles
        self.data.qvel[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def fingertips_waypoint(self) -> Waypoint:
        """Where the fingertips are, in the numbers a path is written in."""
        axes = self.data.xmat[self.tool_body].reshape(3, 3)
        pointing = axes[:, 2]
        tip = self.data.xpos[self.tool_body] + FINGERTIP_OFFSET * pointing
        return Waypoint(
            float(tip[0]), float(tip[1]), float(tip[2] - TABLE_TOP_Z), math.atan2(pointing[1], pointing[0])
        )

    def run_joint_trajectory(self, times: np.ndarray, joint_angles: np.ndarray) -> TrajectoryRunResult:
        """Carry out a joint trajectory: the arm is commanded along it and the physics follows.

        ``times`` are seconds from the start and ``joint_angles`` the six joint
        angles at each. The command between two samples is the straight line
        between them, which at MoveIt's sampling is finer than the servo can
        resolve. The trajectory's length is the arm time it cost.
        """
        started = time.perf_counter()
        times = np.asarray(times, dtype=float)
        joint_angles = np.asarray(joint_angles, dtype=float)
        duration = float(times[-1])
        physics_steps = max(1, round((duration + SETTLE_SECONDS_AFTER_MOTION) / TIMESTEP))
        peak_force, first_touch_seconds, worst_tracking_error, first_touch_fingertips = 0.0, None, 0.0, None
        wrench = np.zeros(6)
        glass_geoms = {g for g in range(self.model.ngeom) if self.model.geom_bodyid[g] in set(self.bodies)}
        for step in range(1, physics_steps + 1):
            seconds_in = step * TIMESTEP
            command = np.array(
                [
                    np.interp(min(seconds_in, duration), times, joint_angles[:, joint])
                    for joint in range(len(ARM_JOINTS))
                ]
            )
            self.data.ctrl[: len(ARM_JOINTS)] = command
            mujoco.mj_step(self.model, self.data)
            self._physics_steps += 1
            for call in self.after_each_physics_step:
                call(self)
            if step % 5 == 0:
                worst_tracking_error = max(
                    worst_tracking_error, float(np.abs(self.joint_angles() - command).max())
                )
                force = self._contact_force_between_arm_and_glasses(glass_geoms, wrench)
                peak_force = max(peak_force, force)
                if first_touch_seconds is None and force > TOUCH_FORCE:
                    first_touch_seconds, first_touch_fingertips = seconds_in, self.fingertips_waypoint()
        self.seconds += time.perf_counter() - started
        self.arm_seconds += duration
        return TrajectoryRunResult(
            duration, peak_force, first_touch_seconds, worst_tracking_error, first_touch_fingertips
        )

    def _contact_force_between_arm_and_glasses(self, glass_geoms: set, wrench: np.ndarray) -> float:
        """The force between anything of the arm's and any glass, as a wrist sensor reads the push."""
        summed_force = np.zeros(3)
        contacts = self.data.contact
        for k in range(self.data.ncon):
            one, other = contacts.geom1[k], contacts.geom2[k]
            if (one in self.jaw_geoms and other in glass_geoms) or (
                other in self.jaw_geoms and one in glass_geoms
            ):
                mujoco.mj_contactForce(self.model, self.data, k, wrench)
                summed_force += contacts.frame[k].reshape(3, 3).T @ wrench[:3]
        return float(np.linalg.norm(summed_force))

    def arm_presses_on_table(self) -> bool:
        """Whether any part of the hand or the arm is pressing on the table top."""
        table = self.model.geom("table").id
        contacts = self.data.contact
        for k in range(self.data.ncon):
            pair = {contacts.geom1[k], contacts.geom2[k]}
            if table in pair and pair & self.jaw_geoms:
                return True
        return False

    def count_toppled_glasses(self) -> int:
        return sum(1 for i in self.on_table() if self.tilt(i) >= STANDING_TILT_DEG)
