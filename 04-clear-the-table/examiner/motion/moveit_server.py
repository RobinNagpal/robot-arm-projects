"""MoveIt 2, as a small server that the simulator side can ask for motions.

**Why a separate process.** MoveIt runs in the ROS environment, which has no
MuJoCo and no PyTorch; the physics and the learning run in problem 4's own
environment, which has no ROS. Rather than force one environment to hold
both, this file runs in the ROS one and talks to the other over a pipe, one
JSON object per line. The simulator side asks "plan me a motion from here to
there with these settings" and gets back a list of joint angles and times,
which is exactly what a ROS controller would receive from move_group.

**What is MoveIt's and what is not.** Everything about getting the arm from
one pose to another is MoveIt's: the planner (OMPL's RRT-Connect), inverse
kinematics (KDL), the collision world (the table and a box per glass), and the
time parameterisation (time-optimal, scaled by the velocity and acceleration
factors the caller passes). The caller decides *where* and *with what
settings*; this file never chooses either. That split is the point of the
exercise: the learned model supplies the settings, MoveIt does the moving.

Two kinds of motion are offered.

``plan`` is a free move to a pose, planned by OMPL around every box in the
scene. It is for crossing the table to the place a push begins.

``line`` is a straight line of the fingertips, made by solving inverse
kinematics at closely spaced points along it and then handing the resulting
joint path to MoveIt's time parameterisation. It is for the stroke itself,
where the hand must not wander. It is checked against the scene as it goes,
so a line that would put the arm into a box is refused rather than driven.

Protocol, one JSON object in and one out:

    {"cmd": "scene", "boxes": [{"centre": [x,y,z], "size": [sx,sy,sz]}, ...]}
    {"cmd": "plan",  "q": [6], "goal": {"position": [..], "quaternion": [x,y,z,w]}, ...}
    {"cmd": "line",  "q": [6], "goal": {...}, "step": 0.005, ...}
    {"cmd": "fk",    "q": [6]}
    {"cmd": "quit"}
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "ros" / "moveit"
GROUP = "ur_manipulator"
TIP = "tool0"
# The 2F-85 knuckle angle with the fingers closed: the figure in the SRDF.
SHUT_KNUCKLE = 0.7929
JOINTS = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)


def _yaml(name: str) -> dict:
    # A round trip through JSON because the YAML files use anchors, and ROS's
    # parameter reader refuses aliases outright.
    return json.loads(json.dumps(yaml.safe_load((CONFIG / name).read_text())))


class Server:
    def __init__(self, urdf: Path) -> None:
        from moveit.planning import MoveItPy

        config = {
            "robot_description": urdf.read_text(),
            "robot_description_semantic": (CONFIG / "work_cell.srdf").read_text(),
            "robot_description_kinematics": _yaml("kinematics.yaml"),
            "robot_description_planning": _yaml("joint_limits.yaml"),
            "planning_pipelines": {"pipeline_names": ["ompl"]},
            # MoveIt reads this block under its own name twice over: once as the
            # node's parameter prefix and once as the namespace we ask for.
            "plan_request_params": {
                "plan_request_params": {
                    "planning_attempts": 3,
                    "planning_pipeline": "ompl",
                    "planner_id": "RRTConnectkConfigDefault",
                    "planning_time": 3.0,
                    "max_velocity_scaling_factor": 0.5,
                    "max_acceleration_scaling_factor": 0.5,
                }
            },
            "ompl": _yaml("ompl_planning.yaml"),
            "planning_scene_monitor_options": {
                "name": "planning_scene_monitor",
                "robot_description": "robot_description",
                "joint_state_topic": "/joint_states",
                "attached_collision_object_topic": "/moveit_cpp/planning_scene_monitor",
                "publish_planning_scene_topic": "/moveit_cpp/publish_planning_scene",
                "monitored_planning_scene_topic": "/monitored_planning_scene",
                # There is no joint-state publisher here: the caller says where
                # the arm is with every request, so waiting for one would only
                # make the start-up fail.
                "wait_for_initial_state_timeout": 0.0,
            },
        }
        self.moveit = MoveItPy(node_name="push_planner", config_dict=config)
        self.arm = self.moveit.get_planning_component(GROUP)
        self.model = self.moveit.get_robot_model()
        self.monitor = self.moveit.get_planning_scene_monitor()
        self.boxes = 0
        self.world: list[dict] = []

    # ------------------------------------------------------------------ state

    def _state(self, q):
        from moveit.core.robot_state import RobotState

        state = RobotState(self.model)
        state.set_joint_group_positions(GROUP, np.asarray(q, dtype=float))
        # The hand pushes shut, and the physics hand is drawn shut, so MoveIt
        # must plan around the shut hand. Left at its default the fingers
        # stand open, 17 mm further out each side, and the planner would keep
        # a clearance the real hand does not need.
        state.set_joint_group_positions("gripper", np.array([SHUT_KNUCKLE]))
        state.update()
        return state

    def scene(self, boxes: list[dict]) -> dict:
        """Replace the collision world with these boxes. The table is the caller's to include."""
        self.world = [dict(box, id=box.get("id", f"box_{k}")) for k, box in enumerate(boxes)]
        self._apply(self.world)
        return {"ok": True, "boxes": len(boxes)}

    def _apply(self, boxes: list[dict]) -> None:
        from geometry_msgs.msg import Pose
        from moveit_msgs.msg import CollisionObject
        from shape_msgs.msg import SolidPrimitive

        with self.monitor.read_write() as scene:
            scene.remove_all_collision_objects()
            for box in boxes:
                shape = SolidPrimitive()
                shape.type = SolidPrimitive.BOX
                shape.dimensions = [float(v) for v in box["size"]]
                pose = Pose()
                pose.position.x, pose.position.y, pose.position.z = (float(v) for v in box["centre"])
                pose.orientation.w = 1.0
                obj = CollisionObject()
                obj.header.frame_id = "world"
                obj.id = box["id"]
                obj.primitives = [shape]
                obj.primitive_poses = [pose]
                obj.operation = CollisionObject.ADD
                scene.apply_collision_object(obj)
            scene.current_state.update()
        self.boxes = len(boxes)

    def _without(self, name: str | None):
        """The scene with one box taken out, for a stroke that has to touch it."""
        if name is not None:
            self._apply([box for box in self.world if box["id"] != name])

    def _restore(self, name: str | None) -> None:
        if name is not None:
            self._apply(self.world)

    def _pose(self, goal: dict):
        from geometry_msgs.msg import Pose

        pose = Pose()
        pose.position.x, pose.position.y, pose.position.z = (float(v) for v in goal["position"])
        pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w = goal["quaternion"]
        return pose

    def _joints_for(self, goal: dict, seeds: list, then: list | None = None):
        """Joint angles that put the flange at ``goal`` without touching the scene.

        KDL starts from whatever the state holds, so the answer depends on the
        seed, and a UR arm reaches any one pose in up to eight ways. Seeding
        from where the arm is, and then from a few postures that suit a hand
        held level, picks a way that is near the start and not folded under
        the table. The first solution that is collision-free is taken.
        """
        # The shut hand is the same shape upside down, so a pose can be reached
        # with the fingers stacked either way up. That doubles the postures
        # available and, measured over the glass zone, is the difference
        # between reaching about half the pushes and nearly all of them.
        for flipped in (False, True):
            aim = _flipped(goal) if flipped else goal
            later = [_flipped(g) if flipped else g for g in (then or [])]
            pose = self._pose(aim)
            for seed in seeds:
                state = self._state(seed)
                if not state.set_from_ik(GROUP, pose, TIP, 0.05):
                    continue
                state.update()
                q = _nearest(np.array(state.get_joint_group_positions(GROUP)), np.asarray(seed, dtype=float))
                # The lock is taken for the check alone: the lines below
                # rebuild the scene, which needs the lock to itself.
                with self.monitor.read_only() as scene:
                    if not scene.is_state_valid(self._state(q), GROUP):
                        continue
                # The posture is only any good if the straight lines that
                # follow it can be driven from it: a posture that reaches the
                # first pose but hits the table on the way down to the second
                # is the wrong one of the eight.
                here, good = q, True
                for goal_after in later:
                    path, _ = self._walk(here, goal_after, 0.01)
                    if path is None:
                        good = False
                        break
                    here = path[-1]
                if good:
                    return q.tolist(), flipped
        return None, False

    def ik(self, request: dict) -> dict:
        found, flipped = self._joints_for(
            request["goal"], [request["q"], *request.get("seeds", [])], request.get("then")
        )
        return {
            "ok": found is not None,
            "flipped": flipped,
            "q": found,
            "why": "" if found else "no collision-free solution",
        }

    def fk(self, q) -> dict:
        state = self._state(q)
        matrix = np.array(state.get_global_link_transform(TIP))
        return {"ok": True, "matrix": matrix.tolist()}

    # ----------------------------------------------------------------- motion

    def plan(self, request: dict) -> dict:
        """A free move, planned by OMPL around the scene."""
        from moveit.planning import PlanRequestParameters

        started = time.perf_counter()
        self.arm.set_start_state(robot_state=self._state(request["q"]))
        if request.get("goal_joints") is not None:
            # A place the caller already knows the arm can stand: no inverse
            # kinematics, so no chance of being handed a different posture.
            target = list(request["goal_joints"])
        else:
            seeds = [request["q"], *request.get("seeds", [])]
            target, flipped = self._joints_for(request["goal"], seeds, request.get("then"))
        if target is None:
            return {
                "ok": False,
                "why": "no collision-free joint angles reach the goal",
                "planning_seconds": time.perf_counter() - started,
            }
        self.arm.set_goal_state(robot_state=self._state(target))
        parameters = PlanRequestParameters(self.moveit, "plan_request_params")
        parameters.planner_id = request.get("planner", "RRTConnectkConfigDefault")
        parameters.planning_time = float(request.get("planning_time", 3.0))
        parameters.planning_attempts = int(request.get("attempts", 3))
        parameters.max_velocity_scaling_factor = float(request.get("vel", 0.5))
        parameters.max_acceleration_scaling_factor = float(request.get("acc", 0.5))
        # OMPL is random, and its answer is then checked again at a finer
        # resolution by MoveIt's own ValidateSolution adapter, which can reject a
        # path the planner thought was clear when it skims a box. A second draw
        # nearly always goes round, so a refusal is only reported after a few.
        for _ in range(int(request.get("redraws", 4))):
            result = self.arm.plan(single_plan_parameters=parameters)
            if result:
                break
        took = time.perf_counter() - started
        if not result:
            return {"ok": False, "why": "no plan found", "planning_seconds": took}
        return {**_unpack(result.trajectory), "planning_seconds": took}

    def _walk(self, q, goal: dict, step: float, check: bool = True, debug: bool = False):
        """Joint angles along a straight line of the flange, or the reason there are none.

        Each point is solved from the one before it, so the arm stays in one
        posture. A jump between neighbours means the solver changed posture,
        and a straight stroke must never do that.
        """
        self._without(goal.get("without"))
        try:
            return self._walk_in_scene(q, goal, step, check, debug)
        finally:
            self._restore(goal.get("without"))

    def _walk_in_scene(self, q, goal: dict, step: float, check: bool, debug: bool):
        state = self._state(q)
        start = np.array(state.get_global_link_transform(TIP))
        end_position = np.array(goal["position"], dtype=float)
        length = float(np.linalg.norm(end_position - start[:3, 3]))
        pieces = max(1, int(np.ceil(length / step)))
        path = [np.asarray(q, dtype=float)]
        with self.monitor.read_only() as scene:
            for k in range(1, pieces + 1):
                at = start[:3, 3] + (end_position - start[:3, 3]) * (k / pieces)
                pose = self._pose({"position": at, "quaternion": goal["quaternion"]})
                if not state.set_from_ik(GROUP, pose, TIP, 0.02):
                    return None, f"no joint angles reach point {k} of {pieces}"
                state.update()
                if check and not scene.is_state_valid(state, GROUP, debug):
                    return None, f"the arm would touch the scene at point {k} of {pieces}"
                path.append(np.array(state.get_joint_group_positions(GROUP)))
                if np.abs(path[-1] - path[-2]).max() > 0.35:
                    return None, "the arm would change posture mid-line"
        return path, ""

    def line(self, request: dict) -> dict:
        """A straight line of the fingertips, solved by inverse kinematics and timed by MoveIt."""
        from moveit.core.robot_trajectory import RobotTrajectory
        from moveit_msgs.msg import RobotTrajectory as RobotTrajectoryMsg
        from trajectory_msgs.msg import JointTrajectoryPoint

        started = time.perf_counter()
        path, why = self._walk(
            request["q"],
            request["goal"],
            float(request.get("step", 0.005)),
            request.get("check", True),
            bool(request.get("debug")),
        )
        if path is None:
            return {"ok": False, "why": why}
        message = RobotTrajectoryMsg()
        message.joint_trajectory.joint_names = list(JOINTS)
        for q in path:
            point = JointTrajectoryPoint()
            point.positions = [float(v) for v in q]
            message.joint_trajectory.points.append(point)
        trajectory = RobotTrajectory(self.model)
        trajectory.set_robot_trajectory_msg(self._state(request["q"]), message)
        trajectory.joint_model_group_name = GROUP
        if not trajectory.apply_totg_time_parameterization(
            float(request.get("vel", 0.1)), float(request.get("acc", 0.1))
        ):
            return {"ok": False, "why": "the line could not be timed"}
        return {**_unpack(trajectory), "planning_seconds": time.perf_counter() - started}


