"""Works out the two turns as v3 really runs them, and draws the pictures in
turn-by-wrist.md, turn-by-whole-arm.md and wrist-or-whole-arm.md.

Run from v3-turn-top-flat/figures/, with this project's own Python, which has
PyBullet:

    ../.pixi/envs/default/bin/python two_turns.py

joint_torques.py works out v2's board at v2's ready pose. This file does the
same for what v3 actually does: seed 1's top (24.4 x 16.5 x 1.9 cm, 0.31 kg),
gripped 5 cm over its edge, its edge at the turning spot 50 cm in front of the
arm and 40 cm up, lined up with wrist 1's axis. The side views are drawn to
scale from the same robot model.

Before drawing, it checks itself: the gripped edge stays put in the whole-arm
turn, the shoulder, elbow and wrist 1 turns add up to the board's, the board
ends flat, and wrist 1's holding torque from PyBullet agrees with the plain
weight-times-lever sum that the docs work through by hand.
"""

from __future__ import annotations

import math
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import joint_torques as jt
import numpy as np
import pybullet as p
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle
from pick_up_and_place import (
    BAD,
    BG,
    GOOD,
    INK,
    INK2,
    PATH,
    TOP,
    arrow,
    board,
    gripper,
    holder,
    note,
    plt,
    save,
    scene,
    unit,
    upright,
)

G = 9.81

# Seed 1's top, as measured, and how it is held. Distances are along the
# tool's reach from tool0: the edge is 12 cm down (fingertips at 17 cm, 5 cm
# over the edge), the middle of the two pad rows 14.7 cm, the board's centre
# half its width past the edge.
LENGTH, WIDTH, THICKNESS = 0.244, 0.165, 0.019
DENSITY = 400.0
MASS = DENSITY * LENGTH * WIDTH * THICKNESS
EDGE = 0.120
PADS = 0.147
CENTRE = EDGE + WIDTH / 2
FINGERS_START, FINGERTIP = 0.050, 0.170

# The turning spot, from task.py: the middle of the gripped edge goes here.
SPOT = np.array([0.50, 0.0, 0.40])

# Joint limits the turns are timed against, scaled by CARRY_SPEED, as in
# arm/motion.py.
CARRY_SPEED = 0.1
SPEED_LIMIT = 3.14 * CARRY_SPEED  # rad/s
ACCELERATION_LIMIT = 4.0 * CARRY_SPEED  # rad/s^2

STEP = math.radians(5.0)
ANGLES = np.radians(np.arange(0, 91, 5))

# What Gazebo reported, seed 1, 400 kg/m^3 (turn-results.md). N·m, degrees.
GAZEBO = {
    "wrist": {
        "peak": (0.33, 26.77, 27.25, 4.07, 0.04, 0.04),
        "holding": (0.00, 24.93, 25.88, 2.71, 0.00, 0.04),
    },
    "whole": {
        "peak": (0.30, 25.28, 27.21, 4.17, 0.04, 0.04),
        "holding": (0.00, 18.01, 18.54, 2.71, 0.00, 0.04),
    },
}
WRIST_COLOUR, WHOLE_COLOUR = "#c0504d", "#2a78d6"
ARM_FILL, ARM_EDGE, JOINT = "#c9ccd1", "#8a9098", "#4f6d8f"


# ------------------------------------------------------------------ the robot


def load(board_mass: float) -> tuple[int, list[int], int, dict]:
    """The robot, holding seed 1's top where the fingers hold it."""
    root = ET.parse(jt.ROBOT).getroot()
    m = max(board_mass, 1e-9)
    size = (LENGTH, THICKNESS, WIDTH)  # along the tool's x, y, z
    link = ET.SubElement(root, "link", name="board")
    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "origin", xyz="0 0 0", rpy="0 0 0")
    ET.SubElement(inertial, "mass", value=f"{m}")
    ET.SubElement(
        inertial,
        "inertia",
        ixx=f"{m * (size[1] ** 2 + size[2] ** 2) / 12}",
        iyy=f"{m * (size[0] ** 2 + size[2] ** 2) / 12}",
        izz=f"{m * (size[0] ** 2 + size[1] ** 2) / 12}",
        ixy="0",
        ixz="0",
        iyz="0",
    )
    joint = ET.SubElement(root, "joint", name="board_grip", type="fixed")
    ET.SubElement(joint, "parent", link="tool0")
    ET.SubElement(joint, "child", link="board")
    ET.SubElement(joint, "origin", xyz=f"0 0 {CENTRE}", rpy="0 0 0")
    path = Path(tempfile.mkdtemp()) / "robot_with_top.urdf"
    path.write_text(ET.tostring(root, encoding="unicode"))

    p.resetSimulation()
    p.setGravity(0, 0, -G)
    body = p.loadURDF(str(path), useFixedBase=True, flags=p.URDF_USE_INERTIA_FROM_FILE)
    names = {p.getJointInfo(body, i)[1].decode(): i for i in range(p.getNumJoints(body))}
    arm = [names[f"{n}_joint"] for n in jt.ARM_JOINTS]
    return body, arm, names["board_grip"], names


class Robot:
    def __init__(self, board_mass: float = MASS) -> None:
        self.body, self.arm, self.board, self.names = load(board_mass)

    def frame(self, q, joint: str) -> np.ndarray:
        """Where a joint's frame is, which is a point on its axis."""
        jt.place(self.body, self.arm, q)
        state = p.getLinkState(self.body, self.names[joint], computeForwardKinematics=True)
        return np.array(state[4])

    def tool(self, q) -> tuple[np.ndarray, np.ndarray]:
        jt.place(self.body, self.arm, q)
        state = p.getLinkState(self.body, self.names["flange-tool0"], computeForwardKinematics=True)
        return np.array(state[4]), np.array(p.getMatrixFromQuaternion(state[5])).reshape(3, 3)

    def holding(self, q) -> np.ndarray:
        zero = np.zeros(6)
        return jt.torques(self.body, self.arm, q, zero, zero)

    def solve_tool(self, position, rotation, seed) -> np.ndarray:
        centre = position + rotation[:, 2] * CENTRE
        return jt.solve(self.body, self.arm, self.board, centre, rotation, np.zeros(3), seed)

    def masses_beyond_wrist_1(self, q) -> list[tuple[str, float, np.ndarray]]:
        """Every mass wrist 1 holds up: name, kg, and where its centre is."""
        jt.place(self.body, self.arm, q)
        parts = [
            ("wrist 1 link", "wrist_1_joint"),
            ("wrist 2 link", "wrist_2_joint"),
            ("wrist 3 link", "wrist_3_joint"),
            ("gripper body", "gripper_mount"),
            ("fingers", "left_finger_joint"),
            ("fingers", "right_finger_joint"),
            ("camera", "wrist_camera_mount"),
            ("table top", "board_grip"),
        ]
        out = []
        for label, joint in parts:
            index = self.names[joint]
            mass = p.getDynamicsInfo(self.body, index)[0]
            centre = np.array(p.getLinkState(self.body, index, computeForwardKinematics=True)[0])
            out.append((label, mass, centre))
        return out


def down_tool(edge_direction: np.ndarray) -> np.ndarray:
    """A tool pointing straight down, its x axis along the edge: down_tool_pose() in grasps.py."""
    x = np.array([edge_direction[0], edge_direction[1], 0.0])
    x /= np.linalg.norm(x)
    d = np.array([0.0, 0.0, -1.0])
    return np.column_stack((x, np.cross(d, x), d))


# ---------------------------------------------------------------- the turns


