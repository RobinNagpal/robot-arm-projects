# Solution 6 — the same foundation model, fine-tuned here

> **What it uses** — LeRobot, with PyTorch underneath, and this machine's own
> Metal GPU for the training run, which is further than this document expected
> a 450-million-parameter fine-tune to go. The model is SmolVLA: the same
> library,
> the same model and the same downloaded weights as [solution
> 5](05-smolvla-as-it-downloads.md), with its training continued on pushes
> made on this bench by low-rank adaptation, so that the actions it emits are
> fitted to this cell's own range rather than left to the range the borrowed
> recordings happened to use.
> **What it does** — a model that arrives fitted to real teleoperation of
> other robots is neither thrown away nor used as it arrives. Its numbers are
> kept, and a small correction to them is learned from pushes made on this
> bench, so that it stops being a general copier of robot motion and becomes a
> pusher of glasses on this table. The action chunks it then emits are this
> solution's answer to problem 3.
> **How the output is produced** — a rendered view of the table from the top
> goes in, together with one instruction in plain English and the arm's own
> pose, which is the same every time because the jaw is parked between
> actions. The corrected model returns an **action chunk**: a short run of
> consecutive jaw waypoints predicted together in one pass. The shared
> geometry refuses the glasses that tip before they slide, and a chunk whose
> path would reach one of those is not carried out.
> The bench then carries the waypoints out directly, because a chunk needs no
> expansion. The arm looks again, and the loop repeats until the table is done
> or the push budget is spent.
> **How it differs from the other five** — [solution
> 1](01-one-fixed-nudge.md) fits nothing and chooses its one push by fixed
> arithmetic on the measurements.
> [Solution 2](02-geometry-ranked.md) generates pushes by geometry and fits
> only a ranker to choose between them, and it is this solution's teacher,
> because its pushes are the demonstrations. [Solution
> 3](03-imitation-from-demonstrations.md) learns from those same
> demonstrations but from random numbers, borrowing an architecture and no
> weights, which makes the pair with this one a test of whether borrowed
> weights are worth having.
> [Solution 4](04-a-world-model.md) learns how the table changes and searches
> over candidate pushes at run time instead of learning a push directly.
> [Solution 5](05-smolvla-as-it-downloads.md) is this exact model with no
> training in this cell at all, which makes it this solution's matched
> partner.
> **What it costs** — the demonstrations are free, because solution 2
> generates them and the bench executes them without anybody holding a
> controller. The training is a low-rank fine-tune, and it fits in 1.02 GiB on
> a laptop, so nothing was rented; hours of a small rented accelerator, of
> order tens of dollars, is what it would take to spend real compute on it.
> Running it costs one large forward
> pass per chunk, the same as its partner's, so the two cost the same to run
> and differ only in what it cost to build them. The licence is not the
> obstacle it was in problem 2, but a fine-tuned file inherits whatever terms
> the borrowed file carried, so the terms have to be read before anything
> leaves this project.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the
> side, all four sensors, and the words this project uses them with. What
> follows is only what is specific to this solution.

## Introduction

This document explains how to answer problem 3 by taking a robot foundation
model that was already fitted elsewhere and continuing its training on pushes
made in this cell. The method has a name, **fine-tuning**, and it is the
ordinary way a borrowed model is put to work on a particular job. Nothing in
it is unusual, and that is deliberate: this is the standard move, written out
in full so that what it buys can be measured rather than assumed.

**The whole reason this solution exists is that it is one half of a matched
pair.** [Solution 5](05-smolvla-as-it-downloads.md) is this model with no
training in this cell. This is the same model with training in this cell.
Everything else between the two is held still, and the list of what
"everything else" covers is the argument, so it is worth setting out one item
at a time. The [test bench](../the-bench.md) holds the input still, so both
are shown the same rendered view of the same tables in the same order, with
the same instruction and the same joint readings, and the same measurements
reach the shared checks in both. It holds the output still, so both hand back a
chunk of jaw waypoints. It holds the marking still, so both are read off the
same scorecard, computed the same way. And these two solutions hold the
library, the model and the starting weights still, because they are the same
library, the same model and the same downloaded file.

One thing differs, which is the training. The section below asks whether
anything else does, because a matched pair invites exactly that mistake, and
the answer it reaches is that nothing else does. The model's output does stop
being numbers in the range the borrowed recordings used and becomes numbers in
the range this cell's own pushes use, but that is a property of the weights the
training changed rather than a second thing changed beside them, and the
convention by which those numbers are read as jaw waypoints is chosen once and
used by both. So **nothing varies between the two that the training did not
bring**, and the gap between solution 5 and this one is therefore a measurement
of what this training bought on a robot foundation model, and of nothing else.

That makes this pair the same question [problem
2](../../02-segment-glasses/problem.md) asks about a segmenter, asked one
level up. There the pair was a model that finds objects in pictures, borrowed
untouched against borrowed and fine-tuned, and the answer was about perception
alone. Here the model does not report what it sees; it decides what the arm
does next. So the question is no longer "does training help a model describe
this cell" but "does training help a model act in it", and the two answers do
not have to agree. A model can be fitted to a cell well enough to find every
glass in it and still be a poor chooser of pushes, because choosing a push
needs a sense of what a push does, and nothing in a picture contains that.

**Most of this is built, and the parts that are not are named where they
appear.** The solution lives in `03-push-glasses-apart/06-smolvla-fine-tuned/`:
it records its demonstrations from the teacher, fits the correction, and has
been run on the bench's held-out tables, with its numbers in that folder's
README. The two parts of the shared contract it waited on are in the bench
now — a rendered view looking straight down in `bench/top_view.py`, and
`Bench.follow()`, which carries a chunk of waypoints out as an action — so
nothing below is blocked on them. Three things here are still prescriptions
rather than code, and each says so where it is described: **DAgger**, the
**second rung on π0.5**, and the **several training seeds** the bench asks for,
of which one was fitted. Everything else in this document describes a program
that has run.

By the end you will understand what fine-tuning is and why it is far cheaper
than fitting a model of this size from random numbers, what low-rank
adaptation is and what it trades away to fit in the memory it has to fit in,
where the demonstrations come from and why they are free while also capping
what this solution can ever be, which of solution 5's weaknesses the training
repairs and which of them survive it untouched, the two ways training on one
cell's pushes goes wrong, and why a markedly larger foundation model is a
second rung here rather than the main line.

## The problem this solves

Problem 3 asks for a jaw trajectory, and then another, until every glass has
about 70 mm of clear room around it or the glasses that are left have been
refused with a reason. [The problem](../problem.md) explains why that is hard,
and the hardest part of it is a missing number: whether a pushed glass slides
or tips depends on the friction between the glass and the table, **nothing in
the cell measures friction**, and the bench never tells any solution what it
is using.

A learned policy answers that difficulty in the only way available to anything
here, which is by sampling outcomes rather than deriving them. It is shown
many pushes and what they did, and what it ends up holding is a sense of what
a push of this kind tends to produce on this table, friction included, without
any term in it standing for friction. Solution 5 already borrows a model built
that way, and borrows it from a very large collection of real robot motion, so
the general shape of that answer is available without fitting anything.

The question this solution exists to answer is therefore narrower and more
interesting than "does learning help". It is: **having borrowed a policy, what
is still wrong with it, and does training here fix that?**

Three things are still wrong in solution 5, and all three have one cause. The
model was fitted on 487 community datasets of real teleoperation — real
cameras, real rooms, real robots of other shapes — and this cell hands it a
view rendered by a simulator, of opaque glasses standing on a bare table, seen
straight down from above. First, the pictures are of a world the weights never
met, so what the model finds in them may have little to do with what is there.
Second, the numbers it produces are actions on the scale of the robots it was
fitted on, so whether they are the right size for this jaw on this table is
left to chance rather than fitted. Third, and underneath both, the model has
never seen the consequence of a push on this table, so whatever sense of
pushing it holds belongs to other tables.

