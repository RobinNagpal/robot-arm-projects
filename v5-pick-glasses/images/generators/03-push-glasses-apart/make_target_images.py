"""Diagrams for the shared document — the target layout, where the glasses should end up.

``docs/03-push-glasses-apart/the-target-layout.md`` is a geometry document, so
nothing here is sketched. Every table drawn is one the project's own generator
made, and every method the document describes is written out below and run:

- ``03-push-glasses-apart/bench/bench.py`` supplies ``scene(seed)``, the fifty
  held-out tables all six solutions are scored on, and ``has_room``, the
  asymmetric room test the whole document turns on;
- ``the_floor`` is the document's constrained optimisation, solved by SLSQP,
  which is the sequential quadratic programming the document names;
- ``relaxation``, ``slots``/``assign`` and ``lloyd`` are the other three
  methods, written as the document describes them.

**The document says this machinery is not written yet, and that is still true.**
These four implementations exist in this file, for these pictures, and nowhere
else in the project. Every number a figure shows is one of them run over the
fifty tables, printed by ``report()`` at the end, and the captions say so. A
figure here never claims the project ships a layout service.

No glass's size appears in this file. The glasses are the ones
``bench.scene`` drew, and their rims and feet are read off the outlines it
returns, so a drawing is a measurement rather than a choice.

This needs MuJoCo and SciPy in one environment, which is problem 3's own, so
it is run from the problem folder rather than from the project root:

    cd 03-push-glasses-apart
    pixi run python ../images/generators/03-push-glasses-apart/make_target_images.py
"""

from __future__ import annotations

import importlib.util
import math
import sys
import types
from pathlib import Path

import numpy as np
from diagram_style import (
    COMFORTABLE_REACH,
    GLASS,
    GLASS_ZONE,
    GOOD,
    GRIP_ROOM,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PAPER,
    RACK_AREA,
    ROBOT_BASE,
    TITLE_SIZE,
    WARN,
    bare,
    glass_from_above,
    new,
    save,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Rectangle
from scipy.optimize import linear_sum_assignment, minimize

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "work_cell"))


def _bench():
    """``03-push-glasses-apart/bench/bench.py``: the tables, and the room test.

    Only ``scene`` and the constants are wanted, and neither touches the
    physics, so when MuJoCo is absent a placeholder stands in long enough to
    load the module. Written the way ``make_toppling_view_images.py`` does it.
    """
    sys.path.insert(0, str(ROOT / "03-push-glasses-apart/bench"))
    if importlib.util.find_spec("mujoco") is None:
        sys.modules["mujoco"] = types.ModuleType("mujoco")
    import bench

    return bench


BENCH = _bench()
MM = 1000.0

# diagram_style took these from the project's own sources. The assertions keep
# this file in step with the examiner it is drawing, so a constant that moves
# shows up as a failed run rather than as a wrong picture.
assert GRIP_ROOM == BENCH.GRIP_ROOM * MM, "diagram_style and bench.py disagree on the room"
assert tuple(v * MM for v in BENCH.GLASS_ZONE) == GLASS_ZONE, "disagreement on the glass zone"

# The fifty held-out tables. The same range run.py is scored on in every
# solution folder, so a count here can be checked against a results.json.
SEEDS = range(10000, 10050)

# The examiner's room test is ``>=``, so a layout that lands exactly on the line
# fails it by a rounding error rather than by any real crowding. Both methods
# that aim for the line are solved to this much clear of it: ten microns, a
# hundredth of the 1.0 mm median error a real push lands with.
MARGIN = 0.01

# The worked examples. Only the seed is written down; the glasses and their
# places come back out of bench.scene, which is the authority for both.
PAIR_SEED = 10032      # holds a wide glass crowding a narrow one that does not crowd it
FLOOR_SEED = 10040     # all six glasses crowded, and the largest floor of the fifty
ASSIGN_SEED = 10024    # the table where a greedy pairing costs the most against Hungarian
RELAX_SEED = 10017     # four glasses, and the table make_02_images.py works through

# Lloyd's algorithm needs the zone sampled, and repulsion needs a step size.
# Neither is a measurement; both are settings of a method written for a figure.
LLOYD_GRID = 140
LLOYD_ROUNDS = 30
RELAX_STEP = 0.35
RELAX_LIMIT = 2000
RESTARTS = 10          # jittered starting layouts, for the caution about seeds
RESTART_JITTER = 40.0  # mm


# --------------------------------------------------------------------------- #
# The table, as the numbers the layout problem is posed in
# --------------------------------------------------------------------------- #
def table(seed: int):
    """One held-out table: where the glasses stand, how wide they are, how wide their feet are."""
    glasses = BENCH.scene(seed)
    places = np.array([[g.position[0] * MM, g.position[1] * MM] for g in glasses])
    rims = np.array([g.outline.max_diameter * MM for g in glasses])
    feet = np.array([2.0 * float(g.outline.radius[0]) * MM for g in glasses])
    return places, rims, feet, glasses[0].kind


def denied(rim: float) -> float:
    """How far a neighbour's middle has to stay from a glass of this rim.

    This is the asymmetric half of the whole document. The room a glass needs
    is set by how wide its *neighbour* is, so the circle belonging to a glass
    is the one it denies to other glasses' middles, and a wide glass denies
    more than a narrow one.
    """
    return GRIP_ROOM + rim / 2.0


def need(rims, margin: float = MARGIN):
    """The least centre-to-centre distance for every pair: 70 mm plus half the wider rim."""
    count = len(rims)
    wanted = np.zeros((count, count))
    for i in range(count):
        for j in range(count):
            if i != j:
                wanted[i, j] = GRIP_ROOM + max(rims[i], rims[j]) / 2.0 + margin
    return wanted


def crowded(places, rims) -> list[int]:
    """Which glasses have no room, asked of the examiner itself. bench.py works in metres."""
    out = []
    for i in range(len(places)):
        others = [(places[j, 0] / MM, places[j, 1] / MM, rims[j] / MM)
                  for j in range(len(places)) if j != i]
        if not BENCH.has_room(places[i, 0] / MM, places[i, 1] / MM, others):
            out.append(i)
    return out


def out_from_my_own_middle(places, rims) -> list[int]:
    """The wrong test: room counted out from a glass's own middle instead of in to its neighbour's edge.

    It looks like the right test and is the mistake the document warns about,
    so what it gets wrong is worth counting rather than asserting.
    """
    return [i for i in range(len(places))
            if any(math.dist(places[i], places[j]) < denied(rims[i])
                   for j in range(len(places)) if j != i)]


def one_sided(places, rims):
    """Pairs where exactly one of the two is crowded by the other: the asymmetry itself."""
    out = []
    for i in range(len(places)):
        for j in range(i + 1, len(places)):
            apart = math.dist(places[i], places[j])
            if (apart < denied(rims[j])) != (apart < denied(rims[i])):
                out.append((i, j, apart))
    return out


def travelled(places, layout) -> tuple[float, float]:
    """How far this layout moves the glasses in total, and the sum of the squares."""
    steps = np.hypot(*(layout - places).T)
    return float(steps.sum()), float((steps ** 2).sum())


