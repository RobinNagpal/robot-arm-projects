"""The arm, its gripper, and the two sensors that matter when handling glass.

Planning goes through MoveIt: free moves are planned by OMPL and can bend
around the table, the rack and the other glasses, while approach, retreat and
the descent into a slot use MoveIt's Cartesian path service so the gripper
travels in a straight line rather than arriving from wherever the planner
fancied.

Three capabilities here exist only because the thing being carried is glass.

**Squeezing to a force.** Opening the fingers is a position job, but holding a
glass is not: what matters then is how hard the pads press. The gripper
therefore has two controllers and this class swaps between them.

**Weighing what is held.** The wrist force sensor is the only way to find out
what a glass actually weighs, and a glass's weight is not knowable in advance
because its wall thickness is not visible from outside.

**Turning in place.** Inverting a glass is a rotation about an axis through the
grip, not a move to a new pose. Asking for it as a pose would let the planner
take the glass on a detour to get there.
"""

from __future__ import annotations

import math
import time

import numpy as np
from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Duration as DurationMsg
from control_msgs.action import FollowJointTrajectory
from controller_manager_msgs.srv import SwitchController
from geometry_msgs.msg import Pose, PoseStamped, WrenchStamped
from moveit.planning import MoveItPy
from moveit_msgs.srv import GetCartesianPath
from rclpy.action import ActionClient
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.node import Node
from ros_gz_interfaces.msg import Contacts
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from ..table.layout import WORLD_FRAME
from ..transforms import make_pose, spin

FINGER_JOINTS = ("left_finger_joint", "right_finger_joint")

# The link the wrist force sensor is bolted to, used when the reading does not
# say for itself. See arm/gripper.urdf.xacro.
WRIST_SENSOR_LINK = "gripper_body"

# How many readings the weight is taken over. The sensor reports at 100 Hz, so
# this is about a third of a second: long enough to ride out the spike from the
# fingers closing or the arm stopping, short enough that the arm is still where
# it was when the run began.
WRIST_SAMPLES = 32

# The two controllers that drive the fingers. Only one of them may hold the
# joints at a time, so they are swapped rather than both left running.
POSITION_CONTROLLER = "gripper_controller"
FORCE_CONTROLLER = "gripper_force_controller"

# Which of the tool's own axes the glass turns about. The grasp puts tool z
# along the approach, which is horizontal, and tool y across it, also
# horizontal. Turning about y therefore swings the glass from upright to
# upside down without dragging it sideways.
TURN_AXIS = 1

# How far the arm feels its way down in one step when lowering a glass into a
# slot, and how far down it is willing to go before giving up. Two millimetres
# is small enough that a rim meeting a rack peg is a touch rather than a knock.
# How many times a move is planned before it is called impossible. The planner
# samples at random, so a move it fails once it often solves next time.
PLANNING_TRIES = 3

DESCENT_STEP = 0.002
DESCENT_LIMIT = 0.060

# How much of the weight has to leave the wrist before the thing being lowered
# counts as having landed. Small, because it only has to be bigger than the
# sensor's own wander: as soon as the rack is taking any real share of the
# glass, the rim is down.
TOUCHDOWN_UNLOADING_N = 0.4


def _describe(pose: Pose) -> str:
    p = pose.position
    return f"({p.x:.3f}, {p.y:.3f}, {p.z:.3f})"


# A contact report older than this is treated as stale: the sensor only
# publishes while surfaces are actually touching.
CONTACT_FRESHNESS = 0.4


class MotionFailed(RuntimeError):
    """Raised when the arm could not carry out a requested move."""


