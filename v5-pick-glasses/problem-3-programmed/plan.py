"""Which glass to push, from where, which way and how far. Geometry only.

Solution 3 of the overview. Every landing spot is checked against the whole
table before anything is scored: room from every other glass, inside the
zone, inside the reach, and a clear path for both the glass and the jaw. Of
what survives, the shortest push wins, because every millimetre pushed is a
millimetre in which something can be knocked.

Nothing here predicts where a glass will end up. The push is aimed, made, and
the next look says where it went.
"""

from __future__ import annotations

import math

import numpy as np
from work_cell.arm.dimensions import COMFORTABLE_REACH, FINGERTIP_OFFSET
from work_cell.table.layout import ROBOT_BASE

from bench import (
    BODY_SIZE,
    FINGER_LENGTH,
    GRIP_ROOM,
    JAW_THICKNESS,
    JAW_TOP,
    TOOL_LENGTH,
    Push,
    Seen,
    has_room,
    in_zone,
)

# Glass on a dry wooden top is somewhere in here. Nothing in the cell measures
# it, so the tipping check is made at both ends.
MU_LOWEST = 0.2
MU_HIGHEST = 0.5

# A glass that slides only at the low end is tried with a push this long, and
# looked at before and after. Short pushes lose up to 2.5 mm to the contact
# taking up and the glass settling onto its far edge, so this is well over that.
PROBE = 0.005
# The probe counts as a slide when the glass moved this far. A glass that
# tipped instead leans back to where it was, give or take the error in the
# averaged looks, about 0.4 mm.
PROBE_MOVED = 0.0015
# Looks averaged before and after a probe.
LOOKS_PER_PROBE = 3
# The probe is only made when the lean it could cause is under this share of
# the angle the glass would fall past.
PROBE_LEAN_SHARE = 0.7
# That angle needs the height of the centre of mass. No glass has it above
# this share of its own height: the family tests check it.
CENTRE_OF_MASS_SHARE = 2 / 3

# A push aims this far past where the glass would just have room, so one that
# lands a little short still clears.
AIM_MARGIN = 0.010

# The fingertips come down this far outside the glass's widest part, then feel
# their way in underneath it.
APPROACH_GAP = 0.010

# How far past where the glass should be to keep feeling before deciding it is
# not there. A few measurement errors.
FEEL_BEYOND = 0.030

# Space kept between the jaw, or the glass being pushed, and any other glass.
CLEARANCE = 0.008

# A push that frees nothing is still made if it cuts the table's shortfall of
# room by this much, so the next look starts from a looser table.
LEAST_EASING = 0.010

HEADINGS = 72
STEP = 0.002
LONGEST_PUSH = 0.15


def slides(glass: Seen) -> str:
    """Whether a push at the jaw's top edge slides this glass: "yes", "no" or "try".

    It slides while the push is lower than a / mu: half the foot, over the
    friction. The top edge, because a glass wider higher up meets the jaw
    there first. "try" means it depends on the friction, and a probe is safe.
    """
    half_foot = glass.foot / 2
    if half_foot / MU_HIGHEST > JAW_TOP:
        return "yes"
    if half_foot / MU_LOWEST <= JAW_TOP:
        return "no"
    falls_past = math.atan2(half_foot, CENTRE_OF_MASS_SHARE * glass.height)
    return "try" if math.atan2(PROBE, JAW_TOP) < PROBE_LEAN_SHARE * falls_past else "no"


def room(glass: Seen, seen: list[Seen], margin: float = 0.0) -> bool:
    return has_room(glass.x, glass.y, [(o.x, o.y, o.widest) for o in seen if o.id != glass.id], margin)


def reachable(point: np.ndarray) -> bool:
    return COMFORTABLE_REACH[0] <= float(np.linalg.norm(point - ROBOT_BASE[:2])) <= COMFORTABLE_REACH[1]


