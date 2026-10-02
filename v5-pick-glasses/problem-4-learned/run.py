"""Clear mixed tables with the learned pipeline, and score it against the simulator.

The order of work, which is the only thing this file decides:

    loop:
        look from above                                  TopNet
        for each glass not yet measured that has a clean place to look from:
            take the side picture                        Ranker chooses the place
            measure it, name it, find the grip           SideNet, GripNet
            refuse it if GripNet says no grip, or SideNet is unsure of the kind
        if a measured, holdable glass has room:
            choose its slot for the whole table          rack_plan (programmed)
            squeeze at its kind's force cap and rack it  spec.py lookup
        else push one crowded glass                      push model + search
        stop when nothing is left worth doing, and give each glass left a reason

Racking is the bench's take(): problem 1 does the real picking in Gazebo. So
the grip is judged, not tried: against where the project's own rule would
hold that glass if its true shape and kind were known.

    pixi run python run.py                 # 50 held-out tables; writes results.json
    pixi run python run.py --tables 5 --show
    pixi run python run.py --tables 3 --trace    # every step written to saved/runs/
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from work_cell.glasses import spec

import push_features as features
import push_plan
import rack_plan
import render
import scoring
import steps
import tables
import train
from bench import STANDING_TILT_DEG, Bench, Push, has_room
from push_model import Ensemble

HERE = Path(__file__).parent
RUNS = HERE / "saved" / "runs"

MAX_PUSHES = 16
PUSHES_PER_GLASS = 4

# A grip lands on the right part of the glass when it is within this of where
# the rule puts it: half the pad's height, so the pads still overlap the band.
GRIP_TOLERANCE = 0.007

# On the way in the fingers are opened to the opening plus this, as task.py
# does. An opening read narrower than the glass by more than this means the
# fingers meet the glass before they start to close.
APPROACH_MARGIN = 0.020


class Run:
    """One table, cleared."""

    def __init__(self, seed: int, models: dict, push_model: Ensemble, trace: bool = False) -> None:
        self.seed = seed
        self.bench: Bench = tables.mixed_bench(seed)
        self.models, self.push_model = models, push_model
        self.rng = np.random.default_rng(seed)
        self.measured: dict[int, steps.Measured] = {}
        self.refused: dict[int, str] = {}
        self.racked: dict[int, dict] = {}
        self.free = rack_plan.ALL
        self.pushes = 0
        self.per_glass = Counter()
        self.views: list[bool] = []
        self.events: list[dict] | None = [] if trace else None

    def note(self, **event) -> None:
        if self.events is not None:
            self.events.append(event)

    # Hooks for explain.py, which draws each step as it happens. Nothing here
    # uses them; they let a walkthrough watch a real run without copying it.
    def on_look(self, top, sightings, glasses, ids) -> None: ...

    def on_measure(self, target, others, glasses, ids, best, side, measured, clean, reason) -> None: ...

    def on_rack(self, sighting, slot, free_before, rest, measured) -> None: ...

    def on_push(self, seen, kinds, wanted, target, choice, started_at, felt) -> None: ...

    def on_stop(self, here, verdicts) -> None: ...

    def clear(self) -> None:
        while True:
            top, sightings, glasses, ids = steps.look(self.bench, self.models["top_net"])
            here = [s for s in sightings if s.id is not None and s.id not in self.refused]
            self.note(step="look", found=[_sighting(s) for s in sightings], on_table=[int(i) for i in ids])
            self.on_look(top, sightings, glasses, ids)
            if any(self.bench.tilt(i) >= STANDING_TILT_DEG for i in ids):
                for i in ids:
                    self.refused.setdefault(i, "stopped: a glass on the table has fallen over")
                return

            for s in here:
                if s.id not in self.measured:
                    self.try_to_measure(s, [o for o in sightings if o is not s], glasses, ids)
            here = [s for s in sightings if s.id is not None and s.id not in self.refused]
            if not here:
                break

            standing = [s for s in sightings if s.id is not None]
            if self.rack_one(here, standing):
                continue
            if not self.push_one(here, sightings):
                break

        for i in self.bench.on_table():
            if i not in self.refused:
                self.refused[i] = "never found from above" if i not in self.measured else "left without room"

    def try_to_measure(self, target, others, glasses, ids) -> None:
        best = steps.view(target, others, self.models["ranker"])
        if best is None or best[0] < steps.MIN_VIEW_SCORE:
            self.on_measure(target, others, glasses, ids, best, None, None, None, None)
            return
        score, angle = best
        side, measured = steps.measure(
            glasses, target, angle, score, self.models["side_net"], self.models["grip_net"]
        )
        self.measured[target.id] = measured
        index = ids.index(target.id)
        alone = render.render([glasses[index]], side.camera_to_world)
        clean = scoring.is_good(side, alone)
        self.views.append(clean)
        reason = steps.refusal(measured)
        if reason:
            self.refused[target.id] = reason
        self.on_measure(target, others, glasses, ids, best, side, measured, clean, reason)
        self.note(
            step="measure",
            glass=target.id,
            angle=angle,
            view_score=score,
            view_clean=clean,
            said=_measured(measured),
            truth=_truth(self.bench.glasses[target.id]),
            refused=reason,
        )

    def wide(self, s) -> bool:
        m = self.measured.get(s.id)
        return rack_plan.is_wide(m.widest, m.height) if m else rack_plan.is_wide(s.seen.widest, s.seen.height)

    def rack_one(self, here, standing) -> bool:
        """Rack one measured, holdable glass that has room. False when there is none.

        Room is judged against every glass still standing, refused ones too:
        a glass left standing is still in the fingers' way.
        """
        roomy = [
            s
            for s in here
            if s.id in self.measured
            and has_room(
                s.seen.x,
                s.seen.y,
                [(o.seen.x, o.seen.y, o.seen.widest) for o in standing if o is not s],
                margin=push_plan.TAKE_MARGIN,
            )
        ]
        for s in roomy:
            rest = [self.wide(o) for o in here if o is not s]
            slot = rack_plan.best_slot(self.free, self.wide(s), rest)
            if slot is None:
                self.refused[s.id] = "no slot left in the rack that it fits"
                self.note(step="refuse", glass=s.id, reason=self.refused[s.id])
                continue
            free_before = self.free
            self.free -= rack_plan.consumed(slot, self.wide(s))
            m = self.measured[s.id]
            self.on_rack(s, slot, free_before, rest, m)
            self.bench.take(s.id)
            self.racked[s.id] = {"slot": slot, "wide": self.wide(s), "had_room": self.bench.taken[s.id]}
            self.note(
                step="rack",
                glass=s.id,
                slot=slot,
                wide=self.wide(s),
                squeeze_n=m.squeeze,
                free_after=sorted(self.free),
            )
            return True
        return False

    def push_one(self, here, sightings) -> bool:
        """Push one crowded glass apart. False when no push is worth making."""
        wanted_ids = {s.id for s in here}
        seen = [_with_foot(s, self.measured.get(s.id)) for s in here]
        # Glasses refused earlier still stand in the way, so the model is told
        # about them; they just have no room worth winning.
        for s in sightings:
            if s.id is not None and s.id in self.refused:
                seen.append(_with_foot(s, self.measured.get(s.id)))
        kinds = {i: m.kind for i, m in self.measured.items()}
        wanted = np.array([s.id in wanted_ids for s in seen], dtype=float)

        rest = [self.wide(s) for s in here]
        if rack_plan.capacity(self.free, tuple(sorted(rest))) == 0:
            for s in here:
                self.refused[s.id] = "no slot left in the rack that it fits"
            return False

        before = push_plan.shortfall(
            np.array([[s.x, s.y] for s in seen]), np.array([s.widest for s in seen]), wanted
        )
        # Any standing glass may be pushed, a refused one too: moving a glass
        # that cannot be racked out of the way is often what frees one that can.
        verdicts = {}
        for target in seen:
            if self.per_glass[target.id] >= PUSHES_PER_GLASS:
                verdicts[target.id] = push_plan.Verdict(
                    None, f"pushed {PUSHES_PER_GLASS} times and still without room"
                )
                continue
            verdicts[target.id] = push_plan.best_push(self.push_model, seen, target, kinds, wanted, self.rng)
        choice = min((v.choice for v in verdicts.values() if v.choice), key=lambda c: c.cost, default=None)

        if self.pushes >= MAX_PUSHES or choice is None or choice.cost > before - push_plan.WORTH_IT:
            for s in here:
                verdict = verdicts.get(s.id)
                if self.pushes >= MAX_PUSHES:
                    self.refused[s.id] = f"the table's {MAX_PUSHES} pushes are spent"
                elif s.id not in self.measured:
                    self.refused[s.id] = "no clean side view, and no push expected to make one"
                elif verdict is not None and verdict.choice is None:
                    self.refused[s.id] = verdict.reason
                else:
                    self.refused[s.id] = "no push the model expects to make room"
            self.on_stop(here, verdicts)
            return False

        target = next(s for s in seen if s.id == choice.target)
        started_at = self.bench.position(choice.target)
        felt = self.bench.push(
            Push(
                choice.target,
                features.jaw_start(target, choice.heading, choice.offset),
                choice.heading,
                features.jaw_reach(target),
                choice.travel,
                choice.aim,
            )
        )
        self.pushes += 1
        self.per_glass[choice.target] += 1
        self.on_push(seen, kinds, wanted, target, choice, started_at, felt)
        self.note(
            step="push",
            glass=choice.target,
            kind_given=kinds.get(choice.target, features.NOT_MEASURED),
            heading_deg=float(np.degrees(choice.heading)),
            offset_mm=1000 * choice.offset,
            travel_mm=1000 * choice.travel,
            topple_chance=choice.topple,
            aim=list(choice.aim),
            landed=[float(v) for v in self.bench.position(choice.target)],
            blocked=felt.blocked,
            jammed=felt.jammed,
        )
        return True


def _with_foot(s: steps.Sighting, m: steps.Measured | None):
    return s.seen if m is None else replace(s.seen, foot=m.foot)


def _sighting(s: steps.Sighting) -> dict:
    return {
        "glass": s.id,
        "x": s.seen.x,
        "y": s.seen.y,
        "height_mm": 1000 * s.seen.height,
        "widest_mm": 1000 * s.seen.widest,
    }


def _measured(m: steps.Measured) -> dict:
    return {
        "kind": m.kind,
        "kind_chances": dict(zip(steps.nets.KINDS, np.round(m.kind_chances, 3).tolist(), strict=True)),
        "height_mm": round(1000 * m.height, 1),
        "widths_mm": np.round(1000 * m.widths, 1).tolist(),
        "hold_chance": round(m.hold_chance, 3),
        "grip_height_mm": round(1000 * m.grip_height, 1),
        "opening_mm": round(1000 * m.opening, 1),
        "squeeze_n": m.squeeze,
    }


def _truth(glass) -> dict:
    grip = tables.glass_grip(glass)
    return {
        "kind": glass.kind,
        "height_mm": round(1000 * glass.outline.total_height, 1),
        "holdable": grip.holdable,
        "grip_height_mm": round(1000 * grip.height, 1),
        "opening_mm": round(1000 * grip.opening, 1),
        "why_not": grip.reason,
        "squeeze_n": spec.kind(glass.kind).force_cap_n,
    }


class Scorecard:
    def __init__(self) -> None:
        self.c = Counter()
        self.refusals = Counter()
        self.confusion = np.zeros((4, 4), int)
        self.grip_mm: list[tuple[float, float]] = []
        self.height_mm: list[float] = []
        self.width_mm: list[float] = []

    def table(self, run: Run) -> str:
        c, bench = self.c, run.bench
        c["tables"] += 1
        c["glasses"] += len(bench.glasses)
        c["pushes"] += run.pushes
        c["views judged"] += len(run.views)
        c["views clean"] += sum(run.views)
        toppled = any(
            bench.tilt(i) >= STANDING_TILT_DEG for i in range(len(bench.glasses)) if i not in bench.taken
        )
        c["tables with a topple"] += toppled

        for i, glass in enumerate(bench.glasses):
            truth = tables.glass_grip(glass)
            c[f"holdable by the rule: {truth.holdable}"] += 1
            m = run.measured.get(i)
            if m is not None:
                c["measured"] += 1
                self.confusion[tables.kind_index(glass.kind), tables.kind_index(m.kind)] += 1
                c["named right"] += m.kind == glass.kind
                self.height_mm.append(1000 * abs(m.height - glass.outline.total_height))
                true_widths = 2 * np.interp(
                    scoring.FRACTIONS * glass.outline.total_height, glass.outline.height, glass.outline.radius
                )
                self.width_mm.append(1000 * float(np.median(np.abs(m.widths - true_widths))))
                said = m.hold_chance >= steps.HOLD_CHANCE
                c[f"GripNet holdable {said}, rule {truth.holdable}"] += 1
            if i in run.racked:
                c["racked"] += 1
                c["racked without room"] += not run.racked[i]["had_room"]
                if m.kind != glass.kind:
                    c["racked, named wrongly"] += 1
                if m.squeeze > spec.kind(glass.kind).force_cap_n:
                    c["racked, squeezed harder than its kind allows"] += 1
                if not truth.holdable:
                    c["racked, though the rule finds no grip"] += 1
                else:
                    dh, do = m.grip_height - truth.height, m.opening - truth.opening
                    self.grip_mm.append((1000 * dh, 1000 * do))
                    c["racked, grip on the band"] += abs(dh) <= GRIP_TOLERANCE
                    c["racked, fingers would meet it on the way in"] += do < -APPROACH_MARGIN
            elif i in run.refused:
                reason = run.refused[i]
                self.refusals[reason.split(" (")[0]] += 1
                c["refused, though the rule could hold it"] += truth.holdable
        dangerous = (
            c["racked, though the rule finds no grip"] + c["racked, squeezed harder than its kind allows"]
        )
        return "toppled" if toppled else ("dangerous" if dangerous else "ok")

    def summary(self) -> dict:
        c = self.c
        grip = np.array(self.grip_mm) if self.grip_mm else np.zeros((1, 2))
        return {
            "tables": c["tables"],
            "glasses": c["glasses"],
            "racked": c["racked"],
            "refused": dict(self.refusals.most_common()),
            "pushes": c["pushes"],
            "tables_with_a_topple": c["tables with a topple"],
            "racked_without_room": c["racked without room"],
            "view": {"judged": c["views judged"], "clean": c["views clean"]},
            "measure": {
                "measured": c["measured"],
                "height_mm_median": round(float(np.median(self.height_mm)), 1) if self.height_mm else None,
                "width_mm_median": round(float(np.median(self.width_mm)), 1) if self.width_mm else None,
            },
            "name": {
                "named_right": c["named right"],
                "of": c["measured"],
                "confusion_rows_made_as_columns_named": {
                    made: dict(zip(steps.nets.KINDS, row.tolist(), strict=True))
                    for made, row in zip(steps.nets.KINDS, self.confusion, strict=True)
                },
            },
            "grip": {
                "gripnet_vs_rule": {k: v for k, v in c.items() if k.startswith("GripNet holdable")},
                "height_mm_median": round(float(np.median(np.abs(grip[:, 0]))), 1),
                "height_mm_worst": round(float(np.abs(grip[:, 0]).max()), 1),
                "opening_mm_median": round(float(np.median(np.abs(grip[:, 1]))), 1),
                "on_the_band": c["racked, grip on the band"],
                "fingers_meet_it_on_the_way_in": c["racked, fingers would meet it on the way in"],
            },
            "dangerous": {
                "racked_named_wrongly": c["racked, named wrongly"],
                "squeezed_harder_than_its_kind_allows": c["racked, squeezed harder than its kind allows"],
                "racked_though_the_rule_finds_no_grip": c["racked, though the rule finds no grip"],
            },
            "refused_though_the_rule_could_hold_it": c["refused, though the rule could hold it"],
            "holdable_by_the_rule": c["holdable by the rule: True"],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=50)
    parser.add_argument("--first", type=int, default=tables.TEST_SEEDS)
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--trace", action="store_true", help="write every step of every table to saved/runs/")
    arguments = parser.parse_args()
    torch.set_num_threads(4)
    models = train.load()
    push_model = Ensemble.load(train.WEIGHTS)
    card = Scorecard()

    started = time.time()
    for seed in range(arguments.first, arguments.first + arguments.tables):
        run = Run(seed, models, push_model, trace=arguments.trace)
        run.clear()
        outcome = card.table(run)
        if arguments.show:
            kinds = Counter(g.kind.replace("_glass", "") for g in run.bench.glasses)
            print(
                f"table {seed}: {dict(kinds)}  racked {len(run.racked)}, refused {len(run.refused)}, "
                f"pushes {run.pushes}: {outcome}"
            )
        if arguments.trace:
            RUNS.mkdir(parents=True, exist_ok=True)
            truth = [
                _truth(g) | {"start": [float(v) for v in run.bench.start[i]]}
                for i, g in enumerate(run.bench.glasses)
            ]
            (RUNS / f"table-{seed}.json").write_text(
                json.dumps(
                    {
                        "table": seed,
                        "outcome": outcome,
                        "glasses": truth,
                        "steps": run.events,
                        "racked": run.racked,
                        "refused": run.refused,
                    },
                    indent=1,
                    default=float,
                )
                + "\n"
            )

    result = card.summary()
    result["seconds"] = round(time.time() - started)
    full = arguments.first == tables.TEST_SEEDS and arguments.tables == 50
    save = HERE / ("results.json" if full else "partial.json")
    save.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
