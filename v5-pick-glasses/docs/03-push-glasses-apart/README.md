# Problem 3 — push the glasses apart

Problem 2 has ended. The arm knows which pixels are which glass and where each
one stands. Some of them are standing too close together for the gripper to get
round one without fouling its neighbour.

The arm has to **move them apart by dragging them across the table**, not by
lifting them. It does not pick anything up and it does not measure a shape.

This problem is answered **six different ways**, and that is the point of the
folder. Six methods, from a fixed nudge to a fine-tuned robot foundation model,
are given the same readings and marked by the same examiner, so that they can be
compared and one of them chosen knowing what the choice costs. The cell they all
share is described once in [the cell](../the-cell.md).

## Read in this order

1. [**The problem**](problem.md) — what is on the table, what goes in and what
   must come out, the height limit that decides whether a glass slides or tips,
   and what "done" means.
2. [**The examiner**](the-examiner.md) — the crowded tables, what a solution is
   given and never given, and how a run is marked. **Every solution document
   assumes this one.**
3. [**The target layout**](the-target-layout.md) — where the glasses should end
   up, which turns out to be geometry rather than a learning problem, and the
   least movement the task can need.
4. [**Pushing without toppling**](pushing-without-toppling.md) — the refusal
   rule, and the loop of plan, feel and look again, shared by all six.
5. [**The six solutions**](solutions/overview.md) — what they share, what each
   changes, and which pair to compare first.

## The six

| # | Solution | Model and framework | What is learned |
|---|---|---|---|
| 1 | [One fixed nudge](solutions/01-one-fixed-nudge.md) | NumPy | nothing |
| 2 | [Geometry generates, a model ranks](solutions/02-geometry-ranked.md) | gradient-boosted trees, scikit-learn | a preference |
| 3 | [Imitation from demonstrations](solutions/03-imitation-from-demonstrations.md) | ACT, LeRobot | the push, by copying |
| 4 | [A world model, then plan with it](solutions/04-a-world-model.md) | an ensemble in PyTorch, then TD-MPC2 | what a push does |
| 5 | [A foundation model as it downloads](solutions/05-smolvla-as-it-downloads.md) | SmolVLA, LeRobot | nothing |
| 6 | [The same model, fine-tuned here](solutions/06-smolvla-fine-tuned.md) | SmolVLA with LoRA, LeRobot | all of it |

Each document opens with a block saying what it uses, how the output is
produced, how it differs from the other five, and what it costs — so the six can
be read side by side without reading any of them in full.

**Solutions 5 and 6 are the pair to look at first.** Same library, same model,
same downloaded weights; one has had its training continued on this cell's own
pushes. The gap between them measures what fine-tuning buys on a robot
foundation model.

## What is built, and what it costs to run

**All six are built and all six have been run by the examiner**, and the numbers
are set side by side in
[`03-push-glasses-apart/results/`](../../03-push-glasses-apart/results/). Each
document says which of its own second rungs was built and which was not, and no
number anywhere is an estimate: where something could not be run, the result is
absent and the reason is given instead.

One thing worth knowing before the results. The two solutions that borrow a
large model needed the examiner to grow first, and one prescription that would
have helped them both was never built: an early abort, which would stop a push
while the glass is still moving rather than report the topple afterwards. That
absence is measured rather than assumed, because the fine-tuned solution topples
glasses and is what the absence costs.

Unlike the rest of this project, problem 3 does not require everything to run
on one laptop with no graphics card. Each solution states what it needs and
roughly what renting it costs, the way a licence is stated — so a reader knows
the price of reproducing it. Solutions 1 and 2 need nothing rented at all.

## The plan behind the six

[The plan](solutions-plan.md) records the decisions in short form: the contract
all six share, why these six and not others, what the examiner grew in order to mark them,
and what the scorecard needs that problem 2's did not.
