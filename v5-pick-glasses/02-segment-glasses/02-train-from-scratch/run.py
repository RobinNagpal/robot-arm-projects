"""Run the network over the held-out scenes, score it, and write its numbers.

    pixi run python 02-train-from-scratch/run.py --scenes 20
    pixi run python 02-train-from-scratch/run.py --crowded --show

The scenes come from above the bench's dividing line, which is the half no
training ever saw. The same scenes, pictures and scorecard as every other
solution here, so the results files can be set side by side.

**A survey is three pictures, not one.** At the cell's own survey height one
picture does not hold the glass zone, because a rim seen from above leans away
from the point below the camera, so the cell stands at the stations ``data.py``
works out and this file asks the network about each picture on its own. The
three answers are then brought together and a glass is counted once, which is
``marking.survey``'s job and the same for all six.

**Turning a mask into a place and a width is the bench's step, not this
solution's.** This solution contributes only the masks, and so does solution 1,
which is exactly why the gap between the two scorecards is readable.

Only TopNet is loaded here. The Ranker and SideNet this folder also fits belong
to the steps after the bench's, so nothing in this run touches them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import models
import pipeline
import torch
from train import WEIGHTS

import data
import marking
from scoring import Scorecard

# How many held-out scenes a run scores unless it is told otherwise.
SCENES = 20


def load() -> pipeline.Finder:
    """TopNet, as ``train.py`` saved it."""
    save = WEIGHTS / "top_net.pt"
    if not save.exists():
        raise SystemExit(
            f"there is no {save.name} in {save.parent}, so nothing has been trained yet.\n"
            f"Train it first:\n"
            f"  pixi run python {Path(__file__).parent.name}/train.py"
        )
    top_net = models.TopNet()
    top_net.load_state_dict(torch.load(save))
    return pipeline.Finder(top_net)


def summary(card: Scorecard, scenes: int, crowded: bool) -> dict:
    """The shared numbers, and the three facts that identify this solution."""
    return marking.summary("02-train-from-scratch", card, scenes, crowded) | {
        "model": "TopNet, a small U-Net written here",
        "votes a pile needs": pipeline.MIN_VOTES,
        "fitted here": "every weight, from random numbers",
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

    finder = load()
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
