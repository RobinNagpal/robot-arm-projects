"""Which push to make next, decided by asking the model about thousands of them.

For one glass, the cross-entropy method draws pushes, asks the model what each
one would do to the table, keeps the best few, draws again around those, and
repeats. The best push over all the crowded glasses is the one made. Then the
arm looks again and the search runs afresh, so the model is trusted one push
ahead and no further.

**The map is the only thing written down.** Where a glass may stand -- the
glass zone, which keeps it clear of the rack -- and how far the arm can reach.
Whether a push slides a glass, topples it, moves its neighbour or misses it
altogether is the model's to say, and there is no friction value and no tipping
formula anywhere in this folder.

With one exception, and it is worth being plain about it. **How deep the
fingertips may be driven is still bounded by the geometry reference's own lean
bound.** Problem 3's solution 4 has no such rail and paid for it with twenty
toppled glasses in fifty tables; there a toppled glass costs that table, and
here it costs that table too, except that problem 4 pays no partial credit for
the glasses on it. Reaching deeper than the bound is also the one mistake a
camera cannot see coming, because a glass that has not been touched and a glass
that is leaning both sit still. So the rail stays, and ``deepest`` is the
reference's function rather than a second copy of its arithmetic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import borrowed
import encoding
import numpy as np
from push_model import Ensemble, sigmoid
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.table.layout import ROBOT_BASE, TABLE_CENTRE_XY, TABLE_SIZE

from partners import GLASS_ZONE, GRIP_ROOM, Seen

import plan

# The deepest the fingertips may be driven while feeling for a glass, which is
# the reference's own bound: the glass's measured middle, or the lean that much
# travel against it would imply, whichever is nearer. Borrowed rather than
# worked out again -- a second copy would be free to drift, and this one took
# four rounds of measurement against the cell to get right.
deepest = borrowed.nudge._furthest

# A push is not made if any copy of the model gives it more than this chance of
# toppling something. The worst copy, not the average: where the copies
# disagree the model has not seen a push like this one, and problem 4 cannot
# absorb a toppled glass.
#
# Problem 3's own figure, and it needed no changing, which is itself worth
# knowing. Measured on tables 500 to 519 -- neither the tables the model was
# trained on nor the twenty the README reports -- the result hardly moves
# anywhere below 0.04: between 0.002 and 0.02 it is seven or eight tables
# separated and one or two glasses over, and only at 0.08 does it start
# trading glasses for tables. The model's worst copy is nearly always either
# sure or appalled, so there is not much in between for a threshold to cut.
TOPPLE_LIMIT = 0.01

# A glass is aimed at least this far inside the zone's edge, because it will
# not land exactly where it is aimed.
ZONE_MARGIN = 0.012

# A glass the model predicts to move less than this is taken as not moved.
STILL = 0.002

# A predicted movement longer than the push itself plus this is the model
# answering outside what it has seen, and the push is dropped.
ENVELOPE = 0.02

# Each millimetre pushed costs this much of a millimetre of crowding, so the
# shortest push that does the job wins. Problem 3's figure, and it earns its
# keep twice over here: a millimetre of push is also a millimetre of arm time.
TRAVEL_COST = 0.1

# A push has to be expected to clear at least this much crowding to be worth
# making.
WORTH_IT = 0.002

# A push has to look safe on the table as measured and on this many copies of
# it moved by about the camera's own error. The search asks about thousands of
# pushes and will find the few where the model is wrong by luck; a hole that
# narrow does not survive a millimetre's shift.
JITTERS = 2
JITTER_POSITION = 0.001
JITTER_WIDTH = 0.003

# The cross-entropy search: draws a round, how many of the best aim the next
# round, and how many rounds. Smaller than problem 3's, because problem 4's
# search has a fourth number in it -- how far to reach in -- and the thinking
# time is reported per answer rather than per push.
DRAWS, ELITES, ROUNDS = 200, 24, 3


def shortfall(xy: np.ndarray, widest: np.ndarray) -> np.ndarray:
    """How much room the table is short of, summed over its glasses, metres.

    The reference's own measure -- each glass's worst neighbour, not every
    neighbour -- so that the search is optimising the number the geometry
    reference eases and the draw reports. ``test_world_model.py`` checks the
    two agree on drawn tables; this one takes a stack of tables at once,
    because the search weighs hundreds of them per round.
    """
    xy, widest = np.asarray(xy, dtype=float), np.asarray(widest, dtype=float)
    count = xy.shape[-2]
    if count < 2:
        return np.zeros(xy.shape[:-2])
    gap = np.linalg.norm(xy[..., :, None, :] - xy[..., None, :, :], axis=-1)
    # need[j] is the room glass j's neighbour has to keep from it, which is the
    # grip's own width and half of j's: not symmetric, because a narrow glass
    # beside a wide one is crowded before the wide one is.
    missing = (GRIP_ROOM + widest / 2.0) - gap
    # A glass is not its own neighbour, and it is nearer to itself than any.
    missing = np.where(np.eye(count, dtype=bool), -np.inf, missing)
    return np.clip(missing.max(-1), 0.0, None).sum(-1)


def in_reach(xy: np.ndarray) -> np.ndarray:
    """Whether the arm can hold the jaw at each of these points, as ``plan.reachable`` asks it."""
    distance = np.linalg.norm(xy - ROBOT_BASE[:2], axis=-1)
    return (distance >= COMFORTABLE_REACH[0]) & (distance <= COMFORTABLE_REACH[1])


def on_table(xy: np.ndarray) -> np.ndarray:
    """Whether the jaw could be put at each of these points at all.

    ``follow()`` refuses a path with a waypoint off the table, and a refused
    path is worse than a push that does nothing: the arm never moves, so the
    solution is handed the same table back and has spent one of that glass's
    tries on nothing. The touchdown point of a push sits outside the glass, so
    a glass near the edge of the zone can easily have one off the table.

    The margin is the reference's own ``TABLE_MARGIN``: a pose on the very rim
    is one the arm would have to reach over the edge to hold.
    """
    inset = borrowed.tour.TABLE_MARGIN
    return (np.abs(xy[..., 0] - TABLE_CENTRE_XY[0]) <= TABLE_SIZE[0] / 2 - inset) & (
        np.abs(xy[..., 1] - TABLE_CENTRE_XY[1]) <= TABLE_SIZE[1] / 2 - inset
    )


def in_zone(xy: np.ndarray, margin: float = ZONE_MARGIN) -> np.ndarray:
    """Whether each point is this far inside the glass zone.

    The cell's own ``in_zone`` with a margin, over a whole stack of tables.
    ``test_world_model.py`` checks it against ``partners.in_zone`` at a margin
    of nothing, so the two cannot drift apart.
    """
    x_min, x_max, y_min, y_max = GLASS_ZONE
    x, y = xy[..., 0], xy[..., 1]
    return (x >= x_min + margin) & (x <= x_max - margin) & (y >= y_min + margin) & (y <= y_max - margin)


@dataclass
class Choice:
    """One push the search would make, and what it expects of it."""

    target: int
    heading: float
    offset: float
    travel: float
    reach: float  # how far the fingertips go in before the model expects to meet the glass
    cost: float  # the crowding the table is expected to be left with, plus the push's own price
    aim: tuple[float, float]  # where the model says the glass will end up


@dataclass
class Verdict:
    """The best push for one glass, or why it has none."""

    choice: Choice | None
    reason: str


def jittered(seen: list[Seen], rng: np.random.Generator) -> list[Seen]:
    """The same table with every reading moved by about the camera's error."""
    return [
        replace(
            glass,
            x=glass.x + rng.normal(0.0, JITTER_POSITION),
            y=glass.y + rng.normal(0.0, JITTER_POSITION),
            widest=glass.widest + rng.normal(0.0, JITTER_WIDTH),
            foot=glass.foot + rng.normal(0.0, JITTER_WIDTH),
        )
        for glass in seen
    ]


