"""The simulator's side of the pipe to MoveIt.

``moveit_server.py`` holds MoveIt in the ROS environment. This file starts it
and speaks to it from problem 4's environment, and does the one piece of
geometry that belongs on this side: turning "put the fingertips here, pointing
this way" into the pose of the flange that MoveIt plans for.

Nothing here decides anything about a motion. A caller passes the pose and the
settings; this file passes them on and hands back the joint trajectory.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from examiner.simulation.ur5e_model import flange_pose_for_fingertips

THIS_FOLDER = Path(__file__).resolve().parent
# The examiner's folder, which keeps the ROS environment and what is generated for it.
EXAMINER_FOLDER = THIS_FOLDER.parent
# The ROS environment, the arm's description and MoveIt's settings: see examiner/ros/README.md.
ROS_FOLDER = EXAMINER_FOLDER / "ros"
ROS_ENVIRONMENT = ROS_FOLDER / ".pixi" / "envs" / "default"
GENERATED_FOLDER = EXAMINER_FOLDER / "generated"
URDF_FILE = GENERATED_FOLDER / "work_cell.urdf"
ARM_COLLISION_MESHES = ROS_ENVIRONMENT / "share" / "ur_description" / "meshes" / "ur5e" / "collision"


FAST_DDS_UDP_PROFILE = """<?xml version="1.0" encoding="UTF-8" ?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <transport_descriptors>
    <transport_descriptor><transport_id>udp_only</transport_id><type>UDPv4</type></transport_descriptor>
  </transport_descriptors>
  <participant profile_name="udp_participant" is_default_profile="true">
    <rtps>
      <useBuiltinTransports>false</useBuiltinTransports>
      <userTransports><transport_id>udp_only</transport_id></userTransports>
    </rtps>
  </participant>
