"""One table, and the queue of tables, in the full-arm cell.

The loop is problem 4's, with the hand-over changed to what a MoveIt cell
needs. Each turn the arm goes to the viewing pose, a picture is taken, the box
model turns it into boxes, and the solution answers with a ``Request`` -- which
glass, which way, how far, and the settings to give MoveIt -- or with ``Done``.
MoveIt then plans and the arm carries out the push, and the turn ends.

**A table ends in the same three ways** as in problem 4: the solution says it is
done, the arm time runs out, or a glass goes over. The marks are problem 4's
own ``TableResult`` and ``Scorecard``, so a number from here is read on the same
scale as a number from there.

**A refused push costs no arm time.** MoveIt plans all four motions of a push
before the arm moves, so a push it cannot plan -- the hand would meet a
neighbour's box, the wrist cannot get round, the posture would flip -- leaves
the arm where it was. The solution is told why, which is the only way it can
learn which pushes the arm can make.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from cell import VIEWS, ArmCell, Memory, Seen3, boxes_from_readings
from moveit_link import MoveItLink
from pusher import Box, Request, Settings  # noqa: F401

from contract import GLASS_OVER, RAN_OUT, SAID_DONE, Done, TableResult
from open_run import ARM_BUDGET, Run
from partners import Waypoint
from scoring import Repeats

# The most answers one table may be given, refusals included. A solution that
# keeps asking for pushes the arm cannot make spends no arm time, so the clock
# cannot stop it; this does.
MAX_ANSWERS = 14

# Under this many arm seconds left, no push can be made: the trip to look
# alone costs more.
LEAST_ACTION = 8.0


@dataclass(frozen=True)
class ArmLook:
    """What a solution is shown at each turn."""

    picture: np.ndarray  # the wrist camera's picture from the viewing pose
    boxes: tuple[Box, ...]  # what the box model found in it
    seconds_left: float
    refused: str = ""  # why the last request was not carried out
    jaw: Waypoint | None = None
    pictures: tuple = ()  # the picture from each viewing place, in the order of ``cell.VIEWS``


class ArmSolution(Protocol):
    name: str

    def begin(self, seed: int) -> None: ...

    def decide(self, look: ArmLook) -> Request | Done: ...


Perceive = Callable[[Seen3], list[Box]]


def from_readings(look: Seen3) -> list[Box]:
    """Problem 2's readings as boxes: the baseline's way of seeing, with no learned model in it."""
    return boxes_from_readings(look.measured)


@dataclass
class Tally:
    """Diagnosis that is not part of the mark: why pushes were refused, how often MoveIt was asked."""

    tables: int = 0
    pushes: int = 0
    refusals: int = 0
    refused_because: dict = field(default_factory=dict)
    planning_seconds: float = 0.0


def clear_table(
    solution: ArmSolution,
    seed: int,
    seconds_left: float,
    link: MoveItLink,
    perceive: Perceive = from_readings,
    *,
    tally: Tally | None = None,
    cell: ArmCell | None = None,
) -> TableResult:
    tally = Tally() if tally is None else tally
    cell = ArmCell(seed, link) if cell is None else cell
    began = time.perf_counter()
    solution.begin(seed)
    ended_by, refused, answers = RAN_OUT, "", 0
    planning_before = link.planning_seconds
    previous: list[Box] = []
    try:
        while True:
            left = seconds_left - cell.arm_seconds
            if left < LEAST_ACTION:
                break
            # Both viewing places every turn, nearest first. A glass that was
            # pushed may have landed out of sight of the first pose, and a box
            # that is missing is a glass the arm will strike, so the cost of the
            # second look is paid every time rather than only once.
            memory = Memory()
            failed = False
            taken: dict[int, np.ndarray] = {}
            here = cell.bench.tcp()
            for view in sorted(VIEWS, key=lambda v: math.dist((v.x, v.y), (here.x, here.y))):
                if not _at(cell, view):
                    # The first trip of a turn starts from the last push, and
                    # every glass but the one pushed is where it was; the second
                    # is made knowing only what the first look showed.
                    cell.known = list(memory.boxes) if memory.boxes else list(previous)
                    ok, why = cell.go_to_view(
                        seconds_left - cell.arm_seconds, view, blind=bool(memory.boxes) or not previous
                    )
                    if not ok:
                        refused = why
                        key = "trip to look: " + why[:110]
                        tally.refused_because[key] = tally.refused_because.get(key, 0) + 1
                        failed = True
                        break
                seen = cell.look()
                taken[VIEWS.index(view)] = seen.picture
                memory.update(perceive(seen))
            if failed:
                break
            boxes = list(memory.boxes)
            answer = solution.decide(
                ArmLook(
                    seen.picture,
                    tuple(boxes),
                    seconds_left - cell.arm_seconds,
                    refused,
                    seen.jaw,
                    tuple(taken[k] for k in sorted(taken)),
                )
            )
            answers += 1
            refused = ""
            if isinstance(answer, Done):
                ended_by = SAID_DONE
                break
            result = cell.push(boxes, answer, seconds_left - cell.arm_seconds)
            if result.ok:
                previous = _after(boxes, answer)
                tally.pushes += 1
                if cell.toppled():
                    ended_by = GLASS_OVER
                    break
            else:
                tally.refusals += 1
                refused = result.why
                key = result.why.split(":")[0]
                tally.refused_because[key] = tally.refused_because.get(key, 0) + 1
                if "are left" in result.why:
                    break
            if answers >= MAX_ANSWERS:
                break
        thinking = max(
            0.0,
            (time.perf_counter() - began) - cell.bench.seconds - (link.planning_seconds - planning_before),
        )
        tally.tables += 1
        tally.planning_seconds += link.planning_seconds - planning_before
        return TableResult(
            seed=seed,
            glasses=cell.glasses(),
            pickable_at_start=cell.pickable_at_start,
            pickable_at_end=cell.pickable(),
            toppled=cell.toppled(),
            ended_by=ended_by,
            arm_seconds=cell.arm_seconds,
            thinking_seconds=thinking,
            answers=answers,
        )
    finally:
        cell.close()


def _after(boxes: list[Box], request: Request) -> list[Box]:
    """The boxes as they should be after a push: the pushed glass where it was aimed, with room to spare."""
    pushed = boxes[request.glass]
    moved = Box(
        pushed.x + request.travel * math.cos(request.heading),
        pushed.y + request.travel * math.sin(request.heading),
        pushed.radius + 0.02,
        pushed.height,
        pushed.foot,
    )
    return [b for i, b in enumerate(boxes) if i != request.glass] + [moved]


def _at(cell: ArmCell, view: Waypoint) -> bool:
    jaw = cell.bench.tcp()
    gap = abs((jaw.heading - view.heading + math.pi) % (2 * math.pi) - math.pi)
    return math.dist((jaw.x, jaw.y, jaw.z), (view.x, view.y, view.z)) < 0.02 and gap < 0.05


def clear_queue(
    build: Callable[[], ArmSolution],
    seeds: Sequence[int],
    link: MoveItLink,
    perceive: Perceive = from_readings,
    budget: float = ARM_BUDGET,
    tally: Tally | None = None,
    log: Callable[[str], None] | None = None,
) -> Run:
    run = Run(budget=budget, seeds=tuple(seeds))
    solution = build()
    for seed in run.seeds:
        if run.left < LEAST_ACTION:
            break
        result = clear_table(solution, seed, run.left, link, perceive, tally=tally)
        if result.never_reached:
            continue
        run.results.append(result)
        if log:
            log(
                f"table {seed}: {result.pickable_at_start}->{result.pickable_at_end}/{result.glasses} "
                f"pickable, {result.arm_seconds:.0f} arm s, {result.answers} answers, {result.ended_by}, "
                f"toppled {result.toppled}"
            )
    return run


def judge(
    build: Callable[[], ArmSolution],
    link: MoveItLink,
    perceive: Perceive,
    first: int,
    tables: int,
    runs: int = 1,
    budget: float = ARM_BUDGET,
    log: Callable[[str], None] | None = print,
) -> tuple[dict, Tally, list[list[dict]]]:
    """Walk the queue ``runs`` times: problem 4's scorecard, the tally, and every table's own row."""
    repeats = Repeats()
    tally = Tally()
    rows: list[list[dict]] = []
    for walk in range(runs):
        card = repeats.run()
        started = time.perf_counter()
        run = clear_queue(build, list(range(first, first + tables)), link, perceive, budget, tally, log)
        for result in run.results:
            card.table(result)
        rows.append(card.tables)
        if log:
            log(
                f"run {walk + 1}/{runs}: {run.attempted} tables, {run.arm_seconds:.0f} arm s, "
                f"{time.perf_counter() - started:.0f} s of laptop time"
            )
    return repeats.summary(), tally, rows


def headline(summary: dict) -> str:
    """The numbers a run is read by, on one line; with the spread when there are several runs."""
    spread = summary["spread"]

    def mid(key: str) -> str:
        entry = spread[key]
        if summary["runs"] > 1:
            return f"{entry['median']:g} (sd {entry['sd']:.2g})"
        return f"{entry['median']:g}"

    return (
        f"tables {mid('tables_attempted')}, glasses {mid('glasses')}, "
        f"pickable {mid('glasses_end.pickable_at_start')} -> {mid('glasses_end.pickable')} "
        f"(share {mid('glasses_end.pickable_share')}), broken {mid('glasses_end.broken')}, "
        f"separated {mid('outcome.separated')}, failed {mid('outcome.failed')}, "
        f"unfinished {mid('outcome.unfinished')}, "
        f"said done {mid('ended_by.said_done')}, arm s {mid('arm_seconds.total')}"
    )
