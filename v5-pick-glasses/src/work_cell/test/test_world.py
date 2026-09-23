import math
import random
from pathlib import Path

import numpy as np
import pytest
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.glasses.spawn import random_glasses
from work_cell.rack.build import rack_sdf, random_rack_pose, write_marker
from work_cell.rack.layout import PEG_HEIGHT
from work_cell.rack.layout import (
    GLASS_ZONE,
    MARKER_DICTIONARY,
    MARKER_ID,
    MARKER_SIZE,
    SLOT_COUNT,
    SLOT_SPACING,
    slots_from_marker,
)
from work_cell.table.build import table_sdf
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z
from work_cell.world.build import build_world

TABLE_TEMPLATE = (Path(__file__).resolve().parents[1] / "work_cell" / "table" / "table.sdf").read_text()

TEMPLATE = "<sdf><world>\n<!-- TABLE -->\n<!-- RACK -->\n<!-- GLASSES -->\n</world></sdf>"


def test_the_rack_has_one_peg_per_slot():
    sdf = rack_sdf(0.5, 0.3, 0.0, marker_uri="file:///marker.png")
    for index in range(SLOT_COUNT):
        assert f"peg_{index}_collision" in sdf
        assert f"peg_{index}_visual" in sdf


def test_the_rack_carries_a_marker_for_the_arm_to_find_it_by():
    sdf = rack_sdf(0.5, 0.3, 0.0, marker_uri="file:///somewhere/marker.png")
    assert 'name="marker"' in sdf
    # A marker visual with no picture on it is a blank white square, which the
    # detector cannot see and which nothing else here would notice.
    assert "file:///somewhere/marker.png" in sdf
    assert f"{MARKER_SIZE:.4f}" in sdf


def test_the_rack_stands_where_it_is_put():
    here = rack_sdf(0.50, 0.30, 0.0, marker_uri="file:///marker.png")
    there = rack_sdf(0.60, 0.35, 0.2, marker_uri="file:///marker.png")
    assert here != there
    assert "0.5000 0.3000" in here


