"""Diagrams for solution 5 — a learned residual on the push model.

Four pictures, each about one claim the document makes.

Every glass drawn here is a real outline from ``work_cell.glasses.shapes``,
either drawn by the spawner or built at proportions ``diagram_style`` holds for
this kind, and every arrangement is one the spawner produced. No size is
written down in this file.

The numbers marked MEASURED below are not invented and not rounded from
theory. They come from running the project's own physics bench,
``problem-3-sim/bench.py``, with the programmed planner,
``problem-3-programmed/plan.py``: for each of tables 10100 to 10349, ask
``plan.choose`` for the push it would really make, make it, and compare where
the glass landed against where the push aimed it. 248 of those tables yielded
a push that touched the glass. The document says the same numbers in prose, and
says how to reproduce them.

    pixi run python images/generators/problem-3/make_05_images.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
from diagram_style import (
    CAST,
    GLASS,
    GLASS_ZONE,
    GOOD,
    INK,
    JAW_TOP,
    LABEL_SIZE,
    LOWEST_GRIP,
    MU_HIGH,
    MU_LOW,
    MUTED,
    NOTE_SIZE,
    TABLE_FRICTION,
    TITLE_SIZE,
    WARN,
    bare,
    glass_from_above,
    glass_from_the_side,
    has_room,
    new,
    push_arrow,
    pushable,
    save,
    topple_height,
)
from matplotlib.patches import Circle, Ellipse, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import build, draw, family  # noqa: E402

# --------------------------------------------------------------------------- #
# MEASURED. 248 first pushes on tables 10100-10349. See the module docstring.
# --------------------------------------------------------------------------- #

# The residual itself, in the push's own frame: along is the way the jaw moved,
# across is to its left. The glass always finishes a little short of where the
# jaw took it, because the contact has to take up and the glass settles onto
# its leading edge before it starts to travel.
LOSS_ALONG = -1.31
LOSS_ALONG_SD = 1.12
LOSS_ACROSS = -0.05
LOSS_ACROSS_SD = 0.54

# The same loss split by kind: (mean, standard deviation, how many pushes).
# One kind per table, so each kind gets about a quarter of the sample.
LOSS_BY_KIND = {
    "straight glass": (-0.49, 0.46, 63),
    "short stemmed glass": (-0.99, 0.79, 61),
    "tapered glass": (-1.32, 0.96, 63),
    "stemmed glass": (-2.44, 1.13, 61),
}

# How far the planner chooses to push, over the same 248 pushes. It takes the
# shortest push that frees the glass, so half of them are tiny.
TRAVEL_MEDIAN = 2.0
TRAVEL_P90 = 36.0
TRAVEL_LONGEST = 132.0

# The loss as a share of the push, measured rather than divided: the median of
# (loss / travel) over the short pushes and over the long ones.
SHARE_SHORT = 0.57     # pushes of 5 mm or less, 160 of them
SHARE_LONG = 0.02      # pushes of 20 mm or more, 64 of them

# What the examples buy. A ridge fit of the two residual components on the
# inputs the arm already has — how far it means to push, the glass's foot
# width, widest width and height, and which kind of glass the table holds —
# trained on the first n of a shuffled half and scored on the held-out 124,
# averaged over 40 shuffles. The y value is the root mean square distance
# between where the corrected prediction put the glass and where it went.
EXAMPLES = (0, 5, 10, 20, 40, 80, 124)
HELD_OUT_RMS = (1.83, 1.87, 1.55, 1.27, 1.12, 1.07, 1.05)
# The same held-out score for a correction that is one number, the average
# loss, fitted on 40 pushes.
MEAN_ONLY_RMS = 1.25

# Pushes per run, from problem-3-programmed/results.json: 212 pushes over the
# 50 held-out tables. This is the rate at which labelled rows arrive.
PUSHES_PER_RUN = 212 / 50

# The margin the geometric planner already carries on every destination,
# AIM_MARGIN in problem-3-programmed/plan.py. It is the thing the residual has
# to be compared against.
AIM_MARGIN = 10.0

# How many glasses are drawn for the population panel, and the seed.
POPULATION = 400
POPULATION_SEED = 5


def proportions(outline) -> tuple[float, float, float]:
    """Height, rim diameter and base fraction of a real outline, in millimetres.

    Read off the outline rather than stored, so that a glass in a picture is
    the glass the spawner drew and not a shape chosen to make the point.
    """
    radius = np.asarray(outline.radius)
    rim = 2000.0 * float(radius.max())
    return 1000.0 * outline.total_height, rim, 2000.0 * float(radius[0]) / rim


def foot_widths(count: int, seed: int) -> list[float]:
    """The foot diameter of ``count`` drawn tapered glasses, in millimetres."""
    return [2000.0 * float(outline.radius[0]) for outline, _ in family("tapered_glass", count, seed)]


# --------------------------------------------------------------------------- #
# A real crowded arrangement, laid out the way problem 3's own tables are.
# --------------------------------------------------------------------------- #

# From problem-3-sim/bench.py, which is the reference implementation for this
# problem. A table is built by placing each glass either somewhere free or
# deliberately close to one already down, between touching and having room.
CROWD_SHARE = 0.6
START_GAP = 5.0      # the least daylight between two glasses at the start
GRIP_ROOM = 70.0     # clear room the open jaw needs from a glass's middle


def widest(shape: tuple[float, float, float]) -> float:
    """The widest diameter of a glass, which is what a neighbour has to clear."""
    return shape[1]


def layout(rng: random.Random, shapes: list[tuple[float, float, float]]) -> list[tuple[float, float]] | None:
    """One attempt at a crowded table, by ``bench.py``'s own placement rule."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    placed: list[tuple[float, float, float]] = []
    for shape in shapes:
        width = widest(shape)
        for _ in range(300):
            if placed and rng.random() < CROWD_SHARE:
                px, py, pwidth = rng.choice(placed)
                near = rng.uniform((width + pwidth) / 2 + START_GAP, GRIP_ROOM + max(width, pwidth) / 2)
                angle = rng.uniform(-np.pi, np.pi)
                x, y = px + near * np.cos(angle), py + near * np.sin(angle)
            else:
                x, y = rng.uniform(x_from, x_to), rng.uniform(y_from, y_to)
            if (x_from <= x <= x_to and y_from <= y <= y_to
                    and all(np.hypot(x - qx, y - qy) >= (width + qwidth) / 2 + START_GAP
                            for qx, qy, qwidth in placed)):
                placed.append((x, y, width))
                break
        else:
            return None
    return [(x, y) for x, y, _ in placed]


