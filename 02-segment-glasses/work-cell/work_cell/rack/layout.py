"""The drying rack, and how much room a glass needs in it.

The rack has six slots in a row. Its own measurements are fixed and known — it
is one object that does not change — but where it is standing on the table is
not, so every slot position is worked out at run time from a marker on the rack
base rather than written down here.

The interesting part of this file is the tilt budget. A glass going into a slot
has a few millimetres of room on each side, and that room is used up by tilt far
faster than by sideways error, because a glass is tall. Working out how much
tilt a particular glass can afford is what decides whether the slot beside it
has to be left empty — and since that depends on the glass's measured width and
height, it cannot be decided in advance.

Plain numpy, no ROS, so the whole module can be tested directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from ..table.layout import ROBOT_BASE, TABLE_TOP_Z

# Where the table top is and where the arm is bolted down both come from
# table/layout.py, which is the one place the cell's own measurements live.
# They are re-exported here because everything about the rack is measured from
# them.
__all__ = [
    "ARM_TILT_ACCURACY_DEG",
    "GLASS_ZONE",
    "MARKER_DICTIONARY",
    "MARKER_ID",
    "MARKER_SIZE",
    "PEG_HEIGHT",
    "PEG_RADIUS",
    "RACK_AREA",
    "RACK_BASE_HEIGHT",
    "RACK_TOP_Z",
    "ROBOT_BASE",
    "SLOT_COUNT",
    "SLOT_SPACING",
    "TABLE_TOP_Z",
    "Slot",
    "fill_order",
    "landing_point",
    "needs_empty_neighbour",
    "slots_consumed",
    "slots_within_stretch",
    "rack_box",
    "slots_from_marker",
    "tilt_budget_deg",
    "usable_slots",
]

# The rack's own measurements. Six slots in a row.
SLOT_COUNT = 6
SLOT_SPACING = 0.100
RACK_BASE_HEIGHT = 0.020

# The rack stands on the table, so its top is where a rim comes to rest.
RACK_TOP_Z = TABLE_TOP_Z + RACK_BASE_HEIGHT

# The pegs a glass is stood over, one in the middle of each slot. They only
# have to keep a glass from sliding sideways, not hold it up. A glass has to
# arrive with its rim above the tops of these, or it is carried sideways into
# one.
#
# The height is a trade against the glasses. Upside down, a glass goes over its
# peg, so the peg must end below the glass's solid base and inside the part of
# a wine glass's bowl that is still wide. At this height that rules out the
# shortest shot glasses and the smallest wine glasses, so shapes.py does not
# draw them.
PEG_HEIGHT = 0.055
PEG_RADIUS = 0.008

# The marker printed on the middle of the base. It belongs to the rack rather
# than to the camera: the rack carries it, and the camera reads whatever the
# rack carries. A 4x4 dictionary is the coarsest ArUco family, which is what to
# use when there is only one marker to tell apart from nothing, because bigger
# squares read reliably from further away.
MARKER_DICTIONARY = cv2.aruco.DICT_4X4_50
MARKER_ID = 0
# Sized by what the camera can resolve and what the rack has room for. A 4x4
# marker is six cells across counting its border, and the detector needs
# several pixels per cell, so a small marker is simply invisible from survey
# height. The limit the other way is the pegs either side of the middle: the
# marker has to stay clear of them, and of the shadow they cast across it when
# the rack is off to one side of the picture.
MARKER_SIZE = 0.070

# Where the glasses start out, as a rectangle on the table: x from, x to,
# y from, y to.
#
# Every corner of it is inside the band of reach the arm works well over —
# `COMFORTABLE_REACH` in arm/dimensions.py — and `test_dimensions.py` holds
# the two to that. The rectangle used to run out to 825 mm from the base at
# its far corner, past what the arm can reach at all, so a glass drawn there
# was refused however well it had been measured. A glass the arm cannot get to
# teaches nothing about picking glasses up.
#
# The far corner is the one that binds: a rectangle is a clumsy shape to cut
# out of an annulus, and squaring it off costs some table. It is kept as a
# rectangle because that is what is easy to read, to draw and to argue about.
# As drawn the corners stand 330 to 777 mm from the base, against a band that
# ends at 780, so it is as much table as the reach allows. Six glasses still
# lay out without crowding on all of the first two hundred seeds; much smaller
# and they stop fitting.
#
# All of it is on the arm's right, because the rack stands on its left. The two
# never share a stretch of table, which is what keeps the rack out of the back
# of a survey picture and makes it obvious, watching the run, which side the
# arm is working on.
GLASS_ZONE = (0.32, 0.64, -0.44, -0.08)

# Where the middle of the rack may stand, as x from, x to, y from, y to. The arm
# is not told where in here it is; it looks down on the middle of this area
# and reads the marker.
#
# Straight down on the middle, because the pegs stand either side of the
# marker. Seen from off to one side, a peg's top appears shifted away from the
# camera, and a tall peg on the near side then covers the marker's border,
# which is all the detector reads.
#
# The row is 580 mm long, so the middle may only wander about 30 mm before one
# end or the other leaves COMFORTABLE_REACH.
RACK_AREA = (0.32, 0.38, 0.34, 0.38)

# How much tilt the arm can be relied on to hold during the descent. A slot
# that would demand better than this from a particular glass is a slot that
# glass may not use on its own.
ARM_TILT_ACCURACY_DEG = 3.0


@dataclass(frozen=True)
class Slot:
    """One place in the rack a glass can be stood, mouth down."""

    index: int
    centre: np.ndarray

    def __post_init__(self) -> None:
        object.__setattr__(self, "centre", np.asarray(self.centre, dtype=float))


def slots_within_stretch(
    slots: list[Slot], base: np.ndarray, reach: tuple[float, float], tool_offset: float
) -> list[Slot]:
    """The slots the arm can stand over whichever way round it is holding the glass.

    Standing a glass in a slot puts the tool a grasp's depth to one side
    of the slot, and which side is settled long before — by how the glass was
    picked up and which way it was turned. So a slot is only safe to promise
    if the arm can reach it from either side, which rules out the far end of
    the row and the near end alike.

    An empty answer is a real answer and the caller may ignore it: better to
    try a slot that may not work than to refuse a glass already in hand.
    """
    low, high = reach
    keep = []
    for slot in slots:
        out = float(np.linalg.norm((slot.centre - base)[:2]))
        if low + tool_offset <= out <= high - tool_offset:
            keep.append(slot)
    return keep


def rack_box(slots: list[Slot]) -> tuple[np.ndarray, tuple[float, float, float], np.ndarray]:
    """One box around the whole rack: where it is, how big, and which way round.

    Which way round is the part that matters. The rack stands square to the
    table but not square to the world — its row of slots runs across the arm,
    not along x — and a box built from the slots' extent without turning it to
    match is a box at right angles to the rack it is standing in for. That
    leaves the real rack unprotected and puts a six hundred millimetre slab
    across open table, where the arm meets it as a collision it cannot explain.

    Returned as position, size and orientation rather than built here, because
    this file may not import ROS and a collision object is a ROS message.
    """
    centre = np.mean([slot.centre for slot in slots], axis=0)
    along = np.asarray(slots[-1].centre - slots[0].centre, dtype=float)
    length = float(np.linalg.norm(along))

    # A rack of one slot has no direction of its own; square to the world will
    # do, since the box is then as wide as it is long.
    if length <= 0.0:
        return centre, (SLOT_SPACING, SLOT_SPACING, RACK_BASE_HEIGHT), np.eye(3)

    across = along / length
    up = np.array([0.0, 0.0, 1.0])
    return (
        centre,
        (SLOT_SPACING, length + SLOT_SPACING, RACK_BASE_HEIGHT),
        np.column_stack((np.cross(across, up), across, up)),
    )


def slots_from_marker(marker_position: np.ndarray, marker_yaw: float) -> list[Slot]:
    """Where every slot is, given where the marker on the rack was seen.

    The rack is known and its position is not, so one measurement of the marker
    places all six. Nothing here may be a constant in the code: move the rack
    and the answer has to move with it.
    """
    marker_position = np.asarray(marker_position, dtype=float)
    across = np.array([-math.sin(marker_yaw), math.cos(marker_yaw), 0.0])

    # The marker sits at the middle of the rack base, so the slots run half a
    # rack's width either side of it.
    first = -(SLOT_COUNT - 1) / 2.0
    return [
        Slot(index, marker_position + across * (first + index) * SLOT_SPACING)
        for index in range(SLOT_COUNT)
    ]


def tilt_budget_deg(glass_width: float, glass_height: float, spacing: float = SLOT_SPACING) -> float:
    """How far a glass may lean while going into a slot, in degrees.

    The clearance on each side is half of whatever the slot spacing leaves
    over, and the glass pivots about its rim as it goes down, so the angle that
    uses up that clearance is atan(clearance / height).

    A glass 80 mm across in slots 100 mm apart has 10 mm a side. At 90 mm tall
    that is 6.3 degrees, which is comfortable. Make the same glass 175 mm tall
    and it is 3.3 degrees. Widen it to 90 mm as well and it is 1.6 degrees,
    which no arm should be asked for.
    """
    if glass_height <= 0:
        raise ValueError("a glass must have some height")
    clearance = (spacing - glass_width) / 2.0
    if clearance <= 0:
        return 0.0
    return math.degrees(math.atan(clearance / glass_height))


def needs_empty_neighbour(
    glass_width: float, glass_height: float, *, spacing: float = SLOT_SPACING
) -> bool:
    """Whether this glass has to have the slot beside it left empty.

    Leaving a gap doubles the spacing, which turns an impossible tilt budget
    into an easy one: the 90 mm glass above goes from 1.6 degrees to 17.4.
    """
    return tilt_budget_deg(glass_width, glass_height, spacing) < ARM_TILT_ACCURACY_DEG


def usable_slots(free: list[Slot], *, needs_gap: bool) -> list[Slot]:
    """Which of the free slots this glass could actually go into.

    A glass needing a gap can only use a slot whose neighbours are also free,
    because placing it consumes them too.
    """
    if not needs_gap:
        return list(free)
    free_indices = {slot.index for slot in free}
    return [
        slot
        for slot in free
        if (slot.index - 1) not in _occupied(free_indices)
        and (slot.index + 1) not in _occupied(free_indices)
    ]


def _occupied(free_indices: set[int]) -> set[int]:
    """The slot numbers that are not free."""
    return set(range(SLOT_COUNT)) - free_indices


def slots_consumed(slot: Slot, *, needs_gap: bool) -> set[int]:
    """Which slot numbers are used up by putting a glass in ``slot``."""
    if not needs_gap:
        return {slot.index}
    return {slot.index - 1, slot.index, slot.index + 1} & set(range(SLOT_COUNT))


def landing_point(slot: Slot) -> np.ndarray:
    """Where the rim of a glass comes to rest in ``slot``: on the rack's top.

    A slot's centre is placed from the marker and carries the marker's height,
    which is not the height of the rack top. The rack stands on the known
    table, so its top is known and is used instead.
    """
    return np.array([slot.centre[0], slot.centre[1], RACK_TOP_Z])


def fill_order(slots: list[Slot], reach_from: np.ndarray = ROBOT_BASE) -> list[Slot]:
    """The order to fill slots in: furthest from the arm first.

    Working outward from the far end means a glass already standing in the rack
    is never between the arm and the next slot, so the arm never has to reach
    over one glass to place another.
    """
    reach_from = np.asarray(reach_from, dtype=float)
    return sorted(slots, key=lambda slot: -float(np.linalg.norm(slot.centre - reach_from)))
