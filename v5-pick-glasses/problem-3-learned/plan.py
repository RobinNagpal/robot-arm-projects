"""Clear one table: take every glass with room, push the rest apart, one push at a time.

Each push is chosen by the cross-entropy method against the forward model.
Only the first push is ever made. Then the arm looks again and plans afresh
from what it sees, so the model is trusted one push ahead and no further.

The map is the only thing written down: where a glass may stand (the zone,
which keeps it clear of the rack) and where the arm can reach. Whether a push
topples a glass, is blocked on the way down, or moves a neighbour is the
model's to say.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.table.layout import ROBOT_BASE

import features
from bench import GRIP_ROOM, Bench, Push, has_room, in_zone
from model import Ensemble, sigmoid

# Added to the room a glass needs before it is taken, for the camera's error.
# Chosen on the tuning tables: at 4 or 5 mm, glasses that had room were pushed
# instead of taken, and every extra push is another chance to topple one.
TAKE_MARGIN = 0.003

# A push is not made if any copy of the model gives it more than this chance
# of toppling something. The worst copy, not the average: where the copies
# disagree, the model has not seen a push like this one.
TOPPLE_LIMIT = 0.01

# A glass is aimed at least this far inside the zone's edge, because it will
# not land exactly where it is aimed.
ZONE_MARGIN = 0.012

# A glass predicted to move less than this is taken as not moved at all.
STILL = 0.002

# A predicted movement bigger than the push plus this is the model guessing
# outside what it has seen, and the push is dropped.
ENVELOPE = 0.02

# Each millimetre of push costs this much of a millimetre of crowding: the
# shortest push that does the job wins.
TRAVEL_COST = 0.1

# A push has to be expected to clear at least this much crowding to be worth
# making.
WORTH_IT = 0.002

# A push has to look safe on JITTERS copies of the table, each moved by about
# the camera's error as problem 2 scored it. The search tries thousands of
# pushes and will find the few where the model is wrong by luck; a hole that
# narrow does not survive a millimetre's shift.
JITTERS = 4
JITTER_POSITION = 0.001
JITTER_WIDTH = 0.003

MAX_PUSHES = 16
PUSHES_PER_GLASS = 4

# The cross-entropy search: draws per round, how many of the best are kept to
# aim the next round, and rounds.
DRAWS, ELITES, ROUNDS = 300, 30, 4


def shortfall(xy: np.ndarray, widest: np.ndarray) -> float:
    """How much room is missing on the table, summed over every glass.

    For each glass, each neighbour's edge that is inside GRIP_ROOM adds how
    far inside it is. Zero when every glass can be gripped.
    """
    gap = np.linalg.norm(xy[:, None] - xy[None], axis=-1)
    need = GRIP_ROOM + widest[None] / 2
    missing = np.clip(need - gap, 0.0, None)
    np.fill_diagonal(missing, 0.0)
    return float(missing.sum())


def _in_reach(xy: np.ndarray) -> np.ndarray:
    distance = np.linalg.norm(xy - ROBOT_BASE[:2], axis=-1)
    return (distance >= COMFORTABLE_REACH[0]) & (distance <= COMFORTABLE_REACH[1])


def _in_zone(xy: np.ndarray) -> np.ndarray:
    return np.array([in_zone(x, y) for x, y in xy]) & np.array(
        [in_zone(x - ZONE_MARGIN, y - ZONE_MARGIN) and in_zone(x + ZONE_MARGIN, y + ZONE_MARGIN) for x, y in xy]
    )


@dataclass
class Choice:
    target: int
    heading: float
    offset: float
    travel: float
    cost: float
    aim: tuple[float, float]


@dataclass
class Verdict:
    """Why a glass's best push was turned down, if it was."""

    choice: Choice | None
    reason: str


def jittered(seen: list, rng: np.random.Generator) -> list:
    """The same table with every reading moved by about the camera's error."""
    return [
        replace(
            s,
            x=s.x + rng.normal(0.0, JITTER_POSITION),
            y=s.y + rng.normal(0.0, JITTER_POSITION),
            widest=s.widest + rng.normal(0.0, JITTER_WIDTH),
            foot=s.foot + rng.normal(0.0, JITTER_WIDTH),
        )
        for s in seen
    ]


def score(model: Ensemble, seen: list, target, kind: str, heading, offset, travel, rng: np.random.Generator):
    """Expected crowding after each candidate push, and why any were dropped.

    Returns (cost per candidate, inf where dropped; predicted landing of the
    target; counts of candidates dropped for each reason).
    """
    rows = features.encode(seen, target, kind, heading, offset, travel)
    out = model.predict(rows)
    move = out.mean(0)
    topple = sigmoid(out[:, :, features.TOPPLED]).max(0)
    blocked = sigmoid(out[:, :, features.BLOCKED]).mean(0)
    for _ in range(JITTERS):
        shifted = jittered(seen, rng)
        mine = next(s for s in shifted if s.id == target.id)
        out = model.predict(features.encode(shifted, mine, kind, heading, offset, travel))
        topple = np.maximum(topple, sigmoid(out[:, :, features.TOPPLED]).max(0))

    along, left = features.frame(heading)
    slots = [target, *features.others_of(seen, target)]
    index = {s.id: i for i, s in enumerate(seen)}
    now = np.array([[s.x, s.y] for s in seen])
    widest = np.array([s.widest for s in seen])
    after = np.repeat(now[None], len(heading), 0)
    for slot, glass in enumerate(slots):
        d = (move[:, 2 * slot, None] * along + move[:, 2 * slot + 1, None] * left) * features.MOVE_SCALE
        after[:, index[glass.id]] += d
    landing = after[:, index[target.id]]

    moved_far = np.linalg.norm(landing - now[index[target.id]], axis=1) > travel + ENVELOPE
    start = np.array([features.jaw_start(target, h, o) for h, o in zip(heading, offset, strict=True)])
    tip_end = start + (features.jaw_reach(target) + travel)[:, None] * along
    reachable = _in_reach(start) & _in_reach(tip_end)
    # A glass the push leaves where it is may stand near the edge already; only
    # one it moves has to land well inside.
    moves = np.linalg.norm(after - now[None], axis=-1) > STILL
    inside = np.all(
        [_in_zone(after[:, i]) | ~moves[:, i] for i in range(len(seen))], axis=0
    )

    crowding = np.array([shortfall(a, widest) for a in after])
    here = shortfall(now, widest)
    cost = blocked * here + (1 - blocked) * crowding + TRAVEL_COST * travel

    dropped = {
        "topple": ~(topple <= TOPPLE_LIMIT),
        "map": ~(inside & reachable),
        "unsure": moved_far,
    }
    cost[dropped["topple"] | dropped["map"] | dropped["unsure"]] = math.inf
    return cost, landing, {k: int(v.sum()) for k, v in dropped.items()}


