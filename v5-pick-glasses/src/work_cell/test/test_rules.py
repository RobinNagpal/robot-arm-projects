import pytest
from work_cell.arm.dimensions import LOWEST_GRIP
from work_cell.glasses import spec
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.rules import NoGrip, find_grip
from work_cell.glasses.shapes import (
    centre_height,
    family,
    short_stemmed,
    stemmed,
    straight,
    tapered,
)
from work_cell.glasses.spawn import SpawnedGlass

# What the gripper can do. The real number lives in arm/dimensions.py; the
# tests pass their own so that the rules can be exercised without the arm.
MAX_OPENING = 0.095


def grip_for(outline, kind_name, max_opening=MAX_OPENING):
    return find_grip(
        profile_from_outline(outline), spec.kind(kind_name), gripper_max_opening=max_opening
    )


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
    pint = grip_for(straight(height=0.170, rim_diameter=0.090), "straight_glass")
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
    assert not failures, f"{len(failures)} of 40 failed, first: {failures[:1]}"


def test_a_weighed_straight_glass_is_held_level_with_its_centre_of_mass():
    """The lever that turns a glass in the fingers is the gap between the two.

    Across the family, with the fingers kept off the table, and against the
    true centre of the solid glass rather than the estimate the rule used.
    """
    kind = spec.kind("straight_glass")
    for outline, _ in family("straight_glass", 40, seed=8):
        mass = SpawnedGlass("g", "straight_glass", outline, (0.0, 0.0, 0.0), 0.0).mass
        grip = find_grip(
            profile_from_outline(outline),
            kind,
            gripper_max_opening=MAX_OPENING,
            lowest_grip=LOWEST_GRIP,
            mass=mass,
        )
        centre = centre_height(outline, kind.wall_thickness_m)
        assert grip.height == pytest.approx(centre, abs=0.005)
        assert grip.band[0] >= LOWEST_GRIP


def test_weighing_moves_the_grip_down_and_never_up():
    # The outline alone cannot see the solid base, so its guess is high.
    kind = spec.kind("straight_glass")
    for outline, _ in family("straight_glass", 40, seed=8):
        profile = profile_from_outline(outline)
        mass = SpawnedGlass("g", "straight_glass", outline, (0.0, 0.0, 0.0), 0.0).mass
        before = find_grip(profile, kind, gripper_max_opening=MAX_OPENING, lowest_grip=LOWEST_GRIP)
        after = find_grip(
            profile, kind, gripper_max_opening=MAX_OPENING, lowest_grip=LOWEST_GRIP, mass=mass
        )
        assert after.height <= before.height


def test_the_grip_stays_low_however_tall_the_glass_is():
    # Rule one: what the fingers hold ends up in the air after the turn.
    for outline, _ in family("straight_glass", 25, seed=4):
        grip = grip_for(outline, "straight_glass")
        assert grip.height < 0.5 * outline.total_height


# ------------------------------------------------------------- the refusals


def test_a_glass_wider_than_the_gripper_is_refused():
    outline = straight(height=0.120, rim_diameter=0.090)
    with pytest.raises(NoGrip, match="fingers only open"):
        grip_for(outline, "straight_glass", max_opening=0.040)


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
