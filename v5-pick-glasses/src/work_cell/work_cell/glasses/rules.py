"""Where to close the fingers on a glass nobody measured.

This is the heart of the project. The arm has a measured Profile and the name
of a kind; it needs a height to grip at and how far to open the fingers. It
gets both by applying the kind's rule to the profile.

The finger opening is never looked up. It is the width the camera measured at
the height the rule chose, which is why a 7 mm stem and a 14 mm stem both work
without anybody writing either number down.

Three rules cover the four kinds:

- ``lowest_vertical_section`` — the lowest run of wall that is upright enough
  for two flat pads. A straight glass.
- ``narrowest_below_widest`` — the stem. A stemmed glass.
- ``flattest_in_band`` — for a cone, which has no upright section anywhere and
  still has a best place to grip.

Every answer is then checked, and a rule that returns something silly on an odd
glass is rejected rather than attempted. Leaving a glass standing is a much
better outcome than picking it up badly.

Plain numpy, no ROS, so the whole module can be tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from .profile import Profile
from .spec import FLATTEST_IN_BAND, LOWEST_VERTICAL_SECTION, NARROWEST_BELOW_WIDEST, Kind


@dataclass(frozen=True)
class Grip:
    """Where to hold one glass, worked out from its measured profile."""

    height: float
    """How far up the glass the fingers close, in metres from the table."""

    opening: float
    """How far apart the fingers are when they touch, in metres."""

    band: tuple[float, float]
    """The run of wall the pads will sit on. Used to check they fit."""

    @property
    def band_height(self) -> float:
        return self.band[1] - self.band[0]


class NoGrip(Exception):
    """No safe place to hold this glass was found.

    Carries the reason, because the reason is what a person needs in order to
    decide whether a rule wants widening or the glass is simply wrong for this
    gripper.
    """


def find_grip(
    profile: Profile, kind: Kind, *, gripper_max_opening: float, lowest_grip: float = 0.0
) -> Grip:
    """Work out where to hold a glass, and check the answer before returning it.

    Raises NoGrip with a reason if the rule cannot find somewhere safe.
    """
    band = _apply_rule(profile, kind, lowest_grip)
    height = (band[0] + band[1]) / 2.0
    opening = profile.width_at(height)
    grip = Grip(height=height, opening=opening, band=band)
    _check(grip, profile, kind, gripper_max_opening, lowest_grip)
    return grip


# ----------------------------------------------------------------- the rules


def _apply_rule(profile: Profile, kind: Kind, lowest_grip: float) -> tuple[float, float]:
    """Run the kind's rule, and return the run of wall to grip.

    The band the rule searches starts no lower than ``lowest_grip``. The floor
    belongs here rather than only in the check at the end: every one of these
    rules looks for the *lowest* wall that will do, so a floor applied
    afterwards would turn "hold it a little higher" into "this glass cannot be
    held", on every glass.
    """
    within = kind.band_for(profile.total_height)
    within = (max(within[0], lowest_grip), within[1])
    if within[0] >= within[1]:
        raise NoGrip(
            f"the gripper cannot reach below {lowest_grip * 1000:.0f} mm without the table, "
            f"and this glass has nothing to hold above that and below "
            f"{within[1] * 1000:.0f} mm"
        )

    if kind.grip_rule == LOWEST_VERTICAL_SECTION:
        return _lowest_vertical_section(profile, kind, within)
    if kind.grip_rule == NARROWEST_BELOW_WIDEST:
        return _narrowest_below_widest(profile, kind, within)
    if kind.grip_rule == FLATTEST_IN_BAND:
        return _flattest_in_band(profile, kind, within)
    raise NoGrip(f"{kind.name} names a grip rule that does not exist: {kind.grip_rule}")


def _lowest_vertical_section(
    profile: Profile, kind: Kind, within: tuple[float, float]
) -> tuple[float, float]:
    """The lowest tall-enough run of upright wall inside the band.

    Lowest rather than best, because rule one beats rule three: the grip wants
    to be near the base so the fingers finish above the rack after the turn.
    """
    bands = [b for b in profile.vertical_bands(within=within) if b.height >= kind.min_band_height_m]
    if not bands:
        raise NoGrip(
            f"no upright wall at least {kind.min_band_height_m * 1000:.0f} mm tall "
            f"in the lower part of this {kind.name}"
        )
    lowest = bands[0]
    # Only the bottom of the run is used, so that a tall straight glass is
    # still gripped low rather than in the middle of a very long band.
    return lowest.bottom, min(lowest.bottom + kind.min_band_height_m, lowest.top)


def _narrowest_below_widest(
    profile: Profile, kind: Kind, within: tuple[float, float]
) -> tuple[float, float]:
    """The stem: the narrowest part below the widest part."""
    waist = profile.waist_at()
    if waist is None:
        raise NoGrip(f"no stem found on this {kind.name}; it may not be stemmed at all")

    low, high = within
    if not low <= waist <= high:
        raise NoGrip(
            f"the stem of this {kind.name} is {waist * 1000:.0f} mm up, outside the "
            f"{low * 1000:.0f} to {high * 1000:.0f} mm band the rule looks in"
        )

    half = kind.min_band_height_m / 2.0
    return waist - half, waist + half


def _flattest_in_band(
    profile: Profile, kind: Kind, within: tuple[float, float]
) -> tuple[float, float]:
    """The least sloping run of wall, for a glass with no upright part at all."""
    band = profile.flattest_band(within=within, height=kind.min_band_height_m)
    if band is None:
        raise NoGrip(
            f"the band this {kind.name} is gripped in is shorter than the "
            f"{kind.min_band_height_m * 1000:.0f} mm the pads need"
        )
    return band.bottom, band.top


# ---------------------------------------------------------------- the checks


def _check(
    grip: Grip, profile: Profile, kind: Kind, gripper_max_opening: float, lowest_grip: float
) -> None:
    """Reject an answer that is real arithmetic but a bad idea.

    A rule can return something silly on an odd glass — a waist found in a
    reflection, a stem on a glass far too wide for the gripper — and every one
    of these is cheaper to catch here than with the arm already moving.
    """
    if not kind.min_opening_m <= grip.opening <= kind.max_opening_m:
        raise NoGrip(
            f"the rule wants the fingers {grip.opening * 1000:.0f} mm apart, outside the "
            f"{kind.min_opening_m * 1000:.0f} to {kind.max_opening_m * 1000:.0f} mm "
            f"a {kind.name} should ever need"
        )

    if grip.opening > gripper_max_opening:
        raise NoGrip(
            f"the fingers only open to {gripper_max_opening * 1000:.0f} mm and this glass "
            f"is {grip.opening * 1000:.0f} mm across where the rule wants to hold it"
        )

    if grip.band_height < kind.min_band_height_m - 1e-9:
        raise NoGrip(
            f"the pads need {kind.min_band_height_m * 1000:.0f} mm of wall and this grip "
            f"has {grip.band_height * 1000:.0f} mm"
        )

    # The gripper comes in level, so its body lies across the grip height. Held
    # too low and the body is through the table before the fingers ever reach
    # the glass, which the planner reports as a move it cannot make rather than
    # as a grip it should not have been given.
    if grip.height < lowest_grip:
        raise NoGrip(
            f"the rule wants to hold it {grip.height * 1000:.0f} mm up, and the gripper "
            f"body will not clear the table below {lowest_grip * 1000:.0f} mm"
        )

    # Rule one, enforced rather than assumed. After the turn the fingers are
    # wherever they were, upside down, and a grip above halfway puts them
    # inside the rack.
    if grip.height > 0.5 * profile.total_height:
        raise NoGrip(
            f"the grip is {grip.height * 1000:.0f} mm up a "
            f"{profile.total_height * 1000:.0f} mm glass, which is too high to invert"
        )
