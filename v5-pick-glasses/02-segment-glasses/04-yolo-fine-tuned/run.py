"""Run the fine-tuned model over the held-out scenes, score it, and write results.json.

    pixi run python 04-yolo-fine-tuned/run.py
    pixi run python 04-yolo-fine-tuned/run.py --scenes 5 --crowded --show

The scenes come from above the bench's dividing line, which is the half no
training ever saw. The model is handed one picture and the kind of glass on the
table, which the cell is told, and never the scene behind the picture.

**A survey is three pictures, not one.** At the cell's own survey height one
picture does not hold the glass zone, so the cell stands at the stations
``data.py`` works out and this file asks the model about each picture on its
own. The three answers are then brought together and a glass is counted once.
Which of a place's reports is kept is decided by how far the glass stood from
the point below that station's camera, nearest first, because a glass directly
under the camera has no splay and cannot be cut off at the frame edge.

**Turning a mask into a place and a width is the bench's step, not this
solution's.** Every solution in this folder is given that same arithmetic, so a
difference in the scorecard belongs to the mask. This solution contributes only
the masks, and so does solution 3, which is exactly why the gap between the two
scorecards is readable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yolo_fine_tuned

import data
import marking
from scoring import Scorecard

# How many held-out scenes a run scores unless it is told otherwise.
SCENES = 20

# Scorecard's own names for the counts this folder can claim. Repeated from
# scoring.py only for the run that found nothing at all, which cannot go
# through Scorecard.summary: there is no median position error to take.


def summary(card: Scorecard, scenes: int, crowded: bool) -> dict:
    """The shared numbers, and the three facts that identify this solution."""
    return marking.summary("04-yolo-fine-tuned", card, scenes, crowded) | {
        "model": yolo_fine_tuned.MODEL,
        "confidence bar": yolo_fine_tuned.CONFIDENCE,
        # Named the same way solution 3 names it, where the answer is "nothing".
        # What the settings were is in this folder's README, beside the numbers.
        "fitted here": "every weight, continuing the borrowed file's training",
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

    save = yolo_fine_tuned.fitted()
    if not save.exists():
        raise SystemExit(
            f"there is no {save.name} in {save.parent}, so nothing has been fine-tuned yet.\n"
            f"Train it first, which is the slow step:\n"
            f"  pixi run python {Path(__file__).parent.name}/train.py"
        )
    finder = yolo_fine_tuned.load(save)

    card = Scorecard()
    for example in data.held_out(given.scenes, hard=given.crowded):
        kept, station = marking.survey(finder, example, card)
        marking.score(card, example, kept, station)
        if given.show:
            print(f"seed {example.seed}  {len(example.glasses)} out, {len(kept)} found")

    result = summary(card, given.scenes, given.crowded)
    marking.show(result)
    tail = "-crowded" if given.crowded else ""
    written = Path(__file__).parent / f"results{tail}.json"
    written.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nsaved to {written}")


if __name__ == "__main__":
    main()
