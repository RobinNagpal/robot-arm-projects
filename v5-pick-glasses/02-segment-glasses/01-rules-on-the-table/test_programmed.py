"""The checks on solution 1 that need no weights and no network.

Two halves, and they are two different things on purpose.

**The finder**, which is what the bench scores: the masks it draws, the shape of
what it hands back, and that the place and width come from the bench's own
arithmetic rather than from anything here. Nothing in this half knows how large
a glass is.

**The viewpoint and the measurement**, which the bench does not score. They are
kept because problem 4's documents name this folder's `views.py` as the view
check their pipeline uses, so the rules are still tested here.

Where a check needs a real glass it uses a family of them rather than one,
because a rule that holds for one glass of a kind and fails for a differently
proportioned one is the failure this project exists to prevent.
"""

import inspect
import math

import find
import numpy as np
import pytest
import views
from find import glass_masks
from measure import corrected, outline
from work_cell.glasses.perception import profile_from_mask
from work_cell.glasses.shapes import family

import data
import marking
import masks_to_glasses
import render
import scoring
from masks_to_glasses import Found
from scoring import Scorecard

# How far a place read off one of this solution's masks may sit from where the
# glass really stands, for a glass directly below the camera. The same
# tolerance the bench's own tests hold that arithmetic to, since it is the same
# arithmetic.
PLACE_TOLERANCE = 0.002


def _glass(kind, outline_, x=0.48, y=-0.26):
    return render.Glass(kind, x, y, outline_.height, outline_.radius)


def _middle_station():
    """The station in the middle of the survey, and the point on the table below it."""
    pose = data.poses()[len(data.poses()) // 2]
    return pose, data.under(pose)


# ------------------------------------------------------------------ the masks


def test_a_mask_is_a_boolean_picture_the_shape_of_the_picture():
    pose, (x, y) = _middle_station()
    outline_ = next(o for o, _ in family("straight_glass", 1, seed=3))
    picture = render.render([_glass("straight_glass", outline_, x, y)], pose)
    masks = glass_masks(picture)
    assert len(masks) == 1
    assert masks[0].shape == picture.depth.shape
    assert masks[0].dtype == bool


def test_a_mask_claims_no_pixel_the_camera_got_no_reading_for():
    """This solution asserts nothing, so `masks_to_glasses` has nothing to exclude."""
    pose, (x, y) = _middle_station()
    outline_ = next(o for o, _ in family("stemmed_glass", 1, seed=5))
    picture = render.render([_glass("stemmed_glass", outline_, x, y)], pose)
    for mask in glass_masks(picture):
        assert np.isfinite(picture.depth[mask]).all()


def test_an_empty_picture_gives_no_masks_and_no_glasses():
    pose, _ = _middle_station()
    picture = render.render([], pose)
    assert glass_masks(picture) == []
    assert find.load().find(picture, "straight_glass") == ([], [])


# ----------------------------------------------- the mask through the bench


@pytest.mark.parametrize("kind", render.KINDS)
def test_a_glass_below_the_camera_is_placed_where_it_stands(kind):
    """The whole chain on a glass with no splay, against a known answer.

    Directly below the camera a rim leans nowhere, so the place the shared
    arithmetic gives is the place the glass stands and a mistake in the
    grouping or in the mask would show here.
    """
    pose, (x, y) = _middle_station()
    finder = find.load()
    for outline_, _ in family(kind, 4, seed=7):
        picture = render.render([_glass(kind, outline_, x, y)], pose)
        found, doubts = finder.find(picture, kind)
        assert doubts == []
        assert len(found) == 1
        assert math.dist((found[0].x, found[0].y), (x, y)) < PLACE_TOLERANCE


def test_what_comes_back_is_the_benchs_own_record_and_carries_no_private_arithmetic():
    pose, (x, y) = _middle_station()
    outline_ = next(o for o, _ in family("tapered_glass", 1, seed=11))
    picture = render.render([_glass("tapered_glass", outline_, x, y)], pose)
    found, _ = find.load().find(picture, "tapered_glass")
    assert [type(one) for one in found] == [Found]
    assert set(Found.__dataclass_fields__) == {"x", "y", "width", "pixels"}
    # The pixels are the mask's, said as (row, column) the way the bench reads them.
    assert found[0].pixels.shape[1] == 2


def test_a_group_too_small_to_place_is_a_doubt_and_not_a_glass(monkeypatch):
    """Too few readings to fit anything to is reported, not guessed at."""
    pose, (x, y) = _middle_station()
    outline_ = next(o for o, _ in family("straight_glass", 1, seed=2))
    picture = render.render([_glass("straight_glass", outline_, x, y)], pose)
    whole = glass_masks(picture)[0]
    rows, columns = np.nonzero(whole)
    few = np.zeros_like(whole)
    few[rows[: masks_to_glasses.MIN_PIXELS // 2], columns[: masks_to_glasses.MIN_PIXELS // 2]] = True

    monkeypatch.setattr(find, "glass_masks", lambda picture: [few])
    found, doubts = find.load().find(picture, "straight_glass")
    assert found == []
    assert doubts == [find.TOO_LITTLE]


def test_the_glasses_the_layout_set_out_are_found_one_each_over_a_whole_survey():
    """The claim the method makes, end to end on the bench's own held-out scenes.

    Over the three stations, because one station's frame cuts off a glass near
    its edge and the overlap is what answers that.
    """
    finder, card = find.load(), Scorecard()
    for example in data.held_out(2):
        kept, station = marking.survey(finder, example, card)
        marking.score(card, example, kept, station)
    find_counts = marking.summary("test", card, 2, False)["find"]
    assert find_counts["found"] == card.count["put out"]
    assert (find_counts["missed"], find_counts["merged"], find_counts["split"]) == (0, 0, 0)


def test_this_solution_answers_the_same_interface_as_the_other_five():
    assert list(inspect.signature(find.Finder.find).parameters) == ["self", "picture", "kind"]
    assert list(inspect.signature(find.load).parameters) == ["save"]


# ------------------------------------- the viewpoint and the measurement


@pytest.mark.parametrize("kind", render.KINDS)
def test_the_corrected_height_is_within_three_millimetres(kind):
    for outline_, _ in family(kind, 10, seed=11):
        glass = _glass(kind, outline_)
        picture = render.render([glass], render.side_pose(glass.x, glass.y, math.pi))
        profile = corrected(profile_from_mask(outline(picture), render.LENS, render.STANDOFF))
        height, width = scoring.profile_error(profile, scoring.true_profile(glass))
        assert abs(height) < 0.003
        assert width < 0.003


def test_a_glass_just_behind_in_the_picture_makes_the_gap_negative():
    target = views.Seen(0.48, -0.26, 0.04)
    # Looking along -y: the camera stands on +y, so a glass at -y is behind.
    angle = math.pi / 2
    close_behind = views.Seen(0.48 + 0.02, -0.26 - 0.15, 0.04)
    far_behind = views.Seen(0.48 + 0.02, -0.26 - 0.40, 0.04)
    assert views.gap(target, [close_behind], angle) < 0
    assert views.gap(target, [far_behind], angle) == math.pi
    assert views.gap(target, [], angle) == math.pi


def test_the_widest_gap_comes_first():
    target = views.Seen(0.48, -0.26, 0.04)
    ranked = views.ranked(target, [views.Seen(0.48, -0.10, 0.04)])
    gaps = np.array([g for g, _ in ranked])
    assert (np.diff(gaps) <= 0).all()
