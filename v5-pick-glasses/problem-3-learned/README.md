# Problem 3 — the learned way

Glasses stand too close together to be picked up. Push them apart, then pick
each one up. Here a model learns what a push will do from pushes made in a
physics engine, and a search picks the next push using that model. This is the
first rung of [a world
model](../docs/03-push-glasses-apart/solutions/04-a-world-model.md), solution 4
in [the overview](../docs/03-push-glasses-apart/solutions/overview.md), and it
is the approach this project uses for problem 3.

## Why this approach

It was built beside the programmed approach (`../problem-3-programmed`, which
holds the candidate geometry solutions 1 and 2 use), and the two were run on
the same 50 held-out tables. [The six
solutions](../docs/03-push-glasses-apart/solutions/overview.md) sets out what
each one changes and [what is
built](../docs/03-push-glasses-apart/solutions/overview.md#what-is-built).

| | Learned (this folder) | Programmed |
|---|---|---|
| Glasses racked | **208** of 251 | 199 of 251 |
| Glasses toppled | 0 | 0 |
| Pushes | **113** | 212 |
| Pushes repeated because the first fell short | **15** | 90 |
| Tables finished | 34 of 50 | 35 of 50 |
| Landing, median / worst | 1.7 / 24.8 mm | **1.0 / 3.9 mm** |
| Pushes that went wrong (blocked, never touched, jammed) | 6 | **0** |

It racks more glasses in about half the pushes, and it topples none. Fewer
pushes matter most, because touching a glass is the only step that can topple
one.

It wins while being less accurate about where a glass lands. The reason is what
it predicts. The programmed planner knows where the pushed glass will land, but
not whether the push will make room. So it pushes, looks, and often has to push
again. The model predicts what the task needs: where *every* glass ends up, and
the chance of a topple or a blocked jaw. The search can therefore pick the push
that makes the most room, instead of the one that lands most exactly.

It also needs no written-down physics. There is no friction value, no tipping
formula and no rule about where the jaw fits. Friction is not measured anywhere
in this cell, so a rule that depends on it rests on a guess. Here, whether a
push slides, topples or is blocked is only what the model has seen happen.

The same model would serve a different goal, for example spreading glasses
evenly, by changing only the cost. A trained policy would have to be trained
again.

### What it costs

- **Training.** 38,012 pushes in the simulator and 5 trained networks, about 31
  minutes on a laptop CPU. The programmed approach needs none.
- **Six pushes went wrong** (4 blocked, 1 never touched, 1 jammed) where the
  programmed approach had none. Each was caught by looking again, and none
  toppled anything.
- **Toppling is the weak point.** None happened on the 50 held-out tables. On
  100 tuning tables the same settings toppled 1 glass, and the model had rated
  every topple it missed as safe. See [the results](#results--50-held-out-tables-251-glasses).
- **The comparison is not fully controlled.** The two approaches differ in
  their search and in how they check the jaw's path, not only in the model. So
  not all of the gain can be charged to the model.
  [Solution 10](../docs/03-push-glasses-apart/solutions/04-a-world-model.md)
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
| Decide which glasses have room | a distance rule: no neighbour's edge within 70 mm of the glass's middle |
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
- Round 1: 24,759 random pushes on 4,000 tables.
- Round 2: 13,253 pushes on 5,000 new tables, mostly chosen by the planner
  using the round 1 model. The planner finds the pushes where the model is
  wrong in its favour. Making those pushes and recording what really happened
  fills exactly those holes.
- Every push is also used mirrored left to right, which is still a true push.

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
saw (`make collect` draws 200 of them; the stored set has 300).
The model behind the results below printed 4.5 mm median for where the pushed
glass lands, and blocked guessed right 96% of the time. A fresh training run
gives close numbers, not identical ones.

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

| | Result |
|---|---|
| Tables | done 34, incomplete 16, wrong 0 |
| Glasses | racked 208, refused 43, toppled 0 |
| Pushes | 113 (15 repeats); 4 blocked on the way down, 1 never touched, 1 jammed |
| Landing | 1.7 mm from where the model aimed it, median; 24.8 mm worst |
| Model, on unseen tables | pushed glass lands 4.5 mm from its prediction, median; blocked guessed right 96% of the time |

**Toppling is the weak point, even though none happened here.** On 100 tuning
tables the same settings toppled 1 glass. The model rated every topple it
missed as safe:
- the jaw met a stemmed glass's stem under the bowl, then lifted and tipped it;
- the jaw's 90 mm body clipped a neighbour behind;
- a tapered glass tipped on its own.

A lower topple limit does not remove these; it only refuses more. They need
more examples than 40 minutes of pushing gives.

The tables, the physics and the scoring are in `../problem-3-sim`, shared with
`../problem-3-programmed`, so both approaches are tested on the same tables.
