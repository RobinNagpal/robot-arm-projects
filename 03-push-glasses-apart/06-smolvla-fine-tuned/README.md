# Solution 6 — the same foundation model, fine-tuned here

SmolVLA, the 450-million-parameter robot model that [solution
5](../05-smolvla-as-it-downloads) uses as it downloads, with its training
continued on pushes made on this bench. The training is a **low-rank
correction**. Every borrowed number stays where it is. A small correction is
learned beside them and then folded in. So the model keeps its size and speed.

The two solutions are a matched pair. Only the training differs, so the gap
between their scores is what the training bought.

Full explanation: [the
document](../docs/solutions/06-smolvla-fine-tuned.md).

## What is here

The table lists each file and its job.

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
feel and look again, are imported from solution 5. A second copy would be a
second thing that could differ between the pair. `Fitted` is solution 5's
`Downloaded` with the correction loaded on top. Only the twelve lines that
fetch the weights and build the processors are written again here. The
training needs the model before the correction is attached.

## Running it

```
make demonstrations   # the teacher over 5200 training tables (about 70 minutes)
make tuning           # the same on 300 tuning tables, which say when to stop
make train            # fits the correction (downloads the weights once)
make run              # the 50 held-out tables, 3 evaluation runs
make test
```

Any run shorter than the full held-out set writes `partial.json`, never
`results.json`. `make train SEED=1 INTO=correction-1` fits a second training
seed. `run.py --correction correction --correction correction-1` scores both,
which is what [the examiner](../docs/the-examiner.md)
asks for.

## What it costs

