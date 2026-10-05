"""The checks on solution 2 that need no trained weights.

Two halves, and they are two different things on purpose.

**The finder**, which is what the bench scores: the labels TopNet is marked
against, the masks its votes turn into, and that the place and the width come
from the bench's own arithmetic rather than from anything here. Where the
network itself is needed it is stood in for by a fixed answer, because a test
that needs trained weights is not a test.

**The viewpoint and the measurement**, which the bench does not score. They are
kept because problem 4's documents name this folder's Ranker and SideNet as
parts their pipeline reuses, so the rules around them are still tested here.
"""

import inspect
import math

import models
import numpy as np
import pipeline
import pytest
import show_ranker
import show_side_net
import show_top_net
import torch
import viewpoints
from models import SHRINK, SMALL, VOTE_SCALE

import data
import marking
import masks_to_glasses
import render
from masks_to_glasses import Found
from scoring import Scorecard


def _sight(seed: int = 3):
    """One training scene's middle station: a picture, and the truth behind it."""
    example = data.spawned(seed)
    return example, example.sights[len(example.sights) // 2]


class _Said:
    """TopNet stood in for by a fixed answer, so the chain can be tested without weights.

    It answers with the true labels of whichever picture it is handed, which is
    the best any network could do, so what is being tested below is everything
    the solution does to an answer rather than the answer itself.
    """

    def __init__(self, target: np.ndarray) -> None:
        # The network's own output is a score, not a flag, and the chain reads
        # "above zero" as glass, so a label of 1 becomes a score of 1.
        self.out = target.copy()

    def to(self, where):
        return self

    def eval(self):
        return self

    def __call__(self, inputs):
        return torch.as_tensor(self.out)[None]


# ------------------------------------------------------- what TopNet is taught


def test_every_true_arrow_ends_on_its_own_glasss_middle():
    example, sight = _sight()
    picture, glasses = sight.picture, example.glasses
    target = models.top_target(picture, glasses)
    ids = picture.ids[::SHRINK, ::SHRINK]
    rows, columns = np.indices(SMALL)
    for index, glass in enumerate(glasses):
        mine = ids == index + 1
        column, row = models.rim_middle(picture, glass)
        assert np.allclose(columns[mine] + target[1][mine] * VOTE_SCALE, column, atol=1e-3)
        assert np.allclose(rows[mine] + target[2][mine] * VOTE_SCALE, row, atol=1e-3)


def test_the_height_channel_is_read_from_the_cameras_own_pose():
    """The three stations are at one height, but nothing here may assume which.

    The first channel is a height above the table, so the same glass must come
    out the same at every station however high the camera was. A height written
    down instead of read from the pose would make this fail at two stations
    out of three.
    """
    example = data.spawned(render.TEST_SEEDS)
    tops = []
    for sight in example.sights:
        given = models.top_input(sight.picture)
        on_glass = sight.picture.ids[::SHRINK, ::SHRINK] > 0
        tops.append(given[0][on_glass].max())
    assert max(tops) - min(tops) < 0.1


def test_a_training_scene_can_be_drawn():
    image, numbers, pixels = show_top_net.taught_picture(3)
    assert image.shape[1] == 2 * show_top_net.ZOOM * SMALL[1]
    assert numbers["input"].shape == numbers["target"].shape == (3, *SMALL)
    assert [pixel["true_answer"]["glass"] for pixel in pixels] == [1, 1, 1, 0]


# -------------------------------------------------------- votes into masks


def test_a_pile_becomes_a_boolean_mask_of_the_whole_block_each_vote_stood_for():
    """The net works at half size, so one vote claims its whole block of pixels."""
    example, sight = _sight()
    picture = sight.picture
    votes = pipeline.cast_votes(picture, _Said(models.top_target(picture, example.glasses)))
    assert votes.middles
    mask = pipeline.pile_mask(picture, votes, votes.middles[0])
    assert mask.shape == picture.depth.shape
    assert mask.dtype == bool
    # Every claimed pixel is one of the pixels of the glass, within the block.
    assert mask.sum() % (SHRINK * SHRINK) == 0


def test_a_pile_with_too_few_votes_is_a_doubt_and_not_a_glass():
    example, sight = _sight()
    picture = sight.picture
    votes = pipeline.cast_votes(picture, _Said(models.top_target(picture, example.glasses)))
    # A middle nothing voted for: no pile there, so nothing to report.
    nowhere = (SMALL[0] - 1, SMALL[1] - 1)
    assert pipeline.pile_mask(picture, votes, nowhere) is None
    found, doubts = pipeline.gather(picture, pipeline.Votes(votes.out, votes.rows, votes.columns,
                                                           votes.landed, votes.tally, [nowhere]))
    assert found == []
    assert doubts == [pipeline.TOO_FEW_VOTES]


def test_the_true_labels_through_the_chain_find_every_glass_that_voted_inside_the_frame():
    """What the solution does to an answer, judged on the best answer there is.

    The arrows are the true arrows and the glass pixels are the true glass
    pixels, so every glass should come back once, at the place the bench's own
    arithmetic gives for its exact mask.

    Every glass **whose votes stayed in the frame**, which is not all of them: a
    glass near the bottom edge of one station's picture has its rim's middle off
    the picture, so its votes land nowhere and its pile cannot be picked. That is
    a fact about one station rather than a fault, and the station that saw the
    glass squarely is what the survey's overlap is for. The test below puts the
    three stations together and expects all of them.
    """
    example, sight = _sight()
    picture = sight.picture
    in_frame = []
    for index, glass in enumerate(example.glasses):
        column, row = models.rim_middle(picture, glass)
        if 0 <= row < SMALL[0] and 0 <= column < SMALL[1]:
            in_frame.append(masks_to_glasses.one_glass(picture, sight.visible[index]))
    in_frame = [one for one in in_frame if one is not None]

    found, doubts = pipeline.find_glasses(picture, _Said(models.top_target(picture, example.glasses)))
    assert doubts == []
    assert len(found) == len(in_frame)
    for one in in_frame:
        assert min(math.dist((f.x, f.y), (one.x, one.y)) for f in found) < 0.01


def _votes_in_frame(example, glass_index: int) -> bool:
    """Whether any station's picture holds the middle this glass's pixels vote for."""
    for sight in example.sights:
        column, row = models.rim_middle(sight.picture, example.glasses[glass_index])
        if 0 <= row < SMALL[0] and 0 <= column < SMALL[1]:
            return True
    return False


def test_a_glass_whose_middle_is_off_every_picture_cannot_be_voted_for():
    """The limit of the voting design on this bench, stated as a test rather than found later.

    A vote is a place in the picture, and the tally is the size of the picture,
    so a glass whose own middle falls outside the frame casts votes that land
    nowhere. The survey's three stations do not rescue it: they are spread along
    one axis only, because one picture already covers the glass zone across the
    other, and a glass at the far edge of that other axis has its rim thrown
    outside the frame from every station. Those glasses are missed, and the
    repair would be a tally with a margin round the picture rather than a better
    network.
    """
    missing = [
        (example.seed, index)
        for example in data.held_out(2)
        for index in range(len(example.glasses))
        if not _votes_in_frame(example, index)
    ]
    assert missing, "this test is about glasses no station can vote for, and there were none"


def test_the_three_stations_together_find_every_glass_they_can_vote_for():
    """The whole chain on the bench, with the network stood in for by the answer key.

    This is the ceiling for this design rather than a measurement of the trained
    network: what is on trial is the voting, the picking of middles, the masks
    and the survey, none of which needs weights to be wrong. The glasses no
    station can vote for are left out, for the reason the test above gives.
    """

    class Perfect:
        """A finder that is handed a picture and answers with that picture's own labels."""

        def __init__(self, example) -> None:
            self.targets = {
                id(sight.picture): models.top_target(sight.picture, example.glasses)
                for sight in example.sights
            }

        def find(self, picture, kind: str):
            return pipeline.find_glasses(picture, _Said(self.targets[id(picture)]))

    card, votable = Scorecard(), 0
    for example in data.held_out(2):
        votable += sum(_votes_in_frame(example, index) for index in range(len(example.glasses)))
        kept, station = marking.survey(Perfect(example), example, card)
        marking.score(card, example, kept, station)
    counts = marking.summary("test", card, 2, False)["find"]
    assert counts["found"] == votable
    assert (counts["merged"], counts["split"], counts["false"]) == (0, 0, 0)


def test_what_comes_back_is_the_benchs_own_record_and_carries_no_private_arithmetic():
    example, sight = _sight()
    picture = sight.picture
    found, _ = pipeline.find_glasses(picture, _Said(models.top_target(picture, example.glasses)))
    assert [type(one) for one in found] == [Found] * len(found)
    assert set(Found.__dataclass_fields__) == {"x", "y", "width", "pixels", "cut_off"}


def test_this_solution_answers_the_same_interface_as_the_other_five():
    assert list(inspect.signature(pipeline.Finder.find).parameters) == ["self", "picture", "kind"]


def test_the_training_scenes_come_from_below_the_benchs_dividing_line():
    """A score claimed on a scene that was trained on leaves no trace in the numbers."""
    seen = [example.seed for example in data.training(4)]
    assert seen and max(seen) < render.TEST_SEEDS
    with pytest.raises(ValueError):
        data.training_seeds(2, start=render.TEST_SEEDS - 1)


# ------------------------------------- the viewpoint and the measurement


def test_a_glass_squarely_in_the_way_vetoes_the_view():
    target = viewpoints.Seen(0.48, -0.26, 0.04)
    angle = math.pi / 2
    blocker = viewpoints.Seen(0.48, -0.26 + 0.2, 0.04)
    assert viewpoints.allowed(target, [], angle)
    assert not viewpoints.allowed(target, [blocker], angle)
    assert viewpoints.veto(target, [blocker], angle) == "a glass in the way"


def test_a_reported_glass_reaches_the_viewpoint_step_as_a_half_width():
    """The viewpoint rules are about distances from an axis; the bench reports a width."""
    one = Found(0.5, -0.3, 0.08, np.zeros((0, 2), dtype=int), cut_off=False)
    assert viewpoints.reported(one) == viewpoints.Seen(0.5, -0.3, 0.04)


def test_the_rankers_training_examples_can_be_drawn():
    drawn = list(show_ranker.taught(2))
    assert drawn
    for _, image, record in drawn:
        assert image.shape[1] == show_ranker.MAP + show_ranker.LARGE[0]
        assert list(record["given_to_ranker"]) == list(viewpoints.FEATURES)
        assert record["true_answer"]["unspoiled"] in (0, 1)


def test_sidenets_training_examples_can_be_drawn():
    drawn = list(show_side_net.taught(2))
    assert drawn
    for _, image, record, numbers in drawn:
        assert image.shape[1] == 2 * show_side_net.ZOOM * SMALL[1] + show_side_net.CHART_WIDTH
        assert numbers["input"].shape == (1, *SMALL)
        assert len(record["true_answer"]["widths_mm_bottom_to_top"]) == len(numbers["target"]) - 1 == 16
