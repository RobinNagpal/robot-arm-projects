"""Draws the pictures in docs/turn-by-whole-arm/.

Run from anywhere, with this project's own Python:

    .pixi/envs/default/bin/python docs/turn-by-whole-arm/figures/draw_whole_arm.py

It borrows the drawing helpers and the colours of the wrist docs' pictures
(../../turn-by-wrist/figures/draw_steps.py). The turn itself is worked out
here the same way the docs work it by hand: seed 1, in the arm's own upright
plane, with the gripped edge at the turning spot. The drawings of the arm made
to scale from the robot's model are in ../../figures/, made by two_turns.py.
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
    AXIS_Z,
    BAD,
    FAINT,
    GOOD,
    GRIP,
    INK,
    INK2,
    PATH,
    TOP,
    TOP_EDGE,
    arrow,
    clean,
    floor,
    note,
    plt,
    title,
)
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge  # noqa: E402

# Seed 1, in the arm's plane: "out" along the plane from the base's line, and
# "up" from the floor, in cm. From turn-by-whole-arm's hand working.
EDGE = np.array([48.2, 40.0])
SHOULDER = np.array([0.0, 16.25])
UPPER_ARM, FOREARM = 42.5, 39.22
TOOL_TO_EDGE = 12.0
WIDTH, THICKNESS = 16.5, 1.9
WRIST_1_FROM_TOOL = np.array([-10.0, 10.0])  # with the tool pointing straight down


def save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", name)


def turn(v, degrees):
    """``v`` turned anticlockwise by ``degrees`` in the page."""
    a = math.radians(degrees)
    return np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])


def arm_at(angle):
    """Where each part is with the top turned ``angle`` degrees about its edge, away from the arm."""
    tool = EDGE + turn(np.array([0.0, TOOL_TO_EDGE]), angle)
    wrist_1 = tool + turn(WRIST_1_FROM_TOOL, angle)
    to_wrist = wrist_1 - SHOULDER
    reach = float(np.linalg.norm(to_wrist))
    bend = math.degrees(math.acos((reach**2 - UPPER_ARM**2 - FOREARM**2) / (2 * UPPER_ARM * FOREARM)))
    alpha = math.degrees(math.acos((UPPER_ARM**2 + reach**2 - FOREARM**2) / (2 * UPPER_ARM * reach)))
    elevation = math.degrees(math.atan2(to_wrist[1], to_wrist[0]))
    upper = elevation + alpha
    elbow = SHOULDER + UPPER_ARM * np.array([math.cos(math.radians(upper)), math.sin(math.radians(upper))])
    far = EDGE + turn(np.array([0.0, -WIDTH]), angle)
    return {
        "tool": tool,
        "wrist_1": wrist_1,
        "elbow": elbow,
        "reach": reach,
        "bend": bend,
        "alpha": alpha,
        "elevation": elevation,
        "upper": upper,
        "far": far,
    }


def board(ax, near, far, colour=TOP_EDGE, alpha=1.0, z=4):
    direction = (far - near) / np.linalg.norm(far - near)
    side = np.array([-direction[1], direction[0]]) * THICKNESS / 2
    ax.add_patch(
        Polygon([near + side, far + side, far - side, near - side], fc=TOP, ec=colour, lw=1.3, alpha=alpha, zorder=z)
    )


def steps_at_a_glance():
    steps = [
        ("1  Look and measure", "same as the wrist turn", "top: centre, 3 axes,\n24.4 × 16.5 × 1.9 cm\nedge 16.6 cm up"),
        ("2  Plan everything", "the turn check differs", "Route, and all 18 turn\nposes reachable with\nthe wrist the same way"),
        ("3  Grip the edge", "same as the wrist turn", "fingers 5 cm over the edge\ntool0 28.6 cm up\nH: tool in the board"),
        ("4  Lift straight up", "same as the wrist turn", "up 20.5 cm\nbottom edge at 20.6 cm\nboard hangs down"),
        ("5  Carry it round", "same as the wrist turn", "arc 54 → 50 cm out\nboard centre 31.8 cm up\nedge turned 105°"),
        ("6  Edge along wrist 1", "why differs", "not needed to end flat;\nkeeps the turn in the\narm's plane: 3 joints"),
        ("7  Turn about the edge", "shoulder, elbow, wrist 1", "18 poses, 5° apart\nedge stays at 40 cm\nwrist 1 142°, 8.7 s"),
        ("8  Hold and report", "same checks", "hold 5 s, tilt 0.1°\nshoulder, elbow hold\n18 N·m, not 25"),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    clean(ax, 0, 40, 0, 19)
    w, h = 8.6, 7.4
    for i, (name, moves, out) in enumerate(steps):
        row, col = divmod(i, 4)
        x = 0.4 + col * 10.0
        y = 10.6 - row * 9.6
        colour = base.LEG if i == 6 else (INK2 if moves.startswith("same") else PATH)
        ax.add_patch(
            FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.5", fc="white", ec=colour, lw=1.6)
        )
        note(ax, (x + 0.4, y + h - 0.8), name, color=colour, size=11, weight="bold")
        note(ax, (x + 0.4, y + h - 2.3), moves, color=INK2, size=8.8, va="top")
        ax.plot([x + 0.4, x + w - 0.4], [y + 3.6, y + 3.6], color="#e3e2dc", lw=1)
        note(ax, (x + 0.4, y + 3.2), out, color=INK, size=9, va="top")
        if col < 3:
            arrow(ax, (x + w + 0.1, y + h / 2), (x + 9.9, y + h / 2), color=FAINT, lw=1.5)
    arrow(ax, (38.8, 10.6), (4.7, 9.3), color=FAINT, lw=1.5, rad=-0.08)
    note(
        ax,
        (20, 18.6),
        "seed 1, the whole-arm turn. Grey: the same code as the wrist turn. Coloured: what differs.",
        size=10,
        ha="center",
    )
    save(fig, "steps_at_a_glance.png")


def turn_about_the_edge():
    """p' = c + R · (p − c), in three pictures, with tool0 and the top's far edge."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.8))
    tool = np.array([48.2, 52.0])
    far = np.array([48.2, 23.5])
    angle = 90.0  # anticlockwise in the page: away from the arm, which is to the left

    def frame(ax, x0, x1, y0, y1, name):
        clean(ax, x0, x1, y0, y1)
        ax.axhline(0, color="#e3e2dc", lw=0.8, zorder=0)
        ax.axvline(0, color="#e3e2dc", lw=0.8, zorder=0)
        title(ax, name)

    # 1. Subtract the pivot.
    ax = axes[0]
    frame(ax, -24, 26, -22, 22, "1) Subtract the edge: measure from it")
    near, t, f = np.zeros(2), tool - EDGE, far - EDGE
    board(ax, near, f)
    ax.plot([0, t[0]], [0, t[1]], color=GRIP, lw=3)
    ax.plot(*t, "o", color=INK, ms=6, zorder=6)
    ax.plot(0, 0, "o", color=PATH, ms=9, zorder=6)
    note(ax, (1.2, t[1]), "tool0 − edge\n= (48.2, 52.0) − (48.2, 40.0)\n= (0, 12)", size=9)
    note(ax, (1.2, f[1] + 2), "far edge − edge = (0, −16.5)", size=9)
    note(ax, (1.2, -1.8), "edge: (0, 0)", color=PATH, size=9)

    # 2. Turn about the origin.
    ax = axes[1]
    frame(ax, -24, 26, -22, 22, "2) Turn 90° about (0, 0)")
    t2, f2 = turn(t, angle), turn(f, angle)
    board(ax, near, f, alpha=0.2, colour=FAINT)
    ax.plot([0, t[0]], [0, t[1]], color=GRIP, lw=3, alpha=0.2)
    board(ax, near, f2)
    ax.plot([0, t2[0]], [0, t2[1]], color=GRIP, lw=3)
    ax.plot(*t2, "o", color=INK, ms=6, zorder=6)
    ax.plot(0, 0, "o", color=PATH, ms=9, zorder=6)
    ax.add_patch(Wedge((0, 0), 12, 90, 180, fc="none", ec=PATH, lw=1, ls="--"))
    ax.add_patch(Wedge((0, 0), 16.5, 270, 360, fc="none", ec=PATH, lw=1, ls="--"))
    note(ax, (t2[0], t2[1] + 3), "(0, 12) → (−12, 0)", size=9, ha="center")
    note(ax, (f2[0], -3.8), "(0, −16.5) → (16.5, 0)", size=9, ha="right")
    note(ax, (-23, -15), "a quarter turn maps\n(out, up) → (−up, out)", color=PATH, size=9)

    # 3. Add the pivot back.
    ax = axes[2]
    frame(ax, 22, 72, 18, 62, "3) Add the edge back: into the room")
    ax.axhline(0, color="none")
    board(ax, EDGE, far, alpha=0.2, colour=FAINT)
    ax.plot([EDGE[0], tool[0]], [EDGE[1], tool[1]], color=GRIP, lw=3, alpha=0.2)
    t3, f3 = EDGE + t2, EDGE + f2
    board(ax, EDGE, f3)
    ax.plot([EDGE[0], t3[0]], [EDGE[1], t3[1]], color=GRIP, lw=3)
    ax.plot(*t3, "o", color=INK, ms=6, zorder=6)
    ax.plot(*EDGE, "o", color=PATH, ms=9, zorder=6)
    note(ax, (t3[0], t3[1] + 3), "tool0 (36.2, 40.0)", size=9, ha="center")
    note(ax, (f3[0], f3[1] - 3), "far edge (64.7, 40.0)", size=9, ha="center")
    note(ax, (EDGE[0] + 1, EDGE[1] + 11), "edge (48.2, 40.0):\nit has not moved", color=PATH, size=9)
    note(ax, (23, 21), "arm's plane, cm: across = out from the base, up = height", color=FAINT, size=8.5)
    save(fig, "turn_about_the_edge.png")


