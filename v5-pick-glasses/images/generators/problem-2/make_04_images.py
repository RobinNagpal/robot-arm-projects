"""Pictures for solution 4 — learned doubt steers the next picture.

Eight diagrams, each carrying one point:

1. the three cases a doubt number has to tell apart, and the one that matters
2. wrong is not the same thing as unusual
3. the five ways to get a doubt number, and what each costs
4. the ordering: geometry generates and vetoes, the model only sorts
5. the loop, drawn as a loop, with the budget as the way out
6. the same seven viewpoints ordered by the rule and by the model
7. what a calibration check looks like, and what a bad one looks like
8. where the seconds go, and what the cap on looks is for

Run from the project root:

    pixi run python images/generators/problem-2/make_04_images.py
"""

from __future__ import annotations

import math

from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PAPER,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle

# ---------------------------------------------------------------------------
# Small drawing helpers. Nothing here knows anything about the cell.


def _tint(colour: str, alpha: float):
    return to_rgba(colour, alpha)


def _frame(axis, xlim, ylim) -> None:
    axis.set_xlim(*xlim)
    axis.set_ylim(*ylim)
    bare(axis)


def _title(axis, text: str, colour: str = INK, size: float = TITLE_SIZE) -> None:
    axis.set_title(text, fontsize=size, color=colour, pad=9)


def _box(
    axis,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    *,
    edge: str = INK,
    face: str = PAPER,
    size: float = NOTE_SIZE,
    ink: str | None = None,
    align: str = "center",
    lw: float = 1.1,
) -> None:
    """A rounded box with text in it, positioned by its bottom-left corner."""
    axis.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.04,rounding_size=0.14",
            linewidth=lw,
            edgecolor=edge,
            facecolor=face,
        )
    )
    tx = x + width / 2 if align == "center" else x + 0.22
    axis.text(
        tx,
        y + height / 2,
        text,
        ha=align,
        va="center",
        fontsize=size,
        color=ink or INK,
        linespacing=1.5,
    )


def _arrow(axis, start, end, colour: str = INK, lw: float = 1.2, style: str = "-") -> None:
    axis.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "color": colour,
            "linewidth": lw,
            "linestyle": style,
            "shrinkA": 0,
            "shrinkB": 0,
            "mutation_scale": 13,
        },
    )


def _glass(axis, cx: float, base: float, height: float, bottom: float, top: float,
           colour: str = GLASS, alpha: float = 0.20, lw: float = 1.5) -> None:
    """A tapered silhouette standing on a table line, in panel units."""
    points = [
        (cx - bottom / 2, base),
        (cx - top / 2, base + height),
        (cx + top / 2, base + height),
        (cx + bottom / 2, base),
    ]
    axis.add_patch(
        Polygon(points, closed=False, facecolor=_tint(colour, alpha), edgecolor=colour, linewidth=lw)
    )


def _extent(axis, x0: float, x1: float, y: float, label: str, colour: str,
            beside: bool = False) -> None:
    """A bar under the picture saying how wide one reported object came out."""
    axis.plot([x0, x1], [y, y], color=colour, linewidth=2.6, solid_capstyle="butt")
    for x in (x0, x1):
        axis.plot([x, x], [y - 0.17, y + 0.17], color=colour, linewidth=1.6)
    if beside:
        axis.text(x1 + 0.25, y, label, ha="left", va="center", fontsize=NOTE_SIZE, color=colour)
    else:
        axis.text((x0 + x1) / 2, y - 0.5, label, ha="center", va="top", fontsize=NOTE_SIZE,
                  color=colour, linespacing=1.4)


# ---------------------------------------------------------------------------
# 1. Confident and right, unsure and right, confident and wrong.


