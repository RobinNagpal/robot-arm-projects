import pytest
from work_cell.glasses import spec
from work_cell.glasses.shapes import KIND_RANGES


def test_every_kind_the_shapes_module_can_draw_has_a_rule():
    # If these two drift apart, the simulation spawns a glass the arm has no
    # rule for and the run fails for a reason that looks like perception.
    assert set(spec.LIBRARY) == set(KIND_RANGES)


def test_every_rule_names_a_procedure_that_exists():
    known = {
        spec.LOWEST_VERTICAL_SECTION,
        spec.JUST_BELOW_CENTRE_OF_MASS,
        spec.NARROWEST_BELOW_WIDEST,
        spec.FLATTEST_IN_BAND,
    }
    for kind in spec.LIBRARY.values():
        assert kind.grip_rule in known


def test_the_library_holds_no_measurement_of_a_glass():
    """The rule this whole design rests on, enforced rather than trusted.

    Every number in a record is either a fraction of the glass's own height, or
    a limit belonging to the gripper. Anything in between — a height in
    millimetres that describes a glass — would make the record true of one
    glass and wrong for the rest of its kind.
    """
    for kind in spec.LIBRARY.values():
        low, high = kind.search_band
        assert 0.0 <= low < high <= 1.0, f"{kind.name}: search band must be fractions"

        # The gripper's own limits. These are bounded by what a two-finger
        # gripper can do, not by any particular glass.
        assert 0.0 < kind.min_opening_m < kind.max_opening_m <= 0.10
        assert 0.0 < kind.min_band_height_m <= 0.02


def test_the_search_band_is_always_in_the_lower_half():
    # Rule one of the three: hold the end that becomes the top after the turn.
    # A band reaching above halfway would let a rule grip a glass near its rim,
    # and after the turn those fingers are down among the rack pegs.
    for kind in spec.LIBRARY.values():
        assert kind.search_band[0] < 0.5


def test_a_band_becomes_real_heights_for_a_measured_glass():
    straight = spec.kind("straight_glass")
    assert straight.band_for(0.100) == pytest.approx((0.005, 0.050))
    # The same record, a glass twice the size, and the band scales with it.
    assert straight.band_for(0.200) == pytest.approx((0.010, 0.100))


def test_a_stemmed_glass_may_not_be_squeezed_as_hard_as_a_thick_one():
    assert spec.kind("stemmed_glass").force_cap_n < spec.kind("short_stemmed_glass").force_cap_n


def test_every_wall_category_has_both_a_cap_and_a_thickness():
    for kind in spec.LIBRARY.values():
        assert kind.force_cap_n > 0
        assert kind.wall_thickness_m > 0


def test_an_unknown_kind_is_reported_rather_than_guessed_at():
    with pytest.raises(KeyError, match="no rule"):
        spec.kind("teacup")
