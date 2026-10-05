"""Fit the policy on the collected demonstrations, from random numbers.

**What is fitted** is one mapping: the straight-down picture of a crowded
table, to the chunk of jaw waypoints the teacher's push turned out to be.
Nothing else. No reward, no outcome, no geometry. The loss is the model's
own --- L1 against the demonstrated chunk, with ACT's variational term on
top --- and it measures only how close the action was to the teacher's.

**Where it saves** is ``weights/<rung>-<seed>/``: the network, and the
scaling the numbers were put on, beside each other so a run cannot load one
without the other. A summary of every seed goes to
``weights/<rung>-training.json``.

**Several seeds, because one training run is not a measurement.** Training
varies with its own random seed, so the bench asks for several and for the
spread across them. Each seed here is a separate fit of the same model on
the same data, saved separately, and ``run.py`` evaluates all of them.

**The numbers printed at the end are not the score.** They are how far the
fitted chunk is from the teacher's chunk, in millimetres, on tables the fit
saw and on tables it did not. Both are printed because the gap between them
is the thing worth watching: a small error on fitted tables beside a large one
on unseen tables means the policy has memorised rather than generalised, and
the cure for that is more demonstrations rather than more steps. Neither
number is the score. The score is the outcome on the held-out tables, and only
``run.py`` measures it.

One seed at a time is the usual way to run it, because a seed takes of order
an hour and a shell that drops takes the whole run with it::

    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 1 --first-seed 0
    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 1 --first-seed 1
    pixi run python -u 03-imitation-from-demonstrations/train.py --rung diffusion --seeds 1
    pixi run python -u 03-imitation-from-demonstrations/train.py --steps 200 --seeds 1  # a smoke test

Every seed appends to the same summary, so stopping between seeds loses
nothing already fitted.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from collect import CHECK, DEMOS
from policy import KINDS, Imitator, Scale, where_to_run

HERE = Path(__file__).parent
WEIGHTS = HERE / "weights"

# The vision backbone starts from random numbers here rather than from
# ImageNet, so it is fitted at the same rate as everything else. LeRobot's
# own presets hold it back, which suits a downloaded backbone and not this
# one.
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 1e-4
WARMUP = 500
# Sixteen fits on this machine's graphics processor at the size the policy
# reads, and it is twice the samples per step for well under twice the time.
BATCH = 16


def folder(rung: str, seed: int) -> Path:
    return WEIGHTS / f"{rung}-{seed}"


def learning_rate(step: int, steps: int, peak: float) -> float:
    """Warm up, then cosine down to a tenth. Standard, and it matters at this few steps."""
    if step < WARMUP:
        return peak * (step + 1) / WARMUP
    through = (step - WARMUP) / max(1, steps - WARMUP)
    return peak * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * through)))


def fit(
    rung: str,
    pictures: np.ndarray,
    actions: np.ndarray,
    scale: Scale,
    seed: int,
    steps: int,
    batch: int,
    peak: float,
) -> tuple[Imitator, list[float]]:
    """One fit of one model on all the demonstrations. Returns it and its loss curve."""
    model = Imitator.new(rung, scale, seed=seed, device=where_to_run())
    model.net.train()
    optimiser = torch.optim.AdamW(model.net.parameters(), lr=peak, weight_decay=WEIGHT_DECAY)
    rng = np.random.default_rng(seed)
    curve, running, clock = [], [], time.time()
    for step in range(steps):
        for group in optimiser.param_groups:
            group["lr"] = learning_rate(step, steps, peak)
        rows = rng.integers(0, len(actions), size=batch)
        loss = model.loss(pictures[rows], actions[rows])
        loss.backward()
        optimiser.step()
        optimiser.zero_grad(set_to_none=True)
        running.append(float(loss.detach()))
        if (step + 1) % max(1, steps // 20) == 0:
            curve.append(round(float(np.mean(running)), 4))
            running = []
            print(
                f"  seed {seed} step {step + 1}/{steps}: loss {curve[-1]:.3f}, "
                f"{(time.time() - clock) / 60:.0f} min",
                flush=True,
            )
    return model, curve


def how_far_off(model: Imitator, pictures: np.ndarray, actions: np.ndarray, most: int = 200) -> dict:
    """How far the fitted chunk is from the teacher's, on pictures never fitted on.

    A diagnostic, not a score. A policy can be close to its teacher on every
    waypoint and still clear fewer tables, and it can differ from the teacher
    and do as well.
    """
    count = min(most, len(actions))
    gaps, turns, ends = [], [], []
    for i in range(count):
        guess = model.chunk(pictures[i])
        want = actions[i]
        gaps.append(1000 * np.hypot(guess[:, 0] - want[:, 0], guess[:, 1] - want[:, 1]))
        turns.append(
            np.degrees(
                np.abs(
                    np.arctan2(
                        guess[:, 4] * want[:, 3] - guess[:, 3] * want[:, 4],
                        guess[:, 3] * want[:, 3] + guess[:, 4] * want[:, 4],
                    )
                )
            )
        )
        ends.append(1000 * math.dist(guess[-1, :2], want[-1, :2]))
    gaps, turns = np.concatenate(gaps), np.concatenate(turns)
    return {
        "chunks": count,
        "waypoint_mm_median": round(float(np.median(gaps)), 1),
        "waypoint_mm_90th": round(float(np.percentile(gaps, 90)), 1),
        "heading_deg_median": round(float(np.median(turns)), 1),
        "last_waypoint_mm_median": round(float(np.median(ends)), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rung", choices=KINDS, default="act")
    parser.add_argument("--seeds", type=int, default=3, help="separate fits, because one is not a measure")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--steps", type=int, default=10000)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--lr", type=float, default=LEARNING_RATE)
    arguments = parser.parse_args()

    held = np.load(DEMOS)
    pictures, actions = held["pictures"], held["actions"]
    checking = np.load(CHECK)
    scale = Scale.of(pictures, actions)
    device = where_to_run()
    print(
        f"{len(actions)} demonstrations of {actions.shape[1]} waypoints from "
        f"{len(np.unique(held['tables']))} tables; fitting {arguments.rung} on {device}"
    )

    WEIGHTS.mkdir(exist_ok=True)
    summary = WEIGHTS / f"{arguments.rung}-training.json"
    # A seed takes of order an hour, so seeds are usually fitted in separate
    # runs. Earlier ones are read back rather than written over.
    report = json.loads(summary.read_text()) if summary.exists() else {"seeds": []}
    report |= {"rung": arguments.rung, "device": device, "demonstrations": int(len(actions))}
    for seed in range(arguments.first_seed, arguments.first_seed + arguments.seeds):
        started = time.time()
        model, curve = fit(
            arguments.rung, pictures, actions, scale, seed, arguments.steps, arguments.batch, arguments.lr
        )
        spent = time.time() - started
        model.save(folder(arguments.rung, seed))
        off = how_far_off(model, checking["pictures"], checking["actions"])
        on = how_far_off(model, pictures, actions)
        print(
            f"seed {seed}: loss {curve[0]:.3f} -> {curve[-1]:.3f} in {spent / 60:.0f} min\n"
            f"  per waypoint, against the teacher's own chunk: "
            f"{on['waypoint_mm_median']} mm on tables it was fitted on, "
            f"{off['waypoint_mm_median']} mm on tables it never saw\n"
            f"  heading: {on['heading_deg_median']} deg fitted, {off['heading_deg_median']} deg unseen "
            f"-> {folder(arguments.rung, seed)}"
        )
        report["seeds"] = [row for row in report["seeds"] if row["seed"] != seed]
        report["seeds"].append(
            {
                "seed": seed,
                "steps": arguments.steps,
                "batch": arguments.batch,
                "learning_rate": arguments.lr,
                "minutes": round(spent / 60, 1),
                "loss": curve,
                "against_the_teacher": {"tables_it_never_saw": off, "tables_it_was_fitted_on": on},
            }
        )
        report["seeds"].sort(key=lambda row: row["seed"])
        summary.write_text(json.dumps(report, indent=2) + "\n")

    print(
        f"\nsaved to {WEIGHTS}. The millimetres above say how close the student is to its teacher,\n"
        f"which is not the score: run.py measures the outcome on the held-out tables."
    )


if __name__ == "__main__":
    main()
