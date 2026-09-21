import random
from pathlib import Path

import pytest
from work_cell.glasses.spawn import random_glasses
from work_cell.rack.build import PEG_HEIGHT, random_rack_pose, rack_sdf
from work_cell.rack.layout import SLOT_COUNT
from work_cell.world.build import build_world

TEMPLATE = "<sdf><world>\n<!-- TABLE -->\n<!-- RACK -->\n<!-- GLASSES -->\n</world></sdf>"


def test_the_rack_has_one_peg_per_slot():
    sdf = rack_sdf(0.5, 0.3, 0.0)
    for index in range(SLOT_COUNT):
        assert f"peg_{index}_collision" in sdf
        assert f"peg_{index}_visual" in sdf


def test_the_rack_carries_a_marker_for_the_arm_to_find_it_by():
    assert 'name="marker"' in rack_sdf(0.5, 0.3, 0.0)


def test_the_rack_stands_where_it_is_put():
    here = rack_sdf(0.50, 0.30, 0.0)
    there = rack_sdf(0.60, 0.35, 0.2)
    assert here != there
    assert "0.5000 0.3000" in here


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
