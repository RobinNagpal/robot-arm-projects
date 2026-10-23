"""Problem 4's draw, checked on families of tables rather than on one table.

Every promise in ``table_draw.py``'s docstring is a promise about *all* the tables,
so each one is asserted over a run of seeds from both bands -- the low seeds a
solution may train on and the high ones it is scored on. A draw that kept its
promises on seed 0 and broke them on seed 43 would be the worse failure of the
two, because the scores would still come out looking reasonable.

Nothing here steps the physics. The draw is arithmetic on points and widths,
and the one test that touches the examiner only builds the world to show that the
glasses can be stood up in it.
"""

import math

import pytest

from examiner.simulation import table_draw
from examiner.simulation.table_simulator import Simulator
from examiner.simulation.taken_from_problem_3 import GRIP_ROOM, TEST_SEEDS, SpawnedGlass, has_room, in_zone

# A dozen tables from each band. Enough to parametrize without the output
# becoming a wall of test names.
SEEDS = [*range(12), *range(TEST_SEEDS, TEST_SEEDS + 12)]
# For the counts that only mean something in bulk: that nothing about a table
# is constant, and that every kind and every composition really comes up.
MANY = range(200)


def _spots(glasses: list[SpawnedGlass]) -> list[tuple[float, float, float]]:
    return [(g.position[0], g.position[1], g.outline.max_diameter) for g in glasses]


def _crowded(spots: list[tuple[float, float, float]]) -> list[int]:
    return [
        i
        for i, (x, y, _) in enumerate(spots)
        if not has_room(x, y, [s for j, s in enumerate(spots) if j != i])
    ]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_table_is_four_to_seven_glasses_of_one_kind(seed):
    glasses = table_draw.table(seed)
    assert table_draw.FEWEST <= len(glasses) <= table_draw.MOST
    assert len({g.kind for g in glasses}) == 1
    assert [g.name for g in glasses] == [f"glass_{i}" for i in range(len(glasses))]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_table_has_a_touching_group(seed):
    """A table always holds glasses that are in each other's way.

    The group is a pair on some tables and three glasses on others, which is
    what separates a solution that manages the easy case from one that manages
    both: a pair falls to a single well aimed nudge and three do not. What this
    checks is that a group really is a clump of glasses in each other's way,
    rather than glasses that merely ended up near one another.
    """
    spots = _spots(table_draw.table(seed))
    clumps = table_draw.groups_of(spots)
    assert max(len(c) for c in clumps) >= table_draw.LEAST_IN_A_GROUP
    pairs = [(i, j) for i in range(len(spots)) for j in range(i + 1, len(spots))]
    assert any(table_draw.in_the_way(spots[i], spots[j]) for i, j in pairs)


def test_both_sizes_of_group_really_occur():
    """Neither kind of table may quietly disappear from the draw.

    If every table held a pair the problem would be a test of one nudge, and if
    every table held three the easy case would never be seen. Both have to be
    drawn often enough that a run of fifty tables holds many of each.
    """
    biggest = [table_draw.facts(seed)["biggest_group"] for seed in range(200)]
    assert biggest.count(2) > 60, "too few tables whose hardest group is a pair"
    assert biggest.count(3) > 60, "too few tables with a group of three"


@pytest.mark.parametrize("seed", SEEDS)
def test_every_table_leaves_one_or_two_glasses_with_room_to_spare(seed):
    """A solution has to decide to leave a glass alone, so there is always one.

    The room is checked with GROUP_GAP to spare, because a glass that only
    just has room is a glass the noise in a look can put on either side of the
    line, and then the table's own description would depend on the weather.
    """
    spots = _spots(table_draw.table(seed))
    free = [i for i in range(len(spots)) if i not in _crowded(spots)]
    assert table_draw.FREE_BAND[0] <= len(free) <= table_draw.FREE_BAND[1]
    for i in free:
        x, y, _ = spots[i]
        assert has_room(x, y, [s for j, s in enumerate(spots) if j != i], table_draw.GROUP_GAP)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_number_of_crowded_glasses_stays_inside_its_narrow_band(seed):
    spots = _spots(table_draw.table(seed))
    assert table_draw.CROWDED_BAND[0] <= len(_crowded(spots)) <= table_draw.CROWDED_BAND[1]


@pytest.mark.parametrize("seed", SEEDS)
def test_glasses_are_a_small_gap_apart_and_in_the_zone_never_overlapping(seed):
    """Crowded means in the hand's way, not stacked. Nothing here overlaps."""
    spots = _spots(table_draw.table(seed))
    assert all(in_zone(x, y) for x, y, _ in spots)
    # The gap is far smaller than the room the hand needs, which is why two
    # glasses can be well clear of each other and still both be stuck.
    assert table_draw.START_GAP < GRIP_ROOM
    for i, (x, y, width) in enumerate(spots):
        for ox, oy, owidth in spots[i + 1 :]:
            daylight = math.dist((x, y), (ox, oy)) - (width + owidth) / 2
            assert daylight >= table_draw.START_GAP - 1e-9


@pytest.mark.parametrize("seed", SEEDS)
def test_every_crowded_glass_is_one_the_physics_can_slide_rather_than_tip(seed):
    """Asked with solution 1's own rule, so the two cannot drift apart.

    A table holding a glass that tips before it slides would mark every
    solution down for the draw's bad luck, and no solution could tell the
    difference between that and its own mistake. Glasses that already have
    room are not held to this: nothing has to push them.
    """
    # Solution 1's own module, asked directly rather than through ``table_draw``,
    # so that this is a check and not the draw agreeing with itself.
    slides = table_draw.solution_one().slides

    glasses = table_draw.table(seed)
    for i in _crowded(_spots(glasses)):
        assert slides(table_draw.as_seen(glasses[i].outline)) != "no"


