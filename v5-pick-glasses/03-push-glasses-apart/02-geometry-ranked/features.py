"""The eight numbers the ranker is shown about a candidate push.

Every one of them is a length, an angle, a count or a ratio. None of them is
an address on the table, and that is the point: slide the whole arrangement
across the glass zone or turn it round, and every number below is unchanged,
so the model cannot tell the two arrangements apart and must score them the
same. A model given x and y would instead learn where this bench's crowds
happen to form, which is a fact about the bench and not about pushing.

The two that look positional are not. The distance to the edge of the glass
zone and the distance to the rack are distances to fixed features of the cell,
which is a relation: a destination 15 mm from a boundary has 15 mm of margin
wherever that boundary is.

``NAMES`` and ``row`` are the one place the list lives. Nothing else in this
folder decides what an input is.
"""

from __future__ import annotations

import math

import numpy as np
from candidates import nudge
from work_cell.arm.dimensions import GRIPPER_MAX_OPENING
from work_cell.rack.layout import RACK_AREA, SLOT_COUNT, SLOT_SPACING

from bench import GLASS_ZONE, GRIP_ROOM, JAW_TOP, Push, Seen

NAMES = (
    "contact angle, from the line to the nearest edge",
    "push distance",
    "room at the destination",
    "destination to the zone edge",
    "destination to the rack",
    "neighbours within reach",
    "foot width",
    "push height over the topple limit",
)
INPUTS = len(NAMES)

# How far out a neighbour's middle can be and still deny this glass the room
# the jaw needs. Nothing wider than the gripper's opening is ever drawn, so a
# neighbour beyond this cannot reach into that room however wide it is.
CROWD_RADIUS = GRIP_ROOM + GRIPPER_MAX_OPENING / 2

# The table the rack can stand on. Its row of slots runs across the arm from
# the marker in the middle of RACK_AREA, so the area it may occupy is that
# area grown by half a row either way. Read from the rack's own layout rather
# than written down, because moving the rack has to move this with it.
RACK_HALF_ROW = (SLOT_COUNT - 1) / 2 * SLOT_SPACING
RACK_BOX = (RACK_AREA[0], RACK_AREA[1], RACK_AREA[2] - RACK_HALF_ROW, RACK_AREA[3] + RACK_HALF_ROW)


def row(glass: Seen, others: list[Seen], push: Push) -> np.ndarray:
    """The eight inputs for one candidate push of ``glass``, in metres and radians.

    Nothing is rescaled. A tree compares one input against one threshold and
    never sums two of them, so the scale of each is a private matter.
    """
    return np.array(
        [
            contact_angle(glass, others, push.heading),
            push.travel,
            room_at(push.aim, others),
            zone_edge_distance(*push.aim),
            rack_distance(*push.aim),
            float(neighbours_within(glass, others)),
            glass.foot,
            topple_ratio(glass.foot),
        ],
        dtype=np.float64,
    )


def rows(seen: list[Seen], candidates: list) -> np.ndarray:
    """One row per candidate, in the order given."""
    others = {g.id: [o for o in seen if o.id != g.id] for g in seen}
    if not candidates:
        return np.zeros((0, INPUTS))
    return np.stack([row(c.glass, others[c.glass.id], c.push) for c in candidates])


def contact_angle(glass: Seen, others: list[Seen], heading: float) -> float:
    """How far the push points away from the nearest neighbour's edge, radians.

    Zero is straight into that neighbour and pi is straight away from it, so
    "pushing away from the crowd" is one value of one input wherever on the
    table the crowd is. Unsigned, because a push to the neighbour's left and
    the mirror of it to its right are the same push as far as the table is
    concerned.
    """
    near = nearest(glass, others)
    if near is None:
        return math.pi
    bearing = math.atan2(near.y - glass.y, near.x - glass.x)
    return abs(math.remainder(heading - bearing, 2 * math.pi))


def nearest(glass: Seen, others: list[Seen]) -> Seen | None:
    """The neighbour whose edge comes closest, which is what the room test measures to."""
    return min(
        others,
        key=lambda o: math.dist((o.x, o.y), (glass.x, glass.y)) - o.widest / 2,
        default=None,
    )


def room_at(point: tuple[float, float], others: list[Seen]) -> float:
    """How much more than the room it needs a glass at ``point`` would have, metres.

    Negative means still crowded. Every clearance is recomputed with the glass
    moved to where the push would put it.
    """
    # A glass alone on the table has room by any measure, and is taken rather
    # than pushed, so the enumerator never offers a candidate for one.
    return min((math.dist(point, (o.x, o.y)) - o.widest / 2 - GRIP_ROOM for o in others), default=0.0)


def zone_edge_distance(x: float, y: float) -> float:
    """How far a point inside the glass zone is from leaving it, metres."""
    x_min, x_max, y_min, y_max = GLASS_ZONE
    return min(x - x_min, x_max - x, y - y_min, y_max - y)


def rack_distance(x: float, y: float) -> float:
    return _box_distance(x, y, RACK_BOX)


def neighbours_within(glass: Seen, others: list[Seen]) -> int:
    """How many other glasses stand close enough to be in the way. The crowd, as a count."""
    return sum(math.dist((o.x, o.y), (glass.x, glass.y)) <= CROWD_RADIUS for o in others)


def topple_ratio(foot: float) -> float:
    """The jaw's top edge over the topple limit for this foot, at the worst friction believed.

    One means the push is exactly at the limit. The height is fixed, so this
    varies only with the glass, and it is the input through which the model can
    prefer pushes that stand further from a limit computed from a friction
    nobody measured.
    """
    return JAW_TOP / (foot / 2 / nudge.MU_HIGHEST)


def _box_distance(x: float, y: float, box: tuple[float, float, float, float]) -> float:
    x_min, x_max, y_min, y_max = box
    return math.hypot(max(x_min - x, 0.0, x - x_max), max(y_min - y, 0.0, y - y_max))
