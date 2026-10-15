"""Checks for the learned solution: the encoding, the search, and one whole table.

Everything here runs against families of tables rather than one example, which
is this project's rule and is more than a habit for a learned solution. A model
is fitted to whatever it was shown, so a check that passes on one table says
nothing at all; and the draw itself changed once already, from four to seven
glasses down to three to five.

Nothing here needs a trained model. The two that need a model at all use either
copies at their starting weights or a model made to answer a fixed way, which
is the only way to check that the search drops a push for the reason it says it
does.
"""

from __future__ import annotations

import math

import collect
import encoding
import learned
import numpy as np
import pytest
import search
from borrowed import jaw_paths
from push_model import Ensemble, PushNet
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE

import tables
from open_run import HOME, clear_table, open_cell
from partners import PUSH_HEIGHT, TRAVEL_HEIGHT, Seen, in_zone

import plan

# Enough tables to cross the draw's compositions, kinds and counts, and few
# enough to stay a quick check.
FAMILY = range(40)


def as_seen(seed: int) -> list[Seen]:
    """Table ``seed`` as a perfect look at it would read, which is what the cell's own truth is."""
    return [
        Seen(
            id=i,
            x=glass.position[0],
            y=glass.position[1],
            height=glass.outline.total_height,
            widest=glass.outline.max_diameter,
            foot=2 * float(glass.outline.radius[0]),
            standing=True,
        )
        for i, glass in enumerate(tables.table(seed))
    ]


class Fixed:
    """A model that answers the same way whatever it is asked.

    It stands in for a trained one wherever the question is what the search
    does with an answer rather than what the answer should be.
    """

    def __init__(self, along: float = 0.0, across: float = 0.0, topple: float = -12.0) -> None:
        self.along, self.across, self.topple = along, across, topple

    def predict(self, x: np.ndarray) -> np.ndarray:
        out = np.zeros((1, len(x), encoding.OUTPUTS), dtype=np.float32)
        out[:, :, 0] = self.along / encoding.MOVE_SCALE
        out[:, :, 1] = self.across / encoding.MOVE_SCALE
        out[:, :, encoding.TOPPLED] = self.topple
        return out


# ------------------------------------------------------------------ the measure


@pytest.mark.parametrize("seed", FAMILY)
def test_shortfall_is_the_references_own(seed: int) -> None:
    """The search optimises the same crowding the geometry reference eases."""
    seen = as_seen(seed)
    xy = np.array([[glass.x, glass.y] for glass in seen])
    widest = np.array([glass.widest for glass in seen])
    mine = float(search.shortfall(xy, widest))
    theirs = plan.shortfall([(glass.x, glass.y, glass.widest) for glass in seen])
    assert mine == pytest.approx(theirs, abs=1e-12)


def test_shortfall_takes_a_stack_of_tables_at_once() -> None:
    """One table at a time and a hundred at a time have to give the same answers."""
    seen = as_seen(3)
    widest = np.array([glass.widest for glass in seen])
    rng = np.random.default_rng(0)
    stack = np.array([[glass.x, glass.y] for glass in seen]) + rng.normal(0.0, 0.02, (100, len(seen), 2))
    together = search.shortfall(stack, widest)
    assert together.shape == (100,)
    for i in range(0, 100, 17):
        assert together[i] == pytest.approx(float(search.shortfall(stack[i], widest)))


def test_in_zone_agrees_with_the_cell() -> None:
    """The vectorised zone test is the cell's own, so it cannot be allowed to drift."""
    points = np.array([(x, y) for x in np.linspace(0.2, 0.8, 25) for y in np.linspace(-0.6, 0.1, 25)])
    mine = search.in_zone(points, margin=0.0)
    theirs = np.array([in_zone(x, y) for x, y in points])
    assert (mine == theirs).all()
    # With a margin it can only ever be stricter.
    assert not (search.in_zone(points) & ~theirs).any()


# ----------------------------------------------------------------- the encoding


@pytest.mark.parametrize("seed", FAMILY)
def test_a_push_reads_the_same_whichever_way_the_table_faces(seed: int) -> None:
    """The point of the push's own frame: a push north and the same push east are one example.

    The table is turned about the pushed glass and the push turned with it, and
    the row the model is shown must not change. If it did, every example would
    have to be collected in every direction.
    """
    seen = as_seen(seed)
    target = seen[0]
    turn = 0.7
    spun = [
        Seen(
            id=glass.id,
            x=target.x + math.cos(turn) * (glass.x - target.x) - math.sin(turn) * (glass.y - target.y),
            y=target.y + math.sin(turn) * (glass.x - target.x) + math.cos(turn) * (glass.y - target.y),
            height=glass.height,
            widest=glass.widest,
            foot=glass.foot,
            standing=glass.standing,
        )
        for glass in seen
    ]
    plain = encoding.encode(seen, target, [0.3], [0.004], [0.05], [0.02])
    turned = encoding.encode(spun, spun[0], [0.3 + turn], [0.004], [0.05], [0.02])
    assert np.allclose(plain, turned, atol=1e-5)


