"""The simulated room, and the line between it and the robot.

The first tests check the spawner lays out a room that can physically stand
up: a top standing on its edge, held by its ends so that straight up is the
only way out. The last one checks the robot's code never reads the spawner's
numbers, which is the whole point of measuring.
"""

import ast
from pathlib import Path

import numpy as np
import pytest
from synthetic import spawned_box
from turn_top_flat.task import TURN_CLEARANCE, TURN_SPOT
from turn_top_flat.world import spec
from turn_top_flat.world.spawn import box_sdf, random_room

PACKAGE = Path(__file__).resolve().parents[1] / "turn_top_flat"

SEEDS = range(1, 31)


def test_the_same_seed_gives_the_same_room():
    a, b = random_room(5), random_room(5)
    assert a.top.size == b.top.size
    assert a.holders[4].centre == pytest.approx(b.holders[4].centre)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_top_stands_upright_on_a_long_edge(seed):
    top = spawned_box(random_room(seed).top)
    # Its width points up, and it stands on the floor, give or take the
    # millimetre of air it settles through.
    assert top.axis(1) == pytest.approx([0.0, 0.0, 1.0])
    assert top.bottom_z == pytest.approx(0.001, abs=1e-9)
    assert top.size[0] > top.size[1]
    # A face looks at the arm.
    towards_arm = -np.array([top.centre[0], top.centre[1], 0.0]) / np.linalg.norm(top.centre[:2])
    assert abs(float(top.axis(2) @ towards_arm)) > np.cos(np.radians(10.0))


def _extent(box, frame):
    """The box's interval along each of the three axes of ``frame``, as (low, high) rows."""
    along = (box.corners() - frame.centre) @ frame.rotation
    return np.stack([along.min(axis=0), along.max(axis=0)], axis=1)


def _overlap(a, b):
    """Whether two intervals overlap by more than a hair."""
    return min(a[1], b[1]) - max(a[0], b[0]) > 1e-9


def _gap(interval, point=0.0):
    """How far ``point`` is from an interval, zero if inside it."""
    return max(interval[0] - point, point - interval[1], 0.0)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_holders_stand_on_the_floor_without_touching_the_top(seed):
    room = random_room(seed)
    top = spawned_box(room.top)
    assert len(room.holders) == 6
    for spawned in room.holders:
        block = spawned_box(spawned)
        assert block.bottom_z == pytest.approx(0.0, abs=1e-9)
        # The top's box and the block's are apart along at least one of the
        # top's own axes, so the top does not start inside a holder.
        top_extent, block_extent = _extent(top, top), _extent(block, top)
        assert not all(_overlap(top_extent[i], block_extent[i]) for i in range(3))


@pytest.mark.parametrize("seed", SEEDS)
def test_the_only_way_out_is_straight_up(seed):
    room = random_room(seed)
    top = spawned_box(room.top)
    top_extent = _extent(top, top)
    blocks = [_extent(spawned_box(spawned), top) for spawned in room.holders]
    # Slid by more than the play in any level direction, it runs into a
    # holder; lifted, it runs into nothing.
    shove = spec.HOLDER_PLAY + 0.001
    for axis in (0, 2):
        for sign in (1.0, -1.0):
            moved = top_extent.copy()
            moved[axis] += sign * shove
            assert any(all(_overlap(moved[i], block[i]) for i in range(3)) for block in blocks)
    lifted = top_extent.copy()
    lifted[1] += max(block[1][1] for block in blocks) - top_extent[1][0] + 0.01
    assert not any(all(_overlap(lifted[i], block[i]) for i in range(3)) for block in blocks)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_middle_of_the_upper_edge_is_free_for_the_fingers(seed):
    # The fingers are 3 cm wide and come down over the middle of the edge.
    room = random_room(seed)
    top = spawned_box(room.top)
    for spawned in room.holders:
        extent = _extent(spawned_box(spawned), top)
        assert _gap(extent[0]) > 0.015 + 0.03


