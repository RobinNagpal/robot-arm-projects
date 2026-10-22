# Solution 7 — Evo-1, a newer and larger borrowed model, fitted here

This solution asks one question: on a task this narrow, is a newer and larger
borrowed model worth its cost? It swaps solution 6's model for
[Evo-1](https://arxiv.org/abs/2511.04555), published in November 2025. Evo-1
has about 775 million numbers on an InternVL3-1B vision-language backbone.
Nothing else changes. So the scorecard shows the model, not the data and not
the loop.

Evo-1 is a vision-language-action model, like
[solution 5's](../docs/solutions/05-smolvla-as-it-downloads.md#a-model-that-sees-is-told-and-acts).
It draws each chunk by **flow matching**, the way solution 5's model does, so
every number here needs a spread.
[Solution 5's document](../docs/solutions/05-smolvla-as-it-downloads.md#flow-matching-and-why-one-run-is-not-enough)
explains flow matching, and
[solution 6's document](../docs/solutions/06-smolvla-fine-tuned.md#fine-tuning--continuing-somebody-elses-training)
explains fine-tuning. The reasoning for this solution is in
[its document](../docs/solutions/07-evo1-fine-tuned.md).

## What is the same as solution 6, and what is different

The table below compares the two solutions row by row. The bold entries are the
differences.

| | solution 6 | solution 7 |
|---|---|---|
| model | SmolVLA, 453.9M numbers | **Evo-1, 775.2M numbers** |
| what is fitted | a low-rank correction, 3.8M numbers | **its own first stage, 122.0M numbers** |
| picture | the cell's 384-pixel top view | **the same view scaled to 448** |
| demonstrations | solution 6's `demonstrations/` | the same folder, read not copied |
| reading an action as a waypoint | solution 5's `joining.py` | the same module, imported |
| the loop over a table | solution 5's `clear.py` | the same module, imported |
| fitting effort | 1000 steps, batch 4, rate 1e-4 | the same |
| the test | 50 held-out tables, 251 glasses | the same |

Two differences are forced by the checkpoint, not chosen:

- **The picture has to grow.** Evo-1 accepts only 448 pixels, so the 384-pixel
  view is scaled up.
- **The answer is 24 numbers wide.** The model's own post-processing trims it
  to the 6 this cell uses.

## Does it run on this machine?

Yes, **with no change to its code**, only to its configuration. Evo-1's source
mentions CUDA in three places, but each is a default argument or a guard that
switches a CUDA-only path off. These three settings were enough:

| setting | why |
|---|---|
| flash attention off | an NVIDIA kernel, absent here; the model falls back to plain attention |
| mixed precision off | the model already guards it to CUDA, so this only makes it explicit |
| float32 rather than bfloat16 | Metal's bfloat16 is not something a result should rest on |

Measured while building it:

| | |
|---|---|
| parameters | 775.2M, of which **122.0M** are fitted |
| memory held, answering | 3.60 GiB |
| one forward and backward pass | 1.7 s and 0.1 s |

## Where the code is

| | |
|---|---|
| `partners.py` | What this solution borrows from solutions 1, 2, 5 and 6, loaded not copied |
| `evo.py` | Evo-1 configured for this cell, and the fitted model ready to answer |
| `train.py` | Fits the action half, several seeds, and says how far it got |
| `run.py` | The held-out tables, scored with the bench's `Repeats` |
| `test_evo1.py` | The shapes, the forced sizes, and that the conventions really are solution 5's |

## Running it

Solution 6's demonstrations must exist first, because this solution is fitted
on that same folder.

```
pixi run python 06-smolvla-fine-tuned/demonstrations.py          # if not already made
pixi run python 06-smolvla-fine-tuned/demonstrations.py --check
make train SEED=0 INTO=fitted-0     # about an hour a seed
make train SEED=1 INTO=fitted-1
make train SEED=2 INTO=fitted-2
pixi run python run.py --fit fitted-0 --fit fitted-1 --fit fitted-2 --runs 1
make test
```

`make film FILM=3` writes videos of the first three held-out tables into
`videos/`. A run shorter than the full held-out set writes `partial.json`, never
`results.json`, because one short run is not a result.

## Results

**The fits were made. The scoring run was not.**

Three fits, one per seed, a thousand steps each at about a hundred minutes
each. The table shows the distance from the teacher's own waypoints, on tuning
tables nothing was fitted on, with the spread across seeds.

| | step 0 | step 500 | step 1,000 |
|---|---|---|---|
| Distance from the teacher | 302 mm (±6) | 293 mm (±8) | **288 mm (±1)** |

The glass zone is 320 mm across, so these answers move somewhere else on the
table entirely. **The fit did not learn the task.** Solution 6, on the same
demonstrations and budget, reached 85 mm by step 1,000.

The scoring run was stopped. It would have cost about two hours of the graphics
chip to score a policy that aims nowhere near the glasses.
[Solution 5](../05-smolvla-as-it-downloads/README.md) already measures what an
unfitted borrowed model does here.

This does not show that the model is worse. Solution 6 adjusts 3.8 million
numbers. This solution fits a **122 million** number action head from random
values. Four thousand examples is far too few for that, so matching the step
count was unfair to Evo-1.
[The solution's document](../docs/solutions/07-evo1-fine-tuned.md#results)
explains this.
[Issue #24](https://github.com/RobinNagpal/robot-arm-projects/issues/24) is the
cheap next test: can the head memorise fifty demonstrations?
