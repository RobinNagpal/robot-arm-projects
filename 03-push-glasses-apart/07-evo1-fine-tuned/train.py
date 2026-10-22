"""Fit Evo-1's action half on the teacher's pushes, and say how far it got.

**What is fitted.** The action half only. Evo-1's own first training stage
freezes the vision-language half, so the 653 million borrowed numbers are
never written to and the 122 million in the flow-matching head are. **Where
it is saved**: those 122 million numbers alone, beside this file, never a copy
of the borrowed weights. It is written at every check and not only at the end,
so a run that has to be stopped leaves a fit that can be scored, and
``training.json`` beside it says how many steps went into what is there.

**What it is fitted towards.** [Solution 6](../06-smolvla-fine-tuned)'s
demonstrations, which are the paths the teacher's jaw really followed, used as
that folder wrote them rather than collected again. Using the same file is
what makes this solution's score comparable with solution 6's: the two differ
in the model and in nothing else, not even in the simulator's randomness.

**The loss cannot be read as a distance.** Evo-1 draws its chunk by flow
matching, so the training shows it a target with noise mixed in and asks for
the direction back towards the target. The number that prints is a direction
error and not millimetres.

**So a distance is measured as well**, because the loss alone says nothing a
reader can picture. Every so often the model is asked for a chunk on tables it
was not fitted on, the answer is read as jaw waypoints, and the median
distance from the teacher's own waypoints is reported in millimetres. The same
measurement is taken before the first step, when the action half is still
random. That first number is what fitting has to beat.

**Why the effort is solution 6's effort.** The step count, the batch and the
learning rate are the ones solution 6 uses. They were not chosen for this
model and are probably not its best, but a newer model given more training
than the one it is compared with would measure training as well as the model,
and this solution exists to measure only the model. What is spent is recorded
so that a later run can spend more on purpose.

    pixi run python 07-evo1-fine-tuned/train.py
    pixi run python 07-evo1-fine-tuned/train.py --steps 200 --batch 2
    pixi run python 07-evo1-fine-tuned/train.py --seed 1 --into fitted-1
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from evo import BACKBONE, DENOISING_STEPS, FITTED, LAYERS, STAGE, built, counts, head, scaled, span
from partners import CAMERA, FITTING, REPO, SLOTS, TUNING, described, device_for, to_jaw
from torch.utils.data import DataLoader

HERE = Path(__file__).parent

# Solution 6's recipe, for the reason the docstring gives.
STEPS = 1000
BATCH = 4
LEARNING_RATE = 1e-4
WARMUP = 100
CHECK_EVERY = 500
# Tuning chunks measured at a check. Each one is a walk from noise through
# DENOISING_STEPS passes of the whole model, so this is the expensive part of
# a check and there are deliberately few of them.
CHECK_CHUNKS = 8


def loaded(root: Path):
    """One of solution 6's demonstration sets, as a LeRobot dataset."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    if not (root / "meta").exists():
        raise FileNotFoundError(
            f"no demonstrations at {root}. Make them with "
            "`pixi run python 06-smolvla-fine-tuned/demonstrations.py`."
        )
    return LeRobotDataset(REPO, root=root)


def ready(items: list[dict], chunk: int, pre) -> dict:
    """A batch of demonstrations, prepared the way one observation is prepared at run time.

    The pictures are scaled to the side the checkpoint insists on and the flat
    chunk is folded back into waypoints, and then the model's own
    pre-processing does the rest, so what it is fitted on and what it is asked
    go through one piece of code.
    """
    batch = {
        CAMERA: scaled(torch.stack([item[CAMERA] for item in items])),
        "observation.state": torch.stack([item["observation.state"] for item in items]),
        "action": torch.stack([item["action"].reshape(chunk, SLOTS) for item in items]),
        "action_is_pad": torch.zeros(len(items), chunk, dtype=torch.bool),
        "task": [item["task"] for item in items],
    }
    return pre(batch)


def chunk_error_mm(policy, pre, post, data, chunk: int, how_many: int) -> dict:
    """How far the model's waypoints land from the teacher's, in millimetres.

    The answer is drawn from noise, so this is one sample of a distribution
    and not a fixed number. It is still the only figure here a reader can
    picture.
    """
    policy.eval()
    gaps = []
    for i in range(min(how_many, len(data))):
        item = data[i]
        batch = pre(
            {
                CAMERA: scaled(item[CAMERA]).unsqueeze(0),
                "observation.state": item["observation.state"].unsqueeze(0),
                "task": [item["task"]],
            }
        )
        policy.reset()
        with torch.no_grad():
            said = post(policy.predict_action_chunk(batch))[0].cpu().numpy().astype(float)
        wanted = to_jaw(item["action"].reshape(chunk, SLOTS).numpy().astype(float))
        gaps.append(1000 * np.hypot(*(to_jaw(said)[:, :2] - wanted[:, :2]).T))
    policy.train()
    flat = np.concatenate(gaps)
    return {"median": round(float(np.median(flat)), 1), "worst": round(float(flat.max()), 1)}


def memory_gib(device: str) -> float:
    """How much of the machine's memory the fitting is holding, gibibytes.

    Whether a 0.77B model can be fitted on a laptop is this number, so it is
    measured rather than estimated.
    """
    if device == "mps":
        return torch.mps.current_allocated_memory() / 2**30
    if device == "cuda":
        return torch.cuda.max_memory_allocated() / 2**30
    return 0.0


