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

# How far the circle fitted to a group's outside may sit from the glass's own
# widest part. It is the check's own error, and what it has to be smaller than
# is the room the kind's range leaves: the narrowest kind here spans 60 to
# 85 mm, so a fit wrong by this much still refuses nothing it should keep.
FIT_TOLERANCE = 0.004


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
    assert set(Found.__dataclass_fields__) == {"x", "y", "width", "pixels", "cut_off"}
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


# ------------------------------------- the circle, the split and the refusals


def test_the_circle_fit_recovers_a_circle_it_was_given():
    """The arithmetic on its own, against an answer written down before the fit ran."""
    angles = np.linspace(0, 2 * math.pi, 37)[:-1]
    ring = np.stack([0.4 + 0.031 * np.cos(angles), -0.2 + 0.031 * np.sin(angles)], 1)
    assert abs(find.circle_width(ring) - 0.062) < 1e-9
    # Where the ring sits makes no difference to how wide it is.
    assert abs(find.circle_width(ring - [0.9, 0.4]) - 0.062) < 1e-9


@pytest.mark.parametrize("kind", render.KINDS)
def test_the_fitted_footprint_is_the_glasss_own_width(kind):
    """What the check is held against, on a family rather than on one glass.

    The fit is on the outside of a group's patch of table, so it has to come
    back near the glass's widest part for the kind's own range to mean anything.
    """
    pose, (x, y) = _middle_station()
    for outline_, _ in family(kind, 6, seed=7):
        picture = render.render([_glass(kind, outline_, x, y)], pose)
        one = masks_to_glasses.one_glass(picture, glass_masks(picture)[0])
        fitted = find.footprint(find.dots_of(picture, one.pixels))
        assert abs(fitted - 2.0 * float(outline_.radius.max())) < FIT_TOLERANCE


def test_the_split_puts_two_separated_clouds_of_dots_one_each_side():
    """k-means with two centres, on dots whose answer is not in question."""
    rng = np.random.default_rng(0)
    left = rng.normal([0.40, -0.30], 0.01, (200, 2))
    right = rng.normal([0.52, -0.30], 0.01, (200, 2))
    mine = find.halve(np.concatenate([left, right]))
    # Each cloud whole on one side, whichever of the two sides it landed on.
    assert len(set(mine[:200].tolist())) == 1
    assert len(set(mine[200:].tolist())) == 1
    assert mine[0] != mine[-1]


@pytest.mark.parametrize("kind", render.KINDS)
def test_two_glasses_in_one_group_come_apart_into_two_reports(kind):
    """The step the document prescribes, where distance alone has nothing left to say.

    Each pair stands with half the grouping distance of bare table between the
    two footprints, so the dots chain into one group however far apart the
    centres are. A family of pairs, because a rule that separates one pair and
    fails on a differently proportioned one is the failure to catch.
    """
    pose, (x, y) = _middle_station()
    drawn = [outline_ for outline_, _ in family(kind, 8, seed=7)]
    for first, second in zip(drawn[::2], drawn[1::2], strict=True):
        apart = float(first.radius.max() + second.radius.max()) + find.GROUPING / 2.0
        glasses = [_glass(kind, first, x, y - apart / 2), _glass(kind, second, x, y + apart / 2)]
        picture = render.render(glasses, pose)
        assert len(glass_masks(picture)) == 1

        found, doubts = find.load().find(picture, kind)
        assert (len(found), doubts) == (2, [])
        # Each report nearest a different glass, which is what two glasses means.
        away = [[math.dist((one.x, one.y), (g.x, g.y)) for g in glasses] for one in found]
        assert sorted(gaps.index(min(gaps)) for gaps in away) == [0, 1]


def _in_a_row(kind: str, count: int, seed: int, x: float, y: float):
    """``count`` glasses of one kind in a line, each half the grouping distance from the next.

    Inside the grouping distance on purpose, so the whole row chains into one
    group and distance alone has nothing left to say about it.
    """
    drawn = [outline_ for outline_, _ in family(kind, count, seed=seed)]
    at, places = 0.0, []
    for before, outline_ in zip([None, *drawn[:-1]], drawn, strict=True):
        if before is not None:
            at += float(before.radius.max() + outline_.radius.max()) + find.GROUPING / 2.0
        places.append(at)
    middle = sum(places) / len(places)
    return [_glass(kind, o, x, y + p - middle) for o, p in zip(drawn, places, strict=True)]


