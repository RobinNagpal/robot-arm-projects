"""Run the written rules over the held-out scenes, score them, and write the numbers.

    pixi run python 01-rules-on-the-table/run.py --scenes 20
    pixi run python 01-rules-on-the-table/run.py --crowded --show

There is no training step to run first, which is this solution's whole claim:
not one number in the folder was fitted to anything. The same scenes, pictures
and scorecard as every other solution here, so the results files can be set side
by side.

**A survey is three pictures, not one.** At the cell's own survey height one
picture does not hold the glass zone, because a rim seen from above leans away
from the point below the camera, so the cell stands at the stations ``data.py``
works out and this file asks the rules about each picture on its own. The three
answers are then brought together and a glass is counted once, which is
``marking.survey``'s job and the same for all six.

**Turning a mask into a place and a width is the bench's step, not this
solution's.** This solution contributes only the masks, so a difference in the
scorecard belongs to the mask.

A solution is handed the picture and the kind of glass on the table, which the
cell is told, and never the scene behind it: no list of glasses and no true mask.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import find

import data
import marking
from scoring import Scorecard

# How many held-out scenes a run scores unless it is told otherwise.
SCENES = 20


def summary(card: Scorecard, scenes: int, crowded: bool) -> dict:
    """The shared numbers, and the three facts that identify this solution."""
    return marking.summary("01-rules-on-the-table", card, scenes, crowded) | {
        "model": "none: written rules over the depth readings",
        "grouping distance mm": round(1000 * find.GROUPING, 1),
        "fitted here": "nothing",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenes", type=int, default=SCENES, help=f"held-out scenes (default {SCENES})")
    parser.add_argument("--show", action="store_true", help="print each scene as it is scored")
    parser.add_argument(
        "--crowded",
        action="store_true",
        help="score on crowded layouts, where one glass really does hide another",
    )
    given = parser.parse_args()
    if given.scenes < 1:
        raise SystemExit(f"--scenes {given.scenes}: there would be nothing to work on")

    finder = find.load()
    card = Scorecard()
    for example in data.held_out(given.scenes, hard=given.crowded):
        kept, station = marking.survey(finder, example, card)
        marking.score(card, example, kept, station)
        if given.show:
            print(f"seed {example.seed}  {len(example.glasses)} out, {len(kept)} found")

    result = summary(card, given.scenes, given.crowded)
    marking.show(result)
    tail = "-crowded" if given.crowded else ""
    save = Path(__file__).parent / f"results{tail}.json"
    save.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
