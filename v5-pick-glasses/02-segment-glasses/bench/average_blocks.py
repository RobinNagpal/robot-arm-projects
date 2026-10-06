"""Average a solution's scorecard over several blocks of held-out arrangements.

A single run scores 20 held-out arrangements and writes one ``results.json``.
Twenty arrangements is a small sample, so a score read off one of them carries a
sampling wobble that the file itself cannot show. This script runs the same
solution over several non-overlapping blocks of held-out arrangements — seeds
10000 to 10019, 10020 to 10039 and so on, none of which any training has seen —
and reports the average of the blocks together with the spread across them.

What it does **not** measure is training variation. Every block is scored with
the same fitted weights, so the spread here is "which arrangements did we draw",
not "which training run did we get". Measuring the second would mean refitting,
which is a different and much more expensive question.

Counts are summed and then expressed per 100 glasses, because the blocks hold
slightly different numbers of glasses. Medians cannot be averaged honestly, so
the median columns report the mean of the blocks' medians and are labelled as
such.

    pixi run python bench/average_blocks.py
    pixi run python bench/average_blocks.py --crowded
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# Which file each solution writes, with {tail} standing for the block and layout.
SOLUTIONS = {
    "01-rules-on-the-table": "results{tail}.json",
    "02-train-from-scratch": "results{tail}.json",
    "03-yolo-zero-shot": "results{tail}.json",
    "04-yolo-fine-tuned": "results{tail}.json",
    "05-sam2-with-a-keeper": "results-sam2{tail}.json",
    "06-rf-detr-fine-tuned": "results-modal{tail}.json",
}

BLOCKS = (10000, 10020, 10040, 10060, 10080)
COUNTS = ("found", "missed", "merged", "split", "false")


def blocks_for(folder: str, name: str, crowded: bool) -> list[dict]:
    """Every block's scorecard for one solution, in block order."""
    out = []
    for start in BLOCKS:
        tail = "-crowded" if crowded else ""
        # The first block is the one the committed results file already holds,
        # written before --from-seed existed, so it has no block in its name.
        for candidate in (f"{tail}-from{start}", tail if start == BLOCKS[0] else None):
            if candidate is None:
                continue
            path = HERE / folder / name.format(tail=candidate)
            if path.exists():
                out.append(json.loads(path.read_text()))
                break
    return out


def averaged(cards: list[dict]) -> dict:
    """The blocks together: counts per 100 glasses, and the spread over blocks."""
    glasses = sum(c["glasses"] for c in cards)
    summary = {
        "blocks": len(cards),
        "arrangements": sum(c["scenes"] for c in cards),
        "glasses": glasses,
    }
    for key in COUNTS:
        total = sum(c["find"][key] for c in cards)
        per_block = [100.0 * c["find"][key] / c["glasses"] for c in cards]
        summary[key] = total
        summary[f"{key}_per_100"] = round(100.0 * total / glasses, 1)
        summary[f"{key}_per_100_lowest"] = round(min(per_block), 1)
        summary[f"{key}_per_100_highest"] = round(max(per_block), 1)
    for label, where in (("position_mm_median", ("find", "position_mm_median")),
                         ("covered_median", ("mask", "all", "covered_median")),
                         ("not_the_glass_median", ("mask", "all", "not_the_glass_median"))):
        values = []
        for c in cards:
            at = c
            for step in where:
                at = at[step]
            if at is not None:
                values.append(at)
        if values:
            summary[f"{label}_mean_of_blocks"] = round(statistics.fmean(values), 1)
            summary[f"{label}_lowest"] = round(min(values), 1)
            summary[f"{label}_highest"] = round(max(values), 1)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--crowded", action="store_true", help="the crowded layouts")
    parser.add_argument("--json", action="store_true", help="write results-averaged.json")
    given = parser.parse_args()

    out = {}
    for folder, name in SOLUTIONS.items():
        cards = blocks_for(folder, name, given.crowded)
        if not cards:
            print(f"{folder:24s} no blocks found")
            continue
        got = averaged(cards)
        out[folder] = got
        print(
            f"{folder:24s} {got['blocks']} blocks, {got['glasses']:3d} glasses: "
            f"found {got['found_per_100']:5.1f} per 100 "
            f"({got['found_per_100_lowest']:.1f} to {got['found_per_100_highest']:.1f}), "
            f"place {got.get('position_mm_median_mean_of_blocks', float('nan')):5.1f} mm, "
            f"covered {got.get('covered_median_mean_of_blocks', float('nan')):5.1f}%"
        )
    if given.json:
        where = HERE / "results" / (
            "results-averaged-crowded.json" if given.crowded else "results-averaged.json"
        )
        where.write_text(json.dumps(out, indent=2) + "\n")
        print(f"\nsaved to {where}")


if __name__ == "__main__":
    main()