@pytest.mark.parametrize("seed", FAMILY)
def test_the_mirror_is_a_mirror(seed: int) -> None:
    """Twice mirrored is the original, and only the sideways numbers change."""
    seen = as_seen(seed)
    x = encoding.encode(seen, seen[0], [0.3], [0.004], [0.05], [0.02])
    y = np.zeros((1, encoding.OUTPUTS), dtype=np.float32)
    y[0, : encoding.MOVES] = np.arange(encoding.MOVES)
    y[0, encoding.TOPPLED] = 1.0
    once = encoding.mirror(x, y)
    twice = encoding.mirror(*once)
    assert np.allclose(twice[0], x) and np.allclose(twice[1], y)
    # Which slots hold a glass does not change in a mirror, and nor does
    # whether something went over.
    assert (encoding.present(once[0]) == encoding.present(x)).all()
    assert once[1][0, encoding.TOPPLED] == y[0, encoding.TOPPLED]
    assert once[0][0, 3] == pytest.approx(-x[0, 3])


@pytest.mark.parametrize("seed", FAMILY)
def test_a_glass_not_seen_again_carries_no_label(seed: int) -> None:
    """A missing glass is a missing label, not a label of nothing moving."""
    seen = as_seen(seed)
    target = seen[0]
    others = encoding.others_of(seen, target)
    after = {glass.id: glass for glass in [target, *others[1:]]}
    row, mask = encoding.outcome(seen, after, target, heading=0.0, toppled=False)
    assert mask[0] == 1.0 and mask[1] == 1.0  # the pushed glass was measured
    assert mask[2] == 0.0 and mask[3] == 0.0  # its nearest neighbour was not
    assert row[2] == 0.0 and row[3] == 0.0
    # Toppling is always known, because a glass going over ends the table.
    assert mask[encoding.TOPPLED] == 1.0
    for slot in range(len(others) + 1, encoding.OTHERS + 1):
        assert mask[2 * slot] == 0.0


# ------------------------------------------------------------------- the search


@pytest.mark.parametrize("seed", FAMILY)
def test_the_reach_never_passes_the_references_lean_bound(seed: int) -> None:
    """How deep the fingertips may go is the reference's bound and not the search's.

    This is the one piece of written-down physics the solution keeps, and a
    search that drew outside it would be reaching into leaning glasses.
    """
    for glass in as_seen(seed):
        low, high = search.bounds(glass)
        assert low[3] == pytest.approx(plan.APPROACH_GAP)
        assert high[3] <= search.deepest(glass) + 1e-12
        assert low[0] == pytest.approx(-math.pi) and high[0] == pytest.approx(math.pi)
        assert abs(low[1]) <= glass.widest / 2 and abs(high[1]) <= glass.widest / 2


@pytest.mark.parametrize("seed", range(8))
def test_a_model_that_sees_a_topple_everywhere_stops_every_push(seed: int) -> None:
    """The one refusal that has to work. A table where nothing is safe gets no push."""
    seen = as_seen(seed)
    rng = np.random.default_rng(seed)
    verdict = search.best_push(Fixed(along=0.03, topple=12.0), seen, seen[0], rng)
    assert verdict.choice is None
    assert "tip" in verdict.reason


@pytest.mark.parametrize("seed", range(8))
def test_a_safe_model_is_believed_and_the_push_is_on_the_map(seed: int) -> None:
    """A push the search returns has to be one the cell could carry out."""
    seen = as_seen(seed)
    rng = np.random.default_rng(seed)
    # A model that says the glass goes where it is pushed and nothing tips.
    verdict = search.best_push(Fixed(along=0.04, topple=-12.0), seen, seen[0], rng)
    assert verdict.choice is not None, verdict.reason
    choice = verdict.choice
    low, high = search.bounds(seen[0])
    for i, value in enumerate((choice.heading, choice.offset, choice.travel, choice.reach)):
        assert low[i] - 1e-9 <= value <= high[i] + 1e-9
    assert search.in_zone(np.array(choice.aim)).all()


@pytest.mark.parametrize("seed", range(8))
def test_the_push_the_search_returns_is_one_the_cell_would_carry_out(seed: int) -> None:
    """Every waypoint on the table and inside the heights the jaw rides at.

    ``follow()`` refuses a path that breaks either, and a refused path is the
    worst answer a solution can give: the arm does not move, so nothing is
    learned and nothing is charged, and one of that glass's tries is gone.
    """
    seen = as_seen(seed)
    verdict = search.best_push(Fixed(along=0.04, topple=-12.0), seen, seen[0], np.random.default_rng(seed))
    assert verdict.choice is not None, verdict.reason
    target, choice = seen[0], verdict.choice
    push = encoding.push_of(target, choice.heading, choice.offset, choice.travel, choice.aim)
    for point in jaw_paths.to_push(HOME, push, choice.reach).waypoints:
        assert PUSH_HEIGHT - 1e-9 <= point.z <= TRAVEL_HEIGHT + 1e-9
        assert abs(point.x - TABLE_CENTRE_XY[0]) <= TABLE_SIZE[0] / 2
        assert abs(point.y - TABLE_CENTRE_XY[1]) <= TABLE_SIZE[1] / 2