def test_the_drawn_marker_is_one_the_detector_can_actually_read(tmp_path):
    """The point of drawing it is that it reads back. Anything else is a square."""
    import cv2

    path = write_marker(tmp_path / "rack_marker.png")
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    assert image is not None

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(MARKER_DICTIONARY),
        cv2.aruco.DetectorParameters(),
    )
    # A marker touching the edge of its own image has no quiet zone, so it is
    # padded here the way the rack's dark base pads it in the world.
    padded = cv2.copyMakeBorder(image, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    _, ids, _ = detector.detectMarkers(padded)
    assert ids is not None
    assert MARKER_ID in ids.flatten().tolist()


def test_the_marker_stays_clear_of_the_pegs_either_side_of_it():
    """A peg standing on the marker hides a corner, and a hidden corner is a
    marker the detector drops."""
    nearest_peg = SLOT_SPACING / 2.0
    assert nearest_peg > MARKER_SIZE / 2.0


def test_the_rack_pose_is_drawn_rather_than_fixed():
    # The marker only earns its place if the rack actually moves between runs.
    poses = {random_rack_pose(random.Random(seed)) for seed in range(5)}
    assert len(poses) == 5


def test_the_pegs_are_short_enough_to_lower_a_glass_over():
    assert 0.01 < PEG_HEIGHT < 0.06


def test_the_world_gets_the_table_the_rack_and_every_glass(tmp_path):
    glasses = random_glasses(3, seed=1)
    world = build_world(TEMPLATE, "<model name='table'/>", (0.5, 0.3, 0.0), glasses, tmp_path)
    assert "table" in world
    assert "drying_rack" in world
    for glass in glasses:
        assert glass.name in world


def test_every_glass_gets_its_own_mesh_written(tmp_path):
    # One mesh per glass, not one per kind: no two glasses in a run are the
    # same size, so a shared mesh would be the wrong shape for all but one.
    glasses = random_glasses(4, seed=2)
    build_world(TEMPLATE, "", (0.5, 0.3, 0.0), glasses, tmp_path)
    written = sorted(p.name for p in tmp_path.glob("*.stl"))
    assert written == sorted(f"{g.name}.stl" for g in glasses)


def test_the_meshes_are_all_different_because_the_glasses_are(tmp_path):
    glasses = random_glasses(4, seed=3)
    build_world(TEMPLATE, "", (0.5, 0.3, 0.0), glasses, tmp_path)
    sizes = {p.stat().st_size for p in tmp_path.glob("*.stl")}
    contents = {p.read_text() for p in tmp_path.glob("*.stl")}
    assert len(contents) == 4, "two glasses were given identical meshes"
    assert sizes  # written, not empty


def test_a_template_missing_a_marker_says_which_one(tmp_path):
    with pytest.raises(ValueError, match="RACK"):
        build_world("<sdf><!-- TABLE --><!-- GLASSES --></sdf>", "", (0, 0, 0), [], tmp_path)


# --------------------------------------------- the two sides of the table
#
# The rack stands on the arm's left and the glasses on its right. These are
# the facts that keep them apart, and they are checked over every rack pose
# and every set of glasses the run can draw, not over one of each: a gap that
# holds for the arrangement someone had in mind and closes for the next one is
# the failure worth catching.

RACK_HALF_LENGTH = (SLOT_COUNT - 1) * SLOT_SPACING / 2.0 + 0.04
RACK_HALF_WIDTH = 0.070


def _rack_poses(count=60):
    return [random_rack_pose(random.Random(seed)) for seed in range(count)]


def test_the_rack_stands_square_to_the_table():
    """A rack at an angle is what put a slot out of reach at one end."""
    for _, _, yaw in _rack_poses():
        assert math.isclose(yaw % (math.pi / 2), 0.0, abs_tol=1e-9)


def test_every_slot_is_inside_the_arm_s_comfortable_reach():
    near, far = COMFORTABLE_REACH
    for x, y, yaw in _rack_poses():
        for slot in slots_from_marker(np.array([x, y, TABLE_TOP_Z]), yaw):
            out = math.hypot(*slot.centre[:2])
            assert near <= out <= far, f"slot {slot.index} is {out:.3f} m out"


def test_no_glass_ever_stands_on_or_beside_the_rack():
    """The gap is what keeps the rack out of the back of a survey picture."""
    for seed, (rx, ry, _) in enumerate(_rack_poses(30)):
        for glass in random_glasses(6, seed):
            gx, gy = glass.position[:2]
            clear = math.hypot(
                max(abs(gx - rx) - RACK_HALF_LENGTH, 0.0),
                max(abs(gy - ry) - RACK_HALF_WIDTH, 0.0),
            )
            assert clear > 0.15, f"a glass came {clear:.3f} m from the rack"


def test_the_glasses_are_all_on_one_side_and_the_rack_on_the_other():
    _, _, _, y_max = GLASS_ZONE
    for _, ry, _ in _rack_poses():
        assert y_max < ry, "the rack is meant to be the far side of the arm"


def test_the_table_is_big_enough_for_everything_standing_on_it():
    """The table is generated from table/layout.py, so this checks the numbers
    rather than the file: nothing may hang over an edge."""
    half_x, half_y, _ = (TABLE_SIZE[0] / 2.0, TABLE_SIZE[1] / 2.0, 0)
    x_from, x_to, y_from, y_to = GLASS_ZONE
    left = TABLE_CENTRE_XY[0] - half_x, TABLE_CENTRE_XY[1] - half_y
    right = TABLE_CENTRE_XY[0] + half_x, TABLE_CENTRE_XY[1] + half_y

    # Widest a drawn glass gets, so its edge is covered and not just its middle.
    margin = 0.06
    assert left[0] < x_from - margin and x_to + margin < right[0]
    assert left[1] < y_from - margin and y_to + margin < right[1]

    for x, y, _ in _rack_poses():
        assert left[0] < x - RACK_HALF_LENGTH and x + RACK_HALF_LENGTH < right[0]
        assert left[1] < y - RACK_HALF_WIDTH and y + RACK_HALF_WIDTH < right[1]


def test_the_table_model_is_the_table_that_layout_py_describes():
    """table.sdf holds no measurements of its own, so the box the simulator
    loads and the box MoveIt is told about cannot drift apart."""
    sdf = table_sdf(TABLE_TEMPLATE)
    assert f"{TABLE_SIZE[0]:.4f} {TABLE_SIZE[1]:.4f} {TABLE_SIZE[2]:.4f}" in sdf
    assert f"{TABLE_CENTRE_XY[0]:.4f} {TABLE_CENTRE_XY[1]:.4f}" in sdf
    # Four legs, and all of them under the top rather than beyond its corners.
    assert sdf.count('<visual name="leg_') == 4


def test_the_pads_may_touch_the_glass_they_are_holding():
    """The pads are the only parts of the gripper that touch a held glass.

    Left off this list, every move with a glass in hand starts in collision
    and the arm cannot lift anything.
    """
    from work_cell.scene import GRIPPER_LINKS

    assert "left_pad" in GRIPPER_LINKS
    assert "right_pad" in GRIPPER_LINKS


def test_every_link_that_can_touch_a_held_glass_is_listed():
    """Whatever the gripper is made of, the parts that close on a glass are
    the parts allowed to be against it."""
    from work_cell.scene import GRIPPER_LINKS

    for side in ("left", "right"):
        assert f"{side}_finger" in GRIPPER_LINKS
        assert f"{side}_pad" in GRIPPER_LINKS
