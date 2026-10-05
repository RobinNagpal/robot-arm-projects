"""How a run is scored against what the simulator really did.

Shared by both approaches, so their numbers mean the same thing. Nothing here
is used by an approach to decide anything; only to judge it afterwards.

What problem.md calls done, correct but incomplete, and wrong:

- **done**: every glass was racked, each one while it really had room.
- **incomplete**: some glasses are still on the table, each with a reason
  given, and nothing went wrong.
- **wrong**: a glass toppled, left the glass zone, was picked while it did not
  really have room, or was left on the table with no reason given.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from bench import STANDING_TILT_DEG, Bench, has_room, in_zone


class Scorecard:
    """Counts and errors for one run, in the same shape for both approaches."""

    def __init__(self) -> None:
        self.count = Counter()
        self.refusals = Counter()
        self.aim_mm: list[float] = []

    def scene(self, bench: Bench, refused: dict[int, str]) -> str:
        """Judge one table once the approach has finished with it. Returns its outcome."""
        c = self.count
        glasses = len(bench.glasses)
        c["scenes"] += 1
        c["glasses"] += glasses
        start = bench.start
        for i in range(glasses):
            others = [(*start[j], bench.glasses[j].outline.max_diameter) for j in range(glasses) if j != i]
            c["crowded at start"] += not has_room(*start[i], others)

        pushed: Counter = Counter()
        for record in bench.records:
            c["pushes"] += 1
            c["repeat pushes"] += pushed[record.push.glass] > 0
            pushed[record.push.glass] += 1
            felt = record.felt
            c["blocked on the way down"] += felt.blocked
            c["never touched"] += not felt.blocked and felt.touched is None
            c["jammed"] += felt.jammed
            if felt.touched is not None:
                self.aim_mm.append(1000 * float(np.hypot(*np.subtract(record.landed, record.push.aim))))

        wrong = False
        for i in range(glasses):
            if i in bench.taken:
                if bench.taken[i]:
                    c["racked"] += 1
                else:
                    c["picked without room"] += 1
                    wrong = True
                continue
            if bench.tilt(i) >= STANDING_TILT_DEG:
                c["toppled"] += 1
                wrong = True
            elif not in_zone(*bench.position(i)):
                c["pushed out of the zone"] += 1
                wrong = True
            elif i in refused:
                c["refused"] += 1
                self.refusals[refused[i]] += 1
            else:
                c["left with no reason"] += 1
                wrong = True

        outcome = "wrong" if wrong else "done" if all_racked(bench) else "incomplete"
        c[outcome] += 1
        return outcome

    def summary(self) -> dict:
        c = self.count
        aim = np.array(self.aim_mm) if self.aim_mm else np.zeros(1)
        return {
            "scenes": c["scenes"],
            "glasses": c["glasses"],
            "crowded_at_start": c["crowded at start"],
            "outcome": {k: c[k] for k in ("done", "incomplete", "wrong")},
            "glasses_end": {
                k.replace(" ", "_"): c[k]
                for k in (
                    "racked",
                    "refused",
                    "toppled",
                    "pushed out of the zone",
                    "picked without room",
                    "left with no reason",
                )
            },
            "refused_because": dict(self.refusals),
            "pushes": {
                "total": c["pushes"],
                "repeats": c["repeat pushes"],
                "blocked_on_the_way_down": c["blocked on the way down"],
                "never_touched": c["never touched"],
                "jammed": c["jammed"],
                "aim_mm_median": round(float(np.median(aim)), 1),
                "aim_mm_worst": round(float(aim.max()), 1),
            },
        }

    def report(self, save: Path) -> None:
        """Print the summary and save it, so two approaches can be set side by side."""
        result = self.summary()
        outcome, end, pushes = result["outcome"], result["glasses_end"], result["pushes"]
        print(
            f"\n{result['scenes']} held-out scenes, {result['glasses']} glasses, "
            f"{result['crowded_at_start']} without room at the start\n"
        )
        print(
            f"tables   done {outcome['done']}, incomplete {outcome['incomplete']}, wrong {outcome['wrong']}"
        )
        print(
            f"glasses  racked {end['racked']}, refused {end['refused']}, toppled {end['toppled']}, "
            f"out of zone {end['pushed_out_of_the_zone']}, picked without room {end['picked_without_room']}, "
            f"left with no reason {end['left_with_no_reason']}"
        )
        print(f"refused  {result['refused_because'] or 'none'}")
        print(
            f"pushes   {pushes['total']} ({pushes['repeats']} repeats); "
            f"blocked {pushes['blocked_on_the_way_down']}, "
            f"never touched {pushes['never_touched']}, jammed {pushes['jammed']}; landed "
            f"{pushes['aim_mm_median']} mm from the aim median, {pushes['aim_mm_worst']} worst"
        )
        save.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nsaved to {save}")


def all_racked(bench: Bench) -> bool:
    return len(bench.taken) == len(bench.glasses)
