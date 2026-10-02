"""Choose one push against the forward model. Programmed: the search, not the model.

Problem 3's cross-entropy search (problem-3-learned/plan.py), with three
changes for mixed tables:

- each glass is given its own kind, or NOT_MEASURED;
- a push on a glass that is not measured must clear a stricter topple limit,
  because what the model learned for such a glass is an average over the
  kinds it could be, not the worst of them;
- room is only counted for glasses still worth racking. A glass already
  refused, or one the rack has no slot for, is not pushed for.

The map is the only thing written down: where a glass may stand and where the
arm can reach. Whether a push topples, is blocked or moves a neighbour is the
model's to say.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.table.layout import ROBOT_BASE

import push_features as features
from bench import GRIP_ROOM, in_zone
from push_model import Ensemble, sigmoid

# Problem 3's settings, chosen on its tuning tables.
TAKE_MARGIN = 0.003
TOPPLE_LIMIT = 0.01
ZONE_MARGIN = 0.012
STILL = 0.002
ENVELOPE = 0.02
TRAVEL_COST = 0.1
WORTH_IT = 0.002
JITTERS = 4
JITTER_POSITION = 0.001
JITTER_WIDTH = 0.003
DRAWS, ELITES, ROUNDS = 300, 30, 4

# For a glass nobody has measured yet. Stricter than TOPPLE_LIMIT; a tuning
# number, set by eye, not on tuning tables.
UNMEASURED_TOPPLE_LIMIT = 0.005


def shortfall(xy: np.ndarray, widest: np.ndarray, wanted: np.ndarray) -> float:
    """Room still missing round the glasses worth racking, summed.

    For each wanted glass, every neighbour's edge inside GRIP_ROOM adds how far
    inside it is. A refused glass still counts as a neighbour that is in the
    way; it just has no room of its own to win.
    """
    gap = np.linalg.norm(xy[:, None] - xy[None], axis=-1)
    missing = np.clip(GRIP_ROOM + widest[None] / 2 - gap, 0.0, None)
    np.fill_diagonal(missing, 0.0)
    return float((missing * wanted[:, None]).sum())


def _in_reach(xy: np.ndarray) -> np.ndarray:
    distance = np.linalg.norm(xy - ROBOT_BASE[:2], axis=-1)
    return (distance >= COMFORTABLE_REACH[0]) & (distance <= COMFORTABLE_REACH[1])


def _in_zone(xy: np.ndarray) -> np.ndarray:
    return np.array(
        [
            in_zone(x - ZONE_MARGIN, y - ZONE_MARGIN) and in_zone(x + ZONE_MARGIN, y + ZONE_MARGIN)
            for x, y in xy
        ]
    )


@dataclass
class Choice:
    target: int
    heading: float
    offset: float
    travel: float
    cost: float
    aim: tuple[float, float]
    topple: float  # the worst copy's topple chance


@dataclass
class Verdict:
    choice: Choice | None
    reason: str


def jittered(seen: list, rng: np.random.Generator) -> list:
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


def score(model: Ensemble, seen, target, kinds, wanted, heading, offset, travel, rng):
    """Expected room missing after each candidate push; inf where a push is dropped."""
    out = model.predict(features.encode(seen, target, kinds, heading, offset, travel))
    move = out.mean(0)
    topple = sigmoid(out[:, :, features.TOPPLED]).max(0)
    blocked = sigmoid(out[:, :, features.BLOCKED]).mean(0)
    for _ in range(JITTERS):
        shifted = jittered(seen, rng)
        mine = next(s for s in shifted if s.id == target.id)
        out = model.predict(features.encode(shifted, mine, kinds, heading, offset, travel))
        topple = np.maximum(topple, sigmoid(out[:, :, features.TOPPLED]).max(0))

    along, left = features.frame(heading)
    index = {s.id: i for i, s in enumerate(seen)}
    now = np.array([[s.x, s.y] for s in seen])
    widest = np.array([s.widest for s in seen])
    after = np.repeat(now[None], len(heading), 0)
    for slot, glass in enumerate([target, *features.others_of(seen, target)]):
        d = (move[:, 2 * slot, None] * along + move[:, 2 * slot + 1, None] * left) * features.MOVE_SCALE
        after[:, index[glass.id]] += d
    landing = after[:, index[target.id]]

    moved_far = np.linalg.norm(landing - now[index[target.id]], axis=1) > travel + ENVELOPE
    start = np.array([features.jaw_start(target, h, o) for h, o in zip(heading, offset, strict=True)])
    tip_end = start + (features.jaw_reach(target) + travel)[:, None] * along
    reachable = _in_reach(start) & _in_reach(tip_end)
    moves = np.linalg.norm(after - now[None], axis=-1) > STILL
    inside = np.all([_in_zone(after[:, i]) | ~moves[:, i] for i in range(len(seen))], axis=0)

    crowding = np.array([shortfall(a, widest, wanted) for a in after])
    here = shortfall(now, widest, wanted)
    cost = blocked * here + (1 - blocked) * crowding + TRAVEL_COST * travel

    limit = TOPPLE_LIMIT if target.id in kinds else UNMEASURED_TOPPLE_LIMIT
    dropped = {"topple": ~(topple <= limit), "map": ~(inside & reachable), "unsure": moved_far}
    cost[dropped["topple"] | dropped["map"] | dropped["unsure"]] = math.inf
    return cost, landing, topple, {k: int(v.sum()) for k, v in dropped.items()}


def best_push(model: Ensemble, seen, target, kinds, wanted, rng: np.random.Generator) -> Verdict:
    """The cross-entropy method over heading, offset and travel for one glass."""
    half = target.widest / 2
    low = np.array([-math.pi, -features.OFFSET * half, features.TRAVEL[0]])
    high = np.array([math.pi, features.OFFSET * half, features.TRAVEL[1]])
    draws = rng.uniform(low, high, (2 * DRAWS, 3))
    tally = {"topple": 0, "map": 0, "unsure": 0}
    best = None
    for _ in range(ROUNDS):
        draws[:, 0] = features.angle_wrap(draws[:, 0])
        draws[:, 1:] = np.clip(draws[:, 1:], low[1:], high[1:])
        cost, landing, topple, dropped = score(
            model, seen, target, kinds, wanted, draws[:, 0], draws[:, 1], draws[:, 2], rng
        )
        for k in tally:
            tally[k] += dropped[k]
        order = np.argsort(cost)
        if math.isfinite(cost[order[0]]) and (best is None or cost[order[0]] < best.cost):
            i = order[0]
            best = Choice(target.id, float(draws[i, 0]), float(draws[i, 1]), float(draws[i, 2]),
                          float(cost[i]), tuple(landing[i]), float(topple[i]))  # fmt: skip
        elite = draws[order[:ELITES]][np.isfinite(cost[order[:ELITES]])]
        if len(elite) < 3:
            draws = rng.uniform(low, high, (DRAWS, 3))
            continue
        mean = np.array(
            [math.atan2(np.sin(elite[:, 0]).mean(), np.cos(elite[:, 0]).mean()), *elite[:, 1:].mean(0)]
        )
        spread = np.maximum(elite.std(0), [0.05, 0.002, 0.003])
        spread[0] = min(spread[0], np.std(features.angle_wrap(elite[:, 0] - mean[0])) + 0.05)
        draws = mean + spread * rng.standard_normal((DRAWS, 3))
    if best is not None:
        return Verdict(best, "")
    if tally["topple"] and tally["topple"] >= tally["map"]:
        return Verdict(None, "every push the model was asked about might tip something over")
    return Verdict(None, "nowhere inside the zone and within reach to push it to")
