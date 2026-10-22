# Solution 3 — imitation from demonstrations

The arm is shown a few thousand good pushes, and a network learns to copy
them. The table seen from straight above goes in. An **action chunk** comes
out: a short run of jaw waypoints, predicted together in one forward pass. The
bench carries it out as given. The policy has no friction model, no candidate
list and no geometry inside it.

The model is **ACT**, an action chunking transformer, from
[LeRobot](https://github.com/huggingface/lerobot). The second rung is
**Diffusion Policy**, also from LeRobot. Both are fitted here from random
numbers, vision backbone included. Only the library is downloaded.

Read [the document](../docs/solutions/03-imitation-from-demonstrations.md)
for why any of this. Read [the test
bench](../docs/the-examiner.md) first if you have not.

## Where the demonstrations come from

The teacher is [Solution 2](../02-geometry-ranked), unchanged. It runs on
training tables. For every push it makes, two things are kept: the
straight-down picture at the moment it decided, and `Record.waypoints`, the
path the jaw really followed. Nothing here invents a path. The teacher has to
be fitted first, so `make teacher` comes before `make collect`.

Only the pushes that worked are kept. That means nothing fell, nothing left the
glass zone, the jaw touched what it went for without jamming, and the table
gained room. Every drop is counted by its reason and by the kind of glass, in
`data/collection.json`. [The
document](../docs/solutions/03-imitation-from-demonstrations.md#choosing-which-demonstrations-to-keep-and-the-bias-it-buys)
explains why both the filter and the count are needed.

**5,200 training tables, 17,816 pushes, 6,659 kept** (19 minutes, 8 workers).
The table counts the dropped pushes by reason.

| Dropped | Pushes |
|---|---|
| a 5 mm test push, not a push at the task | 10,645 |
| a glass toppled | 278 |
| the table gained no room | 180 |
| a glass left the glass zone | 21 |
| blocked on the way down | 18 |
| jammed | 15 |

**The thinning is small in total, but very uneven across kinds of glass.** Most
drops are the teacher's own 5 mm test push, which is not a push at the task. Of
the 7,171 real pushes, 512 were dropped, which is 7%. The straight glass keeps
3,940 of its 7,131 pushes. The tapered glass keeps only 360 of its 1,656. The
teacher's refusals explain this: 3,057 of the tapered glass's 4,783 say "tips
before it slides". So the teacher rarely makes a real push on one. The
demonstration set is mostly straight glasses, and the policy sees the hardest
kind of glass the least.

A further **300 tables above the training band** give 399 demonstrations that
are never fitted on. The training diagnostic is measured against them.

## Where the code is

The table lists each file and what it does.

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

The bench, the tables, the physics and the scoring are in
[`../bench/`](../bench). Every solution shares them.

## Running it

`data/` and `weights/` are not in git. On a fresh checkout, run these in order:

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

A run that is not the full 50 held-out tables over more than one fitted seed
writes `partial.json`, never `results.json`. One seed has no spread, and the
spread is what makes it a result.

## Does it train on this machine?

**Yes, and nothing was rented.** ACT at LeRobot's default size is about 52
million parameters. The dataset is a few thousand pictures with a five-column
action. It fits on the graphics processor an Apple M4 already has. [The
document](../docs/solutions/03-imitation-from-demonstrations.md#what-it-needs)
compares this with renting.

Two things had to be true for it to fit in hours rather than overnight.

**The policy reads the picture at half the bench's size.** It reads 192 by 192
instead of 384, shrunk with an area filter inside `policy.py`. The vision
backbone is most of the cost of a step, and that cost falls with the area. So
this is roughly three times faster per step. One pixel then covers about 3.7 mm
of table, against the 1.9 mm the bench renders. That is still finer than
anything the policy has to resolve.

**It needs enough demonstrations, and they cost minutes, not money.** An early
fit used 3,144 demonstrations from 1,300 tables and 51 passes over them. It
drove the training loss to 0.04 and was useless. It was 11 mm from the
teacher's chunk on tables it had been fitted on, and 62 mm on tables it had
not. Four times as many tables removed most of that gap. Those two figures were
taken before the examiner had a real Robotiq 2F-85, so they are history. They
stay because the shape of that lesson changed the design. The fit below uses
6,659 demonstrations and 10,000 steps at batch 16, about 24 passes over them.

Every time quoted here was measured while other jobs ran on this machine. So
the minutes are an upper bound, not a benchmark.

## What the fitting cost, and what it bought

Three seeds, 10,000 steps each at batch 16, took between **54 and 78 minutes a
seed** on the M4's graphics processor. That is about three hours in all.
`weights/act-training.json` has every seed's loss curve.

`train.py` prints how far the fitted chunk is from the teacher's own chunk, per
waypoint. It does this on tables the fit saw and on tables it did not. **It is
not the score**; the score is the outcome, below. The table gives this distance
for the early fit and for the current one.

| Demonstrations | Passes over them | Fitted tables | Unseen tables |
|---|---|---|---|
| 3,144, with the old blade | 51 | 11 mm | 62 mm |
| 6,659, with the real hand | 24 | 20-21 mm | 48-52 mm |

The first row is memorising: near-perfect on what it saw, useless on what it
did not. Four times the tables closed most of that gap. But the error on unseen
tables fell by only about a fifth. The policy now predicts something close to
the average demonstration. More steps do not fix the first row, and more data
does not fix the second.

The heading shows this more sharply. On tables each seed was fitted on, its
chunk points within **3.5 to 3.9 degrees** of the teacher's heading. On tables
it never saw, it is **22 to 27 degrees** out. A push 25 degrees off does not
arrive late. It arrives somewhere else.

## Results — 50 held-out tables, 251 glasses, 3 fitted seeds

Every figure is the median across the three seeds, with the standard deviation
and the range, as `results.json` holds them. 203 of the 251 glasses have no
room at the start. The table puts ACT beside its teacher.

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

The three runs produced 1,349 chunks. Of those, **1,027 had at least one
waypoint outside what the jaw can reach**, and were pulled back inside it. The
shared gate in front of the policy refused 555 glasses before the policy was
asked, because they tip before they slide.

**The student falls a long way short of its teacher, and now that costs
glasses.** It clears 2 tables against the teacher's 14. It racks 63 glasses
against 107, and spends more than twice the pushes. It topples **12 glasses
where the teacher topples 1**, so 11 of its fifty tables are wrong. With the old
invented blade, this solution was clumsy but safe. The real hand is 266 mm long
behind its fingertips and 89 mm across at the wrist. So a chunk 25 degrees off
no longer misses harmlessly.

**It travels less than the floor**, at 0.87 times the least displacement any
legal arrangement of these tables needs. That is not efficiency. Three quarters
of its pushes stop on the way down, so few glasses move at all.

**The seeds disagree on the score but agree on the shape.** They clear 1 to 3
tables and topple 7 to 13 glasses. The seed that fitted closest to the teacher
is not the safest. A closer fit makes its pushes real. A real push on a crowded
table is the only thing here that can knock a glass over.

## The readings variant — the same fits, told where the glasses are

`measure_frames.py` showed that the descent point varies by 135.8 mm as a
position on the table, and by 7.5 mm in the push's own frame. So most of what
the policy must learn is the coordinate system. This variant tests the cheapest
repair. The policy still answers with absolute waypoints. The readings the
examiner already hands every solution go in beside the picture, as six slots of
six numbers through `readings.py`. The model grows by 38,400 numbers, less than
one part in a thousand. [The
document](../docs/solutions/03-imitation-from-demonstrations.md#telling-the-policy-where-the-glasses-are-and-what-it-changed)
explains the design and what the result means.

```
make collect                                   # the readings are recorded too
pixi run python train.py --readings --seeds 1 --first-seed 0   # and 1, and 2
pixi run python run.py --readings              # writes results-act-readings.json
```

Three seeds ran on the same 50 held-out tables. The table gives averages across
the three seeds.

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
the run-to-run variation, so the score did not move. The bad seed is gone, and
the spread on racked glasses halved, from 7.2 to 3.5. The aim improved by 6 mm,
but the blocked descents did not change. So the limit is the straight drop onto
the first waypoint, not the aim.

The picture-only numbers above remain this solution's result. This variant is
recorded beside them in `results-act-readings.json`, not in place of them.

## Why it scores that way

**Three quarters of its pushes end before a glass is touched.** On held-back
demonstrations, its waypoints sit 48 to 52 mm from the teacher's at the median.
At the worst tenth they sit 152 to 157 mm away. The heading is 22 to 27 degrees
out. With a hand 266 mm long and 89 mm across at the wrist, a heading that far
off puts the wrist over a neighbour. `follow()` then lowers the jaw to the
chunk's first waypoint and stops if it touches anything. That happens on 331 of
the 438 pushes. Each one is reported blocked, with nothing moved.

Solution 1's enumeration checks exactly this. For every candidate, it tests the
fingertip path, the finger segment and the wrist-and-body segment against every
other glass. **Nothing in a cloned policy does that check.** It sees only pushes
that happened to clear, never the ones the geometry rejected. "The absence of an
example is not a label" applies to jaw clearance as much as to
[refusals](../docs/solutions/03-imitation-from-demonstrations.md#when-a-glass-cannot-be-pushed-safely).

**Every glass left has a reason, but not every glass is left standing.** The
shared gate and the push budget write those reasons, not the policy. The gate
cannot make a blind push safe. 12 glasses go over, and each one ends its table,
so 11 of the fifty end *wrong*. With the invented blade, this same policy
toppled about one glass in three runs. The policy did not get worse; the hand
got real.

**It is cheap to run.** It thinks for 11 ms per push, which is one forward
pass. The teacher takes 102 ms to enumerate and rank candidates. That is the one
column where this solution beats solution 2. It is worth nothing on its own,
because here the arm is the bottleneck, not the program.

## What this measures

[The
document](../docs/solutions/03-imitation-from-demonstrations.md#where-it-sits-among-the-other-five)
says the pairing with the teacher shows whether a good push can be learned from
a picture. It also says that "a student far short says it is not". This
student falls well short. The reason is the one the document names in advance:
[mode averaging under a single-answer
loss](../docs/solutions/03-imitation-from-demonstrations.md#mode-averaging-under-a-single-answer-loss).
The teacher picks one push out of hundreds of legal candidates by an argmax.
That choice flips between glasses and headings under a small change in the
table. A network fitted to name one answer under an L1 loss returns something
between them.

Three things follow, and none of them is a tuning knob.

**More demonstrations will not close it on their own.** The fitting table above
shows this. Four times the data removed the memorising and left the error.

**The second rung is now the key experiment, not a spare.** Diffusion Policy
draws from a distribution over chunks, which is the one repair for averaging.
It is written in `policy.py` and it runs. It has not been fitted here, for the
cost reasons [the
document](../docs/solutions/03-imitation-from-demonstrations.md#the-second-way--diffusion-policy)
gives. `results-diffusion.json` is absent rather than guessed.

**The design gives the policy no way to say which glass it means.** One picture
goes in and one chunk comes out, with nothing naming the target. A policy told
the glass would be much easier to fit. But that is not what the document
describes. Changing the output contract would change what the comparison
measures.

## Known gaps

- **The denoising rung is not fitted**, as above.
- **There are three training seeds, and they disagree** by more than a little:
  1 to 3 tables cleared, 7 to 13 glasses toppled. Read every number here with
  its spread.
- **The crowded corner cases are not over-represented.** The document
  prescribes it. `collect.py` draws consecutive table numbers instead, so the
  set holds whatever mixture the bench produces.
- **DAgger is not built.** It would ask the teacher what it would do on the
  tables the policy itself walked into. It is the other cheap thing left
  undone, and it would attack the jaw-clearance failure directly. [The
  document](../docs/solutions/03-imitation-from-demonstrations.md#compounding-error)
  explains it.
- **Chunks are pulled inside the jaw's limits**, and the count is reported with
  the results. A network can emit a coordinate the jaw cannot reach, and on
  unfamiliar tables this one does.
- **`film.py` captions `push()` and knows nothing about `follow()`.** So for
  `make film`, `loop.py` sets the caption for a chunk itself.
- **The bench's chunk wants a glass and an aim that the policy does not
  produce.** `Chunk(glass, waypoints, aim)` carries both, because the scorecard
  counts pushes per glass and measures how far each glass ended from its aim.
  `chunks.aimed_at` reads them back off the finished chunk, outside the policy.
  It changes no motion.
- **The jaw's top speed is a cap this solution never meets.** A chunk's
  waypoint spacing is its speed, and the bench slows a leg that needs more than
  the jaw has. The teacher's legs are about 0.7 mm apart. The longest
  demonstration resampled into a chunk stays under 2 mm, against a cap at
  10 mm. A policy that learned coarser chunks would be slowed.
