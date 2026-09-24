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


DRAWINGS = {"the-five-problems": five_problems}


def main() -> None:
    for draw in DRAWINGS.values():
        draw()


if __name__ == "__main__":
    main()
