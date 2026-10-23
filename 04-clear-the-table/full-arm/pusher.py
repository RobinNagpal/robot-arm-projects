"""One push, carried out by MoveIt on the whole arm.

This is the file where the four jobs of the full-arm track meet, so it is worth
saying what each job is and where its answer enters.

1. **A box round each glass** is an input. It comes from the box model
   (``seeing.py``), not from the simulator, and it is what MoveIt is told the
   world contains.
2. **Where the glass should go** is an input. It comes from the solution's
   learned decision as a direction and a distance.
3. **What to tell MoveIt** is an input. The solution's second learned decision
   is a handful of settings -- how fast, how high, how much room to leave --
   and they are passed on unchanged.
4. **The motion** is MoveIt's. This file asks MoveIt for four motions in turn
   and runs each one on the arm in the simulator: a free move to a point just
   behind the glass, a straight drop to pushing height, the straight stroke
   itself, and a straight retreat. Nothing in this file moves the arm any
   other way, and nothing in it chooses a joint angle.

The order matters and is the reason ``plan`` is given the later lines to check.
A UR arm reaches one pose in up to eight postures, and holding a level hand
low over a table is possible in only some of them. A posture that arrives
behind the glass but cannot then drop to pushing height without the forearm
meeting the table is useless, so the planner is told about the drop and the
stroke when it picks where to arrive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
from arm_simulator import ArmSimulator
from moveit_link import Motion, MoveItLink, flange_goal
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

from partners import STANDING_TILT_DEG

# How high the hand travels between pushes: clear of the tallest glass drawn.
# Not a learned setting: it is a property of the cell, as problem 3's
# TRAVEL_HEIGHT is, and it is the same for every solution.
TRAVEL = 0.30

# MoveIt's table is a little lower than the real one. The hand's collision
# model in the URDF is the real gripper's meshes and the simulator's is the
# boxes drawn from them; at pushing height the two differ by millimetres and a
# table at its true height would call the fingers touching it.
TABLE_SLACK = 0.004

# How far the hand backs off after a stroke before it lifts, so that it does
# not drag the glass it has just placed back with it.
BACK_OFF = 0.03


@dataclass(frozen=True)
class Box:
    """One glass, as a box MoveIt can avoid: where it stands and how much room it takes."""

    x: float
    y: float
    radius: float  # half the width of the box
    height: float
    foot: float = 0.0  # half the width where the glass stands on the table; 0 when not known


@dataclass(frozen=True)
class Settings:
    """What the learned model passes to MoveIt.

    Every field is a MoveIt setting or a number MoveIt is given, which is the
    meaning of "the model passes the parameters and MoveIt does the movement".
    """

    push_height: float  # how high the middle of the hand rides during the stroke, metres above the table
    stroke_speed: float  # velocity and acceleration scaling for the stroke line
    approach_speed: float  # the same for the free move and the drop
    padding: float  # room added round every box before MoveIt sees it, metres
    standoff: float  # how far behind the glass's box the hand comes down, metres
    # how much further than the box says the stroke goes: glasses narrow away from their widest point
    overreach: float = 0.012

    @staticmethod
    def default() -> Settings:
        return Settings(
            push_height=0.085,
            stroke_speed=0.05,
            approach_speed=0.4,
            padding=0.01,
            standoff=0.03,
            overreach=0.012,
        )


@dataclass(frozen=True)
class Request:
    """One push, as a solution asks for it: which glass, which way, how far, and with what settings."""

    glass: int  # an index into the boxes handed over
    heading: float  # the way the hand pushes, radians
    travel: float  # how far the glass is to move, metres
    settings: Settings


@dataclass(frozen=True)
class Leg:
    """One straight stretch of a path, as a jaw-only solution writes one.

    The fingertips go in a straight line to ``x``, ``y`` and ``z`` (metres above the
    table top), pointing along ``heading``, no faster than ``speed`` metres a second.
    A speed of zero means as fast as the settings allow.
    """

    x: float
    y: float
    z: float
    heading: float
    speed: float = 0.0


@dataclass
class Pushed:
    """What happened. ``ok`` is false when MoveIt had no motion to give, and then the arm did not move."""

    ok: bool
    why: str = ""
    arm_seconds: float = 0.0
    peak_force: float = 0.0
    touched: bool = False
    touch_at: object = None  # the fingertips' place at the first touch, for calibration
    stages: list = field(default_factory=list)
    stopped: bool = False  # ``stop_when`` ended it before the last motion


def table_box() -> dict:
    return {
        "id": "table",
        "centre": [TABLE_CENTRE_XY[0], TABLE_CENTRE_XY[1], TABLE_TOP_Z - TABLE_SLACK - TABLE_SIZE[2] / 2],
        "size": [TABLE_SIZE[0], TABLE_SIZE[1], TABLE_SIZE[2]],
    }


def scene_boxes(boxes: list[Box], padding: float) -> list[dict]:
    """The table and a box round every glass, each grown by ``padding`` on every side."""
    world = [table_box()]
    for k, box in enumerate(boxes):
        side = 2 * (box.radius + padding)
        high = box.height + padding
        world.append(
            {"id": f"glass_{k}", "centre": [box.x, box.y, TABLE_TOP_Z + high / 2], "size": [side, side, high]}
        )
    return world


class Pusher:
    """Pushes glasses with the arm, asking MoveIt for every motion."""

    def __init__(self, simulator: ArmSimulator, link: MoveItLink) -> None:
        self.simulator = simulator
        self.link = link

    def goals(self, boxes: list[Box], request: Request) -> dict:
        """The four poses of a push, worked out from the target's box and the settings."""
        box, s = boxes[request.glass], request.settings
        push = np.array([math.cos(request.heading), math.sin(request.heading)])
        centre = np.array([box.x, box.y])
        # The hand comes down far enough behind the box that the box, grown by
        # its padding, is not touching it; otherwise MoveIt would call the
        # start of the drop a collision.
        start = centre - (box.radius + s.padding + s.standoff) * push
        # The glass is to move ``travel``. The fingertips end that far along
        # their line, less the glass's own radius, because it is the glass's
        # near edge they meet. The box is as wide as the glass is anywhere, and
        # the hand usually meets it where it is narrower -- measured, 17 mm
        # narrower on a stemmed glass -- so the stroke is lengthened by
        # ``overreach`` to make up the difference.
        end = centre + (request.travel + s.overreach - box.radius) * push
        back = end - BACK_OFF * push
        z_travel, z_push = TABLE_TOP_Z + TRAVEL, TABLE_TOP_Z + s.push_height
        name = f"glass_{request.glass}"
        return {
            "above": flange_goal(*start, z_travel, request.heading),
            "down": flange_goal(*start, z_push, request.heading),
            "stroke": flange_goal(*end, z_push, request.heading, without=name),
            "back": flange_goal(*back, z_push, request.heading, without=name),
            "up": flange_goal(*back, z_travel, request.heading, without=name),
        }

    def push(
        self, boxes: list[Box], request: Request, seconds_left: float = math.inf, stop_when=None
    ) -> Pushed:
        """Plan the four motions, and only if all of them can be made, carry them out.

        Planning everything first is deliberate. A push that was half carried
        out -- the hand down beside a glass and unable to stroke it -- leaves
        the arm in a place the next plan may not be able to leave. Asking for
        all four before moving costs nothing in arm time, because planning is
        not arm time, and it means a refusal leaves the arm where it was.

        ``stop_when``, when given, is asked after each motion, and a true answer
        stops the push there: the arm holds where that motion ended.
        """
        s, simulator, link = request.settings, self.simulator, self.link
        goals = self.goals(boxes, request)
        link.scene(scene_boxes(boxes, s.padding))
        q0 = simulator.joints()

        approach = link.plan(
            q0,
            goals["above"],
            then=[goals["down"], goals["stroke"]],
            vel=s.approach_speed,
            acc=s.approach_speed,
        )
        if not approach.ok:
            return Pushed(False, f"no way to the start of the push: {approach.why}")
        q_above = approach.joints[-1]
        drop = link.line(q_above, goals["down"], vel=s.approach_speed, acc=s.approach_speed)
        if not drop.ok:
            return Pushed(False, f"no way down to pushing height: {drop.why}")
        stroke = link.line(drop.joints[-1], goals["stroke"], vel=s.stroke_speed, acc=s.stroke_speed)
        if not stroke.ok:
            return Pushed(False, f"no stroke: {stroke.why}")
        retreat = link.line(stroke.joints[-1], goals["back"], vel=s.stroke_speed, acc=s.stroke_speed)
        lift = (
            link.line(retreat.joints[-1], goals["up"], vel=s.approach_speed, acc=s.approach_speed)
            if retreat.ok
            else retreat
        )
        if not (retreat.ok and lift.ok):
            return Pushed(False, f"no way back out: {(retreat if not retreat.ok else lift).why}")

        needed = sum(m.seconds for m in (approach, drop, stroke, retreat, lift))
        if needed > seconds_left:
            # A push is never cut short to fit: half a stroke leaves the hand
            # standing against a glass, which is worse than not starting.
            return Pushed(
                False, f"the push needs {needed:.1f} s and {seconds_left:.1f} s are left", arm_seconds=0.0
            )

        motions = [("approach", approach), ("drop", drop), ("stroke", stroke), ("retreat", retreat)]
        return self._carry_out([*motions, ("lift", lift)], stop_when)

    def follow(
        self,
        boxes: list[Box],
        legs: list[Leg],
        glass: int | None,
        settings: Settings,
        seconds_left: float = math.inf,
        stop_when=None,
    ) -> Pushed:
        """A path of straight lines, the way a jaw-only solution writes one, carried out by MoveIt.

        The hand goes by a free move to travel height above the first point, down
        to it in a straight line, along every leg in a straight line, and straight
        back up to travel height at the end. As with a push, every motion is
        planned before the arm moves, so a path MoveIt cannot make leaves the arm
        where it was. ``glass`` is the glass the path means to push: its box is
        left out of the collision check once the hand is down, because the hand is
        meant to touch it. Every other box stays in.

        A leg is never run faster than MoveIt planned it. When it asks to be
        slower, its timing is stretched evenly, which keeps the path and lowers
        every speed and acceleration along it.
        """
        simulator, link = self.simulator, self.link
        name = None if glass is None else f"glass_{glass}"
        link.scene(scene_boxes(boxes, settings.padding))
        first, last = legs[0], legs[-1]
        z_travel = TABLE_TOP_Z + TRAVEL
        goals = [
            flange_goal(leg.x, leg.y, TABLE_TOP_Z + leg.z, leg.heading, without=name if k else None)
            for k, leg in enumerate(legs)
        ]
        approach = link.plan(
            simulator.joints(),
            flange_goal(first.x, first.y, z_travel, first.heading),
            then=goals[:2],
            vel=settings.approach_speed,
            acc=settings.approach_speed,
        )
        if not approach.ok:
            return Pushed(False, f"no way to the start of the path: {approach.why}")
        motions = [("approach", approach)]
        q = approach.joints[-1]
        here = np.array([first.x, first.y, TRAVEL])
        ends = list(zip(legs, goals, strict=True))
        if last.z < TRAVEL - 1e-6:
            up = flange_goal(last.x, last.y, z_travel, last.heading, without=name)
            ends.append((Leg(last.x, last.y, TRAVEL, last.heading), up))
        for k, (leg, goal) in enumerate(ends):
            there = np.array([leg.x, leg.y, leg.z])
            length = float(np.linalg.norm(there - here))
            if length < 1e-4 and (k == 0 or abs(leg.heading - ends[k - 1][0].heading) < 1e-6):
                continue
            line = link.line(q, goal, vel=settings.approach_speed, acc=settings.approach_speed)
            if not line.ok:
                return Pushed(False, f"no straight way to point {k} of the path: {line.why}")
            motions.append(("drop" if k == 0 else "leg", _no_faster_than(line, length, leg.speed)))
            q, here = line.joints[-1], there

        needed = sum(m.seconds for _, m in motions)
        if needed > seconds_left:
            # A path is never cut short to fit, for the reason a push is not.
            return Pushed(
                False, f"the path needs {needed:.1f} s and {seconds_left:.1f} s are left", arm_seconds=0.0
            )
        return self._carry_out(motions, stop_when)

    def _carry_out(self, motions: list, stop_when=None) -> Pushed:
        """Run planned motions one after another, and say what each one did."""
        simulator = self.simulator
        pushed = Pushed(True)
        positions = [simulator.position(i).copy() for i in range(len(simulator.glasses))]
        for k, (name, motion) in enumerate(motions):
            ran = simulator.run(motion.times, motion.joints)
            pushed.arm_seconds += ran.seconds
            pushed.peak_force = max(pushed.peak_force, ran.peak_force)
            if ran.touched_at is not None and name in ("stroke", "leg") and not pushed.touched:
                pushed.touched = True
                pushed.touch_at = ran.touch_at
            moved = [
                round(1000 * float(np.linalg.norm(simulator.position(i) - positions[i])), 1)
                for i in range(len(positions))
            ]
            pushed.stages.append((name, round(ran.seconds, 2), self.toppled(), moved))
            if stop_when is not None and k < len(motions) - 1 and stop_when():
                pushed.stopped = True
                break
        return pushed

    def toppled(self) -> int:
        return sum(1 for i in self.simulator.on_table() if self.simulator.tilt(i) >= STANDING_TILT_DEG)


def _no_faster_than(motion: Motion, length: float, speed: float) -> Motion:
    """The same motion, its timing stretched evenly so that it covers ``length`` no faster than ``speed``."""
    if speed <= 0.0 or motion.seconds <= 0.0:
        return motion
    wanted = length / speed
    if wanted <= motion.seconds:
        return motion
    return replace(motion, times=np.asarray(motion.times) * (wanted / motion.seconds))
