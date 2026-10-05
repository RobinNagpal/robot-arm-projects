"""The quick checks on everything in this solution that is not the model itself.

No weights, no network and no fine-tune. What is checked here is the labels
written for the package, the split between observed and asserted pixels, the
two prescribed checks, the visible fraction, and that this folder answers the
same interface the other solutions do. A check that needs a download or a
graphics processor is not a check.

**The one that matters most is the trap.** A mask covering a glass's whole
silhouette claims pixels where the camera saw the glass in front of it, and the
depth reading at such a pixel belongs to that other glass. Feeding those in with
the rest moves the reported place onto the glass in front, and nothing else in
the project objects: the mask looks better, the footprint stays round, and the
width stays inside the range the kind allows. So several checks below do nothing
but prove those pixels are named and left out.

Every check whose answer could turn on a glass's proportions runs over all four
kinds and over a family drawn across each kind's range, because a rule that
holds for one glass of a kind and fails for a differently proportioned one is
the failure this project exists to prevent.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import cv2
import labels
import numpy as np
import pytest
import rf_detr_seg
import train
import weights
from rf_detr_seg import Finder, Seen
from work_cell.glasses.shapes import family
from work_cell.glasses.spawn import MIN_SEPARATION
from work_cell.rack.layout import GLASS_ZONE

import data
import masks_to_glasses
import render

KINDS = render.KINDS

# How much of the hidden part the split has to recover on an exact silhouette,
# and how much of a glass with a clear view it is allowed to give away.
RECOVERED = 0.9
GIVEN_AWAY = 0.05

# How many of the bench's crowded scenes the two measurements below are taken
# over. Enough that a median means something, few enough to stay a quick check.
CROWDED_SCENES = 6


def _one(kind, outline, x, y):
    return render.Glass(kind, x, y, outline.height, outline.radius)


def _middle():
    """The middle station of the survey, and the point on the table below it."""
    pose = data.poses()[len(data.poses()) // 2]
    return pose, data.under(pose)


def _standing(kind, near_outline, far_outline, gap):
    """A pair of glasses on a line out from under the camera, and a picture of them.

    The only arrangement in which one glass covers another from above: on a line
    out from the camera a nearer outline leans over a further one, and close
    enough together it reaches far enough to cover part of it.
    """
    pose, (bx, by) = _middle()
    angle = 0.3
    glasses = [
        _one(kind, outline, bx + away * math.cos(angle), by + away * math.sin(angle))
        for outline, away in ((near_outline, 0.06), (far_outline, 0.06 + gap))
    ]
    return glasses, pose, render.render(glasses, pose)


def _silhouettes(glasses, pose):
    """Each glass's whole outline, from a render of that glass on its own.

    The same thing data.Sight.whole does, written out here so a test can build
    its own arrangement rather than take one of the bench's.
    """
    return [render.render([glass], pose).ids == 1 for glass in glasses]


@lru_cache(maxsize=len(KINDS))
def partly_hidden(kind):
    """One arrangement of ``kind`` in which the far glass is partly, not wholly, covered.

    Searched for rather than written down, because the four kinds are covered
    very differently by the same spacing and a pair that works for one leaves
    another either untouched or gone altogether. Each kind's own family of
    proportions is drawn and the first pair that leaves both parts worth
    measuring is used, so no glass's size is written anywhere.
    """
    drawn = sorted((outline for outline, _ in family(kind, 12, seed=5)), key=lambda o: o.total_height)
    enough = 2 * masks_to_glasses.MIN_PIXELS
    for near in (drawn[-1], drawn[len(drawn) // 2], drawn[-3]):
        for far in (drawn[len(drawn) // 2], drawn[-2], drawn[-1], drawn[0]):
            for gap in (0.05, 0.06, 0.07, 0.08, 0.09, 0.10):
                glasses, pose, picture = _standing(kind, near, far, gap)
                whole = _silhouettes(glasses, pose)
                seen = picture.ids == 2
                if seen.sum() >= enough and (whole[1] & ~seen).sum() >= enough:
                    return glasses, pose, picture, whole
    return None


@lru_cache(maxsize=1)
def crowded():
    """The bench's own crowded scenes, drawn once for the two measurements below."""
    return list(data.held_out(CROWDED_SCENES, hard=True))


