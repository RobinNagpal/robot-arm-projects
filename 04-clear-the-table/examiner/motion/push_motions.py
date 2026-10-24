"""One push, carried out by MoveIt on the whole arm.

This is the file where the four jobs of problem 4 meet, so it is worth
saying what each job is and where its answer enters.

1. **A box round each glass** is an input. It comes from the box model
   (``box_model.py``), not from the simulator, and it is what MoveIt is told the
   world contains.
2. **Where the glass should go** is an input. It comes from the solution's
   learned decision as a direction and a distance.
3. **What to tell MoveIt** is an input. The solution's second learned decision
   is a handful of settings -- how fast, how high, how much room to leave --
   and they are passed on unchanged.
4. **The motion** is MoveIt's. This file asks MoveIt for four motions in turn
   and runs each one on the arm in the simulator: a free move to a point just
   behind the glass, a straight drop to pushing height, the straight stroke
   itself, and a straight retreat. Nothing in this file moves the arm any
   other way, and nothing in it chooses a joint angle.

The order matters and is the reason ``plan_free_move`` is given the later lines to check.
A UR arm reaches one pose in up to eight postures, and holding a level hand
low over a table is possible in only some of them. A posture that arrives
behind the glass but cannot then drop to pushing height without the forearm
meeting the table is useless, so the planner is told about the drop and the
stroke when it picks where to arrive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

from examiner.motion.moveit_connection import MoveItConnection, flange_goal_for_fingertips
from examiner.simulation.arm_and_table_simulator import ArmAndTableSimulator
from examiner.simulation.taken_from_problem_3 import STANDING_TILT_DEG

# How high the hand travels between pushes: clear of the tallest glass drawn.
# Not a learned setting: it is a property of the cell, as problem 3's
# TRAVEL_HEIGHT is, and it is the same for every solution.
TRAVEL_HEIGHT = 0.30

# MoveIt's table is a little lower than the real one. The hand's collision
# model in the URDF is the real gripper's meshes and the simulator's is the
# boxes drawn from them; at pushing height the two differ by millimetres and a
# table at its true height would call the fingers touching it.
MOVEIT_TABLE_LOWERED_BY = 0.004

# How far the hand backs off after a stroke before it lifts, so that it does
# not drag the glass it has just placed back with it.
BACK_OFF_BEFORE_LIFT = 0.03


@dataclass(frozen=True)
class GlassBox:
    """One glass, as a box MoveIt can avoid: where it stands and how much room it takes."""

    x: float
    y: float
    radius: float  # half the width of the box
    height: float
    foot: float = 0.0  # half the width where the glass stands on the table; 0 when not known


@dataclass(frozen=True)
class MoveItSettings:
    """What the learned model passes to MoveIt.

    Every field is a MoveIt setting or a number MoveIt is given, which is the
    meaning of "the model passes the parameters and MoveIt does the movement".
    """

    push_height: float  # how high the middle of the hand rides during the stroke, metres above the table
    stroke_speed: float  # velocity and acceleration scaling for the stroke line
    approach_speed: float  # the same for the free move and the drop
    padding: float  # room added round every box before MoveIt sees it, metres
    standoff: float  # how far behind the glass's box the hand comes down, metres
    # how much further than the box says the stroke goes: glasses narrow away from their widest point
    overreach: float = 0.012

    @staticmethod
    def default() -> MoveItSettings:
        return MoveItSettings(
            push_height=0.085,
            stroke_speed=0.05,
            approach_speed=0.4,
            padding=0.01,
            standoff=0.03,
            overreach=0.012,
        )


@dataclass(frozen=True)
class PushRequest:
    """One push, as a solution asks for it: which glass, which way, how far, and with what settings."""

    glass: int  # an index into the boxes handed over
    heading: float  # the way the hand pushes, radians
    travel: float  # how far the glass is to move, metres
    settings: MoveItSettings


@dataclass
class PusherResult:
    """What happened. ``made`` is false when MoveIt had no motion to give, and then the arm did not move."""

    made: bool
    refusal_reason: str = ""
    arm_seconds: float = 0.0
    peak_force: float = 0.0
    hand_touched_a_glass: bool = False
    fingertips_at_first_touch: object = None  # the fingertips' place at the first touch, for calibration
    motion_stages: list = field(default_factory=list)
    stopped_early: bool = False  # ``stop_when`` ended it before the last motion


def table_collision_box() -> dict:
    return {
        "id": "table",
        "centre": [
            TABLE_CENTRE_XY[0],
            TABLE_CENTRE_XY[1],
            TABLE_TOP_Z - MOVEIT_TABLE_LOWERED_BY - TABLE_SIZE[2] / 2,
        ],
        "size": [TABLE_SIZE[0], TABLE_SIZE[1], TABLE_SIZE[2]],
    }


def moveit_collision_boxes(boxes: list[GlassBox], padding: float) -> list[dict]:
    """The table and a box round every glass, each grown by ``padding`` on every side."""
    world = [table_collision_box()]
    for k, box in enumerate(boxes):
        side = 2 * (box.radius + padding)
        high = box.height + padding
        world.append(
            {"id": f"glass_{k}", "centre": [box.x, box.y, TABLE_TOP_Z + high / 2], "size": [side, side, high]}
        )
    return world


class MoveItPusher:
    """Pushes glasses with the arm, asking MoveIt for every motion."""

    def __init__(self, simulator: ArmAndTableSimulator, moveit: MoveItConnection) -> None:
        self.simulator = simulator
        self.moveit = moveit

    def flange_goals_of_push(self, boxes: list[GlassBox], request: PushRequest) -> dict:
        """The four poses of a push, worked out from the target's box and the settings."""
        box, settings = boxes[request.glass], request.settings
        along_push = np.array([math.cos(request.heading), math.sin(request.heading)])
        centre = np.array([box.x, box.y])
        # The hand comes down far enough behind the box that the box, grown by
        # its padding, is not touching it; otherwise MoveIt would call the
        # start of the drop a collision.
        start = centre - (box.radius + settings.padding + settings.standoff) * along_push
        # The glass is to move ``travel``. The fingertips end that far along
        # their line, less the glass's own radius, because it is the glass's
        # near edge they meet. The box is as wide as the glass is anywhere, and
        # the hand usually meets it where it is narrower -- measured, 17 mm
        # narrower on a stemmed glass -- so the stroke is lengthened by
        # ``overreach`` to make up the difference.
        end = centre + (request.travel + settings.overreach - box.radius) * along_push
        back = end - BACK_OFF_BEFORE_LIFT * along_push
        z_travel, z_push = TABLE_TOP_Z + TRAVEL_HEIGHT, TABLE_TOP_Z + settings.push_height
        pushed_box = f"glass_{request.glass}"
        return {
            "above": flange_goal_for_fingertips(*start, z_travel, request.heading),
            "down": flange_goal_for_fingertips(*start, z_push, request.heading),
            "stroke": flange_goal_for_fingertips(
                *end, z_push, request.heading, box_the_line_may_pass_through=pushed_box
            ),
            "back": flange_goal_for_fingertips(
                *back, z_push, request.heading, box_the_line_may_pass_through=pushed_box
            ),
            "up": flange_goal_for_fingertips(
                *back, z_travel, request.heading, box_the_line_may_pass_through=pushed_box
            ),
        }

    def plan_and_make_push(
        self, boxes: list[GlassBox], request: PushRequest, arm_seconds_left: float = math.inf, stop_when=None
    ) -> PusherResult:
        """Plan the four motions, and only if all of them can be made, carry them out.

        Planning everything first is deliberate. A push that was half carried
        out -- the hand down beside a glass and unable to stroke it -- leaves
        the arm in a place the next plan may not be able to leave. Asking for
        all four before moving costs nothing in arm time, because planning is
        not arm time, and it means a refusal leaves the arm where it was.

        ``stop_when``, when given, is asked after each motion, and a true answer
        stops the push there: the arm holds where that motion ended.
        """
        settings, simulator, moveit = request.settings, self.simulator, self.moveit
        goals = self.flange_goals_of_push(boxes, request)
        moveit.set_collision_boxes(moveit_collision_boxes(boxes, settings.padding))
        start_joint_angles = simulator.joint_angles()

        approach = moveit.plan_free_move(
            start_joint_angles,
            goals["above"],
            lines_that_follow=[goals["down"], goals["stroke"]],
            velocity_scaling=settings.approach_speed,
            acceleration_scaling=settings.approach_speed,
        )
        if not approach.planned:
            return PusherResult(False, f"no way to the start of the push: {approach.refusal_reason}")
        joint_angles_above_the_glass = approach.joint_angles[-1]
        drop = moveit.plan_straight_line(
            joint_angles_above_the_glass,
            goals["down"],
            velocity_scaling=settings.approach_speed,
            acceleration_scaling=settings.approach_speed,
        )
        if not drop.planned:
            return PusherResult(False, f"no way down to pushing height: {drop.refusal_reason}")
        stroke = moveit.plan_straight_line(
            drop.joint_angles[-1],
            goals["stroke"],
            velocity_scaling=settings.stroke_speed,
            acceleration_scaling=settings.stroke_speed,
        )
        if not stroke.planned:
            return PusherResult(False, f"no stroke: {stroke.refusal_reason}")
        retreat = moveit.plan_straight_line(
            stroke.joint_angles[-1],
            goals["back"],
            velocity_scaling=settings.stroke_speed,
            acceleration_scaling=settings.stroke_speed,
        )
        lift = (
            moveit.plan_straight_line(
                retreat.joint_angles[-1],
                goals["up"],
                velocity_scaling=settings.approach_speed,
                acceleration_scaling=settings.approach_speed,
            )
            if retreat.planned
            else retreat
        )
        if not (retreat.planned and lift.planned):
            return PusherResult(
                False, f"no way back out: {(retreat if not retreat.planned else lift).refusal_reason}"
            )

        arm_seconds_needed = sum(
            motion.duration_seconds for motion in (approach, drop, stroke, retreat, lift)
        )
        if arm_seconds_needed > arm_seconds_left:
            # A push is never cut short to fit: half a stroke leaves the hand
            # standing against a glass, which is worse than not starting.
            return PusherResult(
                False,
                f"the push needs {arm_seconds_needed:.1f} s and {arm_seconds_left:.1f} s are left",
                arm_seconds=0.0,
            )

        result = PusherResult(True)
        positions_before = [simulator.position(i).copy() for i in range(len(simulator.glasses))]
        for stage, motion in (
            ("approach", approach),
            ("drop", drop),
            ("stroke", stroke),
            ("retreat", retreat),
            ("lift", lift),
        ):
            trajectory = simulator.run_joint_trajectory(motion.times, motion.joint_angles)
            result.arm_seconds += trajectory.arm_seconds
            result.peak_force = max(result.peak_force, trajectory.peak_force)
            if trajectory.first_touch_seconds is not None and stage == "stroke":
                result.hand_touched_a_glass = True
                result.fingertips_at_first_touch = trajectory.first_touch_fingertips
            moved_mm = [
                round(1000 * float(np.linalg.norm(simulator.position(i) - positions_before[i])), 1)
                for i in range(len(positions_before))
            ]
            result.motion_stages.append(
                (stage, round(trajectory.arm_seconds, 2), self.count_toppled_glasses(), moved_mm)
            )
            if stop_when is not None and stage != "lift" and stop_when():
                result.stopped_early = True
                break
        return result

    def count_toppled_glasses(self) -> int:
        return sum(1 for i in self.simulator.on_table() if self.simulator.tilt(i) >= STANDING_TILT_DEG)
