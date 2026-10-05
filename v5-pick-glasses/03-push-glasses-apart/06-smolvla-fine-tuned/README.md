# Solution 6 — the same foundation model, fine-tuned here

SmolVLA, the 450-million-parameter robot foundation model that [solution
5](../05-smolvla-as-it-downloads) uses exactly as it downloads, with its
training continued on pushes made on this bench. The training is a **low-rank
correction**: every borrowed number stays where it is and a small correction is
learned beside it, then folded in, so what runs afterwards is a model of the
original size and speed.

The two solutions are a matched pair. Same library, same weights, same picture,
same sentence, same reading of an action into jaw waypoints, same loop, same
checks, same marking. One thing differs, which is the training, and the gap
between the two scores is what that training bought.

Full explanation: [the
document](../../docs/03-push-glasses-apart/solutions/06-smolvla-fine-tuned.md).

## What is here

| File | What it does |
|---|---|
| `partners.py` | Puts solutions 1, 2 and 5 on the import path, and says why each is borrowed |
| `chunks.py` | A recorded push cut, resampled and read into the model's units: the training target |
| `demonstrations.py` | Runs the teacher over the training tables and writes a LeRobot dataset |
| `correction.py` | The borrowed model, the low-rank correction, and loading the two together |
| `train.py` | Fits the correction. Says what it fits and where it saves |
| `run.py` | The held-out tables, scored; writes `results.json` |
| `test_fine_tuned.py` | The checks that need no correction and no download |

The convention that reads an action as jaw waypoints, and the loop of plan,
feel and look again, are solution 5's and are imported rather than copied,
because a second copy of either would be a second thing that could vary
between the pair. `Fitted` is solution 5's `Downloaded` with the correction
loaded on top, so the asking is inherited too. What is written out again here
is the twelve lines that fetch the weights and build the processors, because
the training needs the model before the correction is attached to it.

## Running it

```
make demonstrations   # the teacher over 800 training tables (about 20 minutes)
make tuning           # the same on 50 tuning tables, which say when to stop
make train            # fits the correction (downloads the weights once)
make run              # the 50 held-out tables, 3 evaluation runs
make test
```

Any run shorter than the full held-out set writes `partial.json`, never
`results.json`. `make train SEED=1 INTO=correction-1` fits a second training
seed, and `run.py --correction correction --correction correction-1` scores
both, which is what [the bench](../../docs/03-push-glasses-apart/the-bench.md)
asks for.

## What it costs

**It trains on this machine.** The document said it needed a rented
accelerator; that turned out to be wrong, and the reason is the one the
document gives for why low-rank adaptation is used at all. Only the
correction's four million numbers carry gradients and optimiser state, so what
has to be held is the model plus a little: **1.02 GiB of the Mac's unified
memory**, measured while it ran, against the 22 GB the document quotes for a
low-rank fine-tune of π0. Memory was never the obstacle at this size. Time is:
a step took 4 seconds on Metal — and that was on a laptop shared with three
other training runs — where an NVIDIA card would take a fraction of a second.
So the committed correction is 1,000 steps at a batch of 4, which is a small
fraction of the compute LeRobot's own SmolVLA recipe spends (twenty thousand
steps at a batch of sixty-four), and that is the honest caveat on every number
here.

Renting would still be the way to spend real compute on it, and the figures
are the ones the rest of this problem uses: hours of a small accelerator is of
order tens of dollars, a weekend of order a hundred, a month of order five
hundred. Nothing here was rented.

At run time it is one large forward pass per chunk, on this laptop, which is
solution 5's cost exactly because the correction is folded into the weights.

## The demonstrations

800 training tables, 22 minutes of simulator time, **2,012 demonstrations from
740 of those tables**; the other 60 gave the teacher nothing to push. Of the
3,554 pushes the teacher made, 1,533 were the 5 mm test pushes that belong to
the shared tipping check rather than to the chooser, and of the 2,021 real
pushes only **9 were discarded** — 8 toppled a glass, 1 pushed one out of the
zone. So the bias from filtering to successes, which the document spends a page
on, is four tenths of one per cent here. `demonstrations/collected.json`
records all of it.

A chunk covers 89 mm of table in 49 waypoint periods, 1.8 mm a waypoint.

## Three things to know before reading the numbers

**The student pushes faster than its teacher.** A chunk holds the number of
waypoints SmolVLA emits in one pass, which is 50, and the teacher's push is
two or three times that many once the bench has sampled it. So the recorded
push is resampled to a chunk's length, and since the bench consumes waypoints
a fixed period apart, that makes the student's jaw travel about 36 mm/s where
the teacher felt forward at 10 and pushed at 20. It is the one place the
borrowed model's shape shows through into the physics.

**One training seed, not several.** The document and the bench both ask for
several, because training varies with its seed. Only one was fitted here, so
the spread in `results.json` is over evaluation runs alone and is a narrower
claim than the spread the bench wants.

**The compute column was re-measured, and it says what the method predicts.**
`seconds_per_push` is wall time with the bench's own share taken off, so a
reading taken while the machine is busy measures the other work too. Timed
while several training runs shared the laptop it read 0.82 s; timed again on
an idle machine it reads 283 ms. That second figure is the one to use, and it
confirms what the method guarantees rather than merely agreeing with it: a
low-rank correction folds into the weights without adding any, so this
solution's forward pass is the same arithmetic as solution 5's, and solution 5
measured on the same idle machine costs 283 ms too, agreeing to the
millisecond. The two are the same price per
push, and fine-tuning changes what the model answers rather than what it costs
to ask.

## What the training moved

