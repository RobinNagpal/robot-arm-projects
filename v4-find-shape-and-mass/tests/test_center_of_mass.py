"""The centre-of-mass dataset: irregular outlines, scenes that stay in view, and points that land right."""

import math
import random
from collections import Counter

import pytest

from center_of_mass.generate import pose_line
from center_of_mass.polygons import (
    CLASSES,
    CORNER_ANGLE,
    CORNER_SPREAD,
    SIDE_RATIO,
    SIDES,
    corner_angles,
    irregular_outline,
    is_convex,
    side_lengths,
)
from center_of_mass.scene import (
    CAMERA,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    RANGES,
    centre_of_mass,
    draw_scene,
    project,
    top_of_centre_of_mass,
    unproject,
)
from center_of_mass.scoring import Guess, Truth, match
from center_of_mass.settings import AUGMENTATION, KEYPOINT_SIGMA
from synthetic.shapes import polygon_centroid, widest


def outlines(name, count=300):
    rng = random.Random(name)
    return [irregular_outline(name, 0.1, rng) for _ in range(count)]


def scenes(count=300):
    return [draw_scene(random.Random(f"scene-{i}"), i) for i in range(count)]


def on_the_table(block):
    c, s = math.cos(block.yaw), math.sin(block.yaw)
    x, y = block.position
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in block.outline]


@pytest.mark.parametrize("name", CLASSES)
def test_every_outline_has_its_sides_and_keeps_to_its_limits(name):
    for points in outlines(name):
        assert len(points) == SIDES[name]
        assert is_convex(points)
        lengths = side_lengths(points)
        assert SIDE_RATIO[0] - 1e-9 <= max(lengths) / min(lengths) <= SIDE_RATIO[1] + 1e-9
        angles = corner_angles(points)
        assert CORNER_ANGLE[0] - 1e-9 <= min(angles) and max(angles) <= CORNER_ANGLE[1] + 1e-9
        assert max(angles) - min(angles) >= CORNER_SPREAD - 1e-9
        assert sum(angles) == pytest.approx((len(points) - 2) * math.pi)


@pytest.mark.parametrize("name", CLASSES)
def test_every_outline_is_centred_on_its_centre_of_mass_and_the_right_size(name):
    for points in outlines(name):
        assert polygon_centroid(points) == pytest.approx((0.0, 0.0), abs=1e-9)
        assert widest(points) == pytest.approx(0.1)


def test_the_centre_of_mass_is_not_just_the_middle_of_the_corners():
    # Otherwise the dataset would not need a model to learn mass at all.
    for name in CLASSES:
        if name == "triangle":  # for a triangle the two are always the same point
            continue
        offsets = []
        for points in outlines(name):
            mx = sum(x for x, _ in points) / len(points)
            my = sum(y for _, y in points) / len(points)
            offsets.append(math.hypot(mx, my))
        assert sum(offsets) / len(offsets) > 0.002, name  # 2 mm on a 10 cm block


def test_an_unknown_class_is_refused():
    with pytest.raises(ValueError):
        irregular_outline("circle", 0.1, random.Random(0))


def test_the_same_seed_gives_the_same_scene():
    assert draw_scene(random.Random("a"), 3) == draw_scene(random.Random("a"), 3)


def test_every_class_turns_up_about_as_often_as_every_other():
    counts = Counter(block.shape for scene in scenes(500) for block in scene.blocks)
    expected = sum(counts.values()) / len(CLASSES)
    for name in CLASSES:
        assert abs(counts[name] - expected) < 0.1 * expected, name


def test_blocks_lie_flat_do_not_overlap_and_are_alone_on_the_table():
    for scene in scenes():
        assert scene.distractors == ()
        for i, a in enumerate(scene.blocks):
            assert not a.on_edge
            for b in scene.blocks[i + 1 :]:
                reach_a = max(math.hypot(x, y) for x, y in a.outline)
                reach_b = max(math.hypot(x, y) for x, y in b.outline)
                assert math.dist(a.position, b.position) >= reach_a + reach_b


def test_heights_are_drawn_on_their_own_across_the_whole_range():
    heights = [block.thickness for scene in scenes() for block in scene.blocks]
    low, high = RANGES.thickness
    assert all(low <= h <= high for h in heights)
    # Spread over the range, not bunched at one end.
    assert min(heights) < low + 0.1 * (high - low) and max(heights) > high - 0.1 * (high - low)


def test_every_corner_of_every_block_is_inside_the_picture():
    for scene in scenes():
        assert scene.camera == CAMERA
        for block in scene.blocks:
            for x, y in on_the_table(block):
                for height in (0.0, block.thickness):
                    u, v = project((x, y, height))
                    assert 0 < u < IMAGE_WIDTH and 0 < v < IMAGE_HEIGHT


