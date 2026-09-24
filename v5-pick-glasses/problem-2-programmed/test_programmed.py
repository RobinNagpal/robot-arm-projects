"""The three steps, each on glasses drawn across their whole range."""

import math

import numpy as np
import pytest
from work_cell.glasses.perception import profile_from_mask
from work_cell.glasses.shapes import family

import render
import scoring
import views
from find import Seen, find_glasses
from measure import corrected, outline


def _glass(kind, outline_, x=0.48, y=-0.26):
    return render.Glass(kind, x, y, outline_.height, outline_.radius)


@pytest.mark.parametrize("kind", render.KINDS)
def test_the_corrected_height_is_within_three_millimetres(kind):
    for outline_, _ in family(kind, 10, seed=11):
        glass = _glass(kind, outline_)
        picture = render.render([glass], render.side_pose(glass.x, glass.y, math.pi))
        profile = corrected(profile_from_mask(outline(picture), render.LENS, render.STANDOFF))
        height, width = scoring.profile_error(profile, scoring.true_profile(glass))
        assert abs(height) < 0.003
        assert width < 0.003


def test_two_glasses_in_line_with_the_camera_are_still_two():
    (near, _), (far, _) = family("stemmed_glass", 2, seed=4)
    glasses = [_glass("stemmed_glass", near, 0.40, -0.26), _glass("stemmed_glass", far, 0.56, -0.26)]
    found = find_glasses(render.render(glasses, render.top_pose()))
    assert len(found) == 2
    for glass in glasses:
        assert min(math.dist((f.seen.x, f.seen.y), (glass.x, glass.y)) for f in found) < 0.002


def test_a_glass_just_behind_in_the_picture_makes_the_gap_negative():
    target = Seen(0.48, -0.26, 0.04)
    # Looking along -y: the camera stands on +y, so a glass at -y is behind.
    angle = math.pi / 2
    close_behind = Seen(0.48 + 0.02, -0.26 - 0.15, 0.04)
    far_behind = Seen(0.48 + 0.02, -0.26 - 0.40, 0.04)
    assert views.gap(target, [close_behind], angle) < 0
    assert views.gap(target, [far_behind], angle) == math.pi
    assert views.gap(target, [], angle) == math.pi


def test_the_widest_gap_comes_first():
    target = Seen(0.48, -0.26, 0.04)
    ranked = views.ranked(target, [Seen(0.48, -0.10, 0.04)])
    gaps = np.array([g for g, _ in ranked])
    assert (np.diff(gaps) <= 0).all()
