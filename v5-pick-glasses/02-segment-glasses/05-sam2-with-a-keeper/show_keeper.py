"""Print what the keeper was shown beside what it answered, over one real picture.

    pixi run python 05-sam2-with-a-keeper/show_keeper.py
    pixi run python 05-sam2-with-a-keeper/show_keeper.py --scene 10003 --station 2 --crowded

This is the claim the document makes for this solution and for no other one in
the set: **the deciding can be explained by printing its inputs beside its
answer.** Every proposal here comes out as eight named measurements, the three
calibrated chances the keeper gave them, the answer that followed, and what the
arithmetic after the keeper then did about it. A person can read that, disagree
with it, and point at the measurement that was wrong.

What the simulator knows is printed beside it, because this is a tool for
arguing with the keeper rather than a scorecard: the answer the truth deserves
comes from the same arithmetic `train.py` labels with. Nothing here is scored
and nothing here is written down; `run.py` does the scoring.

It needs the keeper fitted and SAM 2 downloaded, because these are real
proposals from a real picture and there is no honest way to show them otherwise.
"""

from __future__ import annotations

import argparse

import reports
import sam_keeper
import train
import weights

import data
import render


def fitting_rung() -> str:
    """The rung whose keeper there is something to explain.

    Read off the table rather than written down here, so this file still knows
    nothing about which rung is which. The other rung does its deciding inside
    borrowed weights, which is exactly what cannot be printed.
    """
    fits = [name for name, solution in train.SOLUTIONS.items() if solution.fits]
    if len(fits) != 1:
        raise SystemExit(f"expected one rung that fits something, and the table holds {len(fits)}")
    return fits[0]


def outcome(proposal, chance, widths) -> str:
    """What happened to this proposal after the keeper spoke."""
    answer = sam_keeper.verdict(chance)
    if answer == sam_keeper.KEEP:
        return "reported as a glass" if reports.legal(proposal.found, widths) else reports.TOO_WIDE
    if answer == sam_keeper.SPLIT:
        return "prompted again inside itself, to see whether it comes apart"
    if answer == sam_keeper.UNSURE:
        return "handed over: take another picture from another place"
    return "dropped"


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the keeper's inputs beside its answer")
    parser.add_argument("--scene", type=int, default=render.TEST_SEEDS, help="which held-out seed")
    parser.add_argument("--station", type=int, default=1, help="which of the survey's pictures, from 1")
    parser.add_argument(
        "--crowded", action="store_true", help="a layout where one glass really does hide another"
    )
    given = parser.parse_args()

    if given.scene < render.TEST_SEEDS:
        raise SystemExit(f"seed {given.scene} is one the keeper may have been fitted on; use a held-out one")
    example = data.crowded(given.scene) if given.crowded else data.spawned(given.scene)
    if not 1 <= given.station <= len(example.sights):
        raise SystemExit(f"--station {given.station}: the survey has {len(example.sights)} of them")
    sight = example.sights[given.station - 1]

    finder = sam_keeper.load(weights.fitted(fitting_rung()))
    widths = data.widths(example.kind)
    shortlist = sam_keeper.survey(sight.picture, example.kind)[1]

    print(
        f"\nseed {given.scene}, station {given.station} of {len(example.sights)}, "
        f"{example.kind}, {len(example.glasses)} on the table, {len(shortlist)} proposals\n"
    )
    for number, proposal in enumerate(shortlist, start=1):
        chance = finder.chances(proposal.features[None])[0]
        truth = sam_keeper.ANSWERS[sam_keeper.label(proposal.mask, sight.visible)]
        print(
            f"proposal {number}: {int(proposal.mask.sum())} pixels at "
            f"({proposal.found.x:.3f}, {proposal.found.y:.3f}) m, {1000 * proposal.found.width:.0f} mm wide"
        )
        for line in sam_keeper.explanation(proposal.features, chance):
            print(f"  {line}")
        print(f"  {'so':>14}  {outcome(proposal, chance, widths)}")
        print(f"  {'the truth':>14}  {truth}\n")


if __name__ == "__main__":
    main()