Continuing the model's training on pushes made here is the standard repair for
all three at once, and that is what this solution does.

## The main idea

The idea is one sentence long: keep the borrowed numbers, and learn a small
correction to them from pushes made on this bench.

Three things follow from that sentence, and most of this document is those
three things.

**The numbers do not start from nothing.** A model's weights are the numbers
inside it, and SmolVLA holds about 450 million of them. Fitting that many from
random values would mean teaching the model everything, down to the fact that
an edge in a picture is worth noticing and that a motion should be smooth. The
borrowed weights already hold all of that, so the training continues from them
rather than beginning beside them.

**The pushes are this bench's pushes.** This is the part that makes the
difference to solution 5. Solution 5 asks a model fitted on real teleoperation
to act on a rendered view of a simulated table, which is a different kind of
input leading to a different kind of outcome. Fine-tuning does not ask that.
It shows the model this bench's views and this bench's pushes during training,
so at run time the model is being shown the kind of thing it was fitted on.
The difference between the two kinds of input is called the **domain gap**, and
fine-tuning is how a domain gap is closed.

**Only a small part of the model is actually changed.** Rather than moving all
450 million numbers, the training leaves every borrowed number where it is and
learns a small correction that is added alongside them. That technique is
called **low-rank adaptation**, it is what makes the training affordable, and
it has its own section below, because what it trades away matters to how the
pair's result should be read.

Everything else about the model is unchanged, including the things that limit
it. It still takes one instruction in words, and the task still has one
instruction, so that channel still carries nothing. It still takes the arm's
own pose, and the bench parks the jaw between actions, so that channel carries
nothing either: the same six numbers go in at every ask. It still predicts a
chunk of waypoints and commits to the whole of it before looking again, because
the number of actions SmolVLA emits in a pass and the number it is configured
to carry out are the same fifty. And it still has no field in it for a rule, so
it still cannot be the thing that refuses a glass.

## Fine-tuning — continuing somebody else's training

Because fine-tuning is the single thing that separates this solution from its
partner, it is worth setting out carefully and in plain words.

**Training** a network means showing it an example, comparing what it produced
against the answer that was wanted, and nudging every weight a little in the
direction that would have helped. Repeat that over many examples and the
weights settle at values that produce good answers. **Training from a random
start** means the weights begin as noise, so the nudges have to build every
part of the model out of nothing. **Fine-tuning** means the weights begin at
values somebody else's training already settled, so the nudges have much less
to do.

The reason that is so much cheaper is clearest when it is stated in terms of
what the data has to pay for. Every weight in a model is a number the training
data has to determine. If the data does not hold enough information to pin a
weight down, that weight ends up fitted to accidents of the particular
examples it was shown rather than to anything real. So the amount of data
needed grows with the number of weights that have to be determined from
nothing, and fine-tuning changes that sum almost entirely: the great majority
of the weights already sit at values that work, and the data only has to adjust
them.

A comparison from mathematics makes the shape of this clear. Fitting from a
random start is like solving for every coefficient of a long polynomial with no
idea of any of them. Fine-tuning is like being handed a polynomial that already
fits a similar curve and being asked to adjust its coefficients a little. The
second problem needs far fewer points before it is well determined, because
most of the answer is already there.

There is a second saving, about time rather than data, and for a model that
acts rather than describes it has two halves. A model fitted on pictures holds,
in its early layers, detectors for things common to all vision: an edge, a
corner, a shading that runs across a curved surface. Those transfer almost
completely, because an edge is an edge, and a rendered glass standing on a bare
table has a strong edge round it. A model fitted on robot motion holds
something similar about motion: that a trajectory is smooth, that a jaw
approaches a thing before it touches it, that a motion has a beginning and an
end. Those transfer too, because they are properties of moving a tool rather
than properties of any one robot. A random start spends much of its training
discovering both of those again. Fine-tuning does not, so only the later
judgement has to change — what in this picture is a glass worth pushing, which
way, and how far.

That gives an honest expectation rather than a result, and it should be read as
one. What carries over best is the cheap general machinery at the bottom of the
model. What carries over worst is the judgement at the top, which was fitted to
decide what to do next in rooms that look nothing like this one, with grippers
shaped nothing like this one, on tasks that were mostly not pushing. So
fine-tuning here has more work to do than the usual advice about borrowed
models implies, and still far less work than a random start. That last claim is
the one [solution 3](03-imitation-from-demonstrations.md) exists to check from
the other side, because it fits a policy here from random numbers on the very
same demonstrations.

## Low-rank adaptation — a small correction instead of a large change

Fine-tuning as described above moves every weight, and on a model of this size
that is the expensive way to do it. Low-rank adaptation is the cheap way, and
it is what this solution uses.

Start with what a layer of a network does. It takes a list of numbers in,
multiplies it by a table of numbers, and hands a list of numbers out. The table
is the weights of that layer, and a model of this size holds many such tables,
some of them large. Ordinary fine-tuning changes every number in every table.

**Low-rank adaptation leaves every borrowed number exactly where it is, and
learns a correction that is added to it.** The correction is the same size as
the table it corrects, so the layer still does the same work. What makes it
cheap is that the correction is not allowed to be an arbitrary table. It is
forced to be the product of two thin tables: one that squeezes the incoming
list down to a handful of numbers, and one that expands that handful back out
to full width. Because the squeeze is narrow, the two thin tables together hold
far fewer numbers than the table they correct, even though their product is as
wide as it.

The comparison from mathematics is the useful one, and it is the same move this
project meets elsewhere. A table of numbers can be written as a sum of simple
patterns, each pattern being one outward direction paired with one inward
direction, and the number of patterns needed is the table's **rank**. Forcing
the correction through a narrow squeeze is forcing it to be a sum of only a
handful of such patterns, which is exactly the move of approximating a large
table by a few of its strongest patterns, or a curve by a few terms of a
series.

**The practical reason this matters here is accelerator memory, and the
arithmetic is worth doing.** Training does not only have to hold the weights.
For every weight that is being changed it also has to hold that weight's
gradient, which says which way to nudge it, and the optimiser's running
averages of that gradient, which are what make the nudges stable. Those add up
to several times the size of the model itself. With low-rank adaptation only
the correction's numbers are being changed, so only they carry gradients and
optimiser state, and the borrowed weights sit there as a fixed cost. What has
to fit in the accelerator is then the model's own size plus a little, rather
than several times the model's size.

The brief numbers for the larger family make the difference plain. On π0,
which holds about 3.3 billion parameters, a low-rank fine-tune needs more than
22 GB of accelerator memory and a full fine-tune needs more than 70 GB. The
first is an accelerator that can be rented by the hour; the second is not
something this project is going to reach for. SmolVLA is much smaller — about
450 million parameters, a few gigabytes at inference, and it runs on a laptop
— and **at that size the saving is larger than it needs to be**: the measured
figure for the training below is 1.02 GiB, which fits on this machine without
anything being rented. The arithmetic above is still what makes that true, but
the conclusion it was written to support — that an accelerator has to be
rented — is only the conclusion for the larger model.

**The trade is that it adapts less deeply, and this has to be stated plainly
because it decides how the pair's result should be read.** The correction is
confined to a handful of directions in each table, so a change that genuinely
needs the whole table cannot be expressed. Where the new task is near the old
one, that costs nothing, because the change needed is small and a few
directions hold it comfortably. Where the new task is far from the old one, a
full fine-tune would go further. This cell is far: rendered pictures of a
simulated table, one gripper, one motion, and a kind of outcome none of the
borrowed datasets contained. So this is exactly the case where the trade bites,
and the consequence for the comparison is that **the gap this pair measures is
a lower bound on what fine-tuning could buy**, not the whole of it. A result
that says low-rank fine-tuning bought little does not say that fine-tuning
bought little.

