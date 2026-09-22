import math
import re

import numpy as np
import pytest
from work_cell.glasses.shapes import KIND_RANGES, stemmed, straight
from work_cell.glasses.spawn import (
    GLASS_LABEL,
    GLASS_TINTS,
    MIN_SEPARATION,
    collision_cylinders,
    glass_sdf,
    random_glasses,
    revolve,
)
from work_cell.glasses.spec import LIBRARY
from work_cell.rack.layout import GLASS_ZONE, TABLE_TOP_Z

# ------------------------------------------------------------ the layout


def test_glasses_are_stood_on_the_table_inside_the_zone():
    x_min, x_max, y_min, y_max = GLASS_ZONE
    for glass in random_glasses(5, seed=1):
        x, y, z = glass.position
        assert x_min <= x <= x_max and y_min <= y <= y_max
        assert z == pytest.approx(TABLE_TOP_Z)


def test_glasses_are_never_crowded_together():
    # Two glasses too close cannot be told apart in one picture, and the wrist
    # camera cannot get a clean side-on view of either.
    glasses = random_glasses(5, seed=2)
    for i, one in enumerate(glasses):
        for other in glasses[i + 1 :]:
            assert math.dist(one.position[:2], other.position[:2]) >= MIN_SEPARATION


def test_a_seed_makes_a_run_repeatable():
    first = random_glasses(4, seed=7)
    again = random_glasses(4, seed=7)
    assert [g.kind for g in first] == [g.kind for g in again]
    assert [g.position for g in first] == [g.position for g in again]


def test_two_glasses_of_the_same_kind_come_out_different_sizes():
    """The point of the whole project, enforced in the spawner.

    If the run put two identical wine glasses on the table, an arm that looked
    its answer up in a table would pass, and the measuring would never be
    tested.
    """
    glasses = random_glasses(6, seed=3, kinds=["stemmed_glass"])
    heights = {round(g.outline.total_height, 4) for g in glasses}
    assert len(heights) == len(glasses)


def test_every_spawned_glass_is_a_kind_the_arm_has_a_rule_for():
    for glass in random_glasses(6, seed=4):
        assert glass.kind in LIBRARY


def test_asking_for_too_many_glasses_says_so_rather_than_overlapping_them():
    with pytest.raises(RuntimeError, match="crowding"):
        random_glasses(50, seed=1)


def test_a_glass_weighs_something_a_kitchen_scale_would_recognise():
    for glass in random_glasses(6, seed=5):
        assert 0.03 < glass.mass < 0.60


# -------------------------------------------------------------- the mesh


def test_spinning_an_outline_gives_a_closed_band_of_triangles():
    outline = straight(height=0.090, rim_diameter=0.080)
    vertices, faces = revolve(outline, segments=16)
    assert len(vertices) == len(outline.height) * 16
    # Two triangles per quad, one quad per segment per gap between rings.
    assert len(faces) == 2 * 16 * (len(outline.height) - 1)


def test_the_mesh_is_the_size_the_outline_said():
    outline = straight(height=0.090, rim_diameter=0.080)
    vertices, _ = revolve(outline, segments=32)
    assert vertices[:, 2].max() == pytest.approx(0.090)
    assert vertices[:, 2].min() == pytest.approx(0.0)
    radius = np.hypot(vertices[:, 0], vertices[:, 1])
    assert radius.max() == pytest.approx(0.040, abs=1e-3)


# --------------------------------------------------------- the collisions


def test_the_collision_stack_spans_the_whole_glass():
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009)
    stack = collision_cylinders(outline)
    assert stack[0][0] == pytest.approx(0.0)
    assert stack[-1][1] == pytest.approx(0.200)


def test_a_collision_slice_is_never_thinner_than_the_glass_inside_it():
    # If it were, the fingers would close through the wall.
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009)
    for bottom, top, radius in collision_cylinders(outline):
        inside = (outline.height >= bottom) & (outline.height <= top)
        assert radius >= outline.radius[inside].max() - 1e-9


def test_the_stack_keeps_the_stem_separate_from_the_bowl():
    # A stem averaged into the bowl above it would be a collision shape the
    # fingers cannot reach, and the grasp would fail for a reason that looks
    # like planning.
    outline = stemmed(height=0.200, bowl_diameter=0.085, stem_diameter=0.009)
    radii = [radius for _, _, radius in collision_cylinders(outline)]
    assert min(radii) < 0.012


# ----------------------------------------------------------------- the sdf


def test_the_model_carries_the_mass_and_the_mesh():
    glass = random_glasses(1, seed=1)[0]
    sdf = glass_sdf(glass, mesh_uri="model://glasses/glass_0.stl")
    assert glass.name in sdf
    assert "model://glasses/glass_0.stl" in sdf
    assert f"{glass.mass:.4f}" in sdf


def test_the_model_is_labelled_because_that_is_the_whole_problem():
    """What makes a glass invisible to the depth camera is the label, not the
    material. The model is painted a solid colour so a person can see it, and
    that has to stay true without the arm noticing."""
    glass = random_glasses(1, seed=1)[0]
    assert f"<label>{GLASS_LABEL}</label>" in glass_sdf(glass, mesh_uri="x.stl")


def test_every_glass_in_a_run_is_a_different_colour():
    """Only so a person can tell them apart. Nothing in the arm reads it."""
    glasses = random_glasses(len(GLASS_TINTS), seed=3)
    colours = {
        re.search(r"<diffuse>([\d. ]+)</diffuse>", glass_sdf(g, mesh_uri="x.stl")).group(1)
        for g in glasses
    }
    assert len(colours) == len(glasses)


def test_a_glass_is_never_so_dark_it_reads_as_background():
    """The mask keeps a hole only where something is visible through it."""
    for tint in GLASS_TINTS:
        assert max(tint) > 0.2


def test_a_full_table_can_always_be_laid_out():
    """Six is the most the table is meant to hold, and it has to fit every
    time, not most times: this runs before the simulator starts, so a layout
    that cannot be drawn is a run that never begins.

    Placing glasses one at a time fails on its own far short of a full zone —
    one glass early on in the wrong place is enough — which is why the whole
    arrangement is redrawn rather than the last spot retried."""
    for seed in range(200):
        glasses = random_glasses(6, seed)
        assert len(glasses) == 6


def test_the_same_seed_survives_a_redrawn_layout():
    # The retry must not make a seed mean two different tables.
    assert [g.position for g in random_glasses(6, 11)] == [
        g.position for g in random_glasses(6, 11)
    ]


def test_a_run_can_be_asked_for_one_kind_of_glass_only():
    """So that one problem can be looked at without the other kinds in the way."""
    for kind in KIND_RANGES:
        drawn = random_glasses(3, seed=5, kinds=[kind])
        assert {g.kind for g in drawn} == {kind}


def test_asking_for_two_kinds_gives_only_those_two():
    drawn = random_glasses(6, seed=6, kinds=["straight_glass", "tapered_glass"])
    assert {g.kind for g in drawn} <= {"straight_glass", "tapered_glass"}


def test_asking_for_nothing_in_particular_still_draws_any_kind():
    drawn = random_glasses(6, seed=7)
    assert {g.kind for g in drawn} <= set(KIND_RANGES)
