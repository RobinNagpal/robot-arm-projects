"""The best any solution here could do: the renderer's own masks, and no model.

Every solution in this folder draws masks and then hands them to
masks_to_glasses, so a scorecard holds two things at once: how well the masks
were drawn, and what the arithmetic afterwards can do with a mask however well
it was drawn. This file separates them. It hands the arithmetic the masks the
renderer itself used to draw the scene, which no segmenter can improve on, and
runs them through the same survey of three stations and the same scorecard. What
comes out is a floor under every result in this folder: a solution close to it is
limited by the view and the arithmetic rather than by its model, and a solution
far from it has something left to gain from better masks.

    pixi run python floor.py --scenes 20
    pixi run python floor.py --scenes 20 --crowded

It runs three ways, because a mask can be exact in three different senses:

``visible``   only the pixels the camera can see of a glass, which is what
              every solution here draws when it is fitted on this cell.
``whole``     the glass's whole outline as if nothing stood in front of it,
              which is what the amodal rung of 06-rf-detr-fine-tuned draws,
              with the pixels it only asserts named so that their depth
              readings are left out.
``poisoned``  the same whole outline with nothing named, which is the one
              implementation mistake that destroys the answer while every check
              still passes. It is run here so that the cost of making it is a
              measurement rather than a warning.

The first two come out of the scorecard the same, and that is the point rather
than a fault: naming the asserted pixels removes them from the arithmetic, so a
whole outline with them named leaves exactly the visible pixels behind. What
naming is worth therefore cannot be seen in a whole run, where most glasses
have nothing in front of them anyway, and ``hidden()`` below answers it for the
partly hidden glasses the question is actually about.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import data
import marking
import masks_to_glasses
from scoring import Scorecard

# The three senses in which a mask can be exact, in the order they are reported.
WAYS = ("visible", "whole", "poisoned")


class Exact:
    """A finder that knows the answer, so that only the arithmetic is on trial.

    It is handed a picture like any solution, and it looks the scene behind that
    picture up rather than working it out. Nothing else in this folder may do
    that, which is why this class lives here and not beside the solutions.
    """

    def __init__(self, way: str) -> None:
        self.way = way
        self.scenes: dict[int, data.Sight] = {}

    def remember(self, example: data.Example) -> None:
        for sight in example.sights:
            self.scenes[id(sight.picture)] = sight

    def find(self, picture, kind: str) -> tuple[list[masks_to_glasses.Found], list[str]]:
        sight = self.scenes[id(picture)]
        found = []
        for index in range(len(sight.glasses)):
            visible = sight.visible[index]
            if self.way == "visible":
                mask, asserted = visible, None
            else:
                mask = sight.whole[index]
                asserted = mask & ~visible if self.way == "whole" else None
            one = masks_to_glasses.one_glass(picture, mask, asserted)
            if one is not None:
                found.append(one)
        # Nothing is ever in doubt here: an exact mask is either large enough to
        # fit a footprint to or it is not.
        return found, []


def measure(way: str, scenes: int, crowded: bool) -> dict:
    """One way of being exact, over the same held-out scenes a solution is scored on."""
    finder, card = Exact(way), Scorecard()
    for example in data.held_out(scenes, hard=crowded):
        finder.remember(example)
        kept, station = marking.survey(finder, example, card)
        marking.score(card, example, kept, station)
    return marking.summary(f"exact {way} masks", card, scenes, crowded)


def hidden(scenes: int) -> dict:
    """What naming the asserted pixels is worth, for one partly hidden glass at a time.

    The scorecard above answers for a whole run, where a glass nothing stands in
    front of is unaffected either way and there are many of those. This answers
    for the glasses the question is about, which is where the difference lives.
    """
    apart: dict[str, list[float]] = {"named": [], "fed in": []}
    widths: dict[str, list[float]] = {"named": [], "fed in": []}
    for example in data.held_out(scenes, hard=True):
        for sight in example.sights:
            for index, glass in enumerate(sight.glasses):
                visible, whole = sight.visible[index], sight.whole[index]
                asserted = whole & ~visible
                enough = masks_to_glasses.MIN_PIXELS
                if asserted.sum() < enough or visible.sum() < enough:
                    continue
                for label, named in (("named", asserted), ("fed in", None)):
                    one = masks_to_glasses.one_glass(sight.picture, whole, named)
                    if one is not None:
                        apart[label].append(1000.0 * float(np.hypot(one.x - glass.x, one.y - glass.y)))
                        widths[label].append(1000.0 * one.width)
    return {
        "partly hidden glasses": len(apart["named"]),
        "asserted pixels": {
            label: {
                "position_mm_median": round(float(np.median(apart[label])), 1),
                "position_mm_worst": round(float(np.max(apart[label])), 1),
                "width_mm_median": round(float(np.median(widths[label])), 1),
            }
            for label in apart
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenes", type=int, default=20, help="how many held-out scenes to use")
    parser.add_argument(
        "--crowded",
        action="store_true",
        help="score on crowded layouts, where one glass really does hide another",
    )
    given = parser.parse_args()

    results = [measure(way, given.scenes, given.crowded) for way in WAYS]
    for result in results:
        print(f"\n{result['solution']}")
        marking.show(result)

    whole = {"ways": results}
    if given.crowded:
        whole |= {"one glass at a time": hidden(given.scenes)}
        print(f"\nper partly hidden glass  {json.dumps(whole['one glass at a time'], indent=2)}")

    tail = "-crowded" if given.crowded else ""
    save = Path(__file__).parent / f"results-floor{tail}.json"
    save.write_text(json.dumps(whole, indent=2) + "\n")
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