def work_out() -> dict:
    """Both turns, from the same hanging pose at the turning spot, every 5 degrees."""
    robot = Robot()
    ready = np.radians([0, -90, 90, -90, -90, 0])
    tool_at_spot = SPOT + np.array([0, 0, EDGE])

    # As _plan_route() does: a trial pose at the spot, wrist 1's axis from it,
    # then the hanging pose with the edge along that axis.
    trial = robot.solve_tool(tool_at_spot, down_tool(np.array([1.0, 0, 0])), ready)
    axis = jt.wrist_1_axis(robot.body, robot.arm, robot.board, trial)
    start = robot.solve_tool(tool_at_spot, down_tool(-axis), trial)

    # flat_turn(): the quarter turn that swings the board away from the arm.
    _, rot0 = robot.tool(start)
    outward = np.array([SPOT[0], SPOT[1], 0.0]) / np.linalg.norm(SPOT[:2])
    turn = math.pi / 2 if (jt.rotation(axis, math.pi / 2) @ rot0)[:, 2] @ outward > 0 else -math.pi / 2

    r = {"robot": robot, "axis": axis, "start": start, "turn": turn, "rot0": rot0}
    r["wrist"] = [start + np.eye(6)[3] * turn * a / (math.pi / 2) for a in ANGLES]

    # swing_about_edge(): every pose is the first one turned about the edge.
    r["whole"] = [start.copy()]
    for a in ANGLES[1:]:
        r["whole"].append(solve_edge(r, a / (math.pi / 2), r["whole"][-1]))
    return r


def solve_edge(r: dict, fraction: float, seed) -> np.ndarray:
    """Joint angles with the board turned ``fraction`` of the way flat about its gripped edge."""
    robot = r["robot"]
    target = jt.rotation(r["axis"], r["turn"] * fraction) @ r["rot0"]
    offset = np.array([0.0, 0.0, EDGE - CENTRE])  # the edge, from the board's centre
    return jt.solve(robot.body, robot.arm, robot.board, SPOT, target, offset, seed)


def plane(axis: np.ndarray):
    """Coordinates in the arm's own upright plane: out along it from the base, and up. In cm."""
    out = np.cross(axis, [0.0, 0.0, 1.0])
    out /= np.linalg.norm(out)
    return lambda point: np.array([float(np.asarray(point) @ out), float(point[2])]) * 100


def wrist_1_levers(r: dict, q) -> list[tuple[str, float, float, float]]:
    """Each mass wrist 1 holds up, with its sideways lever from wrist 1's axis. Metres."""
    to_plane = plane(r["axis"])
    w1 = to_plane(r["robot"].frame(q, "wrist_1_joint")) / 100
    merged: dict[str, list[float]] = {}
    for label, mass, centre in r["robot"].masses_beyond_wrist_1(q):
        u, z = to_plane(centre) / 100 - w1
        entry = merged.setdefault(label, [0.0, 0.0, 0.0])
        entry[0] += mass
        entry[1] += mass * u
        entry[2] += mass * z
    return [(label, m, mu / m, mz / m) for label, (m, mu, mz) in merged.items()]


def half_cosine_time(angle: float) -> float:
    """How long _one_joint_trajectory() in arm/motion.py takes to turn a joint by ``angle``."""
    return max(
        math.pi * abs(angle) / (2 * SPEED_LIMIT),
        math.sqrt(math.pi**2 * abs(angle) / (2 * ACCELERATION_LIMIT)),
    )


def moving_part(r: dict) -> dict:
    """How much the motion adds to each joint's torque, at CARRY_SPEED and at full speed."""
    robot = r["robot"]
    out = {}
    for scale in (CARRY_SPEED, 1.0):
        # The wrist turn, exactly as the trajectory is built.
        speed, acc = 3.14 * scale, 4.0 * scale
        angle = abs(r["turn"])
        duration = max(math.pi * angle / (2 * speed), math.sqrt(math.pi**2 * angle / (2 * acc)))
        t = np.linspace(0, duration, 401)
        phase = math.pi * t / duration
        q = np.array([r["start"] + np.eye(6)[3] * r["turn"] * (1 - math.cos(f)) / 2 for f in phase])
        dq = np.outer(r["turn"] * math.pi * np.sin(phase) / (2 * duration), np.eye(6)[3])
        ddq = np.outer(r["turn"] * math.pi**2 * np.cos(phase) / (2 * duration**2), np.eye(6)[3])
        tau = np.array([jt.torques(robot.body, robot.arm, *state) for state in zip(q, dq, ddq, strict=True)])
        hold = np.array([robot.holding(x) for x in q])
        out[("wrist", scale)] = (duration, np.abs(tau - hold).max(axis=0))

        # The whole-arm turn, the board's angle following the same half
        # cosine, stretched until no joint goes past its limits. MoveIt times
        # the real one its own way, so this is only a fair stand-in.
        unit_time = np.linspace(0, 1, 401)
        s = (1 - np.cos(math.pi * unit_time)) / 2
        q = [r["start"].copy()]
        for fraction in s[1:]:
            q.append(solve_edge(r, fraction, q[-1]))
        q = np.array(q)
        dq, ddq = jt.derivatives(q, unit_time)
        duration = max(np.abs(dq).max() / speed, math.sqrt(np.abs(ddq).max() / acc))
        t = unit_time * duration
        dq, ddq = dq / duration, ddq / duration**2
        tau = np.array([jt.torques(robot.body, robot.arm, *state) for state in zip(q, dq, ddq, strict=True)])
        hold = np.array([robot.holding(x) for x in q])
        out[("whole", scale)] = (duration, np.abs(tau - hold).max(axis=0))
    return out


# ----------------------------------------------------------------- checks


def check(r: dict) -> None:
    robot = r["robot"]
    for q, a in zip(r["whole"], ANGLES, strict=True):
        position, rotation = robot.tool(q)
        edge = position + rotation[:, 2] * EDGE
        assert np.linalg.norm(edge - SPOT) < 1e-4, "the gripped edge should stay put"
        change = np.degrees(q - r["start"])
        assert abs(change[1] + change[2] + change[3] + math.degrees(a)) < 0.01, (
            "the three turns should add up"
        )
        assert np.abs(change[[0, 4, 5]]).max() < 0.01, "base and wrists 2 and 3 should not move"
    for q in (r["wrist"][-1], r["whole"][-1]):
        _, rotation = robot.tool(q)
        assert abs(rotation[2, 2]) < 1e-6, "the tool should end level, so the board is flat"
        assert abs(rotation[2, 1]) > 0.999999, "the board's face should look straight up or down"
    for q in r["wrist"]:
        by_hand = G * sum(m * u for _, m, u, _ in wrist_1_levers(r, q))
        assert abs(abs(by_hand) - abs(robot.holding(q)[3])) < 1e-3, "weight times lever should match PyBullet"


# ------------------------------------------------------------------ drawing


def style(ax, xlabel=None, ylabel=None):
    ax.grid(color="#e1e0d9", lw=1)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_facecolor(BG)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2)


def title(ax, text, size=11.5):
    ax.set_title(text, loc="left", fontsize=size, fontweight="bold", color=INK, pad=8)


def rect_between(a, b, half):
    d = (b - a) / np.linalg.norm(b - a)
    n = np.array([-d[1], d[0]]) * half
    return [a + n, b + n, b - n, a - n]