def best_push(model: Ensemble, seen: list, target, kind: str, rng: np.random.Generator) -> Verdict:
    """The cross-entropy method over heading, offset and travel for one glass."""
    half = target.widest / 2
    low = np.array([-math.pi, -features.OFFSET * half, features.TRAVEL[0]])
    high = np.array([math.pi, features.OFFSET * half, features.TRAVEL[1]])
    # First round: spread over everything, twice as many draws.
    draws = rng.uniform(low, high, (2 * DRAWS, 3))
    tally = {"topple": 0, "map": 0, "unsure": 0}
    best = None
    for _ in range(ROUNDS):
        draws[:, 0] = features.angle_wrap(draws[:, 0])
        draws[:, 1:] = np.clip(draws[:, 1:], low[1:], high[1:])
        cost, landing, dropped = score(model, seen, target, kind, draws[:, 0], draws[:, 1], draws[:, 2], rng)
        for k in tally:
            tally[k] += dropped[k]
        order = np.argsort(cost)
        if math.isfinite(cost[order[0]]) and (best is None or cost[order[0]] < best.cost):
            i = order[0]
            best = Choice(target.id, float(draws[i, 0]), float(draws[i, 1]), float(draws[i, 2]),
                          float(cost[i]), tuple(landing[i]))  # fmt: skip
        elite = draws[order[:ELITES]][np.isfinite(cost[order[:ELITES]])]
        if len(elite) < 3:
            draws = rng.uniform(low, high, (DRAWS, 3))
            continue
        # The heading's mean is taken round the circle.
        mean = np.array([math.atan2(np.sin(elite[:, 0]).mean(), np.cos(elite[:, 0]).mean()), *elite[:, 1:].mean(0)])
        spread = np.maximum(elite.std(0), [0.05, 0.002, 0.003])
        spread[0] = min(spread[0], np.std(features.angle_wrap(elite[:, 0] - mean[0])) + 0.05)
        draws = mean + spread * rng.standard_normal((DRAWS, 3))
    if best is not None:
        return Verdict(best, "")
    if tally["topple"] and tally["topple"] >= tally["map"]:
        return Verdict(None, "every push the model was asked about might tip something over")
    return Verdict(None, "nowhere inside the zone and within reach to push it to")


def clear(bench: Bench, model: Ensemble, kind: str, rng: np.random.Generator) -> dict[int, str]:
    """Rack every glass that can be reached safely. Returns the refused ones, with reasons."""
    pushes, per_glass = 0, {}
    refused: dict[int, str] = {}
    while True:
        seen = bench.look()
        if not all(s.standing for s in seen):
            # Nothing more is touched on a table with a glass lying on it.
            return {s.id: "stopped: a glass on the table has fallen over" for s in seen}
        roomy = [
            s for s in seen
            if has_room(s.x, s.y, [(o.x, o.y, o.widest) for o in seen if o.id != s.id], margin=TAKE_MARGIN)
        ]  # fmt: skip
        if roomy:
            for s in roomy:
                bench.take(s.id)
            continue
        if not seen:
            return refused

        here = shortfall(np.array([[s.x, s.y] for s in seen]), np.array([s.widest for s in seen]))
        verdicts = {}
        for target in seen:
            if per_glass.get(target.id, 0) >= PUSHES_PER_GLASS:
                verdicts[target.id] = Verdict(None, f"pushed {PUSHES_PER_GLASS} times and still without room")
                continue
            verdicts[target.id] = best_push(model, seen, target, kind, rng)
        choices = [v.choice for v in verdicts.values() if v.choice is not None]
        choice = min(choices, key=lambda c: c.cost, default=None)

        if pushes >= MAX_PUSHES or choice is None or choice.cost > here - WORTH_IT:
            for s in seen:
                verdict = verdicts[s.id]
                if pushes >= MAX_PUSHES:
                    refused[s.id] = f"the table's {MAX_PUSHES} pushes are spent"
                elif verdict.choice is None:
                    refused[s.id] = verdict.reason
                else:
                    refused[s.id] = "no push the model expects to make room"
            return refused

        target = next(s for s in seen if s.id == choice.target)
        bench.push(
            Push(
                glass=choice.target,
                start=features.jaw_start(target, choice.heading, choice.offset),
                heading=choice.heading,
                reach=features.jaw_reach(target),
                travel=choice.travel,
                aim=choice.aim,
            )
        )
        pushes += 1
        per_glass[choice.target] = per_glass.get(choice.target, 0) + 1
