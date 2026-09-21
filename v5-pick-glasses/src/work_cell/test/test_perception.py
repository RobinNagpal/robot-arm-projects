"""Perception is tested by drawing a mask from a known glass and measuring it.

Drawing the mask ourselves is the point: the true size is known exactly, so a
test can assert that the measurement comes back right rather than merely
plausible. A real run gets its mask from a segmentation model instead.
"""

import numpy as np
import pytest
from work_cell.glasses.perception import (
    Intrinsics,
    NotMeasurable,
    handle_direction,
    profile_from_mask,
    raggedness,
    row_widths,
    smooth,
)
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.shapes import stemmed, straight, tapered

CAMERA = Intrinsics(fx=600.0, fy=600.0, cx=320.0, cy=240.0)
DISTANCE = 0.30


def draw_mask(outline, intrinsics=CAMERA, distance=DISTANCE, size=(480, 640), hollow=False):
    """Render a glass outline as the silhouette a side-on camera would see."""
    rows, columns = size
    mask = np.zeros(size, dtype=bool)
    metres_across = distance / intrinsics.fx
    metres_up = distance / intrinsics.fy

    base_row = rows - 40
    centre_column = columns // 2
    for row in range(rows):
        height = (base_row - row) * metres_up
        if height < 0 or height > outline.total_height:
            continue
        half = outline.diameter_at(height) / 2.0 / metres_across
        left = int(round(centre_column - half))
        right = int(round(centre_column + half))
        mask[row, left : right + 1] = True
        if hollow and right - left > 6:
            # A transparent glass segments with holes: the model sees the table
            # through the middle of it.
            mask[row, left + 3 : right - 2] = False
    return mask


# ------------------------------------------------------------- row widths


def test_a_row_is_measured_edge_to_edge_not_by_counting_pixels():
    # A hollow silhouette has to measure the same as a solid one, because a
    # transparent object always segments with holes in the middle.
    outline = straight(height=0.090, rim_diameter=0.080)
    solid = row_widths(draw_mask(outline))[1]
    hollow = row_widths(draw_mask(outline, hollow=True))[1]
    assert hollow == pytest.approx(solid)


def test_an_almost_empty_mask_is_refused():
    with pytest.raises(NotMeasurable):
        row_widths(np.zeros((480, 640), dtype=bool))


# ----------------------------------------------------------- the smoothing


def test_smoothing_keeps_a_step_rather_than_ramping_it():
    # The rules look for the step where a stem becomes a bowl, so a filter that
    # smears it would take away the thing being measured.
    widths = np.array([10.0] * 10 + [40.0] * 10)
    smoothed = smooth(widths, window=5)
    assert smoothed[:8] == pytest.approx(10.0)
    assert smoothed[12:] == pytest.approx(40.0)


def test_smoothing_removes_a_single_wandering_pixel():
    widths = np.array([20.0, 20.0, 27.0, 20.0, 20.0, 20.0, 20.0])
    assert smooth(widths, window=5) == pytest.approx(20.0)


def test_raggedness_separates_a_clean_outline_from_a_noisy_one():
    clean = np.linspace(40.0, 44.0, 200)
    noisy = clean + np.tile([0.0, 3.0], 100)
    assert raggedness(clean) < raggedness(noisy) / 5


# ------------------------------------------------------ the whole measurement


@pytest.mark.parametrize(
    "outline",
    [
        straight(height=0.090, rim_diameter=0.080),
        straight(height=0.160, rim_diameter=0.055),
        tapered(height=0.175, rim_diameter=0.090),
        stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.012),
    ],
    ids=["squat-straight", "tall-straight", "tapered", "stemmed"],
)
def test_a_drawn_glass_measures_back_to_the_size_it_was_drawn(outline):
    measured = profile_from_mask(draw_mask(outline), CAMERA, DISTANCE)
    # Within a pixel or so, which at this range is about half a millimetre.
    assert measured.total_height == pytest.approx(outline.total_height, abs=0.002)
    assert measured.max_width == pytest.approx(outline.max_diameter, abs=0.002)


def test_a_measured_stemmed_glass_still_has_its_stem_found():
    # The real test of the chain: draw a glass, measure it through a camera,
    # and the feature finder must still see the stem in the result.
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.012)
    measured = profile_from_mask(draw_mask(outline), CAMERA, DISTANCE)
    waist = measured.waist_at()
    assert waist is not None
    assert measured.width_at(waist) == pytest.approx(0.012, abs=0.0015)


def test_the_same_glass_at_twice_the_distance_measures_the_same():
    # Distance is what turns pixels into millimetres, so getting it wrong
    # scales the whole answer. This is the arithmetic that check rests on.
    outline = straight(height=0.120, rim_diameter=0.070)
    near = profile_from_mask(draw_mask(outline, distance=0.25), CAMERA, 0.25)
    far = profile_from_mask(draw_mask(outline, distance=0.50), CAMERA, 0.50)
    assert near.total_height == pytest.approx(far.total_height, abs=0.003)
    assert near.max_width == pytest.approx(far.max_width, abs=0.003)


def test_a_ragged_mask_is_refused_rather_than_measured():
    outline = straight(height=0.120, rim_diameter=0.070)
    mask = draw_mask(outline)
    # A reflection flickering in and out down one side of the glass, which is
    # what a mis-segmented transparent object actually looks like.
    rows = np.arange(200, 400, 4)
    mask[rows, 180:200] = True
    with pytest.raises(NotMeasurable, match="ragged"):
        profile_from_mask(mask, CAMERA, DISTANCE)


def test_a_clean_mask_is_nowhere_near_the_raggedness_limit():
    # The check has to leave room for the pixel of wander a real mask edge has,
    # or every good picture gets thrown away too.
    from work_cell.glasses.perception import MAX_RAGGEDNESS

    _, widths = row_widths(draw_mask(straight(height=0.120, rim_diameter=0.070)))
    assert raggedness(widths) < MAX_RAGGEDNESS / 4


def test_a_distance_of_zero_is_refused():
    with pytest.raises(ValueError):
        profile_from_mask(draw_mask(straight(0.09, 0.08)), CAMERA, 0.0)


# ------------------------------------------------------------- the handle


def test_two_matching_views_mean_there_is_no_handle():
    outline = straight(height=0.120, rim_diameter=0.070)
    p = profile_from_outline(outline)
    assert handle_direction(p, p) is None


def test_a_view_that_is_much_wider_than_the_other_is_a_handle():
    plain = profile_from_outline(straight(height=0.120, rim_diameter=0.070))
    # The same glass seen from the side its handle sticks out of.
    widened = plain.width.copy()
    middle = slice(len(widened) // 3, 2 * len(widened) // 3)
    widened[middle] *= 1.5
    from work_cell.glasses.profile import Profile

    assert handle_direction(Profile(plain.height, widened), plain) is not None