def arm_triangle():
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 6.2))
    for ax, angle in zip(axes, (0, 45, 90), strict=True):
        clean(ax, -22, 72, -3, 76)
        floor(ax, -22, 72, depth=3)
        ax.add_patch(Rectangle((-4, 0), 8, SHOULDER[1], fc="#dfe3e8", ec="#8a9098", zorder=1))
        a = arm_at(angle)
        s, e, w, t = SHOULDER, a["elbow"], a["wrist_1"], a["tool"]
        ax.plot([s[0], w[0]], [s[1], w[1]], color=PATH, lw=1, ls="--", zorder=2)
        ax.plot([s[0], e[0]], [s[1], e[1]], color="#8a9098", lw=7, solid_capstyle="round", zorder=3)
        ax.plot([e[0], w[0]], [e[1], w[1]], color="#a7adb5", lw=6, solid_capstyle="round", zorder=3)
        ax.plot([w[0], t[0]], [w[1], t[1]], color="#c9ccd1", lw=5, solid_capstyle="round", zorder=3)
        ax.plot([t[0], EDGE[0]], [t[1], EDGE[1]], color=GRIP, lw=3, zorder=3)
        board(ax, EDGE, a["far"])
        for point, colour in ((s, INK), (e, INK), (w, PATH), (t, INK)):
            ax.add_patch(Circle(point, 1.3, fc=colour, ec="white", zorder=6))
        ax.plot(*EDGE, "o", color=TOP_EDGE, ms=6, zorder=7)
        middle = (s + w) / 2
        note(ax, (middle[0] + 1.5, middle[1] - 2.5), f"D = {a['reach']:.1f}", color=PATH, size=9.5)
        note(ax, (e[0] + 2, e[1] + 2.5), f"elbow bend {a['bend']:.1f}°", size=9.5)
        lean = a["upper"] - arm_at(0)["upper"]
        note(ax, (s[0] - 1, s[1] + 5), f"upper arm turned\n{lean:+.1f}° from the start", size=9, ha="right")
        note(ax, (w[0] + 1, w[1] - 5), f"wrist 1\n({w[0]:.1f}, {w[1]:.1f})", color=PATH, size=9)
        note(ax, (EDGE[0] + 2, EDGE[1] - 4), "edge (48.2, 40.0)", color=TOP_EDGE, size=8.5)
        title(ax, f"top turned {angle}°")
    note(
        axes[0],
        (-21, 73),
        "upper arm 42.5 cm, forearm 39.22 cm, D = shoulder to wrist 1. Arm's plane, cm.",
        size=9,
    )
    save(fig, "arm_triangle.png")


