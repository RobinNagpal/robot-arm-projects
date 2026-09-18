"""From masks to YOLO outlines, on masks drawn by hand."""

import cv2
import numpy as np
import pytest

from synthetic.labels import MIN_PIXELS, instances, outline, yolo_line


def label_of(index):
    return index + 1


def test_a_square_in_the_mask_becomes_its_four_corners():
    mask = np.zeros((100, 200), np.uint8)
    mask[20:60, 50:90] = 1
    (found,) = instances(mask, [3], label_of)
    assert found.class_id == 3
    assert found.pixels == 40 * 40
    assert found.box == (50, 20, 40, 40)
    assert sorted(found.outline) == [(50, 20), (50, 59), (89, 20), (89, 59)]


def test_each_block_gets_its_own_class_and_background_is_ignored():
    mask = np.zeros((100, 100), np.uint8)
    mask[10:30, 10:30] = 1
    mask[50:90, 50:90] = 3  # block 2; block 1 is not in the picture at all
    found = instances(mask, [0, 5, 6], label_of)
    assert [(i.block, i.class_id) for i in found] == [(0, 0), (2, 6)]


def test_a_block_showing_only_a_few_pixels_is_not_labelled():
    mask = np.zeros((100, 100), np.uint8)
    mask[0:5, 0:5] = 1
    assert MIN_PIXELS > 25
    assert instances(mask, [0], label_of) == []


def test_a_block_cut_in_two_is_still_one_outline_covering_both_pieces():
    mask = np.zeros((100, 100), np.uint8)
    mask[20:40, 10:30] = 1
    mask[20:40, 60:90] = 1
    (found,) = instances(mask, [0], label_of)
    xs = [x for x, _ in found.outline]
    assert min(xs) == 10
    assert max(xs) == 89
    # Drawn back as a filled polygon, the outline covers both pieces and the gap between stays empty.
    redrawn = np.zeros_like(mask)
    cv2.fillPoly(redrawn, [np.array(found.outline, np.int32)], 1)
    assert redrawn[30, 20] == 1
    assert redrawn[30, 75] == 1
    assert redrawn[30, 45] == 0


def test_a_hexagon_outline_keeps_six_corners():
    mask = np.zeros((200, 200), np.uint8)
    angles = np.linspace(0, 2 * np.pi, 7)[:-1]
    corners = np.stack([100 + 60 * np.cos(angles), 100 + 60 * np.sin(angles)], axis=1).astype(np.int32)
    cv2.fillPoly(mask, [corners], 1)
    simplified = outline(mask)
    # Pixel stairs on the slanted edges add a few points, but nowhere near the hundreds of the raw boundary.
    assert 6 <= len(simplified) <= 30


def test_yolo_line_divides_by_the_image_size():
    mask = np.zeros((100, 200), np.uint8)
    mask[20:60, 50:90] = 1
    (found,) = instances(mask, [4], label_of)
    numbers = yolo_line(found, 200, 100).split()
    assert numbers[0] == "4"
    values = np.array(numbers[1:], float).reshape(-1, 2)
    assert values.min() >= 0 and values.max() <= 1
    assert values[:, 0].min() == pytest.approx(50 / 200)
    assert values[:, 1].max() == pytest.approx(59 / 100)