def _a_covered_pair(kind):
    arrangement = partly_hidden(kind)
    if arrangement is None:
        pytest.skip(f"no arrangement of {kind} covered one glass partly rather than wholly")
    return arrangement


# ------------------------------------------------------- the labels, written out


def test_a_polygon_comes_back_as_the_mask_it_was_written_from():
    """Masks go to the package as polygons, so what they lose has to be small."""
    for kind in KINDS:
        for outline, _ in family(kind, 6, seed=1):
            pose, (bx, by) = _middle()
            mask = render.render([_one(kind, outline, bx + 0.05, by)], pose).ids == 1
            back = np.zeros(mask.shape, np.uint8)
            for polygon in labels.outlines(mask):
                corners = np.array(polygon, np.int32).reshape(-1, 1, 2)
                cv2.fillPoly(back, [corners], 1)
            back = back.astype(bool)
            shared = (mask & back).sum() / max(1, (mask | back).sum())
            assert shared > 0.98, f"{kind} lost too much going through polygons: {shared:.3f}"


def test_the_rectangle_round_a_mask_holds_it_and_nothing_more():
    pose, (bx, by) = _middle()
    outline = next(o for o, _ in family("stemmed_glass", 1, seed=2))
    mask = render.render([_one("stemmed_glass", outline, bx + 0.04, by - 0.03)], pose).ids == 1
    x, y, across, down = labels.box(mask)
    rows, columns = np.nonzero(mask)
    assert (x, y) == (float(columns.min()), float(rows.min()))
    assert across == float(columns.max() - columns.min() + 1)
    assert down == float(rows.max() - rows.min() + 1)


def test_an_empty_mask_has_no_outline_and_no_annotation(tmp_path):
    assert labels.outlines(np.zeros((8, 8), bool)) == []
    counted = labels.write([], amodal=False, folder=tmp_path)
    assert counted == {"pictures": 0, "glasses": 0}


def test_a_written_split_is_the_coco_folder_the_package_looks_for(tmp_path):
    counted = labels.write([data.crowded(3)], amodal=False, folder=tmp_path)
    written = json.loads((tmp_path / "_annotations.coco.json").read_text())
    assert counted["pictures"] == len(data.stations())
    assert len(written["images"]) == counted["pictures"]
    assert len(written["annotations"]) == counted["glasses"]
    # One class, so a query's class answer is a choice between "glass" and nothing.
    assert [category["name"] for category in written["categories"]] == [labels.CLASS]
    assert {note["category_id"] for note in written["annotations"]} == {labels.CLASS_ID}
    for image in written["images"]:
        assert (tmp_path / image["file_name"]).exists()
        assert (image["height"], image["width"]) == (render.HEIGHT, render.WIDTH)


def test_the_target_flag_is_the_whole_difference_between_the_two_rungs(tmp_path):
    """Whole silhouettes cover more than visible pixels, and never less."""
    example = data.crowded(4)
    visible = labels.write([example], amodal=False, folder=tmp_path / "modal")
    whole = labels.write([example], amodal=True, folder=tmp_path / "amodal")
    assert visible["pictures"] == whole["pictures"]
    for sight in example.sights:
        for seen, all_of_it in zip(sight.visible, sight.whole, strict=True):
            assert (seen & ~all_of_it).sum() == 0
    areas = {}
    for name in ("modal", "amodal"):
        written = json.loads((tmp_path / name / "_annotations.coco.json").read_text())
        areas[name] = sum(note["area"] for note in written["annotations"])
    assert areas["amodal"] > areas["modal"]


def test_a_glass_with_a_clear_view_is_the_same_mask_either_way():
    """The free test the second rung leaves behind: nothing in front, nothing to add."""
    for kind in KINDS:
        outline = next(o for o, _ in family(kind, 1, seed=7))
        pose, (bx, by) = _middle()
        glasses = [_one(kind, outline, bx, by)]
        picture = render.render(glasses, pose)
        assert ((picture.ids == 1) == _silhouettes(glasses, pose)[0]).all()


