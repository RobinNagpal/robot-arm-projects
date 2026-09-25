"""Draw training scenes, train the three models, save their weights.

One scene gives one overhead picture (TopNet) and one side picture from a
random allowed place round a random glass (Ranker and SideNet). So SCENES
scenes is SCENES pictures for each model.

    pixi run python train.py            # 200 scenes
    pixi run python train.py --scenes 50
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import numpy as np
import torch

import models
import render
import scoring
import viewpoints

WEIGHTS = Path(__file__).parent / "weights"


def examples(count: int):
    rng = random.Random(0)
    top_x, top_y, rank_x, rank_y, side_x, side_y = [], [], [], [], [], []
    for seed in range(count):
        glasses = render.scene(seed)
        picture = render.render(glasses, render.top_pose())
        top_x.append(models.top_input(picture))
        top_y.append(models.top_target(picture, glasses))

        seen = [viewpoints.seen(g) for g in glasses]
        index = rng.randrange(len(glasses))
        target, others = seen[index], seen[:index] + seen[index + 1 :]
        options = [a for a in viewpoints.angles() if viewpoints.allowed(target, others, a)]
        if not options:
            continue
        # Half the time the most crowded place rather than a random one.
        # Spoiled views are rare, about one in eight, and a ranker that sees
        # twenty of them learns nothing from them.
        if seed % 2:
            angle = min(options, key=lambda a: viewpoints.features(target, others, a)[2])
        else:
            angle = rng.choice(options)
        pose = render.side_pose(target.x, target.y, angle)
        side = render.render(glasses, pose)
        alone = render.render([glasses[index]], pose)
        rank_x.append(viewpoints.features(target, others, angle))
        rank_y.append(float(scoring.is_good(side, alone)))
        side_x.append(models.side_input(side))
        side_y.append(models.side_target(glasses[index]))
    return [np.stack(v).astype(np.float32) for v in (top_x, top_y, rank_x, rank_y, side_x, side_y)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=200)
    count = parser.parse_args().scenes
    assert count <= render.TEST_SEEDS
    torch.manual_seed(0)
    WEIGHTS.mkdir(exist_ok=True)

    started = time.time()
    top_x, top_y, rank_x, rank_y, side_x, side_y = examples(count)
    print(
        f"{count} scenes drawn in {time.time() - started:.0f}s: "
        f"{len(top_x)} overhead, {len(side_x)} side pictures, {int(rank_y.sum())} of them unspoiled"
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