def draw_arm(
    ax, r: dict, q, *, alpha=1.0, z=3, board_alpha=None, labels=False, arm=True, wrist=True, top=True
):
    """The robot and the top in the arm's plane, to scale, in cm.

    Without ``arm``, only the wrist end is drawn; without ``wrist`` either,
    only the gripper and the top.
    """
    robot = r["robot"]
    to_plane = plane(r["axis"])
    base = np.array([0.0, 0.0])
    shoulder = to_plane(robot.frame(q, "shoulder_lift_joint"))
    elbow = to_plane(robot.frame(q, "elbow_joint"))
    w1 = to_plane(robot.frame(q, "wrist_1_joint"))
    w2 = to_plane(robot.frame(q, "wrist_2_joint"))
    position, rotation = robot.tool(q)
    tool0 = to_plane(position)
    reach = to_plane(position + rotation[:, 2]) - tool0
    reach /= np.linalg.norm(reach)
    across = np.array([-reach[1], reach[0]])

    if arm:
        ax.add_patch(Rectangle((-9, 0), 18, 9, fc=ARM_EDGE, ec="none", alpha=alpha, zorder=z))
        points = [base + np.array([0, 9]), shoulder, elbow, w1, w2, tool0]
        widths = [11, 13, 11, 9, 9]
    elif wrist:
        points = [w1, w2, tool0]
        widths = [9, 9]
    else:
        points, widths = [], []
    for colour, extra in ((ARM_EDGE, 2.5), (ARM_FILL, 0.0)):
        for (a, b), w in zip(zip(points, points[1:], strict=False), widths, strict=True):
            ax.plot(
                [a[0], b[0]],
                [a[1], b[1]],
                color=colour,
                lw=w + extra,
                solid_capstyle="round",
                alpha=alpha,
                zorder=z,
            )
    joints = ([shoulder, elbow] if arm else []) + ([w1, w2] if arm or wrist else [])
    for point in joints:
        ax.add_patch(Circle(point, 2.4, fc=JOINT, ec="none", alpha=alpha, zorder=z + 0.2))

    # The gripper, seen along the edge: its body is 11 cm wide across the way
    # the fingers close, and the fingers reach from 5 cm to 17 cm.
    ax.add_patch(
        Polygon(
            rect_between(tool0, tool0 + reach * 5, 5.5), fc="#3d3d3a", ec="none", alpha=alpha, zorder=z + 0.3
        )
    )
    for side in (1, -1):
        centre = across * side * (THICKNESS * 50 + 0.15 + 0.6)
        a = tool0 + reach * FINGERS_START * 100 + centre
        b = tool0 + reach * FINGERTIP * 100 + centre
        ax.add_patch(
            Polygon(rect_between(a, b, 0.6), fc="#77766f", ec="#3d3d3a", lw=0.5, alpha=alpha, zorder=z + 0.6)
        )
    if top:
        a = tool0 + reach * EDGE * 100
        b = tool0 + reach * (EDGE + WIDTH) * 100
        ax.add_patch(
            Polygon(
                rect_between(a, b, THICKNESS * 50),
                fc=TOP,
                ec="#b8491c",
                lw=0.8,
                alpha=alpha if board_alpha is None else board_alpha,
                zorder=z + 0.5,
            )
        )

    if labels:
        return {
            "shoulder": shoulder,
            "elbow": elbow,
            "wrist 1": w1,
            "wrist 2": w2,
            "tool0": tool0,
            "reach": reach,
        }
    return {"wrist 1": w1, "tool0": tool0, "reach": reach}


def floor(ax, x0, x1):
    ax.add_patch(Rectangle((x0, -6), x1 - x0, 6, fc="#e6e4dc", ec="none", zorder=0))
    ax.plot([x0, x1], [0, 0], color="#c3c2b7", lw=1.5, zorder=0)


def side_axes(ax, x0, x1, y0, y1):
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    style(ax, "out from the arm's base, cm", "height above the floor, cm")
    floor(ax, x0, x1)


# ------------------------------------------------------------ 1. overview


