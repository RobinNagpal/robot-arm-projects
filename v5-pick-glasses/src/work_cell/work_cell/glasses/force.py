"""How hard to squeeze a glass whose weight nobody knows.

A glass held between two pads is not resting on anything. It hangs there, and
the only thing stopping it sliding down is friction. Press harder and there is
more friction; press too hard and the glass cracks. The right force is the
smallest one safely above sliding.

The force needed depends on the weight, and the arm does not know the weight,
because it does not know the size. So it works in two stages:

1. **Estimate.** Spin the measured outline to get the glass's volume, treat it
   as a shell of a thickness that comes from the kind, and multiply by the
   density of glass. That is wrong by about a third either way — wall thickness
   varies more than anything else about a glass — and it does not need to be
   better, because it only has to get the first squeeze into the right range.

2. **Measure.** Lift the glass ten millimetres and read the wrist force. That
   is the true weight, and it arrives while the glass is still a centimetre
   above the table, which is the last moment a mistake is free.

Every kind also has a force cap. A glass that turns out to need more than its
cap is one the arm cannot safely hold — heavy, with thin walls — and the right
answer is to put it down and say so, not to squeeze harder and hope.

Plain numpy, no ROS, so the whole module can be tested directly.
"""

from __future__ import annotations

import numpy as np

from .profile import Profile
from .spec import Kind

# Soda-lime glass.
GLASS_DENSITY = 2500.0  # kg/m^3

GRAVITY = 9.81

# How grippy a silicone pad is against dry glass. Measure your own; this is a
# reasonable place to start and the single number most worth checking against
# a real pad, because every force below scales with it.
GRIP_FACTOR = 0.6

# Squeeze this much harder than the sum says, to cover a knock on the way.
SAFETY_FACTOR = 2.0

# The gentlest squeeze that will still register as contact on the way in. Used
# for taking up the slack before the real force is applied.
CONTACT_FORCE_N = 1.0


class TooHeavyToHold(Exception):
    """This glass needs more force than its walls are rated for."""


def estimate_mass(profile: Profile, kind: Kind) -> float:
    """Guess what a measured glass weighs, in kilograms.

    A glass is a shell, not a solid, so the volume that matters is the wall:
    the surface swept by the outline, times how thick it is. The base is added
    as a disc, because it is solid and on a short glass it is a good fraction
    of the weight.
    """
    thickness = kind.wall_thickness_m
    radius = profile.width / 2.0

    # Lateral surface of a solid of revolution, integrated up the glass.
    lateral = float(np.trapezoid(2.0 * np.pi * radius, profile.height))
    base = float(np.pi * radius[0] ** 2)

    return (lateral + base) * thickness * GLASS_DENSITY


def estimate_centre_height(profile: Profile, kind: Kind, mass: float | None = None) -> float:
    """Guess how high up a measured glass its centre of mass is, in metres.

    The same shell as estimate_mass(): the wall, and the base as a disc. That
    alone comes out high, by up to 13 mm on a tall tumbler, because the base of
    a real glass is solid and far heavier than a disc one wall thick, and the
    camera cannot see how thick it is.

    Weighing settles it. Once ``mass`` is known, whatever the glass weighs
    beyond the shell is taken to be in the base and put at the bottom. That
    brings the estimate to within a few millimetres, and it asks nothing of
    the glass but its outline and its weight.
    """
    thickness = kind.wall_thickness_m
    radius = profile.width / 2.0

    lateral = float(np.trapezoid(2.0 * np.pi * radius, profile.height))
    lateral_moment = float(np.trapezoid(2.0 * np.pi * radius * profile.height, profile.height))
    base = float(np.pi * radius[0] ** 2)

    shell = (lateral + base) * thickness * GLASS_DENSITY
    moment = (lateral_moment + base * thickness / 2.0) * thickness * GLASS_DENSITY
    # A glass that weighs less than its shell has thinner walls than the kind
    # says, which moves the centre very little; only extra weight is placed.
    return moment / max(shell, mass or 0.0)


def required_force(mass: float, *, grip_factor: float = GRIP_FACTOR) -> float:
    """The force each pad must press with to hold a glass of this weight.

        force = (weight x safety factor) / (2 x grip factor)

    The 2 is there because two pads each do half the holding.
    """
    if mass < 0:
        raise ValueError("mass cannot be negative")
    weight = mass * GRAVITY
    return weight * SAFETY_FACTOR / (2.0 * grip_factor)


def starting_force(profile: Profile, kind: Kind) -> float:
    """What to squeeze with before the glass has been weighed.

    Capped, because an overshooting estimate must not be allowed to crack a
    glass before the weighing step has had a chance to correct it.
    """
    return min(required_force(estimate_mass(profile, kind)), kind.force_cap_n)


def force_for_measured_mass(mass: float, kind: Kind) -> float:
    """The force to hold a glass that has now been weighed properly.

    Raises TooHeavyToHold if that force is past what the walls are rated for.
    """
    needed = required_force(mass)
    if needed > kind.force_cap_n:
        raise TooHeavyToHold(
            f"holding {mass * 1000:.0f} g needs {needed:.1f} N per pad, and a "
            f"{kind.wall}-walled {kind.name} is only rated to {kind.force_cap_n:.1f} N"
        )
    return needed


def holding_force(mass: float, kind: Kind) -> float:
    """What to hold a weighed glass with while it is turned over and carried.

    The wall's rating, not the weight sum. The sum is enough to stop the glass
    sliding down between the pads. It is not enough to stop it turning about
    the line between them, which is the other way a held glass moves: the
    pads meet a round glass along a short upright line, so they resist that
    turn only a few millimetres either side of it. Turned over and carried, a
    glass whose centre of mass is a centimetre off that line swung round in
    the fingers at the weight sum, and did not at the rating.

    The rating is the most the wall is safe at, so squeezing at it is safe by
    definition. Raises TooHeavyToHold, as the weight sum does, if even that
    will not carry the glass.
    """
    force_for_measured_mass(mass, kind)
    return kind.force_cap_n


def mass_from_wrist(total_newtons: float, gripper_newtons: float) -> float:
    """Turn a wrist force reading into the weight of what is being held."""
    return max(0.0, (total_newtons - gripper_newtons) / GRAVITY)


def is_slipping(width_at_grasp: float, width_now: float, *, tolerance: float = 0.0005) -> bool:
    """Whether the fingers have crept closed since the glass was gripped.

    Creeping means the glass is sliding down through the pads. Checked during a
    slow twenty-degree tilt, because slipping is recoverable at twenty degrees
    and is not at a hundred and eighty.
    """
    return (width_at_grasp - width_now) > tolerance