def test_the_centre_of_mass_is_the_centroid_of_the_placed_outline():
    for scene in scenes(50):
        for block in scene.blocks:
            x, y, z = centre_of_mass(block)
            assert polygon_centroid(on_the_table(block)) == pytest.approx((x, y), abs=1e-9)
            assert z == pytest.approx(block.thickness / 2)
            assert top_of_centre_of_mass(block) == pytest.approx((x, y, block.thickness))


def test_the_projection_matches_a_camera_looking_straight_down():
    # Straight below the camera is the middle of the picture. With the camera
    # pitched down and not turned, the top of the picture is towards +x and
    # its right towards -y. The rendered masks confirm this; see preview.py.
    assert project((0.0, 0.0, 0.0)) == pytest.approx((IMAGE_WIDTH / 2, IMAGE_HEIGHT / 2))
    u, v = project((0.1, 0.0, 0.0))
    assert u == pytest.approx(IMAGE_WIDTH / 2) and v < IMAGE_HEIGHT / 2
    u, v = project((0.0, -0.1, 0.0))
    assert u > IMAGE_WIDTH / 2 and v == pytest.approx(IMAGE_HEIGHT / 2)
    # Nearer the camera, the same offset covers more pixels.
    assert project((0.1, 0.0, 0.05))[1] < project((0.1, 0.0, 0.0))[1]


def test_a_pose_line_holds_the_box_and_the_point_as_fractions_of_the_picture():
    line = pose_line(2, (100, 60, 40, 20), (120.0, 72.0)).split()
    assert line[0] == "2"
    box = [120 / IMAGE_WIDTH, 70 / IMAGE_HEIGHT, 40 / IMAGE_WIDTH, 20 / IMAGE_HEIGHT]
    point = [120 / IMAGE_WIDTH, 72 / IMAGE_HEIGHT]
    assert [float(v) for v in line[1:7]] == pytest.approx(box + point, abs=1e-6)
    assert line[7] == "2"


def test_unproject_undoes_project():
    for point in [(0.0, 0.0, 0.0), (0.12, -0.2, 0.03), (-0.15, 0.25, 0.06)]:
        pixel = project(point)
        assert unproject(pixel, point[2]) == pytest.approx(point[:2], abs=1e-9)


def truth_at(x, y, height=0.03, box=(100, 100, 160, 160)):
    return Truth(
        box=box, class_id=0, point=project((x, y, height)), centre_of_mass=(x, y, height / 2), height=height
    )


def test_a_point_a_centimetre_off_on_the_table_scores_ten_millimetres():
    truth = truth_at(0.05, 0.02)
    guess = Guess(box=truth.box, class_id=0, confidence=0.9, point=project((0.05, 0.03, truth.height)))
    (scored,), extra = match([truth], [guess], min_iou=0.5)
    assert extra == []
    assert scored.millimetres == pytest.approx(10.0)
    assert scored.pixels > 0


def test_matching_pairs_by_box_and_leaves_misses_and_extras_apart():
    a = truth_at(0.0, 0.0, box=(0, 0, 50, 50))
    b = truth_at(0.1, 0.1, box=(200, 200, 260, 260))
    on_a = Guess(box=(2, 2, 52, 52), class_id=1, confidence=0.8, point=a.point)
    nowhere = Guess(box=(400, 400, 440, 440), class_id=0, confidence=0.9, point=(420, 420))
    scored, extra = match([a, b], [on_a, nowhere], min_iou=0.5)
    assert scored[0].guess == on_a and scored[0].millimetres == pytest.approx(0.0, abs=1e-6)
    assert scored[1].guess is None
    assert extra == [nowhere]


def test_the_surer_guess_gets_the_block_when_two_overlap_it():
    a = truth_at(0.0, 0.0, box=(0, 0, 50, 50))
    sure = Guess(box=(1, 1, 51, 51), class_id=0, confidence=0.9, point=a.point)
    unsure = Guess(box=(0, 0, 50, 50), class_id=0, confidence=0.3, point=a.point)
    scored, extra = match([a], [unsure, sure], min_iou=0.5)
    assert scored[0].guess == sure and extra == [unsure]


def test_no_augmentation_moves_blocks_out_of_the_picture_or_bends_the_label():
    # Moving, turning, enlarging or tiling the picture cuts blocks at its
    # edge while their label still marks the whole block's centre of mass;
    # perspective moves the true centre away from the transformed point.
    for key in ("degrees", "translate", "scale", "shear", "perspective", "mosaic", "mixup", "copy_paste"):
        assert AUGMENTATION[key] == 0, key
    assert 0 < KEYPOINT_SIGMA < 1
