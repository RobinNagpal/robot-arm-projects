"""Fit the policy on the collected demonstrations, from random numbers.

**What is fitted** is one mapping: what problem 4 shows a solution -- the
picture from the camera on the arm, the readings of the glasses it caught, and
where the jaw is standing -- to the path the teacher's answer turned out to be.
Nothing else. No reward, no outcome, no geometry. The loss is the model's own,
L1 against the demonstrated chunk with ACT's variational term on top, and it
measures only how close the path was to the teacher's.

**The fitting loop is problem 3's**, borrowed and not written again, for the
reason ``wiring.py`` gives. So are the learning rate, its warm-up and its
cosine decay, and the batch. The two problems' students differ in their problem
and their data, and in nothing else that could be mistaken for a result.

**Three seeds, because one fit is not a measurement.** Each is a separate fit of
the same model on the same demonstrations, saved separately, and ``run.py``
evaluates all of them and reports the spread.

**The numbers printed at the end are not the score.** They say how far the
fitted chunk is from the teacher's, on tables the fit saw and on tables it did
not, and the gap between those two is what is worth watching: a small error on
fitted tables beside a large one on unseen tables is memorising rather than
learning, and the cure for that is more demonstrations rather than more steps.
The score is the outcome on the tables, and only ``run.py`` measures it.

One seed at a time is the usual way to run it, because a seed takes of order an
hour and a shell that drops takes the run with it::

    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 1 --first-seed 0
    pixi run python -u 03-imitation-from-demonstrations/train.py --steps 200 --seeds 1  # a smoke test

Every seed appends to the same summary, so stopping between seeds loses nothing
already fitted.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import chunks
import loading
import numpy as np
from wiring import fitting, pictures, policy

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"

# The rung. Problem 3 offered a denoising second rung as well; this folder fits
# the one the document names -- a small model with action chunking -- and leaves
# the comparison between the two to the problem that already made it.
RUNG = "act"

# How many steps a fit takes. Problem 3 used ten thousand for the same model and
# the same batch. Measured here, a step costs 0.4 s on this machine's graphics
# chip -- the chunk is 200 rows against problem 3's 120, and the machine is
# shared -- so ten thousand is an hour and a quarter and eight is under an hour,
# which is the budget. The difference from problem 3 is written down because it
# is a difference between the two students that is not the problem.
STEPS = 8_000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3, help="separate fits, because one is not a measure")
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--batch", type=int, default=fitting.BATCH)
    parser.add_argument("--lr", type=float, default=fitting.LEARNING_RATE)
    parser.add_argument("--most", type=int, default=None, help="read only this many demonstrations")
    arguments = parser.parse_args()

    held = loading.load(loading.FITTING, pictures.shrink, arguments.most)
    checking = loading.load(loading.HELD_BACK, pictures.shrink, arguments.most)
    seen, actions, states = held["pictures"], held["actions"], held["states"]
    scale = policy.Scale.of(seen, actions)
    device = policy.where_to_run()
    facts = loading.collected(loading.FITTING)
    print(
        f"{len(actions)} demonstrations of up to {actions.shape[1]} waypoints from "
        f"{len(np.unique(held['episodes']))} tables, band {facts['band']['first_table']}; "
        f"fitting {RUNG} on {device} with {states.shape[1]} readings beside each picture"
    )

    WEIGHTS.mkdir(exist_ok=True)
    summary = WEIGHTS / "training.json"
    # A seed takes of order an hour, so seeds are usually fitted in separate
    # runs. Earlier ones are read back rather than written over.
    report = json.loads(summary.read_text()) if summary.exists() else {"seeds": []}
    report |= {
        "rung": RUNG,
        "device": device,
        "demonstrations": int(len(actions)),
        "band": facts["band"],
        "chunk": chunks.CHUNK,
    }
    for seed in range(arguments.first_seed, arguments.first_seed + arguments.seeds):
        started = time.time()
        model, curve = fitting.fit(
            RUNG,
            seen,
            actions,
            scale,
            seed,
            arguments.steps,
            arguments.batch,
            arguments.lr,
            states=states,
        )
        spent = time.time() - started
        model.save(WEIGHTS / f"{RUNG}-{seed}")
        unseen = fitting.how_far_off(
            model, checking["pictures"], checking["actions"], states=checking["states"]
        )
        fitted = fitting.how_far_off(model, seen, actions, states=states)
        lengths = how_long_off(model, checking)
        print(
            f"seed {seed}: loss {curve[0]:.3f} -> {curve[-1]:.3f} in {spent / 60:.0f} min\n"
            f"  per waypoint, against the teacher's own chunk: "
            f"{fitted['waypoint_mm_median']} mm on tables it was fitted on, "
            f"{unseen['waypoint_mm_median']} mm on tables it never saw\n"
            f"  length: agrees about pushing {100 * lengths['agreed_about_pushing']:.0f}% of the time, "
            f"{lengths['waypoints_out_when_both_push']} waypoints out when both push"
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
                "against_the_teacher": {"tables_it_never_saw": unseen, "tables_it_was_fitted_on": fitted},
                "path_length": lengths,
            }
        )
        report["seeds"].sort(key=lambda row: row["seed"])
        summary.write_text(json.dumps(report, indent=2) + "\n")

    print(
        f"\nsaved to {WEIGHTS}. The millimetres above say how close the student is to its teacher,\n"
        "which is not the score: run.py measures the outcome on the tables."
    )


def how_long_off(model, set_of: dict, most: int = 200) -> dict:
    """How well the fit gets a path's *length* right, which problem 3 never had to ask.

    Problem 3's student only ever pushed, so every chunk it emitted was the same
    length. Here a path is either one waypoint, to go and stand somewhere, or
    forty to a hundred and eighty, to come down and shove a glass. The sixth
    column of the chunk is what says which, so a fit that answers with the right
    shape and the wrong length is wrong in a way no millimetre of waypoint error
    shows.

    Two numbers come out of it: how often the fit agrees with the teacher about
    whether this answer touches a glass at all, and how far out the length is
    when the two agree it does.
    """
    count = min(most, len(set_of["actions"]))
    agreed, off = 0, []
    for i in range(count):
        guess = model.chunk(set_of["pictures"][i], set_of["states"][i : i + 1])
        wanted, got = chunks.length_of(set_of["actions"][i]), chunks.length_of(guess)
        pushing = (wanted > 1, got > 1)
        agreed += pushing[0] == pushing[1]
        if all(pushing):
            off.append(abs(got - wanted))
    return {
        "chunks": count,
        "agreed_about_pushing": round(agreed / count, 3) if count else 0.0,
        "waypoints_out_when_both_push": round(float(np.median(off)), 1) if off else None,
    }


if __name__ == "__main__":
    main()
