"""Draws the pictures in docs/tilt-onto-legs/.

Run from anywhere, with this project's own Python:

    .pixi/envs/default/bin/python docs/tilt-onto-legs/figures/draw_tilt.py

It borrows the drawing helpers and colours of the wrist docs' pictures
(../../turn-by-wrist/figures/draw_steps.py). The poses come from the task's own
code (assembly/grasps.py and assembly/table.py), run on seed 1's top and legs
as the camera measured them, so the pictures show the poses the robot plans.
The arm is left out; only tool0, the gripper and the top are drawn.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[1] / "turn-by-wrist" / "figures"))

import draw_steps as base  # noqa: E402
import numpy as np  # noqa: E402
from draw_steps import (  # noqa: E402
    AXIS_X,
    AXIS_Y,
    BAD,
    FAINT,
    GOOD,
    GRIP,
    INK,
    INK2,
    LEG,
    PATH,
    TOP,
    TOP_BOX,
    TOP_EDGE,
    arrow,
    clean,
    floor,
    note,
    plt,
    title,
)
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle  # noqa: E402
from turn_top_flat.assembly.grasps import (  # noqa: E402
    backed_off,
    board_point,
    carry_round,
    edge_pick_poses,
    gripped_edge,
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
    wrist_spin,
)
from turn_top_flat.assembly.table import landing_angle, read_legs  # noqa: E402
from turn_top_flat.geometry import Box  # noqa: E402
from turn_top_flat.transforms import WORLD_Z  # noqa: E402

# Seed 1's legs as the camera measured them: four standing sticks, 2.9 cm
# square and 16.7 cm tall.
LEG_CENTRES = [(0.11874, -0.76219), (0.29929, -0.70156), (0.07479, -0.63131), (0.25534, -0.57069)]
LEG_SIZE = (0.02933, 0.02933, 0.16672)
LEGS = read_legs(
    [Box.upright((x, y, 0.08436), math.radians(-71.439), LEG_SIZE) for x, y in LEG_CENTRES], np.zeros(3)
)

# From task.py.
TURN_HEIGHT, LEAN_RADIUS, CARRY_CLEARANCE = 0.40, 0.45, 0.04
LEANING = math.radians(20.0)
ABOVE_LEGS, LINE_STEP, TILT_STEP, LAND_DROP = 0.05, 0.02, math.radians(3.0), 0.003
TOP_RETREAT, LIFT, TOP_APPROACH, LIFT_CLEAR = 0.06, 0.08, 0.08, 0.04
BASE = np.zeros(3)

BOARD = TOP_BOX
EDGE, _, _ = upright_edge(BOARD)
WIDTH = 2.0 * float(EDGE[2] - BOARD.centre[2])
PICK = edge_pick_poses(BOARD)[0]
LIFTED = shifted(PICK, WORLD_Z * (WIDTH + LIFT_CLEAR))
HELD = hold(BOARD, PICK)

AXIS = tilt_axis(LEGS.toward)
OUTWARD = LEGS.hinge.copy()
OUTWARD[2] = 0.0
OUTWARD /= np.linalg.norm(OUTWARD)
LEAN_AT = OUTWARD * LEAN_RADIUS
LEAN_AT[2] = max(TURN_HEIGHT, LEGS.hinge[2] + CARRY_CLEARANCE + WIDTH)
LANDING = landing_angle(LEGS, LAND_DROP)
HANGING = min(hanging_tool_poses(LEAN_AT, LEGS.along), key=lambda pose: wrist_spin(LIFTED, pose, BASE))
RESTING = resting_edge(HANGING, HELD, BOARD.size, LEGS.toward)
STANDING = shifted(HANGING, LEGS.hinge - board_point(HANGING, HELD, RESTING))
TOUCH = turned_about(STANDING, LEGS.hinge, AXIS, LEANING)
ABOVE = shifted(TOUCH, WORLD_Z * ABOVE_LEGS)
LEAN = swing_about_edge(HANGING, AXIS, LEANING, math.radians(5.0))
OUT_LINE = straight_line(LEAN[-1], ABOVE, LINE_STEP)
TILT = tilt_steps(TOUCH, LEGS.hinge, AXIS, LANDING - LEANING, TILT_STEP)
AWAY = backed_off(TILT[-1], TOP_RETREAT)
UP = shifted(AWAY, WORLD_Z * LIFT)
CARRY_HEIGHT = max((LIFTED @ np.linalg.inv(HELD))[2, 3], (HANGING @ np.linalg.inv(HELD))[2, 3])
CARRY = carry_round(HELD, LIFTED, HANGING, CARRY_HEIGHT, BASE)

# The side view: across = how far out, away from the arm, square to the far row; up = height. cm.
AWAY_FROM_ARM = -LEGS.toward


def side(point):
    return np.array([float(np.asarray(point) @ AWAY_FROM_ARM), float(point[2])]) * 100.0


def save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", name)


def top_section(ax, tool_pose, alpha=1.0, colour=TOP_EDGE, z=4):
    """The top, cut through its middle square to the far row, with the tool held on it."""
    board = tool_pose @ np.linalg.inv(HELD)
    centre, up, normal = board[:3, 3], board[:3, 1], board[:3, 2]
    w, t = BOARD.size[1] / 2.0, BOARD.size[2] / 2.0
    corners = [centre + up * a * w + normal * b * t for a, b in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    ax.add_patch(
        Polygon([side(c) for c in corners], fc=TOP, ec=colour, lw=1.2, alpha=alpha, zorder=z)
    )
    tool, grip = side(tool_pose[:3, 3]), side(gripped_edge(tool_pose))
    ax.plot([tool[0], grip[0]], [tool[1], grip[1]], color=GRIP, lw=3, alpha=alpha, zorder=z + 1)
    ax.plot(*tool, "o", color=INK, ms=4, alpha=alpha, zorder=z + 2)


def legs_side(ax):
    for leg in (*LEGS.far, *LEGS.near):
        x = side(leg.centre)[0]
        ax.add_patch(Rectangle((x - 1.47, 0), 2.93, leg.top_z * 100, fc=LEG, ec="#1c5cab", alpha=0.35, zorder=2))


def steps_at_a_glance():
    steps = [
        ("1  Look and measure", "as the air turns", "floor; the top 24.4 × 16.5 × 1.9\n4 legs, seen as sticks"),
        ("2  Measure the legs", "all joints, to aim the camera", "far and near pairs, the hinge\nline 76 cm out, 16.8 cm up\nthe rows 13.8 cm apart"),
        ("3  Plan everything", "nothing moves", "lean 20° (or 30°), where to\nhang it, the touch, 23 tilt\nposes, every pose followed"),
        ("4  Grip, lift, carry", "as the air turns", "carried 165° round to\nhang 45 cm out, 40 cm up,\nedge along the far row"),
        ("5  Lean and carry out", "most joints", "lean 20° about the gripped\nedge; straight out 26.5 cm\nto 5 cm above the legs"),
        ("6  Feel for the legs", "shoulder, elbow, wrist 1", "down 0.5 mm at a time until\nthe efforts jump; back one\nstep; loosen the grip 4 mm"),
        ("7  Tilt it down", "all six", "about the resting edge, 3° a\nstep, 69°, to 3 mm above the\nnear legs; unchecked"),
        ("8  Let go, check", "all six", "open, pull back 6 cm, up 8 cm;\nlook: 18.6 cm tall, level:\na table"),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    clean(ax, 0, 40, 0, 19)
    w, h = 8.6, 7.4
    for i, (name, moves, out) in enumerate(steps):
        row, col = divmod(i, 4)
        x, y = 0.4 + col * 10.0, 10.6 - row * 9.6
        colour = INK2 if moves.startswith("as the") else (TOP_EDGE if i in (5, 6) else PATH)
        ax.add_patch(
            FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.5", fc="white", ec=colour, lw=1.6)
        )
        note(ax, (x + 0.4, y + h - 0.8), name, color=colour, size=11, weight="bold")
        note(ax, (x + 0.4, y + h - 2.3), "moves: " + moves, color=INK2, size=8.8, va="top")
        ax.plot([x + 0.4, x + w - 0.4], [y + 3.6, y + 3.6], color="#e3e2dc", lw=1)
        note(ax, (x + 0.4, y + 3.2), out, color=INK, size=8.8, va="top")
        if col < 3:
            arrow(ax, (x + w + 0.1, y + h / 2), (x + 9.9, y + h / 2), color=FAINT, lw=1.5)
    arrow(ax, (38.8, 10.6), (4.7, 9.3), color=FAINT, lw=1.5, rad=-0.08)
    note(ax, (20, 18.6), "seed 1, make tilt. Grey: the same as the turns in the air.", size=10, ha="center")
    save(fig, "steps_at_a_glance.png")


def legs_from_above():
    fig, (wide, close) = plt.subplots(1, 2, figsize=(14, 7.2), gridspec_kw={"width_ratios": [1, 1.15]})

    def footprint(ax, scale=1.0):
        centre = LEGS.hinge + LEGS.toward * WIDTH / 2.0
        a, t = LEGS.along * BOARD.size[0] / 2.0, LEGS.toward * WIDTH / 2.0
        corners = [centre + a + t, centre - a + t, centre - a - t, centre + a - t]
        ax.add_patch(
            Polygon([c[:2] * 100 for c in corners], fc=TOP, ec=TOP_EDGE, alpha=0.18, ls="--", lw=1.2, zorder=1)
        )
        for leg, label in zip((*LEGS.far, *LEGS.near), ("far", "far", "near", "near"), strict=True):
            c = leg.centre[:2] * 100
            ax.add_patch(Rectangle((c[0] - 1.47, c[1] - 1.47), 2.93, 2.93, fc=LEG, ec="#1c5cab", zorder=3))
            if scale > 1:
                note(ax, (c[0] + 2.0, c[1] - 2.0), label, color=LEG, size=9)

    # a) the whole room.
    clean(wide, -45, 75, -95, 70)
    wide.add_patch(Circle((0, 0), 13, fc="#dfe3e8", ec="#8a9098", zorder=2))
    note(wide, (0, 0), "base", size=8.5, ha="center")
    c = BOARD.centre[:2] * 100
    wide.add_patch(Rectangle((c[0] - 12.2, c[1] - 1), 24.4, 2, fc=TOP, ec=TOP_EDGE, zorder=4))
    note(wide, (c[0], c[1] + 5), "the top, in its holders", color=TOP_EDGE, size=9, ha="center")
    footprint(wide)
    path = np.array([(pose @ np.linalg.inv(HELD))[:2, 3] * 100 for pose in CARRY])
    wide.plot(path[:, 0], path[:, 1], color=PATH, lw=1.3, zorder=3)
    arrow(wide, path[-3], path[-1], color=PATH, lw=1.3, scale=10)
    lean = LEAN_AT[:2] * 100
    wide.plot(*lean, "o", color=PATH, ms=7, zorder=6)
    note(wide, (lean[0] - 3, lean[1] + 1), "leaned over here:\n45 cm out, 40 cm up", color=PATH, size=9, ha="right")
    hinge = LEGS.hinge[:2] * 100
    wide.plot([0, hinge[0]], [0, hinge[1]], color=FAINT, lw=0.8, ls="--", zorder=0)
    note(wide, (-44, -86), "carried round the base, hanging:\n35 poses, the top's centre on an arc", color=PATH, size=9)
    note(wide, (hinge[0] + 4, hinge[1] - 4), "legs, 76 cm out", color=LEG, size=9)
    title(wide, "a) From above: the top, the legs, the carry")

    # b) close up on the legs.
    centre = (LEGS.hinge + LEGS.toward * 0.07)[:2] * 100
    clean(close, centre[0] - 26, centre[0] + 26, centre[1] - 22, centre[1] + 22)
    footprint(close, scale=2.0)
    far_middle = np.mean([leg.centre for leg in LEGS.far], axis=0)[:2] * 100
    near_middle = np.mean([leg.centre for leg in LEGS.near], axis=0)[:2] * 100
    close.plot([leg.centre[0] * 100 for leg in LEGS.far], [leg.centre[1] * 100 for leg in LEGS.far], color=BAD, lw=2.2, zorder=4)
    close.plot(*hinge, "o", color=BAD, ms=8, zorder=6)
    note(close, (hinge[0] + 3, hinge[1] - 5.5), "hinge: between the far legs'\nmiddles, at their tops (16.8 cm)", color=BAD, size=9)
    arrow(close, hinge, hinge + LEGS.along[:2] * 9, color=AXIS_X, lw=1.8)
    note(close, hinge + LEGS.along[:2] * 9 + [0, -3.5], "along", color=AXIS_X, size=9.5, ha="center")
    arrow(close, hinge, hinge + LEGS.toward[:2] * 9, color=AXIS_Y, lw=1.8)
    note(close, hinge + LEGS.toward[:2] * 11 + [2.5, 0], "toward\n(the arm)", color=AXIS_Y, size=9.5)
    close.plot([far_middle[0], near_middle[0]], [far_middle[1], near_middle[1]], color=INK2, lw=1, ls=":")
    mid = (far_middle + near_middle) / 2
    note(close, (mid[0] - 1.2, mid[1] + 0.5), "rows\n13.8 cm", size=9, ha="right")
    top_centre = (LEGS.hinge + LEGS.toward * WIDTH / 2.0)[:2] * 100
    note(close, top_centre + LEGS.toward[:2] * 12 + [-3, 1.5], "where the top ends:\n24.4 × 16.5 cm, from the\nhinge towards the arm", color=TOP_EDGE, size=9)
    title(close, "b) The legs close up: far, near, hinge, along, toward")
    save(fig, "legs_from_above.png")


def tilt_side_view():
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    x0, x1, y0, y1 = 30, 95, -3, 62

    def frame(ax, name):
        clean(ax, x0, x1, y0, y1)
        floor(ax, x0, x1, depth=3)
        legs_side(ax)
        title(ax, name)
        note(ax, (x0 + 1, y1 - 2), "the arm is off to the left", color=FAINT, size=8.5)

    ax = axes[0, 0]
    frame(ax, "a) Lean it 20° about the gripped edge, in the air")
    top_section(ax, HANGING, alpha=0.3, colour=FAINT)
    for pose in LEAN[:-1]:
        top_section(ax, pose, alpha=0.15, colour=FAINT)
    top_section(ax, LEAN[-1])
    edge = side(gripped_edge(HANGING))
    ax.plot(*edge, "o", color=PATH, ms=7, zorder=8)
    note(ax, (edge[0] + 2, edge[1] + 3), "gripped edge stays put:\n45 cm out, 40 cm up", color=PATH, size=9)
    note(ax, (x0 + 1, 12), "4 poses, 5° apart", size=9)

    ax = axes[0, 1]
    frame(ax, "b) Carry it out, leaning, then let it down")
    top_section(ax, LEAN[-1], alpha=0.25, colour=FAINT)
    for pose in OUT_LINE[3:-1:4]:
        top_section(ax, pose, alpha=0.12, colour=FAINT)
    top_section(ax, ABOVE, alpha=0.45)
    top_section(ax, TOUCH)
    start, end = side(LEAN[-1][:3, 3]), side(ABOVE[:3, 3])
    arrow(ax, start + [0, 4], end + [0, 4], color=PATH, lw=1.5)
    note(ax, ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 7), "straight line, 26.5 cm", color=PATH, size=9, ha="center")
    hinge = side(LEGS.hinge)
    ax.plot(*hinge, "o", color=BAD, ms=7, zorder=8)
    note(ax, (hinge[0] + 2, hinge[1] - 3), "lower edge on the hinge,\nfelt for 0.5 mm at a time", color=BAD, size=9)
    note(ax, (end[0] + 3, end[1] + 1), "5 cm above", size=9)

    ax = axes[1, 0]
    frame(ax, "c) Tilt it down about the edge resting on the far legs")
    for pose in TILT[:-1:5]:
        top_section(ax, pose, alpha=0.2, colour=FAINT)
    top_section(ax, TOUCH, alpha=0.35, colour=FAINT)
    top_section(ax, TILT[-1])
    ax.plot(*hinge, "o", color=BAD, ms=7, zorder=8)
    note(ax, (hinge[0] + 2, hinge[1] + 3), "this edge does not move:\nnothing slides on the legs", color=BAD, size=9)
    note(ax, (x0 + 1, 40), "from leaning 20° to 1.25°\nshort of flat: 68.75°,\n23 poses, 3° apart", size=9)

    ax = axes[1, 1]
    frame(ax, "d) Let go, pull back out, lift clear")
    top_section(ax, TILT[-1], alpha=1.0)
    for pose, label in ((AWAY, "back 6 cm, the way it reached in"), (UP, "up 8 cm")):
        tool = side(pose[:3, 3])
        grip = side(gripped_edge(pose))
        ax.plot([tool[0], grip[0]], [tool[1], grip[1]], color=GRIP, lw=3, alpha=0.6)
        ax.plot(*tool, "o", color=INK, ms=4)
        note(ax, (tool[0] - 1, tool[1] + 3), label, size=9, ha="right")
    note(ax, (x0 + 1, 44), "fingers open to 7.4 cm; the top\nfalls the last 3 mm onto the\nnear legs", size=9)
    save(fig, "tilt_side_view.png")


def landing():
    fig, ax = plt.subplots(figsize=(12, 5.6))
    clean(ax, -4, 26, -3, 13)
    shown = math.radians(8.0)  # drawn steeper than the real 1.25°, to be seen
    hinge = np.array([20.0, 8.0])
    rows = 13.8
    near_x = hinge[0] - rows
    for x in (hinge[0], near_x):
        ax.add_patch(Rectangle((x - 1.47, -3), 2.93, 11, fc=LEG, ec="#1c5cab", alpha=0.5))
    direction = np.array([-math.cos(shown), math.sin(shown)])
    far_end = hinge + direction * 18.0
    normal = np.array([direction[1], -direction[0]]) * -1
    ax.add_patch(Polygon([hinge, far_end, far_end + normal * 1.0, hinge + normal * 1.0], fc=TOP, ec=TOP_EDGE))
    ax.plot([hinge[0], hinge[0] - 18], [hinge[1], hinge[1]], color=FAINT, ls="--", lw=1)
    ax.plot(*hinge, "o", color=BAD, ms=8, zorder=6)
    note(ax, (hinge[0] + 0.7, hinge[1] - 1.2), "hinge: the far legs' tops", color=BAD, size=9.5)
    lift = rows * math.sin(shown)
    arrow(ax, (near_x + 2.6, hinge[1]), (near_x + 2.6, hinge[1] + lift), color=PATH, lw=1.2, style="<|-|>", scale=9)
    note(ax, (near_x - 2.0, hinge[1] - 0.6), "rise = rows · sin(short)\n= 3 mm (LAND_DROP)", color=PATH, size=9.5, ha="right", va="top")
    ax.plot([near_x, hinge[0]], [hinge[1] - 1.6, hinge[1] - 1.6], color=INK2, lw=0.8)
    note(ax, ((near_x + hinge[0]) / 2, hinge[1] - 2.4), "rows = 13.8 cm", size=9.5, ha="center")
    note(ax, (hinge[0] - 4.5, hinge[1] + 0.45), "short", color=INK2, size=9)
    note(
        ax,
        (-3.5, 12.2),
        "short = arcsin(rise / rows) = arcsin(0.3 / 13.81) = 1.25°      landing angle = 90° − 1.25° = 88.75°\n"
        "(the angle is drawn much steeper here, so it can be seen)",
        size=9.5,
        va="top",
    )
    save(fig, "landing_angle.png")


def feel_for_legs():
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    depths = np.arange(5.0, 0.4, -0.5)
    changes = [0.02, 0.03, 0.02, 0.04, 0.03, 0.05, 0.04, 0.06, 3.6, 0.0][: len(depths)]
    touch = int(np.argmax(np.array(changes) > 0.5))
    ax.bar(depths[: touch + 1], changes[: touch + 1], width=0.35, color=[PATH] * touch + [BAD])
    ax.axhline(0.5, color=AXIS_X, lw=1, ls="--")
    ax.text(5.2, 0.62, "TOUCH_EFFORT 0.5 N·m", color=AXIS_X, fontsize=9)
    ax.annotate(
        "the legs take some weight:\nthe change jumps (2.9 to 5.2 N·m in the runs)",
        (depths[touch], changes[touch]),
        xytext=(-0.4, 2.8),
        fontsize=9.5,
        color=BAD,
        arrowprops={"arrowstyle": "-|>", "color": BAD},
    )
    ax.annotate(
        "hanging clear: at most 0.06 N·m",
        (depths[3], changes[3]),
        xytext=(4.9, 1.3),
        fontsize=9.5,
        color=PATH,
        arrowprops={"arrowstyle": "-|>", "color": PATH},
    )
    ax.set_xlim(5.4, -6.4)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.axvline(-6.0, color=FAINT, lw=0.8, ls=":")
    ax.text(-0.2, 4.2, "where the legs\nwere measured", fontsize=9, color=INK2)
    ax.text(-4.0, 4.2, "give up 6 mm past\n(TOUCH_LIMIT)", fontsize=9, color=FAINT)
    ax.set_ylim(0, 5)
    ax.set_xlabel("how far above where the legs were measured, mm (0.5 mm steps, left to right)", color=INK2)
    ax.set_ylabel("largest change in shoulder,\nelbow, wrist 1 effort, N·m", color=INK2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_facecolor(base.BG)
    title(ax, "Feeling for the far legs (a sketch, with the sizes the runs showed)")
    save(fig, "feel_for_legs.png")


def table_check():
    fig, ax = plt.subplots(figsize=(11, 6))
    clean(ax, -12, 40, -3, 62)
    floor(ax, -12, 40, depth=3)
    legs_top, thickness, depth = 16.8, 1.9, 16.5
    for x in (1.5, 13.8 + 1.5):
        ax.add_patch(Rectangle((x - 1.47, 0), 2.93, legs_top, fc=LEG, ec="#1c5cab"))
    ax.add_patch(Rectangle((-0.2, legs_top), depth, thickness, fc=TOP, ec=TOP_EDGE))
    ax.add_patch(Rectangle((-0.6, 0), depth + 0.8, legs_top + thickness + 0.3, fc="none", ec=PATH, ls="--", lw=1.3))
    arrow(ax, (-3, 0), (-3, legs_top + thickness), color=PATH, lw=1.2, style="<|-|>", scale=9)
    note(ax, (-3.6, 9), "height of the fitted box\n= legs + top\n18.6 cm (expected 18.6)", color=PATH, size=9.5, ha="right")
    for camera, label in (((8, 50), "view from 50 cm above"), ((24, 45), "view from the arm's side, 45 cm up")):
        ax.plot(*camera, "s", color=INK, ms=8)
        arrow(ax, camera, (8, legs_top + thickness + 0.5), color=FAINT, lw=1)
        note(ax, (camera[0] + 1.5, camera[1] + 2), label, size=9)
    ax.add_patch(Rectangle((-0.2, legs_top + thickness - 0.6), depth, 0.6, fc="none", ec=GOOD, lw=1.5))
    note(ax, (depth + 1, legs_top + 1.4), "top 6 mm of points: a plane,\nits tilt from level (0.0°)", color=GOOD, size=9)
    note(ax, (19, 10), "a table if: height within 1 cm of expected,\nand the top within 3° of level", color=INK, size=10)
    note(ax, (-11, 58), "The top and legs touch, so the camera sees one coloured lump. A box fitted to it is the table.", size=9.5)
    save(fig, "table_check.png")


def main():
    steps_at_a_glance()
    legs_from_above()
    tilt_side_view()
    landing()
    feel_for_legs()
    table_check()
    print(
        f"tilt poses {len(TILT)}, out line {len(OUT_LINE)}, carry {len(CARRY)}, landing {math.degrees(LANDING):.2f}"
    )


if __name__ == "__main__":
    main()
