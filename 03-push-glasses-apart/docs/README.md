# Problem 3 — push the glasses apart

Problem 2 has ended. The arm knows where each glass stands. Some glasses stand
too close together for the gripper to reach one without hitting its neighbour.

The arm has to **move them apart by dragging them across the table**. It does
not lift anything, and it does not measure a shape.

This folder answers the problem **several different ways**. Every solution gets
the same readings and the same examiner, so they can be compared. The cell they
share is described once in [the cell](../../01-rack-one-glass/docs/the-cell.md).

## Read in this order

1. [**The problem**](problem.md): what is on the table, what goes in, what
   comes out, and what "done" means.
2. [**The examiner**](the-examiner.md): the crowded tables, what a solution is
   given, and how a run is marked. **Every solution document assumes this
   one.**
3. [**The target layout**](the-target-layout.md): where the glasses should end
   up, and the least movement the task needs.
4. [**Pushing without toppling**](pushing-without-toppling.md): when a glass
   slides and when it tips, the refusal rule, and the loop of plan, feel and
   look again.
5. [**The solutions**](solutions/overview.md): what they share, what each one
   changes, and which pair to compare first.

## The seven

The first six are measured. The seventh was added later. It asks whether a
newer and larger borrowed model helps.

| # | Solution | Model and framework | What is learned |
|---|---|---|---|
| 1 | [One fixed nudge](solutions/01-one-fixed-nudge.md) | NumPy | nothing |
| 2 | [Geometry generates, a model ranks](solutions/02-geometry-ranked.md) | gradient-boosted trees, scikit-learn | a preference |
| 3 | [Imitation from demonstrations](solutions/03-imitation-from-demonstrations.md) | ACT, LeRobot | the push, by copying |
| 4 | [A world model, then plan with it](solutions/04-a-world-model.md) | an ensemble in PyTorch, then TD-MPC2 | what a push does |
| 5 | [A foundation model as it downloads](solutions/05-smolvla-as-it-downloads.md) | SmolVLA, LeRobot | nothing |
| 6 | [The same model, fine-tuned here](solutions/06-smolvla-fine-tuned.md) | SmolVLA with LoRA, LeRobot | all of it |
| 7 | [A newer, larger borrowed model](solutions/07-evo1-fine-tuned.md) | Evo-1 on InternVL3-1B, LeRobot | all of it |

Each solution document opens with a short block. It says what the solution
uses, how it differs from the others, and what it costs.

**Solutions 5 and 6 are the pair to look at first.**
[The overview](solutions/overview.md#what-each-comparison-isolates) says why.

## What is built, and what it costs to run

All six are built and run by the examiner. The scores are side by side in
[`03-push-glasses-apart/results/`](../results/). No
number is an estimate. Where something could not be run, the reason is given
instead.

One part of the design is not built: an early abort that would stop a push
while the glass is still moving.
[Pushing without toppling](pushing-without-toppling.md#an-early-abort-acting-during-the-push)
explains it.

Problem 3 may use rented hardware. Each solution says what it needs and what
renting it costs. Solutions 1 and 2 need nothing rented.

## The plan behind the six

[The plan](solutions-plan.md) lists the decisions in short form: why these six
and not others, and what the examiner had to add to mark them.
