"""The five jaw-only solutions, run on the whole arm.

The first cell's solutions were written for a jaw that moves on its own. Each one
is shown a ``Look`` -- a picture, the glasses in it with a number each, and where
the jaw stands -- and answers with a ``Chunk``, a path of waypoints for the jaw, or
with ``Done``. This file lets the same solutions, with the same trained weights,
clear a table with the UR5e: it turns what the arm sees into a ``Look``, and it
turns each path into straight lines that MoveIt plans and the arm carries out.

**What the solution is told.** The box model reads only the two viewing poses,
because those are the poses it was trained on, so the glasses in a ``Look`` always
come from there: from both poses at the start of a table, and again after every
path that came down to push. A path that stays at travel height only moves the
arm, so after one the glasses are where they were. The picture in a ``Look`` is
the arm camera's picture from wherever the solution's last path left the hand,
because the solutions that read pictures choose where to look from. It is not
the picture they were trained on, because the arm's camera is mounted differently
from the jaw-only cell's, so those two are expected to do badly until they are
trained again on the arm.

**A glass keeps its number.** The jaw-only cell numbered every glass, and the
solutions remember glasses by those numbers from one look to the next. The box
model numbers nothing, so this file does: a glass found within ``MATCH`` of where
a numbered glass was last seen, or was last aimed at, keeps that number.

**What the arm does with a path.** The waypoints are joined into straight legs,
each run at the speed the jaw-only cell would have run it at. MoveIt plans the
whole path before the arm moves, as it does a push, so a path it cannot make is
refused and the solution is told why, exactly as the jaw-only cell told it.
"""

from __future__ import annotations

import importlib
import math
import sys
from pathlib import Path

import numpy as np
from arm_contract import REFUSED, Box, Leg, Pose, Request, Run, Settings
from pusher import TRAVEL
from solving import AS_NEEDED, VIEWS, Eyes, after

from contract import Done, Look
from partners import DESCEND_SPEED, TOP_SPEED, WAYPOINT_PERIOD, Chunk, Seen, Waypoint

PROBLEM = Path(__file__).resolve().parent.parent

# How far a glass may stand from where its number was last seen, or last aimed
# at, and keep that number.
MATCH = 0.04

# How far two legs may turn from each other, and how much their speeds may differ,
# and still be joined into one straight leg.
STRAIGHT_ON = math.radians(2.0)
SAME_SPEED = 0.10

# What a path is planned with: the room the arm's own pushes leave round every
# box, and the speed of the free move to the start of the path.
PATH = Settings.default()


def legs_of(chunk: Chunk) -> list[Leg]:
    """The chunk's waypoints as straight legs, each with the speed the jaw-only cell would run it at.

    The jaw-only cell comes down to the first waypoint at ``DESCEND_SPEED`` and then
    gives each leg one ``WAYPOINT_PERIOD``, or longer when that would be faster than
    ``TOP_SPEED``. So the speed of a leg is its length over one period, up to
    ``TOP_SPEED``. Runs of legs that carry straight on at the same speed are joined,
    because MoveIt plans a straight line in one piece.
    """
    points = chunk.waypoints
    legs = [Leg(points[0].x, points[0].y, points[0].z, points[0].heading, DESCEND_SPEED)]
    starts = [None]
    for a, b in zip(points, points[1:], strict=False):
        step = np.array([b.x - a.x, b.y - a.y, b.z - a.z])
        length = float(np.linalg.norm(step))
        if length < 1e-9 and abs(b.heading - a.heading) < 1e-9:
            continue
        leg = Leg(b.x, b.y, b.z, b.heading, min(TOP_SPEED, length / WAYPOINT_PERIOD))
        last, start = legs[-1], starts[-1]
        if start is not None and _joins(start, last, leg):
            legs[-1] = Leg(leg.x, leg.y, leg.z, leg.heading, last.speed)
        else:
            legs.append(leg)
            starts.append(a)
    return legs


def _joins(start: Waypoint, last: Leg, leg: Leg) -> bool:
    """Whether ``leg`` carries straight on from ``last``, which began at ``start``, at the same speed."""
    if abs(leg.heading - last.heading) > 1e-6:
        return False
    if abs(leg.speed - last.speed) > SAME_SPEED * max(last.speed, 1e-9):
        return False
    one = np.array([last.x - start.x, last.y - start.y, last.z - start.z])
    two = np.array([leg.x - last.x, leg.y - last.y, leg.z - last.z])
    norms = float(np.linalg.norm(one) * np.linalg.norm(two))
    if norms < 1e-12:
        return False
    return math.acos(float(np.clip(one @ two / norms, -1.0, 1.0))) <= STRAIGHT_ON


def comes_down(legs: list[Leg]) -> bool:
    """Whether a path goes below travel height, where it can move a glass."""
    return any(leg.z < TRAVEL - 1e-6 for leg in legs)


class Numbers:
    """Gives each glass the same number from one look to the next, as the jaw-only cell did."""

    def __init__(self) -> None:
        self.where: dict[int, tuple[float, float]] = {}

    def seen(self, boxes: list[Box]) -> tuple[tuple[Seen, ...], dict[int, int]]:
        """The boxes as numbered glasses, and which box each number is."""
        pairs = sorted(
            (math.dist((box.x, box.y), spot), k, number)
            for k, box in enumerate(boxes)
            for number, spot in self.where.items()
        )
        number_of: dict[int, int] = {}
        taken: set[int] = set()
        for gap, k, number in pairs:
            if gap < MATCH and k not in number_of and number not in taken:
                number_of[k] = number
                taken.add(number)
        fresh = max(self.where, default=-1) + 1
        for k in range(len(boxes)):
            if k not in number_of:
                number_of[k], fresh = fresh, fresh + 1
        for k, box in enumerate(boxes):
            self.where[number_of[k]] = (box.x, box.y)
        seen = tuple(
            Seen(
                number_of[k],
                box.x,
                box.y,
                box.height,
                2 * box.radius,
                2 * (box.foot or box.radius),
                True,
            )
            for k, box in enumerate(boxes)
        )
        return seen, {number: k for k, number in number_of.items()}

    def aimed(self, number: int, aim: tuple[float, float]) -> None:
        """Where a pushed glass should now be, so that it keeps its number when it is found there."""
        self.where[number] = (float(aim[0]), float(aim[1]))


