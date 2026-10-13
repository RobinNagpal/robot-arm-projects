# Problem 3 — the six solutions side by side

Six ways of pushing crowded glasses apart so that each one can then be picked
up, all tested on the same 50 tables holding 251 glasses, 203 of which have no
room at the start. Every solution is given the same tables, spends the same
push budget, and is judged by the same scorecard, which is described in
[`docs/03-push-glasses-apart/the-examiner.md`](../../docs/03-push-glasses-apart/the-examiner.md).
None of them saw these tables while it was being built or fitted. Every number
on this page is read from a solution's own `results.json`.

All six rows were measured with the same hand. The examiner used to push with a
blade 120 mm long and 28 mm thick, invented for the purpose; it now pushes with
a real **Robotiq 2F-85**, turned on its side because that hand is 139 mm across
its fingers and otherwise does not fit between glasses standing 150 mm apart.
That changed the physics of every push, so every figure here was measured again
and the four learned solutions were trained again first. Numbers from before
that change are not comparable with these and are not quoted on this page.

## The results

| | tables done | tables wrong | glasses racked | toppled | pushes | travel | thinking per push |
|---|---|---|---|---|---|---|---|
| [1 one fixed nudge](../01-one-fixed-nudge/) | 14 | **1** | 107 | **1** | **173** | 0.87x | 93 ms |
| [2 geometry ranked](../02-geometry-ranked/) | 14 | **1** | 107 | **1** | 182 | 1.32x | 102 ms |
| [3 imitation, ACT](../03-imitation-from-demonstrations/) | 2 | 11 | 63 | 12 | 438 | 0.87x | **11 ms** |
| [4 a world model](../04-a-world-model/) | **20** | 19 | **146** | 20 | 221 | 1.98x | 374 ms |
| [5 SmolVLA as it downloads](../05-smolvla-as-it-downloads/) | 1 | 9 | 48 | 12 | 620 | 0.42x | 286 ms |
| [6 SmolVLA fine-tuned](../06-smolvla-fine-tuned/) | 1 | **36** | 56 | **40** | 369 | 1.68x | 404 ms |

A table is **done** when every glass on it was picked up, and **wrong** when
the run ended in a state the cell should never reach, which in practice means a
glass on its side. Solutions 3, 5 and 6 are run several times and the figure
shown is the middle one; each folder's own page gives the spread between runs.

**The task is much harder with a real hand than with the invented blade, and
that is the first thing to read off the table.** 203 of the 251 glasses begin
without room, and the best of these six gets 146 of the 251 off the table. The
refusals say why: the hand is 139 mm across its fingers, so for many glasses
there is nowhere to stand it that is not inside a neighbour, and it cannot be
brought lower than 75 mm, so for many others a push would tip the glass before
it slid. Neither refusal is a failure of a method. Both are the cell telling
the methods that the job, as the cell is built, is partly impossible.

## Travel, and why the column is a trap

**Travel is how far the glasses were really moved, as a multiple of the least
any legal arrangement needs.** That least is the displacement floor, which
[the target layout](../../docs/03-push-glasses-apart/the-target-layout.md)
computes from the geometry of each table: 3,284 mm over these fifty tables
altogether. The floor belongs to the table rather than to any method, so no
solution can go below it while doing the job.

**This column means nothing on its own, and has to be read beside the glasses
racked.** A solution that never touches anything travels nothing and scores
best on it. That is exactly what the two smallest numbers are: SmolVLA as it
downloads travels 0.42 times the floor because its jaw comes down about 200 mm
above the table and never reaches a glass, and the imitation policy travels
0.87 because three quarters of its pushes are stopped on the way down. The
fixed nudge is at 0.87 for a third reason, which is that it refuses 143 of the
251 glasses and so never has to spend the travel they would have needed.
**None of these three is economical. All three are simply not doing the work.**

Among the solutions that move most of the glasses the column does separate
them. The world model spends 1.98 times the floor to rack 146 glasses, which is
the dearest work on this page and also the most of it. Solution 6 spends 1.68
to rack 56, which is the clearest bad bargain here: the fine-tuning taught it
to move decisively without teaching it where to put the jaw down, so most of
that travel is glasses being shoved somewhere unhelpful or knocked over.

## Thinking time, and what it does not say

The thinking column is the solution's own time, with the simulator's time taken
off, measured on an idle machine with nothing else running. That last condition
matters: the same runs timed while other work was on the machine reported up to
three and a half times these figures, so a compute column measured under load
compares the load and not the methods.

Read against the other columns, the column says something that is easy to get
backwards. **The cheapest thinking belongs to a neural network, and the dearest
to a search.** The imitation policy answers in 11 ms, because predicting a
chunk of waypoints is one pass through a small network, while the two geometry
solutions spend about a tenth of a second enumerating candidates and the world
model spends longest of all, because it imagines each candidate through an
ensemble of five before choosing.

