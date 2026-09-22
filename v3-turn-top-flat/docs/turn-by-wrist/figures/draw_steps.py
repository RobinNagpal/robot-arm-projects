"""Draws the pictures in docs/turn-by-wrist/.

Run from anywhere, with this project's own Python:

    .pixi/envs/default/bin/python docs/turn-by-wrist/figures/draw_steps.py

The poses come from the task's own code (assembly/grasps.py), run on seed 1's
top as the camera measured it, so the numbers in the pictures are the numbers
the robot works with. The arm itself is drawn as a sketch, not to scale; the
to-scale drawings of the arm are in ../../figures/, made by two_turns.py.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import (  # noqa: E402
    Circle,
    FancyArrowPatch,
    FancyBboxPatch,
    Polygon,
    Rectangle,
    Wedge,
)

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[2]
sys.path.insert(0, str(PROJECT / "src" / "turn_top_flat"))

from turn_top_flat.arm.dimensions import (  # noqa: E402
    SURVEY_AZIMUTHS_DEG,
    SURVEY_CAMERA_RADIUS,
    SURVEY_LOOK_RADIUS,
)
from turn_top_flat.assembly.grasps import (  # noqa: E402
    carry_round,
    edge_pick_poses,
    hanging_tool_poses,
    hold,
    shifted,
    upright_edge,
    wrist_spin,
)
from turn_top_flat.geometry import Box  # noqa: E402
from turn_top_flat.transforms import WORLD_Z  # noqa: E402

BG = "#fcfcfb"
INK = "#1f1f1d"
INK2 = "#52514e"
FAINT = "#9a9993"
FLOOR = "#e6e4dc"
GREY = "#b4b3ab"
GREY_EDGE = "#8f8e87"
TOP = "#eb6834"
TOP_EDGE = "#b8491c"
LEG = "#2a78d6"
GRIP = "#3d3d3a"
FINGER = "#77766f"
PATH = "#4a3aa7"
GOOD = "#0ca30c"
BAD = "#d03b3b"
AXIS_X, AXIS_Y, AXIS_Z = "#d03b3b", "#0ca30c", "#2a78d6"

plt.rcParams.update(
    {
        "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10.5,
        "text.color": INK,
        "figure.facecolor": BG,
        "savefig.facecolor": BG,
    }
)

# ------------------------------------------------------------ seed 1's room

# The top as the camera measured it, which is within a millimetre of where the
# simulator put it. Its own axes: along its length, up its face, out of its face.
CENTRE = np.array([-0.013, 0.540, 0.0834])
ALONG = np.array([-1.0, 0.0095, 0.0]) / np.linalg.norm([-1.0, 0.0095, 0.0])
UP = np.array([0.0, 0.0, 1.0])
NORMAL = np.cross(ALONG, UP)
SIZE = np.array([0.244, 0.165, 0.019])
TOP_BOX = Box(CENTRE, np.column_stack((ALONG, UP, NORMAL)), SIZE)

# The robot never sees these. They are drawn so the pictures show what is there.
HOLDER_HEIGHT = 0.055
LEGS = [(0.119, -0.762), (0.299, -0.702), (0.075, -0.631), (0.255, -0.571)]
LEG_SIDE, LEG_HEIGHT = 0.029, 0.167

# From task.py and grasps.py.
TURN_SPOT = np.array([0.50, 0.0, 0.40])
TURN_CLEARANCE = 0.40
TOP_APPROACH = 0.08
LIFT_CLEAR = 0.04
EDGE_BELOW_TOOL = 0.12
FINGERTIP = 0.17
BASE = np.zeros(3)

# Wrist 1's axis at the turning spot, as Arm.joint_axis() finds it for seed 1.
AXIS = np.array([0.267, 0.964, 0.0]) / np.linalg.norm([0.267, 0.964, 0.0])


def cm(v):
    return np.asarray(v, dtype=float) * 100.0


def save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print("wrote", name)


def arrow(ax, a, b, color=PATH, lw=2.0, rad=0.0, style="-|>", z=7, scale=14):
    ax.add_patch(
        FancyArrowPatch(
            tuple(a),
            tuple(b),
            arrowstyle=style,
            mutation_scale=scale,
            lw=lw,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
            zorder=z,
            shrinkA=0,
            shrinkB=0,
        )
    )


def note(ax, xy, text, color=INK2, size=9.5, ha="left", va="center", weight="normal", z=9, box=False):
    bbox = {"boxstyle": "round,pad=0.2", "fc": BG, "ec": "none", "alpha": 0.9} if box else None
    ax.text(*xy, text, color=color, fontsize=size, ha=ha, va=va, zorder=z, fontweight=weight, bbox=bbox)


def title(ax, text):
    ax.set_title(text, loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=8)


def clean(ax, x0, x1, y0, y1):
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")


def floor(ax, x0, x1, depth=4.0):
    ax.add_patch(Rectangle((x0, -depth), x1 - x0, depth, fc=FLOOR, ec="none", zorder=0))
    ax.plot([x0, x1], [0, 0], color="#c3c2b7", lw=1.5, zorder=0)


def dimension(ax, x, y0, y1, text, side="right", color=INK2):
    """A vertical measurement line from y0 to y1 at x, with its label."""
    arrow(ax, (x, y0), (x, y1), color=color, lw=1.0, style="<|-|>", scale=8)
    offset = 0.8 if side == "right" else -0.8
    note(
        ax, (x + offset, (y0 + y1) / 2), text, color=color, size=9, ha="left" if side == "right" else "right"
    )


def level(ax, x0, x1, y, text=None, color=FAINT):
    ax.plot([x0, x1], [y, y], color=color, lw=0.8, ls=(0, (3, 3)), zorder=1)
    if text:
        note(ax, (x0 - 0.6, y), text, color=color, size=8.5, ha="right")


# ------------------------------------------------ the moves, from the real code

EDGE, _, _ = upright_edge(TOP_BOX)
HEIGHT = 2.0 * float(EDGE[2] - CENTRE[2])
PICKS = edge_pick_poses(TOP_BOX)
PICK = PICKS[0]
APPROACH = shifted(PICK, WORLD_Z * TOP_APPROACH)
LIFTED = shifted(PICK, WORLD_Z * (HEIGHT + LIFT_CLEAR))
HELD = hold(TOP_BOX, PICK)
HANGING = min(hanging_tool_poses(TURN_SPOT, AXIS), key=lambda pose: wrist_spin(LIFTED, pose, BASE))
CARRY_HEIGHT = max((LIFTED @ np.linalg.inv(HELD))[2, 3], (HANGING @ np.linalg.inv(HELD))[2, 3])
CARRY = carry_round(HELD, LIFTED, HANGING, CARRY_HEIGHT, BASE)


# ------------------------------------------------------------------ pictures


def steps_at_a_glance():
    steps = [
        (
            "1  Look and measure",
            "all joints, to aim\nthe camera",
            "top: centre, 3 axes,\n24.4 × 16.5 × 1.9 cm\nedge 16.6 cm up",
        ),
        (
            "2  Plan everything",
            "nothing moves",
            "a Route: approach, pick,\nlifted, 22 carry poses,\nwrist side",
        ),
        (
            "3  Grip the edge",
            "all joints",
            "fingers 5 cm over the edge\ntool0 28.6 cm up\nH: tool in the board",
        ),
        (
            "4  Lift straight up",
            "shoulder, elbow,\nwrist 1",
            "up 20.5 cm\nbottom edge at 20.6 cm\nboard hangs down",
        ),
        (
            "5  Carry it round",
            "mostly the base,\nwrist 3 a little",
            "arc 54 → 50 cm out\nboard centre 31.8 cm up\nedge turned 105°",
        ),
        (
            "6  Edge along wrist 1",
            "(planned in step 2)",
            "edge along (0.267, 0.964, 0)\n15.5° off the y axis",
        ),
        ("7  Turn it flat", "wrist 1 only", "−90°, 7.9 s\nhalf a cosine wave\ntop ends 72 cm up"),
        ("8  Hold and report", "none", "hold 5 s\ntilt 0.1°\nfingers still feel it"),
    ]
    fig, ax = plt.subplots(figsize=(13.5, 6.4))
    clean(ax, 0, 40, 0, 19)
    w, h = 8.6, 7.4
    for i, (name, moves, out) in enumerate(steps):
        row, col = divmod(i, 4)
        x = 0.4 + col * 10.0
        y = 10.6 - row * 9.6
        colour = TOP if i == 6 else PATH
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.5", fc="white", ec=colour, lw=1.6
            )
        )
        note(ax, (x + 0.4, y + h - 0.8), name, color=colour, size=11, weight="bold")
        note(ax, (x + 0.4, y + h - 2.3), "moves: " + moves, color=INK2, size=8.8, va="top")
        ax.plot([x + 0.4, x + w - 0.4], [y + 3.6, y + 3.6], color="#e3e2dc", lw=1)
        note(ax, (x + 0.4, y + 3.2), out, color=INK, size=9, va="top")
        if col < 3:
            arrow(ax, (x + w + 0.1, y + h / 2), (x + 9.9, y + h / 2), color=FAINT, lw=1.5)
    arrow(ax, (38.8, 10.6), (4.7, 9.3), color=FAINT, lw=1.5, rad=-0.08)
    note(
        ax,
        (20, 18.6),
        "seed 1: what each step does, which joints move, and what it hands on",
        size=10,
        ha="center",
    )
    save(fig, "steps_at_a_glance.png")


def room_from_above():
    fig, ax = plt.subplots(figsize=(8.6, 9.6))
    clean(ax, -48, 108, -95, 78)

    # The turning spot and the space it needs.
    spot = cm(TURN_SPOT[:2])
    ax.add_patch(Circle(spot, cm(TURN_CLEARANCE), fc="#efeaf9", ec=PATH, ls="--", lw=1.2, zorder=0))
    ax.plot(*spot, marker="*", ms=16, color=PATH, zorder=6)
    note(ax, (spot[0] + 2, spot[1] - 5), "turning spot\n(50, 0), 40 cm up", color=PATH, size=9)
    note(ax, (spot[0] + 8, spot[1] + 33), "nothing seen within 40 cm\n(TURN_CLEARANCE)", color=PATH, size=8.5)

    # The arm's base and room axes.
    ax.add_patch(Circle((0, 0), 13, fc="#dfe3e8", ec="#8a9098", lw=1, zorder=2))
    note(ax, (0, 0), "base", size=8.5, ha="center")
    arrow(ax, (0, 0), (32, 0), color=AXIS_X, lw=2.2)
    arrow(ax, (0, 0), (0, 32), color=AXIS_Y, lw=2.2)
    note(ax, (33, -3), "x (in front)", color=AXIS_X, size=9.5)
    note(ax, (-1.5, 30), "y (left)", color=AXIS_Y, size=9.5, ha="right")
    note(ax, (-3, -4), "z points\nup, out of\nthe page", color=AXIS_Z, size=8, ha="right", va="top")

    # The top, its holders and its own axes.
    c = cm(CENTRE[:2])
    a, n = ALONG[:2], NORMAL[:2]
    half_l, half_t = cm(SIZE[0]) / 2, cm(SIZE[2]) / 2
    corners = [
        c + a * half_l + n * half_t,
        c - a * half_l + n * half_t,
        c - a * half_l - n * half_t,
        c + a * half_l - n * half_t,
    ]
    ax.add_patch(Polygon(corners, fc=TOP, ec=TOP_EDGE, zorder=4))
    for end in (1, -1):
        middle = c + a * end * (half_l - 1.0)
        ax.add_patch(
            Rectangle(
                (middle[0] - 2.9, middle[1] - 2.8), 5.7, 5.5, fc=GREY, ec=GREY_EDGE, alpha=0.7, zorder=3
            )
        )
    note(ax, (c[0], c[1] + 9), "table top, standing on its long edge", color=TOP_EDGE, size=9.5, ha="center")
    note(ax, (c[0] + 16, c[1] - 1), "holders\n(never seen)", color=FAINT, size=8)
    arrow(ax, c, c + a * 16, color=AXIS_X, lw=1.6, scale=11)
    arrow(ax, c, c - n * 12, color=AXIS_Y, lw=1.6, scale=11)
    note(ax, (c[0] - 17, c[1] - 3), "along", color=AXIS_X, size=8.5, ha="right")
    note(ax, (c[0] + 3, c[1] - 7), "−normal: its face\nlooks back at the arm", color=AXIS_Y, size=8)
    note(ax, (c[0] - 26, c[1] - 12), "centre\n(−1.3, 54.0)\n8.3 cm up", color=INK2, size=8.5, ha="right")

    # The legs.
    for x, y in LEGS:
        ax.add_patch(Rectangle((cm(x) - 1.45, cm(y) - 1.45), 2.9, 2.9, fc=LEG, ec="#1c5cab", zorder=4))
    note(
        ax,
        (cm(0.19), cm(-0.83)),
        "four legs, standing where the table goes\n(used by make tilt, obstacles here)",
        color=LEG,
        size=8.5,
        ha="center",
    )

    title(ax, "The room from above, seed 1. Centimetres.")
    save(fig, "room_from_above.png")


def survey_views():
    fig, (top, side) = plt.subplots(1, 2, figsize=(13.5, 6.4), gridspec_kw={"width_ratios": [1.05, 1]})

    clean(top, -104, 104, -104, 104)
    top.add_patch(Wedge((0, 0), 100, 0, 360, width=65, fc="#f1f0ea", ec="none", zorder=0))
    top.add_patch(Circle((0, 0), 13, fc="#dfe3e8", ec="#8a9098", zorder=2))
    for azimuth in SURVEY_AZIMUTHS_DEG:
        heading = np.array([math.cos(math.radians(azimuth)), math.sin(math.radians(azimuth))])
        camera, target = heading * cm(SURVEY_CAMERA_RADIUS), heading * cm(SURVEY_LOOK_RADIUS)
        top.plot(*camera, "o", color=PATH, ms=7, zorder=5)
        arrow(top, camera, target, color=PATH, lw=1.4, scale=10)
    c = cm(CENTRE[:2])
    top.add_patch(Rectangle((c[0] - 12.2, c[1] - 1), 24.4, 2, fc=TOP, ec=TOP_EDGE, zorder=4))
    for x, y in LEGS:
        top.add_patch(Rectangle((cm(x) - 1.45, cm(y) - 1.45), 2.9, 2.9, fc=LEG, ec="#1c5cab", zorder=4))
    # The four close views of step 1b, 40 cm from the top's centre.
    toward = -CENTRE.copy()
    toward[2] = 0.0
    toward /= np.linalg.norm(toward)
    along = np.cross(WORLD_Z, toward)
    for d in (
        WORLD_Z + 0.8 * toward,
        WORLD_Z + 0.8 * toward + 0.5 * along,
        WORLD_Z + 0.8 * toward - 0.5 * along,
        WORLD_Z + 0.2 * toward,
    ):
        camera = cm(CENTRE + 0.40 * d / np.linalg.norm(d))
        top.plot(*camera[:2], "s", color=TOP, ms=7, zorder=6)
        arrow(top, camera[:2], c, color=TOP, lw=1.1, scale=9)
    note(
        top,
        (-102, 102),
        "● 8 survey views: camera 30 cm out, 60 cm up,\n   looking at the floor 65 cm out",
        color=PATH,
        size=9,
        va="top",
    )
    note(
        top,
        (-102, -84),
        "■ 4 close views of the top,\n   each 40 cm from its centre",
        color=TOP,
        size=9,
        va="top",
    )
    note(top, (0, -3.5), "base", size=8, ha="center")
    title(top, "a) Where the camera looks from, seen from above")

    clean(side, -8, 120, -8, 75)
    floor(side, -8, 120)
    side.add_patch(Rectangle((-4, 0), 8, 18, fc="#dfe3e8", ec="#8a9098", zorder=2))
    camera = np.array([30.0, 60.0])
    target = np.array([65.0, 0.0])
    down = math.atan2(camera[1] - target[1], target[0] - camera[0])
    half = math.atan(math.tan(math.radians(30)) * 240 / 320)
    for edge_angle in (down - half, down + half):
        reach = camera[1] / math.tan(edge_angle)
        side.plot([camera[0], camera[0] + reach], [camera[1], 0], color=PATH, lw=0.9, ls="--")
        note(side, (camera[0] + reach, -3.5), f"{camera[0] + reach:.0f}", color=PATH, size=8.5, ha="center")
    side.add_patch(
        Polygon(
            [
                camera,
                (camera[0] + camera[1] / math.tan(down - half), 0),
                (camera[0] + camera[1] / math.tan(down + half), 0),
            ],
            fc=PATH,
            alpha=0.08,
            ec="none",
        )
    )
    arrow(side, camera, target, color=PATH, lw=1.8)
    side.plot(*camera, "o", color=PATH, ms=9, zorder=6)
    side.plot([camera[0], camera[0] + 22], [camera[1], camera[1]], color=FAINT, lw=0.8)
    side.add_patch(Wedge(camera, 14, -math.degrees(down), 0, fc="none", ec=INK2, lw=0.8))
    note(side, (camera[0] + 15, camera[1] - 4), f"{math.degrees(down):.1f}° below level", size=9)
    dimension(side, 24, 0, 60, "60 cm up", side="left")
    side.plot([0, 30], [66, 66], color=INK2, lw=0.8)
    note(side, (15, 68.5), "30 cm out", size=9, ha="center")
    note(side, (66, 6), "aims at 65 cm", color=PATH, size=9)
    note(
        side,
        (60, 40),
        "the picture covers the floor\nfrom about 37 to 112 cm out\n(320 × 240 pixels, 60° wide)",
        size=9,
    )
    note(side, (0, 21), "base", size=8.5, ha="center")
    title(side, "b) One survey view, from the side")
    save(fig, "survey_views.png")


def pixel_to_point():
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    clean(ax, -4, 64, -14, 22)
    # Seen from above the camera: x to the right in the picture, z straight out.
    ax.plot(0, 0, "o", color=INK, ms=8, zorder=6)
    note(ax, (-1, -2.8), "camera", size=9, ha="center")
    f = 10.0
    ax.plot([f, f], [-10, 10], color=INK2, lw=2)
    note(ax, (f, 11.5), "the picture", size=9, ha="center")
    ax.plot([0, 58], [0, 0], color=FAINT, lw=0.8, ls="--")
    note(ax, (58.5, 0), "optical axis", color=FAINT, size=8.5)
    u = 2.5
    ax.plot(f, u, "s", color=TOP, ms=8, zorder=6)
    point = np.array([48.0, u * 48.0 / f])
    ax.plot([0, point[0]], [0, point[1]], color=TOP, lw=1.6)
    ax.plot(*point, "o", color=TOP, ms=10, zorder=6)
    ax.add_patch(Rectangle((46.5, -10), 3, 40, fc=TOP, alpha=0.18, ec="none"))
    note(ax, (f + 1.0, u + 3.2), "pixel column u = 220\n(the middle is cx = 160)", color=TOP_EDGE, size=9)
    dimension(
        ax,
        52.5,
        0,
        point[1],
        "x = (u − cx) · z / fx\n  = (220 − 160) · 0.40 / 277\n  = 0.087 m",
        color=TOP_EDGE,
    )
    arrow(ax, (0, -8), (48, -8), color=INK2, lw=1.0, style="<|-|>", scale=8)
    note(ax, (24, -10.5), "z = the depth the camera reports for that pixel = 0.40 m", size=9, ha="center")
    note(
        ax,
        (-3, 19),
        "fx = 277 pixels: how many pixels one metre spans, one metre away\n"
        "(320 pixels across a 60° view: 160 / tan 30° = 277)",
        size=9,
    )
    note(
        ax,
        (22, -13.2),
        "the same for the rows gives y. Then camera_to_world, the camera's pose, turns (x, y, z) into room coordinates.",
        size=9,
        ha="center",
    )
    save(fig, "pixel_to_point.png")


def board_box():
    fig, (front, side) = plt.subplots(1, 2, figsize=(13, 6.2), gridspec_kw={"width_ratios": [1.5, 1]})

    # Seen from the arm, looking along +y: room x to the right, z up.
    clean(front, -24, 27, -5, 24)
    floor(front, -24, 27)
    half_l, width = cm(SIZE[0]) / 2, cm(SIZE[1])
    front.add_patch(
        Rectangle((-half_l, 0.1), 2 * half_l, width, fc=TOP, ec=TOP_EDGE, lw=1.2, zorder=3, alpha=0.9)
    )
    rng = np.random.default_rng(3)
    dots = np.column_stack((rng.uniform(-half_l, half_l, 260), rng.uniform(0.3, width, 260)))
    front.scatter(dots[:, 0], dots[:, 1], s=2.5, color="#7a2e0e", alpha=0.45, zorder=4)
    for end in (1, -1):
        x = end * (half_l - 2.4)
        front.add_patch(
            Rectangle((x - 2.85, 0), 5.7, cm(HOLDER_HEIGHT), fc=GREY, ec=GREY_EDGE, alpha=0.85, zorder=5)
        )
    note(front, (-half_l - 0.6, 3.2), "holder", color=INK2, size=8.5, ha="right")
    centre = np.array([0.0, cm(CENTRE[2])])
    front.plot(*centre, "o", color=INK, ms=7, zorder=8)
    note(
        front,
        (centre[0] - 1, centre[1] - 1.2),
        "centre\n8.3 cm up",
        size=9,
        ha="right",
        va="top",
        color=INK,
        box=True,
    )
    arrow(front, centre, (centre[0], cm(EDGE[2])), color=AXIS_Z, lw=2.4)
    edge = np.array([0.0, cm(EDGE[2])])
    front.plot(*edge, "o", color=PATH, ms=9, zorder=8)
    note(
        front,
        (0.9, (centre[1] + edge[1]) / 2 + 0.6),
        "up × (width / 2)\n= (0, 0, 1) × 8.25 cm",
        color=AXIS_Z,
        size=9,
        box=True,
    )
    note(
        front,
        (0.9, edge[1] + 2.3),
        "edge = centre + up × width / 2\n= 8.3 + 8.25 = 16.6 cm up",
        color=PATH,
        size=9.5,
        weight="bold",
    )
    arrow(front, centre, (centre[0] - 9, centre[1]), color=AXIS_X, lw=2)
    note(front, (centre[0] - 9.3, centre[1] + 1.5), "along", color=AXIS_X, size=9, ha="center", box=True)
    front.plot(centre[0] + 3.2, centre[1] - 1.2, marker="$\\otimes$", ms=13, color=AXIS_Y, zorder=8)
    note(
        front,
        (centre[0] + 4.4, centre[1] - 1.2),
        "normal: into the page,\naway from the arm",
        color=AXIS_Y,
        size=8.5,
        box=True,
    )
    front.plot([-half_l, half_l], [-2.2, -2.2], color=INK2, lw=0.8)
    note(front, (0, -3.6), "length 24.4 cm", size=9, ha="center")
    dimension(front, half_l + 4.5, 0.1, width + 0.1, "width\n16.5 cm")
    note(front, (-23.5, 22.5), "dots: the points the camera saw on the face", color="#7a2e0e", size=9)
    title(front, "a) The fitted box, seen from the arm")

    # Seen from the side, along x: the thickness and the lean.
    clean(side, -22, 16, -5, 24)
    floor(side, -22, 16)
    t = cm(SIZE[2])
    side.add_patch(Rectangle((-t / 2, 0.1), t, width, fc=TOP, ec=TOP_EDGE, zorder=3))
    lean = math.radians(5)
    corners = np.array([(-t / 2, 0.1), (t / 2, 0.1), (t / 2, width + 0.1), (-t / 2, width + 0.1)])
    turn = np.array([[math.cos(lean), -math.sin(lean)], [math.sin(lean), math.cos(lean)]])
    side.add_patch(
        Polygon((corners - [0, 0.1]) @ turn.T + [0, 0.1], fc="none", ec=BAD, ls="--", lw=1.2, zorder=2)
    )
    arrow(side, (0, 8.3), (6, 8.3), color=AXIS_Y, lw=2)
    note(side, (6.4, 8.3), "normal\n(level when upright)", color=AXIS_Y, size=8.5)
    note(
        side,
        (-21.5, 21),
        "leaning more than 5° (dashed) →\nthe arm refuses (TOP_MAX_TILT)",
        color=BAD,
        size=9,
    )
    side.plot([-t / 2, t / 2], [-2.2, -2.2], color=INK2, lw=0.8)
    note(side, (0, -3.6), "thickness 1.9 cm", size=9, ha="center")
    note(side, (-21.5, 15), "tilt = arcsin(| z part of normal |)\nseed 1: 0.0°", size=9)
    arrow(side, (-15, 0.5), (-15, 6), color=AXIS_Z, lw=1.4, scale=10)
    note(side, (-14.3, 3.5), "z", color=AXIS_Z, size=9)
    title(side, "b) Seen from the side")
    save(fig, "board_box.png")


def plan_checks():
    fig, ax = plt.subplots(figsize=(12.5, 7.4))
    clean(ax, 0, 50, 0, 30)

    def box(x, y, w, h, text, colour=PATH, fill="white", size=9.5, weight="normal"):
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.4", fc=fill, ec=colour, lw=1.4
            )
        )
        note(ax, (x + w / 2, y + h / 2), text, color=INK, size=size, ha="center", weight=weight)

    box(0.5, 25.5, 14, 3.6, "Is the turning spot clear?\nnothing seen within 40 cm\nof (50, 0)")
    box(0.5, 18.8, 14, 4.4, "Find wrist 1's axis\nat the spot, from a trial pose\n→ (0.267, 0.964, 0)")
    arrow(ax, (7.5, 25.5), (7.5, 23.2), color=FAINT, lw=1.4)
    box(0.5, 12.6, 14, 4.0, "Two grips to try:\nA: tool x along +along\nB: tool x along −along")
    arrow(ax, (7.5, 18.8), (7.5, 16.6), color=FAINT, lw=1.4)

    checks = [
        ("1", "Reach 8 cm above the edge?", "note which way the wrist is flipped"),
        ("2", "Reach the lifted pose, 20.5 cm up?", "same wrist side"),
        ("3", "Hang it at the spot, edge along the axis?", "two ways round: least wrist 3 first"),
        ("4", "Turn wrist 1 by 90° from there?", "end stop, and a collision check every 2°"),
        ("5", "Work out the carry", "22 poses on an arc round the base"),
    ]
    x0, y = 19.5, 27.0
    note(ax, (x0, 29.4), "for grip A, then grip B:", color=PATH, size=10, weight="bold")
    for i, (number, question, detail) in enumerate(checks):
        top = y - i * 4.4
        box(x0, top - 3.2, 17.5, 3.2, f"{number}.  {question}\n{detail}", size=9.2)
        if i < len(checks) - 1:
            arrow(ax, (x0 + 8.75, top - 3.2), (x0 + 8.75, top - 4.4), color=GOOD, lw=1.4)
            note(ax, (x0 + 9.2, top - 3.8), "yes", color=GOOD, size=8)
        if i < 4:
            arrow(ax, (x0 + 17.5, top - 1.6), (39.5, top - 1.6), color=BAD, lw=1.1)
    arrow(ax, (14.5, 14.6), (x0, 25.4), color=FAINT, lw=1.4, rad=-0.15)
    box(
        39.5,
        10.5,
        10,
        16.0,
        "no:\ntry the other grip,\nkeeping the reason",
        colour=BAD,
        fill="#fbeeee",
        size=9.2,
    )
    box(
        39.5,
        0.8,
        10,
        7.0,
        "both grips failed:\nstop, and say why.\nThe top has not\nbeen touched.",
        colour=BAD,
        fill="#fbeeee",
        size=9.2,
    )
    arrow(ax, (44.5, 10.5), (44.5, 7.8), color=BAD, lw=1.1)
    box(
        x0,
        0.8,
        17.5,
        3.4,
        "Route: approach, pick, lifted,\ncarry poses, wrist side → steps 3–7",
        colour=GOOD,
        fill="#eef8ee",
        size=9.4,
        weight="bold",
    )
    arrow(ax, (x0 + 8.75, y - 4 * 4.4 - 3.2), (x0 + 8.75, 4.2), color=GOOD, lw=1.4)
    note(
        ax,
        (0.5, 9.5),
        "Everything here is done on the\nrobot's model. The real arm does\nnot move until a Route comes out.",
        color=INK2,
        size=9.5,
        va="top",
    )
    save(fig, "plan_checks.png")


def gripper_side(ax, tool_z, gap, board_x=0.0, alpha=1.0):
    """The gripper seen along the board's edge: the body, and a finger either side, pads marked."""
    ax.add_patch(Rectangle((-2.2, tool_z), 4.4, 9, fc="#c9ccd1", ec="#8a9098", alpha=alpha, zorder=5))
    ax.add_patch(Rectangle((-5.5, tool_z - 5), 11, 5, fc=GRIP, ec=GRIP, alpha=alpha, zorder=6))
    for side in (1, -1):
        inner = board_x + side * gap / 2
        left = inner if side > 0 else inner - 1.2
        ax.add_patch(
            Rectangle((left, tool_z - 17), 1.2, 12, fc=FINGER, ec=GRIP, lw=0.6, alpha=alpha, zorder=6)
        )
        for row in (13.5, 15.9):
            pad_x = inner - 0.15 if side > 0 else inner - 0.0
            ax.add_patch(
                Rectangle(
                    (pad_x, tool_z - row - 0.9), 0.15, 1.8, fc="#2b2b28", ec="none", alpha=alpha, zorder=7
                )
            )
    ax.plot([-3.5, 3.5], [tool_z, tool_z], color=INK, lw=1.6, zorder=8)
    ax.plot(0, tool_z, "o", color=INK, ms=4, zorder=9)


