"""Does the borrowed model's weakness divide by kind of glass? One measurement.

Solution 8 prompts a borrowed segmentation model with a grid of points and keeps
what a small classifier calls a glass. Whether that works at all depends on
something the solution cannot change: whether the borrowed model draws an outline
round a glass of this kind when it is shown a grey picture shaded from depth
instead of the photographs its weights were fitted on. A kind whose outline is
one wall running from the table to the rim is a strong boundary in such a
picture, while a wide bowl standing on a thin stem is mostly not.

So this file asks only about the proposals, with no classifier and no scorecard
after them. For every glass it finds the proposal that matches the glass best and
reports that match two ways, because the two answer different questions:

``overlap``   the shared pixels against the pixels either the proposal or the
              glass holds, which falls when the proposal spills past the glass
              as well as when it stops short of it.
``coverage``  the share of the glass's own pixels the proposal holds, which is
              the question "how much of this glass was proposed at all".

    pixi run python proposals_by_kind.py --scenes 2

``--scenes`` is per kind and small on purpose: one picture through the model's
picture encoder costs seconds, and the difference between the kinds here is far
larger than the spread within one of them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import data
import masks_to_glasses
import render
import sam_keeper

# A proposal holding this much of a glass has found that glass, whatever else it
# also holds. Half is the loosest reading anybody would accept, which is the
# point: it is the share used to say a glass was proposed at all.
FOUND = 0.5

# And this much of it is an outline a measurement could be read off.
WHOLE = 0.9


def best_match(sight: data.Sight, kind: str) -> list[tuple[float, float]]:
    """Per glass in one picture, the best proposal's overlap and coverage."""
    _, proposals = sam_keeper.survey(sight.picture, kind)
    masks = np.stack([one.mask for one in proposals]) if proposals else None
    out = []
    for index in range(len(sight.glasses)):
        truth = sight.visible[index]
        # A glass the camera barely sees at this station is not evidence about
        # the model, so it is left out rather than counted as a failure.
        if truth.sum() < masks_to_glasses.MIN_PIXELS:
            continue
        if masks is None:
            out.append((0.0, 0.0))
            continue
        shared = (masks & truth).sum((1, 2))
        either = (masks | truth).sum((1, 2))
        out.append((float((shared / np.maximum(either, 1)).max()), float((shared / truth.sum()).max())))
    return out


def measure(per_kind: int) -> dict:
    matches: dict[str, list[tuple[float, float]]] = {kind: [] for kind in render.KINDS}
    wanted = dict.fromkeys(render.KINDS, per_kind)
    for seed in data.held_out_seeds(per_kind * len(render.KINDS) * len(render.KINDS)):
        kind = render.KINDS[seed % len(render.KINDS)]
        if wanted[kind] <= 0:
            continue
        wanted[kind] -= 1
        example = data.spawned(seed)
        for sight in example.sights:
            matches[kind].extend(best_match(sight, example.kind))

    report = {}
    for kind, got in matches.items():
        overlap, coverage = np.array([m[0] for m in got]), np.array([m[1] for m in got])
        report[kind] = {
            "glasses": len(got),
            "overlap_median": round(float(np.median(overlap)), 2),
            "coverage_median": round(float(np.median(coverage)), 2),
            "share_proposed": round(float((coverage >= FOUND).mean()), 2),
            "share_whole": round(float((coverage >= WHOLE).mean()), 2),
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenes", type=int, default=2, help="held-out scenes per kind of glass")
    given = parser.parse_args()

    report = measure(given.scenes)
    for kind, got in report.items():
        print(
            f"{kind:20s} {got['glasses']:3d} glasses  "
            f"overlap {got['overlap_median']:.2f}  coverage {got['coverage_median']:.2f}  "
            f"proposed {got['share_proposed']:.0%}  whole {got['share_whole']:.0%}"
        )

    save = Path(__file__).parent / "results-by-kind.json"
    save.write_text(json.dumps({"scenes per kind": given.scenes, "kinds": report}, indent=2) + "\n")
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
