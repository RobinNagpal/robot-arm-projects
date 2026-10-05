"""The renderer and the scorecard's silhouette, on one glass alone."""

import math

import numpy as np
from work_cell.glasses.shapes import family

import render
import scoring


def _alone(kind: str, x: float = 0.48, y: float = -0.26) -> render.Glass:
    outline, _ = family(kind, 1, seed=3)[0]
    return render.Glass(kind, x, y, outline.height, outline.radius)


def test_a_glass_alone_is_measured_to_within_the_known_rim_error():
    glass = _alone("straight_glass")
    picture = render.render([glass], render.side_pose(glass.x, glass.y, math.pi))
    height, width = scoring.profile_error(scoring.silhouette(picture), scoring.true_profile(glass))
    # The near rim sits above the lens, so a silhouette reads tall, never short.
    assert 0.0 <= height < 0.015
    assert width < 0.003


def test_the_top_view_puts_a_glass_where_it_stands():
    glass = _alone("stemmed_glass", 0.40, -0.35)
    picture = render.render([glass], render.top_pose())
    rows, columns = np.nonzero(picture.ids == 1)
    points = render.to_world(picture, rows, columns)
    top = points[points[:, 2] >= points[:, 2].max() - 0.008]
    assert np.allclose(top[:, :2].mean(0), [glass.x, glass.y], atol=0.002)


def test_scenes_are_the_same_every_time():
    first, again = render.scene(render.TEST_SEEDS), render.scene(render.TEST_SEEDS)
    assert [(g.x, g.y) for g in first] == [(g.x, g.y) for g in again]