# ------------------------------------------- the split, and the trap it avoids


@pytest.mark.parametrize("kind", KINDS)
def test_the_split_finds_the_hidden_part_of_an_exact_silhouette(kind):
    glasses, pose, picture, whole = _a_covered_pair(kind)
    truth = whole[1] & ~(picture.ids == 2)
    mine = rf_detr_seg.hidden_by_others(picture, whole, data.under(pose))
    recovered = (mine[1] & truth).sum() / truth.sum()
    assert recovered > RECOVERED, f"{kind}: only {recovered:.2f} of the hidden part was named"
    # And the glass in front, which nothing hides, keeps what it was seen at.
    clear = picture.ids == 1
    assert (mine[0] & clear).sum() < GIVEN_AWAY * clear.sum()


def test_naming_the_asserted_pixels_places_a_glass_far_closer_than_feeding_them_in():
    """The measurement the whole second rung turns on, with no model in the chain.

    It is a claim about a population and not about every glass, which is how the
    bench states it too. A glass seen only down one narrow side is placed badly
    whatever is done with it, and feeding its asserted pixels in can happen to
    push it back the right way. What cannot happen, over a run, is for the
    poisoned readings to be worth having.
    """
    named, fed_in = [], []
    for example in crowded():
        for sight in example.sights:
            asserted = rf_detr_seg.hidden_by_others(sight.picture, sight.whole, data.under(sight.pose))
            for index, glass in enumerate(sight.glasses):
                seen, whole = sight.visible[index], sight.whole[index]
                if (whole & ~seen).sum() < masks_to_glasses.MIN_PIXELS:
                    continue
                here = [
                    masks_to_glasses.one_glass(sight.picture, whole, which)
                    for which in (asserted[index], None)
                ]
                if any(one is None for one in here):
                    continue
                named.append(math.dist((here[0].x, here[0].y), (glass.x, glass.y)))
                fed_in.append(math.dist((here[1].x, here[1].y), (glass.x, glass.y)))
    assert len(named) >= 10, f"only {len(named)} partly hidden glasses, which measures nothing"
    assert np.median(fed_in) > 2 * np.median(named)


def test_the_split_recovers_the_hidden_part_of_the_benchs_own_crowded_scenes():
    shared = []
    for example in crowded():
        for sight in example.sights:
            mine = rf_detr_seg.hidden_by_others(sight.picture, sight.whole, data.under(sight.pose))
            for index in range(len(sight.glasses)):
                truth = sight.whole[index] & ~sight.visible[index]
                if truth.sum() < masks_to_glasses.MIN_PIXELS:
                    continue
                shared.append((mine[index] & truth).sum() / (mine[index] | truth).sum())
    assert len(shared) >= 10
    assert np.median(shared) > RECOVERED


@pytest.mark.parametrize("kind", KINDS)
def test_nothing_is_asserted_when_nothing_stands_in_front(kind):
    """Three glasses round the camera at the cell's own separation hide nothing."""
    outlines = [outline for outline, _ in family(kind, 3, seed=11)]
    pose, (bx, by) = _middle()
    away = MIN_SEPARATION / math.sqrt(3.0)
    glasses = [
        _one(kind, outline, bx + away * math.cos(turn), by + away * math.sin(turn))
        for outline, turn in zip(outlines, np.linspace(0.0, 2 * math.pi, 3, endpoint=False), strict=True)
    ]
    picture = render.render(glasses, pose)
    whole = _silhouettes(glasses, pose)
    for index, asserted in enumerate(rf_detr_seg.hidden_by_others(picture, whole, data.under(pose))):
        assert not asserted.any(), f"{kind}: glass {index} gave away pixels nothing was covering"


