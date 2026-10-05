"""The quick checks on everything this solution does that is not the model itself.

No weights, no training run and no network. What is checked here is the step
that writes the bench's scenes out as a training set, the refusals that keep
that set below the bench's dividing line, the single class, and what the
finder does with a set of masks once it has them. The model is handed in, so
the finder can be checked without one.

Every check that involves a glass runs over more than one of them, because a
rule that holds for one glass and fails for a differently proportioned one is
the failure this project exists to prevent.
"""

from __future__ import annotations

import inspect
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import dataset
import numpy as np
import pytest
import torch
import yolo_fine_tuned

import data
import masks_to_glasses
import render

HERE = Path(__file__).parent

# A borrowed category list would hold names like these. None of them may appear
# as a string anywhere in this folder, because the single class is what removes
# solution 3's two naming failures and a filter on names would put them back.
BORROWED_NAMES = ("cup", "wine glass", "bowl", "vase", "bottle")


def _scene(seed: int) -> data.Example:
    return data.spawned(seed)


def _disc(radius: int, at=(120, 160)) -> np.ndarray:
    """A filled circle in a picture-sized mask, standing in for a glass seen from above."""
    mask = np.zeros((render.HEIGHT, render.WIDTH), dtype=bool)
    rows, columns = np.ogrid[: render.HEIGHT, : render.WIDTH]
    return mask | ((rows - at[0]) ** 2 + (columns - at[1]) ** 2 <= radius**2)


class _Stub:
    """Something shaped like an Ultralytics model, answering with masks given in advance.

    The finder is everything this solution does after the model, so it is worth
    checking on its own. What goes in is a list of masks and their confidence
    numbers; what the real model does to arrive at those is not this file's
    business.
    """

    def __init__(self, masks, sure=None) -> None:
        self.masks = list(masks)
        self.sure = list(sure) if sure is not None else [0.9] * len(self.masks)
        self.asked = []

    def predict(self, image, **settings):
        self.asked.append(settings)
        if not self.masks:
            return [SimpleNamespace(masks=None, boxes=None)]
        stacked = torch.from_numpy(np.stack(self.masks).astype(np.float32))
        boxes = SimpleNamespace(conf=torch.tensor(self.sure, dtype=torch.float32))
        return [SimpleNamespace(masks=SimpleNamespace(data=stacked), boxes=boxes)]


# ------------------------------------------------------------------ one class


def test_the_model_is_named_in_one_place_and_it_is_a_segmentation_model():
    """Solution 3 must start from the same file, so there is one constant to compare."""
    assert yolo_fine_tuned.MODEL.endswith("-seg.pt")
    named = [
        source.name
        for source in sorted(HERE.glob("*.py"))
        if yolo_fine_tuned.MODEL in source.read_text() and source.name != Path(__file__).name
    ]
    assert named == ["yolo_fine_tuned.py"], f"the model is named in {named}"


def test_there_is_one_class_and_it_is_called_glass():
    assert dataset.GLASS == 0
    assert dataset.NAME == "glass"
    assert yolo_fine_tuned.CLASS == dataset.NAME


def test_no_borrowed_category_name_appears_anywhere_in_this_folder():
    for source in sorted(HERE.glob("*.py")):
        if source.name == Path(__file__).name:
            continue
        text = source.read_text()
        for name in BORROWED_NAMES:
            for quoted in (f'"{name}"', f"'{name}'"):
                assert quoted not in text, f"{source.name} names the borrowed category {name}"


def test_the_written_description_names_one_class_and_points_at_both_parts(tmp_path):
    written = dataset.describe(tmp_path).read_text()
    assert f"  {dataset.GLASS}: {dataset.NAME}\n" in written
    named = [line for line in written.splitlines() if line.startswith("  ")]
    assert named == [f"  {dataset.GLASS}: {dataset.NAME}"], "one class and no others"
    assert f"path: {tmp_path.resolve()}" in written
    assert f"train: images/{dataset.FIT}" in written
    assert f"val: images/{dataset.CHECK}" in written


# ------------------------------------------------------- outlines out of a mask


@pytest.mark.parametrize("radius", [8, 20, 50])
def test_a_masks_outline_encloses_the_mask_it_came_from(radius):
    mask = _disc(radius)
    edge = dataset.outline(mask)
    assert edge is not None and len(edge) >= dataset.CORNERS
    filled = np.zeros(mask.shape, dtype=np.uint8)
    cv2.fillPoly(filled, [edge.astype(np.int32)], 1)
    # A polygon through the pixel centres of a round edge loses a thin fringe,
    # so this asks that it is the same region and not that it is the same pixels.
    assert (filled.astype(bool) & mask).sum() > 0.95 * mask.sum()
    assert (filled.astype(bool) & ~mask).sum() < 0.05 * mask.sum()


