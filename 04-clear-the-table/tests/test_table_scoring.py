"""Tests for problem 4's end-state scorecard.

Two kinds of test, because the card has two halves. The counting is checked
against ``ScoredTable``s built here, so that a number can be made exactly what
the test is about. The pickable rule is checked against real drawn glasses —
families of them, never one example — because a rule about room that works on
one glass and fails on a differently proportioned one is the failure this
project exists to prevent.

Nothing here runs a solution or a push. A few of problem 3's tables are built
in the physics engine, which costs hundredths of a second each, and no physics
is stepped beyond the settling the examiner does when it opens.
"""

from __future__ import annotations

import random

import pytest
from work_cell.glasses.shapes import family
from work_cell.glasses.spec import LIBRARY
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

from examiner.examining import table_scoring
from examiner.examining.table_scoring import GLASS_OVER, RAN_OUT, SAID_DONE, ScoredTable
from examiner.simulation.table_simulator import Simulator
from examiner.simulation.taken_from_problem_3 import (
    GRIP_ROOM,
    STANDING_TILT_DEG,
    TEST_SEEDS,
    SpawnedGlass,
    in_zone,
)

KINDS = sorted(LIBRARY)
# Eight tables is every kind twice and every glass count, and still fast.
SEEDS = range(TEST_SEEDS, TEST_SEEDS + 8)
# The table top, the one the common examiner stands every glass on.
TABLE_TOP = TABLE_TOP_Z
# Four spots well inside the glass zone, one near each corner.
CORNERS = [(x, y) for x in (0.38, 0.58) for y in (-0.38, -0.14)]


def test_the_scoring_under_test_is_problem_fours() -> None:
    """A guard, because problem 3 has a module of the same name.

    If the path ever puts problem 3's examiner first, every test below would pass
    while measuring problem 3's push-by-push scorecard instead of this one.
    """
    assert "04-clear-the-table" in table_scoring.__file__


# ------------------------------------------------------------------ the counting


def result(
    seed: int = 0,
    glasses: int = 5,
    pickable_at_start: int = 2,
    pickable_at_end: int = 5,
    toppled: int = 0,
    ended_by: str = SAID_DONE,
    arm_seconds: float = 30.0,
    thinking_seconds: float = 0.5,
    answers: int = 6,
) -> ScoredTable:
    return ScoredTable(
        seed=seed,
        glasses=glasses,
        pickable_at_start=pickable_at_start,
        pickable_at_end=pickable_at_end,
        toppled=toppled,
        ended_by=ended_by,
        arm_seconds=arm_seconds,
        thinking_seconds=thinking_seconds,
        answers=answers,
    )


def a_family_of_tables() -> list[ScoredTable]:
    """One table of every shape the examiner can hand over: clean, broken, crowded."""
    rng = random.Random(7)
    rows = []
    for seed in SEEDS:
        glasses = 4 + seed % 4
        broken = seed % 5 == 0
        rows.append(
            result(
                seed=seed,
                glasses=glasses,
                pickable_at_start=rng.randint(1, glasses - 1),
                pickable_at_end=rng.randint(1, glasses),
                toppled=1 if broken else 0,
                ended_by=GLASS_OVER if broken else SAID_DONE if seed % 3 else RAN_OUT,
                arm_seconds=10.0 + seed % 11,
                thinking_seconds=0.1 * (seed % 7),
                answers=2 + seed % 9,
            )
        )
    return rows


def a_card(rows: list[ScoredTable]) -> table_scoring.Scorecard:
    card = table_scoring.Scorecard()
    for row in rows:
        card.table(row)
    return card


@pytest.mark.parametrize("glasses", [4, 5, 6, 7])
@pytest.mark.parametrize("toppled", [0, 1, 2])
def test_every_table_gets_exactly_one_of_the_three_outcomes(glasses: int, toppled: int) -> None:
    for pickable_at_end in range(glasses + 1):
        row = result(glasses=glasses, pickable_at_end=pickable_at_end, toppled=toppled)
        named = table_scoring.outcome(row)
        assert [row.separated, row.failed, row.unfinished].count(True) == 1
        assert named == ("failed" if toppled else "separated" if pickable_at_end == glasses else "unfinished")


@pytest.mark.parametrize("glasses", [4, 5, 6, 7])
def test_a_broken_glass_fails_the_table_however_much_room_the_rest_have(glasses: int) -> None:
    rows = [result(glasses=glasses, pickable_at_end=p, toppled=1) for p in range(glasses + 1)]
    summary = a_card(rows).summary()
    assert summary["outcome"] == {"separated": 0, "failed": glasses + 1, "unfinished": 0}
    assert summary["glasses_end"]["broken"] == glasses + 1