def _waypoint(pose: Pose) -> Waypoint:
    return Waypoint(pose.x, pose.y, pose.z, pose.heading)


def _view_at(pose: Pose) -> int | None:
    """Which viewing pose the hand is at, if any."""
    return next((k for k, view in enumerate(VIEWS) if _at(pose, view)), None)


def _at(here: Pose, there: Pose) -> bool:
    turn = abs((here.heading - there.heading + math.pi) % (2 * math.pi) - math.pi)
    return math.dist((here.x, here.y, here.z), (there.x, there.y, there.z)) < 0.02 and turn < 0.05


class OnTheArm:
    """One jaw-only solution, clearing a table with the whole arm."""

    def __init__(self, inner, see=None) -> None:
        self.inner = inner
        self.name = f"{inner.name}, on the arm"
        self.tables = 0
        # How a picture becomes boxes: the box model, unless a test says otherwise.
        self.see = see

    def clear(self, run: Run) -> None:
        # The jaw-only cell told a solution its table number. The arm's examiner
        # keeps that to itself, so a solution is told how many tables it has met.
        # None of the five reads it for anything but a fresh start.
        self.tables += 1
        self.inner.begin(self.tables)
        eyes = Eyes(run.arm, AS_NEEDED, self.see)
        numbers = Numbers()
        boxes = eyes.look()
        if boxes is None:
            run.finish(f"the arm cannot get to a place to look from: {eyes.why}")
            return
        seen, box_of = numbers.seen(boxes)
        # The viewing pose whose picture the eyes have just taken, so the first
        # look after a round of looking needs no new picture.
        fresh = _view_at(run.arm.pose())
        refused = ""
        while True:
            pose = run.arm.pose()
            if fresh is not None and _at(pose, VIEWS[fresh]):
                picture = eyes.pictures[fresh]
            else:
                picture = run.arm.camera.capture().image
            fresh = None
            look = Look(picture, seen, _waypoint(pose), run.clock.left, refused)
            answer = self.inner.answer(look)
            if isinstance(answer, Done):
                run.finish(answer.why or "the solution said it had finished")
                return
            legs = legs_of(answer)
            glass = box_of.get(answer.glass)
            moved = run.arm.follow(legs, boxes, glass, PATH)
            if moved.end == REFUSED:
                refused = moved.why
                continue
            refused = ""
            if comes_down(legs):
                numbers.aimed(answer.glass, answer.aim)
                if glass is not None:
                    eyes.expected = _aimed(boxes, glass, answer.aim)
                boxes = eyes.look()
                if boxes is None:
                    run.finish(f"the arm cannot get to a place to look from: {eyes.why}")
                    return
                seen, box_of = numbers.seen(boxes)
                fresh = _view_at(run.arm.pose())


def _aimed(boxes: list[Box], glass: int, aim: tuple[float, float]) -> list[Box]:
    """The boxes as they should be after a push, with the pushed glass where it was aimed."""
    box = boxes[glass]
    heading = math.atan2(aim[1] - box.y, aim[0] - box.x)
    return after(boxes, Request(glass, heading, math.dist((box.x, box.y), aim), PATH))


# --------------------------------------------------------------- the five solutions
#
# Each folder's own modules are imported by their plain names, as that folder's own
# runner imports them, so its folder goes on the path first. Only one is built in a
# process, because two of them have modules of the same name.


def _from(folder: str, module: str):
    path = str(PROBLEM / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module(module)


def one_fixed_nudge(weights: Path | None = None) -> OnTheArm:
    """Solution 1: the geometry reference. Nothing in it is trained."""
    return OnTheArm(_from("01-one-fixed-nudge", "nudge").OneFixedNudge())


def geometry_ranked(weights: Path | None = None) -> OnTheArm:
    """Solution 2: solution 1's loop, with problem 3's fitted trees ordering the pushes."""
    return OnTheArm(_from("02-geometry-ranked", "ranked").GeometryRanked())


def imitation(weights: Path | None = None) -> OnTheArm:
    """Solution 3: the gate and the chunked policy, fitted at one seed (seed 0 unless named)."""
    runner = _from("03-imitation-from-demonstrations", "run")
    folder = weights or runner.fits(0, 1)[0]
    return OnTheArm(runner.built(folder))


def world_model(weights: Path | None = None) -> OnTheArm:
    """Solution 4: the jaw-only cell's fitted model of what a push does, and its search."""
    learned = _from("04-a-world-model", "learned")
    model = None if weights is None else learned.Ensemble.load(weights)
    return OnTheArm(learned.WorldModel(model))


def smolvla(weights: Path | None = None) -> OnTheArm:
    """Solution 6: SmolVLA with the correction fitted at one seed (seed 0 unless named)."""
    fine_tuned = _from("06-smolvla-fine-tuned", "fine_tuned")
    folder = weights or importlib.import_module("weights").fitted(1)[0]
    return OnTheArm(fine_tuned.FineTuned(fine_tuned.load(folder)))
