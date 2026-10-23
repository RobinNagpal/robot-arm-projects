"""One table in the full-arm cell: the arm, MoveIt, the camera on the wrist, and the marks.

``ArmSimulator`` is the physics. ``MoveItLink`` is the planner. ``Pusher`` turns a
request into MoveIt motions. This file puts them together for one table, and is
what the examiner (``arm_examiner.py``) and the data tools work with. A solution never
sees it: it is handed an arm and a clock instead.

**Where the arm looks from.** The box model was trained on pictures from two
viewing poses, ``VIEW`` and ``VIEW_B``, and both are kept here with the joint
angles the arm reaches them in.
"""

from __future__ import annotations

import math

import arm_camera
from arm_simulator import READY, ArmSimulator
from moveit_link import MESHES, MoveItLink, flange_goal, generate_urdf
from pusher import Box, Pushed, Pusher, Request, Settings, scene_boxes, table_box  # noqa: F401
from work_cell.rack.layout import GLASS_ZONE

from partners import STANDING_TILT_DEG, Waypoint
from scoring import pickable_on_table

# Where the arm stands to take a picture: over the middle of the glass zone,
# higher than problem 4's travel height, because here the hand and the arm
# behind it must clear the tallest glass's box, and 0.30 left the hand's
# underside a few millimetres from it. Pointing away from the base.
VIEW = Waypoint(
    x=(GLASS_ZONE[0] + GLASS_ZONE[1]) / 2,
    y=(GLASS_ZONE[2] + GLASS_ZONE[3]) / 2,
    z=0.36,
    heading=0.0,
)


# How tall the glass zone's keep-out volume stands above the table. The tallest
# glass drawn is a little over 0.21 m.
ZONE_CEILING = 0.25


def zone_box() -> dict:
    """A box over the whole glass zone, for planning the trips between viewing poses."""
    x0, x1, y0, y1 = GLASS_ZONE
    margin = 0.03
    return {
        "id": "zone",
        "centre": [(x0 + x1) / 2, (y0 + y1) / 2, 0.75 + ZONE_CEILING / 2],
        "size": [x1 - x0 + 2 * margin, y1 - y0 + 2 * margin, ZONE_CEILING],
    }


# The second place to look from: the near side of the zone, hand pointing across
# it. A glass behind another glass, as seen from the first pose, is in plain view
# from here. Measured over the first sixty training tables, one pose misses a
# glass on about a quarter of them, and a push that heads for a glass nobody
# told MoveIt about strikes it.
VIEW_B = Waypoint(x=VIEW.x, y=-0.04, z=0.36, heading=-math.pi / 2)
VIEWS = (VIEW, VIEW_B)


_VIEW_SETS: list | None = None


def view_joint_sets(link: MoveItLink | None = None) -> list:
    """The joint angles of both viewing postures, worked out once by MoveIt and then kept.

    Inverse kinematics reaches one pose in several postures and the solver does not
    always return the same one, and some postures of the viewing pose have the
    forearm over the glass zone, which the planner treats as solid while the arm is
    looking. So the postures are chosen once, checked, written down, and every later
    run is sent to those exact joint angles instead of being asked to find them.
    """
    global _VIEW_SETS
    if _VIEW_SETS is not None:
        return _VIEW_SETS
    import json

    from moveit_link import GENERATED

    file = GENERATED / "views.json"
    if file.exists():
        _VIEW_SETS = json.loads(file.read_text())
        return _VIEW_SETS

    own = link is None
    link = MoveItLink() if own else link
    try:
        link.scene([table_box(), zone_box()])
        found = []
        for view in VIEWS:
            q = link.ik(list(READY), flange_goal(view.x, view.y, 0.75 + view.z, view.heading))
            if q is None:
                raise RuntimeError(f"MoveIt cannot reach the viewing pose {view}")
            found.append(q)
    finally:
        if own:
            link.close()
    GENERATED.mkdir(exist_ok=True)
    file.write_text(json.dumps(found))
    _VIEW_SETS = found
    return found


def view_joints(link: MoveItLink) -> list:
    return view_joint_sets(link)[0]


class ArmCell:
    """The cell for one table."""

    def __init__(
        self, seed: int, link: MoveItLink, glasses: list | None = None, *, camera: bool = True
    ) -> None:
        import tables

        self.seed = seed
        self.link = link
        # Every table starts with the arm at the viewing pose, as problem 4's
        # starts with the jaw at HOME. Parked anywhere else, the arm would
        # have to sweep through the glass zone to get to its first look, and
        # it does that blind.
        self.simulator = ArmSimulator(
            seed,
            glasses if glasses is not None else tables.table(seed),
            urdf=generate_urdf(),
            meshes=MESHES,
            start=view_joints(link),
        )
        self.pusher = Pusher(self.simulator, link)
        self.camera = arm_camera.ArmCamera(self.simulator) if camera else None
        self.pickable_at_start = pickable_on_table(self.simulator)

    # ------------------------------------------------------------- the marks

    def glasses(self) -> int:
        return len(self.simulator.glasses)

    def toppled(self) -> int:
        return sum(1 for i in self.simulator.on_table() if self.simulator.tilt(i) >= STANDING_TILT_DEG)

    def pickable(self) -> int:
        return pickable_on_table(self.simulator)

    @property
    def arm_seconds(self) -> float:
        return self.simulator.arm_seconds

    # ---------------------------------------------------------------- pushing

    def push(self, boxes: list[Box], request: Request, seconds_left: float = math.inf) -> Pushed:
        return self.pusher.push(boxes, request, seconds_left)

    def close(self) -> None:
        if self.camera is not None:
            self.camera.close()
