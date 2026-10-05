# The six solutions — same table, six ways to push

## Introduction

Problem 3 asks the arm to drag crowded glasses apart until each one has room
for the gripper, without knocking any of them over. This folder answers that
six times, and the point of having six is not that one of them is the answer.
The point is to be able to compare them and then choose, knowing what the
choice costs. By the end of this document you will understand what all six
share, what single thing each one changes, and which pair to look at first.

The arrangement is the same one problem 2 uses: six cars driven to one
destination, over the same road, so that when one arrives sooner you know it
was the car.

## What all six share

Three things are held still, and [the test bench](../the-bench.md) describes
them in full. In short:

**The same input.** What the camera work hands over for each standing glass —
where it stands, how tall it is, how wide at its widest and at its foot,
whether it is upright — every reading carrying problem 2's measured error. Plus
a view of the table from the top, for the solutions that read pictures, and
what the jaw felt on the last push. Never the simulator's record, and never
the friction it is using.

**The same output.** A jaw trajectory. A solution that thinks in whole pushes
emits one and the bench expands it through a macro the bench owns; a solution
that produces waypoints emits them directly.

**The same marking.** One scorecard, and the displacement floor from [the
target layout](../the-target-layout.md) as the yardstick.

The decision that makes all of this work is that **the score is the table
afterwards, not the push that changed it**. There is no shared language for an
action here — three numbers and fifty waypoints are not the same kind of thing
— but the table is the same table either way. So the outcome is what is
measured, and any action space is allowed as long as the outcome is measured
identically.

Two more parts belong to no solution. Where the glasses should end up is
geometry, solved before the arm moves, and it lives in [the target
layout](../the-target-layout.md). The height limit that decides whether a glass
slides or tips, the refusal for glasses that cannot be pushed at all, and the
loop of plan, feel and look again all live in [pushing without
toppling](../pushing-without-toppling.md).

## The six, in one table

They are ordered by **how much of the pushing the model is asked to own**,
which is what decides both the work involved and what can go wrong.

| # | Solution | What is learned | Model and framework | Licence |
|---|---|---|---|---|
| 1 | [One fixed nudge](01-one-fixed-nudge.md) | nothing | NumPy | — |
| 2 | [Geometry generates, a model ranks](02-geometry-ranked.md) | a preference over candidates | gradient-boosted trees, scikit-learn | permissive |
| 3 | [Imitation from demonstrations](03-imitation-from-demonstrations.md) | the push itself, by copying | ACT, LeRobot | permissive |
| 4 | [A world model, then plan with it](04-a-world-model.md) | what a push does | an ensemble in PyTorch, then TD-MPC2 | permissive |
| 5 | [A foundation model as it downloads](05-smolvla-as-it-downloads.md) | nothing | SmolVLA, LeRobot | check the weights |
| 6 | [The same model, fine-tuned here](06-smolvla-fine-tuned.md) | all of it, from a borrowed start | SmolVLA with LoRA, LeRobot | check the weights |

Three carry a **second rung** rather than a document of their own:

- **Solution 3** predicts an action chunk directly with ACT, or denoises
  towards one with Diffusion Policy.
- **Solution 4** uses an ensemble written in this project, or TD-MPC2 off the
  shelf.
- **Solution 6** fine-tunes SmolVLA, or π0.5, to see whether a markedly larger
  foundation model helps.

## What each comparison isolates

| Question | Compare | What is held still |
|---|---|---|
| Does any learning beat a fixed nudge? | 1 against the rest | the bench |
| Is ranking hand-made candidates enough? | 2 against 3–6 | the bench |
| Build the world model, or take one off the shelf? | inside 4 | that the push is chosen by planning against a learned model |
| Plan with a model, or learn the push directly? | 4 against 3 | that everything is fitted here, from nothing |
| **What does fine-tuning a foundation model buy?** | **5 against 6** | **the model and its weights** |
| Does a much larger foundation model help? | inside 6 | the fine-tuning |

**Start with solution 5 against solution 6.** It is the sharpest pair, because
it is the same library, the same model and the same downloaded weights, and one
of them has had its training continued on this cell's own pushes. That is the
question problem 2 asks about a segmenter, asked one level up about a robot
foundation model.

## Two things that cut across the table

### Where the learned part sits

Reading the table downwards is reading a ladder from a model that only
*prefers* to a model that *decides*. Solution 2's model orders candidates the
geometry already approved, so a wrong answer wastes one push. Solutions 3, 4, 5
and 6 produce the push themselves, so a wrong answer is carried out.

What makes that bearable in five of the six is the refusal rule. For them the
topple limit is arithmetic applied **before** any model is consulted, so no
model can cause the failure this problem cares most about: a better model makes
bad pushes rarer, and only the arrangement puts a ceiling on how bad they get.
Solution 4 is the exception, because it holds no friction value to put in the
limit and refuses on its own model's evidence instead, so there the ceiling
comes from the model after all. [Pushing without
toppling](../pushing-without-toppling.md) sets out both arrangements.

### Where the demonstrations come from

Solutions 3 and 6 learn by copying, and what they copy is solution 2's ranked
geometric pushes. That is cheap, because a push on the bench costs
milliseconds — and it has a consequence worth stating plainly rather than
softening.

**Those two inherit solution 2's ceiling** on the pushes they imitate, and
filtering the demonstrations to successes trains them on a biased sample of
what solution 2 does well. So **solutions 3 and 6 are the only ones whose score
depends on another solution's**. Solution 2 labels its own candidates from the
bench, and solution 4 collects its own pushes — random ones first, then its own
planner's — so neither owes anything to a sibling. That is a real asymmetry in
the comparison, not a detail.

## What is built

**All six are built, and all six have been run on the bench.** Each has code in
a folder named after the document you are reading about it, and the numbers they
produced are set side by side in
[`03-push-glasses-apart/results/`](../../../03-push-glasses-apart/results/).
Where something could not be run, the result is absent and the reason is
written down rather than estimated.

Solutions 1 and 2 were built first, and that order mattered more than expected.
Solution 2 is the teacher whose pushes solutions 3 and 6 learn from, so until it
worked there was nothing for them to learn from. The bench also had to grow
before the three that read pictures could run at all: the view from above and
the path that accepts waypoints are both recent, and
[the plan](../solutions-plan.md) says what they cost to add.

One prescription in [pushing without
toppling](../pushing-without-toppling.md) is **not** built and is worth knowing
about before reading the results: the early abort, which would stop a push
while the glass is still moving. Nothing here implements it, and solution 6 is
what its absence costs.

## Where to go next

- [The problem](../problem.md) — what is asked for, and what makes it hard.
- [The test bench](../the-bench.md) — the shared input, output and marking.
  **Read this before any solution.**
- [The target layout](../the-target-layout.md) — where the glasses should end
  up, and the least movement the task needs.
- [Pushing without toppling](../pushing-without-toppling.md) — the limit and
  the loop, shared by all six.
- Then the six, in order: [1](01-one-fixed-nudge.md),
  [2](02-geometry-ranked.md), [3](03-imitation-from-demonstrations.md),
  [4](04-a-world-model.md), [5](05-smolvla-as-it-downloads.md),
  [6](06-smolvla-fine-tuned.md).
