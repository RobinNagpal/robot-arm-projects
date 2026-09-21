import numpy as np
import pytest
from work_cell.glasses.shapes import KIND_RANGES, build, family, straight, stemmed, tapered


def test_an_outline_starts_at_the_table_and_ends_at_the_rim():
    outline = straight(height=0.090, rim_diameter=0.080)
    assert outline.height[0] == pytest.approx(0.0)
    assert outline.total_height == pytest.approx(0.090)


def test_a_straight_glass_is_slightly_narrower_at_the_bottom():
    outline = straight(height=0.090, rim_diameter=0.080, taper=0.05)
    assert outline.diameter_at(0.090) == pytest.approx(0.080)
    assert outline.diameter_at(0.0) == pytest.approx(0.080 * 0.95)


def test_a_tapered_glass_is_much_narrower_at_the_bottom():
    outline = tapered(height=0.175, rim_diameter=0.090, base_fraction=0.45)
    assert outline.diameter_at(0.0) == pytest.approx(0.090 * 0.45)
    # The whole wall slopes, so no two heights share a diameter.
    assert outline.diameter_at(0.02) < outline.diameter_at(0.10)


def test_a_stemmed_glass_has_a_waist_between_a_wide_bowl_and_a_wide_foot():
    outline = stemmed(
        height=0.200, bowl_diameter=0.085, stem_diameter=0.009, foot_diameter=0.070
    )
    narrowest = float(outline.radius.min()) * 2
    assert narrowest == pytest.approx(0.009, abs=1e-4)
    # The foot and the bowl are both wider than the stem.
    assert outline.diameter_at(0.0) > narrowest
    assert outline.diameter_at(0.200) > narrowest


def test_the_widest_point_of_a_stemmed_glass_is_in_the_bowl():
    outline = stemmed(
        height=0.200, bowl_diameter=0.085, stem_diameter=0.009, foot_diameter=0.070
    )
    widest_at = float(outline.height[int(np.argmax(outline.radius))])
    assert widest_at > 0.5 * outline.total_height


def test_every_kind_can_be_built_from_the_middle_of_its_range():
    for kind, ranges in KIND_RANGES.items():
        middle = {name: (low + high) / 2 for name, (low, high) in ranges.items()}
        outline = build(kind, **middle)
        assert outline.total_height > 0
        assert float(outline.radius.min()) > 0


def test_a_family_spreads_across_the_range_and_repeats_for_a_seed():
    first = family("stemmed_glass", 20, seed=3)
    again = family("stemmed_glass", 20, seed=3)
    heights = [outline.total_height for outline, _ in first]

    assert [o.total_height for o, _ in again] == heights
    low, high = KIND_RANGES["stemmed_glass"]["height"]
    # Twenty draws should not all land in the middle third.
    assert min(heights) < low + (high - low) / 3
    assert max(heights) > high - (high - low) / 3


def test_an_unknown_kind_is_refused_rather_than_guessed_at():
    with pytest.raises(ValueError):
        build("teacup", height=0.08)
