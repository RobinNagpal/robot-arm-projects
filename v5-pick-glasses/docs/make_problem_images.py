"""Draw the diagrams that belong to the problem statements.

These are different in kind from the ones `make_images.py` draws, and the
difference is worth stating. Those plot what the project's own functions
return, so they cannot drift from the code. These describe problems that are
not built yet, so there is no function to call. They are drawn from the
geometry written in the problem documents beside them, and the numbers in both
places have to be kept in step by hand.

    python docs/make_problem_images.py

Needs matplotlib, which is not a dependency of the project itself.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle  # noqa: E402

IMAGES = Path(__file__).resolve().parent.parent / "images"

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


DRAWINGS = {
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
