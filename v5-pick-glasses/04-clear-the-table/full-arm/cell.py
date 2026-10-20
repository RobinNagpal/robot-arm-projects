"""One table in the full-arm cell: the arm, MoveIt, the camera on the wrist, and the scoring.

``ArmBench`` is the physics. ``MoveItLink`` is the planner. ``Pusher`` turns a
request into four MoveIt motions. This file is what a solution sees: a place to
look from, a way to ask for a push, and the same marks problem 4 gives.

**Looking costs arm time, as it does in problem 4.** The camera is on the wrist,
so a look is a trip to the pose the picture is taken from, planned by MoveIt and
carried out by the arm. The trip is charged like any other motion. After a push
the hand is standing behind the glass it pushed, looking along the push, so the
next look needs its own trip; the cell makes it before every decision and the
cost is part of the cost of a decision.

**What a solution is told.** The picture, and the boxes the box model found in
it. Nothing else about the glasses: no sizes, no positions from the simulator.
``measured`` (problem 2's readings, with problem 2's error) is kept for the
baselines that are meant to be the geometry reference and for the box model's
own training labels, and is not part of what a learned solution reads.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import arm_camera
import numpy as np
from arm_bench import READY, ArmBench
from moveit_link import MESHES, MoveItLink, flange_goal, generate_urdf
from pusher import Box, Pushed, Pusher, Request, Settings, scene_boxes, table_box  # noqa: F401
from work_cell.rack.layout import GLASS_ZONE

import wrist
from partners import STANDING_TILT_DEG, Seen, Waypoint
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


@dataclass(frozen=True)
class Seen3:
    """What one look hands over."""

    picture: np.ndarray
    measured: tuple[Seen, ...]  # problem 2's readings of the glasses the camera could see
    jaw: Waypoint  # where the fingertips were when the picture was taken


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
        self.bench = ArmBench(
            seed,
            glasses if glasses is not None else tables.table(seed),
            urdf=generate_urdf(),
            meshes=MESHES,
            start=view_joints(link),
        )
        self.pusher = Pusher(self.bench, link)
        self.camera = arm_camera.ArmCamera(self.bench) if camera else None
        self.known: list[Box] = []  # the boxes of the last look, for planning the trip to the next one
        self.pickable_at_start = pickable_on_table(self.bench)

    # ------------------------------------------------------------- the marks

    def glasses(self) -> int:
        return len(self.bench.glasses)

    def toppled(self) -> int:
        return sum(1 for i in self.bench.on_table() if self.bench.tilt(i) >= STANDING_TILT_DEG)

    def pickable(self) -> int:
        return pickable_on_table(self.bench)

    @property
    def arm_seconds(self) -> float:
        return self.bench.arm_seconds

    # ---------------------------------------------------------------- looking

    def go_to_view(
        self, seconds_left: float = math.inf, view: Waypoint = VIEW, blind: bool = False
    ) -> tuple[bool, str]:
        """Take the arm to the pose a picture is taken from, by MoveIt. Returns whether it got there."""
        # ``blind`` is the trip made before all the glasses are known. The whole
        # glass zone is then treated as solid up to just above the tallest
        # glass, so the arm flies over it to look and cannot strike a glass it
        # has not been told about. A trip made after a full look uses the boxes.
        extra = [zone_box()] if blind else []
        self.link.scene(scene_boxes(self.known, 0.01) + extra)
        motion = self.link.plan(
            self.bench.joints(),
            None,
            vel=0.6,
            acc=0.6,
            planning_time=5.0,
            attempts=3,
            goal_joints=view_joint_sets()[VIEWS.index(view)],
        )
        if not motion.ok:
            return False, f"no way to the viewing pose: {motion.why}"
        if motion.seconds > seconds_left:
            return False, "the trip to look does not fit in the time left"
        self.bench.run(motion.times, motion.joints)
        return True, ""

    def look(self) -> Seen3:
        """The picture from where the hand stands, and the readings of the glasses in it."""
        jaw = self.bench.tcp()
        picture = self.camera.view(jaw)
        seen = tuple(wrist.in_picture(jaw, self.bench.look()))
        return Seen3(picture, seen, jaw)

    # ---------------------------------------------------------------- pushing

    def push(self, boxes: list[Box], request: Request, seconds_left: float = math.inf) -> Pushed:
        self.known = list(boxes)
        return self.pusher.push(boxes, request, seconds_left)

    def close(self) -> None:
        if self.camera is not None:
            self.camera.close()


class Memory:
    """The boxes found so far, merged across looks.

    One picture does not show the table: a glass behind another is simply not
    in it. The arm therefore looks from two places at the start of a table and
    keeps what it found. Only the glass it pushes moves, so after a push that
    one box is forgotten and the next look puts it back, and every other box
    stays where it was.
    """

    MATCH = 0.03  # two boxes this close are the same glass

    def __init__(self) -> None:
        self.boxes: list[Box] = []

    def update(self, found: list[Box]) -> None:
        for box in found:
            for k, old in enumerate(self.boxes):
                if math.dist((box.x, box.y), (old.x, old.y)) < self.MATCH:
                    self.boxes[k] = box
                    break
            else:
                self.boxes.append(box)

    def forget(self, box: Box) -> None:
        self.boxes = [b for b in self.boxes if math.dist((b.x, b.y), (box.x, box.y)) > 1e-9]


def boxes_from_readings(seen) -> list[Box]:
    """Boxes straight from problem 2's readings. For the baselines and as the box model's answer key."""
    return [Box(g.x, g.y, g.widest / 2.0, g.height, g.foot / 2.0) for g in seen]


def thinking(started: float, cell: ArmCell) -> float:
    return max(0.0, (time.perf_counter() - started) - cell.bench.seconds)
