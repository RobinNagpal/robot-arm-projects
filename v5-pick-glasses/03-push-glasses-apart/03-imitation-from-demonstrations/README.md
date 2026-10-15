# Solution 3 — imitation from demonstrations

The arm is shown what a good push looks like, a few thousand times, and a
network is trained to copy it. In goes the table seen from straight above. Out
comes an **action chunk**: a short run of jaw waypoints, predicted together in
one forward pass, which the bench carries out as given. No friction model, no
candidate list, no geometry inside the policy.

The model is **ACT**, an action chunking transformer, from
[LeRobot](https://github.com/huggingface/lerobot). The second rung is
**Diffusion Policy**, also from LeRobot. Nothing is downloaded but the
library: both are fitted here from random numbers, including the vision
backbone.

Read [the document](../../docs/03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md)
for why any of this. Read [the test
bench](../../docs/03-push-glasses-apart/the-examiner.md) first if you have not.

## Where the demonstrations come from

[Solution 2](../02-geometry-ranked), unchanged. It is run on training tables,
and for every push it makes two things are kept: the straight-down picture at
the moment it decided, and `Record.waypoints`, the path the jaw really
followed. Nothing here invents a path. The teacher has to be fitted first,
which is why `make teacher` comes before `make collect`.

Only the pushes that worked are kept — nothing fell, nothing left the glass
zone, the jaw touched what it went for and did not jam, and the table gained
room — because a cloned policy copies a bad label as readily as a good one.
Every drop is counted by its reason and by the kind of glass, in
`data/collection.json`, because filtering by outcome thins the data exactly on
the tables the teacher found hard.

**5,200 training tables, 17,816 pushes, 6,659 kept** (19 minutes, 8 workers).
What was dropped:

| Dropped | Pushes |
|---|---|
| a 5 mm test push, not a push at the task | 10,645 |
| a glass toppled | 278 |
| the table gained no room | 180 |
| a glass left the glass zone | 21 |
| blocked on the way down | 18 |
| jammed | 15 |

**The thinning the document warns about is still small in total, but it is very
uneven across the kinds of glass.** Most of what is dropped is the teacher's
own 5 mm test push, which is not a push at the task at all. Of the 7,171 real
pushes, 512 were dropped, which is 7%. The uneven part is which glass they came
from: the straight glass keeps 3,940 of its 7,131 pushes, while the tapered
glass keeps only 360 of its 1,656. The reason is in the teacher's own refusals,
where 3,057 of the tapered glass's 4,783 say "tips before it slides", so the
teacher rarely gets as far as making a real push on one. This means the
demonstration set is mostly straight glasses, and the policy therefore sees the
hardest kind of glass the least.

A further **300 tables above the training band** give 399 demonstrations that
are never fitted on. They are what the training diagnostic is measured against.

## Where the code is

| File | What it does |
|---|---|
| `teacher.py` | Loads solution 2, and solution 1's shared tipping limit |
| `collect.py` | Runs the teacher, keeps the pushes that worked, writes `data/` |
| `chunks.py` | A recorded path in, a chunk the bench will follow out. No model |
| `policy.py` | LeRobot's ACT and Diffusion Policy, and the scaling they see |
| `train.py` | Fits one rung, several seeds, into `weights/` |
| `loop.py` | Look, take what has room, gate, ask for a chunk, follow it |
| `run.py` | The held-out tables, scored with the bench's `Repeats` |
| `test_imitation.py` | The arithmetic, the shapes, the refusals and the interface |
| `measure_frames.py` | How much of the target is the coordinate system. Fits nothing |
| `readings.py` | One look into a fixed row of 36 numbers, for the readings variant |

The bench, the tables, the physics and the scoring are
[`../bench/`](../bench), shared with every other solution.

## Running it

`data/` and `weights/` are not in git. On a fresh checkout, in this order:

```
make teacher             # fit solution 2, which is the teacher    (seconds)
make collect             # run it on 5200 training tables         (19 minutes)
make train SEED=0        # fit one seed of ACT                     (about an hour)
make train SEED=1        # and the next, because one is not a measurement
make train SEED=2
make run                 # the 50 held-out tables; writes results.json
make test                # the quick checks: no fitted policy, no download
```

`make film FILM=3` writes videos of the first three held-out tables into
`videos/`. `make train RUNG=diffusion` and `make run RUNG=diffusion` are the
second rung.

Any run that is not the full 50 held-out tables over more than one fitted
seed writes `partial.json`, never `results.json`. One seed has no spread, and
the spread is what makes it a result.

## Does it train on this machine?

**Yes, and nothing was rented.** The document first budgeted a small rented
accelerator, of order tens of dollars. It was not needed. ACT at LeRobot's own
default size is about 52 million parameters and the dataset is a few thousand
pictures with a five-column action, which fits on the graphics processor an
Apple M4 already has.

Two things had to be true for it to fit in hours rather than overnight.

**The policy reads the picture at half the bench's size.** 192 by 192 rather
than 384, shrunk with an area filter inside `policy.py`. The vision backbone
is most of the cost of a step and that cost falls with the area, so this is
roughly three times faster per step. One pixel then covers about 3.7 mm of
table, against the 1.9 mm the bench renders, which is still finer than
anything the policy has to resolve.

**It needs enough demonstrations, which cost minutes rather than money.** An
early fit used 3,144 demonstrations from 1,300 tables and 51 passes over them.
It drove the training loss to 0.04 and was useless: 11 mm from the teacher's
chunk on tables it had been fitted on, 62 mm on tables it had not. Collecting
four times as many tables removed most of that gap. Those two figures were
taken before the examiner was given a real Robotiq 2F-85, so they are history
rather than a measurement of the fit below, and they are kept because it was
the shape of that lesson, rather than its exact millimetres, that changed the
design. The fit below is 6,659 demonstrations and 10,000 steps at batch 16,
which is about 24 passes over them.

Every figure quoted here was measured on this machine while several other jobs
were running on it, so the minutes are an upper bound rather than a benchmark.

## What the fitting cost, and what it bought

Three seeds, 10,000 steps each at batch 16, between **54 and 78 minutes a
seed** on the M4's graphics processor — so about three hours for the lot, which
is what the document meant by "hours". `weights/act-training.json` has every
seed's loss curve.

The diagnostic `train.py` prints is how far the fitted chunk is from the
teacher's own chunk, per waypoint, on tables the fit saw and on tables it did
not. **It is not the score** — the score is the outcome, below — but the two
numbers together say what is happening, and they changed the design once:

| Demonstrations | Passes over them | Fitted tables | Unseen tables |
|---|---|---|---|
| 3,144, with the old blade | 51 | 11 mm | 62 mm |
| 6,659, with the real hand | 24 | 20-21 mm | 48-52 mm |

The first row is memorising: near-perfect on what it saw, useless on what it
did not. Four times the tables closed most of that gap, and the error on unseen
tables came down by only about a fifth. The policy stopped memorising and started
predicting something close to the average demonstration instead. More steps do
not fix the first row and more data does not fix the second.

The heading tells the same story more sharply than the millimetres do. On
tables each seed was fitted on, its chunk points within **3.5 to 3.9 degrees**
of where the teacher pointed; on tables it never saw, it is **22 to 27 degrees**
out. A push that is 25 degrees off does not arrive late, it arrives somewhere
else, and that is what the results below are made of.

## Results — 50 held-out tables, 251 glasses, 3 fitted seeds

Every figure is the median across the three seeds, with the standard deviation
and the range, as `results.json` holds them. 203 of the 251 glasses have no
room at the start.

| | ACT | Teacher (solution 2) |
|---|---|---|
| Tables done | **2** +/- 1.0 (1 to 3) | 14 |
| Tables correct but incomplete | 36 +/- 3.8 (35 to 42) | 35 |
| Tables wrong | 11 +/- 3.1 (7 to 13) | 1 |
| Glasses racked | **63** +/- 7.2 (51 to 64) | 107 |
| Glasses refused, with a reason | 175 +/- 10.7 (174 to 193) | 143 |
| Glasses toppled | 12 +/- 3.2 (7 to 13) | 1 |
| Glasses pushed out of the zone | 0 +/- 0.6 (0 to 1) | 0 |
| Glasses left with no reason | 0 | 0 |
| Pushes spent | 438 +/- 43 (414 to 497) | 182 |
| Pushes blocked on the way down | 331 +/- 68 (323 to 445) | 0 |
| Pushes that never touched anything | 19 +/- 3.2 (18 to 24) | 0 |
| Pushes jammed | 4 +/- 2.5 (2 to 7) | 0 |
| Travel against the floor | 0.87x | 1.32x |
| Landed from its aim, median / worst | 41.4 / 211.8 mm | 1.6 / 32.8 mm |
| Thinking per push | **11 ms** | 102 ms |

Of the 1,349 chunks the three runs produced, **1,027 had at least one waypoint
outside what the jaw can reach** and were pulled back inside it. The shared gate
in front of the policy refused 555 glasses before the policy was reached at
all, because they tip before they slide.

**The student falls a long way short of its teacher**, and with the real hand it
now falls short in a way that costs glasses. It clears 2 tables against the
teacher's 14 and racks 63 glasses against 107, and it spends more than twice the
pushes doing it. The important change is the bottom of the table: it topples
**12 glasses where the teacher topples 1**, which makes 11 of its fifty tables
wrong. Under the invented blade this solution was clumsy but safe; the real hand
turns the same clumsiness into broken glass, because the hand is now 266 mm long
behind its fingertips and 89 mm across at the wrist, so a chunk that is 25
degrees off no longer misses harmlessly.

**It is also now travelling less than the floor**, at 0.87 times the least
displacement any legal arrangement of these fifty tables needs. That is not
efficiency. It is the signature of a solution that mostly does not move
anything: three quarters of its pushes are stopped on the way down, so the
glasses that do move are the few it reached.

**The seeds disagree about the score but agree about the shape.** The three sit
between 1 and 3 tables cleared and between 7 and 13 glasses toppled, and the
seed that fitted closest to the teacher per waypoint is not the safest one. A
closer fit does not make this solution safer, because it makes its pushes real,
and a real push on a crowded table is the only thing here that can knock a
glass over.

## The readings variant — the same fits, told where the glasses are

`measure_frames.py` showed that the descent point varies by 135.8 mm written as
a position on the table and by 7.5 mm written in the push's own frame, so most of
what the policy must learn is the coordinate system. The variant tests the
cheapest repair for that: the policy keeps answering with absolute waypoints, and
the readings the examiner already hands every solution go in beside the picture,
as six slots of six numbers through `readings.py`. The model grows by 38,400
numbers, which is less than one part in a thousand.

```
make collect                                   # the readings are recorded too
pixi run python train.py --readings --seeds 1 --first-seed 0   # and 1, and 2
pixi run python run.py --readings              # writes results-act-readings.json
```

Three seeds, the same 50 held-out tables. Averages across the three seeds:

| | from the picture alone | with the readings |
|---|---|---|
| Glasses racked | 59.3 | 61.3 |
| The three seeds separately | 64, 51, 63 | 61, 65, 58 |
| Tables done | 2.0 (1 to 3) | **3.0 (3 every run)** |
| Glasses toppled | 10.7 | 10.3 |
| Landed from its aim, median | 43.9 mm | 37.7 mm |
| Travel a run | 2,245 mm | 1,824 mm |
| Pushes blocked on the way down | 366.3 | 370.3 |
| Against the teacher, tables it saw | 20.4 to 20.7 mm | 17.2 to 19.3 mm |
| Against the teacher, tables it did not | 48.1 to 52.4 mm | 48.3 to 52.9 mm |

**The readings bought consistency, not glasses.** Two glasses of 251 is 0.4 of
the run-to-run variation, so the score did not move. What moved is the spread:
the bad seed is gone, all three now sit between 58 and 65 racked, and every run
clears exactly 3 tables where before one seed managed 1. The spread on racked
glasses halved, from 7.2 to 3.5.

**The aim improved and the score did not, which locates the real limit.** The
policy lands 6 mm closer to its teacher's target and travels a third less, so it
used the readings; and the blocked descents did not budge. The binding
constraint is the straight drop onto the chunk's first waypoint, not the aim,
because what stops the jaw is usually not at the target but on the way to it.

The picture-only numbers above remain this solution's result. This variant is
recorded beside it in `results-act-readings.json`, not in place of it.

## Why it scores that way

**Three quarters of its pushes end before a glass is touched.** The policy's
chunk lands in roughly the right neighbourhood, but no closer than that:
measured over held-back demonstrations its waypoints sit 48 to 52 mm from the
teacher's own at the median, and 152 to 157 mm at the worst tenth, with the
heading 22 to 27 degrees out. The hand reaches 266 mm back behind its
fingertips and is 89 mm across at the wrist, so on a crowded table a heading
that far off puts that wrist over a neighbour. After that, `follow()` brings
the jaw down to the chunk's first waypoint and stops if it touches anything on
the way, which it does on 331 of the 438 pushes, and the push is reported
blocked with nothing moved.

Solution 1's enumeration checks exactly this: for every candidate it tests the
fingertip path, the finger segment and the wrist-and-body segment against every
other glass. **Nothing in a cloned policy reproduces that check.** It sees
only pushes that happened to clear, never the ones the geometry rejected, and
"the absence of an example is not a label" applies to jaw clearance as much as
to refusals.

**It leaves no glass unexplained, but it no longer leaves them standing.**
Every glass that is not racked has a reason written against it, which is the
shared gate and the push budget doing their work rather than the policy doing
its. What the gate cannot do is make a blind push safe: 12 glasses go over, and
each one stops its table, which is why 11 of the fifty end *wrong*. Under the
invented blade this same policy toppled about one glass in three runs. The
policy did not get worse; the hand got real, and a 266 mm hand swung 25 degrees
off centre hits things that a thin blade passed beside.

**It is cheap to run.** 11 ms of thinking per push, which is one forward pass,
against the teacher's 102 ms of enumerating and ranking candidates. That is
the one column where this solution beats solution 2, and it is worth nothing
on its own: distilling a program into a policy for speed only pays when the
program is the bottleneck, and here the arm is.

## What this measures

[The document](../../docs/03-push-glasses-apart/solutions/03-imitation-from-demonstrations.md)
says the pairing of this solution with its teacher is a reading of whether the
mapping from a picture of a crowded table to a good push is learnable, and that
"a student that falls well short says the opposite". This student falls well
short, and the reason is the one the document names in advance under **mode
averaging under a single-answer loss**: the teacher picks one push out of
hundreds of legal candidates by an argmax, which flips between glasses and
headings under a small change in the table, and a network fitted to name one
answer under an L1 loss returns something between them.

Three things follow, and none of them is a tuning knob.

**More demonstrations will not close it on their own.** That is what the table
above shows: four times the data removed the memorising and left the error.

**The second rung is now the interesting experiment, not a spare.** Diffusion
Policy represents a distribution over chunks and draws from it, which is the
one repair for averaging. It is written in `policy.py` and it runs; it has not
been fitted here, because it is about twice ACT's cost per training step and
sixteen denoising passes per push, and several seeds of it is a night's work on
top of ACT's. `results-diffusion.json` is absent rather than guessed.

**The design as specified gives the policy no way to say which glass it means.**
One picture goes in and one chunk comes out, with nothing naming the target.
A policy conditioned on the glass would be a much easier thing to fit — but it
is not what the document describes, and changing the output contract would
change what the comparison measures.

## Known gaps

- **The denoising rung is not fitted**, as above.
- **Three training seeds**, and they disagree by more than a little: 1 to 3
  tables cleared, 7 to 13 glasses toppled. Every number above carries its
  spread, and nothing here should be read without it.
- **The crowded corner cases are not over-represented.** The document
  prescribes it; `collect.py` draws consecutive table numbers instead, so the
  demonstration set holds whatever mixture the bench produces.
- **DAgger is not implemented.** The document's repair for compounding error —
  asking the teacher what it would have done on the tables the policy itself
  walked into — is the other cheap thing left undone, and it would attack the
  jaw-clearance failure directly.
- **Chunks are pulled inside the jaw's limits**, and the count is reported with
  the results rather than hidden. A network can emit a coordinate the jaw
  cannot reach, and on unfamiliar tables this one does.
- **`film.py` captions `push()` and knows nothing about `follow()`**, so
  `make film` labels a chunk through `loop.py` setting the caption itself.
- **The bench's chunk wants a glass and an aim that the policy does not
  produce.** `Chunk(glass, waypoints, aim)` carries both because the scorecard
  counts pushes per glass and measures how far each glass ended from its aim.
  `chunks.aimed_at` reads them back off the finished chunk, outside the policy.
  It changes no motion, but it means this solution's output is not literally
  the whole answer, which the document says it is.
- **The jaw's top speed is a cap this solution never meets.** A chunk's
  waypoint spacing is its speed, and the bench slows a leg that would need
  more than the jaw has. The teacher's legs are about 0.7 mm apart and the
  longest demonstration resampled into a chunk stays under 2 mm, against a cap
  at 10 mm, so nothing here is slowed by it. A policy that learned to emit
  coarser chunks would be.