def in_zone_wall(point, slack: float = 0.5) -> bool:
    """Whether a glass has been pushed up against a wall of the glass zone."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    return (min(point[0] - x_from, x_to - point[0]) <= slack
            or min(point[1] - y_from, y_to - point[1]) <= slack)


def rims_through_each_other(layout, rims) -> bool:
    """Whether two glasses physically interpenetrate in this layout.

    A layout no arm could pass through, as against one that is merely too
    crowded to grip. The document claims the relaxation's intermediate layouts
    are free of these, which is a claim that can be checked.
    """
    return any(math.dist(layout[i], layout[j]) < (rims[i] + rims[j]) / 2.0
               for i in range(len(layout)) for j in range(i + 1, len(layout)))


# --------------------------------------------------------------------------- #
# Method 1 — the constrained optimisation, which is what defines the floor
# --------------------------------------------------------------------------- #
def the_floor(places, rims, start=None):
    """Least total squared displacement, subject to clearance, the zone and the reach.

    The document's first method, and SLSQP is the sequential quadratic
    programming it names: at each layout the curved clearance constraints are
    replaced by their straight-line approximation, the resulting quadratic
    program is solved exactly, and the answer is taken as a step.

    The rack is left out of the constraints on purpose. It does not overlap
    the glass zone at all, which ``report()`` checks and prints, so adding it
    would be a constraint that can never bind.
    """
    count = len(places)
    flat = places.reshape(-1)
    wanted = need(rims)
    pairs = [(i, j) for i in range(count) for j in range(i + 1, count)]

    def objective(layout):
        return float(np.sum((layout - flat) ** 2))

    def slope(layout):
        return 2.0 * (layout - flat)

    def clearance(layout):
        here = layout.reshape(count, 2)
        return np.array([math.dist(here[i], here[j]) - wanted[i, j] for i, j in pairs])

    def reach(layout):
        radius = np.hypot(*layout.reshape(count, 2).T)
        return np.concatenate([radius - COMFORTABLE_REACH[0], COMFORTABLE_REACH[1] - radius])

    answer = minimize(
        objective, flat if start is None else start.reshape(-1), jac=slope,
        bounds=[(GLASS_ZONE[0], GLASS_ZONE[1]), (GLASS_ZONE[2], GLASS_ZONE[3])] * count,
        method="SLSQP",
        constraints=[{"type": "ineq", "fun": clearance}, {"type": "ineq", "fun": reach}],
        options={"maxiter": 1500, "ftol": 1e-10},
    )
    return answer.x.reshape(count, 2), bool(answer.success)


def jittered_floors(places, rims, seed: int):
    """The same solver from RESTARTS perturbed starting layouts, keeping the legal answers.

    The document's first caution is that this problem has more than one local
    optimum, so the solver and its seed have to be fixed. This is that caution
    measured rather than asserted.
    """
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(RESTARTS):
        start = places + rng.normal(0.0, RESTART_JITTER, places.shape)
        start[:, 0] = np.clip(start[:, 0], GLASS_ZONE[0], GLASS_ZONE[1])
        start[:, 1] = np.clip(start[:, 1], GLASS_ZONE[2], GLASS_ZONE[3])
        layout, converged = the_floor(places, rims, start=start)
        if converged and not crowded(layout, rims):
            out.append(travelled(places, layout)[0])
    return out


# --------------------------------------------------------------------------- #
# Method 2 — repulsive relaxation
# --------------------------------------------------------------------------- #
def relaxation(places, rims, step: float = RELAX_STEP, limit: int = RELAX_LIMIT):
    """Every layout the repulsion passes through, from the measured one to equilibrium.

    The cost is zero while a pair is comfortably apart and climbs as the pair
    closes in on the distance it needs; the walls of the zone cost the same
    way. Each glass takes a small step down the slope of the total. Returning
    the whole sequence rather than only its end is the point of the method:
    the document's claim is that those intermediate layouts are a set of
    waypoints.
    """
    wanted = need(rims)
    count = len(places)
    layout = places.astype(float).copy()
    path = [layout.copy()]
    for _ in range(limit):
        push = np.zeros_like(layout)
        for i in range(count):
            for j in range(count):
                if i == j:
                    continue
                away = layout[i] - layout[j]
                apart = max(float(np.hypot(*away)), 1e-6)
                if apart < wanted[i, j]:
                    push[i] += (wanted[i, j] - apart) * away / apart
            push[i, 0] += max(0.0, GLASS_ZONE[0] + GRIP_ROOM - layout[i, 0])
            push[i, 0] -= max(0.0, layout[i, 0] - (GLASS_ZONE[1] - GRIP_ROOM))
            push[i, 1] += max(0.0, GLASS_ZONE[2] + GRIP_ROOM - layout[i, 1])
            push[i, 1] -= max(0.0, layout[i, 1] - (GLASS_ZONE[3] - GRIP_ROOM))
        if float(np.max(np.abs(push))) < 1e-6:
            break
        layout = layout + step * push
        layout[:, 0] = np.clip(layout[:, 0], GLASS_ZONE[0], GLASS_ZONE[1])
        layout[:, 1] = np.clip(layout[:, 1], GLASS_ZONE[2], GLASS_ZONE[3])
        path.append(layout.copy())
    return path


def worst_shortfall(layout, rims) -> float:
    """How many millimetres the most crowded pair is short of the room it needs.

    Negative while anything is crowded, zero once nothing is. This is the one
    number that says how far a layout is from legal, and plotting it along the
    relaxation's path is how to see whether the crowding really does fall at
    every step.
    """
    wanted = need(rims, margin=0.0)
    return min((math.dist(layout[i], layout[j]) - wanted[i, j]
                for i in range(len(layout)) for j in range(i + 1, len(layout))), default=0.0)


# --------------------------------------------------------------------------- #
# Method 3 — assignment to slots
# --------------------------------------------------------------------------- #
def slots(spacing: float):
    """A triangular lattice of places inside the zone, outside the rack and inside the reach.

    Triangular rather than square because it is the densest packing of points
    at a given spacing, so it offers the most slots the zone can hold. The
    spacing is the conservative one the document asks for: enough that the
    clear room holds for *any* glass of the kind at *any* slot, which means
    the widest rim the kind's drawer can produce.
    """
    out = []
    row, y = 0, GLASS_ZONE[2] + 1.0
    while y <= GLASS_ZONE[3] - 1.0:
        x = GLASS_ZONE[0] + 1.0 + (spacing / 2.0 if row % 2 else 0.0)
        while x <= GLASS_ZONE[1] - 1.0:
            inside_rack = RACK_AREA[0] <= x <= RACK_AREA[1] and RACK_AREA[2] <= y <= RACK_AREA[3]
            away = math.hypot(x - ROBOT_BASE[0], y - ROBOT_BASE[1])
            if not inside_rack and COMFORTABLE_REACH[0] <= away <= COMFORTABLE_REACH[1]:
                out.append((x, y))
            x += spacing
        y += spacing * math.sqrt(3.0) / 2.0
        row += 1
    return np.array(out)


def widest_rim(kind: str, draws: int = 2000) -> float:
    """The widest rim this kind's drawer can produce, over ``draws`` of it.

    Not a glass measurement: it is the top of the kind's declared range, which
    is what a slot lattice has to be spaced for if any glass of the kind is to
    fit any slot. Measured from the drawer rather than written down, so the
    spacing follows the range if the range changes.
    """
    import random

    from work_cell.glasses.shapes import draw

    rng = random.Random(0)
    return max(draw(kind, rng)[0].max_diameter * MM for _ in range(draws))


def assign(places, places_offered):
    """Hungarian against greedy against the worst, on one fixed set of slots.

    The point of the figure is that these three differ while the slots do not,
    so the cost of a bad pairing is visible with the places held still.
    ``linear_sum_assignment`` is the Hungarian algorithm the document names.
    """
    cost = np.array([[math.dist(p, s) for s in places_offered] for p in places])
    rows, best_columns = linear_sum_assignment(cost)
    best = float(cost[rows, best_columns].sum())

    taken, greedy_total, greedy_columns = set(), 0.0, []
    for i in range(len(places)):
        column = int(np.argmin([c if k not in taken else np.inf for k, c in enumerate(cost[i])]))
        taken.add(column)
        greedy_total += float(cost[i, column])
        greedy_columns.append(column)

    # The most expensive way of using the same slots the best answer used, which
    # is what an unlucky pairing costs when the places themselves are ideal.
    rows, worst_columns = linear_sum_assignment(-cost[:, best_columns])
    worst = float(cost[rows, best_columns[worst_columns]].sum())
    return {"best": best, "best_columns": list(best_columns),
            "greedy": greedy_total, "greedy_columns": greedy_columns,
            "worst": worst, "worst_columns": list(best_columns[worst_columns])}


# --------------------------------------------------------------------------- #
# Method 4 — Lloyd's algorithm
# --------------------------------------------------------------------------- #
def lloyd(places, rounds: int = LLOYD_ROUNDS, grid: int = LLOYD_GRID):
    """Move every glass to the middle of its own nearest-point cell, repeatedly.

    The cells are found by sampling the zone rather than by building the
    Voronoi diagram exactly. At this grid the middle of a cell is settled to
    well under a millimetre, which is far finer than the millimetre a push
    lands to, so the approximation cannot change what the figure says.
    """
    xs = np.linspace(GLASS_ZONE[0], GLASS_ZONE[1], grid)
    ys = np.linspace(GLASS_ZONE[2], GLASS_ZONE[3], grid)
    mesh_x, mesh_y = np.meshgrid(xs, ys)
    cloud = np.stack([mesh_x.ravel(), mesh_y.ravel()], axis=1)
    layout = places.astype(float).copy()
    for _ in range(rounds):
        owner = np.argmin(((cloud[:, None, :] - layout[None, :, :]) ** 2).sum(axis=2), axis=1)
        for i in range(len(layout)):
            mine = cloud[owner == i]
            if len(mine):
                layout[i] = mine.mean(axis=0)
    return layout


# --------------------------------------------------------------------------- #
# Everything the figures quote, measured once
# --------------------------------------------------------------------------- #
def measure():
    """Run all four methods over the fifty held-out tables and collect the numbers."""
    spacing = {kind: GRIP_ROOM + widest_rim(kind) / 2.0 for kind in BENCH.KINDS}
    rows = []
    for seed in SEEDS:
        places, rims, feet, kind = table(seed)
        floor_layout, converged = the_floor(places, rims)
        path = relaxation(places, rims)
        offered = slots(spacing[kind])
        pairing = assign(places, offered)
        even = lloyd(places)
        rows.append({
            "seed": seed, "kind": kind, "places": places, "rims": rims, "feet": feet,
            "crowded": crowded(places, rims),
            "own_middle": out_from_my_own_middle(places, rims),
            "one_sided": one_sided(places, rims),
            "floor": floor_layout, "floor_converged": converged,
            "floor_mm": travelled(places, floor_layout)[0],
            "floor_legal": not crowded(floor_layout, rims),
            "floor_on_wall": sum(in_zone_wall(p) for p in floor_layout),
            "restarts": jittered_floors(places, rims, seed),
            "relax": path[-1], "relax_steps": len(path) - 1,
            "relax_mm": travelled(places, path[-1])[0],
            "relax_legal": not crowded(path[-1], rims),
            "relax_monotone": all(
                worst_shortfall(path[k + 1], rims) >= worst_shortfall(path[k], rims) - 1e-9
                for k in range(len(path) - 1)),
            "relax_through": any(rims_through_each_other(layout, rims) for layout in path),
            "slots": len(offered), "spacing": spacing[kind], "pairing": pairing,
            "lloyd": even, "lloyd_mm": travelled(places, even)[0],
            "lloyd_legal": not crowded(even, rims),
        })
    return rows, spacing


def column(rows, name):
    return np.array([r[name] for r in rows], dtype=float)


def zone_against_reach():
    """How far the glass zone sits from the arm's base, and whether the rack touches it.

    Two of the five conditions the document lists turn out never to be able to
    bind, and this is where that is established rather than assumed.
    """
    x_from, x_to, y_from, y_to = GLASS_ZONE
    edge_x = np.linspace(x_from, x_to, 800)
    edge_y = np.linspace(y_from, y_to, 800)
    radii = np.hypot(*np.array([(x, y) for x in edge_x for y in (y_from, y_to)]
                               + [(x, y) for y in edge_y for x in (x_from, x_to)]).T)
    overlaps = not (RACK_AREA[1] < x_from or RACK_AREA[0] > x_to
                    or RACK_AREA[3] < y_from or RACK_AREA[2] > y_to)
    return float(radii.min()), float(radii.max()), overlaps


# --------------------------------------------------------------------------- #
# Drawing helpers, in the shape the other generators in this folder use
# --------------------------------------------------------------------------- #
def stage(axis, title: str) -> None:
    bare(axis)
    axis.set_title(title, fontsize=TITLE_SIZE, color=INK, pad=9)


def chart(axis, title: str) -> None:
    axis.set_title(title, fontsize=TITLE_SIZE, color=INK, pad=9)
    axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED, length=3)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
        axis.spines[side].set_linewidth(0.9)


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, behind=False, **kwargs) -> None:
    """A block of small text. ``behind`` lays white under it, for notes that cross a drawn line."""
    if behind:
        kwargs["bbox"] = dict(boxstyle="round,pad=0.3", facecolor=PAPER, edgecolor="none")
    axis.text(x, y, text, fontsize=size, color=colour, ha=kwargs.pop("ha", "center"),
              zorder=kwargs.pop("zorder", 10), **kwargs)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.015, text, fontsize=NOTE_SIZE, color=MUTED, ha="center", va="bottom")


def square(axis) -> None:
    """Equal axes, pinned to the top of the slot.

    Without the anchor an equal-aspect panel shrinks about its middle, and its
    title then sits lower than the titles of the panels beside it.
    """
    axis.set_aspect("equal")
    axis.set_anchor("N")


def zone_frame(axis, pad=(44.0, 44.0, 58.0, 62.0)) -> None:
    """The glass zone as the rectangle a glass has to stay inside, and nothing else."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    axis.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from, facecolor="none",
                             edgecolor=MUTED, lw=1.0, ls=(0, (5, 4)), zorder=1))
    square(axis)
    axis.set_xlim(x_from - pad[0], x_to + pad[1])
    axis.set_ylim(y_from - pad[2], y_to + pad[3])


