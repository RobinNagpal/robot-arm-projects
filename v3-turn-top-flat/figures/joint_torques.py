"""Works out the torque on each of the UR5e's six joints while the table top
is turned 90 degrees, from hanging to flat, for each way of doing the turn, and
draws the charts in one-joint-or-many.md. This is the calculation behind part 1
of v3.

Run from v3-turn-top-flat/figures/, with v2's Python, which has PyBullet:

    ../../v2-assemble-table/.pixi/envs/default/bin/python joint_torques.py

The robot is ur5e_v2_gripper.urdf: v2's UR5e and gripper with the meshes
stripped out, because only masses, inertias and joint positions affect a
torque. PyBullet does the dynamics. This file only sets up the three swings and
reads the answers off.

Before any number is printed, three checks have to pass: the robot weighs what
Universal Robots say it weighs, the holding torques agree with a second way of
working them out, and the work done by the joints matches the energy the arm
and board actually gain. If any fails, the script stops rather than print
numbers nobody should trust.
"""

from __future__ import annotations

import math
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pybullet as p

HERE = Path(__file__).parent
ROBOT = HERE / "ur5e_v2_gripper.urdf"

G = 9.81
# PyBullet keeps poses in single precision, good to about one part in ten
# million. Nudges used to measure how the board moves must be well above that.
NUDGE = 1e-4
ARM_JOINTS = ("shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3")
NAMES = ("base", "shoulder", "elbow", "wrist 1", "wrist 2", "wrist 3")
# The most each joint can push, from ur_description/config/ur5e/joint_limits.yaml.
LIMIT = np.array([150.0, 150.0, 150.0, 28.0, 28.0, 28.0])
MAX_SPEED = math.radians(180.0)

# v2's largest table top: 30 cm along the gripped edge, 20 cm out from it, 2 cm
# thick, at 400 kg/m^3. The fingers close on its thickness, 2.7 cm in from the
# edge, so its centre sits 7.3 cm past the middle of the pads, which are 11 cm
# from the flange. See pick-up-and-place.md.
BOARD_SIZE = np.array([0.30, 0.02, 0.20])  # along the tool's x, y, z
PAD_CENTRE = 0.110
BOARD_CENTRE = PAD_CENTRE + 0.073
V2_BOARD_MASS = 0.48
# Each finger travels from 0 (shut) outwards, so closed on a 2 cm board each
# sits 1 cm open.
FINGERS_ON_BOARD = BOARD_SIZE[1] / 2

# v2's "ready" pose: the tool points straight down in front of the arm, which
# is how the board hangs once it has been lifted straight up out of its
# holders. In it, the board's gripped edge lies along wrist 1's axis, which is
# what lets wrist 1 alone lay it flat.
START = np.radians([0.0, -90.0, 90.0, -90.0, -90.0, 0.0])

# The same board, in the same place, reached with the wrist flipped: wrist 2 on
# the other side of wrist 1. A UR arm can reach almost any pose in several
# postures like this. Filled in by flipped_start(), because the shoulder and
# elbow have to be worked out afresh to keep the board where it was.
POSTURES = ("normal wrist", "flipped wrist")
_FLIPPED: np.ndarray | None = None


# ------------------------------------------------------------------ the robot


def make_urdf(expanded: Path) -> None:
    """Rebuild ur5e_v2_gripper.urdf from v2's expanded robot description."""
    root = ET.parse(expanded).getroot()
    for link in root.iter("link"):
        for tag in ("visual", "collision"):
            for element in link.findall(tag):
                link.remove(element)
        # Frames with no mass of their own would be given 1 kg each by PyBullet.
        if link.find("inertial") is None:
            inertial = ET.SubElement(link, "inertial")
            ET.SubElement(inertial, "origin", xyz="0 0 0", rpy="0 0 0")
            ET.SubElement(inertial, "mass", value="1e-9")
            ET.SubElement(
                inertial, "inertia", ixx="1e-12", ixy="0", ixz="0", iyy="1e-12", iyz="0", izz="1e-12"
            )
    for tag in ("gazebo", "ros2_control", "transmission"):
        for element in root.findall(tag):
            root.remove(element)
    header = (
        "<!-- v2's UR5e, gripper and wrist camera, with the meshes, sensors and\n"
        "     plugins removed. Written by make_urdf() in joint_torques.py. -->\n"
    )
    ROBOT.write_text('<?xml version="1.0"?>\n' + header + ET.tostring(root, encoding="unicode") + "\n")


