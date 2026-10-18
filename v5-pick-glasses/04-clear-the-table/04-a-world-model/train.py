"""Fit the forward model on the collected pushes, and say how wrong it still is.

    pixi run python train.py

Reads every ``train*.npz`` in ``data/`` -- round 1's random pushes and round
2's planned ones, if they have been collected -- and checks the fitted copies
against ``validation.npz``, which comes from tables nothing was trained on. The
numbers printed at the end are what to expect at run time.

Every push is used mirrored as well. A push and its mirror image are both true
examples of the same physics, so a small set doubles for nothing.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import encoding
import numpy as np
import torch
from borrowed import DATA, WEIGHTS
from push_model import ENSEMBLE, Ensemble, PushNet, fit, sigmoid

# What a missed topple costs the fit, over and above the weight that already
# balances the rare answer against the common one.
#
# It is ten because the random pushes were doubled, and the two changes only
# work together. More pushes make the topple head stop sounding the alarm: on
# the 658 validation pushes the doubled set catches 51 topples of 70 against 57,
# while flagging 94 safe pushes against 116. Raising this cost puts the alarm
# back. Measured on nine clocked walks of a hundred and fifty tables below the
# held-out line, against the fit before either change: this separates 15.7
# tables a walk against 14.3, frees 42.3 glasses against 40.3, and loses 1.7
# against 3.0. Thirty was measured too and is worse on breakages; the README has
# all four corners.
TOPPLE_SCALE = 10.0


def load(folder: Path, doubted: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every collected round, with each push's mirror image beside it.

    ``doubted`` adds round 3, the pushes the copies disagreed about. It is off
    by default because that round was measured and not kept: over four search
    seeds on two hundred tuning tables it separated the same number of tables
    and put two and a half more glasses over, and the README says why.
    """
    paths = sorted(folder.glob("train*.npz"))
    if doubted:
        paths.append(folder / "doubted.npz")
    rounds = [np.load(path) for path in paths]
    if not rounds:
        raise SystemExit(f"no pushes in {folder}. Collect them first: pixi run python collect.py")
    x = np.concatenate([part["inputs"] for part in rounds])
    y = np.concatenate([part["outputs"] for part in rounds])
    mask = np.concatenate([part["mask"] for part in rounds])
    flipped_x, flipped_y = encoding.mirror(x, y)
    return (
        np.concatenate([x, flipped_x]),
        np.concatenate([y, flipped_y]),
        np.concatenate([mask, mask]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--save", type=str, default="", help="write the validation numbers to this file")
    parser.add_argument(
        "--doubted", action="store_true", help="also fit on round 3, which was measured and not kept"
    )
    parser.add_argument(
        "--topple-scale",
        type=float,
        default=TOPPLE_SCALE,
        help="multiply what a missed topple costs the fit; 1 is the balance before the pushes doubled",
    )
    arguments = parser.parse_args()
    # Held down on purpose: the machine this was fitted on was also running
    # another solution's measurement.
    torch.set_num_threads(arguments.threads)

    x, y, mask = load(DATA, arguments.doubted)
    toppled = float(y[:, encoding.TOPPLED].mean())
    print(
        f"{len(x) // 2} pushes, {len(x)} with their mirror images; "
        f"{100 * toppled:.1f}% toppled something, "
        f"{100 * float(mask[:, : encoding.MOVES].mean()):.0f}% of the movement labels were measured"
    )

    nets = []
    for copy in range(ENSEMBLE):
        started = time.perf_counter()
        net = PushNet()
        net.mean.copy_(torch.as_tensor(x.mean(0)))
        net.spread.copy_(torch.as_tensor(x.std(0) + 1e-6))
        history = fit(
            net,
            x,
            y,
            mask,
            epochs=arguments.epochs,
            seed=copy,
            topple_weight=arguments.topple_scale * (1 - toppled) / max(toppled, 1e-6),
        )
        print(
            f"copy {copy}: loss {history[0]:.3f} -> {history[-1]:.3f} "
            f"({time.perf_counter() - started:.0f}s)"
        )
        nets.append(net)
    ensemble = Ensemble(nets)
    ensemble.save(WEIGHTS)
    print(f"saved to {WEIGHTS}\n")

    check = np.load(DATA / "validation.npz")
    numbers = report(ensemble, check["inputs"], check["outputs"], check["mask"])
    if arguments.save:
        where = Path(arguments.save)
        held = json.loads(where.read_text()) if where.exists() else {}
        # What a missed topple cost this fit, beside what the fit achieved. The
        # setting and the numbers belong together: the same data at a different
        # cost is a different model, and the README compares four of them.
        held["model"] = {"topple_scale": arguments.topple_scale} | numbers
        where.write_text(json.dumps(held, indent=2) + "\n")


def report(ensemble: Ensemble, x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict:
    """How far out the model is on pushes from tables it never saw.

    Two things are asked of it, and they are not the same question. How far
    out it is about where a glass goes, which is what the search's cost rests
    on; and how well it can tell a push that topples something from one that
    does not, which is what every glass on the table rests on.
    """
    out = ensemble.predict(x)
    mean = out.mean(0)
    fell = y[:, encoding.TOPPLED].astype(bool)
    # Only pushes whose own glass was really measured again say anything about
    # where a glass lands.
    measured = mask[:, 0].astype(bool) & ~fell
    error = np.hypot(*(mean[measured, :2] - y[measured, :2]).T) * encoding.MOVE_SCALE * 1000
    travel = np.hypot(*y[measured, :2].T) * encoding.MOVE_SCALE * 1000
    worst = sigmoid(out[:, :, encoding.TOPPLED]).max(0)
    # Most collected pushes never reach the glass -- the reach is drawn over
    # the whole range on purpose, because that is what teaches the model where
    # contact is -- so the median push moves nothing and a median error over
    # all of them flatters the model. The pushes that really moved a glass are
    # the ones the search's cost rests on, so they are reported separately.
    went = travel > 2.0

    numbers = {
        "pushes": int(len(x)),
        "landing_mm_median": round(float(np.median(error)), 1),
        "landing_mm_90th": round(float(np.percentile(error, 90)), 1),
        "glass_moved_mm_median": round(float(np.median(travel)), 1),
        "pushes_that_moved_the_glass": int(went.sum()),
        "landing_mm_median_when_moved": round(float(np.median(error[went])), 1),
        "landing_mm_90th_when_moved": round(float(np.percentile(error[went], 90)), 1),
        "glass_moved_mm_median_when_moved": round(float(np.median(travel[went])), 1),
        "toppled": int(fell.sum()),
        "safe": int((~fell).sum()),
    }
    for limit in (0.01, 0.1, 0.5):
        numbers[f"topples_caught_at_{limit}"] = int((worst[fell] > limit).sum())
        numbers[f"safe_pushes_flagged_at_{limit}"] = int((worst[~fell] > limit).sum())
    print(
        f"validation, {numbers['pushes']} pushes on tables nothing was trained on\n"
        f"  where the pushed glass lands: {numbers['landing_mm_median']} mm out at the median, "
        f"{numbers['landing_mm_90th']} mm at the 90th "
        f"(it really moved {numbers['glass_moved_mm_median']} mm at the median)\n"
        f"  of the {numbers['pushes_that_moved_the_glass']} that really moved it "
        f"({numbers['glass_moved_mm_median_when_moved']} mm at the median): "
        f"{numbers['landing_mm_median_when_moved']} mm out at the median, "
        f"{numbers['landing_mm_90th_when_moved']} mm at the 90th\n"
        f"  toppling: {numbers['toppled']} of {numbers['pushes']} pushes put a glass over"
    )
    for limit in (0.01, 0.1, 0.5):
        print(
            f"    at a {limit} chance: {numbers[f'topples_caught_at_{limit}']} of {numbers['toppled']} "
            f"caught, {numbers[f'safe_pushes_flagged_at_{limit}']} of {numbers['safe']} safe pushes flagged"
        )
    return numbers


if __name__ == "__main__":
    main()