@pytest.mark.parametrize("seed", range(8))
def test_a_model_that_promises_the_moon_is_not_believed(seed: int) -> None:
    """A movement far longer than the push is the model answering outside what it saw."""
    seen = as_seen(seed)
    rng = np.random.default_rng(seed)
    verdict = search.best_push(Fixed(along=0.9, topple=-12.0), seen, seen[0], rng)
    assert verdict.choice is None


@pytest.mark.parametrize("seed", range(8))
def test_the_predicted_table_moves_the_pushed_glass_where_the_aim_says(seed: int) -> None:
    """What a solution believes without looking has to agree with what it aimed at."""
    seen = as_seen(seed)
    rng = np.random.default_rng(seed)
    model = Fixed(along=0.03, topple=-12.0)
    verdict = search.best_push(model, seen, seen[0], rng)
    assert verdict.choice is not None, verdict.reason
    places = search.predicted_table(model, seen, seen[0], verdict.choice)
    assert set(places) <= {glass.id for glass in seen}
    assert places[seen[0].id][0] == pytest.approx(verdict.choice.aim[0], abs=1e-6)
    assert places[seen[0].id][1] == pytest.approx(verdict.choice.aim[1], abs=1e-6)


# ------------------------------------------------------------------- the solution


def test_the_model_loads_and_answers_the_shape_the_search_expects() -> None:
    """Three copies in, three answers out, of the width the encoding says."""
    model = Ensemble([PushNet() for _ in range(2)])
    rows = np.zeros((7, encoding.INPUTS), dtype=np.float32)
    out = model.predict(rows)
    assert out.shape == (2, 7, encoding.OUTPUTS)


@pytest.mark.parametrize("predicting", [False, True])
def test_a_whole_table_runs_both_ways(predicting: bool) -> None:
    """The loop ends, says why, and breaks nothing, with a model that knows nothing.

    Copies at their starting weights disagree about everything, so the search
    refuses nearly every push. That is the right thing for an untrained model to
    do, and what is being checked here is that the loop still ends and still
    declares itself rather than running until the clock stops it.
    """
    solution = learned.WorldModel(Ensemble.untrained(), predicting=predicting)
    result = clear_table(solution, 0, 400.0, cell=collect.blind_cell(0))
    assert result.toppled == 0
    assert result.said_done
    assert solution.look_seconds > 0.0


def test_collecting_sees_the_same_table_as_the_rendered_cell() -> None:
    """Collecting renders no pictures, so it has to be shown the same glasses.

    What a look catches is ``wrist.in_picture``, which is geometry; the picture
    beside it is for solutions that work from pixels, and this one does not. If
    that ever stopped being true, collecting would be training the model on a
    different table from the one it runs on.
    """
    blind = clear_table(learned.WorldModel(Ensemble.untrained()), 1, 400.0, cell=collect.blind_cell(1))
    rendered = clear_table(learned.WorldModel(Ensemble.untrained()), 1, 400.0, cell=open_cell(1))
    assert blind.answers == rendered.answers
    assert blind.arm_seconds == pytest.approx(rendered.arm_seconds)
    assert blind.pickable_at_end == rendered.pickable_at_end


@pytest.mark.parametrize("seed", range(2000, 2008))
def test_a_collecting_table_stops_when_it_has_had_its_pushes(seed: int) -> None:
    """A table gives up to its share of pushes and no more.

    This is checked because it was once wrong, and in a way nothing else would
    have caught. The limit was held in a field called ``pushes``, which is the
    name the reference keeps its own running count of pushes under, so the
    limit and the count chased each other upwards and a table that did not
    topple a glass ran for two hundred pushes. The data it collected was still
    true; it was just nearly all from the few tables nothing fell over on.
    """
    examples, _arm, _toppled = collect.table(seed)
    assert len(examples) <= collect.PUSHES_PER_TABLE


def test_collecting_one_table_labels_what_it_saw() -> None:
    """Every example that survives collection has to carry labels and a mask."""
    examples, arm_seconds, _toppled = collect.table(1000)
    assert examples, "a collecting table that produced nothing would train on nothing"
    assert arm_seconds > 0.0, "driving round to look and then pushing cannot be free"
    for example in examples:
        assert example.inputs.shape == (encoding.INPUTS,)
        assert example.outputs.shape == (encoding.OUTPUTS,)
        assert example.mask[encoding.TOPPLED] == 1.0
        # Nothing is learned where nothing was measured.
        assert np.all(example.outputs[example.mask == encoding.MASKED] == 0.0)
