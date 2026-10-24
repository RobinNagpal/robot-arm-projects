"""How a table of boxes, and a push, are written for the learned models.

Four solutions learn from the same experience, so they read the same encoding.
Writing it once also means a change to it is a change to all four.

**A table is a set of glasses, and a model must not care what order they are
in.** Each glass is one row of numbers -- where it stands, its radius, height and
foot, and how much room it is short of -- and a table is up to ``GLASS_SLOTS`` rows with
a flag for which are real. The models that read it are built so that shuffling
the rows shuffles their answers the same way.

**A push is a glass, a direction, a distance and six settings.** The settings
are the ones MoveIt is given (``push_motions.MoveItSettings``) and each is scaled to run from
0 to 1 over the range a model is allowed to choose from, so that a network's
outputs all have the same size and a model cannot choose a setting outside it.
"""

from __future__ import annotations

import math

import numpy as np
from work_cell.rack.layout import GLASS_ZONE

from examiner.motion.push_motions import GlassBox, MoveItSettings, PushRequest
from examiner.simulation.taken_from_problem_3 import GRIP_ROOM, has_room  # noqa: I001  (puts problem 3's solution 1 on the path)

import plan  # problem 3's solution 1: the room-shortfall arithmetic lives there

# The range each setting a model chooses is allowed to take, and how far it may push.
# They are the cell's limits on what a model may tell MoveIt, not a statement of what is good.
SETTING_RANGES = {
    "push_height": (0.075, 0.125),
    "stroke_speed": (0.006, 0.20),  # log-uniform
    "approach_speed": (0.3, 0.7),
    "padding": (0.005, 0.02),
    "standoff": (0.02, 0.05),
    "overreach": (0.0, 0.025),
}
TRAVEL_RANGE = (0.02, 0.10)
GLASS_SLOTS = 6
GLASS_ZONE_CENTRE = np.array([(GLASS_ZONE[0] + GLASS_ZONE[1]) / 2, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2])
NUMBERS_PER_GLASS = 5 + 1  # x, y, radius, height, foot, short-of-room
SETTING_NAMES = ("push_height", "stroke_speed", "approach_speed", "padding", "standoff", "overreach")
NUMBERS_PER_PUSH = 2 + 1 + len(SETTING_NAMES)  # cos, sin of the heading; travel; settings


def room_shortfall_of_glass(boxes: list[GlassBox], glass: int) -> float:
    """How far glass ``k`` is from having room: zero when it has it, metres otherwise."""
    this_box = boxes[glass]
    largest_shortfall = 0.0
    for other_index, other in enumerate(boxes):
        if other_index != glass:
            largest_shortfall = max(
                largest_shortfall,
                GRIP_ROOM + other.radius - math.dist((this_box.x, this_box.y), (other.x, other.y)),
            )
    return max(0.0, largest_shortfall)


def count_pickable_boxes(boxes: list[GlassBox]) -> int:
    return sum(
        has_room(
            box.x,
            box.y,
            [
                (other.x, other.y, 2 * other.radius)
                for other_index, other in enumerate(boxes)
                if other_index != index
            ],
        )
        for index, box in enumerate(boxes)
    )


def total_room_shortfall(boxes: list[GlassBox]) -> float:
    return plan.shortfall([(box.x, box.y, 2 * box.radius) for box in boxes])


def encode_table(boxes: list[GlassBox]) -> tuple[np.ndarray, np.ndarray]:
    """(GLASS_SLOTS, NUMBERS_PER_GLASS) numbers and a (GLASS_SLOTS,) mask saying which rows are glasses."""
    rows = np.zeros((GLASS_SLOTS, NUMBERS_PER_GLASS), dtype=np.float32)
    mask = np.zeros(GLASS_SLOTS, dtype=bool)
    for index, box in enumerate(boxes[:GLASS_SLOTS]):
        rows[index] = [
            (box.x - GLASS_ZONE_CENTRE[0]) / 0.2,
            (box.y - GLASS_ZONE_CENTRE[1]) / 0.2,
            box.radius / 0.05,
            box.height / 0.2,
            (box.foot or box.radius) / 0.04,
            room_shortfall_of_glass(boxes, index) / 0.05,
        ]
        mask[index] = True
    return rows, mask


def setting_to_unit(name: str, value: float) -> float:
    lowest, highest = SETTING_RANGES[name]
    if name == "stroke_speed":  # chosen on a log scale, because 0.02 and 0.04 differ as much as 0.2 and 0.4
        return (math.log(value) - math.log(lowest)) / (math.log(highest) - math.log(lowest))
    return (value - lowest) / (highest - lowest)


def unit_to_setting(name: str, unit: float) -> float:
    unit = min(1.0, max(0.0, float(unit)))
    lowest, highest = SETTING_RANGES[name]
    if name == "stroke_speed":
        return math.exp(math.log(lowest) + unit * (math.log(highest) - math.log(lowest)))
    return lowest + unit * (highest - lowest)


def encode_push(request: PushRequest) -> np.ndarray:
    """The push as numbers: cos and sin of the heading, travel in 0..1, then the six settings in 0..1."""
    settings = request.settings
    return np.array(
        [
            math.cos(request.heading),
            math.sin(request.heading),
            (request.travel - TRAVEL_RANGE[0]) / (TRAVEL_RANGE[1] - TRAVEL_RANGE[0]),
            *(setting_to_unit(name, getattr(settings, name)) for name in SETTING_NAMES),
        ],
        dtype=np.float32,
    )