</profiles>
"""


def write_arm_urdf_if_missing() -> Path:
    """Write the arm's URDF if it is not there yet: the xacro the Gazebo cell is built from.

    One description serves MoveIt, which plans on it, and the simulator, which
    reads the link lengths out of it, so the two cannot disagree.
    """
    if URDF_FILE.exists():
        return URDF_FILE
    GENERATED_FOLDER.mkdir(exist_ok=True)
    environment = _ros_environment_variables()
    subprocess.run(
        [
            str(ROS_ENVIRONMENT / "bin" / "xacro"),
            str(ROS_FOLDER / "arm" / "arm.urdf.xacro"),
            "controllers_file:=/dev/null",
            "-o",
            str(URDF_FILE),
        ],
        check=True,
        env=environment,
        capture_output=True,
    )
    return URDF_FILE


def _ros_environment_variables(domain: int = 0) -> dict:
    environment = dict(os.environ)
    environment["AMENT_PREFIX_PATH"] = str(ROS_ENVIRONMENT)
    # Problem 4's own variables would point the ROS interpreter at the wrong
    # libraries, so they are taken out.
    for name in ("PYTHONPATH", "PYTHONHOME", "CONDA_PREFIX", "PIXI_PROJECT_ROOT"):
        environment.pop(name, None)
    # Each server gets a ROS domain of its own so that several running side by
    # side do not discover one another.
    environment["ROS_DOMAIN_ID"] = str(domain % 100)
    # No discovery at all. Servers sharing a domain hear each other's planning
    # scenes, and with a dozen processes running at once two of them can land
    # on the same domain number whatever it is derived from. Nothing here talks
    # to another process over ROS -- the pipe is the only channel -- so each
    # server is simply told to find nobody.
    environment["ROS_AUTOMATIC_DISCOVERY_RANGE"] = "OFF"
    environment.pop("ROS_LOCALHOST_ONLY", None)
    # Fast DDS without shared memory: see generated/fastdds-udp.xml. Written on
    # the spot so that a fresh checkout has it.
    profile = GENERATED_FOLDER / "fastdds-udp.xml"
    if not profile.exists():
        GENERATED_FOLDER.mkdir(exist_ok=True)
        profile.write_text(FAST_DDS_UDP_PROFILE)
    environment["FASTRTPS_DEFAULT_PROFILES_FILE"] = str(profile)
    return environment


def rotation_to_quaternion_xyzw(rotation: np.ndarray) -> list[float]:
    """A rotation matrix as (x, y, z, w), the order ROS messages use."""
    m = rotation
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        return [(m[2, 1] - m[1, 2]) * s, (m[0, 2] - m[2, 0]) * s, (m[1, 0] - m[0, 1]) * s, 0.25 / s]
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        return [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    if m[1, 1] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        return [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
    return [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s]


def flange_goal_for_fingertips(
    x: float, y: float, z: float, heading: float, box_the_line_may_pass_through: str | None = None
) -> dict:
    """The flange pose that puts the fingertips at (x, y, z) pointing along ``heading``.

    ``z`` is in the world, not above the table. The hand is rolled, so the
    fingers stack vertically; see ``ur5e_model.flange_pose_for_fingertips``.
    """
    position, rotation = flange_pose_for_fingertips(x, y, z, heading)
    goal = {"position": position.tolist(), "quaternion": rotation_to_quaternion_xyzw(rotation)}
    if box_the_line_may_pass_through is not None:
        # Name of a box the line may pass through, because the line ends in
        # touching it. Everything else in the scene still counts.
        goal["without"] = box_the_line_may_pass_through
    return goal


@dataclass(frozen=True)
class PlannedMotion:
    """A trajectory MoveIt made: joint angles and the time each is reached."""

    planned: bool
    refusal_reason: str
    times: np.ndarray
    joint_angles: np.ndarray
    planning_seconds: float

    @property
    def duration_seconds(self) -> float:
        return float(self.times[-1]) if self.planned and len(self.times) else 0.0


class MoveItConnection:
    """A running MoveIt, asked for motions over a pipe."""

    # How long MoveIt gets to come up. It takes about a second. Now and then the
    # middleware it sits on waits forever for a lock while creating a node, and
    # nothing ever wakes it; a server that is not ready by now is killed and
    # started again.
    STARTUP_TIMEOUT_SECONDS = 40.0
    STARTUP_ATTEMPTS = 4

    def __init__(self, ros_domain: int | None = None) -> None:
        import select

        # One ROS domain per process. Servers started in one domain hear each
        # other's planning scenes, and a box another process put in the world
        # is a box this one plans round; so by default the domain is the
        # process's own number.
        if ros_domain is None:
            ros_domain = os.getpid()

        urdf = write_arm_urdf_if_missing()
        server_log = open(GENERATED_FOLDER / f"moveit-{os.getpid()}.log", "w")  # noqa: SIM115  (kept open for the server's life)
        for attempt in range(self.STARTUP_ATTEMPTS):
            self.process = subprocess.Popen(
                [str(ROS_ENVIRONMENT / "bin" / "python"), str(THIS_FOLDER / "moveit_server.py"), str(urdf)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=server_log,
                env=_ros_environment_variables(ros_domain + 17 * attempt),
                text=True,
                bufsize=1,
            )
            readable, _, _ = select.select([self.process.stdout], [], [], self.STARTUP_TIMEOUT_SECONDS)
            if readable:
                first_reply = self._read_reply()
                if first_reply.get("ready"):
                    break
            self.process.kill()
            self.process.wait()
        else:
            raise RuntimeError(
                "MoveIt did not start after several tries; see examiner/generated/moveit-*.log"
            )
        self.server_log = server_log
        self.requests_sent = 0
        self.planning_seconds = 0.0

    def _read_reply(self) -> dict:
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("MoveIt closed its pipe; see examiner/generated/moveit-*.log")
        return json.loads(line)

    def _send_request(self, request: dict) -> dict:
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        self.requests_sent += 1
        return self._read_reply()

    def set_collision_boxes(self, boxes: list[dict]) -> None:
        answer = self._send_request({"cmd": "scene", "boxes": boxes})
        if not answer["ok"]:
            raise RuntimeError(answer["why"])

    def forward_kinematics(self, joint_angles) -> np.ndarray:
        return np.array(self._send_request({"cmd": "fk", "q": list(map(float, joint_angles))})["matrix"])

    def plan_free_move(
        self,
        start_joint_angles,
        goal: dict | None,
        *,
        lines_that_follow: list | None = None,
        velocity_scaling: float = 0.5,
        acceleration_scaling: float = 0.5,
        planning_time_seconds: float = 3.0,
        planning_attempts: int = 3,
        goal_joint_angles=None,
    ) -> PlannedMotion:
        """A free move to a flange pose, planned by OMPL around the collision boxes.

        ``lines_that_follow`` are the goals of the straight lines the arm will drive next, so
        that MoveIt picks a posture at the goal from which they can be driven.
        """
        return self._request_motion(
            {
                "cmd": "plan",
                "q": list(map(float, start_joint_angles)),
                "goal": goal,
                "goal_joints": None if goal_joint_angles is None else list(map(float, goal_joint_angles)),
                "seeds": self.inverse_kinematics_seeds(goal) if goal else [],
                "then": lines_that_follow or [],
                "vel": velocity_scaling,
                "acc": acceleration_scaling,
                "planning_time": planning_time_seconds,
                "attempts": planning_attempts,
            }
        )

    def inverse_kinematics_seeds(self, goal: dict) -> list:
        """Postures to start the inverse kinematics from, turned towards the goal.

        An arm facing a point reaches it with the shoulder pointed at it, so the
        pan is set to the bearing of the goal and the rest to a posture that
        holds a level hand out over a table.
        """
        x, y = goal["position"][:2]
        bearing = float(np.arctan2(y, x))
        rows = []
        for pan in (bearing, bearing + 0.7, bearing - 0.7, bearing + 1.4, bearing - 1.4):
            for lift, elbow, wrist1 in (
                (-1.2, 1.7, -2.0),
                (-1.7, 2.1, -2.0),
                (-0.9, 1.2, -1.6),
                (-1.5, -1.7, 3.2),
                (-2.2, 1.9, 0.2),
            ):
                for wrist2 in (-1.5708, 1.5708):
                    rows.append([pan, lift, elbow, wrist1, wrist2, 0.0])
        return rows

    def inverse_kinematics(
        self, start_joint_angles, goal: dict, lines_that_follow: list | None = None
    ) -> list | None:
        answer = self._send_request(
            {
                "cmd": "ik",
                "q": list(map(float, start_joint_angles)),
                "goal": goal,
                "seeds": self.inverse_kinematics_seeds(goal),
                "then": lines_that_follow or [],
            }
        )
        return answer["q"] if answer["ok"] else None

    def plan_straight_line(
        self,
        start_joint_angles,
        goal: dict,
        *,
        velocity_scaling: float = 0.1,
        acceleration_scaling: float = 0.1,
        step_metres: float = 0.005,
        check_collisions: bool = True,
    ) -> PlannedMotion:
        """A straight line of the flange to a pose, solved and timed by MoveIt."""
        return self._request_motion(
            {
                "cmd": "line",
                "q": list(map(float, start_joint_angles)),
                "goal": goal,
                "vel": velocity_scaling,
                "acc": acceleration_scaling,
                "step": step_metres,
                "check": check_collisions,
            }
        )

    def _request_motion(self, request: dict) -> PlannedMotion:
        answer = self._send_request(request)
        self.planning_seconds += answer.get("planning_seconds", 0.0)
        if not answer["ok"]:
            return PlannedMotion(
                False,
                answer.get("why", ""),
                np.zeros(0),
                np.zeros((0, 6)),
                answer.get("planning_seconds", 0.0),
            )
        return PlannedMotion(
            True, "", np.array(answer["t"]), np.array(answer["q"]), answer.get("planning_seconds", 0.0)
        )

    def close(self) -> None:
        try:
            self.process.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
            self.process.stdin.flush()
        except Exception:
            pass
        try:
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()
        self.server_log.close()

    def __enter__(self) -> MoveItConnection:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


if __name__ == "__main__":  # a smoke test: start MoveIt and ask for one thing
    with MoveItConnection() as moveit:
        parked = [-0.9, -1.45, 1.75, -1.85, -1.5708, -0.9]
        print(np.round(moveit.forward_kinematics(parked), 3), file=sys.stderr)