def overview():
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.4))
    axes = axes.ravel()
    names = [
        "1. Look round, measure the top",
        "2. Plan every pose first",
        "3. Grip the middle of the edge",
        "4. Lift straight up",
        "5. Carry round, hanging",
        "6. Line the edge up with wrist 1",
        "7a. Turn: wrist 1 alone (make wrist)",
        "7b. Turn: whole arm, about the edge",
    ]
    edge, down = upright()
    for ax, name in zip(axes, names, strict=True):
        scene(ax, 1.0, 6.2, -0.3, 4.4, name)

    ax = axes[0]
    holder(ax, 4.0)
    board(ax, edge, down)
    cam = np.array([2.0, 3.6])
    ax.add_patch(Circle(cam, 0.3, fc="white", ec=INK2, lw=1.5, zorder=4))
    ax.add_patch(Circle(cam, 0.12, fc=INK2, zorder=5))
    for deg in (-50, -30, -10):
        ax.plot(
            [cam[0], cam[0] + 3 * math.cos(math.radians(deg))],
            [cam[1], cam[1] + 3 * math.sin(math.radians(deg))],
            color=INK2,
            lw=0.8,
            ls=":",
            zorder=3,
        )
    note(ax, (1.2, 0.75), "camera on the wrist:\nsize, pose, upper edge")

    ax = axes[1]
    for i, text in enumerate(
        ("the grip from above", "the lift out", "the carry, hanging", "the turn itself")
    ):
        ax.text(1.3, 3.7 - i * 0.62, "✓  " + text, fontsize=10.5, color=GOOD)
    note(ax, (1.3, 0.55), "nothing moves until every\npose has been checked")

    ax = axes[2]
    holder(ax, 4.0)
    board(ax, edge, down)
    gripper(ax, edge, down)
    note(ax, (1.2, 3.9), "fingers 5 cm over the edge,\none each side of the board")

    ax = axes[3]
    lifted = edge + np.array([0, 1.2])
    holder(ax, 4.0)
    board(ax, edge, down, alpha=0.2)
    board(ax, lifted, down)
    gripper(ax, lifted, down)
    arrow(ax, edge + np.array([0.5, -0.6]), lifted + np.array([0.5, -0.6]), lw=1.5)
    note(ax, (1.1, 1.6), "until its lower\nedge is 4 cm above\nwhere its upper\nedge was")

    ax = axes[4]
    ax.cla()
    ax.set_xlim(-2.4, 3.6)
    ax.set_ylim(-1.2, 3.8)
    ax.set_aspect("equal")
    ax.axis("off")
    title(ax, names[4])
    ax.add_patch(Circle((0, 0), 0.35, fc=ARM_FILL, ec=ARM_EDGE, zorder=3))
    note(ax, (0, -0.65), "arm's base", ha="center")
    ax.add_patch(Polygon(rect_between(np.array([-1.2, 2.6]), np.array([1.2, 2.6]), 0.08), fc=TOP, zorder=4))
    ax.add_patch(Polygon(rect_between(np.array([2.5, -0.9]), np.array([2.5, 0.9]), 0.08), fc=TOP, zorder=4))
    ax.add_patch(Arc((0, 0), 5.2, 5.2, theta1=8, theta2=82, color=PATH, lw=2, zorder=2))
    arrow(ax, np.array([2.6 * math.cos(0.3), 2.6 * math.sin(0.3)]), np.array([2.6, 0.02]), color=PATH)
    note(ax, (-1.2, 3.1), "seen from above: where it stood")
    note(ax, (2.8, -0.2), "turning spot:\n50 cm out,\n40 cm up")
    note(ax, (0.2, 1.2), "base turns;\nboard stays\nhanging", size=9)

    ax = axes[5]
    ax.cla()
    ax.set_xlim(-2.4, 3.6)
    ax.set_ylim(-1.2, 3.8)
    ax.set_aspect("equal")
    ax.axis("off")
    title(ax, names[5])
    ax.add_patch(Circle((0, 0), 0.35, fc=ARM_FILL, ec=ARM_EDGE, zorder=3))
    spot = np.array([2.5, 0.0])
    ax.plot([0, 3.4], [0, 0], color=INK2, ls=":", lw=1)
    tilt = math.radians(15.5)
    axis = np.array([math.sin(tilt), math.cos(tilt)])
    ax.plot(*np.array([spot - axis * 1.6, spot + axis * 1.6]).T, color=JOINT, lw=1.2, ls="--")
    ax.add_patch(Polygon(rect_between(spot - axis * 1.1, spot + axis * 1.1, 0.08), fc=TOP, zorder=4))
    ax.plot([spot[0], spot[0]], [-1.0, 1.6], color=INK2, lw=0.8, ls=":")
    note(ax, (spot[0] + 0.45, 1.75), "wrist 1's axis\n(15.5° off square)", size=9)
    note(
        ax,
        (-2.3, 2.6),
        "turned about the vertical on\nthe way, so the gripped edge\nruns along wrist 1's axis",
        size=9.5,
    )

    ax = axes[6]
    wrist = np.array([1.9, 3.3])
    tool_off = np.array([0.4, -0.35])
    for i, deg in enumerate(range(0, 91, 30)):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        rot = np.array([[c, -s], [s, c]])
        tool = wrist + rot @ tool_off
        e = tool + rot @ np.array([0, -1.2])
        fade = 0.2 + 0.8 * (i / 3) ** 2
        ax.plot(
            *np.array([wrist, wrist + rot @ np.array([0.4, 0]), tool]).T,
            color=ARM_EDGE,
            lw=6,
            alpha=fade,
            solid_capstyle="round",
            zorder=4,
        )
        board(ax, e, rot @ unit(-90), alpha=fade)
        gripper(ax, e, rot @ unit(-90), alpha=fade, arm=False)
    ax.add_patch(Circle(wrist, 0.14, fc=PATH, zorder=9))
    ax.add_patch(Arc(wrist, 6.2, 6.2, theta1=-82, theta2=8, color=PATH, ls="--", lw=1.2, zorder=2))
    note(ax, (4.25, 0.5), "board swings round\nwrist 1 (dot) and\nends 32 cm higher", size=9)

    ax = axes[7]
    pivot = np.array([2.6, 3.0])
    for i, deg in enumerate(range(-90, 1, 15)):
        board(ax, pivot, unit(deg), alpha=0.12 + 0.88 * (i / 6) ** 2)
    gripper(ax, pivot, unit(0), arm=False)
    ax.add_patch(Circle(pivot, 0.09, fc=PATH, zorder=9))
    arrow(ax, pivot + unit(-80) * 2.05, pivot + unit(-10) * 2.05, rad=0.35)
    note(ax, (1.05, 0.55), "the gripped edge (dot)\nstays put, like a\ndrawbridge", size=9)

    fig.suptitle(
        "The whole run. Steps 1–6 are the same for both turns; only step 7 differs. "
        "Then: hold flat 5 s, report.",
        x=0.01,
        ha="left",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()
    save(fig, "turn_overview.png")


# ------------------------------------------------------------ 2. the arm's joints


def arm_joints(r: dict):
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6.6), gridspec_kw={"width_ratios": [1.35, 1]})
    side_axes(a, -30, 80, -6, 82)
    title(a, "The six joints, at the start of the turn (to scale)")
    at = draw_arm(a, r, r["start"], labels=True)
    a.text(-28, 4, "base\n(shoulder pan)", fontsize=9.5, color=INK, va="center")
    a.annotate("", xy=(0, 18), xytext=(0, -3), arrowprops=dict(arrowstyle="<->", color=BAD, lw=1.4))
    for name, xy, text in (
        ("shoulder", (-27, 22), "shoulder"),
        ("elbow", (-27, 67), "elbow"),
        ("wrist 1", (22, 74), "wrist 1"),
        ("wrist 2", (56, 72), "wrist 2"),
    ):
        point = at[name]
        a.annotate(
            text,
            xy=point,
            xytext=xy,
            fontsize=10,
            color=INK,
            fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8),
        )
    for name in ("shoulder", "elbow", "wrist 1"):
        a.add_patch(Circle(at[name], 1.0, fc="white", ec="none", zorder=8))
        a.add_patch(Circle(at[name], 0.45, fc=BAD, ec="none", zorder=9))
    w2 = at["wrist 2"]
    a.annotate(
        "",
        xy=w2 + np.array([7, 0]),
        xytext=w2 - np.array([4, 0]),
        arrowprops=dict(arrowstyle="<->", color=BAD, lw=1.4),
        zorder=9,
    )
    tool0 = at["tool0"]
    a.annotate(
        "",
        xy=tool0 + np.array([0, -30]),
        xytext=tool0 + np.array([0, 6]),
        arrowprops=dict(arrowstyle="<->", color=BAD, lw=1.2),
        zorder=2,
    )
    a.annotate(
        "wrist 3",
        xy=tool0 + np.array([0.5, -3]),
        xytext=(62, 50),
        fontsize=10,
        fontweight="bold",
        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8),
    )
    a.text(
        6,
        34,
        "red dot: turns about a line\nstraight out of the page\n"
        "(shoulder, elbow, wrist 1:\nall three parallel)",
        fontsize=9.5,
        color=INK2,
    )
    a.text(52, 30, "red arrow: turns\nabout that line", fontsize=9.5, color=INK2)
    a.text(52, 7, "table top,\nhanging", fontsize=9.5, color="#b8491c")

    # Close-up of the gripper and the board, seen along the edge.
    b.set_xlim(-14, 14)
    b.set_ylim(-31, 4)
    b.set_aspect("equal")
    b.axis("off")
    title(b, "The tool and how the top is held (seen along the edge)")
    b.add_patch(Rectangle((-5.5, -5), 11, 5, fc="#3d3d3a", zorder=3))
    b.add_patch(Rectangle((-2.5, 0), 5, 3, fc=ARM_FILL, ec=ARM_EDGE, zorder=3))
    for side in (1, -1):
        x = side * (THICKNESS * 50 + 0.15 + 0.6)
        b.add_patch(Rectangle((x - 0.6, -17), 1.2, 12, fc="#77766f", ec="#3d3d3a", lw=0.5, zorder=4))
        for row in (13.5, 15.9):
            b.add_patch(
                Rectangle(
                    (side * (THICKNESS * 50) - (0.15 if side > 0 else -0.0), -row - 0.9),
                    0.15 * side,
                    1.8,
                    fc=GOOD,
                    ec=GOOD,
                    lw=1.2,
                    zorder=6,
                )
            )
    b.add_patch(
        Rectangle(
            (-THICKNESS * 50, -(EDGE + WIDTH) * 100),
            THICKNESS * 100,
            WIDTH * 100,
            fc=TOP,
            ec="#b8491c",
            zorder=5,
        )
    )
    b.plot([0], [0], "o", color=PATH, ms=7, zorder=9)
    for depth, text in (
        (0, "tool0 (the flange): 0"),
        (-5, "fingers start: 5 cm"),
        (-12, "gripped edge: 12 cm"),
        (-14.7, "middle of the pad rows: 14.7 cm"),
        (-17, "fingertips: 17 cm"),
        (-(CENTRE * 100), f"top's centre: {CENTRE * 100:.2f} cm"),
        (-(EDGE + WIDTH) * 100, "far edge: 28.5 cm"),
    ):
        b.plot([1.9, 5.8], [depth, depth], color=INK2, lw=0.7, ls=":", zorder=2)
        b.text(6.0, depth, text, fontsize=9, color=INK2, va="center")
    for vec, label, off in (
        (np.array([0, -4.5]), "z: the way the\ngripper reaches", (-12.5, -3.2)),
        (np.array([-4.5, 0]), "y: the way the\nfingers close", (-13.5, 2.0)),
    ):
        b.add_patch(
            FancyArrowPatch(
                (0, 0), tuple(vec), arrowstyle="-|>", mutation_scale=14, color=PATH, lw=2, zorder=9
            )
        )
        b.text(*off, label, fontsize=9, color=PATH)
    b.add_patch(Circle((-12.6, -9), 0.7, fc="white", ec=PATH, lw=1.5, zorder=9))
    b.add_patch(Circle((-12.6, -9), 0.2, fc=PATH, zorder=10))
    b.text(
        -11.4, -9, "x: along the edge,\nout of the page\n(= wrist 1's axis)", fontsize=9, color=PATH, va="top"
    )
    b.text(-13.5, -26, "green: the pad rows,\n2.4 cm apart,\none pair on each finger", fontsize=9, color=GOOD)
    save(fig, "arm_joints.png")


# ------------------------------------------------------------ 3. wrist 1's axis, from above