The two borrowed-model solutions look different from each other here, 286 ms
against 404, and the difference is not the fine-tuning. A low-rank correction is
folded into the weights before the model runs, so it changes which numbers the
model uses and not how many, and the cost of **one forward pass** is the same
for both: 285 ms for solution 5 and 292 ms for solution 6, which agree to within
a few per cent. What differs is how many passes a push costs. Solution 6's
answers are more often thrown away for aiming at a glass the loop has already
refused — 421 of its 1,515 answers, against 5 of solution 5's 1,855 — so it
spends about 1.4 passes per push where solution 5 spends 1.0. **Fine-tuning
changed what the model answers, not what it costs to ask.**

## What the comparison says

**The written rules are the only solutions that can be left running
unattended.** Solutions 1 and 2 each topple one glass in fifty tables and end
one table wrong. Every solution that learns something ends between nine and
thirty-six tables wrong. A glass on its side leaves shards and an arm that will
carry on moving through them, so this column is not one trade-off among several;
it is the condition on using any of the rest.

**One learned solution clears many more glasses, and it breaks far more.** The
world model racks 146 against the geometry's 107, which is more than a third
again, and it topples 20 against 1. So the honest summary is not that learning
won or lost. It is that the same mechanism — predicting an outcome instead of
refusing whenever the arithmetic is unsure — is what buys the extra glasses and
what breaks the extra ones, and the two cannot be separated by tuning a
threshold. A lower topple limit refuses more of the pushes the model is unsure
about, and every one of those 20 topples came from a push the model was sure
about.

**The learning that paid attacked the quantity the geometry gets wrong.** The
geometry computes exactly how much room a push would gain, because that is
arithmetic on the destination, and it predicts badly where a pushed glass will
actually stop, because that needs the friction and the weight distribution that
nobody in this cell has measured. Solution 4 fits a model of the second and
racks the most glasses; solution 2 fits a model of the first and reaches
*exactly* the same fourteen tables and 107 glasses as the printed rule it was
meant to beat, for nine more pushes and half again the travel. **So the useful
question is not whether to learn, but which quantity is worth learning** — and
when every table bottoms out on the hand's width or height, ordering the
candidates differently changes only the route.

**Imitation fails for a reason that was measured rather than guessed.**
Solution 3 learns from solution 2's own recorded pushes, so its teacher is in
the room and is one of the rows above. On tables it was fitted on its chunks
point within 4 degrees of the teacher's; on tables it never saw, 22 to 27
degrees out. The hand is 266 mm long behind its fingertips, so a heading that
far off puts the wrist over a neighbour, the descent is stopped, and nothing
moves. Fitting it on four times the tables removed the memorising and took only
about a fifth off that error, which says the shortfall is the policy averaging over
pushes that disagree rather than a shortage of examples.

**The borrowed model cannot act, and fitting it taught it to act unsafely.**
Solution 5 racks 48 glasses, which is exactly the 48 that already had room: its
pushes achieve nothing at all, because the chunks come back about 200 mm above
the table. Solution 6 fits that same model on this cell's own demonstrations for
a thousand steps, and the chunks then come down to exactly the height the
gripper pushes at — and onto the glasses. 223 of the 369 pushes in its middle
run are blocked coming down, it topples 40 glasses, and 36 of its fifty tables end wrong.
**Fitting bought enough competence to act and not enough to act safely, which
on this scorecard is worse than inaction.** Its correction was still improving
when the training budget ran out, so that is what a thousand steps buys rather
than what the method can do.

## What these results do not cover

- **Not Gazebo.** The physics is MuJoCo, standing in for the simulator the rest
  of the project uses, because a learned approach needs thousands of pushes.
- **A guessed friction.** No solution is told what the table's friction is, and
  the ones that reason about toppling use a believed range instead. The bench
  knows the true value and never shares it.
- **No early abort.** [Pushing without
  toppling](../../docs/03-push-glasses-apart/pushing-without-toppling.md) argues
  for stopping a push while the glass is still moving. Nothing here implements
  it, and solutions 4 and 6 are what its absence costs.
- **One training seed for solutions 4, 5 and 6.** The spread those three report
  is over evaluation runs rather than over trainings, which is a narrower claim
  than the examiner asks for. Solution 3 is the only learned solution fitted
  several times, and its three seeds disagree by more than a little.
- **One kind of glass per table**, as the cell's own layout produces.

## Reproducing

```
pixi run python 01-one-fixed-nudge/run.py
```

The same line for each of the other five, from this problem's folder. The ones
that fit something need their training step first, and each folder's README
says which and what it costs.