def board_side(ax, bottom, alpha=1.0, z=3):
    t = cm(SIZE[2])
    ax.add_patch(Rectangle((-t / 2, bottom), t, cm(SIZE[1]), fc=TOP, ec=TOP_EDGE, alpha=alpha, zorder=z))


def holders_side(ax):
    t = cm(SIZE[2])
    for side in (1, -1):
        inner = side * (t / 2 + 0.15)
        left = inner if side > 0 else inner - 2
        ax.add_patch(Rectangle((left, 0), 2, cm(HOLDER_HEIGHT), fc=GREY, ec=GREY_EDGE, zorder=4))


def grip_moves():
    fig, axes = plt.subplots(1, 4, figsize=(14.5, 7.2), gridspec_kw={"width_ratios": [1, 1, 1, 1.25]})
    edge_z = cm(EDGE[2])
    pick_z, approach_z = cm(PICK[2, 3]), cm(APPROACH[2, 3])
    thickness = cm(SIZE[2])
    panels = [
        ("a) Open, and go above", approach_z, thickness + 3.0, "fingers open to\n1.9 + 3 = 4.9 cm"),
        ("b) Straight down 8 cm", pick_z, thickness + 3.0, "fingertips 5 cm\nbelow the edge"),
        (
            "c) Close",
            pick_z,
            thickness,
            "told to close to 1.9 − 0.4\n= 1.5 cm; they stop on\nthe board and squeeze",
        ),
    ]
    for ax, (name, tool_z, gap, text) in zip(axes[:3], panels, strict=True):
        clean(ax, -13, 13, -3, 49)
        floor(ax, -13, 13, depth=3)
        board_side(ax, 0.1)
        holders_side(ax)
        gripper_side(ax, tool_z, gap)
        level(ax, -12, 12, edge_z)
        note(ax, (-12.5, tool_z + 1.2), f"tool0 {tool_z:.1f}", size=8.5)
        note(ax, (0, -2.3), text, size=8.8, ha="center", va="top")
        title(ax, name)
    arrow(axes[0], (8, approach_z - 2), (8, pick_z - 2), color=PATH, lw=1.6)

    ax = axes[3]
    clean(ax, -13, 22, -3, 49)
    floor(ax, -13, 22, depth=3)
    board_side(ax, 0.1)
    holders_side(ax)
    gripper_side(ax, pick_z, thickness)
    for z, label in (
        (edge_z, "edge 16.6 (measured)"),
        (pick_z, "tool0 28.6"),
        (approach_z, "approach 36.6"),
        (pick_z - 17, "fingertips 11.6"),
    ):
        level(ax, -12, 12, z)
        note(ax, (12.3, z), label, size=8.5)
    ax.plot([6.8, 12], [approach_z, approach_z], color=FAINT, lw=0.8)
    dimension(ax, 7.5, pick_z, approach_z, "8 cm\nTOP_APPROACH", color=PATH)
    dimension(ax, -9.5, pick_z - 17, pick_z, "17 cm\nFINGERTIP_OFFSET", side="left", color=INK)
    dimension(ax, -4.3, edge_z, pick_z, "12", side="left", color=TOP_EDGE)
    dimension(ax, 4.2, pick_z - 17, edge_z, "5 cm\nTOP_INSERTION", color=TOP_EDGE)
    note(ax, (-12.5, 45.5), "pads at 13.5 and 15.9 cm from tool0:\nboth rows on the board", size=8.5)
    note(ax, (-12.5, 8.6), "holders\n5.5 cm", color=INK2, size=8)
    title(ax, "d) The numbers, seed 1 (cm above the floor)")
    save(fig, "grip_moves.png")


