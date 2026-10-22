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

The limits that belong to the gripper are imported from it rather than copied
here, so that fitting a different gripper changes them in one place. No ROS, so
this can still be read and tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..arm import robotiq_2f85

# The procedures a rule can name. Each one turns a measured profile into a
# height to grip at; they are implemented in rules.py.
LOWEST_VERTICAL_SECTION = "lowest_vertical_section"
JUST_BELOW_CENTRE_OF_MASS = "just_below_centre_of_mass"
NARROWEST_BELOW_WIDEST = "narrowest_below_widest"
FLATTEST_IN_BAND = "flattest_in_band"

# How thick the walls of each kind are, which sets how hard it may be squeezed.
# These are not sizes of a glass: they are a category the force cap is looked up
# from, and they would be the same for a shot glass and a pint glass.
#
# The level these sit at is set by the gripper, and that is a change worth
# understanding, because it is the clearest example in this project of real
# hardware overruling a number somebody chose.
#
# This file used to cap a thin wall at 6 N, a normal one at 12 and a thick one
# at 20. Those were guesses. Nothing had been measured, and
# implementation-notes.md said so. The Robotiq 2F-85 then made the guesses
# impossible to keep, because **it cannot squeeze more gently than 20 N**. That
# is not a recommended minimum, it is the bottom of the range the gripper
# exposes, so under the old caps this gripper could not legally hold a thin or
# a normal glass at all, and the arm would have refused nearly every glass on
# the table.
#
# So the caps are now written against the gripper's floor instead of against a
# guess. The ordering between the three is kept, because the ordering is the
# part there was a reason for: a thicker wall takes more squeezing than a
# thinner one. What changed is where the scale starts, and it now starts
# somewhere real. A thin wall is allowed the floor and nothing above it, a
# normal wall half again, and a thick wall twice.
#
# This is the first thing to calibrate against real glassware, and until it is
# calibrated it is the least certain number in the project. What makes it
# tolerable in the meantime is that the error is visible rather than hidden:
# glasses/force.py reports how much harder the gripper squeezes than the sums
# ask for, so the size of the gap is in the run's own output.
WALL_FORCE_CAP_N = {
    "thin": 1.0 * robotiq_2f85.MIN_FORCE_N,
    "normal": 1.5 * robotiq_2f85.MIN_FORCE_N,
    "thick": 2.0 * robotiq_2f85.MIN_FORCE_N,
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
    #
    # The figures each kind gives below were chosen against a 14 mm pad, and
    # the 2F-85's pad is 22 mm. So the pads now stand taller than the wall
    # they are guaranteed, and their top and bottom edges can land on wall
    # that is curving away. That is a real gap and it is left open on purpose,
    # because closing it means choosing a new number and there is nothing to
    # choose it from: raising these to match the pad would refuse a great many
    # glasses on the strength of a guess, which is the same mistake the old
    # force caps made. What decides it is how much slope a silicone pad of
    # this size really takes up, which is a measurement to make on a bench and
    # not a sum to do here. See docs/known-gaps.md.
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
        # Held a little below its centre of mass: below, so that upside down
        # it hangs from the pads instead of balancing on them, and only a
        # little, so its weight has a short lever to swing it with. Held at
        # the bottom instead, a tall one swung round between the pads at the
        # force the wall is rated for.
        grip_rule=JUST_BELOW_CENTRE_OF_MASS,
        # The lower half. Rule one of the three: hold the end that becomes the
        # top after the turn, so the fingers end up above the rack rather than
        # among the pegs. The centre of mass of a tumbler is always in it.
        search_band=(0.05, 0.50),
        min_band_height_m=0.012,
        min_opening_m=0.020,
        # As wide as the gripper can hold, which is a little less than how
        # far it opens, because a glass filling the last few millimetres of
        # the stroke would touch the gripper's own body. A tumbler is the one
        # kind that can be too wide to pick up at all, so this is a number
        # about the gripper rather than about glasses, and it is imported so
        # that it cannot fall out of step with the gripper the way it once
        # had: this line said 95 mm, which no gripper in this cell ever did.
        max_opening_m=robotiq_2f85.MAX_GRIP,
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
        max_opening_m=robotiq_2f85.MAX_GRIP,
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
