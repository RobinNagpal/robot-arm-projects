"""Make one candidate push on the bench and write down what it did.

This is the label, and it costs nothing to collect: the bench measures the
table after every push in any case. It has two parts, as the document asks.
The first is how much clear room the whole table gained, so that a push which
frees one glass by crowding another is not paid for half of its effect. The
second is whether anything toppled, which makes a push the worst candidate
there is.

The label is read from the simulator's own record, which the bench allows as
a training label on training tables and nowhere else. Nothing that decides a
push at run time reads it: the eight inputs come from ``look()``, carrying the
camera's error, exactly as they will when the arm is working. The camera's own
reading of the same outcome is kept beside the label, because the difference
between the two is how much of a group's spread a run could even perceive.

Candidates are tried from a saved state rather than on a rebuilt table. The
table is the same table either way, and restoring it is thousands of times
cheaper than building it, which is what makes a few thousand labelled pushes
a matter of minutes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import mujoco
import numpy as np
from candidates import Candidate, nudge

from bench import STANDING_TILT_DEG, Bench, Felt, Seen

# The label for a push that toppled a glass: worse than any push can be good,
# so it sorts below every push that did not. Nothing in this project stands a
# glass back up.
TOPPLED = -1.0


@dataclass(frozen=True)
class Before:
    """One table, held still, so that every candidate starts from it."""

    seen: list[Seen]  # what the camera reports, which is all the arm has
    layout: list[tuple[float, float, float]]  # the simulator's record, for the label only
    saved: tuple[np.ndarray, np.ndarray] = field(repr=False)


@dataclass(frozen=True)
class Rolled:
    """One candidate, made for real."""

    label: float  # metres of room gained, or TOPPLED
    gained: float  # metres of room gained, whatever happened
    seen_gained: float  # the same, as the camera measured it
    toppled: bool
    felt: Felt
    after: list[Seen]


def capture(table: Bench) -> Before:
    """Hold the table as it stands, ready for one candidate after another."""
    return Before(table.look(), truth(table), (table.data.qpos.copy(), table.data.qvel.copy()))


def restore(table: Bench, before: Before) -> None:
    table.data.qpos[:] = before.saved[0]
    table.data.qvel[:] = before.saved[1]
    mujoco.mj_forward(table.model, table.data)


def roll(table: Bench, before: Before, candidate: Candidate) -> Rolled:
    """Put the table back as it was, make the push, and measure what it did."""
    restore(table, before)
    felt = table.push(candidate.push)
    after = table.look()
    gained = nudge.shortfall(before.layout) - nudge.shortfall(truth(table))
    fell = any(table.tilt(i) >= STANDING_TILT_DEG for i in table.on_table())
    return Rolled(
        label=TOPPLED if fell else gained,
        gained=gained,
        seen_gained=room_gained(before.seen, after),
        toppled=fell,
        felt=felt,
        after=after,
    )


def truth(table: Bench) -> list[tuple[float, float, float]]:
    """Where every glass still on the table really is, and how wide it really is."""
    return [(*table.position(i), table.glasses[i].outline.max_diameter) for i in table.on_table()]


def room_gained(before: list[Seen], after: list[Seen]) -> float:
    """How much of the table's shortfall of room the push removed, metres, as the camera sees it.

    Over the whole table, not over the pushed glass alone.
    """
    return nudge.shortfall(_layout(before)) - nudge.shortfall(_layout(after))


def _layout(seen: list[Seen]) -> list[tuple[float, float, float]]:
    return [(glass.x, glass.y, glass.widest) for glass in seen]
