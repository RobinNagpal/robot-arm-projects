"""Clear the held-out tables with the ranked geometry, and score it.

The same tables, measurements, jaw and scorecard as the other solutions, and
the same loop as ``01-one-fixed-nudge/run.py``: look, rack every glass that
has room, settle the tipping question, enumerate, choose, push, look again.
The one difference is the choosing. There the printed rule takes the shortest
push that finishes the job; here the fitted model scores every survivor and
the arm makes the first push on the sorted list.

``--rule`` runs the same loop with the model deleted, which is the comparison
that matters: both sides see exactly the same candidates, so the gap between
them is the value of the ordering and nothing else.

    pixi run python run.py                 # 50 held-out tables; writes results.json
    pixi run python run.py --rule          # the same, with the printed rule; writes rule.json
    pixi run python run.py --tables 5 --show
    pixi run python run.py --tables 3 --film 3   # videos of the first 3 in videos/
"""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter
from pathlib import Path

import ranker
from candidates import nudge, rule_choice, survivors

import bench
from film import FilmedBench
from scoring import Scorecard

# A glass with this much room to spare is taken. Solution 1's number, so the
# two runs rack on the same rule: three standard deviations of the measurement
# error in the gap.
TAKE_MARGIN = 0.005

VIDEOS = Path(__file__).parent / "videos"


def by_model(model: ranker.Scorer):
    """Choose with the trees: every survivor scored, the best one taken."""
    return lambda seen, skip: ranker.choose(seen, skip, model)


def by_rule(seen: list[bench.Seen], skip: set[int]) -> tuple[bench.Push | None, dict[int, str]]:
    """Choose with the model deleted. This is solution 1's printed rule over the same set."""
    kept, why = survivors(seen, skip)
    best = rule_choice(kept)
    return (best.push if best else None), why


def clear(table: bench.Bench, pick, show: bool = False, watch=None) -> dict[int, str]:
    """Take what can be taken, push the rest apart, repeat. Returns what was refused, and why.

    ``watch(seen, push, felt, probe)`` is called after every push, which is how
    ``demos.py`` records a demonstration without a second copy of this loop.
    """
    pushed: Counter = Counter()
    proven: set[int] = set()
    tipped: dict[int, str] = {}
    while True:
        seen = table.look()
        if not all(glass.standing for glass in seen):
            # Nothing in this project stands a glass back up, and the arm does
            # not touch anything near one lying on the table.
            return {glass.id: "stopped: a glass fell over" for glass in seen if glass.standing}

        ready = [glass for glass in seen if nudge.room(glass, seen, TAKE_MARGIN)]
        if ready:
            for glass in ready:
                table.take(glass.id)
            continue
        if not seen:
            return {}

        worn = {g for g, n in pushed.items() if n >= bench.PUSHES_PER_GLASS}
        push, why = pick(seen, worn | set(tipped))
        why |= tipped
        if push is None or pushed.total() >= bench.PUSHES_PER_TABLE:
            spent = "push budget spent" if push is not None else "still without room after pushing"
            return {glass.id: why.get(glass.id, spent) for glass in seen}

        glass = next(g for g in seen if g.id == push.glass)
        if nudge.needs_probe(glass, proven):
            # Friction decides this one, and the model is not asked about it.
            # Push a little and look: a glass that slid has moved; one that
            # tipped leaned and fell back where it was.
            before = where(table, push.glass)
            short = nudge.probe(push)
            felt = table.push(short)
            pushed[push.glass] += 1
            if watch:
                watch(seen, short, felt, True)
            after = where(table, push.glass)
            moved = math.dist(before, after) if after else 0.0
            if after and moved >= nudge.PROBE_MOVED:
                proven.add(push.glass)
            else:
                tipped[push.glass] = "tipped when tried"
            if show:
                print(f"  probe glass {push.glass}: moved {1000 * moved:.1f} mm")
            continue

        felt = table.push(push)
        pushed[push.glass] += 1
        if watch:
            watch(seen, push, felt, False)
        if show:
            print(
                f"  push glass {push.glass} {1000 * push.travel:.0f} mm: "
                f"{'blocked' if felt.blocked else 'no touch' if felt.touched is None else 'touched'}"
                f"{', jammed' if felt.jammed else ''}"
            )


def where(table: bench.Bench, glass: int) -> tuple[float, float] | None:
    """Where a glass stands, averaged over several looks. None if it is down."""
    looks = [next(g for g in table.look() if g.id == glass) for _ in range(nudge.LOOKS_PER_PROBE)]
    if not all(g.standing for g in looks):
        return None
    return sum(g.x for g in looks) / len(looks), sum(g.y for g in looks) / len(looks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=50)
    parser.add_argument("--rule", action="store_true", help="the printed rule, with the model deleted")
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    arguments = parser.parse_args()
    pick = by_rule if arguments.rule else by_model(ranker.Ranker.load())
    card = Scorecard()

    started = time.time()
    for i, seed in enumerate(range(bench.TEST_SEEDS, bench.TEST_SEEDS + arguments.tables)):
        filmed = i < arguments.film
        table = FilmedBench(seed, "ranked") if filmed else bench.Bench(seed)
        if arguments.show:
            print(f"seed {seed} {table.glasses[0].kind}, {len(table.glasses)} glasses")
        clock = time.time()
        refused = clear(table, pick, arguments.show)
        # The scorecard takes the bench's own physics off this, so what is
        # reported per push is the choosing.
        outcome = card.scene(table, refused, time.time() - clock)
        if arguments.show:
            print(f"  {outcome}; refused {refused or 'none'}")
        if filmed:
            racked = sum(table.taken.values())
            table.save(VIDEOS / f"table-{seed}.mp4", f"{outcome}: racked {racked}, refused {len(refused)}")

    print(f"\n{time.time() - started:.0f}s for {arguments.tables} tables")
    if arguments.film:
        print(f"videos of the first {min(arguments.film, arguments.tables)} in {VIDEOS}/")
    # Only the full held-out run is a result; anything shorter must not overwrite one.
    name = "rule.json" if arguments.rule else "results.json"
    if arguments.tables != 50:
        name = "partial.json"
    card.report(Path(__file__).parent / name)


if __name__ == "__main__":
    main()
