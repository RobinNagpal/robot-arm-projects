"""Fit the low-rank correction on problem 4's demonstrations, and say how far it got.

**What is fitted.** Nothing but the correction. The 450 million borrowed numbers
are frozen and never written to; what moves is the pair of thin tables problem
3's ``correction.py`` adds beside each attention projection, which is about four
million numbers. **Where it is saved**: ``weights/correction-<seed>``, the
correction alone and never a copy of the borrowed weights, written at every
check so that a run which has to be stopped leaves something that can be scored.
``weights/training.json`` says what went into each one.

**What it is fitted towards.** The demonstrations in ``../demonstrations``, which
are the ranked geometry's own answers on tables 1000 to 1299: the picture from
the camera on the arm, where the jaw was standing, and the path the jaw then
followed. ``targets.py`` is what reads one of those into the model's convention.
The loss is SmolVLA's own: it is a flow-matching model, so the training shows it
a target chunk with noise mixed in and asks for the direction back towards the
target. The number it prints is therefore not a distance and cannot be read as
one.

**So a distance is measured as well**, because the loss alone says nothing a
reader can picture. Every so often the model is asked for a chunk on tables it
was not fitted on, the answer is decoded into jaw waypoints, and the distance
from the teacher's own waypoints is reported in millimetres. The same
measurement is taken before the first step, when the correction is still zero
and the model is therefore exactly solution 5. That first number is what
training has to beat.

**The looks and the pushes are measured apart.** Four demonstrations in five are
the teacher driving the arm somewhere it can see from, so one median over the
mixture would be a median over looks. Problem 3 never had to split them, because
its camera hangs above the table and a push was the only answer there was.

**The recipe is problem 3's, imported and not chosen again** -- the step count,
the batch, the rate and its warm-up, the pre-processing of a batch and the
distance itself all come from
``03-push-glasses-apart/06-smolvla-fine-tuned/train.py``. The two problems'
fits then differ in their problem and their data, and in nothing that could be
mistaken for a result. One difference follows from that and is not a choice. A
thousand steps at a batch of four shows the model four thousand demonstrations,
which is about a third of one pass over problem 4's eleven thousand; problem 3
chose the recipe on a set of 1,074, where it was nearly four passes, and fitted
on a set of 6,935, where it was three fifths of one.

**Three seeds, because one fit is not a measurement.** Each is a separate fit of
the same correction on the same demonstrations, saved separately, and ``run.py``
walks the held-out queue once with each.

    pixi run python -u 06-smolvla-fine-tuned/train.py
    pixi run python -u 06-smolvla-fine-tuned/train.py --seeds 1 --first-seed 2
    pixi run python -u 06-smolvla-fine-tuned/train.py --steps 4 --chunks 2  # a smoke test

Every seed appends to the same record, so stopping between seeds loses nothing
already fitted.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import targets
import torch
import weights
from borrowed import MODEL_CHUNK, correction, fitting, loading, policy
from targets import LOOKING, PUSHING, SQUEEZED
from torch.utils.data import DataLoader

# How often to print the loss and the rate between checks. Nothing is measured
# there, so it is not one of problem 3's numbers.
SAY_EVERY = 50


def views(tuning: targets.Targets, how_many: int) -> dict[str, targets.Spread]:
    """A handful of tuning demonstrations of each kind, spread across the set.

    The mixture first, which is the number problem 3 reports, and then the looks
    and the pushes on their own. The squeezed pushes are counted with the pushes
    because that is what they are; ``targets.py`` keeps them apart only to say
    how many of them there are.
    """
    kinds = targets.by_kind(tuning)
    pushing = sorted(kinds[PUSHING] + kinds[SQUEEZED])
    chosen = {
        "all": list(range(len(tuning))),
        "looking": kinds[LOOKING],
        "pushing": pushing,
    }
    return {
        name: targets.Spread(tuning, [rows[i] for i in targets.evenly(how_many, len(rows))])
        for name, rows in chosen.items()
        if rows
    }


def distances(model, pre, post, each: dict[str, targets.Spread], how_many: int) -> dict:
    """How far the model's waypoints land from the teacher's, in millimetres, by kind."""
    return {name: fitting.chunk_error_mm(model, pre, post, view, how_many) for name, view in each.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3, help="separate fits, because one is not a measure")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--steps", type=int, default=fitting.STEPS)
    parser.add_argument("--batch", type=int, default=fitting.BATCH)
    parser.add_argument("--lr", type=float, default=fitting.LEARNING_RATE)
    parser.add_argument("--check-every", type=int, default=fitting.CHECK_EVERY)
    parser.add_argument("--chunks", type=int, default=fitting.CHECK_CHUNKS, help="tuning chunks a check")
    parser.add_argument("--device", default=None, help="cpu, mps or cuda; the fastest one by default")
    arguments = parser.parse_args()

    where = arguments.device or policy.device_for()
    fitted_on = targets.Targets(loading.FITTING)
    tuning = targets.Targets(loading.HELD_BACK)
    facts = loading.collected(loading.FITTING)
    print(
        f"{len(fitted_on)} demonstrations from {fitted_on.tables} tables, band "
        f"{facts['band']['first_table']}; {len(tuning)} held back from tables it never saw",
        flush=True,
    )
    each = views(tuning, arguments.chunks)
    print("    the tuning sample: " + ", ".join(f"{name} {len(view)}" for name, view in each.items()))

    weights.FITS.mkdir(exist_ok=True)
    # A seed takes of order an hour, so seeds are sometimes fitted in separate
    # runs. Earlier ones are read back rather than written over.
    record = json.loads(weights.RECORD.read_text()) if weights.RECORD.exists() else {"seeds": []}
    for seed in range(arguments.first_seed, arguments.first_seed + arguments.seeds):
        row = one_fit(seed, arguments, where, fitted_on, each)
        record |= {
            "weights": policy.WEIGHTS,
            "rank": correction.RANK,
            "scaling": correction.SCALING,
            "tables": list(correction.TABLES),
            "chunk": MODEL_CHUNK,
            "device": where,
            "band": facts["band"],
            "demonstrations": len(fitted_on),
            "tables_fitted_on": fitted_on.tables,
            "tuning_demonstrations": len(tuning),
        }
        record["seeds"] = [one for one in record["seeds"] if one["seed"] != seed] + [row]
        record["seeds"].sort(key=lambda one: one["seed"])
        weights.RECORD.write_text(json.dumps(record, indent=2) + "\n")

    print(
        f"\nsaved to {weights.FITS}. The millimetres above say how close the correction is to the\n"
        "teacher, which is not the score: run.py measures the outcome on the tables."
    )


def one_fit(seed: int, arguments, where: str, fitted_on: targets.Targets, each: dict) -> dict:
    """One seed, from the borrowed weights to a saved correction. Returns its record."""
    torch.manual_seed(seed)
    # A fresh count for each seed, so that the record says what one fit read
    # rather than what the whole run read.
    fitted_on.counts = targets.Counts()
    model, pre, post = correction.borrowed(where)
    model = correction.with_correction(model)
    moving, total = correction.counts(model)
    print(
        f"\nseed {seed}: correction rank {correction.RANK}, scaling {correction.SCALING}, on "
        f"{', '.join(correction.TABLES)}\n"
        f"    {moving / 1e6:.2f}M numbers move of {total / 1e6:.1f}M, on {where}",
        flush=True,
    )

    loader = DataLoader(
        fitted_on,
        batch_size=arguments.batch,
        shuffle=True,
        num_workers=0,
        drop_last=True,
        collate_fn=lambda items: fitting.ready(items, pre),
    )
    optimiser = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=arguments.lr)

    # Before the first step the correction is still zero, so the model is
    # exactly solution 5 and this is the number training has to beat.
    history = [{"step": 0, "tuning_mm": distances(model, pre, post, each, arguments.chunks)}]
    print(f"    step     0  untrained, tuning {history[0]['tuning_mm']}", flush=True)

    into = weights.correction(seed)
    model.train()
    started, step, losses, feed, held = time.time(), 0, [], iter(loader), 0.0
    while step < arguments.steps:
        try:
            batch = next(feed)
        except StopIteration:
            feed = iter(loader)
            continue
        for group in optimiser.param_groups:
            group["lr"] = fitting.rate(step, arguments.steps, arguments.lr)
        loss, _ = model.forward(batch)
        loss.backward()
        if step == 0:
            # Read before the step, because zeroing the gradients drops them.
            # Worth printing once: SmolVLA freezes its vision-language half by
            # itself, and a correction inside a frozen half that never got a
            # gradient would train silently to nothing.
            took = sum(1 for p in model.parameters() if p.requires_grad and p.grad is not None)
            moving_now = sum(1 for p in model.parameters() if p.requires_grad)
            print(f"    {took} of the correction's {moving_now} tables took a gradient", flush=True)
        optimiser.step()
        optimiser.zero_grad()
        losses.append(float(loss.item()))
        step += 1
        held = max(held, fitting.memory_gib(where))
        if step % SAY_EVERY == 0 and step % arguments.check_every:
            # A line often enough to see the rate early, because a fit of this
            # length is committed to on the strength of its first few minutes.
            # It measures nothing: the checks below are the measurement.
            print(
                f"    step {step:5d}  loss {np.mean(losses[-SAY_EVERY:]):.4f}, "
                f"{(time.time() - started) / step:.2f}s a step",
                flush=True,
            )
        if step % arguments.check_every == 0 or step == arguments.steps:
            recent = round(float(np.mean(losses[-arguments.check_every :])), 4)
            mm = distances(model, pre, post, each, arguments.chunks)
            history.append({"step": step, "loss": recent, "tuning_mm": mm})
            print(
                f"    step {step:5d}  loss {recent:.4f}, tuning {mm}, "
                f"{(time.time() - started) / step:.2f}s a step, "
                f"{(time.time() - started) / 60:.0f} min so far",
                flush=True,
            )
            # Saved at every check and not only at the end, so a run stopped
            # part way leaves a correction that can be scored. The folder
            # always holds the latest check and ``steps_done`` says which.
            model.model.save_pretrained(into)

    minutes = (time.time() - started) / 60
    print(f"    {minutes:.1f} minutes, holding {held:.2f} GiB. Correction in {into}", flush=True)
    del model
    return {
        "seed": seed,
        "steps_wanted": arguments.steps,
        "steps_done": step,
        "batch": arguments.batch,
        "learning_rate": arguments.lr,
        "warmup": fitting.WARMUP,
        "minutes": round(minutes, 1),
        "memory_gib": round(held, 2),
        "moving_numbers": moving,
        "total_numbers": total,
        "tuning_chunks_a_check": arguments.chunks,
        "reading_the_demonstrations": fitted_on.counts.summary(),
        "history": history,
    }


if __name__ == "__main__":
    main()
