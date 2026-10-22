"""Fit the ranker: enumerate candidates on training tables, make every sampled one, label it.

What is fitted is one number per candidate push --- how much clear room the
whole table gained, with a toppled glass counted as the worst push there is.
Only the order of those numbers is ever used.

Where it saves: the trees in ``model/ranker.joblib``, and the measurements in
``training.json`` beside this file --- the row count, what each input
contributed and the validation numbers.
The labelled rows are cached in ``data/rows.npz``, so fitting again pushes
nothing again.

The tables are drawn from below the bench's dividing line, so nothing here is
a table the solution is marked on. The validation tables are a separate band,
also below it.

    pixi run python train.py
    pixi run python train.py --tables 300
    pixi run python train.py --refresh        # push again rather than reuse data/rows.npz

Making every candidate in a group would be hundreds of pushes for one glass,
which is hours rather than the minutes this method is supposed to cost. So a
group contributes at most FREEING_PER_GROUP of the pushes that finish the job
--- there are rarely more --- and an even sample of EASING_PER_GROUP of the
rest. ``spread.py`` measures what is inside a group before any of this is
believed.
"""

from __future__ import annotations

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import features
import numpy as np
from candidates import Candidate, nudge, rule_choice, survivors
from ranker import MODEL, Ranker
from rollout import Before, capture, restore, roll

from bench import TEST_SEEDS, Bench, Seen

DATA = Path(__file__).parent / "data" / "rows.npz"
REPORT = Path(__file__).parent / "training.json"

# Decisions recorded per table: the opening one, then the table as the printed
# rule leaves it. The second is the kind of state a run really plans in.
STEPS_PER_TABLE = 2
FREEING_PER_GROUP = 3
EASING_PER_GROUP = 5

# A glass with this much room to spare is racked rather than pushed, as the run
# does, so the states recorded here are the states the run plans from.
TAKE_MARGIN = 0.005

# Validation tables: never fitted on, and below the dividing line, so they are
# not the held-out ones either.
VALIDATION_SEEDS = 9000

COLUMNS = ("gained", "toppled", "freeing", "travel", "eased", "group", "decision", "table")


def sample(group: list[Candidate], rng: np.random.Generator, freeing: int, easing: int) -> list[Candidate]:
    """At most ``freeing`` job-finishing pushes and ``easing`` of the rest, drawn evenly."""
    finishing = [c for c in group if c.freeing]
    loosening = [c for c in group if not c.freeing]
    keep = [finishing[i] for i in _draw(len(finishing), freeing, rng)]
    return keep + [loosening[i] for i in _draw(len(loosening), easing, rng)]


def _draw(count: int, most: int, rng: np.random.Generator) -> list[int]:
    if count <= most:
        return list(range(count))
    return sorted(rng.choice(count, size=most, replace=False).tolist())


def table_rows(seed: int) -> dict[str, np.ndarray]:
    """Every labelled candidate from one table, over STEPS_PER_TABLE decisions."""
    rng = np.random.default_rng(seed)
    table = Bench(seed)
    rows: list[np.ndarray] = []
    labels: list[tuple[float, ...]] = []
    for step in range(STEPS_PER_TABLE):
        before = after_racking(table)
        if before is None or len(before.seen) < 2:
            break
        seen = before.seen
        kept, _ = survivors(seen, set())
        if not kept:
            break
        for glass in {c.glass.id for c in kept}:
            group = [c for c in kept if c.glass.id == glass]
            for candidate in sample(group, rng, FREEING_PER_GROUP, EASING_PER_GROUP):
                made = roll(table, before, candidate)
                rows.append(features.row(candidate.glass, _others(seen, glass), candidate.push))
                labels.append(
                    (
                        made.label,
                        made.gained,
                        float(made.toppled),
                        float(candidate.freeing),
                        candidate.push.travel,
                        candidate.eased,
                        float(seed * 100 + glass + 10_000_000 * step),
                        float(seed + 10_000_000 * step),
                        float(seed),
                    )
                )
        # The rule's own choice moves the table on, so the next decision is
        # taken on a table one push further in.
        restore(table, before)
        teacher = rule_choice(kept)
        if teacher is None:
            break
        table.push(teacher.push)
        if not all(glass.standing for glass in table.look()):
            break
    if not rows:
        return _empty()
    labelled = np.array(labels, dtype=np.float64)
    return {
        "rows": np.stack(rows),
        "label": labelled[:, 0],
        **{name: labelled[:, i + 1] for i, name in enumerate(COLUMNS)},
    }


