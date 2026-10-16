# Problem 3 — the six solutions side by side

This page compares every solution to problem 3. Each one pushes crowded glasses
apart so that each glass can then be picked up. All are tested on the same 50
tables, holding 251 glasses, 203 of which have no room at the start. Every
solution gets the same tables, spends the same push budget, and is judged by
the same scorecard, described in
[`docs/03-push-glasses-apart/the-examiner.md`](../../docs/03-push-glasses-apart/the-examiner.md).
None of them saw these tables while being built or fitted. Every number here is
read from a solution's own `results.json`.

All six rows use the same hand: a real **Robotiq 2F-85**, turned on its side.
The examiner used to push with an invented blade. That changed the physics of
every push, so every figure here was measured again, and the four learned
solutions were trained again first. Numbers from before the change are not
comparable and are not quoted here.
[The bench's notes on the jaw](../bench/README.md#the-jaw) explain the hand.

## The results

Each row is one solution. Bold marks the best and the worst values.

| | tables done | tables wrong | glasses racked | toppled | pushes | travel | thinking per push |
|---|---|---|---|---|---|---|---|
| [1 one fixed nudge](../01-one-fixed-nudge/) | 14 | **1** | 107 | **1** | **173** | 0.87x | 93 ms |
| [2 geometry ranked](../02-geometry-ranked/) | 14 | **1** | 107 | **1** | 182 | 1.32x | 102 ms |
| [3 imitation, ACT](../03-imitation-from-demonstrations/) | 2 | 11 | 63 | 12 | 438 | 0.87x | **11 ms** |
| [4 a world model](../04-a-world-model/) | **20** | 19 | **146** | 20 | 221 | 1.98x | 374 ms |
| [5 SmolVLA as it downloads](../05-smolvla-as-it-downloads/) | 1 | 9 | 48 | 12 | 620 | 0.42x | 286 ms |
| [6 SmolVLA fine-tuned](../06-smolvla-fine-tuned/) | 1 | **36** | 56 | **40** | 369 | 1.68x | 404 ms |

A table is **done** when every glass on it was picked up. It is **wrong** when
the run ended in a state the cell should never reach, which in practice means a
glass on its side. Solutions 3, 5 and 6 are run several times, and the figure
shown is the middle one. Each folder's own page gives the spread between runs.

[Solution 7](../07-evo1-fine-tuned/) has no row. Its fits did not learn the
task, so its scoring run was stopped.
[Its document](../../docs/03-push-glasses-apart/solutions/07-evo1-fine-tuned.md#results)
explains why.

**The task is much harder with a real hand than with the invented blade.** 203
of the 251 glasses start without room, and the best solution gets 146 off the
table. The refusals say why. The hand is 139 mm across its fingers, so for
many glasses there is nowhere to put it that is not inside a neighbour. It
cannot go lower than 75 mm, so for many others a push would tip the glass.
Neither refusal is a failure of a method. The cell, as built, makes part of the
job impossible.

## Travel, and why the column is a trap

**Travel is how far the glasses really moved, as a multiple of the least any
legal layout needs.** That least is the displacement floor, which
[the target layout](../../docs/03-push-glasses-apart/the-target-layout.md)
computes: 3,284 mm over these fifty tables. No solution can go below it while
doing the job.

**This column means nothing on its own. Read it beside the glasses racked.** A
solution that never touches anything travels nothing and scores best. That is
what the two smallest numbers are. SmolVLA as it downloads travels 0.42 times
the floor, because its jaw comes down about 200 mm above the table and never
reaches a glass. The imitation policy travels 0.87, because three quarters of
its pushes are stopped on the way down. The fixed nudge is also at 0.87, for a
third reason: it refuses 143 of the 251 glasses and never spends their travel.
**None of these three is economical. All three are simply not doing the
work.**

Among the solutions that move most glasses, the column does separate them. The
world model spends 1.98 times the floor to rack 146 glasses: the most costly
work here, and also the most of it. Solution 6 spends 1.68 to rack 56. That is
the clearest bad bargain. Fine-tuning taught it to move firmly without teaching
it where to put the jaw down. So most of its travel shoves glasses somewhere
unhelpful or knocks them over.

## Thinking time, and what it does not say

The thinking column is the solution's own time, with the simulator's time taken
off. It was measured on an idle machine. That matters: the same runs timed
while other work was running reported up to three and a half times these
figures.

**The cheapest thinking belongs to a neural network, and the most costly to a
search.** The imitation policy answers in 11 ms, because a chunk of waypoints
is one pass through a small network. The two geometry solutions spend about a
tenth of a second trying candidates. The world model spends longest, because it
imagines each candidate through an ensemble of five before choosing.

The two borrowed-model solutions differ here, 286 ms against 404, but not
because of fine-tuning. A low-rank correction is folded into the weights before
the model runs. It changes which numbers the model uses, not how many. So **one
forward pass** costs the same for both: 285 ms for solution 5 and 292 ms for
solution 6. What differs is how many passes a push costs. Solution 6's answers
are more often thrown away for aiming at a glass already refused: 421 of its
1,515 answers, against 5 of solution 5's 1,855. So it spends about 1.4 passes
per push, where solution 5 spends 1.0. **Fine-tuning changed what the model
answers, not what it costs to ask.**

## What the comparison says

**Only the written rules can be left running unattended.** Solutions 1 and 2
each topple one glass in fifty tables and end one table wrong. Every solution
that learns something ends between nine and thirty-six tables wrong. A glass on
its side leaves shards, and the arm keeps moving through them. So this column
is not one trade-off among several. It is the condition for using any of the
rest.

**One learned solution clears many more glasses, and it breaks far more.** The
world model racks 146 against the geometry's 107, more than a third again. It
topples 20 against 1. So learning did not simply win or lose. One mechanism
does both: predicting an outcome instead of refusing whenever the arithmetic is
unsure. It buys the extra glasses and breaks the extra ones. Tuning a threshold
cannot separate the two. A lower topple limit refuses more of the pushes the
model is unsure about, but every one of those 20 topples came from a push the
model was sure about.

**The learning that paid off targeted what the geometry gets wrong.** The
geometry computes exactly how much room a push gains, because that is
arithmetic on the destination. It predicts badly where a pushed glass will
stop, because that needs friction and weight, which nobody here has measured.
Solution 4 learns a model of where the glass stops, and racks the most glasses.
Solution 2 learns a model of the room gained, and reaches *exactly* the same
fourteen tables and 107 glasses as the fixed rule it was meant to beat, for
nine more pushes and half again the travel. **So the useful question is not
whether to learn, but what is worth learning.** When every table is limited by
the hand's width or height, ordering the candidates differently changes only
the route.

**Imitation fails for a reason that was measured.** Solution 3 learns from
solution 2's recorded pushes, so its teacher is one of the rows above. On
tables it was fitted on, its chunks point within 4 degrees of the teacher's. On
new tables they are 22 to 27 degrees off. The hand is 266 mm long behind its
fingertips, so that error puts the wrist over a neighbour. The descent is
stopped, and nothing moves. Fitting on four times the tables removed the
memorising but cut only about a fifth of that error. So the shortfall is the
policy averaging over pushes that disagree, not a lack of examples.

**The borrowed model cannot act, and fitting it taught it to act unsafely.**
Solution 5 racks 48 glasses, exactly the 48 that already had room. Its pushes
do nothing, because its chunks come back about 200 mm above the table.
Solution 6 fits the same model on this cell's demonstrations for a thousand
steps. Its chunks then come down to exactly the push height, and onto the
glasses. In its middle run, 223 of 369 pushes are blocked coming down. It
topples 40 glasses, and 36 of its fifty tables end wrong. **Fitting bought
enough skill to act but not enough to act safely, which here is worse than
doing nothing.** Its correction was still improving when the training budget
ran out. So this is what a thousand steps buys, not what the method can do.

## What these results do not cover

- **Not Gazebo.** The physics is MuJoCo, standing in for the simulator the rest
  of the project uses, because a learned approach needs thousands of pushes.
- **A guessed friction.** No solution is told the table's friction. The ones
  that reason about toppling use a believed range. The bench knows the true
  value and never shares it.
- **No early abort.** [Pushing without
  toppling](../../docs/03-push-glasses-apart/pushing-without-toppling.md)
  argues for stopping a push while the glass is still moving. Nothing here
  builds it, and solutions 4 and 6 show what its absence costs.
- **One training seed for solutions 4, 5 and 6.** Their spread is over
  evaluation runs, not over trainings. That is a narrower claim than the
  examiner asks for. Solution 3 is the only learned solution fitted several
  times, and its three seeds disagree noticeably.
- **One kind of glass per table**, as the cell's own layout produces.

## Reproducing

```
pixi run python 01-one-fixed-nudge/run.py
```

The same line works for each of the other five, from this problem's folder.
The ones that fit something need their training step first. Each folder's
README says which, and what it costs.