def test_a_mask_with_nothing_in_it_and_a_mask_too_small_to_enclose_anything_have_no_outline():
    assert dataset.outline(np.zeros((render.HEIGHT, render.WIDTH), dtype=bool)) is None
    one_pixel = np.zeros((render.HEIGHT, render.WIDTH), dtype=bool)
    one_pixel[100, 100] = True
    assert dataset.outline(one_pixel) is None


def test_the_outline_keeps_the_largest_piece_of_a_mask_that_came_apart():
    """One line of a label file is one object, so a glass in patches is one polygon."""
    mask = _disc(30, at=(120, 100)) | _disc(6, at=(120, 220))
    edge = dataset.outline(mask)
    assert edge is not None
    assert edge[:, 0].max() < 180, "the small far patch should not be in the polygon"


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_a_pictures_label_is_one_line_per_visible_glass_in_the_single_class(seed):
    sight = _scene(seed).sights[0]
    lines = dataset.label(sight)
    big_enough = sum(mask.sum() >= masks_to_glasses.MIN_PIXELS for mask in sight.visible)
    assert 0 < len(lines) <= big_enough
    for line in lines:
        parts = line.split()
        assert parts[0] == str(dataset.GLASS)
        corners = np.array(parts[1:], dtype=float)
        assert len(corners) % 2 == 0 and len(corners) >= 2 * dataset.CORNERS
        assert (corners >= 0.0).all() and (corners <= 1.0).all()


# -------------------------------------------------- the set that gets written


def test_a_written_set_pairs_every_picture_with_a_label(tmp_path):
    counts = dataset.write(dataset.scenes(4), tmp_path, dataset.FIT)
    images = sorted((tmp_path / "images" / dataset.FIT).glob("*.png"))
    labels = sorted((tmp_path / "labels" / dataset.FIT).glob("*.txt"))
    assert counts["pictures"] == len(images) == len(labels) == 4 * len(data.stations())
    assert [one.stem for one in images] == [one.stem for one in labels]
    assert counts["outlines"] == sum(len(one.read_text().splitlines()) for one in labels)

    written = cv2.imread(str(images[0]))
    assert written.shape == (render.HEIGHT, render.WIDTH, 3)
    assert written.dtype == np.uint8


def test_a_written_set_holds_the_crowded_scenes_as_well_as_the_spawned_ones(tmp_path):
    dataset.write(dataset.scenes(4), tmp_path, dataset.FIT)
    names = [one.name for one in (tmp_path / "images" / dataset.FIT).glob("*.png")]
    assert any(name.startswith("crowded") for name in names)
    assert any(name.startswith("spawned") for name in names)


def test_building_a_set_writes_both_parts_and_empties_what_was_there_before(tmp_path):
    root = tmp_path / "dataset"
    stale = root / "images" / dataset.FIT / "stale.png"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"")
    described, counts = dataset.build(dataset.scenes(2), dataset.scenes(1, start=2), root)
    assert described.exists() and not stale.exists()
    assert counts[dataset.FIT]["pictures"] == 2 * len(data.stations())
    assert counts[dataset.CHECK]["pictures"] == 1 * len(data.stations())


# ---------------------------------------------- the line training may not cross


def test_a_held_out_scene_is_refused_as_training_data(tmp_path):
    held_out = data.spawned(render.TEST_SEEDS)
    with pytest.raises(ValueError, match="held-out line"):
        dataset.write([held_out], tmp_path, dataset.FIT)


def test_the_scenes_a_training_run_draws_are_all_below_the_line():
    drawn = list(dataset.scenes(8))
    assert len(drawn) == 8
    assert all(example.seed < render.TEST_SEEDS for example in drawn)
    assert sum(example.crowded for example in drawn) == data.how_many_crowded(8)
    with pytest.raises(ValueError):
        list(dataset.scenes(8, start=render.TEST_SEEDS - 4))


def test_two_stretches_of_training_scenes_do_not_share_a_scene():
    """What the run fits on and what it checks itself on have to be different scenes."""
    first = [(e.seed, e.crowded) for e in dataset.scenes(8)]
    second = [(e.seed, e.crowded) for e in dataset.scenes(8, start=8)]
    assert not set(first) & set(second)


# ----------------------------------------------------------------- the finder


