"""Run the borrowed model over the held-out scenes, score it, and write its numbers.

    pixi run python 03-yolo-zero-shot/run.py --scenes 20
    pixi run python 03-yolo-zero-shot/run.py --crowded --show

There is no training step to run first, which is the solution's whole claim: the
weights download themselves on the first picture and nothing in this folder is
fitted. The same scenes, pictures and scorecard as every other solution here, so
the results files can be set side by side.

**A survey is three pictures, not one.** At the cell's own survey height one
picture does not hold the glass zone, because a rim seen from above leans away
from the point below the camera, so the cell stands at three stations and this
file asks the model about each picture on its own. The three answers are then
brought together and a glass is counted once. Which of a place's reports is kept
is decided by how far the glass stood from the point below that station's camera:
nearest first, because a glass directly under the camera has no splay and cannot
be cut off at the frame edge, so that station's report is the one to believe.

A solution is handed the picture and the kind of glass on the table, which the
cell is told, and never the scene behind it: no list of glasses and no true mask.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yolo_zero_shot

import data
import marking
from scoring import Scorecard

# Scorecard's own names for the counts this folder can claim. Repeated from
# scoring.py only for the run that found nothing at all, which cannot go through
# Scorecard.summary: there is no median position error to take.


def summary(card: Scorecard, scenes: int, crowded: bool) -> dict:
    """The shared numbers, and the three facts that identify this solution."""
    return marking.summary("03-yolo-zero-shot", card, scenes, crowded) | {
        "model": yolo_zero_shot.MODEL,
        "confidence bar": yolo_zero_shot.CONFIDENCE_BAR_SET_BY_HAND,
        "fitted here": "nothing",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the borrowed model on held-out scenes")
    parser.add_argument("--scenes", type=int, default=20)
    parser.add_argument("--show", action="store_true", help="print each scene as it is scored")
    parser.add_argument(
        "--crowded",
        action="store_true",
        help="score on crowded layouts, where one glass really does hide another",
    )
    given = parser.parse_args()
    if given.scenes < 1:
        raise SystemExit(f"--scenes {given.scenes}: there would be nothing to work on")

    finder = yolo_zero_shot.load()
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
