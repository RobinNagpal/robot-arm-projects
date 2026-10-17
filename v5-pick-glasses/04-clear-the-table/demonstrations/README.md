# The demonstrations

What the ranked geometry saw and what it did, written down so that a model can
be fitted on it.

Two solutions to problem 4 learn by copying: solution 3 fits a small model here
from nothing, and solution 6 corrects a large borrowed one. They are meant to be
compared with each other, and that comparison is only about the models if the
material is the same. So the sets are collected once, into this folder, and both
read them from here. Problem 3 learned that the hard way: its two copying
solutions started with different bands, different counts and different tables
for checking, and the comparison between them was partly a comparison of their
data.

This folder holds nothing but the sets and the record of what they are:

| | |
| --- | --- |
| `fitted-on/` | the set a model is fitted on |
| `held-back/` | the set kept back from fitting |
| `collected.json` | what both are: the band, the size and what they cost |

The collector is [`../03-imitation-from-demonstrations/collect.py`](../03-imitation-from-demonstrations),
with the two conventions a demonstration is written in — `chunks.py` for the
action and `readings.py` for the observation — and `loading.py`, which is where
these paths are and how a set is read back. Solution 6 reads the sets from here
and those conventions from there.

## What a demonstration is

The **observation** is what problem 4 hands every solution in one `Look`, plus
two things about the answer itself:

- the picture the camera on the arm rendered from where the jaw was standing,
  at the size the camera renders it,
- the readings of the glasses that picture caught, as slots,
- where the jaw was standing,
- three numbers about how this table has gone so far: how many answers the
  teacher had given on it, how many since it last touched a glass, and how far
  the jaw had travelled since then, and
- **the decision**: which of four kinds of answer this was, and which glass it
  was aimed at.

The **action** is the path the jaw followed, as the teacher wrote it and the
bench carried it out, in the cell's own numbers.

**The last two of those were added after the first fits, and both are there for
the same measured reason.** A model fitted to copy this set has to produce two
very different kinds of answer out of one output, and because four answers in
five are looks, what it produced was always a look: the first fitted policy
freed no glasses on any table. So the decision is now recorded beside the path,
which lets one model learn to choose and another learn to draw, and the three
numbers about the table's history are what let a model tell a table it has just
arrived at from one it has already been round.

**The set itself keeps one convention, and each solution reads it.** A push
measured from the glass it pushes is one answer wherever that glass stands, and
in the table's own numbers it is a different answer at every glass — which is
worth a great deal to the model that has to draw one. But it is a *reading*
rather than what happened, and the other solution fitted on this set refused a
path written that way, because a path measured from a glass is not a path its
model can express. So the set holds the plain truth and the reading is done
where it is wanted: ``loading.aimed_at`` reads the glass's place back out of the
row the policy is shown, and solution 3's own fitting subtracts it. Nothing is
kept in step by hand, because the place is already in the row.

**The teacher's own "this table is finished" is in the set too.** The loop never
asks the cell to carry anything out for it, so there is no path to copy; the
frame holds the last look and the decision, and the model that learns to choose
is fitted on it. Without it, a learned solution has no way to say a table is
done except by going quiet, and the first fitted policy declared nine of its ten
tables finished while they were still crowded.

**One answer is one demonstration, and that is the difference from problem 3.**
Problem 3 counted only pushes, because its camera hangs above the table and a
solution is handed the whole arrangement for nothing. Problem 4 took that camera
away, so four answers in five are the teacher driving the arm somewhere it can
see from. A model shown only the shoves would have no idea how to get a look at
the table, so the looks are demonstrations too.

**The action is the commanded path, and that is the followed path.** The label
has to be the path the jaw really followed, and for a kept demonstration the two
are the same path: over 128 of the teacher's pushes, the bench's own record of
the motion agrees with the path it was handed to within 0.4 mm at every
waypoint, and none of those records was short.

The record itself is not used as the label, for two reasons. A path that was
only a look leaves no record at all, because nothing moved — the jaw was already
at travel height and `follow()` had nothing to drive. And a record of a push
carries the bench's own ending, the back-off and the lift home, which is a
steady 22 entries on the end of every one of them. `follow()` makes that ending
for itself, so a chunk that asked for it would be asking for the lift twice.

## The band, and how much there is

