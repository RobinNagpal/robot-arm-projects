# Problem 3 — the learned way

Glasses stand too close together to be picked up. Push them apart, then pick
each one up. Here a model learns what a push will do from pushes made in a
physics engine, and a search picks the next push using that model. This is the
first rung of [a world
model](../../docs/03-push-glasses-apart/solutions/04-a-world-model.md), solution 4
in [the overview](../../docs/03-push-glasses-apart/solutions/overview.md), and it
is the approach this project uses for problem 3.

## Why this approach

It was built beside the programmed approach (`../03-push-glasses-apart/01-one-fixed-nudge`, which
holds the candidate geometry solutions 1 and 2 use), and the two were run on
the same 50 held-out tables. [The six
solutions](../../docs/03-push-glasses-apart/solutions/overview.md) sets out what
each one changes and [what is
built](../../docs/03-push-glasses-apart/solutions/overview.md#what-is-built).

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

**It racks the most glasses of any approach here, and it breaks the most.** It
gets 146 glasses off the table against the programmed approach's 107, which is
more than a third again, and it finishes 20 tables against 14. Then it topples
20 glasses against 1, and because a toppled glass stops the table it happens
on, 19 of its fifty tables end *wrong* against the programmed approach's 1.

So the two cannot be put in order on one number, and the choice between them is
a choice about what a mistake costs. If a dropped glass is a wiped floor, this
one is clearly ahead. If a dropped glass is broken glass in a kitchen, it is
not usable at all, and the programmed approach is the only one of the pair that
can be run unattended.

The reason it both wins and loses is the same reason, and it is what the model
predicts. The programmed planner knows where the pushed glass will land, but it
does not know whether the push will make room, so it pushes, looks, and often
has to push again. The model predicts what the task actually needs: where
*every* glass ends up, and the chance of a topple or a blocked jaw. This means
the search can pick the push that makes the most room rather than the one that
lands most exactly — and it also means that every push it makes rests on a
guessed chance of toppling, which with the real gripper is a guess the model
gets wrong twenty times in fifty tables.

It also needs no written-down physics. There is no friction value, no tipping
formula and no rule about where the jaw fits. Friction is not measured anywhere
in this cell, so a rule that depends on it rests on a guess. Here, whether a
push slides, topples or is blocked is only what the model has seen happen.

The same model would serve a different goal, for example spreading glasses
evenly, by changing only the cost. A trained policy would have to be trained
again.

### What it costs

- **Training.** 15,379 pushes really made in the simulator, 30,758 once each is
  used mirrored as well, and 5 trained networks, which is about half an hour on
  a laptop processor. The programmed approach needs none of this.
- **Fifteen pushes went wrong** (8 blocked on the way down, 7 jammed) where the
  programmed approach had one. Each was caught by looking again, so none of
  them is a hidden failure, but each one spent a push from the table's budget.
- **Toppling is the weak point, and it is now the headline rather than a
  footnote.** 20 glasses went over on the 50 held-out tables, and in every case
  the model had rated the push that did it as safe enough to make. The model is
  not blind to toppling — on validation pushes it catches 158 of the 192 that
  really topple something — but it reaches that recall by flagging 172 of 436
  safe pushes as well, so it is working at the edge of what it can tell apart.
  See [the results](#results--50-held-out-tables-251-glasses).
- **It thinks four times longer than it did.** 374 ms a push, against the
  programmed approach's 93 ms, because the search asks five networks about
  1,500 pushes for every crowded glass.
- **The comparison is not fully controlled.** The two approaches differ in
  their search and in how they check the jaw's path, not only in the model. So
  not all of the difference can be charged to the model.
  [Solution 4's document](../../docs/03-push-glasses-apart/solutions/04-a-world-model.md)
  has the full comparison.

## How it works

```
1. look ──▶ take every glass with room
2. for every glass still crowded: search pushes ──model──▶ best push
3. make that one push ──▶ look again ──▶ back to 1
   no push expected to help ──▶ refuse the rest, with the reason
```

Only one step uses the model. Everything else is plain code:

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

**The model.** A small network (3 layers of 256), trained 5 times from
different starts. Where the 5 copies disagree, the model has not seen a push
like this one.
- In, 34 numbers: the table's kind; the pushed glass's height, widest width
  and foot width; the push (how far across the glass the jaw meets it, and how
  far it pushes); and where up to 5 other glasses stand and how big they are.
  Positions are measured along the push and across it, so a push north and the
  same push east are one example.
- Out, 14 numbers: where the pushed glass moves, where each other glass moves,
  the chance something topples, and the chance the jaw is blocked on the way
  down.

**Training data.** Each example is one push really made in the simulator: look,
push, look again. The question is the table and the push. The answer is what
the second look found. Nobody tells the model whether a push was good; a push
that toppled a glass teaches it as much as one that worked. The labels come
from the camera's readings, not from the simulator's record.
- Round 1: 7,686 random pushes on 4,000 tables.
- Round 2: 7,693 pushes on 5,000 new tables, mostly chosen by the planner
  using the round 1 model. The planner finds the pushes where the model is
  wrong in its favour. Making those pushes and recording what really happened
  fills exactly those holes.
- Every push is also used mirrored left to right, which is still a true push,
  so the 15,379 pushes become 30,758 examples.
- **27.3% of them toppled something.** With the real gripper the training set
  is nearly a third topples, which is why the model can see toppling at all;
  it is also why it cannot see it sharply, because a quarter of everything
  looks dangerous.

**Choosing a push.** For each crowded glass, the cross-entropy method (CEM)
tries 1,500 pushes, varying the heading, where across the glass to push, and
how far. A push is dropped if:
- any of the 5 copies gives it more than a 1% chance of toppling something,
  on the table as seen or on 4 copies moved by the camera's error;
- a glass it moves lands outside the glass zone, or the jaw leaves the arm's
  reach. This map is the only thing written down;
- the model predicts a move longer than the push itself. That is the model
  guessing outside what it has seen.

The rest are scored by how much room is still missing on the table
afterwards, plus a small cost per millimetre pushed. The best push over all
glasses is made. Then the arm looks again and plans afresh. The model is
never asked more than one push ahead.

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

`train` ends by printing how far out the model is on validation tables it never
saw. The model behind the results below was checked on 628 such pushes. It puts
the pushed glass **6.5 mm** from where it really lands at the median, and 38.9
mm at the worst tenth, against a median real movement of 35 mm; it guesses
*blocked on the way down* right 96% of the time; and at a 0.1 chance it catches
158 of the 192 pushes that really topple something, while flagging 172 of the
436 that are safe. A fresh training run gives close numbers, not identical
ones.

Then test it:

```
make run               # the 50 held-out tables; writes results.json
make test              # quick checks, no training needed
```

Any run shorter than the 50 held-out tables writes `partial.json`, never
`results.json`. The planner's two settings (the 1% topple limit, and taking a
glass with 3 mm of room to spare) were chosen on tables 9500 on, which are
neither trained on nor held out: `pixi run python run.py --first 9500`.

## Seeing what it does

These need a trained model, and write into folders that are not in git.

```
make film                  # videos of the first 3 held-out tables, in videos/
make film FILM=10          # the first 10
make trace TABLE=10004     # one table, step by step, in traces/table-10004/
make examples              # 20 training pushes as JSON, in traces/
```

**`make film`** shows the table from the arm's side, with what the arm is doing
written on it, and ends on the table's outcome.

**`make trace TABLE=<n>`** clears one table and writes into
`traces/table-<n>/`. `TABLE` is any table number; 10000 to 10049 are the
held-out ones. The same without make is
`pixi run python trace_table.py --table <n>`. It writes:
- `step-NN-*.png`, a picture for each step, named by its number. The film's
  view is on the left, the table from above as the arm knows it is on the
  right, and what was decided or done is written underneath. A push gets
  three: what the model expects, the jaw at the end of the push, and what the
  next look found.
- `trace.json`. For every push it holds the 34 numbers the model was given,
  the 14 each of the 5 copies gave back, and the 14 that really happened. It
  also holds each look, and for each crowded glass how many pushes the search
  asked about and why any were dropped.
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

Why each refused glass was refused:

| Reason | Glasses |
|---|---|
| stopped: a glass on the table has fallen over | 53 |
| no push the model expects to make room | 14 |
| the table's 16 pushes are spent | 10 |
| pushed 4 times and still without room | 8 |

**Read those two tables together, because the second explains the first.** The
largest single reason a glass is left on the table is not that the search could
not find a push for it. It is that some *other* glass had already fallen over,
which stops the table, so 53 glasses are refused as a consequence of the 20
topples rather than on their own merits. Remove the toppling and this solution
would clear far more than 146.

**The worst landing is 532 mm, which is not a mis-estimate but a different kind
of event.** A push that catches a glass badly can send it sliding most of the
way across the zone, and the model, which was fitted on pushes that mostly move
a glass about 35 mm, has no way to predict that. These are the same pushes that
topple, seen from the other side.

**The hand is why this got worse rather than the model.** The same search and
the same topple limit toppled about one glass when the examiner used a thin
invented blade. The real Robotiq 2F-85, rolled on its side, reaches 266 mm back
behind its fingertips, is 89 mm across at the wrist, and cannot be brought
lower than 75 mm, so a push that was previously a clean slide now often lifts
or clips. The model learns that from examples rather than from a rule, and 27%
of its examples now topple something, which is too blunt a signal to separate
the safe pushes from the unsafe ones.

A lower topple limit does not remove this; it only refuses more glasses. What
would help is examples of the specific ways this hand topples a glass, and that
costs more pushing than half an hour gives.

The tables, the physics and the scoring are in `../03-push-glasses-apart/bench`, shared with
`../03-push-glasses-apart/01-one-fixed-nudge`, so both approaches are tested on the same tables.
