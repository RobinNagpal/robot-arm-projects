"""How many labelled blocks of each class each split holds, and how hard they are.

    python -m synthetic.stats

A dataset can look fine picture by picture and still be lopsided: one class
far rarer than the others, or nearly every octagon a few pixels wide. This
counts, from the scene records, what the model will actually be shown.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .shapes import CLASSES

SMALL = 400  # pixels; a block this small is about 20 pixels across


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=Path("data/shapes"))
    args = parser.parse_args()

    splits = sorted(p.name for p in (args.data / "scenes").iterdir() if p.is_dir())
    header = (
        f"{'':12}" + "".join(f"{name:>11}" for name in CLASSES) + f"{'on edge':>9}{'small':>7}{'empty':>7}"
    )
    for split in splits:
        records = [json.loads(p.read_text()) for p in sorted((args.data / "scenes" / split).glob("*.json"))]
        per_class, on_edge, small, empty = Counter(), 0, 0, 0
        for record in records:
            if not record["visible"]:
                empty += 1
            for seen in record["visible"]:
                per_class[seen["shape"]] += 1
                on_edge += record["blocks"][seen["block"]]["on_edge"]
                small += seen["pixels"] < SMALL
        total = sum(per_class.values())
        print(f"\n{split}: {len(records)} pictures, {total} labelled blocks")
        print(header)
        print(
            f"{'blocks':12}"
            + "".join(f"{per_class[name]:>11}" for name in CLASSES)
            + f"{on_edge / max(total, 1):>9.0%}{small / max(total, 1):>7.0%}{empty:>7}"
        )


if __name__ == "__main__":
    main()