One more property of the correction is worth knowing, because it decides the
compute column on the scorecard. Once training has finished, the two thin
tables can be multiplied out and the result added into the borrowed table, so
what is left is a single table of the original size. The fine-tuned model is
then exactly as large and exactly as fast as the downloaded one. **So this
solution and its partner cost the same to run**, and whatever separates their
scores cannot be explained by one of them having been given more computation
at run time.

## Where the demonstrations come from, and what they cost

Fine-tuning needs examples, which here means recorded pushes with what was
seen beside what was done, and this is where the arrangement of the six
helps.

[Solution 2](02-geometry-ranked.md) generates pushes by geometry and ranks them
with a fitted ranker, and it is a working chooser of pushes. Run it on the
bench over the training half of the tables and almost every push it makes is a
demonstration. The observation is what this model takes as its input: the
rendered view of the table from the top taken at the moment the push was
chosen, the one instruction, and the arm's own pose. The action is the path the
jaw really followed, which the bench writes down on every action, so a
demonstration is a recording of the shared contract being satisfied and nothing
in it had to be drawn, labelled or judged by a person.

What that came to, measured: **800 training tables, 22 minutes of simulator
time on this laptop, 2,012 demonstrations.** Two things about the count are
worth knowing. **Most of the teacher's pushes are not demonstrations**: of the
3,554 pushes it made, 1,533 were the 5 mm test pushes that settle whether a
glass slides, and those belong to the shared tipping check rather than to the
chooser, so none of them is a target. And of the remaining 2,021 real pushes,
**only 9 had to be thrown away** — 8 toppled a glass and 1 pushed one out of
the zone. The section below warns at length about what filtering to successes
throws out, and on this bench the answer is four tenths of one per cent. That
is a quantity worth having rather than a worry worth carrying.

Two things about that recording are worth noticing, because they decide what
the policy can and cannot learn. The teacher works from the numeric readings
`look()` hands over, and the student works from the picture of the same table
at the same moment, which is the same information in a different form. So the
student has to recover from a picture what its teacher was given as numbers,
and any push that depended on a difference of a millimetre between two readings
is a push the student is being asked to justify from pixels. And the jaw's
report of what it felt during the push — the force, and how far it travelled
before touching — arrives after the chunk has been chosen, so it is in the
recording but not in the observation the model is asked to act on.

**That makes the data free in the sense that matters, and it is worth saying
why that is a privilege of working in a simulator.** On a real arm this is the
expensive part of the whole exercise and usually the part that decides whether
a method is affordable at all: somebody sits with a controller and teleoperates
the task hundreds of times, the recordings disagree with each other, and the
robot wears out. Here a program does it unattended. Any judgement made in this
folder about whether fine-tuning is worth its price should carry that
qualification, because on a real arm the price would be quite different.

**But free data is not neutral data, and this solution inherits two things
from its teacher that have to be said without softening.**

**Its ceiling is solution 2.** Behaviour cloning fits the teacher's choices.
There is no reward in it, nothing scores the policy's own attempts, and nothing
ever shows it a push better than one the teacher made. So on the pushes it
imitates, this solution cannot be better at pushing than solution 2 is at its
best. If this solution scores above solution 2 on the scorecard, that is a
result that needs explaining rather than a result to celebrate, and the next
section gives the one explanation that is honest.

**Filtering to successes trains it on a biased sample of its teacher.** A
demonstration that toppled a glass, pushed one out of the zone or ended in a
jam is not something to imitate, so those recordings are discarded. That is the
right thing to do and it has a cost that is easy to miss: what is discarded is
exactly the set of situations the teacher handled badly. What is left is a
picture of solution 2 in the cases where solution 2 was right. The policy is
therefore fitted on the easy half of its teacher's own experience, and the hard
half — the glass that stuck, the jaw that met a neighbour first, the push that
went nowhere — is missing from its training by construction.

**On this bench that half is tiny, and knowing the size changes what the
argument is worth.** Solution 2 is good enough that 9 pushes in 2,021 had to be
discarded. So the missing hard half is not a hole in the training set; it is
nine examples. What this really says is something less comfortable than the
usual worry: the hard cases the teacher handled badly are nearly absent not
because they were filtered out but because the teacher almost never meets one,
and a student fitted on that set has never been shown a difficult table because
the teacher does not produce difficult tables. DAgger is still the repair, and
it is the repair for a different reason than the filtering: it would put the
*learner* in states the teacher never visits, and there are plenty of those
however good the teacher is.

**So what can fine-tuning add beyond its teacher?** One thing, and it is worth
being precise about it, because it is the only honest claim in this direction.
Not better pushes: the best push in the training set is the best push the
policy has ever seen. What it can add is **robustness in situations the teacher
handled badly**. Where the teacher's ranking was close to arbitrary between two
candidates, averaging over many tables gives something less arbitrary than
either. Where the teacher's geometry was brittle because a measurement was a
couple of millimetres out, a policy fitted on what actually happened across
many such cases can behave sensibly rather than following the arithmetic into a
mistake. And the borrowed weights contribute a general sense of how a pushing
motion goes, which is a thing the teacher does not have at all, because the
teacher's motion comes from a macro. That is the whole of the upside, and it is
about not falling over in unfamiliar situations rather than about pushing
better.

The standard repair for the missing hard half has a name and it is cheap here.
**DAgger**, dataset aggregation, runs the half-trained policy, lets it reach
states the teacher never visits, and asks the teacher what it would have done
at each of those states. The dataset then covers where the learner goes rather
than where the teacher goes. It normally costs a person to label every such
state; here it costs a call into solution 2, which is a program. This is a
prescription in this document rather than code that exists, and it belongs to
this solution and to solution 3 equally, since both learn from the same
demonstrations.

One last point about the data holds the comparison with solution 3 still. Both
solutions learn from the same demonstration set, drawn from the same training
half of the tables. So between those two the data is held still and the
borrowing is what differs, which makes that pair a test of whether borrowed
weights are worth having when the examples are the same. This solution is
therefore in two pairs at once, and they ask different questions.

## Whether anything but the training differs

