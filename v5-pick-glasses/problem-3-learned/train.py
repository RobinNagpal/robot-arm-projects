"""Train the forward model on the collected pushes, and say how good it is.

Reads data/train.npz and data/validation.npz from collect.py. The validation
pushes are from tables never trained on, so the numbers printed at the end are
what to expect at run time.

    pixi run python train.py
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch

import features
from collect import DATA
from model import ENSEMBLE, Ensemble, PushNet, fit, sigmoid

WEIGHTS = Path(__file__).parent / "weights"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=120)
    arguments = parser.parse_args()
    torch.set_num_threads(8)

    # Round 1's random pushes, and round 2's planned ones if collected.
    rounds = [np.load(path) for path in sorted(DATA.glob("train*.npz"))]
    check = np.load(DATA / "validation.npz")
    x = np.concatenate([r["inputs"] for r in rounds])
    y = np.concatenate([r["outputs"] for r in rounds])
    x, y = np.concatenate([x, features.mirror(x, y)[0]]), np.concatenate([y, features.mirror(x, y)[1]])
    toppled = float(y[:, features.TOPPLED].mean())
    print(f"{len(x) // 2} pushes, {len(x)} with their mirror images; {100 * toppled:.1f}% toppled something")

    nets = []
    for i in range(ENSEMBLE):
        started = time.time()
        net = PushNet()
        net.mean.copy_(torch.as_tensor(x.mean(0)))
        net.spread.copy_(torch.as_tensor(x.std(0) + 1e-6))
        history = fit(net, x, y, epochs=arguments.epochs, seed=i, topple_weight=(1 - toppled) / toppled)
        print(f"copy {i}: loss {history[0]:.3f} -> {history[-1]:.3f} ({time.time() - started:.0f}s)")
        nets.append(net)
    ensemble = Ensemble(nets)
    ensemble.save(WEIGHTS)
    print(f"saved to {WEIGHTS}\n")
    report(ensemble, check["inputs"], check["outputs"])


def report(ensemble: Ensemble, x: np.ndarray, y: np.ndarray) -> dict:
    """How far out the model is on pushes from tables it never saw."""
    out = ensemble.predict(x)
    mean = out.mean(0)
    moved = ~y[:, features.BLOCKED].astype(bool) & ~y[:, features.TOPPLED].astype(bool)
    error = np.hypot(*(mean[moved, :2] - y[moved, :2]).T) * features.MOVE_SCALE * 1000
    travel = np.hypot(*y[moved, :2].T) * features.MOVE_SCALE * 1000

    topple_worst = sigmoid(out[:, :, features.TOPPLED]).max(0)
    fell = y[:, features.TOPPLED].astype(bool)
    blocked_p = sigmoid(out[:, :, features.BLOCKED]).mean(0)
    blocked = y[:, features.BLOCKED].astype(bool)
    result = {
        "pushes": int(len(x)),
        "landing_mm_median": float(np.median(error)),
        "landing_mm_90th": float(np.percentile(error, 90)),
        "glass_moved_mm_median": float(np.median(travel)),
        "toppled": int(fell.sum()),
        "topples_caught_at_0.1": int((topple_worst[fell] > 0.1).sum()),
        "safe_pushes_flagged_at_0.1": int((topple_worst[~fell] > 0.1).sum()),
        "blocked_right": float(((blocked_p > 0.5) == blocked).mean()),
    }
    print(
        f"validation, {result['pushes']} pushes on unseen tables\n"
        f"  where the pushed glass lands: {result['landing_mm_median']:.1f} mm out median, "
        f"{result['landing_mm_90th']:.1f} mm at the 90th percentile "
        f"(it moved {result['glass_moved_mm_median']:.0f} mm median)\n"
        f"  toppling: {result['topples_caught_at_0.1']} of {result['toppled']} caught at a 0.1 chance; "
        f"{result['safe_pushes_flagged_at_0.1']} of {len(x) - result['toppled']} safe pushes flagged\n"
        f"  blocked on the way down: right {100 * result['blocked_right']:.0f}% of the time"
    )
    return result


if __name__ == "__main__":
    main()