def test_a_report_with_nothing_in_front_of_it_is_fully_visible():
    kind = "straight_glass"
    outline = next(o for o, _ in family(kind, 1, seed=13))
    pose, (bx, by) = _middle()
    glasses = [_one(kind, outline, bx, by)]
    picture = render.render(glasses, pose)
    mask = _silhouettes(glasses, pose)[0]
    one = rf_detr_seg._judge(picture, mask, np.zeros_like(mask), 0.9, kind)
    assert one.doubt is None
    assert one.visible_fraction == pytest.approx(1.0)
    assert math.dist((one.found.x, one.found.y), (glasses[0].x, glasses[0].y)) < 0.01


def test_the_visible_fraction_is_the_observed_share_of_the_mask():
    mask = np.zeros((10, 10), bool)
    mask[:, :8] = True
    asserted = np.zeros((10, 10), bool)
    asserted[:, :2] = True
    assert Seen(mask, asserted, 1.0, None, None).visible_fraction == pytest.approx(0.75)
    assert Seen(np.zeros((4, 4), bool), np.zeros((4, 4), bool), 1.0, None, None).visible_fraction == 0.0


# ----------------------------------------------- the two checks, which refuse


def test_a_mask_claiming_glass_where_the_camera_saw_the_table_is_doubted():
    """The prescribed check: the asserted part must lie where the camera could not see.

    The leak is sized to sit between the two checks on purpose: small enough
    that the width stays inside what the kind allows, large enough to be a claim
    about a patch the camera had a clear view of.
    """
    kind = "straight_glass"
    outline = next(o for o, _ in family(kind, 1, seed=17))
    pose, (bx, by) = _middle()
    glasses = [_one(kind, outline, bx, by)]
    picture = render.render(glasses, pose)
    honest = _silhouettes(glasses, pose)[0]

    rows, columns = np.nonzero(honest)
    across = int(columns.max() - columns.min())
    patch = int(round(2 * rf_detr_seg.OVER_A_CLEAR_VIEW * honest.sum()))
    leaked = honest.copy()
    leaked[rows.min() : rows.min() + patch // across, columns.max() + across : columns.max() + 2 * across] = (
        True
    )

    kept = rf_detr_seg._judge(picture, honest, np.zeros_like(honest), 0.9, kind)
    spilled = rf_detr_seg._judge(picture, leaked, np.zeros_like(leaked), 0.9, kind)
    assert kept.doubt is None
    assert spilled.doubt.startswith("it claims glass where the camera saw past it")
    # Doubted, and the stray readings left out of the arithmetic all the same.
    assert spilled.asserted.sum() > 0
    assert not (spilled.asserted & honest).any()


@pytest.mark.parametrize("kind", KINDS)
def test_a_width_no_glass_of_the_kind_could_have_is_doubted(kind):
    """The other prescribed check: a report claims a footprint, and it has to be a legal one.

    One mask over two glasses standing well apart is the shape that fails it,
    and it is the loud failure the quiet one is traded against: a merged region
    is wider than any glass of the kind can be, so it is refused.
    """
    outlines = [outline for outline, _ in family(kind, 2, seed=29)]
    pose, (bx, by) = _middle()
    glasses = [
        _one(kind, outlines[0], bx - MIN_SEPARATION, by),
        _one(kind, outlines[1], bx + MIN_SEPARATION, by),
    ]
    picture = render.render(glasses, pose)
    merged = (picture.ids == 1) | (picture.ids == 2)
    one = rf_detr_seg._judge(picture, merged, np.zeros_like(merged), 0.9, kind)
    assert one.found is not None
    assert one.found.width > data.widths(kind)[1]
    assert one.doubt is not None, f"{kind}: a region {one.found.width:.3f} m wide was not refused"
    assert one.doubt.startswith("its width is outside what this kind can be")


def test_a_refusal_says_when_the_glass_ran_off_the_edge_of_the_frame():
    """The commonest reason a mask here is refused is the view, not the model.

    At the cell's own survey height one picture does not hold the glass zone, so
    a glass at the far side of a station's frame is cut off and the width read
    off it is not the glass's. The survey stands at three overlapping stations
    for exactly that, and a refusal that says so is readable where a bare
    "width out of range" is not.
    """
    kind = "straight_glass"
    outline = next(o for o, _ in family(kind, 1, seed=31))
    pose, (bx, by) = _middle()
    corner = _silhouettes([_one(kind, outline, *GLASS_ZONE[1::2])], pose)[0]
    middle = _silhouettes([_one(kind, outline, bx, by)], pose)[0]
    assert rf_detr_seg.cut_off(corner)
    assert not rf_detr_seg.cut_off(middle)

    empty = np.zeros_like(corner)
    assert rf_detr_seg._refused(middle, empty, 0.9, None, "no good").doubt == "no good"
    assert rf_detr_seg._refused(corner, empty, 0.9, None, "no good").doubt == (
        "no good, and it runs off the edge of the frame"
    )


