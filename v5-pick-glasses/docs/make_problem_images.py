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


DRAWINGS = {
    "the-five-problems": five_problems,
    "problem-1-what-is-asked": problem_1,
}


def main() -> None:
    for draw in DRAWINGS.values():
        draw()


if __name__ == "__main__":
    main()
