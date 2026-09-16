"""Where the tool has to be to pick the top up, carry it, and turn it flat.

A part in the gripper is rigidly attached to the tool, so once it has been
picked up, the part and the tool move as one body. That is captured by the
*hold*: the tool's pose written in the part's own frame, worked out at the
moment of the grasp. Putting the part anywhere is then one line: the tool
goes to the part's new pose times the hold.

The top stands upright. The tool grips the middle of its upper edge from
straight above, a finger either side, so the board hangs straight down from
the fingers with its gripped edge along the tool's x axis. Turning it flat is
then one turn about a line along that edge's direction: through the edge
itself when the whole arm turns it, through the wrist when one joint does,
and through its lower edge, resting on two legs, when it is tilted down onto
them.

All poses are 4x4 matrices. Plain numpy, no ROS.
"""

from __future__ import annotations

import math

import numpy as np

from ..arm.dimensions import FINGERTIP_OFFSET
from ..geometry import Box
from ..transforms import WORLD_Z, frame, rotation_about, rotation_z

# How deep the fingers reach down over the top's upper edge. Deep enough that
# both rows of pads are on the board, because it is the spread between the
# rows that keeps a board held by one edge from tipping out of the fingers
# once it is flat.
TOP_INSERTION = 0.050

# How far below tool0 the gripped edge is, along the tool's reach.
EDGE_BELOW_TOOL = FINGERTIP_OFFSET - TOP_INSERTION


def hold(part: Box, tool_pose: np.ndarray) -> np.ndarray:
    """The tool's pose in the part's own frame."""
    return np.linalg.inv(part.pose) @ tool_pose


def carried_tool_pose(held: np.ndarray, tool_rotation: np.ndarray, part_centre: np.ndarray) -> np.ndarray:
    """Where tool0 must be for a held part to sit at ``part_centre``.

    The tool's orientation is chosen by the caller; the part's orientation
    follows from it through the hold.
    """
    part_rotation = tool_rotation @ held[:3, :3].T
    return frame(part_centre, part_rotation) @ held


def upright_edge(top: Box) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The middle of an upright board's upper edge, the way that edge runs, and its face normal.

    Of the board's two broad axes, "up" is the one closer to the vertical,
    whichever way round the fit happened to label them.
    """
    up_axis = max((0, 1), key=lambda i: abs(float(top.axis(i)[2])))
    up = top.axis(up_axis) * math.copysign(1.0, float(top.axis(up_axis)[2]))
    along = top.axis(1 - up_axis)
    edge = top.centre + up * float(top.size[up_axis]) / 2.0
    return edge, along, top.axis(2)


def upright_size(top: Box) -> tuple[float, float]:
    """An upright board's length, along its edges, and its height."""
    up_axis = max((0, 1), key=lambda i: abs(float(top.axis(i)[2])))
    return float(top.size[1 - up_axis]), float(top.size[up_axis])


def upright_tilt(top: Box) -> float:
    """How far the board leans from upright, in radians: its face normal against the level."""
    return math.asin(min(1.0, abs(float(top.axis(2)[2]))))


def down_tool_pose(position: np.ndarray, edge_direction: np.ndarray) -> np.ndarray:
    """A tool pointing straight down at ``position``, its x axis along ``edge_direction``.

    The fingers close along the tool's y axis, square to the edge, so a board
    held like this has its edge along x and hangs straight down along z.
    """
    x = np.array([edge_direction[0], edge_direction[1], 0.0])
    x /= np.linalg.norm(x)
    down = -WORLD_Z
    return frame(position, np.column_stack((x, np.cross(down, x), down)))


def edge_pick_poses(top: Box) -> list[np.ndarray]:
    """Tool poses that grip an upright top by the middle of its upper edge, from straight above.

    Which way round the tool is makes no difference to the grip, so both are
    offered.
    """
    edge, along, _ = upright_edge(top)
    position = edge + WORLD_Z * EDGE_BELOW_TOOL
    return [down_tool_pose(position, sign * along) for sign in (1.0, -1.0)]


def hanging_tool_poses(edge: np.ndarray, axis: np.ndarray) -> list[np.ndarray]:
    """Tool poses that hold a hanging board with its gripped edge at ``edge``, running along ``axis``.

    The two ways round differ by half a turn of the last wrist joint.
    """
    return [down_tool_pose(edge + WORLD_Z * EDGE_BELOW_TOOL, sign * axis) for sign in (1.0, -1.0)]


def gripped_edge(tool_pose: np.ndarray) -> np.ndarray:
    """Where the middle of the gripped edge is, for the tool at ``tool_pose``."""
    return tool_pose[:3, 3] + tool_pose[:3, 2] * EDGE_BELOW_TOOL