def test_a_mask_with_too_little_in_it_is_a_doubt_and_not_a_place():
    kind = "straight_glass"
    outline = next(o for o, _ in family(kind, 1, seed=23))
    pose, (bx, by) = _middle()
    picture = render.render([_one(kind, outline, bx, by)], pose)
    scrap = np.zeros((render.HEIGHT, render.WIDTH), bool)
    scrap[100:103, 100:103] = True
    one = rf_detr_seg._judge(picture, scrap, np.zeros_like(scrap), 0.9, kind)
    assert one.found is None
    assert one.doubt.startswith("too little of it was seen to place it")


# --------------------------------------------------------------- the interface


class _Stub:
    """A model that answers with masks handed to it, so the chain can be run dry."""

    def __init__(self, masks):
        self.masks = masks

    def predict(self, image, threshold):
        del image, threshold
        return type(
            "Answer",
            (),
            {"mask": np.stack(self.masks), "confidence": np.linspace(0.9, 0.8, len(self.masks))},
        )


def test_the_finder_names_the_asserted_pixels_before_the_arithmetic_sees_them(monkeypatch):
    """End to end through find, with a stub where the fine-tuned model would be.

    This is the check the whole second rung turns on: the place that comes back
    has to be the place the observed pixels alone give, not the place the whole
    silhouette gives.
    """
    kind = "tapered_glass"
    glasses, pose, picture, whole = _a_covered_pair(kind)

    monkeypatch.setattr(rf_detr_seg, "_loaded", lambda checkpoint: _Stub(whole))
    finder = Finder(Path("no-such-checkpoint"))

    seen = finder.look(picture, kind)
    assert len(seen) == len(whole)
    behind = seen[1]
    assert behind.asserted.any()
    assert behind.visible_fraction < 1.0
    # The place is the one the named split gives, to the millimetre.
    named = masks_to_glasses.one_glass(picture, whole[1], behind.asserted)
    assert (behind.found.x, behind.found.y) == pytest.approx((named.x, named.y))
    # And it is not the place the whole silhouette would have given.
    fed_in = masks_to_glasses.one_glass(picture, whole[1], None)
    assert math.dist((behind.found.x, behind.found.y), (fed_in.x, fed_in.y)) > 0.005

    found, doubts = finder.find(picture, kind)
    assert isinstance(found, list) and isinstance(doubts, list)
    assert all(isinstance(one, masks_to_glasses.Found) for one in found)


def test_this_folder_answers_the_same_three_calls_the_other_solutions_do():
    import inspect

    assert inspect.signature(rf_detr_seg.load).parameters.keys() == {"save"}
    fitting = inspect.signature(rf_detr_seg.fit).parameters
    assert "examples" in fitting
    for named in ("amodal", "save"):
        assert fitting[named].kind is inspect.Parameter.KEYWORD_ONLY
    for call in ("find", "look"):
        assert callable(getattr(Finder, call))


def test_loading_a_model_that_was_never_fitted_refuses_rather_than_guesses(tmp_path):
    with pytest.raises(FileNotFoundError):
        rf_detr_seg.load(tmp_path / "fitted-amodal.pth")


def test_the_two_targets_are_saved_apart_and_the_borrowed_cache_sits_here():
    assert weights.fitted("modal") != weights.fitted("amodal")
    assert set(train.TARGETS) == {"modal", "amodal"}
    for target in train.TARGETS:
        assert weights.fitted(target).parent == weights.CACHE
    assert weights.borrowed().is_relative_to(Path(__file__).parent)