A matched pair invites one particular mistake, and it is the mistake of saying
that nothing varies except the training when something else does. [Problem
2's own pair](../../02-segment-glasses/solutions/04-yolo-fine-tuned.md) shows
how to avoid it. There, the fine-tuning also replaces the model's borrowed list
of everyday categories with a single class, and that document does not claim
otherwise. What it does instead is show that the second change comes **with**
the training and cannot be had separately, so that nothing varies which the
training did not bring. The same care is owed here, but that answer cannot
simply be carried across, so it has to be worked out: beyond the weights, what
else is really different between solution 5 and this one?

Going through the contract item by item, most of it is genuinely held still.
The tables are the same tables, drawn from the same numbers, and the first look
at a given table is identical for every solution. The readings carry the same
error. The rendered view from the top is the same view. The output is a chunk
of waypoints in both. The marking is the same scorecard. The shared topple
check runs on both, unchanged. And the instruction in words is the same
instruction, because the task has one — which is a thing to keep deliberately
rather than assume, since giving the fine-tuned model a better-worded
instruction would quietly add a second variable to the pair.

**At the output there is something that looks like a second change, and it is
worth seeing why it is not one.** A model like this produces numbers in an
action space: so many values per waypoint, each with a range and a meaning
fixed by the robots the model was fitted on. This cell's action space is not
one of those. It is a jaw, held level, travelling a short distance across a
table at one height, on an arm the borrowed recordings were not made on. So the
numbers the model returns have to be read as waypoints for this jaw, and
[solution 5](05-smolvla-as-it-downloads.md) sets out what that reading involves
and settles it: **the convention is chosen once and used by both**, so that
what a waypoint number means, which frame it is in and where a height of zero
sits are the same in both halves of the pair. That is held still, and it has to
be, because a pair is only clean while everything except the training is held
still.

What the training changes is not that convention but whether the model has
ever been asked to speak in it. Solution 5 depends on the borrowed model
happening to emit numbers that, read through the agreed convention, make sense
for this table; nothing fitted them, so nothing guarantees their scale. This
solution's training targets are recordings of real pushes on this bench,
already expressed in that same convention, so the ranges the model is trained
to produce are this cell's ranges. **That is a property of the trained weights
rather than a second thing changed beside them.** Problem 2 needed its
argument because its second change was a real one: a list of category names is
part of how a model is configured and not only a value inside it, so it could
in principle have been altered without any training, and that document had to
show that the training forced it. Here there is no such separate part. The
configuration, which is the convention for reading an action, is held still for
both, and the scale of what comes out is whatever the weights emit, so saying
the weights were trained and saying the scale moved are one statement said
twice. So **nothing varies between the two that the training did not bring**,
and the pair is a clean measurement.

**One thing the convention settles turned out to reach into the physics, and it
is worth naming because it was not obvious until the code was written.** A
chunk holds the number of waypoints the borrowed model emits in one pass, which
is fifty, and the bench consumes waypoints a fixed period apart, so a chunk is
two and a half seconds of motion whatever it contains. The teacher's push, once
the bench has sampled it, is a hundred waypoints or more, because the teacher
feels forward at 10 mm/s and pushes at 20. Fitting that push into a chunk means
resampling it, and resampling it means the student's jaw travels about 36 mm/s
where its teacher travelled at 10 and 20. So **the student does not merely
imitate its teacher's pushes; it makes them faster**, and the glasses are
pushed by a jaw with more momentum behind it. It is not free to go as fast as
it likes: the bench holds a commanded path to the jaw's top speed of 200 mm/s,
past which a leg simply takes longer, so spacing buys speed only up to the
speed the arm has. A demonstration's 36 mm/s is nowhere near that, but a
chunk the model invents can be, and then the cap decides how fast the push
really is. This is forced rather than
chosen: the alternatives are to change the chunk length, which is the borrowed
model's own, or to ask the model several times during one push, which would
spend several of the shared budget's pushes on one. It does not disturb the
pair, because solution 5's chunks are two and a half seconds of motion too.

**There is one place where the pair could nonetheless be made unfair, and it
should be named rather than hidden.** The agreed convention is a choice, and a
careless choice hurts solution 5 much more than it hurts this solution, because
this solution's training can absorb a poor convention while its partner's
cannot. If the convention puts the borrowed model's natural range badly out of
scale for this table, solution 5 fails at something other than the question
being asked, and the gap this pair reports is then the sum of what training
bought and what a careless convention cost, with no way to separate the two
afterwards. So the convention has to be chosen as well as it can be, recorded
with solution 5, and left alone once both have run.

## What fine-tuning closes, and what it cannot touch

This is the section the matched pair exists for. Solution 5's weaknesses are
known, and the honest exercise is to go through them one at a time and say
which the training repairs and which it inherits untouched, rather than letting
"it is fine-tuned" stand in for an answer.

**The domain gap closes, and this is the large one.** Solution 5 is shown a
kind of input it was never fitted on, and a model used across such a gap fails
in a characteristic way: not by producing nonsense, but by producing confident,
plausible, wrong answers, which is worse because nothing further along looks
suspicious. A chunk of waypoints that is smooth and well formed and aimed at
nothing in particular is exactly that kind of failure.

**That gap has now been measured, and the number is larger than the prose
suggests.** Before the training has taken a single step the correction is
still zero, so the model is exactly solution 5, and asking it for a chunk on
tuning tables the teacher had also been run over puts its waypoints a median of
**320 mm** from the teacher's, and 660 mm away at worst. The glass zone is
320 mm by 360 mm. So the borrowed model's answer is not a push aimed at the
wrong glass; it is a smooth motion somewhere else on the table entirely, which
is what reading a model across a domain gap this wide actually looks like.

Fine-tuning removes the gap by construction, because the inputs the model is
fitted on are the inputs it will be asked about. The pale blue of a glass against the tan of the table,
the same blue whatever the kind, the outline leaning outwards from the point
below the camera, the bare table, one kind of glass to a table: all of those
are simply what a table looks like, as far as the fine-tuned model is
concerned, because that is what every table in its training set looked like.

**The scale of the actions stops being left to chance**, for the reason the
previous section gives. The model is trained towards recordings of real pushes
on this bench, so the size of the motion it proposes is the size this table
needs, rather than the size the borrowed recordings happened to use.

**That turns out to be two claims, and only one of them held.** The *height*
was learned, and convincingly. Solution 5 measures its own chunks and reports
that they come no lower than 247 mm above the table: the borrowed model
essentially never brings the jaw down to the glasses at all. The fine-tuned
model's chunks come down to 50 mm, which is the height the gripper pushes at.
That is the model having learned from this bench's own pushes that a push
happens on the table rather than above it, and it is the clearest single sign
in these measurements that the domain gap closed.

The *length* was not learned. The fine-tuned chunks still cover about 310 mm
of table where the teacher's covered 89, at about 90 mm/s where the teacher
pushed at 20 — better than solution 5's 964 mm, and still three times too far.
So the model learned where a push happens long before it learned how far one
goes, and a push three times too long on a crowded table is a push into a
neighbour. The toppled count in the folder's README is that. The honest answer
to "does the scale of the actions stop being left to chance" is therefore:
partly, and the part that was left is the part that topples glasses.

**Something like friction is absorbed, and this one needs care rather than
celebration.** Nothing in the cell measures friction and the bench never
reveals it, so neither solution can know it. But the bench holds the same three
coefficients on every table, and every demonstration was produced under them.
So a fine-tuned policy can absorb this bench's own friction into its weights
without any term in it standing for friction: it learns how far a glass of this
kind tends to go for a push of this length, which is a consequence of the
friction it was never told. That is a real gain on this bench and a liability
anywhere else. What the model holds is a constant, not a way of measuring one.
Change the table and the policy is confidently wrong in exactly the direction
that topples a glass, because the height at which a glass slides rather than
tips is set by that same coefficient. So part of whatever this solution gains
over its partner is a memorised property of the bench, and that part would not
survive the move to a real table. Solution 5 has no such memory — and no such
ability either.

Now the weaknesses that survive.

**The force reading still has nowhere to go.** [The test
bench](../the-bench.md) calls the jaw's report of what it felt the only channel
through which friction is observable at all, and this model's inputs are a
picture, a sentence and the joint readings. Training cannot add a fourth input,
so that channel stays closed in both halves of the pair, exactly as [solution
5](05-smolvla-as-it-downloads.md) describes it. What the training gives instead
is the absorbed constant above, which is not a way of reading the channel.

**The instruction is still nearly dead weight.** SmolVLA is a
vision-language-action model, and the language is the part that lets one model
be told to do different things in different words. Problem 3 has one task, so
there is one instruction, and the same words go in on every table. Fine-tuning
does not change that, because the task is what it is. Worse, the training makes
it harder to pretend otherwise: when every example in a training set carries
the identical instruction, nothing in the training penalises a model for
ignoring the language channel entirely, so the sensible expectation is that the
fine-tuned model learns to ignore it. That is a fact about a cell with one task
and not about the language half itself, which this problem never asks for, so
nothing here is evidence for or against vision-language-action models in
general. The model is therefore paying for a capability neither solution uses,
and that cost appears in its size, in its memory and in the price of its
forward pass. It is a real argument for [solution
3](03-imitation-from-demonstrations.md), whose ACT policy carries no language
machinery at all and is far smaller for it.

**The refusal still is not the policy's, and it cannot become the policy's.** A
policy is a function from an observation to an action; there is no field in it
for a rule, so there is no way to tell it never to topple a glass. The topple
limit therefore stays where [pushing without
toppling](../pushing-without-toppling.md) puts it, outside all six solutions,
as a check that reads every proposed push before the jaw moves. Fine-tuning
leaves that exactly as it was, and in one respect it makes the policy's own
behaviour here worse rather than better. The demonstrations were filtered to
successes and the teacher refused the glasses it should refuse, so the training
set contains no example of a glass that must not be pushed. The policy has
therefore never been shown the case. It will propose a push on such a glass as
readily as on any other, and the shared check will stop it. The safety work is
being done by the geometry, in both solutions, and that should not be credited
to the model in either.

**It still cannot explain a refusal.** Solution 2 can say that a glass tips
before it slides because its foot is narrow enough that the limit falls below
the jaw's top edge, and the number can be printed. A policy that was stopped
has nothing to say, and this project treats a refusal as a result that has to
carry a reason. So the reason comes from the shared check, not from the model,
in both halves of the pair.

**A surprise in the middle of a chunk is still carried out.** The model commits
to a short run of waypoints at once, which is the mechanism that keeps it
steady over a motion rather than wobbling from one step to the next, and it is
the reason [the bench](../the-bench.md) accepts waypoints at all instead of
forcing every solution down to three numbers. The cost of committing is that
something unexpected during the chunk — a glass that sticks, a neighbour met
earlier than the readings implied — is met by a policy that is still executing
what it decided before. Fine-tuning changes how often a surprise arrives, by
making the predictions better suited to this table. It does not change what
happens when one does.

**And the thing that was supposed to act inside a push is not built.** The
early abort — the monitor that reads the jaw's force as the push develops and
stops it the moment the contact stops behaving like a slide — is a design in
[pushing without toppling](../pushing-without-toppling.md) and nothing in the
bench does it. What the bench does is stop at a jam, which is a much higher
force than a glass beginning to tip, and `follow()` is explicit that below that
level the chunk is carried out as it was given, because carrying it out as
given is the point of accepting one. So a surprise inside a chunk is not caught
by anything today. That falls on solution 5 and this solution equally, so it
does not disturb the pair; it does mean the pair's topple counts are what the
limit computed before the jaw moves achieves on its own.

**The run-time cost is unchanged.** It is a large neural network forward pass
per chunk in both, since the correction folds into the weights, and that cost
is why the scorecard carries a compute column at all.

**And the input's own error is unchanged.** Both solutions are handed readings
that carry problem 2's measured error, and no amount of training makes a
measurement truer than it was. What training can do is make the policy behave
sensibly when a reading is a little wrong, because it was fitted on recordings
in which readings were a little wrong. That is a different and smaller claim
than making the reading right.

## Two ways training on one cell's pushes goes wrong

Fine-tuning is cheap and it is not free of risk, and the two risks have names
worth knowing.

**Catastrophic forgetting.** Continuing a model's training on a narrow set of
examples moves its weights away from the general answer they held, so the model
becomes better at this cell and worse everywhere else. Low-rank adaptation
softens this, for a reason worth understanding rather than taking on trust: the
borrowed numbers are never overwritten, so what was general is still in there,
and the correction can in principle be removed to get the original model back.
Softened is not absent. The corrected model is the one that runs, and at run
time it describes a world of rendered tables with one kind of glass to a table.
It would be a poor policy for any other robot or any other task, and asking it
for one would be asking it about a world it was trained away from. Within this
project that is not a loss, because the only tables this model will be shown
are this bench's. It does mean the correction is a narrow asset that has to be
kept in step with the cell, and that is one more thing to maintain rather than
a fixed file to keep.

**Overfitting.** A model fitted on a small set of examples can learn the
examples instead of the thing the examples are of. Here that would mean
learning the tables rather than the pushing: which parts of the glass zone tend
to hold a glass, how many glasses tend to be present, which crowded pairs the
bench likes to draw, and in the worst case which push follows which table. Such
a policy scores well on the tables it was trained on and poorly on new ones.
Two things guard against it, and the bench already provides both. The tables
are numbered and the numbers are split, so no solution is ever marked on a
table it learned from, and overfitting appears as a gap between the two halves
rather than hiding inside one number. And the demonstrations cost only
simulator time, so the training set can be made large and varied for nothing,
which is the cheapest defence against overfitting there is.

The two risks pull in opposite directions in one respect, and knowing that
saves confusion. Training longer and harder on this bench's pushes closes the
domain gap further while making both forgetting and overfitting more likely. So
there is a sensible amount of training rather than a maximum, and the held-out
half of the tables is what decides where it is.

A third thing is not a risk of training but a consequence of it, and it belongs
here because it decides how this solution is measured at all. A policy of this
kind is stochastic: asked the same question twice it may act differently,
because the action is drawn rather than computed. Training itself varies with
its own random seed, so the same recipe run twice gives two policies of
different quality. [The bench](../the-bench.md) requires several training seeds
and several evaluation runs for exactly this reason, and the scorecard carries
the spread. **This matters most to this document of any in the folder**, because
the thing being measured is the gap between two solutions, and a gap smaller
than either solution's own spread has not been shown to exist.

## A second rung: the same fine-tune on a larger model

Everything above is about one model, and there is an obvious next question that
one model cannot answer: would a markedly larger foundation model do better?
That question is this solution's second rung.

**The rung is the same fine-tune on π0.5.** The same demonstrations, the same
low-rank adaptation, the same bench, the same marking, with a much larger
borrowed model in the middle. Because everything except the model is held
still, the gap between the two rungs measures what size is worth on this task,
in the same way the gap between this solution and solution 5 measures what
training is worth. It is also less work than it sounds: the version of LeRobot
this problem installs carries π0.5 beside SmolVLA, so the rung is the same
training loop pointed at a different policy and a different set of weights,
rather than new machinery. What it is not is affordable here, and that is the
whole of why it stays a prescription.

**Its cost is a weekend on a rented accelerator, which is of order a hundred
dollars.** That is honest and it is not nothing. It is also the affordable
corner of this family: π0, which belongs to it too, holds about 3.3 billion
parameters, and a full fine-tune of it needs more than 70 GB of accelerator
memory, which is why no full fine-tune of a model this size appears anywhere in
this folder. Low-rank adaptation is what brings a model of that size within
reach at all, and it is the only way the rung is reached.

**It is a rung rather than the main line for one practical reason, and the
reason is about where mistakes are found.** Almost everything that will go
wrong in this solution is in the pipeline rather than in the model: rendering
the view from the top, recording the demonstrations in a form the training loop
accepts, carrying the action space across, choosing how long to train, and
getting the evaluation to run the trained policy against the bench at all. Each
of those is found by a run that fails. SmolVLA uses a few gigabytes at
inference and runs on a laptop, so on the small model every one of those
mistakes is found for nothing, and only a training run that is already correct
ever reaches rented hardware. Starting on the large model instead means
debugging a pipeline at a hundred dollars a weekend, which is how a budget
disappears without a single comparison being produced.

So the order is: get the small model working end to end, measure it against
solution 5, and only then rent the accelerator for the weekend that answers
whether size helps. If the small model's fine-tune turns out to buy little, the
rung is also the thing most worth trying next, because "a larger model" and "a
full fine-tune rather than a low-rank one" are the two directions the result
leaves open, and only the first of them is affordable here.

## The pushes are what this contributes

One point about the output has to be clear, because it decides what the
comparison with solution 5 is a comparison of.

**This solution contributes action chunks and nothing else.** It does not
compute where the glasses should end up: that is [the target
layout](../the-target-layout.md), computed once from the measurements and handed
to all six, so that no solution can look good at pushing by having aimed at an
easier arrangement. It does not own the topple check, which is shared. It does
not own the loop of plan, feel and look again, which is shared. And it does not
own the macro that turns a parameterised push into a jaw trajectory, because it
never produces a parameterised push; it emits waypoints, and the bench carries
them out as they are.

That last point is worth one more sentence, because it is the reason this
solution is allowed to be itself. The bench could have insisted that every
solution hand back the same handful of push parameters, which sounds fairer and
is not, because squeezing a chunked policy down to three numbers destroys the
action chunking that makes it work. What the bench does instead is score the
outcome and never the action: which glasses have room, which are standing,
where each one ended up, and how many pushes it took. So a three-number push
and a chunk of fifty waypoints are compared on the only thing problem 3
actually cares about, which is the table afterwards.

It follows that **a difference in the score belongs to the chunks**. This
solution contributes the chunks and so does solution 5, which is exactly why
the gap between the two is readable.

## How the concepts fit together

The pieces now join into one picture, and it is worth having that picture in
one place before the question every solution document in this folder has to
answer.

A model fitted on a very large pool of other people's teleoperation is
downloaded, and its borrowed numbers are kept rather than replaced. Solution 2
is then run over the training half of the tables, and every push it makes is
recorded together with the view from the top, the one instruction and the joint
readings that were true at that moment. Those recordings are the examples, the
ones in which something went wrong are discarded, and the training moves a
small low-rank correction beside the borrowed numbers until the chunks the
model emits look like the teacher's pushes. The correction is then folded into
the weights, so what runs afterwards is a model of the original size and the
original speed.

What that buys is the domain gap closed, because the pictures the model was
fitted on are the pictures it is shown, and actions on this cell's own scale,
because the targets it was trained towards were this cell's own pushes. What it
does not buy is anything the model has no input for, anything the teacher never
did, and anything the shared machinery owns. The section on what fine-tuning
closes and what it cannot touch is those gains and those limits taken one at a
time.

## When a glass cannot be pushed safely

Every solution document in this folder answers this question, and this one's
answer is short, because the answer does not come from the model.

A glass slides while the jaw's contact height is below half its foot width
divided by the friction coefficient, and tips above it. The height that counts
is the **top edge of the jaw**, which stands at 65 mm because the jaw rides as
low as the gripper goes, at 50 mm, and is 30 mm tall. For a glass whose foot is
narrow enough, the limit falls below 65 mm, and there is then no contact height
the arm can offer that is below it. Such a glass tips before it slides whatever
the arm does, and **the only correct answer for it is to refuse**, with the
reason recorded. A refusal is a result, and a run that refuses the glasses it
should refuse is marked *correct but incomplete*, which is a good outcome.

**That check is not this solution's and cannot be made this solution's.** It
belongs to [pushing without toppling](../pushing-without-toppling.md), where it
is explained once for all six, and it runs on every glass before the jaw moves.
In code it is `slides` in `01-one-fixed-nudge/plan.py`, which is worth saying
because that is not where a thing shared by six solutions would naturally sit.
There is no shared module for it: solutions 2, 3, 5 and this one all reach into
solution 1's folder for the same arithmetic rather than each writing it out, so
the six do refuse the same glasses, but by borrowing rather than by sharing.
The reasons it has to sit outside the policy are worth repeating in
one place, because they are easy to lose in the middle of a document about
training. A policy has no field in it for a rule, so it cannot be told. Its
training set contained no refusals, because the teacher refused those glasses
and the recordings that remain are of pushes that happened, so it has never
seen the case. And the cost of being wrong is not symmetric: a glass left
standing with a reason can be revisited by anything later in the project, while
a glass that went over is finished, because nothing in this project can stand a
glass back up.

So this solution's honest position is that it proposes and the shared geometry
disposes. **This is the one place where this solution and its untrained partner
are guaranteed to behave the same**, because the thing that decides the outcome
is the same code in both, reading the same readings, applying the same
arithmetic. Any difference in the refusal counts between the two comes from
their pushes having left the glasses in different places, not from either of
them being better at refusing.

Two qualifications keep that from sounding safer than it is. The check needs
the friction coefficient, nobody has it, and the limit it computes is only as
good as the guess. And the guard against a guess that was too generous — the
early abort that reads the jaw's force while the push is happening and stops it
when the contact stops behaving like a slide — **is a design and not code**.
The bench stops a push at a jam, which is far more force than a glass needs to
begin tipping, and nothing reads the force as it develops. So the only thing
protecting a glass in either half of this pair is the limit computed before the
jaw moves, and a 5 mm test push where that limit is undecided.

## A worked example

Follow one table through, because the difference from solution 5 is easier to
recognise once both have been run over the same one.

**The table.** Five tapered glasses stand in the glass zone, drawn at
proportions from across the kind's range, so they are not all the same height.
Two of them stand as close together as the bench allows, so neither has its
70 mm of clear room measured to the other's edge, and because the test is to
the edge rather than to the middle, the narrower of the two is crowded while
the wider one may not be. A third glass, standing alone, is drawn with a foot
narrow enough that its limit falls below the jaw's top edge. The bench renders
the view from the top and hands over the readings, each carrying problem 2's
error.

**What solution 5 would do.** The downloaded model is shown a rendered view of
a kind it has never seen — pale blue glasses, opaque, shaded, standing on a
tan table — together with an instruction, and it returns
a chunk of waypoints on the scale of robots that are not this one, read
through the convention the pair agreed in advance. What comes out is a smooth,
well-formed jaw motion whose relationship to these five glasses is genuinely in
doubt — it may come down in open table, or behind the wrong glass, or behind
the right glass pointing the wrong way. Nothing in the output looks wrong,
which is the characteristic failure of a model used across a domain gap.

**What this solution would do.** The corrected model is shown a view of a kind
every example in its training set looked like, and returns a chunk in this
cell's own units. The expected shape of that chunk is the shape its teacher's
pushes had: the closed jaw travels to a point behind the crowded glass, on the
line leading away from its neighbour, comes down to the lowest height the
gripper reaches, feels forward until it touches, and pushes. That is what
solution 2 does, and this solution was fitted on recordings of it doing so.

**Where this solution is only as good as its teacher.** Which of the crowded
pair to move is a choice solution 2's ranker makes, and on a pair like this one
it is close to arbitrary, because moving either one would give both their room.
The policy inherits whatever the ranker tended to do, averaged over many
tables. It does not improve on the choice, because nothing scored the choice;
it only makes it more consistently than a ranker whose answer flips on a
millimetre of measurement error.

**Where the look-again loop does the work in both.** The pushed glass does not
land where it was aimed, because the friction guess was wrong and a glass
rotates as well as slides. The arm looks again and sees where the glass really
is. Here the two halves of the pair diverge in a way the scorecard can see: the
fine-tuned policy has been fitted on many recordings in which a glass landed
short, so its next chunk is of the kind that followed a short landing in
training, while the downloaded model is in the same position it was in before
and has learned nothing from the attempt. Neither of them improves its own
model of pushing during the run, because neither is being trained at run time.
What differs is whether the model had ever seen this situation at all.

**And the case neither can answer.** The third glass, with the narrow foot,
cannot be pushed safely. The shared check computes the limit from the glass's
measured foot width and the jaw's top edge, finds it below 65 mm, and refuses
that glass with that reason before either model is asked anything. The glass is
left standing and the table is marked *correct but incomplete*. The refusal,
its reason and its correctness belong entirely to the shared geometry.

**But the refused glass stays in the picture, and that is the part the code
had to settle.** Neither model can be told to leave it alone — there is no
field in a policy for a rule — so a chunk whose path runs into a refused glass
is simply not carried out. That check reads the path, which is something the
geometry can only do once the model has answered, so it costs one of the
table's pushes every time it fires: an answer was asked for and spent, and the
model cannot be asked for a different one. Both halves of the pair pay that in
the same code, which is why it does not disturb the comparison, and the counts
in each folder's `asking.json` say how often it happened.

The honest summary of the example is that fine-tuning changes the first half of
it and not the second. The chunk becomes a push aimed at a glass on this table,
in units this cell can carry out, informed by what pushes on this table
actually did. The refusal, the topple limit, the destinations and the loop are
exactly where they were, because they were never the model's to begin with.

## What it needs

It needs **LeRobot**, which is Apache-2.0, and the SmolVLA weights, which the
library fetches by itself. That file is large, it comes from outside the
project, and it is not something to commit beside the code. The terms on the
weights are the thing to read rather than the terms on the library, because a
file produced by continuing their training inherits whatever they carried, and
no amount of training here relicenses it. It needs **PyTorch** underneath,
which is what both the training and the forward pass run on.

It needs **the two parts of the bench this solution waited on**, and both are
there now. A rendered view looking straight down is the input this model takes,
and `bench/top_view.py` is that view: a camera fixed 750 mm above the middle of
the glass zone, looking straight down, returning a 384 by 384 picture that
frames the whole zone. It is separate from the camera the films use, which
looks steeply down from the arm's side. A path by which a chunk of waypoints is
carried out as an action is the output this model produces, and `Bench.follow()`
is that path: it takes the waypoints as they come, consumes them a fixed period
apart, and reports the same record a parameterised push does, so the scorecard
cannot tell which door an action came through. Neither was hard, and both were
the real price of going off the shelf, because every LeRobot policy expects
pictures and an action space at control rate.

It needs **solution 2 built**, because solution 2 is the teacher and its pushes
are the training set. It needs **simulator time** to record those pushes over
the training half of the tables, unattended, and a filter that discards the
recordings in which something went wrong. It needs the **held-out half** of the
tables, which the bench already enforces, for checking that the policy learned
pushing rather than the tables.

**It does not need a rented accelerator, and this is the place the document
was wrong.** The training runs on this machine, an Apple Silicon Mac with no
NVIDIA card, through Metal. Measured while it ran: **1.02 GiB held**, with the
borrowed weights, the correction, the correction's gradients and the
optimiser's running averages all in memory at once. Low-rank adaptation is
exactly why, and for exactly the reason the section above gives — only the
correction's four million numbers carry gradients and optimiser state, so what
has to be held is the model plus a little. What the writing got wrong was how
little "a little" is at 450 million parameters. Memory was never close to being
the obstacle.

**What renting buys here is time, not memory, and that distinction matters
because time is what this solution is actually short of.** A training step on
Metal takes a second or two where an NVIDIA card would take a fraction of one,
and LeRobot's own SmolVLA fine-tune is twenty thousand steps at a batch of
sixty-four. What ran here is a thousand at a batch of four, which is a small
fraction of that compute, and **every number this solution reports carries
that caveat**. A step took about four seconds, on a laptop that was also
running three other solutions' training at the time. Renting is still how real compute would be spent on it:
hours of a small accelerator is of order tens of dollars, a weekend of order a
hundred, and a month of order five hundred, which is the scale to keep in mind
if the training has to be repeated over several seeds. None of it was spent.

The project's old rule was that everything must run on this machine, and [the
plan](../solutions-plan.md) lifts that rule for problem 3 so that each solution
states what it needs and roughly what renting it costs, in the same way a
licence is stated. **The lifting turned out not to be needed for this
solution**, which is the opposite of what this section first claimed. Where it
is still needed is the second rung: π0, which belongs to the same family, holds
about 3.3 billion parameters and its full fine-tune floor is above 70 GB, and
there the question really is whether the training fits. At 450 million it was
not a question. And **the trained model runs here perfectly well** too,
because SmolVLA uses a few gigabytes at inference, so neither building this
solution nor using it needed anything rented.

