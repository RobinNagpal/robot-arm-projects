"""One of problem 4's tables in the physics engine.

The physics and the glasses are problem 3's, in the copy of ``common_bench.py``
that ``taken_from_problem_3.py`` brings in. What is problem 4's own is which glasses stand
on a table, and ``table_draw.py`` draws them. So a ``Simulator`` is the common
simulator with one thing added: given only a table number, it stands that
table's glasses from ``table_draw.table``.

``arm_and_table_simulator.py`` extends this class with the UR5e, and that is the simulator
every solution is run in. This class is what it inherits about the table: where
each glass stands, how far it leans, and the measurements a look returns.
"""

from __future__ import annotations

from examiner.simulation import table_draw
from examiner.simulation.taken_from_problem_3 import CommonSimulator, SpawnedGlass


class Simulator(CommonSimulator):
    """One of problem 4's tables in the physics engine."""

    def __init__(self, seed: int, glasses: list[SpawnedGlass] | None = None) -> None:
        super().__init__(seed, glasses if glasses is not None else table_draw.table(seed))
