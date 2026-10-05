"""Fit the low-rank correction on the teacher's pushes, and say how far it got.

**What is fitted.** Nothing but the correction. The 450 million borrowed
numbers are frozen and never written to; what moves is the pair of thin
tables ``correction.py`` adds beside each attention projection, which is
about four million numbers. **Where it is saved**: ``correction/``, beside
this file, as a LoRA adapter — the correction alone, never a copy of the
borrowed weights. It is written at every check and not only at the end, so a
run that has to be stopped leaves a correction that can be scored, and
``training.json`` beside it says how many steps went into what is there.

**What it is fitted towards.** The chunks in ``demonstrations/``, which are
the paths the teacher's jaw really followed, read through the same convention
the model answers in. The loss is SmolVLA's own: it is a flow-matching model,
so the training shows it a target chunk with noise mixed into it and asks for
the direction back towards the target. The number it prints is therefore not
a distance and cannot be read as one.

**So a distance is measured as well**, because the loss alone says nothing a
reader can picture. Every so often the model is asked for a chunk on tables
it was not fitted on, the answer is decoded into jaw waypoints, and the
median distance from the teacher's own waypoints is reported in millimetres.
The same measurement is taken before the first step, when the correction is
still zero and the model is therefore exactly solution 5. That first number
is what training has to beat.

**When to stop** is what the tuning tables are for. They are tables below the
held-out line that nothing is fitted on, so a correction that has started
learning the tables rather than the pushing shows as the tuning distance
turning upwards while the fitting loss keeps falling.

    pixi run python 06-smolvla-fine-tuned/train.py
    pixi run python 06-smolvla-fine-tuned/train.py --steps 500 --batch 2
    pixi run python 06-smolvla-fine-tuned/train.py --seed 1 --into correction-1
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from chunks import CHUNK
from correction import CORRECTION, RANK, SCALING, TABLES, borrowed, counts, with_correction
from demonstrations import FITTING, REPO, TUNING
from partners import CAMERA, SLOTS, WEIGHTS, device_for, to_jaw
from torch.utils.data import DataLoader

HERE = Path(__file__).parent

# The recipe. It is short, and the step count is where the tuning tables said
# to stop rather than a budget: the tuning error fell from 320 mm to 84 mm by
# step 500 and did not improve by step 1000, while the fitting loss halved,
# which is the shape that says more training is being spent on the examples
# rather than on the pushing. It is also a small fraction of the compute
# LeRobot's own SmolVLA fine-tune spends — twenty thousand steps at a batch of
# sixty-four, on an NVIDIA card — and every result this folder reports carries
# that caveat as well.
STEPS = 1000
BATCH = 4
LEARNING_RATE = 1e-4
# Steps over which the rate climbs from nothing. A correction that starts at
# zero is a large change to the model in its first few steps, and warming up
# is the ordinary guard against that first change being a bad one.
WARMUP = 100
CHECK_EVERY = 500
# Tuning chunks measured each time. Each one is a forward pass of the whole
# model, so this is the part of a check that costs anything.
CHECK_CHUNKS = 16


def loaded(root: Path):
    """One of the demonstration sets, as a LeRobot dataset."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    if not (root / "meta").exists():
        raise FileNotFoundError(
            f"no demonstrations at {root}. Make them with "
            "`pixi run python 06-smolvla-fine-tuned/demonstrations.py`."
        )
    return LeRobotDataset(REPO, root=root)


def ready(items: list[dict], pre) -> dict:
    """A batch of demonstrations, put through the model's own pre-processing.

    Every sample goes through the same pipeline a single observation goes
    through at run time, so what the model is trained on and what it is asked
    is prepared by one piece of code. The pipeline gives each observation a
    batch of one, which is why the observations are joined and the chunks,
    which it leaves alone, are stacked.
    """
    each = [
        pre(
            {
                CAMERA: item[CAMERA],
                "observation.state": item["observation.state"],
                "action": item["action"].reshape(CHUNK, SLOTS),
                "task": item["task"],
            }
        )
        for item in items
    ]
    joined = {
        key: torch.cat([one[key] for one in each], dim=0)
        for key in (CAMERA, "observation.state", "observation.language.tokens")
    }
    joined["observation.language.attention_mask"] = torch.cat(
        [one["observation.language.attention_mask"] for one in each], dim=0
    ).bool()
    joined["action"] = torch.stack([one["action"] for one in each])
    return joined


