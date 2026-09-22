"""The arm's numbers, checked against the rules that depend on them.

These tests exist because the two files can drift apart silently: a grip rule
that asks for more wall than the pads are tall, or a glass record that allows
an opening wider than the gripper, both fail at run time in a way that looks
like a planning problem.
"""

import numpy as np
import pytest
from work_cell.arm import dimensions
from work_cell.arm.dimensions import survey_stations
from work_cell.glasses import spec
from work_cell.rack.layout import GLASS_ZONE


def test_no_rule_allows_an_opening_the_gripper_cannot_reach():
    for kind in spec.LIBRARY.values():
        assert kind.max_opening_m <= dimensions.GRIPPER_MAX_OPENING, (
            f"{kind.name} allows {kind.max_opening_m * 1000:.0f} mm but the fingers "
            f"only open to {dimensions.GRIPPER_MAX_OPENING * 1000:.0f} mm"
        )


def test_no_rule_asks_for_more_wall_than_the_pads_need():
    # A band shorter than the pad means the pad overhangs the flat part, which
    # is how a glass slips out of a grip that looked fine on paper.
    for kind in spec.LIBRARY.values():
        assert kind.min_band_height_m <= dimensions.PAD_HEIGHT * 1.5


def test_the_arm_lifts_the_glass_clear_before_it_weighs_it():
    assert 0 < dimensions.WEIGH_LIFT < dimensions.LIFT_HEIGHT


def test_the_slip_test_is_gentle_enough_to_recover_from():
    # The point is to catch a sliding glass while it is still nearly upright.
    assert 0 < dimensions.SLIP_TEST_DEG <= 45.0


def test_the_wrist_cannot_manage_a_half_turn_on_its_own():
    # The whole reason the wrist is wound backwards before the fingers close.
    assert dimensions.WRIST_JOINT_LIMIT_DEG < 180.0


def test_the_measuring_standoff_is_a_real_distance():
    # Perception turns pixels into millimetres with this number, so a wrong one
    # scales every measurement the arm makes.
    assert 0.15 < dimensions.MEASURE_STANDOFF < 0.60


def test_the_camera_is_offset_from_the_tool():
    # If it were not, pointing the tool at a glass would point the camera at it
    # too, and the code that corrects for the offset would be untested.
    assert float(abs(dimensions.CAMERA_OFFSET).max()) > 0.01


# --- where the camera stands to survey -----------------------------------


def _covered(zone, footprint, stations):
    """Is every corner of the zone inside some station's picture?"""
    x_from, x_to, y_from, y_to = zone
    for x in np.linspace(x_from, x_to, 21):
        for y in np.linspace(y_from, y_to, 21):
            if not any(
                abs(x - c[0]) <= footprint[0] / 2 + 1e-9 and abs(y - c[1]) <= footprint[1] / 2 + 1e-9
                for c in stations
            ):
                return False
    return True


def test_the_stations_cover_the_whole_zone():
    zone = GLASS_ZONE
    footprint = (0.519, 0.389)
    assert _covered(zone, footprint, survey_stations(zone, footprint))


def test_a_narrower_lens_just_means_more_stations():
    """No number here assumes a particular camera."""
    zone = GLASS_ZONE
    wide = survey_stations(zone, (0.519, 0.389))
    narrow = survey_stations(zone, (0.20, 0.15))
    assert len(narrow) > len(wide)
    assert _covered(zone, (0.20, 0.15), narrow)


def test_one_station_is_enough_when_one_picture_covers_it_all():
    zone = (0.4, 0.6, -0.1, 0.1)
    assert len(survey_stations(zone, (1.0, 1.0))) == 1


def test_a_camera_that_sees_nothing_is_refused_rather_than_looped_on():
    with pytest.raises(ValueError):
        survey_stations(GLASS_ZONE, (0.0, 0.3))
