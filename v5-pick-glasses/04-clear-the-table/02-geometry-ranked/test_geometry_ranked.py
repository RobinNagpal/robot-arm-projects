"""The candidate set, the eight inputs, the ranker, and the loop it is plugged into.

Nearly everything here is arithmetic over drawn tables, so it runs in
milliseconds and needs no graphics context. The one test that builds the real
cell says so in its name, and it runs a single table.

The tables come from ``tables.table``, which draws three to five glasses across
the four families, and the glasses are read off the draw rather than out of the
simulator. None of the questions below is a question about physics: they are
about what a chooser does with a table, and a table is four numbers a glass.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from borrowed import RANKED, RANKER, candidates, features, nudge, ranker
from measure import perfect, true_table
from ranked import STILL_CROWDED, ByModel, GeometryRanked, by_rule, load_ranker, reasons

import wrist
from contract import GLASS_OVER, RAN_OUT, SAID_DONE
from open_run import clear_table
from partners import PUSHING, Felt, Record, Seen

import plan

# Every table measured on is below TEST_SEEDS. These are the first few of them,
# which between them hold three to five glasses of several families.
DRAWN = range(6)

# The reasons a chooser in this folder can give for leaving a glass. A new one
# appearing is a thing to notice, not a thing to accept quietly.
REASONS = {STILL_CROWDED, "nowhere clear to push it to", "tips before it slides"}


@pytest.fixture(scope="module")
def score():
    """Problem 3's fitted trees, loaded once for the whole file."""
    return load_ranker()


def _tables() -> list[list[Seen]]:
    return [true_table(seed) for seed in DRAWN]


def _crowded(glasses: list[Seen]) -> set[int]:
    """The glasses a chooser would be shown: the ones that do not have room already."""
    return {glass.id for glass in glasses if plan.room(glass, glasses, nudge.ROOM_MARGIN)}


# ------------------------------------------------------------- what is borrowed


def test_the_ranker_is_problem_threes_own_fitted_file_and_not_a_refit(score):
    """Nothing here fits a model, so a difference from problem 3 is the problem.

    Three halves of the same point: the file comes out of problem 3's own
    folder, this folder keeps no fitted model that could quietly be loaded
    instead, and the file was fitted on exactly the inputs problem 3's
    ``features.py`` still names.
    """
    assert RANKED == PUSHING / "02-geometry-ranked"
    assert RANKER.parent.parent == RANKED
    assert not (Path(__file__).parent / "model").exists()
    assert score.trees.n_features_in_ == features.INPUTS


def test_nothing_of_solution_ones_loop_was_written_again():
    """The port adds a chooser and inherits the rest. This is what says so.

    Every method of the geometry reference has to be the same object on this
    class. If one were copied here to change a line in the middle of it, the
    two would drift, and the comparison between the two solutions would stop
    being a comparison of their choosers.
    """
    added = {"name", "__init__", "_choose", "inputs"}
    assert {key for key in vars(GeometryRanked) if not key.startswith("__")} <= added
    for attribute in dir(nudge.OneFixedNudge):
        if attribute.startswith("__") or attribute in added:
            continue
        assert getattr(GeometryRanked, attribute) is getattr(nudge.OneFixedNudge, attribute)


# ------------------------------------------------------------ the candidate set


def test_the_chooser_really_has_something_to_choose_between():
    """A ranking over one candidate is the printed rule wearing a hat.

    So the premise of this solution is that the groups are usually wide. Not
    always: on the simplified draw a glass hemmed in on every side can leave no
    candidate at all, and that is a table about which this solution and the
    printed rule must agree, because neither has anything to pick. What the
    premise needs is that most tables leave a real choice.
    """
    widths = [len(candidates.survivors(glasses, set())[0]) for glasses in _tables()]
    choosing = [width for width in widths if width > 1]
    assert len(choosing) >= len(widths) - 1, widths
    assert max(widths) > 50, widths


def test_the_printed_rule_over_this_candidate_set_picks_what_solution_one_picks():
    """The check that this folder enumerates what the geometry reference chooses from.

    If the two disagree, ``measure.py --rule`` stops being solution 1 and the
    comparison in the README is between two different things.
    """
    for glasses in _tables():
        crowded = _crowded(glasses)
        mine, _, _ = by_rule(glasses, crowded)
        theirs, _ = plan.choose(glasses, crowded)
        assert mine == theirs


def test_the_model_only_reorders_what_the_geometry_offered(score):
    """It can never add a push, and never bring back one the geometry refused."""
    for glasses in _tables():
        kept, why = candidates.survivors(glasses, set())
        order, scores, also = ranker.ranked(glasses, set(), score)
        assert len(order) == len(kept)
        assert set(order) == set(kept)
        assert also == why
        assert list(scores) == sorted(scores, reverse=True)


# ------------------------------------------------------------------ the inputs