And once trained, it needs **a correction kept in step with the cell**. Change
the camera, the way the view from the top is rendered, the range of proportions
a kind is drawn from, or the teacher, and the file is quietly out of date in a
way no test of the code would notice.

## Where it is strong and where it breaks

**It is fitted on the inputs it will be shown.** That is the single strongest
thing about it, and the thing its partner cannot claim. The domain gap is
closed by construction rather than left to hope.

**Its demonstrations cost nothing.** The teacher is a program, so the usual
reason not to fine-tune a policy — that somebody has to teleoperate the task
hundreds of times — does not apply here.

**It needs no reward function.** That is a larger advantage than it sounds,
because a reward is a score and what this problem has are constraints. Written
as a fine, "never topple a glass" becomes a price, and a price is a trade the
policy may make. Learning from examples of correct pushes leaves "never topple"
as a constraint the teacher enforced and the shared check enforces again.

**Its training is affordable, and its run-time cost is its partner's.** The
low-rank correction fits in the memory of a laptop, which is further than this
document expected it to go, and it folds into the weights afterwards, so
nothing about running it is more expensive than running the model as it
downloads.

**It is one half of the cleanest comparison in this folder**, and that is a
strength of the arrangement rather than of the model.

Against that, four kinds of weakness.

**What it inherits from being a borrowed model.** It is about 450 million
parameters, and a large fraction of them serve a language channel this task
does not use, because there is one instruction. It commits to a chunk, so a
surprise inside a push is carried out. It cannot explain anything it did. And
the correction is low-rank, so it adapts less deeply than a full fine-tune
would, which means it may leave part of what fine-tuning could buy unclaimed.