def rate(step: int, steps: int, top: float) -> float:
    """Warm up, then fall away as a cosine. The ordinary schedule, and nothing is tuned in it."""
    if step < WARMUP:
        return top * (step + 1) / WARMUP
    through = (step - WARMUP) / max(1, steps - WARMUP)
    return top * 0.5 * (1 + math.cos(math.pi * through))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--lr", type=float, default=LEARNING_RATE)
    parser.add_argument("--seed", type=int, default=0, help="the training seed; the spread needs several")
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    parser.add_argument("--check-every", type=int, default=CHECK_EVERY)
    parser.add_argument("--chunks", type=int, default=CHECK_CHUNKS, help="tuning chunks measured at a check")
    parser.add_argument("--into", default=None, help="folder for the fit, for a second seed")
    arguments = parser.parse_args()

    where = arguments.device or device_for()
    torch.manual_seed(arguments.seed)
    shape = described(FITTING)
    chunk = shape["chunk"]
    fitting, tuning = loaded(FITTING), loaded(TUNING)
    print(f"{fitting.num_frames} demonstrations from {fitting.num_episodes} tables, {len(tuning)} to tune on")

    stats = {"observation.state": span(), "action": span()}
    policy, pre, post = built(chunk, stats, where)
    moving, total = counts(policy)
    print(f"evo-1       {BACKBONE}, {LAYERS} layers, {STAGE}, {DENOISING_STEPS} denoising steps")
    print(f"            {moving / 1e6:.1f}M numbers move of {total / 1e6:.1f}M, on {where}")

    loader = DataLoader(
        fitting,
        batch_size=arguments.batch,
        shuffle=True,
        num_workers=0,
        drop_last=True,
        collate_fn=lambda items: ready(items, chunk, pre),
    )
    optimiser = torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad], lr=arguments.lr)

    # Before the first step the action half is still random, so this is the
    # number fitting has to beat.
    history = [{"step": 0, "tuning_mm": chunk_error_mm(policy, pre, post, tuning, chunk, arguments.chunks)}]
    print(f"step     0  unfitted, tuning {history[0]['tuning_mm']}")

    into = HERE / arguments.into if arguments.into else FITTED
    into.mkdir(parents=True, exist_ok=True)
    facts = {
        "backbone": BACKBONE,
        "vlm_layers": LAYERS,
        "training_stage": STAGE,
        "denoising_steps": DENOISING_STEPS,
        "moving_numbers": moving,
        "total_numbers": total,
        "steps_wanted": arguments.steps,
        "batch": arguments.batch,
        "learning_rate": arguments.lr,
        "warmup": WARMUP,
        "seed": arguments.seed,
        "device": where,
        "demonstrations": fitting.num_frames,
        "tables_fitted_on": fitting.num_episodes,
        "tuning_demonstrations": len(tuning),
        "chunk": chunk,
    }
    # Saved beside the fit because the run has to scale its inputs exactly as
    # the fitting did, and these numbers are what say how.
    (into / "stats.json").write_text(
        json.dumps(
            {"chunk": chunk, "stats": {k: {n: v.tolist() for n, v in s.items()} for k, s in stats.items()}},
            indent=2,
        )
        + "\n"
    )

    policy.train()
    started, step, losses, feed = time.time(), 0, [], iter(loader)
    held = 0.0
    while step < arguments.steps:
        try:
            batch = next(feed)
        except StopIteration:
            feed = iter(loader)
            continue
        for group in optimiser.param_groups:
            group["lr"] = rate(step, arguments.steps, arguments.lr)
        loss, _ = policy.forward(batch)
        loss.backward()
        if step == 0:
            # Read before the step, because zeroing the gradients drops them.
            # Worth printing once: the vision-language half is frozen on
            # purpose, and a head that never got a gradient would fit silently
            # to nothing.
            touched = sum(1 for p in policy.parameters() if p.requires_grad and p.grad is not None)
            moving_now = sum(1 for p in policy.parameters() if p.requires_grad)
            print(f"            {touched} of the head's {moving_now} tables took a gradient")
        optimiser.step()
        optimiser.zero_grad()
        losses.append(float(loss.item()))
        step += 1
        held = max(held, memory_gib(where))
        if step % arguments.check_every == 0 or step == arguments.steps:
            recent = round(float(np.mean(losses[-arguments.check_every :])), 4)
            mm = chunk_error_mm(policy, pre, post, tuning, chunk, arguments.chunks)
            history.append({"step": step, "loss": recent, "tuning_mm": mm})
            print(
                f"step {step:5d}  loss {recent:.4f}, tuning {mm}, "
                f"{(time.time() - started) / step:.2f}s a step, {(time.time() - started) / 60:.0f} min so far"
            )
            torch.save(head(policy), into / "head.pt")
            (into / "training.json").write_text(
                json.dumps(
                    {
                        **facts,
                        "steps_done": step,
                        "minutes": round((time.time() - started) / 60, 1),
                        "memory_gib": round(held, 2),
                        "history": history,
                    },
                    indent=2,
                )
                + "\n"
            )

    print(f"\n{(time.time() - started) / 60:.1f} minutes, holding {held:.2f} GiB. Fit in {into}")


if __name__ == "__main__":
    main()
