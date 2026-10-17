# Problem 4 — the borrowed model, fine-tuned on this problem's own demonstrations

`lerobot/smolvla_base`, the same weights [solution
5](../05-smolvla-as-it-downloads/) runs untouched, with a small correction
fitted here on the answers the ranked geometry gave on problem 4's tables. The
question it answers is what training on this cell buys a general model that has
already been asked the question cold.

This is [problem 3's solution 6](../../03-push-glasses-apart/06-smolvla-fine-tuned/)
brought to problem 4's contract. The model, the join between what it emits and
this cell's jaw, the correction's shape and the fitting recipe are all
**imported, not copied**.

## What came out

**The first fit learned the looking and not the pushing.** Four of the teacher's
answers in five move the arm only to see, and a fit drawn from that mixture
spends four fifths of itself on the kind of answer that changes nothing: its
chunks carried the jaw high, swept shorter and slower, and only one answer in
fifty came down far enough to move a glass. On the held-out queue that left no
table separated, no glass freed, and a glass broken on three tables in four. The
fit bought safety and not competence.

**Two things were changed after that, and neither is a different model.** Each
batch is now drawn evenly from the looks and the pushes, so that the material's
own four-to-one mixture cannot drown the answers that matter; and every answer
goes through the clearance check that solution 5 runs, which raises a path that
cannot be shown to reach only the glass it names.

**What those two bought is safety and reach, and no competence at all.** On the
held-out queue the broken glasses fell from eight a walk to one, the pickable
share rose from 0.103 to 0.378, and the solution now says a table is finished
instead of being stopped by a falling glass. It still separates no table and
frees no glass. The pair this folder exists to measure — the same weights with
and without this cell's demonstrations — says the same thing from the other
side: fitting makes the model act a third again as often and leaves the outcome
exactly where it was.
[`what-changed.md`](../../docs/04-clear-the-table/what-changed.md) records both
changes beside the measurements that justified them.

## What is borrowed and what is new

| | |
|---|---|
| `joining.py` in problem 3's solution 5 | **borrowed, unchanged.** How six of somebody else's joint readings become jaw waypoints, and how the jaw's pose becomes the model's state. |
| `policy.py` in problem 3's solution 5 | **borrowed, unchanged.** Loading the weights and asking them. |
| `as_downloaded.py` in problem 4's solution 5 | **borrowed, unchanged.** The model sat in problem 4's conversation. `fine_tuned.py` subclasses it, so the loop, the stopping rule and the accounting are one piece of code for both halves of the pair. |
| `correction.py` in problem 3's solution 6 | **borrowed, unchanged.** Where the correction goes — rank 16, scaling 32, on attention's four projections — and how the corrected model is loaded. |
| `train.py` in problem 3's solution 6 | **borrowed in part.** The step count, the batch, the rate and its warm-up, the pre-processing of a batch, and the distance from the teacher in millimetres. Its loop is not used, because this one fits three seeds and reads problem 4's demonstrations. |
| `chunks.py` in problem 3's solution 6 | **borrowed in part.** Cutting a recorded push down to its flat part, resampling, and the round-trip check that a target is one the model can express. |
| `loading.py`, `chunks.py`, `readings.py` in problem 4's solution 3 | **borrowed, unchanged.** Where the demonstrations are and what one holds. The two fitted solutions read one set through one reader. |
| `bench/stopping.py` | **borrowed.** How a trained policy says it has finished. Its count is taken as it comes; this folder sets no number of its own. |
| `bench/keeping_clear.py` | **borrowed, through solution 5.** The clearance check a solution runs over its own answer. It is inherited rather than called here, which keeps the pair one piece of code. |
| `borrowed.py` | **new.** Loads all nine of those under the plain names they import each other by. Nothing is put on `sys.path`. |
| `targets.py` | **new.** One stored demonstration, read as something the borrowed model can be fitted towards. The only new thinking about the data. |
| `train.py`, `run.py` | **new.** Three fits, and the two measurements. |

**Nothing is put on the import path, which is deliberate.** Problem 3 has
modules called `scoring`, `clock` and `partners` too, and problem 4's own have
to win. Every borrowed file is loaded from its own path and registered under the
name its siblings import it by.

## What the correction is fitted towards

The demonstrations are the ones in [`../demonstrations`](../demonstrations/),
collected once by solution 3's collector and read by both fitted solutions:
**11,016 answers of the ranked geometry on 300 tables numbered 1000 to 1299**,
with 1,850 more from tables 8000 to 8049 held back. Of the 11,016, **8,965 are
the teacher driving the arm somewhere it can see from** and 2,051 are pushes.
Four answers in five are looks, because the camera is on the arm.

The borrowed model takes six numbers for its state and emits fifty rows of six.
Problem 4 stores an answer as two hundred rows of its own convention. Three
things happen in between, and none of them invents a path.

**The glasses leave the state.** The model's state is six joint readings, so the
only thing in a `Look` that fits is where the jaw is standing. The glasses the
camera caught stay in the picture, which is where the model is expected to read
them. Problem 4's own students take those readings as numbers beside the
picture; this one cannot, and that is a property of the borrowed model.

**The descent leaves the path.** Every demonstrated push starts at travel height
and comes straight down over its first 23 waypoints before it drives anywhere.
`follow()` does that drop itself, so a chunk that asked for it would ask for the
drop twice.

**The path is padded, and squeezed only when it will not fit.** A chunk is fifty
rows and most paths are shorter, so the path keeps the teacher's own spacing and
its last pose is repeated to the end. That matters because the bench eats
waypoints at a fixed rate, so how far apart they are *is* how fast the jaw goes.
Measured over the fitting set, **1,824 of the 2,051 pushes fit in fifty rows**,
and the 227 that do not are resampled into them, which asks for the teacher's
own path at a median of 1.64 times its speed and 3.34 at the worst. A look is
the same shape held still: its pose, repeated, which the bench follows as one
waypoint and charges as the crossing alone.

**The reading is exact, and that was measured rather than assumed.** Every one
of the 12,866 demonstrations in the two sets was read into the model's
convention and decoded back: the worst error is 0.0000 mm and 0.0000 degrees,
and no waypoint had to be pulled inside the jaw's limits. Every jaw pose in the
sets is inside the frame the convention maps onto, which is why nothing is
clipped.

## What the fit cost

Three seeds, each a separate fit of the same correction on the same
demonstrations. `weights/training.json` holds all of it.

| | |
|---|---|
| steps, batch, learning rate | 1,000, 4, 1e-4 — problem 3's own, imported |
| numbers that move | 3.81M of 453.9M |
| time a seed | 26.5 minutes each on this laptop's Metal GPU |
| memory held | 1.02 to 1.05 GiB |
| loss | 0.86 to 0.96 at step 50, down to 0.26 to 0.28 at the end |
| demonstrations read a seed | 4,000 of the 11,016, drawn evenly from the looks and the pushes, of which about 5% were squeezed |

**One thousand steps at a batch of four is a third of one pass over this set.**
Problem 3 chose that recipe on a set of 1,074 demonstrations, where it was
nearly four passes, and finally fitted on a set of 6,935, where it was three
fifths of one. The step count is held at problem 3's on purpose, so that the two
problems' fits cost the same and can be compared; the consequence is that this
correction has seen a third of its material once. It is also, as problem 3 says
of its own, about one part in three hundred of the compute LeRobot's own SmolVLA
fine-tune asks for.

**The distance to the teacher barely moved, and the spread says why that is hard
to read.** The check decodes the model's chunk into jaw waypoints and measures
the distance from the teacher's own, on sixteen demonstrations of each kind from
tables the fit never saw. Before the first step the correction is zero, so the
model is exactly solution 5 — and because the answer is drawn from fresh noise,
the three seeds' step-zero readings of that one model are the noise floor:

| median distance from the teacher's waypoints | untrained | after 1,000 steps |
|---|---|---|
| over all three kinds | 152 to 163 mm | 131 to 142 mm |
| on the teacher's looks | 185 to 204 mm | 198 to 212 mm |
| on the teacher's pushes | 82 to 97 mm | 78 to 86 mm |

The loss fell threefold, so the correction learned something about the
distribution it was shown. The decoded distance moved much less: taken over all
three kinds it closed by about twenty millimetres, on the pushes it closed by
about eight, and on the looks it did not close at all. Sixteen chunks a kind is a
small sample and the answer is drawn from fresh noise, so this is a weak
instrument; what it is strong enough to say is that the fit did not move the
model's waypoints towards its teacher's by anything like the margin problem 3
saw, where the same measurement fell from about 300 mm to about 100 mm.

## How it says it is done

Problem 4 asks every solution to declare a table finished, and that is a
sentence a policy cannot utter. `bench/stopping.py` is the shared answer — a run
of answers that could not touch a glass is taken as the policy saying it sees
nothing to do — and this solution uses its count as it comes, which is sixteen.

That count matters here and could not matter for solution 5. A fitted model has
learned its teacher's habit of driving the arm about to see, so it goes quiet for
a spell and then acts. The count was compared on eight tables below the held-out
line, with one correction and every table given 120 arm seconds of its own:

| eight tables, 36 glasses | 3 quiet answers | 12 | 16 |
|---|---|---|---|
| Tables separated | 0 | 0 | **1** |
| Glasses broken | 3 | 4 | 3 |
| Glasses pickable at the end | 8 (0.222) | 7 (0.194) | **9 (0.25)** |
| Of which it made pickable | −2 | −3 | **0** |
| Said done | 2 | 1 | 0 |
| Paths carried out | 251 | 251 | 307 |

Sixteen is the best column of the three on every count that is scored, so the
bench's own number is the one used and nothing here overrides it.

**That comparison was made before the even mixture and the clearance check**, so
its numbers describe a solution that no longer exists: with the clearance check
in front of it, this solution breaks about one glass a walk rather than three on
eight tables. It is kept because it is the record of how the count was chosen,
and because the choice still stands — a fitted model copies its teacher's habit
of driving about to see, so it needs a long quiet spell before anyone may call it
finished.

## What the fit changed — the same tables, the same loop, one difference

Twenty tables below the held-out line, each given 120 arm seconds of its own,
walked three times: the fitted side by the three corrections, the untouched side
by the same weights with nothing fitted. Both sides run through this folder's own
loop under the same stopping count, and both run the same clearance check over
their answers, so the training is the only difference between the columns. Each
cell is the median of the three walks with the least and the most beside it.

| twenty tables, 84 glasses | the same weights, nothing fitted | **fitted here** |
|---|---|---|
| Tables separated | 0 | **0** |
| Tables failed by a topple | 1 (0 to 3) | **2 (1 to 4)** |
| Glasses broken | 1 (0 to 3) | **2 (1 to 5)** |
| Glasses pickable at the end | 31, 0.369 (0.321 to 0.393) | **31, 0.369 (0.345 to 0.381)** |
| Of which it made pickable | 0 (−1 to 0) | **0 (0 to +1)** |
| Said done | 17 of 20 (16 to 18) | **13 of 20 (11 to 16)** |
| Answers over the twenty tables | 335 (328 to 359) | **438 (410 to 486)** |
| Arm seconds over the twenty | 1,416 (1,397 to 1,556) | **1,468 (1,311 to 1,661)** |
| Paths the interlock refused | 0 (0 to 1) | **0 (0 to 1)** |
| Thinking an answer | 0.281 s | **0.283 s** |

**This is a null result, and it is the honest headline of this folder.** The two
columns separate the same number of tables, which is none; they free the same
number of glasses, which is none; and they end with the same pickable share to
three decimal places. The fitted side breaks one more glass than the untrained
side, which is inside the spread of either. A thousand steps of this cell's
demonstrations did not make the borrowed model better at this cell's task.

**What the fit did change is how much the model acts.** The fitted side gives a
third again as many answers — 438 against 335 — because it stops declaring the
table finished so early: thirteen of its twenty tables end with the stopping
rule taking it at its word, against seventeen on the untrained side. More
answers at the same outcome is the measurement of a model that has learned to
keep working at a table it cannot clear.

**And the fit did change the shape of the answers, towards the teacher's.** This
is the one place where training shows clearly, measured by the same code on both
sides:

| median over every answer, on these twenty tables | the same weights, nothing fitted | **fitted** |
|---|---|---|
| Lowest point of a chunk | 150 mm (143 to 152) | **115 mm (114 to 128)** |
| Travel across the table | 832 mm (816 to 850) | **360 mm (337 to 370)** |
| Step between waypoints | 15.0 mm (14.8 to 15.3) | **4.9 mm (4.7 to 5.2)** |
| Answers that reach the pushing height | 13% to 16% | **20% to 26%** |
| Shoves carried on until the glass had room | 5 to 7 a walk | **27 to 48 a walk** |
| Share of arm time on paths that could not touch a glass | 96% to 98% | **89% to 91%** |

Read the first three rows together and the fit is visible. The untrained model
sweeps eight hundred millimetres across a table whose glass zone is 320 by
360 mm, in steps of fifteen millimetres, which is one long fast arc over
everything. The fitted model draws a path less than half as long in steps a
third as long, which is the size and the speed of the teacher's own answers, and
it comes down to the height a push works at twice as often. It also ends up
making five to nine times as many real shoves at a glass.

**So the fit taught the model the size of the motion and not the place to put
it.** That is the sharpest statement this pair supports: everything measurable
about the *form* of the answers moved towards the teacher, and nothing
measurable about the *result* moved at all. A path of the right length and speed
that comes down next to no glass in particular changes nothing on the table, and
the clearance arithmetic is what keeps it from changing something for the worse:
315 to 343 of the fitted side's answers are raised to travel height because they
cannot account for themselves.

**Problem 3's finding turns up again here.** A policy that barely reaches a
glass scores the same as one that reaches the wrong part of it, because both
leave the table as they found it, and the second one occasionally breaks
something on the way.

## What it achieves on the held-out queue

The measurement: fifty tables from table 10,000, in order, fifteen arm minutes
for the whole list, walked three times, one walk a fitted correction. Run once,
to `results.json`. The right-hand column is this solution's own first walk of the
same queue, before the even mixture and the clearance check.

| | walk 1 | walk 2 | walk 3 | median (least to most) | before |
|---|---|---|---|---|---|
| Tables attempted | 16 | 10 | 10 | **10 (10 to 16)** | 8 (2 to 8) |
| Glasses on them | 61 | 37 | 37 | | 29 |
| Tables separated | 0 | 0 | 0 | **0** | 0 |
| Tables failed by a topple | 2 | 0 | 1 | **1 (0 to 2)** | 6 (1 to 7) |
| Tables left unfinished | 14 | 10 | 9 | **10 (9 to 14)** | 1 (1 to 2) |
| Glasses pickable at the end | 19 of 61 | 15 of 37 | 14 of 37 | **0.378 (0.311 to 0.405)** | 0.103 |
| Glasses it made pickable | 0 | 0 | 0 | **0** | 0 |
| Glasses broken | 2 | 0 | 1 | **1 (0 to 2)** | 8 (1 to 10) |
| Said done at all | 13 | 9 | 8 | **9 (8 to 13)** | 0 |
| Said done while still crowded | 13 | 9 | 8 | **9 (8 to 13)** | 0 |
| Paths the interlock refused | 0 | 0 | 0 | **0** | 0 |
| Answers | 271 | 277 | 267 | **271 (267 to 277)** | 316 |
| Thinking an answer | 0.281 s | 0.281 s | 0.282 s | **0.281 s** | 0.279 s |

**It is now a harmless solution rather than a destructive one.** Seven of the
eight glasses it used to break on a walk are no longer broken, and the pickable
share nearly quadrupled — from 0.103 to 0.378 — without the model freeing a
single glass. The share moved because a table that loses a glass counts for
nothing at either end, so a walk that keeps its glasses standing is credited
with the ones that arrived with room.

**It separates nothing and frees nothing, in all three walks.** The gain over
the glasses that already had room is exactly zero every time, which is the
plainest statement of the result: every glass that could be picked at the end of
a walk could already be picked at the start.

**It now says a table is finished, where before it never did.** Eight to
thirteen of its ten to sixteen tables end with the stopping rule taking it at
its word, and every one of those declarations is made while the table is still
crowded. That is not the gate learning anything about the table: it is sixteen
answers in a row that the clearance check raised to travel height, which the
shared rule rightly reads as a policy proposing nothing.

**The shape of its answers on these tables is the same shape as on the twenty
below the line**, which is what says the pair measurement generalises: the
chunks bottom out at 110 to 168 mm, travel 322 to 357 mm, step 4.4 to 4.9 mm,
and 15% to 26% of them reach the pushing height. Between 180 and 245 answers a
walk are raised, most often because the path comes down without reaching the
glass it is nearest to.

**The spread between the three corrections is still wider than any effect in
the table.** One walk reached sixteen tables and two reached ten, from the same
recipe, the same data and the same number of steps. Nothing in this folder's
result should be read at a finer resolution than that.

### Beside the other solutions, on the same queue

Solution 5 walks the same queue with the same loop and the same clearance check,
which is the comparison that matters: the training is the only difference.

| the held-out queue, 15 arm minutes | geometry reference | small fitted model | borrowed, nothing fitted | **borrowed, fitted here** |
|---|---|---|---|---|
| Tables attempted | 26 | 13 (12 to 16) | 11 | **10 (10 to 16)** |
| Tables separated | 10 | 1 (0 to 1) | 0 (0 to 1) | **0** |
| Tables failed by a topple | 0 | 2 (2 to 5) | 0 | **1 (0 to 2)** |
| Glasses pickable at the end | 0.627 | 0.377 | 0.400 | **0.378** |
| Glasses it made pickable | +25 | +3 | 0 (0 to +2) | **0** |
| Glasses broken | 0 | 2 (2 to 5) | 0 | **1 (0 to 2)** |
| Said done while still crowded | 14 of 26 | 9 of 13 | 9 of 11 | **9 of 10** |
| Thinking an answer | 15 ms | 19 ms | 279 ms | **281 ms** |

**The fit is no longer a gain over the same weights untrained, and it is still a
clear loss against geometry.** Untrained, the borrowed model breaks nothing and
frees nothing in two walks of three; fitted, it breaks about one glass a walk
and frees nothing in any walk. Both
are beaten by the small fitted model, which at least frees three glasses, and
all three are far behind a hundred lines of arithmetic that separates ten tables
and breaks none.

The one row where the fit still looks like an improvement over its untrained
self is the one this page has to warn about. It is not there. Both borrowed
columns now score their share almost entirely on glasses that arrived with room,
and the fitted column's extra tenth of a point is noise beside a spread of 0.311
to 0.405.

Two notes on reading that table. The geometry reference's walk records tables
10,000 to 10,025 with no gaps, so its 26 are 26 real attempts and the queue rule
that drops an untouched table would not change its number. And the two thinking
figures for the borrowed model are the same forward pass on the same machine
under the same load, so they are properly comparable now: the correction is
multiplied into the weights, so both are a model of exactly the same size, and
both cost about twenty times the geometry's compute an answer.

## Running it

```
pixi run python -u 06-smolvla-fine-tuned/train.py --seeds 3
pixi run python -u 06-smolvla-fine-tuned/run.py
pixi run pytest -q 06-smolvla-fine-tuned
```

`make train`, `make measure` and `make test` are the same three, and `make
selection` and `make pair` are the runs below the held-out line. The first run
downloads about 2 GB of weights and then reads them from the cache. The whole
measurement is six minutes of laptop time; the pair below the line is half an
hour, because nothing there stops early.

`run.py` writes the held-out result to `results.json` only when the whole
arrangement matches — fifty tables from ten thousand, three walks, fifteen arm
minutes — and anything shorter goes to `partial.json` beside it, so a run made
while building cannot overwrite the measurement.

What each file in here holds:

| | |
|---|---|
| `results.json`, `results-tables.json` | the measurement: the held-out queue, walked three times, and every table in it |
| `asking.json` | what the solution asked for on that walk: the shape of its answers and its own split of the arm time |
| `pair-fitted.json`, `pair-untrained.json` | the two halves of the pair on the twenty tables below the line, with their own `-tables` and `-asking` files |
| `selection-quiet-3.json`, `-12`, `-16` | the stopping count compared on eight tables below the line |
| `weights/training.json` | what the three fits did, step by step. The corrections themselves are left out of git and made again by `train.py` |

No test here loads a model or a correction: a test that needs two gigabytes off
the internet is not a test, and what is worth testing is the two joins either
side of the weights.
