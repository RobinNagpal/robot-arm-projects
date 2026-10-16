"""The observation: the picture from the arm's camera, what it caught, and where the jaw is.

Problem 4 hands a solution three things in every ``Look``, and a model is shown
all three. The picture is the one the camera on the wrist rendered. This module
is the other two, turned into the fixed row of numbers a network takes.

**The jaw's pose has to go in, and in problem 3 it did not.** Problem 3's camera
is bolted above the table and its jaw is parked in the same place between
pushes, so solution 3 there could pass a state of width zero and lose nothing.
Here the camera moves with the jaw, so the same table photographed from two
stands is two different pictures, and nothing in the picture says which stand it
was taken from. Without the pose the model cannot place anything it sees on the
table, and cannot write a path in the table's own numbers.

**The glasses the picture caught go in as slots.** A table holds three to five
glasses and the camera catches some of them, while a network's input is a fixed
width. The answer is problem 3's and problem 4's solution 4's: a fixed number of
slots, each holding one glass, with a flag saying whether the slot is used. An
unused slot is zero throughout, and the flag is what tells the model that its
zeros mean "nothing here" rather than "a glass at the origin".

**The slots are sorted, because a network is not permutation invariant.** The
same table handed over in two orders would be two different inputs. Sorting by
position across the table and then along it is deterministic, and it is
recoverable from the picture, so the ordering agrees with what the model sees.

No glass's size is written down here. Every number in a slot was measured by
the arm during the run, and ``PLACE_SCALE`` is a unit for putting metres near
one, which is where a network wants its inputs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from work_cell.table.layout import TABLE_CENTRE_XY

import tables
from partners import Seen, Waypoint

# The one line the task is described by, for the policies that take a sentence.
# Problem 4's version says the looking out loud, because here it is half the job.
INSTRUCTION = "look round the table and push the glasses apart"

# What the picture is called in the dataset. Named for where the camera is, which
# is the whole difference between this problem and problem 3.
CAMERA = "observation.images.wrist"

# Slots for glasses. The most the draw puts on a table, read from the draw
# rather than written down, so that a wider draw widens the slots with it.
GLASSES = tables.MOST
# Per slot: across, along, widest, height, foot, and whether the slot is used.
PER_GLASS = 6
# The jaw: across, along, up, and its heading as a cosine and a sine.
JAW_WIDTH = 5
STATE_WIDTH = JAW_WIDTH + GLASSES * PER_GLASS

# Distances are divided by this so that they sit near one. It is a unit for
# scaling and not a measurement of any glass; problem 3's solution 3 and problem
# 4's solution 4 use the same figure, so every model in the project describes a
# table on one scale.
PLACE_SCALE = 0.10


def to_state(jaw: Waypoint, seen: Sequence[Seen]) -> np.ndarray:
    """One ``Look``'s numbers as ``STATE_WIDTH`` floats.

    Positions are measured from the middle of the table rather than from the
    cell's origin, because the middle is a point the model can see and a number
    counted from somewhere off the picture would make it learn the offset first.
    """
    if len(seen) > GLASSES:
        raise ValueError(f"the draw puts at most {GLASSES} glasses on a table, not {len(seen)}")
    row = np.zeros(STATE_WIDTH, dtype=np.float32)
    row[0] = (jaw.x - TABLE_CENTRE_XY[0]) / PLACE_SCALE
    row[1] = (jaw.y - TABLE_CENTRE_XY[1]) / PLACE_SCALE
    row[2] = jaw.z / PLACE_SCALE
    row[3] = math.cos(jaw.heading)
    row[4] = math.sin(jaw.heading)
    for slot, glass in enumerate(sorted(seen, key=lambda g: (g.x, g.y))):
        at = JAW_WIDTH + slot * PER_GLASS
        row[at] = (glass.x - TABLE_CENTRE_XY[0]) / PLACE_SCALE
        row[at + 1] = (glass.y - TABLE_CENTRE_XY[1]) / PLACE_SCALE
        row[at + 2] = glass.widest / PLACE_SCALE
        row[at + 3] = glass.height / PLACE_SCALE
        row[at + 4] = glass.foot / PLACE_SCALE
        row[at + 5] = 1.0
    return row
