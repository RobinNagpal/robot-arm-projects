"""Problem 4's tables: four to six glasses of mixed kinds, some too close to grip.

Problem 3's crowded layout, with each glass's kind drawn on its own instead of
one kind per table. Every table has at least two kinds and at least one glass
without room.

Also the simulator's own answers for each glass: its kind, and where the
project's grip rule would hold it if its true shape were known. The models
are trained against these. The arm is never given them; scoring reads them
afterwards.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from work_cell.arm.dimensions import GRIPPER_MAX_OPENING, LOWEST_GRIP
from work_cell.glasses import spec
from work_cell.glasses.profile import profile_from_outline
from work_cell.glasses.rules import NoGrip, find_grip
from work_cell.glasses.shapes import Outline, draw
from work_cell.glasses.spawn import SpawnedGlass
from work_cell.table.layout import TABLE_TOP_Z

from bench import KINDS, Bench, _crowded_layout
from render import Glass

# Tables from here on are held out. Training draws only below it.
TEST_SEEDS = 10_000


def scene(seed: int) -> list[SpawnedGlass]:
    """Table number ``seed``: four to six glasses, at least two kinds, some crowded."""
    rng = random.Random(seed)
    count = 4 + seed % 3
    for _ in range(200):
        kinds = [rng.choice(KINDS) for _ in range(count)]
        if len(set(kinds)) < 2:
            continue
        outlines = [draw(kind, rng)[0] for kind in kinds]
        spots = _crowded_layout(rng, outlines)
        if spots is not None:
            return [
                SpawnedGlass(f"glass_{i}", kind, outline, (x, y, TABLE_TOP_Z), 0.0)
                for i, (kind, outline, (x, y)) in enumerate(zip(kinds, outlines, spots, strict=True))
            ]
    raise RuntimeError(f"no crowded mixed layout for table {seed}")


def mixed_bench(seed: int) -> Bench:
    """Problem 3's physics bench, on a mixed table."""
    return Bench(seed, scene(seed))


def to_render(glasses: list[SpawnedGlass], places: list[tuple[float, float]]) -> list[Glass]:
    """The glasses as problem 2's renderer draws them, standing at ``places``."""
    return [
        Glass(g.kind, float(x), float(y), g.outline.height, g.outline.radius)
        for g, (x, y) in zip(glasses, places, strict=True)
    ]


def on_bench(bench: Bench) -> tuple[list[int], list[Glass]]:
    """The glasses still on the bench's table, where they stand now, for drawing."""
    ids = bench.on_table()
    places = [tuple(bench.position(i)) for i in ids]
    return ids, to_render([bench.glasses[i] for i in ids], places)


@dataclass(frozen=True)
class TrueGrip:
    """Where the grip rule holds a glass, worked out from its true shape and kind."""

    holdable: bool
    height: float  # metres up from the table; 0 when not holdable
    opening: float  # metres between the pads; 0 when not holdable
    reason: str  # why not, when not holdable


def true_grip(kind: str, outline: Outline, mass: float | None = None) -> TrueGrip:
    """The label GripNet learns: the project's own rule, given everything."""
    try:
        grip = find_grip(
            profile_from_outline(outline),
            spec.kind(kind),
            gripper_max_opening=GRIPPER_MAX_OPENING,
            lowest_grip=LOWEST_GRIP,
            mass=mass,
        )
    except NoGrip as reason:
        return TrueGrip(False, 0.0, 0.0, str(reason))
    return TrueGrip(True, grip.height, grip.opening, "")


def glass_grip(glass: SpawnedGlass) -> TrueGrip:
    return true_grip(glass.kind, glass.outline, glass.mass)


def kind_index(kind: str) -> int:
    return KINDS.index(kind)

