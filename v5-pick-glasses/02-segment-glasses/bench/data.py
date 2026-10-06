"""The camera, the scenes, and everything a solution is allowed to be told.

This module owns the camera for all three solutions. That is the point of it:
the three scorecards are only comparable if the three solutions were handed the
same pictures, and a solution that chose its own viewpoint could beat another by
its viewpoint rather than by its method. No other file in this folder renders
anything.

**Where the camera stands.** At the cell's own `SURVEY_HEIGHT`, not at
`render.TOP_HEIGHT`. The shared simulator looks down from 750 mm so that one
picture holds the whole zone; the cell cannot reach that high and does not try.
What follows from the cell's height is that one picture does not hold the zone,
because a rim seen from above leans away from the point below the camera and the
higher the glass the further it leans. So the cell takes **three** pictures, from
the stations `survey_stations` works out, and this module renders all three. The
stations are computed exactly as `work_cell/task.py` computes them, from the
frame less the margins a real survey loses, so they are the cell's own stations
and not a number invented here.

**Two truths per glass per picture.**

- the **visible** mask, the pixels the camera can see of that glass, read
  straight out of the renderer's id picture;
- the **whole** mask, that glass's entire outline, got by rendering the glass
  alone from the same station and taking where it landed. The simulator knows
  what it drew, so this label costs one render and no labelling.

A solution fitted on this cell trains against the first; the amodal rung of
06-rf-detr-fine-tuned trains against the second, and that is the only
difference between the two rungs. The whole masks are rendered on first use, so
a solution that never asks for them never waits for them.

**Two kinds of scene.** The spawned ones, which are what the cell really
produces, and crowded ones built here, which stand glasses closer than the
layout rule allows and on a line out from under a camera, because that is the
only arrangement in which one glass covers another from above. A spawned layout
keeps a guaranteed separation, so hiding is rare in one even at the survey
height, and a training set of spawned scenes alone leaves an amodal rung
almost nothing to learn from. Both kinds are drawn for every solution, so all
six still see the same scenes.

**Which seeds may be drawn from** is settled here and not left to each caller.
render.TEST_SEEDS is the line: below it is for training, at or above it is held
out. Asking for training seeds that cross the line raises, because the
alternative is a scorecard quietly claimed on scenes that were trained on, and
that failure leaves no trace in the numbers.
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache, cached_property

import numpy as np
from work_cell.arm.dimensions import (
    GRIPPER_MAX_OPENING,
    SURVEY_BASELINE,
    SURVEY_HEIGHT,
    survey_stations,
)
from work_cell.glasses.shapes import KIND_RANGES, build, draw
from work_cell.glasses.spawn import MIN_SEPARATION
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

import pictures
import render
from render import Glass, Picture, to_world

# How much of a training set is crowded rather than spawned. Half, because the
# edge of the specification should sit in the middle of the training set and
# with spawned scenes alone it sits outside it.
CROWDED_SHARE = 0.5

# How many glasses a crowded line holds, and how many lines a crowded scene has.
# Two lines leave room to point in opposite directions from under the camera
# without either line running into the other.
CROWDED_LINES = 2
CROWDED_DEEP = 3

# How close a crowded line stands its glasses, as a share of the separation the
# layout rule guarantees. Written as a share of that rule rather than as a
# distance, because the point is to be inside it.
CROWDED_GAP = (0.3, 0.7)
CROWDED_FIRST = (0.25, 0.45)


# ------------------------------------------- what the cell is told about a kind


@cache
def widths(kind: str) -> tuple[float, float]:
    """The narrowest and widest footprint a glass of ``kind`` can have, in metres.

    A limit on the kind, which the cell is told, and not the size of any glass:
    it is worked out by building the kind at the corners of the range it is drawn
    from, so nothing about one glass is written down here. A solution uses it to
    refuse a footprint no glass of this kind could have, and this file uses it to
    tell one glass's report from another's.
    """
    proportions = KIND_RANGES[kind]
    names = list(proportions)
    corners = itertools.product(*(proportions[name] for name in names))
    built = [build(kind, **dict(zip(names, corner, strict=True))).max_diameter for corner in corners]
    return min(built), max(built)


@cache
def shortest(kind: str) -> float:
    """How tall the shortest glass of ``kind`` can be. A limit on the kind."""
    return float(min(KIND_RANGES[kind]["height"]))


# ------------------------------------------------------------------ the camera


def frame() -> tuple[float, float]:
    """How much table one picture covers at the survey height, in metres.

    From the lens and the height, the way the cell works it out from its own
    camera rather than from a number written down.
    """
    return (
        SURVEY_HEIGHT * render.WIDTH / render.FOCAL,
        SURVEY_HEIGHT * render.HEIGHT / render.FOCAL,
    )


def shared() -> tuple[float, float]:
    """How much of one picture a station can actually be credited with.

    A station is worth the part of the table both of its pictures show, because
    a glass in one and not the other cannot be placed. Sliding sideways for the
    second picture costs the baseline off that axis, and a glass has to be
    inside far enough not to be cut off at the edge, which costs the widest
    glass the gripper could ever close on off both. The same arithmetic as
    ``work_cell/task.py``, so these are the cell's stations.
    """
    across, down = frame()
    return (across - GRIPPER_MAX_OPENING, down - SURVEY_BASELINE - GRIPPER_MAX_OPENING)


@cache
def stations() -> tuple[np.ndarray, ...]:
    """Where the camera stands to survey the glass zone. Three places, not one."""
    return tuple(survey_stations(GLASS_ZONE, shared()))


@cache
def poses() -> tuple[np.ndarray, ...]:
    """The camera looking straight down from each station, at the survey height."""
    return tuple(
        render.look_at(np.array([x, y, TABLE_TOP_Z + SURVEY_HEIGHT]), np.array([x, y, TABLE_TOP_Z]))
        for x, y in stations()
    )


def under(pose: np.ndarray) -> tuple[float, float]:
    """The point on the table directly below a camera. Splay is measured from here."""
    return float(pose[0, 3]), float(pose[1, 3])


# ------------------------------------------------------------------ one picture


@dataclass
class Sight:
    """One station: the picture taken there, and the truth behind it.

    A solution is handed ``picture`` and the kind of glass, and nothing else.
    The masks are for training and for scoring, and no solution is shown them.
    """

    glasses: list[Glass]
    pose: np.ndarray
    picture: Picture

    @cached_property
    def image(self) -> np.ndarray:
        """What a model is shown: (rows, columns, 3) of uint8."""
        return pictures.shade(self.picture)

    @cached_property
    def visible(self) -> list[np.ndarray]:
        """Per glass, the pixels the camera can see of it."""
        return [self.picture.ids == index + 1 for index in range(len(self.glasses))]

    @cached_property
    def whole(self) -> list[np.ndarray]:
        """Per glass, its whole outline, from a render of that glass on its own."""
        return [render.render([glass], self.pose).ids == 1 for glass in self.glasses]

    def masks(self, amodal: bool) -> list[np.ndarray]:
        """The training target: whole outlines for an amodal rung, visible pixels otherwise."""
        return self.whole if amodal else self.visible


@dataclass
class Example:
    """One scene: the glasses on the table, and the three pictures of them."""

    seed: int
    glasses: list[Glass]
    sights: list[Sight]
    crowded: bool  # built here to hide glasses, rather than spawned by the layout

    @property
    def kind(self) -> str:
        """Which kind of glass is on the table, which the cell is told.

        A kind, never a size: what it fixes is the range of footprints a glass
        here could have, and every glass is still measured.
        """
        return self.glasses[0].kind

    @cached_property
    def reference(self) -> Picture:
        """One picture holding every glass, for scoring only. Never handed to a solution.

        The scorecard says which true glass a reported one is by the ids under
        its pixels, so it needs one picture in which every glass appears and
        none hides another. That is what ``render.top_pose`` is: from 750 mm the
        whole zone is in frame and nothing covers anything. It is also the
        picture every solution in this folder is scored in, so the find counts
        here mean the same as theirs.
        """
        return render.render(self.glasses, render.top_pose())


def in_reference(picture: Picture, pixels: np.ndarray, reference: Picture) -> np.ndarray:
    """The same pixels, said in the reference picture's own rows and columns.

    A glass found at a station is reported in that station's picture, and the
    scorecard reads ids out of the reference picture, so the two have to be
    brought together. Each pixel's depth reading makes it a point in the room,
    and the point is then projected into the reference camera. A point on a
    glass lands inside that glass's own outline from any viewpoint, and from the
    reference height nothing covers anything, so the id it lands on is this
    glass's. Pixels that land outside the reference frame are dropped, which is
    honest: the scorecard cannot be told anything about them.
    """
    points = to_world(picture, pixels[:, 0], pixels[:, 1])
    local = (points - reference.camera_to_world[:3, 3]) @ reference.camera_to_world[:3, :3]
    columns = np.round(render.LENS.fx * local[:, 0] / local[:, 2] + render.LENS.cx)
    rows = np.round(render.LENS.fy * local[:, 1] / local[:, 2] + render.LENS.cy)
    inside = (
        np.isfinite(columns)
        & np.isfinite(rows)
        & (local[:, 2] > 0)
        & (columns >= 0)
        & (columns < render.WIDTH)
        & (rows >= 0)
        & (rows < render.HEIGHT)
    )
    return np.stack([rows[inside], columns[inside]], 1).astype(int)


def spawned(seed: int) -> Example:
    """Scene ``seed`` from the simulator, seen from every station."""
    return _seen(seed, render.scene(seed), crowded=False)


def crowded(seed: int) -> Example:
    """A scene built to hide glasses behind each other, seen from every station.

    Glasses stand on lines running out from under the middle station, tallest
    first, closer together than the layout rule allows. Both parts are needed:
    on a line out from the camera a nearer outline leans over a further one, and
    inside the guaranteed separation it reaches far enough to cover it. Sizes
    are drawn, as everywhere in this project, so a line is a different three
    glasses every seed.
    """
    rng = random.Random(seed)
    kind = render.KINDS[seed % len(render.KINDS)]
    middle = under(poses()[len(poses()) // 2])

    glasses = []
    start = rng.uniform(0.0, 2.0 * math.pi)
    for line in range(CROWDED_LINES):
        # Opposite sides of the camera, so two lines cannot run into each other.
        angle = start + line * 2.0 * math.pi / CROWDED_LINES
        outlines = sorted(
            (draw(kind, rng)[0] for _ in range(CROWDED_DEEP)),
            key=lambda outline: -outline.total_height,
        )
        away = rng.uniform(*CROWDED_FIRST) * MIN_SEPARATION
        for outline in outlines:
            x = middle[0] + away * math.cos(angle)
            y = middle[1] + away * math.sin(angle)
            if in_zone(x, y):
                glasses.append(Glass(kind, x, y, outline.height, outline.radius))
            # Advanced whether or not the glass was kept, so the line's spacing
            # does not depend on what the zone allowed.
            away += rng.uniform(*CROWDED_GAP) * MIN_SEPARATION

    return _seen(seed, glasses, crowded=True)


def in_zone(x: float, y: float) -> bool:
    """Whether a glass standing here would be on the part of the table glasses stand on."""
    x_from, x_to, y_from, y_to = GLASS_ZONE
    return x_from <= x <= x_to and y_from <= y <= y_to


def _seen(seed: int, glasses: list[Glass], *, crowded: bool) -> Example:
    sights = [Sight(glasses, pose, render.render(glasses, pose)) for pose in poses()]
    return Example(seed, glasses, sights, crowded)


# -------------------------------------------------------------- which scenes


def training_seeds(count: int, start: int = 0) -> list[int]:
    """``count`` seeds from ``start``, all of them below the held-out line."""
    if count < 0 or start < 0:
        raise ValueError(f"asked for {count} training seeds from {start}")
    if start + count > render.TEST_SEEDS:
        raise ValueError(
            f"training asked for seeds {start} to {start + count - 1}, and "
            f"{render.TEST_SEEDS} upwards is held out for testing"
        )
    return list(range(start, start + count))


def held_out_seeds(count: int, start: int = render.TEST_SEEDS) -> list[int]:
    """``count`` seeds from ``start``, all of them at or above the held-out line."""
    if count < 0:
        raise ValueError(f"asked for {count} held-out seeds")
    if start < render.TEST_SEEDS:
        raise ValueError(f"seed {start} is below {render.TEST_SEEDS}, so training may have seen it")
    return list(range(start, start + count))


def how_many_crowded(scenes: int, share: float = CROWDED_SHARE) -> int:
    """How many of a run's scenes are the crowded kind."""
    return int(round(scenes * share))


def training(count: int, share: float = CROWDED_SHARE) -> Iterator[Example]:
    """The training scenes, spawned and crowded, one at a time so a long run holds one.

    Both kinds come from seeds below the held-out line, so no scene here can be
    one a score is later claimed on.
    """
    hard = how_many_crowded(count, share)
    for seed in training_seeds(count - hard):
        yield spawned(seed)
    for seed in training_seeds(hard):
        yield crowded(seed)


def held_out(count: int, hard: bool = False, start: int = render.TEST_SEEDS) -> Iterator[Example]:
    """The scenes a score may be claimed on, and which no training ever sees.

    ``start`` picks which block of held-out seeds to use. Every seed at or above
    the dividing line is held out, so blocks of ``count`` starting at
    ``TEST_SEEDS``, ``TEST_SEEDS + count`` and so on are different arrangements
    that no training has seen either. Scoring the same solution on several
    blocks is how a run-to-run spread is measured rather than guessed at.
    """
    build = crowded if hard else spawned
    for seed in held_out_seeds(count, start):
        yield build(seed)
