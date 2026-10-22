"""Run one rung over the held-out scenes, score it, and write its numbers.

    pixi run python 05-sam2-with-a-keeper/run.py --solution sam2 --scenes 20
    pixi run python 05-sam2-with-a-keeper/run.py --solution sam2 --crowded --show
    pixi run python 05-sam2-with-a-keeper/run.py --solution sam3

The same two names as train.py and the same table, and the same indifference to
which of them was asked for: what `train.py` wrote is loaded, the rung is handed
one picture at a time, and what it hands back is scored. The rung that fits
nothing has nothing to load, and that is a fact in the table rather than a
branch here.

**A survey is three pictures, not one.** At the cell's own survey height one
picture does not hold the glass zone, because a rim seen from above leans away
from the point below the camera, so the cell stands at three stations and this
file asks the solution about each picture on its own. The three answers are then
brought together and a glass is counted once. Which of a place's reports is kept
is decided by how far the glass stood from the point below that station's camera:
nearest first, because a glass directly under the camera has no splay and cannot
be cut off at the frame edge, so that station's report is the one to believe.
That is the whole reason the cell surveys from overlapping stations.

What a solution hands back is masks_to_glasses.Found, which is the one shape
every solution in this folder produces: the pixels of one glass, the place on the
table they give, and the width. That place and that width come from
masks_to_glasses for all three, so a difference in the scorecard belongs to how
the mask was drawn and never to what was done with the mask afterwards.

A solution is handed the picture and the kind of glass on the table, which the
cell is told, and never the scene behind it: no list of glasses and no true mask,
which is what data.py keeps for training.

What comes out is `results-<rung>.json` beside this file, with the same find
line `../01-rules-on-the-table` and `../02-train-from-scratch` print, so every
approach in this problem can be set beside the others.
"""

from __future__ import annotations

import json
from pathlib import Path

import weights
from train import NAMES, chosen, command, how_many, module

import data
import marking
from scoring import Scorecard

# Scorecard's own names for the counts this folder can claim. Repeated from
# scoring.py only for the run that found nothing at all, which cannot go
# through Scorecard.summary: there is no median position error to take.


def summary(name: str, card: Scorecard, scenes: int, crowded: bool) -> dict:
    """The shared numbers, under the name of whichever rung was run."""
    return marking.summary(name, card, scenes, crowded)


def main() -> None:
    parser = command("Run one solution on held-out scenes and score it")
    parser.add_argument("--show", action="store_true", help="print each scene as it is scored")
    parser.add_argument(
        "--crowded",
        action="store_true",
        help="score on crowded layouts, where one glass really does hide another",
    )
    parser.add_argument(
        "--from-seed",
        type=int,
        default=None,
        help="first held-out seed, to score a different block of arrangements",
    )
    given = parser.parse_args()
    solution = chosen(given.solution)
    scenes = how_many(given, 20)

    fitted = weights.fitted(given.solution) if solution.fits else None
    if fitted is not None and not fitted.exists():
        raise SystemExit(
            f"{given.solution} has not been fitted yet: there is no {fitted.name} in {fitted.parent}.\n"
            f"Fit it first, which is the slow step:\n"
            f"  pixi run python 05-sam2-with-a-keeper/train.py --solution {given.solution}\n"
            f"The solutions here are: {NAMES}"
        )
    finder = module(given.solution).load(fitted)

    block = {} if given.from_seed is None else {"start": given.from_seed}
    card = Scorecard()
    for example in data.held_out(scenes, hard=given.crowded, **block):
        kept, station = marking.survey(finder, example, card)
        marking.score(card, example, kept, station)
        if given.show:
            print(f"seed {example.seed}  {len(example.glasses)} out, {len(kept)} found")

    result = summary(given.solution, card, scenes, given.crowded)
    marking.show(result)
    tail = "-crowded" if given.crowded else ""
    if given.from_seed is not None:
        tail += f"-from{given.from_seed}"
    save = Path(__file__).parent / f"results-{given.solution}{tail}.json"
    save.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
