"""Diagrams for solution 6 — geometry generates, a model ranks.

Everything drawn here is measured against this repository's own reference
implementation of problem 3, not against anything invented for a picture:

- ``problem-3-sim/bench.py`` holds ``scene(seed)``, the crowded tables both
  approaches are scored on, and ``has_room``, the project's own room test;
- ``problem-3-programmed/plan.py`` holds the candidate pushes and the rule
  that ranks them, which is the "geometry generates" half of this solution
  already written;
- ``problem-3-programmed/results.json`` and ``problem-3-learned/results.json``
  hold what each scored on the fifty held-out tables.

``bench.py`` imports MuJoCo, which is not in the root environment, so nothing
here imports it and this file still runs from the project root. The population
numbers in ``SWEEP``, ``ORDERS`` and ``ORACLE`` were measured instead by a
throwaway script run in the environment that does have MuJoCo:

    cd problem-3-programmed && pixi run python <script>

It walked ``bench.scene`` over test seeds 10000 to 10049 — the same fifty
held-out tables ``problem-3-programmed/run.py`` is scored on — calling
``plan.along`` for every heading of every crowded glass and ``bench.has_room``
on every destination, and it carried the run forward on the first thirty of
them under four different choosing rules. The script is not committed because
it belongs to that environment rather than this one; every number it produced
is named in the document beside the claim it supports, and the worked example
below is re-derived here from first principles as a check that the two have not
drifted apart.

The worked example is different. Only its glasses' *positions* are written
down, because a position is a layout and not a measurement of a glass. The
glasses themselves are redrawn here from the project's own drawer at the same
seed, exactly as ``bench.scene`` draws them, so no glass's size appears in
this file. ``check_the_example`` re-runs the room test on what it redrew and
prints the result, so a silent drift between this file and the bench shows up
as a failed check rather than as a wrong picture.

    pixi run python images/generators/problem-3/make_06_images.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from diagram_style import (
    COMFORTABLE_REACH,
    GLASS,
    GLASS_ZONE,
    GOOD,
    GRIP_ROOM,
    INK,
    JAW_TOP,
    LABEL_SIZE,
    LOWEST_GRIP,
    MUTED,
    NOTE_SIZE,
    TABLE_FRICTION,
    TITLE_SIZE,
    WARN,
    bare,
    glass_from_above,
    has_room,
    in_reach,
    in_zone,
    new,
    push_arrow,
    save,
    topple_height,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import draw  # noqa: E402

# ---------------------------------------------------------------------------
# The jaw and the friction. Numbers belonging to the gripper and to the table,
# never to a glass.
#
# JAW_TOP comes from diagram_style, which takes it from bench.py: the middle of
# the jaw rides at LOWEST_GRIP, the jaw is a finger tall, and a glass that is
# wider higher up meets its top edge first. Every tapered glass is wider higher
# up, so JAW_TOP and not LOWEST_GRIP is the height a glass is really pushed at.
#
# plan.py checks the tipping limit at both ends of the range it is willing to
# believe, because nothing in the cell measures friction. TABLE_FRICTION is
# what the simulator really rubs glass on table at; it is ground truth a run is
# scored against, and never an input to any decision the arm makes.
# ---------------------------------------------------------------------------
MU_LOWEST = 0.2
MU_HIGHEST = 0.5

# Measured in the root environment over 400 glasses from the project's own
# drawer, random.Random(0), kind "tapered_glass": the share that slides rather
# than tips when the jaw meets it at each height.
PUSHABLE = {
    LOWEST_GRIP: {0.2: 100.0, 0.3: 93.0, 0.35: 77.0, 0.5: 13.5},
    JAW_TOP: {0.2: 99.2, 0.3: 55.8, 0.35: 25.0, 0.5: 0.0},
}
# The last of those is exact rather than sampled. A push at JAW_TOP slides a
# glass only while its foot is wider than 2 * JAW_TOP * mu, which at 0.5 is
# 65 mm; the widest foot the tapered kind's range allows is its widest rim
# times its largest base fraction, which is under that. So no tapered glass the
# spawner can draw could be pushed at all at that friction.

# plan.py's own enumerator.
HEADINGS = 72                  # one every 5 degrees
HEADING_STEP = 360.0 / HEADINGS
TRAVEL_STEP = 2.0              # mm
LONGEST_PUSH = 150.0           # mm
AIM_MARGIN = 10.0              # mm of room aimed at beyond what is needed

# ---------------------------------------------------------------------------
# Measured by measure_06.py over bench.scene, test seeds 10000-10049.
# Nothing in this block is a glass measurement; they are counts and shares.
# ---------------------------------------------------------------------------
SWEEP = {
    "tables": 50,
    "glasses": 251,
    "crowded": 193,
    "closest_pair_mm": 57,
    "median_neighbour_mm": 94,
    # plan.slides() over the crowded glasses: it slides at both frictions, it
    # tips at both, or it depends and a probe settles it.
    "slides_yes": 36,
    "slides_no": 0,
    "slides_try": 157,
    # Safe pushes per crowded glass: every heading and travel that passes the
    # corridor, zone, reach and tipping tests.
    "safe_median": 193,
    "safe_mean": 261,
    "safe_max": 1209,
    "safe_none_pct": 5.2,
    # Of those, the ones that leave the glass with room.
    "free_median": 0,
    "free_mean": 1.8,
    "free_max": 23,
    "free_none_pct": 71.5,
    "free_one_pct": 4.7,
    "free_five_plus_pct": 15.5,
    # The shape of a non-empty freeing set.
    "free_sets": 55,
    "free_headings_median": 5,
    "free_headings_max": 23,
    "free_one_arc_pct": 60,
    "free_arc_median_deg": 15,
    "free_margin_spread_median_mm": 1,
    "free_margin_spread_p90_mm": 1,
    "free_travel_spread_median_mm": 30,
    # The label: how many glasses have room after the push.
    "free_label_tied_pct": 100.0,
    "ranked_sets": 117,
    "ranked_label_tied_pct": 34.2,
    "ranked_label_max_spread": 3,
    "table_free_sets": 47,
    "table_label_tied_pct": 42.6,
    "table_label_max_spread": 2,
}

# The run carried forward in geometry, thirty tables, four ways of choosing
# which candidate to push, from measure_06.py section C. A push is taken to
# land where it aimed, which results.json says is true to 1.0 mm at the median.
ORDERS = [
    ("plan.py's own rule", 119, 31, 72, 20),
    ("most glasses freed, then eased, then shortest", 119, 31, 88, 20),
    ("uniformly at random from the ranked set", 111, 39, 96, 17),
    ("deliberately the worst of the ranked set", 104, 46, 167, 16),
]
ORDER_TABLES = 30

# The one-ply oracle from measure_06b.py: on each table every distinct first
# push is tried, plan.py's rule runs the rest, and the best result is kept. It
# is an upper bound on what any ranker could win on the opening move, because
# no ranker can do better than being told the answer.
ORACLE = {"tables": 12, "glasses": 60,
          "plan_racked": 44, "plan_refused": 16, "plan_pushes": 29,
          "best_racked": 46, "best_refused": 14, "best_pushes": 29}

# What the two reference implementations scored on the fifty held-out tables,
# read from their own results.json files.
SCORED = {
    "programmed": {"racked": 199, "refused": 52, "toppled": 0, "pushes": 212, "repeats": 90,
                   "aim_median_mm": 1.0, "aim_worst_mm": 3.9, "done": 35},
    "learned": {"racked": 208, "refused": 43, "toppled": 0, "pushes": 113, "repeats": 15,
                "aim_median_mm": 1.7, "aim_worst_mm": 24.8, "done": 34},
}

# ---------------------------------------------------------------------------
# The worked example. bench.scene(EXAMPLE_SEED) draws EXAMPLE_COUNT glasses of
# EXAMPLE_KIND from random.Random(EXAMPLE_SEED) and lays them out crowded; the
# layout is what is written down here, in millimetres, and the glasses are
# redrawn below. EXAMPLE_FREEING is every push of EXAMPLE_MOVER that leaves it
# with room, as (heading in degrees, travel in millimetres).
# ---------------------------------------------------------------------------
EXAMPLE_SEED = 10017
EXAMPLE_KIND = "tapered_glass"
EXAMPLE_COUNT = 4
# The two that already have room and are racked before any push is planned,
# and the two that do not.
EXAMPLE_RACKED_FIRST = (0, 2)
EXAMPLE_CROWDED = (1, 3)
EXAMPLE_POSITIONS = [
    (540.5, -157.0),
    (511.5, -349.1),
    (323.8, -206.0),
    (418.7, -330.5),
]
# Every push that leaves its glass with room, once the other two are gone, as
# (heading in degrees, travel in millimetres). plan.py's enumerator stops each
# heading at the first travel that works, so there is at most one per heading.
EXAMPLE_FREEING = {
    1: [(50, 38), (55, 42), (60, 46), (65, 52), (70, 58), (75, 64), (80, 72), (85, 82),
        (90, 92), (95, 102), (245, 96), (250, 86), (255, 76), (260, 68), (265, 60),
        (270, 54), (275, 48), (280, 44), (285, 40)],
    3: [(55, 120), (60, 108), (65, 98), (70, 88), (75, 78), (80, 70), (85, 62), (90, 56),
        (95, 50), (100, 46), (105, 42), (235, 44), (240, 48), (245, 54), (250, 60),
        (255, 66), (260, 74), (265, 84), (270, 94), (275, 104)],
}
EXAMPLE_SAFE = {1: 823, 3: 1061}
EXAMPLE_EASING = {1: 377, 3: 420}
EXAMPLE_RANKED = 836
# What plan.choose picks out of all of that: the shortest freeing push.
EXAMPLE_CHOICE = (1, 50, 38)


def example_glasses():
    """The example's glasses, redrawn from the project's own drawer.

    ``bench.scene`` draws its outlines with ``random.Random(seed)`` and
    ``glasses.shapes.draw``, in order, before it places them. Repeating that
    here gives the same glasses without importing the bench, and without any
    size being written down in this file.
    """
    rng = random.Random(EXAMPLE_SEED)
    return [draw(EXAMPLE_KIND, rng)[0] for _ in range(EXAMPLE_COUNT)]


def widths(outlines) -> list[float]:
    return [o.max_diameter * 1000.0 for o in outlines]


def feet(outlines) -> list[float]:
    return [2.0 * float(o.radius[0]) * 1000.0 for o in outlines]


def layout_without(index: int, positions, width_list) -> list[tuple[float, float, float]]:
    """Every other glass as (x, y, widest width), which is what has_room reads."""
    return [(positions[k][0], positions[k][1], width_list[k])
            for k in range(len(positions)) if k != index]


def keep_out(index: int, width_list) -> float:
    """How far another glass's middle has to stay from this one's.

    This is the asymmetric part. The room a glass needs is set by how wide its
    *neighbour* is, so the circle drawn round a glass is the one a neighbour's
    middle must stay outside, and a wide glass pushes its neighbours further
    away than a narrow one does.
    """
    return GRIP_ROOM + width_list[index] / 2.0


def room_margin(point, layout) -> float:
    """How much room a glass at ``point`` has beyond what it needs. May be negative."""
    return min((math.hypot(point[0] - ox, point[1] - oy) - GRIP_ROOM - w / 2.0
                for ox, oy, w in layout), default=float("inf"))


def aim_of(centre, heading_degrees: float, travel: float) -> tuple[float, float]:
    angle = math.radians(heading_degrees)
    return (centre[0] + travel * math.cos(angle), centre[1] + travel * math.sin(angle))


# ---------------------------------------------------------------------------
# Drawing helpers.
# ---------------------------------------------------------------------------
def stage(axis, title: str) -> None:
    bare(axis)
    axis.set_title(title, fontsize=TITLE_SIZE, color=INK, pad=9)


def chart(axis, title: str) -> None:
    """A panel that really is a plot: recessive axes, no box round it."""
    axis.set_title(title, fontsize=TITLE_SIZE, color=INK, pad=9)
    axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED, length=3)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
        axis.spines[side].set_linewidth(0.9)


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, **kwargs) -> None:
    axis.text(x, y, text, fontsize=size, color=colour, ha=kwargs.pop("ha", "center"), **kwargs)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.015, text, fontsize=NOTE_SIZE, color=MUTED, ha="center", va="bottom")


def bars(axis, labels, values, colours, span: float, note_of=None) -> None:
    """A row of horizontal bars with the value written at the end of each."""
    for position, (label, value, colour) in enumerate(zip(labels, values, colours, strict=True)):
        y = -position * 1.0
        axis.add_patch(Rectangle((0.0, y - 0.26), span * value / max(values), 0.52,
                                 facecolor=to_rgba(colour, 0.45), edgecolor=colour, lw=1.0))
        axis.text(0.0, y + 0.38, label, fontsize=LABEL_SIZE, color=INK, ha="left", va="bottom")
        text = note_of(position) if note_of else f"{value}"
        axis.text(span * value / max(values) + span * 0.015, y, text,
                  fontsize=NOTE_SIZE, color=colour, ha="left", va="center")


# ---------------------------------------------------------------------------
# 2. How large the candidate sets are, and how alike their members are.
# ---------------------------------------------------------------------------
def picture_how_alike() -> None:
    """The two sets the geometry produces, and which of them holds any signal."""
    figure, (sizes, margins, flat) = new(14.6, 4.8, columns=3)

    # ------------------------------- panel 1: safe pushes against freeing ones
    stage(sizes, "What the enumerator produces, per crowded glass")
    sizes.set_xlim(0.0, 10.0)
    sizes.set_ylim(-5.6, 2.2)
    rows = [
        (f"safe pushes: median {SWEEP['safe_median']}", 1.3, GLASS,
         f"mean {SWEEP['safe_mean']}, most {SWEEP['safe_max']};\n"
         f"{SWEEP['safe_none_pct']:.0f}% of crowded glasses have none"),
        (f"of those, the ones that leave it with room: median {SWEEP['free_median']}", -0.9, WARN,
         f"mean {SWEEP['free_mean']:.1f}, most {SWEEP['free_max']};\n"
         f"{SWEEP['free_none_pct']:.0f}% have none at all"),
    ]
    widest = SWEEP["safe_median"]
    for label, y, colour, tail in rows:
        value = SWEEP["safe_median"] if colour is GLASS else max(SWEEP["free_median"], 0.4)
        sizes.add_patch(Rectangle((0.4, y - 0.26), 8.6 * value / widest, 0.52,
                                  facecolor=to_rgba(colour, 0.45), edgecolor=colour, lw=1.1))
        sizes.text(0.4, y + 0.40, label, fontsize=LABEL_SIZE, color=INK, ha="left", va="bottom")
        sizes.text(0.4, y - 0.40, tail, fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top")
    note(sizes, 5.0, -2.75,
         f"The gap between those two bars is the whole story of\n"
         f"this cell. The geometry can almost always find a push\n"
         f"that is safe. It can rarely find one that finishes the job,\n"
         f"so {SWEEP['free_none_pct']:.0f}% of the time the planner falls back on a push\n"
         f"that only helps a little.", INK, va="top")

    # --------------------------- panel 2: the survivors land in the same place
    chart(margins, "How much the freeing pushes differ")
    items = [
        ("room left over,\nbest minus worst", SWEEP["free_margin_spread_median_mm"], GOOD),
        ("travel,\nlongest minus shortest", SWEEP["free_travel_spread_median_mm"], GLASS),
    ]
    for position, (label, value, colour) in enumerate(items):
        y = -1.5 * position
        margins.barh([y], [value], height=0.5, color=to_rgba(colour, 0.5),
                     edgecolor=colour, lw=1.0)
        margins.text(value + 1.2, y, f"{value} mm", fontsize=LABEL_SIZE, color=colour,
                     ha="left", va="center")
        margins.text(0.0, y + 0.42, label, fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    margins.set_xlim(0.0, 44.0)
    margins.set_ylim(-4.6, 1.6)
    margins.set_yticks([])
    margins.spines["left"].set_visible(False)
    margins.set_xlabel("millimetres of spread inside one candidate set, median",
                       fontsize=LABEL_SIZE, color=INK)
    note(margins, 22.0, -1.05,
         "A freeing push stops at the first travel that\n"
         "works, so every survivor comes to rest within a\n"
         "millimetre of the same room margin. They differ\n"
         "in how far the glass travels to get there, and\n"
         "the geometry prints that number for nothing.", INK, va="top")

    # ---------------------------------------- panel 3: the label does not vary
    chart(flat, "Does the label vary inside a candidate set?")
    names = ["the pushes that\nfinish the job", "every push\nworth making"]
    tied = [SWEEP["free_label_tied_pct"], SWEEP["ranked_label_tied_pct"]]
    counts = [SWEEP["free_sets"], SWEEP["ranked_sets"]]
    colours = [WARN, GOOD]
    positions = np.arange(len(names))
    flat.bar(positions, tied, width=0.5, color=[to_rgba(c, 0.5) for c in colours],
             edgecolor=colours, lw=1.1)
    for x, (value, count) in enumerate(zip(tied, counts, strict=True)):
        flat.text(x, value + 2.5, f"{value:.0f}% tied", fontsize=LABEL_SIZE, color=colours[x],
                  ha="center", va="bottom")
        flat.text(x, 3.0, f"{count} sets", fontsize=NOTE_SIZE, color=INK, ha="center", va="bottom")
    flat.text(0.0, -24.0, "what legality already guarantees", fontsize=NOTE_SIZE, color=MUTED,
              ha="center", va="top")
    flat.text(1.0, -24.0, "what the planner really sorts", fontsize=NOTE_SIZE, color=MUTED,
              ha="center", va="top")
    flat.set_xticks(positions)
    flat.set_xticklabels(names, fontsize=LABEL_SIZE)
    flat.set_xlim(-0.65, 1.65)
    flat.set_ylim(0.0, 142.0)
    flat.set_ylabel("share of sets in which every candidate scores the same",
                    fontsize=NOTE_SIZE, color=INK)
    note(flat, 0.5, 138.0,
         "the label is how many glasses have room after the push", INK, va="top")

    footer(figure,
           f"Measured over the {SWEEP['tables']} held-out tables of bench.scene, {SWEEP['glasses']} "
           f"glasses, {SWEEP['crowded']} of them without room at the start. Where the geometry can "
           f"finish the job, every way of finishing it scores the\nsame: the freeing set is a complete "
           f"tie in {SWEEP['free_label_tied_pct']:.0f}% of the {SWEEP['free_sets']} sets there are, and "
           f"its members come to rest within {SWEEP['free_margin_spread_median_mm']} mm of each other. "
           f"The variation is in the wider ranked set, where most candidates do not finish the job.")
    figure.subplots_adjust(bottom=0.22, top=0.90, wspace=0.24)
    save(figure, "06-how-alike-the-survivors-are.png")
    print("  how alike: freeing sets tied on the label in "
          f"{SWEEP['free_label_tied_pct']:.0f}% of {SWEEP['free_sets']}; "
          f"ranked sets tied in {SWEEP['ranked_label_tied_pct']:.1f}% of {SWEEP['ranked_sets']}")


# ---------------------------------------------------------------------------
# 3. The tipping check, and where the refusals really come from.
# ---------------------------------------------------------------------------
def picture_the_refusals() -> None:
    """What the filter removes before the model is asked, and what it does not."""
    figure, (limit, refusals) = new(13.4, 5.0, columns=2)

    # ---------------------------- panel 1: the tipping check plan.py makes
    chart(limit, "The tipping check, as plan.py makes it")
    top, right_edge = 175.0, 100.0
    foot = np.linspace(20.0, right_edge, 400)
    for mu, colour in ((MU_LOWEST, GOOD), (TABLE_FRICTION, INK), (MU_HIGHEST, WARN)):
        height = np.array([topple_height(f, mu) for f in foot])
        inside = height <= top
        limit.plot(foot[inside], height[inside], color=colour,
                   lw=1.7 if mu == TABLE_FRICTION else 1.3,
                   ls="-" if mu == TABLE_FRICTION else (0, (4, 3)))
        # The label goes where the curve leaves the panel, so it never floats
        # off the top with its line nowhere near it.
        last = float(foot[inside][-1])
        reach = min(topple_height(last, mu), top)
        limit.text(last + 1.5, reach - (4.0 if reach >= top - 1.0 else 0.0),
                   f"friction {mu:g}" + (" — the simulator's own" if mu == TABLE_FRICTION else ""),
                   fontsize=NOTE_SIZE, color=colour, ha="left",
                   va="top" if reach >= top - 1.0 else "center")
    limit.axhline(JAW_TOP, color=INK, lw=1.6)
    limit.text(21.0, JAW_TOP + 3.0,
               f"{JAW_TOP:.0f} mm, the top edge of the jaw: where a glass is really pushed",
               fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    limit.axhline(LOWEST_GRIP, color=MUTED, lw=1.1, ls=(0, (3, 3)))
    limit.text(21.0, LOWEST_GRIP - 3.0, f"{LOWEST_GRIP:.0f} mm, where the middle of the jaw rides",
               fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top")
    limit.set_xlim(20.0, 132.0)
    limit.set_ylim(0.0, top)
    limit.set_xlabel("the glass's foot, millimetres across", fontsize=LABEL_SIZE, color=INK)
    limit.set_ylabel("the height a push starts tipping it, mm", fontsize=LABEL_SIZE, color=INK)
    note(limit, 131.0, 44.0,
         f"A glass slides while the jaw meets it below\nits curve. plan.py calls a glass safe when "
         f"even\n{MU_HIGHEST:g} clears the line, refuses it when even {MU_LOWEST:g}\ndoes not, and "
         f"probes when the two disagree.\nOver the {SWEEP['crowded']} crowded glasses of the "
         f"held-out\ntables that came to {SWEEP['slides_yes']} safe, "
         f"{SWEEP['slides_try']} to probe, {SWEEP['slides_no']} refused.", INK, va="top", ha="right")

    # ---------------------------------- panel 2: what the refusals really are
    stage(refusals, f"Why {SCORED['programmed']['refused']} glasses were refused")
    refusals.set_xlim(-0.3, 10.0)
    refusals.set_ylim(-4.3, 1.1)
    bars(refusals,
         ["nowhere clear to push it to",
          "it tips before it slides",
          "toppled, pushed out of the zone, or picked without room"],
         [SCORED["programmed"]["refused"], SWEEP["slides_no"], 0],
         [WARN, MUTED, MUTED], 8.6,
         note_of=lambda i: [f"{SCORED['programmed']['refused']}", "0", "0"][i])
    refusals.text(0.0, -2.75,
                  f"Read the two panels together. The tipping arithmetic is real and it is inside the\n"
                  f"filter, so a glass that would go over never reaches a ranker. On these tables it\n"
                  f"refuses nothing, because the jaw meets a glass low enough that the foot usually\n"
                  f"wins. Every refusal problem-3-programmed made on the {SWEEP['tables']} held-out "
                  f"tables was the other\nkind: {SWEEP['safe_none_pct']:.0f}% of crowded glasses have "
                  f"no safe push at all, and most of the rest have\nnone that finishes the job. That "
                  f"is a shortage of candidates, and no ranking repairs it.",
                  fontsize=NOTE_SIZE, color=INK, ha="left", va="top")

    footer(figure,
           f"The simulator rubs glass on table at {TABLE_FRICTION:g}. The arm is never told that "
           f"number and nothing in the cell measures it, so plan.py carries the whole range "
           f"{MU_LOWEST:g} to {MU_HIGHEST:g} and settles the cases in between by\npushing 5 mm and "
           f"looking. Keep the two apart when reading any figure here: "
           f"{TABLE_FRICTION:g} is ground truth a run is scored against, and never an input to a "
           f"decision.")
    figure.subplots_adjust(bottom=0.17, top=0.91, wspace=0.16)
    save(figure, "06-where-the-refusals-come-from.png")
    print(f"  refusals: slides() gave {SWEEP['slides_yes']} yes, {SWEEP['slides_try']} try, "
          f"{SWEEP['slides_no']} no; results.json refused "
          f"{SCORED['programmed']['refused']}, all for nowhere to push to")


# ---------------------------------------------------------------------------
# 4. The pattern itself, with this cell's numbers in it.
# ---------------------------------------------------------------------------
def picture_the_pattern() -> None:
    """Generate, veto, then order — against a model whose output is the push."""
    figure, (ranked, policy) = new(13.4, 5.4, columns=2)
    for axis in (ranked, policy):
        bare(axis)
        axis.set_xlim(0.0, 10.0)
        axis.set_ylim(-0.9, 10.0)

    def band(axis, y, height, label, colour, alpha=0.14):
        axis.add_patch(Rectangle((0.6, y), 8.8, height, facecolor=to_rgba(colour, alpha),
                                 edgecolor=colour, lw=1.1, zorder=2))
        axis.text(0.82, y + height - 0.22, label, fontsize=LABEL_SIZE, color=INK,
                  ha="left", va="top", zorder=4)

    def arrow(axis, y_from, y_to, colour=INK):
        push_arrow(axis, (5.0, y_from), (5.0, y_to), colour=colour, lw=1.4, zorder=5)

    ranked.set_title("Geometry generates, geometry vetoes, the model orders",
                     fontsize=TITLE_SIZE, color=INK, pad=9)
    band(ranked, 7.9, 1.5, f"the enumerator sweeps {HEADINGS} headings and every {TRAVEL_STEP:.0f} mm",
         GLASS)
    ranked.text(0.82, 8.22,
                f"out to {LONGEST_PUSH:.0f} mm, stopping each heading at the first clash",
                fontsize=NOTE_SIZE, color=MUTED, ha="left", va="bottom")
    arrow(ranked, 7.9, 6.9)
    band(ranked, 5.4, 1.5, "the filter keeps only what is safe", WARN)
    ranked.text(0.82, 5.72,
                "a clear corridor for glass, fingers and wrist; the zone; the reach; tipping",
                fontsize=NOTE_SIZE, color=MUTED, ha="left", va="bottom")
    arrow(ranked, 5.4, 4.6)
    band(ranked, 2.4, 2.2,
         f"a median of {SWEEP['safe_median']} safe pushes, every one of them safe", GOOD)
    ranked.add_patch(Rectangle((0.6, 2.4), 8.8, 2.2, facecolor="none", edgecolor=GOOD,
                               lw=2.0, zorder=3))
    ranked.annotate("", xy=(8.2, 3.42), xytext=(1.8, 3.42), zorder=6,
                    arrowprops={"arrowstyle": "<|-|>", "color": GOOD, "lw": 1.2})
    ranked.text(5.0, 3.02, "the model's whole output: a reordering inside this box",
                fontsize=NOTE_SIZE, color=GOOD, ha="center", va="bottom")
    ranked.text(5.0, 2.62, "it cannot add a push, and it cannot overrule a rejection",
                fontsize=NOTE_SIZE, color=MUTED, ha="center", va="bottom")
    arrow(ranked, 2.4, 1.5, GOOD)
    band(ranked, 0.35, 0.9, "the arm makes the top one, then looks again", INK, alpha=0.06)
    ranked.text(9.4, 7.02, "safety lives here", fontsize=NOTE_SIZE, color=WARN,
                ha="right", va="bottom")

    policy.set_title("A model that chooses the push instead", fontsize=TITLE_SIZE, color=INK, pad=9)
    band(policy, 7.9, 1.5, "the arrangement, as numbers or as a picture", GLASS)
    arrow(policy, 7.9, 6.9)
    band(policy, 5.4, 1.5, "the model emits a heading and a distance", MUTED, alpha=0.10)
    policy.text(0.82, 5.72, "its output space is every push, safe or not",
                fontsize=NOTE_SIZE, color=MUTED, ha="left", va="bottom")
    arrow(policy, 5.4, 4.6)
    band(policy, 2.4, 2.2, "a toppled glass is among the things it can emit", WARN)
    policy.text(5.0, 3.05, "nothing in this project stands a glass back up",
                fontsize=NOTE_SIZE, color=MUTED, ha="center", va="bottom")
    policy.text(5.0, 2.66, "and nothing in the model's shape says which push it just chose",
                fontsize=NOTE_SIZE, color=MUTED, ha="center", va="bottom")
    arrow(policy, 2.4, 1.5, WARN)
    band(policy, 0.35, 0.9, "a geometric check has to be bolted on here anyway", INK, alpha=0.06)
    policy.text(5.0, 0.16,
                "and once it is bolted on it is doing the safety work that the left-hand column\n"
                "does up front, for a model that is far harder to train",
                fontsize=NOTE_SIZE, color=MUTED, ha="center", va="top")

    footer(figure,
           "This is the pattern worth taking away, and it is worth taking away even though it earns "
           "little here. The model's output is a permutation of a set the arithmetic has already "
           "cleared, so no value it can emit is\nan unsafe push. Delete its weights, keep plan.py's "
           "printed rule, and the run still works — which is exactly what problem-3-programmed is, "
           "and it topples nothing on the fifty held-out tables.")
    figure.subplots_adjust(bottom=0.15, top=0.91, wspace=0.08)
    save(figure, "06-generate-veto-then-rank.png")
    print("  the pattern: drawn with the enumerator's real shape, "
          f"{HEADINGS} headings x {TRAVEL_STEP:.0f} mm steps to {LONGEST_PUSH:.0f} mm")


# ---------------------------------------------------------------------------
# 5. Does the order matter, and where the learning actually paid.
# ---------------------------------------------------------------------------
def picture_does_order_matter() -> None:
    """The evidence for the verdict: reorder the same candidate set and count."""
    figure, (orders, scored) = new(14.2, 5.8, columns=2)

    # ------------------------------------- panel 1: four ways of choosing
    chart(orders, f"The same candidates, four orders, {ORDER_TABLES} tables")
    names = [row[0] for row in ORDERS]
    pushes = [row[3] for row in ORDERS]
    refused = [row[2] for row in ORDERS]
    positions = np.arange(len(names))
    colours = [GOOD, GLASS, WARN, WARN]
    orders.barh(-positions, pushes, height=0.46, color=[to_rgba(c, 0.45) for c in colours],
                edgecolor=colours, lw=1.1)
    for y, (push, miss) in enumerate(zip(pushes, refused, strict=True)):
        orders.text(push + 3.0, -y, f"{push} pushes, {miss} glasses refused",
                    fontsize=NOTE_SIZE, color=colours[y], ha="left", va="center")
        orders.text(0.0, -y + 0.38, names[y], fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    orders.set_xlim(0.0, 250.0)
    orders.set_ylim(-9.6, 1.2)
    orders.set_yticks([])
    orders.spines["left"].set_visible(False)
    orders.set_xlabel("pushes taken to clear the same thirty tables", fontsize=LABEL_SIZE, color=INK)
    note(orders, 125.0, -4.35,
         f"Ordering is worth something: shuffle the same set and the run costs\n"
         f"{ORDERS[2][3] - ORDERS[0][3]} more pushes and leaves {ORDERS[2][2] - ORDERS[0][2]} "
         f"more glasses behind. plan.py's printed rule already\nhas that. Ranking by the label this "
         f"solution proposes clears the same\nglasses and takes {ORDERS[1][3] - ORDERS[0][3]} "
         f"more pushes to do it.\n\n"
         f"And a ranker cannot beat being told the answer. Over "
         f"{ORACLE['tables']} tables and\n{ORACLE['glasses']} glasses, trying every possible first "
         f"push and keeping the best\nresult racks {ORACLE['best_racked']} against plan.py's "
         f"{ORACLE['plan_racked']}, for the same "
         f"{ORACLE['plan_pushes']} pushes. That is\nthe whole of what a perfect opening choice is "
         f"worth here: {ORACLE['best_racked'] - ORACLE['plan_racked']} glasses in "
         f"{ORACLE['glasses']}.", INK, va="top")

    # ---------------------------- panel 2: what the two implementations scored
    chart(scored, f"The two implementations, {SWEEP['tables']} held-out tables")
    pair = [("geometry alone\nproblem-3-programmed", SCORED["programmed"], GLASS),
            ("a learned forward model and a search\nproblem-3-learned", SCORED["learned"], GOOD)]
    width = 0.34
    metrics = ["glasses racked", "glasses refused", "pushes taken", "repeat pushes"]
    keys = ["racked", "refused", "pushes", "repeats"]
    spots = np.arange(len(metrics))
    for offset, (name, data, colour) in zip((-width / 2, width / 2), pair, strict=True):
        values = [data[k] for k in keys]
        scored.bar(spots + offset, values, width=width, color=to_rgba(colour, 0.5),
                   edgecolor=colour, lw=1.1, label=name)
        for x, value in zip(spots + offset, values, strict=True):
            scored.text(x, value + 4.0, str(value), fontsize=NOTE_SIZE, color=colour,
                        ha="center", va="bottom")
    scored.set_xticks(spots)
    scored.set_xticklabels(metrics, fontsize=NOTE_SIZE)
    scored.set_ylim(0.0, 285.0)
    scored.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper left", ncol=1)
    note(scored, 3.52, 258.0,
         f"Both topple nothing.\nThe learned one racks "
         f"{SCORED['learned']['racked'] - SCORED['programmed']['racked']} more glasses\n"
         f"in {SCORED['programmed']['pushes'] - SCORED['learned']['pushes']} fewer pushes — and not "
         f"by\nordering these candidates\nbetter. It replaced the model\nof what a push does, "
         f"which is\nthe quantity geometry gets wrong.", INK, va="top", ha="right")

    footer(figure,
           "This is the evidence the verdict rests on. A better order is worth a little and "
           "plan.py's rule already collects it. The large gain in this cell came from somewhere "
           "else entirely: predicting where the glass\nactually goes. Read the right-hand panel as "
           "the answer to 'should a model go here at all' — yes, but as a forward model, not as a "
           "ranker over candidates the arithmetic has already sorted.")
    figure.subplots_adjust(bottom=0.20, top=0.90, wspace=0.16)
    save(figure, "06-does-the-order-matter.png")
    for name, racked, miss, push, cleared in ORDERS:
        print(f"    {name:46s} racked {racked} refused {miss} pushes {push} cleared {cleared}")
    print(f"    {'a perfect first push, ' + str(ORACLE['tables']) + ' tables':46s} racked "
          f"{ORACLE['best_racked']} refused {ORACLE['best_refused']} pushes {ORACLE['best_pushes']}"
          f"  against plan.py's {ORACLE['plan_racked']}/{ORACLE['plan_refused']}/"
          f"{ORACLE['plan_pushes']}")


# ---------------------------------------------------------------------------
# 1. The room test, and the fan of pushes that satisfies it.
# ---------------------------------------------------------------------------
def example_state():
    """The worked example, redrawn: outlines, widths, feet, and the two states.

    The first state is the table as the run first sees it. The second is what
    is left once every glass that already has room has been racked, which is
    where the planner is actually asked for a push.
    """
    outlines = example_glasses()
    width_list = widths(outlines)
    foot_list = feet(outlines)
    return outlines, width_list, foot_list


def check_the_example(width_list) -> None:
    """Re-run the room test on what was redrawn, and print what it found.

    If this file and the bench ever drift apart, the numbers printed here stop
    matching the ones the measurement script reported, and the pictures are
    wrong in a way somebody can see.
    """
    print("  the worked example, checked against what was redrawn:")
    for index, centre in enumerate(EXAMPLE_POSITIONS):
        others = layout_without(index, EXAMPLE_POSITIONS, width_list)
        print(f"    g{index} at ({centre[0]:.1f}, {centre[1]:.1f}): widest {width_list[index]:.1f} mm, "
              f"a neighbour must stay {keep_out(index, width_list):.1f} mm away, "
              f"it has {room_margin(centre, others):+.1f} mm of its own, "
              f"has room: {has_room(centre, others)}")
    stay = [k for k in range(len(EXAMPLE_POSITIONS)) if k not in EXAMPLE_RACKED_FIRST]
    for mover in EXAMPLE_CROWDED:
        others = [(EXAMPLE_POSITIONS[k][0], EXAMPLE_POSITIONS[k][1], width_list[k])
                  for k in stay if k != mover]
        margins, ok = [], 0
        for heading, travel in EXAMPLE_FREEING[mover]:
            aim = aim_of(EXAMPLE_POSITIONS[mover], heading, travel)
            margins.append(room_margin(aim, others))
            ok += int(has_room(aim, others) and in_zone(aim) and in_reach(aim))
        print(f"    g{mover}: {len(EXAMPLE_FREEING[mover])} freeing pushes, {ok} of them still pass "
              f"the room test here, margins {min(margins):.1f} to {max(margins):.1f} mm")


def picture_the_room_test() -> None:
    """The asymmetric room test on a real table, and the fan that satisfies it."""
    outlines, width_list, foot_list = example_state()
    check_the_example(width_list)
    stay = [k for k in range(len(EXAMPLE_POSITIONS)) if k not in EXAMPLE_RACKED_FIRST]

    figure, (test, fan) = new(13.8, 6.6, columns=2)

    # ------------------------------------- panel 1: who has room, and who does not
    stage(test, "The room test, on a table bench.scene drew")
    table_panel(test)
    widest_one = max(range(len(width_list)), key=lambda k: width_list[k])
    narrowest = min(range(len(width_list)), key=lambda k: width_list[k])
    for index, centre in enumerate(EXAMPLE_POSITIONS):
        others = layout_without(index, EXAMPLE_POSITIONS, width_list)
        short = room_margin(centre, others) < 0.0
        colour = WARN if short else GLASS
        test.add_patch(Circle(centre, keep_out(index, width_list), facecolor="none",
                              edgecolor=colour, lw=1.0, ls=(0, (4, 3)), alpha=0.65, zorder=2))
        glass_from_above(test, centre, width_list[index],
                         base_fraction=foot_list[index] / width_list[index],
                         colour=colour, alpha=0.30, lw=1.2)
    # The radius of the keep-out circle, drawn on the widest glass and on the
    # narrowest, which is where the asymmetry shows.
    for index, angle in ((widest_one, 60.0), (narrowest, 250.0)):
        centre = EXAMPLE_POSITIONS[index]
        radius = keep_out(index, width_list)
        tip = aim_of(centre, angle, radius)
        colour = WARN if room_margin(centre, layout_without(index, EXAMPLE_POSITIONS,
                                                            width_list)) < 0.0 else GLASS
        test.plot([centre[0], tip[0]], [centre[1], tip[1]], color=colour, lw=1.2, zorder=7)
        note(test, tip[0], tip[1] + 6.0,
             f"{radius:.0f} mm, because\nthis glass is {width_list[index]:.0f} mm wide",
             colour, va="bottom",
             bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2})
    first, second = EXAMPLE_CROWDED
    a, b = EXAMPLE_POSITIONS[first], EXAMPLE_POSITIONS[second]
    test.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=1.3, zorder=8)
    note(test, (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0 + 8.0,
         f"{math.dist(a, b):.0f} mm apart", INK, va="bottom",
         bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2})
    note(test, (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2.0, GLASS_ZONE[2] - 18.0,
         f"The circle round a glass is the one a neighbour's middle must stay\n"
         f"outside, and its radius is {GRIP_ROOM:.0f} mm plus half that glass's own width.\n"
         f"The test is not symmetric. The two red glasses are the same "
         f"{math.dist(a, b):.0f} mm\napart and both are short of room, but by "
         f"{abs(room_margin(a, layout_without(first, EXAMPLE_POSITIONS, width_list))):.1f} mm and "
         f"{abs(room_margin(b, layout_without(second, EXAMPLE_POSITIONS, width_list))):.1f} mm, "
         f"because\nthey are not the same width. The two blue ones have room and are\n"
         f"racked before a push is planned at all.", va="top")

    # --------------------------------------------- panel 2: every way to fix it
    total_free = sum(len(EXAMPLE_FREEING[m]) for m in EXAMPLE_CROWDED)
    stage(fan, f"Every push that finishes the job: {total_free} of them")
    table_panel(fan)
    all_margins = []
    for index in stay:
        centre = EXAMPLE_POSITIONS[index]
        glass_from_above(fan, centre, width_list[index],
                         base_fraction=foot_list[index] / width_list[index],
                         colour=WARN, alpha=0.26, lw=1.2)
        fan.add_patch(Circle(centre, keep_out(index, width_list), facecolor="none",
                             edgecolor=WARN, lw=0.9, ls=(0, (4, 3)), alpha=0.55, zorder=2))
    for mover in EXAMPLE_CROWDED:
        centre = EXAMPLE_POSITIONS[mover]
        others = [(EXAMPLE_POSITIONS[k][0], EXAMPLE_POSITIONS[k][1], width_list[k])
                  for k in stay if k != mover]
        for heading, travel in EXAMPLE_FREEING[mover]:
            aim = aim_of(centre, heading, travel)
            all_margins.append(room_margin(aim, others))
            push_arrow(fan, centre, aim, colour=GOOD, lw=1.2, zorder=8)
    for index in EXAMPLE_RACKED_FIRST:
        centre = EXAMPLE_POSITIONS[index]
        fan.add_patch(Circle(centre, width_list[index] / 2.0, facecolor="none",
                             edgecolor=MUTED, lw=1.0, ls=(0, (2, 3)), alpha=0.7, zorder=2))
        note(fan, centre[0], centre[1], "racked\nfirst", MUTED, va="center",
             bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2})
    note(fan, (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2.0, GLASS_ZONE[2] - 18.0,
         f"Of the {EXAMPLE_SAFE[EXAMPLE_CROWDED[0]] + EXAMPLE_SAFE[EXAMPLE_CROWDED[1]]} safe pushes "
         f"between these two glasses, {total_free} leave both with room.\nEvery one of them scores "
         f"the same: both glasses grippable afterwards.\nEvery one leaves between "
         f"{min(all_margins):.1f} and {max(all_margins):.1f} mm of room to spare, because the "
         f"enumerator\nstops each heading at the first travel that works. They differ only in\n"
         f"how far the glass travels, which runs from "
         f"{min(t for m in EXAMPLE_CROWDED for _, t in EXAMPLE_FREEING[m]):.0f} to "
         f"{max(t for m in EXAMPLE_CROWDED for _, t in EXAMPLE_FREEING[m]):.0f} mm.", va="top")

    footer(figure,
           f"This is the whole of what a ranker would be handed here, and the whole of what is wrong "
           f"with handing it over. The arithmetic has already reduced {EXAMPLE_RANKED} candidates to "
           f"{total_free} that finish the job, and those\n{total_free} are a tie on the thing the "
           f"model was going to predict. plan.py takes the shortest of them — glass "
           f"{EXAMPLE_CHOICE[0]}, {EXAMPLE_CHOICE[1]}°, {EXAMPLE_CHOICE[2]} mm — and a model "
           f"asked to order them can only agree, disagree, or be slower.")
    figure.subplots_adjust(bottom=0.24, top=0.93, wspace=0.05)
    save(figure, "06-the-room-test-and-the-fan.png")
    print(f"    {total_free} freeing pushes, margins {min(all_margins):.1f}-{max(all_margins):.1f} mm, "
          f"all scoring the same")


def table_panel(axis, left: float = 44.0, right: float = 44.0,
                below: float = 58.0, above: float = 66.0) -> None:
    """The glass zone, drawn as the rectangle a destination has to stay inside."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from, facecolor="none",
                             edgecolor=MUTED, lw=1.0, ls=(0, (5, 4)), zorder=1))
    axis.set_aspect("equal")
    axis.set_xlim(x_from - left, x_to + right)
    axis.set_ylim(y_from - below, y_to + above)


def main() -> None:
    print(f"reach {COMFORTABLE_REACH[0]:.0f}-{COMFORTABLE_REACH[1]:.0f} mm; zone {GLASS_ZONE}; "
          f"grip room {GRIP_ROOM:.0f} mm; jaw top {JAW_TOP:.0f} mm; "
          f"table friction {TABLE_FRICTION:g} (the simulator's, not the arm's)")
    for height, shares in PUSHABLE.items():
        print(f"  400 drawn tapered glasses pushed at {height:.0f} mm: "
              + ", ".join(f"mu={mu:g} {share:.1f}%" for mu, share in shares.items()))
    picture_the_room_test()
    picture_how_alike()
    picture_the_refusals()
    picture_the_pattern()
    picture_does_order_matter()


if __name__ == "__main__":
    main()
