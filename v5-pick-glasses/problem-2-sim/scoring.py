"""How a run is scored against what the simulator put out.

Shared by both approaches, so their numbers mean the same thing. Nothing here
is used by a pipeline to decide anything; only to judge it afterwards.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
from work_cell.glasses.detect import standing_on_the_table, the_one_in_the_middle
from work_cell.glasses.perception import NotMeasurable, profile_from_mask
from work_cell.glasses.profile import Profile
from work_cell.table.layout import TABLE_TOP_Z

from render import LENS, STANDOFF, Glass, Picture

# Heights at which profiles are compared, as fractions of the glass's height.
FRACTIONS = (np.arange(16) + 0.5) / 16

# A side picture is unspoiled when it measures within this of the same camera
# with the glass standing alone.
GOOD_HEIGHT = 0.003
GOOD_WIDTH = 0.002

# Two true glasses that each hold more than this share of one found glass's
# pixels were merged into it.
MERGED_SHARE = 0.2


def true_profile(glass: Glass) -> Profile:
    return Profile(glass.height, 2.0 * glass.radius)


def profile_error(measured: Profile, truth: Profile) -> tuple[float, float]:
    """Height error, and the median width error over the glass, in metres."""
    heights = FRACTIONS * truth.total_height
    widths = np.array([measured.width_at(h) - truth.width_at(h) for h in heights])
    return measured.total_height - truth.total_height, float(np.median(np.abs(widths)))


def silhouette(picture: Picture) -> Profile:
    """Problem 1's step 2, unchanged: the glass in the middle, row by row."""
    standing = standing_on_the_table(
        picture.depth,
        LENS,
        picture.camera_to_world,
        TABLE_TOP_Z,
        within=(STANDOFF - 0.12, STANDOFF + 0.12),
    )
    return profile_from_mask(the_one_in_the_middle(standing), LENS, STANDOFF)


def is_good(picture: Picture, alone: Picture) -> bool:
    """Did the other glasses spoil this picture?

    ``alone`` is the same camera with only the target on the table. Compared
    against that rather than the true shape, because a silhouette reads a tall
    glass several millimetres tall from any side, and that is about the glass,
    not the viewpoint.
    """
    try:
        height, width = profile_error(silhouette(picture), silhouette(alone))
    except NotMeasurable:
        return False
    return abs(height) < GOOD_HEIGHT and width < GOOD_WIDTH


class Scorecard:
    """Counts and errors for one run, in the same shape for both approaches."""

    def __init__(self) -> None:
        self.count = Counter()
        self.position_mm: list[float] = []
        self.profile_mm: list[tuple[float, float]] = []
        self.rng = random.Random(1)

    def found(self, glasses: list[Glass], top: Picture, pixels: list[np.ndarray], xy) -> list[int | None]:
        """Which true glass each found one is, judged by the pixels it covers."""
        self.count["put out"] += len(glasses)
        claimed, matches = Counter(), []
        for mine, (x, y) in zip(pixels, xy, strict=True):
            ids = top.ids[mine[:, 0], mine[:, 1]]
            shares = Counter(ids[ids > 0].tolist())
            total = max(1, sum(shares.values()))
            if sum(share / total > MERGED_SHARE for share in shares.values()) > 1:
                self.count["merged"] += 1
            if not shares:
                self.count["false"] += 1
                matches.append(None)
                continue
            index = shares.most_common(1)[0][0] - 1
            claimed[index] += 1
            matches.append(index)
            self.position_mm.append(1000 * float(np.hypot(x - glasses[index].x, y - glasses[index].y)))
        self.count["found"] += len(claimed)
        self.count["split"] += sum(n > 1 for n in claimed.values())
        self.count["missed"] += len(glasses) - len(claimed)
        return matches

    def view(self, glasses: list[Glass], index: int, chosen, allowed, pose_for, render) -> None:
        """Judge the chosen place, and a random allowed one beside it."""
        for label, angle in (("chosen", chosen), ("random", self.rng.choice(sorted(allowed)))):
            pose = pose_for(angle)
            good = is_good(render(glasses, pose), render([glasses[index]], pose))
            self.count[f"{label} unspoiled"] += good
            self.count[f"{label} views"] += 1

    def handed_over(self, reason: str) -> None:
        self.count[f"handed over: {reason}"] += 1

    def measured(self, measured: Profile, glass: Glass) -> tuple[float, float]:
        height, width = profile_error(measured, true_profile(glass))
        self.profile_mm.append((1000 * height, 1000 * width))
        return height, width

    def summary(self, scenes: int) -> dict:
        errors = np.array(self.profile_mm) if self.profile_mm else np.zeros((1, 2))
        c = self.count
        return {
            "scenes": scenes,
            "glasses": c["put out"],
            "find": {k: c[k] for k in ("found", "missed", "merged", "split", "false")}
            | {
                "position_mm_median": round(float(np.median(self.position_mm)), 1),
                "position_mm_worst": round(float(np.max(self.position_mm)), 1),
            },
            "view": {
                "chosen_unspoiled": c["chosen unspoiled"],
                "random_unspoiled": c["random unspoiled"],
                "judged": c["chosen views"],
                "handed_over": {k.split(": ")[1]: v for k, v in c.items() if k.startswith("handed over")},
            },
            "measure": {
                "measured": len(self.profile_mm),
                "height_mm_median": round(float(np.median(np.abs(errors[:, 0]))), 1),
                "height_mm_worst": round(float(np.abs(errors[:, 0]).max()), 1),
                "width_mm_median": round(float(np.median(errors[:, 1])), 1),
            },
        }

    def report(self, scenes: int, save: Path) -> None:
        """Print the summary and save it, so two approaches can be set side by side."""
        result = self.summary(scenes)
        find, view, measure = result["find"], result["view"], result["measure"]
        print(f"\n{scenes} held-out scenes, {result['glasses']} glasses\n")
        print(
            f"find     found {find['found']}, missed {find['missed']}, merged {find['merged']}, "
            f"split {find['split']}, false {find['false']}; position "
            f"{find['position_mm_median']} mm median, {find['position_mm_worst']} worst"
        )
        print(
            f"view     chosen place unspoiled {view['chosen_unspoiled']} of {view['judged']}, "
            f"random allowed place {view['random_unspoiled']} of {view['judged']}; "
            f"handed over {view['handed_over'] or 'none'}"
        )
        print(
            f"measure  {measure['measured']} glasses; height {measure['height_mm_median']} mm median, "
            f"{measure['height_mm_worst']} worst; width {measure['width_mm_median']} mm median"
        )
        save.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nsaved to {save}")
