# Imitation from demonstrations

Problem 4 by copying the ranked geometry. **Two models are fitted here from
random numbers on [the demonstrations](../demonstrations)**, and each has one
job. The **gate** is shown what problem 4 shows every solution and says which of
four kinds of answer to give — go and look, probe a glass, push a glass, or say
the table is finished — and which glass to give it at. The **policy** is then
shown the same thing plus that decision, and draws the path.

**Why two and not one.** The first version of this solution was one model doing
both, and it freed no glasses at all on the held-out queue. Four of every five
answers the teacher gives are a move to see from somewhere else, and fitting
minimises the distance to the teacher's answer, so wherever the picture did not
say which kind of answer was wanted the model produced something between the
two — and something between a look and a push is a look. Splitting the decision
out of the drawing is the change that makes the pushing learnable at all, and
`gate.py` argues it in full.

Nothing is downloaded. The policy is
[LeRobot](https://github.com/huggingface/lerobot)'s ACT, which is Apache-2.0,
and its vision backbone starts from random numbers rather than from ImageNet,
because a downloaded backbone would make "fitted from nothing" untrue. The gate
is four convolutions and two linear heads, written in this folder.

## What is new here, and what is borrowed

Almost all of this is borrowed, and `wiring.py` is the one page the debt to
problem 3 is on.

**[`../demonstrations`](../demonstrations)** holds the two sets themselves, in a
folder of their own because solution 6 is fitted on the same demonstrations and
neither solution owns them. The conventions that define them are here —
`chunks.py` for the action, `readings.py` for the observation, `loading.py` for
where the sets are and how one is read back — and `collect.py` is what made
them.

**Problem 3's [solution 3](../../03-push-glasses-apart/03-imitation-from-demonstrations)**
is the wiring: the ACT configuration, the normalisation, the one class a fitted
model is asked through, the fitting loop with its learning rate and its warm-up,
and the size a picture is read at. None of it is written again here. The two
problems exist to be compared, so if the model or the fitting loop were rewritten
a difference between them could be the wiring rather than the problem.

**`bench/stopping.py`** is how a policy with no words for it says it has
finished, and it is now the *backstop* rather than the rule. The teacher's own
declarations are in the demonstrations — `collect.py` records the answer it never
had to carry out — so the gate is fitted on them and a table ends when the gate
says it is finished. The quiet rule is still consulted, because a gate that never
said "done" would otherwise spend a whole queue's budget on one table, and the
two reasons are counted apart in a run's record.

**`bench/keeping_clear.py`** is the arithmetic this solution runs over its own
answer before handing it over. A look has to ride at travel height and a push has
to reach only the glass the gate named, at the height a push works at; anything
else is raised to travel height, where it goes to the same place and touches
nothing. It is the same check solutions 5 and 6 run, and the reason all three run
it is measured: most of the glasses this problem broke were broken by a hand
travelling at the height of the glasses' rims, not by a push aimed badly.

The check is given **every glass this solution has measured on the table**, which
`Measured` in the same file keeps, and not the glasses in the current picture.
The camera rides on the arm, so one picture is part of the table, and the part
left out is where a shove can drive its glass into a neighbour nobody is looking
at — the hand is never near the glass that breaks, so nothing about the hand can
catch it. The geometry solutions have had a belief about the whole table since
problem 4 began, in `01-one-fixed-nudge/remembered.py`; this is the same idea in
its simplest form, and the models are still shown only what the camera caught.

What is left is `gate.py`, which is the new model and its fitting, `clear.py`,
which wraps the two models to problem 4's contract, `train.py`, which fits the
gate and points the borrowed fitting loop at this problem's data, and `run.py`,
which measures.

## Two things this problem asks of a chunk that problem 3 did not

**A path has to be able to be a look.** Problem 3's student only ever pushed, so
every chunk it emitted was the same length. Here the teacher's answers are one
waypoint when it drives somewhere to see and 39 to 190 when it comes down and
shoves, and four in five are the first kind. So a chunk holds a path's own
waypoints at their own spacing, padded out with the last one repeated, and a
sixth column says where the path ends: one while it is still going, zero after.

That column is worth being clear about. It is **not** a channel for "this table
is finished" — `stopping.py` explains why that would be a different experiment,
and nothing in the demonstrations says when a table is done. It says how long
*this path* is, which every demonstration labels.

Padding rather than resampling also fixes something problem 3 had to live with.
Problem 3 squeezed each push into a chunk's worth of waypoints, which made the
student push faster than its teacher, because in this cell how far apart the
waypoints are *is* how fast the jaw goes. Here a kept path reaches the bench
with the spacing the teacher wrote, so the student pushes at the teacher's speed.
It also keeps the corner at the bottom of the descent sharp: resampling a path
that drops straight down and then drives straight forward rounds that corner
off, and a jaw that cuts it is a jaw moving sideways while it is still coming
down, which is how a glass gets clipped.

**The jaw's pose has to go in.** Problem 3's camera is bolted above the table and
its jaw is parked in the same place between pushes, so its solution 3 passed a
state of width zero and lost nothing. Here the camera rides on the arm, so the
same table seen from two stands is two different pictures and nothing in a
picture says which stand it was taken from. Without the pose the model cannot
place what it sees on the table, and cannot write a path in the table's own
numbers. So the state is the jaw's pose and the readings of the glasses the
picture caught — the same three things `Look` carries.

## Saying it is done

**The gate says it, and it was fitted on the teacher saying it.** Problem 4's
teacher answers a table it considers finished with a statement rather than a
path, and the collector now records that answer: the last picture, the readings,
and "done" as the kind. So "the table needs nothing more" is one of the four
things the gate chooses between, learned from 297 examples of the teacher
choosing it, and a table ends when the gate chooses it.

That is a change from the first version of this solution, and the reason is on
its card. With no way to say it, the solution relied entirely on the shared quiet
rule — and declared nine of its ten tables finished while they were still
crowded, because the only thing the rule can see is that the answers have stopped
touching anything, and this policy's answers had never touched anything.

**The quiet rule is still there, as the backstop.** A gate that never said "done"
would spend a whole queue's budget on one table, so a run of answers that could
not touch a glass is still taken as the policy saying it sees nothing worth
doing. The rule is used exactly as written and its number is the bench's own, so
every solution in this problem reads the same one. A run's record counts the two
endings apart, which is the measurement of whether the gate learned to stop.

That number had to come from somewhere, and the right place is the teacher:
however many answers in a row the geometry reference gives without touching a
glass, a learned policy must be allowed at least as many before anyone calls it
finished. `teacher.py` here is that measurement and
`teacher-quiet-spells.json` is what it found, over forty tables of the band the
demonstrations come from:

| | |
| --- | --- |
| quiet spells that ended in a push | 326; longest **8**, middling 2 |
| the spell each table ended with | 40; longest **11**, middling 10 |
| the bench takes | **16** quiet answers as done |

It is measured on the demonstration band and not on the twenty tables this
solution is marked on, so that no part of the solution was set by watching its
own score. Being wrong high costs a few arm seconds of waving at a table that is
already finished; being wrong low ends the table.

Those two measurements — the teacher's quiet spells and the teacher's own
declarations — are the same fact read two ways, and the gate reads the better of
them. A spell of quiet answers says the teacher *happens not to be pushing*; the
declaration says it *has decided the table is finished*. The first is all a model
with no spare output can be given; the second is what the teacher actually did,
and it is now in the material.

The backstop wants one thing back from the solution: the tallest glass it has
**measured** on this table. A path can clear the height the jaw works at and
still sweep its fingers through a glass standing taller than it, and without that
number a policy knocking glasses over would be recorded as proposing nothing.
It is one number read off the looks, kept for the length of a table and
forgotten with it. The model is never shown it and nothing chooses anything with
it.

## `Look.refused` is unusable by a model

The contract does tell a solution why its last path was not carried out. It
tells it in a sentence of English, which solution 1 reads and acts on and a
fitted policy cannot read at all — and nothing in the demonstrations would have
taught it what to do if it could. So a refused path leaves this solution
answering the same way again: the arm has not moved, the clock has not advanced,
the picture is the same, and the model is deterministic.

Two things break that loop now. The bench's cap on answers is one, and it is read
off the arm time left, **so a measurement run must leave the clock switched on**:
solution 2's own measurement turns it off altogether, with a hundred thousand arm
seconds, which for a geometry solution is right and for this one would spin for
two million answers. `run.py` gives each table four arm minutes instead.

The other is the three numbers the gate is given about this solution's own
behaviour — how many answers it has given on this table, how many since it last
touched a glass, and how far the jaw has travelled since then. A refused path
still counts as an answer, so the gate's input changes even when the picture does
not, and a solution stuck in that loop eventually says it is finished instead of
spinning. Those three numbers are facts about the solution rather than about the
table, which is why it is allowed to keep them.

## The held-out queue

The real measurement: one ordered list of fifty tables from 10,000 up, fifteen
arm minutes for the whole list, and however far down it gets. `bench/judging.py`
owns the arrangement and this folder takes none of it as an argument. Each of its
three walks is one of the three fits, which is where the spread comes from. A
table the clock ended before the arm moved on it at all is dropped rather than
counted, so "tables attempted" means tables the arm really worked on.

| | `act-0` | `act-1` | `act-2` | spread |
| --- | --- | --- | --- | --- |
| tables attempted | 36 | 9 | 14 | 14 (9 to 36) |
| glasses on them | 142 | 33 | 52 | |
| tables separated | 0 | 0 | 2 | 0 (0 to 2) |
| glasses pickable at the end | 51 of 142 | 10 of 33 | 22 of 52 | share 0.359 ± 0.06 |
| glasses made pickable | −1 | −2 | +3 | −1 (−2 to +3) |
| glasses broken | 1 | 1 | 1 | **1 (1 to 1)** |
| said done, of the tables it reached | 33 | 6 | 11 | 11 (6 to 33) |
| said done while still crowded | 33 | 6 | 9 | 9 (6 to 33) |
| refused by the interlock | 14 | 0 | 0 | 0 (0 to 14) |
| thinking per answer | 15.8 ms | 22.0 ms | 21.4 ms | 21 ms |

**All three fits push, one of the three separates two tables, and each breaks
exactly one glass.** That is the state of this solution after it was fitted on
three times the demonstrations, and the one column that changed cleanly is the
breakages: every fit used to break one, two or three, and every fit now breaks
one.

**The three fits are no longer alike in how far they get, and that is a fault
rather than a spread.** `act-0` attempted thirty-six tables and declared
thirty-three of them finished while they were still crowded, so it reached three
times as far as the others by doing almost nothing on each table. Fourteen of
its answers were refused by the cell's own interlock, where the other two fits
had none refused at all. A fit that gives up instantly is cheap, and the share
punishes it only through the glasses it leaves crowded, which is why
**the three numbers on this card have to be read together** — tables attempted,
glasses freed and glasses broken — and why a solution cannot be ranked by any
one of them.

**The share fell from 0.400 to 0.359 and the glasses freed from +2 to −1, and
neither difference clears the noise.** Six walks a side say so: the share is
0.400 (0.316 to 0.404) against 0.361 (0.303 to 0.423), which is about one and a
half standard errors of the difference, and the freed glasses overlap
completely. Over the same twelve walks the broken glasses are 2 (1 to 2) against
1 (0 to 1), which does clear it. So three times the demonstrations halved what
this solution breaks and left the rest where it was.

**A table that loses a glass pays nothing at either end**, so what the share
mostly measures for this solution is how often it keeps its glasses standing;
the gain row is what says how much work it did. Reading the two together is the
only honest reading.

**The tipping interlock now refuses almost nothing**, between none and two
answers in a walk, where an earlier walk of this solution was refused between
nothing and thirteen times and the first version fourteen thousand times over
twenty tables. The clearance arithmetic
refuses those answers first, from the solution's own side, and a refused answer
is one the arm never spends time on.

## The same three fits on twenty training tables

Tables 0 to 19, each given four arm minutes of its own, which is how solutions 1
and 2 were measured so that the three can be set side by side. It is not the
measurement above and carries no throughput reading — "tables attempted" here is
always twenty — but it is twenty tables rather than thirteen, so it is where the
comparison with the geometry solutions lives. The ceiling column is what the
ranked chooser reaches with the arm taken away: true positions, exact pushes and
no clock.

| | solution 1 | solution 2 | **solution 3** | ceiling |
| --- | --- | --- | --- | --- |
| tables separated | 5 | 4 | **0 to 2** | 11 |
| glasses pickable at the end, of 84 | 47 | 43 | **31 to 33** | 66 |
| glasses made pickable | +14 | +10 | **0 to +4** | +33 |
| glasses toppled | 0 | 0 | **1 to 3** | — |
| arm seconds a table | 42.6 | 41.1 | **25 to 71** | — |
| share of arm time looking | 46% | 44% | **61% to 79%** | — |
| said done while still crowded | 15 of 20 | 16 of 20 | **15 to 19 of 20** | — |
| thinking per answer | 16.2 ms | 18.3 ms | **15 to 20 ms** | — |

Taken fit by fit: `act-0` leaves the eighty-four glasses as it found them and
topples one, `act-1` frees one and topples one, and `act-2` separates two tables
and frees four while toppling three. The three fits of one recipe still disagree
with each other more than two of them disagree with doing nothing, which is the
plainest statement of how early this solution still is. **What three times the
demonstrations changed here is the spread rather than the middle**: every fit now
topples at least one glass on these twenty tables where one of the three used to
walk them clean, and one fit now separates two tables where the best used to
separate one.

**The arm-time column is the one to look at twice.** `act-0` spends 25 seconds a
table and `act-1` spends 71, which is not a difference in how fast they move but
in how soon they stop: `act-0` gives 307 answers over the twenty tables and
`act-1` gives 730. A fit that stops early is cheap and useless, and the held-out
card above shows the same fit reaching thirty-six tables by doing nothing on
each.

What the answers are made of is in `measurement-fits.json`, and these are the
numbers to read if you want to know where the work goes:

| over twenty tables, per fit | |
| --- | --- |
| what the gate asked for | 175 to 397 looks, 106 to 239 probes, 12 to 89 pushes, 5 to 14 declarations |
| the gate named a glass the picture does not hold | 10, 16, 13 times |
| answers pulled down onto the two heights the cell accounts for | 29, 134, 161 |
| answers raised to travel height, because they could not account for themselves | 89, 203, 99 |
| the commonest reason for raising one | the hand would meet a glass it is not aimed at: 71 to 150 |
| glasses it had measured but could not see at the time | 1, 13, 5 |
| pushes carried on until the glass had room | 1, 22, 13 |
| how far a carried-on push moves its glass | 32, 15 and 25 mm |
| tables the gate finished, of 20 | 14, 5, 13 |
| tables the quiet rule finished instead | 5, 13, 4 |

**The commonest refusal is still the same one**, and it is the obstacle this
solution's own measurements keep pointing at: between seventy-one and a hundred
and fifty times over twenty tables, the direction the policy drew would take the
hand through a glass it was not aimed at. Three times the demonstrations brought
that direction six degrees closer to the teacher's, which is the largest gain
this round produced, and it did not move the refusal out of first place.

**Every glass this solution lost went over on the same kind of answer**, and the
record says so exactly. `run.py` keeps each table's last answer beside how that
table ended, because the solution itself cannot: a table ends the moment a glass
goes over, so the look that would show it the damage is never taken. Of the five
glasses lost over the three fits, all five followed a push that was aimed at a
glass, passed the whole clearance check, and was then **carried on** by the
arithmetic until the glass would have room.

**What changed with three times the demonstrations is how far those pushes were
driving.** Before, two of the three lost glasses went over while the arithmetic
expected the glass to move almost nowhere — 0.0 and 2.7 millimetres — which is a
glass tipping under a hand that was barely moving it. Now four of the five went
over on drives the arithmetic expected to move the glass **32 to 37
millimetres**, which is half the room a glass needs and a genuine attempt at the
task. The better the policy aims, the further the arithmetic is willing to carry
its push, and the further it carries it the more of the risk it takes on. That is
the trade this solution now sits in, and it is why its breakages halved while its
freed glasses did not rise: the pushes it does make are longer and fewer.

Nothing the solution can compute would have refused those pushes. The glasses had
been watched sliding, and the tipping rule answers "try it and see" for every
glass this cell draws. So this is where arithmetic stops being able to help this
solution, and what is left is the model that draws the shove.

Three measured things stand between this and a result like the geometry
solutions', and all three are quantities rather than opinions.

**One push is still smaller than the room a glass needs, though less so.** A
glass needs about 76 mm of clear space for the hand to get round it, and a push
this policy draws, carried on as far as the glass has been watched sliding, now
moves it 15 to 32 mm where it used to move 4 to 23. So a glass needs two or three
such pushes rather than three or four, each of which has to be decided and aimed
again, and each of which earns the next one its length.

**No push can be predicted safe, so every one costs two answers.** The tipping
rule answers "it will slide" for no glass this cell draws — over 1,600 drawn
glasses it is always "no" or "try it and see" — so a push is allowed only after
a probe has shown the glass slides. The gate has to choose the probe and then
the push, at the same glass, in that order.

**The direction the policy draws is often blocked by a neighbour.** Between 71
and 150 times over twenty tables the drawn path would take the hand through a
glass it is not aimed at, so the clearance rule raises it and nothing moves.
Three times the demonstrations brought that direction from 21–23° away from the
teacher's to 15–18°, which is the largest single gain of that change and still
leaves this the commonest refusal. Choosing the direction arithmetically would
repair it, and it is deliberately not done here: it would make this solution the
geometry reference with a learned chooser in front, which answers a different
question. Asking the gate for its *next* choice of glass instead was built and
measured, and it made things worse;
[`what-changed.md`](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/what-changed.md) has the
numbers.

### What the fitting cost

| | the gate | the chunked policy |
| --- | --- | --- |
| steps | 4,000 a seed, batch 64 | 8,000 a seed, batch 16 |
| wall time | 6.7 to 6.8 minutes a seed | 57 minutes a seed, 2 h 51 m for three |
| loss | 2.4 down to 1.50 to 1.58 | 6.7 to 7.7 down to 0.085 to 0.088 |

| the policy against its teacher | 300 tables of demonstrations | **900 tables** |
| --- | --- | --- |
| on tables it was fitted on | 8.7, 9.2, 9.8 mm a waypoint | 12.2, 11.7, 11.5 |
| on tables it never saw | 23.7, 23.8, 23.7 mm a waypoint | **22.6, 23.2, 22.7** |
| on the pushes alone, tables it never saw | 20 mm a waypoint | **17.7, 20.4, 19.4** |
| the direction of those pushes | 21° to 23° out | **15° to 18° out** |

**The two distances disagreed, that was read as memorising, and the band was
widened from three hundred tables to nine hundred.** The first version of this
solution was 18 to 19 mm from its teacher on both sets of tables, which said it
had learned a habit rather than a set of tables. The version after the split was
twice as close on tables it saw and a third further away on tables it did not,
which is the signature of a model that is memorising — and the cure for that is
more examples rather than more steps.

**What three times the demonstrations bought, measured:** the memorising stopped
— the error on fitted tables rose by three millimetres while the error on unseen
tables fell by one, so the gap between them closed from fourteen millimetres to
eleven — the pushes came about two millimetres closer, and **the direction of a
push came six degrees closer**, which is the largest single gain and the one that
bears on the commonest refusal. On the tables it halves the glasses this solution
breaks and leaves everything else inside the spread.
[What changed](https://github.com/RobinNagpal/robot-arm-projects/blob/851a30b61e6c06465c9f94ec8cb03efda004f2b1/v5-pick-glasses/docs/04-clear-the-table/what-changed.md) has those numbers
in full, including the gate's, which did not improve at all: fitted on three
times the material every one of its readings got wider rather than better, so it
was not short of data either.

`weights/training.json` holds the loss curves and every distance, and
`weights/gate.json` holds the gate's accuracy on tables it never saw.

## Running it

    pixi run python -u 03-imitation-from-demonstrations/collect.py             # the demonstrations
    pixi run python -u 03-imitation-from-demonstrations/collect.py --held-back
    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 1 --first-seed 0
    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 3 --gate-only
    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 3 --policy-only --looks 8000
    pixi run python -u 03-imitation-from-demonstrations/run.py                 # tables 0 to 19
    pixi run python -u 03-imitation-from-demonstrations/run.py --judge          # the held-out queue
    pixi run python -u 03-imitation-from-demonstrations/teacher.py              # the quiet spells
    pixi run pytest -q 03-imitation-from-demonstrations

Or `make collect`, `make train`, `make measure`, `make judge`, `make teacher`;
`make train-gate` and `make train-policy` are the two halves, and the second
takes `LOOKS`, which is how many of the teacher's looks the policy's fit reads.
The cap exists because looks are four answers in five and the sampler throws
most of them away again, so reading all 26,693 of them would cost a gigabyte of
memory and twenty minutes a run for frames no step would see. The gate is fitted
without it, because how often each kind of answer really happens is part of what
it has to learn.

Without `--judge`, `run.py` refuses to touch a table numbered `TEST_SEEDS` or
above: those are walked once, through `bench/judging.py`, which is what
`--judge` hands them to.

What is in git and what is not: the weights are tens of megabytes a seed and
`train.py` makes them again from the demonstrations, so they are left out, while
`weights/training.json`, `teacher-quiet-spells.json`, `results.json` and
`measurement.json` stay in, because each of them is something that was
measured.
