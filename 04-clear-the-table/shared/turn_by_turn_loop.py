"""How a solution clears a table turn by turn, and how it chooses to look.

The examiner hands a solution only a ``TableAttempt``: an arm with a camera, and a clock. So
everything that happens between "start" and "finished" is the solution's to decide,
including when to take a picture and from where. This file holds the parts that every
solution here shares, so that each solution's own file holds only its own choices.

**One turn.** The solution looks, turns the pictures into boxes with the box model,
chooses one push or decides it has finished, and asks the arm for the push. After a push
the table has changed, so the next turn looks again. After a refused push nothing has
moved, so the next turn decides again from the same boxes without looking.

**Two ways of looking.** The box model was trained on pictures from the two viewing
poses, so those are the only places a solution looks from.

- ``LOOK_FROM_BOTH_PLACES_EVERY_TURN`` takes a picture from both poses on every turn. A
  solution that reads the pictures themselves needs this, because it must be shown both,
  and both must be new.
- ``LOOK_ONLY_AS_NEEDED`` takes both pictures at the start of a table, and remembers how
  many glasses they showed. After a push it goes to the nearer pose first, and goes on to
  the other only when the first picture shows fewer glasses than that. The glasses are not
  taken away, so a picture that shows them all has missed none.

**The obstacles a trip is planned round.** On the way to the second pose the arm treats the
whole glass zone as solid up to above the tallest glass, because a glass the first
picture missed may stand anywhere. On the way to the first pose after a push, it plans
round the glasses where it last saw them, with the pushed glass where it was aimed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from work_cell.rack.layout import GLASS_ZONE

from examiner.examining.one_table_cell import VIEW_WAYPOINTS, ZONE_KEEP_OUT_HEIGHT
from examiner.examining.solution_contract import (
    REACHED,
    REFUSED,
    Arm,
    GlassBox,
    HandPose,
    MoveItSettings,
    PushRequest,
    TableAttempt,
    WristPicture,
)

VIEW_POSES = tuple(HandPose(v.x, v.y, v.z, v.heading) for v in VIEW_WAYPOINTS)

LOOK_FROM_BOTH_PLACES_EVERY_TURN, LOOK_ONLY_AS_NEEDED = "every view", "as needed"

# The settings for a trip to look: quicker than a push, and the room every push leaves.
TRIP_TO_LOOK_SETTINGS = MoveItSettings(
    push_height=0.085, stroke_speed=0.05, approach_speed=0.6, padding=0.01, standoff=0.03
)

# How far outside the glass zone the solid block over it reaches.
ZONE_BLOCK_MARGIN = 0.03


@dataclass(frozen=True)
class TableFinished:
    """The solution's own statement that the table needs nothing more, and why."""

    reason: str = ""


@dataclass(frozen=True)
class TurnObservation:
    """What a solution decides from on one turn."""

    boxes: tuple[GlassBox, ...]  # what the box model found, merged across the pictures of this turn
    latest_pictures: tuple[
        np.ndarray, ...
    ]  # the latest picture from each viewing pose, in the order of ``VIEW_POSES``
    arm_seconds_left: float
    last_push_refusal_reason: str = ""  # why the last push was refused, and empty when it was made


def boxes_covering_the_glass_zone(padding: float) -> list[GlassBox]:
    """Square boxes that, once MoveIt grows them by ``padding``, cover the glass zone and no more.

    A box MoveIt is given is square, and the zone is not, so it is covered by a row of
    overlapping squares as wide as its short side.
    """
    x0, x1, y0, y1 = GLASS_ZONE
    x0, x1 = x0 - ZONE_BLOCK_MARGIN, x1 + ZONE_BLOCK_MARGIN
    y0, y1 = y0 - ZONE_BLOCK_MARGIN, y1 + ZONE_BLOCK_MARGIN
    side = min(x1 - x0, y1 - y0)
    count = math.ceil(max(x1 - x0, y1 - y0) / side - 1e-9)
    along_x = (x1 - x0) >= (y1 - y0)
    start, stop = (x0, x1) if along_x else (y0, y1)
    centres = np.linspace(start + side / 2, stop - side / 2, count) if count > 1 else [(start + stop) / 2]
    middle = (y0 + y1) / 2 if along_x else (x0 + x1) / 2
    return [
        GlassBox(
            float(c) if along_x else middle,
            middle if along_x else float(c),
            side / 2 - padding,
            ZONE_KEEP_OUT_HEIGHT - padding,
        )
        for c in centres
    ]


