"""Shared look and shared arithmetic for the problem-3 diagrams.

One module so that eleven separately written scripts produce pictures that sit
beside each other without looking like eleven different documents. Import it,
call ``new``/``save``, and use the colour names rather than literals.

    from diagram_style import GLASS, GOOD, INK, MUTED, WARN, bare, new, save

Every script in this folder writes into ``images/problem-3/`` and is run from
the project root:

    pixi run python images/generators/problem-3/make_01_images.py

The second half of this module is the arithmetic problem 3 turns on: whether a
pushed glass slides or tips, how much clear room a gripper needs round a glass,
and which pairs on a table are too close to grip. It lives here rather than in
each script because eleven documents disagreeing about when a glass topples
would be worse than eleven documents that look different.

Nothing here is a glass measurement. The sizes below are the *kind's* declared
range, taken from ``glasses/shapes.py``, which is a rule about what may be
drawn and not a fact about any one glass.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

IMAGES = Path(__file__).resolve().parents[3] / "images" / "problem-3"

# The palette the rest of the project's diagrams use.
INK = "#22272e"      # text, and anything structural
MUTED = "#8b949e"    # captions, and things in the background
GLASS = "#4c8fd6"    # the object being reasoned about
WARN = "#d9694b"     # the failure, the thing going wrong
GOOD = "#5aa469"     # the fix, the thing going right
PAPER = "#ffffff"

TITLE_SIZE = 12
LABEL_SIZE = 9
NOTE_SIZE = 8.4


# --------------------------------------------------------------------------- #
# The cell, in millimetres. Every one of these is read from the project's own
# source rather than written down again here; the file it came from is named so
# that a reader can check it.
# --------------------------------------------------------------------------- #

GRIPPER_MAX_OPENING = 95.0   # arm/dimensions.py
LOWEST_GRIP = 50.0           # arm/dimensions.py: below this the gripper body is through the table
PAD_HEIGHT = 14.0            # arm/dimensions.py

# The height a glass is really pushed at, which is NOT LOWEST_GRIP.
#
# The middle of the jaw rides at LOWEST_GRIP, but the jaw is 30 mm tall, so its
# top edge is 15 mm higher. A glass that is wider higher up — which every
# tapered glass is, by definition — meets that top edge first, and that is
# where the push lands. problem-3-sim/bench.py says so in as many words:
# "A glass that is wider higher up meets the jaw here first, so this, not
# PUSH_HEIGHT, is how high it is pushed."
#
# Fifteen millimetres sounds like a detail and is not. Pushing a tapered glass
# at 65 mm rather than 50 mm takes the share that can be pushed at all from
# 92% to 52% at mu = 0.3, and from 14% to nothing whatever at mu = 0.5.
FINGER_HEIGHT = 30.0         # problem-3-sim/bench.py
JAW_TOP = LOWEST_GRIP + FINGER_HEIGHT / 2.0   # 65 mm
MIN_SEPARATION = 150.0       # glasses/spawn.py: guaranteed between centres when problem 2 ended

# How much clear room the open jaw needs round a glass's middle before it can
# close on it. Problem 3's own statement rounds this to "about 70 mm in every
# direction"; it is kept as one number here so that eleven documents quote the
# same one.
GRIP_ROOM = 70.0
TOUCHING_APART = 75.0                    # rims in contact, for the widest pair

# The symmetric worst case: two of the widest glasses of the kind. Useful as a
# single conservative number, but it is NOT the test the code uses. The real
# test is ``has_room`` below, and it is asymmetric.
GRIPPABLE_APART = 2.0 * GRIP_ROOM        # 140 mm between middles

# What the simulator actually uses for friction between glass and table.
# problem-3-sim/bench.py TABLE_FRICTION. The arm is not told this number: it is
# the ground truth a run is scored against, not an input to any decision. That
# distinction is the whole of solution 9, and every document that quotes a
# friction figure has to say which of the two it means.
TABLE_FRICTION = 0.35

# Where the glasses may stand, and where the arm is bolted down.
# rack/layout.py GLASS_ZONE and table/layout.py ROBOT_BASE.
GLASS_ZONE = (320.0, 640.0, -440.0, -80.0)   # x from, x to, y from, y to
ROBOT_BASE = (0.0, 0.0)
COMFORTABLE_REACH = (300.0, 780.0)           # arm/dimensions.py
RACK_AREA = (320.0, 380.0, 340.0, 380.0)     # rack/layout.py, on the arm's other side

# The tapered kind's declared range, from glasses/shapes.py KIND_RANGES.
# base_fraction is the base diameter as a fraction of the rim, which is what
# decides whether a glass slides or tips.
KIND_TALLEST = 230.0
KIND_SHORTEST = 90.0
KIND_WIDEST = 105.0
KIND_NARROWEST = 65.0
BASE_FRACTION = (0.38, 0.58)

# The cast these diagrams draw, as (height, rim, base_fraction) in millimetres.
# A wide-footed glass that pushes easily, a narrow-footed tall one that does
# not, and two in between. All four are inside the range above, so none of them
# is a special case invented to make a picture work.
STURDY = (150.0, 100.0, 0.58)     # base 58 mm: slides even on a grippy table
TIPPY = (225.0, 70.0, 0.38)       # base 27 mm: tips before the gripper can reach low enough
MIDDLING = (180.0, 90.0, 0.48)    # base 43 mm
SHORT_ONE = (95.0, 68.0, 0.50)    # base 34 mm
CAST = (STURDY, TIPPY, MIDDLING, SHORT_ONE)

# Friction between glass and table. Nothing in this cell measures it, which is
# the point: the arithmetic below is only as good as a guessed number, and
# every document that uses it has to say so. This pair brackets the range
# usually quoted for glass on a dry surface.
MU_LOW = 0.3
MU_HIGH = 0.5


def base_width(rim: float, base_fraction: float) -> float:
    """The diameter of the foot a glass actually stands on."""
    return rim * base_fraction


def topple_height(base: float, mu: float) -> float:
    """The height above the table at which a push stops sliding and starts tipping.

    Pushing at height h on an object whose base is ``base`` across, standing on
    a table it rubs against with friction ``mu``, the object slides while
    h < a / mu, where a is half the base. At and above that height the moment
    about the leading edge of the foot wins and it goes over.

    This is the one piece of arithmetic every solution in problem 3 shares, and
    it takes a guessed ``mu``, so the answer is a limit rather than a promise.
    """
    if base <= 0.0:
        raise ValueError("a glass has to stand on something")
    return (base / 2.0) / mu


def tips(base: float, push_height: float, mu: float) -> bool:
    """Whether a push at this height on this glass tips it over instead of sliding it."""
    return push_height >= topple_height(base, mu)


def pushable(base: float, mu: float, lowest: float = LOWEST_GRIP) -> bool:
    """Whether this glass can be pushed at all by this gripper.

    The gripper cannot get below ``lowest`` without its own body going through
    the table, so a glass whose topple height is below that has no safe place
    to be pushed. The right answer for it is to refuse, not to try gently.
    """
    return topple_height(base, mu) > lowest


def push_margin(base: float, mu: float, lowest: float = LOWEST_GRIP) -> float:
    """How many millimetres of room there are between the lowest push and the topple.

    Negative means the glass cannot be pushed safely at all. Small and positive
    means it can, but only if the arm's height control is better than the
    margin, which is worth saying out loud in a document.
    """
    return topple_height(base, mu) - lowest


def has_room(point, others) -> bool:
    """Whether a glass at ``point`` can be gripped: no other glass's edge inside GRIP_ROOM.

    ``others`` is (x, y, widest width) for every other glass on the table, in
    millimetres. This is the project's own test, copied from
    ``problem-3-sim/bench.py``, and it is the one to use.

    It is **not symmetric**. The room a glass needs depends on how wide its
    neighbour is, not on how wide it is, so a narrow glass beside a wide one is
    crowded while the wide one beside it is not. A symmetric centre-to-centre
    threshold gets that backwards, and gets the count wrong.
    """
    return all(
        float(np.hypot(point[0] - ox, point[1] - oy)) >= GRIP_ROOM + width / 2.0
        for ox, oy, width in others
    )


def grippable(a, b, width_b: float = KIND_WIDEST) -> bool:
    """Whether a glass at ``a`` has room, given one neighbour at ``b`` of width ``width_b``.

    A two-glass shorthand for ``has_room``. The default neighbour is the widest
    the kind allows, which makes the answer the conservative one; pass the real
    width when it is known.
    """
    return has_room(a, [(b[0], b[1], width_b)])


def crowded_pairs(positions) -> list[tuple[int, int]]:
    """Every pair on the table that is too close for the gripper, as index pairs."""
    out = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            if not grippable(positions[i], positions[j]):
                out.append((i, j))
    return out


def room_around(positions, index) -> float:
    """How much clear room a glass has: the distance to its nearest neighbour.

    Returned in millimetres between centres, so compare it against
    ``GRIPPABLE_APART`` rather than against ``GRIP_ROOM``.
    """
    here = positions[index]
    others = [p for k, p in enumerate(positions) if k != index]
    if not others:
        return float("inf")
    return min(float(np.hypot(here[0] - p[0], here[1] - p[1])) for p in others)


def in_zone(point, margin: float = 0.0) -> bool:
    """Whether a destination is inside the table the glasses are allowed to be on."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    return (x_from + margin <= point[0] <= x_to - margin
            and y_from + margin <= point[1] <= y_to - margin)