def wrist_axis(r: dict):
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6.2), gridspec_kw={"width_ratios": [1.3, 1]})
    axis = r["axis"][:2]
    out = np.array([axis[1], -axis[0]])
    angle = math.degrees(math.atan2(-axis[0], axis[1]))
    robot = r["robot"]
    w1 = robot.frame(r["start"], "wrist_1_joint")[:2] * 100
    tool0 = robot.tool(r["start"])[0][:2] * 100
    foot = axis * 13.33

    a.set_xlim(-12, 72)
    a.set_ylim(-26, 30)
    a.set_aspect("equal")
    style(a, "x: straight out in front of the arm, cm", "y: to the arm's left, cm")
    title(a, "Seen from above: why wrist 1's axis is 15.5° off")
    a.add_patch(Circle((0, 0), 7, fc=ARM_FILL, ec=ARM_EDGE, zorder=3))
    a.text(0, -10.5, "arm's base", ha="center", fontsize=9.5, color=INK2)
    a.plot([0, 70], [0, 0], color=INK2, ls=":", lw=1.2, zorder=2)
    a.text(60, 1.2, "line of reach", fontsize=9.5, color=INK2)
    line = np.array([foot - out * 5, foot + out * 72])
    a.plot(*line.T, color=JOINT, lw=7, alpha=0.35, solid_capstyle="round", zorder=2)
    a.text(
        *(foot + out * 8 + axis * 4.5),
        "the arm's own upright plane:\nupper arm, forearm, wrist 1",
        fontsize=9.5,
        color=JOINT,
        rotation=angle,
        rotation_mode="anchor",
    )
    a.annotate("", xy=foot, xytext=(0, 0), arrowprops=dict(arrowstyle="<->", color=BAD, lw=1.4))
    a.text(
        -11,
        28.5,
        "13.3 cm: the UR5e's links\nstep sideways at the\nshoulder, elbow and wrist",
        fontsize=9,
        color=BAD,
        va="top",
    )
    a.plot(*w1, "o", color=JOINT, ms=9, zorder=5)
    a.text(w1[0], w1[1] - 5.5, "wrist 1", fontsize=9.5, color=JOINT, ha="center")
    a.plot(*tool0, "o", color=PATH, ms=7, zorder=6)
    half = LENGTH * 50
    a.add_patch(
        Polygon(
            rect_between(tool0 - axis * half, tool0 + axis * half, THICKNESS * 50),
            fc=TOP,
            ec="#b8491c",
            zorder=5,
        )
    )
    a.plot(
        *np.array([tool0 - np.array([0, 20]), tool0 + np.array([0, 20])]).T,
        color=INK2,
        ls="--",
        lw=1,
        zorder=4,
    )
    a.text(tool0[0] + 1.2, tool0[1] - 20, "square across the\nline of reach", fontsize=9, color=INK2)
    a.add_patch(Arc(tool0, 32, 32, theta1=90 + angle, theta2=90, color=BAD, lw=1.4, zorder=6))
    a.text(tool0[0] + 1.2, tool0[1] + 17.5, f"{abs(angle):.1f}°", fontsize=10.5, color=BAD, fontweight="bold")
    a.text(
        tool0[0] + 7,
        tool0[1] + 11,
        "the hanging top's edge,\nturned to lie along\nwrist 1's axis",
        fontsize=9,
        color="#b8491c",
        va="top",
    )
    a.text(0, -22, f"sin(angle) = 13.3 cm / 50 cm   →   angle = {abs(angle):.1f}°", fontsize=10.5, color=INK)

    # What goes wrong if it is not lined up: seen from in front, after the turn.
    b.set_xlim(-18, 18)
    b.set_ylim(-13, 19)
    b.set_aspect("equal")
    b.axis("off")
    title(b, "After a wrist-only turn, seen from the base")
    for y0, tilt, colour, text in (
        (12, 0.0, GOOD, "edge along wrist 1's axis:\nthe top ends flat"),
        (-4, 15.5, BAD, "edge square across the reach:\nthe top ends 15.5° off flat"),
    ):
        c, s = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
        d = np.array([c, -s])
        centre = np.array([0.0, y0])
        b.add_patch(
            Polygon(rect_between(centre - d * 12.2, centre + d * 12.2, 0.95), fc=TOP, ec="#b8491c", zorder=3)
        )
        b.plot([-14, 14], [y0, y0], color=INK2, lw=0.8, ls=":", zorder=2)
        b.text(-17.5, y0 + (2.5 if tilt == 0 else 5.0), text, fontsize=10, color=colour, fontweight="bold")
    b.text(
        -17.5,
        -12.5,
        "Turning about a line tilted from the edge\nleaves the top tilted by exactly that angle.",
        fontsize=9.5,
        color=INK2,
    )
    save(fig, "wrist_axis.png")


# ------------------------------------------------------------ 4. the wrist turn, side view


def wrist_turn(r: dict):
    fig, ax = plt.subplots(figsize=(11, 7.4))
    side_axes(ax, -20, 90, -6, 88)
    title(ax, "The wrist turn, to scale: wrist 1 turns 90°, nothing else moves", 13)
    for i, a in enumerate((0, 30, 60, 90)):
        index = int(a / 5)
        last = a == 90
        at = draw_arm(
            ax,
            r,
            r["wrist"][index],
            alpha=1.0 if last else 0.28 + 0.15 * i,
            arm=last or i == 0,
            board_alpha=0.25 + 0.75 * (i / 3) ** 2,
        )
    w1 = at["wrist 1"]
    to_plane = plane(r["axis"])
    robot = r["robot"]

    def point(q, depth):
        position, rotation = robot.tool(q)
        return to_plane(position + rotation[:, 2] * depth)

    for depth, colour, text, where, xy in (
        (EDGE, PATH, "gripped edge", 9, (14, 44)),
        (EDGE + WIDTH, TOP, "far edge", 4, (64, 14)),
    ):
        path = np.array([point(q, depth) for q in r["wrist"]])
        ax.plot(*path.T, color=colour, lw=1.6, ls="--", zorder=8)
        radius = np.linalg.norm(path[0] - w1)
        ax.plot(*path[0], "o", color=colour, ms=6, zorder=9)
        ax.plot(*path[-1], "o", color=colour, ms=6, zorder=9)
        ax.annotate(
            f"{text}'s path:\n{radius:.0f} cm from wrist 1",
            xy=path[where],
            xytext=xy,
            fontsize=9.5,
            color=colour,
            arrowprops=dict(arrowstyle="-", color=colour, lw=0.8),
        )
    ax.add_patch(Circle(w1, 1.2, fc=PATH, zorder=10))
    start, end = point(r["wrist"][0], EDGE), point(r["wrist"][-1], EDGE)
    ax.text(
        w1[0] - 22,
        w1[1] + 8,
        "wrist 1: the only\njoint that turns",
        fontsize=10,
        color=PATH,
        fontweight="bold",
    )
    ax.annotate(
        f"edge starts {start[1]:.0f} cm up",
        xy=start,
        xytext=(start[0] - 30, start[1] - 12),
        fontsize=9.5,
        color=INK2,
        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8),
    )
    ax.annotate(
        f"edge ends {end[1]:.0f} cm up,\n{end[0] - start[0]:.0f} cm further out",
        xy=end,
        xytext=(end[0] - 4, end[1] + 9),
        fontsize=9.5,
        color=INK2,
        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8),
    )
    ax.text(
        -18,
        80,
        "Faded: the top at 0°, 30° and 60°. Solid: flat, at 90°.\n"
        "The board turns about wrist 1, not about its own edge.",
        fontsize=10,
        color=INK2,
    )
    save(fig, "wrist_turn.png")


# ------------------------------------------------------------ 5. the wrist turn's timing