class BoxesMergedAcrossPictures:
    """The boxes found on one turn, merged across its pictures.

    One picture does not show the table: a glass behind another is simply not in it.
    Two boxes close together from two pictures are the same glass, and the newer one is kept.
    """

    SAME_GLASS_DISTANCE = 0.03  # two boxes this close are the same glass

    def __init__(self) -> None:
        self.boxes: list[GlassBox] = []

    def add_boxes(self, found: list[GlassBox]) -> None:
        for box in found:
            for k, kept in enumerate(self.boxes):
                if math.dist((box.x, box.y), (kept.x, kept.y)) < self.SAME_GLASS_DISTANCE:
                    self.boxes[k] = box
                    break
            else:
                self.boxes.append(box)


class RefusedGlasses:
    """The glasses not to ask for again on this table, remembered by where they stand.

    A glass's number is only its place in one look's list of boxes, and the next look can list
    the same glasses in another order. So a number kept from one look can name a different
    glass in the next one, and the glass that was refused would be asked for again. A refused
    glass is therefore kept as the place it stands, and it is found in every later look as the
    box within ``BoxesMergedAcrossPictures.SAME_GLASS_DISTANCE`` of that place, the same test
    that tells two pictures of one glass apart from two glasses.
    """

    def __init__(self) -> None:
        self.refused_places: list[tuple[float, float]] = []

    def remember(self, boxes: tuple[GlassBox, ...] | list[GlassBox], glass: int) -> None:
        """Remember glass ``glass`` of ``boxes``, the look the refused push was asked from."""
        if 0 <= glass < len(boxes):
            self.refused_places.append((boxes[glass].x, boxes[glass].y))

    def indices_in_look(self, boxes: tuple[GlassBox, ...] | list[GlassBox]) -> set[int]:
        """The numbers that the remembered glasses have in this look."""
        return {
            k
            for k, box in enumerate(boxes)
            if any(
                math.dist((box.x, box.y), place) < BoxesMergedAcrossPictures.SAME_GLASS_DISTANCE
                for place in self.refused_places
            )
        }


def boxes_expected_after_push(boxes: list[GlassBox], request: PushRequest) -> list[GlassBox]:
    """The boxes as they should be after a push: the pushed glass where it was aimed, with room to spare."""
    pushed = boxes[request.glass]
    moved = GlassBox(
        pushed.x + request.travel * math.cos(request.heading),
        pushed.y + request.travel * math.sin(request.heading),
        pushed.radius + 0.02,
        pushed.height,
        pushed.foot,
    )
    return [b for i, b in enumerate(boxes) if i != request.glass] + [moved]


_SHARED_BOX_MODEL = None


def shared_box_model():
    """Job 0, loaded once and shared, because every solution here sees through the same model."""
    global _SHARED_BOX_MODEL
    if _SHARED_BOX_MODEL is None:
        from shared.seeing import box_model

        _SHARED_BOX_MODEL = box_model.BoxModel.load()
    return _SHARED_BOX_MODEL


def _hand_is_at(here: HandPose, view: HandPose) -> bool:
    turn = abs((here.heading - view.heading + math.pi) % (2 * math.pi) - math.pi)
    return math.dist((here.x, here.y, here.z), (view.x, view.y, view.z)) < 0.02 and turn < 0.05