def _whole_glasses(sight) -> list[np.ndarray]:
    """The masks of the glasses this station saw all of.

    A glass cut off at the frame edge is left out. Its place reads out several
    centimetres wrong however perfect the mask is, which is about the survey
    height and not about this solution, and it is why the cell stands at
    overlapping stations in the first place.
    """
    whole = []
    for mask in sight.visible:
        if mask.sum() < masks_to_glasses.MIN_PIXELS:
            continue
        if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
            continue
        whole.append(mask)
    return whole


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_a_glasss_own_mask_comes_back_as_that_glass_in_the_right_place(seed):
    example = _scene(seed)
    judged = 0
    for sight in example.sights:
        masks = _whole_glasses(sight)
        if not masks:
            continue
        judged += len(masks)
        finder = yolo_fine_tuned.Finder(_Stub(masks))
        found, doubts = finder.find(sight.picture, example.kind)
        assert doubts == []
        assert len(found) == len(masks)
        for one in found:
            nearest = min(math.dist((one.x, one.y), (g.x, g.y)) for g in example.glasses)
            assert nearest < 0.005
    assert judged, "the survey should see at least one glass whole from somewhere"


def test_one_glass_proposed_twice_leaves_one_report():
    """With one class a duplicate is two candidates of the same class, and one answer."""
    example = _scene(0)
    sight = example.sights[0]
    mask = max(sight.visible, key=lambda one: one.sum())
    shrunk = cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    finder = yolo_fine_tuned.Finder(_Stub([mask, shrunk], [0.9, 0.8]))
    found, _ = finder.find(sight.picture, example.kind)
    assert len(found) == 1


def test_a_footprint_no_glass_of_this_kind_could_have_is_a_doubt_and_not_a_glass():
    example = _scene(0)
    sight = example.sights[0]
    # The whole table, which is far wider than any glass of any kind.
    everything = np.ones((render.HEIGHT, render.WIDTH), dtype=bool)
    finder = yolo_fine_tuned.Finder(_Stub([everything]))
    found, doubts = finder.find(sight.picture, example.kind)
    assert found == []
    assert doubts == ["kept, but its width is outside what this kind can be"]


def test_a_candidate_with_no_depth_readings_behind_it_is_a_doubt_and_not_a_glass():
    example = _scene(0)
    sight = example.sights[0]
    speck = np.zeros((render.HEIGHT, render.WIDTH), dtype=bool)
    speck[:2, :2] = True
    finder = yolo_fine_tuned.Finder(_Stub([speck]))
    found, doubts = finder.find(sight.picture, example.kind)
    assert found == []
    assert doubts == ["found something with too few depth readings to place"]


def test_a_picture_the_model_found_nothing_in_comes_back_empty_rather_than_failing():
    example = _scene(0)
    finder = yolo_fine_tuned.Finder(_Stub([]))
    assert finder.find(example.sights[0].picture, example.kind) == ([], [])


def test_the_candidates_arrive_surest_first():
    example = _scene(0)
    sight = example.sights[0]
    masks = [mask for mask in sight.visible if mask.sum() >= masks_to_glasses.MIN_PIXELS][:3]
    sure = [0.3, 0.9, 0.6][: len(masks)]
    finder = yolo_fine_tuned.Finder(_Stub(masks, sure))
    _, ordered = finder.candidates(sight.picture)
    assert list(ordered) == sorted(sure, reverse=True)


def test_the_two_settings_are_the_ones_handed_to_the_model():
    example = _scene(0)
    stub = _Stub([])
    yolo_fine_tuned.Finder(stub).find(example.sights[0].picture, example.kind)
    asked = stub.asked[0]
    assert asked["conf"] == yolo_fine_tuned.CONFIDENCE
    assert asked["iou"] == yolo_fine_tuned.OVERLAP
    assert asked["imgsz"] == yolo_fine_tuned.PICTURE


# ----------------------------------------------------- the shared interface


def test_this_solution_answers_the_same_interface_as_the_others():
    fit = inspect.signature(yolo_fine_tuned.fit)
    assert list(fit.parameters)[:3] == ["examples", "amodal", "save"]
    assert fit.parameters["amodal"].kind is inspect.Parameter.KEYWORD_ONLY
    assert fit.parameters["save"].kind is inspect.Parameter.KEYWORD_ONLY
    find = inspect.signature(yolo_fine_tuned.Finder.find)
    assert list(find.parameters) == ["self", "picture", "kind"]
    assert list(inspect.signature(yolo_fine_tuned.load).parameters) == ["save"]


def test_this_model_has_no_amodal_target_and_says_so_before_it_loads_anything():
    with pytest.raises(ValueError, match="amodal"):
        yolo_fine_tuned.fit([], amodal=True, save=HERE / "never-written.pt")
    assert not (HERE / "never-written.pt").exists()


def test_too_few_scenes_to_both_fit_on_and_check_on_is_refused():
    with pytest.raises(RuntimeError, match="fitted on and checked on"):
        yolo_fine_tuned.fit([], amodal=False, save=HERE / "never-written.pt")
    assert not (HERE / "never-written.pt").exists()