def in_reach(point) -> bool:
    """Whether the arm can comfortably stand over a point on the table."""
    low, high = COMFORTABLE_REACH
    return low <= float(np.hypot(point[0] - ROBOT_BASE[0], point[1] - ROBOT_BASE[1])) <= high


def destination_ok(point, others, margin: float = 0.0) -> bool:
    """Whether a glass could be pushed to ``point`` and be better off there.

    Clear of every other glass by the gripper's own requirement, inside the
    zone, and inside the arm's reach. Moving one glass out of a crowd and into
    a different crowd is the mistake this is here to prevent.
    """
    if not in_zone(point, margin) or not in_reach(point):
        return False
    return all(grippable(point, other) for other in others)


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #

def new(width: float, height: float, columns: int = 1):
    """A figure with a white background, and one or more bare panels."""
    figure, axes = plt.subplots(1, columns, figsize=(width, height))
    figure.patch.set_facecolor(PAPER)
    for axis in (axes if columns > 1 else [axes]):
        axis.set_facecolor(PAPER)
    return figure, axes


def bare(axis) -> None:
    """No ticks, no frame. Most of these pictures are drawings, not plots."""
    axis.set_xticks([])
    axis.set_yticks([])
    for side in axis.spines.values():
        side.set_visible(False)


def save(figure, name: str) -> Path:
    """Write into images/problem-3/ and say where it went."""
    IMAGES.mkdir(parents=True, exist_ok=True)
    path = IMAGES / name
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor=PAPER)
    plt.close(figure)
    print(f"wrote images/problem-3/{name}")
    return path