def load(board_mass: float) -> tuple[int, list[int], int]:
    """The robot with a board of this mass held in the gripper."""
    root = ET.parse(ROBOT).getroot()
    lx, ly, lz = BOARD_SIZE
    m = max(board_mass, 1e-9)
    board = ET.SubElement(root, "link", name="board")
    inertial = ET.SubElement(board, "inertial")
    ET.SubElement(inertial, "origin", xyz="0 0 0", rpy="0 0 0")
    ET.SubElement(inertial, "mass", value=f"{m}")
    ET.SubElement(
        inertial,
        "inertia",
        ixx=f"{m * (ly**2 + lz**2) / 12}",
        iyy=f"{m * (lx**2 + lz**2) / 12}",
        izz=f"{m * (lx**2 + ly**2) / 12}",
        ixy="0",
        ixz="0",
        iyz="0",
    )
    joint = ET.SubElement(root, "joint", name="board_grip", type="fixed")
    ET.SubElement(joint, "parent", link="tool0")
    ET.SubElement(joint, "child", link="board")
    ET.SubElement(joint, "origin", xyz=f"0 0 {BOARD_CENTRE}", rpy="0 0 0")

    path = Path(tempfile.mkdtemp()) / "robot_with_board.urdf"
    path.write_text(ET.tostring(root, encoding="unicode"))

    p.resetSimulation()
    p.setGravity(0, 0, -G)
    body = p.loadURDF(str(path), useFixedBase=True, flags=p.URDF_USE_INERTIA_FROM_FILE)

    names = {p.getJointInfo(body, i)[1].decode(): i for i in range(p.getNumJoints(body))}
    arm = [names[f"{n}_joint"] for n in ARM_JOINTS]
    board_link = names["board_grip"]
    return body, arm, board_link


def movable(body: int) -> list[int]:
    return [i for i in range(p.getNumJoints(body)) if p.getJointInfo(body, i)[2] != p.JOINT_FIXED]


def full(body: int, arm: list[int], q6: np.ndarray, fingers: float = 0.0) -> list[float]:
    """Arm values padded out to every movable joint, including the two fingers."""
    order = movable(body)
    values = [fingers] * len(order)
    for value, joint in zip(q6, arm, strict=True):
        values[order.index(joint)] = float(value)
    return values


def arm_part(body: int, arm: list[int], values) -> np.ndarray:
    order = movable(body)
    return np.array([values[order.index(j)] for j in arm])


def place(body: int, arm: list[int], q6, dq6=None) -> None:
    for joint in movable(body):
        if joint not in arm:
            p.resetJointState(body, joint, FINGERS_ON_BOARD, 0.0)
    for i, joint in enumerate(arm):
        p.resetJointState(body, joint, float(q6[i]), 0.0 if dq6 is None else float(dq6[i]))


def board_pose(body: int, arm: list[int], board_link: int, q6) -> tuple[np.ndarray, np.ndarray]:
    """Where the board's centre is, and which way it faces, for these angles."""
    place(body, arm, q6)
    state = p.getLinkState(body, board_link, computeForwardKinematics=True)
    return np.array(state[4]), np.array(p.getMatrixFromQuaternion(state[5])).reshape(3, 3)


def torques(body: int, arm: list[int], q6, dq6, ddq6) -> np.ndarray:
    """Torque on each arm joint, for these angles, speeds and accelerations."""
    tau = p.calculateInverseDynamics(
        body, full(body, arm, q6, FINGERS_ON_BOARD), full(body, arm, dq6), full(body, arm, ddq6)
    )
    return arm_part(body, arm, tau)


# -------------------------------------------------------------- the swings


def min_jerk(n: int) -> np.ndarray:
    """0 to 1 with no sudden starts or stops: smooth speed and smooth acceleration."""
    s = np.linspace(0.0, 1.0, n)
    return 10 * s**3 - 15 * s**4 + 6 * s**5