def crowded_table(count: int = 5) -> tuple[list[tuple[float, float]], list[tuple[float, float, float]],
                                           list[int], int, int, np.ndarray, np.ndarray]:
    """One crowded table of one kind, and a push that gives one glass its room.

    Problem 3's own tables come from ``scene`` in ``problem-3-sim/bench.py``.
    That module imports a physics engine, which these drawing scripts do not
    load, so its placement rule is reproduced above and its crowding test,
    ``has_room``, is imported from ``diagram_style``. The glasses themselves
    are drawn by ``work_cell.glasses.shapes.draw``, exactly as the bench draws
    them, so no size in this picture was chosen by hand.

    Returns the centres, the glasses' proportions, which glasses lack room,
    which one is pushed, which neighbour crowds it, the push direction, and
    where the push aims.
    """
    for seed in range(1, 600):
        rng = random.Random(seed)
        shapes = [proportions(draw("tapered_glass", rng)[0]) for _ in range(count)]
        centres = layout(rng, shapes)
        if centres is None:
            continue
        table = [(x, y, widest(shape)) for (x, y), shape in zip(centres, shapes, strict=True)]
        crowded = [i for i, (x, y, _) in enumerate(table)
                   if not has_room((x, y), [q for k, q in enumerate(table) if k != i])]
        if not crowded:
            continue

        for index in crowded:
            others = [q for k, q in enumerate(table) if k != index]
            here = table[index]
            partner = min(others, key=lambda q: float(np.hypot(q[0] - here[0], q[1] - here[1])))
            line = np.array([table[index][0] - partner[0], table[index][1] - partner[1]])
            line = line / float(np.linalg.norm(line))
            for travel in np.arange(20.0, 140.0, 1.0):
                landing = np.array(centres[index]) + travel * line
                if not has_room(landing, others):
                    continue
                # The planner pads its destination, and the picture needs the
                # landing spot far enough from the rest to carry a label.
                if min(float(np.hypot(*np.subtract(landing, q[:2]))) for q in others) < 140.0 + AIM_MARGIN:
                    continue
                if not (GLASS_ZONE[0] + 30.0 <= landing[0] <= GLASS_ZONE[1] - 30.0
                        and GLASS_ZONE[2] + 30.0 <= landing[1] <= GLASS_ZONE[3] - 30.0):
                    continue
                return centres, shapes, crowded, index, others.index(partner) + (
                    1 if others.index(partner) >= index else 0), line, landing
    raise RuntimeError("no crowded table in the search had a glass with a clear push to room")