def frame_arrows(ax, origin, x_dir, y_dir, length, labels, colours, lw=2.0):
    for direction, label, colour in zip((x_dir, y_dir), labels, colours, strict=True):
        tip = np.asarray(origin) + np.asarray(direction) * length
        arrow(ax, origin, tip, color=colour, lw=lw, scale=11)
        note(ax, tip + np.asarray(direction) * 2.6, label, color=colour, size=8.5, ha="center", box=True)


def hold_frames():
    """The board's frame and the tool's frame, hanging and flat. Seen along the gripped edge."""
    fig, (hang, flat) = plt.subplots(1, 2, figsize=(12.5, 6.4))
    t, w = cm(SIZE[2]), cm(SIZE[1])

    # Hanging: out to the right, up the page.
    clean(hang, -24, 30, -4, 42)
    edge = np.array([0.0, 20.0])
    centre = edge - [0, w / 2]
    tool = edge + [0, 12]
    hang.add_patch(Rectangle((-t / 2, edge[1] - w), t, w, fc=TOP, ec=TOP_EDGE, zorder=3, alpha=0.9))
    hang.add_patch(Rectangle((-5.5, tool[1] - 5), 11, 5, fc=GRIP, alpha=0.35, zorder=2))
    hang.plot(*centre, "o", color=INK, ms=6, zorder=8)
    hang.plot(*tool, "o", color=INK, ms=6, zorder=8)
    frame_arrows(hang, centre, (0, 1), (1, 0), 6, ("up", "normal"), (AXIS_Y, AXIS_Z))
    frame_arrows(hang, tool, (0, -1), (1, 0), 5, ("tool z", "tool y"), (AXIS_Z, AXIS_Y))
    hang.plot([-1, -1], [centre[1], tool[1]], color=PATH, lw=0, zorder=1)
    dimension(hang, -4.5, centre[1], tool[1], "20.2 cm along\nthe board's up", side="left", color=PATH)
    arrow(hang, (-20, 0), (-20, 8), color=FAINT, lw=1.2, scale=10)
    note(hang, (-19.3, 4), "room z", color=FAINT, size=8.5)
    note(
        hang,
        (10, 31),
        "H, written in the board's own axes:\n  position (0, 0.202, 0)\n  tool z = −(board up)\n  tool y = board normal",
        color=PATH,
        size=9.5,
        va="top",
    )
    note(
        hang,
        (10, 12),
        "Here the board's up is room z,\nso the tool is also 20.2 cm\nup in the room.",
        size=9,
        va="top",
    )
    title(hang, "a) Hanging, just after the grip")

    # Flat: the same board turned a quarter turn, away from the arm.
    clean(flat, -24, 30, -4, 44)
    edge = np.array([0.0, 18.0])
    centre = edge + [w / 2, 0]
    tool = edge - [12, 0]
    flat.add_patch(Rectangle((edge[0], edge[1] - t / 2), w, t, fc=TOP, ec=TOP_EDGE, zorder=3, alpha=0.9))
    flat.add_patch(Rectangle((tool[0], tool[1] - 5.5), 5, 11, fc=GRIP, alpha=0.35, zorder=2))
    flat.plot(*centre, "o", color=INK, ms=6, zorder=8)
    flat.plot(*tool, "o", color=INK, ms=6, zorder=8)
    frame_arrows(flat, centre, (-1, 0), (0, 1), 6, ("up", "normal"), (AXIS_Y, AXIS_Z))
    frame_arrows(flat, tool, (1, 0), (0, 1), 5, ("tool z", "tool y"), (AXIS_Z, AXIS_Y))
    arrow(
        flat,
        (tool[0], tool[1] - 3.5),
        (centre[0], centre[1] - 3.5),
        color=PATH,
        lw=1.0,
        style="<|-|>",
        scale=8,
    )
    note(
        flat,
        ((tool[0] + centre[0]) / 2, centre[1] - 5.5),
        "still 20.2 cm along the board's up",
        color=PATH,
        size=9,
        ha="center",
    )
    ghost = centre + [0, 20.2]
    flat.add_patch(Circle(ghost, 1.2, fc="none", ec=BAD, ls="--", lw=1.4))
    flat.plot([centre[0], ghost[0]], [centre[1], ghost[1]], color=BAD, ls="--", lw=1)
    note(
        flat,
        (ghost[0] + 1.8, ghost[1]),
        "“20.2 cm up in the room”\nwould put the tool here: wrong",
        color=BAD,
        size=9,
    )
    arrow(flat, (-20, 0), (-20, 8), color=FAINT, lw=1.2, scale=10)
    note(flat, (-19.3, 4), "room z", color=FAINT, size=8.5)
    note(
        flat,
        (-22, 41),
        "Same H. The board's up now points\nsideways in the room, so tool · H⁻¹\nstill finds the board.",
        size=9,
        va="top",
    )
    title(flat, "b) Flat, after the turn")
    save(fig, "hold_frames.png")


