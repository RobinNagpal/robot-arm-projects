"""The picture steps of a run, one function each.

    look     overhead picture --TopNet--> where each glass stands, how wide, how tall
    view     24 places round a glass --geometry veto--> allowed --Ranker--> best place
    measure  side picture --SideNet--> height, 16 widths, kind
                          --GripNet--> can it be held; grip height; opening

The order they run in is run.py's. Finding and choosing a view are problem
2's own functions (02-segment-glasses/02-train-from-scratch/pipeline.py), called as they are.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from work_cell.glasses import spec
from work_cell.table.layout import TABLE_TOP_Z

import nets
import pipeline as p2  # 02-segment-glasses/02-train-from-scratch
import render
import tables
import viewpoints
from bench import Bench, Seen

# A found glass is the bench glass standing nearest it, if one is this close.
# That is the physics deciding which glass is at the place the arm acts on.
SAME_PLACE = 0.03

# Below this, the Ranker's best place is not worth a look: problem 2's line.
MIN_VIEW_SCORE = p2.MIN_SCORE

# GripNet has to give at least this chance that a glass can be held before
# the arm goes in. Below it the glass is refused, which is always safe.
HOLD_CHANCE = 0.5

# SideNet has to give its kind at least this chance. A glass it is unsure of
# is refused rather than squeezed at a force picked for a guess.
KIND_CHANCE = 0.6


@dataclass(frozen=True)
class Sighting:
    """One glass TopNet found, and which glass on the bench it is."""

    id: int | None  # None when no glass stands there
    seen: Seen  # as problem 3's planner takes it; foot filled in once measured
    pixels: np.ndarray


@dataclass(frozen=True)
class Measured:
    """What SideNet and GripNet said about one glass from one side picture."""

    angle: float
    view_score: float
    height: float
    widths: np.ndarray
    kind_chances: np.ndarray
    hold_chance: float
    grip_height: float
    opening: float

    @property
    def kind(self) -> str:
        return nets.KINDS[int(self.kind_chances.argmax())]

    @property
    def foot(self) -> float:
        return float(self.widths[0])

    @property
    def widest(self) -> float:
        return float(self.widths.max())

    @property
    def squeeze(self) -> float:
        """The force cap of the kind SideNet named: a table lookup, not a model."""
        return spec.kind(self.kind).force_cap_n


def look(bench: Bench, top_net) -> tuple[render.Picture, list[Sighting], list[render.Glass], list[int]]:
    """The overhead picture of the table as it stands, and every glass TopNet found in it."""
    ids, glasses = tables.on_bench(bench)
    top = render.render(glasses, render.top_pose())
    sightings = []
    for found in p2.find_glasses(top, top_net):
        points = render.to_world(top, found.pixels[:, 0], found.pixels[:, 1])
        points = points[np.isfinite(points).all(1)]
        height = float(points[:, 2].max() - TABLE_TOP_Z)
        x, y = found.seen.x, found.seen.y
        near = min(ids, key=lambda i: math.dist(bench.position(i), (x, y)), default=None)
        if near is not None and math.dist(bench.position(near), (x, y)) > SAME_PLACE:
            near = None
        standing = near is None or bench.tilt(near) < 20.0
        sightings.append(
            Sighting(
                near,
                Seen(near if near is not None else -1, x, y, height, 2 * found.seen.radius, 0.0, standing),
                found.pixels,
            )
        )
    return top, sightings, glasses, ids


def view(target: Sighting, others: list[Sighting], ranker) -> tuple[float, float] | None:
    """(score, angle) of the best allowed place for a side picture, or None if none is allowed."""
    as_seen = lambda s: viewpoints.Seen(s.seen.x, s.seen.y, s.seen.widest / 2)  # noqa: E731
    ranked = p2.rank_views(as_seen(target), [as_seen(o) for o in others], ranker)
    return ranked[0] if ranked else None


def measure(glasses: list[render.Glass], target: Sighting, angle: float, score: float, side_net, grip_net):
    """Take the side picture from ``angle`` and ask both models about it."""
    side = render.render(glasses, render.side_pose(target.seen.x, target.seen.y, angle))
    picture = nets.side_input(side)[None]
    height, widths, chances = nets.side_output(nets.predict(side_net, picture)[0])
    hold, grip_height, opening = nets.grip_output(nets.predict(grip_net, picture)[0])
    return side, Measured(angle, score, height, widths, chances, hold, grip_height, opening)


def refusal(measured: Measured) -> str | None:
    """Why a measured glass is left standing, or None if the arm may go in."""
    if measured.hold_chance < HOLD_CHANCE:
        return f"GripNet says it cannot be held (chance {measured.hold_chance:.2f})"
    if measured.kind_chances.max() < KIND_CHANCE:
        return f"SideNet is unsure of the kind ({measured.kind_chances.max():.2f} for {measured.kind})"
    return None
