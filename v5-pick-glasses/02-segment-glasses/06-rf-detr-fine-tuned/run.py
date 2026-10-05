"""Run the fine-tuned model over the held-out scenes, score it, write results.json.

    pixi run python 06-rf-detr-fine-tuned/run.py --target amodal --scenes 20
    pixi run python 06-rf-detr-fine-tuned/run.py --target modal --crowded --show

The survey of three stations, the bringing-together of their answers and the
words the numbers come in are all ``bench/marking.py``, which every solution
here calls. Nothing in this file decides any of that, which is what keeps the
six comparable.

**The scenes come from the bench**, at or above its held-out line, so no scene
scored here was trained on.

**Two numbers belong to this solution and to no other**, and they are written
beside the shared scorecard. The **visible fraction** of each report says how
much of that glass the camera actually saw, which is what tells a consumer
further down how much of the answer was asserted. And the count of **reports
with an asserted part at all** says how often the second rung did anything,
because on a glass with a clear view the two rungs agree exactly and a run
where nothing was ever hidden cannot tell them apart.

Both come off the same pass of the model the marking uses. ``Recording`` below
is why: it answers ``find`` for the marking and keeps what each slot asserted on
the way past, so no picture goes through the model twice.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rf_detr_seg
import weights
from train import TARGETS

import data
import marking
from scoring import Scorecard


class Recording:
    """The finder, answering ``find`` as the marking expects, and noting the completion."""

    def __init__(self, finder: rf_detr_seg.Finder) -> None:
        self.finder = finder
        self.told: list[dict] = []

    def find(self, picture, kind: str):
        seen = self.finder.look(picture, kind)
        self.told += [
            {"visible_fraction": one.visible_fraction, "asserted": int(one.asserted.sum())}
            for one in seen
            if one.found is not None
        ]
        return rf_detr_seg.keep(seen, kind)


def completion(told: list[dict]) -> dict:
    """How much of its own answer this solution asserted rather than observed."""
    fractions = [one["visible_fraction"] for one in told]
    return {
        "reports": len(told),
        "with an asserted part": sum(one["asserted"] > 0 for one in told),
        "visible_fraction_median": round(float(np.median(fractions)), 3) if fractions else None,
        "visible_fraction_lowest": round(float(np.min(fractions)), 3) if fractions else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=TARGETS, required=True, help="which fine-tune to score")
    parser.add_argument("--scenes", type=int, default=20, help="how many held-out scenes")
    parser.add_argument("--crowded", action="store_true", help="score on crowded layouts")
    parser.add_argument("--show", action="store_true", help="print each scene as it is scored")
    given = parser.parse_args()

    save = weights.fitted(given.target)
    if not save.exists():
        raise SystemExit(
            f"{given.target} has not been fine-tuned yet: there is no {save.name} in {save.parent}.\n"
            f"Fit it first, which is the slow step:\n"
            f"  pixi run python 06-rf-detr-fine-tuned/train.py --target {given.target}"
        )
    finder = Recording(rf_detr_seg.load(save))

    card = Scorecard()
    for example in data.held_out(given.scenes, hard=given.crowded):
        kept, station = marking.survey(finder, example, card)
        marking.score(card, example, kept, station)
        if given.show:
            print(f"seed {example.seed}  {len(example.glasses)} out, {len(kept)} found")

    result = marking.summary(f"rf-detr-seg {given.target}", card, given.scenes, given.crowded)
    result["completion"] = completion(finder.told)
    marking.show(result)
    print(f"asserted {json.dumps(result['completion'])}")

    tail = "-crowded" if given.crowded else ""
    where = Path(__file__).parent / f"results-{given.target}{tail}.json"
    where.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\nsaved to {where}")


if __name__ == "__main__":
    main()