`collected.json` is the record for both sets. The one a model is fitted on:

| | |
| --- | --- |
| tables | 300, numbered 1000 to 1299 |
| folder | `fitted-on/` |
| demonstrations | 11,313 |
| answers a table | 37.7 |
| of them looking | 8,965 — 4,822 drives to a stand and 4,143 extra frames from where the jaw already stood — **79%** |
| of them pushing | 2,062 — 1,416 ranging, 331 testing, 315 pushing the glass somewhere |
| of them finishing | 297 — the teacher saying the table needs nothing more |
| dropped | 11: 8 shoved a glass out of the zone, 3 put one over |
| a path | 1 waypoint to look, 39 to 190 to push; the median over all of them is 1 and the ninetieth is 44 |
| on disk | about 350 MB |

**Read the three middle rows together, because they are the whole difficulty of
fitting anything on this set.** Four answers in five change nothing about the
table. Of the ones that touch a glass, five in six are a five-millimetre poke
made to find something out rather than to move the glass anywhere. **One answer
in thirty-six is a push at the task.** A fit drawn evenly from this material
spends almost all of itself on the answer that is easy and does nothing, which
is why the two models fitted on it now take it differently: the one that chooses
is shown the mixture as it is, with each kind's part of the loss divided by how
common it is, and the one that draws is given batches drawn evenly from the
kinds.

A second set is collected the same way from tables 8000 to 8049 into
`held-back/`: 1,900 demonstrations in 92 s, with the same 38 answers a table
and the same 79% looking, so it is the fitting set in miniature. It is not a score — the score is
the outcome on the tables, which each solution's own runner measures — but it is
what says whether a fit has memorised its tables or learned something: the
distance between the student's chunk and the teacher's, on pictures the fit never
saw.

The band starts at 1000 and not at 0 because the twenty tables every solution in
this problem is measured on are 0 to 19. A student fitted on those would be
measured on tables it had already seen.

### What it cost

**Eight and a half minutes of wall time for the whole set**: 516.6 s for 300
tables, which is 1.72 s a table and 0.047 s a demonstration. Nobody holds a
controller — the tables are drawn from numbers and the teacher is a program — so
the only cost is simulator time.

It is worth setting that against problem 3, because the expectation going in was
that problem 4's demonstrations would cost several times more, and the two
numbers pull in opposite directions.

| | problem 3's set | this set |
| --- | --- | --- |
| a table | 0.74 s | 1.72 s |
| a demonstration | 0.55 s | 0.047 s |

**A table costs twice as much**, and that is the camera: the teacher has to
drive the arm around before it can act, so it makes about six pushes a table
here against problem 3's three, and a push is where the physics time goes —
each one settles the table for half a simulated second.

**A demonstration costs a tenth as much**, and that is the same fact read the
other way. Problem 3 kept 1.3 demonstrations from a table because only a push
counted. Here every answer is one, and 37 of them come off a table, so the
rendering of 37 pictures is cheap beside the six pushes that had to happen
anyway. The set is therefore wide in frames and narrow in *pushes*: 2,062 of
them against problem 3's 6,935, from a fifth of the tables.

## The teacher was trained somewhere else

The teacher is [solution 2](../02-geometry-ranked), run unchanged. Its chooser
is problem 3's fitted ranker, **loaded and not refitted**, and the tables that
ranker was fitted on were problem 3's tables — 0 to 199 of problem 3's own
draw. Problem 4 draws its own tables from its own seed string, so its table 7 is
not problem 3's table 7, and nothing says the ordering that ranker learned over
there is the right ordering here. Solution 2's own measurement says the same
thing from the other side: on these tables the fitted ordering picks a different
push from the printed rule most of the time, and separates fewer tables than the
rule does.

So this is a set of demonstrations by a teacher trained on another problem's
tables, and a student fitted on it inherits that. It is not a flaw to be fixed
here — refitting the ranker on problem 4's tables would make solution 2 a
different solution, and the comparison between problems 3 and 4 would stop
meaning anything — but it is a fact a reader of a result needs.

## What is dropped, and what is not

A cloned policy copies whatever is in its data, so an answer that ended badly is
not one to copy. Four endings are dropped, and only the answer that caused them:

- a glass went over,
- a glass was shoved out of the glass zone,
- the jaw was blocked on the way down, or jammed against something,
- the path was longer than a chunk.