@pytest.mark.parametrize("seed", SEEDS)
def test_one_touching_group_never_reaches_into_another(seed):
    """Groups are separate clumps, which is what makes the composition mean anything.

    Two groups a hair apart would read as one group of five, and the band on
    crowded glasses would be measuring something other than what it says.
    """
    spots = _spots(table_draw.table(seed))
    clumps = table_draw.groups_of(spots)
    for a, clump in enumerate(clumps):
        for other in clumps[a + 1 :]:
            for i in clump:
                for j in other:
                    apart = math.dist(spots[i][:2], spots[j][:2])
                    assert apart >= GRIP_ROOM + max(spots[i][2], spots[j][2]) / 2 + table_draw.GROUP_GAP


def test_the_composition_varies_so_there_is_no_constant_to_memorise():
    """Every shape of table the draw allows really turns up, and so does every kind.

    This is the test that would catch the draw quietly collapsing onto one
    arrangement, which is the failure that matters most: a policy can learn a
    constant table in far less time than it can learn to separate glasses.
    """
    seen_shapes, seen_kinds, counts = set(), set(), set()
    for seed in MANY:
        card = table_draw.facts(seed)
        seen_shapes.add((card["groups"], card["with_room"]))
        seen_kinds.add(card["kind"])
        counts.add(card["glasses"])
    assert seen_kinds == set(table_draw.KINDS)
    allowed = {(tuple(sorted(groups, reverse=True)), free) for groups, free in table_draw.COMPOSITIONS}
    assert seen_shapes == allowed
    assert counts == set(range(table_draw.FEWEST, table_draw.MOST + 1))


def test_a_glass_number_says_nothing_about_whether_it_is_crowded():
    """The glasses are shuffled before they are named, and this is why.

    Laid out as they are drawn, the big group goes down first and ``glass_0``
    is crowded on every table. That is a free answer for anything learning
    from the identifiers, and it would not survive contact with a real cell,
    where the numbering is whatever the detector happened to emit.
    """
    crowded_first = sum(1 for seed in MANY if 0 in _crowded(_spots(table_draw.table(seed))))
    # Roughly the share of glasses that are crowded on an average table, which
    # is what a number carrying no information looks like. Loose on purpose.
    assert 0.4 * len(MANY) < crowded_first < 0.9 * len(MANY)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_same_seed_always_draws_the_same_table(seed):
    first, again = table_draw.table(seed), table_draw.table(seed)
    assert [(g.name, g.kind, g.position) for g in first] == [(g.name, g.kind, g.position) for g in again]
    assert [g.outline.max_diameter for g in first] == [g.outline.max_diameter for g in again]
    assert table_draw.facts(seed) == table_draw.facts(seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_facts_describe_the_table_that_was_really_drawn(seed):
    """``facts`` is what the documents quote, so it is checked against the glasses."""
    card = table_draw.facts(seed)
    spots = _spots(table_draw.table(seed))
    crowded = _crowded(spots)
    assert card["seed"] == seed
    assert card["kind"] in table_draw.KINDS
    assert card["glasses"] == len(spots)
    assert card["touching_pairs"] >= 1
    assert card["crowded"] == len(crowded)
    assert card["with_room"] == len(spots) - len(crowded)
    assert card["biggest_group"] == max(len(c) for c in table_draw.groups_of(spots))
    assert card["crowded_can_slide"] is True
    assert card["closest"] >= table_draw.START_GAP - 1e-9
    # There is always something to do, which is what a shortfall above zero means.
    assert card["shortfall"] > 0.0
    assert sum(card["groups"]) == len(crowded)


def test_a_table_that_cannot_be_drawn_raises_instead_of_looping_for_ever(monkeypatch):
    """The retries are bounded, and running out of them says which seed and why.

    Asking every group to keep a metre from every other cannot be done inside
    a zone 320 mm across, so this is the impossible case, reached quickly by
    cutting the retries down first.
    """
    monkeypatch.setattr(table_draw, "GROUP_GAP", 1.0)
    monkeypatch.setattr(table_draw, "LAYOUT_TRIES", 1)
    monkeypatch.setattr(table_draw, "GROUP_TRIES", 1)
    monkeypatch.setattr(table_draw, "SPOT_TRIES", 2)
    with pytest.raises(RuntimeError, match="no table for seed 3"):
        table_draw.table(3)


def test_a_glass_that_cannot_be_drawn_slidable_raises_and_says_so(monkeypatch):
    monkeypatch.setattr(table_draw, "GLASS_TRIES", 0)
    with pytest.raises(RuntimeError, match="slide rather than tip"):
        table_draw.table(0)


@pytest.mark.parametrize("seed", [*SEEDS[:3], *SEEDS[-3:]])
def test_the_draw_can_be_stood_up_on_the_examiner(seed):
    """The whole point of the list: it is what ``Simulator(seed, glasses=...)`` takes.

    Building the world is as far as this goes. The physics is not stepped,
    because what is being checked is that the draw is a table the cell will
    accept and that every glass starts where the draw put it.
    """
    glasses = table_draw.table(seed)
    table = Simulator(seed, glasses)
    for i, glass in enumerate(glasses):
        # The world writes a position to five decimal places, so a glass
        # stands within a hundredth of a millimetre of where it was drawn.
        assert math.dist(table.position(i), glass.position[:2]) < 2e-5
