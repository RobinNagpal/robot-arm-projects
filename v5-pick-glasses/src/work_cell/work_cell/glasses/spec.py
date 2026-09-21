"""What the arm is told about glasses in advance.

One rule governs this file, and it is worth stating before anything else:

    This file may hold rules and limits. It may not hold the size of any glass.

"Hold the narrowest part below the bowl" is true of every stemmed glass ever
made. "Hold it 90 mm up" is true of exactly one. The first is a rule and
belongs here; the second is a measurement and is worked out at run time from
what the camera saw.

Every number below is either a fraction of a glass's own height, or a limit
belonging to the gripper. Swap every glass in the building for a different size
and nothing here changes.

No ROS and no numpy, so this can be read and tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

# The three procedures a rule can name. Each one turns a measured profile into
# a height to grip at; they are implemented in rules.py.
LOWEST_VERTICAL_SECTION = "lowest_vertical_section"
NARROWEST_BELOW_WIDEST = "narrowest_below_widest"
FLATTEST_IN_BAND = "flattest_in_band"

# How thick the walls of each kind are, which sets how hard it may be squeezed.
# These are not sizes of a glass: they are a category the force cap is looked up
# from, and they would be the same for a shot glass and a pint glass.
WALL_FORCE_CAP_N = {
    "thin": 6.0,
    "normal": 12.0,
    "thick": 20.0,
}

# Rough wall thickness per category, used only to estimate the weight of a
# glass from its measured outline before it has been lifted and weighed. The
# estimate is wrong by about a third either way, which is fine, because it only
# has to get the first squeeze into the right range.
WALL_THICKNESS_M = {
    "thin": 0.0018,
    "normal": 0.0028,
    "thick": 0.0045,
}


@dataclass(frozen=True)
class Kind:
    """One kind of glass: how to recognise it, and where to hold it."""

    name: str
    grip_rule: str

    # Where in the glass to look for a grip, as fractions of its own height.
    search_band: tuple[float, float]

    # The flat part has to be at least this tall for the pads to sit on it.
    # A gripper property rather than a glass one.
    min_band_height_m: float

    # What the gripper can usefully close on. Outside this, the answer is
    # rejected rather than attempted.
    min_opening_m: float
    max_opening_m: float

    wall: str
    expects_handle: bool = False

    @property
    def force_cap_n(self) -> float:
        return WALL_FORCE_CAP_N[self.wall]

    @property
    def wall_thickness_m(self) -> float:
        return WALL_THICKNESS_M[self.wall]

    def band_for(self, total_height: float) -> tuple[float, float]:
        """Turn the search band into real heights for one measured glass."""
        low, high = self.search_band
        return low * total_height, high * total_height


LIBRARY: dict[str, Kind] = {
    "straight_glass": Kind(
        name="straight_glass",
        grip_rule=LOWEST_VERTICAL_SECTION,
        # The lower half. Rule one of the three: hold the end that becomes the
        # top after the turn, so the fingers end up above the rack rather than
        # among the pegs.
        search_band=(0.05, 0.50),
        min_band_height_m=0.012,
        min_opening_m=0.020,
        max_opening_m=0.095,
        wall="normal",
    ),
    "tapered_glass": Kind(
        name="tapered_glass",
        grip_rule=FLATTEST_IN_BAND,
        # Lower still. The wall slopes everywhere, and it is closest to
        # vertical near the base, so that is the only place worth gripping.
        search_band=(0.05, 0.35),
        min_band_height_m=0.012,
        min_opening_m=0.020,
        max_opening_m=0.095,
        wall="normal",
    ),
    "stemmed_glass": Kind(
        name="stemmed_glass",
        grip_rule=NARROWEST_BELOW_WIDEST,
        search_band=(0.05, 0.60),
        min_band_height_m=0.010,
        # A stem, not a bowl. Anything wider than 40 mm is not a stem, and the
        # rule has found something else.
        min_opening_m=0.004,
        max_opening_m=0.040,
        wall="thin",
    ),
    "short_stemmed_glass": Kind(
        name="short_stemmed_glass",
        grip_rule=NARROWEST_BELOW_WIDEST,
        # A short stem sits lower, so the band stops sooner.
        search_band=(0.04, 0.40),
        min_band_height_m=0.008,
        min_opening_m=0.006,
        max_opening_m=0.045,
        wall="thick",
        expects_handle=True,
    ),
}


def kind(name: str) -> Kind:
    """Look up one kind, or say plainly that it is unknown.

    An unknown kind is not an error to recover from. It means a glass the arm
    has no rule for, and the right response further up is to leave it standing
    and report it.
    """
    try:
        return LIBRARY[name]
    except KeyError:
        raise KeyError(f"no rule for a glass of kind {name!r}") from None
