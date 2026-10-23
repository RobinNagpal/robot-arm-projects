"""The reference: problem 3's geometry chooses the push, fixed settings go to MoveIt.

Nothing here is learned. It shows what the arm scores when the decisions are
made by rule, which every learned solution is then measured against.

The choice of glass, direction and distance is problem 3's ``plan.choose``,
imported as it is. It reads the same fields a ``Seen`` carries, so each box is
turned back into one. The settings are one fixed set, picked once for safety and
never adjusted: a slow stroke at the lowest height the hand rides at.

It looks only as much as it needs (``turn_by_turn_loop.AS_NEEDED``), because it reads the boxes and
not the pictures.
"""

from __future__ import annotations

import math

import numpy as np

from examiner.motion.push_motions import Request, Settings
from examiner.simulation.taken_from_problem_3 import Push, Seen
from shared.turn_by_turn_loop import AS_NEEDED, Done, TurnByTurn

import plan  # problem 3's solution 1, put on the path by partners

# How much further than the shortest freeing push the stroke goes, metres. See ``choose``.
EXTRA = 0.02

# The shortest stroke worth making. A push of two or three millimetres leans a glass
# onto the hand without sliding it, and the lean is what tips it when the hand
# backs off; so a push is lengthened to this where the geometry allows.
LEAST_TRAVEL = 0.04

# Slow enough that the push is gentle, low enough to meet the glass near its foot.
SAFE = Settings(push_height=0.085, stroke_speed=0.05, approach_speed=0.4, padding=0.01, standoff=0.03)


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
        self.skip: set[int] = set()
        self.last: int | None = None

    def begin(self) -> None:
        self.skip = set()
        self.last = None

    def decide(self, look):
        seen = as_seen(look.boxes)
        # A push MoveIt refused is not asked for again.
        if look.refused and self.last is not None:
            self.skip.add(self.last)
        push = self.choose(seen)
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

    def choose(self, seen):
        """Problem 3's choice of the shortest push that frees a glass, lengthened to a push that moves it.

        Problem 3's simulator feels for the glass and then pushes a set distance, so
        it asks for the least that clears. Here the stroke is planned before the
        arm moves and nothing feels for contact, and a stroke that ends a
        millimetre past touching moves a glass by nothing at all: measured,
        pushes of 4 mm on average moved glasses by under a millimetre. So the
        shortest freeing push is lengthened to ``EXTRA`` more, from the same
        list of pushes the geometry has already checked against every
        neighbour, and no further than the last of them.
        """
        before = plan.shortfall([(g.x, g.y, g.widest) for g in seen])
        best = None
        for glass in seen:
            if glass.id in self.skip or plan.slides(glass) == "no":
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
            if glass.id in self.skip or plan.slides(glass) == "no":
                continue
            others = [o for o in seen if o.id != glass.id]
            layout = [(o.x, o.y, o.widest) for o in others]
            for heading in np.arange(plan.HEADINGS) * (2 * math.pi / plan.HEADINGS):
                for push in plan.along(glass, others, heading):
                    eased = before - plan.shortfall([*layout, (*push.aim, glass.widest)])
                    if eased >= plan.LEAST_EASING and (easing is None or eased > easing[0]):
                        easing = (eased, push)
        return easing[1] if easing else None