def draw_table(axis, places, rims, feet, colour=GLASS, alpha=0.26, labels=False) -> None:
    """Every glass on a table, from the top, at the sizes the examiner drew them."""
    for i, (place, rim, foot) in enumerate(zip(places, rims, feet, strict=True)):
        glass_from_above(axis, place, rim, base_fraction=foot / rim, colour=colour,
                         alpha=alpha, lw=1.0)
        if labels:
            axis.text(place[0], place[1], str(i), fontsize=NOTE_SIZE, color=INK,
                      ha="center", va="center", zorder=9)


def arrow(axis, start, end, colour, lw=1.5, zorder=8) -> None:
    axis.annotate("", xy=tuple(end), xytext=tuple(start), zorder=zorder,
                  arrowprops=dict(arrowstyle="-|>", color=colour, lw=lw,
                                  shrinkA=0.0, shrinkB=0.0))


def measure_bar(axis, a, b, text, colour=INK, offset=10.0, size=NOTE_SIZE) -> None:
    """A dimension line between two points with its length written beside it.

    A positive ``offset`` writes the text above the line, a negative one below,
    which is what keeps two dimension lines end to end from colliding.
    """
    axis.annotate("", xy=tuple(b), xytext=tuple(a), zorder=9,
                  arrowprops=dict(arrowstyle="<|-|>", color=colour, lw=1.0,
                                  shrinkA=0.0, shrinkB=0.0))
    middle = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    axis.text(middle[0], middle[1] + offset, text, fontsize=size, color=colour,
              ha="center", va="bottom" if offset >= 0.0 else "top", zorder=9,
              bbox=dict(boxstyle="round,pad=0.18", facecolor=PAPER, edgecolor="none"))