def path_outcome():
    fig, ax = plt.subplots(figsize=(12.5, 5.6))
    clean(ax, 0, 50, 0, 24)

    def box(x, y, w, h, text, colour=PATH, fill="white", size=9.5, weight="normal"):
        ax.add_patch(
            FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.4", fc=fill, ec=colour, lw=1.4)
        )
        note(ax, (x + w / 2, y + h / 2), text, color=INK, size=size, ha="center", weight=weight)

    box(0.5, 8, 12, 6, "18 tool poses,\n5° apart about\nthe gripped edge")
    arrow(ax, (12.5, 11), (16, 11), color=FAINT, lw=1.5)
    box(16, 6.5, 13, 9, "MoveIt: straight lines\nthrough them, a point\nevery 5 mm, every point\ncollision-checked,\ntop included\n→ joint angles + fraction")
    outcomes = [
        (17.2, "fraction ≈ 100%\nrun it; tool must arrive\nwithin 5 mm and 1.7°", GOOD, "#eef8ee"),
        (9.4, "90% to 99.9%\nrun what there is, then one\nfree move to the last pose,\nwrist kept the same way", AXIS_Z, "#eef4fb"),
        (1.6, "under 90%\nstop: something is in the way\n(nothing is run)", BAD, "#fbeeee"),
    ]
    for y, text, colour, fill in outcomes:
        box(34, y, 15.5, 5.6, text, colour=colour, fill=fill, size=9.2)
        arrow(ax, (29, 11), (34, y + 2.8), color=colour, lw=1.3)
    note(ax, (0.5, 3.5), "SWING_STEP = 5°\nSWING_MIN_FRACTION = 0.9\nCARRY_SPEED = 0.1", color=INK2, size=9.5)
    save(fig, "path_outcome.png")


def main():
    steps_at_a_glance()
    turn_about_the_edge()
    arm_triangle()
    path_outcome()


if __name__ == "__main__":
    main()