def turned_about(pose: np.ndarray, point: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """``pose`` turned by ``angle`` about the line through ``point`` along ``axis``."""
    turn = np.eye(4)
    turn[:3, :3] = rotation_about(axis, angle)
    turn[:3, 3] = point - turn[:3, :3] @ point
    return turn @ pose


def flat_turn(tool_pose: np.ndarray, axis: np.ndarray, base: np.ndarray) -> float:
    """The quarter turn about ``axis`` that swings a hanging board flat, away from the arm.

    Swung towards the arm, the board would end up in the arm's lap, with the
    tool pointing back at its own base. Returns +pi/2 or -pi/2.
    """
    outward = tool_pose[:3, 3] - base
    outward[2] = 0.0
    down = tool_pose[:3, 2]
    return max(
        (math.pi / 2.0, -math.pi / 2.0), key=lambda a: float((rotation_about(axis, a) @ down) @ outward)
    )


def swing_about_edge(tool_pose: np.ndarray, axis: np.ndarray, angle: float, step: float) -> list[np.ndarray]:
    """Tool poses that turn a held board by ``angle`` about its own gripped edge, ``step`` at a time.

    The gripped edge stays where it is and the board turns round it like a
    drawbridge. The tool moves on a small circle round the edge.
    """
    edge = gripped_edge(tool_pose)
    count = max(1, math.ceil(abs(angle) / step))
    return [turned_about(tool_pose, edge, axis, angle * k / count) for k in range(1, count + 1)]


def carry_round(
    held: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    height: float,
    base: np.ndarray,
    step: float = math.radians(5.0),
) -> list[np.ndarray]:
    """Tool poses that carry a held part from ``start`` round the base to above ``end``.

    ``start`` and ``end`` are tool poses that differ only by a turn about the
    vertical. The part goes up to ``height`` first, then round the arm's base
    on an arc at that height: distance from the base and bearing both change
    evenly, so the path never cuts in close to the base. On the way the tool
    turns evenly from the way it pointed at the start to the way it has to
    point at the end. None of that tips the part: it only ever turns about the
    vertical.
    """

    def polar(point):
        offset = point[:2] - base[:2]
        return float(np.linalg.norm(offset)), math.atan2(offset[1], offset[0])

    def wrap(angle):
        return (angle + math.pi) % (2.0 * math.pi) - math.pi

    (r0, a0) = polar((start @ np.linalg.inv(held))[:3, 3])
    (r1, a1) = polar((end @ np.linalg.inv(held))[:3, 3])
    turn = wrap(a1 - a0)
    relative = end[:3, :3] @ start[:3, :3].T
    spin = math.atan2(relative[1, 0], relative[0, 0])
    steps = max(1, math.ceil(max(abs(turn), abs(spin)) / step))

    poses = []
    for fraction in np.linspace(0.0, 1.0, steps + 1):
        radius, azimuth = r0 + (r1 - r0) * fraction, a0 + turn * fraction
        centre = np.array(
            [base[0] + radius * math.cos(azimuth), base[1] + radius * math.sin(azimuth), height]
        )
        poses.append(carried_tool_pose(held, rotation_z(spin * fraction) @ start[:3, :3], centre))
    return poses


def wrist_spin(start: np.ndarray, end: np.ndarray, base: np.ndarray) -> float:
    """How far the last wrist joint turns between two tool poses that point straight down.

    The arm's base turning carries the tool round with it, so what the wrist
    has to add is the tool's own turn less the base's.
    """
    relative = end[:3, :3] @ start[:3, :3].T
    spin = math.atan2(relative[1, 0], relative[0, 0])
    carried = _azimuth(end[:3, 3], base) - _azimuth(start[:3, 3], base)
    return abs((spin - carried + math.pi) % (2.0 * math.pi) - math.pi)


def _azimuth(point: np.ndarray, base: np.ndarray) -> float:
    return math.atan2(point[1] - base[1], point[0] - base[0])


def resting_edge(tool_pose: np.ndarray, held: np.ndarray, size: np.ndarray, toward: np.ndarray) -> np.ndarray:
    """The middle of the board's lower edge on its ``toward`` side, in the board's own frame.

    ``tool_pose`` has the board hanging straight down. Tilted towards
    ``toward`` with its lower edge on something, that is the edge it rests
    and turns on, the way a box tipped over turns on the edge it tips
    towards. Turning about that line, nothing slides on what it rests on.
    """
    rotation = (tool_pose @ np.linalg.inv(held))[:3, :3]
    up = max((0, 1), key=lambda i: abs(float(rotation[2, i])))
    local = np.zeros(3)
    local[up] = -math.copysign(float(size[up]) / 2.0, float(rotation[2, up]))
    local[2] = math.copysign(float(size[2]) / 2.0, float(rotation[:, 2] @ toward))
    return local


def board_point(tool_pose: np.ndarray, held: np.ndarray, local: np.ndarray) -> np.ndarray:
    """Where a point given in the held board's own frame is, for the tool at ``tool_pose``."""
    return (tool_pose @ np.linalg.inv(held) @ np.append(local, 1.0))[:3]


def tilt_axis(toward: np.ndarray) -> np.ndarray:
    """The axis that tilts a standing board's top towards ``toward`` when turned a positive angle about it."""
    axis = np.cross(WORLD_Z, toward)
    return axis / np.linalg.norm(axis)


def tilt_steps(tool_pose: np.ndarray, point: np.ndarray, axis: np.ndarray, angle: float, step: float) -> list:
    """Tool poses that turn a held board by ``angle`` about the line through ``point``, ``step`` at a time."""
    count = max(1, math.ceil(abs(angle) / step))
    return [turned_about(tool_pose, point, axis, angle * k / count) for k in range(1, count + 1)]


def straight_line(start: np.ndarray, end: np.ndarray, step: float) -> list[np.ndarray]:
    """Poses along the straight line from ``start`` to ``end``, which point the same way, ``step`` apart.

    The arm follows the same line either way. Spelled out, each few
    centimetres of it can be checked on its own before the move is made.
    """
    count = max(1, math.ceil(float(np.linalg.norm(end[:3, 3] - start[:3, 3])) / step))
    return [shifted(end, (start[:3, 3] - end[:3, 3]) * (1.0 - k / count)) for k in range(1, count + 1)]


def shifted(pose: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """The same pose moved by ``offset``, in world coordinates."""
    moved = pose.copy()
    moved[:3, 3] = pose[:3, 3] + offset
    return moved


def backed_off(pose: np.ndarray, distance: float) -> np.ndarray:
    """The same pose moved back along the tool's own reach direction."""
    return shifted(pose, -pose[:3, 2] * distance)