CENTRES, SHAPES, CROWDED, PUSHED, PARTNER, DIRECTION, LANDING = crowded_table()
ACROSS = np.array([-DIRECTION[1], DIRECTION[0]])


def zone(axis, pad: float = 30.0) -> None:
    """The part of the table glasses may stand on, and nothing else."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                             facecolor="none", edgecolor=MUTED, lw=0.9, ls=(0, (5, 4))))
    axis.set_xlim(x_from - pad, x_to + pad)
    axis.set_ylim(y_from - pad, y_to + pad)
    axis.set_aspect("equal")
    axis.set_anchor("N")
    bare(axis)


def table_panel(axis) -> None:
    """The arrangement, the crowded pair, the push, and where it is aimed."""
    zone(axis, pad=100.0)
    for index, (centre, (_, rim, fraction)) in enumerate(zip(CENTRES, SHAPES, strict=True)):
        if index == PUSHED:
            continue
        glass_from_above(axis, centre, rim, fraction,
                         colour=WARN if index in CROWDED else GLASS,
                         alpha=0.30 if index == PARTNER else 0.14)

    _, rim, fraction = SHAPES[PUSHED]
    glass_from_above(axis, CENTRES[PUSHED], rim, fraction, colour=WARN, alpha=0.12, foot=False, lw=1.2)
    glass_from_above(axis, LANDING, rim, fraction, colour=GOOD, alpha=0.26)

    gap = float(np.hypot(*np.subtract(CENTRES[PUSHED], CENTRES[PARTNER])))
    needed = GRIP_ROOM + widest(SHAPES[PARTNER]) / 2.0
    axis.plot(*zip(CENTRES[PUSHED], CENTRES[PARTNER], strict=True),
              color=WARN, lw=1.0, ls=(0, (2, 2)), zorder=5)
    middle = np.mean([CENTRES[PUSHED], CENTRES[PARTNER]], axis=0)
    sideways = ACROSS
    axis.annotate(f"{gap:.0f} mm from this neighbour;\nit needs {needed:.0f} mm from one\n"
                  f"{widest(SHAPES[PARTNER]):.0f} mm across", xy=middle,
                  xytext=middle + 130.0 * sideways, ha="center", va="center",
                  fontsize=NOTE_SIZE, color=WARN,
                  arrowprops=dict(arrowstyle="-", color=WARN, lw=0.7, shrinkA=8, shrinkB=2))

    behind = np.array(CENTRES[PUSHED]) - (rim / 2.0 + 26.0) * DIRECTION
    push_arrow(axis, behind, np.array(LANDING) - (rim / 2.0 - 4.0) * DIRECTION, colour=INK, lw=1.6, zorder=9)
    axis.annotate("before the push", xy=CENTRES[PUSHED],
                  xytext=np.array(CENTRES[PUSHED]) - 112.0 * sideways, ha="center", va="center",
                  fontsize=NOTE_SIZE, color=WARN,
                  arrowprops=dict(arrowstyle="-", color=WARN, lw=0.7, shrinkA=6, shrinkB=2))
    axis.annotate("where the model says\nthe glass will finish", xy=LANDING,
                  xytext=np.array(LANDING) - 128.0 * ACROSS, ha="center", va="center",
                  fontsize=NOTE_SIZE, color=GOOD,
                  arrowprops=dict(arrowstyle="-", color=GOOD, lw=0.7, shrinkA=8, shrinkB=2))
    axis.set_title("one real table, one push, to scale", fontsize=LABEL_SIZE, color=INK, pad=8)
    axis.text(0.5, -0.03, "the prediction and the outcome are the same circle at this scale",
              transform=axis.transAxes, ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED)


def zoom_panel(axis) -> None:
    """The residual itself, magnified, and turned so the push points right."""
    predicted = np.zeros(2)
    landed = np.array([LOSS_ALONG, LOSS_ACROSS])

    axis.set_xlim(-3.6, 3.2)
    axis.set_ylim(-3.0, 3.0)
    axis.set_aspect("equal")
    axis.set_anchor("N")
    bare(axis)

    push_arrow(axis, (-3.2, -2.3), (0.9, -2.3), colour=MUTED, lw=1.2)
    axis.text(-1.15, -2.66, "the way the push went", ha="center", fontsize=NOTE_SIZE, color=MUTED)

    # One standard deviation of the measured scatter, about the average.
    axis.add_patch(Ellipse(landed, 2 * LOSS_ALONG_SD, 2 * LOSS_ACROSS_SD, angle=0.0,
                           facecolor=WARN, alpha=0.13, edgecolor=WARN, lw=0.9, ls=(0, (3, 2))))
    axis.plot([predicted[0]] * 2, [-1.5, 1.5], color=GOOD, lw=0.9, ls=(0, (3, 3)))
    axis.plot([landed[0]] * 2, [-1.5, 1.5], color=WARN, lw=0.9, ls=(0, (3, 3)))

    for point, colour in ((predicted, GOOD), (landed, WARN)):
        axis.add_patch(Circle(point, 0.13, facecolor=colour, edgecolor=colour, zorder=7))
    push_arrow(axis, predicted, landed, colour=WARN, lw=1.5, zorder=8)

    axis.annotate("where the push aimed the glass", xy=predicted, xytext=(0.45, -1.25),
                  ha="left", va="top", fontsize=NOTE_SIZE, color=GOOD,
                  arrowprops=dict(arrowstyle="-", color=GOOD, lw=0.7, shrinkA=1, shrinkB=4))
    axis.annotate(f"where it really went:\n{abs(LOSS_ALONG):.2f} mm short along the push,\n"
                  f"{abs(LOSS_ACROSS):.2f} mm across it",
                  xy=landed, xytext=(-3.4, -0.55), ha="left", va="top",
                  fontsize=NOTE_SIZE, color=WARN,
                  arrowprops=dict(arrowstyle="-", color=WARN, lw=0.7, shrinkA=1, shrinkB=4))
    axis.annotate("one standard deviation of the\nscatter around that average",
                  xy=(landed[0], landed[1] + LOSS_ACROSS_SD), xytext=(-0.1, 1.45),
                  ha="center", fontsize=NOTE_SIZE, color=MUTED,
                  arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7, shrinkA=1, shrinkB=3))

    axis.plot([1.6, 2.6], [-2.3] * 2, color=INK, lw=1.8)
    axis.text(2.1, -2.66, "1 mm", ha="center", fontsize=NOTE_SIZE, color=INK)
    axis.set_title("the same landing spot, magnified", fontsize=LABEL_SIZE, color=INK, pad=8)
    axis.text(0.5, -0.03, f"averages over {sum(n for _, _, n in LOSS_BY_KIND.values())} measured pushes",
              transform=axis.transAxes, ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED)


def what_a_residual_is() -> None:
    figure, (left, right) = new(11.2, 5.0, columns=2)
    table_panel(left)
    zoom_panel(right)
    figure.suptitle("A residual is the gap between the prediction and the measurement",
                    fontsize=TITLE_SIZE, color=INK, y=0.99)
    save(figure, "05-what-a-residual-is.png")


# --------------------------------------------------------------------------- #
# The loss is a fixed cost, so it matters most on the shortest pushes.
# --------------------------------------------------------------------------- #

def by_kind_panel(axis) -> None:
    order = sorted(LOSS_BY_KIND.items(), key=lambda row: row[1][0])
    places = np.arange(len(order))
    means = [-row[1][0] for row in order]
    spreads = [row[1][1] for row in order]
    axis.barh(places, means, xerr=spreads, height=0.55, color=GLASS, alpha=0.55,
              edgecolor=GLASS, error_kw=dict(ecolor=MUTED, capsize=4, lw=1.0))
    axis.set_yticks(places)
    axis.set_yticklabels([f"{row[0]}\n{row[1][2]} pushes" for row in order], fontsize=NOTE_SIZE, color=INK)
    axis.set_xlabel("millimetres the glass finished short of the aim", fontsize=NOTE_SIZE, color=INK)
    axis.set_xlim(0, 4.0)
    axis.tick_params(axis="x", labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.set_title("the loss differs by kind, and a stemmed glass is the worst",
                   fontsize=LABEL_SIZE, color=INK, pad=8)
    axis.text(0.5, -0.20, "bars are averages, whiskers one standard deviation",
              transform=axis.transAxes, ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED)


def share_panel(axis) -> None:
    travel = np.linspace(TRAVEL_MEDIAN, TRAVEL_LONGEST, 400)
    axis.plot(travel, 100.0 * abs(LOSS_ALONG) / travel, color=INK, lw=1.6,
              label="the average loss, as a share of the push")
    axis.scatter([TRAVEL_MEDIAN, TRAVEL_P90], [100.0 * SHARE_SHORT, 100.0 * SHARE_LONG],
                 s=44, color=WARN, zorder=6, label="measured median, short and long pushes")
    axis.annotate(f"the planner's median push is {TRAVEL_MEDIAN:.0f} mm,\n"
                  f"and loses {100.0 * SHARE_SHORT:.0f} per cent of it",
                  xy=(TRAVEL_MEDIAN, 100.0 * SHARE_SHORT), xytext=(18, 70),
                  fontsize=NOTE_SIZE, color=WARN,
                  arrowprops=dict(arrowstyle="-|>", color=WARN, lw=0.9, shrinkA=2, shrinkB=4))
    axis.annotate(f"nine pushes in ten are under {TRAVEL_P90:.0f} mm,\n"
                  f"where the same loss is {100.0 * SHARE_LONG:.0f} per cent",
                  xy=(TRAVEL_P90, 100.0 * SHARE_LONG), xytext=(52, 26),
                  fontsize=NOTE_SIZE, color=MUTED,
                  arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9, shrinkA=2, shrinkB=4))
    axis.set_xlabel("how far the push was commanded to go, millimetres", fontsize=NOTE_SIZE, color=INK)
    axis.set_ylabel("the loss as a share of the push, per cent", fontsize=NOTE_SIZE, color=INK)
    axis.set_xlim(0, TRAVEL_LONGEST)
    axis.set_ylim(0, 100)
    axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper right", labelcolor=INK)
    axis.set_title("the same loss on every push, whatever its length",
                   fontsize=LABEL_SIZE, color=INK, pad=8)


def the_loss_is_a_fixed_cost() -> None:
    figure, (left, right) = new(11.4, 4.6, columns=2)
    by_kind_panel(left)
    share_panel(right)
    figure.suptitle("What there is to learn: a fixed loss at the start of every push",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    figure.subplots_adjust(wspace=0.32)
    save(figure, "05-the-loss-is-a-fixed-cost.png")


# --------------------------------------------------------------------------- #
# What the examples buy, and what the first few cost.
# --------------------------------------------------------------------------- #

def what_the_examples_buy() -> None:
    figure, axis = new(8.6, 5.2)
    examples = np.array(EXAMPLES, dtype=float)
    scores = np.array(HELD_OUT_RMS, dtype=float)

    axis.axhline(HELD_OUT_RMS[0], color=MUTED, lw=1.0, ls=(0, (5, 4)))
    axis.text(126, HELD_OUT_RMS[0] + 0.02, "no model at all: the physics prediction on its own",
              ha="right", fontsize=NOTE_SIZE, color=MUTED)
    axis.axhline(HELD_OUT_RMS[-1], color=MUTED, lw=1.0, ls=(0, (5, 4)))
    axis.text(126, HELD_OUT_RMS[-1] + 0.02, "the floor this fit reaches", ha="right",
              fontsize=NOTE_SIZE, color=MUTED)

    axis.plot(examples, scores, color=GOOD, lw=1.8, marker="o", ms=5, zorder=5)
    axis.scatter([EXAMPLES[1]], [HELD_OUT_RMS[1]], s=120, facecolor="none", edgecolor=WARN, lw=1.6, zorder=6)
    axis.annotate("five examples are worse than none:\nthe fit follows the noise in them",
                  xy=(EXAMPLES[1], HELD_OUT_RMS[1]), xytext=(20, 1.74),
                  fontsize=NOTE_SIZE, color=WARN,
                  arrowprops=dict(arrowstyle="-|>", color=WARN, lw=0.9, shrinkA=2, shrinkB=6))
    axis.scatter([40], [MEAN_ONLY_RMS], s=44, color=MUTED, zorder=6)
    axis.annotate("one number — the average loss — gets\nmost of the way there on its own",
                  xy=(40, MEAN_ONLY_RMS), xytext=(56, 1.42), fontsize=NOTE_SIZE, color=MUTED,
                  arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9, shrinkA=2, shrinkB=4))

    axis.set_xlabel("labelled pushes the residual was fitted on", fontsize=NOTE_SIZE, color=INK)
    axis.set_ylabel("held-out error, root mean square millimetres", fontsize=NOTE_SIZE, color=INK)
    axis.set_xlim(-4, 130)
    axis.set_ylim(0.9, 2.0)
    axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)

    runs = axis.twiny()
    runs.set_xlim(-4 / PUSHES_PER_RUN, 130 / PUSHES_PER_RUN)
    runs.set_xlabel(f"runs of the arm, at the {PUSHES_PER_RUN:.1f} pushes a run really makes",
                    fontsize=NOTE_SIZE, color=INK)
    runs.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right", "left"):
        runs.spines[side].set_color(MUTED) if side == "top" else runs.spines[side].set_visible(False)

    axis.set_title(f"Measured, not assumed: 124 held-out pushes, 40 shuffles\n"
                   f"for scale, the planner already pads every destination by {AIM_MARGIN:.0f} mm",
                   fontsize=LABEL_SIZE, color=INK, pad=26)
    save(figure, "05-what-the-examples-buy.png")


# --------------------------------------------------------------------------- #
# The one line the residual is not allowed to move.
# --------------------------------------------------------------------------- #

def side_panel(axis) -> None:
    """Two real glasses of one kind, with the height a push may not exceed."""
    spacing = 150.0
    for place, (height, rim, fraction) in ((0.0, CAST[0]), (spacing, CAST[1])):
        outline = build("tapered_glass", height=height / 1000.0, rim_diameter=rim / 1000.0,
                        base_fraction=fraction)
        drawn_height, drawn_rim, drawn_fraction = proportions(outline)
        glass_from_the_side(axis, place, drawn_height, drawn_rim, drawn_fraction, colour=GLASS, alpha=0.22)
        foot = drawn_rim * drawn_fraction
        limits = [(topple_height(foot, mu), colour) for mu, colour in ((MU_LOW, GOOD), (MU_HIGH, WARN))]
        for index, (limit, colour) in enumerate(limits):
            half = drawn_rim * (drawn_fraction + (1.0 - drawn_fraction) * limit / drawn_height) / 2.0
            axis.plot([place - half - 14, place + half + 14], [limit, limit],
                      color=colour, lw=1.4, ls=(0, (4, 3)), zorder=7)
            # At the end of its own line rather than above it, and alternating
            # ends, so that two limits close together never collide and neither
            # lands on the band's edge.
            crowded = index > 0 and limits[index - 1][0] - limit < 26.0
            right = not crowded
            axis.text(place + (half + 18 if right else -half - 18), limit, f"{limit:.0f} mm",
                      ha="left" if right else "right", va="center",
                      fontsize=NOTE_SIZE, color=colour, zorder=8)
        safe = sum(pushable(foot, mu, JAW_TOP) for mu in (MU_LOW, MU_HIGH))
        verdict = ("it can be pushed", "only if the friction is low", "it must be refused")[2 - safe]
        axis.text(place, -16, f"foot {foot:.0f} mm", ha="center", fontsize=NOTE_SIZE, color=INK)
        axis.text(place, -32, verdict, ha="center", fontsize=NOTE_SIZE,
                  color=GOOD if safe == 2 else WARN)

    # The band is drawn to the top edge of the jaw, not to the middle of it. A
    # tapered glass is wider higher up, so it meets the top edge first, and that
    # is the height the push really lands at.
    axis.axhspan(0, JAW_TOP, color=MUTED, alpha=0.16, zorder=1)
    axis.axhline(LOWEST_GRIP, color=MUTED, lw=1.0, ls=(0, (3, 3)), zorder=6)
    axis.axhline(JAW_TOP, color=INK, lw=1.4, zorder=6)
    axis.annotate(f"the jaw's middle rides at {LOWEST_GRIP:.0f} mm, but its top\n"
                  f"edge is at {JAW_TOP:.0f} mm and a tapered glass meets\n"
                  f"that first, so a limit inside this band\nmeans no safe push exists at all",
                  xy=(-100, 40), xytext=(-108, 248), ha="left", va="top",
                  fontsize=NOTE_SIZE, color=INK,
                  arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8, shrinkA=6, shrinkB=2))
    for index, (mu, colour) in enumerate(((MU_LOW, GOOD), (MU_HIGH, WARN))):
        axis.plot([-105, -85], [-54 - 15 * index] * 2, color=colour, lw=1.4, ls=(0, (4, 3)))
        axis.text(-81, -54 - 15 * index, f"tips above this line if the friction is {mu}",
                  va="center", fontsize=NOTE_SIZE, color=colour)
    axis.plot([-110, spacing + 60], [0, 0], color=INK, lw=1.2)
    axis.set_xlim(-110, spacing + 60)
    axis.set_ylim(-78, 255)
    axis.set_aspect("equal")
    bare(axis)
    axis.set_title("a wide foot leaves room to push, and 15 mm of jaw takes it away",
                   fontsize=LABEL_SIZE, color=INK, pad=8)


def population_panel(axis) -> None:
    """How many drawn glasses of this kind can be pushed at all, against friction."""
    feet = foot_widths(POPULATION, POPULATION_SEED)
    frictions = np.linspace(0.24, 0.56, 120)

    def share_at(height: float) -> list[float]:
        return [100.0 * sum(pushable(foot, mu, height) for foot in feet) / len(feet) for mu in frictions]

    wishful = share_at(LOWEST_GRIP)
    real = share_at(JAW_TOP)
    axis.plot(frictions, wishful, color=MUTED, lw=1.3, ls=(0, (4, 3)))
    axis.plot(frictions, real, color=INK, lw=1.8)
    axis.fill_between(frictions, 0, real, color=GLASS, alpha=0.14)

    # Everything is named in one block in the corner both curves have left
    # empty, so that no label and no leader line crosses either of them.
    axis.text(0.556, 106.0, f"dashed: if the push landed at the jaw's middle, {LOWEST_GRIP:.0f} mm",
              ha="right", va="top", fontsize=NOTE_SIZE, color=MUTED)
    axis.text(0.556, 96.0, f"solid: where it really lands, the jaw's top edge,\n"
                           f"{JAW_TOP:.0f} mm, which a tapered glass meets first",
              ha="right", va="top", fontsize=NOTE_SIZE, color=INK)
    marks = ((MU_LOW, GOOD, 74.0, "{:.0f} per cent of them at {}"),
             (TABLE_FRICTION, MUTED, 64.0,
              "{:.0f} per cent at {}, the simulator's own\ntable, which the arm is never told"),
             (MU_HIGH, WARN, 44.0, "none whatever at {1}"))
    for mu, colour, where, template in marks:
        value = 100.0 * sum(pushable(foot, mu, JAW_TOP) for foot in feet) / len(feet)
        axis.scatter([mu], [value], s=46, color=colour, zorder=6)
        axis.text(0.556, where, template.format(value, mu), ha="right", va="top",
                  fontsize=NOTE_SIZE, color=colour)
    axis.set_xlabel("friction between glass and table, which the arm never measures",
                    fontsize=NOTE_SIZE, color=INK)
    axis.set_ylabel(f"share of {POPULATION} drawn glasses that can be pushed at all, per cent",
                    fontsize=NOTE_SIZE, color=INK)
    axis.set_xlim(0.24, 0.56)
    axis.set_ylim(0, 112)
    axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.set_title("fifteen millimetres of jaw, and half the glasses change answer",
                   fontsize=LABEL_SIZE, color=INK, pad=8)


def the_line_the_residual_may_not_move() -> None:
    figure, (left, right) = new(11.6, 4.8, columns=2)
    side_panel(left)
    population_panel(right)
    figure.suptitle("The tipping limit is not the residual's to correct",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    figure.subplots_adjust(wspace=0.26)
    save(figure, "05-the-line-the-residual-may-not-move.png")


def main() -> None:
    gap = float(np.hypot(*np.subtract(CENTRES[PUSHED], CENTRES[PARTNER])))
    print(f"arrangement: {len(CENTRES)} drawn tapered glasses, {len(CROWDED)} of them without room; "
          f"glass {PUSHED} stands {gap:.1f} mm from glass {PARTNER}, which is "
          f"{widest(SHAPES[PARTNER]):.1f} mm across, so it needs "
          f"{GRIP_ROOM + widest(SHAPES[PARTNER]) / 2.0:.1f} mm")
    what_a_residual_is()
    the_loss_is_a_fixed_cost()
    what_the_examples_buy()
    the_line_the_residual_may_not_move()


if __name__ == "__main__":
    main()
