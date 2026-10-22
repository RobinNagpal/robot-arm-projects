"""How a solution clears a table turn by turn, and how it chooses to look.

The examiner hands a solution only a ``Run``: an arm with a camera, and a clock. So
everything that happens between "start" and "finished" is the solution's to decide,
including when to take a picture and from where. This file holds the parts that every
solution here shares, so that each solution's own file holds only its own choices.

**One turn.** The solution looks, turns the pictures into boxes with the box model,
chooses one push or decides it has finished, and asks the arm for the push. After a push
the table has changed, so the next turn looks again. After a refused push nothing has
moved, so the next turn decides again from the same boxes without looking.

**Two ways of looking.** The box model was trained on pictures from the two viewing
poses, so those are the only places a solution looks from.

- ``EVERY_VIEW`` takes a picture from both poses on every turn. A solution that reads the
  pictures themselves needs this, because it must be shown both, and both must be new.
- ``AS_NEEDED`` takes both pictures at the start of a table, and remembers how many
  glasses they showed. After a push it goes to the nearer pose first, and goes on to the
  other only when the first picture shows fewer glasses than that. The glasses are not
  taken away, so a picture that shows them all has missed none.

**The scene a trip is planned in.** On the way to the second pose the arm treats the
whole glass zone as solid up to above the tallest glass, because a glass the first
picture missed may stand anywhere. On the way to the first pose after a push, it plans
round the glasses where it last saw them, with the pushed glass where it was aimed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from arm_contract import REACHED, REFUSED, Arm, Box, Frame, Pose, Request, Run, Settings
from cell import VIEWS as VIEW_WAYPOINTS
from cell import ZONE_CEILING
from work_cell.rack.layout import GLASS_ZONE

VIEWS = tuple(Pose(v.x, v.y, v.z, v.heading) for v in VIEW_WAYPOINTS)

EVERY_VIEW, AS_NEEDED = "every view", "as needed"

# The settings for a trip to look: quicker than a push, and the room every push leaves.
TRIP = Settings(push_height=0.085, stroke_speed=0.05, approach_speed=0.6, padding=0.01, standoff=0.03)

# How far outside the glass zone the solid block over it reaches.
ZONE_MARGIN = 0.03


@dataclass(frozen=True)
class Done:
    """The solution's own statement that the table needs nothing more, and why."""

    why: str = ""


@dataclass(frozen=True)
class Turn:
    """What a solution decides from on one turn."""

    boxes: tuple[Box, ...]  # what the box model found, merged across the pictures of this turn
    pictures: tuple[np.ndarray, ...]  # the latest picture from each viewing pose, in the order of ``VIEWS``
    seconds_left: float
    refused: str = ""  # why the last push was refused, and empty when it was made


def over_the_zone(padding: float) -> list[Box]:
    """Square boxes that, once MoveIt grows them by ``padding``, cover the glass zone and no more.

    A box in the scene is square, and the zone is not, so it is covered by a row of
    overlapping squares as wide as its short side.
    """
    x0, x1, y0, y1 = GLASS_ZONE
    x0, x1, y0, y1 = x0 - ZONE_MARGIN, x1 + ZONE_MARGIN, y0 - ZONE_MARGIN, y1 + ZONE_MARGIN
    side = min(x1 - x0, y1 - y0)
    count = math.ceil(max(x1 - x0, y1 - y0) / side - 1e-9)
    along_x = (x1 - x0) >= (y1 - y0)
    start, stop = (x0, x1) if along_x else (y0, y1)
    centres = np.linspace(start + side / 2, stop - side / 2, count) if count > 1 else [(start + stop) / 2]
    middle = (y0 + y1) / 2 if along_x else (x0 + x1) / 2
    return [
        Box(
            float(c) if along_x else middle,
            middle if along_x else float(c),
            side / 2 - padding,
            ZONE_CEILING - padding,
        )
        for c in centres
    ]


