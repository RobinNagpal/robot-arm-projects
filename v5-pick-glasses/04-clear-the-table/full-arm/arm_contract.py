"""What passes between a solution and the examiner in the full-arm cell.

This file holds shapes and no behaviour, so that every other file can agree on them.
There are three parties, and each owns different things.

**The arm** is a physical thing. It has a camera on its wrist, it knows where its hand
is, and it moves in two ways: a free move to a pose, and a push. MoveIt plans every
motion before the arm starts, so a move MoveIt cannot plan is refused and the arm stays
where it was. A move that has started can still stop before its goal, and the result
says where the hand really is.

**The run** is one attempt at one table. It holds the arm, the clock and the state of
the attempt. The solution ends the attempt by calling ``finish``. The examiner ends it
when a glass goes over or the time runs out, and from then on every call to the arm or
the camera raises ``RunOver``.

**The examiner** builds the table, keeps the table number to itself, and marks the table
when the run ends. The table number is also the random seed that drew the glasses, so a
solution is never given it.

The solution is handed only a ``Run``. How often it looks, from where, and when it pushes
are all its own choices; the only thing it must do is say when it has finished.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from pusher import Box, Request, Settings

__all__ = [
    "Arm",
    "Box",
    "Camera",
    "Clock",
    "Examiner",
    "Frame",
    "MoveEnd",
    "Moved",
    "Pose",
    "PushRequest",
    "PushStage",
    "Pushed",
    "Run",
    "RunOver",
    "RunState",
    "Settings",
    "Solution",
    "TableResult",
]

# One push, as a solution asks for it. The name the rest of the code uses is ``Request``.
PushRequest = Request


@dataclass(frozen=True)
class Pose:
    """Where the fingertips are and which way the hand points, seen from above.

    ``x`` and ``y`` are metres on the table, ``z`` is metres above the table top, and
    ``heading`` is in radians.
    """

    x: float
    y: float
    z: float
    heading: float


@dataclass(frozen=True)
class Frame:
    """One picture from the wrist camera."""

    image: np.ndarray  # rows x columns x 3 colour values
    pose: Pose  # where the hand was when the picture was taken
    time: float  # arm seconds into the run


MoveEnd = Literal["reached", "stopped", "refused"]
REACHED: MoveEnd = "reached"  # the arm got to the goal
STOPPED: MoveEnd = "stopped"  # the arm started, but stopped before the goal
REFUSED: MoveEnd = "refused"  # MoveIt found no plan, or it did not fit the time; the arm did not move


@dataclass(frozen=True)
class Moved:
    end: MoveEnd
    why: str  # the reason, when it stopped or was refused
    pose: Pose  # where the hand really is now
    seconds: float  # arm time this move used


PushStage = Literal["approach", "drop", "stroke", "retreat", "lift"]


@dataclass(frozen=True)
class Pushed(Moved):
    stages_done: tuple[PushStage, ...] = ()  # the motions that finished, in order
    touched: bool = False  # whether the wrist felt the glass during the stroke


class Camera(Protocol):
    width: int  # pixels
    height: int
    focal_length: float  # pixels

    def capture(self) -> Frame:
        """A picture from where the hand is now.

        It costs a little arm time, because the arm must stand still while it is taken.
        """
        ...


class Arm(Protocol):
    camera: Camera

    def pose(self) -> Pose: ...

    def move_to(self, pose: Pose, settings: Settings, scene: list[Box]) -> Moved:
        """A free move, planned by MoveIt round ``scene`` with each box grown by ``settings.padding``."""
        ...

    def push(self, request: Request, scene: list[Box]) -> Pushed:
        """One push of ``scene[request.glass]``, every motion of it planned before the arm moves."""
        ...


RunState = Literal["running", "finished", "a glass went over", "out of time"]
RUNNING: RunState = "running"
FINISHED: RunState = "finished"
GLASS_OVER: RunState = "a glass went over"
OUT_OF_TIME: RunState = "out of time"


class Clock(Protocol):
    @property
    def used(self) -> float:  # arm seconds used on this table
        ...

    @property
    def left(self) -> float:  # arm seconds left for this table
        ...


class Run(Protocol):
    arm: Arm
    clock: Clock

    @property
    def state(self) -> RunState: ...

    def finish(self, why: str) -> None:
        """The solution says it has finished. ``why`` is kept for the record and never scored."""
        ...


class RunOver(Exception):
    """Raised by any arm or camera call once the run's state is no longer ``running``."""

    def __init__(self, state: RunState) -> None:
        super().__init__(state)
        self.state = state


class Solution(Protocol):
    name: str

    def clear(self, run: Run) -> None:
        """Look, decide, push, and so on, and then ``run.finish(why)``."""
        ...


@dataclass(frozen=True)
class TableResult:
    """One table, as the examiner found it when the run ended."""

    table: int
    glasses: int
    separated_at_start: int  # glasses the gripper could pick at the start
    separated_at_end: int
    fell_over: int
    ended_by: RunState
    arm_seconds: float
    # For the record, and not part of the mark.
    pushes_asked: int = 0  # every push asked for, refused ones included
    thinking_seconds: float = 0.0  # wall time spent deciding, with the physics and MoveIt taken off
    why: str = ""  # the solution's reason, when it finished


class Examiner(Protocol):
    def start(self, table: int) -> Run: ...

    def result(self, run: Run) -> TableResult: ...

    def run(self, solution: Solution, table: int) -> TableResult: ...
