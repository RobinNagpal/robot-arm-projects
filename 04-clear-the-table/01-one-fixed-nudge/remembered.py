"""The table as the solution believes it, put together out of several looks.

One look reaches only as far as the camera does, so no single look is the
table. Something has to hold what the last look said about the far corner while
the jaw is busy in the near one, and that is this.

**Merging goes by the glass numbers the examiner hands back, and that is a
shortcut rather than an answer.** Deciding that the glass in this picture is
the one that was in the last picture is the association problem, and it is
problem 2's: on a real cell it is solved by measuring and matching, and it gets
harder exactly when a glass has just been moved. Taking the numbers from
``Seen.id`` steps over all of that. It is honest here because problem 4 is about
seeing less of the table and saying when to stop, not about re-identifying a
glass -- but nobody should read this file as evidence that the problem is
solved.

**Repeated looks are averaged, because they are free and the error is not.**
Every look draws fresh error, so two looks of the same glass are two
measurements, and the mean of them is better than either. Problem 3's solution
1 does the same thing by hand around its test push, three looks at a time.

**A glass that was pushed is forgotten first.** Averaging only helps while the
measurements are of the same thing. Fold a reading taken after a shove into the
mean of readings taken before it and the answer is a place the glass has never
stood. So the caller says when it has moved a glass, and the average for that
glass starts again from the next look of it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from partners import Seen


@dataclass(frozen=True)
class Believed:
    """One glass, and how much looking is behind the figures."""

    seen: Seen
    looks: int


def _averaged(held: Seen, fresh: Seen, looks: int) -> Seen:
    """The running mean of the measurements, one more look in.

    ``standing`` is taken from the newest look rather than averaged: it is the
    answer to "is it still upright", and the latest answer is the only one that
    matters.
    """

    def mean(was: float, now: float) -> float:
        return (was * looks + now) / (looks + 1)

    return Seen(
        id=held.id,
        x=mean(held.x, fresh.x),
        y=mean(held.y, fresh.y),
        height=mean(held.height, fresh.height),
        widest=mean(held.widest, fresh.widest),
        foot=mean(held.foot, fresh.foot),
        standing=fresh.standing,
    )


class Remembered:
    """Every glass the arm has seen on this table, as well as it can say."""

    def __init__(self) -> None:
        self._held: dict[int, Believed] = {}

    def merge(self, seen: Iterable[Seen]) -> None:
        """Fold one look into the belief."""
        for glass in seen:
            held = self._held.get(glass.id)
            if held is None or held.looks == 0:
                self._held[glass.id] = Believed(glass, 1)
            else:
                self._held[glass.id] = Believed(_averaged(held.seen, glass, held.looks), held.looks + 1)

    def forget(self, glass: int) -> None:
        """Say that this glass has been moved, so what was measured before is about where it was.

        The last reading is kept rather than thrown away, because it is still
        the best guess at where to go and look; but it no longer counts as a
        measurement, so the next look replaces it instead of being averaged
        into it.
        """
        held = self._held.get(glass)
        if held is not None:
            self._held[glass] = Believed(held.seen, 0)

    def glasses(self) -> list[Seen]:
        """Every glass believed to be on the table, in the order they were numbered."""
        return [self._held[glass].seen for glass in sorted(self._held)]

    def looks_of(self, glass: int) -> int:
        """How many looks the belief about this glass is averaged over, since it last moved."""
        held = self._held.get(glass)
        return held.looks if held is not None else 0

    def where(self, glass: int) -> tuple[float, float] | None:
        """Where the glass is believed to stand, or None if it has never been seen."""
        held = self._held.get(glass)
        return (held.seen.x, held.seen.y) if held is not None else None

    def down(self) -> list[int]:
        """The glasses last seen lying over. Nothing here stands one back up."""
        return [glass for glass, held in self._held.items() if not held.seen.standing]

    def __len__(self) -> int:
        return len(self._held)