class Memory:
    """The boxes found on one turn, merged across its pictures.

    One picture does not show the table: a glass behind another is simply not in it.
    Two boxes close together from two pictures are the same glass, and the newer one is kept.
    """

    MATCH = 0.03  # two boxes this close are the same glass

    def __init__(self) -> None:
        self.boxes: list[Box] = []

    def update(self, found: list[Box]) -> None:
        for box in found:
            for k, old in enumerate(self.boxes):
                if math.dist((box.x, box.y), (old.x, old.y)) < self.MATCH:
                    self.boxes[k] = box
                    break
            else:
                self.boxes.append(box)


def after(boxes: list[Box], request: Request) -> list[Box]:
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


_BOX_MODEL = None


def box_model():
    """Job 0, loaded once and shared, because every solution here sees through the same model."""
    global _BOX_MODEL
    if _BOX_MODEL is None:
        import seeing

        _BOX_MODEL = seeing.BoxModel.load()
    return _BOX_MODEL


def _at(here: Pose, view: Pose) -> bool:
    turn = abs((here.heading - view.heading + math.pi) % (2 * math.pi) - math.pi)
    return math.dist((here.x, here.y, here.z), (view.x, view.y, view.z)) < 0.02 and turn < 0.05


class Eyes:
    """Where a solution looks from, and what it has found there."""

    def __init__(self, arm: Arm, how: str, see=None) -> None:
        self.arm, self.how = arm, how
        self.see = see or (lambda frame: box_model().detect(frame.image, frame.pose))
        self.pictures: dict[int, np.ndarray] = {}
        self.glasses = 0  # the most glasses one turn's pictures have shown
        self.expected: list[Box] = []  # where the glasses should be after the last push
        self.why = ""

    def look(self) -> list[Box] | None:
        """The boxes on the table now, or ``None`` when the arm cannot get to a place to look from."""
        memory = Memory()
        here = self.arm.pose()
        order = sorted(range(len(VIEWS)), key=lambda k: math.dist((VIEWS[k].x, VIEWS[k].y), (here.x, here.y)))
        for n, k in enumerate(order):
            if n > 0 and self.how == AS_NEEDED and 0 < self.glasses <= len(memory.boxes):
                break
            if not _at(self.arm.pose(), VIEWS[k]):
                if memory.boxes:
                    scene = memory.boxes + over_the_zone(TRIP.padding)
                elif self.expected:
                    scene = list(self.expected)
                else:
                    scene = over_the_zone(TRIP.padding)
                moved = self.arm.move_to(VIEWS[k], TRIP, scene)
                if moved.end != REACHED:
                    self.why = moved.why
                    return None
            frame: Frame = self.arm.camera.capture()
            self.pictures[k] = frame.image
            memory.update(self.see(frame))
        self.glasses = max(self.glasses, len(memory.boxes))
        return memory.boxes

    def in_order(self) -> tuple[np.ndarray, ...]:
        return tuple(self.pictures[k] for k in sorted(self.pictures))

    def pushed(self, boxes: list[Box], request: Request) -> None:
        self.expected = after(boxes, request)


class TurnByTurn:
    """A solution that looks, chooses one push, makes it, and repeats until it has finished.

    A solution says how it looks with ``looking`` and how it chooses with ``decide``.
    ``begin`` is called at the start of every table, so that it can forget the last one.
    """

    name = "turn by turn"
    looking = AS_NEEDED
    see = None  # how a picture becomes boxes; the box model unless a solution says otherwise

    def begin(self) -> None:
        pass

    def decide(self, turn: Turn) -> Request | Done:
        raise NotImplementedError

    def clear(self, run: Run) -> None:
        self.begin()
        eyes = Eyes(run.arm, self.looking, self.see)
        boxes: list[Box] | None = None
        refused = ""
        while True:
            if boxes is None:
                boxes = eyes.look()
                if boxes is None:
                    run.finish(f"the arm cannot get to a place to look from: {eyes.why}")
                    return
            answer = self.decide(Turn(tuple(boxes), eyes.in_order(), run.clock.left, refused))
            if isinstance(answer, Done):
                run.finish(answer.why)
                return
            pushed = run.arm.push(answer, boxes)
            if pushed.end == REFUSED:
                refused = pushed.why
                continue
            refused = ""
            eyes.pushed(boxes, answer)
            boxes = None