def _empty() -> dict[str, np.ndarray]:
    return {"rows": np.zeros((0, features.INPUTS)), "label": np.zeros(0), **{c: np.zeros(0) for c in COLUMNS}}


def after_racking(table: Bench) -> Before | None:
    """Take every glass that has room, as the run does, then hold the table still.

    None once a glass is down, because nothing here stands one back up.
    """
    while True:
        before = capture(table)
        if not all(glass.standing for glass in before.seen):
            return None
        ready = [glass for glass in before.seen if nudge.room(glass, before.seen, TAKE_MARGIN)]
        if not ready:
            return before
        for glass in ready:
            table.take(glass.id)


def _others(seen: list[Seen], glass: int) -> list[Seen]:
    return [o for o in seen if o.id != glass]


def collect(seeds: list[int], workers: int) -> dict[str, np.ndarray]:
    started = time.time()
    with Pool(workers) as pool:
        parts = pool.map(table_rows, seeds, chunksize=4)
    joined = {key: np.concatenate([part[key] for part in parts]) for key in parts[0]}
    print(
        f"{len(seeds)} tables, {len(joined['rows'])} candidates made in {time.time() - started:.0f}s: "
        f"{int(joined['freeing'].sum())} finish the job, {int(joined['toppled'].sum())} toppled a glass"
    )
    return joined


def pairs_right(label: np.ndarray, score: np.ndarray) -> tuple[int, int]:
    """How many pairs within one group the scores put in the right order, and how many pairs were not ties."""
    right = total = 0
    for i in range(len(label)):
        for j in range(i + 1, len(label)):
            if label[i] == label[j]:
                continue
            total += 1
            right += (score[i] > score[j]) == (label[i] > label[j])
    return right, total


def regrets(data: dict[str, np.ndarray], score: np.ndarray, key: str = "group") -> dict:
    """How much room the top-ranked push gives up against the best in its group, millimetres.

    Beside it, the printed rule's own choice and what an arbitrary pick costs.
    ``key`` is "group" for one glass's candidates and "decision" for every
    candidate on the table at one moment, which is the list the run sorts.
    """
    model, rule, arbitrary, right, pairs = [], [], [], 0, 0
    offered = taken = 0
    for group in np.unique(data[key]):
        here = data[key] == group
        label = data["label"][here]
        if len(label) < 2:
            continue
        best = label.max()
        mine = score[here]
        top = int(np.argmax(mine))
        model.append(best - label[top])
        rule.append(best - label[_rule_pick(data, here)])
        arbitrary.append(best - label.mean())
        # The run is scored on glasses that end up grippable, not on
        # millimetres, so whether the top pick finishes a glass matters more
        # than the room it gains. The printed rule takes one whenever one is
        # offered, by construction.
        if data["freeing"][here].any():
            offered += 1
            taken += int(data["freeing"][here][top] > 0)
        got, total = pairs_right(label, mine)
        right, pairs = right + got, pairs + total
    return {
        "groups": len(model),
        "pairs_right": round(right / pairs, 3) if pairs else None,
        "groups_offering_a_job_finishing_push": offered,
        "where_the_rankers_top_pick_finishes_the_job": taken,
        "regret_mm_median": {
            "ranker": round(1000 * float(np.median(model)), 2),
            "printed rule": round(1000 * float(np.median(rule)), 2),
            "an arbitrary pick": round(1000 * float(np.median(arbitrary)), 2),
        },
        "regret_mm_mean": {
            "ranker": round(1000 * float(np.mean(model)), 2),
            "printed rule": round(1000 * float(np.mean(rule)), 2),
            "an arbitrary pick": round(1000 * float(np.mean(arbitrary)), 2),
        },
    }