# --------------------------------------------------------------------------- #
# 1. What "has room" means, and why the test is not symmetric
# --------------------------------------------------------------------------- #
def picture_what_has_room_means(rows) -> None:
    """The one condition the whole document rests on, drawn to the neighbour's edge."""
    figure, (edge, pair, counts) = new(15.0, 5.1, columns=3)
    row = next(r for r in rows if r["seed"] == PAIR_SEED)
    places, rims, feet = row["places"], row["rims"], row["feet"]
    narrow, wide = row["one_sided"][0][0], row["one_sided"][0][1]

    # ------------------------------------- panel 1: in to the edge, not out from the middle
    stage(edge, "Room is counted in to the neighbour's edge")
    apart = denied(rims[wide])
    here, there = np.array([0.0, 0.0]), np.array([apart, 0.0])
    edge.add_patch(Circle(tuple(here), GRIP_ROOM, facecolor="none", edgecolor=GOOD,
                          lw=1.3, ls=(0, (4, 3)), zorder=2))
    glass_from_above(edge, here, rims[narrow], base_fraction=feet[narrow] / rims[narrow], lw=1.1)
    glass_from_above(edge, there, rims[wide], base_fraction=feet[wide] / rims[wide],
                     colour=WARN, lw=1.1)
    # The dimension lines go below the glasses, so that neither of them lands on
    # a rim, and the two labels sit on opposite sides of their shared end.
    rule = -GRIP_ROOM - 22.0
    for x in (0.0, GRIP_ROOM, apart):
        edge.plot([x, x], [rule, 0.0], color=MUTED, lw=0.7, ls=(0, (2, 2)), zorder=1)
    measure_bar(edge, (0.0, rule), (GRIP_ROOM, rule), f"{GRIP_ROOM:.0f} mm of clear room",
                GOOD, offset=6.0)
    measure_bar(edge, (GRIP_ROOM, rule), (apart, rule),
                f"half the neighbour's rim,\n{rims[wide] / 2:.1f} mm", WARN, offset=-6.0)
    note(edge, apart / 2.0, rule - 56.0,
         f"The jaw needs {GRIP_ROOM:.0f} mm from this glass's middle outwards\n"
         f"before it fits round it, and the neighbour is in the way as\n"
         f"soon as any part of it is inside that. So the two middles\n"
         f"have to be at least {GRIP_ROOM:.0f} mm plus half the neighbour's rim\n"
         f"apart — for this pair, {apart:.1f} mm.", INK, va="top")
    square(edge)
    edge.set_xlim(-GRIP_ROOM - 20.0, apart + rims[wide] / 2.0 + 20.0)
    edge.set_ylim(rule - 190.0, GRIP_ROOM + 20.0)

    # --------------------------------------- panel 2: the same pair as they really stand
    stage(pair, f"So the test is not symmetric — table {PAIR_SEED}")
    real = math.dist(places[narrow], places[wide])
    for index, colour in ((wide, WARN), (narrow, GLASS)):
        pair.add_patch(Circle(tuple(places[index]), denied(rims[index]),
                              facecolor=to_rgba(colour, 0.07), edgecolor=colour, lw=1.2,
                              ls=(0, (4, 3)), zorder=2))
    for index, colour in ((narrow, GLASS), (wide, WARN)):
        glass_from_above(pair, places[index], rims[index],
                         base_fraction=feet[index] / rims[index], colour=colour, lw=1.1)
    measure_bar(pair, places[narrow], places[wide], f"{real:.1f} mm apart", INK, offset=5.0)
    span = denied(rims[wide])
    middle = (places[narrow] + places[wide]) / 2.0
    pair.text(middle[0], middle[1] + span + 24.0,
              f"the wide glass denies {denied(rims[wide]):.1f} mm, and the narrow\n"
              f"one's middle is {denied(rims[wide]) - real:.1f} mm inside that: the narrow glass\n"
              f"has no room, and cannot be gripped",
              fontsize=NOTE_SIZE, color=WARN, ha="center", va="bottom", zorder=9)
    pair.text(middle[0], middle[1] - span - 24.0,
              f"the narrow glass denies only {denied(rims[narrow]):.1f} mm, and the wide\n"
              f"one's middle is {real - denied(rims[narrow]):.1f} mm outside that: the wide glass\n"
              f"beside it is perfectly grippable",
              fontsize=NOTE_SIZE, color=GLASS, ha="center", va="top", zorder=9)
    square(pair)
    pair.set_xlim(middle[0] - span - 52.0, middle[0] + span + 52.0)
    pair.set_ylim(middle[1] - span - 118.0, middle[1] + span + 86.0)

    # ------------------------------------------- panel 3: what the wrong test costs
    glasses = sum(len(r["places"]) for r in rows)
    no_room = sum(len(r["crowded"]) for r in rows)
    wrong = sum(len(r["own_middle"]) for r in rows)
    missed = sum(len(set(r["crowded"]) - set(r["own_middle"])) for r in rows)
    added = sum(len(set(r["own_middle"]) - set(r["crowded"])) for r in rows)
    lopsided = sum(len(r["one_sided"]) for r in rows)
    tables_lopsided = sum(1 for r in rows if r["one_sided"])

    chart(counts, "What the symmetric version gets wrong")
    bars = [("glasses without room,\nby the examiner's own test", no_room, GOOD),
            ("called crowded by the test that\nmeasures out from its own middle", wrong, MUTED),
            ("really crowded, and that test\nsays they are fine", missed, WARN),
            ("fine, and that test says\nthey are crowded", added, WARN)]
    for position, (label, value, colour) in enumerate(bars):
        y = -1.45 * position
        counts.barh([y], [value], height=0.5, color=to_rgba(colour, 0.45), edgecolor=colour, lw=1.0)
        counts.text(value + no_room * 0.015, y, f"{value}", fontsize=LABEL_SIZE, color=colour,
                    ha="left", va="center")
        counts.text(0.0, y + 0.38, label, fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    counts.set_xlim(0.0, no_room * 1.2)
    counts.set_ylim(-7.5, 1.3)
    counts.set_yticks([])
    counts.spines["left"].set_visible(False)
    counts.set_xlabel(f"glasses, out of {glasses} on {len(rows)} tables", fontsize=LABEL_SIZE,
                      color=INK)
    note(counts, no_room * 0.6, -5.2,
         f"On {tables_lopsided} of the {len(rows)} tables there is a pair in which\n"
         f"exactly one of the two is crowded — {lopsided} such pairs in all.\n"
         f"Those are the pairs a symmetric test cannot describe at\n"
         f"all, because it has to call both of them crowded or both\n"
         f"of them fine, and neither is true.", INK, va="top")

    footer(figure,
           f"Measured over the {len(rows)} held-out tables of bench.scene, seeds {SEEDS.start} to "
           f"{SEEDS.stop - 1}: {glasses} glasses, {no_room} of them without room, which is the number "
           f"every solution's results.json also reports as crowded at the start.\nThe left two panels "
           f"are table {PAIR_SEED} as the examiner drew it, at the rims it drew; the circles are "
           f"computed from those rims, not chosen.")
    figure.subplots_adjust(bottom=0.20, top=0.89, wspace=0.22)
    save(figure, "target-what-has-room-means.png")


# --------------------------------------------------------------------------- #
# 2. Which of the conditions can actually bind
# --------------------------------------------------------------------------- #
def picture_which_conditions_bind(rows) -> None:
    """Five conditions are stated; two of them can never be active, and that is measurable."""
    figure, (plan, verdicts) = new(13.2, 6.4, columns=2)
    nearest, farthest, rack_overlaps = zone_against_reach()
    row = next(r for r in rows if r["seed"] == FLOOR_SEED)

    # ----------------------------------------------- panel 1: the cell, from the top
    stage(plan, "The conditions, drawn on the table from the top")
    for radius in COMFORTABLE_REACH:
        angles = np.linspace(-math.pi / 2.0, math.pi / 2.0, 400)
        plan.plot(ROBOT_BASE[0] + radius * np.cos(angles), ROBOT_BASE[1] + radius * np.sin(angles),
                  color=MUTED, lw=1.0, ls=(0, (6, 4)), zorder=1)
    plan.plot([ROBOT_BASE[0]], [ROBOT_BASE[1]], marker="o", color=INK, ms=5.0, zorder=5)
    plan.text(ROBOT_BASE[0] - 16.0, ROBOT_BASE[1], "the arm's base", fontsize=NOTE_SIZE,
              color=INK, ha="right", va="center")
    x_from, x_to, y_from, y_to = GLASS_ZONE
    plan.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                             facecolor=to_rgba(GLASS, 0.07), edgecolor=GLASS, lw=1.2,
                             ls=(0, (5, 4)), zorder=2))
    plan.text((x_from + x_to) / 2.0, y_from - 18.0,
              f"the glass zone, {x_to - x_from:.0f} by {y_to - y_from:.0f} mm",
              fontsize=NOTE_SIZE, color=GLASS, ha="center", va="top")
    plan.add_patch(Rectangle((RACK_AREA[0], RACK_AREA[2]), RACK_AREA[1] - RACK_AREA[0],
                             RACK_AREA[3] - RACK_AREA[2], facecolor=to_rgba(GOOD, 0.25),
                             edgecolor=GOOD, lw=1.2, zorder=3))
    plan.text(RACK_AREA[1] + 16.0, (RACK_AREA[2] + RACK_AREA[3]) / 2.0,
              f"the rack, {RACK_AREA[1] - RACK_AREA[0]:.0f} by {RACK_AREA[3] - RACK_AREA[2]:.0f} mm,\n"
              "on the arm's other side",
              fontsize=NOTE_SIZE, color=GOOD, ha="left", va="center")
    draw_table(plan, row["places"], row["rims"], row["feet"])
    # The arcs are labelled where they run clear of the zone: the inner one to
    # the left of it, the outer one to the right.
    for radius, label, at in ((COMFORTABLE_REACH[0], "300 mm", -1.21),
                              (COMFORTABLE_REACH[1], "780 mm", -0.33)):
        plan.text(radius * math.cos(at), radius * math.sin(at), label,
                  fontsize=NOTE_SIZE, color=MUTED, ha="center", va="center", zorder=6,
                  bbox=dict(boxstyle="round,pad=0.18", facecolor=PAPER, edgecolor="none"))
    for corner, distance, name in (((x_from, y_to), nearest, "nearest"),
                                   ((x_to, y_from), farthest, "farthest")):
        plan.annotate("", xy=corner, xytext=(ROBOT_BASE[0], ROBOT_BASE[1]), zorder=4,
                      arrowprops=dict(arrowstyle="-", color=WARN, lw=1.0, ls=(0, (3, 2))))
        plan.text(corner[0] * 0.35, corner[1] * 0.35, f"{name} corner, {distance:.0f} mm",
                  fontsize=NOTE_SIZE, color=WARN, ha="center", va="center", zorder=7,
                  bbox=dict(boxstyle="round,pad=0.18", facecolor=PAPER, edgecolor="none"))
    square(plan)
    plan.set_xlim(-250.0, 790.0)
    plan.set_ylim(-540.0, 450.0)

    # ------------------------------------------------ panel 2: the verdict on each one
    stage(verdicts, "Which of them can ever be the active one")
    on_wall = int(sum(r["floor_on_wall"] for r in rows))
    tables_on_wall = sum(1 for r in rows if r["floor_on_wall"])
    no_room = sum(len(r["crowded"]) for r in rows)
    glasses = sum(len(r["places"]) for r in rows)
    lines = [
        ("clear room round every glass", GOOD, True,
         f"binds constantly: {no_room} of the {glasses} glasses start without it, and it is\n"
         f"the only condition that moves a glass on every one of the {len(rows)} tables."),
        ("inside the glass zone", GOOD, True,
         f"binds sometimes: the floor layout puts {on_wall} glasses hard against a wall of\n"
         f"the zone, on {tables_on_wall} tables. A crowd near an edge has to spread along it."),
        ("inside the arm's reach", WARN, False,
         f"cannot bind. The zone's own corners sit {nearest:.0f} and {farthest:.0f} mm from the base,\n"
         f"and the comfortable ring is {COMFORTABLE_REACH[0]:.0f} to {COMFORTABLE_REACH[1]:.0f} mm, "
         f"so the zone is inside the ring entirely."),
        ("outside the rack", WARN, rack_overlaps,
         "cannot bind. The rack is on the far side of the base from the glass zone and the two\n"
         "rectangles do not overlap at any point, so nothing standing in the zone can be in it."),
    ]
    verdicts.set_xlim(0.0, 10.0)
    verdicts.set_ylim(-4.6, 1.1)
    for position, (name, colour, binds, why) in enumerate(lines):
        y = -1.1 * position
        verdicts.add_patch(Rectangle((0.1, y - 0.12), 0.22, 0.62, facecolor=to_rgba(colour, 0.55),
                                     edgecolor=colour, lw=1.0))
        verdicts.text(0.55, y + 0.34, name, fontsize=LABEL_SIZE, color=INK, ha="left", va="center")
        verdicts.text(0.55, y + 0.05, ("binds" if binds else "never binds"), fontsize=NOTE_SIZE,
                      color=colour, ha="left", va="center")
        verdicts.text(0.55, y - 0.14, why, fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top")
    note(verdicts, 0.1, -4.0,
         "The document lists a fifth condition, a clear side-on\n"
         "viewpoint. Problem 3's examiner has no viewpoint test in it\n"
         "and none of the six solutions chooses a viewpoint, so\n"
         "there is nothing here to measure and nothing drawn.",
         INK, va="top", ha="left")

    footer(figure,
           f"The left panel is table {FLOOR_SEED}; the zone, the rack, the reach ring and the base are "
           f"the project's own constants, and the two corner distances were computed from them. "
           f"Writing a layout solver that\nenforces the reach or the rack is therefore not wrong, only "
           f"wasted: two of the four conditions are satisfied by anything standing in the zone at all.")
    figure.subplots_adjust(bottom=0.12, top=0.92, wspace=0.05)
    save(figure, "target-which-conditions-can-bind.png")


# --------------------------------------------------------------------------- #
# 3. The displacement floor
# --------------------------------------------------------------------------- #
def picture_the_displacement_floor(rows) -> None:
    """The yardstick: the least travel the task can cost, which belongs to the geometry."""
    figure, (moves, spread, scale) = new(15.0, 5.0, columns=3)
    row = next(r for r in rows if r["seed"] == FLOOR_SEED)
    places, rims, feet, layout = row["places"], row["rims"], row["feet"], row["floor"]

    # --------------------------------------- panel 1: the least movement on one table
    stage(moves, f"The least movement table {FLOOR_SEED} can be fixed with")
    zone_frame(moves, pad=(40.0, 40.0, 30.0, 40.0))
    draw_table(moves, places, rims, feet, colour=WARN, alpha=0.16)
    draw_table(moves, layout, rims, feet, colour=GOOD, alpha=0.26)
    for start, end in zip(places, layout, strict=True):
        step = end - start
        arrow(moves, start, end, INK, lw=1.3)
        # The length is written just past the head, along the push, so that it
        # never lands on the glass it belongs to.
        tip = end + 16.0 * step / max(float(np.hypot(*step)), 1e-6)
        moves.text(tip[0], tip[1], f"{float(np.hypot(*step)):.0f}", fontsize=NOTE_SIZE,
                   color=INK, ha="center", va="center", zorder=9,
                   bbox=dict(boxstyle="round,pad=0.16", facecolor=PAPER, edgecolor="none"))
    note(moves, (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2.0, GLASS_ZONE[2] + 96.0,
         f"All {len(places)} glasses start without room (pale). The layout that\n"
         f"gives all {len(places)} of them their room while moving them least (solid)\n"
         f"costs {row['floor_mm']:.0f} mm of travel in total, and no legal arrangement of\n"
         f"this table costs less. Arrows are labelled in millimetres.", INK, va="top",
         behind=True)

    # ------------------------------------------- panel 2: the floor across the fifty
    floors = column(rows, "floor_mm")
    chart(spread, "How large the floor is, table by table")
    spread.hist(floors, bins=np.arange(0.0, 170.0, 12.5), color=to_rgba(GOOD, 0.45),
                edgecolor=GOOD, lw=1.0)
    for value, label, colour in ((float(np.median(floors)), "median", INK),
                                 (float(floors.min()), "least", MUTED),
                                 (float(floors.max()), "most", MUTED)):
        spread.axvline(value, color=colour, lw=1.0, ls=(0, (3, 2)))
        spread.text(value, 11.6, f"{label}\n{value:.0f} mm", fontsize=NOTE_SIZE, color=colour,
                    ha="center", va="bottom")
    spread.set_xlim(0.0, 170.0)
    spread.set_ylim(0.0, 17.6)
    spread.set_yticks(np.arange(0.0, 12.1, 2.0))
    spread.set_xlabel("millimetres of travel the table cannot be fixed for less than",
                      fontsize=LABEL_SIZE, color=INK)
    spread.set_ylabel("tables", fontsize=LABEL_SIZE, color=INK)
    note(spread, 85.0, 16.9,
         f"Summed over the {len(rows)} tables the floor is {floors.sum():.0f} mm. It is available "
         f"before any\nsolution exists, because it comes from the measurements and the\n"
         f"constants and nothing else. It cannot flatter a solution: it never saw one.",
         INK, va="top")

    # ------------------------------------------------ panel 3: what the scale reads
    stage(scale, "The scale it puts every solution on")
    scale.set_xlim(0.0, 12.6)
    scale.set_ylim(-6.2, 1.4)
    # Only as far down as the bars it is a reference for, so it does not run
    # through the note underneath them.
    scale.plot([1.0, 1.0], [-3.8, 0.55], color=GOOD, lw=1.4, ls=(0, (3, 2)), zorder=2)
    scale.text(1.14, 0.60, "the floor", fontsize=NOTE_SIZE, color=GOOD, ha="left", va="bottom")
    readings = [
        (1.0, GOOD, "at the floor",
         "every millimetre it spent was a millimetre the task\n"
         "required. Its remaining error is not its fault, and more\n"
         "cleverness in choosing pushes buys it nothing."),
        (2.0, GLASS, "twice the floor",
         "it spent twice the travel the task demanded."),
        (10.0, WARN, "ten times the floor",
         "it was wandering."),
    ]
    for position, (value, colour, label, why) in enumerate(readings):
        y = -1.75 * position
        scale.add_patch(Rectangle((0.0, y - 0.22), value, 0.44,
                                  facecolor=to_rgba(colour, 0.45), edgecolor=colour, lw=1.0))
        scale.text(value + 0.22, y, f"{value:.0f}x", fontsize=LABEL_SIZE, color=colour,
                   ha="left", va="center")
        scale.text(0.0, y + 0.34, label, fontsize=LABEL_SIZE, color=colour, ha="left",
                   va="bottom")
        scale.text(0.0, y - 0.34, why, fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top")
    note(scale, 0.0, -4.5,
         "Nothing can be placed on this scale yet. The scorecard in\n"
         "bench/scoring.py counts pushes, repeats and the aim error;\n"
         "it does not add up how far the glasses travelled, and no\n"
         "results.json in the six solution folders reports a distance.",
         WARN, va="top", ha="left")

    footer(figure,
           f"The floor is the objective of the constrained optimisation at its answer, computed here "
           f"by SLSQP over the {len(rows)} held-out tables, and it is drawn as the total distance that "
           f"answer moves the glasses. Every one of\nthe {len(rows)} answers passes the examiner's own "
           f"room test. The method is written in this generator for these figures; the document is "
           f"explicit that the project does not ship it yet.")
    figure.subplots_adjust(bottom=0.20, top=0.90, wspace=0.18)
    save(figure, "target-the-displacement-floor.png")


# --------------------------------------------------------------------------- #
# 4. The four methods, measured against the floor
# --------------------------------------------------------------------------- #
def picture_four_methods(rows) -> None:
    """What each method costs in travel, and what the caution about seeds really costs."""
    figure, (costs, seeds) = new(13.8, 5.4, columns=2)
    floors = column(rows, "floor_mm")

    series = [
        ("the constrained\noptimisation", floors / floors, GOOD,
         f"legal on {sum(r['floor_legal'] for r in rows)}/{len(rows)}"),
        ("assignment to slots,\nHungarian", column(rows, "pairing_best") / floors, GLASS,
         f"legal on {len(rows)}/{len(rows)} by construction"),
        ("repulsive\nrelaxation", column(rows, "relax_mm") / floors, INK,
         f"legal on {sum(r['relax_legal'] for r in rows)}/{len(rows)}"),
        ("Lloyd's\nalgorithm", column(rows, "lloyd_mm") / floors, WARN,
         f"legal on {sum(r['lloyd_legal'] for r in rows)}/{len(rows)}"),
    ]
    chart(costs, "What each method spends, as a multiple of the floor")
    rng = np.random.default_rng(0)
    for position, (label, values, colour, legality) in enumerate(series):
        y = -position
        costs.scatter(values, y + rng.uniform(-0.17, 0.17, len(values)), s=13,
                      color=to_rgba(colour, 0.5), edgecolors="none", zorder=3)
        middle = float(np.median(values))
        costs.plot([middle, middle], [y - 0.3, y + 0.3], color=colour, lw=2.0, zorder=5)
        costs.text(middle * 1.07, y, f"median {middle:.1f}x", fontsize=NOTE_SIZE, color=colour,
                   ha="left", va="center", zorder=6,
                   bbox=dict(boxstyle="round,pad=0.18", facecolor=PAPER, edgecolor="none"))
        costs.text(0.33, y - 0.40, f"{label}   —   {legality}".replace("\n", " "),
                   fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    costs.axvline(1.0, color=GOOD, lw=1.0, ls=(0, (3, 2)), zorder=1)
    costs.set_xlim(0.32, 60.0)
    costs.set_xscale("log")
    costs.set_xticks([1, 2, 5, 10, 20, 40])
    costs.set_xticklabels(["1x", "2x", "5x", "10x", "20x", "40x"])
    costs.set_ylim(-5.1, 0.95)
    costs.set_yticks([])
    costs.spines["left"].set_visible(False)
    costs.set_xlabel("total travel the layout asks for, over the floor for the same table",
                     fontsize=LABEL_SIZE, color=INK)
    note(costs, 0.33, -4.0,
         "One dot per table. The floor is 1x by definition, so the three other\n"
         "methods are reading how much travel they ask for that the task did\n"
         "not require. Note the log scale: the worst tables are far out.",
         INK, va="top", ha="left")

    # ---------------------------------------- panel 2: the caution about the seed
    usable = [r for r in rows if len(r["restarts"]) >= 2]
    ratios = [max(r["restarts"]) / r["floor_mm"] for r in usable]
    above = sum(1 for r in usable if max(r["restarts"]) > r["floor_mm"] + 1.0)
    chart(seeds, "The same solver, started somewhere else")
    seeds.scatter(column(usable, "floor_mm"), [max(r["restarts"]) for r in usable], s=26,
                  color=to_rgba(WARN, 0.55), edgecolors=WARN, lw=0.8, zorder=4)
    limit = 1.08 * max(max(r["restarts"]) for r in usable)
    seeds.plot([0.0, limit], [0.0, limit], color=GOOD, lw=1.2, zorder=2)
    seeds.text(limit * 0.52, limit * 0.46, "the floor itself", fontsize=NOTE_SIZE, color=GOOD,
               ha="left", va="top", rotation=38.0)
    seeds.set_xlim(0.0, limit)
    seeds.set_ylim(0.0, limit)
    seeds.set_xlabel("the floor for this table, mm", fontsize=LABEL_SIZE, color=INK)
    seeds.set_ylabel(f"worst legal answer from {RESTARTS} jittered starts, mm",
                     fontsize=LABEL_SIZE, color=INK)
    note(seeds, limit * 0.40, limit * 0.30,
         f"On {above} of the {len(usable)} tables a start {RESTART_JITTER:.0f} mm away leaves\n"
         f"the solver in a different local optimum, and the\n"
         f"worst of them asks for {max(ratios):.1f} times the floor's travel\n"
         f"for the same table. Two solutions handed layouts\n"
         f"from unfixed starts would be compared on their\n"
         f"targets rather than on their pushing.", INK, va="top", ha="left")

    footer(figure,
           f"All four methods are written in this generator as the document describes them and run over "
           f"the same {len(rows)} held-out tables; none of them is shipped by the project. Lloyd's "
           f"algorithm optimises neither clearance\nnor travel, which is why it is the only one that "
           f"leaves tables illegal, and the slot lattice is legal by construction but pays for it in "
           f"travel. The jitter in the right panel is Gaussian, {RESTART_JITTER:.0f} mm per axis.")
    figure.subplots_adjust(bottom=0.22, top=0.90, wspace=0.26)
    save(figure, "target-four-methods-against-the-floor.png")


# --------------------------------------------------------------------------- #
# 5. Finding places and assigning them are two different problems
# --------------------------------------------------------------------------- #
def picture_assignment(rows) -> None:
    """The second problem readers miss: with the places fixed, the pairing still costs."""
    figure, (greedy, best) = new(11.2, 5.6, columns=2)
    row = next(r for r in rows if r["seed"] == ASSIGN_SEED)
    places, rims, feet = row["places"], row["rims"], row["feet"]
    offered = slots(row["spacing"])
    pairing = row["pairing"]

    for axis, title, columns, total, colour in (
        (greedy, "Nearest free slot, taken a glass at a time", pairing["greedy_columns"],
         pairing["greedy"], WARN),
        (best, "The Hungarian answer, on exactly the same slots", pairing["best_columns"],
         pairing["best"], GOOD),
    ):
        stage(axis, title)
        zone_frame(axis, pad=(28.0, 28.0, 40.0, 28.0))
        for spot in offered:
            axis.add_patch(Circle(tuple(spot), 5.0, facecolor=PAPER, edgecolor=MUTED, lw=0.9,
                                  zorder=4))
        draw_table(axis, places, rims, feet, alpha=0.18, labels=True)
        for index, column_index in enumerate(columns):
            arrow(axis, places[index], offered[column_index], colour, lw=1.4)
            axis.add_patch(Circle(tuple(offered[column_index]), 5.0, facecolor=to_rgba(colour, 0.7),
                                  edgecolor=colour, lw=1.0, zorder=6))
        note(axis, (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2.0, GLASS_ZONE[2] - 14.0,
             f"{total:.0f} mm of travel in total", colour, size=LABEL_SIZE, va="top")

    crossing = sum(1 for index, column_index in enumerate(pairing["greedy_columns"])
                   if column_index != pairing["best_columns"][index])
    ratios = column(rows, "pairing_greedy") / column(rows, "pairing_best")
    worse = int((ratios > 1.0 + 1e-9).sum())
    worst = column(rows, "pairing_worst") / column(rows, "pairing_best")

    footer(figure,
           f"Table {ASSIGN_SEED}, {len(places)} glasses and the {len(offered)} slots a "
           f"{row['spacing']:.0f} mm lattice fits in the zone. The slots are identical in both panels, "
           f"so nothing here is a better set of places: the whole difference is which glass was sent "
           f"to which,\nand it differs for {crossing} of the {len(places)} glasses. Greedy is often "
           f"right — it ties the Hungarian answer on {len(rows) - worse} of the {len(rows)} tables — "
           f"but when it is wrong it is wrong by up to {ratios.max():.2f} times the travel, and the "
           f"most expensive\nlegal pairing of the slots the best answer used costs "
           f"{np.median(worst):.1f} times it at the median. Finding good places is one problem; "
           f"deciding who goes where is a second one, and it is exactly solved by the Hungarian "
           f"algorithm.")
    figure.subplots_adjust(bottom=0.15, top=0.93, wspace=0.06)
    save(figure, "target-finding-places-is-not-assigning-them.png")


# --------------------------------------------------------------------------- #
# 6. Relaxation, step by step
# --------------------------------------------------------------------------- #
def picture_relaxation(rows) -> None:
    """The method that arrives rather than solves, and what its sequence of layouts is worth."""
    figure, axes = new(16.6, 3.9, columns=5)
    row = next(r for r in rows if r["seed"] == RELAX_SEED)
    places, rims, feet = row["places"], row["rims"], row["feet"]
    path = relaxation(places, rims)
    shown = [0, 1, 2, len(path) - 1]

    for axis, step in zip(axes[:4], shown, strict=True):
        layout = path[step]
        short = worst_shortfall(layout, rims)
        settled = step == len(path) - 1
        title = ("the measured table" if step == 0
                 else "equilibrium" if settled else f"step {step}")
        stage(axis, title)
        zone_frame(axis, pad=(30.0, 30.0, 92.0, 34.0))
        for index, place in enumerate(layout):
            colour = GOOD if settled else WARN if index in crowded(layout, rims) else GLASS
            glass_from_above(axis, place, rims[index], base_fraction=feet[index] / rims[index],
                             colour=colour, alpha=0.26, lw=1.0)
            # The circles stay on at equilibrium as well: the whole claim of the
            # method is that no middle ends up inside one, and that is only
            # visible if they are still drawn when it is true.
            axis.add_patch(Circle(tuple(place), denied(rims[index]), facecolor="none",
                                  edgecolor=colour, lw=0.8, ls=(0, (3, 3)), alpha=0.6,
                                  zorder=2))
            if step > 0:
                arrow(axis, places[index], place, INK, lw=1.0)
        note(axis, (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2.0, GLASS_ZONE[2] - 18.0,
             (f"nothing is crowded; {travelled(places, layout)[0]:.0f} mm\n"
              f"of travel spent, against a floor\nof {row['floor_mm']:.0f} mm" if settled
              else f"the worst pair is {-short:.1f} mm short\nof the room it needs; "
                   f"{travelled(places, layout)[0]:.0f} mm\nof travel spent so far"),
             GOOD if settled else INK, va="top")

    # ------------------------------- the last panel: does the crowding fall every step?
    curve = axes[4]
    chart(curve, "Crowding, step by step")
    # Against the step number rather than against progress, and only the opening
    # stretch, because that is where the method's claim to fall at every step
    # breaks and a normalised axis would hide it.
    window = 60
    for other, colour, width in ((RELAX_SEED, GOOD, 1.8), (FLOOR_SEED, WARN, 1.4),
                                 (ASSIGN_SEED, GLASS, 1.4)):
        that = next(r for r in rows if r["seed"] == other)
        trail = relaxation(that["places"], that["rims"])
        shortfalls = [-worst_shortfall(layout, that["rims"]) for layout in trail]
        curve.plot(np.arange(len(shortfalls))[:window], shortfalls[:window], color=colour,
                   lw=width, label=f"table {other}, {len(trail) - 1} steps in all")
    curve.axhline(0.0, color=MUTED, lw=0.9, ls=(0, (3, 2)))
    curve.set_xlim(0.0, window)
    curve.set_xlabel("relaxation step", fontsize=LABEL_SIZE, color=INK)
    curve.set_ylabel("millimetres the worst pair is short", fontsize=LABEL_SIZE, color=INK)
    curve.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper right")
    not_monotone = sum(1 for r in rows if not r["relax_monotone"])
    through = sum(1 for r in rows if r["relax_through"])
    spent = float(np.median(column(rows, "relax_mm") / column(rows, "floor_mm")))
    top = curve.get_ylim()[1]
    note(curve, window * 0.30, top * 0.60,
         f"The crowding does not fall at every step: on {not_monotone} of\n"
         f"the {len(rows)} tables some step leaves the worst pair worse\n"
         f"off than the step before, because a glass pushed\n"
         f"out of one crowd arrives in another. Table "
         f"{FLOOR_SEED}\ngets worse on its very first step.", INK, va="top", ha="left")

    footer(figure,
           f"Table {RELAX_SEED}, the same table make_02_images.py works through, relaxed in "
           f"{len(path) - 1} steps. Dashed circles are the room each glass denies its neighbours, "
           f"red is a glass that has none, and arrows are where each glass\nhas moved from. "
           f"This is the method of letting like charges "
           f"loose in a box, and it arrives without solving anything — but it has no idea travel is "
           f"supposed to be small, so it spends {spent:.1f} "
           f"times the floor at the median. The sequence is\nits real advantage, being a set of "
           f"waypoints as well as a destination; on {through} of the {len(rows)} tables, though, two "
           f"glasses pass through each other on the way, so the route is not free of overlaps\nas the "
           f"document claims. A layout is legal when no glass's middle lies inside another's circle, "
           f"which is why the circles still overlap at equilibrium.")
    figure.subplots_adjust(bottom=0.26, top=0.90, wspace=0.18)
    save(figure, "target-relaxation-step-by-step.png")


# --------------------------------------------------------------------------- #
def report(rows, spacing) -> None:
    """Print every number the document and the captions quote, so both can be checked."""
    nearest, farthest, rack_overlaps = zone_against_reach()
    floors = column(rows, "floor_mm")
    glasses = sum(len(r["places"]) for r in rows)
    print(f"{len(rows)} tables, seeds {SEEDS.start}-{SEEDS.stop - 1}: {glasses} glasses, "
          f"{sum(len(r['crowded']) for r in rows)} without room at the start")
    print(f"  room {GRIP_ROOM:.0f} mm to the neighbour's edge; one-sided pairs "
          f"{sum(len(r['one_sided']) for r in rows)} on "
          f"{sum(1 for r in rows if r['one_sided'])} tables")
    print(f"  out-from-my-own-middle test: calls {sum(len(r['own_middle']) for r in rows)} crowded, "
          f"misses {sum(len(set(r['crowded']) - set(r['own_middle'])) for r in rows)}, "
          f"adds {sum(len(set(r['own_middle']) - set(r['crowded'])) for r in rows)}")
    print(f"  glass zone sits {nearest:.0f}-{farthest:.0f} mm from the base, reach is "
          f"{COMFORTABLE_REACH[0]:.0f}-{COMFORTABLE_REACH[1]:.0f} mm; rack overlaps zone: "
          f"{rack_overlaps}")
    print(f"  floor: median {np.median(floors):.1f} mm, {floors.min():.1f}-{floors.max():.1f}, "
          f"total {floors.sum():.0f} mm; legal on "
          f"{sum(r['floor_legal'] for r in rows)}/{len(rows)}; "
          f"converged on {sum(r['floor_converged'] for r in rows)}/{len(rows)}; "
          f"{sum(r['floor_on_wall'] for r in rows)} glasses end on a zone wall")
    usable = [r for r in rows if len(r["restarts"]) >= 2]
    print(f"  jittered starts: {sum(1 for r in usable if max(r['restarts']) > r['floor_mm'] + 1.0)}"
          f"/{len(usable)} tables find a worse local optimum, worst "
          f"{max(max(r['restarts']) / r['floor_mm'] for r in usable):.2f}x the floor")
    for name, key in (("relaxation", "relax_mm"), ("Hungarian on slots", "pairing_best"),
                      ("Lloyd", "lloyd_mm")):
        values = column(rows, key) / floors
        print(f"  {name}: median {np.median(values):.2f}x the floor, worst {values.max():.1f}x")
    print(f"  relaxation: median {np.median(column(rows, 'relax_steps')):.0f} steps, legal on "
          f"{sum(r['relax_legal'] for r in rows)}/{len(rows)}, crowding falls at every step on "
          f"{sum(r['relax_monotone'] for r in rows)}/{len(rows)}, two glasses pass through each "
          f"other on {sum(1 for r in rows if r['relax_through'])}/{len(rows)}")
    ratios = column(rows, "pairing_greedy") / column(rows, "pairing_best")
    print(f"  slots: {np.median(column(rows, 'slots')):.0f} at a median spacing of "
          f"{np.median(list(spacing.values())):.0f} mm; greedy pairing ties Hungarian on "
          f"{int((ratios <= 1.0 + 1e-9).sum())}/{len(rows)} tables, worst {ratios.max():.2f}x")
    print(f"  Lloyd leaves {len(rows) - sum(r['lloyd_legal'] for r in rows)} of {len(rows)} tables "
          f"still illegal")


def main() -> None:
    rows, spacing = measure()
    # The pairing totals are wanted as plain columns in three figures, so they
    # are lifted out of the dict once rather than unpacked at every use.
    for row in rows:
        for key in ("best", "greedy", "worst"):
            row[f"pairing_{key}"] = row["pairing"][key]
    report(rows, spacing)
    picture_what_has_room_means(rows)
    picture_which_conditions_bind(rows)
    picture_the_displacement_floor(rows)
    picture_four_methods(rows)
    picture_assignment(rows)
    picture_relaxation(rows)


if __name__ == "__main__":
    main()