def three_cases_of_doubt() -> None:
    figure, axes = new(12.6, 5.2, columns=3)

    cases = [
        {
            "title": "confident — and right",
            "colour": GOOD,
            "centres": [3.0, 7.0],
            "extents": [(2.0, 4.0, "74 mm", 0), (6.0, 8.0, "71 mm", 0)],
            "doubt": 0.07,
            "verdict": "Two masks, two glasses.",
            "cost": "Nothing to spend a look on.",
        },
        {
            "title": "unsure — and right",
            "colour": GLASS,
            "centres": [4.3, 5.9],
            "extents": [(3.2, 5.4, "78 mm", 0), (4.8, 7.0, "74 mm", 1)],
            "doubt": 0.74,
            "verdict": "Two masks, two glasses.",
            "cost": "A look is spent that was not needed.\nThat costs seconds, not correctness.",
        },
        {
            "title": "confident — and wrong",
            "colour": WARN,
            "centres": [4.3, 5.9],
            "extents": [(3.2, 7.0, "232 mm\nno glass of this kind is", 0)],
            "doubt": 0.06,
            "verdict": "One mask, two glasses.",
            "cost": "Nothing is flagged, so no look is taken,\nand everything downstream believes it.",
        },
    ]

    for axis, case in zip(axes, cases, strict=True):
        _frame(axis, (0, 10), (0, 11))
        _title(axis, case["title"], colour=case["colour"])

        axis.add_patch(
            Rectangle((0.5, 5.9), 9.0, 4.7, facecolor=PAPER, edgecolor=MUTED, linewidth=1.0)
        )
        axis.text(0.6, 10.8, "one survey picture", fontsize=NOTE_SIZE, color=MUTED)
        axis.plot([0.7, 9.3], [6.4, 6.4], color=MUTED, linewidth=1.0)
        for cx in case["centres"]:
            _glass(axis, cx, 6.4, 3.3, 2.1, 1.7)

        axis.text(5.0, 5.55, "what came back", ha="center", fontsize=NOTE_SIZE, color=MUTED)
        for x0, x1, label, lane in case["extents"]:
            _extent(axis, x0, x1, 5.05 - 0.95 * lane, label, case["colour"], beside=lane > 0)

        axis.text(1.0, 3.15, "the doubt number the model returns", fontsize=NOTE_SIZE, color=MUTED)
        axis.add_patch(
            Rectangle((1.0, 2.35), 8.0, 0.45, facecolor=_tint(MUTED, 0.16), edgecolor=MUTED,
                      linewidth=0.8)
        )
        marker = 1.0 + 8.0 * case["doubt"]
        axis.add_patch(
            Rectangle((marker - 0.07, 2.20), 0.14, 0.75, facecolor=case["colour"],
                      edgecolor=case["colour"])
        )
        axis.text(1.0, 1.85, "settled", fontsize=NOTE_SIZE, color=MUTED)
        axis.text(9.0, 1.85, "doubtful", ha="right", fontsize=NOTE_SIZE, color=MUTED)

        axis.text(1.0, 1.15, case["verdict"], fontsize=LABEL_SIZE, color=INK)
        axis.text(1.0, 0.42, case["cost"], fontsize=NOTE_SIZE, color=case["colour"],
                  linespacing=1.5, va="center")

    figure.subplots_adjust(bottom=0.14, wspace=0.06)
    figure.text(
        0.5,
        0.03,
        "The third case is the one the number exists to catch, and the one every kind of doubt "
        "number is worst at.",
        ha="center",
        fontsize=LABEL_SIZE,
        color=WARN,
    )
    save(figure, "04-three-cases-of-doubt.png")


# ---------------------------------------------------------------------------
# 2. Being wrong and being unusual are different things.