**It trains on this machine.** It held **1.02 GiB of the Mac's unified
memory**, measured while it ran. A low-rank fine-tune of π0 needs 22 GB. [The
document](../docs/solutions/06-smolvla-fine-tuned.md#low-rank-adaptation--a-small-correction-instead-of-a-large-change)
says why. Time is the limit, not memory. The 1,000 steps took 47 minutes on
Metal, about 3 seconds a step, on a laptop shared with other training runs.
An NVIDIA card would take a fraction of a second. So the committed correction
is 1,000 steps at a batch of 4. LeRobot's own SmolVLA recipe is twenty
thousand steps at a batch of sixty-four. That caveat applies to every number
here.

Renting would cost of order tens of dollars for hours of a small accelerator,
a hundred for a weekend, and five hundred for a month. Nothing here was
rented.

At run time it is one large forward pass per chunk on this laptop. That is
solution 5's cost, because the correction is folded into the weights.

## The demonstrations

**The band changed after the main result was measured.** The committed
`results.json` was fitted on 800 tables starting at table 0. The band is now
5,200 tables starting at table 1,000, matching [solution
3](../03-imitation-from-demonstrations/README.md). That also keeps out the
teacher's own fitting tables, 0 to 199. [The
document](../docs/solutions/06-smolvla-fine-tuned.md#where-the-demonstrations-come-from-and-what-they-cost)
gives the reasons. The new band's result is
[its own section below](#the-same-fitting-on-solution-3s-tables).

The old band: 800 training tables, 19 minutes of simulator time, **1,074
demonstrations from 430 of those tables**. On the other 370 the teacher found
nothing it could push with the real hand. With the invented blade it found
something on all but 60. The teacher made 2,766 pushes. 1,663 were 5 mm test
pushes for the shared tipping check. Of the 1,103 real pushes, **29 were
discarded**: 13 toppled a glass, 12 jammed, 3 pushed one out of the zone and 1
was blocked coming down. That is 2.6 per cent. `demonstrations/collected.json`
records it all.

**The new band gave six and a half times as much**: **6,935 demonstrations
from 2,796 of 5,200 tables**. The teacher refused 46 per cent of tables on
either band. So the new band is the old one scaled up, not easier ground.

A chunk covers 78 mm of table in 49 waypoint periods, 1.6 mm a waypoint.

## Three things to know before reading the numbers

**The student pushes faster than its teacher.** A chunk holds 50 waypoints.
The teacher's push is two or three times that many. Resampling it makes the
student's jaw travel about 32 mm/s, where the teacher felt forward at 10 and
pushed at 20.

**One training seed, not several.** The examiner asks for several. Only one was
fitted here, so the spread in `results.json` covers evaluation runs only.

**The compute column was re-measured.** `seconds_per_push` is wall time
without the bench's own share. So a busy machine inflates it. Timed while
training runs shared the laptop, it read 0.82 s. Timed on an idle machine, it
read 283 ms, and solution 5 read 283 ms too. That matches the method: the
folded correction adds no arithmetic. The committed `results.json` reads
404 ms.

## What the training moved

`correction/training.json` holds the whole curve. The table gives the distance
between the model's waypoints and the teacher's, on tuning tables nothing was
fitted on.

| Step | Fitting loss | Tuning error, median | Worst |
|---|---|---|---|
| 0 — the correction is zero, so this is solution 5 | — | **331 mm** | 574 mm |
| 500 | 0.291 | 107 mm | 283 mm |
| 1000 | 0.150 | **85 mm** | 255 mm |

The glass zone is 320 mm by 360 mm. So the untrained answer is a motion
somewhere else on the table. Five hundred steps cut the error by two thirds.
The next five hundred took another fifth off.

**Training stopped at 1,000 steps because that was the budget.** This fit's
error was still falling. But the three fits on the new band ended at 101.5,
106.1 and 90.0 mm, against 92.6, 115.3 and 77.0 mm at step 500. The error rose
in two and fell in one. So between 500 and 1,000 steps the curve is flat
within its noise. Each tuning figure comes from a handful of drawn chunks, so
twenty millimetres is near the noise. More steps would still very likely
help. Read the results below as what a thousand steps buys.

**The chunks changed shape.** Each solution's `asking.json` records what its
answers looked like. The table compares the medians.

| | Solution 5, untrained | This solution | The teacher |
|---|---|---|---|
| Lowest the chunk reaches above the table | 217 mm | **75 mm** | 75 mm |
| Distance across the table in one chunk | 868 mm | 320 mm | 78 mm |
| Per waypoint, which is the speed | 14.6 mm | 4.6 mm | 1.6 mm |

The first row is what the training bought: the jaw now comes down to the push
height. The other rows are what it did not buy. Its pushes are still about four
times too long and three times too fast. The toppled count below is the price.

## Results — 50 held-out tables, 251 glasses, 203 without room at the start

These come from the correction fitted on the 800-table band. Three evaluation
runs of one training seed. `results.json` holds every run. The table gives the
middle value with the spread across the three.

| | |
|---|---|
| Tables | 1 done, 14 not finished, **36 wrong** |
| Glasses | 56 racked (±7.6), 138 refused (±1.0), **40 toppled** (±5.6), 15 pushed out of the zone (±4.4) |
| Glasses picked without room, or left with no reason | **0** and **0** |
| Pushes | 369 (±12), of which 260 repeats |
| Pushes that went wrong, in the middle run | **223 blocked on the way down**, 66 jammed, 33 never touched, of 369 |
| Travel | 5,518 mm, which is 1.68 times the displacement floor |
| Where the glass stopped, from where the chunk ended | 57.3 mm median, 784 mm worst |
| Thinking per push | 404 ms (±16) on an idle machine |

**This is a bad score, for one reason.** 223 of the 369 pushes in the middle
run were **blocked on the way down**: the jaw came down onto a glass. That
share is from one run. The spread gives a median per field, and those come
from different runs, such as 227 blocked from another run. The model learned
the push height and did not learn where to put the jaw down. That causes 40
glasses over, 36 tables wrong, and 66 refusals that read "stopped: a glass
fell over".

**The real gripper changed this solution least of the four learned ones.**
With the invented blade it toppled about 46 glasses a run and ended 38 tables
wrong. Now it is 40 and 36. Its failure never depended on the hand: a jaw that
comes down on a glass hits it either way. The refit did learn the new height,
75 mm where the earlier fit reached 50.

**The geometry did its job.** No glass was picked without room, and none was
left without a reason, on every run.

### The same fitting on solution 3's tables

The whole fitting was done again on the new band. The first try ran over the
old tables at the new size, so there are three measurements. That accidental
column is a control: it separates *how much* the student learns from *where*.
The table reads left to right from the old band to the matched one.

| | 800 tables from 0 | 5,200 tables from 0 | 5,200 tables from 1,000 |
|---|---|---|---|
| Demonstrations | 1,074 | 6,907 | **6,935** |
| Teacher's own tables inside the band | 200 of 800 | 200 of 5,200 | **none** |
| Glasses racked | 56 (±7.6) | 52 (±3.8) | 53 (±2.1) |
| Glasses refused | 138 (±1.0) | 145 (±0.6) | 137 (±4.5) |
| Glasses toppled | 40 (±5.6) | 40 (±3.6) | 42 (±3.6) |
| Tables wrong | 36 (±2.9) | 36 (±2.9) | 36 (±1.5) |
| Pushes blocked on the way down | 227 (±8.9) | 217 (±32) | 229 (±45) |
| Chunk error on tuning tables at the end | 85 mm | 98 mm | 99 mm |

**Six and a half times the data changed nothing measurable.** Between the
first and last columns, in standard errors of the difference: racked glasses
move by 0.7, toppled by 1.0, tables wrong by 1.1 and blocked descents by 0.1.
None reaches two. The last two columns come from three training seeds with one
evaluation run each. [The
document's "Was it the data?"](../docs/solutions/06-smolvla-fine-tuned.md#was-it-the-data)
reads these columns in full.

On the wrong band, refusals rose from 138 to 145, ten standard errors. On the
matched band they read 137. So that effect came from particular tables and
fits. That run's `seconds_per_push` of 1.07 s against 0.39 s is also an
artefact: it shared the graphics chip with a fit.

### Against the other solutions that have run

The table puts this solution beside three others. The full comparison is in
[the results](../results/README.md).

| | 1 — fixed nudge | 4 — world model | 5 — untrained | 6 — this |
|---|---|---|---|---|
| Tables done | 14 | **20** | 1 | 1 |
| Tables wrong | **1** | 19 | 9 | 36 |
| Glasses racked | 107 | **146** | 48 | 56 |
| Glasses toppled | **1** | 20 | 12 | 40 |
| Pushes | **173** | 221 | 620 | 369 |

Every column is from that solution's own committed `results.json`. For 5 and
6, which run several times, each figure is the median over runs.

**Training worked, and the score got worse.** The chunk error against the
teacher fell by three quarters. The jaw now reaches the table. But solution 5
stays out of the *wrong* column by never touching a glass, while this solution
knocks glasses over. So a thousand steps bought enough skill to act, but not
enough to act safely. Both are far below the geometry.

Two things are worth trying next. One is more training: the compute here was
about one part in three hundred of LeRobot's own recipe. The other is
**DAgger**, because "the jaw comes down on a glass" is a state the teacher
never visits, so the demonstrations cannot teach it.