def lift_out():
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 8.4))
    edge_z = cm(EDGE[2])
    lift = cm(HEIGHT + LIFT_CLEAR)
    for ax, raised, name in zip(
        axes, (0.0, lift), ("a) Gripped, in the holders", "b) Lifted 20.5 cm"), strict=True
    ):
        clean(ax, -18, 26, -3, 62)
        floor(ax, -18, 26, depth=3)
        holders_side(ax)
        board_side(ax, 0.1 + raised)
        gripper_side(ax, cm(PICK[2, 3]) + raised, cm(SIZE[2]))
        level(ax, -2, 7, edge_z)
        for z, label in (
            (0.1 + raised, "bottom edge"),
            (edge_z + raised, "top edge"),
            (cm(PICK[2, 3]) + raised, "tool0"),
        ):
            note(
                ax, (8.0, z + (1.2 if label == "top edge" and raised == 0 else 0)), f"{label} {z:.1f}", size=9
            )
        title(ax, name)
        note(ax, (4.5, 7.5), "holders 5.5 cm (never seen)", color=INK2, size=8.5)
    ax = axes[1]
    dimension(ax, -4, 0.1, edge_z, "board height\n16.5 cm", side="left", color=TOP_EDGE)
    dimension(ax, -4, edge_z, 0.1 + lift, "4 cm\nLIFT_CLEAR", side="left", color=PATH)
    arrow(ax, (-12, cm(PICK[2, 3]) - 4), (-12, cm(PICK[2, 3]) + lift - 4), color=PATH, lw=1.6)
    note(
        ax, (-12.6, cm(PICK[2, 3]) + lift / 2 - 4), "whole thing\nup 20.5 cm", color=PATH, size=9, ha="right"
    )
    note(
        axes[0],
        (-17.5, 58),
        "The fingers reached the top edge freely,\nso whatever holds the board is lower than\n16.6 cm. Lift the bottom edge past 16.6,\nplus 4 cm, and the board is out.",
        size=9.2,
        va="top",
    )
    save(fig, "lift_out.png")


