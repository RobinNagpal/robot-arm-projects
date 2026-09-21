"""The arm's numbers, checked against the rules that depend on them.

These tests exist because the two files can drift apart silently: a grip rule
that asks for more wall than the pads are tall, or a glass record that allows
an opening wider than the gripper, both fail at run time in a way that looks
like a planning problem.
"""

from work_cell.arm import dimensions
from work_cell.glasses import spec


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
