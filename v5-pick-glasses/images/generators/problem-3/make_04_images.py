"""Diagrams for solution 4 — predict the slide with pushing mechanics.

Every glass drawn here is built by the project's own builder at proportions
drawn from ``KIND_RANGES["tapered_glass"]``, so no size on any of these
pictures was chosen to make a picture work. The mechanics is computed rather
than sketched: the load under the foot is solved for, the limit surface is the
real ellipse, and each push is integrated rather than drawn as an arc.

    pixi run python images/generators/problem-3/make_04_images.py

Everything the document quotes is printed by ``report()`` at the end, so a
number in the prose can be checked against a number on the terminal.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from diagram_style import (
    CAST,
    GLASS,
    GOOD,
    GRIP_ROOM,
    INK,
    KIND_NARROWEST,
    KIND_WIDEST,
    LABEL_SIZE,
    LOWEST_GRIP,
    MU_HIGH,
    MU_LOW,
    MUTED,
    NOTE_SIZE,
    STURDY,
    TABLE_FRICTION,
    TIPPY,
    WARN,
    bare,
    base_width,
    glass_from_above,
    glass_from_the_side,
    has_room,
    new,
    push_arrow,
    push_margin,
    pushable,
    save,
    tips,
    topple_height,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Ellipse, Polygon, Wedge

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses import spec  # noqa: E402
from work_cell.glasses.force import GLASS_DENSITY, GRAVITY, GRIP_FACTOR  # noqa: E402
from work_cell.glasses.shapes import build, family  # noqa: E402

KIND = spec.kind("tapered_glass")

# How many glasses the family sweeps run over, and the seed they are drawn
# with. Both are properties of the experiment, not of any glass.
SWEPT = 400
SEED = 0

# How far a push actually has to carry a glass, measured on the project's own
# crowded tables rather than guessed. ``scene(seed)`` in problem-3-sim/bench.py
# was run for the sixty tapered-kind seeds below 400 — the seeds where
# ``seed % 4 == 1``, which is 1 to 237 — and for every glass that bench's own
# ``has_room`` calls crowded, the shortfall is how far the nearest offending
# neighbour's edge reaches inside GRIP_ROOM. That is the least the glass has to
# travel to gain its room. 300 glasses, 210 of them crowded; the median
# shortfall is 11.8 mm and the largest in sixty scenes is 31.8 mm.
#
# The numbers are held here rather than recomputed because bench.py imports
# MuJoCo, which is in the problem-3-programmed environment and not in the root
# one every generator in this repository runs under. To check them:
#
#   cd problem-3-programmed && pixi run python -c "
#   import sys; sys.path.insert(0, '../problem-3-sim'); import bench; ..."
PUSH_TYPICAL = 11.8
PUSH_LONGEST = 31.8
CROWDED_OF = (210, 300, 60)

# The jaw, as problem-3-sim/bench.py builds it. Its fingers are 30 mm tall and
# ride with their middle at LOWEST_GRIP, so the face that meets the glass runs
# from 35 to 65 mm. A tapered glass is wider higher up, so it touches the top
# edge of that face first, and bench's JAW_TOP says so in as many words: this,
# not PUSH_HEIGHT, is how high the glass is really pushed.
JAW_TOP = 65.0
JAW_WIDTH = 28.0

# What problem 2 hands over, as bench.py models it: one standard deviation of
# 0.5 mm on a glass's position and 2.5 mm on a width. The position figure is
# the accuracy a prediction would have to beat to be worth having, and the
# width figure is the error the tipping rule's own input carries.
MEASURED_POSITION = 0.5
MEASURED_WIDTH = 2.5

# Three ways the weight of a glass can rest on its own foot, each written as
# the inner and outer edge of the contact as a fraction of the foot's radius.
# A slightly concave base stands on its rim; a true flat base carries load over
# the whole circle; a slightly domed base stands on a patch in the middle and
# rocks. Nothing in this cell can tell them apart, and the difference decides
# both how far out the glass may be pushed and how much it turns when it is.
RIM = (0.90, 1.00)
FLAT = (0.00, 1.00)
DOMED = (0.00, 0.55)
BASES_MODELLED = ((RIM, "slightly concave:\nit stands on its rim"),
                  (FLAT, "flat: load over\nthe whole foot"),
                  (DOMED, "slightly domed: it stands\non a patch in the middle"))

RADIAL, ANGULAR = 90, 240


# --------------------------------------------------------------------------- #
# The glasses, and what can be computed about them without measuring one.
# --------------------------------------------------------------------------- #
def outline_mm(outline) -> tuple[np.ndarray, np.ndarray]:
    """Heights and radii of one built outline, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def base_diameter(outline) -> float:
    """How wide the foot is, read off the outline where it meets the table."""
    return float(2.0 * outline.radius[0] * 1000.0)


def radius_at(outline, height: float) -> float:
    """How far the wall stands out from the axis at one height above the table."""
    z, r = outline_mm(outline)
    return float(np.interp(height, z, r))


def mass_kg(outline) -> float:
    """What the glass weighs, by the same shell sum the project's force module uses."""
    z, r = np.asarray(outline.height), np.asarray(outline.radius)
    lateral = float(np.trapezoid(2.0 * np.pi * r, z))
    disc = float(np.pi * r[0] ** 2)
    return (lateral + disc) * KIND.wall_thickness_m * GLASS_DENSITY


def from_cast(entry):
    """Build one of diagram_style's cast as a real outline."""
    height, rim, fraction = entry
    return build("tapered_glass", height=height / 1000.0,
                 rim_diameter=rim / 1000.0, base_fraction=fraction)


# --------------------------------------------------------------------------- #
# The mechanics.
# --------------------------------------------------------------------------- #
def load_centre(mu: float, height: float) -> float:
    """How far forward the weight shifts while the glass is being pushed.

    Take moments about the middle of the foot, at table level. The push is
    ``mu * m * g`` at height ``height``; the friction that balances it acts at
    table level, so it has no moment there; and the only thing left to cancel
    the push's moment is the ground pressing up harder at the front than at the
    back. The upward force is the whole weight, so its centre has to sit
    ``mu * height`` forward of the middle. The mass cancels, which is the one
    unknown in this problem that removes itself.
    """
    return mu * height


def foot_grid(contact, foot_radius: float):
    """Sample points over the part of the foot that carries load, with their areas."""
    inner, outer = contact[0] * foot_radius, contact[1] * foot_radius
    edges = np.linspace(inner, outer, RADIAL + 1)
    radii = 0.5 * (edges[:-1] + edges[1:])
    ring_area = np.pi * (edges[1:] ** 2 - edges[:-1] ** 2) / ANGULAR
    angles = np.linspace(0.0, 2.0 * np.pi, ANGULAR, endpoint=False)
    r = np.repeat(radii, ANGULAR)
    area = np.repeat(ring_area, ANGULAR)
    a = np.tile(angles, RADIAL)
    return r * np.cos(a), r * np.sin(a), area


