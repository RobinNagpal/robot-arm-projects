# Problem 4 — clear the table

A table holds three to five drinking glasses, and some of them stand too close
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
3. [**The six solutions side by side**](../../04-clear-the-table/results/README.md)
   — every column of the result, the ceiling on the same tables, and which
   columns mislead when read on their own.
4. **One page for each solution**, which gives its spread and what it found out
   while being built: [one fixed nudge](solutions/01-one-fixed-nudge.md),
   [geometry ranked](solutions/02-geometry-ranked.md),
   [imitation from demonstrations](solutions/03-imitation-from-demonstrations.md),
   [a world model](solutions/04-a-world-model.md),
   [SmolVLA as it downloads](solutions/05-smolvla-as-it-downloads.md) and
   [SmolVLA fine-tuned](solutions/06-smolvla-fine-tuned.md).

The cell underneath is the same cell, described once in
[the cell](../the-cell.md). Two documents of problem 3's are still worth
reading, because problem 4 does not restate them: its
[problem](../03-push-glasses-apart/problem.md) derives how much room the hand
needs and the height limit that decides whether a glass slides or tips, and its
[examiner](../03-push-glasses-apart/the-examiner.md) describes the per-push
arrangement that this problem takes two things away from.

## What has been measured

**All six solutions, on the held-out queue.** That queue is fifty tables
offered in order from table ten thousand, with fifteen minutes of arm time for
the whole queue, walked three times. No solution saw those tables while it was
being built or fitted, and the budget belongs to the queue rather than to a
table, so how quickly a solution works decides how far down the list it gets.

| | attempted | separated | glasses freed | pickable share | broken |
|---|---|---|---|---|---|
| [1 one fixed nudge](../../04-clear-the-table/01-one-fixed-nudge/) | 26 | 10 | +25 | **0.627** | **0** |
| [2 geometry ranked](../../04-clear-the-table/02-geometry-ranked/) | 25 | 7 | +19 | 0.582 | **0** |
| [3 imitation, ACT](../../04-clear-the-table/03-imitation-from-demonstrations/) | 11 | 0 | +2 | **0.400** | **2** |
| [4 a world model](../../04-clear-the-table/04-a-world-model/) | **40** | **14** | **+39** | 0.598 | 1 |
| [5 SmolVLA as it downloads](../../04-clear-the-table/05-smolvla-as-it-downloads/) | 11 | 1 | +2 | 0.439 | **0** |
| [6 SmolVLA fine-tuned](../../04-clear-the-table/06-smolvla-fine-tuned/) | 11 | 0 | **0** | 0.405 | **0** |

Every row is the solution as it stands after a round of repairs. The six were
measured once, then the three that were learning something and failing were
changed, and then they were measured again.
[What changed](what-changed.md) records each change beside the measurement that
justified it, and it also records the three changes that were measured and
thrown away.

**Each of the six was also filmed clearing the same table**, so that what a row
of the table above means can be watched rather than inferred. The six films are
linked from
[the comparison page](../../04-clear-the-table/results/README.md#a-film-of-each-solution),
and each solution's own page below links its own.

**[The comparison page](../../04-clear-the-table/results/README.md) is where to
read this properly.** It gives every column, says what perfect play achieves on
exactly the tables each solution reached, and explains the three columns that
mislead when read on their own — above all "tables attempted", which a solution
that gives up instantly would win.

The short version has three parts.

**The world model leads, and it is the only learned solution that beats
arithmetic.** It separates fourteen of the forty tables it reaches, frees the
most glasses of any solution, and now breaks one glass a walk where it used to
break eight. Cut to the twenty-six tables the fixed nudge also reached, it
separates eleven against ten and breaks nothing, so on the same tables it is
level or a little ahead, and its clear advantage is that it reaches half again
as many tables in the same quarter of an hour.

**Arithmetic is still the best answer per table attempted.** One fixed nudge,
chosen by geometry with nothing learned anywhere, separates ten of twenty-six
and breaks no glass, which is the best pickable share on the card.

**The three solutions that answer from a picture are now nearly harmless, and
between them they free four glasses.** That is a poor result, and it is a far
better one than the first walk, where the three of them freed nothing at all and
broke twenty-eight glasses between them. The cause of the poor result is the same
in each case: with the camera on the arm, four of the teacher's five answers only
move it to see, so fitting on those answers teaches the looking rather than the
pushing. Only one of the three is doing the task on purpose — the imitation
policy chooses a glass, tests it and pushes it — while the borrowed model's two
freed glasses come from shoves that happened to go a helpful way.

The six solutions asked this question are problem 3's own, so each of them also
has a standing under problem 3's per-push scorecard, and the two can be set
side by side: the [fixed nudge](../03-push-glasses-apart/solutions/01-one-fixed-nudge.md),
the [ranked geometry](../03-push-glasses-apart/solutions/02-geometry-ranked.md),
the [imitation policy](../03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md),
the [world model](../03-push-glasses-apart/solutions/04-a-world-model.md), a
[borrowed foundation model as it downloads](../03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md),
[the same model fine-tuned here](../03-push-glasses-apart/solutions/06-smolvla-fine-tuned.md),
and a [newer and larger borrowed model](../03-push-glasses-apart/solutions/07-evo1-fine-tuned.md).
Each was run again under this scorecard, and each result carries a spread
wherever anything about it was uncertain, because a result quoted without one
is not a result. Solution 7, the newer and larger borrowed model, is not part
of problem 4: problem 3 fitted it three times and it did not learn the task
there, so there is nothing to port.

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
