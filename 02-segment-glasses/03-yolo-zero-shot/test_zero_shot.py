"""The quick checks on solution 3, with no download and no network.

Everything the solution does to the borrowed model's answer is checked here: the
filter on the category names, the hand-set bar on the confidence, the conversion
from the model's outline to a boolean mask, the merging of one glass named twice,
and that the chain refuses cleanly when the model returns nothing. What is not
checked is the model itself, because a test that needs weights off the network is
not a test.

The model's answer is stood in for by `_Answer`, which holds the four parts this
solution reads: the fixed list of category names, a class number and a confidence
per detection, and an outline per detection. The real answer carries much more
and none of it is read here.

Where a check needs a real glass it uses a family of them rather than one,
because a rule that holds for one glass of a kind and fails for a differently
proportioned one is the failure this project exists to prevent.
"""

import inspect
import math
from dataclasses import dataclass

import cv2
import drinking_vessels
import numpy as np
import pytest
import yolo_zero_shot
from work_cell.glasses.shapes import family

import data
import masks_to_glasses
import render
from masks_to_glasses import Found

# How far a place read off the model's own outline of a glass may sit from where
# the glass really stands. The same tolerance the bench's own tests hold that
# arithmetic to, since it is the same arithmetic on the same mask.
PLACE_TOLERANCE = 0.002

# A fixed list of category names standing in for the borrowed model's, holding
# every name this solution accepts and several it must drop.
NAMES = dict(enumerate(("person", "bottle", "wine glass", "cup", "fork", "bowl", "dining table", "vase")))
NUMBER_OF = {name: number for number, name in NAMES.items()}


@dataclass
class _Boxes:
    cls: np.ndarray
    conf: np.ndarray


@dataclass
class _Masks:
    xy: list


@dataclass
class _Answer:
    """One of the borrowed model's answers, in the parts this solution reads."""

    names: dict
    boxes: _Boxes
    masks: _Masks | None

    def cpu(self):
        return self


def _answer(named: list[str], confidences: list[float], outlines: list) -> _Answer:
    boxes = _Boxes(np.array([NUMBER_OF[name] for name in named]), np.array(confidences, dtype=float))
    return _Answer(NAMES, boxes, _Masks(outlines))


def _square(left: int, top: int, side: int) -> np.ndarray:
    """A ring of corners, in the (column, row) order the model reports outlines in."""
    return np.array(
        [[left, top], [left + side, top], [left + side, top + side], [left, top + side]], dtype=float
    )


def _picture():
    return data.spawned(render.TEST_SEEDS).sights[0].picture


def _outline_of(mask: np.ndarray) -> np.ndarray:
    """The ring of corners round a mask, the way the model would report it."""
    rings, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return max(rings, key=cv2.contourArea).reshape(-1, 2).astype(float)


# ------------------------------------------------- the filter on category names


def test_the_filter_keeps_the_drinking_vessels_and_their_near_neighbours():
    for name in drinking_vessels.VESSELS + drinking_vessels.NEIGHBOURS:
        assert drinking_vessels.is_drinking_vessel(name)
    assert set(drinking_vessels.ACCEPTED) == set(drinking_vessels.VESSELS + drinking_vessels.NEIGHBOURS)


def test_the_filter_drops_every_other_name_the_model_can_offer():
    for name in ("person", "fork", "dining table"):
        assert not drinking_vessels.is_drinking_vessel(name)


def test_the_filter_reads_the_models_own_numbering_rather_than_one_written_here():
    assert drinking_vessels.accepted_ids(NAMES) == frozenset({1, 2, 3, 5, 7})
    # The same names under a different numbering give the different numbers, so
    # nothing here depends on the order the model happens to list them in.
    shuffled = {number: name for number, name in enumerate(reversed(list(NAMES.values())))}
    assert drinking_vessels.accepted_ids(shuffled) == frozenset({0, 2, 4, 5, 6})