def wrong_or_unusual() -> None:
    figure, axis = new(10.4, 6.0)
    _frame(axis, (0, 12), (0, 10))
    _title(axis, "a number that is high when the model is wrong is not the same\n"
                 "number as one that is high when the input is unusual", size=TITLE_SIZE)

    left, right, bottom, top = 2.5, 11.6, 1.6, 8.1
    mid_x = (left + right) / 2
    mid_y = (bottom + top) / 2

    cells = [
        (left, mid_y, GOOD,
         "the easy case\n\nneither number fires,\nand neither needs to"),
        (mid_x, mid_y, GLASS,
         "a novelty number fires.\nAn error-aware one does not.\n\n"
         "Cost: one look you did not\nneed. Seconds, not glasses."),
        (left, bottom, WARN,
         "CONFIDENTLY WRONG\n\nNothing looks unusual, because\n"
         "nothing is. A novelty number\nsees nothing at all here."),
        (mid_x, bottom, MUTED,
         "both numbers fire.\n\nThe case papers are scored on,\n"
         "and the one least likely to\nreach this table."),
    ]
    width = (right - left) / 2 - 0.15
    height = (top - bottom) / 2 - 0.15
    for x, y, colour, text in cells:
        weight = 1.6 if colour == WARN else 1.0
        axis.add_patch(
            Rectangle((x, y), width, height, facecolor=_tint(colour, 0.10), edgecolor=colour,
                      linewidth=weight)
        )
        axis.text(x + width / 2, y + height / 2, text, ha="center", va="center",
                  fontsize=NOTE_SIZE, color=INK, linespacing=1.6)

    axis.text(left + width / 2, top + 0.35, "the input looks like the training data",
              ha="center", fontsize=LABEL_SIZE, color=INK)
    axis.text(mid_x + width / 2, top + 0.35, "the input is unusual",
              ha="center", fontsize=LABEL_SIZE, color=INK)
    axis.text(left - 0.45, mid_y + height / 2, "the answer\nis right", ha="center", va="center",
              rotation=90, fontsize=LABEL_SIZE, color=INK, linespacing=1.5)
    axis.text(left - 0.45, bottom + height / 2, "the answer\nis wrong", ha="center", va="center",
              rotation=90, fontsize=LABEL_SIZE, color=INK, linespacing=1.5)

    axis.text(
        0.1,
        0.55,
        "An error-aware number has to light the whole bottom row. A novelty number lights the "
        "right-hand column.\nIn this cell every picture comes from one simulator, one camera and one "
        "kind of glass, so the right-hand\ncolumn is nearly empty — which is exactly why novelty "
        "detection buys so little here, and so much at problem 4.",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.6,
        va="center",
    )
    save(figure, "04-wrong-or-unusual.png")


# ---------------------------------------------------------------------------
# 3. The five sources of a doubt number, side by side.


def five_sources() -> None:
    figure, axis = new(13.4, 5.4)
    _frame(axis, (0, 14), (0, 7.4))
    _title(axis, "five ways to get a doubt number, and what each one costs")

    columns = [0.15, 2.9, 7.95, 9.55, 11.75]
    header = [
        "the source",
        "what the number actually is",
        "passes per\npicture",
        "extra training",
        "on a Mac with no\nNVIDIA card",
    ]
    rows = [
        (
            "predictive entropy",
            "the spread of the softmax the segmenter already\nreturns: near zero when one class wins",
            "1",
            "none",
            "fine — and the number\nis badly calibrated",
        ),
        (
            "Monte Carlo dropout",
            "leave dropout switched on, run the same picture\nten times, measure how far the answer moves",
            "10",
            "none, but the net\nneeds dropout",
            "fine: ten passes still\ncost less than one move",
        ),
        (
            "ensembles",
            "train five copies with different seeds and take\ntheir disagreement",
            "5",
            "five times the\ntraining",
            "five overnight jobs —\nthe expensive one",
        ),
        (
            "evidential / Bayesian",
            "predict a distribution over the class probabilities,\n"
            "so one pass can say “I have seen little like this”",
            "1",
            "a new loss, and\nits own checking",
            "fine to run; the\nfitting is the work",
        ),
        (
            "two views disagreeing",
            "project both of a station's pictures onto the table\n"
            "and see how far apart they put the same glass",
            "0",
            "none at all —\nthere is no model",
            "free: the survey has\nalready taken both",
        ),
    ]

    axis.plot([0, 14], [6.15, 6.15], color=INK, linewidth=1.0)
    for x, text in zip(columns, header, strict=True):
        axis.text(x, 6.62, text, fontsize=NOTE_SIZE, color=INK, va="center", linespacing=1.5,
                  weight="bold")

    for index, row in enumerate(rows):
        y = 5.55 - index * 1.1
        if index % 2 == 0:
            axis.add_patch(
                Rectangle((0, y - 0.5), 14, 1.0, facecolor=_tint(GLASS, 0.07), edgecolor="none")
            )
        colour = GOOD if index == 4 else INK
        for x, text in zip(columns, row, strict=True):
            axis.text(x, y, text, fontsize=NOTE_SIZE, color=colour, va="center", linespacing=1.5)

    axis.text(
        0.15,
        0.28,
        "Inference cost is the wrong thing to worry about: ten passes of a small net are "
        "milliseconds, and one arm move is seconds.\nWhat these really cost is training time and "
        "one more thing to keep in step with the world. The bottom row costs neither.",
        fontsize=NOTE_SIZE,
        color=MUTED,
        linespacing=1.6,
        va="center",
    )
    save(figure, "04-five-sources-of-doubt.png")


