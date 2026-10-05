"""The loop the policy runs in: look, take what has room, gate, ask for a chunk, follow it.

The loop is not this solution's contribution. It is the one every solution in
this problem runs --- act, measure what really happened, decide again from
what was measured --- and it is what keeps copying survivable, because the
table the policy is asked about is always a measured one and never a
predicted one. The only step this solution replaces is the choosing.

Three things happen outside the policy, and each is here rather than in the
model for a reason the document gives.

**The tipping limit is a gate in front.** A glass whose foot is narrow enough
that it tips before it slides at any plausible friction is refused with that
reason, and the policy is never asked about it. A chunk of waypoints has no
channel for "I cannot move this glass", so a refusal cannot come out of the
policy; and the absence of an example is not a label, so nothing in the data
would have taught it to refuse. The arithmetic is solution 1's ``slides``,
the same one solutions 1 and 2 use, evaluated at the jaw's top edge on the
measured foot width.

**Which glass a chunk is for is read off the chunk.** The bench's ``Chunk``
carries a glass and an aim beside the waypoints, and a policy that emits
waypoints produces neither. ``chunks.aimed_at`` reads both back, from the
glasses the gate left in play, so a chunk can never be charged to a glass
that was refused.

**A chunk is pulled inside the jaw's limits.** A network can produce any
number. Heights and positions outside what the jaw can reach are clipped and
counted, which is a limit on the actuator rather than a second attempt at a
refused push.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from chunks import aimed_at, to_waypoints
from teacher import nudge

from bench import PUSHES_PER_GLASS, PUSHES_PER_TABLE, Bench, Chunk

# A glass with this much room to spare is taken rather than pushed. Solutions
# 1 and 2's number, so all three rack on the same rule: three standard
# deviations of the measurement error in the gap.
TAKE_MARGIN = 0.005

TIPS = "tips before it slides"
FELL = "stopped: a glass fell over"
SPENT = "push budget spent"
STUCK = "still without room after pushing"


@dataclass
class Tally:
    """What the run-time wrapping around the policy had to do. Not a score."""

    chunks: int = 0
    waypoints_pulled_in: int = 0
    chunks_pulled_in: int = 0
    gated: Counter = field(default_factory=Counter)

    def merge(self, other: Tally) -> None:
        self.chunks += other.chunks
        self.waypoints_pulled_in += other.waypoints_pulled_in
        self.chunks_pulled_in += other.chunks_pulled_in
        self.gated.update(other.gated)

    def summary(self) -> dict:
        return {
            "chunks": self.chunks,
            "chunks_pulled_inside_the_limits": self.chunks_pulled_in,
            "waypoints_pulled_inside_the_limits": self.waypoints_pulled_in,
            "glasses_gated_before_the_policy": dict(self.gated),
        }


def clear(table: Bench, camera, policy, tally: Tally | None = None, show: bool = False) -> dict[int, str]:
    """Clear one table with the policy. Returns the glasses left, each with its reason."""
    tally = tally if tally is not None else Tally()
    pushed: Counter = Counter()
    while True:
        seen = table.look()
        if not all(glass.standing for glass in seen):
            # Nothing in this project stands a glass back up, and the arm does
            # not work near one lying down.
            return {glass.id: FELL for glass in seen if glass.standing}
        if not seen:
            return {}

        ready = [glass for glass in seen if nudge.room(glass, seen, TAKE_MARGIN)]
        if ready:
            for glass in ready:
                table.take(glass.id)
            continue

        gated = {glass.id: TIPS for glass in seen if nudge.slides(glass) == "no"}
        worn = {glass for glass, count in pushed.items() if count >= PUSHES_PER_GLASS}
        left = [glass for glass in seen if glass.id not in gated and glass.id not in worn]
        if not left or pushed.total() >= PUSHES_PER_TABLE:
            over = pushed.total() >= PUSHES_PER_TABLE or bool(worn)
            return {glass.id: gated.get(glass.id, SPENT if over else STUCK) for glass in seen}

        waypoints, pulled = to_waypoints(policy.chunk(camera.view()))
        glass, aim = aimed_at(waypoints, left)
        tally.chunks += 1
        tally.waypoints_pulled_in += pulled
        tally.chunks_pulled_in += pulled > 0
        tally.gated.update(gated.values())

        _caption(table, glass, len(waypoints))
        felt = table.follow(Chunk(glass, waypoints, aim))
        pushed[glass] += 1
        if show:
            print(
                f"  chunk of {len(waypoints)} at glass {glass}: "
                f"{'blocked' if felt.blocked else 'no touch' if felt.touched is None else 'touched'}"
                f"{', jammed' if felt.jammed else ''}"
                f"{f', {pulled} waypoints pulled in' if pulled else ''}"
            )


def _caption(table: Bench, glass: int, waypoints: int) -> None:
    """Tell a filmed bench what is happening. ``film.py`` only captions ``push()``."""
    if hasattr(table, "doing"):
        table.doing = f"chunk {len(table.records) + 1}: glass {glass}, {waypoints} waypoints"