def test_each_detections_name_is_answered_one_at_a_time():
    asked = [NUMBER_OF[name] for name in ("person", "cup", "fork", "wine glass")]
    kept = drinking_vessels.are_drinking_vessels(asked, NAMES)
    assert kept.dtype == bool
    assert kept.tolist() == [False, True, False, True]
    assert drinking_vessels.are_drinking_vessels([], NAMES).shape == (0,)


# ----------------------------------------------------- the bar on the confidence


def test_the_bar_on_the_confidence_is_a_hand_set_knob_and_lives_in_one_place():
    bar = yolo_zero_shot.CONFIDENCE_BAR_SET_BY_HAND
    assert 0.0 < bar < 1.0
    # At the bar is above it, so the one constant decides and nothing rounds.
    assert above([bar - 0.01, bar, bar + 0.01]) == [False, True, True]


def above(confidences):
    return yolo_zero_shot.above_the_bar(confidences).tolist()


def test_an_outline_below_the_bar_is_dropped_whatever_it_was_named():
    bar = yolo_zero_shot.CONFIDENCE_BAR_SET_BY_HAND
    answer = _answer(
        ["cup", "wine glass"], [bar + 0.1, bar - 0.1], [_square(10, 10, 40), _square(100, 100, 40)]
    )
    masks = yolo_zero_shot.masks_from(answer, (render.HEIGHT, render.WIDTH))
    assert len(masks) == 1
    assert masks[0][20, 20] and not masks[0][110, 110]


def test_a_name_the_filter_drops_is_dropped_however_sure_the_model_is():
    answer = _answer(["dining table"], [0.99], [_square(10, 10, 40)])
    assert yolo_zero_shot.masks_from(answer, (render.HEIGHT, render.WIDTH)) == []


# --------------------------------------------- the model's outline into a mask


def test_a_ring_of_corners_becomes_a_boolean_mask_of_the_pictures_shape():
    shape = (render.HEIGHT, render.WIDTH)
    mask = yolo_zero_shot.outline_to_mask(_square(10, 20, 30), shape)
    assert mask.shape == shape
    assert mask.dtype == bool
    # The ring is reported as (column, row), so the filled square stands at
    # column 10 and row 20 and not the other way round.
    assert mask[25, 15] and not mask[15, 25]
    assert mask.sum() == pytest.approx(31 * 31, rel=0.1)


def test_an_outline_with_too_few_corners_encloses_nothing():
    shape = (render.HEIGHT, render.WIDTH)
    for corners in ([], [[5, 5]], [[5, 5], [9, 9]]):
        mask = yolo_zero_shot.outline_to_mask(np.array(corners, dtype=float), shape)
        assert mask.shape == shape
        assert not mask.any()


def test_an_outline_running_past_the_frame_is_cut_at_the_frame():
    shape = (render.HEIGHT, render.WIDTH)
    mask = yolo_zero_shot.outline_to_mask(_square(-50, -50, 100), shape)
    assert mask[0, 0]
    assert mask.sum() == 51 * 51


def test_one_glass_named_twice_is_handed_over_once():
    """The split the document warns about, paid for here rather than in the scorecard."""
    nearly = _square(10, 10, 40) + 1.0
    answer = _answer(["cup", "wine glass"], [0.9, 0.8], [_square(10, 10, 40), nearly])
    assert len(yolo_zero_shot.masks_from(answer, (render.HEIGHT, render.WIDTH))) == 1

    # Two outlines of two different things are two masks.
    apart = _answer(["cup", "wine glass"], [0.9, 0.8], [_square(10, 10, 40), _square(100, 100, 40)])
    assert len(yolo_zero_shot.masks_from(apart, (render.HEIGHT, render.WIDTH))) == 2


