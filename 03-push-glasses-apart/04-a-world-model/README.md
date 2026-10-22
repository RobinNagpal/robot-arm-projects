# Problem 3 — the learned way

Glasses stand too close together to be picked up. Push them apart, then pick
each one up. Here a model learns what a push will do from pushes made in a
physics engine. A search then picks the next push using that model. This
folder is the first way of [a world
model](../docs/solutions/04-a-world-model.md), solution 4
in [the overview](../docs/solutions/overview.md). It is
the approach this project uses for problem 3.

## Why this approach

It was built beside the programmed approach
(`../03-push-glasses-apart/01-one-fixed-nudge`, which holds the candidate
geometry solutions 1 and 2 use). Both ran on the same 50 held-out tables. [The
overview](../docs/solutions/overview.md) sets out what
each solution changes and [what is
built](../docs/solutions/overview.md#what-is-built).

The table compares the two. Bold marks the better value in each row.

| | Learned (this folder) | Programmed (solution 1) |
|---|---|---|
| Glasses racked | **146** of 251 | 107 of 251 |
| Tables finished | **20** of 50 | 14 of 50 |
| Tables wrong | 19 | **1** |
| Glasses toppled | 20 | **1** |
| Pushes | 221 | **173** |
| Pushes repeated because the first fell short | 102 | **63** |
| Travel against the floor | 1.98x | **0.87x** |
| Landing, median / worst | 6.9 / 532.3 mm | **1.7 / 57.6 mm** |
| Pushes that went wrong (blocked, never touched, jammed) | 15 | **1** |
| Thinking per push | 374 ms | **93 ms** |

**It racks the most glasses, and it breaks the most.** It racks 146 glasses
against 107, and finishes 20 tables against 14. But it topples 20 glasses
against 1, so 19 of its tables end *wrong* against 1.

So the choice depends on what a toppled glass costs. If it is a wiped floor,
this approach is ahead. If it is broken glass in a kitchen, only the programmed
approach can run unattended.

The model predicts where *every* glass ends up, and the chance of a topple or a
blocked jaw. So the search can pick the push that makes the most room. But
every push also rests on a guessed topple chance, and with the real gripper
that guess is often wrong. [The solution
document](../docs/solutions/04-a-world-model.md)
explains why: no written physics, one model for many goals, and where it fails.

### What it costs

- **Training.** 15,379 pushes really made in the simulator, 30,758 examples
  once each is also used mirrored, and 5 trained networks. That is about half
  an hour on a laptop processor. The programmed approach needs none of this.
- **Fifteen pushes went wrong** (8 blocked on the way down, 7 jammed), against
  one for the programmed approach. The next look caught each one, but each spent
  a push from the table's budget.
- **Toppling is the weak point.** 20 glasses went over on the 50 held-out
  tables. In every case the model had rated the push as safe enough to make.
  See [the results](#results--50-held-out-tables-251-glasses).
- **It thinks four times longer.** 374 ms a push, against 93 ms, because the
  search asks five networks about 1,500 pushes for every crowded glass.
- **The comparison is not fully controlled.** The two approaches also differ in
  their search and in how they check the jaw's path. So not all of the
  difference comes from the model.

## How it works

```
1. look ──▶ take every glass with room
2. for every glass still crowded: search pushes ──model──▶ best push
3. make that one push ──▶ look again ──▶ back to 1
   no push expected to help ──▶ refuse the rest, with the reason
```

Only one step uses the model. The table shows which part does each step:

| Step | Done by |
|---|---|
| Read where each glass stands and how big it is | the camera (problem 2); here `look()` in the bench |
| Decide which glasses have room | a distance rule: no neighbour's edge within 76 mm of the glass's middle |
| Pick up a glass with room | the arm |
| Make up pushes to try | the search |
| **Say what each push would do** | **the model** |
| Drop risky pushes, score the rest, pick the best | the search, using the model's answers |
| Make the push | the arm: a straight move at a fixed slow speed. It does not choose a force; it stops if it touches something coming down, or jams (over 20 N) |
| Check what happened | the camera again |

**The model** is a small network (3 layers of 256), trained 5 times from
different starts. It takes 34 numbers and gives back 14. Positions are measured
along the push and across it. The solution document explains [what the model
is shown](../docs/solutions/04-a-world-model.md#what-this-model-is-shown-and-what-it-answers)
and [why the copies
disagree](../docs/solutions/04-a-world-model.md#ensembles-as-a-measure-of-ignorance).

**Training data.** Each example is one push in the simulator: look, push, look
again. The label is what the second look found, not the simulator's record.
- Round 1: 7,686 random pushes on 4,000 tables.
- Round 2: 7,693 pushes on 5,000 new tables, mostly chosen by the planner using
  the round 1 model. These fill the holes the planner finds.
- Every push is also used mirrored left to right, so 15,379 pushes become 30,758
  examples.
- **27.3% of them toppled something.** That is why the model can see toppling
  at all. It is also why it cannot see it sharply.

**Choosing a push.** For each crowded glass, the cross-entropy method (CEM)
tries 1,500 pushes, varying the heading, where across the glass to push, and
how far. A push is dropped if:
- any of the 5 copies gives it more than a 1% chance of toppling something,
  on the table as seen or on 4 copies moved by the camera's error;
- a glass it moves lands outside the glass zone, or the jaw leaves the arm's
  reach;
- the model predicts a move longer than the push itself.

The rest are scored by the room still missing afterwards, plus a small cost per
millimetre pushed. The best push over all glasses is made. Then the arm looks
again. The model is never asked more than one push ahead. [Planning by
sampling](../docs/solutions/04-a-world-model.md#planning-by-sampling-the-cross-entropy-method)
explains the search.

## Running it

It runs on its own: MuJoCo and PyTorch in a [pixi](https://pixi.sh)
environment, with no ROS and no Gazebo. Install pixi, then from this folder:

```
make setup             # install the environment
make help              # every command, one line each
```

The collected pushes (`data/`) and the trained model (`weights/`) are not in
git. On a fresh checkout, make them first, in this order:

```
make collect           # round 1: random pushes on 4,000 tables, about 5 minutes
make train             # about 5 minutes
make collect-planned   # round 2: the planner's own pushes, about 20 minutes
make train             # again, on both rounds
```

`train` ends by printing the model's error on validation tables it never saw.
The model behind the results below was checked on 628 such pushes:
- the pushed glass lands **6.5 mm** from the prediction at the median, and 38.9
  mm at the worst tenth, against a median real movement of 35 mm;
- *blocked on the way down* is guessed right 96% of the time;
- at a 0.1 chance it catches 158 of the 192 pushes that really topple
  something, but also flags 172 of the 436 safe ones.

A fresh training run gives close numbers, not identical ones.

Then test it:

```
make run               # the 50 held-out tables; writes results.json
make test              # quick checks, no training needed
```

Any run shorter than the 50 held-out tables writes `partial.json`, never
`results.json`. The planner has two settings: the 1% topple limit, and taking a
glass with 3 mm of room to spare. Both were chosen on tables 9500 on, which are
neither trained on nor held out: `pixi run python run.py --first 9500`.

## Seeing what it does

These need a trained model. They write into folders that are not in git.

```
make film                  # videos of the first 3 held-out tables, in videos/
make film FILM=10          # the first 10
make trace TABLE=10004     # one table, step by step, in traces/table-10004/
make examples              # 20 training pushes as JSON, in traces/
```

**`make film`** shows the table from the arm's side, with what the arm is doing
written on it. It ends on the table's outcome.

**`make trace TABLE=<n>`** clears one table and writes into
`traces/table-<n>/`. `TABLE` is any table number; 10000 to 10049 are the
held-out ones. Without make, run `pixi run python trace_table.py --table <n>`.
It writes:
- `step-NN-*.png`, one picture per step. The film's view is on the left. The
  table from above, as the arm knows it, is on the right. What was decided or
  done is written underneath. A push gets three pictures: what the model
  expects, the jaw at the end of the push, and what the next look found.
- `trace.json`. For every push it holds the 34 numbers the model was given, the
  14 each of the 5 copies gave back, and the 14 that really happened. It also
  holds each look, and for each crowded glass how many pushes the search tried
  and why any were dropped.
- `video.mp4`, the same film `make film` makes.

Held-out tables worth tracing:

| Table | What it shows |
|---|---|
| 10000 | the simplest case: one push, then every glass is taken |
| 10004 | three pushes on three different glasses; all 6 racked |
| 10006 | a push blocked on the way down and tried again; one glass pushed twice |
| 10012 | two pushes, then no push is worth making and 3 glasses are refused |

**`make examples`** writes the first 20 collected pushes to
`traces/examples-train.json`. Each is written twice: as the numbers stored for
training, and in millimetres with names. For round 2's pushes, the unseen
validation pushes, or more of them:

```
pixi run python examples.py --round train_planned
pixi run python examples.py --round validation --count 100
```

## Results — 50 held-out tables, 251 glasses

203 of the 251 glasses have no room at the start, so they must be pushed before
they can be taken.

| | Result |
|---|---|
| Tables | done 20, incomplete 11, wrong 19 |
| Glasses | racked 146, refused 85, toppled 20 |
| Pushes | 221 (102 repeats); 8 blocked on the way down, 0 never touched, 7 jammed |
| Travel | 6,496 mm, which is 1.98 times the displacement floor |
| Landing | 6.9 mm from where the model aimed it, median; 532.3 mm worst |
| Thinking | 374 ms a push |
| Model, on unseen tables | pushed glass lands 6.5 mm from its prediction, median; blocked guessed right 96% of the time |

The next table gives the reason for each refused glass:

| Reason | Glasses |
|---|---|
| stopped: a glass on the table has fallen over | 53 |
| no push the model expects to make room | 14 |
| the table's 16 pushes are spent | 10 |
| pushed 4 times and still without room | 8 |

**Read the two tables together.** Most refused glasses were refused because
another glass on their table had fallen. So the 20 topples cost far more than
20 glasses. The worst landing, 532 mm, is a push that sent a glass sliding
across the zone. The real Robotiq 2F-85 is the main reason toppling got worse:
with the earlier thin blade, the same planner toppled about one glass. The
hand, rolled on its side, reaches 266 mm behind its fingertips, is 89 mm across
at the wrist, and cannot come lower than 75 mm. So a push that used to slide a
glass now often lifts or clips it. A lower
topple limit would only refuse more glasses. More examples of how this hand
topples a glass would help. [A worked
example](../docs/solutions/04-a-world-model.md#a-worked-example)
in the solution document explains all of this.

The tables, the physics and the scoring are in `../03-push-glasses-apart/bench`,
shared with `../03-push-glasses-apart/01-one-fixed-nudge`, so both approaches
are tested on the same tables.
