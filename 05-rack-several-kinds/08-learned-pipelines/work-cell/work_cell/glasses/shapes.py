"""What a glass looks like, as an outline that can be spun into a solid.

A drinking glass is a solid of revolution: take a flat outline of one side and
spin it about a vertical axis. So a glass is fully described by a list of
(height, radius) pairs running from the base up to the rim, and everything else
in the project works from that list.

Nothing here knows the size of any real glass. A shape is a *recipe* with
proportions in it, and a size is drawn per glass, so the same recipe makes a
shot glass and a pint glass. That is deliberate: the arm is never told how big
the glass in front of it is, and the only way to be sure of that is for the
test glasses themselves to vary.

Plain numpy, no ROS, so the whole module can be tested directly.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

from ..arm.dimensions import LOWEST_GRIP
from . import spec
from .rules import MIN_HANG

# How many points the outline is sampled at. Enough that a stem two millimetres
# tall still gets several samples on a 200 mm glass.
SAMPLES = 240

# How thick the solid base of a tumbler is, as a fraction of its height. Real
# ones run from about a twentieth to a tenth; a heavy base is what keeps a tall
# glass from tipping.
TUMBLER_BASE_FRACTION = 0.06

# How many times a glass is redrawn before its range is called wrong. Only a
# kind held at its centre of mass is ever redrawn, and about one in four
# straight glasses is kept, so this is never reached by bad luck alone.
DRAW_ATTEMPTS = 200

# How far above the top of the stem the inside of the bowl starts, as a
# fraction of the height. The bottom of a bowl is solid where it meets the stem.
BOWL_FLOOR_FRACTION = 0.03


@dataclass(frozen=True)
class Outline:
    """One side of a glass, from the base up to the rim.

    ``height`` and ``radius`` are matching arrays in metres. ``height[0]`` is
    always 0, which is where the glass meets the table.

    ``floor`` is the height of the inside bottom: everything below it is solid
    glass. It is what makes one end closed and the other open, so a glass
    turned over can be seen to be upside down.
    """

    height: np.ndarray
    radius: np.ndarray
    floor: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "height", np.asarray(self.height, dtype=float))
        object.__setattr__(self, "radius", np.asarray(self.radius, dtype=float))

    @property
    def total_height(self) -> float:
        return float(self.height[-1])

    @property
    def max_diameter(self) -> float:
        return float(2.0 * self.radius.max())

    def diameter_at(self, height: float) -> float:
        """The width of the glass at one height, interpolated between samples."""
        return float(2.0 * np.interp(height, self.height, self.radius))


def straight(height: float, rim_diameter: float, taper: float = 0.04) -> Outline:
    """A tube. A rocks glass, a pint glass, a shot glass.

    ``taper`` is how much narrower the base is than the rim, as a fraction. Real
    straight glasses are never perfectly parallel — they have to stack and come
    out of a mould — and a perfectly parallel one would let a grip rule pass
    that has no business passing.
    """
    h = np.linspace(0.0, height, SAMPLES)
    rim = rim_diameter / 2.0
    base = rim * (1.0 - taper)
    return Outline(h, base + (rim - base) * (h / height), floor=TUMBLER_BASE_FRACTION * height)


def tapered(height: float, rim_diameter: float, base_fraction: float = 0.45) -> Outline:
    """A cone. A milkshake glass.

    Much narrower at the bottom than the top, which is what makes flat fingers
    slide up the wall as they close, and why the grip has to go low.
    """
    h = np.linspace(0.0, height, SAMPLES)
    rim = rim_diameter / 2.0
    base = rim * base_fraction
    return Outline(h, base + (rim - base) * (h / height), floor=TUMBLER_BASE_FRACTION * height)


def stemmed(
    height: float,
    bowl_diameter: float,
    stem_diameter: float,
    foot_fraction: float = 0.82,
    stem_fraction: float = 0.42,
) -> Outline:
    """A bowl on a stem on a foot. A wine glass, a champagne flute.

    ``stem_fraction`` is how far up the glass the stem ends, as a fraction of
    the total height. ``foot_fraction`` is how wide the foot is as a fraction
    of the bowl.

    The foot is measured against the bowl rather than given its own size on
    purpose. Drawn independently it can come out wider than the bowl, which no
    wine glass is, and which quietly breaks every rule that looks for the
    narrowest part *below the widest* — on such a glass the widest part is the
    foot, and there is nothing below it.
    """
    foot_diameter = bowl_diameter * foot_fraction
    h = np.linspace(0.0, height, SAMPLES)
    foot_top = 0.05 * height
    stem_top = stem_fraction * height

    foot = foot_diameter / 2.0
    stem = stem_diameter / 2.0
    bowl = bowl_diameter / 2.0

    radius = np.empty_like(h)
    for index, y in enumerate(h):
        if y <= foot_top:
            # The foot flares out at the very bottom.
            radius[index] = stem + (foot - stem) * (1.0 - y / foot_top) ** 2
        elif y <= stem_top:
            radius[index] = stem
        else:
            # The bowl opens out from the stem. A square root rather than a
            # straight line, so the widest part is near the rim rather than at
            # it, which is what a real bowl does.
            fraction = (y - stem_top) / (height - stem_top)
            radius[index] = stem + (bowl - stem) * math.sqrt(fraction)
    return Outline(h, radius, floor=(stem_fraction + BOWL_FLOOR_FRACTION) * height)


def short_stemmed(height: float, bowl_diameter: float, stem_diameter: float) -> Outline:
    """A stemmed glass with a short, thick stem. An Irish coffee glass."""
    return stemmed(height, bowl_diameter, stem_diameter, foot_fraction=0.75, stem_fraction=0.22)


# Each kind, and the range every proportion is drawn from. These ranges are the
# only sizes anywhere in the project, they describe the *test glasses* rather
# than any glass the arm is told about, and they are deliberately wide: a rule
# that only works in the middle of the range is not a rule.
KIND_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "straight_glass": {
        # A tall shot glass up to a tall highball. Nothing shorter, because it
        # has to fit over a rack peg upside down; see PEG_HEIGHT. In practice
        # the short end is redrawn: see reachable().
        "height": (0.065, 0.170),
        "rim_diameter": (0.045, 0.090),
        "taper": (0.02, 0.10),
    },
    "tapered_glass": {
        # The widest range of any kind, from a tapered shot glass up to a large
        # tapered glass, and deliberately so. A tall glass's outline is thrown
        # outwards when seen from above, and the taller it is the further out it
        # goes, so a range this wide is what lets one glass cover a shorter one
        # completely in an overhead picture. That is the headline difficulty of
        # problem 2, and with a narrow range it cannot happen at all.
        #
        # The short end is as low as the rest of the cell allows: below this a
        # glass no longer clears a rack peg when it is stood mouth down, and the
        # gripper can no longer close on it where the rule says. Those two are
        # what set it, not the perception problem.
        "height": (0.090, 0.230),
        "rim_diameter": (0.065, 0.105),
        "base_fraction": (0.38, 0.58),
    },
    "stemmed_glass": {
        # A mid-sized wine glass up to a large one. The smallest wine glasses
        # are left out: their bowl narrows so soon that a rack peg reaches the
        # narrow part; see PEG_HEIGHT.
        "height": (0.165, 0.230),
        "bowl_diameter": (0.060, 0.100),
        "stem_diameter": (0.006, 0.014),
        # As a fraction of the bowl, and always under 1: see stemmed().
        "foot_fraction": (0.70, 0.95),
        "stem_fraction": (0.34, 0.52),
    },
    "short_stemmed_glass": {
        "height": (0.110, 0.165),
        "bowl_diameter": (0.060, 0.085),
        "stem_diameter": (0.011, 0.020),
    },
}

_BUILDERS = {
    "straight_glass": straight,
    "tapered_glass": tapered,
    "stemmed_glass": stemmed,
    "short_stemmed_glass": short_stemmed,
}


def build(kind: str, **proportions: float) -> Outline:
    """Make one outline of ``kind`` from explicit proportions."""
    if kind not in _BUILDERS:
        raise ValueError(f"no such kind of glass: {kind}")
    return _BUILDERS[kind](**proportions)


def draw(kind: str, rng: random.Random) -> tuple[Outline, dict[str, float]]:
    """Draw one glass of ``kind`` at a random size from its range.

    A glass the gripper could not hold where its rule says is drawn again;
    see reachable().

    Returns the outline and the proportions it was drawn with, because a
    failure is only worth reporting if the glass that caused it can be made
    again.
    """
    for _ in range(DRAW_ATTEMPTS):
        chosen = {name: rng.uniform(low, high) for name, (low, high) in KIND_RANGES[kind].items()}
        outline = build(kind, **chosen)
        if reachable(kind, outline):
            return outline, chosen
    raise RuntimeError(
        f"no {kind} in {DRAW_ATTEMPTS} draws had its centre of mass above where the "
        f"fingers can reach; its range in KIND_RANGES wants raising"
    )


def reachable(kind: str, outline: Outline) -> bool:
    """Whether the fingers can be put below this glass's centre of mass.

    Only asked of a kind whose rule holds it there. Below LOWEST_GRIP the
    gripper body is through the table. A short tumbler has its centre lower
    than the fingers can go, so it could only be held above it, and upside
    down it would balance on the pads and fall. Such a glass is not put on
    the table.
    """
    rules = spec.kind(kind)
    if rules.grip_rule != spec.JUST_BELOW_CENTRE_OF_MASS:
        return True
    centre = centre_height(outline, rules.wall_thickness_m)
    lowest = max(LOWEST_GRIP, rules.band_for(outline.total_height)[0])
    return lowest + rules.min_band_height_m / 2.0 + MIN_HANG <= centre


def centre_height(outline: Outline, wall: float) -> float:
    """How high the centre of mass of a glass is: the solid, less the hollow."""
    moments = []
    for height, radius in ((outline.height, outline.radius), hollow(outline, wall)):
        area = np.pi * radius**2
        moments.append((np.trapezoid(area, height), np.trapezoid(area * height, height)))
    (volume, first), (empty, empty_first) = moments
    return float((first - empty_first) / (volume - empty))


def hollow(outline: Outline, wall: float) -> tuple[np.ndarray, np.ndarray]:
    """The inside of a glass: heights and radii from its floor up to the rim.

    The inside wall is the outside moved in by the wall thickness. Below the
    floor there is no inside at all, which is the solid base or stem.
    """
    above = outline.height > outline.floor
    at_floor = np.interp(outline.floor, outline.height, outline.radius)
    height = np.concatenate(([outline.floor], outline.height[above]))
    radius = np.concatenate(([at_floor], outline.radius[above]))
    return height, np.maximum(radius - wall, 0.0)


def family(kind: str, count: int, seed: int = 0) -> list[tuple[Outline, dict[str, float]]]:
    """A spread of ``count`` glasses of one kind, across the whole range.

    This is what a new kind is tested against. One glass proves nothing, because
    a rule tuned to one glass looks exactly like a rule until the second glass
    arrives. The spread is deterministic for a given seed so that a gate that
    fails can be investigated.
    """
    rng = random.Random(seed)
    return [draw(kind, rng) for _ in range(count)]