class TableLooker:
    """Takes the arm to the viewing places, takes the pictures, and turns them into boxes."""

    def __init__(self, arm: Arm, looking_mode: str, picture_to_boxes=None) -> None:
        self.arm, self.looking_mode = arm, looking_mode
        self.picture_to_boxes = picture_to_boxes or (
            lambda picture: shared_box_model().boxes_in_picture(picture.image, picture.hand_pose)
        )
        self.latest_picture_per_view: dict[int, np.ndarray] = {}
        self.most_glasses_seen = 0  # the most glasses one turn's pictures have shown
        self.expected_boxes_after_push: list[GlassBox] = []  # where the glasses should be after the last push
        self.failure_reason = ""

    def look_at_table(self) -> list[GlassBox] | None:
        """The boxes on the table now, or ``None`` when the arm cannot get to a place to look from."""
        merged = BoxesMergedAcrossPictures()
        here = self.arm.hand_pose()
        nearest_first = sorted(
            range(len(VIEW_POSES)),
            key=lambda k: math.dist((VIEW_POSES[k].x, VIEW_POSES[k].y), (here.x, here.y)),
        )
        for pictures_so_far, view in enumerate(nearest_first):
            if (
                pictures_so_far > 0
                and self.looking_mode == LOOK_ONLY_AS_NEEDED
                and 0 < self.most_glasses_seen <= len(merged.boxes)
            ):
                break
            if not _hand_is_at(self.arm.hand_pose(), VIEW_POSES[view]):
                if merged.boxes:
                    obstacles = merged.boxes + boxes_covering_the_glass_zone(TRIP_TO_LOOK_SETTINGS.padding)
                elif self.expected_boxes_after_push:
                    obstacles = list(self.expected_boxes_after_push)
                else:
                    obstacles = boxes_covering_the_glass_zone(TRIP_TO_LOOK_SETTINGS.padding)
                moved = self.arm.move_hand_to(VIEW_POSES[view], TRIP_TO_LOOK_SETTINGS, obstacles)
                if moved.outcome != REACHED:
                    self.failure_reason = moved.reason
                    return None
            picture: WristPicture = self.arm.wrist_camera.take_picture()
            self.latest_picture_per_view[view] = picture.image
            merged.add_boxes(self.picture_to_boxes(picture))
        self.most_glasses_seen = max(self.most_glasses_seen, len(merged.boxes))
        return merged.boxes

    def pictures_in_view_order(self) -> tuple[np.ndarray, ...]:
        return tuple(self.latest_picture_per_view[k] for k in sorted(self.latest_picture_per_view))

    def remember_push(self, boxes: list[GlassBox], request: PushRequest) -> None:
        self.expected_boxes_after_push = boxes_expected_after_push(boxes, request)


class TurnByTurnSolution:
    """A solution that looks, chooses one push, makes it, and repeats until it has finished.

    A solution says how it looks with ``looking_mode`` and how it chooses with ``decide_turn``.
    ``start_new_table`` is called at the start of every table, so that it can forget the last one.
    """

    name = "turn by turn"
    looking_mode = LOOK_ONLY_AS_NEEDED
    picture_to_boxes = None  # how a picture becomes boxes; the box model unless a solution says otherwise

    def start_new_table(self) -> None:
        pass

    def decide_turn(self, observation: TurnObservation) -> PushRequest | TableFinished:
        raise NotImplementedError

    def clear_table(self, attempt: TableAttempt) -> None:
        self.start_new_table()
        looker = TableLooker(attempt.arm, self.looking_mode, self.picture_to_boxes)
        boxes: list[GlassBox] | None = None
        last_push_refusal_reason = ""
        while True:
            if boxes is None:
                boxes = looker.look_at_table()
                if boxes is None:
                    attempt.declare_finished(
                        f"the arm cannot get to a place to look from: {looker.failure_reason}"
                    )
                    return
            observation = TurnObservation(
                tuple(boxes),
                looker.pictures_in_view_order(),
                attempt.clock.arm_seconds_left,
                last_push_refusal_reason,
            )
            answer = self.decide_turn(observation)
            if isinstance(answer, TableFinished):
                attempt.declare_finished(answer.reason)
                return
            push_result = attempt.arm.push_glass(answer, boxes)
            if push_result.outcome == REFUSED:
                last_push_refusal_reason = push_result.reason
                continue
            last_push_refusal_reason = ""
            looker.remember_push(boxes, answer)
            boxes = None
