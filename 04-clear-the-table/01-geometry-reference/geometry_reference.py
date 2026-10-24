"""The reference: problem 3's geometry chooses the push, fixed settings go to MoveIt.

Nothing here is learned. It shows what the arm scores when the decisions are
made by rule, which every learned solution is then measured against.

The choice of glass, direction and distance is problem 3's ``plan.choose``,
loaded from the exact copy of it. It reads the same fields a ``Seen`` carries, so
each box is turned back into one. The settings are one fixed set, picked once for
safety and never adjusted: a slow stroke, low on the glass.

Two things differ from problem 3, because the arm's cell differs from problem 3's.
The arm's hand rides higher, so problem 3's tipping rule is given the arm's top
edge (``problem_3_files_see_the_arm_top_edge``). And a glass that has room stays on the table here, so it is
left out of the choice (``glasses_already_free``).

It looks only as much as it needs (``turn_by_turn_loop.LOOK_ONLY_AS_NEEDED``), because it reads the boxes and
not the pictures.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np

from examiner.motion.push_motions import MoveItSettings, PushRequest
from examiner.simulation import taken_from_problem_3
from examiner.simulation.taken_from_problem_3 import FINGER_HEIGHT, GEOMETRY, Push, Seen
from shared.turn_by_turn_loop import LOOK_ONLY_AS_NEEDED, RefusedGlasses, TableFinished, TurnByTurnSolution

# How much further than the shortest freeing push the stroke goes, metres. See ``choose_push``.
EXTRA_TRAVEL = 0.02

# The shortest stroke worth making. A push of two or three millimetres leans a glass
# onto the hand without sliding it, and the lean is what tips it when the hand
# backs off; so a push is lengthened to this where the geometry allows.
LEAST_TRAVEL = 0.04

# Slow enough that the push is gentle, low enough to meet the glass near its foot.
SAFE_SETTINGS = MoveItSettings(
    push_height=0.085, stroke_speed=0.05, approach_speed=0.4, padding=0.01, standoff=0.03
)

# The top edge of the hand when it pushes at the safe settings' height. The hand is problem
# 3's hand, so its fingers are as tall, but its middle rides at SAFE_SETTINGS.push_height.
HAND_TOP_EDGE = SAFE_SETTINGS.push_height + FINGER_HEIGHT / 2


@contextmanager
def problem_3_files_see_the_arm_top_edge() -> Iterator[None]:
    """Problem 3's names, with the hand's top edge where the arm carries it, while problem 3's files load.

    Problem 3's files read the top edge of the hand, as ``JAW_TOP``, from a module
    they call ``bench``. Problem 3's hand rides with its middle at 75 mm, so its top
    edge is at 107 mm; the arm's hand rides 10 mm higher, at ``SAFE_SETTINGS.push_height``.
    A glass tips more easily when it is pushed higher, and problem 3's tipping rule
    asks exactly that, so problem 3's files are given the arm's top edge.

    The name is changed only while the files load, and only for them. The table draw
    also asks problem 3's tipping rule, through the ``plan`` the rest of this problem
    imports, and it keeps problem 3's top edge. With any other number it would draw
    other tables, and no result from before the change could be compared with one
    after it.
    """
    arm = types.ModuleType("bench")
    arm.__dict__.update({k: v for k, v in vars(taken_from_problem_3).items() if not k.startswith("__")})
    arm.JAW_TOP = HAND_TOP_EDGE
    before = sys.modules.get("bench")
    sys.modules["bench"] = arm
    try:
        yield
    finally:
        if before is None:
            sys.modules.pop("bench", None)
        else:
            sys.modules["bench"] = before


def _load_problem_3_plan_at_the_arm_top_edge() -> types.ModuleType:
    """Problem 3's solution 1, loaded from its exact copy with the arm's top edge."""
    spec = importlib.util.spec_from_file_location("plan_at_the_arms_height", GEOMETRY / "plan.py")
    module = importlib.util.module_from_spec(spec)
    with problem_3_files_see_the_arm_top_edge():
        spec.loader.exec_module(module)
    return module


plan = _load_problem_3_plan_at_the_arm_top_edge()


def glasses_already_free(readings: list[Seen]) -> set[int]:
    """The glasses that already stand where a push that frees a glass would put them.

    Problem 3 lifts a glass off the table as soon as it has room, so its rule never
    sees one. Here a glass with room stays on the table, and to problem 3's rule it
    looks like the easiest glass of all to free, because the shortest push gives it
    room. Pushing it gains nothing and can tip it. So a glass is left out when it
    already has room by ``plan.AIM_MARGIN``, the margin a freeing push aims for. It
    is still an obstacle that every other push keeps clear of.
    """
    return {glass.id for glass in readings if plan.room(glass, readings, plan.AIM_MARGIN)}


def readings_from_boxes(boxes) -> list[Seen]:
    return [
        Seen(
            id=i,
            x=box.x,
            y=box.y,
            height=box.height,
            widest=2 * box.radius,
            foot=2 * (box.foot or box.radius),
            standing=True,
        )
        for i, box in enumerate(boxes)
    ]


class GeometryReference(TurnByTurnSolution):
    name = "geometry, fixed settings"
    looking_mode = LOOK_ONLY_AS_NEEDED

    def __init__(self, settings: MoveItSettings = SAFE_SETTINGS) -> None:
        self.settings = settings
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass: int | None = None

    def start_new_table(self) -> None:
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass = None

    def decide_turn(self, observation):
        readings = readings_from_boxes(observation.boxes)
        # A push MoveIt refused is not asked for again.
        if observation.last_push_refusal_reason and self.last_requested_glass is not None:
            self.refused_glasses.remember(observation.boxes, self.last_requested_glass)
        push = self.choose_push(
            readings, self.refused_glasses.indices_in_look(observation.boxes) | glasses_already_free(readings)
        )
        if push is None:
            return TableFinished("every glass has room, or none that is left can be pushed")
        self.last_requested_glass = push.glass
        return PushRequest(glass=push.glass, heading=push.heading, travel=push.travel, settings=self.settings)

    def lengthened_push(self, glass, others, heading, push):
        """The same push made EXTRA_TRAVEL longer, if the geometry still finds it clear; otherwise as it was.

        This asks ``plan.along``'s own question again at the longer distance:
        does any stretch of the hand, or the glass itself on its way, come within
        CLEARANCE of a neighbour. The answer is the one problem 3 would give.
        """
        u = np.array([math.cos(heading), math.sin(heading)])
        middle = np.array([glass.x, glass.y])
        radius = glass.widest / 2
        start = middle - (radius + plan.APPROACH_GAP) * u
        travel = max(push.travel + EXTRA_TRAVEL, LEAST_TRAVEL)
        end = middle + travel * u
        if not (plan.in_zone(*end) and plan.reachable(end - plan.FINGERTIP_OFFSET * u)):
            return push
        for other in others:
            centre, other_radius = np.array([other.x, other.y]), other.widest / 2
            passing = min(
                radius + other_radius + plan.CLEARANCE, float(np.linalg.norm(centre - middle)) - 0.001
            )
            swept = any(
                plan.segment_distance(centre, start - far * u, end - near * u)
                < half + other_radius + plan.CLEARANCE
                for near, far, half in plan.JAW_SEGMENTS
            )
            if plan.segment_distance(centre, middle, end) < passing or swept:
                return push
        return Push(push.glass, push.start, heading, push.reach, travel, (float(end[0]), float(end[1])))

    def choose_push(self, readings, glasses_to_skip):
        """Problem 3's choice of the shortest push that frees a glass, lengthened to a push that moves it.

        Problem 3's simulator feels for the glass and then pushes a set distance, so
        it asks for the least that clears. Here the stroke is planned before the
        arm moves and nothing feels for contact, and a stroke that ends a
        millimetre past touching moves a glass by nothing at all: measured,
        pushes of 4 mm on average moved glasses by under a millimetre. So the
        shortest freeing push is lengthened to ``EXTRA_TRAVEL`` more, from the same
        list of pushes the geometry has already checked against every
        neighbour, and no further than the last of them. ``skip`` is the glasses
        not to push.
        """
        shortfall_before = plan.shortfall([(g.x, g.y, g.widest) for g in readings])
        best = None
        for glass in readings:
            if glass.id in glasses_to_skip or plan.slides(glass) == "no":
                continue
            others = [o for o in readings if o.id != glass.id]
            layout = [(o.x, o.y, o.widest) for o in others]
            for heading in np.arange(plan.HEADINGS) * (2 * math.pi / plan.HEADINGS):
                safe = plan.along(glass, others, heading)
                for push in safe:
                    if plan.has_room(*push.aim, layout, plan.AIM_MARGIN):
                        # The first freeing push is the shortest on this heading.
                        push = self.lengthened_push(glass, others, heading, push)
                        if best is None or push.travel < best.travel:
                            best = push
                        break
        if best is not None:
            return best
        # Nothing frees a glass outright; take the push that most eases the table.
        easing = None
        for glass in readings:
            if glass.id in glasses_to_skip or plan.slides(glass) == "no":
                continue
            others = [o for o in readings if o.id != glass.id]
            layout = [(o.x, o.y, o.widest) for o in others]
            for heading in np.arange(plan.HEADINGS) * (2 * math.pi / plan.HEADINGS):
                for push in plan.along(glass, others, heading):
                    eased = shortfall_before - plan.shortfall([*layout, (*push.aim, glass.widest)])
                    if eased >= plan.LEAST_EASING and (easing is None or eased > easing[0]):
                        easing = (eased, push)
        return easing[1] if easing else None
