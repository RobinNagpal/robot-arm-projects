"""Write this solution's pushes out as demonstrations, for solutions 3 and 6 to learn from.

A demonstration is one run of a crowded table: what the arm saw, what it did,
and what happened, step by step. Collecting them costs nothing here, because
the teacher is a program and the tables are drawn from numbers: run this
solution over the training tables and every push it makes is a finished
example, with no person driving the arm.

**The format** is JSON lines --- one JSON object per line, in the order things
happened. Every length is in metres and every angle in radians, which is what
the bench uses. There are two kinds of line, told apart by ``record``.

``{"record": "push", ...}``

- `table` --- the bench table number. The same number always draws the same
  table, so a solution that reads pictures renders its own.
- `step` --- which push on that table, from 0.
- `kind` --- the one kind of glass on the table.
- `observation` --- one entry per glass still on the table, exactly what
  `look()` returned: `id`, `x`, `y`, `height`, `widest`, `foot`, `standing`.
  It carries problem 2's measurement error, as the arm's own reading does.
- `action` --- the parameterised push: `glass`, `start` (where the fingertips
  come down), `heading`, `reach`, `travel`, `aim`. The bench's own macro
  expands it into the jaw trajectory every solution here is judged on.
- `probe` --- true for the 5 mm test push that settles whether a glass slides
  rather than tips. It is not a push at the task.
- `waypoints` --- the path the jaw really followed, `[x, y, z, heading]` a
  waypoint, sampled by the bench every `WAYPOINT_PERIOD`. `z` is the middle of
  the jaw above the table top. This is the shared output in its other form: a
  policy that emits waypoints rather than push parameters is trained on this
  and hands them back through the bench's `follow()`.
- `felt` --- what the jaw reported: `blocked`, `touched`, `jammed`, `peak`,
  `pushed`.
- `room_gained_mm` --- how much clear room the whole table gained, from the
  looks before and after.
- `toppled` --- whether any glass was down after the push.

``{"record": "table", ...}``, one per table, last:

- `table`, `kind`, `glasses` --- the table.
- `pushes` --- how many push lines it has.
- `racked` --- how many glasses were picked up while they really had room.
- `outcome` --- the bench's own verdict: `done`, `incomplete` or `wrong`.
- `refused` --- glass id to the reason it was refused, as strings.

Two things to read before training on this. **A refusal is a result, not a
failure**: a table whose `refused` is not empty is a correct answer, and
dropping those tables teaches a student nothing about the situations this
teacher found hard. And **filtering to the pushes that worked biases which
tables are covered**, not only which actions, because the tables this solution
handles badly are the ones whose pushes are dropped. The outcome of every push
is recorded here so that a consumer can filter and count what it removed.

A solution that reads pictures renders its own: the table number and the step
are enough to draw the table again, and nothing is archived that can be
redrawn.

    pixi run python demos.py                      # 100 training tables
    pixi run python demos.py --tables 500 --first 0
    pixi run python demos.py --rule               # the teacher with its model deleted
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

import ranker
import run as runner
from rollout import room_gained

from bench import KINDS, TEST_SEEDS, Bench, Felt, Push, Seen
from scoring import Scorecard

DEMOS = Path(__file__).parent / "demonstrations" / "demos.jsonl"

_pick = None


def _load(rule: bool) -> None:
    global _pick
    _pick = runner.by_rule if rule else runner.by_model(ranker.Ranker.load())


def demonstrate(seed: int) -> list[dict]:
    """One table cleared, as a list of records."""
    table = Bench(seed)
    kind = KINDS[seed % len(KINDS)]
    lines: list[dict] = []

    def watch(seen: list[Seen], push: Push, felt: Felt, probe: bool) -> None:
        # An extra look, so this run is not bit for bit the scored one. It
        # costs nothing and it is what makes the push's outcome recordable.
        after = table.look()
        lines.append(
            {
                "record": "push",
                "table": seed,
                "step": len(lines),
                "kind": kind,
                "observation": [asdict(glass) for glass in seen],
                "action": asdict(push),
                "waypoints": [
                    [round(w.x, 5), round(w.y, 5), round(w.z, 5), round(w.heading, 5)]
                    for w in table.records[-1].waypoints
                ],
                "probe": probe,
                "felt": asdict(felt),
                "room_gained_mm": round(1000 * room_gained(seen, after), 3),
                "toppled": not all(glass.standing for glass in after),
            }
        )

    refused = runner.clear(table, _pick, watch=watch)
    outcome = Scorecard().scene(table, refused)
    lines.append(
        {
            "record": "table",
            "table": seed,
            "kind": kind,
            "glasses": len(table.glasses),
            "pushes": len(lines),
            "racked": sum(table.taken.values()),
            "outcome": outcome,
            "refused": {str(glass): reason for glass, reason in refused.items()},
        }
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=100)
    parser.add_argument("--first", type=int, default=0, help="first table number")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rule", action="store_true", help="the teacher with its model deleted")
    arguments = parser.parse_args()
    last = arguments.first + arguments.tables
    assert last <= TEST_SEEDS, "demonstrations come from below the bench's dividing line"

    started = time.time()
    DEMOS.parent.mkdir(exist_ok=True)
    with Pool(arguments.workers, initializer=_load, initargs=(arguments.rule,)) as pool:
        tables = pool.map(demonstrate, range(arguments.first, last), chunksize=4)
    with DEMOS.open("w") as out:
        for lines in tables:
            for line in lines:
                out.write(json.dumps(line) + "\n")

    ends = [lines[-1] for lines in tables]
    pushes = sum(end["pushes"] for end in ends)
    done = sum(end["outcome"] == "done" for end in ends)
    wrong = sum(end["outcome"] == "wrong" for end in ends)
    print(
        f"{arguments.tables} tables, {pushes} pushes, {sum(end['racked'] for end in ends)} glasses racked "
        f"in {time.time() - started:.0f}s\n"
        f"  {done} tables done, {len(ends) - done - wrong} incomplete, {wrong} wrong\n"
        f"  {sum(len(end['refused']) for end in ends)} glasses refused, with their reasons kept\n"
        f"saved to {DEMOS}"
    )


if __name__ == "__main__":
    main()
