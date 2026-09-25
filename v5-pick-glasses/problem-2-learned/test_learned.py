"""The one part here that is not learned: the veto on where the camera may stand."""

import math

import viewpoints


def test_a_glass_squarely_in_the_way_vetoes_the_view():
    target = viewpoints.Seen(0.48, -0.26, 0.04)
    angle = math.pi / 2
    blocker = viewpoints.Seen(0.48, -0.26 + 0.2, 0.04)
    assert viewpoints.allowed(target, [], angle)
    assert not viewpoints.allowed(target, [blocker], angle)