**What it inherits from its teacher.** Its ceiling is solution 2, because
nothing ever showed it a better push and nothing scores its own attempts. Its
training set was filtered to successes, so it was fitted on the easy half of
its teacher's experience and has never seen the hard half. And it has seen no
refusals at all, so it proposes pushes on glasses that must not be pushed.

**What it owes to being trained on one bench.** It becomes good here and worse
elsewhere. Part of what it gains over its partner is this bench's own friction
absorbed into its weights, which is a memorised constant rather than an ability,
and it would not survive a real table. A small or uniform training set would
teach it the tables rather than the pushing, and only the held-out half would
reveal it. And it is stochastic, so a single run is not a measurement, which
bears on this document more than on any other in the folder, because what is
being measured here is a gap.

**What it does not do at all.** It does not refuse, it does not choose
destinations, it does not own the loop, and it does not stop a push that is
going wrong. Each of those belongs to the shared machinery, and a reader who
credits the model with them is crediting it with the geometry's work.

## The general ideas behind this

Nothing in this solution was invented for glassware. Every part of it is a
standard piece of current practice, and each is worth knowing on its own,
including where it is normally the wrong tool.

### Transfer learning and fine-tuning

Take a model fitted on a large general task, keep its weights, and continue
training on the new data. It works because the early layers of a model learn
things common to the whole domain — edges and textures for vision, smoothness
and approach for motion — and only the later layers learn what is specific to
the original task. Yosinski and colleagues
([arXiv:1411.1792](https://arxiv.org/abs/1411.1792)) measured that directly for
vision, showing how well a layer transfers falling away with depth.

It is normally the right choice whenever data for the real task is scarce,
which is almost always. It is normally the wrong choice when data is free and
plentiful **and** the new task looks nothing like the borrowed one, because
then the borrowed weights bring knowledge of a world you do not have while also
forcing your model to be the size somebody else chose. This solution sits
awkwardly between those two, since its demonstrations are free and its inputs
are unlike anything in the borrowed datasets, which is precisely the argument
[solution 3](03-imitation-from-demonstrations.md) makes and this one
deliberately takes the other side of. For more, see [transfer
learning](https://en.wikipedia.org/wiki/Transfer_learning).

### Low-rank adaptation

Instead of changing every weight, add a correction forced through a narrow
squeeze, so that only a small number of new values have to be learned and
stored. The method is **LoRA**, Hu and colleagues
([arXiv:2106.09685](https://arxiv.org/abs/2106.09685)), and it is the standard
way a large borrowed model is adapted on modest hardware.

It is right whenever the model is too large to fine-tune fully and the new task
is near enough to the old one that a small correction can express the change.
It is wrong, or at least limiting, when the new task is far from the old one,
because a correction confined to a few directions cannot hold a change that
needs the whole of a weight table. It is also the wrong tool when the model is
small enough to fine-tune fully for the same money, since then the constraint
buys nothing. Here the model is small and the task is far, which is an
uncomfortable combination and the honest reason the result reads as a lower
bound.

### Behaviour cloning, and its ceiling

Record what a working expert did at each moment, and fit a model to predict the
action from the observation. It is ordinary supervised learning, with no reward
and no exploration, which is what makes it cheap and stable. The price is that
the expert is the ceiling, and that the policy only ever sees states the expert
visits.

It is right when a correct expert already exists and the thing wanted is a fast
or more robust version of it, which is the case here. It is wrong when the
expert is the thing you were trying to improve on, because imitation cannot
exceed what it imitates. The classic failure is **compounding error**: the
policy is slightly wrong, so it drifts into states the demonstrations never
covered, where it is more wrong. **DAgger** (Ross, Gordon and Bagnell, 2011) is
the standard repair, and it is unusually cheap here because the expert is a
program that can be asked for a label at any state.

### Domain adaptation

A model fitted on one kind of data and used on another is working across a
**domain gap**, and the family of methods for closing it is **domain
adaptation**. Fine-tuning on data from the new domain is the simplest member of
that family and the strongest when such data exists.

It is right whenever examples of the real input can be obtained, as here. It is
unavailable when they cannot, and then the harder members are needed: adapting
with no labels, or varying the training data so widely that the new domain
falls inside the range already covered. That second one, **domain
randomisation**, is the usual answer when a policy trained in a simulator has
to work on a real robot, and it is worth knowing here because the problem it
solves is the mirror image of this one. It is also the thing that would have to
be added before any of this reached a real table, since a policy that absorbed
one bench's friction has learned a number rather than a skill.

### Catastrophic forgetting

A network trained on a new task tends to lose what it knew of the old one,
because the weights that held the old knowledge are the weights the new
training moves. The effect was first described for simple networks by McCloskey
and Cohen, and the modern treatment protects the weights that mattered most to
the old task (Kirkpatrick and colleagues,
[arXiv:1612.00796](https://arxiv.org/abs/1612.00796)).

It matters a great deal when a model has to stay good at several things, which
is why continual learning is a field at all. It matters little here, because the
model is wanted for one bench and nothing else, and that is the honest reason
the usual precautions are not taken: not that the effect is absent, but that its
cost in this project is close to zero. Low-rank adaptation happens to soften it
for free, since the borrowed weights are never overwritten and the correction
can be removed.

### Overfitting and the held-out split

A model fitted on a finite set of examples can fit accidents of those examples
rather than the thing they are examples of. The standard defence is to divide
the data, fit on one part and measure on another, so that any such accident
shows as a gap between the two scores.

It is the right practice everywhere and there is no case against it. Its usual
difficulty is that data is scarce, so dividing it hurts. That difficulty does
not arise here, because tables are generated from numbers rather than collected,
and more of them cost only simulator time. For more, see
[overfitting](https://en.wikipedia.org/wiki/Overfitting).

### Action chunking

Predict a short run of consecutive actions in one pass rather than one action at
a time. It is the mechanism behind ACT and it is what SmolVLA emits. One action
at a time makes a policy dither, and dither during a push is a knock; a chunk
commits to a smooth short motion, which is what a push is, and it also cuts the
number of decisions per table, which matters because compounding error compounds
per decision.

It is right for smooth contact-rich motions, which is what this problem has. It
is wrong where a fast reaction inside the chunk is needed, because the chunk is
already decided, and here nothing fills that gap: the early abort that would
have filled it is a design and the bench only stops a push at a jam. For the
same
reason, the bench had to be designed to accept chunks: forcing a chunked policy
down to three numbers would have measured a damaged version of the method rather
than the method.

## Where it sits among the other five

[The six solutions](overview.md) form a ladder, ordered by how much of each one
was fitted in this cell, and this one stands at the top of it, because all of
its fitting happens on a borrowed model.

Against [solution 5](05-smolvla-as-it-downloads.md) there is nothing to compare
except the training, and that is the whole point. Same library, same model,
same downloaded weights, same tables, same readings, same rendered view, same
instruction, same output, same shared checks, same marking, same cost per
forward pass, and the same agreed convention for reading a waypoint. The one
thing that could be mistaken for a second variable — that this solution's
actions are fitted to this cell's own scale — is a property of those trained
weights rather than something changed beside them, so it is part of what is
being measured. Whatever separates the two scores is what fine-tuning bought,
and nothing else can be blamed for it, with the two qualifications this
document has already made: the correction is low-rank, so the answer is a lower
bound, and the agreed convention has to be chosen fairly or the gap measures
that too. **If this document is read for one reason, it should be that one.**

Against [solution 3](03-imitation-from-demonstrations.md), the comparison is
borrowing against building, and it is the second clean pair this solution is
part of. Both learn from the same demonstrations, drawn from the same training
half of the same tables, so the data is held still. Solution 3 fits ACT here
from random numbers, so the project owns every number in it, can regenerate
them, and pays nothing for a language channel it does not use. This solution
borrows 450 million numbers fitted on other robots and adjusts a few of them.
The pair therefore asks whether general knowledge of robot motion, gathered
from 487 datasets of a world this cell is not, is worth more than a small model
fitted exactly to this one.

Against [solution 2](02-geometry-ranked.md), the comparison is the teacher
against the student, and it is not an even comparison in either direction.
Solution 2 is geometry with a small fitted ranker on top; it explains its
refusals, needs no accelerator and no borrowed weights, and it is the ceiling
on the pushes this solution imitates. This solution cannot push better than its
teacher at its best, so if it wins anything it wins consistency in the cases
where the teacher was brittle. Anyone reading the scorecard should expect
solution 2 to be hard to beat, and should treat a large win for this solution
as a question about the teacher's ranker rather than a triumph.

Against [solution 1](01-one-fixed-nudge.md), the comparison is the cheapest
thing against the most expensive. Solution 1 computes one push by fixed
arithmetic and looks again, costs nothing to build or run, and is in this
folder to answer
the question of whether any learning beats a fixed nudge at all. If this
solution does not beat it by a margin larger than its own spread, the
450 million parameters and the hours of training have bought nothing.

Against [solution 4](04-a-world-model.md), the comparison is planning against
reacting. Solution 4 learns how the table changes and searches over candidate
pushes at run time, so it can be told about a new constraint by changing what
it searches for, and it pays for that in computation on every push. This
solution holds its whole answer in its weights and emits a chunk in one pass,
so it is a different kind of expense per push, and can only be changed by
training it again.

Read as a ladder, the six measure what each increment of fitting buys. This
solution is the rung where all of the fitting happens on borrowed weights, and
its partner one rung below is the rung where none of it does. The distance
between those two rungs is the most valuable single number this folder can
produce, which is why it is the first thing this document said and the last.

← [A foundation model as it downloads](05-smolvla-as-it-downloads.md) ·
[The six solutions](overview.md) →
