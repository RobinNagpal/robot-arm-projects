"""How a table of boxes, and a push, are written for the learned models.

Four solutions learn from the same experience, so they read the same encoding.
Writing it once also means a change to it is a change to all four.

**A table is a set of glasses, and a model must not care what order they are
in.** Each glass is one row of numbers -- where it stands, its radius, height and
foot, and how much room it is short of -- and a table is up to ``SLOTS`` rows with
a flag for which are real. The models that read it are built so that shuffling
the rows shuffles their answers the same way.

**A push is a glass, a direction, a distance and six settings.** The settings
are the ones MoveIt is given (``pusher.Settings``) and each is scaled to run from
0 to 1 over the range a model is allowed to choose from, so that a network's
outputs all have the same size and a model cannot choose a setting outside it.
"""

from __future__ import annotations

import math

import numpy as np
from pusher import Box, Request, Settings
from work_cell.rack.layout import GLASS_ZONE

from partners import GRIP_ROOM, has_room  # noqa: I001  (puts problem 3's solution 1 on the path)

import plan  # problem 3's solution 1: the room-shortfall arithmetic lives there

# The range each setting a model chooses is allowed to take, and how far it may push.
# They are the cell's limits on what a model may tell MoveIt, not a statement of what is good.
RANGES = {
    "push_height": (0.075, 0.125),
    "stroke_speed": (0.006, 0.20),  # log-uniform
    "approach_speed": (0.3, 0.7),
    "padding": (0.005, 0.02),
    "standoff": (0.02, 0.05),
    "overreach": (0.0, 0.025),
}
TRAVEL = (0.02, 0.10)
SLOTS = 6
MOVE_SCALE = 0.05  # metres: the unit a pushed glass's travel is learned in
CENTRE = np.array([(GLASS_ZONE[0] + GLASS_ZONE[1]) / 2, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2])
GLASS_WIDTH = 5 + 1  # x, y, radius, height, foot, short-of-room
SETTING_NAMES = ("push_height", "stroke_speed", "approach_speed", "padding", "standoff", "overreach")
ACTION_WIDTH = 2 + 1 + len(SETTING_NAMES)  # cos, sin of the heading; travel; settings


def room_short(boxes: list[Box], k: int) -> float:
    """How far glass ``k`` is from having room: zero when it has it, metres otherwise."""
    here = boxes[k]
    worst = 0.0
    for j, other in enumerate(boxes):
        if j != k:
            worst = max(worst, GRIP_ROOM + other.radius - math.dist((here.x, here.y), (other.x, other.y)))
    return max(0.0, worst)


def pickable_count(boxes: list[Box]) -> int:
    return sum(
        has_room(b.x, b.y, [(o.x, o.y, 2 * o.radius) for j, o in enumerate(boxes) if j != k])
        for k, b in enumerate(boxes)
    )


def shortfall(boxes: list[Box]) -> float:
    return plan.shortfall([(b.x, b.y, 2 * b.radius) for b in boxes])


def table_tensor(boxes: list[Box]) -> tuple[np.ndarray, np.ndarray]:
    """(SLOTS, GLASS_WIDTH) numbers and a (SLOTS,) mask saying which rows are glasses."""
    rows = np.zeros((SLOTS, GLASS_WIDTH), dtype=np.float32)
    mask = np.zeros(SLOTS, dtype=bool)
    for k, b in enumerate(boxes[:SLOTS]):
        rows[k] = [
            (b.x - CENTRE[0]) / 0.2,
            (b.y - CENTRE[1]) / 0.2,
            b.radius / 0.05,
            b.height / 0.2,
            (b.foot or b.radius) / 0.04,
            room_short(boxes, k) / 0.05,
        ]
        mask[k] = True
    return rows, mask


