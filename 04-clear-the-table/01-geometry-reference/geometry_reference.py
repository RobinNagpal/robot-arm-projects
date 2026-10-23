"""The reference: problem 3's geometry chooses the push, fixed settings go to MoveIt.

Nothing here is learned. It shows what the arm scores when the decisions are
made by rule, which every learned solution is then measured against.

The choice of glass, direction and distance is problem 3's ``plan.choose``,
loaded from the exact copy of it. It reads the same fields a ``Seen`` carries, so
each box is turned back into one. The settings are one fixed set, picked once for
safety and never adjusted: a slow stroke, low on the glass.

Two things differ from problem 3, because the arm's cell differs from problem 3's.
The arm's hand rides higher, so problem 3's tipping rule is given the arm's top
edge (``arm_bench``). And a glass that has room stays on the table here, so it is
left out of the choice (``already_free``).

It looks only as much as it needs (``turn_by_turn_loop.AS_NEEDED``), because it reads the boxes and
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

from examiner.motion.push_motions import Request, Settings
from examiner.simulation import taken_from_problem_3
from examiner.simulation.taken_from_problem_3 import FINGER_HEIGHT, GEOMETRY, Push, Seen
from shared.turn_by_turn_loop import AS_NEEDED, Done, Refused, TurnByTurn

# How much further than the shortest freeing push the stroke goes, metres. See ``choose``.
EXTRA = 0.02

# The shortest stroke worth making. A push of two or three millimetres leans a glass
# onto the hand without sliding it, and the lean is what tips it when the hand
# backs off; so a push is lengthened to this where the geometry allows.
LEAST_TRAVEL = 0.04

# Slow enough that the push is gentle, low enough to meet the glass near its foot.
SAFE = Settings(push_height=0.085, stroke_speed=0.05, approach_speed=0.4, padding=0.01, standoff=0.03)

# The top edge of the hand when it pushes at SAFE's height. The hand is problem 3's
# hand, so its fingers are as tall, but its middle rides at SAFE.push_height.
TOP_EDGE = SAFE.push_height + FINGER_HEIGHT / 2


@contextmanager
def arm_bench() -> Iterator[None]:
    """Problem 3's names, with the hand's top edge where the arm carries it, while problem 3's files load.

    Problem 3's files read the top edge of the hand, as ``JAW_TOP``, from a module
    they call ``bench``. Problem 3's hand rides with its middle at 75 mm, so its top
    edge is at 107 mm; the arm's hand rides 10 mm higher, at ``SAFE.push_height``.
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
    arm.JAW_TOP = TOP_EDGE
    before = sys.modules.get("bench")
    sys.modules["bench"] = arm
    try:
        yield
    finally:
        if before is None:
            sys.modules.pop("bench", None)
        else:
            sys.modules["bench"] = before


def _plan_at_the_arms_height() -> types.ModuleType:
    """Problem 3's solution 1, loaded from its exact copy with the arm's top edge."""
    spec = importlib.util.spec_from_file_location("plan_at_the_arms_height", GEOMETRY / "plan.py")
    module = importlib.util.module_from_spec(spec)
    with arm_bench():
        spec.loader.exec_module(module)
    return module


plan = _plan_at_the_arms_height()


def already_free(seen: list[Seen]) -> set[int]:
    """The glasses that already stand where a push that frees a glass would put them.

    Problem 3 lifts a glass off the table as soon as it has room, so its rule never
    sees one. Here a glass with room stays on the table, and to problem 3's rule it
    looks like the easiest glass of all to free, because the shortest push gives it
    room. Pushing it gains nothing and can tip it. So a glass is left out when it
    already has room by ``plan.AIM_MARGIN``, the margin a freeing push aims for. It
    is still an obstacle that every other push keeps clear of.
    """
    return {glass.id for glass in seen if plan.room(glass, seen, plan.AIM_MARGIN)}


def as_seen(boxes) -> list[Seen]:
    return [
        Seen(
            id=i,
            x=b.x,
            y=b.y,
            height=b.height,
            widest=2 * b.radius,
            foot=2 * (b.foot or b.radius),
            standing=True,
        )
        for i, b in enumerate(boxes)
    ]


class Geometry(TurnByTurn):
    name = "geometry, fixed settings"
    looking = AS_NEEDED

    def __init__(self, settings: Settings = SAFE) -> None:
        self.settings = settings
        self.refused = Refused()
        self.last: int | None = None

    def begin(self) -> None:
        self.refused = Refused()
        self.last = None

    def decide(self, look):
        seen = as_seen(look.boxes)
        # A push MoveIt refused is not asked for again.
        if look.refused and self.last is not None:
            self.refused.add(look.boxes, self.last)
        push = self.choose(seen, self.refused.among(look.boxes) | already_free(seen))
        if push is None:
            return Done("every glass has room, or none that is left can be pushed")
        self.last = push.glass
        return Request(glass=push.glass, heading=push.heading, travel=push.travel, settings=self.settings)

    def lengthened(self, glass, others, heading, push):
        """The same push made EXTRA longer, if the geometry still finds it clear; otherwise as it was.

        This asks ``plan.along``'s own question again at the longer distance:
        does any stretch of the hand, or the glass itself on its way, come within
        CLEARANCE of a neighbour. The answer is the one problem 3 would give.
        """
        u = np.array([math.cos(heading), math.sin(heading)])
        middle = np.array([glass.x, glass.y])
        radius = glass.widest / 2
        start = middle - (radius + plan.APPROACH_GAP) * u
        travel = max(push.travel + EXTRA, LEAST_TRAVEL)
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

    def choose(self, seen, skip):
        """Problem 3's choice of the shortest push that frees a glass, lengthened to a push that moves it.

        Problem 3's simulator feels for the glass and then pushes a set distance, so
        it asks for the least that clears. Here the stroke is planned before the
        arm moves and nothing feels for contact, and a stroke that ends a
        millimetre past touching moves a glass by nothing at all: measured,
        pushes of 4 mm on average moved glasses by under a millimetre. So the
        shortest freeing push is lengthened to ``EXTRA`` more, from the same
        list of pushes the geometry has already checked against every
        neighbour, and no further than the last of them. ``skip`` is the glasses
        not to push.
        """
        before = plan.shortfall([(g.x, g.y, g.widest) for g in seen])
        best = None
        for glass in seen:
            if glass.id in skip or plan.slides(glass) == "no":
                continue
            others = [o for o in seen if o.id != glass.id]
            layout = [(o.x, o.y, o.widest) for o in others]
            for heading in np.arange(plan.HEADINGS) * (2 * math.pi / plan.HEADINGS):
                safe = plan.along(glass, others, heading)
                for push in safe:
                    if plan.has_room(*push.aim, layout, plan.AIM_MARGIN):
                        # The first freeing push is the shortest on this heading.
                        push = self.lengthened(glass, others, heading, push)
                        if best is None or push.travel < best.travel:
                            best = push
                        break
        if best is not None:
            return best
        # Nothing frees a glass outright; take the push that most eases the table.
        easing = None
        for glass in seen:
            if glass.id in skip or plan.slides(glass) == "no":
                continue
            others = [o for o in seen if o.id != glass.id]
            layout = [(o.x, o.y, o.widest) for o in others]
            for heading in np.arange(plan.HEADINGS) * (2 * math.pi / plan.HEADINGS):
                for push in plan.along(glass, others, heading):
                    eased = before - plan.shortfall([*layout, (*push.aim, glass.widest)])
                    if eased >= plan.LEAST_EASING and (easing is None or eased > easing[0]):
                        easing = (eased, push)
        return easing[1] if easing else None