def segment_distance(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """How close a line from a to b comes to a point."""
    along = b - a
    t = float(np.clip((point - a) @ along / max(along @ along, 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(point - (a + t * along)))


def shortfall(layout: list[tuple[float, float, float]]) -> float:
    """How much room the table is short of, summed over its glasses, metres.

    ``layout`` is (x, y, widest width) per glass. A glass short of room by
    20 mm from its worst neighbour adds 20 mm. Zero means every glass can be
    gripped.
    """
    total = 0.0
    for i, (x, y, _) in enumerate(layout):
        worst = max(
            (
                GRIP_ROOM + w / 2 - math.dist((x, y), (ox, oy))
                for j, (ox, oy, w) in enumerate(layout)
                if j != i
            ),
            default=0.0,
        )
        total += max(0.0, worst)
    return total


def along(glass: Seen, others: list[Seen], heading: float) -> list[Push]:
    """Every safe push of ``glass`` along ``heading``, shortest first, up to the first that frees it.

    Every clash found at one length is still there at any longer one, so the
    first clash ends the list.
    """
    u = np.array([math.cos(heading), math.sin(heading)])
    middle = np.array([glass.x, glass.y])
    radius = glass.widest / 2
    start = middle - (radius + APPROACH_GAP) * u
    wrist = start - TOOL_LENGTH * u
    # The reach is the flange's, and the flange is behind the fingertips.
    if not (reachable(start - FINGERTIP_OFFSET * u) and reachable(middle - FINGERTIP_OFFSET * u)):
        return []

    safe = []
    for travel in np.arange(STEP, LONGEST_PUSH + 1e-9, STEP):
        # The tip never goes past where the glass's middle lands, so the jaw
        # is checked as if it did.
        end = middle + travel * u
        if not (in_zone(*end) and reachable(end - FINGERTIP_OFFSET * u)):
            break
        clash = False
        for other in others:
            centre, other_radius = np.array([other.x, other.y]), other.widest / 2
            # A glass may start closer to a neighbour than CLEARANCE. Moving
            # it is fine as long as it gets no closer.
            passing = min(radius + other_radius + CLEARANCE, float(np.linalg.norm(centre - middle)) - 0.001)
            if (
                segment_distance(centre, middle, end) < passing
                or segment_distance(centre, start - FINGER_LENGTH * u, end)
                < JAW_THICKNESS / 2 + other_radius + CLEARANCE
                or segment_distance(centre, wrist, end - FINGER_LENGTH * u)
                < BODY_SIZE / 2 + other_radius + CLEARANCE
            ):
                clash = True
                break
        if clash:
            break
        safe.append(
            Push(
                glass=glass.id,
                start=(float(start[0]), float(start[1])),
                heading=heading,
                reach=radius + APPROACH_GAP + FEEL_BEYOND,
                travel=float(travel),
                aim=(float(end[0]), float(end[1])),
            )
        )
        if has_room(*end, [(o.x, o.y, o.widest) for o in others], AIM_MARGIN):
            break
    return safe


def choose(seen: list[Seen], skip: set[int]) -> tuple[Push | None, dict[int, str]]:
    """The push to make next, and why the glasses with no safe push have none.

    First choice: the shortest safe push that gives a glass room. Failing
    that, the safe push that most cuts the table's shortfall, so the next
    look starts from a looser table. ``skip`` is glasses not to push again.
    """
    freeing, easing, why = [], [], {}
    before = shortfall([(g.x, g.y, g.widest) for g in seen])
    for glass in seen:
        if glass.id in skip:
            continue
        if slides(glass) == "no":
            why[glass.id] = "tips before it slides"
            continue
        others = [o for o in seen if o.id != glass.id]
        layout = [(o.x, o.y, o.widest) for o in others]
        pushes = [p for h in np.arange(HEADINGS) * (2 * math.pi / HEADINGS) for p in along(glass, others, h)]
        for push in pushes:
            if has_room(*push.aim, layout, AIM_MARGIN):
                freeing.append(push)
            else:
                eased = before - shortfall([*layout, (*push.aim, glass.widest)])
                if eased >= LEAST_EASING:
                    easing.append((eased, -push.travel, push))
        if not pushes:
            why[glass.id] = "nowhere clear to push it to"
    if freeing:
        return min(freeing, key=lambda p: p.travel), why
    if easing:
        return max(easing, key=lambda e: e[:2])[2], why
    for glass in seen:
        if glass.id not in skip and glass.id not in why:
            why[glass.id] = "nowhere clear to push it to"
    return None, why


def probe(push: Push) -> Push:
    """The same push, cut down to PROBE."""
    u = np.array([math.cos(push.heading), math.sin(push.heading)])
    middle = np.array(push.aim) - push.travel * u
    aim = middle + PROBE * u
    return Push(push.glass, push.start, push.heading, push.reach, PROBE, (float(aim[0]), float(aim[1])))


def needs_probe(glass: Seen, proven: set[int]) -> bool:
    return slides(glass) == "try" and glass.id not in proven
