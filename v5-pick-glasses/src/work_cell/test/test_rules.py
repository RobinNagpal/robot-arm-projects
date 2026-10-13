import pytest
from work_cell.arm.dimensions import GRIPPER_MAX_GRIP, LOWEST_GRIP
from work_cell.glasses import spec
from work_cell.glasses.profile import Profile, profile_from_outline
from work_cell.glasses.rules import BELOW_CENTRE, NoGrip, find_grip
from work_cell.glasses.shapes import (
    centre_height,
    family,
    short_stemmed,
    stemmed,
    straight,
    tapered,
)
from work_cell.glasses.spawn import SpawnedGlass

# What the gripper can do. Taken from the arm rather than chosen here, because
# this is the number that decides which glasses exist as far as the rules are
# concerned, and a test that picked its own would be testing a gripper nobody
# has. It is the widest a glass may be, which on the real gripper is a little
# under how far the fingers part.
MAX_OPENING = GRIPPER_MAX_GRIP


def grip_for(outline, kind_name, max_opening=MAX_OPENING):
    return find_grip(profile_from_outline(outline), spec.kind(kind_name), gripper_max_opening=max_opening)


def holdable(kind_name, count, seed):
    """The drawn glasses of a kind that this gripper could pick up at all.

    ``family()`` draws across the whole plausible range of a kind, and part of
    that range is simply too wide for a Robotiq 2F-85: a straight tumbler is
    as wide at the grip as it is at the rim, and real tumblers run to 90 mm.
    Such a glass is refused, and a refusal is a result rather than a failure,
    so the tests about what a *rule* does are given the glasses the rule can
    be asked about. How many get left out is not swept away with them: it is
    the subject of its own test below.
    """
    for outline, props in family(kind_name, count, seed):
        try:
            grip_for(outline, kind_name)
        except NoGrip as why:
            if "apart" in str(why) or "only open" in str(why):
                continue
        yield outline, props


# ------------------------------------------------- the opening is measured


def test_a_stemmed_glass_is_gripped_on_its_stem():
    grip = grip_for(stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009), "stemmed_glass")
    assert grip.opening == pytest.approx(0.009, abs=6e-4)


def test_two_wine_glasses_of_different_sizes_give_different_openings():
    """The whole argument for measuring rather than looking up.

    Same kind, same rule, same code. Nobody wrote either of these numbers.
    """
    thin = grip_for(stemmed(height=0.230, bowl_diameter=0.070, stem_diameter=0.006), "stemmed_glass")
    thick = grip_for(stemmed(height=0.130, bowl_diameter=0.100, stem_diameter=0.014), "stemmed_glass")
    assert thin.opening == pytest.approx(0.006, abs=6e-4)
    assert thick.opening == pytest.approx(0.014, abs=6e-4)
    assert thick.opening > thin.opening * 2


def test_a_shot_glass_and_a_pint_glass_use_the_same_rule():
    shot = grip_for(straight(height=0.055, rim_diameter=0.045), "straight_glass")
    # 80 mm, because the pint this test used to use was 90 mm and the real
    # gripper cannot hold it. See the test below, which is about exactly that.
    pint = grip_for(straight(height=0.170, rim_diameter=0.080), "straight_glass")
    assert shot.opening < pint.opening
    # Both gripped low, as a fraction of their own height.
    for grip, outline in ((shot, 0.055), (pint, 0.170)):
        assert grip.height < 0.5 * outline


def test_a_tapered_glass_is_gripped_far_below_its_rim_width():
    outline = tapered(height=0.175, rim_diameter=0.090, base_fraction=0.45)
    grip = grip_for(outline, "tapered_glass")
    # The grip is near the bottom, where the glass is much narrower than the rim.
    assert grip.opening < 0.070
    assert grip.height < 0.35 * 0.175


def test_a_short_stemmed_glass_is_gripped_on_its_short_stem():
    outline = short_stemmed(height=0.150, bowl_diameter=0.070, stem_diameter=0.015)
    grip = grip_for(outline, "short_stemmed_glass")
    assert grip.opening == pytest.approx(0.015, abs=8e-4)
    assert grip.height < 0.4 * 0.150


# ------------------------------------------------------- across a whole family


@pytest.mark.parametrize(
    "kind_name", ["straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"]
)
def test_the_rule_works_on_forty_glasses_of_its_kind(kind_name):
    """A rule that only works in the middle of the size range is not a rule."""
    kind = spec.kind(kind_name)
    failures = []
    for outline, props in family(kind_name, 40, seed=2):
        try:
            grip = grip_for(outline, kind_name)
        except NoGrip as why:
            failures.append((props, str(why)))
            continue
        assert kind.min_opening_m <= grip.opening <= kind.max_opening_m
        assert grip.height < 0.5 * outline.total_height
    # A glass too wide for the fingers is refused by the gripper, not by the
    # rule, so it is not evidence against the rule. Anything else is.
    rule_failures = [f for f in failures if "apart" not in f[1] and "only open" not in f[1]]
    assert not rule_failures, f"{len(rule_failures)} of 40 failed, first: {rule_failures[:1]}"


def _weighed(outline):
    return SpawnedGlass("g", "straight_glass", outline, (0.0, 0.0, 0.0), 0.0).mass