def score(
    model: Ensemble,
    seen: list[Seen],
    target: Seen,
    draws: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    """What the table would be left like after each candidate push, and what was dropped.

    ``draws`` is one row per candidate: heading, offset, travel, reach.
    Returns the cost of each candidate, infinite where it was dropped; where
    the model says the pushed glass would end up; and how many candidates each
    reason dropped.
    """
    heading, offset, travel, reach = (draws[:, i] for i in range(4))
    rows = encoding.encode(seen, target, heading, offset, travel, reach)
    out = model.predict(rows)
    move = out.mean(0)
    topple = sigmoid(out[:, :, encoding.TOPPLED]).max(0)
    for _ in range(JITTERS):
        shifted = jittered(seen, rng)
        mine = next(glass for glass in shifted if glass.id == target.id)
        shaken = model.predict(encoding.encode(shifted, mine, heading, offset, travel, reach))
        topple = np.maximum(topple, sigmoid(shaken[:, :, encoding.TOPPLED]).max(0))

    along, left = encoding.frame(heading)
    slots = [target, *encoding.others_of(seen, target)]
    where = {glass.id: i for i, glass in enumerate(seen)}
    now = np.array([[glass.x, glass.y] for glass in seen])
    widest = np.array([glass.widest for glass in seen])
    after = np.repeat(now[None], len(draws), 0)
    for slot, glass in enumerate(slots):
        step = (move[:, 2 * slot, None] * along + move[:, 2 * slot + 1, None] * left) * encoding.MOVE_SCALE
        after[:, where[glass.id]] += step
    landing = after[:, where[target.id]]

    # Where the fingertips come down and where they end up, which are the two
    # poses the arm has to be able to hold. The touchdown point is the one
    # ``encoding.push_of`` writes, for every candidate at once.
    middle = now[where[target.id]]
    start = middle - (target.widest / 2 + plan.APPROACH_GAP) * along + offset[:, None] * left
    tip_end = start + (reach + travel)[:, None] * along
    usable = in_reach(start) & in_reach(tip_end) & on_table(start) & on_table(tip_end)
    # A glass the push leaves where it is may already stand near the zone's
    # edge; only one the push moves has to land well inside it.
    moves = np.linalg.norm(after - now[None], axis=-1) > STILL
    inside = np.all(in_zone(after) | ~moves, axis=-1)
    went_far = np.linalg.norm(landing - now[where[target.id]], axis=1) > travel + ENVELOPE

    cost = shortfall(after, widest) + TRAVEL_COST * travel
    dropped = {
        "topple": ~(topple <= TOPPLE_LIMIT),
        "map": ~(inside & usable),
        "unsure": went_far,
    }
    cost = np.where(dropped["topple"] | dropped["map"] | dropped["unsure"], math.inf, cost)
    return cost, landing, {reason: int(flags.sum()) for reason, flags in dropped.items()}


def bounds(target: Seen) -> tuple[np.ndarray, np.ndarray]:
    """The box the search draws its pushes from: heading, offset, travel, reach.

    ``reach`` starts at the touchdown point itself -- a reach of nothing cannot
    touch the glass at all, because the touchdown point is already outside its
    widest part -- and stops at the lean bound.
    """
    half = target.widest / 2
    low = np.array([-math.pi, -encoding.OFFSET * half, encoding.TRAVEL[0], plan.APPROACH_GAP])
    high = np.array([math.pi, encoding.OFFSET * half, encoding.TRAVEL[1], deepest(target)])
    return low, np.maximum(high, low + 1e-6)


def best_push(model: Ensemble, seen: list[Seen], target: Seen, rng: np.random.Generator) -> Verdict:
    """The cross-entropy method over heading, offset, travel and reach for one glass."""
    low, high = bounds(target)
    # The first round is spread over the whole box, and twice as wide, because
    # nothing is known yet about where the good pushes are.
    draws = rng.uniform(low, high, (2 * DRAWS, 4))
    tally = {"topple": 0, "map": 0, "unsure": 0}
    best = None
    for _ in range(ROUNDS):
        draws[:, 0] = encoding.angle_wrap(draws[:, 0])
        draws[:, 1:] = np.clip(draws[:, 1:], low[1:], high[1:])
        cost, landing, dropped = score(model, seen, target, draws, rng)
        for reason in tally:
            tally[reason] += dropped[reason]
        order = np.argsort(cost)
        if math.isfinite(cost[order[0]]) and (best is None or cost[order[0]] < best.cost):
            i = order[0]
            best = Choice(
                target=target.id,
                heading=float(draws[i, 0]),
                offset=float(draws[i, 1]),
                travel=float(draws[i, 2]),
                reach=float(draws[i, 3]),
                cost=float(cost[i]),
                aim=(float(landing[i, 0]), float(landing[i, 1])),
            )
        elite = draws[order[:ELITES]][np.isfinite(cost[order[:ELITES]])]
        if len(elite) < 3:
            # Nothing worth aiming at, so start again rather than draw tighter
            # and tighter around a hole the model has refused.
            draws = rng.uniform(low, high, (DRAWS, 4))
            continue
        # The heading's mean is taken round the circle, not along the number line.
        turn = math.atan2(np.sin(elite[:, 0]).mean(), np.cos(elite[:, 0]).mean())
        mean = np.array([turn, *elite[:, 1:].mean(0)])
        spread = np.maximum(elite.std(0), [0.05, 0.002, 0.003, 0.002])
        spread[0] = min(spread[0], np.std(encoding.angle_wrap(elite[:, 0] - mean[0])) + 0.05)
        draws = mean + spread * rng.standard_normal((DRAWS, 4))
    if best is not None:
        return Verdict(best, "")
    if tally["topple"] and tally["topple"] >= tally["map"]:
        return Verdict(None, "every push the model was asked about might tip something over")
    return Verdict(None, "nowhere inside the zone and within reach to push it to")


def predicted_table(model: Ensemble, seen: list[Seen], target: Seen, choice: Choice) -> dict:
    """Where the model says every glass it can see will be after this one push.

    The search already worked this out while it was weighing hundreds of
    candidates, and it is asked again here for the one that won rather than
    carried through the search, because a Choice that held a whole table would
    be a Choice nothing else could read.

    This is what a solution running without a look between pushes believes
    instead of looking.
    """
    draws = np.array([[choice.heading, choice.offset, choice.travel, choice.reach]])
    rows = encoding.encode(seen, target, draws[:, 0], draws[:, 1], draws[:, 2], draws[:, 3])
    move = model.predict(rows).mean(0)
    along, left = encoding.frame(draws[:, 0])
    places = {}
    for slot, glass in enumerate([target, *encoding.others_of(seen, target)]):
        step = (move[:, 2 * slot, None] * along + move[:, 2 * slot + 1, None] * left) * encoding.MOVE_SCALE
        places[glass.id] = (glass.x + float(step[0, 0]), glass.y + float(step[0, 1]))
    return places


def worth_making(choice: Choice | None, crowding: float) -> bool:
    """Whether the best push found is expected to leave the table better than it is.

    Without this a solution would push a glass two millimetres for ever: every
    push cuts the crowding by something, and the something can be smaller than
    the error in measuring it.
    """
    return choice is not None and choice.cost <= crowding - WORTH_IT


def crowding_now(seen: list[Seen]) -> float:
    """How much room the table is short of, as the arm believes the table to be."""
    if not seen:
        return 0.0
    xy = np.array([[glass.x, glass.y] for glass in seen])
    return float(shortfall(xy, np.array([glass.widest for glass in seen])))
