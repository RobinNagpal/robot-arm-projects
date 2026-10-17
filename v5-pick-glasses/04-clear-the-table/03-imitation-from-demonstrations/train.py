"""Fit the gate and the policy on the collected demonstrations, from random numbers.

**Two models are fitted here, and the split is what the first held-out walk
asked for.** The gate decides which of the teacher's four kinds of answer to
give and which glass to give it at; the policy then draws that one kind of path.
Fitting one model to do both produced the average of a look and a push, which is
a look, and the solution freed no glasses at all. ``gate.py`` argues the split
in full.

**What the policy is fitted on** is one mapping: what problem 4 shows a solution
-- the picture from the camera on the arm, the readings of the glasses it
caught, where the jaw is standing, what it has been doing on this table, and the
decision the gate has taken -- to the path the teacher's answer turned out to
be. Nothing else. No reward, no outcome, no geometry. The loss is the model's
own, L1 against the demonstrated chunk with ACT's variational term on top, and
it measures only how close the path was to the teacher's.

**The mixture the policy sees is balanced, and the gate's is not.** Of the
teacher's answers, four in five are looks and about one in thirty-five is a push
at the task. The policy has to draw a push as well as it draws a look, so its
batches are drawn evenly from the kinds; the gate has to *choose* between them,
so how often each really happens is part of what it has to learn.

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
import gate
import loading
import numpy as np
import readings
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
    parser.add_argument("--gate-steps", type=int, default=gate.STEPS, help="steps for the gate's own fit")
    parser.add_argument("--gate-only", action="store_true", help="fit the gate and leave the policy alone")
    parser.add_argument(
        "--policy-only", action="store_true", help="fit the chunked policy and leave the gate alone"
    )
    arguments = parser.parse_args()

    held = loading.load(loading.FITTING, pictures.shrink, arguments.most)
    checking = loading.load(loading.HELD_BACK, pictures.shrink, arguments.most)
    device = policy.where_to_run()
    facts = loading.collected(loading.FITTING)
    print(
        f"{len(held['actions'])} demonstrations of up to {held['actions'].shape[1]} waypoints from "
        f"{len(np.unique(held['episodes']))} tables, band {facts['band']['first_table']}; "
        f"fitting on {device} with {held['states'].shape[1]} readings beside each picture"
    )
    WEIGHTS.mkdir(exist_ok=True)
    if not arguments.policy_only:
        for seed in range(arguments.first_seed, arguments.first_seed + arguments.seeds):
            fit_the_gate(held, checking, seed, arguments.gate_steps)
    if arguments.gate_only:
        return

    # The policy is shown the kinds evenly. ``balanced`` says why, and the rows
    # it picks are what every array below is indexed by, so the pictures, the
    # paths and the readings stay in step.
    rows = balanced(held["gate"][:, 0], np.random.default_rng(0))
    seen = held["pictures"][rows]
    actions = from_their_glasses(held["actions"][rows], held["aimed_at"][rows])
    states = held["states"][rows]
    scale = policy.Scale.of(seen, actions)
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
        measured = from_their_glasses(checking["actions"], checking["aimed_at"])
        unseen = fitting.how_far_off(model, checking["pictures"], measured, states=checking["states"])
        pushing = checking["gate"][:, 0] != readings.LOOK
        unseen_pushes = fitting.how_far_off(
            model,
            checking["pictures"][pushing],
            measured[pushing],
            states=checking["states"][pushing],
        )
        fitted = fitting.how_far_off(model, seen, actions, states=states)
        lengths = how_long_off(model, checking | {"actions": measured})
        print(
            f"seed {seed}: loss {curve[0]:.3f} -> {curve[-1]:.3f} in {spent / 60:.0f} min\n"
            f"  per waypoint, against the teacher's own chunk: "
            f"{fitted['waypoint_mm_median']} mm on tables it was fitted on, "
            f"{unseen['waypoint_mm_median']} mm on tables it never saw\n"
            f"  per waypoint, over the answers that touch a glass: "
            f"{unseen_pushes['waypoint_mm_median']} mm on tables it never saw\n"
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
                "against_the_teacher": {
                    "tables_it_never_saw": unseen,
                    "tables_it_was_fitted_on": fitted,
                    # The same measurement over the answers that touch a glass
                    # alone. It is the one that matters and the one an average
                    # over every answer hides, because four answers in five are
                    # looks and a look is easy.
                    "the_pushes_it_never_saw": unseen_pushes,
                },
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




def from_their_glasses(actions: np.ndarray, aimed_at: np.ndarray) -> np.ndarray:
    """The same chunks, with a push measured from the glass it was aimed at.

    The demonstrations hold what the teacher really did, in the cell's own
    numbers, because solution 6 reads the same set. This is the reading ticket 19
    asks for, and it is this solution's own: a push's waypoints are where they
    are because of where the glass is, so measured from the table the same shove
    at two glasses is two unrelated answers and the model has to learn the
    table's layout before it can learn the shove. Measured from the glass it is
    one answer. An answer aimed at no glass has an origin of nothing and is
    unchanged. ``clear.py`` adds the glass's place back on at run time.
    """
    moved = actions.copy()
    moved[:, :, 0] -= aimed_at[:, None, 0]
    moved[:, :, 1] -= aimed_at[:, None, 1]
    return moved


def balanced(kinds: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Rows drawn evenly from the kinds of answer, as many as there are frames.

    The teacher's own mixture is four looks to every push, and about one answer
    in thirty-five is a push at the task rather than a probe. A fit on that
    mixture spends almost all of itself on the kind of answer that is easy and
    does not change the table, which is the measured reason this solution freed
    no glasses on its first held-out walk.

    Drawing the same number of rows as there are frames keeps the memory and the
    cost of a step exactly as they were: the looks are thinned rather than the
    pushes copied. A kind with few frames is drawn from with replacement, so its
    frames repeat -- which is the price of balance, and visible as the gap
    between the error on tables it was fitted on and on tables it never saw.

    The teacher's "done" is left out altogether. There is no path to copy for
    it, and a run answers ``Done`` from the gate without asking the policy for
    anything.
    """
    wanted = [kind for kind in range(len(readings.KINDS)) if kind != readings.DONE]
    have = {kind: np.flatnonzero(kinds == kind) for kind in wanted}
    have = {kind: rows for kind, rows in have.items() if len(rows)}
    if not have:
        raise ValueError("the demonstrations hold no answer with a path in them")
    each = max(1, len(kinds) // len(have))
    drawn = [rng.choice(rows, size=each, replace=len(rows) < each) for rows in have.values()]
    rows = np.concatenate(drawn)
    rng.shuffle(rows)
    return rows


def fit_the_gate(held: dict, checking: dict, seed: int, steps: int) -> None:
    """One fit of the gate, saved beside the policy's weights, with what it got right."""
    numbers = held["states"][:, : readings.GATE_WIDTH]
    started = time.time()
    net, curve = gate.fit(held["pictures"], numbers, held["gate"], seed, steps=steps)
    gate.saved(seed).parent.mkdir(exist_ok=True)
    torch_save(net, gate.saved(seed))
    right = gate.how_often_right(
        net, checking["pictures"], checking["states"][:, : readings.GATE_WIDTH], checking["gate"]
    )
    print(
        f"gate {seed}: loss {curve[0]:.3f} -> {curve[-1]:.3f} in {(time.time() - started) / 60:.1f} min\n"
        f"  on tables it never saw: the kind right {100 * right['kind_right']:.0f}% of the time, "
        f"the glass right {100 * right['slot_right']:.0f}%"
    )
    summary = WEIGHTS / "gate.json"
    report = json.loads(summary.read_text()) if summary.exists() else {"seeds": []}
    report["seeds"] = [row for row in report["seeds"] if row["seed"] != seed]
    report["seeds"].append(
        {
            "seed": seed,
            "steps": steps,
            "minutes": round((time.time() - started) / 60, 1),
            "loss": curve,
            "on_tables_it_never_saw": right,
        }
    )
    report["seeds"].sort(key=lambda row: row["seed"])
    report["kinds"] = list(readings.KINDS)
    summary.write_text(json.dumps(report, indent=2) + "\n")


def torch_save(net, path) -> None:
    """Keep the gate's weights. Here so that nothing else in this file imports torch."""
    import torch

    torch.save(net.state_dict(), path)

if __name__ == "__main__":
    main()
