"""Write a few of the collected pushes out as JSON, to see what the model is trained on.

The pushes are kept in data/*.npz as two tables of numbers: 34 per push going
in, 14 coming out. This writes the first few as they are, and again in
millimetres with a name on each, so one can be read beside the other.

    pixi run python examples.py                        # 20 random pushes from round 1
    pixi run python examples.py --round train_planned  # the planner's own, round 2
    pixi run python examples.py --count 100

Writes traces/examples-<round>.json.
"""

from __future__ import annotations

import argparse
import json

import features
import numpy as np
from collect import DATA
from trace_table import TRACES, compact, mm, rounded

from bench import KINDS


def example(x: np.ndarray, y: np.ndarray) -> dict:
    """One push: what the model is given, and what it is taught to answer."""
    k = len(KINDS)
    blocked, toppled = bool(y[features.BLOCKED]), bool(y[features.TOPPLED])
    others, moved = [], []
    for slot in range(features.OTHERS):
        along, across, widest, height, there = x[k + 5 + 5 * slot : k + 10 + 5 * slot]
        if not there:
            continue
        others.append(
            {
                "ahead_along_the_push": mm(along * features.PLACE_SCALE),
                "to_the_left_of_the_push": mm(across * features.PLACE_SCALE),
                "widest": mm(widest * features.PLACE_SCALE),
                "height": mm(height * features.PLACE_SCALE),
            }
        )
        moved.append(mm(y[2 + 2 * slot : 4 + 2 * slot] * features.MOVE_SCALE))
    return {
        "in_words": "the jaw was blocked on the way down, so nothing was pushed"
        if blocked
        else f"the glass moved {mm(y[0] * features.MOVE_SCALE)} mm along the push"
        + (", and something toppled" if toppled else ""),
        "input_row": rounded(x),
        "output_row": rounded(y),
        "input": {
            "kind": KINDS[int(np.argmax(x[:k]))],
            "pushed_glass": dict(
                zip(("height", "widest", "foot"), mm(x[k : k + 3] * features.PLACE_SCALE), strict=True)
            ),
            "push": {
                "offset_left_of_the_glass_middle": mm(x[k + 3] * features.PLACE_SCALE),
                "travel": mm(x[k + 4] * features.MOVE_SCALE),
            },
            "other_glasses_nearest_first": others,
        },
        "output": {
            "pushed_glass_moved_along_across": mm(y[:2] * features.MOVE_SCALE),
            "other_glasses_moved_along_across": moved,
            "something_toppled": toppled,
            "jaw_blocked_on_the_way_down": blocked,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", default="train", help="train, train_planned or validation")
    parser.add_argument("--count", type=int, default=20)
    arguments = parser.parse_args()
    data = np.load(DATA / f"{arguments.round}.npz")
    x, y = data["inputs"], data["outputs"]
    document = {
        "file": f"data/{arguments.round}.npz",
        "pushes_in_the_file": len(x),
        "of_which_toppled_something": int(y[:, features.TOPPLED].sum()),
        "of_which_blocked_on_the_way_down": int(y[:, features.BLOCKED].sum()),
        "units": "millimetres; the two 'row' lists are the numbers as stored. Places and sizes are "
        "divided by 100 mm, the push's travel and every movement by 50 mm",
        "pushes": [example(x[i], y[i]) for i in range(min(arguments.count, len(x)))],
    }
    TRACES.mkdir(exist_ok=True)
    save = TRACES / f"examples-{arguments.round}.json"
    save.write_text(compact(json.dumps(document, indent=1)))
    print(f"{len(document['pushes'])} of {len(x)} pushes -> {save}")


if __name__ == "__main__":
    main()