# ---------------------------------------------------------------------------
# 4. The ordering that makes this a hybrid rather than a model.


def geometry_then_model() -> None:
    figure, axis = new(13.2, 5.6)
    _frame(axis, (0, 15), (0, 7.1))
    _title(axis, "the geometry generates the candidates and keeps the veto;\n"
                 "the learned score only puts the survivors in order")

    stages = [
        ("generate", 24, GLASS,
         "one candidate every 15 degrees round the cluster,\n"
         "380 mm back, level, 120 mm above the table"),
        ("reach", 10, GLASS,
         "the camera must land 300 to 780 mm from the base:\n14 poses are outside the comfortable reach"),
        ("line of sight", 8, GLASS,
         "no sight line may cross another cluster's fitted\nfootprint circle: two more go"),
        ("plannable", 7, GLASS,
         "inverse kinematics has to solve — MoveIt 2's\nsetFromIK, milliseconds each: one more goes"),
        ("score", 7, GOOD,
         "the learned score sorts these seven.\nIt cannot add an eighth."),
    ]

    bar_x = 3.7
    bar_span = 5.0
    ys = [6.3, 5.25, 4.2, 3.15, 1.65]
    for (name, count, colour, reason), y in zip(stages, ys, strict=True):
        width = bar_span * count / 24
        axis.add_patch(
            Rectangle((bar_x, y - 0.31), width, 0.62, facecolor=_tint(colour, 0.35),
                      edgecolor=colour, linewidth=1.1)
        )
        axis.text(bar_x + width + 0.18, y, str(count), va="center", fontsize=LABEL_SIZE, color=colour)
        axis.text(bar_x - 0.25, y, name, ha="right", va="center", fontsize=LABEL_SIZE, color=INK)
        axis.text(9.15, y, reason, va="center", fontsize=NOTE_SIZE, color=MUTED, linespacing=1.5)

    axis.plot([1.05, 1.05], [2.75, 6.7], color=INK, linewidth=1.6)
    axis.text(0.8, 4.72, "geometry", rotation=90, ha="center", va="center",
              fontsize=LABEL_SIZE, color=INK)
    axis.plot([1.05, 1.05], [1.3, 2.0], color=GOOD, linewidth=1.6)
    axis.text(0.8, 1.65, "learned", rotation=90, ha="center", va="center",
              fontsize=LABEL_SIZE, color=GOOD)

    for y0, y1 in zip(ys[:-1], ys[1:], strict=True):
        _arrow(axis, (bar_x - 1.6, y0 - 0.34), (bar_x - 1.6, y1 + 0.34), colour=MUTED, lw=1.0)

    axis.text(
        3.7,
        0.6,
        "The worst a bad ordering can do is waste one look. It cannot re-admit a pose the geometry "
        "rejected,\nand it is never what decides that a cluster is resolved — the footprint circle is.",
        fontsize=NOTE_SIZE,
        color=WARN,
        linespacing=1.6,
        va="center",
    )
    save(figure, "04-geometry-then-model.png")


# ---------------------------------------------------------------------------
# 5. The loop, drawn as a loop, with the budget as the exit.


