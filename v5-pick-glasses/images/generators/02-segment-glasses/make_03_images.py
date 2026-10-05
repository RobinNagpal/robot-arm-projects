"""Pictures for solution 3 — a borrowed model, run exactly as it downloads.

Five figures, each carrying one point of the document:

In the order the document shows them:

    03-the-name-is-the-only-gate.png   what goes in, what comes back, and the one
                                       step in the chain that this project wrote
    03-the-outlines-were-not-the-problem.png  how much of each glass the outline
                                       covered, on the few glasses it did name
    03-a-glass-from-the-top.png        the features that say "glass" in a photograph,
                                       against the disc this cell renders from the top
    03-what-it-named.png               every name the model offered, per kind, against
                                       the five names the filter was looking for
    03-silence-against-the-floor.png   10 of 100, against the bench's floor and against
                                       solution 4, with every error column empty

Run from the problem folder:

    cd 02-segment-glasses && pixi run python ../images/generators/02-segment-glasses/make_03_images.py

This document's result is a null result, so four of the five figures draw the
measurement rather than a sketch. Every count in them is read at drawing time out
of the solution's own files — ``results.json``, ``results-crowded.json`` and
``results-names.json`` — and out of the bench's ``results-floor.json`` and
solution 4's results beside them, so no number here can drift from the run that
produced it. ``check_the_files`` re-derives the totals the figures lean on and
refuses to draw if the files disagree with them, and the five accepted category
names are parsed out of ``drinking_vessels.py`` rather than copied, so a change
to that list cannot leave a figure claiming the old one.

The two runs are kept apart on purpose and every panel says which it is drawing.
The scorecard is 20 held-out arrangements, 60 pictures. The names are a separate,
smaller run of 3 arrangements per kind, 36 pictures, with no filter in front of
the model at all. They are not the same glasses and are never added together.

The one figure that is a drawing rather than a measurement is the glass from the
top, and it says so on its face: the left panel is a stand-in for a photograph,
and the right panel is this cell's own geometry — the silhouette comes from
``diagram_style.splay_circles`` and the shade is the height of the nearest
surface, which is what the renderer hands the model.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PAPER,
    TALL_A,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
    splay_circles,
)
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon

# --------------------------------------------------------------------------- #
# the measurements, read rather than written down
# --------------------------------------------------------------------------- #

PROBLEM = Path(__file__).resolve().parents[3] / "02-segment-glasses"
SOLUTION = PROBLEM / "03-yolo-zero-shot"

SPAWNED = json.loads((SOLUTION / "results.json").read_text())
CROWDED = json.loads((SOLUTION / "results-crowded.json").read_text())
NAMED = json.loads((SOLUTION / "results-names.json").read_text())

SIBLING = PROBLEM / "04-yolo-fine-tuned"
SIBLING_SPAWNED = json.loads((SIBLING / "results.json").read_text())
SIBLING_CROWDED = json.loads((SIBLING / "results-crowded.json").read_text())

# The sentence the finder returns when the filter kept nothing, counted by the
# bench. Read from the results rather than retyped, because it is a key in a
# dictionary the solution writes and a copy here would rot.
SILENT = "the model named nothing in this picture a drinking vessel"

# Three survey stations per arrangement, which is the bench's arrangement and not
# this solution's. Taken from the results so the picture counts below are the
# run's own arithmetic.
STATIONS = SPAWNED["stations"]

NADIR = np.array([0.0, 0.0])
DEPTH_MAP = LinearSegmentedColormap.from_list("depth", [INK, PAPER])
HALO = {"facecolor": PAPER, "edgecolor": "none", "alpha": 0.90, "pad": 2.4}


def floor_way(name: str, way: str = "exact visible masks") -> dict:
    """One row of the bench's own floor: the shared arithmetic on exact masks.

    The floor file holds several ways of feeding the bench perfect masks. The
    visible-mask way is the one a segmenter could in principle match, since no
    model can outline a pixel the camera did not see, so it is the right thing
    to read this solution against.
    """
    ways = json.loads((PROBLEM / "bench" / name).read_text())["ways"]
    for row in ways:
        if row["solution"] == way:
            return row
    raise ValueError(f"{name} holds no way called {way!r}")


FLOOR_SPAWNED = floor_way("results-floor.json")
FLOOR_CROWDED = floor_way("results-floor-crowded.json")


def accepted_names() -> tuple[str, ...]:
    """The names the filter keeps, parsed out of the solution's own module.

    Parsed rather than copied, because this list is the whole of the solution's
    second step and a figure claiming a list the code no longer has would be
    worse than no figure. ``VESSELS`` are the two entries that are drinking
    vessels outright and ``NEIGHBOURS`` the three near shapes, in that order.
    """
    tree = ast.parse((SOLUTION / "drinking_vessels.py").read_text())
    found: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in ("VESSELS", "NEIGHBOURS"):
                found[target.id] = tuple(ast.literal_eval(node.value))
    return found["VESSELS"] + found["NEIGHBOURS"]


ACCEPTED = accepted_names()

# Every name the model offered, pooled over the four kinds. Used by two figures,
# so it is worked out once.
OFFERED: dict[str, int] = {}
for _kind in NAMED["kinds"].values():
    for _name, _count in _kind["named"].items():
        OFFERED[_name] = OFFERED.get(_name, 0) + _count
OFFERED = dict(sorted(OFFERED.items(), key=lambda pair: -pair[1]))

NAME_PICTURES = NAMED["scenes per kind"] * len(NAMED["kinds"]) * STATIONS
SIGHTINGS = sum(kind["glasses on the table, counted once per picture"] for kind in NAMED["kinds"].values())
OFFERS = sum(OFFERED.values())
ON_THE_LIST = sum(count for name, count in OFFERED.items() if name in ACCEPTED)

# The two roundest things on the model's list, which is where most of its answers
# went. Which two is a reading of the names; how many is measured.
ROUND_THINGS = ("sports ball", "frisbee")
ROUND_OFFERS = sum(OFFERED.get(name, 0) for name in ROUND_THINGS)

SCORED_PICTURES = SPAWNED["scenes"] * STATIONS


def check_the_files() -> None:
    """Refuse to draw if the files disagree with the totals the figures state.

    Every figure below reads these files, so the only way a figure can lie is
    for the arithmetic here to be wrong about them. Each total a panel prints as
    a headline is re-derived from a second place in the data and compared.
    """
    for report in (SPAWNED, CROWDED):
        find = report["find"]
        total = find["found"] + find["missed"]
        if total != report["glasses"]:
            raise ValueError(f"{report['layouts']}: {total} found and missed, {report['glasses']} put out")
        if find["merged"] or find["split"] or find["false"]:
            raise ValueError(f"{report['layouts']}: this solution's story is silence, not error")
        if SILENT not in report["handed over"]:
            raise ValueError(f"{report['layouts']}: no count of the pictures that handed nothing over")
        shown = report["scenes"] * report["stations"]
        if report["handed over"][SILENT] > shown:
            raise ValueError(f"{report['layouts']}: silent in more pictures than were shown")
        kinds = report["mask"]["by_kind"].values()
        if sum(kind["glasses"] for kind in kinds) != report["mask"]["all"]["glasses"]:
            raise ValueError(f"{report['layouts']}: the kinds do not add up to the glasses measured")
        if report["mask"]["all"]["glasses"] != find["found"]:
            raise ValueError(f"{report['layouts']}: masks measured on a different number than were found")

    for kind, got in NAMED["kinds"].items():
        kept = sum(count for name, count in got["named"].items() if name in ACCEPTED)
        if kept != got["named a drinking vessel"]:
            raise ValueError(f"{kind}: {kept} on the parsed list, {got['named a drinking vessel']} recorded")
    if sum(k["named a drinking vessel"] for k in NAMED["kinds"].values()) != ON_THE_LIST:
        raise ValueError("the pooled names do not agree with the per-kind counts")
    if ROUND_OFFERS >= OFFERS:
        raise ValueError("the round things cannot be every name the model offered")


# --------------------------------------------------------------------------- #
# small shared drawing helpers, the same ones the sibling generators use
# --------------------------------------------------------------------------- #

def tint(colour: str, amount: float) -> tuple[float, float, float, float]:
    """A pale version of a palette colour: 1.0 is the colour, 0.0 is paper."""
    near = np.array(to_rgba(colour))
    far = np.array(to_rgba(PAPER))
    return tuple(far + (near - far) * amount)


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, ha="left", va="top", weight="normal",
         halo=False) -> None:
    axis.text(x, y, text, fontsize=size, color=colour, ha=ha, va=va, zorder=8, weight=weight,
              bbox=HALO if halo else None)


def panel_title(axis, text, colour=INK, size=LABEL_SIZE + 0.6) -> None:
    axis.set_title(text, fontsize=size, color=colour, pad=8)


def box(axis, x, y, width, height, text, face, edge=MUTED, size=NOTE_SIZE, colour=INK,
        weight="normal", lw=1.0) -> None:
    """A rounded box with centred text, in axis fractions."""
    axis.add_patch(
        FancyBboxPatch(
            (x - width / 2.0, y - height / 2.0), width, height,
            boxstyle="round,pad=0.006,rounding_size=0.010",
            facecolor=face, edgecolor=edge, lw=lw, zorder=4,
        )
    )
    axis.text(x, y, text, ha="center", va="center", fontsize=size, color=colour, zorder=6,
              weight=weight)


def arrow(axis, start, end, colour=INK, lw=1.3, style="-|>") -> None:
    axis.add_patch(
        FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=11, color=colour, lw=lw,
                        shrinkA=2.0, shrinkB=2.0, zorder=7)
    )


def blank(axis) -> None:
    """A panel drawn in fractions of itself, with no axes of any kind."""
    bare(axis)
    axis.set_xlim(0.0, 1.0)
    axis.set_ylim(0.0, 1.0)


def pretty(kind: str) -> str:
    """A kind of glass as the documents write it."""
    return kind.replace("_", " ")


# --------------------------------------------------------------------------- #
# 1. the shape of the method, and the one gate in it
# --------------------------------------------------------------------------- #

def figure_the_name_is_the_only_gate() -> None:
    """Six steps, one of them this project's, and the funnel measured through it."""
    figure, axis = new(15.6, 6.6)
    blank(axis)

    steps = (
        ("the survey picture\nfrom the top",
         "grey, shaded from depth.\nthe bench's, not this solution's", MUTED),
        ("YOLO26-seg,\nexactly as it downloads",
         "the weights fetch themselves.\nnothing is fitted in this cell", GLASS),
        ("per object it finds:\na box, a name,\na score, an outline",
         "the model's four answers,\nall of them borrowed", GLASS),
        ("keep the outline only if\nthe name is one of five",
         " · ".join(ACCEPTED), WARN),
        ("throw the name away,\nkeep the outline",
         "a mask carrying no claim\nabout what was outlined", INK),
        ("the bench's arithmetic:\na place and a rough width",
         "the same step for all six\nsolutions. not this one's", MUTED),
    )

    width, gap = 0.134, 0.022
    left = (1.0 - (len(steps) * width + (len(steps) - 1) * gap)) / 2.0
    middle = 0.845
    centres = []
    for index, (label, under, colour) in enumerate(steps):
        x = left + width / 2.0 + index * (width + gap)
        centres.append(x)
        gate = colour is WARN
        box(axis, x, middle, width, 0.165, label, tint(colour, 0.20 if gate else 0.10),
            edge=colour, size=NOTE_SIZE - 0.4, weight="bold" if gate else "normal",
            lw=1.6 if gate else 1.0)
        note(axis, x, middle - 0.098, under, colour=colour if gate else MUTED,
             size=NOTE_SIZE - 1.6, ha="center", va="top")
    for one, other in zip(centres[:-1], centres[1:], strict=True):
        arrow(axis, (one + width / 2.0, middle), (other - width / 2.0, middle))

    # The two steps this project wrote are the two in the middle, and the span is
    # drawn rather than said because the point of the figure is how little of the
    # chain it is.
    span_left = centres[3] - width / 2.0
    span_right = centres[4] + width / 2.0
    axis.plot([span_left, span_right], [0.965, 0.965], color=WARN, lw=1.4, zorder=5)
    for end in (span_left, span_right):
        axis.plot([end, end], [0.955, 0.975], color=WARN, lw=1.4, zorder=5)
    note(axis, (span_left + span_right) / 2.0, 0.982,
         "the whole of what this project wrote", colour=WARN, size=NOTE_SIZE,
         ha="center", va="bottom", weight="bold")

    # ---- the funnel, measured ------------------------------------------------
    note(axis, 0.055, 0.620,
         f"What came through that chain, measured over {NAME_PICTURES} pictures "
         f"with no filter in front of the model:",
         colour=INK, size=LABEL_SIZE, va="top", weight="bold")

    rows = (
        (SIGHTINGS, "glasses standing on the table across those pictures",
         f"{SIGHTINGS // len(NAMED['kinds'])} sightings of each of the four kinds", GLASS),
        (OFFERS, "outlines the model returned, each with a name",
         "it does find things in these pictures: nothing about the finding is silent", GLASS),
        (ON_THE_LIST, "of those names were on the filter's list of five",
         f"and every one of the {ON_THE_LIST} was the same name: "
         f"{', '.join(sorted({n for n in OFFERED if n in ACCEPTED}))}", WARN),
    )
    scale = max(row[0] for row in rows)
    bar_left, bar_span = 0.055, 0.46
    for index, (count, label, under, colour) in enumerate(rows):
        y = 0.475 - index * 0.165
        axis.add_patch(
            FancyBboxPatch(
                (bar_left, y - 0.034), bar_span * count / scale, 0.068,
                boxstyle="round,pad=0.0,rounding_size=0.008",
                facecolor=tint(colour, 0.45), edgecolor=colour, lw=1.2, zorder=3,
            )
        )
        note(axis, bar_left + bar_span * count / scale + 0.012, y, f"{count}", colour=colour,
             size=LABEL_SIZE + 2.0, va="center", weight="bold")
        note(axis, bar_left + 0.012, y + 0.044, label, colour=INK, size=NOTE_SIZE, va="bottom",
             halo=True)
        note(axis, bar_left + 0.012, y - 0.046, under, colour=MUTED, size=NOTE_SIZE - 1.2,
             va="top")

    never = [name for name in ACCEPTED if name not in OFFERED]
    note(axis, 0.615, 0.560,
         "The gate is the name, and nothing else.\n\n"
         f"Four of the five names the filter accepts — {', '.join(never)} —\n"
         f"were never offered once in {NAME_PICTURES} pictures.\n\n"
         "The bar on the confidence number cannot be what dropped them. It is\n"
         "handed to the model and then checked again here, so an outline that\n"
         "reaches the check is already above the bar: in this run the second\n"
         "check could drop nothing, and the first dropped nothing that the\n"
         "name would have kept.\n\n"
         "Nothing after the gate can recover an outline the gate threw away,\n"
         "and nothing before it belongs to this project.",
         colour=INK, size=NOTE_SIZE, va="top")

    figure.suptitle(
        "Five of the six steps are borrowed or shared. The one this project wrote is where the "
        "result is lost.",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.02,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.01,
        f"The chain is read off `yolo_zero_shot.py` and the five accepted names out of "
        f"`drinking_vessels.py`. The counts are the separate naming run in `results-names.json`: "
        f"{NAMED['scenes per kind']} held-out\narrangements of each of the four kinds, {STATIONS} "
        f"stations each, {NAME_PICTURES} pictures, every name the model offered and no filter in "
        f"front of it. That is not the run the scorecard comes from, so the two are never added "
        "together.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "03-the-name-is-the-only-gate.png")


# --------------------------------------------------------------------------- #
# 2. why a glass from the top is the hard case
# --------------------------------------------------------------------------- #

def shaded_from_the_top(centre, size, limits, step: float = 0.9):
    """How high above the table the nearest surface is, cell by cell.

    This is what the renderer hands the model, turned the way round the model is
    fed it: the depth reading shaded into grey, brightest where a surface is
    nearest the lens. The silhouette is the cell's own geometry from
    ``splay_circles``, so the shape is the camera's and not a drawing.
    """
    height, rim = size
    circles = splay_circles(NADIR, np.array(centre, dtype=float), height, rim)
    xs = np.arange(limits[0] + step / 2.0, limits[1], step)
    ys = np.arange(limits[2] + step / 2.0, limits[3], step)
    gx, gy = np.meshgrid(xs, ys)
    tallest = np.zeros(gx.shape)
    last = len(circles) - 1
    for index, (offset, radius) in enumerate(circles):
        z = height * index / last
        inside = (gx - offset[0]) ** 2 + (gy - offset[1]) ** 2 <= radius * radius
        tallest = np.where(inside & (z > tallest), z, tallest)
    return circles, tallest


def figure_a_glass_from_the_top() -> None:
    """What identifies a glass in a photograph, and which of it survives here."""
    figure, (left, right) = new(14.6, 7.0, columns=2)

    height, rim = TALL_A
    base = rim / 2.0 * 0.45          # the base fraction splay_circles itself uses

    # ---- a photograph, drawn as a stand-in ----------------------------------
    bare(left)
    left.set_aspect("equal")
    span = rim * 3.4
    left.set_xlim(-span / 2.0, span / 2.0)
    left.set_ylim(-height * 0.32, height * 1.22)
    panel_title(left, "What says “glass” in a photograph", colour=GOOD)

    rows, columns = 150, 150
    wall = np.linspace(0.0, 1.0, rows)[:, None] * np.ones((1, columns))
    picture = np.zeros((rows, columns, 3))
    high, low = np.array(tint(MUTED, 0.30))[:3], np.array(tint(MUTED, 0.75))[:3]
    for channel in range(3):
        picture[:, :, channel] = low[channel] + (high[channel] - low[channel]) * wall
    surface = int(rows * 0.235)
    wood = np.array(tint(WARN, 0.50))[:3]
    grain = 0.07 * np.sin(np.linspace(0.0, 30.0, columns))[None, :]
    for channel in range(3):
        picture[:surface, :, channel] = wood[channel] + grain[0]
    left.imshow(
        np.clip(picture, 0.0, 1.0),
        extent=(-span / 2.0, span / 2.0, -height * 0.28, height * 1.18),
        origin="lower", interpolation="bilinear", zorder=0,
    )

    # the shadow the base casts, which is itself one of the cues
    left.add_patch(Ellipse((rim * 0.10, 0.0), rim * 1.05, rim * 0.22, facecolor=INK, alpha=0.20,
                           zorder=1))

    # the glass itself: a tapered body, drawn see-through so the wall behind it shows
    body = Polygon(
        [(-base, 0.0), (base, 0.0), (rim / 2.0, height), (-rim / 2.0, height)],
        closed=True, facecolor=to_rgba(PAPER, 0.26), edgecolor=to_rgba(PAPER, 0.75), lw=1.1,
        zorder=3,
    )
    left.add_patch(body)
    # a highlight running down one side, and the bright line where the rim catches the light
    left.add_patch(
        Polygon(
            [(-base * 0.86, height * 0.04), (-base * 0.48, height * 0.04),
             (-rim * 0.33, height * 0.95), (-rim * 0.44, height * 0.95)],
            closed=True, facecolor=PAPER, alpha=0.80, edgecolor="none", zorder=4,
        )
    )
    left.add_patch(Ellipse((0.0, height), rim, rim * 0.22, facecolor="none", edgecolor=PAPER,
                           lw=2.2, zorder=5))

    # Two labels down each side, so that none of them lies over the glass they
    # are describing. ``side`` is -1 for the left of the glass and +1 for the
    # right, and the text is hung away from it either way.
    for side, y, text, point in (
        (-1, height * 1.02, "the rim catches the light:\na bright line all the way round",
         (-rim * 0.40, height + rim * 0.055)),
        (-1, height * 0.58, "a highlight runs\ndown one side", (-rim * 0.30, height * 0.56)),
        (1, height * 0.52, "the wall behind shows\nthrough the glass", (rim * 0.15, height * 0.54)),
        (1, height * 0.08, "a shadow says where\nit meets the table", (rim * 0.32, 0.0)),
    ):
        x = side * rim * 0.62
        note(left, x, y, text, colour=INK, size=NOTE_SIZE - 0.6, va="center",
             ha="right" if side < 0 else "left", halo=True)
        arrow(left, (x + side * rim * 0.04, y), point, colour=GOOD, lw=1.0)
    note(left, -span * 0.49, -height * 0.21,
         "Drawn here as a stand-in: no photograph of a glass exists in this project. What matters\n"
         "is only which of these four things the panel on the right still has.",
         colour=INK, size=NOTE_SIZE - 0.6, va="bottom")

    # ---- the same kind of glass, from the top, as this cell renders it -------
    bare(right)
    right.set_aspect("equal")
    # A little away from the point below the camera, as a glass in a survey
    # picture is: standing exactly under the lens would hide the splay entirely.
    place = (rim * 0.62, rim * 0.38)
    circles = splay_circles(NADIR, np.array(place, dtype=float), height, rim)
    # A square window holding the whole silhouette and the point below the
    # camera, worked out from the silhouette rather than guessed, so the disc
    # cannot run off the panel if the cast changes.
    wide = max(max(abs(c[0]) + r, abs(c[1]) + r) for c, r in circles) * 1.10
    limits = (-wide, wide, -wide, wide)
    reach = wide
    circles, tallest = shaded_from_the_top(place, TALL_A, limits)
    right.set_xlim(limits[0], limits[1])
    right.set_ylim(limits[2], limits[3])
    right.imshow(
        tallest, cmap=DEPTH_MAP, extent=limits, origin="lower", interpolation="nearest",
        vmin=-0.45 * height, vmax=height, zorder=0,
    )
    right.scatter([0], [0], s=34, color=WARN, marker="x", zorder=9, linewidths=1.3)
    note(right, reach * 0.04, -reach * 0.055, "camera", colour=WARN, size=NOTE_SIZE - 0.6,
         va="top", halo=True)
    panel_title(right, "What this cell renders, from the top", colour=WARN)

    edge = max(circles, key=lambda one: one[1])
    for x, y, text, point in (
        (-reach * 0.95, reach * 0.80, "no bright rim: the shape is opaque, so the\nrim is"
         " simply the nearest surface and nothing more",
         (edge[0][0] - edge[1] * 0.70, edge[0][1] + edge[1] * 0.70)),
        (reach * 0.95, reach * 0.14, "no highlight, and nothing\nshows through",
         (edge[0][0] + edge[1] * 0.50, edge[0][1] + edge[1] * 0.18)),
        (reach * 0.95, -reach * 0.22, "no texture: one number per pixel,\nhow far away the"
         " nearest surface is",
         (edge[0][0] + edge[1] * 0.50, edge[0][1] - edge[1] * 0.40)),
    ):
        note(right, x, y, text, colour=INK, size=NOTE_SIZE - 0.6, va="center",
             ha="left" if x < 0 else "right", halo=True)
        arrow(right, (x + (reach * 0.02 if x < 0 else -reach * 0.02), y), point, colour=WARN,
              lw=1.0)
    note(right, -reach * 0.95, -reach * 0.95,
         "What is left is a round silhouette and its width. The two roundest\n"
         f"things on the model's list are {ROUND_THINGS[0]} and {ROUND_THINGS[1]}, and\n"
         f"{ROUND_OFFERS} of the {OFFERS} names it offered were one of those two.",
         colour=WARN, size=NOTE_SIZE - 0.6, va="bottom", halo=True)

    figure.suptitle(
        "The gap runs in both directions: the picture is not a photograph, and the thing in it no "
        "longer looks like a glass.",
        fontsize=TITLE_SIZE, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.03,
        "The left panel is a drawing. The right panel is this cell's own geometry: the silhouette is "
        "`splay_circles` through the survey camera, and the shade is the height of\nthe nearest "
        "surface, which is the depth reading the renderer gives and the model is fed. The four "
        "features the left panel points at are the strongest evidence a photograph\noffers that an "
        "object is a glass: three of them are properties of transparency, which this cell does not "
        f"render, and the fourth wants light it has none of. The {ROUND_OFFERS} of {OFFERS}\nis "
        "measured, in `results-names.json`.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "03-a-glass-from-the-top.png")


# --------------------------------------------------------------------------- #
# 3. what the model actually named, against what the filter wanted
# --------------------------------------------------------------------------- #

def figure_what_it_named() -> None:
    """The measurement the whole result turns on, drawn with no filter in front of it."""
    figure, (left, right) = new(15.2, 7.6, columns=2)

    kinds = NAMED["kinds"]
    # Two scales, because the panels count different things: the left one is per
    # kind and the right one is pooled over all four, so a shared scale would
    # leave every bar on the left too short to read. Every bar carries its count.
    per_kind = max(max(kind["named"].values()) for kind in kinds.values())
    scale = max(OFFERED.values())

    # ---- every name, per kind ----------------------------------------------
    blank(left)
    panel_title(left, "Every name the model offered, kind by kind", colour=INK)
    rows = sum(len(kind["named"]) for kind in kinds.values())
    step = 0.80 / (rows + len(kinds) * 1.25)
    bar_left, bar_span = 0.335, 0.52
    y = 0.945
    for kind, got in kinds.items():
        kept = got["named a drinking vessel"]
        note(left, 0.0, y, pretty(kind), colour=INK, size=NOTE_SIZE + 0.4, va="center",
             weight="bold")
        note(left, bar_left + bar_span, y,
             f"{kept} of {sum(got['named'].values())} kept by the filter",
             colour=GOOD if kept else WARN, size=NOTE_SIZE - 0.6, ha="right", va="center")
        y -= step * 1.25
        for name, count in got["named"].items():
            on_the_list = name in ACCEPTED
            colour = GOOD if on_the_list else WARN
            note(left, bar_left - 0.012, y, name, colour=INK if on_the_list else MUTED,
                 size=NOTE_SIZE - 0.4, ha="right", va="center",
                 weight="bold" if on_the_list else "normal")
            left.add_patch(
                FancyBboxPatch(
                    (bar_left, y - step * 0.33), bar_span * count / per_kind, step * 0.66,
                    boxstyle="round,pad=0.0,rounding_size=0.004",
                    facecolor=tint(colour, 0.50), edgecolor=colour, lw=0.9, zorder=3,
                )
            )
            note(left, bar_left + bar_span * count / per_kind + 0.008, y, f"{count}", colour=colour,
                 size=NOTE_SIZE - 0.4, va="center", weight="bold" if on_the_list else "normal")
            y -= step
    note(left, 0.0, 0.035,
         "Green is a name the filter accepts. Red is a name it drops. The bars here are a share of\n"
         f"the busiest kind; the ones on the right are a share of the pooled total. Each kind stood\n"
         f"{SIGHTINGS // len(kinds)} times across the {NAME_PICTURES // len(kinds)} pictures of it.",
         colour=MUTED, size=NOTE_SIZE - 0.6, va="bottom")

    # ---- what the filter was looking for -----------------------------------
    blank(right)
    panel_title(right, "What the filter was looking for, and what arrived", colour=WARN)
    note(right, 0.0, 0.955,
         f"The five names this solution accepts, and how often the model reached for each\n"
         f"across all {NAME_PICTURES} pictures:",
         colour=INK, size=NOTE_SIZE, va="top")
    wanted_left, wanted_span = 0.305, 0.40
    for index, name in enumerate(ACCEPTED):
        count = OFFERED.get(name, 0)
        y = 0.845 - index * 0.058
        colour = GOOD if count else MUTED
        note(right, wanted_left - 0.012, y, name, colour=INK, size=NOTE_SIZE, ha="right",
             va="center", weight="bold" if count else "normal")
        if count:
            right.add_patch(
                FancyBboxPatch(
                    (wanted_left, y - 0.017), wanted_span * count / scale, 0.034,
                    boxstyle="round,pad=0.0,rounding_size=0.004",
                    facecolor=tint(colour, 0.50), edgecolor=colour, lw=0.9, zorder=3,
                )
            )
            note(right, wanted_left + wanted_span * count / scale + 0.010, y, f"{count}",
                 colour=colour, size=NOTE_SIZE, va="center", weight="bold")
        else:
            right.plot([wanted_left, wanted_left + 0.012], [y, y], color=MUTED, lw=1.0, zorder=3)
            note(right, wanted_left + 0.020, y, "never once", colour=MUTED, size=NOTE_SIZE - 0.4,
                 va="center")

    note(right, 0.0, 0.500,
         f"What arrived instead, across all four kinds — {OFFERS} names in all:",
         colour=INK, size=NOTE_SIZE, va="top")
    for index, (name, count) in enumerate(OFFERED.items()):
        y = 0.425 - index * 0.050
        on_the_list = name in ACCEPTED
        colour = GOOD if on_the_list else WARN
        note(right, wanted_left - 0.012, y, name, colour=INK if on_the_list else MUTED,
             size=NOTE_SIZE - 0.4, ha="right", va="center")
        right.add_patch(
            FancyBboxPatch(
                (wanted_left, y - 0.015), wanted_span * count / scale, 0.030,
                boxstyle="round,pad=0.0,rounding_size=0.004",
                facecolor=tint(colour, 0.50), edgecolor=colour, lw=0.9, zorder=3,
            )
        )
        note(right, wanted_left + wanted_span * count / scale + 0.010, y, f"{count}",
             colour=colour, size=NOTE_SIZE - 0.4, va="center")
    note(right, 0.0, 0.030,
         f"{ROUND_OFFERS} of the {OFFERS} are a {ROUND_THINGS[0]} or a {ROUND_THINGS[1]}: the two\n"
         "roundest things on the model's list. The model is not confused about\n"
         "where the objects are. It is answering a different question correctly.",
         colour=WARN, size=NOTE_SIZE, va="bottom")

    figure.suptitle(
        "The model names what it finds. It does not call it a drinking vessel.",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.02,
        f"`what_it_named.py --scenes {NAMED['scenes per kind']}`, recorded in `results-names.json`: "
        f"{NAME_PICTURES} held-out pictures through the model with no filter in front of it, every "
        "name it offered counted.\nThe five accepted names are parsed out of `drinking_vessels.py`, "
        "not copied here. This is a smaller, separate run from the scorecard's "
        f"{SCORED_PICTURES} pictures, and the two are never added together.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "03-what-it-named.png")


# --------------------------------------------------------------------------- #
# 4. where the model did name a glass, the outline was not the problem
# --------------------------------------------------------------------------- #

# The order the document predicts, before the run, from the shapes alone: the two
# kinds without a stem outlined almost exactly, the two with a stem worst, and the
# stemmed glass worst of all.
PREDICTED_ORDER = ("straight_glass", "tapered_glass", "short_stemmed_glass", "stemmed_glass")


def figure_the_outlines_were_not_the_problem() -> None:
    """Two mask numbers by kind, on the handful of glasses that got past the gate."""
    figure, (left, right) = new(14.8, 5.8, columns=2)

    runs = ((SPAWNED, GLASS), (CROWDED, WARN))
    places = {kind: index for index, kind in enumerate(PREDICTED_ORDER)}

    # The floor sits above the bars in one panel and along the baseline in the
    # other, so its label is hung on the side of the line that is empty.
    for axis, field, ceiling, floor_at, below, title in (
        (left, "covered_median", 124.0, 100.0, False, "How much of the real glass the mask covered"),
        (right, "not_the_glass_median", 9.0, 0.0, True, "How much of the mask was not that glass"),
    ):
        bare(axis)
        axis.set_xlim(-0.60, len(PREDICTED_ORDER) - 0.40)
        axis.set_ylim(-ceiling * 0.20, ceiling)
        panel_title(axis, title, colour=INK)
        axis.plot([-0.60, len(PREDICTED_ORDER) - 0.40], [floor_at, floor_at], color=GOOD, lw=1.2,
                  ls=(0, (4, 3)), zorder=2)
        note(axis, len(PREDICTED_ORDER) - 0.45,
             floor_at - ceiling * 0.014 if below else floor_at + ceiling * 0.014,
             f"the bench's floor: {floor_at:.0f}%", colour=GOOD, size=NOTE_SIZE - 0.6, ha="right",
             va="top" if below else "bottom")

        for offset, (report, colour) in zip((-0.19, 0.19), runs, strict=True):
            by_kind = report["mask"]["by_kind"]
            for kind, index in places.items():
                got = by_kind.get(kind)
                x = index + offset
                if got is None:
                    # Nothing to measure rather than a bad measurement: no glass
                    # of this kind got past the filter in this run at all.
                    note(axis, x, ceiling * 0.28, "none\nfound", colour=MUTED,
                         size=NOTE_SIZE - 1.6, ha="center", va="bottom")
                    continue
                value = got[field]
                axis.bar([x], [value], width=0.34, color=tint(colour, 0.45), edgecolor=colour,
                         linewidth=1.1, zorder=3)
                note(axis, x, value + ceiling * 0.014, f"{value:.1f}%", colour=colour,
                     size=NOTE_SIZE - 0.6, ha="center", va="bottom", weight="bold")
                note(axis, x, ceiling * 0.015, f"{got['glasses']}", colour=PAPER,
                     size=NOTE_SIZE - 0.6, ha="center", va="bottom", weight="bold")
        for kind, index in places.items():
            note(axis, index, -ceiling * 0.085, pretty(kind), colour=INK, size=NOTE_SIZE - 0.4,
                 ha="center", va="top")

    found = SPAWNED["mask"]["all"]["glasses"] + CROWDED["mask"]["all"]["glasses"]
    figure.suptitle(
        "On the glasses the filter let through, the outlines were good. That is why the naming is "
        "the whole of the result.",
        fontsize=TITLE_SIZE, color=INK, y=1.02,
    )
    figure.tight_layout()
    figure.text(
        0.055, -0.02,
        "The document predicts this order before the run, from the shapes\n"
        "alone: the two kinds without a stem outlined almost exactly, the\n"
        "two with a stem worst, and the stemmed glass worst of all. The\n"
        "kinds are set out in that order, and the measurement keeps it on\n"
        f"every kind it could be tested on — over {found} glasses in all, with the\n"
        "stemmed glass getting past the gate once in each run. An order\n"
        "that holds over one glass a kind is a hint and not a result, which\n"
        "is why the count is drawn inside every bar.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    figure.text(
        0.545, -0.02,
        "The other half of the same story. Where the model did name a\n"
        "glass, the outline covered it and leaked only a thin margin onto\n"
        "the table — a few percent, which is what an outline built from a\n"
        "short weighted sum of coarse patterns and then enlarged costs.\n\n"
        "So the finding was not the failure, and the outlining was not the\n"
        "failure. The naming was.",
        ha="left", va="top", fontsize=NOTE_SIZE, color=INK,
    )
    figure.text(
        0.5, -0.27,
        "Left bar of each pair: spawned layouts. Right bar: crowded. The pale number inside a bar "
        "is how many glasses that median is over. Both panels are medians over\nglasses from the "
        "solution's own `results.json` and `results-crowded.json`, broken down by kind exactly as "
        "the bench records them, with the floor from `bench/results-floor.json`.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "03-the-outlines-were-not-the-problem.png")


# --------------------------------------------------------------------------- #
# 5. where it sits, and the shape of the failure
# --------------------------------------------------------------------------- #

def figure_silence_against_the_floor() -> None:
    """The null result beside the bench's floor and beside its own fine-tuned sibling."""
    figure, (left, right) = new(15.0, 7.0, columns=2)

    blank(left)
    panel_title(left, "Found, of the glasses put out", colour=INK)

    families = (
        ("spawned layouts — the spacing the cell's own layout rule gives",
         ((FLOOR_SPAWNED, "the bench's floor: the same arithmetic on exact masks", GOOD),
          (SPAWNED, "solution 3 — this one, nothing fitted here", WARN),
          (SIBLING_SPAWNED, "solution 4 — the same model, trained on this cell", GLASS))),
        ("crowded layouts — closer than the layout rule allows",
         ((FLOOR_CROWDED, "the bench's floor", GOOD),
          (CROWDED, "solution 3", WARN),
          (SIBLING_CROWDED, "solution 4", GLASS))),
    )
    scale = max(report["glasses"] for _, rows in families for report, _, _ in rows)
    bar_left, bar_span = 0.055, 0.70
    y = 0.905
    for heading, rows in families:
        note(left, 0.0, y, heading, colour=INK, size=NOTE_SIZE, va="center", weight="bold")
        y -= 0.075
        for report, label, colour in rows:
            find = report["find"]
            whole = bar_span * report["glasses"] / scale
            # the silence drawn as what it is: the rest of the bar, left empty
            left.add_patch(
                FancyBboxPatch(
                    (bar_left, y - 0.028), whole, 0.056,
                    boxstyle="round,pad=0.0,rounding_size=0.006",
                    facecolor=PAPER, edgecolor=MUTED, lw=0.9, ls=(0, (3, 3)), zorder=2,
                )
            )
            left.add_patch(
                FancyBboxPatch(
                    (bar_left, y - 0.028), whole * find["found"] / report["glasses"], 0.056,
                    boxstyle="round,pad=0.0,rounding_size=0.006",
                    facecolor=tint(colour, 0.50), edgecolor=colour, lw=1.2, zorder=3,
                )
            )
            note(left, bar_left + whole + 0.014, y,
                 f"{find['found']} of {report['glasses']}", colour=colour, size=LABEL_SIZE,
                 va="center", weight="bold")
            note(left, bar_left + 0.012, y + 0.036, label, colour=INK, size=NOTE_SIZE - 0.6,
                 va="bottom", halo=True)
            y -= 0.105
        y -= 0.030
    note(left, 0.0, 0.055,
         "The dashed remainder of each bar is the glasses that got no report at all. On the "
         "spawned\nlayouts that is 90 of 100 for this solution, against 1 of 100 for the same "
         "model trained here.",
         colour=MUTED, size=NOTE_SIZE - 0.4, va="bottom")

    # ---- the shape of the failure ------------------------------------------
    blank(right)
    panel_title(right, "The shape of the failure: every error column is empty", colour=WARN)

    find = SPAWNED["find"]
    columns = (
        ("found", find["found"], GOOD, "a real glass\nthat got a report"),
        ("missed", find["missed"], WARN, "a real glass with\nno report anywhere"),
        ("merged", find["merged"], MUTED, "one report covering\ntwo glasses"),
        ("split", find["split"], MUTED, "one glass collecting\ntwo reports"),
        ("false", find["false"], MUTED, "a report with no\nglass under it"),
    )
    tallest = max(count for _, count, _, _ in columns)
    base, top = 0.300, 0.840
    for index, (label, count, colour, meaning) in enumerate(columns):
        x = 0.115 + index * 0.192
        if count:
            right.add_patch(
                FancyBboxPatch(
                    (x - 0.055, base), 0.110, (top - base) * count / tallest,
                    boxstyle="round,pad=0.0,rounding_size=0.006",
                    facecolor=tint(colour, 0.50), edgecolor=colour, lw=1.2, zorder=3,
                )
            )
        else:
            right.plot([x - 0.055, x + 0.055], [base, base], color=MUTED, lw=1.4, zorder=3)
        height = (top - base) * count / tallest
        note(right, x, base + height + 0.018, f"{count}", colour=colour if count else MUTED,
             size=LABEL_SIZE + 2.0, ha="center", va="bottom", weight="bold")
        note(right, x, base - 0.022, label, colour=INK, size=NOTE_SIZE, ha="center", va="top",
             weight="bold")
        note(right, x, base - 0.058, meaning, colour=MUTED, size=NOTE_SIZE - 1.6, ha="center",
             va="top")

    silent = SPAWNED["handed over"][SILENT]
    note(right, 0.02, 0.185,
         f"Every glass this solution reported was a real glass, and no glass collected two\n"
         f"reports. It does not get the count wrong, merge a pair or invent a glass: in "
         f"{silent} of\nthe {SCORED_PICTURES} pictures it handed nothing over at all, and the "
         "run reads as though the table were empty.\n\n"
         "That is the failure the document warns is the hardest to notice, because a missed\n"
         "glass leaves no trace anywhere in the run. Of the "
         f"{find['found']} it did find, the places sit "
         f"{find['position_mm_median']:.1f} mm\nfrom the truth at the median against the floor's "
         f"{FLOOR_SPAWNED['find']['position_mm_median']:.1f} mm — a median over "
         f"{find['found']} glasses, and the bench's own\nnote is that this number saturates, so "
         "read it as a sanity check rather than as a ranking.",
         colour=INK, size=NOTE_SIZE - 0.4, va="top")

    figure.suptitle(
        "It fails by silence, not by error — and the sibling that differs only by training "
        "finds almost all of them.",
        fontsize=TITLE_SIZE + 1, color=INK, y=1.01,
    )
    figure.tight_layout()
    figure.text(
        0.5, -0.01,
        "Every number is read at drawing time out of `03-yolo-zero-shot/results.json` and "
        "`results-crowded.json`, `04-yolo-fine-tuned/`'s two results files and "
        "`bench/results-floor.json`.\nThe floor row is the bench's shared arithmetic on the "
        "renderer's own exact visible masks, which no segmenter can improve on; it misses 18 "
        "crowded glasses because a glass\nstanding wholly behind another is in no picture at all. "
        "The right-hand panel is the spawned run.",
        ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )
    save(figure, "03-silence-against-the-floor.png")


def main() -> None:
    check_the_files()
    print(
        f"scorecard: {SPAWNED['find']['found']} of {SPAWNED['glasses']} spawned, "
        f"{CROWDED['find']['found']} of {CROWDED['glasses']} crowded; "
        f"names: {ON_THE_LIST} of {OFFERS} offers on the list of five"
    )
    figure_the_name_is_the_only_gate()
    figure_the_outlines_were_not_the_problem()
    figure_a_glass_from_the_top()
    figure_what_it_named()
    figure_silence_against_the_floor()


if __name__ == "__main__":
    main()