@pytest.mark.parametrize("kind", render.KINDS)
def test_three_glasses_in_one_group_come_apart_rather_than_being_handed_over(kind):
    """What repeating the split buys, on the row one split cannot answer.

    One split of a row of three leaves a part still holding two, so a rule that
    stopped there would hand the whole row over. The rule asks again of the part,
    and the row comes apart.

    What is checked of each report is that it lands **on** a glass: a place
    further from every glass than the narrowest width the kind allows would be a
    report of the gap between two of them, which is the way a split like this
    goes wrong. Several seeds, because three drawn glasses are a different row
    every time.
    """
    pose, (x, y) = _middle_station()
    narrowest = data.widths(kind)[0]
    for seed in (5, 9, 13, 17):
        glasses = _in_a_row(kind, 3, seed, x, y)
        picture = render.render(glasses, pose)
        assert len(glass_masks(picture)) == 1

        found, doubts = find.load().find(picture, kind)
        assert doubts == []
        # Two parts of one split can land at one place, which the bench collapses
        # exactly as it collapses two stations' reports of one glass.
        kept = masks_to_glasses.one_per_place(found, narrowest)
        assert len(kept) > 1
        for one in kept:
            assert min(math.dist((one.x, one.y), (g.x, g.y)) for g in glasses) < narrowest


def test_a_group_the_split_cannot_divide_is_handed_over_whole(monkeypatch):
    """Where the repetition stops, and what is reported when it stops short.

    Reporting the parts of a group that happened to fit while dropping the one
    that did not would be claiming to know how many glasses the group holds, and
    the fit has just said it cannot. So the group goes over whole.
    """
    kind = "straight_glass"
    pose, (x, y) = _middle_station()
    picture = render.render(_in_a_row(kind, 3, 5, x, y), pose)
    assert len(glass_masks(picture)) == 1
    assert len(find.load().find(picture, kind)[0]) > 1

    # A halving that puts every dot on one side divides nothing, so the splitting
    # has nowhere left to go.
    monkeypatch.setattr(find, "halve", lambda dots: np.ones(len(dots), dtype=bool))
    assert find.load().find(picture, kind) == ([], [find.TOO_WIDE])


def test_a_group_too_narrow_with_the_whole_of_it_in_frame_is_a_doubt(monkeypatch):
    """The refusal the document prescribes, on a group the picture did hold all of."""
    pose, (x, y) = _middle_station()
    outline_ = next(o for o, _ in family("tapered_glass", 1, seed=11))
    picture = render.render([_glass("tapered_glass", outline_, x, y)], pose)
    whole = glass_masks(picture)[0]
    one = masks_to_glasses.one_glass(picture, whole)
    dots = find.dots_of(picture, one.pixels)

    # Cut down to a disc narrower than the narrowest glass of the kind, so the
    # fit has something real to refuse and the frame has nothing to do with it.
    inside = np.hypot(dots[:, 0] - one.x, dots[:, 1] - one.y) < 0.4 * data.widths("tapered_glass")[0]
    small = np.zeros_like(whole)
    small[one.pixels[inside, 0], one.pixels[inside, 1]] = True
    assert not masks_to_glasses.one_glass(picture, small).cut_off

    monkeypatch.setattr(find, "glass_masks", lambda picture: [small])
    assert find.load().find(picture, "tapered_glass") == ([], [find.TOO_NARROW])


def test_a_group_the_frame_cut_short_is_reported_and_not_refused_on_its_width():
    """The repair, on the bench's own held-out scenes rather than on a built case.

    A glass near the edge of a station's frame shows part of its footprint, so
    the circle fitted to it is too narrow for the kind through no fault of the
    grouping. Refusing on that width would throw away correct answers, and the
    bench's floor measures how many: with the renderer's own exact masks the
    kind's range refuses 66 of 297 glass sightings, and every one reaches the
    frame edge.
    """
    finder, cut_short = find.load(), 0
    for example in data.held_out(3):
        narrowest = data.widths(example.kind)[0]
        for sight in example.sights:
            for mask in glass_masks(sight.picture):
                one = masks_to_glasses.one_glass(sight.picture, mask)
                if one is None:
                    continue
                if find.footprint(find.dots_of(sight.picture, one.pixels)) < narrowest:
                    assert one.cut_off
                    cut_short += 1
            assert find.TOO_NARROW not in finder.find(sight.picture, example.kind)[1]
    assert cut_short, "no group in these scenes was cut short, so nothing was tested"


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