def _rule_pick(data: dict[str, np.ndarray], here: np.ndarray) -> int:
    """Which of a group the printed rule would take: shortest job-finishing, else most easing."""
    freeing, travel, eased = data["freeing"][here], data["travel"][here], data["eased"][here]
    if freeing.any():
        return int(np.where(freeing > 0, travel, np.inf).argmin())
    return int(np.lexsort((travel, -eased))[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=200)
    parser.add_argument("--validation", type=int, default=60)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh", action="store_true", help="push again rather than reuse data/rows.npz")
    arguments = parser.parse_args()
    assert arguments.tables <= VALIDATION_SEEDS
    assert VALIDATION_SEEDS + arguments.validation <= TEST_SEEDS

    if DATA.exists() and not arguments.refresh:
        stored = np.load(DATA)
        fitting = {key: stored[key] for key in stored.files if not key.startswith("check_")}
        checking = {key[6:]: stored[key] for key in stored.files if key.startswith("check_")}
        print(f"{len(fitting['rows'])} candidates from {DATA}")
    else:
        DATA.parent.mkdir(exist_ok=True)
        fitting = collect(list(range(arguments.tables)), arguments.workers)
        checking = collect(
            list(range(VALIDATION_SEEDS, VALIDATION_SEEDS + arguments.validation)), arguments.workers
        )
        np.savez_compressed(DATA, **fitting, **{f"check_{k}": v for k, v in checking.items()})

    started = time.time()
    model = Ranker.fit(fitting["rows"], fitting["label"])
    seconds = time.time() - started
    model.save()

    scored = model(checking["rows"])
    check = regrets(checking, scored)
    decisions = regrets(checking, scored, "decision")
    report = {
        "rows": int(len(fitting["rows"])),
        "tables": int(len(np.unique(fitting["table"]))),
        "finish_the_job": int(fitting["freeing"].sum()),
        "toppled": int(fitting["toppled"].sum()),
        "room_gained_mm_median": round(1000 * float(np.median(fitting["gained"])), 2),
        "trees": int(model.trees.n_estimators),
        "depth": int(model.trees.max_depth),
        "fitting_seconds": round(seconds, 1),
        "importances": [[name, round(float(value), 3)] for name, value in model.importances()],
        "validation": {
            "rows": int(len(checking["rows"])),
            "a glass": check,
            "a decision": decisions,
        },
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")

    print(f"\nfitted {model.trees.n_estimators} trees on {report['rows']} rows in {seconds:.1f}s -> {MODEL}")
    print("what mattered:")
    for name, value in model.importances():
        print(f"  {value:5.2f}  {name}")
    print(f"\nvalidation, {report['validation']['rows']} candidates")
    for scope, numbers in (("a glass", check), ("a decision", decisions)):
        mean = numbers["regret_mm_mean"]
        print(
            f"  over {numbers['groups']} groups of the kind '{scope}': "
            f"{numbers['pairs_right']} of the pairs in the right order\n"
            f"    room given up against the best in the group, mean: "
            f"ranker {mean['ranker']} mm, printed rule {mean['printed rule']} mm, "
            f"an arbitrary pick {mean['an arbitrary pick']} mm\n"
            f"    the ranker's top pick finishes the job in "
            f"{numbers['where_the_rankers_top_pick_finishes_the_job']} of the "
            f"{numbers['groups_offering_a_job_finishing_push']} groups that offer one, "
            f"where the printed rule always takes it"
        )
    print(f"  saved to {REPORT}")


if __name__ == "__main__":
    main()
