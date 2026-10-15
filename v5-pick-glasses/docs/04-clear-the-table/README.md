# Problem 4 — clear the table

A table holds four to seven drinking glasses, and some of them stand too close
together for the gripper to get round one without fouling its neighbour. The arm
has to drag them apart across the table until every glass has room, and then
say that it has finished. Nothing is lifted and nothing is racked: **what is
cleared is the crowding, not the table.**

The dragging, the crowding and the room the hand needs are
[problem 3](../03-push-glasses-apart/README.md)'s, unchanged. **Problem 4 is
problem 3 with two assumptions taken away.**

**The camera above the table is gone.** The arm carries its own camera, so it
sees only what is in front of the jaw, and the only way to see the far corner of
the table is to go there. Looking therefore costs motion and time, as it does on
a real robot.

**The push-by-push hand-over is gone.** A solution runs continuously — look,
act, look again — and **says when it is done**. Nothing marks individual pushes,
nothing filters a solution's answers before carrying them out, and the table is
judged by the arrangement on it when the solution stops.

Both removals follow this project's one rule for ordering its problems: each
problem is the one before it with an assumption removed. Problem 3's
arrangement is not being thrown away — it stays the right instrument for
questions of the form "what did this one change do?", and its
[committed results](../../03-push-glasses-apart/results/README.md) are readable
precisely because it holds everything else still. Problem 4 asks the other
question: what would this arm do with nobody helping it?

The request this problem comes from is
[issue 23](https://github.com/RobinNagpal/robot-arm-projects/issues/23) of the
repository, which also records what each of problem 3's solutions is expected
to do here, written down before anything was measured.

This page says what the problem is, which two assumptions it removes, what has
been measured so far, and which document to read next.

## Read in this order

1. [**The problem**](problem.md) — which two assumptions are removed, what is on
   the table, what the arm is given and must hand back, why the budget is the
   arm's own seconds, and what is counted when it stops.
2. [**The examiner**](the-examiner.md) — the tables, the arm's clock, the
   camera on the wrist, the open run, and how a set of tables is marked.

The cell underneath is the same cell, described once in
[the cell](../the-cell.md). Two documents of problem 3's are still worth
reading, because problem 4 does not restate them: its
[problem](../03-push-glasses-apart/problem.md) derives how much room the hand
needs and the height limit that decides whether a glass slides or tips, and its
[examiner](../03-push-glasses-apart/the-examiner.md) describes the per-push
arrangement that this problem takes two things away from.

## What has been measured

**Nothing.** This folder currently holds a question and no answers.

The measuring machinery is being built in
[`04-clear-the-table/bench/`](../../04-clear-the-table/bench/) — the draw, the
arm's clock, the camera carried by the arm, the open loop and the end-state
scorecard — together with a plain geometry solution, ported to this problem's
contract, that exists so the bench has something honest to check itself
against. Anywhere a result would go, there is no result yet, and no number in
this folder should be read as one.

The seven solutions that will be asked this question are problem 3's own, so
they are already written up and already have a standing under the per-push
scorecard: the [fixed nudge](../03-push-glasses-apart/solutions/01-one-fixed-nudge.md),
the [ranked geometry](../03-push-glasses-apart/solutions/02-geometry-ranked.md),
the [imitation policy](../03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md),
the [world model](../03-push-glasses-apart/solutions/04-a-world-model.md), a
[borrowed foundation model as it downloads](../03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md),
[the same model fine-tuned here](../03-push-glasses-apart/solutions/06-smolvla-fine-tuned.md),
and a [newer and larger borrowed model](../03-push-glasses-apart/solutions/07-evo1-fine-tuned.md).
Each will be run again under this scorecard, and each result will carry a
spread, because a result quoted without one is not a result.

## Why the cell is borrowed rather than copied

Problem 4 imports problem 3's bench: the physics, the glasses, the hand and the
measurement noise are the same. It does not copy them, and nothing under
`03-push-glasses-apart/` is changed.

The reason is that a copy drifts. The first time either side changed, the two
cells would differ in some small way nobody wrote down, and the comparison
between problem 3's numbers and problem 4's — which is the whole reason problem
4 exists — would quietly stop meaning anything. Where problem 4 needs something
problem 3 does not offer, such as a camera that can be moved or a clock in arm
seconds, it is added in problem 4's own bench and the reason it could not be
borrowed is written beside it.
