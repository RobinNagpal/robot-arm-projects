"""Run the teacher on training tables and write down what the jaw did.

Nothing here invents a path. Solution 2 is run unchanged on tables drawn
from below the bench's dividing line, and for every push it makes two things
are kept: the straight-down picture of the table at the moment it decided,
and ``Record.waypoints``, the path the jaw really followed. That pair is one
demonstration. Replaying the waypoints through ``Bench.follow`` reproduces
the push, which is what makes a parameterised teacher usable by a policy
that emits trajectories.

**What is dropped, and why it is counted.** A cloned policy copies whatever
is in its data, so a push that toppled a glass is a label like any other.
Only the pushes that worked are kept: nothing fell, nothing left the glass
zone, the jaw touched what it went for and did not jam, and the table gained
room. The 5 mm test pushes that settle whether a glass slides are not pushes
at the task and are dropped too. Every drop is counted by its reason and
written into ``data/collection.json``, because filtering by outcome thins
the data exactly on the tables the teacher found hard, and that thinning is
invisible unless it is counted.

**Refusals are kept as refusals.** A glass the teacher declined to push is a
result. The count and the reasons go into the same summary. Nothing trains
on them: the same limit is evaluated in front of the policy at run time, so
a refusal never needs to be learned.

**The outcome is read from the simulator's record**, which the bench allows
as a training label on training tables and nowhere else. Nothing that
decides a push reads it, here or at run time.

**The pictures are stored at the size the policy reads**, not at the size the
bench renders, which is what keeps a set of this size in memory. See
``pictures.py``: change that size and these files have to be made again.

    pixi run python 03-imitation-from-demonstrations/collect.py
    pixi run python 03-imitation-from-demonstrations/collect.py --tables 50 --workers 4
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import teacher  # first: it is what puts solution 2's folder on the path for ``rollout``
from chunks import CHUNK, push_segment, resample, to_action
from pictures import shrink
from rollout import truth
from teacher import nudge

from bench import KINDS, STANDING_TILT_DEG, TEST_SEEDS, Bench, in_zone
from top_view import TopCamera

HERE = Path(__file__).parent
DATA = HERE / "data"
DEMOS = DATA / "demos.npz"
CHECK = DATA / "validation.npz"
SUMMARY = DATA / "collection.json"

# Demonstrations start here rather than at table 0, so none of them is a
# table solution 2's own ranker was fitted on. Its fitting band is 0 to 200
# and its validation band starts at 9000; both are below the dividing line,
# as these are.
FIRST_TABLE = 1000
# Tables held back from fitting, to say how far the student is from the
# teacher on pictures it never saw. That is a training diagnostic and not the
# score: the score is the outcome, and run.py measures it.
CHECK_TABLE = 8000


class Watched(Bench):
    """One table, with the picture and the table's own state kept before every push.

    The teacher is not changed to produce demonstrations. It pushes as it
    always does and this records around it.
    """

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.camera = TopCamera(self)
        self.pictures: list[np.ndarray] = []
        self.shortfalls: list[float] = []

    def push(self, push):
        # Stored at the size the policy reads, so a few thousand
        # demonstrations are a gigabyte rather than five.
        self.pictures.append(shrink(self.camera.view())[0])
        self.shortfalls.append(nudge.shortfall(truth(self)))
        return super().push(push)

    def close(self) -> None:
        self.camera.close()


def dropped_because(record, probe: bool, table: Bench, before: float) -> str | None:
    """Why this push is not a demonstration, or None if it is one.

    The order matters only for the counting: a push that both toppled a glass
    and jammed is counted once, under the worse of the two.
    """
    if probe:
        return "a 5 mm test push, not a push at the task"
    if any(table.tilt(i) >= STANDING_TILT_DEG for i in table.on_table()):
        return "a glass toppled"
    if any(not in_zone(*table.position(i)) for i in table.on_table()):
        return "a glass left the glass zone"
    felt = record.felt
    if felt.blocked:
        return "blocked on the way down"
    if felt.touched is None:
        return "never touched anything"
    if felt.jammed:
        return "jammed"
    if not push_segment(record.waypoints):
        return "no path at push height to copy"
    if before - nudge.shortfall(truth(table)) <= 0.0:
        return "the table gained no room"
    return None


_pick = None


def _load_teacher() -> None:
    global _pick
    _pick = teacher.pick_pushes()


def demonstrate(seed: int) -> dict:
    """One table cleared by the teacher. Returns its demonstrations and what was dropped."""
    table = Watched(seed)
    probes: list[bool] = []
    try:
        refused = teacher.clear(table, _pick, watch=lambda seen, push, felt, probe: probes.append(probe))
        pictures, actions, lengths = [], [], []
        drops: Counter = Counter()
        for record, picture, before, probe in zip(
            table.records, table.pictures, table.shortfalls, probes, strict=True
        ):
            why = dropped_because(record, probe, table, before)
            if why is not None:
                drops[why] += 1
                continue
            segment = push_segment(record.waypoints)
            lengths.append(len(segment))
            pictures.append(picture)
            actions.append(resample(to_action(segment), CHUNK))
        return {
            "table": seed,
            "kind": KINDS[seed % len(KINDS)],
            "pictures": pictures,
            "actions": actions,
            "lengths": lengths,
            "drops": dict(drops),
            "refused": dict(Counter(refused.values())),
            "glasses_refused": len(refused),
            "pushes": len(table.records),
        }
    finally:
        table.close()


def gather(seeds: list[int], workers: int) -> tuple[dict[str, np.ndarray], dict]:
    """Every demonstration from these tables, and the count of what was left out."""
    with Pool(workers, initializer=_load_teacher) as pool:
        tables = pool.map(demonstrate, seeds, chunksize=2)

    pictures = [picture for t in tables for picture in t["pictures"]]
    actions = [action for t in tables for action in t["actions"]]
    lengths = np.array([n for t in tables for n in t["lengths"]] or [0])
    drops: Counter = Counter()
    refused: Counter = Counter()
    for t in tables:
        drops.update(t["drops"])
        refused.update(t["refused"])
    data = {
        "pictures": np.asarray(pictures, dtype=np.uint8),
        "actions": np.asarray(actions, dtype=np.float32),
        "tables": np.array([t["table"] for t in tables for _ in t["actions"]], dtype=np.int64),
    }
    counts = {
        "tables": len(tables),
        "pushes": sum(t["pushes"] for t in tables),
        "kept": len(actions),
        "dropped": dict(drops.most_common()),
        "glasses_refused": sum(t["glasses_refused"] for t in tables),
        "refused_because": dict(refused.most_common()),
        # Broken down by the kind of glass on the table, because the thinning
        # is not the same on every kind and a total hides that.
        "by_kind": {kind: _for_kind(tables, kind) for kind in KINDS},
        "waypoints_per_push": {
            "chunk": CHUNK,
            "median": int(np.median(lengths)),
            "least": int(lengths.min()),
            "most": int(lengths.max()),
        },
    }
    return data, counts


def _for_kind(tables: list[dict], kind: str) -> dict:
    """What was kept, dropped and refused on the tables of one kind of glass."""
    mine = [t for t in tables if t["kind"] == kind]
    drops: Counter = Counter()
    refused: Counter = Counter()
    for t in mine:
        drops.update(t["drops"])
        refused.update(t["refused"])
    return {
        "tables": len(mine),
        "pushes": sum(t["pushes"] for t in mine),
        "kept": sum(len(t["actions"]) for t in mine),
        "dropped": dict(drops.most_common()),
        "glasses_refused": sum(t["glasses_refused"] for t in mine),
        "refused_because": dict(refused.most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=5200, help="training tables to run the teacher on")
    parser.add_argument("--check", type=int, default=300, help="held-back tables, for the fit diagnostic")
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args()
    assert FIRST_TABLE + arguments.tables <= CHECK_TABLE, "demonstrations must stay below the check band"
    assert CHECK_TABLE + arguments.check <= TEST_SEEDS, "nothing is drawn from above the dividing line"

    DATA.mkdir(exist_ok=True)
    started = time.time()
    fitting, counts = gather(list(range(FIRST_TABLE, FIRST_TABLE + arguments.tables)), arguments.workers)
    np.savez_compressed(DEMOS, **fitting)
    checking, check_counts = gather(
        list(range(CHECK_TABLE, CHECK_TABLE + arguments.check)), arguments.workers
    )
    np.savez_compressed(CHECK, **checking)

    summary = {"fitting": counts, "check": check_counts, "seconds": round(time.time() - started, 1)}
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    report(counts, DEMOS)
    report(check_counts, CHECK)
    print(f"\n{summary['seconds']:.0f}s; what was kept and dropped is in {SUMMARY}")


def report(counts: dict, path: Path) -> None:
    kept, pushes = counts["kept"], counts["pushes"]
    share = 100 * kept / pushes if pushes else 0.0
    print(
        f"\n{counts['tables']} tables, {pushes} pushes, {kept} kept ({share:.0f}%) -> {path}\n"
        f"  dropped  {counts['dropped'] or 'none'}\n"
        f"  refused  {counts['glasses_refused']} glasses {counts['refused_because'] or ''}\n"
        f"  by kind  "
        + ", ".join(f"{k.replace('_', ' ')} {v['kept']}/{v['pushes']}" for k, v in counts["by_kind"].items())
        + "\n"
        f"  the kept pushes are {counts['waypoints_per_push']['median']} waypoints long median "
        f"({counts['waypoints_per_push']['least']} to {counts['waypoints_per_push']['most']}), "
        f"resampled to {CHUNK}"
    )


if __name__ == "__main__":
    main()
