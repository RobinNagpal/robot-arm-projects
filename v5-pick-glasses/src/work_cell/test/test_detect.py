import numpy as np
import pytest
from work_cell.glasses.detect import classify, find_glasses, glass_mask
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.shapes import family, short_stemmed, stemmed, straight, tapered


def profile_of(outline):
    return profile_from_outline(outline)


# ------------------------------------------------------------- the mask


def test_a_hole_in_the_depth_picture_over_something_lit_is_glass():
    rgb = np.full((20, 20, 3), 120, dtype=np.uint8)
    depth = np.full((20, 20), 1.2)
    depth[5:15, 5:15] = np.nan  # the camera saw straight through
    mask = glass_mask(rgb, depth)
    assert mask[10, 10]
    assert not mask[1, 1]


def test_a_hole_over_darkness_is_the_far_wall_rather_than_a_glass():
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    depth = np.full((20, 20), np.nan)
    assert not glass_mask(rgb, depth).any()


def test_zero_depth_counts_as_missing_because_that_is_how_it_is_reported():
    rgb = np.full((10, 10, 3), 200, dtype=np.uint8)
    depth = np.zeros((10, 10))
    assert glass_mask(rgb, depth).all()


def test_mismatched_pictures_are_refused():
    with pytest.raises(ValueError):
        glass_mask(np.zeros((10, 10, 3), np.uint8), np.zeros((8, 8)))


# --------------------------------------------------------- finding blobs


def test_two_separate_blobs_are_two_glasses():
    mask = np.zeros((60, 60), dtype=bool)
    mask[5:25, 5:25] = True
    mask[35:55, 35:55] = True
    found = find_glasses(mask, lambda c, r, z: (c / 100, r / 100, z), table_z=0.75, min_pixels=50)
    assert len(found) == 2


def test_a_speck_is_not_a_glass():
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:13, 10:13] = True
    assert find_glasses(mask, lambda c, r, z: (c, r, z), table_z=0.75, min_pixels=50) == []


def test_a_detection_lands_where_the_blob_is():
    mask = np.zeros((60, 60), dtype=bool)
    mask[20:40, 20:40] = True
    found = find_glasses(mask, lambda c, r, z: (c, r, z), table_z=0.75, min_pixels=50)
    assert found[0].position[0] == pytest.approx(29.5)
    assert found[0].position[2] == pytest.approx(0.75)


def test_the_footprint_is_measured_on_the_table_not_in_pixels():
    """A blob 20 pixels across, at a hundred pixels to the metre, is 200 mm.

    The width has to come out of the projection, because the same blob seen
    from twice as high covers half as many pixels and is still the same glass.
    """
    mask = np.zeros((60, 60), dtype=bool)
    mask[20:40, 20:40] = True
    found = find_glasses(mask, lambda c, r, z: (c / 100, r / 100, z), table_z=0.75, min_pixels=50)
    assert found[0].rough_width == pytest.approx(0.20, abs=0.005)


# ------------------------------------------------------- deciding the kind


def test_a_tube_is_a_straight_glass():
    assert classify(profile_of(straight(height=0.090, rim_diameter=0.080))) == "straight_glass"


def test_a_cone_is_a_tapered_glass():
    assert classify(profile_of(tapered(height=0.175, rim_diameter=0.090))) == "tapered_glass"


def test_a_bowl_on_a_long_stem_is_a_stemmed_glass():
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009)
    assert classify(profile_of(outline)) == "stemmed_glass"


def test_a_bowl_on_a_short_stem_is_a_short_stemmed_glass():
    outline = short_stemmed(height=0.150, bowl_diameter=0.070, stem_diameter=0.015)
    assert classify(profile_of(outline)) == "short_stemmed_glass"


def test_a_stemmed_glass_is_not_mistaken_for_a_tapered_one():
    # Its bowl slopes, so the order the tests are applied in matters: look for
    # a stem before asking whether the wall leans.
    for outline, _ in family("stemmed_glass", 20, seed=8):
        assert classify(profile_of(outline)) in {"stemmed_glass", "short_stemmed_glass"}


@pytest.mark.parametrize(
    "kind_name", ["straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"]
)
def test_every_drawn_glass_gets_a_kind_whose_rule_can_hold_it(kind_name):
    """What the classifier owes the arm is a workable grip, not a matching label.

    It is tempting to require that a glass drawn as tapered comes back as
    tapered. That is the wrong test. A shallow cone has a wall upright enough
    for flat pads, so calling it straight is not a mistake — the straight rule
    grips it perfectly well, and insisting on the label would be testing how
    the glass was generated rather than whether the arm can pick it up.

    So the requirement is the one that matters: whatever kind the profile is
    given, that kind's rule must find somewhere safe to hold it.
    """
    from work_cell.glasses import spec
    from work_cell.glasses.rules import NoGrip, find_grip

    failures = []
    for outline, props in family(kind_name, 40, seed=9):
        profile = profile_of(outline)
        got = classify(profile)
        if got is None:
            failures.append(("no kind", props))
            continue
        try:
            find_grip(profile, spec.kind(got), gripper_max_opening=0.095)
        except NoGrip as why:
            failures.append((f"{got}: {why}", {k: round(v, 4) for k, v in props.items()}))
    assert not failures, f"{len(failures)} of 40 failed, first: {failures[:1]}"


def test_a_clear_cut_shape_gets_the_label_you_would_expect():
    # Where the shape is unambiguous, the classifier should agree with a person.
    assert classify(profile_of(straight(height=0.090, rim_diameter=0.080, taper=0.02))) == (
        "straight_glass"
    )
    assert classify(profile_of(tapered(height=0.140, rim_diameter=0.100, base_fraction=0.40))) == (
        "tapered_glass"
    )


def test_a_shape_no_rule_describes_is_refused_rather_than_forced():
    # A flat disc: no stem, and not tall enough to ask about its wall.
    from work_cell.glasses.profile import Profile

    flat = Profile(np.array([0.0, 0.001, 0.002]), np.array([0.08, 0.08, 0.08]))
    assert classify(flat) is None
