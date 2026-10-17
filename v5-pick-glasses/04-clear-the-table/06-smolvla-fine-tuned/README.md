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
cannot be shown to reach only the glass it names. What those two bought is
measured below and in
[`what-changed.md`](../../docs/04-clear-the-table/what-changed.md).

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
| time a seed | 26.4, 26.4 and 27.1 minutes on this laptop's Metal GPU |
| memory held | 1.02 to 1.05 GiB |
| loss | 0.67 at step 50 to 0.21 to 0.23 at the end |
| demonstrations read a seed | 4,000 of the 11,016, of which about 2% were squeezed |

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
| over all three kinds | 152 to 163 mm | 110 to 148 mm |
| on the teacher's looks | 185 to 204 mm | 181 to 222 mm |
| on the teacher's pushes | 82 to 97 mm | 84 to 116 mm |

The loss fell threefold, so the correction learned something about the
distribution it was shown. The decoded distance did not follow it: the bands
overlap in every row, and on looks and pushes taken apart the fitted model is no
closer to the teacher than the untrained one. Sixteen chunks a kind is a small
sample and the answer is drawn, so this is a weak instrument; what it is strong
enough to say is that the fit did not move the model's waypoints towards its
teacher's by anything like the margin problem 3 saw, where the same measurement
fell from about 300 mm to about 100 mm.

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

## What the fit changed — the same tables, the same loop, one difference

Twenty tables below the held-out line, each given 120 arm seconds of its own,
walked three times: the fitted side by the three corrections, the untouched side
by the same weights with nothing fitted. Both sides run through this folder's own
loop under the same stopping count, so the training is the only difference
between the columns. Each cell is the median of the three walks with the least
and the most beside it.

| twenty tables, 84 glasses | the same weights, nothing fitted | **fitted here** |
|---|---|---|
| Tables separated | 0 | **1 (0 to 2)** |
| Tables failed by a topple | 18 (17 to 19) | **9 (5 to 9)** |
| Glasses broken | 22 (22 to 25) | **9 (7 to 9)** |
| Glasses pickable at the end | 1, 0.012 (0.012 to 0.036) | **21, 0.25 (0.226 to 0.31)** |
| Of which it made pickable | −1 (−4 to −1) | **+1 (0 to +2)** |
| Said done | 0 of 20 | **0 of 20 (0 to 2)** |
| Answers over the twenty tables | 2,308 (2,195 to 3,782) | **749 (745 to 765)** |
| Arm seconds over the twenty | 795 (770 to 862) | **1,871 (1,805 to 2,090)** |
| Paths the interlock refused | 1,688 (1,432 to 3,325) | **65 (52 to 68)** |
| Thinking an answer | 0.280 s | **0.334 s** |

**The training made the model markedly less destructive.** It halves the tables
lost to a topple, halves the glasses broken, and takes the share of glasses with
room at the end from one in a hundred to one in four. It also stops the model
battering at paths the cell will not carry out: 65 refusals a walk against
1,688.

**That is not the same as saying the fit is good, and solution 5's own published
numbers show why.** Measured on these same twenty tables, solution 5 reports one
table separated, two glasses broken and 39% of glasses pickable — better than
anything in the table above. It reached that by stopping after three answers and
handing the table back very nearly as it found it, 66 answers against 749. Two
things about those numbers are not comparable with these, and both have to be
said: the stopping count was three rather than sixteen, and the rule it was
measured under asked only whether a path came down to the height the jaw pushes
at, where the rule now asks whether the hand would sweep a glass standing taller
than that. Under today's rule the same weights never go quiet at all, which is
the left-hand column above. The comparison that holds is the held-out queue
below: solution 5 walked it with the count at three and this solution with it at
sixteen, and **neither said it was done on a single table**, so the count never
bound on either and what separates the two columns there is the training.

Either way, problem 3's finding turns up again in problem 4's numbers: **a
policy that barely reaches a glass scores better than one that reaches the wrong
part of it.**

**What the fit actually taught the model is where to hold the jaw.** The shape
of the answers says it plainly, measured by the same code on both sides:

| median over every answer, on these twenty tables | the same weights, nothing fitted | **fitted** |
|---|---|---|
| Lowest point of a chunk | 128 mm (124 to 143) | **233 mm (231 to 250)** |
| Travel across the table | 442 mm (424 to 490) | **301 mm (295 to 316)** |
| Step between waypoints | 7.8 mm (7.4 to 8.6) | **4.1 mm (3.9 to 4.6)** |
| Answers that reach the pushing height | 0.6% | **2.0%** |
| Share of arm time on paths that could not touch a glass | 0.1% | **25%** |

The fitted model carries the jaw **higher**, sweeps **shorter**, and moves
**slower** — which is what four demonstrations in five look like, because four
in five are the teacher going somewhere to see. That is the fit working: the
teacher's commonest answer is "stand over there at travel height", and the
student learned it. It is also why the fit cannot separate a table: it learned
the looking and not the pushing, and one answer in fifty comes down far enough
to move a glass at all. The held-out walks give the same three numbers to within
their spread — 240 mm, 302 mm and 4.2 mm — so this is the shape of its answers
and not a property of these twenty tables.

**It still breaks nine glasses a run while every one of those answers is
recorded as quiet.** The height a path names is the middle of the jaw and the
hand reaches 69.5 mm below it, so a path at 233 mm puts the hand's lower edge at
163 mm, and glasses on these tables stand 97 to 224 mm tall. A sweep 300 mm long
at that height drags the hand through the top of every tall glass it passes.
Solution 5 reported this fault in `bench/stopping.py`'s stated reason, and this
solution is the clearest case of it: a quarter of its arm time is spent on paths
the rule counts as "proposing nothing", and those paths are what put the glasses
on the floor.

