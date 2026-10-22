"""The camera's readings of the table, as a fixed row of numbers the model can take.

This solution began by showing the policy a picture and nothing else. That is
the purest form of behaviour cloning, but it turned out to cost more than it
was worth, and ``measure_frames.py`` is what showed why. The teacher always
brings the jaw down on the line through the glass it means to push, a
near-constant 46 mm behind that glass's measured middle. So in the push's own
frame the descent point barely varies at all, while written as a position on
the table it varies by 135.8 mm. A policy given only the picture has to
recover each glass's position from pixels before it can place anything, and it
recovers it about 50 mm out, which is the size of the gaps it is threading.

The examiner already measures those positions and hands them to every solution
through ``look()``. Solutions 1, 2 and 4 all read them. So the repair is not to
make the policy better at seeing, but to stop asking it to see something it is
given: the readings go in beside the picture, and the policy is left to decide
what to do with them.

**The problem this module solves is shape.** A table holds four to six glasses,
while a network's input is a fixed width, so a variable number of glasses has
to become a fixed row. The answer here is the one [solution
4](../04-a-world-model/features.py) already uses: a fixed number of slots, each
holding one glass, with a flag saying whether the slot is used. An unused slot
is zero throughout, and the flag is what tells the model that its zeros mean
"nothing here" rather than "a glass at the origin".

**The order of the slots has to be decided, because a network is not
permutation invariant.** The same table handed over in two orders would be two
different inputs, and the model would have to learn that they mean the same
thing. The glasses are therefore sorted by position, across the table and then
along it, which is deterministic and is recoverable from the picture, so the
ordering agrees with what the model sees.
"""

from __future__ import annotations

import numpy as np
from work_cell.table.layout import TABLE_CENTRE_XY

from bench import Seen

# Slots for glasses. Six is the most a table holds, so six is everyone.
GLASSES = 6
# Per slot: across, along, widest, height, foot, and whether the slot is used.
PER_GLASS = 6
STATE_WIDTH = GLASSES * PER_GLASS

# Distances are divided by this so that they sit near one, which is where a
# network wants its inputs. It is a unit for scaling and not a measurement of
# any glass; it is solution 4's own constant, and sharing it means the two
# solutions describe a table on the same scale.
PLACE_SCALE = 0.10


def to_state(seen: list[Seen]) -> np.ndarray:
    """One look at the table as ``STATE_WIDTH`` numbers.

    Positions are measured from the middle of the table rather than from the
    cell's origin, because the middle is the only point in the frame the model
    can see, and an input that counts from somewhere off the picture would make
    the model learn the offset before it could use the number.
    """
    if len(seen) > GLASSES:
        raise ValueError(f"a table holds at most {GLASSES} glasses, not {len(seen)}")
    row = np.zeros(STATE_WIDTH, dtype=np.float32)
    for slot, glass in enumerate(sorted(seen, key=lambda g: (g.x, g.y))):
        at = slot * PER_GLASS
        row[at] = (glass.x - TABLE_CENTRE_XY[0]) / PLACE_SCALE
        row[at + 1] = (glass.y - TABLE_CENTRE_XY[1]) / PLACE_SCALE
        row[at + 2] = glass.widest / PLACE_SCALE
        row[at + 3] = glass.height / PLACE_SCALE
        row[at + 4] = glass.foot / PLACE_SCALE
        row[at + 5] = 1.0
    return row


def empty(count: int = 1) -> np.ndarray:
    """A batch of looks at nothing, for a model fitted without the readings."""
    return np.zeros((count, 0), dtype=np.float32)