def carry_arc():
    fig, (top, side) = plt.subplots(1, 2, figsize=(14, 6.8), gridspec_kw={"width_ratios": [1.1, 1]})
    clean(top, -22, 75, -44, 72)
    top.add_patch(Circle((0, 0), 13, fc="#dfe3e8", ec="#8a9098", zorder=2))
    note(top, (0, 0), "base", size=8.5, ha="center")
    centres = np.array([cm((pose @ np.linalg.inv(HELD))[:3, 3]) for pose in CARRY])
    start = cm((LIFTED @ np.linalg.inv(HELD))[:3, 3])
    top.plot(centres[:, 0], centres[:, 1], color=PATH, lw=1.2, zorder=3)
    top.plot([start[0], centres[-1, 0]], [start[1], centres[-1, 1]], color=BAD, lw=1.1, ls="--", zorder=2)
    middle = np.array([start[0], start[1]]) + (centres[-1, :2] - start[:2]) * 0.52
    note(
        top,
        (middle[0] - 1, middle[1] - 1),
        "a straight line would pass\n36 cm from the base",
        color=BAD,
        size=8.5,
        ha="right",
        va="top",
    )
    for k, pose in enumerate(CARRY):
        board = pose @ np.linalg.inv(HELD)
        c, a, n = cm(board[:3, 3]), board[:3, 0], board[:3, 2]
        top.plot(*c[:2], "o", color=PATH, ms=3.5, zorder=4)
        if k % 3 == 0 or k == len(CARRY) - 1:
            half_l, half_t = cm(SIZE[0]) / 2, cm(SIZE[2]) / 2
            corners = [
                c[:2] + a[:2] * half_l + n[:2] * half_t,
                c[:2] - a[:2] * half_l + n[:2] * half_t,
                c[:2] - a[:2] * half_l - n[:2] * half_t,
                c[:2] + a[:2] * half_l - n[:2] * half_t,
            ]
            top.add_patch(
                Polygon(
                    corners, fc=TOP, ec=TOP_EDGE, alpha=0.35 if 0 < k < len(CARRY) - 1 else 0.95, zorder=5
                )
            )
            x_dir = pose[:3, 0]
            arrow(top, c[:2], c[:2] + x_dir[:2] * 7, color=AXIS_X, lw=1.1, scale=8, z=6)
    radius0, radius1 = np.hypot(*start[:2]), np.hypot(*centres[-1, :2])
    note(top, (start[0] - 3, start[1] + 6), f"start: {radius0:.0f} cm out, at 91.4°", size=9, ha="center")
    note(
        top,
        (centres[-1, 0] + 2, centres[-1, 1] - 8),
        f"end: {radius1:.0f} cm out, at 0°\n(the turning spot)",
        size=9,
    )
    note(
        top,
        (-21, -16),
        "22 poses, one every 5° of the tool's turn.\nThe centre moves evenly in distance and angle.\nRed arrows: the tool's x, along the gripped edge.\nIt turns −104.9° about the vertical on the way:\nthe base gives −91.4°, wrist 3 the other 13.6°.",
        size=9,
        va="top",
    )
    title(top, "a) From above: the board's centre on an arc")

    # Heights, pose by pose.
    side.set_facecolor(BG)
    labels = ["lifted"] + [str(k) for k in range(len(CARRY))]
    tool_z = [cm(LIFTED[2, 3])] + [cm(p[2, 3]) for p in CARRY]
    board_z = [cm((LIFTED @ np.linalg.inv(HELD))[2, 3])] + [
        cm((p @ np.linalg.inv(HELD))[2, 3]) for p in CARRY
    ]
    bottom_z = [z - cm(SIZE[1]) / 2 for z in board_z]
    xs = np.arange(len(labels))
    side.plot(xs, tool_z, "o-", color=INK, ms=3.5, lw=1.4, label="tool0")
    side.plot(xs, board_z, "o-", color=TOP, ms=3.5, lw=1.4, label="board centre")
    side.plot(xs, bottom_z, "o", color=TOP_EDGE, ms=3, lw=1, ls="--", label="board's bottom edge")
    side.axhline(cm(EDGE[2]), color=FAINT, lw=0.8, ls=":")
    side.text(
        len(xs) - 0.5,
        cm(EDGE[2]) + 0.8,
        "where the top edge stood, 16.6",
        color=FAINT,
        fontsize=8.5,
        ha="right",
    )
    for values, fmt in ((tool_z, "{:.1f}"), (board_z, "{:.1f}"), (bottom_z, "{:.1f}")):
        side.annotate(
            fmt.format(values[0]),
            (0, values[0]),
            textcoords="offset points",
            xytext=(-4, -12),
            fontsize=8.5,
            color=INK2,
            ha="center",
        )
        side.annotate(
            fmt.format(values[-1]),
            (xs[-1], values[-1]),
            textcoords="offset points",
            xytext=(0, 6),
            fontsize=8.5,
            color=INK2,
            ha="center",
        )
    side.annotate(
        "pose 0 lifts it 3 cm,\nto the turning spot's height",
        (1, board_z[1]),
        xytext=(4, 42),
        fontsize=9,
        color=PATH,
        arrowprops={"arrowstyle": "-|>", "color": PATH, "lw": 1},
    )
    side.set_xticks(xs[::3], labels[::3], fontsize=8.5)
    side.set_ylim(0, 60)
    side.set_ylabel("cm above the floor", color=INK2)
    side.set_xlabel("pose along the carry", color=INK2)
    for spine in ("top", "right"):
        side.spines[spine].set_visible(False)
    side.grid(axis="y", color="#e8e7e1", lw=0.8)
    side.legend(frameon=False, fontsize=9, loc="lower right")
    title(side, "b) Heights along the way")
    save(fig, "carry_arc.png")