def test_the_surer_of_two_outlines_of_one_glass_is_the_one_kept():
    big, small = _square(10, 10, 44), _square(12, 12, 40)
    surer_is_big = _answer(["cup", "wine glass"], [0.9, 0.5], [big, small])
    surer_is_small = _answer(["cup", "wine glass"], [0.5, 0.9], [big, small])
    kept_big = yolo_zero_shot.masks_from(surer_is_big, (render.HEIGHT, render.WIDTH))
    kept_small = yolo_zero_shot.masks_from(surer_is_small, (render.HEIGHT, render.WIDTH))
    assert kept_big[0].sum() > kept_small[0].sum()


# ------------------------------------------------ the borrowed name goes no further


def test_nothing_the_solution_hands_over_carries_a_category():
    """The borrowed name filters and is then discarded, so it cannot reach a record."""
    assert set(Found.__dataclass_fields__) == {"x", "y", "width", "pixels", "cut_off"}
    masks = yolo_zero_shot.masks_from(
        _answer(["cup"], [0.9], [_square(10, 10, 40)]), (render.HEIGHT, render.WIDTH)
    )
    assert all(mask.dtype == bool for mask in masks)


# ------------------------------------------------------------ the whole chain


def _finding(monkeypatch, answer):
    """The finder with the borrowed model stood in for by a fixed answer."""
    monkeypatch.setattr(yolo_zero_shot, "look", lambda picture: answer)
    return yolo_zero_shot.load()


def test_the_finder_refuses_cleanly_when_the_model_returns_nothing(monkeypatch):
    picture = _picture()
    for answer in (
        _Answer(NAMES, _Boxes(np.zeros(0), np.zeros(0)), None),
        _answer([], [], []),
        _answer(["dining table"], [0.99], [_square(10, 10, 40)]),
    ):
        found, doubts = _finding(monkeypatch, answer).find(picture, "straight_glass")
        assert found == []
        assert len(doubts) == 1 and doubts[0]


def test_an_outline_too_small_to_place_is_a_doubt_and_not_a_glass(monkeypatch):
    # Fewer pixels than the shared arithmetic will fit anything to, so there is
    # nothing to report and nothing to guess at either.
    side = int(math.isqrt(masks_to_glasses.MIN_PIXELS) / 2)
    answer = _answer(["cup"], [0.9], [_square(20, 20, side)])
    found, doubts = _finding(monkeypatch, answer).find(_picture(), "straight_glass")
    assert found == []
    assert len(doubts) == 1


@pytest.mark.parametrize("kind", render.KINDS)
def test_a_glasss_own_outline_through_the_chain_gives_its_place(monkeypatch, kind):
    """The conversion and the shared arithmetic, checked against a known answer.

    The model is stood in for by a perfect outline of one glass, taken from the
    renderer's id picture. What is being checked is that an outline reported the
    way the model reports one arrives at the place the glass really stands, so a
    mistake in the corner order or the fill would show here.
    """
    pose = data.poses()[len(data.poses()) // 2]
    below = data.under(pose)
    for outline, _ in family(kind, 4, seed=7):
        glass = render.Glass(kind, below[0], below[1], outline.height, outline.radius)
        picture = render.render([glass], pose)
        answer = _answer(["wine glass"], [0.9], [_outline_of(picture.ids == 1)])
        found, doubts = _finding(monkeypatch, answer).find(picture, kind)
        assert doubts == []
        assert len(found) == 1
        assert math.dist((found[0].x, found[0].y), below) < PLACE_TOLERANCE


# ---------------------------------------------------------------- one interface


def test_this_solution_answers_the_same_interface_as_the_fitted_ones():
    find = inspect.signature(yolo_zero_shot.Finder.find)
    assert list(find.parameters) == ["self", "picture", "kind"]
    assert list(inspect.signature(yolo_zero_shot.load).parameters) == ["save"]
    fit = inspect.signature(yolo_zero_shot.fit)
    assert list(fit.parameters) == ["examples", "amodal", "save"]


def test_there_is_nothing_to_fit_here_and_fit_says_so_plainly():
    with pytest.raises(RuntimeError, match="fits nothing"):
        yolo_zero_shot.fit([], amodal=False, save=None)
