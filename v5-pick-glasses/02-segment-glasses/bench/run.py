"""Run one solution over the held-out scenes, score it, and write its numbers.

    pixi run python run.py --solution sam --scenes 20
    pixi run python run.py --solution amodal --crowded --show

The same three names as train.py and the same table, and the same indifference
to which of them was asked for: what `make train` wrote is loaded, the solution
is handed one picture at a time, and what it hands back is scored.

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

What comes out is `results-<solution>.json` and the same find line
../02-segment-glasses/01-rules-on-the-table and ../02-segment-glasses/02-train-from-scratch print, so the three approaches
can be set beside each other.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import weights
from train import NAMES, chosen, command, how_many, module

import data
import masks_to_glasses
from scoring import Scorecard

# Scorecard's own names for the counts this folder can claim. Repeated from
# scoring.py only for the run that found nothing at all, which cannot go
# through Scorecard.summary: there is no median position error to take.
FIND = ("found", "missed", "merged", "split", "false")


def survey(finder, example: data.Example, card: Scorecard):
    """Ask the solution about every station's picture, and come back with each glass once.

    Returns the glasses kept and, per glass, the station whose picture it came
    from, because its pixels are that picture's pixels and mean nothing without it.

    The reports are ordered by how far the glass stood from the point below the
    camera that saw it, so where the stations overlap the least splayed view of a
    glass is the one kept.
    """
    reports, station = [], {}
    for sight in example.sights:
        found, doubts = finder.find(sight.picture, example.kind)
        below = data.under(sight.pose)
        for glass in found:
            reports.append((math.dist((glass.x, glass.y), below), glass))
            station[id(glass)] = sight
        # A proposal the solution could not call either way is reported, not
        # guessed at, which is what handed_over counts.
        for doubt in doubts:
            card.handed_over(doubt)

    reports.sort(key=lambda report: report[0])
    kept = masks_to_glasses.one_per_place([glass for _, glass in reports], data.widths(example.kind)[0])
    return kept, station


def score(card: Scorecard, example: data.Example, kept, station) -> None:
    """Judge one scene's answer in the picture the scorecard reads ids from."""
    card.found(
        example.glasses,
        example.reference,
        [data.in_reference(station[id(g)].picture, g.pixels, example.reference) for g in kept],
        [(g.x, g.y) for g in kept],
    )


def summary(name: str, card: Scorecard, scenes: int, crowded: bool) -> dict:
    """What this folder did, in Scorecard's own words.

    Scorecard also carries a view section and a measure section, because the
    folders it was written for go on to choose a viewpoint and measure a glass.
    Nothing here does either, so those sections would be zeros dressed as
    results and only the find section is written.
    """
    find = {key: card.count[key] for key in FIND}
    find |= {"position_mm_median": None, "position_mm_worst": None}
    if card.position_mm:
        find = card.summary(scenes)["find"]
    return {
        "solution": name,
        "scenes": scenes,
        "layouts": "crowded" if crowded else "spawned",
        "stations": len(data.stations()),
        "glasses": card.count["put out"],
        "find": find,
        "handed over": {
            reason.split(": ")[1]: count
            for reason, count in card.count.items()
            if reason.startswith("handed over")
        },
    }


def position(find: dict) -> str:
    """How far the found places sat from the true ones, in scoring.py's own words."""
    if find["position_mm_median"] is None:
        return "position no glass to measure"
    return f"position {find['position_mm_median']} mm median, {find['position_mm_worst']} worst"


def show(result: dict) -> None:
    find = result["find"]
    print(
        f"\n{result['scenes']} held-out {result['layouts']} scenes, {result['glasses']} glasses, "
        f"{result['stations']} stations each\n"
    )
    print(
        f"find     found {find['found']}, missed {find['missed']}, merged {find['merged']}, "
        f"split {find['split']}, false {find['false']}; {position(find)}"
    )
    print(f"doubted  {result['handed over'] or 'nothing'}")


def main() -> None:
    parser = command("Run one solution on held-out scenes and score it")
    parser.add_argument("--show", action="store_true", help="print each scene as it is scored")
    parser.add_argument(
        "--crowded",
        action="store_true",
        help="score on crowded layouts, where one glass really does hide another",
    )
    given = parser.parse_args()
    chosen(given.solution)
    scenes = how_many(given, 20)

    fitted = weights.fitted(given.solution)
    if not fitted.exists():
        raise SystemExit(
            f"{given.solution} has not been trained yet: there is no {fitted.name} in {fitted.parent}.\n"
            f"Train it first, which is the slow step:\n"
            f"  make train SOLUTION={given.solution}\n"
            f"The solutions here are: {NAMES}"
        )
    finder = module(given.solution).load(fitted)

    card = Scorecard()
    for example in data.held_out(scenes, hard=given.crowded):
        kept, station = survey(finder, example, card)
        score(card, example, kept, station)
        if given.show:
            print(f"seed {example.seed}  {len(example.glasses)} out, {len(kept)} found")

    result = summary(given.solution, card, scenes, given.crowded)
    show(result)
    tail = "-crowded" if given.crowded else ""
    save = Path(__file__).parent / f"results-{given.solution}{tail}.json"
    save.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