`correction/training.json` holds the whole curve. Distances below are between
the model's own waypoints and the teacher's, on tuning tables nothing was
fitted on.

| Step | Fitting loss | Tuning error, median | Worst |
|---|---|---|---|
| 0 — the correction is zero, so this is solution 5 | — | **320 mm** | 658 mm |
| 500 | 0.299 | **84 mm** | 270 mm |
| 1000 | 0.159 | 90 mm | 196 mm |

The glass zone is 320 mm by 360 mm, so the borrowed model's untrained answer
is not a push aimed at the wrong glass — it is a smooth motion somewhere else
on the table entirely. Five hundred steps cut that by three quarters.

**Training stopped at 1,000 steps because the tuning column said to.** Between
500 and 1,000 the fitting loss halved while the held-out error did not improve,
which is the shape that says the extra training is going into the examples
rather than into the pushing. Read it with the caution it deserves: each
tuning figure is 16 chunks from a policy that draws its answer, so the step
from 84 mm to 90 mm is inside the noise. What is outside the noise is that the
fall stopped.

**And the chunks changed shape in a way that is easier to see than the loss.**
Each solution's `asking.json` records what its answers looked like:

| | Solution 5, untrained | This solution | The teacher |
|---|---|---|---|
| Lowest the chunk reaches above the table | 247 mm | **50 mm** | 50 mm |
| Distance across the table in one chunk | 964 mm | 315 mm | 89 mm |
| Per waypoint, which is the speed | 16.3 mm | 4.5 mm | 1.8 mm |

The first row is the whole of what the training bought that can be seen
without the scorecard: the borrowed model never brings the jaw down to the
glasses, and the fine-tuned one brings it to exactly the height the gripper
pushes at. The second and third rows are what it did not buy. Its pushes are
still three times too long and four times too fast, and the price of that is
in the toppled column below. (Solution 5's figures are from a run taken before
the bench capped a commanded path to the jaw's top speed, so its *outcome*
counts are not comparable with these; the shape of a chunk is the model's own
output and is.)

## Results — 50 held-out tables, 251 glasses, 193 without room at the start

Three evaluation runs of one training seed. `results.json` holds every run;
below is the middle with the spread across the three.

| | |
|---|---|
| Tables | 4 done, 8 not finished, **38 wrong** |
| Glasses | 77 racked (±5.7), 115 refused (±5.0), **46 toppled** (±5.7), 13 pushed out of the zone (±5.0) |
| Glasses picked without room, or left with no reason | **0** and **0** |
| Pushes | 400 (±40), of which 280 repeats |
| Pushes that went wrong, in the middle run | **247 blocked on the way down**, 45 jammed, 39 never touched, of 400 |
| Where the glass stopped, from where the chunk ended | 60.6 mm median, 917 mm worst |
| Thinking per push | 283 ms (±1) on an idle machine |

**This is a bad score, and it is a bad score for one reason.** Nearly two
thirds of its pushes — 247 of the 400 in the middle run — were **blocked on
the way down**: the chunk's first waypoint is over a glass, so the jaw comes
down onto one instead of behind it. The share is taken from one run rather
than from the spread above, because the spread reports a median for each field
on its own, and those medians come from different runs: 400 pushes from one and
259 blocked from another, which together describe no run that happened.
The model learned the height a push happens at and the kind of motion a push
is, and did not learn where to put the jaw down. From there everything else
follows: 46 glasses over, 38 tables wrong, and 79 of the refusals reading
"stopped: a glass fell over" rather than anything about the glass.

**What it did get right is not nothing**, and it is worth separating out,
because the shared machinery and the model are doing different jobs here. No
glass was ever picked up without really having room, and no glass was ever
left on the table without a reason. Those are the two mistakes the geometry
exists to prevent, and it prevented all of them, on every run, under a policy
that was doing its best to cause them.

### Against the other solutions that have run

| | 1 — fixed nudge | 4 — world model | 5 — untrained | 6 — this |
|---|---|---|---|---|
| Tables done | **33** | 31 | 0 | 4 |
| Tables wrong | **0** | 1 | 3 | 38 |
| Glasses racked | 195 | **202** | 55 | 77 |
| Glasses toppled | **0** | 1 | 4 | 46 |
| Pushes | 213 | **114** | 771 asks | 400 |

Solutions 1 and 4 are from their committed `results.json`. **Solution 5's
column is from its `partial.json`** — one run of the 50 tables, taken before
the bench capped a commanded path to the jaw's top speed — because its own
result was not committed when this was written. Treat it as the shape of the
untrained baseline and read solution 5's README for its number.

**The pair's answer is the uncomfortable one.** Fine-tuning plainly worked as
training: the chunk error against the teacher fell by three quarters, and the
model stopped waving the jaw in the air and started putting it on the table.
It also plainly made the score worse. Solution 5 keeps its tables out of the
*wrong* column by never touching a glass — it hovers, refuses almost
everything and is marked *correct but incomplete* — while this solution
touches glasses and knocks them over. So the honest reading of the gap between
the two is **not** "training bought nothing". It is that a thousand steps of
training bought enough competence to act and not enough to act safely, and on
a scorecard where a toppled glass is unrecoverable, that is worse than
inaction. Both halves of the pair are far below the geometry.

Two things would be worth trying before concluding anything about the method,
and both are named in the document. The first is simply more training: the
compute here was about one part in three hundred of what LeRobot's own SmolVLA
recipe spends, and the one thing the policy most needs to learn — where to put
the jaw down — is the thing it had least of. The second is **DAgger**, because
"the jaw comes down on a glass" is exactly a state the teacher never visits
and therefore exactly what the demonstrations cannot teach.
