"""Tool orientations, worked out without a simulator."""

import math

import numpy as np
import pytest
from work_cell.transforms import facing_options


def _held_upside_down(pointing: float) -> np.ndarray:
    """A level gripper pointing along ``pointing`` radians, after a half turn
    about its closing axis: tool x, which was down, is now up."""
    z = np.array([math.cos(pointing), math.sin(pointing), 0.0])
    x = np.array([0.0, 0.0, 1.0])
    return np.column_stack((x, np.cross(z, x), z))


@pytest.mark.parametrize("pointing", [0.0, 1.0, math.pi, -2.5])
@pytest.mark.parametrize("outward", [(1.0, 0.0), (0.6, 0.8), (-0.3, 1.0)])
def test_the_first_option_points_the_gripper_away_from_the_base(pointing, outward):
    held = _held_upside_down(pointing)
    first = facing_options(held, np.array(outward))[0]
    wanted = np.array([*outward, 0.0]) / np.linalg.norm(outward)
    assert first[:, 2] == pytest.approx(wanted, abs=1e-9)


def test_every_option_holds_the_glass_the_same_way_up():
    """Only a swing about the vertical is allowed: the glass stays inverted
    and the fingers stay level."""
    held = _held_upside_down(2.0)
    options = facing_options(held, np.array([0.5, 0.5]))
    assert len(options) == 12
    for rotation in options:
        assert np.allclose(rotation.T @ rotation, np.eye(3))
        assert rotation[2, :] == pytest.approx(held[2, :], abs=1e-9)


def test_the_options_go_from_the_smallest_swing_to_the_largest():
    held = _held_upside_down(0.0)
    outward = np.array([0.0, 1.0])
    swings = [
        abs(math.atan2(r[1, 2], r[0, 2]) - math.atan2(outward[1], outward[0]))
        for r in facing_options(held, outward)
    ]
    swings = [round(min(s, 2 * math.pi - s), 9) for s in swings]
    assert swings == sorted(swings)
