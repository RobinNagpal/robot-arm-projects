# Problem 3 — the six solutions side by side

Six ways of pushing crowded glasses apart so that each one can then be picked
up, all tested on the same 50 tables holding 251 glasses, 193 of which have no
room at the start. Every solution is given the same tables, spends the same
push budget, and is judged by the same scorecard, which is described in
[`docs/03-push-glasses-apart/the-bench.md`](../../docs/03-push-glasses-apart/the-bench.md).
None of them saw these tables while it was being built or fitted. Every number
on this page is read from a solution's own `results.json`.

## The results

| | tables done | tables wrong | glasses racked | toppled | pushes | thinking per push |
|---|---|---|---|---|---|---|
| [1 one fixed nudge](../01-one-fixed-nudge/) | **33** | **0** | 195 | **0** | 213 | fast |
| [2 geometry ranked](../02-geometry-ranked/) | 31 | **0** | 185 | **0** | 229 | fast |
| [3 imitation, ACT](../03-imitation-from-demonstrations/) | 3 | 1 | 68 | 1 | 643 | fast |
| [4 a world model](../04-a-world-model/) | 31 | 1 | **202** | 1 | **114** | middling |
| [5 SmolVLA as it downloads](../05-smolvla-as-it-downloads/) | 0 | 5 | 56 | 6 | 754 | slow |
| [6 SmolVLA fine-tuned](../06-smolvla-fine-tuned/) | 4 | **38** | 77 | **46** | 400 | slow |

A table is **done** when every glass on it was picked up, and **wrong** when
the run ended in a state the cell should never reach. Solutions 3, 5 and 6 are
run several times and the figure shown is the middle one; each folder's own
page gives the spread between runs.

The thinking column is deliberately coarse. Every time on this page was
measured while the machine was busy with other work, and the same solution
timed twice minutes apart gave answers a factor of two apart. The column is
good for the order of magnitude and nothing finer: the two geometry solutions
think for a small fraction of a second, the world model for longer, and the two
that run a large borrowed model take about a second for every push.

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
