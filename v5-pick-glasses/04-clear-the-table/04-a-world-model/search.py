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

from keeping_clear import why_not_clear
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

# What a chance of toppling something costs a candidate, in metres of crowding
# per unit of chance. This is the search's answer to the winner's curse, and it
# is the one number here that was added after the first held-out walk rather
# than inherited from problem 3.
#
# **Why a price and not just a limit.** A limit alone makes every push under it
# equally attractive, so the search is free to pick the candidate at the very
# edge of what the model will allow -- and because it is maximising over the
# model's own estimates, that edge is exactly where the model is most likely to
# be wrong. The first walk of the held-out queue broke eight glasses, every one
# of them on a push the model called safe. With a price, a candidate that is
# nearly as useful and much less frightening wins instead.
#
# At the limit the price costs a candidate five millimetres of crowding, which
# is what a fifty-millimetre push costs in travel, so a push at the edge of the
# limit has to be worth about that much more room than a safe one to be chosen.
RISK_COST = 0.5

# A push has to look safe on the table as measured and on this many copies of
# it moved by about the camera's own error. The search asks about thousands of
# pushes and will find the few where the model is wrong by luck; a hole that
# narrow does not survive a millimetre's shift.
JITTERS = 2
JITTER_POSITION = 0.001
JITTER_WIDTH = 0.003

# How many of a round's best candidates are put through the clearance check
# before the round is given up on. The corridor filter in ``score`` has already
# thrown out the candidates that sweep a neighbour, so this is the second and
# stricter reading of the same question, asked of the path the push would really
# be carried out as: it includes the descent at the touchdown point, which the
# corridor rule does not. Twelve, because it is the only part of the search that
# is not vectorised, and measured on the tuning band it changes the answer for
# about one candidate in ten.
CLEARANCE_TRIES = 12

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
    # The chance the model's least favourable copy gives this push of putting
    # something over. It is kept so that a run can record what it believed
    # before it pushed, which is the one thing the first held-out walk could
    # not say: whether the pushes that toppled a glass were ones the model was
    # confident about or ones its copies disagreed over.
    risk: float = 0.0


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, int]]:
    """What the table would be left like after each candidate push, and what was dropped.

    ``draws`` is one row per candidate: heading, offset, travel, reach.
    Returns the cost of each candidate, infinite where it was dropped; where
    the model says the pushed glass would end up; the chance it gives each
    candidate of putting something over; and how many candidates each reason
    dropped.

    **Every reading of the model here is its least favourable copy and not its
    average, and that is the change the first held-out walk asked for.** Three
    copies of the network are fitted from different starting weights, so where
    they agree the model has seen pushes like this one and where they disagree
    it has not. A search that averages them is at its most confident exactly
    where it is most ignorant, because it is choosing the best of a few thousand
    noisy estimates. Taking the worst copy of the crowding, the worst copy of
    the topple chance and the worst copy of every map check turns disagreement
    from something the search can exploit into something that costs it.
    """
    heading, offset, travel, reach = (draws[:, i] for i in range(4))
    rows = encoding.encode(seen, target, heading, offset, travel, reach)
    out = model.predict(rows)
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
    # One table per copy of the model, per candidate: (copies, candidates,
    # glasses, 2). The copies are what the pessimism below is taken over.
    after = np.broadcast_to(now, (out.shape[0], len(draws), len(seen), 2)).copy()
    for slot, glass in enumerate(slots):
        across = out[:, :, 2 * slot, None] * along[None]
        sideways = out[:, :, 2 * slot + 1, None] * left[None]
        after[:, :, where[glass.id]] += (across + sideways) * encoding.MOVE_SCALE
    # Where the glass is expected to land is the average of the copies, because
    # it is written into the push as its aim and reported as what the model
    # believes. The pessimism belongs in what a candidate costs, not in what the
    # solution is told to expect.
    landing = after.mean(0)[:, where[target.id]]

    # Where the fingertips come down and where they end up, which are the two
    # poses the arm has to be able to hold. The touchdown point is the one
    # ``encoding.push_of`` writes, for every candidate at once.
    middle = now[where[target.id]]
    start = middle - (target.widest / 2 + plan.APPROACH_GAP) * along + offset[:, None] * left
    tip_end = start + (reach + travel)[:, None] * along
    usable = in_reach(start) & in_reach(tip_end) & on_table(start) & on_table(tip_end)
    # A glass the push leaves where it is may already stand near the zone's
    # edge; only one the push moves has to land well inside it. A candidate is
    # kept only if every copy of the model says the table stays inside the zone.
    moves = np.linalg.norm(after - now[None, None], axis=-1) > STILL
    inside = np.all(in_zone(after) | ~moves, axis=-1).all(0)
    gone = np.linalg.norm(after[:, :, where[target.id]] - middle, axis=-1)
    went_far = (gone > travel[None] + ENVELOPE).any(0)

    cost = shortfall(after, widest).max(0) + TRAVEL_COST * travel + RISK_COST * topple
    dropped = {
        "topple": ~(topple <= TOPPLE_LIMIT),
        "map": ~(inside & usable),
        "unsure": went_far,
        "swept": ~corridor_is_clear(seen, target, draws),
    }
    cost = np.where(
        dropped["topple"] | dropped["map"] | dropped["unsure"] | dropped["swept"], math.inf, cost
    )
    return cost, landing, topple, {reason: int(flags.sum()) for reason, flags in dropped.items()}


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


