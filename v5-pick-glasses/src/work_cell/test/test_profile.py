import numpy as np
import pytest
from work_cell.glasses.profile import Profile, profile_from_outline
from work_cell.glasses.shapes import short_stemmed, stemmed, straight, tapered


def profile_of(outline):
    return profile_from_outline(outline)


def test_the_basics_come_straight_off_the_outline():
    p = profile_of(straight(height=0.090, rim_diameter=0.080, taper=0.05))
    assert p.total_height == pytest.approx(0.090)
    assert p.rim_width == pytest.approx(0.080)
    assert p.base_width == pytest.approx(0.076)
    assert p.max_width == pytest.approx(0.080)


def test_a_profile_needs_matching_arrays():
    with pytest.raises(ValueError):
        Profile(np.linspace(0, 1, 5), np.linspace(0, 1, 4))


# --------------------------------------------------------------- the waist


def test_a_stemmed_glass_has_a_waist_and_it_is_the_stem():
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009, foot_diameter=0.070)
    p = profile_of(outline)
    waist = p.waist_at()
    assert waist is not None
    assert p.width_at(waist) == pytest.approx(0.009, abs=5e-4)
    # It is below the bowl and above the foot.
    assert 0.02 < waist < 0.5 * p.total_height


def test_a_straight_glass_has_no_waist():
    # Its narrowest point is the very bottom, which is the wall ending rather
    # than a stem. This is how the two families are told apart.
    p = profile_of(straight(height=0.090, rim_diameter=0.080))
    assert p.waist_at() is None


def test_a_tapered_glass_has_no_waist_either():
    p = profile_of(tapered(height=0.175, rim_diameter=0.090))
    assert p.waist_at() is None


def test_the_waist_is_found_whatever_the_proportions():
    # A tall thin-stemmed glass and a squat thick-stemmed one, same rule.
    tall = profile_of(
        stemmed(height=0.230, bowl_diameter=0.070, stem_diameter=0.006, foot_diameter=0.060)
    )
    squat = profile_of(
        stemmed(height=0.130, bowl_diameter=0.100, stem_diameter=0.014, foot_diameter=0.085)
    )
    for p, expected in ((tall, 0.006), (squat, 0.014)):
        waist = p.waist_at()
        assert waist is not None
        assert p.width_at(waist) == pytest.approx(expected, abs=6e-4)


def test_a_short_stemmed_glass_has_a_waist_low_down():
    p = profile_of(short_stemmed(height=0.150, bowl_diameter=0.070, stem_diameter=0.015))
    waist = p.waist_at()
    assert waist is not None
    assert waist < 0.3 * p.total_height


# ------------------------------------------------------------ vertical bands


def test_a_straight_glass_is_vertical_nearly_all_the_way_up():
    p = profile_of(straight(height=0.090, rim_diameter=0.080, taper=0.02))
    bands = p.vertical_bands()
    assert bands, "a near-parallel wall should give at least one band"
    assert max(b.height for b in bands) > 0.5 * p.total_height


def test_a_tapered_glass_has_no_vertical_band_at_all():
    # The whole wall slopes, which is exactly why it needs a different rule.
    p = profile_of(tapered(height=0.175, rim_diameter=0.090, base_fraction=0.45))
    assert p.vertical_bands() == []


def test_bands_can_be_restricted_to_part_of_the_glass():
    p = profile_of(straight(height=0.120, rim_diameter=0.070, taper=0.02))
    bands = p.vertical_bands(within=(0.0, 0.040))
    assert bands
    assert all(b.top <= 0.040 + 1e-9 for b in bands)


# ------------------------------------------------------------ flattest band


def test_the_flattest_band_of_a_cone_is_at_the_bottom():
    # A cone's wall leans the same everywhere, but the curve of the profile
    # near the base is flattest, and that is where a cone should be gripped.
    p = profile_of(tapered(height=0.175, rim_diameter=0.090, base_fraction=0.45))
    band = p.flattest_band(within=(0.0, 0.10), height=0.012)
    assert band is not None
    assert band.height == pytest.approx(0.012)
    assert band.bottom < 0.05


def test_no_band_is_returned_when_the_search_range_is_too_short():
    p = profile_of(straight(height=0.090, rim_diameter=0.080))
    assert p.flattest_band(within=(0.02, 0.025), height=0.012) is None
