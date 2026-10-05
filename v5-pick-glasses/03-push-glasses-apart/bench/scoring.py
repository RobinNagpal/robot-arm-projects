"""How a run is scored against what the simulator really did.

Shared by both approaches, so their numbers mean the same thing. Nothing here
is used by an approach to decide anything; only to judge it afterwards.

What problem.md calls done, correct but incomplete, and wrong:

- **done**: every glass was racked, each one while it really had room.
- **incomplete**: some glasses are still on the table, each with a reason
  given, and nothing went wrong.
- **wrong**: a glass toppled, left the glass zone, was picked while it did not
  really have room, or was left on the table with no reason given.

Two things here are not in problem 2's scoring.

**One run is not a measurement.** Four of the six solutions are stochastic, so
asked the same question twice they may answer differently. ``Repeats`` holds
several evaluation runs of one solution and reports the spread across them. A
method that wins by less than its own spread has not been shown to win.

**What a push costs to decide belongs beside the counts.** A fixed nudge is
arithmetic; a planner searches; a foundation model is a large forward pass.
Pass ``seconds`` to ``scene()`` and the scorecard reports the time per push,
with the bench's own physics taken off, so what is left is the solution's
thinking. Leave it out and no time is reported: an unmeasured cost is absent
rather than zero.
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
        self.thinking = 0.0
        self.timed = False

    def scene(self, bench: Bench, refused: dict[int, str], seconds: float | None = None) -> str:
        """Judge one table once the approach has finished with it. Returns its outcome.

        ``seconds`` is the wall time the approach spent on this table, the
        bench included. The bench's own share is taken off, so what is counted
        is the thinking. Left out, no time is reported at all.
        """
        c = self.count
        if seconds is not None:
            self.thinking += max(0.0, seconds - bench.seconds)
            self.timed = True
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
        result = {
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
        if self.timed and c["pushes"]:
            result["seconds_per_push"] = round(self.thinking / c["pushes"], 4)
        return result

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
        if "seconds_per_push" in result:
            print(f"compute  {1000 * result['seconds_per_push']:.1f} ms of thinking per push")
        save.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nsaved to {save}")


class Repeats:
    """Several evaluation runs of one solution, and the spread across them.

    One run is not a measurement for a policy that draws its action rather
    than computing it, and the variation between runs is sometimes larger than
    the gap between two methods. So a solution whose answer is not the same
    twice runs several times and reports all of them::

        runs = Repeats()
        for seed in range(5):
            card = runs.run()
            for table in tables:
                card.scene(table, refused, seconds=spent)
        runs.report(Path("results.json"))

    A deterministic solution has nothing to repeat and keeps using Scorecard
    on its own, which is why the one-run file's shape is unchanged.
    """

    def __init__(self) -> None:
        self.cards: list[Scorecard] = []

    def run(self) -> Scorecard:
        """A fresh scorecard for the next evaluation run."""
        self.cards.append(Scorecard())
        return self.cards[-1]

    def summary(self) -> dict:
        """Every run in full, and the spread of every number across them."""
        each = [card.summary() for card in self.cards]
        return {"runs": len(each), "spread": spread(each), "each": each}

    def report(self, save: Path) -> None:
        """Print the headline numbers with their spread, and save every run."""
        result = self.summary()
        wide = result["spread"]
        print(f"\n{result['runs']} evaluation runs of {result['each'][0]['scenes']} held-out scenes\n")
        for line, keys in (
            ("tables ", ("outcome.done", "outcome.incomplete", "outcome.wrong")),
            ("glasses", ("glasses_end.racked", "glasses_end.refused", "glasses_end.toppled")),
            ("pushes ", ("pushes.total", "pushes.repeats", "seconds_per_push")),
        ):
            shown = [f"{key.split('.')[-1]} {_band(wide[key])}" for key in keys if key in wide]
            print(f"{line}  " + ", ".join(shown))
        save.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nsaved to {save}")


def spread(each: list[dict]) -> dict:
    """The middle and the range of every number that every run reports.

    Keyed by a dotted path into the summary, so ``glasses_end.racked`` is the
    glasses racked. A count only some runs report is left out, because a
    spread over a different set of runs each time would not mean anything.
    """
    rows = [_flat(summary) for summary in each]
    shared = [key for key in rows[0] if all(key in row for row in rows)]
    return {key: _band_of([row[key] for row in rows]) for key in shared}


def _band_of(values: list[float]) -> dict:
    return {
        "median": round(float(np.median(values)), 3),
        "sd": round(float(np.std(values, ddof=1)) if len(values) > 1 else 0.0, 3),
        "least": round(min(values), 3),
        "most": round(max(values), 3),
    }


def _band(band: dict) -> str:
    return f"{band['median']:g} +/- {band['sd']:g} ({band['least']:g} to {band['most']:g})"


def _flat(summary: dict, prefix: str = "") -> dict[str, float]:
    """Every number in a summary, keyed by its dotted path."""
    out: dict[str, float] = {}
    for key, value in summary.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flat(value, f"{name}."))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = float(value)
    return out


def all_racked(bench: Bench) -> bool:
    return len(bench.taken) == len(bench.glasses)
