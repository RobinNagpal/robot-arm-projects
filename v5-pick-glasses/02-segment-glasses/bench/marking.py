"""The marking every solution is scored through, and the words its numbers come in.

A solution in this folder draws masks. It does not decide which station saw a
glass, how two stations' reports are brought together, or how the answer is
written down, because those are the same for all six and keeping them here is
what makes the six comparable. So this file is a library that every solution's
own ``run.py`` calls, and it holds no model and loads no weights. It is not
named ``run.py`` itself because every solution's own runner is, and the two
would then shadow each other.

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
masks_to_glasses for all six, so a difference in the scorecard belongs to how
the mask was drawn and never to what was done with the mask afterwards.

A solution is handed the picture and the kind of glass on the table, which the
cell is told, and never the scene behind it: no list of glasses and no true mask,
which is what data.py keeps for training.

Each solution writes its own ``results.json`` beside itself, in the same words,
so the six can be set side by side.
"""

from __future__ import annotations

import math

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
    """Judge one scene's answer: which glass each mask is, and how well it was drawn.

    The two are judged in different pictures on purpose. Which glass a mask is
    has to be settled in one picture shared by every station, or two stations'
    answers about the same glass could not be brought together. How well the
    mask was drawn has to be judged in the picture it was drawn in, against what
    that station could see, because the stations do not see the same pixels of a
    glass and comparing across them would measure the cameras instead.
    """
    matches = card.found(
        example.glasses,
        example.reference,
        [data.in_reference(station[id(g)].picture, g.pixels, example.reference) for g in kept],
        [(g.x, g.y) for g in kept],
    )
    for glass, index in zip(kept, matches, strict=True):
        if index is not None:
            card.mask(example.kind, glass.pixels, station[id(glass)].visible[index])


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
        "mask": card.mask_quality(),
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
    mask = result.get("mask") or {}
    if mask:
        whole = mask["all"]
        print(
            f"mask     covered {whole['covered_median']}% of the glass median, "
            f"{whole['covered_worst']}% worst; {whole['not_the_glass_median']}% of the mask "
            f"was not the glass median, {whole['not_the_glass_worst']}% worst"
        )
        for kind, row in mask["by_kind"].items():
            print(
                f"  {kind:20} covered {row['covered_median']}%, "
                f"not the glass {row['not_the_glass_median']}%  ({row['glasses']} glasses)"
            )
    print(f"doubted  {result['handed over'] or 'nothing'}")