def wrist_timing(r: dict):
    angle = abs(r["turn"])
    duration = half_cosine_time(angle)
    t = np.linspace(0, duration, 400)
    phase = math.pi * t / duration
    theta = angle * (1 - np.cos(phase)) / 2
    omega = angle * math.pi * np.sin(phase) / (2 * duration)
    alpha = angle * math.pi**2 * np.cos(phase) / (2 * duration**2)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    rows = [
        (np.degrees(theta), "angle turned, degrees", None, "How far"),
        (np.degrees(omega), "speed, degrees a second", math.degrees(SPEED_LIMIT), "How fast"),
        (
            np.degrees(alpha),
            "acceleration, degrees a second²",
            math.degrees(ACCELERATION_LIMIT),
            "Speeding up, slowing down",
        ),
    ]
    for ax, (values, label, limit, name) in zip(axes, rows, strict=True):
        ax.plot(t, values, color=WRIST_COLOUR, lw=2.4)
        style(ax, "time, seconds", label)
        title(ax, name)
        if limit is not None:
            for sign in (1,) if name == "How fast" else (1, -1):
                ax.axhline(sign * limit, color=INK2, lw=1, ls="--")
            ax.text(
                duration * 0.5,
                limit * 1.04,
                f"limit: {limit:.1f}",
                ha="center",
                fontsize=9,
                color=INK2,
                va="bottom",
            )
    axes[0].axhline(90, color=INK2, lw=0.8, ls=":")
    axes[0].text(0.2, 84, f"90° in {duration:.2f} s", fontsize=10, color=INK)
    axes[1].set_ylim(0, 22)
    axes[1].text(
        duration / 2,
        8,
        "touches the limit\nat the middle:\nthis sets the time",
        ha="center",
        fontsize=9.5,
        color=INK,
    )
    axes[2].set_ylim(-26, 26)
    axes[2].text(duration / 2, 12, "well inside\nthe limit", ha="center", fontsize=9.5, color=INK)
    fig.suptitle(
        "Half a cosine wave: it starts and stops at rest, and its speed never jumps "
        "(limits: a tenth of the arm's)",
        x=0.01,
        ha="left",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.tight_layout()
    save(fig, "wrist_turn_timing.png")


# ------------------------------------------------------------ 6. wrist 1's levers


def levers(r: dict):
    fig, axes = plt.subplots(1, 4, figsize=(17, 5.6), gridspec_kw={"width_ratios": [1, 1, 1, 1.3]})
    colours = {
        "wrist 1 link": "#8a9098",
        "wrist 2 link": "#4f6d8f",
        "wrist 3 link": "#77766f",
        "gripper body": "#3d3d3a",
        "fingers": "#b4b3ab",
        "camera": "#1baf7a",
        "table top": TOP,
    }
    to_plane = plane(r["axis"])
    a_sum = G * sum(m * u for _, m, u, _ in wrist_1_levers(r, r["wrist"][0]))
    b_sum = G * sum(m * u for _, m, u, _ in wrist_1_levers(r, r["wrist"][-1]))
    peak_angle = math.degrees(math.atan2(abs(b_sum), abs(a_sum)))
    for ax, deg in zip(axes[:3], (0, peak_angle, 90), strict=True):
        q = r["start"] + np.eye(6)[3] * r["turn"] * deg / 90
        w1 = to_plane(r["robot"].frame(q, "wrist_1_joint"))
        ax.set_xlim(w1[0] - 6, w1[0] + 42)
        ax.set_ylim(w1[1] - 42, w1[1] + 17)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.axvline(w1[0], color=INK2, lw=1, ls=":")
        draw_arm(ax, r, q, arm=False, alpha=0.3, board_alpha=0.3)
        ax.add_patch(Circle(w1, 1.3, fc=PATH, zorder=10))
        total = 0.0
        for label, m, u, z in wrist_1_levers(r, q):
            point = w1 + np.array([u, z]) * 100
            ax.add_patch(
                Circle(point, 0.8 + 1.4 * math.sqrt(m), fc=colours[label], ec="white", lw=1, zorder=11)
            )
            if abs(u) > 0.004:
                ax.plot([w1[0], point[0]], [point[1], point[1]], color=colours[label], lw=1.3, zorder=10)
            total += G * m * u
        name = "hanging" if deg == 0 else "flat" if deg == 90 else "the worst angle"
        title(ax, f"{name}, {deg:.0f}°: {abs(total):.2f} N·m")
    handles = [
        plt.Line2D([], [], marker="o", ls="", color=c, ms=9, label=label) for label, c in colours.items()
    ]
    fig.legend(
        handles=handles, loc="lower left", ncol=7, fontsize=10, frameon=False, bbox_to_anchor=(0.01, 0.0)
    )

    ax = axes[3]
    theta = np.linspace(0, 90, 200)
    curve = np.abs(a_sum * np.cos(np.radians(theta)) + b_sum * np.sin(np.radians(theta)))
    ax.plot(theta, curve, color=PATH, lw=2.4, label="weight × lever, by hand")
    pyb = [abs(r["robot"].holding(q)[3]) for q in r["wrist"]]
    ax.plot(np.degrees(ANGLES), pyb, "o", color=PATH, ms=5, mfc=BG, label="PyBullet, every 5°")
    ax.plot(
        [90],
        [GAZEBO["wrist"]["holding"][3]],
        "s",
        color=WRIST_COLOUR,
        ms=9,
        label="Gazebo, held flat (both turns)",
    )
    ax.axhline(GAZEBO["wrist"]["peak"][3], color=WRIST_COLOUR, lw=1, ls="--")
    ax.axhline(GAZEBO["whole"]["peak"][3], color=WHOLE_COLOUR, lw=1, ls="--")
    ax.text(
        2,
        GAZEBO["whole"]["peak"][3] + 0.04,
        "Gazebo's peaks: 4.07 (wrist), 4.17 (whole arm)",
        fontsize=8.5,
        color=INK2,
    )
    style(ax, "board angle: 0° hanging, 90° flat", "wrist 1 holding torque, N·m")
    ax.set_ylim(2.4, 4.6)
    ax.set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax.legend(frameon=False, fontsize=8.5, loc="lower center")
    title(ax, "τ = g·(A·cos θ + B·sin θ)")
    fig.suptitle(
        "Wrist 1's torque: each weight times its sideways distance from wrist 1 (dotted line), added up",
        x=0.01,
        ha="left",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save(fig, "wrist1_levers.png")


# ------------------------------------------------------------ 7. the whole-arm poses


def whole_arm_poses(r: dict):
    fig, ax = plt.subplots(figsize=(10, 7.4))
    to_plane = plane(r["axis"])
    edge = to_plane(SPOT)
    ax.set_xlim(edge[0] - 24, edge[0] + 24)
    ax.set_ylim(edge[1] - 24, edge[1] + 20)
    ax.set_aspect("equal")
    style(ax, "out from the arm's base, cm", "height above the floor, cm")
    title(ax, "The whole-arm turn: 18 tool poses, each the first one turned about the edge", 12.5)
    tools = []
    for i, q in enumerate(r["whole"]):
        position, _ = r["robot"].tool(q)
        tools.append(to_plane(position))
        if i in (0, 9, 18):
            draw_arm(ax, r, q, arm=False, wrist=False, alpha=(0.25, 0.45, 1.0)[i // 9], top=False)
        if i % 3 == 0:
            draw_arm(
                ax, r, q, arm=False, wrist=False, alpha=0.0, board_alpha=0.15 + 0.85 * (i / 18) ** 2, z=2
            )
    tools = np.array(tools)
    ax.plot(*tools.T, "o", color=PATH, ms=5, zorder=12)
    ax.add_patch(Arc(edge, 24, 24, theta1=90, theta2=180, color=PATH, lw=1.2, ls="--", zorder=11))
    ax.add_patch(Circle(edge, 0.8, fc=BAD, zorder=13))
    ax.annotate(
        "gripped edge: the pivot.\nStays here, to 0.1 mm.",
        xy=edge,
        xytext=(edge[0] + 7, edge[1] + 8),
        fontsize=10,
        color=BAD,
        arrowprops=dict(arrowstyle="-", color=BAD, lw=0.8),
    )
    for k in (0, 18):
        ax.annotate(
            "", xy=tools[k], xytext=edge, arrowprops=dict(arrowstyle="-|>", color=PATH, lw=1.3), zorder=12
        )
    ax.text(
        tools[0][0] + 1.5,
        tools[0][1] + 1.5,
        "tool0 at the start:\n12 cm above the edge",
        fontsize=9.5,
        color=PATH,
    )
    ax.text(
        tools[-1][0] - 1.5,
        tools[-1][1] - 9,
        "tool0 at the end:\n12 cm back towards\nthe base",
        fontsize=9.5,
        color=PATH,
        ha="right",
    )
    ax.text(
        edge[0] - 23,
        edge[1] - 22.5,
        "dots: where tool0 must be at each 5° step.\nThey lie on a circle of radius 12 cm round the edge.",
        fontsize=9.5,
        color=INK2,
    )
    save(fig, "whole_arm_poses.png")


# ------------------------------------------------------------ 8. the whole-arm turn, side view


def whole_arm_turn(r: dict):
    fig, ax = plt.subplots(figsize=(11, 7.4))
    side_axes(ax, -20, 90, -6, 88)
    title(ax, "The whole-arm turn, to scale: shoulder, elbow and wrist 1 move together", 13)
    for i, a in enumerate((0, 45, 90)):
        draw_arm(ax, r, r["whole"][a // 5], alpha=(0.3, 0.5, 1.0)[i], board_alpha=(0.3, 0.55, 1.0)[i])
    to_plane = plane(r["axis"])
    path = np.array([to_plane(r["robot"].frame(q, "wrist_1_joint")) for q in r["whole"]])
    ax.plot(*path.T, color=PATH, lw=1.6, ls="--", zorder=9)
    ax.annotate(
        f"wrist 1 drops {path[0][1] - path[-1][1]:.0f} cm and comes {path[0][0] - path[-1][0]:.0f} cm in",
        xy=path[12],
        xytext=(22, 12),
        fontsize=9.5,
        color=PATH,
        arrowprops=dict(arrowstyle="-", color=PATH, lw=0.8),
    )
    edge = to_plane(SPOT)
    ax.add_patch(Circle(edge, 1.0, fc=BAD, zorder=12))
    ax.annotate(
        "gripped edge: stays at 40 cm up",
        xy=edge,
        xytext=(edge[0] - 6, edge[1] - 20),
        fontsize=9.5,
        color=BAD,
        arrowprops=dict(arrowstyle="-", color=BAD, lw=0.8),
    )
    change = np.degrees(r["whole"][-1] - r["start"])
    ax.text(
        -18,
        80,
        "Faded: 0° and 45°. Solid: flat, at 90°.\n"
        f"Over the turn: shoulder {change[1]:+.1f}° (out 16.5° and back), elbow {change[2]:+.1f}°, "
        f"wrist 1 {change[3]:+.1f}°.",
        fontsize=10,
        color=INK2,
    )
    save(fig, "whole_arm_turn.png")


# ------------------------------------------------------------ 9. joint angles through the turn


def whole_arm_joints(r: dict):
    fig, ax = plt.subplots(figsize=(10, 5.6))
    deg = np.degrees(ANGLES)
    change = np.degrees(np.array(r["whole"]) - r["start"])
    for j, name, colour in (
        (1, "shoulder", "#eda100"),
        (2, "elbow", "#1baf7a"),
        (3, "wrist 1", WHOLE_COLOUR),
    ):
        ax.plot(deg, change[:, j], color=colour, lw=2.4, label=f"{name}, whole-arm turn")
        ax.text(91.5, change[-1, j], f"{name} {change[-1, j]:+.1f}°", fontsize=10, color=colour, va="center")
    ax.plot(
        deg,
        change[:, 1] + change[:, 2] + change[:, 3],
        color=INK,
        lw=1.2,
        ls=":",
        label="shoulder + elbow + wrist 1",
    )
    ax.plot(deg, -deg, color=WRIST_COLOUR, lw=2, ls="--", label="wrist 1, wrist turn (all the others: 0)")
    ax.text(91.5, -90, "sum −90.0°\n= wrist turn's\nwrist 1", fontsize=9.5, color=INK, va="center")
    style(ax, "board angle: 0° hanging, 90° flat", "how far the joint has turned, degrees")
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 15, 30, 45, 60, 75, 90])
    ax.legend(frameon=False, fontsize=9.5, loc="lower left")
    title(ax, "Joint angles through the turn: the three always add up to the board's own turn", 12.5)
    save(fig, "whole_arm_joints.png")


# ------------------------------------------------------------ 10. torque, both turns


def torque_both(r: dict):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    deg = np.degrees(ANGLES)
    for ax, j, name, limit in zip(
        axes, (3, 2, 1), ("Wrist 1", "Elbow", "Shoulder"), (28, 150, 150), strict=True
    ):
        for key, colour, label, width, dash in (
            ("wrist", WRIST_COLOUR, "wrist turn", 5, "-"),
            ("whole", WHOLE_COLOUR, "whole-arm turn", 2, "--"),
        ):
            values = np.array([abs(r["robot"].holding(q)[j]) for q in r[key]])
            ax.plot(deg, values, color=colour, lw=width, ls=dash, label=f"{label}, worked out")
            ax.plot(
                [90],
                [GAZEBO[key]["holding"][j]],
                "s",
                color=colour,
                ms=9,
                mec=BG,
                label=f"{label}, Gazebo holding flat",
            )
            ax.plot(
                [deg[int(np.argmax(values))]],
                [GAZEBO[key]["peak"][j]],
                "^",
                color=colour,
                ms=9,
                mec=BG,
                label=f"{label}, Gazebo peak",
            )
        style(ax, "board angle: 0° hanging, 90° flat", "torque, N·m" if j == 3 else None)
        ax.set_xticks([0, 30, 60, 90])
        title(ax, f"{name} (limit {limit} N·m)")
    axes[0].set_ylim(2.4, 4.6)
    axes[0].text(45, 2.55, "the two lines lie on top of each other", ha="center", fontsize=9.5, color=INK)
    axes[2].text(
        45,
        22.5,
        "the whole arm\nlifts its own\nweight in closer",
        ha="center",
        fontsize=9.5,
        color=WHOLE_COLOUR,
    )
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower left", ncol=3, fontsize=9.5, frameon=False, bbox_to_anchor=(0.01, 0.0)
    )
    fig.suptitle(
        "Holding torque through the turn. Lines: worked out from the robot model. "
        "Marks: what Gazebo measured.",
        x=0.01,
        ha="left",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    save(fig, "torque_both.png")


# ------------------------------------------------------------ 11. the grip, both turns


def grip_both():
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5))
    theta = np.linspace(0, 90, 300)
    rad = np.radians(theta)
    lever = CENTRE - PADS

    along = MASS * G * np.cos(rad)
    twist = MASS * G * lever * np.sin(rad)
    amber = "#c98a00"
    a.plot(theta, along, color=amber, lw=2.4)
    style(a, "board angle: 0° hanging, 90° flat", None)
    a.set_ylabel("pull along the fingers, N\n(friction has to hold it)", color=amber)
    a.set_xticks([0, 30, 60, 90])
    a.set_ylim(0, 3.3)
    a.text(3, along[0] - 0.22, f"{along[0]:.1f} N hanging", color=amber, fontsize=10)
    twin = a.twinx()
    twin.plot(theta, twist, color=PATH, lw=2.4)
    twin.set_ylim(0, 0.33)
    twin.set_ylabel("twist about the pads, N·m\n(the pad rows have to resist it)", color=PATH)
    twin.tick_params(colors=PATH, labelsize=9)
    for side in ("top", "left", "bottom"):
        twin.spines[side].set_visible(False)
    twin.text(88, twist[-1] + 0.012, f"{twist[-1]:.2f} N·m flat", color=PATH, fontsize=10, ha="right")
    title(a, f"Seed 1's top, {MASS:.2f} kg: the same curves for both turns")

    tests = [(1.53, None, None, "held flat"), (2.29, 82, 78, None), (3.82, 48, 46, None)]
    for mass, wrist_at, whole_at, text in tests:
        curve = mass * G * lever * np.sin(rad)
        b.plot(theta, curve, color=INK2, lw=1.4)
        b.text(91, curve[-1], f"{mass:.2f} kg", fontsize=9.5, color=INK2, va="center")
        if wrist_at is None:
            b.plot([90], [curve[-1]], "o", color=GOOD, ms=9, zorder=5)
            b.text(88, curve[-1] - 0.12, text, fontsize=9.5, color=GOOD, ha="right")
            continue
        for at, colour, marker in ((wrist_at, WRIST_COLOUR, "X"), (whole_at, WHOLE_COLOUR, "P")):
            b.plot(
                [at],
                [mass * G * lever * math.sin(math.radians(at))],
                marker,
                color=colour,
                ms=10,
                mec=BG,
                zorder=5,
            )
    b.plot([], [], "X", color=WRIST_COLOUR, ms=10, ls="", label="the tip pads lost it: wrist turn")
    b.plot([], [], "P", color=WHOLE_COLOUR, ms=10, ls="", label="the tip pads lost it: whole-arm turn")
    b.plot(theta, MASS * G * lever * np.sin(rad), color=TOP, lw=2)
    b.text(91, twist[-1], f"{MASS:.2f} kg", fontsize=9.5, color=TOP, va="center")
    style(b, "board angle: 0° hanging, 90° flat", "twist on the grip, N·m")
    b.set_xlim(0, 100)
    b.set_xticks([0, 30, 60, 90])
    b.legend(frameon=False, fontsize=9, loc="upper left")
    title(b, "Heavier tops (Gazebo): both turns lose it at about the same angle")
    fig.tight_layout(w_pad=4)
    save(fig, "grip_both.png")


# ------------------------------------------------------------ 12. the space each turn needs


def space_both(r: dict):
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.8), sharey=True)
    robot = r["robot"]
    to_plane = plane(r["axis"])
    for ax, key, colour, name in (
        (axes[0], "wrist", WRIST_COLOUR, "Wrist turn"),
        (axes[1], "whole", WHOLE_COLOUR, "Whole-arm turn"),
    ):
        side_axes(ax, -10, 95, -6, 88)
        fine = np.linspace(0, 1, 91)
        if key == "wrist":
            poses = [r["start"] + np.eye(6)[3] * r["turn"] * s for s in fine]
        else:
            path = np.array(r["whole"])
            poses = [
                np.array([np.interp(s * 90, np.degrees(ANGLES), path[:, j]) for j in range(6)]) for s in fine
            ]
        for q in poses:
            position, rotation = robot.tool(q)
            a = to_plane(position + rotation[:, 2] * EDGE)
            b = to_plane(position + rotation[:, 2] * (EDGE + WIDTH))
            ax.add_patch(
                Polygon(rect_between(a, b, THICKNESS * 50), fc=colour, ec="none", alpha=1.0, zorder=1)
            )
            ax.add_patch(
                Polygon(
                    rect_between(a, b, THICKNESS * 50 - 0.05),
                    fc="#f7d9cc" if key == "wrist" else "#d4e4f7",
                    ec="none",
                    zorder=1.1,
                )
            )
        draw_arm(ax, r, poses[0], alpha=0.3, board_alpha=0.4)
        draw_arm(ax, r, poses[-1], alpha=1.0)
        lo = np.array([to_plane(robot.tool(q)[0] + robot.tool(q)[1][:, 2] * (EDGE + WIDTH)) for q in poses])
        ax.plot(*lo.T, color=colour, lw=1.4, ls="--", zorder=8)
        title(ax, name, 13)
    w1 = to_plane(robot.frame(r["start"], "wrist_1_joint"))
    axes[0].text(
        -8,
        80,
        "The board sweeps round wrist 1: out to 40 cm from it.\nIt ends 32 cm higher and 12 cm further out.",
        fontsize=10,
        color=INK2,
    )
    axes[1].text(
        -8,
        80,
        "The board sweeps a quarter circle 16.5 cm round its\nown edge, and ends where it began. "
        "But the wrist\nand forearm come down 32 cm to do it.",
        fontsize=10,
        color=INK2,
    )
    axes[0].add_patch(Circle(w1, 1.2, fc=PATH, zorder=10))
    axes[1].add_patch(Circle(to_plane(SPOT), 1.0, fc=BAD, zorder=12))
    fig.suptitle(
        "The space each turn needs. Tinted: everywhere the board passes through. Faded: the start.",
        x=0.01,
        ha="left",
        fontsize=12.5,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "space_both.png")