def pressure(contact, foot_radius: float, shift: float):
    """The load under the foot once the push has thrown the weight forward.

    The pressure varies linearly across the foot and cannot pull, so once the
    centre of load has moved far enough forward the back of the foot lifts and
    only a front crescent carries anything. Returns the sample points and the
    load at each, or ``None`` for the whole thing when no non-negative load on
    that contact can balance the push — which is the glass tipping over.
    """
    x, y, area = foot_grid(contact, foot_radius)
    outer = contact[1] * foot_radius
    if shift >= outer * 0.999:
        return None, None, None

    def centre_of(slope: float) -> float:
        load = np.maximum(0.0, 1.0 + slope * x / max(outer, 1e-9)) * area
        return float(np.sum(load * x) / np.sum(load))

    low, high = 0.0, 1.0
    while centre_of(high) < shift and high < 1e9:
        high *= 2.0
    for _ in range(120):
        middle = 0.5 * (low + high)
        if centre_of(middle) < shift:
            low = middle
        else:
            high = middle
    load = np.maximum(0.0, 1.0 + 0.5 * (low + high) * x / max(outer, 1e-9)) * area
    return x, y, load / np.sum(load)


def mean_support_radius(contact, foot_radius: float, shift: float) -> float | None:
    """The one number the limit surface needs about the base, in millimetres.

    Call it ``c``. It is the average distance from the centre of friction at
    which the weight rests. A base that stands on its rim gives ``c`` close to
    the foot's own radius; a flat base carrying load everywhere gives two
    thirds of it; a domed base that stands on a patch in the middle gives much
    less. Nothing on this cell can tell which.
    """
    x, y, load = pressure(contact, foot_radius, shift)
    if load is None:
        return None
    return float(np.sum(load * np.hypot(x - shift, y)))


def tips_over(contact, foot_radius: float, mu: float, height: float) -> bool:
    """Whether a push at this height throws the weight past the front of the contact."""
    return load_centre(mu, height) >= contact[1] * foot_radius * 0.999


def limit_surface_motion(q, c: float, drive):
    """The twist a contact produces, from the ellipsoidal limit surface.

    ``q`` is where the finger touches, measured from the centre of friction,
    and ``drive`` is the pusher's velocity. The limit surface is the closed
    surface in (force, force, moment) space holding every load the table can
    just sustain. The ellipsoidal approximation makes it an ellipsoid whose
    moment axis is ``c`` times its force axes. Its decisive property is that
    the glass moves along the outward normal at the point where the load sits,
    and for an ellipsoid that means the glass slides parallel to the force and
    turns at ``moment / c^2`` times its sliding speed.

    Returns the velocity of the material point at the centre of friction, the
    turning rate, and whether the pad had to skid across the glass.
    """
    qx, qy = float(q[0]), float(q[1])
    matrix = np.eye(2) + np.array([[qy * qy, -qx * qy], [-qx * qy, qx * qx]]) / c**2
    scaled = np.linalg.solve(matrix, drive)
    turn = (qx * scaled[1] - qy * scaled[0]) / c**2
    if scaled[0] > 0.0 and abs(scaled[1]) <= GRIP_FACTOR * scaled[0]:
        return scaled, turn, False
    # Outside the pad's friction cone the finger skids. The force then sits on
    # an edge of the cone and only its size is unknown.
    for sign in (1.0, -1.0):
        edge = np.array([1.0, sign * GRIP_FACTOR]) / np.hypot(1.0, GRIP_FACTOR)
        cross = qx * edge[1] - qy * edge[0]
        denominator = edge[0] - qy * cross / c**2
        if denominator <= 0.0:
            continue
        size = float(drive[0]) / denominator
        speed, spin = size * edge, size * cross / c**2
        sliding = (speed + spin * np.array([-qy, qx]) - drive)[1]
        if sign * sliding <= 0.0:
            return speed, spin, True
    return scaled, turn, True


def push(outline, mu: float, contact, bias: float, height: float = LOWEST_GRIP,
         distance: float = PUSH_LONGEST, steps: int = 900):
    """Push one glass in a straight line and say where its axis ends up.

    The pusher is the closed gripper: a flat vertical face moving straight,
    touching the glass on its wall. ``bias`` is how far the glass's own base
    puts its centre of friction to one side of its axis, which nothing
    measures. Returns forward travel, sideways drift, the turn in radians,
    whether the pad skidded, and whether the glass tipped instead of sliding.
    """
    foot = base_diameter(outline) / 2.0
    wall = radius_at(outline, height)
    shift = load_centre(mu, height)
    c = mean_support_radius(contact, foot, shift)
    if c is None:
        return 0.0, 0.0, 0.0, False, True, np.zeros((1, 2))

    drive = np.array([1.0, 0.0])
    axis = np.array([0.0, 0.0])
    angle, skidded = 0.0, False
    step = distance / steps
    path = [axis.copy()]
    for _ in range(steps):
        turned = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        offset = np.array([shift, 0.0]) + turned @ np.array([0.0, bias])
        speed, turn, skid = limit_surface_motion(np.array([-wall, 0.0]) - offset, c, drive)
        skidded = skidded or skid
        axis = axis + (speed + turn * np.array([offset[1], -offset[0]])) * step
        angle = angle + turn * step
        path.append(axis.copy())
    return float(axis[0]), float(axis[1]), float(angle), skidded, False, np.array(path)


# --------------------------------------------------------------------------- #
# The glasses these pictures are drawn on.
# --------------------------------------------------------------------------- #
FAMILY = [outline for outline, _ in family("tapered_glass", SWEPT, SEED)]
FEET = np.array([base_diameter(outline) for outline in FAMILY])
MASSES = np.array([mass_kg(outline) for outline in FAMILY])

# The worked glass is the middle one of those that pass the tipping test at the
# grippiest table in the bracket. It has to be one of those, because a glass
# that may not be pushed at all is a glass with nothing to predict.
ALLOWED = [i for i in range(SWEPT) if pushable(FEET[i], MU_HIGH)]
WORKED = FAMILY[ALLOWED[int(np.argsort(FEET[ALLOWED])[len(ALLOWED) // 2])]]

WORKED_FOOT_WIDTH = base_diameter(WORKED)
WORKED_FOOT = WORKED_FOOT_WIDTH / 2.0
WORKED_HEIGHT = outline_mm(WORKED)[0].max()
WORKED_RIM = 2.0 * outline_mm(WORKED)[1].max()
WORKED_WALL = radius_at(WORKED, LOWEST_GRIP)

# How far off the axis the centre of friction can sit. A pressed base stands on
# three high spots; the other two add to nothing, so if one of them carries
# twice its share the centre of the load lands a quarter of the foot's radius
# off the axis. That is a derivation from an assumed imbalance, not a
# measurement, and the document says so.
BIAS_MAX = WORKED_FOOT / 4.0


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, **kwargs) -> None:
    axis.text(x, y, text, fontsize=size, color=colour, ha=kwargs.pop("ha", "center"), **kwargs)


def stage(axis, title: str) -> None:
    bare(axis)
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)


def plot_frame(axis, title: str, xlabel: str, ylabel: str) -> None:
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)
    axis.set_xlabel(xlabel, fontsize=NOTE_SIZE, color=INK)
    axis.set_ylabel(ylabel, fontsize=NOTE_SIZE, color=INK)
    axis.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.015, text, fontsize=NOTE_SIZE, color=INK, ha="center")


