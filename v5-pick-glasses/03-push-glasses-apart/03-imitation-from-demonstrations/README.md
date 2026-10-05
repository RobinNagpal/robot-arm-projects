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
bench](../../docs/03-push-glasses-apart/the-bench.md) first if you have not.

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

**5,200 training tables, 22,846 pushes, 12,656 kept** (14 minutes, 8 workers).
What was dropped:

| Dropped | Pushes |
|---|---|
| a 5 mm test push, not a push at the task | 9,783 |
| the table gained no room | 263 |
| a glass toppled | 125 |
| a glass left the glass zone | 18 |
| blocked on the way down | 1 |

**The thinning the document warns about is small here, and that is worth
saying.** Almost everything dropped is the teacher's own 5 mm test push, which
is not a push at the task at all. Of the 13,063 real pushes, 407 were dropped —
3%. The teacher is clean enough on these tables that filtering by outcome
barely biases which tables are covered. The per-kind share does vary: the
tapered glass keeps 2,622 of 5,619 pushes against the straight glass's 3,582 of
5,998, because tapered glasses need more test pushes.

A further **300 tables above the training band** give 728 demonstrations that
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

The bench, the tables, the physics and the scoring are
[`../bench/`](../bench), shared with every other solution.

## Running it

`data/` and `weights/` are not in git. On a fresh checkout, in this order:

```
make teacher             # fit solution 2, which is the teacher    (seconds)
make collect             # run it on 5200 training tables         (14 minutes)
make train SEED=0        # fit one seed of ACT                     (55 minutes)
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
roughly three times faster per step. One pixel is then 1.6 mm on the table,
which is far finer than anything the policy has to resolve.

**It needs enough demonstrations, which cost minutes rather than money.** The
first fit used 3,144 demonstrations from 1,300 tables and 51 passes over them.
It drove the training loss to 0.04 and was useless: 11 mm from the teacher's
chunk on tables it had been fitted on, 62 mm on tables it had not. Collecting
four times as many took another 14 minutes of arm time and removed that gap
entirely. The fit below is 12,656 demonstrations and 10,000 steps at batch 16,
about 13 passes over them.

Every figure quoted here was measured on this machine while several other jobs
were running on it, so the minutes are an upper bound rather than a benchmark.

## What the fitting cost, and what it bought

Three seeds, 10,000 steps each at batch 16, about **55 minutes a seed** on the
M4's graphics processor — so under three hours for the lot, which is what the
document meant by "hours". `weights/act-training.json` has every seed's loss
curve.

The diagnostic `train.py` prints is how far the fitted chunk is from the
teacher's own chunk, per waypoint, on tables the fit saw and on tables it did
not. **It is not the score** — the score is the outcome, below — but the two
numbers together say what is happening, and they changed the design once:

| Demonstrations | Passes over them | Fitted tables | Unseen tables |
|---|---|---|---|
| 3,144 | 51 | 11 mm | 62 mm |
| 12,656 | 13 | 53-64 mm | 55-64 mm |

The first row is memorising: near-perfect on what it saw, useless on what it
did not. Four times the demonstrations closed that gap — and the error on
unseen tables barely moved. The policy stopped memorising and started
predicting something close to the average demonstration instead. More steps do
not fix the first row and more data does not fix the second.

## Results — 50 held-out tables, 251 glasses, 3 fitted seeds

Every figure is the median across the three seeds, with the standard deviation
and the range, as `results.json` holds them. 193 of the 251 glasses have no
room at the start.

| | ACT | Teacher (solution 2) |
|---|---|---|
| Tables done | **3** +/- 1.7 (3 to 6) | 31 |
| Tables correct but incomplete | 46 +/- 4.4 (39 to 47) | 19 |
| Tables wrong | 1 +/- 2.6 (0 to 5) | 0 |
| Glasses racked | **68** +/- 8.4 (67 to 82) | 185 |
| Glasses refused, with a reason | 182 +/- 11.6 (163 to 184) | 66 |
| Glasses toppled | 1 +/- 2.6 (0 to 5) | 0 |
| Glasses left with no reason | 0 | 0 |
| Pushes spent | 643 +/- 40 (589 to 668) | 229 |
| Pushes blocked on the way down | 569 +/- 67 (492 to 625) | 0 |
| Pushes that never touched anything | 38 +/- 7 (27 to 41) | 0 |
| Pushes jammed | 0 | 0 |
| Landed from its aim, median / worst | 44.9 / 113.7 mm | 1.0 / 3.9 mm |
| Thinking per push | **11 ms** | 101 ms |

Of the 1,900 chunks the three runs produced, **814 had at least one waypoint
outside what the jaw can reach** and were pulled back inside it.

**The student falls a long way short of its teacher**: 3 tables cleared against
31, and 68 glasses racked against 185. It spends nearly three times the
teacher's pushes to do it, because almost every push achieves nothing and the
budget runs out.

**The seeds disagree about more than the score.** Seed 2 fitted closest to the
teacher (37 mm against 53 and 64 per waypoint) and it both racked the most
glasses — 82 — and toppled the most, 5, making 5 tables wrong. The other two
toppled one between them. A closer fit does not make this solution safer; it
makes its pushes real, and a real push on a crowded table is the only thing
here that can knock a glass over.

## Why it scores that way

**Almost every push ends before a glass is touched.** The policy's starting
point lands in roughly the right neighbourhood — within a centimetre or two of
where the teacher put the fingertips — but its heading is around 30 degrees
out. The jaw is 270 mm long behind its fingertips and its body is 90 mm wide,
so on a crowded table a heading that far off puts that body over a neighbour.
`follow()` brings the jaw down to the chunk's first waypoint and stops if it
touches anything on the way, which it does, and the push is reported blocked
with nothing moved.

Solution 1's enumeration checks exactly this: for every candidate it tests the
fingertip path, the finger segment and the wrist-and-body segment against every
other glass. **Nothing in a cloned policy reproduces that check.** It sees
only pushes that happened to clear, never the ones the geometry rejected, and
"the absence of an example is not a label" applies to jaw clearance as much as
to refusals.

**It topples almost nothing and leaves no glass unexplained.** Every table ends
*correct but incomplete* or, once in three runs, wrong. The shared gate in
front of the policy refuses the glasses that tip before they slide, and the
budget accounts for the rest, so the counts the problem calls wrong stay near
zero. That is the gate working, not the policy.

**It is cheap to run.** 11 ms of thinking per push, which is one forward pass,
against the teacher's 101 ms of enumerating and ranking candidates. That is
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
- **Three training seeds**, and they disagree by more than a little: 3 to 6
  tables cleared, 0 to 5 glasses toppled. Every number above carries its
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