def glass_from_above(axis, centre, rim, base_fraction=0.48, colour=None, alpha=0.30,
                     edge=None, lw=1.0, zorder=3, foot=True):
    """One standing glass seen from straight above: its rim, and the foot it stands on.

    Drawing both matters here. Problem 3 reasons about the foot, because that
    is what decides tipping, and about the rim, because that is what the
    gripper has to get round. They are not the same circle and a picture that
    shows only one of them hides the whole difficulty.
    """
    from matplotlib.patches import Circle as _Circle
    colour = colour or GLASS
    axis.add_patch(_Circle(tuple(centre), rim / 2.0, facecolor=colour, alpha=alpha,
                           edgecolor=edge or colour, lw=lw, zorder=zorder))
    if foot:
        axis.add_patch(_Circle(tuple(centre), base_width(rim, base_fraction) / 2.0,
                               facecolor="none", edgecolor=edge or colour,
                               lw=lw, ls=(0, (3, 2)), alpha=0.9, zorder=zorder + 1))


def glass_from_the_side(axis, x, height, rim, base_fraction=0.48, colour=None,
                        alpha=0.30, edge=None, lw=1.0, zorder=3):
    """One standing glass seen level, as the tapered outline it really is.

    A tapered glass is a trapezium from the side, narrower at the foot, and
    that narrowness is the reason it tips. Drawing it as a rectangle would draw
    away the problem.
    """
    from matplotlib.patches import Polygon as _Polygon
    colour = colour or GLASS
    half_rim, half_base = rim / 2.0, base_width(rim, base_fraction) / 2.0
    points = [(x - half_base, 0.0), (x + half_base, 0.0),
              (x + half_rim, height), (x - half_rim, height)]
    axis.add_patch(_Polygon(points, closed=True, facecolor=colour, alpha=alpha,
                            edgecolor=edge or colour, lw=lw, zorder=zorder))
    return points


def grip_ring(axis, centre, colour=None, lw=1.2, zorder=2, alpha=0.75):
    """The room the open jaw needs round a glass before it can close on it.

    Two of these overlapping is what "too close to grip" means, and it is worth
    drawing rather than asserting, because it is a great deal bigger than the
    glass.
    """
    from matplotlib.patches import Circle as _Circle
    axis.add_patch(_Circle(tuple(centre), GRIP_ROOM, facecolor="none",
                           edgecolor=colour or MUTED, lw=lw, ls=(0, (4, 3)),
                           alpha=alpha, zorder=zorder))


def push_arrow(axis, start, end, colour=None, lw=1.6, zorder=6, shrink=0.0):
    """The push itself: where the finger meets the glass and which way it goes."""
    colour = colour or INK
    axis.annotate("", xy=tuple(end), xytext=tuple(start), zorder=zorder,
                  arrowprops=dict(arrowstyle="-|>", color=colour, lw=lw,
                                  shrinkA=shrink, shrinkB=shrink))