@pytest.mark.parametrize("glasses", [4, 5, 6, 7])
def test_a_table_that_lost_a_glass_pays_no_partial_credit(glasses: int) -> None:
    """A risky shove must not be profitable, so a failed table counts nothing.

    The table's glasses still count against the share, which is what makes
    breaking one worse than leaving the table alone.
    """
    clean = result(seed=1, glasses=glasses, pickable_at_start=1, pickable_at_end=glasses - 1)
    broken = result(seed=2, glasses=glasses, pickable_at_start=1, pickable_at_end=glasses, toppled=1)
    one = a_card([clean]).summary()
    both = a_card([clean, broken]).summary()
    assert both["glasses_end"]["pickable"] == one["glasses_end"]["pickable"]
    assert both["glasses_end"]["gain"] == one["glasses_end"]["gain"]
    assert both["glasses"] == 2 * glasses
    assert both["glasses_end"]["pickable_share"] < one["glasses_end"]["pickable_share"]


def test_the_totals_are_the_sums_of_the_tables() -> None:
    rows = a_family_of_tables()
    clean = [r for r in rows if not r.failed]
    summary = a_card(rows).summary()
    assert summary["tables_attempted"] == len(rows)
    assert summary["glasses"] == sum(r.glasses for r in rows)
    assert summary["glasses_end"]["pickable"] == sum(r.pickable_at_end for r in clean)
    assert summary["glasses_end"]["pickable_at_start"] == sum(r.pickable_at_start for r in clean)
    assert summary["answers"] == sum(r.answers for r in rows)
    assert summary["arm_seconds"]["total"] == pytest.approx(sum(r.arm_seconds for r in rows))
    assert sum(summary["outcome"].values()) == len(rows)
    assert sum(summary["ended_by"].values()) == len(rows)
    assert summary["ended_by"]["glass_over"] == summary["outcome"]["failed"]


def test_credit_by_the_glass_tells_apart_two_solutions_that_separate_no_table() -> None:
    """The reason the glass count is reported at all.

    One solution leaves a single glass touching on every table; the other never
    moves the arm. Neither separates a table, so a card that counted only
    tables would call them equal.
    """
    idle, nearly = [], []
    for seed in SEEDS:
        glasses = 4 + seed % 4
        start = 1 + seed % 2
        idle.append(result(seed=seed, glasses=glasses, pickable_at_start=start, pickable_at_end=start))
        nearly.append(
            result(seed=seed, glasses=glasses, pickable_at_start=start, pickable_at_end=glasses - 1)
        )
    left, right = a_card(idle).summary(), a_card(nearly).summary()
    assert left["outcome"]["separated"] == right["outcome"]["separated"] == 0
    assert right["glasses_end"]["pickable"] > left["glasses_end"]["pickable"]
    assert right["glasses_end"]["pickable_share"] > left["glasses_end"]["pickable_share"]
    assert left["glasses_end"]["gain"] == 0
    assert right["glasses_end"]["gain"] > 0


def test_pushing_a_glass_into_its_neighbour_is_reported_as_a_loss() -> None:
    rows = [result(seed=s, glasses=5, pickable_at_start=3, pickable_at_end=1) for s in SEEDS]
    assert a_card(rows).summary()["glasses_end"]["gain"] == -2 * len(SEEDS)


def test_the_arm_time_reported_is_the_mean_over_the_tables_that_succeeded() -> None:
    rows = [
        result(seed=1, glasses=4, pickable_at_end=4, arm_seconds=20.0),
        result(seed=2, glasses=4, pickable_at_end=4, arm_seconds=40.0),
        result(seed=3, glasses=4, pickable_at_end=1, arm_seconds=900.0),
        result(seed=4, glasses=4, pickable_at_end=4, toppled=1, arm_seconds=900.0),
    ]
    summary = a_card(rows).summary()
    assert summary["arm_seconds"]["separated_mean"] == pytest.approx(30.0)
    assert summary["arm_seconds"]["total"] == pytest.approx(1860.0)


def test_with_no_table_separated_the_mean_arm_time_is_absent_rather_than_zero() -> None:
    rows = [result(seed=s, glasses=5, pickable_at_end=2) for s in SEEDS]
    assert "separated_mean" not in a_card(rows).summary()["arm_seconds"]


def test_an_empty_run_reports_zeros_and_no_means() -> None:
    summary = table_scoring.Scorecard().summary()
    assert summary["tables_attempted"] == 0
    assert summary["glasses_end"]["pickable_share"] == 0.0
    assert "separated_mean" not in summary["arm_seconds"]
    assert "thinking_seconds_per_answer" not in summary


