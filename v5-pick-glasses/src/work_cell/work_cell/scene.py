"""What MoveIt is told about the world.

MoveIt plans against its own picture of the cell, not against Gazebo. Without
this the planner would sweep the arm through the table, through the rack, and
through the glasses standing beside the one it is reaching for.

Every glass is described to the planner as a plain cylinder: as wide as the
glass is at its widest, and as tall as the glass is tall. That is deliberately
bigger than the glass really is, because a cylinder that contains the glass can
never let the arm through a place the glass actually occupies. Planning a
little conservatively costs a few refused approaches; planning optimistically
costs broken glass.

Before the arm reaches for a glass, that glass is taken out of the scene,
because the planner will not let the fingers enter a space it believes is
solid. Once the glass is held it goes back in, attached to the gripper, so that
the turn and the carry are planned with it in hand.
"""

from __future__ import annotations

import numpy as np
from geometry_msgs.msg import Pose
from moveit_msgs.msg import AttachedCollisionObject, CollisionObject, PlanningScene
from moveit_msgs.srv import ApplyPlanningScene
from rclpy.node import Node
from shape_msgs.msg import SolidPrimitive

from .rack.layout import RACK_BASE_HEIGHT, SLOT_SPACING, Slot
from .table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z, WORLD_FRAME
from .transforms import frame, make_pose

# Links the held glass is allowed to be touching without that counting as a
# collision: the ones doing the holding.
GRIPPER_LINKS = ["gripper_body", "left_finger", "right_finger"]


class PlanningSceneClient:
    def __init__(self, node: Node) -> None:
        self._node = node
        self._client = node.create_client(ApplyPlanningScene, "/apply_planning_scene")
        self._known: set[str] = set()

    def wait_until_ready(self, timeout: float = 120.0) -> None:
        """Block until move_group is serving edits to the planning scene."""
        if not self._client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f"/apply_planning_scene did not come up within {timeout:.0f}s")

    def _apply(self, objects: list[CollisionObject], attached=()) -> None:
        if not self._client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError("/apply_planning_scene is not available")
        request = ApplyPlanningScene.Request()
        request.scene = PlanningScene(is_diff=True)
        request.scene.world.collision_objects = objects
        request.scene.robot_state.attached_collision_objects = list(attached)
        request.scene.robot_state.is_diff = True
        self._client.call(request)

    # ------------------------------------------------------------ fixed parts

    def add_table(self) -> None:
        pose = Pose()
        pose.position.x, pose.position.y = TABLE_CENTRE_XY
        pose.position.z = TABLE_TOP_Z - TABLE_SIZE[2] / 2.0
        pose.orientation.w = 1.0
        self._apply([_box("table", pose, TABLE_SIZE)])

    def add_rack(self, slots: list[Slot]) -> None:
        """A box around the whole rack, once its position has been read.

        The rack is only in the way from the side, and the arm always comes
        down onto a slot from directly above, so one box over the base is
        enough and is far cheaper to plan against than ten separate pegs.
        """
        centre = np.mean([slot.centre for slot in slots], axis=0)
        across = float(np.linalg.norm(slots[-1].centre - slots[0].centre)) + SLOT_SPACING
        pose = Pose()
        pose.position.x, pose.position.y = float(centre[0]), float(centre[1])
        pose.position.z = TABLE_TOP_Z + RACK_BASE_HEIGHT / 2.0
        pose.orientation.w = 1.0
        self._apply([_box("rack", pose, (SLOT_SPACING, across, RACK_BASE_HEIGHT))])

    # ---------------------------------------------------------------- glasses

    def set_glasses(self, glasses: dict[str, tuple[np.ndarray, float, float]]) -> None:
        """Make the scene hold exactly these glasses and no others.

        Each entry is where the glass stands, how wide it is and how tall, and
        becomes one upright cylinder. The glass the arm is about to grasp is
        left out of the dictionary, which is how it gets removed.
        """
        objects = [
            _cylinder(name, position, width, height)
            for name, (position, width, height) in glasses.items()
        ]
        objects += [_removal(name) for name in self._known - set(glasses)]
        self._apply(objects)
        self._known = set(glasses)

    def attach(
        self,
        name: str,
        held_at: np.ndarray,
        width: float,
        height: float,
        tool_pose: np.ndarray,
        link: str = "gripper_body",
    ) -> None:
        """Say that the arm is now holding this glass.

        Until it is attached, MoveIt plans as if the gripper were empty, and
        will turn a full wine glass through the rack on the way to a slot.
        """
        in_tool = np.linalg.inv(tool_pose) @ frame(held_at, np.eye(3))
        held = _cylinder(name, in_tool[:3, 3], width, height, upright=in_tool[:3, :3])
        held.header.frame_id = link
        self._known.discard(name)
        self._apply([], [AttachedCollisionObject(link_name=link, object=held, touch_links=GRIPPER_LINKS)])

    def detach(self, name: str, link: str = "gripper_body") -> None:
        """Say that the arm has let go.

        Detaching in MoveIt drops the object back into the world where it was
        last held, which is between the fingers, so every move afterwards is
        refused for driving the gripper through it. The second call clears that
        copy away; the glass is now standing in the rack, which the rack box
        already covers.
        """
        self._apply([], [AttachedCollisionObject(link_name=link, object=_removal(name))])
        self._apply([_removal(name)])


def _removal(name: str) -> CollisionObject:
    obj = CollisionObject()
    obj.id = name
    obj.header.frame_id = WORLD_FRAME
    obj.operation = CollisionObject.REMOVE
    return obj


def _box(name: str, pose: Pose, size) -> CollisionObject:
    obj = CollisionObject()
    obj.id = name
    obj.header.frame_id = WORLD_FRAME
    obj.operation = CollisionObject.ADD
    obj.primitives = [
        SolidPrimitive(type=SolidPrimitive.BOX, dimensions=[float(v) for v in np.asarray(size)])
    ]
    obj.primitive_poses = [pose]
    return obj


def _cylinder(
    name: str,
    base: np.ndarray,
    width: float,
    height: float,
    upright: np.ndarray | None = None,
) -> CollisionObject:
    """One glass, as a cylinder standing on its base.

    ``base`` is where the glass meets whatever it is standing on, and a
    cylinder in MoveIt is described by its middle, so the pose is half the
    height up from there.
    """
    upright = np.eye(3) if upright is None else upright
    centre = np.asarray(base, dtype=float) + upright @ np.array([0.0, 0.0, height / 2.0])

    obj = CollisionObject()
    obj.id = name
    obj.header.frame_id = WORLD_FRAME
    obj.operation = CollisionObject.ADD
    obj.primitives = [
        SolidPrimitive(type=SolidPrimitive.CYLINDER, dimensions=[float(height), float(width) / 2.0])
    ]
    obj.primitive_poses = [make_pose(centre, upright)]
    return obj
