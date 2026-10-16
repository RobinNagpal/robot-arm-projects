"""Problem 4's tables: three to five glasses, and every crowded one movable.

Problem 3's ``scene()`` draws four to six glasses of one kind and asks only
that one of them is short of room. That is enough when the bench hands a
solution the whole table and counts its pushes for it. Problem 4 marks the
table as the solution left it, so the draw has to promise more: that there was
something to do, that it was the same *sort* of something on every table, and
that the physics would in fact have moved every glass that needed moving. One
unmovable glass would mark every solution down for the draw's own bad luck.

So this is problem 4's own draw rather than a copy of problem 3's. Nothing
about the cell is drawn again: the hand's reach and ``has_room`` come through
``partners``, the glass zone and the table top from the cell's own layout
modules, and the glasses from the one library that draws them. What changes is
only what the draw promises about the arrangement. Every table holds:

- one touching group, which is a pair on some tables and three glasses on
  others, decided by the seed. A pair falls to one well aimed nudge and three
  do not, so the two together separate a solution that can manage the easy
  case from one that can manage both;
- one or two glasses that already have room, so that leaving a glass alone is
  part of the job and not only pushing;
- two or three crowded glasses. The band is narrow on purpose: two tables are
  only worth comparing if they were about as crowded to begin with;
- every crowded glass one the physics can slide rather than tip, by solution
  1's own tipping rule. The draw redraws the glass until that holds, so a
  table is always solvable in principle and a topple is the solution's doing.

**"Touching" here means closer than the room the open hand needs**, which is
what ``has_room`` measures. The glasses never overlap: the draw leaves
``START_GAP`` of daylight between every pair of them, and two glasses can be
well clear of each other and still be too close for the hand to reach between.

Nothing about a table is constant. The kind, the number of glasses, how they
split into groups and how many are already free all come off the seed, and the
glasses are shuffled before they are named, so ``glass_0`` is as likely to be
the free one as the crowded one. A draw that always produced, say, five
glasses as one pair and one triple would be a fact a trained policy could
learn once instead of learning to separate glasses.
"""

from __future__ import annotations

import math
import random
from types import ModuleType

from work_cell.glasses.shapes import KIND_RANGES, Outline, draw
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

from partners import GRIP_ROOM, Seen, SpawnedGlass, has_room, in_zone

# How many glasses a table holds, fewest and most.
#
# These were four to seven, with a group of three on every table, and that draw
# turned out to be unsolvable rather than hard. Given true positions, exact
# pushes, no clock and no limit on how many pushes it could make, the ranked
# geometry still separated none of twenty tables and ran out of pushes worth
# suggesting after thirty-one of them across the whole twenty: there was
# nowhere left to put a glass. The hand is 139 mm across and cannot come lower
# than 75 mm, so on a zone 320 by 360 mm, seven glasses leave it nowhere to
# stand. A problem nobody can finish measures nothing, because every solution
# scores zero for the same reason and the differences between them disappear.
FEWEST, MOST = 3, 5

# How many of them are crowded, lowest and highest. Two is the floor because
# two glasses is what crowding means, and three the ceiling because this has to
# stay a narrow band: the scorecard averages arm time over tables, and tables
# that started two glasses apart in difficulty would not belong in one average.
CROWDED_BAND = (2, 3)

# How many already have room. Never none, so that a solution has to decide to
# leave a glass alone, and never more than two, because a table of mostly free
# glasses measures almost nothing.
FREE_BAND = (1, 2)

# A crowded glass is crowded by a neighbour, so the smallest touching group is
# two. This is not a free choice; it is what "crowded" means.
LEAST_IN_A_GROUP = 2

# The least daylight between two glasses. Problem 3's bench has a constant of
# this name and this size, but ``partners`` does not re-export it and this is a
# choice belonging to problem 4's draw rather than to the cell, so it is named
# here. The glasses are standing on a table, not stacked: they never touch.
START_GAP = 0.005

# Room kept between one touching group and anything outside it, over and above
# the room the hand needs. Without it a group's edge glass would sit exactly on
# the boundary of having room, and the measurement noise in a solution's look
# would decide which group it belonged to.
GROUP_GAP = 0.008

# Tries before the draw gives up, so that an impossible table raises instead of
# spinning. A table normally lands on its first try; the counts are generous
# because the cost of a retry is one more random point.
GLASS_TRIES = 60
SPOT_TRIES = 400
GROUP_TRIES = 60
LAYOUT_TRIES = 40


def _splits(total: int, least: int) -> list[tuple[int, ...]]:
    """Every way ``total`` crowded glasses divide into groups of ``least`` or more.

    Written out rather than listed as a constant so that moving CROWDED_BAND
    moves the compositions with it.
    """
    if total == 0:
        return [()]
    out = []
    for size in range(least, total + 1):
        rest = total - size
        if rest == 0 or rest >= least:
            out += [(size, *more) for more in _splits(rest, size)]
    return out


