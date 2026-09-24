import pytest
from work_cell.glasses import spec
from work_cell.glasses.force import (
    CONTACT_FORCE_N,
    TooHeavyToHold,
    estimate_centre_height,
    estimate_mass,
    force_for_measured_mass,
    holding_force,
    is_slipping,
    mass_from_wrist,
    required_force,
    starting_force,
)
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.shapes import centre_height, family, stemmed, straight
from work_cell.glasses.spawn import SpawnedGlass


def profile_of(outline):
    return profile_from_outline(outline)


# ------------------------------------------------------------ the estimate


def test_a_drinking_glass_estimates_to_something_a_kitchen_scale_would_agree_with():
    # A rocks glass really does weigh somewhere around 200 to 300 g. The
    # estimate is allowed to be poor, but it may not be absurd, because it sets
    # the first squeeze.
    mass = estimate_mass(profile_of(straight(height=0.090, rim_diameter=0.080)), spec.kind("straight_glass"))
    assert 0.10 < mass < 0.40


def test_a_wine_glass_estimates_lighter_than_a_rocks_glass():
    wine = estimate_mass(
        profile_of(stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009)),
        spec.kind("stemmed_glass"),
    )
    rocks = estimate_mass(profile_of(straight(height=0.090, rim_diameter=0.080)), spec.kind("straight_glass"))
    assert wine < rocks


def test_a_bigger_glass_of_the_same_kind_estimates_heavier():
    kind = spec.kind("straight_glass")
    small = estimate_mass(profile_of(straight(height=0.060, rim_diameter=0.050)), kind)
    large = estimate_mass(profile_of(straight(height=0.170, rim_diameter=0.090)), kind)
    assert large > small * 2


# --------------------------------------------------------------- the sum


def test_the_force_sum_matches_the_worked_example():
    # 250 g: 2.45 N of weight, x2 safety, over 2 pads x 0.6 grip = 4.1 N.
    assert required_force(0.250) == pytest.approx(4.085, abs=0.01)


def test_force_scales_with_weight():
    assert required_force(0.500) == pytest.approx(2 * required_force(0.250))


def test_a_negative_mass_is_refused():
    with pytest.raises(ValueError):
        required_force(-0.1)


# ---------------------------------------------------------------- the cap


def test_a_heavy_thin_walled_glass_is_refused_rather_than_crushed():
    # A kilogram on a thin-walled stem is not something to squeeze harder at.
    with pytest.raises(TooHeavyToHold, match="rated to"):
        force_for_measured_mass(1.0, spec.kind("stemmed_glass"))


def test_a_glass_inside_its_rating_gives_back_the_force_to_use():
    force = force_for_measured_mass(0.180, spec.kind("stemmed_glass"))
    assert force == pytest.approx(required_force(0.180))
    assert force <= spec.kind("stemmed_glass").force_cap_n


def test_the_refusal_says_what_it_weighed_and_what_the_rating_is():
    with pytest.raises(TooHeavyToHold) as caught:
        force_for_measured_mass(1.0, spec.kind("stemmed_glass"))
    message = str(caught.value)
    assert "1000 g" in message and "thin" in message


def test_the_starting_force_never_exceeds_the_cap():
    # The estimate can overshoot, and it must not be allowed to crack a glass
    # before the weighing step has had a chance to correct it.
    for kind_name in spec.LIBRARY:
        kind = spec.kind(kind_name)
        for outline, _ in family(kind_name, 20, seed=6):
            assert starting_force(profile_of(outline), kind) <= kind.force_cap_n


def test_the_starting_force_is_enough_to_lift_the_glass_it_was_estimated_from():
    # It only has to be in the right range, but it has to be in the right range.
    for kind_name in spec.LIBRARY:
        kind = spec.kind(kind_name)
        for outline, _ in family(kind_name, 20, seed=7):
            p = profile_of(outline)
            assert starting_force(p, kind) > CONTACT_FORCE_N


# ------------------------------------------------------------ the weighing


def test_the_wrist_reading_has_the_gripper_taken_off_it():
    # 12 N total, 9.5 N of that is the gripper, so 2.5 N is the glass.
    assert mass_from_wrist(12.0, 9.5) == pytest.approx(2.5 / 9.81, abs=1e-4)


def test_a_reading_lighter_than_the_gripper_means_nothing_is_held():
    assert mass_from_wrist(9.0, 9.5) == 0.0


# ---------------------------------------------------------------- slipping


def test_fingers_that_have_crept_closed_mean_the_glass_is_sliding():
    assert is_slipping(0.0120, 0.0110)


def test_fingers_that_have_not_moved_are_not_slipping():
    assert not is_slipping(0.0120, 0.0120)
    # A tenth of a millimetre is sensor noise, not a slipping glass.
    assert not is_slipping(0.0120, 0.0119)


def test_a_weighed_glass_is_held_at_its_walls_rating():
    # The weight sum stops it sliding down, not turning in the fingers.
    for name in ("straight_glass", "stemmed_glass"):
        kind = spec.kind(name)
        assert holding_force(0.150, kind) == pytest.approx(kind.force_cap_n)
        assert holding_force(0.150, kind) >= force_for_measured_mass(0.150, kind)


def test_a_glass_too_heavy_for_its_rating_is_still_refused():
    with pytest.raises(TooHeavyToHold):
        holding_force(1.0, spec.kind("stemmed_glass"))


def _weighed(outline):
    return SpawnedGlass("g", "straight_glass", outline, (0.0, 0.0, 0.0), 0.0).mass


def test_the_centre_of_mass_from_the_outline_alone_reads_high():
    # The camera cannot see the solid base, so the shell guess puts the weight
    # too far up. Never lower than the truth, which is what weighing corrects.
    kind = spec.kind("straight_glass")
    for outline, _ in family("straight_glass", 40, seed=7):
        guess = estimate_centre_height(profile_from_outline(outline), kind)
        assert guess >= centre_height(outline, kind.wall_thickness_m)


def test_weighing_puts_the_centre_of_mass_within_a_few_millimetres():
    kind = spec.kind("straight_glass")
    for outline, _ in family("straight_glass", 40, seed=7):
        weighed = estimate_centre_height(profile_from_outline(outline), kind, _weighed(outline))
        assert weighed == pytest.approx(centre_height(outline, kind.wall_thickness_m), abs=0.005)
