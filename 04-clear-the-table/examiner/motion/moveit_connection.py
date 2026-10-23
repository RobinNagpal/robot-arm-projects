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

from examiner.simulation.ur5e_model import tool_pose

HERE = Path(__file__).resolve().parent
# The examiner's folder, which keeps the ROS environment and what is generated for it.
EXAMINER = HERE.parent
# The ROS environment, the arm's description and MoveIt's settings: see examiner/ros/README.md.
ROS_FOLDER = EXAMINER / "ros"
ROS = ROS_FOLDER / ".pixi" / "envs" / "default"
GENERATED = EXAMINER / "generated"
URDF = GENERATED / "work_cell.urdf"
MESHES = ROS / "share" / "ur_description" / "meshes" / "ur5e" / "collision"


PROFILE = """<?xml version="1.0" encoding="UTF-8" ?>
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


def generate_urdf() -> Path:
    """Write the arm's URDF if it is not there yet: the xacro the Gazebo cell is built from.

    One description serves MoveIt, which plans on it, and the simulator, which
    reads the link lengths out of it, so the two cannot disagree.
    """
    if URDF.exists():
        return URDF
    GENERATED.mkdir(exist_ok=True)
    environment = _ros_environment()
    subprocess.run(
        [
            str(ROS / "bin" / "xacro"),
            str(ROS_FOLDER / "arm" / "arm.urdf.xacro"),
            "controllers_file:=/dev/null",
            "-o",
            str(URDF),
        ],
        check=True,
        env=environment,
        capture_output=True,
    )
    return URDF


def _ros_environment(domain: int = 0) -> dict:
    environment = dict(os.environ)
    environment["AMENT_PREFIX_PATH"] = str(ROS)
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
    profile = GENERATED / "fastdds-udp.xml"
    if not profile.exists():
        GENERATED.mkdir(exist_ok=True)
        profile.write_text(PROFILE)
    environment["FASTRTPS_DEFAULT_PROFILES_FILE"] = str(profile)
    return environment


def quaternion(rotation: np.ndarray) -> list[float]:
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


def flange_goal(x: float, y: float, z: float, heading: float, without: str | None = None) -> dict:
    """The flange pose that puts the fingertips at (x, y, z) pointing along ``heading``.

    ``z`` is in the world, not above the table. The hand is rolled, so the
    fingers stack vertically; see ``ur5e_model.tool_pose``.
    """
    position, rotation = tool_pose(x, y, z, heading)
    goal = {"position": position.tolist(), "quaternion": quaternion(rotation)}
    if without is not None:
        # Name of a box the line may pass through, because the line ends in
        # touching it. Everything else in the scene still counts.
        goal["without"] = without
    return goal


@dataclass(frozen=True)
class Motion:
    """A trajectory MoveIt made: joint angles and the time each is reached."""

    ok: bool
    why: str
    times: np.ndarray
    joints: np.ndarray
    planning_seconds: float

    @property
    def seconds(self) -> float:
        return float(self.times[-1]) if self.ok and len(self.times) else 0.0


class MoveItLink:
    """A running MoveIt, asked for motions over a pipe."""

    # How long MoveIt gets to come up. It takes about a second. Now and then the
    # middleware it sits on waits forever for a lock while creating a node, and
    # nothing ever wakes it; a server that is not ready by now is killed and
    # started again.
    START_SECONDS = 40.0
    START_TRIES = 4

    def __init__(self, domain: int | None = None) -> None:
        import select

        # One ROS domain per process. Servers started in one domain hear each
        # other's planning scenes, and a box another process put in the world
        # is a box this one plans round; so by default the domain is the
        # process's own number.
        if domain is None:
            domain = os.getpid()

        urdf = generate_urdf()
        log = open(GENERATED / f"moveit-{os.getpid()}.log", "w")  # noqa: SIM115  (kept open for the server's life)
        for attempt in range(self.START_TRIES):
            self.process = subprocess.Popen(
                [str(ROS / "bin" / "python"), str(HERE / "moveit_server.py"), str(urdf)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=log,
                env=_ros_environment(domain + 17 * attempt),
                text=True,
                bufsize=1,
            )
            ready, _, _ = select.select([self.process.stdout], [], [], self.START_SECONDS)
            if ready:
                first = self._read()
                if first.get("ready"):
                    break
            self.process.kill()
            self.process.wait()
        else:
            raise RuntimeError(
                "MoveIt did not start after several tries; see examiner/generated/moveit-*.log"
            )
        self.log = log
        self.requests = 0
        self.planning_seconds = 0.0

    def _read(self) -> dict:
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("MoveIt closed its pipe; see examiner/generated/moveit-*.log")
        return json.loads(line)

    def _ask(self, request: dict) -> dict:
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        self.requests += 1
        return self._read()

    def scene(self, boxes: list[dict]) -> None:
        answer = self._ask({"cmd": "scene", "boxes": boxes})
        if not answer["ok"]:
            raise RuntimeError(answer["why"])

    def fk(self, q) -> np.ndarray:
        return np.array(self._ask({"cmd": "fk", "q": list(map(float, q))})["matrix"])

    def plan(
        self,
        q,
        goal: dict | None,
        *,
        then: list | None = None,
        vel: float = 0.5,
        acc: float = 0.5,
        planning_time: float = 3.0,
        attempts: int = 3,
        goal_joints=None,
    ) -> Motion:
        """A free move to a flange pose, planned by OMPL around the scene."""
        return self._motion(
            {
                "cmd": "plan",
                "q": list(map(float, q)),
                "goal": goal,
                "goal_joints": None if goal_joints is None else list(map(float, goal_joints)),
                "seeds": self.seeds(goal) if goal else [],
                "then": then or [],
                "vel": vel,
                "acc": acc,
                "planning_time": planning_time,
                "attempts": attempts,
            }
        )

    def seeds(self, goal: dict) -> list:
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

    def ik(self, q, goal: dict, then: list | None = None) -> list | None:
        answer = self._ask(
            {
                "cmd": "ik",
                "q": list(map(float, q)),
                "goal": goal,
                "seeds": self.seeds(goal),
                "then": then or [],
            }
        )
        return answer["q"] if answer["ok"] else None

    def line(
        self, q, goal: dict, *, vel: float = 0.1, acc: float = 0.1, step: float = 0.005, check: bool = True
    ) -> Motion:
        """A straight line of the flange to a pose, solved and timed by MoveIt."""
        return self._motion(
            {
                "cmd": "line",
                "q": list(map(float, q)),
                "goal": goal,
                "vel": vel,
                "acc": acc,
                "step": step,
                "check": check,
            }
        )

    def _motion(self, request: dict) -> Motion:
        answer = self._ask(request)
        self.planning_seconds += answer.get("planning_seconds", 0.0)
        if not answer["ok"]:
            return Motion(
                False,
                answer.get("why", ""),
                np.zeros(0),
                np.zeros((0, 6)),
                answer.get("planning_seconds", 0.0),
            )
        return Motion(
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
        self.log.close()

    def __enter__(self) -> MoveItLink:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


if __name__ == "__main__":  # a smoke test: start MoveIt and ask for one thing
    with MoveItLink() as link:
        q = [-0.9, -1.45, 1.75, -1.85, -1.5708, -0.9]
        print(np.round(link.fk(q), 3), file=sys.stderr)