def test_how_a_table_ended_is_kept_apart_from_what_was_left_on_it() -> None:
    rows = [
        result(seed=1, glasses=4, pickable_at_end=4, ended_by=SAID_DONE),
        result(seed=2, glasses=4, pickable_at_end=2, ended_by=SAID_DONE),
        result(seed=3, glasses=4, pickable_at_end=2, ended_by=RAN_OUT),
        result(seed=4, glasses=4, pickable_at_end=3, toppled=1, ended_by=GLASS_OVER),
    ]
    summary = a_card(rows).summary()
    assert summary["ended_by"] == {"said_done": 2, "ran_out": 1, "glass_over": 1}
    assert summary["said_done_while_crowded"] == 1
    assert summary["outcome"] == {"separated": 1, "failed": 1, "unfinished": 2}


def test_a_glass_going_over_is_not_counted_as_not_knowing_when_to_stop() -> None:
    rows = [result(seed=s, glasses=4, pickable_at_end=2, toppled=1, ended_by=GLASS_OVER) for s in SEEDS]
    summary = a_card(rows).summary()
    assert summary["ended_by"]["said_done"] == 0
    assert summary["ended_by"]["ran_out"] == 0
    assert summary["said_done_while_crowded"] == 0


def test_thinking_is_reported_per_answer() -> None:
    rows = [result(seed=s, thinking_seconds=1.0, answers=4) for s in SEEDS]
    summary = a_card(rows).summary()
    assert summary["thinking_seconds"] == pytest.approx(len(SEEDS))
    assert summary["thinking_seconds_per_answer"] == pytest.approx(0.25)


def test_one_row_per_table_is_kept_in_the_order_they_were_attempted() -> None:
    rows = a_family_of_tables()
    kept = a_card(rows).tables
    assert [row["seed"] for row in kept] == [r.seed for r in rows]
    assert [row["outcome"] for row in kept] == [table_scoring.outcome(r) for r in rows]
    assert [row["ended_by"] for row in kept] == [r.ended_by for r in rows]


# ---------------------------------------------------------------- several runs


def test_the_spread_across_runs_is_problem_threes_own() -> None:
    runs = table_scoring.Repeats()
    for pickable_at_end in (2, 3, 4):
        card = runs.run()
        for seed in SEEDS:
            card.table(result(seed=seed, glasses=4, pickable_at_end=pickable_at_end))
    summary = runs.summary()
    assert summary["runs"] == 3
    assert summary["spread"]["glasses_end.pickable"] == {
        "median": 3.0 * len(SEEDS),
        "sd": pytest.approx(float(len(SEEDS)), rel=1e-3),
        "least": 2.0 * len(SEEDS),
        "most": 4.0 * len(SEEDS),
    }
    # One run separated its tables and the others did not, so the mean arm time
    # of a separated table is not a number the three runs share.
    assert "arm_seconds.separated_mean" not in summary["spread"]
    assert len(summary["each"]) == 3


def test_the_spread_is_borrowed_and_not_rewritten() -> None:
    import common_scoring

    assert table_scoring.spread is common_scoring.spread


# ------------------------------------------------------- the rule about room


class Table:
    """A table the scorer can read, for the cases a pose has to be chosen.

    A glass cannot be spawned lying on its side, because ``SpawnedGlass`` takes
    only a yaw, so the one way to ask the scorer about a glass that has gone
    over is to hand it the three things it reads: where each glass stands, how
    far it leans, and how wide it really is. The glasses themselves are real
    drawn ones, and the test below checks that a real examiner is read the same way
    through this stand-in.
    """

    def __init__(self, widths: list[float], spots: list[tuple[float, float]], tilts: list[float]) -> None:
        self.glasses = [_AsWide(width) for width in widths]
        self.spots = spots
        self.tilts = tilts

    def on_table(self) -> list[int]:
        return list(range(len(self.glasses)))

    def position(self, glass: int) -> tuple[float, float]:
        return self.spots[glass]

    def tilt(self, glass: int) -> float:
        return self.tilts[glass]


class _AsWide:
    """Stands in for a spawned glass, which the scorer only asks for a width."""

    def __init__(self, width: float) -> None:
        self.outline = type("Outline", (), {"max_diameter": width})()


def standing(widths: list[float], spots: list[tuple[float, float]]) -> Table:
    return Table(widths, spots, [0.0] * len(widths))


def groups_of(kind: str, size: int) -> list[list[float]]:
    """The widest widths of a family of forty glasses, in groups of ``size``."""
    widths = [outline.max_diameter for outline, _ in family(kind, 40, seed=3)]
    return [widths[i : i + size] for i in range(0, len(widths) - size + 1, size)]


def test_a_real_table_is_read_the_same_way_through_the_stand_in() -> None:
    """Ties the stand-in above to the examiner, so the tests that use it mean something."""
    for seed in SEEDS:
        simulator = Simulator(seed)
        on = simulator.on_table()
        stand_in = standing(
            [simulator.glasses[i].outline.max_diameter for i in on],
            [tuple(float(v) for v in simulator.position(i)) for i in on],
        )
        assert table_scoring.pickable_on_table(stand_in) == table_scoring.pickable_on_table(simulator)