def derivatives(q: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Speeds and accelerations from angles over time.

    A swing starts and ends at rest with no acceleration, so it can be extended
    by a few motionless samples at each end. That lets every sample, the first
    and last included, use a centred difference. Without it the end samples use
    one-sided differences, which are biased, and a biased acceleration at the
    flat end hides the very torque this file is looking for.
    """
    pad = 5
    dt = t[1] - t[0]
    padded = np.concatenate([np.repeat(q[:1], pad, axis=0), q, np.repeat(q[-1:], pad, axis=0)])
    dq = np.gradient(padded, dt, axis=0)
    ddq = np.gradient(dq, dt, axis=0)
    return dq[pad:-pad], ddq[pad:-pad]


def rotation(axis: np.ndarray, angle: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def wrist_1_axis(body, arm, board_link, q6) -> np.ndarray:
    """Wrist 1's axis in the world, found by turning it a hair and watching the board turn.

    PyBullet reports joint axes in each link's centre-of-mass frame, which is
    easy to misread. Measuring the turn needs no knowledge of frames at all.
    """
    _, rot = board_pose(body, arm, board_link, q6)
    step = np.zeros(6)
    step[3] = NUDGE
    _, rot2 = board_pose(body, arm, board_link, q6 + step)
    axis = 0.5 * sum(np.cross(rot[:, i], rot2[:, i]) for i in range(3)) / NUDGE
    return axis / np.linalg.norm(axis)


def solve(body, arm, board_link, target_pos, target_rot, pivot_offset, seed) -> np.ndarray:
    """Joint angles that put a point on the board at target_pos, facing target_rot."""
    q = seed.copy()
    for _ in range(50):
        pos, rot = board_pose(body, arm, board_link, q)
        point = pos + rot @ pivot_offset
        err_pos = target_pos - point
        err_rot = 0.5 * sum(np.cross(rot[:, i], target_rot[:, i]) for i in range(3))
        error = np.concatenate([err_pos, err_rot])
        # A ten-thousandth of a millimetre, and as much in radians: about as fine
        # as single precision allows, and far finer than anything physical.
        if np.linalg.norm(error) < 1e-7:
            return q
        jac = np.zeros((6, 6))
        for j in range(6):
            dq = np.zeros(6)
            dq[j] = NUDGE
            pos2, rot2 = board_pose(body, arm, board_link, q + dq)
            jac[:3, j] = (pos2 + rot2 @ pivot_offset - point) / NUDGE
            jac[3:, j] = 0.5 * sum(np.cross(rot[:, i], rot2[:, i]) for i in range(3)) / NUDGE
        q = q + np.linalg.lstsq(jac, error, rcond=None)[0]
    if np.linalg.norm(error) < 1e-6:
        return q
    raise RuntimeError("the arm cannot follow this swing")


def flipped_start() -> np.ndarray:
    """The flipped-wrist posture that holds the hanging board exactly where START does."""
    global _FLIPPED
    if _FLIPPED is None:
        body, arm, board_link = load(V2_BOARD_MASS)
        pos0, rot0 = board_pose(body, arm, board_link, START)
        # Wrist 1 half a turn, wrist 2 mirrored, wrist 3 half a turn: same tool
        # direction, with wrist 2 on the other side. The solver then moves the
        # shoulder and elbow to put the board back where it was.
        seed = START.copy()
        seed[3] += math.pi
        seed[4] = -seed[4]
        seed[5] += math.pi
        _FLIPPED = solve(body, arm, board_link, pos0, rot0, np.zeros(3), seed)
    return _FLIPPED


def swing(way: str, duration: float, board_mass: float, n: int = 401, posture: str = "normal wrist") -> dict:
    """One swing from hanging to flat. Returns angles, speeds and torques over time."""
    start = START if posture == "normal wrist" else flipped_start()
    body, arm, board_link = load(board_mass)
    t = np.linspace(0.0, duration, n)
    s = min_jerk(n)

    # Wrist 1's axis, and which way to turn about it so the board ends flat and
    # pointing away from the base.
    axis = wrist_1_axis(body, arm, board_link, start)
    pos0, rot0 = board_pose(body, arm, board_link, start)
    assert rot0[:, 2][2] < -0.999, "the board should start hanging straight down"
    assert abs(rot0[:, 0] @ axis) > 0.999, "the gripped edge should lie along wrist 1's axis"
    outward = np.array([pos0[0], pos0[1], 0.0]) / np.linalg.norm(pos0[:2])
    turn = math.pi / 2
    if (rotation(axis, turn) @ rot0)[:, 2] @ outward < 0:
        turn = -turn
    end = rotation(axis, turn) @ rot0
    assert abs(end[:, 2][2]) < 1e-9 and end[:, 2] @ outward > 0.9, "the board should end flat, pointing out"

    if way == "one joint":
        q = np.array([start + np.array([0, 0, 0, 1, 0, 0]) * turn * si for si in s])
    else:
        # The whole arm moves so that one point of the board stays still while
        # the board turns about it: the gripped edge, or the board's own centre.
        pivot_offset = np.array([0.0, 0.0, PAD_CENTRE - BOARD_CENTRE]) if way == "edge fixed" else np.zeros(3)
        pos0, rot0 = board_pose(body, arm, board_link, start)
        pivot = pos0 + rot0 @ pivot_offset
        q = [start.copy()]
        for si in s[1:]:
            q.append(
                solve(body, arm, board_link, pivot, rotation(axis, turn * si) @ rot0, pivot_offset, q[-1])
            )
        q = np.array(q)

    dq, ddq = derivatives(q, t)
    tau = np.array([torques(body, arm, q[i], dq[i], ddq[i]) for i in range(n)])
    hold = np.array([torques(body, arm, q[i], 0 * dq[i], 0 * ddq[i]) for i in range(n)])
    return {
        "t": t,
        "s": s,
        "turn": turn,
        "angle": np.degrees(abs(turn) * s),
        "q": q,
        "dq": dq,
        "ddq": ddq,
        "tau": tau,
        "hold": hold,
        "body": body,
        "arm": arm,
        "duration": duration,
    }


# ----------------------------------------------------------------- checks


def check_mass() -> None:
    body, _, _ = load(0.0)
    total = sum(p.getDynamicsInfo(body, i)[0] for i in range(p.getNumJoints(body)))
    # 17.7 kg of arm from ur_description, 4 kg of base, 0.95 kg of gripper and camera.
    assert abs(total - (17.7 + 4.0 + 0.95)) < 0.01, f"robot weighs {total:.3f} kg"


def check_holding(board_mass: float) -> None:
    """Holding torque two ways: PyBullet's dynamics, and the energy slope.

    The torque needed to hold a joint still is how fast the potential energy
    (every part's weight times its height) changes as that joint turns. That
    needs nothing but where each part's centre of mass is, so it is a fully
    separate route to the same number.
    """
    body, arm, _ = load(board_mass)
    q = START + np.radians([10, 15, -20, 30, 5, 40])

    def potential(q6) -> float:
        place(body, arm, q6)
        return sum(
            p.getDynamicsInfo(body, link)[0]
            * G
            * p.getLinkState(body, link, computeForwardKinematics=True)[0][2]
            for link in range(p.getNumJoints(body))
        )

    slope = np.array([(potential(q + e * NUDGE) - potential(q - e * NUDGE)) / (2 * NUDGE) for e in np.eye(6)])
    place(body, arm, q)
    tau = torques(body, arm, q, np.zeros(6), np.zeros(6))
    assert np.allclose(tau, slope, atol=1e-3), (tau, slope)


def check_energy(result: dict) -> None:
    """The joints' work must equal the energy the arm and board gain, at every moment."""
    body, arm = result["body"], result["arm"]
    energy = []
    for q, dq in zip(result["q"], result["dq"], strict=True):
        place(body, arm, q, dq)
        e = 0.0
        for link in range(p.getNumJoints(body)):
            info = p.getDynamicsInfo(body, link)
            state = p.getLinkState(body, link, computeLinkVelocity=1, computeForwardKinematics=1)
            rot = np.array(p.getMatrixFromQuaternion(state[1])).reshape(3, 3)
            inertia = rot @ np.diag(info[2]) @ rot.T
            v, w = np.array(state[6]), np.array(state[7])
            e += 0.5 * info[0] * v @ v + 0.5 * w @ inertia @ w + info[0] * G * state[0][2]
        energy.append(e)
    power = np.einsum("ij,ij->i", result["tau"], result["dq"])
    gained = np.gradient(np.array(energy), result["t"])
    scale = max(np.abs(power).max(), 1e-9)
    assert np.abs(power - gained)[5:-5].max() < 0.02 * scale, "work and energy disagree"


def check_derivatives() -> None:
    """For the one-joint swing the speeds are known exactly; the numerical ones must match."""
    r = swing("one joint", 1.0, V2_BOARD_MASS)
    tau_ = r["t"] / r["duration"]
    exact_dq = r["turn"] * (30 * tau_**2 - 60 * tau_**3 + 30 * tau_**4) / r["duration"]
    exact_ddq = r["turn"] * (60 * tau_ - 180 * tau_**2 + 120 * tau_**3) / r["duration"] ** 2
    assert np.abs(r["dq"][:, 3] - exact_dq).max() < 1e-3 * np.abs(exact_dq).max()
    assert np.abs(r["ddq"][:, 3] - exact_ddq).max() < 1e-2 * np.abs(exact_ddq).max()


# ----------------------------------------------------------------- output


WAYS = ("one joint", "edge fixed", "centre fixed")
SLOW = 5.0  # v2 moves at a tenth of full speed, which makes this swing about 5 s


def fastest(way: str) -> float:
    """The shortest swing in which no joint goes faster than 180 degrees a second.

    The path the joints follow does not depend on how long the swing takes, so
    every joint speed scales with one over the duration, and one trial run is
    enough to find it.
    """
    trial = swing(way, 1.0, V2_BOARD_MASS)
    return math.ceil(100 * np.abs(trial["dq"]).max() / MAX_SPEED) / 100


def paces(way: str) -> tuple[tuple[float, str], tuple[float, str]]:
    quick = fastest(way)
    return (SLOW, "v2's pace, 5 s"), (quick, f"flat out, {quick:.2f} s")


def peak(values: np.ndarray) -> np.ndarray:
    return np.abs(values).max(axis=0)


def table(board_mass: float) -> dict:
    print(f"\nBoard {board_mass:.2f} kg. Peak torque on each joint, N·m (and % of its limit).")
    print(f"{'':32}" + "".join(f"{n:>13}" for n in NAMES) + "   fastest joint")
    results = {}
    for pace in (0, 1):
        for way in WAYS:
            duration, label = paces(way)[pace]
            r = swing(way, duration, board_mass)
            results[(way, pace)] = r
            row = peak(r["tau"])
            cells = "".join(f"{v:7.2f} ({100 * v / lim:3.0f}%)" for v, lim in zip(row, LIMIT, strict=True))
            print(f"{way + ', ' + label:32}{cells}   {np.degrees(np.abs(r['dq']).max()):4.0f} deg/s")
    return results


def board_share(board_mass: float) -> None:
    """How much of each joint's peak torque is the board, and how much is the arm itself."""
    print(f"\nThe most the {board_mass:.2f} kg board adds to each joint at any moment, N·m:")
    print(f"{'':32}" + "".join(f"{n:>9}" for n in NAMES))
    for pace in (0, 1):
        for way in WAYS:
            duration, label = paces(way)[pace]
            with_board = swing(way, duration, board_mass)["tau"]
            without = swing(way, duration, 0.0)["tau"]
            print(f"{way + ', ' + label:32}" + "".join(f"{v:9.2f}" for v in peak(with_board - without)))


def wrist_parts(board_mass: float) -> None:
    print(f"\nWrist 1 with the {board_mass:.2f} kg board: holding part, moving part, total, N·m")
    for pace in (0, 1):
        for way in WAYS:
            duration, label = paces(way)[pace]
            r = swing(way, duration, board_mass)
            moving = r["tau"][:, 3] - r["hold"][:, 3]
            print(
                f"  {way + ', ' + label:30} hold {peak(r['hold'])[3]:5.2f}   "
                f"move {np.abs(moving).max():5.2f}   total {peak(r['tau'])[3]:5.2f}"
            )


def heaviest(way: str, duration: float, posture: str = "normal wrist") -> tuple[float, str]:
    """The heaviest board this swing can take before some joint hits its limit."""
    low, high = 0.0, 30.0
    for _ in range(15):
        mid = (low + high) / 2
        used = peak(swing(way, duration, mid, n=201, posture=posture)["tau"]) / LIMIT
        low, high = (mid, high) if used.max() < 1.0 else (low, mid)
    used = peak(swing(way, duration, low, n=201, posture=posture)["tau"]) / LIMIT
    return low, NAMES[int(np.argmax(used))]


def posture_table(board_mass: float) -> None:
    """The same three swings, started from each of the two postures, at v2's pace."""
    print(
        f"\nPosture: peak torque on each joint at v2's pace, board {board_mass:.2f} kg, N·m (and % of limit)"
    )
    print(f"{'':30}" + "".join(f"{n:>13}" for n in NAMES) + "   heaviest board")
    for posture in POSTURES:
        for way in WAYS:
            row = peak(swing(way, SLOW, board_mass, posture=posture)["tau"])
            cells = "".join(f"{v:7.2f} ({100 * v / lim:3.0f}%)" for v, lim in zip(row, LIMIT, strict=True))
            mass, joint = heaviest(way, SLOW, posture)
            print(f"{way + ', ' + posture:30}{cells}   {mass:4.1f} kg ({joint})")


def hold_curve() -> None:
    """Wrist 1's holding torque through the swing, in each posture."""
    print("\nWrist 1 holding torque through the swing, N·m (same for every way of swinging):")
    curves = {posture: swing("one joint", SLOW, V2_BOARD_MASS, posture=posture) for posture in POSTURES}
    print("  angle  " + "".join(f"{posture:>16}" for posture in POSTURES))
    for angle in (0, 15, 30, 45, 60, 75, 90):
        row = []
        for posture in POSTURES:
            r = curves[posture]
            row.append(abs(r["hold"][int(np.argmin(np.abs(r["angle"] - angle))), 3]))
        print(f"  {angle:4}°  " + "".join(f"{v:16.2f}" for v in row))
    return curves


def chart(results: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), sharex=True)
    colours = {"one joint": "#c0504d", "edge fixed": "#4f81bd", "centre fixed": "#9bbb59"}
    for ax, joint, title in zip(
        axes, (3, 2, 1), ("Wrist 1 (limit 28 N·m)", "Elbow (limit 150)", "Shoulder (limit 150)"), strict=True
    ):
        for way in WAYS:
            slow, fast = results[(way, 0)], results[(way, 1)]
            ax.plot(
                slow["angle"], np.abs(slow["tau"][:, joint]), color=colours[way], lw=2, label=f"{way}, 5 s"
            )
            ax.plot(
                fast["angle"],
                np.abs(fast["tau"][:, joint]),
                color=colours[way],
                lw=1.2,
                ls="--",
                label=f"{way}, {fast['duration']:.2f} s",
            )
        ax.set_title(title)
        ax.set_xlabel("board angle (0° hanging, 90° flat)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("torque, N·m")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(HERE / "joint_torques.png", dpi=130)


def flip_chart(curves: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    colours = {"normal wrist": "#c0504d", "flipped wrist": "#4f81bd"}
    for posture, r in curves.items():
        ax.plot(r["angle"], np.abs(r["hold"][:, 3]), color=colours[posture], lw=2.2, label=posture)
    ax.set_xlabel("board angle (0° hanging, 90° flat)")
    ax.set_ylabel("wrist 1 holding torque, N·m")
    ax.set_title("Same board, same place, wrist turned the other way")
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / "wrist_flip.png", dpi=130)


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--make-urdf":
        make_urdf(Path(sys.argv[2]))
        return

    p.connect(p.DIRECT)
    check_mass()
    check_holding(V2_BOARD_MASS)
    for way in WAYS:
        check_energy(swing(way, fastest(way), V2_BOARD_MASS))
    check_derivatives()
    print("checks passed: mass, holding torque two ways, work against energy, speeds against exact")

    results = table(V2_BOARD_MASS)
    wrist_parts(V2_BOARD_MASS)
    board_share(V2_BOARD_MASS)
    print("\nHeaviest board before any joint reaches its limit:")
    for pace in (0, 1):
        for way in WAYS:
            duration, label = paces(way)[pace]
            mass, joint = heaviest(way, duration)
            print(f"  {way + ', ' + label:30} {mass:5.1f} kg   ({joint} gives out first)")
    chart(results)
    flip_chart(hold_curve())
    posture_table(V2_BOARD_MASS)


if __name__ == "__main__":
    main()