def decode_push(glass: int, numbers) -> PushRequest:
    """A push back out of numbers. Whatever a network says is clipped into the allowed ranges."""
    values = np.asarray(numbers, dtype=float)
    heading = math.atan2(values[1], values[0])
    travel = TRAVEL_RANGE[0] + min(1.0, max(0.0, values[2])) * (TRAVEL_RANGE[1] - TRAVEL_RANGE[0])
    settings = MoveItSettings(
        **{name: unit_to_setting(name, values[3 + index]) for index, name in enumerate(SETTING_NAMES)}
    )
    return PushRequest(glass, heading, travel, settings)


# ----------------------------------------------------------------- the records


def load_push_records(*paths) -> list[dict]:
    import json
    from pathlib import Path

    rows = []
    for path in paths:
        for line in Path(path).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def boxes_from_layout(layout: list[dict]) -> list[GlassBox]:
    return [
        GlassBox(glass["x"], glass["y"], glass["radius"], glass["height"], glass["foot"]) for glass in layout
    ]


def push_request_from_record(record: dict) -> PushRequest:
    request = record["request"]
    return PushRequest(
        request["glass"], request["heading"], request["travel"], MoveItSettings(**request["settings"])
    )


def push_outcome_from_record(record: dict) -> dict:
    """What a push did, as the numbers the solutions learn from and are scored by.

    ``gain`` is the change in how many glasses the hand could pick. ``eased`` is
    how much total room-shortfall the push took off the table, in millimetres:
    pushes that free no glass yet are still worth something if the table is looser.
    ``moved`` is how far the pushed glass travelled along the push, ``across`` how far
    it strayed sideways, and ``disturbed`` is the most any *other* glass moved.
    """
    before, after = record["before"], record["after"]
    if not record["feasible"]:
        return {
            "feasible": False,
            "gain": 0,
            "eased": 0.0,
            "topple": False,
            "moved": 0.0,
            "across": 0.0,
            "disturbed": 0.0,
            "seconds": 0.0,
        }
    glass, request = record["request"]["glass"], record["request"]
    along_push = (math.cos(request["heading"]), math.sin(request["heading"]))
    moved = (after[glass]["x"] - before[glass]["x"], after[glass]["y"] - before[glass]["y"])
    others = [
        math.dist((after_glass["x"], after_glass["y"]), (before_glass["x"], before_glass["y"]))
        for index, (after_glass, before_glass) in enumerate(zip(after, before, strict=True))
        if index != glass
    ]
    return {
        "feasible": True,
        "gain": sum(row["pickable"] for row in after) - sum(row["pickable"] for row in before),
        "eased": 1000.0
        * (total_room_shortfall(boxes_from_layout(before)) - total_room_shortfall(boxes_from_layout(after))),
        "topple": record["toppled"] > 0,
        "moved": moved[0] * along_push[0] + moved[1] * along_push[1],
        "across": abs(moved[0] * along_push[1] - moved[1] * along_push[0]),
        "disturbed": max(others, default=0.0),
        "seconds": record["arm_seconds"],
    }


def hand_fits_along_push(
    boxes: list[GlassBox], glass_index: int, heading: float, travel: float, lead_in: float = 0.05
) -> bool:
    """Whether the shut hand, driven along this push, stays clear of every other glass.

    This is problem 3's own test of a push (``plan.along``): each stretch of the
    hand against its own width, swept from where the fingertips come down to
    where they stop, and the glass itself against its neighbours on its way. It
    knows the shape of the hand and nothing about the arm behind it, so it
    cannot say that MoveIt will find the push; it can say that a push failing it
    has no hope. It is used to propose pushes worth asking MoveIt about, and the
    models learn the rest -- what the arm can and cannot do -- from MoveIt's
    answers.
    """
    along_push = np.array([math.cos(heading), math.sin(heading)])
    pushed_box = boxes[glass_index]
    middle = np.array([pushed_box.x, pushed_box.y])
    start = middle - (pushed_box.radius + lead_in) * along_push
    end = middle + travel * along_push
    for other_index, other in enumerate(boxes):
        if other_index == glass_index:
            continue
        centre = np.array([other.x, other.y])
        passing = min(
            pushed_box.radius + other.radius + plan.CLEARANCE, float(np.linalg.norm(centre - middle)) - 0.001
        )
        swept = any(
            plan.segment_distance(centre, start - far * along_push, end - near * along_push)
            < half + other.radius + plan.CLEARANCE
            for near, far, half in plan.JAW_SEGMENTS
        )
        if plan.segment_distance(centre, middle, end) < passing or swept:
            return False
    return plan.in_zone(*end)


def heading_away_from_nearest_glass(boxes: list[GlassBox], glass: int) -> float:
    """The direction from the nearest other glass towards glass ``glass``: the way a push usually should go.

    A push towards a neighbour almost never helps, so measuring the heading from
    this direction instead of from the table's x axis hands a learner the one piece
    of geometry every good push shares, and leaves it to learn how far to depart
    from it. With one glass on the table there is no neighbour and the answer is 0.
    """
    this_box = boxes[glass]
    nearest_distance, heading = math.inf, 0.0
    for other_index, other in enumerate(boxes):
        if other_index != glass:
            distance = math.dist((this_box.x, this_box.y), (other.x, other.y))
            if distance < nearest_distance:
                nearest_distance, heading = distance, math.atan2(this_box.y - other.y, this_box.x - other.x)
    return heading


def decode_push_relative_to_neighbour(glass: int, numbers, boxes: list[GlassBox]) -> PushRequest:
    """Like ``decode_push``, but the first two numbers are an angle.

    The angle is measured from ``heading_away_from_nearest_glass``.
    """
    request = decode_push(glass, numbers)
    heading = heading_away_from_nearest_glass(boxes, glass) + request.heading
    return PushRequest(glass, (heading + math.pi) % (2 * math.pi) - math.pi, request.travel, request.settings)
