"""The arm's numbers, checked against the rules that depend on them.

These tests exist because the two files can drift apart silently: a grip rule
that asks for more wall than the pads are tall, or a glass record that allows
an opening wider than the gripper, both fail at run time in a way that looks
like a planning problem.
"""

import math
import re
from pathlib import Path

import numpy as np
import pytest
from ament_index_python.packages import get_package_share_directory
from work_cell.arm import dimensions, robotiq_2f85
from work_cell.arm.dimensions import survey_stations
from work_cell.glasses import spec
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.rules import NoGrip, find_grip
from work_cell.glasses.shapes import straight
from work_cell.glasses.spawn import random_glasses
from work_cell.rack.layout import GLASS_ZONE


def test_no_rule_allows_a_glass_the_gripper_cannot_hold():
    # Against what can be held, not against how far the fingers part. The two
    # differ on this gripper, because a glass filling the last few millimetres
    # of the stroke reaches back and touches the gripper's own body.
    for kind in spec.LIBRARY.values():
        assert kind.max_opening_m <= dimensions.GRIPPER_MAX_GRIP, (
            f"{kind.name} allows {kind.max_opening_m * 1000:.1f} mm but the widest "
            f"glass this gripper can hold is {dimensions.GRIPPER_MAX_GRIP * 1000:.1f} mm"
        )


def test_a_glass_can_be_held_wider_than_it_can_be_gripped():
    # The stroke is the wider of the two and is what the gripper is opened to
    # when it is being got out of the way, so mixing the two up would have the
    # arm refusing glasses it can hold.
    assert dimensions.GRIPPER_MAX_GRIP < dimensions.GRIPPER_MAX_OPENING


def test_the_pads_stand_taller_than_the_wall_any_rule_guarantees():
    """A real pad is 22 mm and every rule asks for less wall than that.

    This is the wrong way round and it is a known gap, recorded in
    docs/known-gaps.md: the figures were chosen against a 14 mm pad. The test
    states the situation rather than hiding it, so that whoever measures how
    much slope a silicone pad takes up has a failing assertion to come back
    to once the numbers are raised.
    """
    for kind in spec.LIBRARY.values():
        assert kind.min_band_height_m < dimensions.PAD_HEIGHT


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


def test_the_tool_has_to_clear_the_table():
    """The tool comes in level, so it lies across the grip height rather than
    above it, and whatever hangs furthest below its axis sets the floor. That
    is the force sensor, which is 89 mm across, not the gripper."""
    assert dimensions.LOWEST_GRIP >= 0.089 / 2.0


def test_a_glass_cannot_be_asked_to_be_held_below_that():
    profile = profile_from_outline(straight(height=0.20, rim_diameter=0.07))
    kind = spec.kind("straight_glass")
    grip = find_grip(
        profile,
        kind,
        gripper_max_opening=dimensions.GRIPPER_MAX_GRIP,
        lowest_grip=dimensions.LOWEST_GRIP,
    )
    assert grip.height >= dimensions.LOWEST_GRIP


def test_a_glass_too_short_to_hold_that_high_is_refused_with_a_reason():
    """Held above half its height it cannot be turned over, and below
    LOWEST_GRIP the gripper is through the table. A glass with no room
    between the two is one this gripper cannot pick up."""
    profile = profile_from_outline(straight(height=0.05, rim_diameter=0.06))
    kind = spec.kind("straight_glass")
    with pytest.raises(NoGrip):
        find_grip(
            profile,
            kind,
            gripper_max_opening=dimensions.GRIPPER_MAX_GRIP,
            lowest_grip=dimensions.LOWEST_GRIP,
        )


def test_no_glass_can_be_put_where_the_arm_cannot_work():
    """The zone and the arm's reach live in different files and have to agree.

    A glass drawn beyond the arm's reach is refused however well it was
    measured, which looks like a perception failure and is not one.
    """
    x_from, x_to, y_from, y_to = GLASS_ZONE
    for x in (x_from, x_to):
        for y in (y_from, y_to):
            out = math.hypot(x, y)
            assert dimensions.COMFORTABLE_REACH[0] <= out <= dimensions.COMFORTABLE_REACH[1], (
                f"a glass at the corner ({x}, {y}) stands {out * 1000:.0f} mm from the base"
            )


def test_the_zone_still_holds_a_run_of_glasses():
    """Tightening it must not make the usual run impossible to lay out."""
    for count in (1, 2, 4):
        assert len(random_glasses(count, seed=3)) == count


def test_the_turn_leaves_the_arm_inside_its_own_reach():
    """Turning swings the tool a grasp's depth either side of the glass, so
    where the glass is parked decides whether the arm can finish the turn."""
    glass_out = dimensions.TURNING_ROOM[0]
    before = glass_out - dimensions.GRASP_DEPTH
    after = glass_out + dimensions.GRASP_DEPTH
    lo, hi = dimensions.COMFORTABLE_REACH
    assert lo <= before <= hi, f"the arm starts the turn {before * 1000:.0f} mm out"
    assert lo <= after <= hi, f"the arm ends the turn {after * 1000:.0f} mm out"