# Every shape of table the draw may produce: the sizes of the touching groups,
# and how many glasses are left with room. Some tables hold a touching pair and
# some a touching group of three, and which one a table gets comes off its
# seed. Both are needed: a pair falls to a single well aimed nudge, a group of
# three does not, and a solution that can do the first and not the second
# should be visible as exactly that rather than scoring zero on everything.
COMPOSITIONS = tuple(
    (groups, free)
    for crowded in range(CROWDED_BAND[0], CROWDED_BAND[1] + 1)
    for groups in _splits(crowded, LEAST_IN_A_GROUP)
    for free in range(FREE_BAND[0], FREE_BAND[1] + 1)
    if FEWEST <= crowded + free <= MOST
)

# The kinds, from the library that draws them, so the four names are not
# written down a third time. ``bench.KINDS`` is the same four in its own order
# and ``partners`` does not re-export it.
KINDS = tuple(sorted(KIND_RANGES))

Spot = tuple[float, float, float]  # x, y, and the glass's widest width


def solution_one() -> ModuleType:
    """Solution 1's geometry, imported on use rather than at the top of the file.

    Its tipping rule and its measure of how much room a table is short of are
    borrowed rather than worked out again, because a second copy of either
    would be free to drift away from the one the solutions use.

    The import is here and not with the others for a mechanical reason.
    ``partners`` is what puts solution 1's folder on the path -- that folder's
    name starts with a digit, so it cannot be a package and cannot be imported
    by name -- and the import sorter files ``partners``, a module of this
    problem's own, below every outside import. A ``plan`` import at the top of
    the file would therefore be reached before the path it needs existed.
    """
    import plan

    return plan


def as_seen(outline: Outline) -> Seen:
    """A glass's true numbers, in the shape solution 1's rules read.

    Those rules take a ``Seen`` because the arm only ever has measurements.
    Asked here of the truth, the tipping rule says whether the physics can
    slide the glass, rather than whether one noisy look made it look slidable.
    """
    return Seen(
        id=0,
        x=0.0,
        y=0.0,
        height=outline.total_height,
        widest=outline.max_diameter,
        foot=2.0 * float(outline.radius[0]),
        standing=True,
    )


def _others(spots: list[Spot], i: int) -> list[Spot]:
    return [spot for j, spot in enumerate(spots) if j != i]


def in_the_way(one: Spot, other: Spot) -> bool:
    """Whether two glasses are closer than the room the open hand needs.

    This is what "touching" means on this table, and it is ``has_room``'s own
    question asked both ways round. Both ways, because ``has_room`` is not
    symmetric -- a narrow glass beside a wide one is crowded before the wide
    one is -- and a group whose glasses were only crowded one way would leave
    the wide one counted as free.
    """
    x, y, width = one
    ox, oy, owidth = other
    return not has_room(x, y, [other]) and not has_room(ox, oy, [(x, y, width)])


def groups_of(spots: list[Spot]) -> list[tuple[int, ...]]:
    """The touching groups: glasses in each other's way, joined up into clumps.

    A clump is what a solution has to break up, and its size is what makes the
    table hard, so the groups are measured off the drawn positions rather than
    taken from what the draw meant to produce.
    """
    seen: set[int] = set()
    found = []
    for start in range(len(spots)):
        if start in seen:
            continue
        clump, edge = {start}, [start]
        while edge:
            i = edge.pop()
            for j in range(len(spots)):
                if j not in clump and in_the_way(spots[i], spots[j]):
                    clump.add(j)
                    edge.append(j)
        seen |= clump
        found.append(tuple(sorted(clump)))
    return found


def _glass(kind: str, rng: random.Random, crowded: bool) -> Outline:
    """One glass, redrawn until the physics could slide it if it is to be pushed.

    Only the crowded ones are held to that. A glass that already has room is
    never pushed, so refusing a tippy one would narrow the families for no
    gain -- and it is the tippy kinds, the tapered ones, that the arm most
    needs to meet standing somewhere it can be left alone.
    """
    for _ in range(GLASS_TRIES):
        outline, _proportions = draw(kind, rng)
        if not crowded or solution_one().slides(as_seen(outline)) != "no":
            return outline
    raise RuntimeError(
        f"no {kind} in {GLASS_TRIES} draws had a foot wide enough to slide rather than tip; "
        f"its range in KIND_RANGES, or the height the jaw pushes at, wants looking at"
    )