def _straight_grip(profile, mass=None):
    return find_grip(
        profile,
        spec.kind("straight_glass"),
        gripper_max_opening=MAX_OPENING,
        lowest_grip=LOWEST_GRIP,
        mass=mass,
    )


def test_a_weighed_straight_glass_is_held_just_below_its_centre_of_mass():
    """Below, so upside down it hangs from the pads rather than balancing on them.

    Across the family, and against the true centre of the solid glass rather
    than the estimate the rule used.
    """
    kind = spec.kind("straight_glass")
    for outline, _ in holdable("straight_glass", 40, seed=8):
        grip = _straight_grip(profile_from_outline(outline), _weighed(outline))
        centre = centre_height(outline, kind.wall_thickness_m)
        assert grip.height < centre
        # Only just: the gap is the lever the weight swings on.
        assert grip.height > centre - BELOW_CENTRE - 0.005
        assert grip.band[0] >= LOWEST_GRIP


def test_the_grip_stays_below_the_centre_with_the_errors_the_camera_makes():
    # Seen from a little above, the far edge of the rim makes a glass read up
    # to 10 mm too tall, and the wrist sensor has read 5% light. Both push the
    # estimate up, which is the dangerous way.
    kind = spec.kind("straight_glass")
    for outline, _ in holdable("straight_glass", 40, seed=9):
        exact = profile_from_outline(outline)
        stretch = (exact.total_height + 0.010) / exact.total_height
        seen = Profile(exact.height * stretch, exact.width)
        grip = _straight_grip(seen, 0.95 * _weighed(outline))
        assert grip.height < centre_height(outline, kind.wall_thickness_m)


def test_a_glass_that_can_only_be_held_above_its_centre_is_refused():
    # 130 mm tall: the fingers cannot go below 50 mm, and its centre of mass
    # is lower than that. Upside down it would balance on the pads.
    outline = straight(height=0.130, rim_diameter=0.070)
    with pytest.raises(NoGrip, match="balance on the pads"):
        _straight_grip(profile_from_outline(outline), _weighed(outline))


def test_weighing_moves_the_grip_down_and_never_up():
    # The outline alone cannot see the solid base, so its guess is high.
    for outline, _ in holdable("straight_glass", 40, seed=8):
        profile = profile_from_outline(outline)
        before = _straight_grip(profile)
        after = _straight_grip(profile, _weighed(outline))
        assert after.height <= before.height


def test_the_grip_stays_low_however_tall_the_glass_is():
    # Rule one: what the fingers hold ends up in the air after the turn.
    for outline, _ in holdable("straight_glass", 25, seed=4):
        grip = grip_for(outline, "straight_glass")
        assert grip.height < 0.5 * outline.total_height


# ------------------------------------------------------------- the refusals


def test_a_glass_wider_than_the_gripper_is_refused():
    # 70 mm is a width a tumbler is allowed to be, so the kind lets it past and
    # it is the gripper that turns it down. Offering something wider than the
    # kind allows would be refused a step earlier and would not test this.
    outline = straight(height=0.120, rim_diameter=0.070)
    with pytest.raises(NoGrip, match="fingers only open"):
        grip_for(outline, "straight_glass", max_opening=0.040)


def test_some_real_tumblers_are_too_wide_for_this_gripper():
    """The clearest price of fitting a real gripper, stated rather than hidden.

    A Robotiq 2F-85 parts its fingers 85 mm and can hold about 80. A straight
    tumbler is no narrower at the grip than at its rim, and real ones run past
    that, so some of them simply cannot be picked up. The arm leaves them
    standing and says why, which is the right answer and not a fault.

    The count is checked loosely from both sides. If it ever became zero the
    drawn family would have stopped covering real sizes; if it ever became most
    of them, something would have gone wrong with the gripper's numbers.
    """
    too_wide = 0
    for outline, _ in family("straight_glass", 40, seed=2):
        try:
            grip_for(outline, "straight_glass")
        except NoGrip as why:
            assert "apart" in str(why) or "only open" in str(why), why
            too_wide += 1
    assert 1 <= too_wide <= 12, f"{too_wide} of 40 straight glasses are too wide"


def test_a_straight_glass_offered_to_the_stem_rule_is_refused():
    # There is no stem to find, and the rule says so rather than inventing one.
    outline = straight(height=0.090, rim_diameter=0.080)
    with pytest.raises(NoGrip, match="no stem"):
        grip_for(outline, "stemmed_glass")


def test_a_tapered_glass_offered_to_the_upright_rule_is_refused():
    # Its wall slopes everywhere, so there is no upright section to sit on.
    outline = tapered(height=0.175, rim_diameter=0.090, base_fraction=0.45)
    with pytest.raises(NoGrip, match="no upright wall"):
        grip_for(outline, "straight_glass")


def test_the_reason_for_a_refusal_is_always_worth_reading():
    outline = straight(height=0.090, rim_diameter=0.080)
    with pytest.raises(NoGrip) as caught:
        grip_for(outline, "stemmed_glass")
    # It names the kind, so a log line says which rule wants widening.
    assert "stemmed_glass" in str(caught.value)
