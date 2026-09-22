"""Reading the room, as the simulator would lay it out, from points alone.

The test is the only place the robot's measurements and the simulator's truth
meet: the room is drawn by the spawner, turned into the points a camera
circling the arm would see, and what the robot reads from those points is
compared with what the spawner put there.
"""

import math

import numpy as np
import pytest
from synthetic import floor_points, spawned_box, visible_surface
from turn_top_flat.perception.room import is_standing, leg_length, read_room
from turn_top_flat.world.spawn import random_room

BASE = np.zeros(3)
# Where the survey puts the camera, near enough: a ring round the base.
CAMERAS = [np.array([0.3 * math.cos(a), 0.3 * math.sin(a), 0.6]) for a in np.radians(range(0, 360, 45))]


def nearest_camera(box):
    return min(CAMERAS, key=lambda c: np.linalg.norm(c - box.centre))


def survey(room):
    """The parts' points and everything else's, as a survey would see them."""
    parts = []
    for spawned in (room.top, *room.legs):
        box = spawned_box(spawned)
        parts.append(visible_surface(box, nearest_camera(box)))
    parts = np.concatenate(parts)
    others = [floor_points()]
    for spawned in room.holders:
        block = spawned_box(spawned)
        others.append(visible_surface(block, nearest_camera(block)))
    return parts, np.concatenate(others)


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 12])
def test_the_upright_top_and_the_legs_are_read_back_as_the_simulator_stood_them(seed):
    room = random_room(seed)
    seen = read_room(*survey(room), self_centre=BASE, self_radius=0.13)

    assert seen.floor_z == pytest.approx(0.0, abs=0.001)

    assert seen.top is not None
    assert seen.top.size == pytest.approx(np.array(room.top.size), abs=0.002)
    assert seen.top.centre == pytest.approx(room.top.centre, abs=0.002)
    assert not seen.unknown

    assert len(seen.legs) == 4
    for leg in seen.legs:
        assert is_standing(leg)
        assert leg_length(leg) == pytest.approx(room.legs[0].size[2], abs=0.002)
        assert min(np.linalg.norm(leg.centre[:2] - true.centre[:2]) for true in room.legs) < 0.003


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 12])
def test_the_holders_are_hidden_in_the_tops_own_shadow(seed):
    # Grey points this close to a part are taken for the part's own dim sides,
    # and the holders are all within that of the top. So the arm never knows
    # how tall they are, and lifts the top by its own height to be sure.
    room = random_room(seed)
    seen = read_room(*survey(room), self_centre=BASE, self_radius=0.13)
    assert not seen.obstacles


def test_nothing_the_robot_sees_of_itself_counts():
    room = random_room(1)
    parts, others = survey(room)
    # A patch of grey right by the base, as the camera would see the arm's own base.
    own_base = np.array(
        [
            [0.05 * math.cos(a), 0.05 * math.sin(a), z]
            for a in np.linspace(0, 6, 200)
            for z in (0.05, 0.1, 0.15)
        ]
    )
    seen = read_room(parts, np.concatenate([others, own_base]), self_centre=BASE, self_radius=0.13)
    assert not seen.obstacles