def real_outline(axis, outline, x=0.0, colour=GLASS, alpha=0.26, lw=1.4) -> None:
    """Draw a built outline from the side, as the shape the builder made."""
    z, r = outline_mm(outline)
    points = [(x - radius, height) for height, radius in zip(z[::-1], r[::-1], strict=True)]
    points += [(x + radius, height) for height, radius in zip(z, r, strict=True)]
    axis.add_patch(Polygon(points, closed=True, facecolor=to_rgba(colour, alpha),
                           edgecolor=colour, lw=lw, zorder=3))


# --------------------------------------------------------------------------- #
# 1. Where h < a / mu comes from.
# --------------------------------------------------------------------------- #
def picture_the_moment_balance() -> None:
    figure, axes = new(13.6, 5.8, columns=2)
    body, walk = axes

    stage(body, "The free body: two moments about the front edge of the foot")
    body.set_aspect("equal")
    body.set_xlim(-136, 124)
    body.set_ylim(-62, WORKED_HEIGHT + 46)
    body.plot([-124, 118], [0, 0], color=INK, lw=1.8, zorder=1)
    real_outline(body, WORKED)

    edge = WORKED_FOOT
    body.plot([edge], [0], "o", color=WARN, ms=7, zorder=8)
    body.plot([edge, edge], [0, LOWEST_GRIP + 6], color=WARN, lw=0.9, ls=(0, (3, 3)), zorder=2)

    push_arrow(body, (-WORKED_WALL - 46, LOWEST_GRIP), (-WORKED_WALL - 2, LOWEST_GRIP), colour=INK)
    note(body, -WORKED_WALL - 24, LOWEST_GRIP + 6, "the push, P", INK)
    body.annotate("", xy=(0, 16), xytext=(0, WORKED_HEIGHT * 0.52),
                  arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 1.5}, zorder=7)
    note(body, -6, WORKED_HEIGHT * 0.55, "the weight, m g", INK, ha="right")
    body.annotate("", xy=(-46, -30), xytext=(-4, -30),
                  arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 1.3}, zorder=7)
    note(body, -25, -40, "friction from the table, μ m g", va="top")

    body.annotate("", xy=(-WORKED_WALL - 58, 0), xytext=(-WORKED_WALL - 58, LOWEST_GRIP),
                  arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.0}, zorder=7)
    body.plot([-WORKED_WALL - 58, -WORKED_WALL - 2], [LOWEST_GRIP, LOWEST_GRIP],
              color=MUTED, lw=0.7, ls=(0, (2, 3)), zorder=2)
    note(body, -WORKED_WALL - 63, LOWEST_GRIP / 2, "h", INK, size=LABEL_SIZE,
         ha="right", va="center")
    body.annotate("", xy=(0, -12), xytext=(edge, -12),
                  arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.0}, zorder=7)
    note(body, edge / 2, -14, "a", INK, size=LABEL_SIZE, va="top")

    note(body, -132, WORKED_HEIGHT + 40,
         "turning it over:  P · h\n"
         "holding it down:  m g · a\n"
         "sliding needs     P = μ m g\n"
         "so it slides while  h < a / μ",
         INK, size=NOTE_SIZE + 0.6, ha="left", va="top", family="monospace")
    note(body, edge + 8, LOWEST_GRIP + 8, "it tips about\nthis edge", WARN, ha="left", va="bottom")
    note(body, 0, -52, f"drawn at the lowest push the gripper can make, {LOWEST_GRIP:.0f} mm")

    stage(walk, "The same statement: the weight walks forward by μ h")
    walk.set_xlim(-54, 104)
    walk.set_ylim(-214, 62)
    rows = ((0.0, MU_LOW, LOWEST_GRIP), (-52.0, TABLE_FRICTION, LOWEST_GRIP),
            (-104.0, MU_HIGH, LOWEST_GRIP), (-156.0, MU_HIGH, JAW_TOP))
    contact = FLAT
    for base_y, mu, height in rows:
        shift = load_centre(mu, height)
        outer = contact[1] * WORKED_FOOT
        walk.plot([-WORKED_FOOT, WORKED_FOOT], [base_y, base_y], color=MUTED, lw=1.0, zorder=2)
        walk.plot([-outer, outer], [base_y, base_y], color=INK, lw=2.6, zorder=4)
        over = tips_over(contact, WORKED_FOOT, mu, height)
        colour = WARN if over else GOOD
        x, _y, load = pressure(contact, WORKED_FOOT, shift)
        if load is not None:
            slice_x = np.linspace(-outer, outer, 90)
            profile = np.interp(slice_x, np.sort(x), load[np.argsort(x)] * 0 + 0)
            del profile
            bins = np.linspace(-outer, outer, 46)
            index = np.clip(np.digitize(x, bins) - 1, 0, len(bins) - 2)
            heights = np.bincount(index, weights=load, minlength=len(bins) - 1)
            centres = 0.5 * (bins[:-1] + bins[1:])
            walk.fill_between(centres, base_y, base_y + 26.0 * heights / max(heights.max(), 1e-9),
                              color=to_rgba(colour, 0.28), zorder=3)
        walk.plot([min(shift, outer + 4.0)], [base_y - 7], "^", color=colour, ms=9, zorder=6)
        pushed_at = ("pushed at the lowest the jaw rides" if height == LOWEST_GRIP
                     else "pushed at the top edge of the jaw")
        walk.text(-52, base_y + 17,
                  f"μ = {mu},  h = {height:.0f} mm: the load sits {shift:.0f} mm forward\n"
                  + pushed_at,
                  fontsize=NOTE_SIZE, color=INK, ha="left", va="center")
        walk.text(WORKED_FOOT + 11, base_y - 7,
                  "still on the foot" if not over else "past it: the glass goes over",
                  fontsize=NOTE_SIZE, color=colour, ha="left", va="center")
    walk.plot([WORKED_FOOT, WORKED_FOOT], [-174, 26], color=MUTED, lw=0.9,
              ls=(0, (3, 3)), zorder=1)
    note(walk, WORKED_FOOT, 34, f"the front edge of the foot, a = {WORKED_FOOT:.1f} mm", INK)
    note(walk, 20, -190,
         "the foot seen edge-on, with the load under it. A tapered glass is wider higher\n"
         "up, so it meets the top edge of the jaw first — which is what the last row costs.")

    footer(figure,
           f"One glass of the kind, built {WORKED_HEIGHT:.0f} mm tall with a {WORKED_RIM:.0f} mm rim, "
           f"standing on a foot {WORKED_FOOT_WIDTH:.1f} mm across. The mass cancels out of both "
           "statements, so the rule needs no weighing — only μ, which nothing in this cell measures.")
    figure.subplots_adjust(bottom=0.13, top=0.89, wspace=0.10)
    save(figure, "04-the-moment-balance.png")


