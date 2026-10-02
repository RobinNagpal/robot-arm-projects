"""Draw training tables, train the four picture models, save their weights.

One table gives one overhead picture (TopNet) and up to SIDES side pictures,
each of a different glass from a place the geometry allows (Ranker, SideNet,
GripNet). So 200 tables is 200 overhead pictures and about 600 side pictures.

Every answer comes from the simulator, for free: which glass each pixel shows,
each glass's true shape and kind, whether a side picture was spoiled, and
where the project's grip rule holds the glass when its true shape is known.

    pixi run python train.py              # 200 tables
    pixi run python train.py --tables 50
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch

import nets
import render
import scoring
import tables
import viewpoints

HERE = Path(__file__).parent
WEIGHTS = HERE / "weights"
DATA = HERE / "data"

# Side pictures per training table, each of a different glass.
SIDES = 3


def side_examples(glasses: list[render.Glass], seed: int, rng: random.Random):
    """(glass index, camera angle) for up to SIDES side pictures of one table.

    Half the tables take the most crowded allowed place rather than a random
    one, as problem 2 does: spoiled pictures are rare, and a ranker shown a
    handful of them learns nothing from them.
    """
    seen = [viewpoints.seen(g) for g in glasses]
    picked = []
    for index in rng.sample(range(len(glasses)), min(SIDES, len(glasses))):
        target, others = seen[index], seen[:index] + seen[index + 1 :]
        options = [a for a in viewpoints.angles() if viewpoints.allowed(target, others, a)]
        if not options:
            continue
        if seed % 2:
            angle = min(options, key=lambda a: viewpoints.features(target, others, a)[2])
        else:
            angle = rng.choice(options)
        picked.append((index, float(angle)))
    return picked


def examples(count: int) -> dict[str, np.ndarray]:
    """Every training picture and answer, drawn from tables 0 to count - 1."""
    rng = random.Random(0)
    out = {k: [] for k in ("top_x", "top_y", "rank_x", "rank_y", "side_x", "side_y", "grip_y", "which")}
    for seed in range(count):
        spawned = tables.scene(seed)
        glasses = tables.to_render(spawned, [g.position[:2] for g in spawned])
        top = render.render(glasses, render.top_pose())
        out["top_x"].append(nets.top_input(top))
        out["top_y"].append(nets.top_target(top, glasses))

        seen = [viewpoints.seen(g) for g in glasses]
        for index, angle in side_examples(glasses, seed, rng):
            pose = render.side_pose(glasses[index].x, glasses[index].y, angle)
            side = render.render(glasses, pose)
            alone = render.render([glasses[index]], pose)
            out["rank_x"].append(viewpoints.features(seen[index], seen[:index] + seen[index + 1 :], angle))
            out["rank_y"].append(float(scoring.is_good(side, alone)))
            out["side_x"].append(nets.side_input(side))
            out["side_y"].append(nets.side_kind_target(glasses[index]))
            out["grip_y"].append(nets.grip_target(tables.glass_grip(spawned[index])))
            out["which"].append((seed, index, angle))
    return {k: np.asarray(v, dtype=np.float32) for k, v in out.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=200)
    count = parser.parse_args().tables
    assert count <= tables.TEST_SEEDS
    torch.manual_seed(0)
    WEIGHTS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)

    started = time.time()
    data = examples(count)
    np.savez_compressed(DATA / "pictures.npz", **data)
    counts = np.bincount(data["side_y"][:, 17].astype(int), minlength=4)
    kinds = ", ".join(f"{n} {k}" for k, n in zip(nets.KINDS, counts, strict=True))
    print(
        f"{count} tables drawn in {time.time() - started:.0f}s: {len(data['top_x'])} overhead, "
        f"{len(data['side_x'])} side pictures ({kinds}); "
        f"{int(data['rank_y'].sum())} unspoiled, {int(data['grip_y'][:, 0].sum())} holdable"
    )

    losses = {}

    started = time.time()
    top_net = nets.TopNet()
    loss = nets.fit(top_net, data["top_x"], data["top_y"], nets.top_loss, epochs=60, batch=8)
    losses["top_net"] = loss
    print(f"TopNet  loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    started = time.time()
    ranker = nets.Ranker()
    rank_x, rank_y = data["rank_x"], data["rank_y"]
    ranker.mean.copy_(torch.as_tensor(rank_x.mean(0)))
    ranker.spread.copy_(torch.as_tensor(rank_x.std(0) + 1e-6))
    # The spoiled views are the rare ones, so the unspoiled ones count for
    # less, until the two weigh the same in total.
    unspoiled = float(rank_y.mean())
    weight = (1 - unspoiled) / unspoiled
    rank_loss = lambda out, y: torch.nn.functional.binary_cross_entropy_with_logits(  # noqa: E731
        out, y, weight=torch.where(y > 0.5, weight, 1.0)
    )
    loss = nets.fit(ranker, rank_x, rank_y, rank_loss, epochs=300, batch=32)
    losses["ranker"] = loss
    print(f"Ranker  loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    started = time.time()
    side_net = nets.SideNet()
    loss = nets.fit(side_net, data["side_x"], data["side_y"], nets.side_loss, epochs=150, flip=True)
    losses["side_net"] = loss
    print(f"SideNet loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    started = time.time()
    grip_net = nets.GripNet()
    loss = nets.fit(grip_net, data["side_x"], data["grip_y"], nets.grip_loss, epochs=150, flip=True)
    losses["grip_net"] = loss
    print(f"GripNet loss {loss[0]:.3f} -> {loss[-1]:.3f}  ({time.time() - started:.0f}s)")

    for name, model in (
        ("top_net", top_net),
        ("ranker", ranker),
        ("side_net", side_net),
        ("grip_net", grip_net),
    ):
        torch.save(model.cpu().state_dict(), WEIGHTS / f"{name}.pt")
    (WEIGHTS / "losses.json").write_text(json.dumps(losses) + "\n")
    print(f"saved to {WEIGHTS}")


def load() -> dict[str, torch.nn.Module]:
    """The four trained picture models, by name."""
    models = {
        "top_net": nets.TopNet(),
        "ranker": nets.Ranker(),
        "side_net": nets.SideNet(),
        "grip_net": nets.GripNet(),
    }
    for name, model in models.items():
        model.load_state_dict(torch.load(WEIGHTS / f"{name}.pt"))
        model.eval()
    return models


if __name__ == "__main__":
    main()