@pytest.mark.parametrize("seed", SEEDS)
def test_the_legs_stand_upright_far_apart_and_where_the_top_will_rest_on_them(seed):
    room = random_room(seed)
    legs = [spawned_box(leg) for leg in room.legs]
    top = spawned_box(room.top)
    assert len(legs) == 4
    for leg in legs:
        assert leg.bottom_z == pytest.approx(0.001, abs=1e-9)
        assert leg.size[2] > leg.size[0]
    for i, a in enumerate(legs):
        for b in legs[i + 1 :]:
            # The robot tells legs apart by the gaps between them.
            assert np.linalg.norm(a.centre[:2] - b.centre[:2]) > 0.12
    # Lying from the far legs' middles towards the arm, the top covers all
    # four, with the near ones in from its near edge.
    far, near = legs[:2], legs[2:]
    toward = np.mean([leg.centre for leg in near], axis=0) - np.mean([leg.centre for leg in far], axis=0)
    toward = toward / np.linalg.norm(toward[:2])
    for leg in near:
        reach = float((leg.centre - far[0].centre) @ toward) + leg.size[0] / 2.0
        assert reach == pytest.approx(top.size[1] - spec.LEG_INSET, abs=1e-9)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_legs_are_out_of_the_way_of_the_top_and_the_turning_spot(seed):
    room = random_room(seed)
    top = spawned_box(room.top)
    for spawned in room.legs:
        leg = spawned_box(spawned)
        assert np.linalg.norm(leg.centre[:2] - top.centre[:2]) > 0.5
        # Turned flat in the air, by the wrist or the whole arm, the top swings
        # round a spot straight in front of the arm, and nothing may be near it.
        assert np.linalg.norm(leg.centre[:2] - TURN_SPOT) > TURN_CLEARANCE + 0.02


def test_the_top_is_as_heavy_as_it_is_asked_to_be():
    assert random_room(1).top.density == spec.TOP_DENSITY
    assert random_room(1, 1500.0).top.density == 1500.0
    # Only the density changes: the room is otherwise the same.
    assert random_room(1, 1500.0).top.size == random_room(1).top.size


def test_the_legs_are_as_heavy_as_they_are_asked_to_be():
    assert all(leg.density == spec.LEG_DENSITY for leg in random_room(1).legs)
    assert all(leg.density == 200.0 for leg in random_room(1, leg_density=200.0).legs)
    # Only the density changes: the legs stand in the same places.
    for light, usual in zip(random_room(1, leg_density=200.0).legs, random_room(1).legs, strict=True):
        assert light.size == usual.size
        assert np.array_equal(light.centre, usual.centre)


@pytest.mark.parametrize("seed", [1, 2, 3, 7, 12])
def test_a_bigger_room_has_bigger_parts_and_the_legs_stand_under_the_bigger_top(seed):
    usual, big = random_room(seed), random_room(seed, scale=2.0)
    assert np.array(big.top.size) == pytest.approx(2.0 * np.array(usual.top.size))
    for big_leg, usual_leg in zip(big.legs, usual.legs, strict=True):
        assert np.array(big_leg.size) == pytest.approx(2.0 * np.array(usual_leg.size))
    # The far legs still stand where they did; the near ones stand just in
    # from the bigger top's near edge.
    legs, top = [spawned_box(leg) for leg in big.legs], spawned_box(big.top)
    far, near = legs[:2], legs[2:]
    toward = np.mean([leg.centre for leg in near], axis=0) - np.mean([leg.centre for leg in far], axis=0)
    toward = toward / np.linalg.norm(toward[:2])
    for leg in near:
        reach = float((leg.centre - far[0].centre) @ toward) + leg.size[0] / 2.0
        assert reach == pytest.approx(top.size[1] - spec.LEG_INSET, abs=1e-9)


def test_every_box_becomes_a_model():
    room = random_room(1)
    for box in room.boxes():
        sdf = box_sdf(box)
        assert f'<model name="{box.name}">' in sdf
        assert ("<static>true</static>" in sdf) == (box.density == 0.0)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.add("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


@pytest.mark.parametrize(
    "path",
    [p for p in PACKAGE.rglob("*.py") if "world" not in p.relative_to(PACKAGE).parts],
    ids=lambda p: str(p.relative_to(PACKAGE)),
)
def test_the_robot_never_reads_the_simulators_numbers(path):
    """Nothing outside world/ may import from it.

    world/ is where the sizes and positions of everything in the room are
    decided. If the robot's code could read them, it would not need to
    measure anything.
    """
    for name in _imports(path):
        assert "world" not in name.split("."), f"{path.name} imports {name}"
