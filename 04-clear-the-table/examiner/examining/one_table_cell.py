"""One table: the arm, MoveIt, the camera on the wrist, and the marks.

``ArmAndTableSimulator`` is the physics. ``MoveItConnection`` is the planner. ``MoveItPusher`` turns a
request into MoveIt motions. This file puts them together for one table, and is
what the examiner (``table_examiner.py``) and the data tools work with. A solution never
sees it: it is handed an arm and a clock instead.

**Where the arm looks from.** The box model was trained on pictures from two
viewing poses, ``FIRST_VIEW_WAYPOINT`` and ``SECOND_VIEW_WAYPOINT``, and both are kept here with the joint
angles the arm reaches them in.
"""

from __future__ import annotations

import math

from work_cell.rack.layout import GLASS_ZONE

from examiner.examining.table_scoring import count_pickable_glasses
from examiner.motion.moveit_connection import (
    ARM_COLLISION_MESHES,
    MoveItConnection,
    flange_goal_for_fingertips,
    write_arm_urdf_if_missing,
)
from examiner.motion.push_motions import (
    GlassBox,
    MoveItPusher,
    PusherResult,
    PushRequest,
    table_collision_box,
)
from examiner.simulation import wrist_camera
from examiner.simulation.arm_and_table_simulator import PARKED_JOINT_ANGLES, ArmAndTableSimulator
from examiner.simulation.taken_from_problem_3 import STANDING_TILT_DEG, Waypoint

# Where the arm stands to take a picture: over the middle of the glass zone,
# higher than problem 4's travel height, because here the hand and the arm
# behind it must clear the tallest glass's box, and 0.30 left the hand's
# underside a few millimetres from it. Pointing away from the base.
FIRST_VIEW_WAYPOINT = Waypoint(
    x=(GLASS_ZONE[0] + GLASS_ZONE[1]) / 2,
    y=(GLASS_ZONE[2] + GLASS_ZONE[3]) / 2,
    z=0.36,
    heading=0.0,
)


# How tall the glass zone's keep-out volume stands above the table. The tallest
# glass drawn is a little over 0.21 m.
ZONE_KEEP_OUT_HEIGHT = 0.25


def glass_zone_keep_out_box() -> dict:
    """A box over the whole glass zone, for planning the trips between viewing poses."""
    x0, x1, y0, y1 = GLASS_ZONE
    margin = 0.03
    return {
        "id": "zone",
        "centre": [(x0 + x1) / 2, (y0 + y1) / 2, 0.75 + ZONE_KEEP_OUT_HEIGHT / 2],
        "size": [x1 - x0 + 2 * margin, y1 - y0 + 2 * margin, ZONE_KEEP_OUT_HEIGHT],
    }


# The second place to look from: the near side of the zone, hand pointing across
# it. A glass behind another glass, as seen from the first pose, is in plain view
# from here. Measured over the first sixty training tables, one pose misses a
# glass on about a quarter of them, and a push that heads for a glass nobody
# told MoveIt about strikes it.
SECOND_VIEW_WAYPOINT = Waypoint(x=FIRST_VIEW_WAYPOINT.x, y=-0.04, z=0.36, heading=-math.pi / 2)
VIEW_WAYPOINTS = (FIRST_VIEW_WAYPOINT, SECOND_VIEW_WAYPOINT)


_VIEWING_JOINT_ANGLES: list | None = None


def viewing_joint_angles(moveit: MoveItConnection | None = None) -> list:
    """The joint angles of both viewing postures, worked out once by MoveIt and then kept.

    Inverse kinematics reaches one pose in several postures and the solver does not
    always return the same one, and some postures of the viewing pose have the
    forearm over the glass zone, which the planner treats as solid while the arm is
    looking. So the postures are chosen once, checked, written down, and every later
    run is sent to those exact joint angles instead of being asked to find them.
    """
    global _VIEWING_JOINT_ANGLES
    if _VIEWING_JOINT_ANGLES is not None:
        return _VIEWING_JOINT_ANGLES
    import json

    from examiner.motion.moveit_connection import GENERATED_FOLDER

    saved_file = GENERATED_FOLDER / "views.json"
    if saved_file.exists():
        _VIEWING_JOINT_ANGLES = json.loads(saved_file.read_text())
        return _VIEWING_JOINT_ANGLES

    opened_here = moveit is None
    moveit = MoveItConnection() if opened_here else moveit
    try:
        moveit.set_collision_boxes([table_collision_box(), glass_zone_keep_out_box()])
        found = []
        for view in VIEW_WAYPOINTS:
            goal = flange_goal_for_fingertips(view.x, view.y, 0.75 + view.z, view.heading)
            joint_angles = moveit.inverse_kinematics(list(PARKED_JOINT_ANGLES), goal)
            if joint_angles is None:
                raise RuntimeError(f"MoveIt cannot reach the viewing pose {view}")
            found.append(joint_angles)
    finally:
        if opened_here:
            moveit.close()
    GENERATED_FOLDER.mkdir(exist_ok=True)
    saved_file.write_text(json.dumps(found))
    _VIEWING_JOINT_ANGLES = found
    return found


def first_viewing_joint_angles(moveit: MoveItConnection) -> list:
    return viewing_joint_angles(moveit)[0]


class OneTableCell:
    """The cell for one table."""

    def __init__(
        self,
        seed: int,
        moveit: MoveItConnection,
        glasses: list | None = None,
        *,
        with_wrist_camera: bool = True,
    ) -> None:
        from examiner.simulation import table_draw

        self.seed = seed
        self.moveit = moveit
        # Every table starts with the arm at the viewing pose, as problem 4's
        # starts with the jaw at HOME. Parked anywhere else, the arm would
        # have to sweep through the glass zone to get to its first look, and
        # it does that blind.
        self.simulator = ArmAndTableSimulator(
            seed,
            glasses if glasses is not None else table_draw.draw_table(seed),
            urdf=write_arm_urdf_if_missing(),
            meshes=ARM_COLLISION_MESHES,
            start_joint_angles=first_viewing_joint_angles(moveit),
        )
        self.pusher = MoveItPusher(self.simulator, moveit)
        self.wrist_camera = wrist_camera.WristCameraRenderer(self.simulator) if with_wrist_camera else None
        self.pickable_at_start = count_pickable_glasses(self.simulator)

    # ------------------------------------------------------------- the marks

    def glass_count(self) -> int:
        return len(self.simulator.glasses)

    def count_toppled_glasses(self) -> int:
        return sum(1 for i in self.simulator.on_table() if self.simulator.tilt(i) >= STANDING_TILT_DEG)

    def pickable_glass_count(self) -> int:
        return count_pickable_glasses(self.simulator)

    @property
    def arm_seconds(self) -> float:
        return self.simulator.arm_seconds

    # ---------------------------------------------------------------- pushing

    def push_glass(
        self, boxes: list[GlassBox], request: PushRequest, arm_seconds_left: float = math.inf
    ) -> PusherResult:
        return self.pusher.plan_and_make_push(boxes, request, arm_seconds_left)

    def close(self) -> None:
        if self.wrist_camera is not None:
            self.wrist_camera.close()