def test_every_input_computes_from_what_the_arms_camera_gives(score):
    """The question the port had to answer: can the eight inputs be computed here.

    Problem 3 hands its features the whole table, because its camera is above
    it. Here they are handed the table as the arm believes it, which is every
    glass it has seen so far and no more. So the inputs are computed over
    subsets of each drawn table, down to a belief of a single glass, and every
    one of them has to come out a finite number the trees can be given.
    """
    for glasses in _tables():
        for believed in _partial_looks(glasses):
            kept, _ = candidates.survivors(believed, set())
            rows = features.rows(believed, kept)
            assert rows.shape == (len(kept), features.INPUTS)
            assert np.isfinite(rows).all(), features.NAMES
            if len(kept):
                assert np.isfinite(score(rows)).all()


def _partial_looks(glasses: list[Seen]) -> list[list[Seen]]:
    """What the arm might believe after seeing part of the table.

    The whole table, the table less its first glass, and the first glass on its
    own. The last is the hard case: three of the eight inputs are about the
    neighbours, and a belief of one glass has none.
    """
    return [glasses, glasses[1:], glasses[:1]]


def test_the_inputs_are_the_eight_problem_three_fitted_on():
    assert GeometryRanked(by_rule).inputs() == features.NAMES
    assert len(features.NAMES) == features.INPUTS == 8


# ---------------------------------------------------------------- the refusals


def test_every_glass_still_worth_pushing_is_given_a_reason():
    glasses = [Seen(i, 0.5 + 0.02 * i, -0.2, 0.15, 0.08, 0.09, True) for i in range(4)]
    told = reasons(glasses, {3}, {1: "tips before it slides"})
    assert told == {0: STILL_CROWDED, 1: "tips before it slides", 2: STILL_CROWDED}


def test_a_glass_with_nowhere_to_go_is_counted_apart_from_one_pushed_too_slightly(score):
    """Problem 3's printed rule reports these two with the same words. Here they differ.

    The reasons are collected where they really arise, at the end of a table in
    the perfect world, and every glass left has exactly one of them.
    """
    for seed in DRAWN:
        table = perfect(seed, ByModel(score))
        assert set(table.why.values()) <= REASONS, table.why
        assert len(table.why) + table.with_room == table.glasses


# -------------------------------------------------------------------- the loop


def test_the_chooser_is_the_only_thing_the_loop_asks_of_this_solution():
    """A chooser that refuses everything makes the loop sweep the ring and say done.

    It is the cheapest proof that the subclass is plugged in where it was meant
    to be: nothing else in the loop had to be told which solution is running.
    """
    asked = []

    def nothing(glasses, skip):
        asked.append(len(glasses))
        return None, {}, 0

    solution = GeometryRanked(nothing)
    result = clear_table(solution, 0, 400.0, cell=_PaperTable(true_table(0)))
    assert result.ended_by == SAID_DONE
    assert asked, "the loop never reached the chooser"
    assert solution.groups == len(asked)
    assert solution.candidates == 0


def test_a_real_table_ends_one_of_the_three_ways_and_is_charged_for_moving():
    """One table on the real cell, with the physics and the camera on the arm."""
    result = clear_table(GeometryRanked(), 0, 400.0)
    assert result.ended_by in (SAID_DONE, RAN_OUT, GLASS_OVER)
    assert result.arm_seconds > 0.0
    assert 4 <= result.glasses <= 7


def test_the_perfect_world_says_whether_the_draw_can_be_separated_at_all(score):
    """With true positions and exact pushes, some tables separate and some do not.

    This is the measurement that makes the port worth having, and it is the one
    that changed the problem. On the first draw it separated none of twenty
    even here, which meant the draw was unsolvable rather than hard, and every
    solution scored zero for a reason that had nothing to do with it. On the
    simplified draw about half separate, so a table left crowded by a real
    solution is now that solution's doing rather than the draw's.

    A table it cannot separate must run out of **candidates** rather than out
    of patience, because a chooser that simply gave up early would look exactly
    the same from outside.
    """
    separable = perfect(15, ByModel(score))
    assert separable.separated, "seed 15 is separable with true positions and exact pushes"

    stubborn = perfect(16, ByModel(score))
    assert not stubborn.separated
    assert 0 < stubborn.pushes < 50, "it should run out of candidates, not out of patience"
    assert stubborn.with_room < stubborn.glasses


class _PaperTable:
    """A work cell made of arithmetic: no physics, no camera, no graphics context.

    It answers the questions ``open_run`` asks of a cell and nothing else, and
    it moves nothing: it is here so that the plumbing between this solution and
    the loop can be tested without the simulator.
    """

    def __init__(self, glasses: list[Seen]) -> None:
        self.standing = {glass.id: glass for glass in glasses}

    def glasses(self) -> int:
        return len(self.standing)

    def view(self, jaw):
        on_table = list(self.standing.values())
        return np.zeros((4, 4, 3), dtype=np.uint8), tuple(wrist.in_picture(jaw, on_table))

    def truth(self):
        return tuple(self.standing.values())

    def follow(self, chunk):
        return Record(chunk.as_push(), Felt(False, 0.0, False, 0.0, 0.0), chunk.aim, chunk.waypoints)

    def toppled(self) -> int:
        return 0

    def pickable(self) -> int:
        return 0

    def charged(self) -> float:
        return 0.0
