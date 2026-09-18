"""What each split of the centre-of-mass dataset holds, and a check on its points.

    python -m center_of_mass.stats

For every split: blocks of each class, and two distances in pixels, averaged
over the blocks.

- **label to mask centre**: from the labelled point to the middle of the
  block's mask. From straight above these should nearly meet. A large number
  means the projection in ``scene.py`` no longer matches the renderer.
- **box centre to label**: from the middle of the box to the labelled point.
  This is how wrong a model would be that only learned to find the box. The
  bigger it is, the more the dataset asks for.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import cv2

from synthetic import sdf

from .polygons import CLASSES
from .preview import mask_centre


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data", type=Path, default=Path("data/center-of-mass"))
    args = parser.parse_args()

    for split in sorted(p.name for p in (args.data / "scenes").iterdir() if p.is_dir()):
        per_class = Counter()
        to_mask, to_box = [], []
        records = sorted((args.data / "scenes" / split).glob("*.json"))
        for path in records:
            mask = cv2.imread(str(args.data / "masks" / split / f"{path.stem}.png"), cv2.IMREAD_UNCHANGED)
            for seen in json.loads(path.read_text())["visible"]:
                per_class[seen["shape"]] += 1
                point = seen["point"]
                to_mask.append(math.dist(point, mask_centre(mask, sdf.block_label(seen["block"]))))
                x, y, w, h = seen["box"]
                to_box.append(math.dist(point, (x + w / 2, y + h / 2)))
        total = sum(per_class.values())
        print(f"\n{split}: {len(records)} pictures, {total} blocks")
        print("  " + "  ".join(f"{name} {per_class[name]}" for name in CLASSES))
        if total:
            print(
                f"  label to mask centre: mean {sum(to_mask) / total:.2f} px, max {max(to_mask):.2f} px\n"
                f"  box centre to label:  mean {sum(to_box) / total:.2f} px, max {max(to_box):.2f} px"
            )


if __name__ == "__main__":
    main()