def turn_direction():
    """In the arm's own upright plane: the two quarter turns wrist 1 could make."""
    fig, ax = plt.subplots(figsize=(11.5, 7.6))
    clean(ax, -8, 95, -4, 92)
    floor(ax, -8, 95, depth=4)
    ax.add_patch(Rectangle((-5, 0), 10, 16, fc="#dfe3e8", ec="#8a9098"))
    note(ax, (0, 18), "base", size=8.5, ha="center")
    w1 = np.array([38.2, 62.0])
    t, w = cm(SIZE[2]), cm(SIZE[1])

    def turn(offset, way):
        """(out, up) about wrist 1: away maps to (−up, out), towards to (up, −out)."""
        return np.array([-offset[1], offset[0]]) if way == "away" else np.array([offset[1], -offset[0]])

    ax.add_patch(Circle(w1, 24.2, fc="none", ec="#d9d8d0", ls=":", lw=1))
    ax.add_patch(Circle(w1, 39.8, fc="none", ec="#d9d8d0", ls=":", lw=1))
    for way, colour, alpha in (("start", INK2, 1.0), ("away", GOOD, 1.0), ("towards", BAD, 0.75)):
        tool = w1 + ([10, -10] if way == "start" else turn(np.array([10, -10]), way))
        edge = w1 + ([10, -22] if way == "start" else turn(np.array([10, -22]), way))
        reach = (edge - tool) / 12
        far = edge + reach * w
        side = np.array([-reach[1], reach[0]]) * t / 2
        ax.add_patch(
            Polygon(
                [edge + side, far + side, far - side, edge - side],
                fc=TOP,
                ec=colour,
                lw=1.6,
                alpha=alpha,
                zorder=4,
            )
        )
        ax.plot(
            [w1[0], tool[0]],
            [w1[1], tool[1]],
            color="#8a9098",
            lw=5,
            alpha=alpha,
            solid_capstyle="round",
            zorder=3,
        )
        ax.plot([tool[0], edge[0]], [tool[1], edge[1]], color=GRIP, lw=3, alpha=alpha, zorder=3)
        ax.plot(*tool, "o", color=INK, ms=4, zorder=6)
        arrow(ax, tool, tool + reach * 7, color=AXIS_Z, lw=1.4, scale=9, z=7)
    ax.add_patch(Circle(w1, 2.0, fc=PATH, ec="white", zorder=8))
    note(ax, (w1[0] - 3, w1[1] + 3.5), "wrist 1 (38.2, 62.0)", color=PATH, size=9.5, ha="right")
    note(ax, (50, 17), "start: hanging, edge 40 cm up", color=INK2, size=9.5)
    note(
        ax,
        (66, 78),
        "−90°: swings away from the arm ✓\nedge ends 72 cm up, 60.2 out\ntool reaches (0.964, −0.267, 0): outward",
        color=GOOD,
        size=9.5,
    )
    note(
        ax,
        (-6, 34),
        "+90°: swings back into the arm ✗\ntool would reach back at the base",
        color=BAD,
        size=9.5,
    )
    arrow(ax, w1 + [16, -18], w1 + [22, 12], color=GOOD, lw=1.6, rad=0.35)
    arrow(ax, w1 + [4, -24], w1 + [-20, -14], color=BAD, lw=1.4, rad=-0.35)
    note(
        ax,
        (w1[0] + 25, w1[1] - 30),
        "dotted: circles the gripped edge (24 cm)\nand the far edge (40 cm) move on",
        color=FAINT,
        size=8.5,
    )
    note(
        ax,
        (-6, 90),
        "The arm's own upright plane: across = out from the base along the plane, up = height. cm. Arrows: tool z.",
        size=9.5,
    )
    save(fig, "turn_direction.png")


