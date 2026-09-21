"""Random scenes: repeatable, inside their ranges, and nothing on top of anything else."""

import math
import random
from collections import Counter

import pytest

from synthetic.randomization import GAP, SEEN, TABLE_SIZE, UNSEEN, draw_scene
from synthetic.shapes import CLASSES, narrowest, widest


def scenes(ranges, count=500, name="scene"):
    return [draw_scene(random.Random(f"{name}-{i}"), ranges) for i in range(count)]


def test_the_same_seed_gives_the_same_scene():
    assert draw_scene(random.Random("a"), SEEN) == draw_scene(random.Random("a"), SEEN)
    assert draw_scene(random.Random("a"), SEEN) != draw_scene(random.Random("b"), SEEN)


def test_every_class_turns_up_about_as_often_as_every_other():
    counts = Counter(block.shape for scene in scenes(SEEN, 2000) for block in scene.blocks)
    assert set(counts) == set(CLASSES)
    expected = sum(counts.values()) / len(CLASSES)
    for shape, count in counts.items():
        assert abs(count - expected) < 0.15 * expected, shape


def test_nothing_on_the_table_overlaps_anything_else():
    for scene in scenes(SEEN):
        things = [(b.position, _reach(b)) for b in scene.blocks]
        things += [(d.position, _distractor_reach(d)) for d in scene.distractors]
        for i, (p, r) in enumerate(things):
            for q, s in things[i + 1 :]:
                assert math.dist(p, q) >= r + s + GAP - 1e-9


def test_every_block_stays_on_the_table():
    for scene in scenes(SEEN):
        for block in scene.blocks:
            x, y = block.position
            reach = _reach(block)
            assert abs(x) + reach <= TABLE_SIZE[0] / 2
            assert abs(y) + reach <= TABLE_SIZE[1] / 2


def test_blocks_are_thinner_than_they_are_wide():
    # Otherwise a thick square block is a rectangle block seen from the side.
    for scene in scenes(SEEN):
        for block in scene.blocks:
            assert block.thickness <= SEEN.thickness[1] * narrowest(list(block.outline)) + 1e-9


def test_some_blocks_stand_on_an_edge():
    blocks = [b for scene in scenes(SEEN) for b in scene.blocks]
    share = sum(b.on_edge for b in blocks) / len(blocks)
    assert share == pytest.approx(SEEN.on_edge_chance, abs=0.05)


@pytest.mark.parametrize("ranges", [SEEN, UNSEEN], ids=["seen", "unseen"])
def test_the_camera_is_above_the_table_and_looks_at_the_blocks(ranges):
    for scene in scenes(ranges, 200):
        if not scene.blocks:
            continue
        camera = scene.camera
        x, y, z = camera.position
        assert z > 0
        # The direction the camera looks along, from its pitch and yaw.
        look = (
            math.cos(camera.pitch) * math.cos(camera.yaw),
            math.cos(camera.pitch) * math.sin(camera.yaw),
            -math.sin(camera.pitch),
        )
        middle = [sum(b.position[k] for b in scene.blocks) / len(scene.blocks) for k in (0, 1)] + [0.0]
        towards = [m - c for m, c in zip(middle, camera.position, strict=True)]
        cosine = sum(a * b for a, b in zip(look, towards, strict=True)) / math.hypot(*towards)
        # Within a few degrees, the aim point is allowed to wander off the middle.
        assert cosine > math.cos(math.radians(15))


def test_the_unseen_set_really_is_unseen():
    assert not set(UNSEEN.table_patterns) & set(SEEN.table_patterns)
    assert not set(UNSEEN.floor_patterns) & set(SEEN.floor_patterns)
    assert UNSEEN.distance[0] >= SEEN.distance[1]
    assert UNSEEN.elevation[1] <= SEEN.elevation[0]
    for low, high in UNSEEN.hue_bands:
        for seen_low, seen_high in SEEN.hue_bands:
            assert high <= seen_low or low >= seen_high


def _reach(block):
    """How far the block reaches from its spot, as generously as the placement assumes."""
    if block.on_edge:
        return math.hypot(max(abs(x) for x, _ in block.outline), block.thickness / 2)
    return max(math.hypot(x, y) for x, y in block.outline)


def _distractor_reach(distractor):
    a, b, c = distractor.dimensions
    if distractor.kind == "capsule":
        return c / 2 + a  # half the straight part, plus the rounded end
    return max(a, b, c)


def test_widest_bounds_reach():
    for scene in scenes(SEEN, 50):
        for block in scene.blocks:
            if not block.on_edge:
                assert _reach(block) <= widest(list(block.outline))
