"""Train the push model on the collected pushes, and say how good it is.

Reads data/pushes.npz and data/pushes_validation.npz from collect.py. The
validation pushes are from tables never trained on.

    pixi run python train_push.py
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch

import push_features as features
from collect import DATA
from push_model import ENSEMBLE, Ensemble, PushNet, fit, sigmoid
from train import WEIGHTS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    arguments = parser.parse_args()
    torch.set_num_threads(8)

    pushes, check = np.load(DATA / "pushes.npz"), np.load(DATA / "pushes_validation.npz")
    x, y = pushes["inputs"], pushes["outputs"]
    mx, my = features.mirror(x, y)
    x, y = np.concatenate([x, mx]), np.concatenate([y, my])
    toppled = float(y[:, features.TOPPLED].mean())
    print(f"{len(x) // 2} pushes, {len(x)} with their mirror images; {100 * toppled:.1f}% toppled something")

    nets, losses = [], []
    for i in range(ENSEMBLE):
        started = time.time()
        net = PushNet()
        net.mean.copy_(torch.as_tensor(x.mean(0)))
        net.spread.copy_(torch.as_tensor(x.std(0) + 1e-6))
        history = fit(net, x, y, epochs=arguments.epochs, seed=i, topple_weight=(1 - toppled) / toppled)
        print(f"copy {i}: loss {history[0]:.3f} -> {history[-1]:.3f} ({time.time() - started:.0f}s)")
        nets.append(net)
        losses.append(history)
    ensemble = Ensemble(nets)
    WEIGHTS.mkdir(exist_ok=True)
    ensemble.save(WEIGHTS)
    (WEIGHTS / "push_losses.json").write_text(json.dumps(losses) + "\n")
    print(f"saved to {WEIGHTS}\n")
    report(ensemble, check["inputs"], check["outputs"])


def report(ensemble: Ensemble, x: np.ndarray, y: np.ndarray) -> dict:
    """How far out the model is on pushes from tables it never saw, by whether the kind was known."""
    out = ensemble.predict(x)
    mean = out.mean(0)
    known = x[:, features.LABELS.index(features.NOT_MEASURED)] == 0
    moved = ~y[:, features.BLOCKED].astype(bool) & ~y[:, features.TOPPLED].astype(bool)
    error = np.hypot(*(mean[:, :2] - y[:, :2]).T) * features.MOVE_SCALE * 1000
    worst = sigmoid(out[:, :, features.TOPPLED]).max(0)
    fell = y[:, features.TOPPLED].astype(bool)
    blocked_p = sigmoid(out[:, :, features.BLOCKED]).mean(0)
    blocked = y[:, features.BLOCKED].astype(bool)
    result = {"pushes": int(len(x)), "blocked_right": float(((blocked_p > 0.5) == blocked).mean())}
    print(f"validation, {len(x)} pushes on unseen tables")
    for name, rows in (("kind known", known), ("not measured", ~known)):
        landing = error[rows & moved]
        result[name] = {
            "pushes": int(rows.sum()),
            "landing_mm_median": float(np.median(landing)),
            "toppled": int((fell & rows).sum()),
            "topples_caught_at_0.1": int((worst[fell & rows] > 0.1).sum()),
            "safe_flagged_at_0.1": int((worst[~fell & rows] > 0.1).sum()),
        }
        r = result[name]
        print(
            f"  {name:13s} {r['pushes']} pushes: pushed glass lands {r['landing_mm_median']:.1f} mm from the "
            f"prediction, median; toppling caught {r['topples_caught_at_0.1']} of {r['toppled']} "
            f"at a 0.1 chance, "
            f"{r['safe_flagged_at_0.1']} safe pushes flagged"
        )
    print(f"  blocked on the way down: right {100 * result['blocked_right']:.0f}% of the time")
    (WEIGHTS / "push_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    main()
