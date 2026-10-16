# The six solutions — same table, six ways to push

## Introduction

Problem 3 asks the arm to drag crowded glasses apart until each one has room
for the gripper, without knocking any over. This folder answers it several
times. The aim is not to find one right answer. The aim is to compare the
answers and choose, knowing what each choice costs.

This page is a map. It shows what all the solutions share, what each one
changes, and which pair to read first.

## What all six share

[The examiner](../the-examiner.md) holds three things fixed for every
solution:

- **the same input**: the readings `look()` gives, with problem 2's error,
  plus a top view for the solutions that read pictures;
- **the same output**: a jaw trajectory, either a whole push the examiner
  expands or waypoints given directly;
- **the same marking**: one scorecard, with the displacement floor from
  [the target layout](../the-target-layout.md) as the yardstick.

The score looks at the table afterwards, not at the push. So the method is the
only thing that differs between any two solutions.

Two more parts belong to no solution.
[The target layout](../the-target-layout.md) says where the glasses should end
up. [Pushing without toppling](../pushing-without-toppling.md) holds the
topple limit, the refusal rule, and the loop of plan, feel and look again.

## The seven, in one table

The solutions are ordered by **how much of the pushing the model owns**. That
decides both the work and what can go wrong. The first six are measured. The
seventh was added later.

| # | Solution | What is learned | Model and framework | Licence |
|---|---|---|---|---|
| 1 | [One fixed nudge](01-one-fixed-nudge.md) | nothing | NumPy | — |
| 2 | [Geometry generates, a model ranks](02-geometry-ranked.md) | a preference over candidates | gradient-boosted trees, scikit-learn | permissive |
| 3 | [Imitation from demonstrations](03-imitation-from-demonstrations.md) | the push itself, by copying | ACT, LeRobot | permissive |
| 4 | [A world model, then plan with it](04-a-world-model.md) | what a push does | an ensemble in PyTorch, then TD-MPC2 | permissive |
| 5 | [A foundation model as it downloads](05-smolvla-as-it-downloads.md) | nothing | SmolVLA, LeRobot | check the weights |
| 6 | [The same model, fine-tuned here](06-smolvla-fine-tuned.md) | all of it, from a borrowed start | SmolVLA with LoRA, LeRobot | check the weights |
| 7 | [A newer, larger borrowed model](07-evo1-fine-tuned.md) | all of it, from a borrowed start | Evo-1 on InternVL3-1B, LeRobot | check the weights |

Three solutions carry a **second way** rather than a document of their own:

- **Solution 3** predicts an action chunk directly with ACT, or denoises
  towards one with Diffusion Policy.
- **Solution 4** uses an ensemble written in this project, or TD-MPC2 off the
  shelf.
- **Solution 6** fine-tunes SmolVLA, or π0.5, to see whether a much larger
  foundation model helps.

**Solution 7 asks that last question properly.** It swaps SmolVLA for Evo-1
and keeps everything else from solutions 5 and 6. So the gap between solutions
6 and 7 is what a newer and larger model is worth here.

## What each comparison isolates

Each row below is one question. The middle column names the solutions to
compare. The last column names what stays the same between them.

| Question | Compare | What is held still |
|---|---|---|
| Does any learning beat a fixed nudge? | 1 against the rest | the examiner |
| Is ranking hand-made candidates enough? | 2 against 3–6 | the examiner |
| Build the world model, or take one off the shelf? | inside 4 | that the push is chosen by planning against a learned model |
| Plan with a model, or learn the push directly? | 4 against 3 | that everything is fitted here, from nothing |
| **What does fine-tuning a foundation model buy?** | **5 against 6** | **the model and its weights** |
| Does a much larger foundation model help? | inside 6 | the fine-tuning |

**Start with solution 5 against solution 6.** They use the same library, the
same model and the same downloaded weights. Only solution 6 has been trained
further on this cell's own pushes. So the gap between them is what fine-tuning
buys.

## Two things that cut across the table

### Where the learned part sits

Solution 2's model only orders pushes the geometry already approved. A wrong
answer wastes one push. Solutions 3 to 6 produce the push themselves, so a
wrong answer is carried out. For most solutions the topple limit is checked
before any model is asked. Solution 4 is the exception.
[Pushing without toppling](../pushing-without-toppling.md#some-glasses-cannot-be-pushed-at-all)
explains both cases.

### Where the demonstrations come from

Solutions 3 and 6 learn by copying solution 2's pushes. So they inherit
solution 2's limits, and they are the only solutions whose score depends on
another solution.
[Solution 2](02-geometry-ranked.md#it-is-the-teacher) explains what it teaches,
and [solution 3](03-imitation-from-demonstrations.md#where-the-demonstrations-come-from)
explains how the demonstrations are made.

## What is built

**All six are built and run by the examiner.** Each has its code in a folder
with the same name as its document. The scores are side by side in
[`03-push-glasses-apart/results/`](../../../03-push-glasses-apart/results/).
Where something could not be run, the reason is written down.

Solutions 1 and 2 were built first, because solution 2 is the teacher.
[The plan](../solutions-plan.md#the-examiner-had-to-grow-before-cars-3-to-6-could-run)
lists what the examiner had to add for the others. The early abort in
[pushing without toppling](../pushing-without-toppling.md#an-early-abort-acting-during-the-push)
is not built.

## Where to go next

- [The problem](../problem.md): what is asked, and what makes it hard.
- [The examiner](../the-examiner.md): the shared input, output and marking.
  **Read this before any solution.**
- [The target layout](../the-target-layout.md): where the glasses should end
  up, and the least movement the task needs.
- [Pushing without toppling](../pushing-without-toppling.md): the limit and
  the loop.
- Then the solutions, in order: [1](01-one-fixed-nudge.md),
  [2](02-geometry-ranked.md), [3](03-imitation-from-demonstrations.md),
  [4](04-a-world-model.md), [5](05-smolvla-as-it-downloads.md),
  [6](06-smolvla-fine-tuned.md), [7](07-evo1-fine-tuned.md).
