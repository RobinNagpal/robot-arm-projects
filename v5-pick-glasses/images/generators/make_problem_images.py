"""Draw the diagrams that belong to the problem statements.

These are different in kind from the ones `make_images.py` draws, and the
difference is worth stating. Those plot what the project's own functions
return, so they cannot drift from the code. These describe problems that are
not built yet, so there is no function to call. They are drawn from the
geometry written in the problem documents beside them, and the numbers in both
places have to be kept in step by hand.

    python images/generators/make_problem_images.py

Needs matplotlib, which is not a dependency of the project itself.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle  # noqa: E402

IMAGES = Path(__file__).resolve().parents[2] / "images"

INK = "#22272e"
MUTED = "#8b949e"
GLASS = "#4c8fd6"
WARN = "#d9694b"
GOOD = "#5aa469"
PAPER = "#ffffff"


def _new(width: float, height: float):
    figure, axes = plt.subplots(figsize=(width, height))
    figure.patch.set_facecolor(PAPER)
    axes.set_facecolor(PAPER)
    return figure, axes


def _save(figure, name: str) -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    figure.savefig(IMAGES / name, dpi=150, bbox_inches="tight", facecolor=PAPER)
    plt.close(figure)
    print(f"wrote images/{name}")


def _bare(axes) -> None:
    axes.set_xticks([])
    axes.set_yticks([])
    for side in axes.spines.values():
        side.set_visible(False)


# --------------------------------------------------------- the five problems


def five_problems() -> None:
    """The ladder: one panel per problem, each adding one difficulty.

    A table on its own does not show that the problems *contain* each other,
    and that is the point of the ordering.
    """
    figure, axes = plt.subplots(1, 5, figsize=(15.5, 3.6))
    figure.patch.set_facecolor(PAPER)

    titles = [
        "1. One glass",
        "2. Many, one kind",
        "3. Too close",
        "4. Several kinds",
        "5. Unknown\nproportions",
    ]
    adds = [
        "the whole pipeline,\nnothing in the way",
        "which pixels are\nwhich glass",
        "move them apart\nwithout lifting",
        "a different rule\nper glass",
        "a rule for a glass\nnobody measured",
    ]
    built = [True, False, False, False, False]

    # Where the glasses stand in each panel, and how wide each one is.
    scenes = [
        [(0.50, 0.50, 0.11)],
        [(0.25, 0.62, 0.10), (0.52, 0.30, 0.10), (0.75, 0.66, 0.10), (0.44, 0.78, 0.10)],
        [(0.34, 0.50, 0.11), (0.50, 0.46, 0.11), (0.70, 0.62, 0.11)],
        [(0.26, 0.60, 0.13), (0.50, 0.34, 0.08), (0.74, 0.64, 0.10)],
        [(0.26, 0.60, 0.15), (0.50, 0.34, 0.06), (0.74, 0.64, 0.12)],
    ]

    for index, (axis, title, add, scene) in enumerate(zip(axes, titles, adds, scenes, strict=True)):
        _bare(axis)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        # Equal aspect, or a glass seen from above comes out as an ellipse.
        axis.set_aspect("equal")
        axis.add_patch(
            Rectangle((0.06, 0.16), 0.88, 0.70, fill=False, ec=MUTED, lw=1.0, zorder=1)
        )

        for x, y, r in scene:
            # Problem 5 is the one where the proportions vary, so its glasses
            # are drawn as outlines rather than as one repeated shape.
            style = dict(fc="none", ec=GLASS, lw=1.6) if index == 4 else dict(fc=GLASS, alpha=0.55, ec=GLASS)
            axis.add_patch(Circle((x, y), r, zorder=3, **style))

        if index == 2:
            # The pair that is too close, and the drag that fixes it.
            axis.add_patch(
                FancyArrowPatch(
                    (0.50, 0.46), (0.50, 0.22), arrowstyle="-|>", mutation_scale=13,
                    color=WARN, lw=1.8, zorder=4,
                )
            )
            axis.text(0.55, 0.30, "drag", color=WARN, fontsize=8, va="center", zorder=5)

        if index == 3 or index == 4:
            for x, y, _radius in scene:
                axis.text(x, y, "?", ha="center", va="center", fontsize=11, color=INK, zorder=5)

        axis.set_title(title, fontsize=10.5, color=INK, pad=9)
        axis.text(0.5, 0.045, add, ha="center", va="center", fontsize=8.2, color=MUTED)
        axis.text(
            0.5, 0.925, "built" if built[index] else "not built yet",
            ha="center", va="center", fontsize=7.6,
            color=GOOD if built[index] else MUTED,
        )

    figure.suptitle(
        "Each problem takes away something the one before it could assume",
        fontsize=11.5, color=INK, y=1.03,
    )
    figure.tight_layout()
    _save(figure, "the-five-problems.png")


# ------------------------------------------------------------- problem 1


def problem_1() -> None:
    """One glass, and the four things about it nobody has told the arm.

    The point of the picture is that the start state is not "a glass at
    (x, y)". It is a table the arm has never looked at.
    """
    figure, axes = _new(9.6, 3.9)
    _bare(axes)
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)

    # left: what is on the table
    axes.add_patch(Rectangle((0.03, 0.18), 0.40, 0.66, fill=False, ec=MUTED, lw=1.0))
    axes.text(0.23, 0.88, "what is there", ha="center", fontsize=10.5, color=INK)

    # a glass, side on, with every dimension marked unknown
    body = [(0.19, 0.28), (0.19, 0.62), (0.27, 0.70), (0.27, 0.28)]
    axes.add_patch(plt.Polygon(body, closed=False, fill=False, ec=GLASS, lw=2.0))
    axes.plot([0.19, 0.27], [0.28, 0.28], color=GLASS, lw=2.0)

    axes.annotate(
        "", xy=(0.155, 0.28), xytext=(0.155, 0.70),
        arrowprops=dict(arrowstyle="<->", color=WARN, lw=1.2),
    )
    axes.text(0.145, 0.49, "how tall?", ha="right", va="center", fontsize=8.6, color=WARN)
    axes.annotate(
        "", xy=(0.19, 0.745), xytext=(0.27, 0.745),
        arrowprops=dict(arrowstyle="<->", color=WARN, lw=1.2),
    )
    axes.text(0.23, 0.775, "how wide?", ha="center", fontsize=8.6, color=WARN)
    axes.text(0.30, 0.60, "what shape?", ha="left", va="center", fontsize=8.6, color=WARN)
    axes.text(0.30, 0.40, "how heavy?", ha="left", va="center", fontsize=8.6, color=WARN)
    axes.plot([0.08, 0.40], [0.28, 0.28], color=INK, lw=1.4)
    axes.text(0.23, 0.225, "the table, at a known height", ha="center", fontsize=8, color=MUTED)

    # middle: the arrow
    axes.add_patch(
        FancyArrowPatch(
            (0.455, 0.51), (0.565, 0.51), arrowstyle="-|>", mutation_scale=18,
            color=INK, lw=1.6,
        )
    )
    axes.text(0.51, 0.565, "measure,\nthen act", ha="center", fontsize=8.6, color=INK)

    # right: the end state
    axes.add_patch(Rectangle((0.59, 0.18), 0.38, 0.66, fill=False, ec=MUTED, lw=1.0))
    axes.text(0.78, 0.88, "what has to happen", ha="center", fontsize=10.5, color=INK)

    axes.plot([0.63, 0.94], [0.30, 0.30], color=INK, lw=1.4)
    axes.add_patch(Rectangle((0.69, 0.30), 0.20, 0.035, fc=MUTED, alpha=0.5, ec=MUTED))
    for peg in (0.735, 0.795, 0.855):
        axes.plot([peg, peg], [0.335, 0.40], color=MUTED, lw=1.6)
    # the glass, upside down over the middle peg
    upside = [(0.755, 0.66), (0.755, 0.335), (0.835, 0.335), (0.835, 0.66)]
    axes.add_patch(plt.Polygon(upside, closed=False, fill=False, ec=GOOD, lw=2.0))
    axes.plot([0.755, 0.835], [0.66, 0.66], color=GOOD, lw=2.0)
    axes.text(0.795, 0.70, "mouth down, over a peg", ha="center", fontsize=8.6, color=GOOD)
    axes.text(0.78, 0.245, "the rack, found by its marker", ha="center", fontsize=8, color=MUTED)

    figure.suptitle(
        "Problem 1: one glass, and nothing known about it in advance",
        fontsize=12, color=INK, y=0.99,
    )
    _save(figure, "problem-1-what-is-asked.png")


# ------------------------------------------------------------- problem 2


def problem_2_merged_in_the_picture() -> None:
    """Two glasses that touch in the picture are far apart on the table.

    This is the whole argument for clustering on the table rather than in the
    image, and it is hard to believe from a sentence.
    """
    figure, (camera, plan) = plt.subplots(1, 2, figsize=(10.4, 4.0))
    figure.patch.set_facecolor(PAPER)

    # --- what the camera sees
    _bare(camera)
    camera.set_xlim(0, 1)
    camera.set_ylim(0, 1)
    camera.set_title("what one camera sees", fontsize=10.5, color=INK, pad=8)
    camera.add_patch(Rectangle((0.12, 0.14), 0.76, 0.72, fill=False, ec=MUTED, lw=1.0))

    near = [(0.38, 0.24), (0.38, 0.68), (0.56, 0.68), (0.56, 0.24)]
    far = [(0.50, 0.30), (0.50, 0.62), (0.64, 0.62), (0.64, 0.30)]
    camera.add_patch(plt.Polygon(far, closed=True, fc=GLASS, alpha=0.35, ec=GLASS, lw=1.5))
    camera.add_patch(plt.Polygon(near, closed=True, fc=GLASS, alpha=0.65, ec=GLASS, lw=1.5))
    camera.annotate(
        "", xy=(0.38, 0.79), xytext=(0.64, 0.79),
        arrowprops=dict(arrowstyle="<->", color=WARN, lw=1.4),
    )
    camera.text(
        0.51, 0.835, "one blob, 260 mm wide", ha="center", fontsize=9, color=WARN,
    )
    camera.text(
        0.50, 0.075,
        "no glass is that wide, and\nconnected components cannot tell",
        ha="center", fontsize=8.4, color=MUTED,
    )

    # --- what is actually on the table
    _bare(plan)
    plan.set_xlim(0, 1)
    plan.set_ylim(0, 1)
    plan.set_aspect("equal")
    plan.set_title("what is on the table, seen from above", fontsize=10.5, color=INK, pad=8)
    plan.add_patch(Rectangle((0.12, 0.20), 0.76, 0.60, fill=False, ec=MUTED, lw=1.0))

    a, b = (0.40, 0.36), (0.62, 0.63)
    for centre in (a, b):
        plan.add_patch(Circle(centre, 0.075, fc=GLASS, alpha=0.55, ec=GLASS, lw=1.5))
    plan.plot([a[0], b[0]], [a[1], b[1]], color=GOOD, lw=1.4, ls=(0, (4, 3)))
    plan.text(
        0.54, 0.51, "180 mm apart", fontsize=9, color=GOOD,
        ha="left", va="bottom", rotation=0,
    )
    # the camera, and the line of sight that puts them one behind the other
    plan.plot([0.16], [0.16], marker="s", ms=7, color=INK)
    plan.text(0.16, 0.11, "camera", ha="center", fontsize=8, color=INK)
    for centre in (a, b):
        plan.plot([0.16, centre[0]], [0.16, centre[1]], color=MUTED, lw=0.9, ls=":")
    plan.text(
        0.50, 0.87,
        "they only overlap from where the camera happened to be",
        ha="center", fontsize=8.4, color=MUTED,
    )

    figure.suptitle(
        "Problem 2: overlapping in the picture is not touching on the table",
        fontsize=12, color=INK, y=1.02,
    )
    figure.tight_layout()
    _save(figure, "problem-2-merged-in-the-picture.png")


def problem_2_where_can_the_camera_stand() -> None:
    """Which side of a glass the camera may be put, once there are several.

    Problem 1 could stand anywhere. Here each other glass casts a wedge the
    camera may not be in, and the arm's reach cuts off the rest.
    """
    figure, axes = _new(6.6, 6.0)
    _bare(axes)
    axes.set_xlim(-0.05, 1.05)
    axes.set_ylim(-0.05, 1.05)
    axes.set_aspect("equal")

    base = (0.5, -0.02)
    target = (0.50, 0.52)
    others = [(0.24, 0.62), (0.72, 0.66), (0.58, 0.30)]
    radius = 0.045

    # the band of reach
    for r, label in ((0.34, None), (0.82, "the arm's comfortable reach")):
        axes.add_patch(Circle(base, r, fill=False, ec=MUTED, lw=1.0, ls=(0, (5, 4))))
        if label:
            axes.text(0.5, base[1] + r + 0.02, label, ha="center", fontsize=8.2, color=MUTED)

    # a wedge behind each other glass: the camera may not look through it
    import math as _math

    for other in others:
        dx, dy = other[0] - target[0], other[1] - target[1]
        span = _math.hypot(dx, dy)
        middle = _math.degrees(_math.atan2(dy, dx))
        half = _math.degrees(_math.asin(min(1.0, (radius * 2.2) / span)))
        wedge = plt.matplotlib.patches.Wedge(
            target, 0.46, middle - half, middle + half, fc=WARN, alpha=0.16, ec="none"
        )
        axes.add_patch(wedge)

    for other in others:
        axes.add_patch(Circle(other, radius, fc=MUTED, alpha=0.5, ec=MUTED))
    axes.add_patch(Circle(target, radius, fc=GLASS, alpha=0.75, ec=GLASS, lw=1.6))
    axes.text(
        target[0] + 0.055, target[1] + 0.055, "the glass to measure",
        ha="left", fontsize=8.6, color=GLASS,
    )

    # two camera positions: one that works, one that does not
    good_at = (0.50 - 0.30, 0.52 - 0.05)
    bad_at = (0.50 + 0.26, 0.52 - 0.28)
    axes.plot(*good_at, marker="s", ms=8, color=GOOD)
    axes.text(
        good_at[0] - 0.02, good_at[1] + 0.055, "reachable, and\nnothing behind",
        ha="center", fontsize=8.2, color=GOOD,
    )
    axes.plot([good_at[0], target[0]], [good_at[1], target[1]], color=GOOD, lw=1.3)

    axes.plot(*bad_at, marker="s", ms=8, color=WARN)
    axes.text(
        bad_at[0] + 0.055, bad_at[1] - 0.005, "another glass\nin the frame",
        ha="left", va="center", fontsize=8.2, color=WARN,
    )
    axes.plot([bad_at[0], target[0]], [bad_at[1], target[1]], color=WARN, lw=1.3, ls=(0, (4, 3)))

    axes.plot(*base, marker="^", ms=10, color=INK)
    axes.text(base[0], base[1] - 0.045, "arm base", ha="center", fontsize=8.4, color=INK)

    axes.set_title(
        "Problem 2: where the camera may stand, once there are several glasses",
        fontsize=11.5, color=INK, pad=12,
    )
    _save(figure, "problem-2-where-can-the-camera-stand.png")


# ------------------------------------------------------------- problem 3

# The room a two-finger gripper needs round a glass, as a radius from the
# glass's middle: half the open jaw, plus the finger, plus a little. Kept here
# beside the picture it is drawn in, and stated in problem-3/problem.md.
CLEARANCE_MM = 70.0
GLASS_MM = 75.0


def problem_3_the_room_a_gripper_needs() -> None:
    """Why two glasses that are not touching can still be un-grippable.

    The gap that matters is not between the glasses. It is between one glass
    and everything the gripper has to put somewhere.
    """
    figure, (before, after) = plt.subplots(1, 2, figsize=(10.6, 4.6))
    figure.patch.set_facecolor(PAPER)

    scale = 1.0 / 400.0  # millimetres to axis units

    def draw(axis, centres, title, ok):
        _bare(axis)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.set_aspect("equal")
        axis.set_title(title, fontsize=10.5, color=INK, pad=8)
        for cx, cy in centres:
            axis.add_patch(
                Circle(
                    (cx, cy), (CLEARANCE_MM * scale), fill=False,
                    ec=GOOD if ok else WARN, lw=1.3, ls=(0, (4, 3)),
                )
            )
            axis.add_patch(
                Circle((cx, cy), (GLASS_MM / 2) * scale, fc=GLASS, alpha=0.6, ec=GLASS, lw=1.4)
            )
        # the jaw, drawn round the left glass
        cx, cy = centres[0]
        jaw, pad = 14 * scale, (GLASS_MM / 2 + 4) * scale
        for left_edge in (cx - pad - jaw, cx + pad):
            axis.add_patch(
                Rectangle(
                    (left_edge, cy - 22 * scale), jaw, 44 * scale,
                    fc=INK, alpha=0.75, ec="none",
                )
            )
        axis.text(
            centres[0][0], centres[0][1] + (CLEARANCE_MM + 16) * scale,
            f"{CLEARANCE_MM:.0f} mm of room needed",
            ha="center", fontsize=8.4, color=GOOD if ok else WARN,
        )
        gap = (centres[1][0] - centres[0][0]) / scale
        axis.annotate(
            "", xy=(centres[0][0], 0.18), xytext=(centres[1][0], 0.18),
            arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2),
        )
        axis.text(
            (centres[0][0] + centres[1][0]) / 2, 0.135,
            f"{gap:.0f} mm apart", ha="center", fontsize=8.6, color=INK,
        )

    draw(
        before, [(0.36, 0.55), (0.36 + 105 * scale, 0.55)],
        "before: the jaw has nowhere to go", False,
    )
    draw(
        after, [(0.30, 0.55), (0.30 + 160 * scale, 0.55)],
        "after: a 55 mm drag is enough", True,
    )

    after.add_patch(
        FancyArrowPatch(
            (0.30 + 105 * scale, 0.42), (0.30 + 160 * scale, 0.42),
            arrowstyle="-|>", mutation_scale=12, color=WARN, lw=1.6,
        )
    )
    after.text(0.30 + 132 * scale, 0.345, "drag", ha="center", fontsize=8.4, color=WARN)

    figure.suptitle(
        "Problem 3: the gap that matters is the one the gripper has to fit in",
        fontsize=12, color=INK, y=1.0,
    )
    figure.tight_layout()
    _save(figure, "problem-3-the-room-a-gripper-needs.png")


def problem_3_push_low_or_it_topples() -> None:
    """Where on a glass it may be pushed, and what decides it.

    A pushed object slides if the contact is below a/mu and tips above it,
    where a is half the base width and mu is the friction with the table. The
    number depends on the glass, so it is worked out per glass.
    """
    figure, axes = _new(9.8, 4.4)
    _bare(axes)
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)

    def glass(x0, topples):
        colour = WARN if topples else GOOD
        # a tapered glass, side on
        body = [(x0, 0.22), (x0 - 0.005, 0.74), (x0 + 0.105, 0.74), (x0 + 0.10, 0.22)]
        axes.add_patch(plt.Polygon(body, closed=False, fill=False, ec=GLASS, lw=2.0))
        axes.plot([x0, x0 + 0.10], [0.22, 0.22], color=GLASS, lw=2.0)
        return colour

    axes.plot([0.04, 0.96], [0.22, 0.22], color=INK, lw=1.6)
    axes.text(0.50, 0.16, "the table", ha="center", fontsize=8.4, color=MUTED)

    # left: pushed low, it slides
    glass(0.14, topples=False)
    axes.add_patch(
        FancyArrowPatch((0.075, 0.30), (0.135, 0.30), arrowstyle="-|>",
                        mutation_scale=14, color=GOOD, lw=2.0)
    )
    axes.text(0.19, 0.30, "pushed low: it slides", fontsize=9, color=GOOD, va="center")
    axes.annotate("", xy=(0.125, 0.22), xytext=(0.125, 0.30),
                  arrowprops=dict(arrowstyle="<->", color=GOOD, lw=1.0))
    axes.text(0.115, 0.26, "h", ha="right", va="center", fontsize=9, color=GOOD)

    # right: pushed high, it tips
    glass(0.60, topples=True)
    axes.add_patch(
        FancyArrowPatch((0.535, 0.64), (0.595, 0.64), arrowstyle="-|>",
                        mutation_scale=14, color=WARN, lw=2.0)
    )
    axes.text(0.72, 0.64, "pushed high: it tips", fontsize=9, color=WARN, va="center")
    axes.add_patch(
        FancyArrowPatch((0.70, 0.30), (0.745, 0.365), arrowstyle="-|>",
                        mutation_scale=11, color=WARN, lw=1.4,
                        connectionstyle="arc3,rad=0.4")
    )
    axes.plot([0.70], [0.22], marker="o", ms=5, color=WARN)
    axes.text(0.705, 0.185, "tips about this edge", fontsize=8, color=WARN)

    axes.text(
        0.50, 0.90,
        "it slides while   h  <  a / \u03bc"
        "      (a = half the base width,  \u03bc = friction with the table)",
        ha="center", fontsize=10, color=INK,
    )
    axes.text(
        0.50, 0.83,
        "a 60 mm base at \u03bc = 0.3 gives 100 mm;  a 45 mm base at \u03bc = 0.5 gives 45 mm,\n"
        "which is below where the gripper can reach — so that glass is refused rather than pushed",
        ha="center", fontsize=8.4, color=MUTED,
    )

    figure.suptitle(
        "Problem 3: how low the push has to be is a property of the glass",
        fontsize=12, color=INK, y=1.04,
    )
    _save(figure, "problem-3-push-low-or-it-topples.png")


# ------------------------------------------------------------- problem 4


def problem_4_one_wrong_name() -> None:
    """What a misnamed kind costs, drawn as the chain it breaks.

    In problem 1 a wrong name shows up at once as a refused grip. With several
    kinds it can be a name that is wrong and plausible, and then every step
    after it is confidently wrong.
    """
    figure, axes = _new(10.6, 3.4)
    _bare(axes)
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)

    boxes = [
        ("measure\nthe profile", GOOD, "right"),
        ("name\nthe kind", WARN, "WRONG"),
        ("choose\nthe grip", WARN, "wrong, and\nplausible"),
        ("squeeze", WARN, "wrong cap"),
        ("turn it\nover", WARN, "held too high"),
    ]
    width, gap = 0.155, 0.045
    for index, (label, colour, note) in enumerate(boxes):
        x = 0.035 + index * (width + gap)
        axes.add_patch(
            Rectangle((x, 0.42), width, 0.30, fc="none", ec=colour, lw=1.8)
        )
        axes.text(x + width / 2, 0.57, label, ha="center", va="center", fontsize=9.5, color=INK)
        axes.text(
            x + width / 2, 0.35, note, ha="center", va="top", fontsize=8.2, color=colour,
        )
        if index:
            axes.add_patch(
                FancyArrowPatch(
                    (x - gap, 0.57), (x - 0.006, 0.57), arrowstyle="-|>",
                    mutation_scale=12, color=MUTED, lw=1.3,
                )
            )

    axes.text(
        0.5, 0.88,
        "nothing downstream re-checks the name, because nothing downstream can",
        ha="center", fontsize=10, color=INK,
    )
    axes.text(
        0.5, 0.15,
        "a tumbler called stemmed is gripped at a stem that does not exist;\n"
        "the fingers close on air, or on the bowl, and the first thing that notices\n"
        "is the width check at first contact",
        ha="center", va="top", fontsize=8.4, color=MUTED,
    )
    figure.suptitle(
        "Problem 4: with several kinds, naming becomes load-bearing",
        fontsize=12, color=INK, y=1.02,
    )
    _save(figure, "problem-4-one-wrong-name.png")


# ----------------------------------------- problem 2, the solution overview


def _two_glasses(axis, near=(0.38, 0.30), far=(0.58, 0.45), r=0.10):
    """The same two overlapping silhouettes, for the three-answers panel."""
    for centre, alpha in ((far, 0.30), (near, 0.55)):
        axis.add_patch(
            plt.Polygon(
                [
                    (centre[0] - r * 0.42, centre[1] - 0.20),
                    (centre[0] - r * 0.50, centre[1] + 0.22),
                    (centre[0] + r * 0.50, centre[1] + 0.22),
                    (centre[0] + r * 0.42, centre[1] - 0.20),
                ],
                closed=True, fc=GLASS, alpha=alpha, ec=GLASS, lw=1.2,
            )
        )
    return near, far, r


def problem_2_three_answers() -> None:
    """Detection, semantic segmentation, instance segmentation.

    Three words that get used as if they meant the same thing. Only the third
    answers problem 2, and the difference is easier seen than said.
    """
    figure, axes = plt.subplots(1, 3, figsize=(11.6, 3.8))
    figure.patch.set_facecolor(PAPER)
    titles = ["detection", "semantic segmentation", "instance segmentation"]
    notes = [
        "two boxes, and they\noverlap: which pixels\nbelong to which?",
        "one region. two glasses,\nand nothing says so",
        "two regions, split along\nthe boundary. this is\nwhat problem 2 needs",
    ]
    for index, (axis, title, note) in enumerate(zip(axes, titles, notes, strict=True)):
        _bare(axis)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.add_patch(Rectangle((0.06, 0.20), 0.88, 0.62, fill=False, ec=MUTED, lw=1.0))
        near, far, r = _two_glasses(axis)

        if index == 0:
            for centre, colour in ((near, WARN), (far, GOOD)):
                axis.add_patch(
                    Rectangle(
                        (centre[0] - r * 0.55, centre[1] - 0.23), r * 1.10, 0.47,
                        fill=False, ec=colour, lw=1.8,
                    )
                )
        if index == 1:
            for centre in (near, far):
                axis.add_patch(
                    plt.Polygon(
                        [
                            (centre[0] - r * 0.42, centre[1] - 0.20),
                            (centre[0] - r * 0.50, centre[1] + 0.22),
                            (centre[0] + r * 0.50, centre[1] + 0.22),
                            (centre[0] + r * 0.42, centre[1] - 0.20),
                        ],
                        closed=True, fc=WARN, alpha=0.55, ec="none",
                    )
                )
        if index == 2:
            for centre, colour in ((far, GOOD), (near, WARN)):
                axis.add_patch(
                    plt.Polygon(
                        [
                            (centre[0] - r * 0.42, centre[1] - 0.20),
                            (centre[0] - r * 0.50, centre[1] + 0.22),
                            (centre[0] + r * 0.50, centre[1] + 0.22),
                            (centre[0] + r * 0.42, centre[1] - 0.20),
                        ],
                        closed=True, fc=colour, alpha=0.6, ec=INK, lw=1.4,
                    )
                )

        axis.set_title(title, fontsize=11, color=INK, pad=8)
        axis.text(0.5, 0.12, note, ha="center", va="top", fontsize=8.4, color=MUTED)

    figure.suptitle(
        "Three things the word \u201csegmentation\u201d is used for, on the same two glasses",
        fontsize=12, color=INK, y=1.03,
    )
    figure.tight_layout()
    _save(figure, "problem-2-three-answers.png")


def problem_2_cluster_and_fit() -> None:
    """The chosen method, in three steps.

    Points in the room, flattened onto the table, grouped by distance, and each
    group checked against the one diameter the kind is allowed to be.
    """
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 4.0))
    figure.patch.set_facecolor(PAPER)

    import numpy as _np

    rng = _np.random.default_rng(7)
    a, b = (0.40, 0.42), (0.62, 0.60)
    rad = 0.038

    def dots(centre, count=260):
        angle = rng.uniform(0, 2 * 3.14159, count)
        spread = rad * _np.sqrt(rng.uniform(0.0, 1.0, count))
        return centre[0] + spread * _np.cos(angle), centre[1] + spread * _np.sin(angle)

    ax, ay = dots(a)
    bx, by = dots(b)

    for axis in axes:
        _bare(axis)
        axis.set_xlim(0.28, 0.76)
        axis.set_ylim(0.26, 0.74)
        axis.set_aspect("equal")

    axes[0].set_title("1. every pixel, put in the room", fontsize=10.5, color=INK, pad=8)
    axes[0].scatter(_np.r_[ax, bx], _np.r_[ay, by], s=5, color=MUTED, alpha=0.8)
    axes[0].text(
        0.52, 0.295, "one blob in the picture;\ntwo clumps on the table",
        ha="center", fontsize=8.4, color=MUTED,
    )

    axes[1].set_title("2. group them by distance", fontsize=10.5, color=INK, pad=8)
    axes[1].scatter(ax, ay, s=5, color=GLASS)
    axes[1].scatter(bx, by, s=5, color=GOOD)
    axes[1].annotate(
        "", xy=(a[0] + rad * 0.9, a[1] + rad * 0.7), xytext=(b[0] - rad * 0.9, b[1] - rad * 0.7),
        arrowprops=dict(arrowstyle="<->", color=INK, lw=1.1),
    )
    axes[1].text(
        0.585, 0.44, "105 mm apart,\nedge to edge",
        ha="left", va="center", fontsize=8.4, color=INK,
    )
    axes[1].text(
        0.52, 0.295, "grouping distance 25 mm:\nsafely two groups",
        ha="center", fontsize=8.4, color=MUTED,
    )

    axes[2].set_title("3. fit a circle, and check it", fontsize=10.5, color=INK, pad=8)
    for centre, colour, width in ((a, GLASS, 76), (b, GOOD, 73)):
        axes[2].scatter(*dots(centre), s=4, color=MUTED, alpha=0.35)
        axes[2].add_patch(Circle(centre, rad, fill=False, ec=colour, lw=2.0))
        axes[2].text(
            centre[0], centre[1] - rad - 0.035, f"{width} mm",
            ha="center", fontsize=9, color=colour,
        )
    axes[2].text(
        0.52, 0.295, "the kind is 60 to 90 mm across:\nboth pass, so two glasses",
        ha="center", fontsize=8.4, color=MUTED,
    )

    figure.suptitle(
        "The chosen method: stop grouping in the picture, group on the table",
        fontsize=12, color=INK, y=1.02,
    )
    figure.tight_layout()
    _save(figure, "problem-2-cluster-and-fit.png")


def problem_2_the_waist() -> None:
    """Why splitting the blob in the picture works, and when it stops.

    Two overlapping discs have a waist. How deep it is decides whether a
    marker-based split finds two regions or one.
    """
    figure, (shape, curve) = plt.subplots(1, 2, figsize=(11.0, 4.0))
    figure.patch.set_facecolor(PAPER)

    import numpy as _np

    _bare(shape)
    shape.set_xlim(0, 130)
    shape.set_ylim(0, 80)
    shape.set_aspect("equal")
    shape.set_title("two discs overlapping, in the mask", fontsize=10.5, color=INK, pad=8)
    for cx in (40, 90):
        shape.add_patch(Circle((cx, 40), 32, fc=MUTED, alpha=0.55, ec="none"))
    shape.plot([65, 65], [40 - 20, 40 + 20], color=WARN, lw=2.2)
    shape.text(67, 40, "the waist,\n40 px = 65 mm", fontsize=8.4, color=WARN, va="center")
    shape.annotate(
        "", xy=(8, 8), xytext=(122, 8),
        arrowprops=dict(arrowstyle="<->", color=INK, lw=1.1),
    )
    shape.text(65, 12, "114 px = 185 mm  (no glass is over 105 mm)", ha="center", fontsize=8.2, color=INK)

    radius = 32.0
    gap = _np.linspace(1, 64, 200)
    ratio = _np.sqrt(_np.clip(1 - (gap / (2 * radius)) ** 2, 0, 1))
    curve.plot(gap, ratio, color=GLASS, lw=2.0)
    curve.axhline(0.7, color=MUTED, lw=1.2, ls=(0, (5, 4)))
    curve.text(2, 0.72, "the marker threshold", fontsize=8.4, color=MUTED)
    cross = 2 * radius * _np.sqrt(1 - 0.7**2)
    curve.axvspan(0, cross, color=WARN, alpha=0.12)
    curve.axvspan(cross, 64, color=GOOD, alpha=0.10)
    curve.text(cross / 2, 0.16, "one region:\nthey stay merged", ha="center", fontsize=8.4, color=WARN)
    curve.text((cross + 64) / 2, 0.16, "splits cleanly", ha="center", fontsize=8.4, color=GOOD)
    curve.plot([50], [_np.sqrt(1 - (50 / 64) ** 2)], marker="o", ms=6, color=INK)
    curve.text(
        50, _np.sqrt(1 - (50 / 64) ** 2) + 0.05, "the worked example",
        ha="center", fontsize=8.2, color=INK,
    )
    curve.set_xlabel("how far apart the two middles are, in pixels", fontsize=9, color=INK)
    curve.set_ylabel("how deep the waist is", fontsize=9, color=INK)
    curve.set_xlim(0, 64)
    curve.set_ylim(0, 1.05)
    curve.set_title("and when the split stops working", fontsize=10.5, color=INK, pad=8)
    for side in ("top", "right"):
        curve.spines[side].set_visible(False)

    figure.suptitle(
        "Splitting the blob in the picture: it works while the waist is deep enough",
        fontsize=12, color=INK, y=1.02,
    )
    figure.tight_layout()
    _save(figure, "problem-2-the-waist.png")


# ----------------------------------------- problem 3, the solution overview


def problem_3_choosing_a_destination() -> None:
    """The four tests a landing spot has to pass, drawn on the real zone.

    The numbers are the worked example in problem-3/solutions/solution-overview.md.
    """
    figure, axes = _new(7.6, 6.4)
    _bare(axes)
    axes.set_xlim(0.24, 0.74)
    axes.set_ylim(-0.50, -0.02)
    axes.set_aspect("equal")

    # the glass zone
    axes.add_patch(
        Rectangle((0.32, -0.44), 0.32, 0.36, fill=False, ec=MUTED, lw=1.2, ls=(0, (5, 4)))
    )
    axes.text(0.48, -0.072, "the glass zone, 320 x 360 mm", ha="center", fontsize=8.4, color=MUTED)

    a, b, landing = (0.40, -0.30), (0.49, -0.28), (0.535, -0.269)
    other = (0.35, -0.41)
    rad = 0.0375           # a 75 mm glass
    room = 0.070           # the room the jaw needs, from the middle

    for centre, label, colour in ((a, "A", GLASS), (b, "B", WARN), (other, "C", MUTED)):
        axes.add_patch(Circle(centre, room, fill=False, ec=colour, lw=1.0, ls=(0, (3, 3))))
        axes.add_patch(Circle(centre, rad, fc=colour, alpha=0.55, ec=colour, lw=1.4))
        axes.text(centre[0], centre[1], label, ha="center", va="center", fontsize=10, color=INK)

    # the overlap that is the problem
    axes.annotate(
        "", xy=(a[0], a[1] - 0.052), xytext=(b[0], b[1] - 0.052),
        arrowprops=dict(arrowstyle="<->", color=WARN, lw=1.3),
    )
    axes.text(
        0.445, -0.357, "92 mm apart, 140 needed",
        ha="center", va="top", fontsize=8.4, color=WARN,
    )

    # the push
    axes.add_patch(
        FancyArrowPatch(b, landing, arrowstyle="-|>", mutation_scale=14, color=GOOD, lw=2.0)
    )
    axes.add_patch(Circle(landing, rad, fill=False, ec=GOOD, lw=1.6, ls=(0, (4, 3))))
    axes.add_patch(Circle(landing, room, fill=False, ec=GOOD, lw=0.9, ls=(0, (3, 3))))
    axes.text(
        landing[0], landing[1] + 0.052, "B, after a 48 mm push",
        ha="center", fontsize=8.4, color=GOOD,
    )

    axes.annotate(
        "", xy=(a[0], a[1] + 0.055), xytext=(landing[0], landing[1] + 0.055),
        arrowprops=dict(arrowstyle="<->", color=GOOD, lw=1.0),
    )
    axes.text(0.468, -0.238, "140 mm", ha="center", va="bottom", fontsize=8.4, color=GOOD)

    axes.text(
        0.49, -0.475,
        "the landing spot passes all four tests:\n"
        "210 mm from C  \u00b7  inside the zone  \u00b7  601 mm from the base  \u00b7  clear of the rack",
        ha="center", fontsize=8.4, color=INK,
    )
    axes.text(
        0.252, -0.44, "dashed ring round each glass =\nthe 70 mm of room the jaw needs",
        fontsize=8, color=MUTED, va="top",
    )

    axes.set_title(
        "Problem 3: choosing where to push a glass to",
        fontsize=12, color=INK, pad=12,
    )
    _save(figure, "problem-3-choosing-a-destination.png")


def problem_3_friction_cone() -> None:
    """The friction cone, and what it decides about a push.

    Background for the pushing-mechanics option. A push inside the cone sticks
    and drives the object; outside it, the finger slides across the surface.
    """
    figure, (cone, spin) = plt.subplots(1, 2, figsize=(10.8, 4.4))
    figure.patch.set_facecolor(PAPER)

    import math as _math

    _bare(cone)
    cone.set_xlim(-0.5, 1.0)
    cone.set_ylim(-0.75, 0.75)
    cone.set_aspect("equal")
    cone.set_title("the friction cone at the contact", fontsize=10.5, color=INK, pad=8)

    # the surface, and the normal
    cone.plot([0, 0], [-0.6, 0.6], color=INK, lw=2.5)
    cone.text(-0.06, 0.62, "the glass's wall", ha="center", fontsize=8.4, color=INK)
    half = _math.degrees(_math.atan(0.35))
    cone.add_patch(
        plt.matplotlib.patches.Wedge((0, 0), 0.85, -half, half, fc=GOOD, alpha=0.18, ec="none")
    )
    cone.annotate("", xy=(0.85, 0), xytext=(0, 0),
                  arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.2, ls=(0, (4, 3))))
    cone.text(0.87, 0, "straight in", fontsize=8.4, color=MUTED, va="center")
    cone.text(
        0.30, 0.20, "inside the cone:\nthe finger sticks,\nand the glass goes",
        fontsize=8.2, color=GOOD,
    )

    for sign in (1, -1):
        cone.annotate(
            "", xy=(0.62 * _math.cos(_math.radians(52)), sign * 0.62 * _math.sin(_math.radians(52))),
            xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=WARN, lw=1.6),
        )
    cone.text(0.10, -0.55, "outside it: the finger\nslides across the glass", fontsize=8.2, color=WARN)
    cone.text(-0.45, 0.0, "half-angle\n= arctan \u03bc", fontsize=8.4, color=GOOD, va="center")

    # right: which way it turns
    _bare(spin)
    spin.set_xlim(-0.2, 1.2)
    spin.set_ylim(-0.6, 0.6)
    spin.set_aspect("equal")
    spin.set_title("and which way the glass turns", fontsize=10.5, color=INK, pad=8)
    spin.add_patch(Circle((0.55, 0.0), 0.28, fc=GLASS, alpha=0.45, ec=GLASS, lw=1.5))
    spin.plot([0.55], [0.0], marker="+", ms=10, color=INK)
    spin.text(0.55, -0.055, "middle", ha="center", va="top", fontsize=8, color=INK)

    spin.add_patch(
        FancyArrowPatch((0.06, 0.16), (0.27, 0.16), arrowstyle="-|>", mutation_scale=13,
                        color=WARN, lw=1.8)
    )
    spin.text(0.02, 0.26, "a push that misses\nthe middle", fontsize=8.2, color=WARN)
    spin.add_patch(
        FancyArrowPatch((0.72, 0.20), (0.80, -0.05), arrowstyle="-|>", mutation_scale=11,
                        color=WARN, lw=1.4, connectionstyle="arc3,rad=0.5")
    )
    spin.text(0.86, 0.08, "it spins", fontsize=8.4, color=WARN, va="center")

    spin.add_patch(
        FancyArrowPatch((0.06, -0.0), (0.27, -0.0), arrowstyle="-|>", mutation_scale=13,
                        color=GOOD, lw=1.8)
    )
    spin.text(0.02, -0.14, "a push through it", fontsize=8.2, color=GOOD)
    spin.text(0.55, -0.42, "slides roughly straight", ha="center", fontsize=8.4, color=GOOD)

    figure.suptitle(
        "Background: the two things contact mechanics decides about a push",
        fontsize=12, color=INK, y=1.02,
    )
    figure.tight_layout()
    _save(figure, "problem-3-friction-cone.png")


# ------------------------------------ shared: how programmed and learned mix


def where_the_learned_part_sits() -> None:
    """Four places a learned component can sit in a pipeline.

    The difference between them is not how clever the model is. It is what
    happens when the model is wrong, and that is decided by the position.
    """
    figure, axes = plt.subplots(1, 4, figsize=(14.6, 4.2))
    figure.patch.set_facecolor(PAPER)

    titles = ["as the decider", "as a proposer", "as a ranker", "as a verifier"]
    subtitles = [
        "the model's answer\nis the answer",
        "the model suggests,\nthe rules check",
        "the rules generate and\nveto, the model orders",
        "the rules act,\nthe model checks",
    ]
    costs = [
        "a wrong answer\nis acted on",
        "a wrong answer\nis rejected",
        "a wrong order costs\none extra try",
        "a wrong check costs\none extra look",
    ]
    safe = [False, True, True, True]

    for index, axis in enumerate(axes):
        _bare(axis)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.set_title(titles[index], fontsize=11, color=INK, pad=10)

        def box(y, label, colour, height=0.13, _axis=axis):
            _axis.add_patch(
                Rectangle((0.16, y), 0.68, height, fill=False, ec=colour, lw=1.8)
            )
            _axis.text(0.5, y + height / 2, label, ha="center", va="center",
                       fontsize=8.6, color=INK)

        def arrow(y0, y1, _axis=axis):
            _axis.add_patch(
                FancyArrowPatch((0.5, y0), (0.5, y1), arrowstyle="-|>",
                                mutation_scale=11, color=MUTED, lw=1.2)
            )

        if index == 0:
            box(0.70, "picture", MUTED)
            arrow(0.70, 0.60)
            box(0.47, "learned model", WARN)
            arrow(0.47, 0.37)
            box(0.24, "the arm acts", MUTED)
        if index == 1:
            box(0.70, "rules find candidates", GOOD)
            arrow(0.70, 0.60)
            box(0.47, "learned model refines", WARN)
            arrow(0.47, 0.37)
            box(0.24, "rules check the result", GOOD)
        if index == 2:
            box(0.70, "rules generate, and veto", GOOD)
            arrow(0.70, 0.60)
            box(0.47, "learned model ranks", WARN)
            arrow(0.47, 0.37)
            box(0.24, "best survivor is used", GOOD)
        if index == 3:
            box(0.70, "rules act", GOOD)
            arrow(0.70, 0.60)
            box(0.47, "learned model checks", WARN)
            arrow(0.47, 0.37)
            box(0.24, "\u201cnot sure\u201d \u2192 look again", GOOD)

        axis.text(0.5, 0.90, subtitles[index], ha="center", va="center",
                  fontsize=8.2, color=MUTED)
        axis.text(
            0.5, 0.12, costs[index], ha="center", va="top", fontsize=8.4,
            color=WARN if not safe[index] else GOOD,
        )

    figure.suptitle(
        "Where the learned part sits decides what happens when it is wrong",
        fontsize=12.5, color=INK, y=1.03,
    )
    figure.tight_layout()
    _save(figure, "where-the-learned-part-sits.png")


def open_and_closed_loop() -> None:
    """One pass against a loop that chooses its own next measurement."""
    figure, (openl, closedl) = plt.subplots(1, 2, figsize=(11.4, 4.2))
    figure.patch.set_facecolor(PAPER)

    for axis in (openl, closedl):
        _bare(axis)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)

    def box(axis, x, y, w, h, label, colour):
        axis.add_patch(Rectangle((x, y), w, h, fill=False, ec=colour, lw=1.7))
        axis.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                  fontsize=8.8, color=INK)

    openl.set_title("open loop: look once, then act", fontsize=10.5, color=INK, pad=10)
    for i, (label, colour) in enumerate(
        [("take the pictures", MUTED), ("work it all out", MUTED), ("act", MUTED)]
    ):
        box(openl, 0.10 + i * 0.30, 0.46, 0.24, 0.16, label, colour)
        if i:
            openl.add_patch(
                FancyArrowPatch((0.06 + i * 0.30, 0.54), (0.095 + i * 0.30, 0.54),
                                arrowstyle="-|>", mutation_scale=11, color=MUTED, lw=1.3)
            )
    openl.text(
        0.5, 0.30,
        "the number of pictures is fixed before the run.\n"
        "if one object is unclear, that is how it stays.",
        ha="center", va="top", fontsize=8.4, color=MUTED,
    )

    closedl.set_title("closed loop: the next picture is chosen on the way",
                      fontsize=10.5, color=INK, pad=10)
    box(closedl, 0.34, 0.74, 0.32, 0.14, "take a picture", GLASS)
    box(closedl, 0.34, 0.50, 0.32, 0.14, "work out what is clear", GLASS)
    box(closedl, 0.06, 0.26, 0.34, 0.14, "unclear: where would\nhelp most?", WARN)
    box(closedl, 0.60, 0.26, 0.34, 0.14, "clear: act", GOOD)
    closedl.add_patch(FancyArrowPatch((0.5, 0.74), (0.5, 0.645), arrowstyle="-|>",
                                      mutation_scale=11, color=MUTED, lw=1.3))
    closedl.add_patch(FancyArrowPatch((0.42, 0.50), (0.26, 0.405), arrowstyle="-|>",
                                      mutation_scale=11, color=WARN, lw=1.3))
    closedl.add_patch(FancyArrowPatch((0.58, 0.50), (0.74, 0.405), arrowstyle="-|>",
                                      mutation_scale=11, color=GOOD, lw=1.3))
    closedl.add_patch(FancyArrowPatch((0.06, 0.33), (0.34, 0.80), arrowstyle="-|>",
                                      mutation_scale=11, color=WARN, lw=1.3,
                                      connectionstyle="arc3,rad=-0.45"))
    closedl.text(0.045, 0.60, "go and look\nfrom there", fontsize=8.2, color=WARN,
                 ha="left", va="center")
    closedl.text(
        0.5, 0.16,
        "each extra look costs arm time, so the loop has a budget\n"
        "and stops when nothing is unclear or the budget is spent",
        ha="center", va="top", fontsize=8.4, color=MUTED,
    )

    figure.suptitle(
        "Feedback: deciding what to measure next, rather than measuring once",
        fontsize=12.5, color=INK, y=1.02,
    )
    figure.tight_layout()
    _save(figure, "open-and-closed-loop.png")


DRAWINGS = {
    "where-the-learned-part-sits": where_the_learned_part_sits,
    "open-and-closed-loop": open_and_closed_loop,
    "problem-3-choosing-a-destination": problem_3_choosing_a_destination,
    "problem-3-friction-cone": problem_3_friction_cone,
    "problem-2-three-answers": problem_2_three_answers,
    "problem-2-cluster-and-fit": problem_2_cluster_and_fit,
    "problem-2-the-waist": problem_2_the_waist,
    "problem-4-one-wrong-name": problem_4_one_wrong_name,
    "the-five-problems": five_problems,
    "problem-1-what-is-asked": problem_1,
    "problem-2-merged-in-the-picture": problem_2_merged_in_the_picture,
    "problem-2-where-can-the-camera-stand": problem_2_where_can_the_camera_stand,
    "problem-3-the-room-a-gripper-needs": problem_3_the_room_a_gripper_needs,
    "problem-3-push-low-or-it-topples": problem_3_push_low_or_it_topples,
}


def main() -> None:
    for draw in DRAWINGS.values():
        draw()


if __name__ == "__main__":
    main()