# ------------------------------------------------------------ report


def report(r: dict) -> None:
    robot = r["robot"]
    print(f"top: {LENGTH * 100:.1f} x {WIDTH * 100:.1f} x {THICKNESS * 100:.1f} cm, {MASS:.3f} kg")
    print(
        f"wrist 1's axis at the turning spot: {np.round(r['axis'], 4).tolist()}, "
        f"{math.degrees(math.atan2(-r['axis'][0], r['axis'][1])):.2f} degrees from the y axis"
    )
    print(
        "start joints (deg):", np.round(np.degrees(r["start"]), 2).tolist(), " turn:", math.degrees(r["turn"])
    )
    print("whole-arm change at flat (deg):", np.round(np.degrees(r["whole"][-1] - r["start"]), 2).tolist())
    shoulder = np.degrees(np.array(r["whole"])[:, 1] - r["start"][1])
    print(
        f"  shoulder travel {shoulder.max() - shoulder.min():.1f}, lowest {shoulder.min():.1f} at "
        f"{np.degrees(ANGLES[int(np.argmin(shoulder))]):.0f} deg"
    )
    for key in ("wrist", "whole"):
        held = np.array([np.abs(robot.holding(q)) for q in r[key]])
        print(f"{key}: holding at 0/flat, and peak (N·m), joints base..wrist 3")
        print("   hanging", np.round(held[0], 2).tolist())
        print("   flat   ", np.round(held[-1], 2).tolist())
        print(
            "   peak   ",
            np.round(held.max(axis=0), 2).tolist(),
            "at",
            np.degrees(ANGLES[held.argmax(axis=0)]).tolist(),
        )
        for q in (r[key][0], r[key][-1]):
            position, rotation = robot.tool(q)
            print(
                "   tool0",
                np.round(position, 3).tolist(),
                "edge",
                np.round(position + rotation[:, 2] * EDGE, 3).tolist(),
                "wrist 1",
                np.round(robot.frame(q, "wrist_1_joint"), 3).tolist(),
            )
    print("wrist 1's loads, lever = sideways distance from its axis (m):")
    for name, q in (("hanging", r["wrist"][0]), ("flat", r["wrist"][-1])):
        rows = wrist_1_levers(r, q)
        print(f"  {name}: " + ", ".join(f"{label} {m:.3f} kg @ {u:+.4f}" for label, m, u, _ in rows))
        print(
            f"     sum m*u = {sum(m * u for _, m, u, _ in rows):+.5f} kg m "
            f"-> {G * sum(m * u for _, m, u, _ in rows):+.3f} N·m"
        )
    print(
        f"half-cosine time for 90 degrees at a tenth of full speed: {half_cosine_time(math.pi / 2):.3f} s "
        f"(speed alone {math.pi * (math.pi / 2) / (2 * SPEED_LIMIT):.3f}, acceleration alone "
        f"{math.sqrt(math.pi**2 * (math.pi / 2) / (2 * ACCELERATION_LIMIT)):.3f})"
    )
    for (key, scale), (duration, moving) in moving_part(r).items():
        print(
            f"moving part, {key}, {scale:.0%} speed, {duration:.2f} s: "
            + np.round(moving, 3).tolist().__str__()
        )


def main() -> None:
    p.connect(p.DIRECT)
    r = work_out()
    check(r)
    print(
        "checks passed: edge stays put, three turns add up, board ends flat, weight × lever matches PyBullet"
    )
    report(r)
    overview()
    arm_joints(r)
    wrist_axis(r)
    wrist_turn(r)
    wrist_timing(r)
    levers(r)
    whole_arm_poses(r)
    whole_arm_turn(r)
    whole_arm_joints(r)
    torque_both(r)
    grip_both()
    space_both(r)


if __name__ == "__main__":
    main()
