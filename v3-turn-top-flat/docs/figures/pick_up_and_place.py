"""Draws the pictures in docs/approaches/pick-up-and-place.md.

Run from v3-turn-top-flat/docs/figures/:  python pick_up_and_place.py

These are sketches to explain the idea, not to scale.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parent

BG = "#fcfcfb"
INK = "#1f1f1d"
INK2 = "#52514e"
FLOOR = "#e6e4dc"
GREY = "#b4b3ab"
TOP = "#eb6834"
LEG = "#2a78d6"
GRIP = "#3d3d3a"
FINGER = "#77766f"
PATH = "#4a3aa7"
GOOD = "#0ca30c"
BAD = "#d03b3b"

plt.rcParams.update(
    {
        "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 11,
        "text.color": INK,
        "figure.facecolor": BG,
        "savefig.facecolor": BG,
    }
)

BOARD_W = 1.8  # the board's width, from the gripped edge to the far one
BOARD_T = 0.16
REACH = 1.2  # from the tool to the gripped edge


def unit(deg):
    return np.array([math.cos(math.radians(deg)), math.sin(math.radians(deg))])


def perp(u):
    return np.array([-u[1], u[0]])


def rect(a, b, half):
    n = perp((b - a) / np.linalg.norm(b - a)) * half
    return [a + n, b + n, b - n, a - n]


def scene(ax, x0, x1, y0, y1, title=None):
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((x0, y0), x1 - x0, -y0, fc=FLOOR, ec="none", zorder=0))
    ax.plot([x0, x1], [0, 0], color="#c3c2b7", lw=1.5, zorder=0)
    if title:
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=6)


def board(ax, edge, u, alpha=1.0, z=4):
    """A board gripped at ``edge``, lying along ``u`` from there."""
    ax.add_patch(
        Polygon(rect(edge, edge + u * BOARD_W, BOARD_T / 2), fc=TOP, ec="#b8491c", lw=1, alpha=alpha, zorder=z)
    )


def gripper(ax, edge, u, open_=False, alpha=1.0, z=5, arm=True):
    """Two fingers either side of ``edge``, reaching along ``u``; a stub of arm behind them."""
    tool = edge - u * REACH
    n = perp(u)
    if arm:
        ax.add_patch(Polygon(rect(tool - u * 0.9, tool, 0.13), fc="#c9ccd1", ec="#8a9098", alpha=alpha, zorder=z))
    ax.add_patch(Polygon(rect(tool, tool + u * 0.45, 0.42), fc=GRIP, ec=GRIP, alpha=alpha, zorder=z))
    gap = BOARD_T / 2 + (0.2 if open_ else 0.0) + 0.05
    for side in (1, -1):
        a = tool + u * 0.45 + n * side * gap
        ax.add_patch(Polygon(rect(a, a + u * 1.25, 0.05), fc=FINGER, ec=GRIP, lw=0.6, alpha=alpha, zorder=z))
    return tool


def arrow(ax, a, b, color=PATH, rad=0.0, lw=2, z=7, style="-|>"):
    ax.add_patch(
        FancyArrowPatch(
            a, b, arrowstyle=style, mutation_scale=16, lw=lw, color=color,
            connectionstyle=f"arc3,rad={rad}", zorder=z,
        )
    )


def note(ax, xy, text, color=INK2, size=9.5, ha="left", va="center"):
    ax.text(*xy, text, color=color, fontsize=size, ha=ha, va=va, zorder=8)


HOLDER_H = 0.6  # how high the holders' slots reach up the board


def holder(ax, x, h=HOLDER_H, alpha=1.0):
    """A holder seen end-on: the two jaws of the slot the board's end stands in.

    There is one at each end of the board. Seen along the gripped edge, as in
    every side view here, the two line up, so they are drawn once.
    """
    for left in (x - BOARD_T / 2 - 0.28, x + BOARD_T / 2):
        ax.add_patch(Rectangle((left, 0), 0.28, h, fc=GREY, ec="#8f8e87", alpha=alpha, zorder=2))


def leg(ax, x, h=1.4):
    ax.add_patch(Rectangle((x - 0.15, 0), 0.3, h, fc=LEG, ec="#1c5cab", zorder=2))


def upright(x=4.0):
    """Where the upper edge of a board standing upright in the holders is, and the way down it."""
    return np.array([x, BOARD_W]), unit(-90)


def save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


# ---------------------------------------------------------------- 1. the problem


def problem():
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4))
    scene(a, 0.2, 6.0, -0.3, 3.4, "At the start, seen from the front")
    # The board standing on one long edge, its two ends in the holders' slots.
    left, right = 1.6, 4.4
    a.add_patch(Rectangle((left, 0), right - left, BOARD_W, fc=TOP, ec="#b8491c", zorder=3))
    for x in (left - 0.2, right - 0.25):
        a.add_patch(Rectangle((x, 0), 0.45, HOLDER_H, fc=GREY, ec="#8f8e87", zorder=4))
    # The gripper coming straight down onto the middle of the upper edge.
    mid = (left + right) / 2
    a.add_patch(Rectangle((mid - 0.13, BOARD_W + 0.95), 0.26, 0.6, fc="#c9ccd1", ec="#8a9098", zorder=5))
    a.add_patch(Rectangle((mid - 0.42, BOARD_W + 0.5), 0.84, 0.45, fc=GRIP, ec=GRIP, zorder=5))
    a.add_patch(Rectangle((mid - 0.1, BOARD_W - 0.5), 0.2, 1.0, fc=FINGER, ec=GRIP, lw=0.6, zorder=6))
    note(a, (0.3, 2.95), "fingers on the middle\nof the upper edge")
    arrow(a, (1.6, 2.7), (mid - 0.15, BOARD_W + 0.1), color=INK2, lw=1, rad=0.2)
    note(a, (mid, 0.95), "table top, standing upright", ha="center")
    note(a, (4.75, 0.95), "holders, one at\neach end: heavy or\nbolted down")
    arrow(a, (4.75, 0.7), (right + 0.15, HOLDER_H * 0.6), color=INK2, lw=1, rad=-0.3)

    scene(b, 0.5, 5.5, -0.3, 3.4, "At the end")
    for x in (1.4, 4.6):
        leg(b, x)
    b.add_patch(Rectangle((1.1, 1.43), 3.8, BOARD_T, fc=TOP, ec="#b8491c", zorder=3))
    note(b, (3.0, 1.95), "table top, flat", ha="center")
    note(b, (3.0, 0.7), "four legs, already standing", ha="center")
    fig.suptitle("Upright to flat: a turn of 90°", x=0.01, y=1.04, ha="left", fontsize=13, fontweight="bold")
    save(fig, "problem.png")


# ---------------------------------------------------------------- 2. old vs new


def chip(ax, x, y, w, text, color, glyph=None):
    ax.add_patch(
        FancyBboxPatch((x, y - 0.45), w, 0.9, boxstyle="round,pad=0.02,rounding_size=0.15",
                       fc="white", ec=color, lw=1.8, zorder=2)
    )
    ax.text(x + w / 2, y - 0.17, text, ha="center", va="center", fontsize=9.5, zorder=3)
    if glyph is not None:
        centre = np.array([x + w / 2, y + 0.27])
        for i, deg in enumerate(glyph):
            u = unit(deg)
            a = centre - u * 0.1 + np.array([(i - (len(glyph) - 1) / 2) * 0.3, 0])
            ax.add_patch(Polygon(rect(a, a + u * 0.2, 0.03), fc=TOP, ec="none", zorder=3,
                                 alpha=0.35 + 0.65 * (i + 1) / len(glyph)))


def old_vs_new():
    fig, ax = plt.subplots(figsize=(13, 3.6))
    ax.set_xlim(-0.1, 14.2)
    ax.set_ylim(0.1, 3.9)
    ax.axis("off")

    ax.text(0, 3.5, "Old way", fontsize=12, fontweight="bold", color=BAD)
    steps = [("Grip", 1.1, INK2, [-90]), ("Lift", 1.1, INK2, [-90]),
             ("ONE planned move:\ncarry + turn 90°", 4.5, BAD, [-90, -60, -30, 0]),
             ("Lower", 1.1, INK2, [0]), ("Let go", 1.1, INK2, [0])]
    x = 0
    for text, w, color, glyph in steps:
        chip(ax, x, 2.75, w, text, color, glyph)
        x += w + 0.35
        if x < 9.5:
            arrow(ax, (x - 0.33, 2.75), (x - 0.03, 2.75), color=INK2, lw=1.2)
    note(ax, (x + 0.1, 2.75), "MoveIt picks the path and how fast\nit turns. The board slips.", color=BAD)

    ax.text(0, 1.75, "New way", fontsize=12, fontweight="bold", color=GOOD)
    steps = [("Check all\nposes first", 1.35, GOOD, None), ("Grip", 0.95, INK2, [-90]),
             ("Lift out of\nthe holders", 1.4, INK2, [-90]),
             ("Carry\nhanging", 1.2, INK2, [-90]), ("Turn flat\n5° steps", 1.4, GOOD, [-90, -60, -30, 0]),
             ("Carry\nflat", 1.0, INK2, [0]), ("Lower", 0.95, INK2, [0]), ("Let go", 0.95, INK2, [0])]
    x = 0
    for i, (text, w, color, glyph) in enumerate(steps):
        chip(ax, x, 1.05, w, text, color, glyph)
        x += w + 0.35
        if i < len(steps) - 1:
            arrow(ax, (x - 0.33, 1.05), (x - 0.03, 1.05), color=INK2, lw=1.2)
    note(ax, (0, 0.3), "Each move does one thing, slowly, along a path you choose.", color=GOOD)
    save(fig, "old_vs_new.png")


# ---------------------------------------------------------------- 3. the ways


def ways():
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.9))
    tags = [("A. Turn it flat in the air", "Simplest", PATH), ("B. Suction cup", "New gripper", PATH),
            ("C. Rest on stands, look again", "Slower, safer", PATH),
            ("D. Edge on two legs, tilt down", "v3's plan, part 2", GOOD)]
    for ax, (title, tag, color) in zip(axes, tags, strict=True):
        scene(ax, 0, 4.4, -0.3, 3.6, title)
        ax.text(0.05, 3.35, tag, color=color, fontsize=10, fontweight="bold")

    a = axes[0]
    pivot = np.array([1.6, 2.6])
    for i, deg in enumerate(range(-90, 1, 15)):
        board(a, pivot, unit(deg), alpha=0.15 + 0.85 * (i / 6) ** 2)
    gripper(a, pivot, unit(0), arm=False)
    arrow(a, pivot + unit(-80) * 2.05, pivot + unit(-10) * 2.05, rad=0.35)

    b = axes[1]
    holder(b, 3.0)
    edge, down = upright(3.0)
    board(b, edge, down)
    centre = edge + down * BOARD_W / 2 + perp(down) * -BOARD_T / 2
    face = -perp(down)
    b.add_patch(Polygon(rect(centre + face * 0.15, centre + face * 0.9, 0.2), fc=GRIP, zorder=5))
    b.add_patch(Polygon(rect(centre + face * 0.9, centre + face * 1.8, 0.12), fc="#c9ccd1", ec="#8a9098", zorder=5))
    b.add_patch(Polygon(rect(centre + face * 0.02, centre + face * 0.17, 0.22), fc=PATH, zorder=6))
    note(b, (0.2, 2.8), "cup on the middle\nof the face")

    c = axes[2]
    for x in (0.7, 3.2):
        c.add_patch(Rectangle((x, 0), 0.5, 0.9, fc=GREY, ec="#8f8e87", zorder=2))
    c.add_patch(Rectangle((0.5, 0.9), 3.4, BOARD_T, fc=TOP, ec="#b8491c", zorder=3))
    c.add_patch(Circle((2.2, 2.6), 0.28, fc="white", ec=INK2, lw=1.5, zorder=4))
    c.add_patch(Circle((2.2, 2.6), 0.11, fc=INK2, zorder=5))
    arrow(c, (2.2, 2.25), (2.2, 1.2), color=INK2, lw=1.2)
    note(c, (2.6, 2.6), "look again,\nthen v2's code")

    d = axes[3]
    # Legs spaced one board-width apart, so the board lands end to end on them.
    for x in (1.7, 3.2):
        leg(d, x, h=1.0)
    corner = np.array([3.3, 1.0 + BOARD_T / 2])
    for deg, alpha in ((30, 1.0), (15, 0.4), (0, 0.2)):
        edge = corner + unit(180 - deg) * BOARD_W
        board(d, edge, unit(-deg), alpha=alpha)
    gripper(d, corner + unit(150) * BOARD_W, unit(-30), arm=False)
    arrow(d, corner + unit(146) * (BOARD_W + 0.3), corner + unit(170) * (BOARD_W + 0.3), rad=0.25)
    d.add_patch(Circle(corner, 0.08, fc=PATH, zorder=8))
    note(d, (2.35, 2.7), "far edge rests on the\nfar legs; the arm tilts\nit down onto the near\nones")
    fig.tight_layout()
    save(fig, "ways.png")


# ---------------------------------------------------------------- 4. the steps


def steps():
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.2))
    axes = axes.ravel()
    edge, down = upright()
    lifted = edge + np.array([0, HOLDER_H + 0.35])
    titles = ["1. Come in above the edge", "2. Grip, check both fingers", "3. Lift straight up, clear",
              "4. Carry round, hanging", "5. Turn flat, 5° at a time", "6. Carry flat to the legs",
              "7. Lower onto the legs", "8. Let go, pull back out"]
    for ax, title in zip(axes, titles, strict=True):
        scene(ax, 1.0, 6.0, -0.3, 4.2, title)
    for ax in axes[:3]:
        holder(ax, 4.0)

    board(axes[0], edge, down)
    gripper(axes[0], edge - down * 0.8, down, open_=True)
    arrow(axes[0], edge - down * 2.3 + perp(down) * 0.6, edge - down * 1.5 + perp(down) * 0.6)
    note(axes[0], (1.2, 3.8), "fingers open, tool pointing\nstraight down at the edge")

    board(axes[1], edge, down)
    gripper(axes[1], edge, down)
    for side in (1, -1):
        axes[1].add_patch(Circle(edge + down * 0.35 + perp(down) * side * 0.15, 0.07, fc=GOOD, zorder=7))
    note(axes[1], (1.2, 3.8), "both fingertip sensors\nmust feel the board")

    board(axes[2], edge, down, alpha=0.2)
    board(axes[2], lifted, down)
    gripper(axes[2], lifted, down)
    arrow(axes[2], edge + np.array([0.45, -0.6]), lifted + np.array([0.45, -0.6]), lw=1.5)
    note(axes[2], (1.1, 2.2), "straight up until its\nlower edge clears\nthe holders; it already\nhangs straight")

    ax = axes[3]
    high = np.array([3.4, 3.2])
    board(ax, high, unit(-90))
    gripper(ax, high, unit(-90))
    arrow(ax, (1.6, 2.2), (5.4, 2.2), rad=-0.25)
    note(ax, (3.5, 0.6), "high, like a leg is carried", ha="center")

    ax = axes[4]
    pivot = np.array([2.4, 3.0])
    for i, deg in enumerate(range(-90, 1, 10)):
        board(ax, pivot, unit(deg), alpha=0.12 + 0.88 * (i / 9) ** 2)
    gripper(ax, pivot, unit(0))
    ax.add_patch(Circle(pivot, 0.08, fc=PATH, zorder=8))
    arrow(ax, pivot + unit(-80) * 2.05, pivot + unit(-10) * 2.05, rad=0.35)
    note(ax, (2.4, 0.5), "away from the arm")

    top = np.array([2.8, 1.52])
    for ax in axes[5:]:
        for x in (3.0, 5.2):
            leg(ax, x)
    board(axes[5], top + np.array([0, 1.6]), unit(0))
    gripper(axes[5], top + np.array([0, 1.6]), unit(0))
    arrow(axes[5], (1.4, 3.9), (2.6, 3.9), lw=1.5)
    note(axes[5], (3.45, 2.3), "the same as v2's\ncode from here on")

    board(axes[6], top + np.array([0, 0.9]), unit(0), alpha=0.25)
    board(axes[6], top, unit(0))
    gripper(axes[6], top, unit(0))
    arrow(axes[6], (2.0, 2.7), (2.0, 1.9), lw=1.5)

    board(axes[7], top, unit(0))
    gripper(axes[7], top - np.array([0.9, 0]), unit(0), open_=True)
    arrow(axes[7], (2.9, 2.3), (2.0, 2.3), lw=1.5)
    note(axes[7], (3.9, 3.6), "then look and\ncheck the table", ha="center")
    fig.suptitle("Way A, step by step (side view; the holders are only there in steps 1–3)",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, "steps.png")


# ---------------------------------------------------------------- 5. the swing


def swing():
    fig, ax = plt.subplots(figsize=(8, 6))
    scene(ax, -2.6, 3.4, -0.3, 5.8)
    pivot = np.array([0.0, 3.2])
    ax.add_patch(plt.matplotlib.patches.Wedge(pivot, BOARD_W + 0.1, -90, 0, fc=PATH, alpha=0.07, zorder=1))
    ax.add_patch(Circle(pivot, 2.3, fc="none", ec=PATH, ls="--", lw=1, zorder=1))
    for i, deg in enumerate(range(-90, 1, 5)):
        board(ax, pivot, unit(deg), alpha=0.08 + 0.92 * (i / 18) ** 2)
    for deg in range(-90, 1, 5):
        ax.add_patch(Circle(pivot - unit(deg) * REACH, 0.03, fc=INK2, zorder=6))
    gripper(ax, pivot, unit(-90), alpha=0.25, arm=False)
    gripper(ax, pivot, unit(0))
    ax.add_patch(Circle(pivot, 0.09, fc=PATH, zorder=9))
    arrow(ax, pivot + unit(-80) * 2.1, pivot + unit(-8) * 2.1, rad=0.35)
    note(ax, (0.5, 3.75), "pivot: the gripped edge.\nThe fingers stay here.")
    note(ax, (2.2, 1.2), "the board sweeps\nthis quarter circle")
    note(ax, (-2.5, 0.75), "keep 25 cm round the\nfingers empty (dashed)")
    note(ax, (-2.5, 5.6), "← the arm is this way")
    note(ax, (-1.95, 2.45), "the tool moves\non a small arc")
    ax.set_title("The swing: like a drawbridge, 5° per step", loc="left", fontsize=13, fontweight="bold")
    save(fig, "swing.png")


# ---------------------------------------------------------------- 6. which way the edge runs


def edge_direction():
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, good in zip(axes, (True, False), strict=True):
        ax.set_xlim(-3.2, 2.4)
        ax.set_ylim(-0.6, 4.4)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.add_patch(Circle((0, 0), 0.35, fc="#c9ccd1", ec="#8a9098", zorder=3))
        note(ax, (0, -0.5), "arm's base", ha="center")
        ax.plot([0, 0], [0.35, 3.9], color=INK2, ls=":", lw=1.2)
        note(ax, (0.1, 0.9), "line of reach")
        fingers = np.array([0, 2.3])
        along = np.array([1.0, 0]) if good else np.array([0, 1.0])
        ax.add_patch(Polygon(rect(fingers - along * 1.3, fingers + along * 1.3, 0.07), fc=TOP, zorder=4))
        flat = np.array([0, 1.0]) if good else np.array([1.0, 0])
        corners = [fingers - along * 1.3, fingers + along * 1.3,
                   fingers + along * 1.3 + flat * 1.6, fingers - along * 1.3 + flat * 1.6]
        ax.add_patch(Polygon(corners, fc="none", ec=TOP, ls="--", lw=1.5, zorder=3))
        ax.add_patch(Circle(fingers, 0.12, fc=PATH, zorder=5))
        if good:
            ax.set_title("✓  Edge across the line of reach", loc="left", color=GOOD, fontsize=13, fontweight="bold")
            note(ax, (-3.1, 1.3), "The swing is the wrist bending,\nlike an elbow. Smooth.")
            note(ax, (0.2, 4.2), "board after the swing (dashed)", size=9)
        else:
            ax.set_title("✗  Edge along the line of reach", loc="left", color=BAD, fontsize=13, fontweight="bold")
            note(ax, (-3.1, 1.3), "The swing needs the wrist to twist\nthrough a pose where two of its\n"
                 "joints line up (a singularity).\nThe path jerks or stops.")
        ax.text(-3.1, 4.3, "seen from above", color=INK2, fontsize=9)
    save(fig, "edge_direction.png")


# ---------------------------------------------------------------- 7. how hard the board pulls


def grip_load():
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    angle = np.linspace(0, 90, 300)
    series = [("Largest board, 0.48 kg", 0.48, 0.073, "#eb6834"), ("Smallest board, 0.25 kg", 0.246, 0.053, "#2a78d6")]
    for label, mass, lever, color in series:
        torque = mass * 9.81 * lever * np.abs(np.sin(np.radians(angle)))
        ax.plot(angle, torque, color=color, lw=2.2, label=label)
        ax.plot([90], [torque[-1]], "o", color=color, ms=8, mec=BG, mew=2)
        ax.text(88, torque[-1] + 0.03, f"{torque[-1]:.2f} N·m", ha="right", fontsize=9.5, color=INK2)
    ax.axhline(0.6, color=INK2, lw=1)
    ax.text(1, 0.565, "rough grip limit: 25 N squeeze, pad rows 2.4 cm apart", fontsize=9.5, color=INK2)
    ax.text(45, 0.68, "the turn", ha="center", color=INK2, fontsize=10)
    ax.set_xticks([0, 45, 90], ["hanging", "halfway", "flat"])
    ax.set_ylabel("pull trying to turn the board\nin the fingers (N·m)", color=INK2)
    ax.set_ylim(0, 0.72)
    ax.set_xlim(-2, 92)
    ax.grid(axis="y", color="#e1e0d9", lw=1)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=INK2)
    ax.set_facecolor(BG)
    ax.legend(frameon=False, loc="center left", bbox_to_anchor=(0.2, 0.6))
    ax.set_title("Hanging is free, flat is the hardest, and flat already works today",
                 loc="left", fontsize=12.5, fontweight="bold")
    save(fig, "grip_load.png")


if __name__ == "__main__":
    problem()
    old_vs_new()
    ways()
    steps()
    swing()
    edge_direction()
    grip_load()
