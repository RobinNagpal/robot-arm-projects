"""Run the programmed pipeline on the held-out scenes, and score it.

The same scenes, pictures and scorecard as problem-2-learned/run.py, so the
two results files can be set side by side.

    pixi run python run.py              # 50 held-out scenes
    pixi run python run.py --scenes 5 --show
"""

from __future__ import annotations

import argparse
from pathlib import Path

from work_cell.glasses.perception import NotMeasurable

import render
import views
from find import find_glasses
from measure import measure
from scoring import Scorecard

# How many places to try before handing a glass over. Each try is an arm move.
TRIES = 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=50)
    parser.add_argument("--show", action="store_true", help="print each glass")
    arguments = parser.parse_args()
    card = Scorecard()

    for seed in range(render.TEST_SEEDS, render.TEST_SEEDS + arguments.scenes):
        glasses = render.scene(seed)
        top = render.render(glasses, render.top_pose())
        found = find_glasses(top)
        matches = card.found(glasses, top, [f.pixels for f in found], [(f.seen.x, f.seen.y) for f in found])

        for item, index in zip(found, matches, strict=True):
            if index is None:
                continue
            others = [f.seen for f in found if f is not item]
            ranked = views.ranked(item.seen, others)
            if not ranked:
                card.handed_over("no allowed place")
                continue

            def pose_for(a, item=item):
                return render.side_pose(item.seen.x, item.seen.y, a)

            card.view(glasses, index, ranked[0][1], [a for _, a in ranked], pose_for, render.render)

            # Measure from the widest gap first; if the picture fails its
            # checks, the next. Where no place is fully clear, the ones that
            # overlap least are still tried: a sliver of overlap can leave the
            # outline good enough, and the checks are what say whether it did.
            reasons = []
            for attempt, (_, angle) in enumerate(ranked[:TRIES]):
                try:
                    profile = measure(render.render(glasses, pose_for(angle)), item.seen)
                except NotMeasurable as reason:
                    reasons.append(str(reason))
                    continue
                card.count["retries"] += attempt
                height, width = card.measured(profile, glasses[index])
                break
            else:
                card.handed_over("no clean picture")
                if arguments.show:
                    print(f"seed {seed} glass {index} handed over: {reasons}")
                continue
            if arguments.show:
                glass = glasses[index]
                print(
                    f"seed {seed} {glass.kind:20s} {glass.total_height * 1000:5.0f} mm tall  "
                    f"tries {attempt + 1}  height {1000 * height:+6.1f} mm  width {1000 * width:4.1f} mm"
                )

    print(f"\nretries after a failed check: {card.count['retries']}")
    card.report(arguments.scenes, Path(__file__).parent / "results.json")


if __name__ == "__main__":
    main()
