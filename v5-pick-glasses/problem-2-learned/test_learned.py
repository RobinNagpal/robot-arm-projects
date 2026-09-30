"""The parts here that need no trained weights."""

import math

import numpy as np

import models
import render
import show_ranker
import show_side_net
import show_top_net
import viewpoints


def test_every_true_arrow_ends_on_its_own_glasss_middle():
    glasses = render.scene(3)
    picture = render.render(glasses, render.top_pose())
    target = models.top_target(picture, glasses)
    ids = picture.ids[:: models.SHRINK, :: models.SHRINK]
    rows, columns = np.indices(models.SMALL)
    for index, glass in enumerate(glasses):
        mine = ids == index + 1
        column, row = models.rim_middle(picture, glass)
        assert np.allclose(columns[mine] + target[1][mine] * models.VOTE_SCALE, column, atol=1e-3)
        assert np.allclose(rows[mine] + target[2][mine] * models.VOTE_SCALE, row, atol=1e-3)


def test_a_training_scene_can_be_drawn():
    image, numbers, pixels = show_top_net.taught_picture(3)
    assert image.shape[1] == 2 * show_top_net.ZOOM * models.SMALL[1]
    assert numbers["input"].shape == numbers["target"].shape == (3, *models.SMALL)
    assert [pixel["true_answer"]["glass"] for pixel in pixels] == [1, 1, 1, 0]


def test_a_glass_squarely_in_the_way_vetoes_the_view():
    target = viewpoints.Seen(0.48, -0.26, 0.04)
    angle = math.pi / 2
    blocker = viewpoints.Seen(0.48, -0.26 + 0.2, 0.04)
    assert viewpoints.allowed(target, [], angle)
    assert not viewpoints.allowed(target, [blocker], angle)
    assert viewpoints.veto(target, [blocker], angle) == "a glass in the way"


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
        assert image.shape[1] == 2 * show_side_net.ZOOM * models.SMALL[1] + show_side_net.CHART_WIDTH
        assert numbers["input"].shape == (1, *models.SMALL)
        assert len(record["true_answer"]["widths_mm_bottom_to_top"]) == len(numbers["target"]) - 1 == 16