## What it achieves on the held-out queue

The measurement: fifty tables from table 10,000, in order, fifteen arm minutes
for the whole list, walked three times, one walk a fitted correction. Run once,
to `results.json`.

| | walk 1, correction 0 | walk 2, correction 1 | walk 3, correction 2 | median (least to most) |
|---|---|---|---|---|
| Tables attempted | 8 | 2 | 8 | **8 (2 to 8)** |
| Glasses on them | 29 | 8 | 29 | |
| Tables separated | 0 | 0 | 0 | **0** |
| Tables failed by a topple | 6 | 1 | 7 | **6 (1 to 7)** |
| Tables left unfinished | 2 | 1 | 1 | **1 (1 to 2)** |
| Glasses pickable at the end | 3 of 29 | 2 of 8 | 2 of 29 | **0.103 (0.069 to 0.25)** |
| Glasses it made pickable | 0 | 0 | 0 | **0** |
| Glasses broken | 8 | 1 | 10 | **8 (1 to 10)** |
| Said done while still crowded | 0 | 0 | 0 | **0** |
| Said done at all | 0 | 0 | 0 | **0** |
| Paths the interlock refused | 0 | 0 | 0 | **0** |
| Answers | 321 | 302 | 316 | **316 (302 to 321)** |
| Thinking an answer | 0.278 s | 0.279 s | 0.281 s | **0.279 s (0.278 to 0.281)** |

**It separates nothing and frees nothing.** The gain over the glasses that
already had room is exactly zero in all three walks, which is the plainest
statement of the result: every glass that could be picked at the end of a walk
could already be picked at the start. What the arm did in fifteen minutes was
break one glass in four of the ones it reached.

**The pickable share of 0.25 in walk 2 is not a better walk.** That walk reached
two tables before the clock stopped it, so its share is 2 glasses of 8 on two
tables, where the other walks' are out of 29 on eight. The three walks are
comparable on the tables they all reached, which is two, and on nothing beyond
that. **Reading the spread as 0.069 to 0.25 would be reading the denominator.**

**It never says it is done.** Not once in eighteen tables, so the whole budget
goes on whatever table the arm is standing at when the clock stops. That is why
it reaches 2 to 8 tables of 50 where the geometry reference reaches 26: it makes
about 40 answers and spends 110 arm seconds a table, against the reference's 37
answers and 43 seconds, and it never stops. One walk spent 834 of its 900 arm
seconds on the first table alone, over 283 answers.

**"Tables attempted" and "how far down the list it got" are not the same number
here, and `results-tables.json` is where that shows.** Walk 1 acted on tables
10,000 to 10,006, which left two and a half arm seconds in the budget — enough
for no path this solution writes. The runner drops a table the arm never moved
on and carries on, so the walk went through the next 39 tables without acting on
any of them, and then found one short enough answer on table 10,046 to be
charged 2.7 seconds and counted. So that walk's eighth table is a scrap of one
answer, and the list it reached the end of is nearly the whole fifty. The
dropped tables are rightly not counted — every glass on them would otherwise be
a glass left crowded — but a reader comparing throughput should take 7 real
tables and not 8.

**The spread between the three corrections is wider than any effect in the
table.** One correction reached two tables and another eight, from the same
recipe, the same data and the same number of steps — a fourfold difference in
throughput for no reason but the training seed. Nothing in this folder's result
should be read at a finer resolution than that.

### Beside the other solutions, on the same queue

Solution 5 has since been walked over the same queue, which is the comparison
that matters: the same weights, the same loop and the same fifty tables, with
the training as the difference. Neither said it was done on any table, so the
stopping count never bound on either walk.

| the held-out queue, 15 arm minutes | geometry reference | small fitted model | borrowed, nothing fitted | **borrowed, fitted here** |
|---|---|---|---|---|
| Tables attempted | 26 | 10 (1 to 11) | 15 (13 to 15) | **8 (2 to 8)** |
| Tables separated | 10 | 0 | 0 | **0** |
| Tables failed by a topple | 0 | 0 | 14 (12 to 14) | **6 (1 to 7)** |
| Glasses pickable at the end | 0.627 | 0.400 | 0.018 | **0.103** |
| Glasses it made pickable | +25 | 0 | −1 | **0** |
| Glasses broken | 0 | 0 | 20 (19 to 22) | **8 (1 to 10)** |
| Said done while still crowded | 14 of 26 | 9 of 10 | 0 | **0** |
| Thinking an answer | 15 ms | 16 ms | 776 ms | **279 ms** |

**The fit is a clear gain over the same weights untrained and a clear loss
against geometry.** It halves the broken glasses and takes the pickable share
from one in fifty to one in ten, and it still breaks a glass on three tables in
four while a hundred lines of arithmetic separates ten tables and breaks
nothing.

Two notes on reading that table. The geometry reference's walk records tables
10,000 to 10,025 with no gaps, so its 26 are 26 real attempts and the queue rule
that now drops an untouched table would not change its number. And the two
thinking figures for the borrowed model are the same forward pass measured under
different machine load — solution 5's walk ran while the graphics chip was also
fitting another model, and this one did not — so the honest reading is that the
borrowed model costs twenty to fifty times the geometry's compute an answer, not
that the fitted one is faster than the untrained one. The correction is
multiplied into the weights, so both are a model of exactly the same size.

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