def the_loop() -> None:
    figure, axis = new(13.6, 7.4)
    _frame(axis, (0, 17), (0, 10))
    _title(axis, "the loop: measure, score the doubt, choose a viewpoint, move, measure again")

    _box(axis, 1.5, 8.45, 5.0, 1.1,
         "SURVEY — three fixed stations, two pictures each.\n"
         "Not learned: it assumes nothing.",
         edge=MUTED, ink=MUTED)
    _arrow(axis, (4.0, 8.4), (4.0, 7.8), colour=MUTED)

    _box(axis, 1.5, 6.3, 5.0, 1.45,
         "1  MEASURE\nLift the masked pixels onto the table, cluster them,\n"
         "fit a footprint circle to each cluster.",
         edge=INK)
    _box(axis, 7.1, 6.3, 5.0, 1.45,
         "2  SCORE THE DOUBT\nCircle outside 45 to 105 mm? Two circles fit no\n"
         "better? Cluster seen from one station only?",
         edge=INK)
    _box(axis, 7.1, 2.85, 5.0, 1.45,
         "3  CHOOSE A VIEWPOINT\n24 candidates, then the geometric veto, then the\n"
         "learned score sorts what is left. Take the best.",
         edge=INK)
    _box(axis, 1.5, 2.85, 5.0, 1.45,
         "4  MOVE AND PHOTOGRAPH\nPlan, move, settle: seconds, and the only real cost.\n"
         "The pictures themselves: milliseconds.",
         edge=INK)

    _arrow(axis, (6.5, 7.0), (7.1, 7.0))
    _arrow(axis, (9.6, 6.25), (9.6, 5.85))
    _box(axis, 8.1, 4.95, 3.0, 0.8, "four looks already spent?", edge=WARN, ink=WARN)
    _arrow(axis, (9.6, 4.9), (9.6, 4.35))
    _arrow(axis, (7.1, 3.6), (6.5, 3.6))

    axis.plot([1.5, 0.85], [3.6, 3.6], color=INK, linewidth=1.2)
    axis.plot([0.85, 0.85], [3.6, 7.0], color=INK, linewidth=1.2)
    _arrow(axis, (0.85, 7.0), (1.5, 7.0))
    axis.text(0.62, 5.3, "re-measure", rotation=90, ha="center", va="center",
              fontsize=NOTE_SIZE, color=INK)

    exits = [
        (12.1, 7.35, GOOD,
         "nothing doubtful left\n→ done: one mask, one position and\none rough width per glass"),
        (11.1, 5.35, WARN,
         "budget spent\n→ stop, and report the cluster as\nunresolved. A named doubt is a result."),
        (12.1, 3.25, WARN,
         "no candidate survives the veto\n→ nowhere left to look from:\nhand it to problem 3"),
    ]
    for x, y, colour, text in exits:
        _arrow(axis, (x, y), (x + 0.75, y), colour=colour)
        axis.text(x + 0.95, y, text, va="center", fontsize=NOTE_SIZE, color=colour, linespacing=1.6)

    axis.text(
        0.1,
        1.35,
        "Steps 1 and 2 are arithmetic, and they alone decide whether a cluster counts as resolved. "
        "The learned part lives\ninside step 3, downstream of the veto, and the loop has three ways "
        "out so that it cannot run for ever.",
        fontsize=NOTE_SIZE,
        color=MUTED,
        linespacing=1.6,
        va="center",
    )
    save(figure, "04-the-loop.png")


# ---------------------------------------------------------------------------
# 6. The rule's order and the model's order, over the same seven viewpoints.
#
# The cluster is 530 mm from the base and 232 mm across: two glasses of 78 and
# 74 mm footprint, centres 155 mm apart, reported as one. The angle theta is
# measured from the line out from the arm's base. The reach test leaves ten of
# the 24 candidates, occlusion takes two and inverse kinematics one.

STANDOFF_MM = 380.0
FX = 277.1
GAP_MM = 155.0
SEPARATION_THETA = 120.0  # the direction the two glasses lie along, relative to the radial line
KEPT = [75.0, 90.0, 105.0, 120.0, -75.0, -90.0, -105.0]
DROPPED = [(135.0, "sight line"), (-120.0, "sight line"), (-135.0, "no IK")]


def _apparent_gap_px(theta_deg: float) -> float:
    """How far apart the two glasses land in the picture, from a standoff at this angle."""
    across = abs(math.sin(math.radians(theta_deg - SEPARATION_THETA)))
    return GAP_MM * FX / STANDOFF_MM * across


def _camera_range_mm(theta_deg: float, cluster_mm: float = 530.0) -> float:
    return math.sqrt(
        cluster_mm**2 + STANDOFF_MM**2 + 2 * cluster_mm * STANDOFF_MM * math.cos(math.radians(theta_deg))
    )


def _unit(theta_deg: float) -> tuple[float, float]:
    """The standoff direction, with the line out from the base drawn as straight up."""
    rad = math.radians(theta_deg)
    return math.sin(rad), math.cos(rad)


