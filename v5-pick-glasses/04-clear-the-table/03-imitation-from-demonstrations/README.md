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
| tables attempted | 13 | 12 | 16 | 13 ± 2.1 (12 to 16) |
| glasses on them | 49 | 45 | 61 | |
| tables separated | 1 | 1 | 0 | 1 (0 to 1) |
| glasses pickable at the end | 20 of 49 | 14 of 45 | 23 of 61 | share 0.377 ± 0.05 |
| glasses made pickable | +3 | +3 | +2 | +3 (+2 to +3) |
| glasses broken | 2 | 5 | 2 | 2 (2 to 5) |
| said done, of the tables it reached | 10 | 6 | 13 | 10 ± 3.5 (6 to 13) |
| said done while still crowded | 9 | 5 | 13 | 9 ± 4.0 (5 to 13) |
| refused by the interlock | 0 | 4 | 13 | 6 ± 6.7 (0 to 13) |
| thinking per answer | 21.2 ms | 19.0 ms | 16.5 ms | 19 ms |

**All three fits now push, and two of the three separate a table.** That is the
first thing to say, because the first version of this solution reached ten
tables and handed every one of them back exactly as it was drawn. Two or three
glasses a queue are now given room they did not start with.

**The share is lower than the first version's, and the broken glasses are
why.** A share of 0.377 against 0.400 looks like a step backwards, and reading
it beside the gain row is what makes sense of it: a forfeited table pays nothing
at either end, so two to five broken glasses can cost more share than three
freed glasses earn. The two rows together are the honest result — the solution
is doing the task, and it is doing it badly rather than not at all.

**The spread is now about what the fits do, not how far they get.** In the first
version one fit reached eleven tables and another reached one, because the third
never answered at all; the walks were comparable on a single table. Now all three
reach twelve to sixteen tables, and they differ in the work: `act-0` separates a
table and breaks two glasses, `act-1` separates a table and breaks five, and
`act-2` separates none and breaks two.

**The tipping interlock refuses between nothing and thirteen answers**, where
the first version was refused nothing here and fourteen thousand times on the
twenty tables below the line. Which tables a livelock happens on is a matter of
the draw, so the two runs disagree about how much of the budget goes that way;
both are reported rather than averaged.

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
| tables separated | 5 | 4 | **0 to 1** | 11 |
| glasses pickable at the end, of 84 | 47 | 43 | **31 to 36** | 66 |
| glasses made pickable | +14 | +10 | **−2 to +3** | +33 |
| glasses toppled | 0 | 0 | **1 to 4** | — |
| arm seconds a table | 42.6 | 41.1 | **49 to 70** | — |
| share of arm time looking | 46% | 44% | **52% to 65%** | — |
| said done while still crowded | 15 of 20 | 16 of 20 | **15 to 19 of 20** | — |
| thinking per answer | 16.2 ms | 18.3 ms | **17 to 19 ms** | — |

Taken fit by fit: `act-0` separates one table of the twenty and frees three
glasses while toppling four, `act-1` frees none and loses one while toppling
one, and `act-2` frees two while toppling two. The three fits of one recipe
disagree with each other more than two of them disagree with doing nothing,
which is the plainest statement of how early this solution still is.

What the answers are made of is in `measurement-fits.json`, and these are the
numbers to read if you want to know where the work goes:

| over twenty tables, per fit | |
| --- | --- |
| what the gate asked for | 322 to 487 looks, 149 to 196 probes, 64 to 90 pushes, 12 to 13 declarations |
| the gate named a glass the picture does not hold | 11, 22, 32 times |
| answers pulled down onto the two heights the cell accounts for | 114, 137, 191 |
| answers raised to travel height, because they could not account for themselves | 137, 107, 112 |
| the commonest reason for raising one | the hand would meet a glass it is not aimed at: 63 to 92 |
| pushes carried on until the glass had room | 16, 29, 34 |
| how far a carried-on push moves its glass | 5, 18 and 25 mm |
| tables the gate finished, of 20 | 12, 13, 13 |
| tables the quiet rule finished instead | 4, 6, 5 |

Three measured things stand between this and a result like the geometry
solutions', and all three are quantities rather than opinions.

**One push is too small for the room a glass needs.** A glass needs about 76 mm
of clear space for the hand to get round it, and a push this policy draws,
carried on until the clearance rule says the glass has room, moves it 5 to
25 mm. So a glass needs three or four such pushes, each of which has to be
decided and aimed again.

**No push can be predicted safe, so every one costs two answers.** The tipping
rule answers "it will slide" for no glass this cell draws — over 1,600 drawn
glasses it is always "no" or "try it and see" — so a push is allowed only after
a probe has shown the glass slides. The gate has to choose the probe and then
the push, at the same glass, in that order.

**The direction the policy draws is often blocked by a neighbour.** Between 63
and 92 times over twenty tables the drawn path would take the hand through a
glass it is not aimed at, so the clearance rule raises it and nothing moves.
Choosing that direction arithmetically would repair it, and it is deliberately
not done here: it would make this solution the geometry reference with a learned
chooser in front, which answers a different question.

### What the fitting cost

| | the gate | the chunked policy |
| --- | --- | --- |
| steps | 4,000 a seed, batch 64 | 8,000 a seed, batch 16 |
| wall time | 6.7 to 6.8 minutes a seed | 57 minutes a seed, 2 h 52 m for three |
| loss | 2.3 to 2.4 down to 1.41 to 1.47 | 6.7 to 7.7 down to 0.058 to 0.066 |

| the policy against its teacher | |
| --- | --- |
| on tables it was fitted on | 8.7, 9.2, 9.8 mm a waypoint |
| on tables it never saw | 23.7, 23.8, 23.7 mm a waypoint |
| on the pushes alone, tables it never saw | 20 mm a waypoint, and 21° to 23° out in direction |

**The two distances no longer agree, and that is a change in what to try
next.** The first version of this solution was 18 to 19 mm from its teacher on
both sets of tables, which said it had learned a habit rather than a set of
tables, and that more demonstrations would teach the same habit. This version is
twice as close on tables it saw and about a third further away on tables it did
not, because it is no longer free to answer with the average of looking and
pushing: it is really trying to draw pushes, and it is short of examples of them.
A push is one answer in thirty-six in the demonstrations, so collecting more —
or collecting them from tables chosen to be crowded — is now a reasonable thing
to try. `weights/training.json` holds the loss curves and both distances, and
`weights/gate.json` holds the gate's accuracy on tables it never saw.

## Running it

    pixi run python -u 03-imitation-from-demonstrations/collect.py             # the demonstrations
    pixi run python -u 03-imitation-from-demonstrations/collect.py --held-back
    pixi run python -u 03-imitation-from-demonstrations/train.py --seeds 1 --first-seed 0
    pixi run python -u 03-imitation-from-demonstrations/run.py                 # tables 0 to 19
    pixi run python -u 03-imitation-from-demonstrations/run.py --judge          # the held-out queue
    pixi run python -u 03-imitation-from-demonstrations/teacher.py              # the quiet spells
    pixi run pytest -q 03-imitation-from-demonstrations

Or `make collect`, `make train`, `make measure`, `make judge`, `make teacher`.

Without `--judge`, `run.py` refuses to touch a table numbered `TEST_SEEDS` or
above: those are walked once, through `bench/judging.py`, which is what
`--judge` hands them to.

What is in git and what is not: the weights are tens of megabytes a seed and
`train.py` makes them again from the demonstrations, so they are left out, while
`weights/training.json`, `teacher-quiet-spells.json`, `results.json` and
`measurement.json` stay in, because each of them is something that was
measured.