def scale_setting(name: str, value: float) -> float:
    lo, hi = RANGES[name]
    if name == "stroke_speed":  # chosen on a log scale, because 0.02 and 0.04 differ as much as 0.2 and 0.4
        return (math.log(value) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return (value - lo) / (hi - lo)


def unscale_setting(name: str, unit: float) -> float:
    unit = min(1.0, max(0.0, float(unit)))
    lo, hi = RANGES[name]
    if name == "stroke_speed":
        return math.exp(math.log(lo) + unit * (math.log(hi) - math.log(lo)))
    return lo + unit * (hi - lo)


def action_vector(request: Request) -> np.ndarray:
    """The push as numbers: cos and sin of the heading, travel in 0..1, then the six settings in 0..1."""
    s = request.settings
    return np.array(
        [
            math.cos(request.heading),
            math.sin(request.heading),
            (request.travel - TRAVEL[0]) / (TRAVEL[1] - TRAVEL[0]),
            *(scale_setting(n, getattr(s, n)) for n in SETTING_NAMES),
        ],
        dtype=np.float32,
    )


def request_from(glass: int, vector) -> Request:
    """A push back out of numbers. Whatever a network says is clipped into the allowed ranges."""
    v = np.asarray(vector, dtype=float)
    heading = math.atan2(v[1], v[0])
    travel = TRAVEL[0] + min(1.0, max(0.0, v[2])) * (TRAVEL[1] - TRAVEL[0])
    settings = Settings(**{n: unscale_setting(n, v[3 + i]) for i, n in enumerate(SETTING_NAMES)})
    return Request(glass, heading, travel, settings)


# ----------------------------------------------------------------- the records


def load_records(*paths) -> list[dict]:
    import json
    from pathlib import Path

    rows = []
    for path in paths:
        for line in Path(path).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def boxes_of(layout: list[dict]) -> list[Box]:
    return [Box(g["x"], g["y"], g["radius"], g["height"], g["foot"]) for g in layout]


def request_of(record: dict) -> Request:
    r = record["request"]
    return Request(r["glass"], r["heading"], r["travel"], Settings(**r["settings"]))


def outcome(record: dict) -> dict:
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
    k, r = record["request"]["glass"], record["request"]
    u = (math.cos(r["heading"]), math.sin(r["heading"]))
    d = (after[k]["x"] - before[k]["x"], after[k]["y"] - before[k]["y"])
    others = [
        math.dist((a["x"], a["y"]), (b["x"], b["y"]))
        for j, (a, b) in enumerate(zip(after, before, strict=True))
        if j != k
    ]
    return {
        "feasible": True,
        "gain": sum(g["pickable"] for g in after) - sum(g["pickable"] for g in before),
        "eased": 1000.0 * (shortfall(boxes_of(before)) - shortfall(boxes_of(after))),
        "topple": record["toppled"] > 0,
        "moved": d[0] * u[0] + d[1] * u[1],
        "across": abs(d[0] * u[1] - d[1] * u[0]),
        "disturbed": max(others, default=0.0),
        "seconds": record["arm_seconds"],
    }


def hand_clear(boxes: list[Box], k: int, heading: float, travel: float, lead: float = 0.05) -> bool:
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
    u = np.array([math.cos(heading), math.sin(heading)])
    glass = boxes[k]
    middle = np.array([glass.x, glass.y])
    start = middle - (glass.radius + lead) * u
    end = middle + travel * u
    for j, other in enumerate(boxes):
        if j == k:
            continue
        centre = np.array([other.x, other.y])
        passing = min(
            glass.radius + other.radius + plan.CLEARANCE, float(np.linalg.norm(centre - middle)) - 0.001
        )
        swept = any(
            plan.segment_distance(centre, start - far * u, end - near * u)
            < half + other.radius + plan.CLEARANCE
            for near, far, half in plan.JAW_SEGMENTS
        )
        if plan.segment_distance(centre, middle, end) < passing or swept:
            return False
    return plan.in_zone(*end)


def away_angle(boxes: list[Box], k: int) -> float:
    """The direction from the nearest other glass towards glass ``k``: the way a push usually should go.

    A push towards a neighbour almost never helps, so measuring the heading from
    this direction instead of from the table's x axis hands a learner the one piece
    of geometry every good push shares, and leaves it to learn how far to depart
    from it. With one glass on the table there is no neighbour and the answer is 0.
    """
    here = boxes[k]
    best, angle = math.inf, 0.0
    for j, other in enumerate(boxes):
        if j != k:
            gap = math.dist((here.x, here.y), (other.x, other.y))
            if gap < best:
                best, angle = gap, math.atan2(here.y - other.y, here.x - other.x)
    return angle


def relative_request(glass: int, vector, boxes: list[Box]) -> Request:
    """Like ``request_from``, but the first two numbers are an angle measured from ``away_angle``."""
    request = request_from(glass, vector)
    heading = away_angle(boxes, glass) + request.heading
    return Request(glass, (heading + math.pi) % (2 * math.pi) - math.pi, request.travel, request.settings)
