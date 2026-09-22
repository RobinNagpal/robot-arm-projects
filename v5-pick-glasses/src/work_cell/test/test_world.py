import random

import pytest
from work_cell.glasses.spawn import random_glasses
from work_cell.rack.build import PEG_HEIGHT, rack_sdf, random_rack_pose, write_marker
from work_cell.rack.layout import (
    MARKER_DICTIONARY,
    MARKER_ID,
    MARKER_SIZE,
    SLOT_COUNT,
    SLOT_SPACING,
)
from work_cell.world.build import build_world

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
