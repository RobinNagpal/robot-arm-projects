"""What passes between a solution and the examiner.

This file holds shapes and no behaviour, so that every other file can agree on them.
There are three parties, and each owns different things.

**The arm** is a physical thing. It has a camera on its wrist, it knows where its hand
is, and it moves in two ways: a free move of the hand to a pose, and a push of one glass.
MoveIt plans every motion before the arm starts, so a move MoveIt cannot plan is refused
and the arm stays where it was. A move that has started can still stop before its goal,
and the result says where the hand really is.

**The table attempt** is one attempt at one table. It holds the arm, the clock and the
state of the attempt. The solution ends the attempt by calling ``declare_finished``. The
examiner ends it when a glass goes over or the time runs out, and from then on every call
to the arm or the camera raises ``TableAttemptOver``.

**The examiner** builds the table, keeps the table number to itself, and marks the table
when the attempt ends. The table number is also the random seed that drew the glasses, so
a solution is never given it.

The solution is handed only a ``TableAttempt``. How often it looks, from where, and when it
pushes are all its own choices; the only thing it must do is say when it has finished.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from examiner.motion.push_motions import GlassBox, MoveItSettings, PushRequest

__all__ = [
    "Arm",
    "ArmClock",
    "AttemptState",
    "Examiner",
    "GlassBox",
    "HandPose",
    "MoveItSettings",
    "MoveOutcome",
    "MoveResult",
    "PushMotionStage",
    "PushRequest",
    "PushResult",
    "Solution",
    "TableAttempt",
    "TableAttemptOver",
    "TableResult",
    "WristCamera",
    "WristPicture",
]


@dataclass(frozen=True)
class HandPose:
    """Where the fingertips are and which way the hand points, seen from above.

    ``x`` and ``y`` are metres on the table, ``z`` is metres above the table top, and
    ``heading`` is in radians.
    """

    x: float
    y: float
    z: float
    heading: float


@dataclass(frozen=True)
class WristPicture:
    """One picture from the wrist camera."""

    image: np.ndarray  # rows x columns x 3 colour values
    hand_pose: HandPose  # where the hand was when the picture was taken
    arm_seconds_into_attempt: float  # when it was taken, in arm seconds since the attempt started


MoveOutcome = Literal["reached", "stopped", "refused"]
REACHED: MoveOutcome = "reached"  # the arm got to the goal
STOPPED: MoveOutcome = "stopped"  # the arm started, but stopped before the goal
REFUSED: MoveOutcome = "refused"  # MoveIt found no plan, or it did not fit the time; the arm did not move


@dataclass(frozen=True)
class MoveResult:
    """What happened to one move of the arm."""

    outcome: MoveOutcome
    reason: str  # why it stopped or was refused, and empty when it reached its goal
    hand_pose: HandPose  # where the hand really is now
    arm_seconds: float  # arm time this move used


PushMotionStage = Literal["approach", "drop", "stroke", "retreat", "lift"]


@dataclass(frozen=True)
class PushResult(MoveResult):
    """What happened to one push: a move, and the motions of the push that were completed."""

    motion_stages_completed: tuple[PushMotionStage, ...] = ()  # in the order they were made
    wrist_felt_the_glass: bool = False  # whether the wrist felt the glass during the stroke


class WristCamera(Protocol):
    width: int  # pixels
    height: int
    focal_length: float  # pixels

    def take_picture(self) -> WristPicture:
        """A picture from where the hand is now.

        It costs a little arm time, because the arm must stand still while it is taken.
        """
        ...


class Arm(Protocol):
    wrist_camera: WristCamera

    def hand_pose(self) -> HandPose: ...

    def move_hand_to(
        self, hand_pose: HandPose, settings: MoveItSettings, obstacle_boxes: list[GlassBox]
    ) -> MoveResult:
        """A free move, planned by MoveIt round ``obstacle_boxes``, each grown by ``settings.padding``."""
        ...

    def push_glass(self, request: PushRequest, glass_boxes: list[GlassBox]) -> PushResult:
        """One push of ``glass_boxes[request.glass]``, every motion of it planned before the arm moves."""
        ...


AttemptState = Literal["running", "finished", "a glass went over", "out of time"]
RUNNING: AttemptState = "running"
FINISHED: AttemptState = "finished"
GLASS_OVER: AttemptState = "a glass went over"
OUT_OF_TIME: AttemptState = "out of time"


class ArmClock(Protocol):
    @property
    def arm_seconds_used(self) -> float:  # arm seconds used on this table
        ...

    @property
    def arm_seconds_left(self) -> float:  # arm seconds left for this table
        ...


class TableAttempt(Protocol):
    arm: Arm
    clock: ArmClock

    @property
    def state(self) -> AttemptState: ...

    def declare_finished(self, reason: str) -> None:
        """The solution says it has finished. ``reason`` is kept for the record and never scored."""
        ...


class TableAttemptOver(Exception):
    """Raised by any arm or camera call once the attempt's state is no longer ``running``."""

    def __init__(self, state: AttemptState) -> None:
        super().__init__(state)
        self.state = state


class Solution(Protocol):
    name: str

    def clear_table(self, attempt: TableAttempt) -> None:
        """Look, decide, push, and so on, and then ``attempt.declare_finished(reason)``."""
        ...


@dataclass(frozen=True)
class TableResult:
    """One table, as the examiner found it when the attempt ended."""

    table_number: int
    glass_count: int
    pickable_at_start: int  # glasses the gripper could pick at the start
    pickable_at_end: int
    glasses_toppled: int
    ended_by: AttemptState
    arm_seconds: float
    # For the record, and not part of the mark.
    pushes_requested: int = 0  # every push asked for, refused ones included
    thinking_seconds: float = 0.0  # wall time spent deciding, with the physics and MoveIt taken off
    finish_reason: str = ""  # the solution's reason, when it said it had finished


class Examiner(Protocol):
    def start_attempt(self, table_number: int) -> TableAttempt: ...

    def mark_attempt(self, attempt: TableAttempt) -> TableResult: ...

    def run_solution_on_table(self, solution: Solution, table_number: int) -> TableResult: ...