def rule_and_model_orders() -> None:
    touching_px = (78.0 + 74.0) / 2 * FX / STANDOFF_MM
    rule_order = sorted(KEPT, key=lambda t: (_camera_range_mm(t), -t))
    # Round the gap before sorting: two mirrored angles give the same gap to the last bit,
    # and without the rounding the tie breaks on floating-point noise rather than on reach.
    model_order = sorted(KEPT, key=lambda t: (-round(_apparent_gap_px(t), 1), _camera_range_mm(t)))

    figure, axes = new(13.6, 6.2, columns=2)
    left, right = axes

    _frame(left, (-520, 520), (-470, 570))
    left.set_aspect("equal")
    _title(left, "the seven viewpoints the geometry left")

    left.add_patch(Circle((0, 0), 116, facecolor=_tint(WARN, 0.10), edgecolor=WARN,
                          linewidth=1.3, linestyle="--"))
    left.text(0, 195, "one fitted circle, 232 mm across", ha="center", fontsize=NOTE_SIZE,
              color=WARN)

    sx, sy = _unit(SEPARATION_THETA)
    for sign, radius in ((1, 39.0), (-1, 37.0)):
        left.add_patch(
            Circle((sign * sx * GAP_MM / 2, sign * sy * GAP_MM / 2), radius,
                   facecolor=_tint(GLASS, 0.45), edgecolor=GLASS, linewidth=1.2)
        )
    left.plot([-sx * 235, sx * 235], [-sy * 235, sy * 235], color=GLASS, linewidth=1.0,
              linestyle=":")
    left.text(-505, 545, "the dotted line is the line the two glasses lie along.\n"
                         "Both are inside one fitted circle, so the geometric\n"
                         "veto has no way of seeing it.",
              ha="left", va="top", fontsize=NOTE_SIZE, color=GLASS, linespacing=1.5)

    _arrow(left, (0, -170), (0, -300), colour=MUTED)
    left.text(0, -345, "towards the base, 530 mm", ha="center", fontsize=NOTE_SIZE, color=MUTED)

    for theta, why in DROPPED:
        ux, uy = _unit(theta)
        left.plot([ux * STANDOFF_MM], [uy * STANDOFF_MM], marker="x", markersize=7,
                  color=MUTED, markeredgewidth=1.6)
        left.text(ux * 470, uy * 470, why, ha="center", va="center", fontsize=7.4, color=MUTED)

    for theta in KEPT:
        ux, uy = _unit(theta)
        gap = _apparent_gap_px(theta)
        colour = GOOD if gap > touching_px else WARN
        left.plot([ux * 150, ux * (STANDOFF_MM - 30)], [uy * 150, uy * (STANDOFF_MM - 30)],
                  color=_tint(colour, 0.5), linewidth=0.9)
        left.plot([ux * STANDOFF_MM], [uy * STANDOFF_MM], marker="o", markersize=7, color=colour)
        tag = f"{theta:+.0f}°\n{gap:.0f} px"
        if theta == rule_order[0]:
            tag += "\nrule's 1st"
        if theta == model_order[0]:
            tag += "\nmodel's 1st"
        left.text(ux * 475, uy * 475, tag, ha="center", va="center", fontsize=7.4, color=colour,
                  linespacing=1.45)

    _frame(right, (-0.7, 6.7), (0, 120))
    right.set_xticks(range(7))
    right.set_xticklabels([f"{t:+.0f}°" for t in rule_order], fontsize=NOTE_SIZE, color=INK)
    right.set_yticks([0, 20, 40, 60, 80, 100])
    right.set_yticklabels([str(v) for v in (0, 20, 40, 60, 80, 100)], fontsize=NOTE_SIZE, color=INK)
    for side in ("left", "bottom"):
        right.spines[side].set_visible(True)
        right.spines[side].set_color(MUTED)
    right.tick_params(length=3, colors=MUTED)
    right.set_ylabel("how far apart the two glasses land, in pixels", fontsize=NOTE_SIZE, color=INK)
    right.set_xlabel("the seven survivors, in the order the printed rule takes them",
                     fontsize=NOTE_SIZE, color=INK)
    _title(right, "the rule takes them worst first")

    for index, theta in enumerate(rule_order):
        gap = _apparent_gap_px(theta)
        colour = GOOD if gap > touching_px else WARN
        right.bar(index, gap, width=0.62, color=_tint(colour, 0.45), edgecolor=colour, linewidth=1.1)
        right.text(index, gap + 2.5, f"{gap:.0f}", ha="center", fontsize=NOTE_SIZE, color=colour)

    right.axhline(touching_px, color=INK, linewidth=1.1, linestyle="--")
    right.text(6.6, touching_px + 2.5, "below this the two silhouettes still touch:\nthe look is wasted",
               ha="right", fontsize=NOTE_SIZE, color=INK, linespacing=1.5)
    rank = rule_order.index(model_order[0])
    right.annotate(
        "the model takes this one first",
        xy=(rank, _apparent_gap_px(model_order[0]) + 6),
        xytext=(rank + 1.7, 108),
        ha="center",
        fontsize=NOTE_SIZE,
        color=GOOD,
        arrowprops={"arrowstyle": "-|>", "color": GOOD, "linewidth": 1.1},
    )
    right.text(-0.35, 13, "the rule takes\nthis one first:\nthe two glasses\nland on top of\n"
                          "each other again",
               fontsize=NOTE_SIZE, color=WARN, linespacing=1.5, va="bottom")

    figure.subplots_adjust(bottom=0.20, wspace=0.18)
    figure.text(
        0.5,
        0.035,
        "The printed rule breaks its ties by least reach, and least reach here means looking straight "
        "along the line the two glasses lie on,\nwhich reproduces the merge. The veto could not know: "
        "both glasses are inside one fitted circle. The scores are illustrative; the pixel gaps are not.",
        ha="center",
        fontsize=NOTE_SIZE,
        color=INK,
        linespacing=1.6,
    )
    save(figure, "04-rule-and-model-orders.png")


