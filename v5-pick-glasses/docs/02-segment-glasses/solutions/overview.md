# The six solutions — same destination, six different cars

## Introduction

Problem 2 asks for one record per glass: which pixels are that glass, and where
it stands on the table. This folder answers that question six times over, with
six quite different methods, and the point of having six is **not** that one of
them is the answer. The point is to be able to compare them, and then to choose
one knowing what the choice costs. By the end of this document you will
understand what all six have in common, what single thing each one changes, and
which pair of them you should look at first if you only have time for one
comparison.

The comparison works because the six are arranged like cars driven to the same
destination. The destination is fixed, the road is the same, and only the car
changes — so when one arrives sooner, you know it was the car.

## What all six share

Three things are held still for every solution, and they are described in full
by [the test bench](../the-bench.md). In short:

**The same input.** One fixed set of arrangements, in the same order. For each
picture, a solution may read the grey picture shaded from depth, the depth
reading at every pixel, and the camera's own pose. Nothing else, and in
particular never the simulator's record of what it put out.

**The same output.** One record per glass: its mask pixels, its place on the
table, a rough width — and beside those records the two honest statements the
problem asks for, which glasses could not be separated and which parts of the
table could not have been seen.

**The same final step.** Turning a mask into a place and a width belongs to the
bench. Every solution hands over masks and the bench does the arithmetic.

That last point is the one that makes the whole comparison mean something, so it
is worth saying plainly what follows from it. **Every solution contributes only
the masks.** None of them can win by measuring more cleverly, and none can lose
by measuring worse. A difference in the score is a difference in the masks.

It also answers a question that would otherwise come up six times. **No model
here produces a pose.** Models produce masks, in the picture. The pose comes
afterwards, from the depth readings and the camera's own pose, by arithmetic —
and a glass standing upright on a flat table has no orientation left to find, so
its pose is simply a position.

One more thing is shared and is deliberately not any solution's business.
Recovering a glass that appeared in no picture at all needs geometry rather than
pixels, so it lives once in [looking again at what was
hidden](../hidden-glasses.md) and all six point at it.

## The six, in one table

They are ordered by **how much is fitted, and where those numbers came from**,
because that is what decides both the work involved and what can go wrong. The
table reads downwards from nothing fitted to everything fitted.

| # | Solution | What is fitted, and where | Libraries and models | Licence |
|---|---|---|---|---|
| 1 | [Rules on the table](01-rules-on-the-table.md) | nothing at all | NumPy, OpenCV | — |
| 2 | [A network trained from scratch](02-train-from-scratch.md) | everything, in this cell | PyTorch, a small convolutional network | — |
| 3 | [A borrowed model, as it downloads](03-yolo-zero-shot.md) | nothing | Ultralytics YOLO26-seg | AGPL-3.0 |
| 4 | [The same model, fine-tuned](04-yolo-fine-tuned.md) | all of it, in this cell | Ultralytics YOLO26-seg | AGPL-3.0 |
| 5 | [A foundation model with a keeper](05-sam2-with-a-keeper.md) | only the keeper | SAM 2 via `transformers`, scikit-learn | permissive |
| 6 | [A transformer segmenter, fine-tuned](06-rf-detr-fine-tuned.md) | all of it, in this cell | RF-DETR-Seg | Apache 2.0 |

Three of them carry a **second rung** inside themselves, which keeps a real idea
without spending a whole document on it:

- **Solution 2** takes its labels either from the bench's answer key, or from
  the arm's own movement with no answer key at all.
- **Solution 5** either prompts with a grid of points and fits a keeper to pick
  the glasses, or prompts the next generation of the same model with a word and
  needs no keeper.
- **Solution 6** trains its masks either on the pixels the camera can see, or on
  each glass's whole silhouette including the part nobody saw.

## What each comparison isolates

This is the table to read if you want to know what the six are *for*. Each row
holds everything still except one thing.

