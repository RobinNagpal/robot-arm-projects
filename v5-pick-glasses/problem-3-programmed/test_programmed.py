"""The tipping rule, the push search and the whole loop, on glasses drawn across their range."""

import math

import numpy as np
import pytest
from work_cell.glasses.shapes import KIND_RANGES, family
from work_cell.glasses.spawn import SpawnedGlass

import bench
import plan
import run
from scoring import Scorecard


def _seen(i, x, y, widest=0.08, foot=0.07, height=0.15):
    return bench.Seen(i, x, y, height, widest, foot, True)


@pytest.mark.parametrize("kind", sorted(KIND_RANGES))
def test_no_glass_has_its_centre_of_mass_above_the_share_the_probe_assumes(kind):
    for outline, _ in family(kind, 40, seed=5):
        centre = SpawnedGlass("g", kind, outline, (0, 0, 0), 0.0).mass_properties[1]
        assert centre < plan.CENTRE_OF_MASS_SHARE * outline.total_height


def test_a_wide_foot_slides_a_narrow_one_does_not_and_between_is_tried():
    assert plan.slides(_seen(0, 0, 0, foot=0.08)) == "yes"
    assert plan.slides(_seen(0, 0, 0, foot=0.02)) == "no"
    assert plan.slides(_seen(0, 0, 0, foot=0.05)) == "try"
    # A tall glass on the same foot may lean too far to probe safely.
    assert plan.slides(_seen(0, 0, 0, foot=0.032, height=0.4)) == "no"


def test_a_crowded_pair_gets_a_push_that_frees_one_and_moves_it_away():
    a, b = _seen(0, 0.46, -0.26), _seen(1, 0.46, -0.16)
    push, why = plan.choose([a, b], set())
    assert push is not None and not why
    moved = next(g for g in (a, b) if g.id == push.glass)
    other = b if moved is a else a
    assert bench.has_room(*push.aim, [(other.x, other.y, other.widest)])
    assert math.dist(push.aim, (other.x, other.y)) > math.dist((moved.x, moved.y), (other.x, other.y))


def test_no_push_leaves_the_zone_or_brings_a_glass_closer_to_a_neighbour():
    seen = bench.Bench(bench.TEST_SEEDS + 3).look()
    for glass in seen:
        others = [o for o in seen if o.id != glass.id]
        for heading in np.arange(plan.HEADINGS) * (2 * math.pi / plan.HEADINGS):
            for push in plan.along(glass, others, heading):
                assert bench.in_zone(*push.aim)
                for other in others:
                    before = math.dist((glass.x, glass.y), (other.x, other.y))
                    assert math.dist(push.aim, (other.x, other.y)) >= min(before - 0.001, 0.0)


def test_the_shortfall_is_zero_only_when_every_glass_has_room():
    apart = [(0.40, -0.40, 0.08), (0.60, -0.10, 0.08)]
    close = [(0.40, -0.40, 0.08), (0.50, -0.40, 0.08)]
    assert plan.shortfall(apart) == 0.0
    assert plan.shortfall(close) == pytest.approx(2 * (bench.GRIP_ROOM + 0.04 - 0.10))


@pytest.mark.parametrize("kind", bench.KINDS)
def test_a_probe_agrees_with_what_a_full_push_does(kind):
    for outline, _ in family(kind, 3, seed=9):
        glass = SpawnedGlass("glass_0", kind, outline, (0.48, -0.26, bench.TABLE_TOP_Z), 0.0)
        tried, full = bench.Bench(0, [glass]), bench.Bench(0, [glass])
        seen = tried.look()[0]
        push = bench.Push(
            0, (seen.x - seen.widest / 2 - 0.01, seen.y), 0.0, seen.widest / 2 + 0.04, 0.03, (0, 0)
        )
        before = run.where(tried, 0)
        tried.push(plan.probe(push))
        after = run.where(tried, 0)
        full.push(push)
        slid = full.tilt(0) < bench.STANDING_TILT_DEG
        assert (after is not None and math.dist(before, after) >= plan.PROBE_MOVED) == slid


@pytest.mark.parametrize("seed", range(bench.TEST_SEEDS, bench.TEST_SEEDS + 4))
def test_a_table_ends_done_or_with_every_glass_accounted_for(seed):
    table = bench.Bench(seed)
    assert Scorecard().scene(table, run.clear(table)) in ("done", "incomplete")
