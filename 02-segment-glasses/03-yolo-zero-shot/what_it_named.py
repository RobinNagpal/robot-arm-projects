"""What the borrowed model actually calls these glasses. The measurement behind the result.

    pixi run python 03-yolo-zero-shot/what_it_named.py --scenes 2

The filter on the category names is the whole of this solution's second step, so
whether the solution can work at all turns on one question the solution cannot
change: which of its own names the model reaches for when it is shown a grey
picture shaded from depth instead of the photographs its weights were fitted on.

The scorecard answers that only indirectly, as a count of glasses missed. This
file answers it directly, by printing every name the model offered and how often,
with no filter in front of it. One picture is a few tenths of a second, so
`--scenes` is small on purpose: the names it gives are the same ones over and
over, which is itself the finding.

Nothing here is allowed to change the filter. Reading these names and then adding
them to the accepted list would be fitting the filter on this cell's own data,
which is the one thing this solution promises not to do.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import drinking_vessels
import numpy as np
import yolo_zero_shot

import data
import render


def named(per_kind: int) -> dict:
    """Per kind of glass, every name the model offered and how often, over whole surveys."""
    counted = {kind: Counter() for kind in render.KINDS}
    glasses = dict.fromkeys(render.KINDS, 0)
    wanted = dict.fromkeys(render.KINDS, per_kind)

    for seed in data.held_out_seeds(per_kind * len(render.KINDS) * len(render.KINDS)):
        kind = render.KINDS[seed % len(render.KINDS)]
        if wanted[kind] <= 0:
            continue
        wanted[kind] -= 1
        example = data.spawned(seed)
        for sight in example.sights:
            answer = yolo_zero_shot.look(sight.picture)
            glasses[kind] += len(example.glasses)
            if answer.boxes is None:
                continue
            for number in np.asarray(answer.boxes.cls, dtype=int).ravel():
                counted[kind][answer.names[int(number)]] += 1

    return {
        kind: {
            "glasses on the table, counted once per picture": glasses[kind],
            "named": dict(names.most_common()),
            "named a drinking vessel": sum(
                count for name, count in names.items() if drinking_vessels.is_drinking_vessel(name)
            ),
        }
        for kind, names in counted.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenes", type=int, default=2, help="held-out scenes per kind of glass")
    given = parser.parse_args()

    report = named(given.scenes)
    for kind, got in report.items():
        print(f"{kind:20s} {got['named a drinking vessel']:3d} kept by the filter   {got['named']}")

    save = Path(__file__).parent / "results-names.json"
    save.write_text(json.dumps({"scenes per kind": given.scenes, "kinds": report}, indent=2) + "\n")
    print(f"\nsaved to {save}")


if __name__ == "__main__":
    main()
