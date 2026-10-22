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

from ..arm import robotiq_2f85
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

# The smallest push the wrist sensor can be trusted to notice, which is how
# the arm knows the pads have reached the glass. Robotiq recommend 1 N as the
# smallest contact worth acting on with the FT 300-S, and the sensor's own
# noise is about a tenth of that.
#
# This used to be a force the fingers were *commanded* with, to take up the
# slack gently before the real squeeze. A real gripper cannot do that, because
# the 2F-85's gentlest setting is 20 N, so there is no such thing as closing on
# a glass at one newton. Contact is therefore something the arm *detects*
# rather than something it applies: the fingers close under position control
# until the sensor sees this much, and only then is a force commanded at all.
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


def commanded_force(newtons: float) -> float:
    """What the gripper will actually be set to, given what the sums asked for.

    The sums above work in single newtons, because that is genuinely all it
    takes to hold a drinking glass between two silicone pads. The gripper does
    not have single newtons. The 2F-85's adjustable range starts at 20 N, so
    anything gentler than that is simply not a setting it has, and asking for
    it would mean asking for something and getting something else.

    So the force is raised to the floor and the fact is not hidden. It is the
    single biggest difference between what this project computes and what the
    hardware does, and ``over_squeeze()`` is how the size of it gets reported.
    """
    return max(newtons, robotiq_2f85.MIN_FORCE_N)


def over_squeeze(newtons: float) -> float:
    """How many times harder the gripper squeezes than the sums asked for.

    One means the gripper did exactly what was wanted. Seven means a glass
    that needed about three newtons was held with twenty, because twenty is
    the gentlest this gripper has. Reported rather than buried, because a
    number nobody prints is a number nobody checks, and this is the one most
    worth checking against real glass.
    """
    if newtons <= 0:
        return 1.0
    return commanded_force(newtons) / newtons


def starting_force(profile: Profile, kind: Kind) -> float:
    """What to squeeze with before the glass has been weighed.

    Capped, because an overshooting estimate must not be allowed to crack a
    glass before the weighing step has had a chance to correct it, and raised
    to what the gripper can actually be set to.
    """
    wanted = min(required_force(estimate_mass(profile, kind)), kind.force_cap_n)
    return commanded_force(wanted)


def force_for_measured_mass(mass: float, kind: Kind) -> float:
    """The force to hold a glass that has now been weighed properly.

    Raises TooHeavyToHold if that force is past what the walls are rated for.

    The force checked against the cap is the one the gripper will really be
    set to, not the one the sum asked for. That distinction is the whole point
    of using a real gripper: a glass needing 3 N is going to be squeezed at
    20 N whatever the sum says, so 20 N is what has to be safe for it. Testing
    the ideal force against the cap would pass glasses the hardware then
    squeezes far harder.
    """
    needed = commanded_force(required_force(mass))
    if needed > kind.force_cap_n:
        raise TooHeavyToHold(
            f"holding {mass * 1000:.0f} g means squeezing at {needed:.1f} N per pad, and a "
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