# ---------------------------------------------------------------------------
# 7. The calibration check.


def calibration() -> None:
    figure, axes = new(12.4, 5.0, columns=2)
    left, right = axes

    bins = [0.55, 0.65, 0.75, 0.85, 0.95]
    overconfident = [0.52, 0.58, 0.63, 0.68, 0.72]
    scaled = [0.54, 0.63, 0.74, 0.83, 0.92]
    counts = [6, 9, 14, 31, 98]

    left.set_xlim(0.5, 1.0)
    left.set_ylim(0.4, 1.0)
    left.plot([0.5, 1.0], [0.5, 1.0], color=MUTED, linewidth=1.2, linestyle="--",
              label="perfectly calibrated")
    left.fill_between(bins, overconfident, bins, color=_tint(WARN, 0.14))
    left.plot(bins, overconfident, color=WARN, linewidth=1.6, marker="o", markersize=5,
              label="as fitted")
    left.plot(bins, scaled, color=GOOD, linewidth=1.6, marker="o", markersize=5,
              label="after one scalar is fitted to it")
    left.set_xlabel("how confident it said it was", fontsize=NOTE_SIZE, color=INK)
    left.set_ylabel("how often it was actually right", fontsize=NOTE_SIZE, color=INK)
    _title(left, "the check: claimed confidence against being right")
    left.annotate(
        "says 95 in 100, is right 72 in 100.\nThe looks it talked the loop out of\ntaking were the "
        "ones most needed.",
        xy=(0.945, 0.705),
        xytext=(0.99, 0.43),
        ha="right",
        va="bottom",
        fontsize=NOTE_SIZE,
        color=WARN,
        linespacing=1.6,
        arrowprops={"arrowstyle": "-|>", "color": WARN, "linewidth": 1.1},
    )
    left.legend(loc="upper left", fontsize=NOTE_SIZE, frameon=False)

    right.set_xlim(0.5, 1.0)
    right.bar(bins, counts, width=0.085, color=_tint(GLASS, 0.4), edgecolor=GLASS, linewidth=1.1)
    for x, count in zip(bins, counts, strict=True):
        right.text(x, count + 2, str(count), ha="center", fontsize=NOTE_SIZE, color=GLASS)
    right.set_xlabel("how confident it said it was", fontsize=NOTE_SIZE, color=INK)
    right.set_ylabel("how many clusters landed in that bin", fontsize=NOTE_SIZE, color=INK)
    _title(right, "and where the predictions actually sit")
    right.text(0.52, 78, "Nearly all of them claim high confidence,\nwhich is why a gap in the top "
                         "bin costs\nmore than a gap anywhere else.",
               fontsize=NOTE_SIZE, color=INK, linespacing=1.6, va="top")

    for axis in (left, right):
        axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED, length=3)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(MUTED)

    figure.subplots_adjust(bottom=0.24, wspace=0.28)
    figure.text(
        0.5,
        0.035,
        "Both curves are drawn to show the shape of the check, not measured. The real ones come from "
        "a scored run against the simulator's\nown record of what it spawned — and until that plot "
        "exists, the doubt number is a heuristic in a weights file.",
        ha="center",
        fontsize=NOTE_SIZE,
        color=MUTED,
        linespacing=1.6,
    )
    save(figure, "04-calibration.png")