# --------------------------------------------------------------------------- #
# 2. What that rule does to a whole family of glasses.
# --------------------------------------------------------------------------- #
def picture_who_can_be_pushed() -> None:
    figure, axes = new(13.6, 4.9, columns=2)
    spread, share = axes

    plot_frame(spread, f"The feet of {SWEPT} drawn glasses of the kind",
               "how wide the foot is (mm)", "how many glasses")
    spread.hist(FEET, bins=26, color=to_rgba(GLASS, 0.50), edgecolor=GLASS, lw=0.8)
    top = spread.get_ylim()[1]
    for mu, colour, level in ((MU_LOW, GOOD, 0.98), (MU_HIGH, WARN, 0.58)):
        cut = 2.0 * mu * LOWEST_GRIP
        spread.axvline(cut, color=colour, lw=1.6)
        ok = 100.0 * np.mean([pushable(b, mu) for b in FEET])
        spread.annotate(f"μ = {mu}: a foot narrower than\n{cut:.0f} mm topples before it slides\n"
                        f"{ok:.0f} per cent of them are wider",
                        xy=(cut, top * (level - 0.02)), xytext=(FEET.max() + 6, top * level),
                        fontsize=NOTE_SIZE, color=colour, ha="left", va="top",
                        arrowprops={"arrowstyle": "-", "color": colour, "lw": 0.8})
    spread.set_xlim(FEET.min() - 3, FEET.max() + 46)
    spread.set_ylim(0, top * 1.06)

    plot_frame(share, "How many of them may be pushed at all",
               "friction between glass and table, μ", "share that may be pushed (per cent)")
    mus = np.linspace(0.20, 0.70, 140)
    lines = ((LOWEST_GRIP, 1.00, INK, "-",
              f"pushed at {LOWEST_GRIP:.0f} mm, contact out to the edge of the foot"),
             (LOWEST_GRIP, 0.70, MUTED, (0, (2, 2)),
              f"pushed at {LOWEST_GRIP:.0f} mm, contact out to 70 per cent of it"),
             (JAW_TOP, 1.00, WARN, (0, (5, 2)),
              f"pushed at {JAW_TOP:.0f} mm, where the jaw's top edge really meets it"))
    for height, reach, colour, style, label in lines:
        curve = [100.0 * np.mean([(reach * b / 2.0) / mu > height for b in FEET]) for mu in mus]
        share.plot(mus, curve, color=colour, lw=1.8, ls=style, label=label)
    for mu, where in ((MU_LOW, (0.212, 120)), (MU_HIGH, (0.555, 44))):
        value = 100.0 * np.mean([pushable(b, mu) for b in FEET])
        share.plot([mu], [value], "o", color=GOOD, ms=7, zorder=6)
        share.annotate(f"μ = {mu}: {value:.0f} per cent", xy=(mu, value), xytext=where,
                       fontsize=NOTE_SIZE, color=GOOD, ha="left", va="center",
                       arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.8})
    share.axvline(TABLE_FRICTION, color=GLASS, lw=1.2)
    share.text(TABLE_FRICTION + 0.008, 104,
               f"what the simulator really uses: {TABLE_FRICTION}.\nThe arm is never told it.",
               fontsize=NOTE_SIZE, color=GLASS, ha="left", va="bottom")
    share.legend(loc="upper right", frameon=False, fontsize=NOTE_SIZE - 0.4,
                 handlelength=2.2, labelcolor=INK)
    share.set_xlim(0.20, 0.715)
    share.set_ylim(-8, 168)

    footer(figure,
           "Read the right panel as three guesses about the same glasses, not as three kinds of "
           "glass. The solid line is the bound every document in this problem quotes. The dotted "
           "one is the same bound for a base whose weight rests further in, and the dashed one is "
           "the bound at the height a tapered glass really meets the jaw. No camera here can tell "
           "the first two apart, and the third is geometry the jaw already commits to.")
    figure.subplots_adjust(bottom=0.21, top=0.88, wspace=0.22)
    save(figure, "04-who-can-be-pushed.png")


