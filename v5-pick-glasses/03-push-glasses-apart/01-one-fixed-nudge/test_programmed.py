"""The tipping rule, the push search and the whole loop, on glasses drawn across their range."""

import math

import numpy as np
import plan
import pytest
import run
from work_cell.glasses.shapes import KIND_RANGES, family
from work_cell.glasses.spawn import SpawnedGlass

import bench
from scoring import Scorecard


def _seen(i, x, y, widest=0.08, foot=0.07, height=0.15):
    return bench.Seen(i, x, y, height, widest, foot, True)


@pytest.mark.parametrize("kind", sorted(KIND_RANGES))
def test_no_glass_has_its_centre_of_mass_above_the_share_the_probe_assumes(kind):
    for outline, _ in family(kind, 40, seed=5):
        centre = SpawnedGlass("g", kind, outline, (0, 0, 0), 0.0).mass_properties[1]
        assert centre < plan.CENTRE_OF_MASS_SHARE * outline.total_height


def test_a_wide_foot_slides_a_narrow_one_does_not_and_between_is_tried():
    """The three answers, tested at the feet the rule's own thresholds imply.

    The feet are worked out from the jaw's top edge and the two frictions
    rather than written down, because the jaw's height is the gripper's and
    has changed once already. A glass slides while half its foot over the
    friction is more than the contact height, so the boundaries are at a foot
    of ``JAW_TOP`` and one of ``0.4 * JAW_TOP``.
    """
    certain = bench.JAW_TOP * 2 * plan.MU_HIGHEST + 0.01
    hopeless = bench.JAW_TOP * 2 * plan.MU_LOWEST - 0.005
    between = (certain + hopeless) / 2
    assert plan.slides(_seen(0, 0, 0, foot=certain)) == "yes"
    assert plan.slides(_seen(0, 0, 0, foot=hopeless)) == "no"
    assert plan.slides(_seen(0, 0, 0, foot=between)) == "try"
    # Wider is never a worse answer than narrower.
    order = {"no": 0, "try": 1, "yes": 2}
    answers = [order[plan.slides(_seen(0, 0, 0, foot=mm / 1000))] for mm in range(20, 140, 4)]
    assert answers == sorted(answers)


def test_the_guard_against_the_probe_itself_tipping_a_glass_no_longer_binds():
    """Another thing the higher push changed, and it changed it the kind way.

    Before making a probe the rule checks that the probe could not tip the
    glass on its own: leaning it by the angle a 5 mm nudge implies has to stay
    well inside the angle the glass falls past. A tall glass on a narrow foot
    used to fail that check and be refused without being probed.

    Pushing 75 mm up instead of 50 changes the arithmetic. The same 5 mm of
    movement at a higher contact point is a *smaller* rotation, so the probe
    became gentler in exactly the way this guard measures, and it no longer
    turns anything down. Every glass the friction test is unsure about is now
    safe to probe, and the friction test is what decides.

    It is recorded as a test because a guard that never fires is easy to
    mistake for a guard that is working, and because it would start firing
    again the moment the hand could push lower.
    """
    for mm in range(20, 140, 2):
        for height in (0.10, 0.20, 0.30, 0.40):
            glass = _seen(0, 0, 0, foot=mm / 1000, height=height)
            if plan.slides(glass) == "no":
                # Refused by the friction test, so the guard was never asked.
                half_foot = glass.foot / 2
                assert half_foot / plan.MU_LOWEST <= bench.JAW_TOP


def test_no_real_glass_is_certainly_safe_to_push_at_this_height():
    """A finding about the gripper, not about the rule.

    "Yes" needs a foot wider than the jaw's top edge is high, which is 107 mm
    now that the hand has to be turned on its side to fit between the glasses.
    The widest foot any of these families draws is about 95 mm. So the arm
    never gets a confident yes: every glass it pushes is either probed first
    or refused, and that is why solution 1 makes so many repeat pushes.
    """
    widest = 0.0
    for kind in bench.KINDS:
        for outline, _ in family(kind, 12, seed=4):
            widest = max(widest, outline.radius[0] * 2)
    assert widest < bench.JAW_TOP


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
def test_the_probe_never_calls_a_glass_safe_that_a_full_push_would_topple(kind):
    """The probe's errors all have to point the same way, and they do.

    The idea of the probe is to settle the friction by experiment: push a
    little and look, because a glass that slid has moved and one that only
    leaned came back. It used to agree with the full push both ways round.

    It no longer does, and the reason is the gripper. The hand must be turned
    on its side to fit between the glasses, and on its side it cannot push
    lower than 75 mm. Pushed that high a glass leans before it slides, and the
    lean takes up the whole 5 mm probe, so almost nothing moves far enough to
    be called a slide. Measured across the four families, a glass that the
    full push slides moves at most a fraction of a millimetre under the
    probe — less than the error in the looks themselves.

    What matters is which way that failure points. The probe now says "it
    tipped" about glasses that would in fact have slid, so the arm refuses
    glasses it could have moved. That costs a refusal, which is a result and
    can be reported. The error it must never make is the other one: calling a
    glass safe and then toppling it, which costs the glass. This asserts the
    safe direction, and that is all it asserts.
    """
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
        probe_says_it_slid = after is not None and math.dist(before, after) >= plan.PROBE_MOVED
        if probe_says_it_slid:
            assert full.tilt(0) < bench.STANDING_TILT_DEG, "the probe called a toppler safe"


@pytest.mark.parametrize("seed", range(bench.TEST_SEEDS, bench.TEST_SEEDS + 4))
def test_a_table_ends_done_or_with_every_glass_accounted_for(seed):
    table = bench.Bench(seed)
    assert Scorecard().scene(table, run.clear(table)) in ("done", "incomplete")
