"""One of problem 4's tables in the physics engine.

The physics, the glasses, the jaw and what the jaw feels are problem 3's, in the
copy of ``common_bench.py`` that ``partners.py`` brings in. What is problem 4's
own is which glasses stand on a table, and ``tables.py`` draws them. So a
``Simulator`` is the common simulator with one thing added: given only a table
number, it stands that table's glasses from ``tables.table``.

Problem 3's own simulator adds more than this: an overhead camera, a push that
feels for the glass, and a way of racking a glass. Problem 4 has none of those.
The arm carries its own camera (``wrist.py``), a solution moves the jaw only by
a list of waypoints, and no glass leaves the table.
"""

from __future__ import annotations

import tables
from partners import CommonSimulator, SpawnedGlass


class Simulator(CommonSimulator):
    """One of problem 4's tables in the physics engine."""

    def __init__(self, seed: int, glasses: list[SpawnedGlass] | None = None) -> None:
        super().__init__(seed, glasses if glasses is not None else tables.table(seed))