Every drop is counted by its reason in `collected.json`, because filtering by
outcome thins the data exactly on the tables the teacher found hard, and that
thinning is invisible unless it is counted.

**The probe pushes are kept, and problem 3 dropped them.** Problem 3's 5 mm test
push belongs to the shared tipping check rather than to the chooser, so it is
not a push at the task there. Here the same shove does a second job that taking
the camera away forced on it: a chunk cannot feel its way in, so the only way to
find out how far away a glass is, is to push a little and look. That makes it an
action at the task in problem 4. `collected.json` counts the three kinds of push
apart — ranging for the glass, testing whether it slides, and pushing it
somewhere — so a reader can see the mixture a student is being fitted on.

**An answer the cell refused is not a demonstration.** The tipping interlock and
the bench's own checks turn some answers away, and the arm never moves, so there
is no path the jaw followed. Only an answer the bench carried out becomes a
frame.

## What a student made of them

[Solution 3](../03-imitation-from-demonstrations) is the first fit on this set:
three seeds of a small chunked model, 8,000 steps each. It copies the teacher's
chunks to within 18 to 21 mm a waypoint and separates no table at all, on the
held-out queue or on twenty training tables, against the teacher's four of
twenty — and it frees not one glass. Its own README says why. One thing about it
belongs here, because it is about the set rather than the model: **four answers
in five in these demonstrations are a look**, and under an L1 objective the
cheapest answer to a picture that does not say which the teacher would have done
is therefore the common one. One of the three seeds answers with a single
waypoint every time.

That is the price of counting every answer as a demonstration, and the
alternative has a price too. A set of pushes alone — problem 3's choice — would
give a student no way to learn where to drive the arm to see, which in this
problem is half the job.

**So the set still records what the teacher did, in the proportions the teacher
did it, and the balancing happens where the fitting is.** That is the answer this
folder arrived at after the first fits, and it is the better place for it: a
dataset that had been balanced when it was written down could not have told
anybody what the teacher's real mixture was, and that mixture is a measurement of
the problem rather than of the teacher. Two models are now fitted on the same
rows and treat the mixture differently — the one that *draws* a path sees the
kinds in equal measure, because it has to draw a push as well as it draws a look;
the one that *chooses* between them sees the mixture as it is, with each kind's
part of the loss divided by how common it is, because how often each kind happens
is part of what it has to learn.

## The format

A [LeRobot](https://github.com/huggingface/lerobot) dataset, written the way
problem 3's solution 6 writes one, because that is the format the borrowed
models take:

| key | what it is |
| --- | --- |
| `observation.images.wrist` | the picture, at the size the camera renders |
| `observation.state` | the jaw's pose, the glasses the picture caught, the three numbers about the table so far, and the decision |
| `action` | the chunk, flat, in the cell's own numbers |
| `gate` | the decision as two numbers: which kind of answer, and which slot it named |
| `task` | one sentence, the same every time |

**Why the decision is in both `observation.state` and `gate`.** The model that
draws a path is *told* the decision, so for it the decision is part of the
observation. The model that makes the decision cannot be told it, so it is given
the front of the same row — the table, the pose and the three numbers — and the
decision is its label, which is what `gate` is. One dataset serves both because
the row is laid out in that order and the deciding model simply reads less of
it. `readings.py` is where the widths are named, and a test holds the two
against each other so they cannot drift apart.

One episode is one table. One frame is one answer.

The chunk is stored flat, one row of `CHUNK * ACTION_WIDTH` numbers, and
reshaped when it is read back. LeRobot works a dataset's statistics out by
reducing each feature over an episode's frames, which only comes out the same
shape on every episode when a frame's feature is one-dimensional.

## Making them again

    pixi run python -u 03-imitation-from-demonstrations/collect.py              # fitted-on
    pixi run python -u 03-imitation-from-demonstrations/collect.py --held-back
    pixi run python -u 03-imitation-from-demonstrations/collect.py --tables 3 --show

The sets themselves are not in git — a few hundred megabytes of rendered
pictures, regenerable from the table numbers — but `collected.json` is, because
what was collected is a measurement.

The collector refuses to draw a table numbered `TEST_SEEDS` or above. Those are
the held-out measurement and nothing is fitted on them.
