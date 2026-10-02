"""Which slot to put a glass in, chosen for the whole table. Programmed.

Problem 4's solution 4. The rack has six slots, and a wide glass also uses up
the slots either side of it. Taking the next free slot can leave a later glass
with nowhere to go. Here every way of filling the rack with the glasses still
standing is tried, which is a few hundred cases at most, and the slot that
leaves room for the most of them wins.

Wide or not is problem 1's arithmetic, `needs_empty_neighbour()` in
rack/layout.py, from a glass's width and height.
"""

from __future__ import annotations

from functools import cache

from work_cell.rack.layout import SLOT_COUNT, needs_empty_neighbour

ALL = frozenset(range(SLOT_COUNT))


def is_wide(width: float, height: float) -> bool:
    return needs_empty_neighbour(width, height)


def usable(free: frozenset[int], wide: bool) -> list[int]:
    """The free slots this glass could go in."""
    if not wide:
        return sorted(free)
    taken = ALL - free
    return [s for s in sorted(free) if s - 1 not in taken and s + 1 not in taken]


def consumed(slot: int, wide: bool) -> frozenset[int]:
    return frozenset({slot - 1, slot, slot + 1} & ALL) if wide else frozenset({slot})


@cache
def capacity(free: frozenset[int], rest: tuple[bool, ...]) -> int:
    """The most of ``rest`` (wide or not, one per glass) the free slots can still take."""
    if not rest:
        return 0
    first, others = rest[0], rest[1:]
    best = capacity(free, others)  # this one left out
    for slot in usable(free, first):
        best = max(best, 1 + capacity(free - consumed(slot, first), others))
        if best == len(rest):
            break
    return best


def best_slot(free: frozenset[int], wide: bool, rest: list[bool]) -> int | None:
    """The slot for this glass that leaves room for the most of the rest, or None if it fits nowhere.

    Ties go to the lower slot number: filling from one end keeps the row
    tidy and the arm from reaching over a glass already standing.
    """
    rest = tuple(sorted(rest))
    options = usable(free, wide)
    if not options:
        return None
    return max(options, key=lambda s: (capacity(free - consumed(s, wide), rest), -s))
