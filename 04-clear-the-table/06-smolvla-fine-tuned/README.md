# Problem 4 — the borrowed model, fine-tuned on this problem's own demonstrations

`lerobot/smolvla_base`, the same weights the retired solution 5 ran untouched
(its page is kept in `docs/solutions/`, and its loop is now
`as_downloaded.py` in this folder), with a small correction
fitted here on the answers the ranked geometry gave on problem 4's tables. The
question it answers is what training on this cell buys a general model that has
already been asked the question cold.

This is [problem 3's solution 6](../../03-push-glasses-apart/06-smolvla-fine-tuned/)
brought to problem 4's contract. The model, the join between what it emits and
this cell's jaw, the correction's shape and the fitting recipe all come from
problem 3, through this problem's unchanged copy of those files in
[`../from-problem-3/`](../from-problem-3/README.md).

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
[`what-changed.md`](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/what-changed.md) records both
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

### Three times the steps, on three times the demonstrations — measured and not kept

The table above says the distance to the teacher barely moved, and the loss was
still falling when the fit stopped, so the plain question is whether this
correction was simply fitted for too short a time. Solution 3's larger
demonstration set — nine hundred tables instead of three hundred — was already
collected, so both were raised together: three thousand steps over twelve
thousand frames, which costs eighty minutes a seed instead of twenty-seven.

**The fit's own record separates the two changes**, because `train.py` measures
the distance to the teacher every five hundred steps, so a longer fit on a
larger set still reports its step-1,000 reading.

| median distance from the teacher | untrained | 1,000 steps, 4,000 frames | 1,000 steps, 12,000 frames | 3,000 steps, 12,000 frames |
|---|---|---|---|---|
| over all three kinds | 152 to 163 mm | 131 to 142 mm | 103 to 146 mm | **83 to 126 mm** |
| on the teacher's pushes | 82 to 97 mm | 78 to 86 mm | 76 to 108 mm | **57 to 91 mm** |

At the same thousand steps the larger set moved the all-kinds median from 134 mm
to 136 mm, and the push median the wrong way, both well inside a spread thirty
millimetres wide. The two thousand extra steps then closed another fifty
millimetres. **So the steps did the work and the larger set never showed.**

The pair was then walked again with the longer fit in place of the fitted side.
The untrained side is the same weights with no correction at all, so it is
unaffected by any of this, and it repeated its earlier walk exactly — which is
what makes the two fitted columns comparable.

| twenty tables, three walks | untrained | 1,000 steps, 4,000 frames | 3,000 steps, 12,000 frames |
|---|---|---|---|
| Tables separated | 0 | 0 (0 to 0) | 0 (0 to 1) |
| Glasses broken | 0 | 2 (1 to 3) | 2 (1 to 2) |
| Glasses it made pickable | 0 | +2 (0 to +3) | 0 (0 to +2) |
| Share of glasses pickable | 0.393 | 0.369 | 0.369 |
| Said done | 18 of 20 | 17 of 20 | 15 of 20 |
| Lowest point of a chunk | 150 mm | 112 mm | 91 mm |
| Travel across the table | 834 mm | 351 mm | 330 mm |
| Step between waypoints | 15.1 mm | 4.8 mm | 4.6 mm |
| Answers reaching the pushing height | 14% | 22% to 27% | 21% to 34% |

Everything about the *form* of the answers moved further towards the teacher,
and nothing about the state of the table moved with it. One of the three walks
separated a table, which no fit of this solution had managed before, and one
table in sixty is not a result.

**It was not kept.** Below the held-out line the two fits tie on every scored
count and the longer one costs three times the machine time, so the step count
stays at problem 3's thousand. The held-out queue agrees without being asked:
the longer fit scored 0.345 there against 0.405, and one of its three walks
broke three glasses. What the measurement adds to the record is the mechanism:
**what limits this solution is not how well the correction copies its teacher's
motion**, because the copy got better by half and the table did not change.

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
| Tables failed by a topple | 0 (0 to 0) | **2 (1 to 3)** |
| Glasses broken | 0 (0 to 0) | **2 (1 to 3)** |
| Glasses pickable at the end | 33, 0.393 (0.381 to 0.405) | **31, 0.369 (0.369 to 0.405)** |
| Of which it made pickable | 0 (−1 to +1) | **+2 (0 to +3)** |
| Said done | 18 of 20 (17 to 19) | **17 of 20 (15 to 17)** |
| Answers over the twenty tables | 353 (331 to 355) | **408 (365 to 409)** |
| Arm seconds over the twenty | 1,486 (1,433 to 1,532) | **1,312 (1,224 to 1,366)** |
| Thinking an answer | 0.281 s | **0.283 s** |

**Fitting buys work and it does not buy care.** That is the sharpest reading
this pair has ever supported, and it took two pieces of shared arithmetic to see
it. The fitted side frees two glasses to the untrained side's none; it also
topples two to the untrained side's none, and a forfeited table pays nothing at
either end, so its share comes out slightly *lower* than the model it started
from. A thousand steps over three hundred tables taught this model to go and act
on a glass. It did not teach it to act on a glass without sometimes putting it
over.

**Neither side separates a table.** That has not changed and it is the plainest
part of the result: a half-billion-number model given three hundred tables of
this cell's demonstrations does not clear a table in it.

**What the fit changed in the shape of the answers**, measured by the same code
on both sides, is where the training is visible:

| median over every answer, on these twenty tables | the same weights, nothing fitted | **fitted** |
|---|---|---|
| Lowest point of a chunk | 150 mm (147 to 153) | **112 mm (106 to 129)** |
| Travel across the table | 833 mm (810 to 841) | **351 mm (335 to 367)** |
| Step between waypoints | 15.1 mm (14.8 to 15.3) | **4.8 mm (4.5 to 5.2)** |
| Answers that reach the pushing height | 14% | **22% to 27%** |
| Shoves carried on until the glass had room | 0 to 3 a walk | **13 to 35 a walk** |
| Share of arm time on paths that could not touch a glass | 98% to 99% | **92% to 94%** |

Read the first three rows together and the fit is visible. The untrained model's
answer is one long fast arc of eight hundred millimetres straight across a glass
zone that is 320 by 360 mm, in steps of fifteen. The fitted model draws a path
less than half as long in steps a third as long, which is the length and the
speed of its teacher's own answers, and it comes down to the height a push works
at nearly twice as often. It ends up making five to ten times as many real
shoves at a glass — and the row above says what those shoves cost.

**So the fit taught the model the size of the motion and where to go, and not
what to be careful of.** Everything measurable about the *form* of the answers
moved towards the teacher, the amount of work done moved with it, and the number
on the card did not, because the work is paid for in glasses.

**What keeps the untrained side harmless is arithmetic and not the model.**
Between 319 and 346 of its answers are raised to travel height because the
solution cannot account for them as a push at one named glass. Before that
arithmetic existed, the same model on the same tables broke twenty-two glasses a
walk.

## What it achieves on the held-out queue

The measurement: fifty tables from table 10,000, in order, fifteen arm minutes
for the whole list, walked three times, one walk a fitted correction. Run once,
to `results.json`. The right-hand column is this solution's own first walk of the
same queue, before the even mixture and the clearance check.

| | walk 1 | walk 2 | walk 3 | median (least to most) | before |
|---|---|---|---|---|---|
| Tables attempted | 11 | 10 | 13 | **11 (10 to 13)** | 8 (2 to 8) |
| Glasses on them | 41 | 37 | 49 | | 29 |
| Tables separated | 0 | 0 | 0 | **0** | 0 |
| Tables failed by a topple | 0 | 0 | 1 | **0 (0 to 1)** | 6 (1 to 7) |
| Tables left unfinished | 11 | 10 | 12 | **11 (10 to 12)** | 1 (1 to 2) |
| Glasses pickable at the end | 17 of 41 | 15 of 37 | 17 of 49 | **0.405 (0.347 to 0.415)** | 0.103 |
| Glasses it made pickable | 0 | 0 | 0 | **0** | 0 |
| Glasses broken | 0 | 0 | 1 | **0 (0 to 1)** | 8 (1 to 10) |
| Said done at all | 9 | 9 | 11 | **9 (9 to 11)** | 0 |
| Said done while still crowded | 9 | 9 | 11 | **9 (9 to 11)** | 0 |
| Paths the interlock refused | 0 | 0 | 1 | **0 (0 to 1)** | 0 |
| Answers | 271 | 275 | 266 | **271 (266 to 275)** | 316 |
| Thinking an answer | 0.282 s | 0.282 s | 0.282 s | **0.282 s** | 0.279 s |

**It is a harmless solution now, where its first walk was the second most
destructive in the problem.** Eight broken glasses a walk became none in two
walks of three and one in the third, and the pickable share went from 0.103 to
0.405 without the model freeing a single glass. The share moved because a table
that loses a glass counts for nothing at either end, so a walk that keeps its
glasses standing is credited with the ones that arrived with room.

**It separates nothing and frees nothing, in all three walks.** The gain over
the glasses that already had room is exactly zero every time, which is the
plainest statement of the result: every glass that could be picked at the end of
a walk could already be picked at the start.

**It now says a table is finished, where before it never did.** Nine to eleven
of its ten to thirteen tables end with the stopping rule taking it at its word,
and every one of those declarations is made while the table is still crowded.
That is not the model learning anything about the table: it is sixteen answers
in a row that the clearance arithmetic raised to travel height, which the shared
rule rightly reads as a policy proposing nothing.

**The shape of its answers on these tables is the same shape as on the twenty
below the line**, which is what says the pair measurement generalises: the chunks
bottom out at about 110 to 130 mm, travel about 350 mm, step about 5 mm, and
between a fifth and a quarter of them reach the pushing height.

**Why the queue shows no freed glasses while the twenty building tables show
two.** On the twenty tables each table is given two arm minutes of its own, so
this solution gives seventeen to twenty-one answers on every one of them. The
queue gives fifteen arm minutes to all fifty, and this solution spends them on
ten to thirteen tables at about twenty-five answers each — but those tables are
walked in order from ten thousand, and the first of them happen to be tables
where its shoves find nothing. With a gain of +2 on one set and 0 on the other,
and three samples of each, the honest statement is that this solution frees
about nothing either way.

### Beside the other solutions, on the same queue

Solution 5 walks the same queue with the same loop and the same clearance check,
which is the comparison that matters: the training is the only difference.

| the held-out queue, 15 arm minutes | geometry reference | small fitted model | borrowed, nothing fitted | **borrowed, fitted here** |
|---|---|---|---|---|
| Tables attempted | 26 | 14 (9 to 36) | 11 | **11 (10 to 13)** |
| Tables separated | 10 | 0 (0 to 2) | 1 (0 to 1) | **0** |
| Tables failed by a topple | 0 | 1 | 0 | **0 (0 to 1)** |
| Glasses pickable at the end | 0.627 | 0.359 | 0.439 | **0.405** |
| Glasses it made pickable | +25 | −1 | +2 | **0** |
| Glasses broken | 0 | 1 | 0 | **0 (0 to 1)** |
| Said done while still crowded | 14 of 26 | 9 of 14 | 9 of 11 | **9 of 11** |
| Thinking an answer | 15 ms | 21 ms | 280 ms | **282 ms** |

**The fit is no longer a gain over the same weights untrained, and it is still a
clear loss against geometry.** Untrained, the borrowed model breaks nothing and
frees two glasses; fitted, it breaks almost nothing and frees none. The small
fitted model attempts more tables than either and separates two of them in one
of its three walks, which neither borrowed model manages, but it ends its queue
a glass down, so none of the three can be said to be doing the task. All three
are far behind a hundred lines of arithmetic that separates ten tables and
breaks none.

**The column that looks like an improvement over its untrained self is not
one.** A share of 0.405 against 0.439 is the wrong way round, and the two walks
are of different tables in any case. The comparison that holds is the pair above,
on one set of tables through one loop, and that says fitting buys work and not
care.

Two notes on reading that table. The geometry reference's walk records tables
10,000 to 10,025 with no gaps, so its 26 are 26 real attempts and the queue rule
that drops an untouched table would not change its number. And the two thinking
figures for the borrowed model are the same forward pass on the same machine
under the same load, so they are properly comparable: the correction is
multiplied into the weights, so both are a model of exactly the same size, and
both cost about nineteen times the geometry's compute an answer.

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