def _spot(rng: random.Random, width: float, group: list[Spot], placed: list[Spot]) -> Spot | None:
    """A spot for one glass joining ``group``, or None when this try missed.

    The first glass of a group goes anywhere in the zone. Each one after it is
    stood next to a glass already in the group, close enough to be in the
    hand's way and far enough off not to overlap it, which is the window the
    two numbers below bound.
    """
    x_min, x_max, y_min, y_max = GLASS_ZONE
    if not group:
        x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
    else:
        nx, ny, nwidth = rng.choice(group)
        near = rng.uniform((width + nwidth) / 2 + START_GAP, GRIP_ROOM + min(width, nwidth) / 2)
        angle = rng.uniform(-math.pi, math.pi)
        x, y = nx + near * math.cos(angle), ny + near * math.sin(angle)
    spot = (x, y, width)
    if not in_zone(x, y):
        return None
    # Daylight from every glass in the group, not only the one it was stood
    # beside, and from everything outside it as well.
    if any(math.dist((x, y), (ox, oy)) < (width + owidth) / 2 + START_GAP for ox, oy, owidth in group):
        return None
    if group and not any(in_the_way(spot, other) for other in group):
        return None
    # Outside the group, room for the hand and GROUP_GAP more, so that no two
    # groups quietly become one and a free glass stays free.
    if any(
        math.dist((x, y), (ox, oy)) < GRIP_ROOM + max(width, owidth) / 2 + GROUP_GAP
        for ox, oy, owidth in placed
    ):
        return None
    return spot


def _group(rng: random.Random, widths: list[float], placed: list[Spot]) -> list[Spot] | None:
    """One whole touching group laid out, or None if it would not fit anywhere."""
    for _ in range(GROUP_TRIES):
        group: list[Spot] = []
        for width in widths:
            for _try in range(SPOT_TRIES):
                spot = _spot(rng, width, group, placed)
                if spot is not None:
                    group.append(spot)
                    break
            else:
                break
        if len(group) == len(widths):
            return group
    return None


def table(seed: int) -> list[SpawnedGlass]:
    """Table number ``seed``, as a list of glasses for ``Bench(seed, glasses=...)``.

    The same seed always gives the same table. Problem 3's convention holds
    here too: seeds below ``TEST_SEEDS`` are for training and the ones above it
    are the tables a solution is scored on.
    """
    # Seeded off a string rather than the bare number so that problem 4's table
    # 7 is not problem 3's table 7 with extra glasses. ``random`` hashes a
    # string the same way in every run, so this is still reproducible.
    rng = random.Random(f"clear-the-table:{seed}")
    kind = rng.choice(KINDS)
    groups, free = rng.choice(COMPOSITIONS)
    # A free glass is a touching group of one: same placement, and the room it
    # needs is the room every group keeps from every other.
    sizes = sorted((*groups, *(1,) * free), reverse=True)

    for _ in range(LAYOUT_TRIES):
        placed: list[Spot] = []
        drawn: list[Outline] = []
        for size in sizes:
            widths = []
            for _each in range(size):
                drawn.append(_glass(kind, rng, crowded=size > 1))
                widths.append(drawn[-1].max_diameter)
            group = _group(rng, widths, placed)
            if group is None:
                break
            placed += group
        else:
            # Shuffled before naming, so a glass's number says nothing about
            # whether it is crowded. The groups go down biggest first, which
            # packs better, and that order would otherwise be learnable.
            order = list(range(len(placed)))
            rng.shuffle(order)
            return [
                SpawnedGlass(f"glass_{i}", kind, drawn[j], (placed[j][0], placed[j][1], TABLE_TOP_Z), 0.0)
                for i, j in enumerate(order)
            ]

    raise RuntimeError(
        f"no table for seed {seed}: {LAYOUT_TRIES} tries never fitted {sum(sizes)} "
        f"{kind}es in groups of {sizes} into the glass zone. Either the composition wants "
        f"narrowing or GROUP_GAP wants cutting"
    )


def facts(seed: int) -> dict:
    """What table ``seed`` really is, measured off the glasses it drew.

    Measured rather than remembered: these are the numbers a document or a
    scorecard quotes, and a draw that silently stopped keeping one of its
    promises would still report the promise if this returned what it intended.
    """
    glasses = table(seed)
    spots: list[Spot] = [(g.position[0], g.position[1], g.outline.max_diameter) for g in glasses]
    clumps = groups_of(spots)
    crowded = [i for i, spot in enumerate(spots) if not has_room(spot[0], spot[1], _others(spots, i))]
    pairs = sum(
        1 for i in range(len(spots)) for j in range(i + 1, len(spots)) if in_the_way(spots[i], spots[j])
    )
    return {
        "seed": seed,
        "kind": glasses[0].kind,
        "glasses": len(glasses),
        "crowded": len(crowded),
        "with_room": len(glasses) - len(crowded),
        "groups": tuple(sorted((len(c) for c in clumps if len(c) > 1), reverse=True)),
        "biggest_group": max((len(c) for c in clumps), default=0),
        "touching_pairs": pairs,
        # How much room the table is short of in total, by solution 1's own
        # measure. Zero would mean there was nothing to do.
        "shortfall": solution_one().shortfall(spots),
        "closest": min(
            (
                math.dist(spots[i][:2], spots[j][:2]) - (spots[i][2] + spots[j][2]) / 2
                for i in range(len(spots))
                for j in range(i + 1, len(spots))
            ),
            default=0.0,
        ),
        "crowded_can_slide": all(
            solution_one().slides(as_seen(glasses[i].outline)) != "no" for i in crowded
        ),
    }

