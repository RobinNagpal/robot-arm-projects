"""Clear the held-out tables with the programmed approach, and score it.

The same tables, measurements, jaw and scorecard as problem-3-learned/run.py,
so the two results files can be set side by side.

    pixi run python run.py              # 50 held-out scenes
    pixi run python run.py --scenes 5 --show
    pixi run python run.py --scenes 3 --film 3   # videos of the first 3 in videos/
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path

import bench
from film import FilmedBench
from plan import LOOKS_PER_PROBE, PROBE_MOVED, choose, needs_probe, probe, room
from scoring import Scorecard

# A glass that has room by this much more than it needs is taken. Three
# standard deviations of the measurement error in the gap: two positions at
# 0.5 mm and half the neighbour's width at 1.25 mm give 1.44 mm, so 4.3 mm.
TAKE_MARGIN = 0.005

# A glass pushed this often and still without room is left, with the reason.
PUSHES_PER_GLASS = 3
PUSHES_PER_TABLE = 15

VIDEOS = Path(__file__).parent / "videos"


def clear(table: bench.Bench, show: bool = False) -> dict[int, str]:
    """Take what can be taken, push the rest apart, repeat. Returns what was refused, and why."""
    pushed = Counter()
    proven: set[int] = set()
    tipped: dict[int, str] = {}
    while True:
        seen = table.look()
        if not all(glass.standing for glass in seen):
            # Nothing in this project stands a glass back up, and the arm does
            # not touch anything near one lying on the table.
            return {glass.id: "stopped: a glass fell over" for glass in seen if glass.standing}

        # Solution 1: every glass racked leaves more room for the rest.
        ready = [glass for glass in seen if room(glass, seen, TAKE_MARGIN)]
        if ready:
            for glass in ready:
                table.take(glass.id)
            continue
        if not seen:
            return {}

        worn = {g for g, n in pushed.items() if n >= PUSHES_PER_GLASS}
        push, why = choose(seen, worn | set(tipped))
        why |= tipped
        if push is None or pushed.total() >= PUSHES_PER_TABLE:
            spent = "push budget spent" if push is not None else "still without room after pushing"
            return {glass.id: why.get(glass.id, spent) for glass in seen}

        glass = next(g for g in seen if g.id == push.glass)
        if needs_probe(glass, proven):
            # Friction decides this one. Push a little and look: a glass that
            # slid has moved; one that tipped leaned and fell back where it was.
            before = where(table, push.glass)
            table.push(probe(push))
            pushed[push.glass] += 1
            after = where(table, push.glass)
            moved = math.dist(before, after) if after else 0.0
            if after and moved >= PROBE_MOVED:
                proven.add(push.glass)
            else:
                tipped[push.glass] = "tipped when tried"
            if show:
                print(f"  probe glass {push.glass}: moved {1000 * moved:.1f} mm")
            continue

        felt = table.push(push)
        pushed[push.glass] += 1
        if show:
            print(
                f"  push glass {push.glass} {1000 * push.travel:.0f} mm: "
                f"{'blocked' if felt.blocked else 'no touch' if felt.touched is None else 'touched'}"
                f"{', jammed' if felt.jammed else ''}"
            )


def where(table: bench.Bench, glass: int) -> tuple[float, float] | None:
    """Where a glass stands, averaged over several looks. None if it is down."""
    looks = [next(g for g in table.look() if g.id == glass) for _ in range(LOOKS_PER_PROBE)]
    if not all(g.standing for g in looks):
        return None
    return sum(g.x for g in looks) / len(looks), sum(g.y for g in looks) / len(looks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=50)
    parser.add_argument("--show", action="store_true", help="print each table")
    parser.add_argument("--film", type=int, default=0, help="film this many of the tables")
    arguments = parser.parse_args()
    card = Scorecard()

    for i, seed in enumerate(range(bench.TEST_SEEDS, bench.TEST_SEEDS + arguments.scenes)):
        filmed = i < arguments.film
        table = FilmedBench(seed, "programmed") if filmed else bench.Bench(seed)
        if arguments.show:
            print(f"seed {seed} {table.glasses[0].kind}, {len(table.glasses)} glasses")
        refused = clear(table, arguments.show)
        outcome = card.scene(table, refused)
        if arguments.show:
            print(f"  {outcome}; refused {refused or 'none'}")
        if filmed:
            racked = sum(table.taken.values())
            table.save(VIDEOS / f"table-{seed}.mp4", f"{outcome}: racked {racked}, refused {len(refused)}")

    if arguments.film:
        print(f"videos of the first {min(arguments.film, arguments.scenes)} in {VIDEOS}/")
    # Only the full held-out run is the result; anything shorter must not overwrite it.
    card.report(Path(__file__).parent / ("results.json" if arguments.scenes == 50 else "partial.json"))


if __name__ == "__main__":
    main()
