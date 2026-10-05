"""Draw training scenes, train the three models, save their weights.

    pixi run python 02-train-from-scratch/train.py            # 200 scenes
    pixi run python 02-train-from-scratch/train.py --scenes 50

**TopNet trains on the bench's own arrangements, from the bench's own
stations.** That is what makes its scorecard comparable with the other five: it
is marked on the pictures it was fitted on the likes of, and never on an
arrangement it learned from, because `data.training` draws only below the
bench's dividing line. One scene gives one picture per station, so SCENES scenes
is three times SCENES pictures. Half of them are the crowded family, which is
`data.CROWDED_SHARE`: the cell's own layout rule never once shows the network a
pair that a page of arithmetic could not already separate, so the edge of the
specification is put in the middle of the training set.

Its labels are the simulator's own record of which glass each pixel shows, which
is rung one of the two the document describes. Rung two, where the labels come
from the arm's own movement instead, is a design and is not built.

**Ranker and SideNet are not part of problem 2** and are trained as they always
were, from `render.scene` and one side picture per scene. The bench stops at a
mask, so nothing in `run.py` uses either of them; they are kept because problem
4's documents name them as parts its pipeline reuses.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import models
import numpy as np
import torch
import viewpoints

import data
import render
import scoring

WEIGHTS = Path(__file__).parent / "weights"


def pick_view(glasses, seed: int, rng: random.Random):
    """The glass and the place one training scene's side picture is taken of.

    (index, target, others, angle), or None when no place round the glass is
    allowed. ``rng`` has to be the one generator carried from scene to scene,
    which is what lets show_ranker.py draw the same examples again.
    """
    seen = [viewpoints.seen(g) for g in glasses]
    index = rng.randrange(len(glasses))
    target, others = seen[index], seen[:index] + seen[index + 1 :]
    options = [a for a in viewpoints.angles() if viewpoints.allowed(target, others, a)]
    if not options:
        return None
    # Half the time the most crowded place rather than a random one.
    # Spoiled views are rare, about one in eight, and a ranker that sees
    # twenty of them learns nothing from them.
    if seed % 2:
        angle = min(options, key=lambda a: viewpoints.features(target, others, a)[2])
    else:
        angle = rng.choice(options)
    return index, target, others, angle


def top_examples(count: int):
    """TopNet's pictures: every station of every training scene, and its labels."""
    top_x, top_y = [], []
    for example in data.training(count):
        for sight in example.sights:
            top_x.append(models.top_input(sight.picture))
            top_y.append(models.top_target(sight.picture, example.glasses))
    return [np.stack(v).astype(np.float32) for v in (top_x, top_y)]


def side_examples(count: int):
    """The Ranker's and SideNet's pictures: one side view per scene."""
    rng = random.Random(0)
    rank_x, rank_y, side_x, side_y = [], [], [], []
    for seed in range(count):
        glasses = render.scene(seed)
        picked = pick_view(glasses, seed, rng)
        if picked is None:
            continue
        index, target, others, angle = picked
        pose = render.side_pose(target.x, target.y, angle)
        side = render.render(glasses, pose)
        alone = render.render([glasses[index]], pose)
        rank_x.append(viewpoints.features(target, others, angle))
        rank_y.append(float(scoring.is_good(side, alone)))
        side_x.append(models.side_input(side))
        side_y.append(models.side_target(glasses[index]))
    return [np.stack(v).astype(np.float32) for v in (rank_x, rank_y, side_x, side_y)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=200)
    count = parser.parse_args().scenes
    assert count <= render.TEST_SEEDS
    torch.manual_seed(0)
    WEIGHTS.mkdir(exist_ok=True)

    started = time.time()
    top_x, top_y = top_examples(count)
    rank_x, rank_y, side_x, side_y = side_examples(count)
    print(
        f"{count} scenes drawn in {time.time() - started:.0f}s: "
        f"{len(top_x)} survey pictures over {len(data.stations())} stations, "
        f"{len(side_x)} side pictures, {int(rank_y.sum())} of them unspoiled"
    )

    started = time.time()
    top_net = models.TopNet()
    loss = models.fit(top_net, top_x, top_y, models.top_loss, epochs=60, batch=8)
    print(f"TopNet  loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    started = time.time()
    ranker = models.Ranker()
    ranker.mean.copy_(torch.as_tensor(rank_x.mean(0)))
    ranker.spread.copy_(torch.as_tensor(rank_x.std(0) + 1e-6))
    # The spoiled views are the rare ones, so the unspoiled ones count for
    # less, until the two weigh the same in total.
    unspoiled = float(rank_y.mean())
    weight = (1 - unspoiled) / unspoiled
    rank_loss = lambda out, y: torch.nn.functional.binary_cross_entropy_with_logits(  # noqa: E731
        out, y, weight=torch.where(y > 0.5, weight, 1.0)
    )
    loss = models.fit(ranker, rank_x, rank_y, rank_loss, epochs=300, batch=32)
    print(f"Ranker  loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    started = time.time()
    side_net = models.SideNet()
    side_loss = lambda out, y: (out - y).abs().mean()  # noqa: E731
    loss = models.fit(side_net, side_x, side_y, side_loss, epochs=150, flip=True)
    print(f"SideNet loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    for name, model in (("top_net", top_net), ("ranker", ranker), ("side_net", side_net)):
        torch.save(model.cpu().state_dict(), WEIGHTS / f"{name}.pt")
    print(f"saved to {WEIGHTS}")


if __name__ == "__main__":
    main()