def chunk_error_mm(policy, pre, post, data, how_many: int) -> dict:
    """How far the model's waypoints land from the teacher's, in millimetres.

    The answer is drawn rather than computed, so this is one sample of a
    distribution and not a fixed number. It is still the only figure here
    that can be pictured.
    """
    policy.eval()
    gaps = []
    for i in range(min(how_many, len(data))):
        item = data[i]
        batch = pre(
            {
                CAMERA: item[CAMERA],
                "observation.state": item["observation.state"],
                "task": item["task"],
            }
        )
        policy.reset()
        with torch.no_grad():
            said = post(policy.predict_action_chunk(batch))[0].numpy().astype(float)
        wanted = to_jaw(item["action"].reshape(CHUNK, SLOTS).numpy().astype(float))
        mine = to_jaw(said)
        gaps.append(1000 * np.hypot(*(mine[:, :2] - wanted[:, :2]).T))
    policy.train()
    flat = np.concatenate(gaps)
    return {"median": round(float(np.median(flat)), 1), "worst": round(float(flat.max()), 1)}


def memory_gib(device: str) -> float:
    """How much of the machine's memory the training is holding, gibibytes.

    The whole question of whether this fits on a laptop is this number, so it
    is measured rather than estimated: what has to be held is the borrowed
    weights plus the correction's gradients and optimiser state, and low-rank
    adaptation is the thing that keeps the second part small.
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
    parser.add_argument("--into", default=None, help="folder for the correction, for a second seed")
    arguments = parser.parse_args()

    where = arguments.device or device_for()
    torch.manual_seed(arguments.seed)
    fitting, tuning = loaded(FITTING), loaded(TUNING)
    print(f"{fitting.num_frames} demonstrations from {fitting.num_episodes} tables, {len(tuning)} to tune on")

    policy, pre, post = borrowed(where)
    policy = with_correction(policy)
    moving, total = counts(policy)
    print(f"correction  rank {RANK}, scaling {SCALING}, on {', '.join(TABLES)}")
    print(f"            {moving / 1e6:.2f}M numbers move of {total / 1e6:.1f}M, on {where}")

    loader = DataLoader(
        fitting,
        batch_size=arguments.batch,
        shuffle=True,
        num_workers=0,
        drop_last=True,
        collate_fn=lambda items: ready(items, pre),
    )
    optimiser = torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad], lr=arguments.lr)

    # Before the first step the correction is still zero, so the model is
    # exactly solution 5 and this is the number training has to beat.
    history = [{"step": 0, "tuning_mm": chunk_error_mm(policy, pre, post, tuning, arguments.chunks)}]
    print(f"step     0  untrained, tuning {history[0]['tuning_mm']}")

    into = HERE / arguments.into if arguments.into else CORRECTION
    facts = {
        "weights": WEIGHTS,
        "rank": RANK,
        "scaling": SCALING,
        "tables": list(TABLES),
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
    }

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
            # Worth printing once: SmolVLA freezes its vision-language half by
            # itself, and a correction inside a frozen half that never got a
            # gradient would train silently to nothing.
            touched = sum(1 for p in policy.parameters() if p.requires_grad and p.grad is not None)
            moving_now = sum(1 for p in policy.parameters() if p.requires_grad)
            print(f"            {touched} of the correction's {moving_now} tables took a gradient")
        optimiser.step()
        optimiser.zero_grad()
        losses.append(float(loss.item()))
        step += 1
        held = max(held, memory_gib(where))
        if step % arguments.check_every == 0 or step == arguments.steps:
            recent = round(float(np.mean(losses[-arguments.check_every :])), 4)
            mm = chunk_error_mm(policy, pre, post, tuning, arguments.chunks)
            history.append({"step": step, "loss": recent, "tuning_mm": mm})
            print(
                f"step {step:5d}  loss {recent:.4f}, tuning {mm}, "
                f"{(time.time() - started) / step:.2f}s a step, {(time.time() - started) / 60:.0f} min so far"
            )
            # Saved at every check, not only at the end, so a run stopped
            # part way leaves a correction that can be scored rather than
            # nothing. The folder always holds the latest check, and
            # ``steps_done`` says which one it is.
            policy.model.save_pretrained(into)
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

    print(f"\n{(time.time() - started) / 60:.1f} minutes, holding {held:.2f} GiB. Correction in {into}")


if __name__ == "__main__":
    main()
