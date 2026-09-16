"""The workflow.

1. Look round the room and work out what is in it: the floor, the table top
   standing upright in its holders, and the four legs.
2. Measure the top properly, close up: length, width and thickness, and where
   its upper edge is.
3. Plan the whole move before touching it, every pose checked.
4. Grip the top by the middle of its upper edge, from straight above, and
   lift it straight up out of the holders. It now hangs straight down.

Then one of three things, by ``turn``:

- ``wrist`` and ``whole_arm``: turn it flat in the air. Carry it round,
  hanging, to the turning spot, and turn it a quarter turn, away from the arm.
  Either wrist 1 turns on its own and every other joint stays still, or the
  whole arm moves so that the gripped edge stays where it is and the board
  turns round it. Hold it flat for a few seconds, then report what each joint
  did and whether the fingers still hold the top.
- ``tilt``: put it on the legs without ever holding it flat in the air.
  Measure the legs close up. Lean the top over a little in the air, carry it
  out over the far legs, and let it down until its lower edge rests on them.
  Tilt it down towards the arm about that edge until it is just above the
  near legs, let go, and pull the fingers back out. Then look at the table
  and check it.

This is the only module that knows what order things happen in. Everything it
calls offers a capability and has no opinion about when it is used.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from .arm.camera import WristCamera
from .arm.dimensions import (
    BASE_POSITION,
    CAMERA_OFFSET,
    GRIPPER_MAX_OPENING,
    MAX_GRASP_WIDTH,
    SELF_RADIUS,
    SURVEY_AZIMUTHS_DEG,
    SURVEY_CAMERA_HEIGHT,
    SURVEY_CAMERA_RADIUS,
    SURVEY_LOOK_RADIUS,
)
from .arm.motion import ARM_JOINTS, WRIST_1, Arm, JointSample, MotionFailed
from .assembly.grasps import (
    EDGE_BELOW_TOOL,
    backed_off,
    board_point,
    carry_round,
    down_tool_pose,
    edge_pick_poses,
    flat_turn,
    hanging_tool_poses,
    hold,
    resting_edge,
    shifted,
    straight_line,
    swing_about_edge,
    tilt_axis,
    tilt_steps,
    turned_about,
    upright_edge,
    upright_size,
    upright_tilt,
    wrist_spin,
)
from .assembly.table import TableLegs, landing_angle, misfit, read_legs
from .geometry import Box, describe
from .perception.fitting import cluster, fit_resting_box, surface_tilt
from .perception.pixels import back_project, colour_masks
from .perception.room import Room, is_standing, read_room
from .scene import PlanningSceneClient
from .transforms import WORLD_X, WORLD_Z, frame, look_along, view_options

# The ways of turning the top flat: two in the air, and one onto the legs.
WRIST = "wrist"
WHOLE_ARM = "whole_arm"
TILT = "tilt"
TURNS = (WRIST, WHOLE_ARM, TILT)

# How much narrower than a part the fingers are told to close, so that they
# stop on the part rather than at their target.
#
# It is bounded on both sides. Below about 3 mm it is smaller than the error in
# the measured width, so on a part measured a couple of millimetres too wide
# the fingers close on nothing. Above about 5 mm the fingers are being asked to
# be somewhere the part already is, and since they are position controlled,
# the simulator resolves that by firing the part out sideways.
GRIP_SQUEEZE = 0.004

# How far above the top's edge the gripper lines up before coming down over
# it. Further than the fingers reach down, so they start clear of the board.
TOP_APPROACH = 0.08

# How far the top is lifted: until its lower edge is this far above where its
# upper edge was. The holders are never seen — grey within a few centimetres
# of a part is taken for the part's own shadowed side — so the lift cannot be
# sized to them. But whatever holds a board upright holds it lower than its
# upper edge, which the fingers reached freely.
LIFT_CLEAR = 0.04

# Joint speed, as a fraction of the arm's limits, for moves with a part in
# the gripper. The part is held by friction alone, and a fast swing with it is
# how it ends up across the room.
CARRY_SPEED = 0.1

# The top is gripped as if it stood upright. One leaning further than this is
# not where the arm thinks its edge is, and is left alone.
TOP_MAX_TILT = math.radians(5.0)

# Where the top is turned: the middle of its gripped edge goes here, straight
# in front of the arm and 40 cm up. That is the arm's own choice of where to
# work, not a fact about the room, and it is still checked to be clear. 40 cm
# up, the widest top hanging from its edge clears the floor by 20 cm. 50 cm
# out, the whole arm can still turn it about its edge without folding up
# tight: that turn brings the tool 12 cm back towards the base.
TURN_SPOT = np.array([0.50, 0.0])
TURN_HEIGHT = 0.40

# Nothing may have been seen within this distance of the turning spot, seen
# from above. Turned by the wrist alone, the board's far edge swings round a
# circle about 40 cm across.
TURN_CLEARANCE = 0.40

# The whole-arm turn is a list of poses this far apart, followed in straight
# lines between them.
SWING_STEP = math.radians(5.0)

# If the whole-arm turn's straight-line path stops short, it is finished with
# one free move, but only this close to the end. Stopping further out means
# something is in the way.
SWING_MIN_FRACTION = 0.9

# How long the top is held flat before the grip is checked. A board slipping
# in the fingers does not always go at once.
HOLD_FLAT = 5.0  # seconds

# ---------------------------------------------------------------- the tilt

# How far the top leans towards the arm when its lower edge comes down on the
# far legs, least first. Upright, it would hang its whole width plus 12 cm
# above them, and the far legs stand further out than the arm can reach that
# high. The less it leans, the less it twists in the fingers on the way: at
# 30 degrees the twist is half what it is flat, and a 3 kg top sagged in the
# fingers before it reached the legs, then twisted out during the tilt and
# knocked all four legs over. At 20 degrees the twist is a third of flat, but
# the arm has to reach higher and further out, which it cannot always do.
LEANS = (math.radians(20.0), math.radians(30.0))

# The top is leaned over in the air with its gripped edge 45 cm out from the
# base, on the way to the legs: close enough in for the arm to hold it
# hanging there, and short of the near legs, which it passes over leaning.
LEAN_RADIUS = 0.45

# How far a carried part's lowest point passes above the leg tops.
CARRY_CLEARANCE = 0.04

# How far above the far legs the top's lower edge stops before it is let down
# onto them.
ABOVE_LEGS = 0.05

# A straight-line move with the top in hand is checked every this far along.
LINE_STEP = 0.02

# Letting the top down onto the far legs. It goes to this far above where
# they were measured, then down in steps this small, until the arm feels them
# take some of its weight, but no further than this below where they were
# measured.
TOUCH_START = 0.005
TOUCH_STEP = 0.0005
TOUCH_LIMIT = 0.006

# The change in the shoulder's, elbow's or wrist 1's effort, from what it was
# with the top hanging just clear of the legs, that counts as the legs taking
# some of its weight. The whole of a 0.3 kg top resting on the legs takes
# about 1.5 N·m off the shoulder.
TOUCH_EFFORT = 0.5  # N·m

# After a step down, the joints' efforts are left to settle this long, then
# averaged over this long.
SETTLE = 0.3  # seconds
AVERAGE = 0.3  # seconds

# How much wider than the top the fingers open once the far legs hold up one
# edge of it, before the tilt. Closed on it, they squeeze it, and a board held
# that tight is shoved into the legs by any error in the arm's path. Just
# open, they only cradle it: the gripped edge lies on the lower finger and
# turns between the two like a hinge. Two millimetres each side is enough to
# see the fingers open, and small enough that the edge, 5 cm in between
# them, can only rock a few degrees.
GRIP_LOOSEN = 0.004

# The tilt down about the far legs is a list of poses this far apart.
TILT_STEP = math.radians(3.0)

# How far above the near legs the top is let go of, to fall the rest of the
# way onto them. Driven all the way down, a near leg standing a hair taller
# than measured would have the top pushed into it.
LAND_DROP = 0.003

# How far the gripper pulls back out from the top once it has let go, along
# the way it reaches in: further than the fingers reach in. Then how far it
# lifts clear.
TOP_RETREAT = 0.06
LIFT = 0.08

# What counts as a good table: within a centimetre of the height it should be,
# and within three degrees of level.
HEIGHT_TOLERANCE = 0.010
TILT_TOLERANCE = math.radians(3.0)


@dataclass(frozen=True)
class Route:
    """Every pose of the move, worked out before the top is touched."""

    approach: np.ndarray
    pick: np.ndarray
    lifted: np.ndarray
    carry: list[np.ndarray]  # ends at the hanging pose at the turning spot
    wrist: float


@dataclass(frozen=True)
class TiltRoute:
    """Every pose of the tilt onto the legs, worked out before the top is touched."""

    route: Route  # the pick-up and the carry, ending hanging where the top is leaned over
    leaning: float  # how far it leans when it comes down on the far legs
    lean: list[np.ndarray]  # leaning it over in the air, about its gripped edge
    out: list[np.ndarray]  # carrying it out, leaning, to just above the far legs
    touch: np.ndarray  # leaning, its lower edge on the far legs, as measured
    resting_edge: np.ndarray  # the edge it rests and turns on, in the top's own frame
    axis: np.ndarray  # what it is tilted about, towards the arm
    landing: float  # how far from upright it is tilted before it is let go of


@dataclass(frozen=True)
class TableCheck:
    """What the camera saw of the finished table."""

    size: np.ndarray  # length along the near edge, depth, height
    expected_height: float
    tilt: float
    offset: float  # how far its centre is from where it was meant to be

    @property
    def good(self) -> bool:
        return (
            abs(float(self.size[2]) - self.expected_height) < HEIGHT_TOLERANCE and self.tilt < TILT_TOLERANCE
        )


@dataclass(frozen=True)
class JointReport:
    """What one joint did during the turn, and while the top was held flat."""

    name: str
    travel: float  # radians, from its lowest angle to its highest
    turned: float  # radians, from start to end
    peak_effort: float  # N·m, during the turn
    holding_effort: float  # N·m, while held flat


@dataclass
class Result:
    turn: str
    top: Box
    seconds: float  # how long the turn took
    joints: list[JointReport]
    slipped_at: float | None = (
        None  # how far from hanging the top was when the fingertips lost it, if they did
    )
    tilt: float | None = None  # how far from level the arm puts the top, from its own joint angles
    held: bool = False  # whether the fingers still felt the top after holding it flat
    table: TableCheck | None = None  # the finished table, for the tilt onto the legs


class TaskFailed(RuntimeError):
    """Raised when the top cannot be turned flat at all."""


class TurnTopTask:
    def __init__(self, node, arm: Arm, camera: WristCamera, scene: PlanningSceneClient, turn: str) -> None:
        if turn not in TURNS:
            raise TaskFailed(f"no way of turning called {turn!r}; the ways are {', '.join(TURNS)}")
        self._log = node.get_logger()
        self._arm = arm
        self._camera = camera
        self._scene = scene
        self._turn = turn
        self._floor_z: float | None = None
        # What the arm currently believes is in the room, by name, which is
        # also exactly what MoveIt is told about.
        self._known: dict[str, Box] = {}

    # ------------------------------------------------------------------ run

    def run(self) -> Result:
        # The launch file gives the cell a head start, but how long it really
        # needs depends on the machine, so wait for the pieces themselves
        # rather than trust that the head start was long enough.
        self._log.info("waiting for the cell to come up")
        self._scene.wait_until_ready()
        self._arm.wait_until_ready()
        self._camera.wait_until_ready()
        self._arm.set_gripper(GRIPPER_MAX_OPENING)
        if self._turn == TILT:
            self._log.info("the top will be rested on the far legs and tilted down onto all four")
        else:
            self._log.info(f"the top will be turned flat in the air by the {self._turn.replace('_', ' ')}")

        self._log.info("looking round the room")
        room = self._survey()
        self._report_room(room)
        if room.top is None:
            raise TaskFailed("no table top in sight")

        top = self._measure_top(room.top)
        if top.size[2] > MAX_GRASP_WIDTH:
            raise TaskFailed("the top is too thick for the gripper to close round")
        if self._turn == TILT:
            return self._put_on_legs(top, room)

        self._check_turning_spot_clear(room)
        route = self._plan_route(top)
        self._pick_up(top, route)

        held = hold(top, route.pick)
        start = self._arm.tool_pose()
        self._arm.start_recording()
        if self._turn == WRIST:
            self._turn_by_wrist()
        else:
            self._turn_by_whole_arm()
        turn = self._arm.stop_recording()
        result = Result(turn=self._turn, top=top, seconds=_moving_time(turn), joints=_joint_reports(turn, []))
        if not self._arm.in_contact:
            # A slip is an answer, not a breakdown: how heavy a top the turn
            # can take is one of the things being found out. The fingertip
            # sensors only say the top has gone from the tip pads; it may have
            # twisted down in the fingers, still pinched by the inner pads, or
            # fallen.
            result.slipped_at = self._turned_when_let_go(start, turn)
            return result

        board = self._arm.tool_pose() @ np.linalg.inv(held)
        tilt = math.acos(min(1.0, abs(float(board[2, 2]))))
        self._log.info(
            f"the top is flat, as far as the arm can tell: {math.degrees(tilt):.1f} degrees off level"
        )

        self._log.info(f"holding it flat for {HOLD_FLAT:.0f} seconds")
        self._arm.start_recording()
        time.sleep(HOLD_FLAT)
        holding = self._arm.stop_recording()
        result.joints = _joint_reports(turn, holding)
        result.tilt = tilt
        result.held = self._arm.in_contact
        return result

    def _turned_when_let_go(self, start: np.ndarray, samples: list[JointSample]) -> float:
        """How far the tool had turned from ``start`` at the last reading the fingers still touched."""
        touching = [sample for sample in samples if sample.touching]
        if not touching:
            return 0.0
        last = self._arm.forward(touching[-1].positions)
        return math.acos(min(1.0, float(start[:3, 2] @ last[:3, 2])))

    # -------------------------------------------------------------- looking

    def _survey(self) -> Room:
        """Look all the way round the arm and read the room from everything seen."""
        views = []
        for azimuth_deg in SURVEY_AZIMUTHS_DEG:
            heading = np.array(
                [math.cos(math.radians(azimuth_deg)), math.sin(math.radians(azimuth_deg)), 0.0]
            )
            camera = BASE_POSITION + heading * SURVEY_CAMERA_RADIUS + WORLD_Z * SURVEY_CAMERA_HEIGHT
            target = BASE_POSITION + heading * SURVEY_LOOK_RADIUS
            views.append((camera, target))
        room = self._look(views, stride=2)
        if self._floor_z is None:
            self._floor_z = room.floor_z
            self._scene.set_floor(room.floor_z)
        self._known = {f"obstacle_{i}": box for i, box in enumerate(room.obstacles)}
        if room.top is not None:
            self._known["top"] = room.top
        for i, leg in enumerate(room.legs):
            self._known[f"leg_{i}"] = leg
        self._publish()
        return room

    def _look(self, views, *, stride: int = 1) -> Room:
        """Take a picture from every view and read the room from all of them together.

        A view the arm cannot reach is skipped rather than treated as a
        failure: the extra views are there to fill in what one view misses,
        so losing one costs coverage, not the measurement.
        """
        parts, others = [], []
        for camera, target in views:
            if not self._point_camera(camera, target - camera):
                self._log.warning(
                    f"could not get the camera to {np.round(camera, 2).tolist()}; skipping that view"
                )
                continue
            view = self._camera.capture()
            part_mask, other_mask = colour_masks(view.rgb, view.depth)
            parts.append(back_project(view.depth, part_mask, view.intrinsics, view.camera_to_world))
            others.append(
                back_project(view.depth, other_mask, view.intrinsics, view.camera_to_world, stride=stride)
            )
        if not parts:
            raise MotionFailed("could not reach any of the views")
        return read_room(
            np.concatenate(parts),
            np.concatenate(others),
            self_centre=BASE_POSITION,
            self_radius=SELF_RADIUS,
            floor_z=self._floor_z,
        )

    def _point_camera(self, position: np.ndarray, direction: np.ndarray) -> bool:
        """Put the camera at ``position`` looking along ``direction``.

        tool0 does not go to ``position``: the camera is bolted to one side of
        it, and the offset turns with the tool.

        The arm is steered into its ready posture turned towards the view, so
        that its own forearm stays above and behind the camera. Left to pick
        any way of reaching the view, the planner sometimes brings the elbow
        round underneath, and the picture is then half full of arm.
        """
        near = self._arm.looking_towards(math.atan2(position[1], position[0]))
        for rotation in view_options(look_along(direction)):
            try:
                self._arm.move_to(frame(position - rotation @ CAMERA_OFFSET, rotation), near=near)
                return True
            except MotionFailed:
                continue
        return False

    def _measure_top(self, seen: Box) -> Box:
        """Measure the top close up, from above and from the arm's side.

        The survey saw it from far off. Up close, the face towards the arm
        gives length and width to a millimetre or so, and the upper edge, seen
        from above at a slant, gives its thickness.
        """
        toward = BASE_POSITION - seen.centre
        toward[2] = 0.0
        toward /= np.linalg.norm(toward)
        along = np.cross(WORLD_Z, toward)
        directions = (
            WORLD_Z + 0.8 * toward,
            WORLD_Z + 0.8 * toward + 0.5 * along,
            WORLD_Z + 0.8 * toward - 0.5 * along,
            WORLD_Z + 0.2 * toward,
        )
        views = [(seen.centre + 0.40 * d / np.linalg.norm(d), seen.centre) for d in directions]
        room = self._look(views)
        if room.top is None or np.linalg.norm(room.top.centre - seen.centre) > 0.08:
            self._log.warning("lost the top close up; keeping the survey's measurement")
            top = seen
        else:
            top = room.top
        tilt = upright_tilt(top)
        length, width, thickness = (float(v) * 100 for v in top.size)
        self._log.info(f"table top: {length:.1f} x {width:.1f} cm, {thickness:.1f} cm thick")
        self._log.info(f"  standing {math.degrees(tilt):.1f} degrees off upright")
        if tilt > TOP_MAX_TILT:
            raise TaskFailed("the top is not standing upright, and it can only be picked up upright")
        self._known["top"] = top
        self._publish()
        return top

    # -------------------------------------------------------------- planning

    def _turning_edge(self) -> np.ndarray:
        """Where the middle of the gripped edge goes for the turn."""
        return np.array([TURN_SPOT[0], TURN_SPOT[1], self._floor_z + TURN_HEIGHT])

    def _check_turning_spot_clear(self, room: Room) -> None:
        spot = self._turning_edge()
        for box in room.obstacles + room.legs + room.unknown:
            if np.linalg.norm(box.centre[:2] - spot[:2]) < TURN_CLEARANCE:
                where = np.round(box.centre[:2], 3).tolist()
                raise TaskFailed(f"the space where the top is turned is not clear: something is at {where}")

    def _plan_route(self, top: Box) -> Route:
        """Every pose from above the top to hanging at the turning spot, and a check of the turn.

        Found out with the top already in the air, a grip that cannot turn it
        flat leaves nothing to do but put it back. So every pose is checked
        first, with the wrist the way it will be, since the arm cannot flip
        its wrist with a part in hand.

        The gripped edge is lined up at the turning spot to run along wrist
        1's axis. That axis depends only on where the tool is, not on how it
        is turned about the vertical, so it is found once from a trial pose.
        Lined up like that, turning wrist 1 alone leaves the board flat, and
        the whole-arm turn about the edge needs no joint but the three that
        bend the arm in its own plane.
        """
        spot = self._turning_edge()
        trial = self._arm.solve(down_tool_pose(spot + WORLD_Z * EDGE_BELOW_TOOL, WORLD_X))
        if trial is None:
            raise TaskFailed(f"the arm cannot reach the turning spot at {np.round(spot, 2).tolist()}")
        axis = self._arm.joint_axis(trial, WRIST_1)

        edge, _, _ = upright_edge(top)
        height = 2.0 * float(edge[2] - top.centre[2])
        why = "no grip could be found"
        for pick in edge_pick_poses(top):
            approach = shifted(pick, WORLD_Z * TOP_APPROACH)
            wrist = self._arm.wrist_side(approach)
            if wrist is None:
                why = "the arm cannot reach above the top's edge"
                continue
            lifted = shifted(pick, WORLD_Z * (height + LIFT_CLEAR))
            if not self._arm.can_reach(lifted, wrist=wrist):
                why = "the arm cannot lift the top clear of its holders"
                continue
            held = hold(top, pick)
            hangings = hanging_tool_poses(spot, axis)
            for hanging in sorted(hangings, key=lambda pose: wrist_spin(lifted, pose, BASE_POSITION)):
                why = self._turn_blocked(hanging, wrist)
                if why is not None:
                    continue
                # The top travels at whichever is higher, its height lifted
                # out or at the turning spot, so it is never lowered back
                # towards the holders on the way.
                centre_height = max(
                    (lifted @ np.linalg.inv(held))[2, 3], (hanging @ np.linalg.inv(held))[2, 3]
                )
                carry = carry_round(held, lifted, hanging, centre_height, BASE_POSITION) + [hanging]
                return Route(approach=approach, pick=pick, lifted=lifted, carry=carry, wrist=wrist)
        raise TaskFailed(f"the top cannot be turned flat however it is gripped: {why}")

    def _turn_blocked(self, hanging: np.ndarray, wrist: float) -> str | None:
        """Why the top cannot be turned flat from ``hanging``, or ``None`` if it can."""
        joints = self._arm.solve(hanging, wrist=wrist)
        if joints is None:
            return "the arm cannot hold it hanging at the turning spot"
        if self._turn == WRIST:
            angle = flat_turn(hanging, self._arm.joint_axis(joints, WRIST_1), BASE_POSITION)
            return self._arm.joint_turn_blocked(joints, WRIST_1, angle)
        steps = swing_about_edge(
            hanging, hanging[:3, 0], flat_turn(hanging, hanging[:3, 0], BASE_POSITION), SWING_STEP
        )
        for number, pose in enumerate(steps):
            if not self._arm.can_reach(pose, wrist=wrist):
                turned = math.degrees(SWING_STEP) * number
                return f"the arm cannot follow the turn about the edge past {turned:.0f} degrees"
        return None

    # ------------------------------------------------------------ picking up

    def _pick_up(self, top: Box, route: Route) -> None:
        """Grip the top, lift it out of the holders, and carry it hanging to the turning spot."""
        thickness = float(top.size[2])
        self._arm.open_gripper(min(thickness + 0.030, GRIPPER_MAX_OPENING))
        self._arm.move_to(route.approach, wrist=route.wrist)
        self._forget("top")
        self._down_onto(route.pick)
        self._grip(thickness)

        self._scene.attach("carried", top, route.pick)
        # Checked if it can be, but the top starts off standing in its holders,
        # and anything of them MoveIt has been told about touches it.
        try:
            self._arm.move_linear(route.lifted, speed=CARRY_SPEED)
        except MotionFailed as failure:
            self._log.info(f"{failure}; lifting it out unchecked")
            self._arm.move_linear(route.lifted, avoid_collisions=False, speed=CARRY_SPEED)
        if not self._arm.in_contact:
            raise TaskFailed("the top slipped out of the fingers as it was lifted")
        self._log.info("lifted out of the holders; carrying it round, hanging")

        try:
            self._arm.move_linear(route.carry, speed=CARRY_SPEED)
        except MotionFailed as failure:
            self._log.info(f"{failure}; letting the planner carry it instead")
            self._arm.move_to(route.carry[-1], speed=CARRY_SPEED, any_shape=False)
        if not self._arm.in_contact:
            raise TaskFailed("the top slipped out of the fingers as it was carried round")

    # --------------------------------------------------------------- turning

    def _turn_by_wrist(self) -> None:
        """Turn wrist 1 by a quarter turn, and nothing else.

        The direction is worked out again from where the arm really is, so a
        few millimetres off the planned pose makes no difference to it.
        """
        axis = self._arm.joint_axis(self._arm.joints(), WRIST_1)
        angle = flat_turn(self._arm.tool_pose(), axis, BASE_POSITION)
        self._log.info(f"turning wrist 1 by {math.degrees(angle):+.0f} degrees, every other joint still")
        self._arm.turn_joint(WRIST_1, angle, speed=CARRY_SPEED)

    def _turn_by_whole_arm(self) -> None:
        """Turn the top a quarter turn about its own gripped edge, whichever joints that takes.

        The poses are worked out from where the tool really is, and followed
        in straight lines. MoveIt picks the joint angles for each one, starting
        from the last, so every joint is free to move.
        """
        start = self._arm.tool_pose()
        axis = start[:3, 0]
        angle = flat_turn(start, axis, BASE_POSITION)
        steps = swing_about_edge(start, axis, angle, SWING_STEP)
        self._log.info(f"turning the top {math.degrees(angle):+.0f} degrees about its gripped edge")
        done = self._arm.move_linear(steps, speed=CARRY_SPEED, min_fraction=SWING_MIN_FRACTION)
        if done < 0.999:
            self._log.info(f"the straight-line turn stopped at {done:.0%}; finishing it with one free move")
            self._arm.move_to(steps[-1], speed=CARRY_SPEED, any_shape=False)

    # ------------------------------------------------------- onto the legs

    def _put_on_legs(self, top: Box, room: Room) -> Result:
        """Rest the top's lower edge on the far legs, then tilt it down onto all four.

        It is never held flat in the air. It leans over a little, comes down
        on the far legs, and from then on they hold up one edge of it while
        the arm lowers the other.
        """
        legs = self._measure_legs(room)
        length, width = upright_size(top)
        why = misfit(legs, length, width)
        if why is not None:
            raise TaskFailed(f"the top will not go on these legs: {why}")
        plan = self._plan_tilt(top, legs)
        self._pick_up(top, plan.route)
        held = hold(top, plan.route.pick)

        self._log.info(
            f"leaning the top {math.degrees(plan.leaning):.0f} degrees towards the arm, in the air"
        )
        self._arm.move_linear(plan.lean, speed=CARRY_SPEED)
        self._log.info("carrying it out over the far legs")
        self._arm.move_linear(plan.out, speed=CARRY_SPEED)
        if not self._arm.in_contact:
            raise TaskFailed("the top slipped out of the fingers as it was leaned over")
        self._let_down(plan.touch)
        self._loosen_grip()

        start = self._arm.tool_pose()
        edge = board_point(start, held, plan.resting_edge)
        steps = tilt_steps(start, edge, plan.axis, plan.landing - plan.leaning, TILT_STEP)
        turn = math.degrees(plan.landing - plan.leaning)
        self._log.info(f"tilting it down about the far legs, {turn:.0f} degrees")
        self._arm.start_recording()
        # Unchecked: the top is resting on the legs, which MoveIt counts as a
        # collision. Every pose of it was checked for the arm itself before
        # the top was picked up.
        self._arm.move_linear(steps, avoid_collisions=False, speed=CARRY_SPEED)
        samples = self._arm.stop_recording()
        result = Result(
            turn=self._turn, top=top, seconds=_moving_time(samples), joints=_joint_reports(samples, [])
        )
        # The fingertips losing touch is no sign of a slip now: with the grip
        # loose the top can lie on the lower finger's inner pad alone. Whether
        # it came down on the legs is for the camera to say.
        if not self._arm.in_contact:
            self._log.info("the fingertips no longer feel the top; the table check will say where it is")

        placed = self._arm.tool_pose()
        self._log.info("letting go just above the near legs")
        self._arm.set_gripper(GRIPPER_MAX_OPENING)
        self._scene.detach("carried")
        board = placed @ np.linalg.inv(held)
        self._known["top"] = Box(board[:3, 3], board[:3, :3], top.size)
        self._publish()
        self._pull_out(placed)
        result.table = self._check_table(top, legs)
        return result

    def _measure_legs(self, room: Room) -> TableLegs:
        """Measure the four legs close up, from above and from the arm's side.

        Done before the top is picked up: hanging over them, it would hide
        them from the camera.
        """
        if len(room.legs) < 4:
            raise TaskFailed(f"found {len(room.legs)} legs, and a table needs 4")
        middle = np.mean([leg.centre for leg in room.legs], axis=0)
        middle[2] = self._floor_z
        toward = BASE_POSITION - middle
        toward[2] = 0.0
        toward /= np.linalg.norm(toward)
        seen = self._look(
            [
                (middle + WORLD_Z * 0.50, middle),
                (middle + toward * 0.15 + WORLD_Z * 0.45, middle),
                (middle + np.cross(WORLD_Z, toward) * 0.12 + WORLD_Z * 0.45, middle),
            ]
        )
        standing = [leg for leg in seen.legs if is_standing(leg)]
        if len(standing) != 4:
            raise TaskFailed(
                f"close up, {len(standing)} standing legs were found where the table goes, not 4"
            )
        self._known = {name: box for name, box in self._known.items() if not name.startswith("leg_")}
        for i, leg in enumerate(standing):
            self._known[f"leg_{i}"] = leg
        self._publish()

        legs = read_legs(standing, BASE_POSITION)
        for leg in legs.all:
            self._log.info(f"  leg, {describe(leg.size)}, at {np.round(leg.centre[:2], 3).tolist()}")
        self._log.info(
            f"legs: the far two {np.linalg.norm(legs.hinge[:2] - BASE_POSITION[:2]) * 100:.0f} cm out, "
            f"their tops {(legs.hinge[2] - self._floor_z) * 100:.1f} cm up, "
            f"the near two {legs.rows * 100:.1f} cm in from them"
        )
        return legs

    def _plan_tilt(self, top: Box, legs: TableLegs) -> TiltRoute:
        """Every pose from above the top to lying on the legs, checked before the top is touched.

        The top ends up lying from the far legs' middles towards the arm,
        centred along them. Working back from there: tilted up until it
        leans 20 degrees, or 30 if the arm cannot reach that, it rests on its
        lower edge on the far legs; lifted a few centimetres, it is above
        them; and it gets there leaning over the same way from where it was
        leaned over in the air, straight in from the legs towards the base.
        """
        axis = tilt_axis(legs.toward)
        out = legs.hinge - BASE_POSITION
        out[2] = 0.0
        out /= np.linalg.norm(out)
        _, height = upright_size(top)
        lean_at = BASE_POSITION + out * LEAN_RADIUS
        lean_at[2] = max(self._floor_z + TURN_HEIGHT, legs.hinge[2] + CARRY_CLEARANCE + height)
        landing = landing_angle(legs, LAND_DROP)

        why = "no grip could be found"
        for leaning in LEANS:
            # Every way of gripping it, with the wrist flipped either way. The
            # wrist cannot be flipped with the top in hand, so the way it is when
            # the top is picked up is the way it is for the whole route, and on
            # some legs only one of the two gets the top all the way down.
            for pick in edge_pick_poses(top):
                approach = shifted(pick, WORLD_Z * TOP_APPROACH)
                usual = self._arm.wrist_side(approach)
                if usual is None:
                    why = "the arm cannot reach above the top's edge"
                    continue
                for wrist in (usual, -usual):
                    if not self._arm.can_reach(approach, wrist=wrist):
                        why = "the arm cannot reach above the top's edge"
                        continue
                    lifted = shifted(pick, WORLD_Z * (height + LIFT_CLEAR))
                    if not self._arm.can_reach(lifted, wrist=wrist):
                        why = "the arm cannot lift the top clear of its holders"
                        continue
                    held = hold(top, pick)
                    hangings = hanging_tool_poses(lean_at, legs.along)
                    for hanging in sorted(hangings, key=lambda pose: wrist_spin(lifted, pose, BASE_POSITION)):
                        edge = resting_edge(hanging, held, top.size, legs.toward)
                        standing = shifted(hanging, legs.hinge - board_point(hanging, held, edge))
                        touch = turned_about(standing, legs.hinge, axis, leaning)
                        above = shifted(touch, WORLD_Z * ABOVE_LEGS)
                        lean = swing_about_edge(hanging, axis, leaning, SWING_STEP)
                        out = straight_line(lean[-1], above, LINE_STEP)
                        tilt = tilt_steps(touch, legs.hinge, axis, landing - leaning, TILT_STEP)
                        stages = (
                            ("hold it hanging where it is leaned over", [hanging]),
                            ("lean it over", lean),
                            ("carry it out over the far legs", out),
                            ("let it down on them", [touch]),
                            ("tilt it down onto the near legs", tilt),
                            ("pull back out of it", [backed_off(tilt[-1], TOP_RETREAT)]),
                        )
                        why = self._first_out_of_reach(stages, wrist)
                        if why is not None:
                            self._log.info(
                                f"  not leaning {math.degrees(leaning):.0f} degrees that way: {why}"
                            )
                            continue
                        # Carried round at whichever is higher, its height lifted out
                        # or where it is leaned over, so it is never lowered back
                        # towards the holders on the way.
                        centre_height = max(
                            (lifted @ np.linalg.inv(held))[2, 3], (hanging @ np.linalg.inv(held))[2, 3]
                        )
                        carry = carry_round(held, lifted, hanging, centre_height, BASE_POSITION) + [hanging]
                        return TiltRoute(
                            route=Route(
                                approach=approach, pick=pick, lifted=lifted, carry=carry, wrist=wrist
                            ),
                            leaning=leaning,
                            lean=lean,
                            out=out,
                            touch=touch,
                            resting_edge=edge,
                            axis=axis,
                            landing=landing,
                        )
        raise TaskFailed(f"the top cannot be put on these legs however it is gripped: {why}")

    def _first_out_of_reach(self, stages, wrist: float) -> str | None:
        """What the arm could not do, of stages followed one after the other, and why; ``None`` if all.

        The poses are followed in order, each from the joint angles of the
        last, which is how the arm will really go through them.
        """
        poses = [pose for _, stage in stages for pose in stage]
        stopped = self._arm.can_follow(poses, wrist=wrist)
        if stopped is None:
            return None
        for what, stage in stages:
            if stopped < len(stage):
                where = f" (pose {stopped + 1} of {len(stage)})" if len(stage) > 1 else ""
                return f"the arm cannot {what}{where}: {self._arm.why_not}"
            stopped -= len(stage)
        return None

    def _let_down(self, touch: np.ndarray) -> None:
        """Let the leaning top down until its lower edge rests on the far legs.

        Where the legs are is known to a millimetre or two, and where the
        board's edge is in the fingers to about the same, so the arm feels for
        them rather than trusting the numbers. It steps down half a millimetre
        at a time and watches its own joints: when the legs take some of the
        top's weight, the shoulder, elbow and wrist 1 have less to hold up.
        Then it goes back up the one step, so the top sits just on the legs
        rather than being pushed into them; as it sags in the fingers, they
        catch it.
        """
        ready = shifted(touch, WORLD_Z * TOUCH_START)
        try:
            self._arm.move_linear(ready, speed=CARRY_SPEED)
        except MotionFailed as failure:
            self._log.info(f"{failure}; going down the last few centimetres unchecked")
            self._arm.move_linear(ready, avoid_collisions=False, speed=CARRY_SPEED)
        before = self._still_efforts()
        depth = TOUCH_START
        while depth > -TOUCH_LIMIT:
            depth -= TOUCH_STEP
            self._arm.move_linear(shifted(touch, WORLD_Z * depth), avoid_collisions=False, speed=CARRY_SPEED)
            change = float(np.max(np.abs(self._still_efforts() - before)[1:4]))
            self._log.info(f"  {depth * 1000:+.1f} mm: the joints' efforts changed by up to {change:.2f} N·m")
            if change > TOUCH_EFFORT:
                self._log.info(
                    f"the far legs took the top's weight {depth * 1000:+.1f} mm from where they were measured"
                )
                up = shifted(touch, WORLD_Z * (depth + TOUCH_STEP))
                self._arm.move_linear(up, avoid_collisions=False, speed=CARRY_SPEED)
                return
        past = TOUCH_LIMIT * 1000
        raise TaskFailed(
            f"let the top down {past:.0f} mm past where the far legs were measured and felt nothing"
        )

    def _loosen_grip(self) -> None:
        """Open the fingers just clear of the top, now the far legs hold up one edge of it.

        The arm still holds up the other edge until the near legs take it; what
        goes is the squeeze. The joints' efforts are compared before and after,
        for the log: they show how much of the top the grip had been holding.
        """
        before = self._still_efforts()
        closed = self._arm.gripper_gap
        gap = self._arm.set_gripper(min(closed + GRIP_LOOSEN, GRIPPER_MAX_OPENING))
        change = self._still_efforts() - before
        self._log.info(
            f"loosened the grip, fingers from {closed * 1000:.1f} mm to {gap * 1000:.1f} mm; "
            f"the shoulder's, elbow's and wrist 1's efforts changed by "
            f"{', '.join(f'{c:+.2f}' for c in change[1:4])} N·m"
        )

    def _still_efforts(self) -> np.ndarray:
        """The arm joints' efforts, averaged over a moment with the arm standing still."""
        time.sleep(SETTLE)
        self._arm.start_recording()
        time.sleep(AVERAGE)
        samples = self._arm.stop_recording()
        if not samples:
            raise TaskFailed("no joint readings came in")
        return np.nanmean([sample.efforts for sample in samples], axis=0)

    def _pull_out(self, place: np.ndarray) -> None:
        """Pull the open gripper back out from the top, then lift clear.

        It backs out along the way it reached in, because one finger is under
        the top. That first move is unchecked: the fingers start out either
        side of the top.
        """
        away = backed_off(place, TOP_RETREAT)
        try:
            self._arm.move_linear(away, avoid_collisions=False)
        except MotionFailed as failure:
            self._log.info(f"{failure}; letting the planner back away instead")
            self._arm.move_to(away)
        up = shifted(away, WORLD_Z * LIFT)
        try:
            self._arm.move_linear(up)
        except MotionFailed as failure:
            self._log.info(f"{failure}; letting the planner lift clear instead")
            self._arm.move_to(up)

    def _check_table(self, top: Box, legs: TableLegs) -> TableCheck | None:
        """Measure what was built.

        The top and the legs under it now touch, so they come back from the
        camera as one coloured lump, and a box fitted to that lump is the
        table: its footprint is the top's, its height is legs plus top.
        """
        _, width = upright_size(top)
        centre = legs.hinge + legs.toward * (width / 2.0)
        centre[2] = self._floor_z
        parts = []
        for camera in (centre + WORLD_Z * 0.50, centre + legs.toward * 0.15 + WORLD_Z * 0.45):
            if self._point_camera(camera, centre - camera):
                view = self._camera.capture()
                mask, _ = colour_masks(view.rgb, view.depth)
                parts.append(back_project(view.depth, mask, view.intrinsics, view.camera_to_world))
        if not parts:
            self._log.error("could not get the camera over the table to check it")
            return None
        lumps = [
            lump
            for lump in cluster(np.concatenate(parts))
            if np.linalg.norm(lump.mean(axis=0)[:2] - centre[:2]) < 0.15
        ]
        if not lumps:
            self._log.error("no table where the table should be")
            return None
        lump = lumps[0]
        table = fit_resting_box(lump, self._floor_z)
        surface = lump[lump[:, 2] > table.top_z - 0.006]
        return TableCheck(
            size=table.size,
            expected_height=legs.hinge[2] - self._floor_z + float(top.size[2]),
            tilt=surface_tilt(surface),
            offset=float(np.linalg.norm(table.centre[:2] - centre[:2])),
        )

    # ------------------------------------------------------------ utilities

    def _grip(self, width: float) -> None:
        """Close the fingers across a part ``width`` wide, and make sure they feel it."""
        self._arm.set_gripper(max(width - GRIP_SQUEEZE, 0.0))
        self._log.info(f"fingers closed to {self._arm.gripper_gap * 1000:.0f} mm on {width * 1000:.0f} mm")
        if not self._arm.wait_for_contact():
            raise TaskFailed("the fingers felt nothing, so the grasp missed")

    def _down_onto(self, pose: np.ndarray) -> None:
        """The last few centimetres down over the top's edge.

        Checked if possible. The fingers pass either side of the board, and a
        board measured a little fat, or anything next to it seen as an
        obstacle, can make the checked line refuse. The line is short, straight
        down, and starts from a pose reached under checking, so it is then run
        unchecked rather than given up on.
        """
        try:
            self._arm.move_linear(pose)
        except MotionFailed as failure:
            self._log.info(f"{failure}; running the last {TOP_APPROACH * 100:.0f} cm unchecked")
            self._arm.move_linear(pose, avoid_collisions=False)

    def _forget(self, name: str) -> None:
        """Drop a part from MoveIt's scene, so the fingers are allowed to reach it."""
        self._known.pop(name, None)
        self._publish()

    def _publish(self) -> None:
        self._scene.set_objects(dict(self._known))

    def _report_room(self, room: Room) -> None:
        self._log.info(f"floor at z = {room.floor_z * 1000:.1f} mm")
        for box in room.obstacles:
            self._log.info(f"  obstacle, {describe(box.size)}, at {np.round(box.centre[:2], 3).tolist()}")
        if room.top is not None:
            self._log.info(
                f"  table top, {describe(room.top.size)}, at {np.round(room.top.centre, 3).tolist()}"
            )
        for leg in room.legs:
            self._log.info(f"  leg, {describe(leg.size)}, at {np.round(leg.centre[:2], 3).tolist()}")
        for box in room.unknown:
            self._log.warning(f"  something coloured that is neither the top nor a leg, {describe(box.size)}")