def flat_check():
    fig, (tilt, timeline) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1, 1.4]})
    clean(tilt, -16, 22, -6, 20)
    angle = math.radians(8)
    length, thick = 24.0, 1.9
    direction = np.array([math.cos(angle), math.sin(angle)])
    normal = np.array([-math.sin(angle), math.cos(angle)])
    origin = np.array([-10.0, 2.0])
    corners = [
        origin,
        origin + direction * length,
        origin + direction * length + normal * thick,
        origin + normal * thick,
    ]
    tilt.add_patch(Polygon(corners, fc=TOP, ec=TOP_EDGE, zorder=3))
    centre = origin + direction * length / 2 + normal * thick / 2
    arrow(tilt, centre, centre + normal * 12, color=AXIS_Z, lw=2)
    tilt.plot([centre[0], centre[0]], [centre[1], centre[1] + 13], color=FAINT, lw=1, ls="--")
    tilt.add_patch(Wedge(centre, 7, 90, 90 + math.degrees(angle), fc="none", ec=INK2, lw=1))
    note(tilt, (centre[0] - 4.5, centre[1] + 13.5), "normal", color=AXIS_Z, size=9, ha="center")
    note(tilt, (centre[0] + 0.8, centre[1] + 14), "straight up", color=FAINT, size=9)
    note(
        tilt,
        (-15.5, -2.5),
        "board = tool · H⁻¹    normal = column 2 of board\ntilt = arccos(| z part of normal |)\nflat: normal = (0, 0, ±1) → arccos 1 = 0°\ndrawn here 8° off; seed 1 came out 0.1°",
        size=9.2,
        va="top",
    )
    title(tilt, "a) How flat, by the arm's own reckoning")

    clean(timeline, 0, 34, -6, 8)
    events = [
        (0, 9.4, "turn wrist 1, −90°, 7.9 s\nrecording every\njoint reading", TOP),
        (9.8, 13.0, "tilt\ncheck", PATH),
        (13.4, 24.2, "hold still 5 s\n(HOLD_FLAT), recording\nevery joint reading", PATH),
        (24.6, 33.8, "fingers still\nfeel it? then\nreport", GOOD),
    ]
    for x0, x1, text, colour in events:
        timeline.add_patch(
            FancyBboxPatch(
                (x0, 0),
                x1 - x0,
                4,
                boxstyle="round,pad=0.02,rounding_size=0.3",
                fc="white",
                ec=colour,
                lw=1.5,
            )
        )
        note(timeline, ((x0 + x1) / 2, 2), text, size=8.8, ha="center", color=INK)
    note(
        timeline,
        (0, -1.5),
        "Report, per joint: moved (highest angle − lowest), net turn,\npeak effort during the turn, average effort while held flat.",
        size=9.2,
        va="top",
    )
    title(timeline, "b) After the turn")
    save(fig, "flat_check.png")


def main():
    steps_at_a_glance()
    room_from_above()
    survey_views()
    pixel_to_point()
    board_box()
    plan_checks()
    grip_moves()
    hold_frames()
    lift_out()
    carry_arc()
    turn_direction()
    flat_check()


if __name__ == "__main__":
    main()