class Arm:
    def __init__(
        self,
        node: Node,
        *,
        group: str = "ur_manipulator",
        tip_link: str = "tool0",
    ) -> None:
        self._node = node
        self._group = group
        self._tip_link = tip_link
        # MoveIt's own node picks up the robot description, the SRDF and the
        # planning pipelines from the parameters the launch file supplies.
        self._moveit = MoveItPy(node_name="glass_task_moveit")
        self._planner = self._moveit.get_planning_component(group)
        self._model = self._moveit.get_robot_model()

        self._cartesian = node.create_client(GetCartesianPath, "/compute_cartesian_path")
        self._arm_controller = ActionClient(
            node, FollowJointTrajectory, "/arm_controller/follow_joint_trajectory"
        )
        self._gripper = ActionClient(
            node, FollowJointTrajectory, "/gripper_controller/follow_joint_trajectory"
        )
        sensors = MutuallyExclusiveCallbackGroup()
        self._last_contact = 0.0
        node.create_subscription(
            Contacts, "/fingertip_contacts", self._on_contacts, 10, callback_group=sensors
        )
        self._finger_positions = (0.0, 0.0)
        node.create_subscription(
            JointState, "/joint_states", self._on_joint_states, 10, callback_group=sensors
        )
        self._wrist_recent: list[np.ndarray] = []
        self._wrist_frame = "gripper_body"
        node.create_subscription(
            WrenchStamped, "/wrist_force", self._on_wrist_force, 10, callback_group=sensors
        )

        # The fingers start under the position controller, which is what opens
        # them; the force controller takes over once the pads are on a glass.
        self._gripper_controller = POSITION_CONTROLLER
        self._force_held = 0.0
        self._force_command = node.create_publisher(
            Float64MultiArray, f"/{FORCE_CONTROLLER}/commands", 10
        )
        self._switch = node.create_client(SwitchController, "/controller_manager/switch_controller")

    # --------------------------------------------------------------- startup

    def wait_until_ready(self, timeout: float = 120.0) -> None:
        """Block until the controllers and the Cartesian service are up.

        How long the simulator needs to get there depends on the machine it is
        running on, so this waits for the things themselves rather than for a
        fixed delay that is generous on one machine and short on the next.
        """
        deadline = time.monotonic() + timeout
        for what, wait in (
            ("the arm controller", self._arm_controller.wait_for_server),
            ("the gripper controller", self._gripper.wait_for_server),
            ("/compute_cartesian_path", self._cartesian.wait_for_service),
            ("/controller_manager/switch_controller", self._switch.wait_for_service),
        ):
            if not wait(timeout_sec=max(0.0, deadline - time.monotonic())):
                raise MotionFailed(f"{what} did not come up within {timeout:.0f}s")

        # The force sensor is not a service, so it is waited for by listening.
        while not self._wrist_recent:
            if time.monotonic() > deadline:
                raise MotionFailed(f"the wrist force sensor said nothing within {timeout:.0f}s")
            time.sleep(0.05)

    # ---------------------------------------------------------------- moving

    def move_to_named(self, name: str) -> None:
        """Go to one of the poses named in the SRDF."""
        self._planner.set_start_state_to_current_state()
        self._planner.set_goal_state(configuration_name=name)
        self._run_plan(f"named pose '{name}'")

    def move_to_pose(self, position: np.ndarray, rotation: np.ndarray) -> None:
        """Plan a free move that puts the tip link at the given pose."""
        goal = PoseStamped()
        goal.header.frame_id = WORLD_FRAME
        goal.pose = make_pose(position, rotation)

        self._planner.set_start_state_to_current_state()
        self._planner.set_goal_state(pose_stamped_msg=goal, pose_link=self._tip_link)
        self._run_plan(f"pose {np.round(position, 3).tolist()}")

    def move_to_first_reachable(self, position: np.ndarray, rotations: list[np.ndarray]) -> np.ndarray:
        """Try each orientation in turn and keep the one that plans.

        Returns the orientation that worked, so the caller can carry on using
        it. Raises if none of them do.
        """
        for index, rotation in enumerate(rotations):
            try:
                self.move_to_pose(position, rotation)
                return rotation
            except MotionFailed:
                if index == len(rotations) - 1:
                    raise
        raise MotionFailed("no orientations were offered")

    def move_linear(
        self,
        waypoints: list[Pose],
        *,
        step: float = 0.005,
        min_fraction: float = 0.9,
        avoid_collisions: bool = True,
    ) -> float:
        """Move the tip link along straight lines through ``waypoints``.

        Returns the fraction of the path that was executed. With collision
        checking on, a path that would drive the fingers into the table comes
        back short instead of being run.
        """
        if not self._cartesian.wait_for_service(timeout_sec=10.0):
            raise MotionFailed("/compute_cartesian_path is not available")

        request = GetCartesianPath.Request()
        request.header.frame_id = WORLD_FRAME
        request.group_name = self._group
        request.link_name = self._tip_link
        request.waypoints = waypoints
        request.max_step = step
        request.avoid_collisions = avoid_collisions
        request.max_velocity_scaling_factor = 0.2
        request.max_acceleration_scaling_factor = 0.2

        response = self._cartesian.call(request)
        if response.fraction < min_fraction:
            raise MotionFailed(
                f"straight-line move to {_describe(waypoints[-1])} only solved "
                f"{response.fraction:.0%} of the way (MoveIt error {response.error_code.val})"
            )

        # Straight-line paths go to the controller directly. MoveIt has already
        # timed the trajectory, and its own executor takes a plan object rather
        # than the message this service hands back.
        self._send(self._arm_controller, response.solution.joint_trajectory, "the straight-line move")
        return float(response.fraction)

    def _run_plan(self, what: str, *, tries: int = PLANNING_TRIES) -> None:
        """Plan and run a move, asking more than once before giving up.

        The planner is a randomised one: it grows a tree from wherever its
        samples happen to fall, and on a move it finds hard it will fail one
        attempt and solve the next from a different set of samples. The cost
        of asking again is seconds; the cost of not asking is a glass left
        standing, or worse, one left held while the arm decides it cannot move.

        This is not a way of forcing through a move that is really impossible.
        A pose that cannot be reached at all fails every attempt just as fast.
        """
        for attempt in range(tries):
            result = self._planner.plan()
            if result:
                self._moveit.execute(result.trajectory, controllers=[])
                return
            if attempt + 1 < tries:
                self._node.get_logger().info(
                    f"no plan found for {what} on attempt {attempt + 1}, asking again"
                )
                self._planner.set_start_state_to_current_state()

        raise MotionFailed(f"no plan found for {what} in {tries} attempts")

    def _send(self, client: ActionClient, trajectory: JointTrajectory, what: str) -> None:
        """Run a joint trajectory on a controller and wait for it to finish."""
        if not client.wait_for_server(timeout_sec=10.0):
            raise MotionFailed(f"the controller for {what} is not available")
        result = client.send_goal(FollowJointTrajectory.Goal(trajectory=trajectory))
        if result.status != GoalStatus.STATUS_SUCCEEDED:
            raise MotionFailed(f"the controller did not finish {what}")

    # --------------------------------------------------------------- gripper

    def set_gripper(self, opening: float, *, seconds: float = 1.0) -> None:
        """Command the total gap between the fingers, in metres.

        This is also how the fingers are taken back off force control, which is
        why letting go of a glass is a call to this and not to a force of zero.
        A force of zero leaves the fingers limp and the glass sitting in them.
        """
        self._use_controller(POSITION_CONTROLLER)
        self._force_held = 0.0
        half = max(0.0, opening) / 2.0

        point = JointTrajectoryPoint()
        point.positions = [half, half]
        point.time_from_start = DurationMsg(sec=int(seconds), nanosec=int((seconds % 1) * 1e9))

        trajectory = JointTrajectory(joint_names=list(FINGER_JOINTS), points=[point])

        if not self._gripper.wait_for_server(timeout_sec=10.0):
            raise MotionFailed("the gripper controller is not available")
        # This blocks until the fingers stop. Closing on a box leaves them short
        # of where they were asked to go, so unlike an arm move, the
        # controller's own verdict on the result is not worth acting on.
        self._gripper.send_goal(FollowJointTrajectory.Goal(trajectory=trajectory))

    def _on_joint_states(self, msg: JointState) -> None:
        by_name = dict(zip(msg.name, msg.position, strict=False))
        if all(joint in by_name for joint in FINGER_JOINTS):
            self._finger_positions = tuple(by_name[joint] for joint in FINGER_JOINTS)

    @property
    def gripper_gap(self) -> float:
        """The gap the fingers are actually at, which is not always the one asked for.

        Closing on a box stops the fingers early, so this is how the arm can
        tell it has hold of something from how it can tell it closed on air.
        """
        return float(sum(self._finger_positions))

    # --------------------------------------------------------------- contact

    def _on_contacts(self, msg: Contacts) -> None:
        if msg.contacts:
            self._last_contact = time.monotonic()

    @property
    def in_contact(self) -> bool:
        """True while a fingertip is touching something."""
        return (time.monotonic() - self._last_contact) < CONTACT_FRESHNESS

    def wait_for_contact(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.in_contact:
                return True
            time.sleep(0.02)
        return False

    # ----------------------------------------------------------------- force

    def set_gripper_force(self, newtons: float) -> None:
        """Squeeze with a given force, and keep squeezing.

        The first call swaps the fingers from the position controller to the
        effort one, because the two cannot both hold the joints. After that,
        changing the force is one message.

        The sign is negative because a finger's travel is measured outwards
        from closed, so pushing inwards is pushing against increasing travel.
        """
        self._use_controller(FORCE_CONTROLLER)
        effort = -abs(float(newtons))
        self._force_command.publish(Float64MultiArray(data=[effort, effort]))
        self._force_held = abs(float(newtons))

    @property
    def wrist_load(self) -> float:
        """The weight hanging below the wrist, in newtons.

        Straight down in the room, not along any axis of the gripper. The
        sensor reports in the gripper's own frame, and the gripper is turned
        on its side for most of this task — a glass is gripped by reaching in
        level at it, so the axis it reaches along lies flat and carries none
        of the weight at all. Reading that axis said every glass weighed
        nothing, and a glass that weighs nothing is one the arm will neither
        squeeze properly nor notice it has put down.

        So the reading is turned into the room's frame first and the upright
        part of it taken. What comes back is the gripper plus whatever it is
        holding, which is what the callers subtract from.
        """
        if not self._wrist_recent:
            raise MotionFailed("the wrist force sensor has not reported yet")
        readings = list(self._wrist_recent)

        # The sensor's own frame first, then the link it is bolted to. Both,
        # because the reading is worth nothing without knowing which way it is
        # pointing, and reading the planning scene can fail for a moment while
        # something else is writing to it.
        for frame in (self._wrist_frame, WRIST_SENSOR_LINK):
            for _ in range(2):
                try:
                    with self._moveit.get_planning_scene_monitor().read_only() as scene:
                        matrix = np.asarray(
                            scene.current_state.get_global_link_transform(frame)
                        )
                    turned = matrix[:3, :3]
                    return float(
                        np.median([abs(float((turned @ one)[2])) for one in readings])
                    )
                except Exception:  # noqa: BLE001, S112 - tried again, then given up on
                    continue

        # Deliberately not falling back to the raw reading. That is the axis
        # the gripper reaches along, which is level for every grasp here, so
        # it would quietly report that every glass weighs nothing — and a
        # glass that weighs nothing is gripped too gently and dropped. A
        # refusal to weigh is recoverable; a wrong weight is not.
        raise MotionFailed(
            "the wrist reading cannot be turned the right way up, so what is held "
            "cannot be weighed"
        )

    def _on_wrist_force(self, msg: WrenchStamped) -> None:
        # All three, because which of them carries the weight depends on how
        # the gripper is turned, and it is turned differently for every glass.
        #
        # Kept as a short run of readings rather than only the latest. The
        # fingers squeeze hard and sideways, the arm starts and stops, and
        # either throws a spike many times the weight of a glass through the
        # sensor. A glass is weighed off the middle of a settled run, the way
        # any scale is read.
        self._wrist_recent.append(
            np.array([msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z], dtype=float)
        )
        del self._wrist_recent[:-WRIST_SAMPLES]
        self._wrist_frame = msg.header.frame_id or self._wrist_frame

    def _weight_now(self) -> float | None:
        """What the wrist is carrying, or None if it cannot say.

        Separate from ``wrist_load`` because the descent asks repeatedly and
        must not fall over mid-descent with a glass in hand if one reading
        cannot be turned into the room's frame.
        """
        try:
            return self.wrist_load
        except MotionFailed:
            return None

    def load_transferred(self, gripper_newtons: float, *, margin: float = 0.3) -> bool:
        """Whether something else is now carrying the weight.

        Asked after a glass has been lowered onto a rack peg and before the
        fingers open. If the rack has taken the weight the sensor is back to
        reading the gripper alone; if it has not, the glass is still hanging
        and letting go would drop it.
        """
        return self.wrist_load <= gripper_newtons + margin

    def _use_controller(self, wanted: str) -> None:
        """Make ``wanted`` the controller holding the finger joints."""
        if self._gripper_controller == wanted:
            return
        if not self._switch.wait_for_service(timeout_sec=10.0):
            raise MotionFailed("/controller_manager/switch_controller is not available")

        request = SwitchController.Request()
        request.activate_controllers = [wanted]
        request.deactivate_controllers = [c for c in (POSITION_CONTROLLER, FORCE_CONTROLLER) if c != wanted]
        request.strictness = SwitchController.Request.STRICT
        response = self._switch.call(request)
        if not response.ok:
            raise MotionFailed(f"could not hand the fingers over to {wanted}")
        self._gripper_controller = wanted

    # ------------------------------------------------------------- turning

    def current_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """Where the tool is now: its position, and its 3x3 orientation.

        Read from the robot's own state rather than remembered from the last
        command, because the last command is where the arm was asked to go and
        this is where it is.
        """
        with self._moveit.get_planning_scene_monitor().read_only() as scene:
            matrix = np.asarray(scene.current_state.get_global_link_transform(self._tip_link))
        return matrix[:3, 3].copy(), matrix[:3, :3].copy()

    def rotate_tool(
        self, angle: float, *, axis: int = TURN_AXIS, about: np.ndarray | None = None
    ) -> np.ndarray:
        """Turn the tool about one of its own axes, in place.

        ``about`` is the point the rotation happens around, in world
        coordinates, and defaults to the tool origin. For a held glass the
        point that matters is where the pads are gripping it, because that is
        the one place the glass is not moving relative to the fingers.

        Returns the orientation the tool ends up in.
        """
        position, rotation = self.current_pose()
        about = position if about is None else np.asarray(about, dtype=float)

        turn = _rotation_about(rotation[:, axis], angle)
        moved = turn @ rotation
        landing = about + turn @ (position - about)

        # A parallel gripper is symmetric about the line it reaches along, and
        # so is a glass, so the orientation half a turn round that line holds
        # the same glass in the same place by the same part of it. To the arm
        # they are not the same at all: one may need a wrist angle it does not
        # have, or fold the elbow into the table. Both are offered, because
        # the second costs nothing and is often the one that works.
        #
        # The grip point is on that line, so spinning about it leaves the
        # glass exactly where it is.
        trouble: MotionFailed | None = None
        for attempt, candidate in enumerate((moved, spin(moved, math.pi))):
            try:
                # Straight first, so the glass sweeps as little as possible. A
                # Cartesian path is all or nothing — half a turn solved is no
                # turn — and interpolating a large rotation is where it gives
                # up most often, so a planned path to the same pose is better
                # than none. The glass is attached by now, so the planner
                # carries it too.
                try:
                    self.move_linear([make_pose(landing, candidate)], avoid_collisions=True)
                except MotionFailed as why:
                    self._node.get_logger().info(f"no straight turn ({why}), planning it instead")
                    self.move_to_pose(landing, candidate)
                return candidate
            except MotionFailed as why:
                trouble = why
                if attempt == 0:
                    self._node.get_logger().info(
                        "that way round will not plan; trying the other way round, which "
                        "holds the glass the same"
                    )

        raise trouble if trouble else MotionFailed("the turn was not attempted")

    def tilt(self, angle: float, *, about: np.ndarray | None = None) -> np.ndarray:
        """Lean the held glass over by a small angle, to see whether it slips."""
        return self.rotate_tool(angle, about=about)

    def turn_over(self, *, about: np.ndarray | None = None) -> np.ndarray:
        """Turn the held glass all the way upside down."""
        return self.rotate_tool(np.pi, about=about)

    def can_rotate_tool(self, angle: float, *, axis: int = TURN_AXIS) -> bool:
        """Whether that turn could be made from where the arm is standing now.

        Asked before the fingers close, never after. The last wrist joint stops
        short of a full turn, so some ways of holding a glass leave the arm
        unable to invert it — and finding that out with the glass already in
        the gripper is the most expensive mistake this task offers, because
        there is then nothing to do but put it back.
        """
        position, rotation = self.current_pose()
        turn = _rotation_about(rotation[:, axis], angle)

        goal = PoseStamped()
        goal.header.frame_id = WORLD_FRAME
        goal.pose = make_pose(position, turn @ rotation)

        self._planner.set_start_state_to_current_state()
        self._planner.set_goal_state(pose_stamped_msg=goal, pose_link=self._tip_link)
        return bool(self._planner.plan())

    # ------------------------------------------------------------- descending

    def descend_until_contact(self, limit: float = DESCENT_LIMIT) -> float:
        """Lower the tool straight down until something touches.

        Feeling for the touchdown rather than driving to a calculated height is
        what makes an unknown glass safe to put down: the height its rim lands
        at depends on how tall it is and how far up it is being held, and both
        were measured, so both carry error. A rim that finds the rack two
        millimetres early is a contact; a rim driven two millimetres past where
        it should have stopped is a chipped rim.

        What counts as touching depends on what is coming down. The fingertip
        sensors feel a pad meeting something, which is the right signal when
        the pads are what arrives first. Setting a glass down, they are not:
        the rim lands and the pads touch nothing, so the fingertips report an
        empty descent all the way to the limit while the rim is already on the
        rack. What gives it away is the weight going out of the wrist as the
        rack takes it, so that is watched as well.

        Returns how far it went down.
        """
        position, rotation = self.current_pose()
        carried = self._weight_now()
        gone = 0.0
        while gone < limit:
            if self.in_contact:
                return gone
            now = self._weight_now()
            if carried is not None and now is not None and carried - now > TOUCHDOWN_UNLOADING_N:
                return gone
            gone += DESCENT_STEP
            self.move_linear(
                [make_pose(position - np.array([0.0, 0.0, gone]), rotation)],
                avoid_collisions=False,
            )
        raise MotionFailed(
            f"came down {limit * 1000:.0f} mm without touching anything, so the "
            "glass is not where it was thought to be"
        )


def _rotation_about(axis: np.ndarray, angle: float) -> np.ndarray:
    """A 3x3 rotation of ``angle`` about a world-frame axis, by Rodrigues."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    cross = np.array(
        [[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]]
    )
    return np.eye(3) + math.sin(angle) * cross + (1.0 - math.cos(angle)) * (cross @ cross)