# ---------------------------------------------------------------------------
# 8. The budget, and what the cap is for.


def budget_and_cap() -> None:
    figure, axes = new(13.6, 5.4, columns=2)
    left, right = axes

    _frame(left, (0, 17), (0, 7.0))
    _title(left, "what a run costs, in stations' worth of arm motion")

    rows = [
        (3, 0, GLASS, "survey only: three stations, six pictures"),
        (3, 4, GOOD, "plus the cap of four extra looks: twice the survey"),
        (3, 12, WARN, "two looks each for six clusters: too much"),
    ]
    scale = 0.45
    for index, (base, extra, colour, note) in enumerate(rows):
        y = 5.4 - index * 1.55
        left.add_patch(
            Rectangle((0.15, y - 0.2), base * scale, 0.62, facecolor=_tint(GLASS, 0.45),
                      edgecolor=GLASS, linewidth=1.1)
        )
        if extra:
            left.add_patch(
                Rectangle((0.15 + base * scale, y - 0.2), extra * scale, 0.62,
                          facecolor=_tint(colour, 0.35), edgecolor=colour, linewidth=1.1)
            )
        end = 0.15 + (base + extra) * scale
        left.text(end + 0.3, y + 0.11, f"{base + extra}t \u2014 {note}", va="center",
                  fontsize=NOTE_SIZE, color=INK)

    cap_x = 0.15 + 7 * scale
    left.plot([cap_x, cap_x], [1.9, 4.6], color=INK, linewidth=1.0, linestyle="--")
    left.text(cap_x + 0.15, 4.75, "the cap", fontsize=NOTE_SIZE, color=INK)
    left.text(
        0.15,
        1.0,
        "t is one station's plan, move and settle.\nIt has to be timed from the survey, not guessed "
        "here.\nScoring 24 candidates \u2014 76,800 rays each, over 212,000\ncubes \u2014 is "
        "milliseconds. Computation is not the budget.",
        fontsize=NOTE_SIZE,
        color=MUTED,
        linespacing=1.6,
        va="center",
    )

    _frame(right, (0, 12), (0, 7.0))
    _title(right, "and what the per-cluster cap is for")

    slots = [0.7, 1.75, 2.8, 3.85]
    right.plot([0.25, 4.3], [6.35, 6.35], color=MUTED, linewidth=1.0)
    for slot, x in enumerate(slots):
        right.text(x, 6.55, f"look {slot + 1}", ha="center", fontsize=7.6, color=MUTED)

    lanes = [
        (5.6, "the 232 mm cluster", GOOD, 1,
         "resolved on the first look: circles of\n78 and 74 mm, 155 mm apart, both in\nrange"),
        (3.2, "a pair in line with every pose\nthe geometry left", WARN, 2,
         "no view separates them. The cap stops\nit at two and reports it unresolved \u2014\n"
         "which is a result, not a failure."),
    ]
    for y, name, colour, used, note in lanes:
        right.text(0.25, y, name, fontsize=NOTE_SIZE, color=INK, linespacing=1.5, va="top")
        for slot, x in enumerate(slots):
            if slot < used:
                right.plot([x], [y - 1.1], marker="o", markersize=13, color=_tint(colour, 0.45),
                           markeredgecolor=colour, markeredgewidth=1.2)
            else:
                right.plot([x], [y - 1.1], marker="o", markersize=13, color=PAPER,
                           markeredgecolor=MUTED, markeredgewidth=0.8)
        right.text(4.8, y - 1.1, note, va="center", fontsize=NOTE_SIZE, color=colour,
                   linespacing=1.5)

    right.text(
        0.25,
        0.75,
        "Filled circles are looks spent. Without the per-cluster cap the second lane\ntakes all four "
        "and the others get none; without the per-run cap the pair takes\nlook after look, each one "
        "scoring well and none of them helping.",
        fontsize=NOTE_SIZE,
        color=MUTED,
        linespacing=1.6,
        va="center",
    )

    figure.subplots_adjust(wspace=0.08)
    save(figure, "04-budget-and-the-cap.png")


def main() -> None:
    three_cases_of_doubt()
    wrong_or_unusual()
    five_sources()
    geometry_then_model()
    the_loop()
    rule_and_model_orders()
    calibration()
    budget_and_cap()


if __name__ == "__main__":
    main()
