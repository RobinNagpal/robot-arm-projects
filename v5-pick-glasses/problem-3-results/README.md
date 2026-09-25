# Problem 3 — the two approaches compared

Two ways of pushing crowded glasses apart and then picking them up, tested on
the same 50 tables (251 glasses, 190 of them without room at the start):

- [`problem-3-programmed`](../problem-3-programmed/): geometry and a
  tipping formula, plus a 5 mm test push. No training.
- [`problem-3-learned`](../problem-3-learned/): a model trained on about
  38,000 pushes that predicts what a push will do, and a search that picks
  the best push using it. 31 minutes of training on a laptop.

Both use the tables, physics (MuJoCo), measurements and scorecard in
[`problem-3-sim`](../problem-3-sim/). Neither saw these 50 tables before. The
numbers come from each folder's `results.json`.

## The results

| | Programmed | Learned |
|---|---|---|
| **Tables done** (every glass picked up) | **35** | 34 |
| Tables not finished (glasses left, each with a reason) | 15 | 16 |
| **Tables wrong** | **0** | **0** |
| Glasses picked up | 199 | **208** |
| Glasses refused | 52 | **43** |
| Glasses knocked over | 0 | 0 |
| Pushes | 212 (92 of them 5 mm test pushes) | **113** |
| Pushes that went wrong (blocked coming down, missed, jammed) | **0** | 6 |
| Where the glass stopped, from where it was aimed: median · worst | **1.0 · 3.9 mm** | 1.7 · 24.8 mm |

**On 100 more tables (9500 on):**

| | Programmed | Learned |
|---|---|---|
| Tables done | 68 | 61 |
| Glasses knocked over | 1 | 2 |

The learned approach chose its settings on these tables, and the programmed
one did not. So these numbers flatter the learned side a little.

## What the numbers mean

**Done, not finished, wrong.** *Done*: every glass was picked up, each one
while it really had room. *Not finished*: some glasses were left on the table,
each with a reason. That is a correct answer. *Wrong*: a glass was knocked
over, pushed out of the glass area, picked up without room, or left with no
reason.

**Refused.** A glass the approach decided not to push. For both approaches
this was almost always because there was no safe way in for the jaw, not
because the glass would tip.

**Where the glass stopped.** How far from its aim the pushed glass really
ended up.

## What the comparison says

**Safety is a tie, and neither is perfect.** Neither knocked anything over on
the 50 test tables. On 100 more tables the programmed side knocked over 1
glass and the learned side 2. The programmed miss was a tapered glass that
passed its test push and tipped later in the push: the test only checks how a
glass starts to move. The learned README says its misses came from cases the
model has seen too rarely, such as the jaw catching under a bowl or the jaw's
body clipping a neighbour.

**Clearing the table is close.** The learned side picked up 9 more glasses
and used about half as many pushes. The programmed side checks the jaw
against every neighbour's widest part, as if the whole jaw were that wide all
the way up. That is safe but strict, so it refuses glasses the jaw could in
fact reach. The learned side has no such rule; it learned where the jaw gets
in from pushes that really happened. It also makes no test pushes.

**Accuracy: the programmed side wins clearly.** It never guesses where a glass
will go. It aims, pushes, and looks again. Its worst miss was 3.9 mm. The
learned side acts on the model's prediction, and when the prediction is wrong
the glass can end up 25 mm away. It also had 6 pushes go wrong: 4 blocked
coming down, 1 that never touched the glass, and 1 that jammed. The
programmed side had none, because its jaw checks are worst case.

**Being able to explain it.** Every programmed refusal has a reason you can
check with a ruler: "nowhere clear to push it to". A learned refusal says the
model did not expect a push to help, and nothing more.

**The general lesson.** It is the same as problem 2, from the other side.
Where the rule can be written down (reach, room, the jaw's size), the rule is
exact and safe. Where it cannot, which pushes squeeze through a tight group,
learning finds more. Neither one learned or worked out toppling well enough.

## What these results do not cover

- **The foot width is given to both.** `look()` reports each glass's foot
  width, but a camera looking down sees the widest part, not the foot. It
  would have to come from a side picture, which a crowded glass may not have.
  Both approaches use it, so the comparison is fair, but both are helped.
- **Not Gazebo.** The physics is MuJoCo, the arm is only its jaw, and no
  motion planning is checked.
- **One friction value.** The same on every table. On a real table it varies
  from place to place, which would hurt the learned side more.
- **One training run.** The learned model was trained once.

## Reproducing

```
cd ../problem-3-programmed && make run
cd ../problem-3-learned && make run
```

Retraining the learned model is described in its README.