# --------------------------------------------------------------------------- #
# 3. The friction cone, and Mason's vote.
# --------------------------------------------------------------------------- #
def picture_the_cone_and_the_vote() -> None:
    figure, axes = new(13.6, 5.8, columns=2)
    cone, vote = axes
    half_angle = np.arctan(GRIP_FACTOR)
    contact = np.array([-WORKED_WALL, 0.0])
    section = 2.0 * WORKED_WALL

    stage(cone, "The friction cone at the pad, drawn on the glass it touches")
    cone.set_aspect("equal")
    cone.set_xlim(-92, 98)
    cone.set_ylim(-88, 78)
    glass_from_above(cone, (0, 0), section, WORKED_FOOT_WIDTH / section, alpha=0.20)
    cone.plot([contact[0] - 3, contact[0] - 3], [-24, 24], color=INK, lw=3.4, zorder=5)
    note(cone, contact[0] - 8, 26, "the closed gripper,\na flat face", INK, ha="right", va="bottom")

    reach = 62.0
    cone.add_patch(Wedge(tuple(contact), reach, -np.degrees(half_angle), np.degrees(half_angle),
                         facecolor=to_rgba(GOOD, 0.18), edgecolor="none", zorder=2))
    for sign in (1, -1):
        angle = sign * half_angle
        cone.annotate("", xy=tuple(contact + reach * np.array([np.cos(angle), np.sin(angle)])),
                      xytext=tuple(contact), zorder=6,
                      arrowprops={"arrowstyle": "-|>", "color": WARN, "lw": 1.4})
    cone.annotate("", xy=(contact[0] + reach, 0.0), xytext=tuple(contact), zorder=6,
                  arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 1.2, "ls": (0, (4, 3))})
    note(cone, contact[0] + reach + 4, 0, "straight in", INK, ha="left", va="center")
    note(cone, contact[0] + 30, 70,
         f"anything the pad can push along lies inside this cone:\n"
         f"half-angle arctan μ = {np.degrees(half_angle):.0f}°, silicone on glass, μ = {GRIP_FACTOR}",
         WARN, ha="left", va="top")
    note(cone, 0, -48, "the glass, cut across at the height of the push")
    note(cone, 0, -64,
         "a flat face meets a round glass on the line through its axis,\n"
         "however far to one side the aim lands")

    shift = load_centre(MU_LOW, LOWEST_GRIP)
    edge_at_load = GRIP_FACTOR * (shift + WORKED_WALL)
    reachable = float(np.sqrt(max(0.0, WORKED_FOOT**2 - shift**2)))

    stage(vote, "Mason's vote: two guesses at the centre of friction, a few millimetres apart")
    vote.set_aspect("equal")
    vote.set_xlim(-92, 98)
    vote.set_ylim(-88, 78)
    vote.add_patch(Circle((0, 0), WORKED_FOOT, facecolor=to_rgba(GLASS, 0.14),
                          edgecolor=GLASS, lw=1.0, ls=(0, (3, 2)), zorder=3))
    wedge = np.linspace(0.0, 78.0, 2)
    for sign in (1, -1):
        angle = sign * half_angle
        vote.plot(contact[0] + wedge * np.cos(angle), wedge * np.sin(angle),
                  color=WARN, lw=1.2, zorder=4)
    along = np.linspace(0.0, 150.0, 2)
    vote.plot(contact[0] + along, 0.0 * along, color=INK, lw=1.3, ls=(0, (4, 3)), zorder=4)
    vote.plot([shift, shift], [-WORKED_FOOT - 4, WORKED_FOOT + 4], color=MUTED, lw=0.9,
              ls=(0, (2, 2)), zorder=3)

    gap = BIAS_MAX / 2.0
    for sideways, colour, tally, level in ((gap, GOOD, "2 votes to 1: it turns this way", 14.0),
                                           (-gap, WARN, "2 votes to 1: it turns the other way",
                                            -18.0)):
        vote.plot([shift], [sideways], "P", color=colour, ms=8, zorder=7)
        vote.annotate("", xy=(shift + 2.0, sideways), xytext=(32, level), zorder=6,
                      arrowprops={"arrowstyle": "-", "color": colour, "lw": 0.8})
        vote.text(33, level, tally, fontsize=NOTE_SIZE, color=colour, ha="left", va="center")
    vote.text(-90, 72, "the push line", fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    vote.text(-90, -22, "the two edges of\nthe friction cone", fontsize=NOTE_SIZE,
              color=WARN, ha="left", va="top")
    vote.text(shift, -48, f"the push puts the centre of friction {shift:.0f} mm forward,\n"
              "whatever else is guessed", fontsize=NOTE_SIZE, color=MUTED,
              ha="center", va="top")
    note(vote, 4, -72,
         f"the blue disc is the foot: everywhere the centre of friction could be.\n"
         f"A unanimous vote would need it {edge_at_load:.0f} mm off the axis, and the foot only "
         f"reaches {reachable:.0f} mm.")

    footer(figure,
           "Mason's theorem asks each of three lines which side of the centre of friction it passes "
           "and lets the majority decide which way the glass turns. It needs no mass, no friction "
           "with the table and no pressure distribution — only where the centre of friction is, and "
           "that is the number this cell has not got.")
    figure.subplots_adjust(bottom=0.15, top=0.89, wspace=0.08)
    save(figure, "04-the-friction-cone-and-the-vote.png")


# --------------------------------------------------------------------------- #
# 4. The limit surface, and the one number it needs about the base.
# --------------------------------------------------------------------------- #
def picture_the_limit_surface() -> None:
    figure, axes = new(13.6, 5.4, columns=2)
    feet, surface = axes

    stage(feet, "Three bases nobody in this cell can tell apart")
    feet.set_aspect("equal")
    feet.set_xlim(-40, 220)
    feet.set_ylim(-56, 50)
    for index, (contact, label) in enumerate(BASES_MODELLED):
        x = index * 90.0
        inner, outer = contact[0] * WORKED_FOOT, contact[1] * WORKED_FOOT
        feet.add_patch(Circle((x, 0), WORKED_FOOT, facecolor="none", edgecolor=MUTED,
                              lw=1.0, ls=(0, (3, 2)), zorder=3))
        feet.add_patch(Wedge((x, 0), outer, 0, 360, width=outer - inner,
                             facecolor=to_rgba(GLASS, 0.34), edgecolor=GLASS, lw=1.0, zorder=2))
        c = mean_support_radius(contact, WORKED_FOOT, 0.0)
        feet.add_patch(Circle((x, 0), c, facecolor="none", edgecolor=WARN, lw=1.6, zorder=5))
        feet.text(x, -32, label, fontsize=NOTE_SIZE, color=INK, ha="center", va="top")
        feet.text(x, 27, f"c = {c:.1f} mm", fontsize=NOTE_SIZE, color=WARN, ha="center")
    note(feet, 90, 50,
         "blue is where the weight rests; the red circle is c, the average distance out at which "
         "it rests", WARN, va="top")

    plot_frame(surface, "The limit surface, sliced through the push direction",
               "force along the push  (as a fraction of μ m g)",
               "moment about the centre of friction  (mm × μ m g)")
    load_f = 0.80
    for (contact, _label), colour, style in zip(
            BASES_MODELLED, (INK, GLASS, MUTED), ("-", (0, (5, 2)), (0, (2, 2))), strict=True):
        c = mean_support_radius(contact, WORKED_FOOT, 0.0)
        surface.add_patch(Ellipse((0, 0), 2.0, 2.0 * c, facecolor="none",
                                  edgecolor=colour, lw=1.7, ls=style, zorder=3))
        surface.text(0.05, c + 0.6, f"c = {c:.1f} mm", fontsize=NOTE_SIZE, color=colour, ha="left")
        load_m = c * np.sqrt(max(0.0, 1.0 - load_f**2))
        surface.plot([load_f], [load_m], "o", color=colour, ms=6, zorder=6)
        direction = np.array([load_f, load_m / c**2])
        direction = direction / np.linalg.norm(direction)
        surface.annotate("", xy=(load_f + direction[0] * 0.30, load_m + direction[1] * 20.0),
                         xytext=(load_f, load_m), zorder=7,
                         arrowprops={"arrowstyle": "-|>", "color": colour, "lw": 1.5})
    surface.plot([load_f, load_f], [-WORKED_FOOT * 1.05, WORKED_FOOT * 0.62], color=WARN,
                 lw=0.9, ls=(0, (3, 3)), zorder=2)
    surface.text(load_f, -WORKED_FOOT * 1.10, "one load", fontsize=NOTE_SIZE, color=WARN,
                 ha="center", va="top")
    surface.text(1.14, 2.0, "these three arrows\nare the outward\nnormals", fontsize=NOTE_SIZE,
                 color=INK, ha="left", va="center")
    surface.set_xlim(-1.10, 1.86)
    surface.set_ylim(-WORKED_FOOT * 1.34, WORKED_FOOT * 1.30)

    footer(figure,
           "The limit surface holds every combination of sliding force and twisting moment the table "
           "can just sustain, and the glass moves along the outward normal where the load sits on "
           "it. Its shape depends on the base through one number, c, which an overhead camera "
           "cannot see.")
    figure.subplots_adjust(bottom=0.16, top=0.88, wspace=0.24)
    save(figure, "04-the-limit-surface.png")


# --------------------------------------------------------------------------- #
# 5. What the prediction is actually worth.
# --------------------------------------------------------------------------- #
MUS = (MU_LOW, TABLE_FRICTION, MU_HIGH)
REACHES = (RIM, FLAT, (0.0, 0.80), DOMED)


def sweep():
    """Every prediction the model makes for the worked glass across the unknowns."""
    rows = []
    for mu in MUS:
        for contact in REACHES:
            for bias in (0.0, BIAS_MAX / 2.0, BIAS_MAX):
                forward, sideways, turn, skid, tipped, path = push(WORKED, mu, contact, bias)
                rows.append((mu, contact, bias, forward, sideways, np.degrees(turn),
                             skid, tipped, path))
    return rows


def one_at_a_time(rows):
    """How much each unknown moves the answer, with the other two held in the middle."""
    standing = [row for row in rows if not row[7]]
    middle = {0: TABLE_FRICTION, 1: FLAT, 2: BIAS_MAX / 2.0}
    out = []
    for index, name, colour in ((2, "the base's own bias,\n0 to a quarter of the foot radius", WARN),
                                (1, "where the weight rests,\nthe rim to a patch in the middle", GLASS),
                                (0, f"friction with the table,\nμ from {MU_LOW} to {MU_HIGH}", MUTED)):
        held = [row for row in standing
                if all(row[k] == middle[k] for k in (0, 1, 2) if k != index)]
        values = [row[4] for row in held] or [0.0]
        out.append((name, max(values) - min(values), colour, len(held)))
    return out


def picture_the_spread() -> None:
    rows = sweep()
    standing = [row for row in rows if not row[7]]
    figure, axes = new(13.6, 5.6, columns=2)
    fan, bars = axes

    plot_frame(fan, "Every path the model predicts for one push of one glass",
               "how far the gripper has travelled (mm)",
               "how far the glass has slipped sideways (mm)")
    for mu, _contact, _bias, _forward, _sideways, _turn, _skid, _tipped, path in standing:
        shade = {MU_LOW: WARN, TABLE_FRICTION: GLASS, MU_HIGH: MUTED}[mu]
        fan.plot(path[:, 0], path[:, 1], color=to_rgba(shade, 0.75), lw=1.2)
    ends = np.array([(row[3], row[4]) for row in standing])
    lowest, highest = ends[:, 1].min(), ends[:, 1].max()
    fan.plot(ends[:, 0], ends[:, 1], "o", color=INK, ms=4, zorder=6)
    fan.annotate("", xy=(PUSH_LONGEST + 2.0, highest), xytext=(PUSH_LONGEST + 2.0, lowest),
                 zorder=6, arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.2})
    fan.text(PUSH_LONGEST + 3.2, (lowest + highest) / 2,
             f"{highest - lowest:.1f} mm\nof spread", fontsize=NOTE_SIZE, color=INK,
             ha="left", va="center")

    at_typical = [float(np.interp(PUSH_TYPICAL, row[8][:, 0], row[8][:, 1])) for row in standing]
    fan.plot([PUSH_TYPICAL, PUSH_TYPICAL], [min(at_typical), max(at_typical)],
             color=INK, lw=2.4, zorder=7)
    fan.text(PUSH_TYPICAL + 1.4, -1.25,
             f"the black bar is the median crowded glass, which only has to move\n"
             f"{PUSH_TYPICAL} mm. By there the whole spread is "
             f"{max(at_typical) - min(at_typical):.2f} mm.",
             fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    fan.fill_between([-0.6, PUSH_LONGEST + 0.6], -MEASURED_POSITION, MEASURED_POSITION,
                     color=to_rgba(GOOD, 0.22), zorder=1)
    fan.text(0.6, -MEASURED_POSITION - 0.10,
             f"one look already settles it to ±{MEASURED_POSITION} mm",
             fontsize=NOTE_SIZE, color=GOOD, ha="left", va="top")
    for mu, shade, level in ((MU_LOW, WARN, 0.98), (TABLE_FRICTION, GLASS, 0.90),
                             (MU_HIGH, MUTED, 0.82)):
        fan.text(0.6, highest * level, f"μ = {mu}", fontsize=NOTE_SIZE, color=shade,
                 ha="left", va="center")
    fan.set_xlim(-0.6, PUSH_LONGEST + 12)
    fan.set_ylim(-2.3, highest * 1.10)

    entries = one_at_a_time(rows)
    plot_frame(bars, "What each unknown is worth on its own, over the longest push",
               "spread it accounts for with the other two held at the middle guess (mm)", "")
    order = sorted(range(len(entries)), key=lambda i: entries[i][1])
    bars.barh([entries[i][0] for i in order], [entries[i][1] for i in order],
              color=[to_rgba(entries[i][2], 0.50) for i in order],
              edgecolor=[entries[i][2] for i in order], height=0.5)
    widest = max(entry[1] for entry in entries)
    for position, index in enumerate(order):
        bars.text(entries[index][1] + widest * 0.02, position, f"{entries[index][1]:.2f} mm",
                  fontsize=NOTE_SIZE, color=entries[index][2], va="center")
    bars.axvline(MEASURED_POSITION, color=GOOD, lw=1.6)
    bars.text(MEASURED_POSITION + widest * 0.02, -0.72,
              f"what one look already costs: {MEASURED_POSITION} mm", fontsize=NOTE_SIZE,
              color=GOOD, va="bottom")
    bars.tick_params(axis="y", labelsize=NOTE_SIZE)
    bars.set_xlim(0, widest * 1.34)
    bars.set_ylim(-1.0, len(entries) - 0.4)

    footer(figure,
           f"Every line is the same push predicted with a different guess at the three numbers "
           f"nobody here measures, over the longest push any crowded glass needed in "
           f"{CROWDED_OF[2]} of the project's own tables. Forward travel is exactly the distance "
           f"the gripper moved, because a flat face keeps a round glass in front of it; "
           f"{len(rows) - len(standing)} of the {len(rows)} guesses say the glass topples instead, "
           "and are not drawn.")
    figure.subplots_adjust(bottom=0.17, top=0.89, wspace=0.36, left=0.04, right=0.985)
    save(figure, "04-the-spread-of-predictions.png")


# --------------------------------------------------------------------------- #
# 6. What the working simulator does instead, and where its tipping edge is.
# --------------------------------------------------------------------------- #
# The rule problem-3-sim/bench.py uses to turn an outline into collision
# shapes, copied here because bench.py imports MuJoCo and this script must run
# in the root environment. Each cylinder is as wide as the glass is at its
# widest inside it, so the shape is never thinner than the glass, and bench's
# own docstring says of the bottom one: "the foot, which is the edge a glass
# tips over".
SLICE_TOLERANCE = 1.5


def stacked_cylinders(outline) -> list[tuple[float, float, float]]:
    """The glass as (bottom, top, radius) in millimetres, from the table up."""
    height, radius = outline_mm(outline)
    cut, start = [], 0
    for i in range(1, len(height)):
        inside = radius[start:i + 1]
        if inside.max() - inside.min() > SLICE_TOLERANCE and i - 1 > start:
            cut.append((float(height[start]), float(height[i - 1]), float(radius[start:i].max())))
            start = i - 1
    cut.append((float(height[start]), float(height[-1]), float(radius[start:].max())))
    return cut


def picture_the_working_model() -> None:
    figure, axis = new(12.8, 4.6)
    bare(axis)
    axis.set_aspect("equal")
    step = 210.0
    axis.plot([-104, 104 + 3 * step], [0, 0], color=INK, lw=1.6)
    axis.axhline(LOWEST_GRIP, color=MUTED, lw=1.0, ls=(0, (4, 3)))
    axis.axhline(JAW_TOP, color=WARN, lw=1.0, ls=(0, (4, 3)))
    for index, entry in enumerate(CAST):
        x = index * step
        height, rim, fraction = entry
        outline = from_cast(entry)
        foot = base_diameter(outline)
        # A tapered glass's wall is straight, so the trapezium diagram_style
        # draws is the outline the builder made, not an approximation of it.
        glass_from_the_side(axis, x, height, rim, fraction, alpha=0.16, lw=1.0)
        stack = stacked_cylinders(outline)
        for order, (bottom, top, radius) in enumerate(stack):
            edge = WARN if order == 0 else MUTED
            axis.add_patch(Polygon([(x - radius, bottom), (x + radius, bottom),
                                    (x + radius, top), (x - radius, top)],
                                   closed=True, facecolor="none", edgecolor=edge,
                                   lw=1.4 if order == 0 else 0.7, zorder=5))
        limit = topple_height(foot, TABLE_FRICTION)
        if limit > JAW_TOP:
            verdict, colour = "pushable at either height", GOOD
        elif pushable(foot, TABLE_FRICTION):
            verdict, colour = f"only if it is pushed at {LOWEST_GRIP:.0f} mm", INK
        else:
            verdict, colour = "must be refused", WARN
        axis.text(x, -16, f"{len(stack)} cylinders, foot {foot:.1f} mm",
                  fontsize=NOTE_SIZE, color=INK, ha="center", va="top")
        axis.text(x, -36, f"topples above {limit:.0f} mm at μ = {TABLE_FRICTION}\n{verdict}",
                  fontsize=NOTE_SIZE, color=colour, ha="center", va="top")
    axis.text(-258, LOWEST_GRIP - 3, f"the middle of the jaw,\n{LOWEST_GRIP:.0f} mm",
              fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top")
    axis.text(-258, JAW_TOP + 4, f"the top edge of the jaw,\n{JAW_TOP:.0f} mm — where a tapered\n"
              "glass really meets it", fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom")
    axis.set_xlim(-262, 3 * step + 112)
    axis.set_ylim(-86, 262)
    axis.set_title("What the working simulator does instead: the glass as stacked cylinders, "
                   "and one friction number",
                   fontsize=LABEL_SIZE, color=INK, pad=8)
    figure.subplots_adjust(bottom=0.03, top=0.90)
    save(figure, "04-the-model-that-was-built.png")


# --------------------------------------------------------------------------- #
# Every number the document quotes.
# --------------------------------------------------------------------------- #
def report() -> None:
    print()
    print("---- the kind, as drawn ----")
    print(f"{SWEPT} tapered glasses, seed {SEED}")
    print(f"  foot        {FEET.min():.1f} to {FEET.max():.1f} mm, median {np.median(FEET):.1f}")
    print(f"  mass        {1000 * MASSES.min():.0f} to {1000 * MASSES.max():.0f} g, "
          f"median {1000 * np.median(MASSES):.0f} g")
    low = MU_LOW * MASSES.min() * GRAVITY
    high = MU_HIGH * MASSES.max() * GRAVITY
    print(f"  push force  {low:.2f} to {high:.2f} N over both μ and the family "
          f"(a factor of {high / low:.1f})")

    print()
    print("---- who may be pushed at all ----")
    for mu in MUS:
        share = 100.0 * np.mean([pushable(b, mu) for b in FEET])
        margins = np.array([push_margin(b, mu) for b in FEET])
        print(f"  μ = {mu}:  {share:.1f} per cent pushable, needs a foot wider than "
              f"{2 * mu * LOWEST_GRIP:.0f} mm; median margin {np.median(margins):+.1f} mm")
    critical = FEET / 2.0 / LOWEST_GRIP
    print(f"  the μ at which each glass becomes unpushable: {critical.min():.2f} to "
          f"{critical.max():.2f}, median {np.median(critical):.2f}")
    for reach in (1.00, 0.80, 0.60):
        at_low = 100.0 * np.mean([(reach * b / 2.0) / MU_LOW > LOWEST_GRIP for b in FEET])
        at_high = 100.0 * np.mean([(reach * b / 2.0) / MU_HIGH > LOWEST_GRIP for b in FEET])
        print(f"  contact out to {reach:.0%} of the foot: {at_low:.1f} per cent at μ={MU_LOW}, "
              f"{at_high:.1f} per cent at μ={MU_HIGH}")

    print()
    print("---- the worked glass ----")
    print(f"  chosen as the middle of the {len(ALLOWED)} glasses that pass the tipping test "
          f"at μ = {MU_HIGH}")
    print(f"  height {WORKED_HEIGHT:.1f} mm, rim {WORKED_RIM:.1f} mm, foot {WORKED_FOOT_WIDTH:.1f} mm, "
          f"mass {1000 * mass_kg(WORKED):.0f} g")
    print(f"  half the foot a = {WORKED_FOOT:.2f} mm; the wall stands {WORKED_WALL:.1f} mm out "
          f"at the push height {LOWEST_GRIP:.0f} mm")
    for mu in (MU_LOW, MU_HIGH):
        print(f"  μ = {mu}: topples above {topple_height(WORKED_FOOT_WIDTH, mu):.1f} mm; "
              f"margin {push_margin(WORKED_FOOT_WIDTH, mu):+.1f} mm; "
              f"tips at the lowest push? {tips(WORKED_FOOT_WIDTH, LOWEST_GRIP, mu)}; "
              f"the load sits {load_centre(mu, LOWEST_GRIP):.1f} mm forward")
    print(f"  the centre of friction is swept out to {BIAS_MAX:.2f} mm off the axis "
          "(a quarter of the foot radius)")
    for contact, label in BASES_MODELLED:
        c = mean_support_radius(contact, WORKED_FOOT, 0.0)
        print(f"  {label.splitlines()[0]:<34s} contact {contact[0]:.2f}–{contact[1]:.2f} of the "
              f"foot radius, c = {c:.2f} mm")
    print(f"  the widest and narrowest c differ by a factor of "
          f"{mean_support_radius(RIM, WORKED_FOOT, 0.0) / mean_support_radius(DOMED, WORKED_FOOT, 0.0):.1f}")
    print(f"  friction cone at the pad: half-angle {np.degrees(np.arctan(GRIP_FACTOR)):.1f}° "
          f"(μ = {GRIP_FACTOR})")
    for mu in (MU_LOW, MU_HIGH):
        shift = load_centre(mu, LOWEST_GRIP)
        needed = GRIP_FACTOR * (shift + WORKED_WALL)
        reachable = float(np.sqrt(max(0.0, WORKED_FOOT**2 - shift**2)))
        print(f"  a unanimous Mason vote at μ={mu} needs the centre of friction {needed:.1f} mm "
              f"off the axis; the foot only reaches {reachable:.1f} mm there "
              f"({'possible' if reachable > needed else 'impossible'})")
    print(f"  the push it is asked to make: {PUSH_TYPICAL} mm typically, {PUSH_LONGEST} mm at "
          "the worst")

    print()
    print("---- the sweep: every prediction for that one glass ----")
    rows = sweep()
    print(f"{'μ':>5} {'contact':>12} {'bias':>6} {'forward':>8} {'sideways':>9} {'turn°':>7} "
          f"{'skid':>6} {'tips':>5}")
    for mu, contact, bias, forward, sideways, turn, skid, tipped, _path in rows:
        reach = f"{contact[0]:.2f}-{contact[1]:.2f}"
        if tipped:
            print(f"{mu:5.2f} {reach:>12} {bias:6.2f} {'—':>8} {'—':>9} {'—':>7} {'':>6} {'TIPS':>5}")
        else:
            print(f"{mu:5.2f} {reach:>12} {bias:6.2f} {forward:8.2f} {sideways:9.2f} "
                  f"{turn:7.2f} {str(skid):>6} {'':>5}")
    standing = [row for row in rows if not row[7]]
    sideways = np.array([row[4] for row in standing])
    print(f"  {len(standing)} of {len(rows)} guesses leave the glass standing")
    print(f"  sideways spread over the whole box: {sideways.min():.2f} to {sideways.max():.2f} mm "
          f"(width {sideways.max() - sideways.min():.2f} mm)")
    print(f"  forward travel: {min(r[3] for r in standing):.3f} to "
          f"{max(r[3] for r in standing):.3f} mm, against a commanded {PUSH_LONGEST} mm")
    worst = max(standing, key=lambda row: abs(row[5]))
    print(f"  largest turn: {worst[5]:.1f}° at μ={worst[0]}, contact {worst[1]}, "
          f"bias {worst[2]:.2f} mm")
    print(f"  any pad skid? {any(row[6] for row in standing)}")
    turned = np.radians(worst[5])
    print(f"  the glass turns towards the push line: the centre of friction's offset from it "
          f"falls from {worst[2]:.2f} mm to {worst[2] * np.cos(turned):.2f} mm over the push")
    for name, width, _colour, count in one_at_a_time(rows):
        print(f"  {name.replace(chr(10), ' '):<62s} {width:5.2f} mm over {count} guesses")
    typical = [float(np.interp(PUSH_TYPICAL, row[8][:, 0], row[8][:, 1])) for row in standing]
    print(f"  by the typical push distance, {PUSH_TYPICAL} mm, the spread is only "
          f"{max(typical) - min(typical):.2f} mm")
    short = [push(WORKED, row[0], row[1], row[2], distance=PUSH_TYPICAL) for row in standing]
    print(f"  largest turn by then: {max(abs(np.degrees(r[2])) for r in short):.2f} degrees")
    print(f"  a look already settles the position to {MEASURED_POSITION} mm, so the prediction is "
          f"{(sideways.max() - sideways.min()) / MEASURED_POSITION:.1f} times wider than the "
          f"measurement at the longest push and "
          f"{(max(typical) - min(typical)) / MEASURED_POSITION:.1f} times at the typical one")

    print()
    print("---- the cast, and what the working simulator makes of it ----")
    for entry, name in zip(CAST, ("sturdy", "tippy", "middling", "short"), strict=True):
        outline = from_cast(entry)
        foot = base_diameter(outline)
        stack = stacked_cylinders(outline)
        print(f"  {name:9s} foot {foot:.1f} mm, {len(stack)} cylinders, bottom one "
              f"{stack[0][0]:.1f}–{stack[0][1]:.1f} mm tall and {2 * stack[0][2]:.1f} mm across; "
              f"topples above {topple_height(foot, TABLE_FRICTION):.1f} mm at μ={TABLE_FRICTION}")
    for entry, name in ((STURDY, "STURDY"), (TIPPY, "TIPPY")):
        foot = base_width(entry[1], entry[2])
        print(f"  {name}: foot {foot:.1f} mm, pushable at μ={MU_LOW}? {pushable(foot, MU_LOW)}; "
              f"at μ={TABLE_FRICTION}? {pushable(foot, TABLE_FRICTION)}; "
              f"at μ={MU_HIGH}? {pushable(foot, MU_HIGH)}")

    print()
    print("---- the jaw's own height, and the room test ----")
    print(f"  the jaw face runs {JAW_TOP - 30.0:.0f} to {JAW_TOP:.0f} mm and is {JAW_WIDTH:.0f} mm "
          f"wide; a tapered glass meets its top edge, so the real push height is {JAW_TOP:.0f} mm")
    for height in (LOWEST_GRIP, JAW_TOP):
        for mu in MUS:
            ok = 100.0 * np.mean([(b / 2.0) / mu > height for b in FEET])
            print(f"    pushed at {height:.0f} mm, μ = {mu}: {ok:.1f} per cent pushable "
                  f"(needs a foot wider than {2 * mu * height:.0f} mm)")
    print(f"  the foot width itself is measured to {MEASURED_WIDTH} mm, one standard deviation, "
          f"which is {MEASURED_WIDTH / 2.0 / TABLE_FRICTION:.1f} mm on the topple height at "
          f"μ = {TABLE_FRICTION}")
    widest, narrowest = FEET.max(), FEET.min()
    for neighbour, label in ((KIND_WIDEST, "the widest tapered glass"),
                             (KIND_NARROWEST, "the narrowest")):
        print(f"  room test against {label} ({neighbour:.0f} mm): the middles have to be "
              f"{GRIP_ROOM + neighbour / 2.0:.1f} mm apart")
    print(f"  a glass {GRIP_ROOM + KIND_WIDEST / 2.0 - 1.0:.1f} mm from the widest neighbour has "
          f"room? {has_room((0.0, 0.0), [(GRIP_ROOM + KIND_WIDEST / 2.0 - 1.0, 0.0, KIND_WIDEST)])}"
          f"; from the narrowest? "
          f"{has_room((0.0, 0.0), [(GRIP_ROOM + KIND_WIDEST / 2.0 - 1.0, 0.0, KIND_NARROWEST)])}")
    print(f"  on {CROWDED_OF[2]} of the project's own tapered tables, {CROWDED_OF[0]} of "
          f"{CROWDED_OF[1]} glasses lack room; the median one has to move {PUSH_TYPICAL} mm and "
          f"the worst {PUSH_LONGEST} mm")
    print(f"  (the 400 drawn for this page run {narrowest:.1f} to {widest:.1f} mm at the foot)")


if __name__ == "__main__":
    picture_the_moment_balance()
    picture_who_can_be_pushed()
    picture_the_cone_and_the_vote()
    picture_the_limit_surface()
    picture_the_spread()
    picture_the_working_model()
    report()
