# Solution 7 — Evo-1, a newer and larger borrowed model, fitted here

This solution answers one question: on a task this narrow, is a newer and
larger borrowed model worth its cost? Solutions 5 and 6 already measure a
450-million-number borrowed model, used as it downloads and fine-tuned on this
bench's own pushes. This solution swaps that model for
[Evo-1](https://arxiv.org/abs/2511.04555), published in November 2025, which
is about 775 million numbers on an InternVL3-1B vision-language backbone, and
changes nothing else. So what the scorecard shows is the model, not the data
and not the loop.

Evo-1 is a vision-language-action model, which means it reads a picture and a
sentence and answers with a run of actions. Its action half draws a chunk by
**flow matching**: it starts from noise and walks that noise towards an answer
in a fixed number of steps, the way solution 5's model does. That is why the
same table asked twice is answered twice, and why every number here needs a
spread.

## What is the same as solution 6, and what is different

The whole value of this solution is that the list of differences is short.

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

Two of those differences are forced by the checkpoint rather than chosen, and
both are recorded because they are still differences:

- **The picture has to grow.** Evo-1 refuses any size but its checkpoint's own
  448 pixels, because the number of image tokens is fixed in the checkpoint. So
  this cell's 384-pixel view is scaled up. Scaling up adds no information, so
  it is not an advantage; it is a cost paid in tokens.
- **The answer is 24 numbers wide.** The model always answers 24 numbers a
  waypoint whatever the cell needs, and its own post-processing trims that to
  the 6 this cell uses.

## Does it run on this machine?

It does, and **with no change to its code** — only to its configuration. That
was the open question in the task that asked for it, because Evo-1's source
mentions CUDA in three places. All three turned out to be either a default
argument or a guard that simply switches a CUDA-only path off, so the three
settings below were enough.

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

Solution 6's demonstrations have to exist first, because this solution is
fitted on that very folder rather than on a collection of its own.

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
`videos/`. Anything shorter than the full held-out set writes `partial.json`
and never `results.json`, because one short run is not a result.

## Results

**Being measured.** The three fits and the scoring run are in progress; this
section will carry the scorecard beside solutions 5 and 6, with the spread, as
soon as they finish. Nothing is claimed here until it does.
