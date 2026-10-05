# Problem 3 — the six solutions side by side

Six ways of pushing crowded glasses apart so that each one can then be picked
up, all tested on the same 50 tables holding 251 glasses, 193 of which have no
room at the start. Every solution is given the same tables, spends the same
push budget, and is judged by the same scorecard, which is described in
[`docs/03-push-glasses-apart/the-bench.md`](../../docs/03-push-glasses-apart/the-bench.md).
None of them saw these tables while it was being built or fitted. Every number
on this page is read from a solution's own `results.json`.

## The results

| | tables done | tables wrong | glasses racked | toppled | pushes | travel | thinking per push |
|---|---|---|---|---|---|---|---|
| [1 one fixed nudge](../01-one-fixed-nudge/) | **33** | **0** | 195 | **0** | 213 | 2.0x | 59 ms |
| [2 geometry ranked](../02-geometry-ranked/) | 31 | **0** | 185 | **0** | 229 | 3.7x | 75 ms |
| [3 imitation, ACT](../03-imitation-from-demonstrations/) | 3 | 1 | 68 | 1 | 643 | 0.4x | **11 ms** |
| [4 a world model](../04-a-world-model/) | 31 | 1 | **202** | 1 | **114** | **1.4x** | 401 ms |
| [5 SmolVLA as it downloads](../05-smolvla-as-it-downloads/) | 0 | 5 | 56 | 6 | 754 | 0.2x | 283 ms |
| [6 SmolVLA fine-tuned](../06-smolvla-fine-tuned/) | 4 | **38** | 77 | **46** | 400 | 2.2x | 283 ms |

A table is **done** when every glass on it was picked up, and **wrong** when
the run ended in a state the cell should never reach.

**Travel is how far the glasses were really moved, as a multiple of the least
any legal arrangement needs.** That least is the displacement floor, which
[the target layout](../../docs/03-push-glasses-apart/the-target-layout.md)
computes from the geometry of each table: 2,534 mm over these fifty tables
altogether. The floor belongs to the table rather than to any method, so no
solution can go below it while doing the job, and a solution at twice the floor
moved the glasses twice as far as the task demanded.

**This column means nothing on its own, and has to be read beside the glasses
racked.** A solution that never touches anything travels nothing and scores
best on it, which is why the two worst solutions here have the two smallest
numbers: SmolVLA as it downloads travels a fifth of the floor because its jaw
comes down too high to reach a glass at all, and the imitation policy travels
less than half the floor because most of its pushes are blocked before they
start. Neither is economical; both are simply not doing the work.

Among the three solutions that do finish most of the tables, the column
separates them cleanly, and it separates them in the same order as the pushes
do. The world model moves the glasses least, at 1.4 times the floor, and racks
the most; the fixed nudge takes 2.0; and the ranked geometry takes 3.7, which
is the same verdict its own page reaches from a different direction. Solution 6
is the instructive case: it travels about as far as the fixed nudge does and
racks a third as many glasses, because the fitting taught it to move
decisively without teaching it where to put the jaw down.

Solutions 3, 5 and 6 are run several times and the figure shown is the middle
one; each folder's own page gives the spread between runs.

The thinking column is the solution's own time, with the simulator's time
taken off, measured on an idle machine with nothing else running. That last
condition matters: the same runs timed while other work was on the machine
reported up to three and a half times these figures, so a compute column
measured under load compares the load and not the methods.

Read against the other columns, the column says something that is easy to get
backwards. **The cheapest thinking belongs to a neural network, and the dearest
to a search.** The imitation policy answers in about a hundredth of a second,
because predicting a chunk of waypoints is one pass through a small network,
while the two geometry solutions spend longer enumerating candidates and the
world model spends longest of all, because it imagines each candidate through
an ensemble before choosing. The two borrowed-model solutions cost the same as
each other, and that is the expected result rather than a surprise: a low-rank
correction changes the weights a model uses, not how many of them it uses, so
fine-tuning buys or loses accuracy without changing the price per push.

## What the comparison says

**Nothing learned beats the written rules here, and that is the result.** The
fixed nudge finishes the most tables, and the only solution that racks more
glasses is the world model, which does it in half the pushes. Everything built
on a borrowed model finishes almost nothing.

**The learning that paid attacked the quantity the geometry gets wrong.** The
geometry computes exactly how much room a push would gain, because that is
arithmetic on the destination, and it predicts badly where a pushed glass will
actually stop, because that needs the friction and the weight distribution that
nobody in this cell has measured. Solution 4 fits a model of the second and
wins; solution 2 fits a model of the first and loses to the printed rule it was
meant to improve. **So the useful question is not whether to learn, but which
quantity is worth learning.**

**Fitting a borrowed model made it worse, not better.** Solution 5 racks a fifth
of the glasses and finishes no table, because about nine of its pushes in ten
touch nothing at all: the trajectories hold the jaw well above the glasses.
Solution 6 fits that same model on this cell's own demonstrations, and it learns
the height a push happens at without learning where to put the jaw down. Two
thirds of its pushes are blocked coming down, and it topples 46 glasses where
the geometry topples none. **Fitting bought enough competence to act and not
enough to act safely, which on this scorecard is worse than inaction** — and
that is why solution 6 has far more wrong tables than the model that can barely
act at all.

**Imitation fails for a different reason, and the reason was measured rather
than guessed.** Solution 3 learns from solution 2's own recorded pushes, so its
teacher is in the room. It places the start of a push roughly right and gets
the heading about thirty degrees out, and the jaw then meets a neighbour on the
way down. Fitting it on four times the demonstrations removed the memorising
but not the averaging, which says the shortfall is the policy averaging over
pushes that disagree, not a shortage of examples.

**Only the geometry never breaks anything.** Solutions 1 and 2 topple no glass
at all, and every solution that learns something topples at least one. A
toppled glass is the one failure this cell cannot take back, so the two columns
on the right of the table matter more than the one on the left.

## What these results do not cover

- **Not Gazebo.** The physics is MuJoCo, standing in for the simulator the rest
  of the project uses, because a learned approach needs thousands of pushes.
- **A guessed friction.** No solution is told what the table's friction is, and
  the ones that reason about toppling use a believed range instead. The bench
  knows the true value and never shares it.
- **No early abort.** [Pushing without
  toppling](../../docs/03-push-glasses-apart/pushing-without-toppling.md) argues
  for stopping a push while the glass is still moving. Nothing here implements
  it, and solution 6 is what its absence costs.
- **One kind of glass per table**, as the cell's own layout produces.

## Reproducing

```
pixi run python 01-one-fixed-nudge/run.py
```

The same line for each of the other five, from this problem's folder. The ones
that fit something need their training step first, and each folder's README
says which and what it costs.