def _flipped(goal: dict) -> dict:
    """The same goal with the hand turned half a turn about its own pointing axis."""
    x1, y1, z1, w1 = goal["quaternion"]
    x2, y2, z2, w2 = 0.0, 0.0, 1.0, 0.0
    quaternion = [
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    ]
    return {**goal, "quaternion": quaternion}


def _nearest(q: np.ndarray, seed: np.ndarray) -> np.ndarray:
    """Each angle moved by whole turns to sit as close to the seed as the joint limits allow."""
    limits = np.array([2 * np.pi, 2 * np.pi, np.pi, 2 * np.pi, 2 * np.pi, 2 * np.pi])
    out = q.copy()
    for k in range(len(q)):
        turns = np.round((seed[k] - q[k]) / (2 * np.pi))
        candidate = q[k] + turns * 2 * np.pi
        out[k] = candidate if abs(candidate) <= limits[k] else q[k]
    return out


def _unpack(trajectory) -> dict:
    message = trajectory.get_robot_trajectory_msg()
    points = message.joint_trajectory.points
    names = list(message.joint_trajectory.joint_names)
    order = [names.index(j) for j in JOINTS]
    times = [p.time_from_start.sec + p.time_from_start.nanosec * 1e-9 for p in points]
    q = [[p.positions[i] for i in order] for p in points]
    return {"ok": True, "t": times, "q": q}


def main() -> None:
    # The pipe back to the caller is a private copy of stdout, and stdout itself
    # is pointed at stderr: ROS and its libraries print to it freely, and one
    # stray line there would corrupt the protocol.
    reply = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    server = Server(Path(sys.argv[1]))
    reply.write(json.dumps({"ok": True, "ready": True}) + "\n")
    reply.flush()
    for line in sys.stdin:
        request = json.loads(line)
        command = request["cmd"]
        if command == "quit":
            break
        try:
            answer = getattr(server, command)(
                request if command in ("plan", "line", "ik") else request.get("boxes", request.get("q"))
            )
        except Exception as error:  # a bad request must not take the server down
            answer = {"ok": False, "why": f"{type(error).__name__}: {error}"}
        reply.write(json.dumps(answer) + "\n")
        reply.flush()
    os._exit(0)  # MoveIt's plugin loader aborts if it is torn down in the usual order


if __name__ == "__main__":
    main()