def segment_distances(centres: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """How far each centre is from each candidate's line, as ``(candidates, centres)``.

    ``plan.segment_distance`` answers this for one line and one point, and the
    search asks it about a few hundred lines and a few points at once, so it is
    written out here over whole arrays. ``test_world_model.py`` holds the two
    against each other on drawn tables, which is what keeps them the same
    arithmetic rather than two versions of it.
    """
    line = ends - starts
    length = np.maximum((line * line).sum(-1), 1e-18)
    offset = centres[None, :, :] - starts[:, None, :]
    part = np.clip((offset * line[:, None, :]).sum(-1) / length[:, None], 0.0, 1.0)
    nearest = starts[:, None, :] + part[..., None] * line[:, None, :]
    return np.linalg.norm(centres[None, :, :] - nearest, axis=-1)


def corridor_is_clear(seen: list[Seen], target: Seen, draws: np.ndarray) -> np.ndarray:
    """Whether each candidate push leaves every other glass alone on the way in.

    **Why the search has to ask this at all.** The model is asked where the
    glasses will end up and is never asked what the hand passes through to get
    there, so nothing in the search as it first stood stopped it choosing a push
    whose approach crosses a neighbour. A hand sweeping a glass puts it over as
    surely as a shove does, and the first walk of the held-out queue lost seven
    tables and eight glasses that way.

    **The rule is the geometry reference's own**, written out over arrays
    instead of one push at a time: the glass must not be driven into a
    neighbour, and no stretch of the hand may sweep within ``CLEARANCE`` of one.
    The hand is not one shape -- rolled, it stays narrow for the first hundred
    and thirty millimetres and then widens to the body -- so each stretch is
    checked against its own width, which is what ``JAW_SEGMENTS`` holds.

    It is asked here, as a filter on the candidates, and not of the push that
    won. A glass whose best push happens to cross a neighbour has other pushes,
    and measured on forty tuning tables, vetoing the winner separated eight
    tables where searching among clear pushes separates seventeen.
    """
    others = [glass for glass in seen if glass.id != target.id]
    if not others:
        return np.ones(len(draws), dtype=bool)
    heading, offset, travel, reach = (draws[:, i] for i in range(4))
    along, left = encoding.frame(heading)
    middle = np.array([target.x, target.y])
    radius = target.widest / 2
    start = middle - (radius + plan.APPROACH_GAP) * along + offset[:, None] * left
    tip_end = start + (reach + travel)[:, None] * along
    landing = middle + travel[:, None] * along

    centres = np.array([[glass.x, glass.y] for glass in others])
    radii = np.array([glass.widest / 2 for glass in others])
    # A glass may already stand closer to its neighbour than the clearance
    # asks; moving it is fine as long as it gets no closer. The reference's own
    # allowance, and the reason the limit is a minimum of two numbers.
    gap = np.linalg.norm(centres - middle, axis=-1) - 0.001
    passing = np.minimum(radius + radii + plan.CLEARANCE, gap)
    clear = segment_distances(centres, np.broadcast_to(middle, landing.shape), landing) >= passing[None]
    for near, far, half in plan.JAW_SEGMENTS:
        swept = segment_distances(centres, start - far * along, tip_end - near * along)
        clear &= swept >= (half + radii + plan.CLEARANCE)[None]
    return clear.all(-1)


def keeps_clear(seen: list[Seen], target: Seen, choice: Choice) -> bool:
    """Whether the path this push would be carried out as passes the clearance check.

    ``corridor_is_clear`` above asks the geometry reference's question about the
    corridor the hand sweeps. This asks ``keeping_clear``'s question about the
    waypoints themselves, which is the one every solution in this problem can
    ask of its own answer, and it covers one thing the corridor rule does not:
    the hand standing at the touchdown point while it comes down.
    """
    push = encoding.push_of(target, choice.heading, choice.offset, choice.travel, choice.aim)
    path = borrowed.jaw_paths.to_push(None, push, choice.reach)
    return not why_not_clear(path, seen, target=target.id, tested=accounted_for(target, choice))


def accounted_for(target: Seen, choice: Choice) -> tuple[int, ...]:
    """The glass this push is at, when this solution can account for it sliding.

    The clearance rule asks a solution to account for driving a glass at all,
    because every glass this cell draws is one the public tipping rule answers
    "it depends on the friction" for. The reference solution accounts for it by
    probing the glass and watching whether it moved. **This solution accounts
    for it with the model it fitted**, which was fitted on pushes in this cell
    including the ones that put a glass over, and whose least favourable copy
    gives this push at most ``TOPPLE_LIMIT`` chance of toppling anything.

    That is evidence of the same kind and arguably of a better kind, because it
    is about this push at this glass rather than about one earlier shove. It is
    written out here rather than left implicit in the search's own dropping of
    risky candidates, so that the link between the two is visible and survives
    somebody changing either of them.
    """
    return (target.id,) if choice.risk <= TOPPLE_LIMIT else ()


def best_push(model: Ensemble, seen: list[Seen], target: Seen, rng: np.random.Generator) -> Verdict:
    """The cross-entropy method over heading, offset, travel and reach for one glass."""
    low, high = bounds(target)
    # The first round is spread over the whole box, and twice as wide, because
    # nothing is known yet about where the good pushes are.
    draws = rng.uniform(low, high, (2 * DRAWS, 4))
    tally = {"topple": 0, "map": 0, "unsure": 0, "swept": 0}
    best = None
    for _ in range(ROUNDS):
        draws[:, 0] = encoding.angle_wrap(draws[:, 0])
        draws[:, 1:] = np.clip(draws[:, 1:], low[1:], high[1:])
        cost, landing, risk, dropped = score(model, seen, target, draws, rng)
        for reason in dropped:
            tally[reason] += dropped[reason]
        order = np.argsort(cost)
        # The cheapest candidate whose own path passes the clearance check every
        # solution in this problem can run. Only the first few are worth asking
        # about: they are already in the order the model prefers them and the
        # corridor filter has already removed the ones that sweep a neighbour,
        # so a round whose whole head fails is a round to draw again rather than
        # one to take a worse push from.
        for i in order[:CLEARANCE_TRIES]:
            if not math.isfinite(cost[i]):
                break
            candidate = Choice(
                target=target.id,
                heading=float(draws[i, 0]),
                offset=float(draws[i, 1]),
                travel=float(draws[i, 2]),
                reach=float(draws[i, 3]),
                cost=float(cost[i]),
                aim=(float(landing[i, 0]), float(landing[i, 1])),
                risk=float(risk[i]),
            )
            if not keeps_clear(seen, target, candidate):
                tally["swept"] += 1
                continue
            if best is None or candidate.cost < best.cost:
                best = candidate
            break
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
    if tally["swept"] and tally["swept"] >= max(tally["topple"], tally["map"]):
        return Verdict(None, "every push worth making would sweep another glass on the way in")
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