def _robotiq_joint_origin(joint: str) -> list[float]:
    """Where Robotiq's own description puts one of the gripper's joints.

    arm/robotiq_2f85.py works the linkage out from a handful of offsets copied
    out of that description, so the drift this file guards against is no
    longer between two files of ours. It is between our copy and Robotiq's
    original, which an update to the package could move under us.
    """
    share = Path(get_package_share_directory("robotiq_description"))
    xacro = (share / "urdf" / "robotiq_2f_85_macro.urdf.xacro").read_text()
    block = re.search(rf'<joint name="\$\{{prefix\}}{joint}".*?</joint>', xacro, re.S)
    assert block, f"{joint} is not in robotiq_description"
    found = re.search(r'<origin xyz="([0-9eE.+-]+) ([0-9eE.+-]+) ([0-9eE.+-]+)"', block.group(0))
    assert found, f"{joint} has no origin"
    return [float(v) for v in found.groups()]


def test_the_linkage_we_copied_is_still_the_linkage_robotiq_publish():
    knuckle = _robotiq_joint_origin("robotiq_85_left_knuckle_joint")
    finger = _robotiq_joint_origin("robotiq_85_left_finger_joint")
    tip = _robotiq_joint_origin("robotiq_85_left_finger_tip_joint")
    assert knuckle == pytest.approx(list(robotiq_2f85.KNUCKLE))
    # The two fixed hops along the finger are added together in our copy,
    # which is only allowed because the fingertip never turns.
    along = [f + t for f, t in zip(finger, tip, strict=True)]
    assert along == pytest.approx(list(robotiq_2f85.ARM))


def test_the_gripper_opens_as_wide_as_robotiq_say_it_does():
    """The one number everybody knows about this gripper is its 85 mm stroke.

    It is not written down anywhere in this project. It falls out of the
    linkage, so getting it right is evidence that the linkage is right.
    """
    assert pytest.approx(0.085, abs=0.0001) == robotiq_2f85.MAX_OPENING


def test_the_glass_is_held_in_the_middle_of_the_pads_not_at_the_tip():
    """At the tip only the front edge of each pad meets the glass, beyond its
    widest line, and squeezing there pushes a round glass out of the fingers."""
    pads_start = dimensions.FINGERTIP_OFFSET - dimensions.PAD_LENGTH
    middle = (pads_start + dimensions.FINGERTIP_OFFSET) / 2.0
    assert middle == pytest.approx(dimensions.grasp_depth(dimensions.GRIPPER_MAX_OPENING))


def test_closing_the_fingers_carries_the_pads_forward():
    """The fingers swing rather than slide, so the pads do not only come
    together, they also come forward. A grip placed for the open gripper would
    sit this far off."""
    assert robotiq_2f85.PAD_TRAVEL > 0.010
    tight = dimensions.grasp_depth(0.030)
    assert tight > dimensions.grasp_depth(dimensions.GRIPPER_MAX_OPENING)


def test_every_glass_fits_between_the_fingers_short_of_the_palm():
    """Held at the middle of the pads, the widest glass allowed must still stop
    short of the gripper's body. This is what GRIPPER_MAX_GRIP is for."""
    widest = max(kind.max_opening_m for kind in spec.LIBRARY.values())
    near_edge = dimensions.grasp_depth(widest) - widest / 2.0
    palm = dimensions.TOOL_TO_GRIPPER_BASE + robotiq_2f85.PALM_REACH
    assert near_edge > palm


def _realsense_property(name: str) -> float:
    """One of Intel's own published numbers for the D405."""
    share = Path(get_package_share_directory("realsense2_description"))
    xacro = (share / "urdf" / "_d405.urdf.xacro").read_text()
    found = re.search(rf'<xacro:property name="{name}" value="([0-9eE.+-]+)"/>', xacro)
    assert found, f"{name} is not in realsense2_description"
    return float(found.group(1))


def test_the_lens_is_where_intel_say_it_is_inside_the_case():
    """The camera's own frame is not at its mounting screw, and the gap is
    Intel's number rather than ours. Aiming the camera means taking it off the
    tool's position, so getting it wrong would point every close-up look a
    centimetre away from the glass."""
    sideways = _realsense_property("d405_cam_depth_py")
    half_height = _realsense_property("d405_cam_height") / 2.0
    forward = (
        _realsense_property("d405_cam_mount_from_center_offset")
        - _realsense_property("d405_glass_to_front")
        - _realsense_property("d405_zero_depth_to_glass")
    )
    assert list(dimensions.CAMERA_LENS_IN_CASE) == pytest.approx([sideways, half_height, forward])


def test_the_camera_can_see_as_far_as_the_arm_asks_it_to():
    """The D405 is a short-range camera: Intel publish about 70 mm to 500 mm.
    Every distance the arm looks from has to be inside that, or the depth it
    reads is outside what the camera stands behind."""
    for distance in (dimensions.MEASURE_STANDOFF, dimensions.SURVEY_HEIGHT):
        assert 0.07 <= distance <= 0.50, f"{distance * 1000:.0f} mm is outside the D405's range"


def test_the_closest_look_is_still_something_the_camera_can_focus_on():
    """The finger view is taken with the fingers already round the glass, and
    it is by far the closest look the arm takes. A D405 cannot focus nearer
    than about 70 mm, so for every width the gripper can hold, the wall of the
    glass has to be at least that far from the lens. This is what decides how
    far back along the tool the camera is mounted."""
    lens = dimensions.CAMERA_OFFSET[2]
    for opening in np.linspace(0.005, dimensions.GRIPPER_MAX_GRIP, 40):
        wall = dimensions.grasp_depth(opening) - opening / 2.0
        assert wall - lens >= 0.070, (
            f"a {opening * 1000:.0f} mm glass puts its wall {1000 * (wall - lens):.0f} mm "
            f"from the lens, inside the camera's blind zone"
        )