def _moving_time(samples: list[JointSample]) -> float:
    """Simulated seconds from the first joint reading that moved to the last.

    The recording also covers the checks made before the arm sets off, which
    are not part of the turn.
    """
    angles = np.array([sample.positions for sample in samples])
    moving = np.nonzero(np.abs(np.diff(angles, axis=0)).max(axis=1) > 1e-4)[0]
    if len(moving) == 0:
        return 0.0
    return samples[moving[-1] + 1].time - samples[moving[0]].time


def _joint_reports(turn: list[JointSample], holding: list[JointSample]) -> list[JointReport]:
    """Per joint: how far it moved during the turn, and the effort it took."""
    if not turn:
        raise TaskFailed("no joint readings came in during the turn")
    angles = np.array([sample.positions for sample in turn])
    efforts = np.array([sample.efforts for sample in turn])
    held = (
        np.array([sample.efforts for sample in holding]) if holding else np.full((1, len(ARM_JOINTS)), np.nan)
    )
    return [
        JointReport(
            name=name,
            travel=float(angles[:, i].max() - angles[:, i].min()),
            turned=float(angles[-1, i] - angles[0, i]),
            peak_effort=float(np.nanmax(np.abs(efforts[:, i])))
            if np.isfinite(efforts[:, i]).any()
            else math.nan,
            holding_effort=float(np.nanmean(np.abs(held[:, i])))
            if np.isfinite(held[:, i]).any()
            else math.nan,
        )
        for i, name in enumerate(ARM_JOINTS)
    ]