| Question | Compare | What is held still |
|---|---|---|
| Does a model beat a written rule at all? | 1 against the rest | the bench |
| Is it better to fit here, or to borrow? | 2 against 3–6 | the bench |
| **What does training actually buy?** | **3 against 4** | **the library, the model, the starting weights** |
| Is a small fitted head enough, or must the whole model move? | 5 against 4 and 6 | that a model is borrowed |
| Does the architecture matter once both are trained? | 4 against 6 | the amount of fitting, the free labels and the single class — the licence changes with the architecture |
| Does predicting the hidden part help? | inside 6 | everything but the training target |

**Start with solution 3 against solution 4.** It is the sharpest comparison in
the set: same library, same model, same downloaded weights, same bench. The
training also replaces the borrowed list of everyday categories with a single
class, which cannot be had separately from the training itself, so nothing
varies between the two that the training did not bring. Whatever gap appears
between them is what fine-tuning bought, and no other pairing can make that
claim as cleanly.

## Two axes that cut across the table

### How much is fitted

Reading the table downwards is reading a ladder. Nothing fitted, then everything
fitted here from nothing, then a borrowed model untouched, then that same model
adjusted, then a borrowed model with a small head of its own, then a borrowed
model fully adjusted.

Each rung costs something different. Nothing fitted costs no data and no
training, and is limited by whether a rule can be written down at all. Fitting
here costs a training set and a training run, and buys a model that knows
exactly these pictures. Borrowing costs neither, and buys a model that knows
photographs of the real world — which is not the same thing as knowing this
cell, and that difference has a name.

### The domain gap

The **domain gap** is the difference between the pictures a model was fitted on
and the pictures it is asked about. It is the single most important idea for
reading this table, because four of the six solutions have one and two do not.

Solutions 1 and 2 have no gap: one is a rule and the other learned from this
cell's own pictures. Solutions 3, 4, 5 and 6 all start from weights fitted on
photographs of the everyday world, while this cell renders a grey picture shaded
from depth. Models fail across such a gap in a characteristic way — not by
producing nonsense, but by producing confident, plausible, wrong answers, which
is worse because nothing downstream looks suspicious.

Fine-tuning is the standard repair, which is exactly why solutions 4 and 6
exist, and exactly why the gap between 3 and 4 is worth measuring.

### The licence, which is a real cost

Two of the six are AGPL-3.0, whose network clause reaches a product that only
ever serves answers over a network and never ships a copy of the model.
Everything else this project depends on is permissively licensed, so those two
would change the terms of the whole perception step if they were carried into a
product.

That is accepted deliberately here, because this folder exists to compare
methods and for that purpose the licence costs nothing. It is worth knowing
anyway, because it means the two cars that win on convenience are the two that
would need replacing if the work ever shipped — and the comparison is designed
so that the reading transfers to whichever model is licensed conveniently.

## What is built

**All six are built and all six have been run on the bench.** Each has code in
a folder named after the document you are reading about it, and the numbers the
six produced are set side by side in
[`02-segment-glasses/results/`](../../../02-segment-glasses/results/). No number
in this project is an estimate: where something could not be run, the result is
absent and the reason is written down instead.

The bench was built before the solutions, which was deliberate rather than
accidental, because a comparison whose yardstick arrives after the results is a
comparison nobody can trust. Building the solutions then tested the yardstick in
return, and twice it was the yardstick that was wrong: the mask measurement had
to be rewritten after the bench's own perfect masks failed it, and two of the
six turned out to have been scored on different pictures from the other four.
Both are fixed, and both were found by measuring rather than by reading.

Three things are specified in these documents and are **not** built, and each is
named in the document that asks for it. Two solutions have a second rung that
cannot run here: one needs weights that are behind a licence gate, and one ran
out of machine part way through its training. Neither claims a number. The
amodal target of solution 6 is the third.

## Where to go next

- [The problem](../problem.md) — what is asked for, and the three difficulties.
- [The test bench](../the-bench.md) — the shared input, output and marking.
  **Read this before any solution document.**
- [Looking again at what was hidden](../hidden-glasses.md) — the part all six
  share.
- Then the six, in order: [1](01-rules-on-the-table.md),
  [2](02-train-from-scratch.md), [3](03-yolo-zero-shot.md),
  [4](04-yolo-fine-tuned.md), [5](05-sam2-with-a-keeper.md),
  [6](06-rf-detr-fine-tuned.md).
