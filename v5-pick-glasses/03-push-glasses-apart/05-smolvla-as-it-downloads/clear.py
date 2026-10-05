"""One table, cleared by asking the borrowed model over and over.

The loop is the same one solutions 1 and 2 run — look, rack every glass that
has room, act on the rest, look again — with the choosing replaced by a
forward pass. What is different is everything about the choosing: nothing here
enumerates a push, scores one, or knows which glass needs moving. The picture
goes in and a trajectory comes out.

Two checks run before the model and are not its to argue with, which is what
the document asks for.

- **Tipping.** A glass that would tip rather than slide when the jaw's top
  edge meets it is refused and removed from the task. The arithmetic is
  solution 1's ``slides``, imported rather than copied, so the six solutions
  refuse exactly the same glasses.
- **The path.** A refused glass stays in the picture, and nothing in the
  model's pretraining would warn it off one. So a trajectory that would reach
  a refused glass is not carried out at all. The heights are bounded in
  ``joining.to_jaw`` for the same reason.

That rejection is not a push and is not charged to the push budget, because
the budget is what makes the six solutions' push counts comparable and a
rejected trajectory never touches the table. The model cannot be told "not
that one", so a table needs a stop of its own as well, and ``ASKS_PER_TABLE``
is it: a guard against a loop rather than a budget. The run reports how often
it bound.

**The per-glass budget binds differently here, and it has to.** The other
solutions choose a glass and can be told to leave a worn one alone. This one
does not choose: which glass a trajectory belongs to is read back off the path
afterwards, for the record. Throwing an answer away on that bookkeeping would
block the model for the rest of the table on the strength of a label it never
emitted. So ``PUSHES_PER_GLASS`` is applied where it can honestly bite — a
table is finished once every glass still on it has either been refused for
tipping or had its share — and every answer that survives the two checks is
carried out and counted against ``PUSHES_PER_TABLE``, which is the number the
six are compared on.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from joining import chunk_for, hits_refused
from work_cell.table.layout import TABLE_TOP_Z

import bench
from bench import Bench, Waypoint
from top_view import TopCamera

# Solution 1's folder is not a package — its name starts with a digit — so it
# joins the path rather than being imported from, as solution 2 does it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "01-one-fixed-nudge"))

import plan as nudge  # noqa: E402

# A glass with this much room to spare is taken. Solution 1's number, so every
# solution racks on the same rule.
TAKE_MARGIN = 0.005

TIPS = "tips before it slides"
SPENT = "push budget spent"
STUCK = "the model kept answering with trajectories that could not be carried out"

# How many answers one table may be given. The push budget is the bench's and
# counts pushes; this counts answers, including the ones thrown away, so that
# a model which keeps aiming at a glass it may not touch cannot run forever.
# Three answers per push in the budget, which is slack rather than a limit.
ASKS_PER_TABLE = 3 * bench.PUSHES_PER_TABLE


@dataclass
class Tally:
    """What the asking cost on one table, beside what the scorecard counts."""

    asked: int = 0
    followed: int = 0
    refused_path: int = 0  # would have reached a glass refused for tipping
    worn_path: int = 0  # carried out, but credited to a glass already at its share
    rejected_by_bench: int = 0  # follow() would not take it
    ran_out_of_asks: int = 0  # tables stopped by ASKS_PER_TABLE rather than by the push budget
    why: Counter = field(default_factory=Counter)
    # What the model's trajectories looked like, one entry per answer: how far
    # the jaw travels in a chunk, how far it moves per waypoint, and how low
    # it gets. The step is the interesting one, because a waypoint period of
    # jaw travel is the speed the chunk is carried out at.
    across_mm: list[float] = field(default_factory=list)
    step_mm: list[float] = field(default_factory=list)
    lowest_mm: list[float] = field(default_factory=list)

    def add(self, other: Tally) -> None:
        self.asked += other.asked
        self.followed += other.followed
        self.refused_path += other.refused_path
        self.worn_path += other.worn_path
        self.rejected_by_bench += other.rejected_by_bench
        self.ran_out_of_asks += other.ran_out_of_asks
        self.why += other.why
        self.across_mm += other.across_mm
        self.step_mm += other.step_mm
        self.lowest_mm += other.lowest_mm

    def saw(self, path: np.ndarray) -> None:
        """Note the shape of one answer."""
        steps = np.hypot(np.diff(path[:, 0]), np.diff(path[:, 1]))
        self.across_mm.append(1000 * float(steps.sum()))
        self.step_mm.append(1000 * float(np.median(steps)))
        self.lowest_mm.append(1000 * float(path[:, 2].min()))

    def summary(self) -> dict:
        middle = {
            f"{name}_median": round(float(np.median(values)), 1)
            for name, values in (
                ("across_mm", self.across_mm),
                ("step_mm", self.step_mm),
                ("lowest_mm", self.lowest_mm),
            )
            if values
        }
        return {
            "asked": self.asked,
            "followed": self.followed,
            "rejected_for_a_refused_glass": self.refused_path,
            "credited_to_a_spent_glass": self.worn_path,
            "rejected_by_the_bench": self.rejected_by_bench,
            "tables_that_ran_out_of_asks": self.ran_out_of_asks,
            "rejected_because": dict(self.why),
            **middle,
        }


def jaw_now(table: Bench) -> Waypoint:
    """Where the jaw stands, which the arm knows exactly from its own encoders.

    Between actions the bench parks the jaw, so in practice this is the same
    pose at every ask. That is a fact about the cell, not a shortcut: it means
    the model's third input is as constant here as its second one.
    """
    x, y, z = table.data.mocap_pos[0]
    w, _, _, spin = table.data.mocap_quat[0]
    return Waypoint(float(x), float(y), float(z - TABLE_TOP_Z), 2 * float(np.arctan2(spin, w)))


def clear(table: Bench, model, camera: TopCamera, show: bool = False) -> tuple[dict[int, str], Tally]:
    """Clear one table. Returns what was refused and why, and what the asking cost."""
    pushed: Counter = Counter()
    tally = Tally()
    while True:
        seen = table.look()
        if not all(glass.standing for glass in seen):
            # Nothing in this project stands a glass back up, and the arm does
            # not touch anything near one lying on the table.
            return {g.id: "stopped: a glass fell over" for g in seen if g.standing}, tally
        if not seen:
            return {}, tally

        tips = {g.id: TIPS for g in seen if nudge.slides(g) == "no"}
        ready = [g for g in seen if nudge.room(g, seen, TAKE_MARGIN)]
        if ready:
            for glass in ready:
                table.take(glass.id)
            continue

        worn = {g for g, n in pushed.items() if n >= bench.PUSHES_PER_GLASS}
        done_with = set(tips) | worn
        if pushed.total() >= bench.PUSHES_PER_TABLE or all(g.id in done_with for g in seen):
            return {g.id: tips.get(g.id, SPENT) for g in seen}, tally
        if tally.asked >= ASKS_PER_TABLE:
            tally.ran_out_of_asks += 1
            return {g.id: tips.get(g.id, STUCK) for g in seen}, tally

        path = model.ask(camera.view(), jaw_now(table))
        tally.asked += 1
        tally.saw(path)
        hit = hits_refused(path, seen, set(tips))
        if hit is not None:
            tally.refused_path += 1
            if show:
                print(f"  ask {tally.asked}: rejected, the path reaches refused glass {hit}")
            continue
        chunk = chunk_for(path, seen)
        tally.worn_path += chunk.glass in worn
        try:
            felt = table.follow(chunk)
        except ValueError as refusal:
            # to_jaw clips into the box follow() accepts, so this should not
            # happen. If it ever does, it is a result and not a crash.
            tally.rejected_by_bench += 1
            tally.why[str(refusal)] += 1
            continue
        pushed[chunk.glass] += 1
        tally.followed += 1
        if show:
            print(
                f"  ask {tally.asked}: glass {chunk.glass}, "
                f"{'blocked' if felt.blocked else 'no touch' if felt.touched is None else 'touched'}"
                f"{', jammed' if felt.jammed else ''}, moved {1000 * felt.pushed:.0f} mm"
            )