def test_a_table_drawn_crowded_has_a_glass_that_cannot_be_picked() -> None:
    """Every table problem 4 draws has at least one glass without room."""
    for seed in SEEDS:
        simulator = Simulator(seed)
        assert 0 <= table_scoring.pickable_on_table(simulator) < len(simulator.on_table())


@pytest.mark.parametrize("kind", KINDS)
def test_glasses_set_far_apart_can_all_be_picked_and_touching_ones_cannot(kind: str) -> None:
    """A family of forty glasses of one kind, at two spacings inside the zone."""
    for four in groups_of(kind, 4):
        roomy = standing(four, CORNERS)
        assert table_scoring.pickable_on_table(roomy) == len(four)

    for three in groups_of(kind, 3):
        # Rim to rim, which is the closest the draw ever puts two glasses.
        at, spots = GLASS_ZONE[0] + max(three), []
        for i, width in enumerate(three):
            spots.append((at, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2))
            at += (width + three[min(i + 1, len(three) - 1)]) / 2
        assert all(in_zone(*spot) for spot in spots), "the row has to fit in the zone to mean anything"
        assert table_scoring.pickable_on_table(standing(three, spots)) == 0


def test_room_is_not_symmetric_between_a_narrow_glass_and_a_wide_one() -> None:
    """The narrow one is crowded first, because room is measured to the other's edge.

    Each pair is drawn from a family, so this is a rule about proportions and
    not about two remembered glasses.
    """
    checked = 0
    for kind in KINDS:
        widths = sorted(outline.max_diameter for outline, _ in family(kind, 40, seed=5))
        narrow, wide = widths[0], widths[-1]
        if wide - narrow < 0.004:
            continue
        # Inside the wide glass's reach and outside the narrow one's: halfway
        # between the two distances, which differ by half the width difference.
        gap = GRIP_ROOM + (narrow + wide) / 4
        pair = standing([narrow, wide], [(0.48, -0.26 - gap / 2), (0.48, -0.26 + gap / 2)])
        assert not table_scoring.pickable(pair, 0)
        assert table_scoring.pickable(pair, 1)
        assert table_scoring.pickable_on_table(pair) == 1
        checked += 1
    assert checked, "no kind drew a wide enough spread of glasses to test with"


@pytest.mark.parametrize("kind", KINDS)
def test_a_glass_that_went_over_cannot_be_picked_and_still_blocks_its_neighbour(kind: str) -> None:
    for pair in groups_of(kind, 2):
        # Far enough apart that both would be pickable standing up.
        spots = [CORNERS[0], CORNERS[1]]
        assert table_scoring.pickable_on_table(standing(pair, spots)) == 2
        over = Table(pair, spots, [0.0, STANDING_TILT_DEG + 1.0])
        assert not table_scoring.pickable(over, 1)
        assert table_scoring.pickable_on_table(over) == 1

        # Lying where it would crowd its neighbour, it is in the way as much as
        # a standing glass is, so neither glass can be picked.
        close = [CORNERS[0], (CORNERS[0][0] + max(pair) / 2, CORNERS[0][1])]
        assert table_scoring.pickable_on_table(Table(pair, close, [0.0, 90.0])) == 0


@pytest.mark.parametrize("kind", KINDS)
def test_a_glass_shoved_out_of_the_zone_is_not_pickable(kind: str) -> None:
    """It needs no column of its own, and it is not a breakage either."""
    for pair in groups_of(kind, 2):
        outside = (GLASS_ZONE[1] + 0.02, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2)
        assert not in_zone(*outside)
        table = standing(pair, [CORNERS[0], outside])
        assert table_scoring.pickable(table, 0)
        assert not table_scoring.pickable(table, 1)
        assert table_scoring.pickable_on_table(table) == 1


def test_asking_for_more_room_never_finds_more_glasses_with_room() -> None:
    for seed in SEEDS:
        simulator = Simulator(seed)
        # Half a metre is more than the glass zone is across, so at that margin
        # no glass on any table has room, however far apart the draw stood it.
        margins = (0.0, 0.005, 0.02, 0.1, 0.5)
        counts = [table_scoring.pickable_on_table(simulator, margin) for margin in margins]
        assert counts == sorted(counts, reverse=True)
        assert counts[-1] == 0


def test_one_glass_on_its_own_in_the_zone_can_always_be_picked() -> None:
    """A family of forty of each kind, each glass alone on a real table."""
    for kind in KINDS:
        for outline, _ in family(kind, 40, seed=11)[:4]:
            glass = SpawnedGlass("glass_0", kind, outline, (0.48, -0.26, TABLE_TOP), 0.0)
            assert table_scoring.pickable_on_table(Simulator(0, [glass])) == 1
