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

**Three more numbers say what the solution knows about itself, and nine more
say what it has decided to do.** Both were added after the first held-out walk,
and the reason is the same for each.

The first three are *memory*. A solution that is shown one picture at a time
cannot tell "I have just arrived at this table" from "I have been round the
whole of it and there is nothing to do", and the measured consequence was that
the fitted policy declared nine of its ten tables finished while they were
still crowded. So it now carries three facts about its own behaviour: how many
answers it has given on this table, how many of them since it last touched a
glass, and how far the jaw has travelled since then. None of them is a fact
about the glasses, and all of them are facts the solution can keep for itself.

The nine are the *decision*. Four say which of the four kinds of answer this
is, as a one-hot, and five describe the glass the answer is aimed at. They are
there because eighty-one per cent of the teacher's answers are moves to see
from somewhere else, and a network fitted to minimise the distance to the
teacher's answer produces the average of the two kinds, which is a look. Told
which kind of answer to draw, and which glass to draw it at, it has only one
thing left to learn. ``gate.py`` is the model that makes that decision, and it
is fitted on the teacher's own choices.

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

# The four kinds of answer, which are the teacher's own five grouped into the
# ones that need telling apart. ``drive`` and ``stay`` are both looks, because
# the difference between them is only whether the jaw has to move to see what is
# wanted. ``ranging`` and ``testing`` are both probes: a five-millimetre shove
# made to find something out. ``pushing`` is a push at the task. ``done`` is the
# teacher saying the table needs nothing more, which is not a path at all.
#
# A probe and a push are kept apart because they are different lengths of the
# same motion, and a model told only "push" would draw the average of the two
# and make a shove too short to free a glass and too long to be a test.
KINDS = ("look", "probe", "push", "done")
LOOK, PROBE, PUSH, DONE = range(len(KINDS))

# Which of the teacher's own words means which kind.
AS_KIND = {"drive": LOOK, "stay": LOOK, "ranging": PROBE, "testing": PROBE, "pushing": PUSH}

# How many answers and how many metres the three numbers about itself are
# divided by, so that they sit near one like everything else. The teacher's
# longest spell of answers on one table is about forty and it rarely travels
# more than a couple of metres between pushes, so these are units rather than
# limits: a solution that goes further simply reports a number above one.
ANSWER_SCALE = 20.0
TRAVEL_SCALE = 2.0

# What a slot number means when an answer is aimed at no glass. One past the
# last slot, and the same number whatever the table holds: a look at a table of
# three glasses and a look at a table of five have to mean the same thing to the
# gate, so this cannot be "however many glasses are in the picture".
NO_GLASS = GLASSES

# What the solution knows about itself: answers on this table, answers since it
# last touched a glass, and metres travelled since then.
SELF_WIDTH = 3
# The glass an answer is aimed at: across, along, widest, height, foot. Zero
# throughout when the answer is aimed at no glass, which a look and a done are.
TARGET_WIDTH = 5
CONDITION_WIDTH = len(KINDS) + TARGET_WIDTH

# What the gate is shown, and what the chunked policy is shown. The gate decides
# the kind and the glass, so it cannot be shown either.
GATE_WIDTH = STATE_WIDTH + SELF_WIDTH
ASKED_WIDTH = GATE_WIDTH + CONDITION_WIDTH


def in_slots(seen: Sequence[Seen]) -> list[Seen]:
    """The glasses in the order the slots hold them, which is what a slot number means.

    One function rather than the same ``sorted`` written in three places, because
    the gate names a glass by its slot and the policy is told that glass's
    numbers; if the two orders ever differed they would mean different glasses.
    """
    return sorted(seen, key=lambda glass: (glass.x, glass.y))


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
    for slot, glass in enumerate(in_slots(seen)):
        at = JAW_WIDTH + slot * PER_GLASS
        row[at] = (glass.x - TABLE_CENTRE_XY[0]) / PLACE_SCALE
        row[at + 1] = (glass.y - TABLE_CENTRE_XY[1]) / PLACE_SCALE
        row[at + 2] = glass.widest / PLACE_SCALE
        row[at + 3] = glass.height / PLACE_SCALE
        row[at + 4] = glass.foot / PLACE_SCALE
        row[at + 5] = 1.0
    return row


def about_itself(answers: int, since_touch: int, travelled: float) -> np.ndarray:
    """The three numbers a solution keeps about its own behaviour on this table.

    Not a belief about the table: a solution that has given twenty answers
    without touching a glass has looked around, and that is a fact about itself.
    It is what lets a model say "done" for a reason rather than because nothing
    crowded happens to be in the current picture.
    """
    return np.array(
        [answers / ANSWER_SCALE, since_touch / ANSWER_SCALE, travelled / TRAVEL_SCALE],
        dtype=np.float32,
    )


def conditioning(kind: int, target: Seen | None) -> np.ndarray:
    """Which kind of answer to draw, and the glass to draw it at.

    The glass's numbers are given as well as its slot being named, because the
    policy writes its path in that glass's own frame and the frame is the glass.
    A look and a done are aimed at nothing, so the five numbers are zero and the
    one-hot is all the policy is told.
    """
    row = np.zeros(CONDITION_WIDTH, dtype=np.float32)
    row[kind] = 1.0
    if target is not None:
        at = len(KINDS)
        row[at] = (target.x - TABLE_CENTRE_XY[0]) / PLACE_SCALE
        row[at + 1] = (target.y - TABLE_CENTRE_XY[1]) / PLACE_SCALE
        row[at + 2] = target.widest / PLACE_SCALE
        row[at + 3] = target.height / PLACE_SCALE
        row[at + 4] = target.foot / PLACE_SCALE
    return row


def to_gate(state: np.ndarray, itself: np.ndarray) -> np.ndarray:
    """What the gate is shown: the table as measured, and the solution's own history."""
    return np.concatenate([state, itself]).astype(np.float32)


def to_asked(state: np.ndarray, itself: np.ndarray, condition: np.ndarray) -> np.ndarray:
    """What the chunked policy is shown: the gate's input, and the decision taken."""
    return np.concatenate([state, itself, condition]).astype(np.float32)
