"""Measure how much the candidates inside one group really differ, before trusting a ranker.

This is the measurement the document asks for and nobody had made. The
argument it tests is structural. ``nudge.along`` stops each heading at the
first travel that gives the glass room, so every push that finishes the job
lands just past the same contour, and all of them leave the table in the same
state. If that is right, the job-finishing pushes in a group are a tie, a
ranking over them carries no information, and whatever signal there is lives
in the wider set of pushes that only ease the crowding.

A ranking problem whose groups are ties is a ranking problem with nothing to
learn, so this number decides whether the fitted half of this solution is
worth anything at all.

What it does: on training tables, at the states a run really plans from, it
enumerates each glass's candidates, makes a sample of them on the bench and
labels every one from the simulator's record. Then it reports the spread of
the label within the job-finishing pushes, within the easing pushes, and what
the best possible choice would have been worth against the printed rule's.

Two groupings are reported, because two are meaningful. **A glass** is one
glass's candidates, which is the group the document argues about. **A
decision** is every candidate on the table at one moment, across all its
glasses, which is the list the ranker actually sorts at run time.

Two floors are reported with them. The same push made again scores identically
by the simulator's record, because the physics repeats exactly from a restored
state; the same push measured by the camera does not, and that number is how
much of a difference a run could even perceive.

    pixi run python spread.py              # writes spread.json
    pixi run python spread.py --tables 40

Sampling: a group runs to hundreds of pushes and making all of them is hours,
so each group contributes every job-finishing push up to FREEING and an even
sample of EASING of the rest. The job-finishing pushes are few, so that part
is usually the whole set; the easing part is a sample and is reported as one.
"""

from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from candidates import Candidate, rule_choice, survivors
from features import room_at
from rollout import TOPPLED, Rolled, restore, roll
from train import STEPS_PER_TABLE, after_racking, sample

from bench import Bench

REPORT = Path(__file__).parent / "spread.json"

FREEING = 12
EASING = 12
# The same candidate made again, to see how much of a group's spread is only
# the camera's error. The physics repeats exactly; the looks do not.
REPEATS = 4


def groups(seed: int) -> list[dict]:
    """Every group on one table, with its sampled candidates labelled.

    One record per glass, plus one per decision covering all of them.
    """
    rng = np.random.default_rng(seed)
    table = Bench(seed)
    found = []
    for step in range(STEPS_PER_TABLE):
        before = after_racking(table)
        if before is None or len(before.seen) < 2:
            break
        seen = before.seen
        kept, _ = survivors(seen, set())
        if not kept:
            break
        decision: list[tuple[Candidate, Rolled]] = []
        for glass in sorted({c.glass.id for c in kept}):
            group = [c for c in kept if c.glass.id == glass]
            tried = sample(group, rng, FREEING, EASING)
            made = [roll(table, before, c) for c in tried]
            again = [roll(table, before, tried[0]) for _ in range(REPEATS - 1)]
            others = [o for o in seen if o.id != glass]
            found.append(
                {
                    "scope": "a glass",
                    "table": seed,
                    "step": step,
                    "glass": glass,
                    "candidates": len(group),
                    "finishing": sum(c.freeing for c in group),
                    "finishing_labels": [m.label for m, c in zip(made, tried, strict=True) if c.freeing],
                    "easing_labels": [m.label for m, c in zip(made, tried, strict=True) if not c.freeing],
                    # Where the finishing pushes aim, before anything is made:
                    # the contour the enumerator stops each heading on.
                    "finishing_margins": [room_at(c.push.aim, others) for c in tried if c.freeing],
                    "repeat_labels": [made[0].label, *(m.label for m in again)],
                    "repeat_seen_labels": [made[0].seen_gained, *(m.seen_gained for m in again)],
                    "rule_label": _rule_label(group, tried, made),
                    "best_label": max(m.label for m in made),
                    "toppled": sum(m.toppled for m in made),
                }
            )
            decision += list(zip(tried, made, strict=True))
        found.append(_decision(seed, step, kept, decision))

        restore(table, before)
        teacher = rule_choice(kept)
        if teacher is None:
            break
        table.push(teacher.push)
        if not all(g.standing for g in table.look()):
            break
    return found


def _decision(seed: int, step: int, kept: list[Candidate], made: list[tuple[Candidate, Rolled]]) -> dict:
    """The whole table at one moment: the list the ranker is really handed."""
    tried = [c for c, _ in made]
    results = [r for _, r in made]
    return {
        "scope": "a decision",
        "table": seed,
        "step": step,
        "glass": None,
        "candidates": len(kept),
        "finishing": sum(c.freeing for c in kept),
        "finishing_labels": [r.label for c, r in made if c.freeing],
        "easing_labels": [r.label for c, r in made if not c.freeing],
        "finishing_margins": [],
        "repeat_labels": [],
        "repeat_seen_labels": [],
        "rule_label": _rule_label(kept, tried, results),
        "best_label": max(r.label for r in results),
        "toppled": sum(r.toppled for r in results),
    }


def _rule_label(group: list, tried: list, made: list) -> float | None:
    """What the printed rule's own choice gained, if that choice was one of the ones made."""
    choice = rule_choice(group)
    for candidate, result in zip(tried, made, strict=True):
        if candidate is choice:
            return result.label
    return None


def spread(values: list[float]) -> dict:
    """How far apart the labels in one group are, in millimetres of room gained."""
    array = 1000 * np.array(values, dtype=np.float64)
    return {
        "count": len(values),
        "range": float(array.max() - array.min()),
        "deviation": float(array.std(ddof=1)) if len(values) > 1 else 0.0,
    }


def summarise(found: list[dict], scope: str) -> dict:
    here = [g for g in found if g["scope"] == scope]
    finishing = [spread(g["finishing_labels"]) for g in here if len(g["finishing_labels"]) > 1]
    easing = [spread(g["easing_labels"]) for g in here if len(g["easing_labels"]) > 1]
    margins = [spread(g["finishing_margins"]) for g in here if len(g["finishing_margins"]) > 1]
    repeated = [spread(g["repeat_labels"]) for g in here if len(g["repeat_labels"]) > 1]
    by_camera = [spread(g["repeat_seen_labels"]) for g in here if len(g["repeat_seen_labels"]) > 1]
    rule_gap = [1000 * (g["best_label"] - g["rule_label"]) for g in here if g["rule_label"] is not None]
    rule_fell = sum(g["rule_label"] == TOPPLED for g in here if g["rule_label"] is not None)
    sizes = [g["candidates"] for g in here]
    return {
        "groups": len(here),
        "candidates_per_group_median": float(np.median(sizes)) if sizes else 0.0,
        "groups_with_a_job_finishing_push": sum(g["finishing"] > 0 for g in here),
        "within_group_spread_mm": {
            "job finishing": _middle(finishing),
            "easing": _middle(easing),
            "the same push made again": _middle(repeated),
            "the same push made again, as the camera measures it": _middle(by_camera),
        },
        "where_the_job_finishing_pushes_aim_mm": _middle(margins),
        "best_possible_over_the_printed_rule_mm": {
            "groups": len(rule_gap),
            "median": round(float(np.median(rule_gap)), 3) if rule_gap else None,
            "mean": round(float(np.mean(rule_gap)), 3) if rule_gap else None,
            "worst": round(float(np.max(rule_gap)), 3) if rule_gap else None,
            "groups_where_the_rule_was_best": int(sum(gap <= 1e-9 for gap in rule_gap)),
            "groups_where_the_rule_toppled_a_glass": rule_fell,
        },
        "toppled": sum(g["toppled"] for g in here),
    }


def _middle(spreads: list[dict]) -> dict:
    if not spreads:
        return {"groups": 0}
    return {
        "groups": len(spreads),
        "candidates_median": float(np.median([s["count"] for s in spreads])),
        "range_mm_median": round(float(np.median([s["range"] for s in spreads])), 3),
        "range_mm_mean": round(float(np.mean([s["range"] for s in spreads])), 3),
        "deviation_mm_median": round(float(np.median([s["deviation"] for s in spreads])), 3),
    }


def report(result: dict, scope: str) -> str:
    here = result[scope]
    finishing = here["within_group_spread_mm"]["job finishing"]
    easing = here["within_group_spread_mm"]["easing"]
    gap = here["best_possible_over_the_printed_rule_mm"]
    return (
        f"\n{here['groups']} groups of the kind '{scope}', "
        f"{here['candidates_per_group_median']:.0f} candidates in the middle one, "
        f"{here['groups_with_a_job_finishing_push']} with a push that finishes the job\n"
        f"  room gained, best to worst within one group, millimetres:\n"
        f"    job-finishing pushes  {finishing.get('range_mm_median', 0):8.3f} median, "
        f"{finishing.get('range_mm_mean', 0):.3f} mean, over {finishing['groups']} groups\n"
        f"    easing pushes         {easing.get('range_mm_median', 0):8.3f} median, "
        f"{easing.get('range_mm_mean', 0):.3f} mean, over {easing['groups']} groups\n"
        f"  the best push in a group over the printed rule's choice: {gap['median']} mm median, "
        f"{gap['worst']} mm worst, and the rule was already best in "
        f"{gap['groups_where_the_rule_was_best']} of {gap['groups']}\n"
        f"  the printed rule's own choice toppled a glass in "
        f"{gap['groups_where_the_rule_toppled_a_glass']} of them"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=60)
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args()

    started = time.time()
    with Pool(arguments.workers) as pool:
        found = [group for part in pool.map(groups, range(arguments.tables), chunksize=2) for group in part]
    result = {
        "tables": arguments.tables,
        "seconds": round(time.time() - started),
        "pushes": sum(
            len(g["finishing_labels"]) + len(g["easing_labels"]) + max(0, len(g["repeat_labels"]) - 1)
            for g in found
            if g["scope"] == "a glass"
        ),
        "a glass": summarise(found, "a glass"),
        "a decision": summarise(found, "a decision"),
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")

    floor = result["a glass"]["within_group_spread_mm"]
    by_record = floor["the same push made again"].get("range_mm_median", 0)
    by_camera = floor["the same push made again, as the camera measures it"].get("range_mm_median", 0)
    print(report(result, "a glass"))
    print(report(result, "a decision"))
    print(
        f"\nthe floor under both: the same push made {REPEATS} times moves the label by "
        f"{by_record:.3f} mm by the simulator's record and {by_camera:.3f} mm as the camera "
        f"measures it\n"
        f"where the job-finishing pushes aim: "
        f"{result['a glass']['where_the_job_finishing_pushes_aim_mm'].get('range_mm_median', 0):.3f} mm "
        f"between the widest and narrowest room left within a group\n"
        f"\n{result['pushes']} pushes made in {result['seconds']}s; saved to {REPORT}"
    )


if __name__ == "__main__":
    main()
