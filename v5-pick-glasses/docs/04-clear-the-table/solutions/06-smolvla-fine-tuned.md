# Solution 6 — the borrowed model, fine-tuned on this problem's own answers

> **What it uses** — SmolVLA, a robot model somebody else trained and published,
> with LeRobot and PyTorch underneath. Its training is continued here by
> low-rank adaptation on answers given in this cell. That training ran on this
> laptop's own graphics chip.
> **What it does** — it keeps the borrowed numbers and learns a small correction
> to them. It is then shown what every solution to problem 4 is shown: a picture
> from the camera the arm carries, and where the jaw is standing. It answers
> with a path for the jaw, which the cell carries out.
> **How it says it is finished** — it cannot. A policy has no output that means
> "this table needs nothing more", so the shared rule reads that statement out
> of the shape of its answers: a run of answers that could not touch a glass is
> taken as the policy saying it sees nothing to do.
> **How it differs from the others** — [solution
> 5](05-smolvla-as-it-downloads.md) is this exact model with no training here,
> and is this solution's matched partner. [Solution
> 3](03-imitation-from-demonstrations.md) learns from the same answers but from
> random numbers, in a model about a ninth the size. [Solutions
> 1](01-one-fixed-nudge.md) and [2](02-geometry-ranked.md) compute their pushes
> from geometry and learn nothing, or almost nothing; solution 2's answers are
> what this solution is fitted on.
> **What it costs** — the demonstrations are free, because a program made them.
> The training takes 27 minutes a seed and holds about one gigabyte, so nothing
> was rented. A run costs one large forward pass an answer, which is 279
> milliseconds here against the geometry's 15. The fitted weights inherit the
> terms of the borrowed ones.

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the arm, the hand and the sensors. [The problem](../problem.md) says what
> problem 4 asks and [the examiner](../the-examiner.md) says how it is marked.
> What follows is only what belongs to this solution.

## Introduction

This document answers problem 4 with a **foundation model**: a large network
that somebody else trained on many robots and published, in the hope that it
already knows something general about moving an arm. The model used here is
SmolVLA. [Solution 5](05-smolvla-as-it-downloads.md) asks it problem 4's
question with no training at all. This solution asks the same model the same
question after continuing its training on answers given in this cell, which is
called **fine-tuning**. The gap between the two scores is what that training
bought.

Problem 4 is problem 3 with two helps taken away. The camera above the table is
gone, so the arm carries its own camera and the only way to see the far corner
is to drive there. The push-by-push hand-over is gone, so a solution runs
continuously and has to say when it is finished. Both changes matter here more
than they look, and the reason is the second half of this document.

**The result is that the training bought safety and not competence.** Given
fifteen arm minutes and a queue of fifty held-out tables, this solution gets to
eight of them, separates none, and frees no glass at all: every glass that could
be picked when a walk ended could already be picked when it began. It breaks a
glass on three of the tables it reaches in four. That is better
than the same weights untrained, which break twenty glasses a walk against this
solution's eight, and it is far behind the hundred lines of arithmetic in
[solution 1](01-one-fixed-nudge.md), which separates ten tables and breaks
nothing.

**The reason is visible in what the model learned.** Four of the teacher's
answers in five move the arm only to see, because the camera is on the arm. The
correction learned that habit and little else: its paths now carry the jaw high
and sweep shorter and slower than the untrained model's, and only one answer in
fifty comes down far enough to move a glass. A policy that has learned to
look and not to push cannot tidy a table, and this one is a clean example of it.

By the end of this document you will know what fine-tuning and low-rank
adaptation are, what the demonstrations are and what is odd about problem 4's
set, how one recorded answer becomes something this model can be trained
towards, what the fit cost, what it changed, and why the camera on the wrist —
which was supposed to suit a model trained on real robots — is not what helped or
hurt it, while taking the overhead camera away is.

## The pair, and what is held still

A matched pair is two runs that differ in one thing. Here that one thing is
meant to be the training, so everything else is held still deliberately.

The model is the same published checkpoint. The reading that turns what the
model emits into a path for this jaw is the same arithmetic, written down once
in problem 3 and imported by both problems and both solutions. The loop is the
same loop: this solution is solution 5's solution with different weights inside
it, so the picture it is shown, the way it keeps its own accounting, and the rule
by which it declares a table finished are one piece of code for both halves of
the pair.

That matters because the reading is a choice, and a careless one would hurt the
untrained model far more than the fitted one, which can absorb it in training.
Holding it still is what keeps the comparison about the weights.

One thing is not held still, and it is worth saying plainly. The published
numbers in solution 5's own folder were measured when the shared stopping rule
counted three quiet answers and asked only whether a path came down to the
height the jaw pushes at. The rule now asks a better question — whether the hand,
which hangs below the point a path names, would sweep a glass standing taller
than that — and the count is now sixteen. Under the old rule the untrained model
stopped after three answers on nineteen tables in twenty; under the new one it
never stops at all. So solution 5's published table and this one are not two
readings of one arrangement, and the comparison used here is a fresh one: the
same weights, untrained, run through this solution's own loop.

## Fine-tuning — continuing somebody else's training

A published model arrives with its numbers already set by training on other
people's data. **Fine-tuning** is training it further on your own, so that what
it already knows is kept and what it does not know about your cell is added.
It is the ordinary way to put a borrowed model to work on one job, and it is
cheap compared with training from nothing, because most of the learning has
already happened.

What it cannot do is add an input or an output. The model takes a picture, a
sentence and six numbers of an arm's own pose, and answers with fifty rows of
six numbers. Training changes what it says, never what it can be told.

## Low-rank adaptation — a small correction instead of a large change

The model holds 454 million numbers. Moving all of them needs more memory than
this laptop has, and it also risks losing what the model already knew.
**Low-rank adaptation** avoids both. Every weight table the training touches
keeps its borrowed numbers, and a correction is added beside it. That correction
is forced through a narrow squeeze — a thin table down to sixteen numbers and a
thin table back out to full width — so the pair of thin tables together hold
3.8 million numbers, less than one per cent of the model.

The correction is put on the four projections inside every attention layer,
which are the tables a change in what the model attends to has to pass through.
Once the training is over, the two thin tables are multiplied out and added into
the borrowed table, so what runs afterwards is a model of exactly the original
size at exactly the original speed. Nothing separating the two halves of the
pair can be put down to one of them being given more computation.

Both of those choices — the width of the squeeze and where the correction goes —
are problem 3's, imported rather than chosen again, so that the two problems'
fits differ in their problem and their data and in nothing else.

## What it was fitted on, and what is strange about it

The training material is **demonstrations**: pairs of what a solution saw and
what it then did. They were collected once, by running [solution
2](02-geometry-ranked.md) over three hundred tables and writing down every
answer it gave with the picture it gave it from. Both of problem 4's copying
solutions read that one set, so the comparison between them is about the models
and not about the material. Collecting it cost eight and a half minutes of
simulator time, because nobody holds a controller: the tables are drawn from
numbers and the teacher is a program.

The set holds **11,016 answers from tables numbered 1000 to 1299**, with 1,850
more from a separate band kept back to measure against. And here is the fact
that governs this whole document: **8,965 of those answers — four in five — are
the teacher driving the arm somewhere it can see from, not pushing anything.**

That is not a flaw in the collection. It is what problem 4 is. Taking the
overhead camera away means a solution has to move the arm to see, so most of
what any solution does is look, and a model shown only the shoves would have no
idea how to get a look at the table. Problem 3's version of this set is the
opposite: its camera hangs above the table, so every demonstration in it is a
push.

A model fitted by copying can only be as good as what it copies, which is called
**behaviour cloning** and has a ceiling: nothing ever shows the policy a better
answer than the teacher's. This set adds a second ceiling on top of that. Four
answers in five say "go and stand over there", and that is the answer the fit
learns best.

## Turning one recorded answer into something the model can be trained towards

The teacher's answer is a path of up to 190 waypoints in this cell's own
numbers. The model emits fifty rows in the units of somebody else's arm. Three
things happen in between, and none of them invents a path.

**The glasses are dropped from what the model is told.** Problem 4 hands a
solution the readings of the glasses its camera caught, as numbers, beside the
picture. This model has six numbers for its state and they are joint angles, so
the only thing that fits is where the jaw is standing. The glasses stay in the
picture, which is where a model of this kind is expected to find them. That is a
property of the borrowed model and not a decision taken here, and it is one of
the prices of borrowing.

**The descent is dropped from the path.** Every demonstrated push starts high
and comes straight down over its first twenty-three waypoints before it drives
anywhere. The cell does that drop by itself — it places the jaw above the first
point of a path and lowers it on — so a path that asked for the drop would be
asking for it twice.

**The rest of the path keeps the teacher's own spacing.** The cell takes
waypoints at a fixed rate, so how far apart they are *is* how fast the jaw is
being asked to go. A path shorter than fifty rows is therefore padded by
repeating its last pose rather than stretched to fit, which is what keeps the
student's push at the teacher's speed. Measured over the set, 1,824 of the 2,051
pushes fit in fifty rows that way. The 227 that do not are squeezed into fifty,
which asks for the teacher's own path at a median of 1.6 times its speed and 3.3
times at the worst, and that is the one place where a target is not the motion
the teacher really made.

A look is the same shape held still: one pose, repeated to the end of the chunk.
The cell skips a step of no length, so such a path costs only the move to get
there, which is what the teacher's look cost.

**The reading was checked rather than assumed.** Every one of the 12,866
demonstrations in the two sets was read into the model's units and decoded back
out: the worst disagreement anywhere is below a thousandth of a millimetre, and
no waypoint had to be pulled inside the jaw's limits. So a chunk that came back
from the model unchanged would decode to the path that was recorded.

## What the fit cost, and what it moved

Three separate fits of the same correction on the same demonstrations, because
one fit is not a measurement: training varies with its random seed, and the
spread between the three turned out to be wider than anything else in this
document.

| | |
|---|---|
| steps, batch | 1,000 at a batch of 4 — problem 3's own recipe |
| numbers that move | 3.8 million of 454 million |
| time | 26.4, 26.4 and 27.1 minutes a seed |
| memory held | about 1.0 gigabytes |
| loss | 0.67 early, 0.21 to 0.23 at the end |

**A thousand steps is a third of one pass over this set.** A step shows the
model four demonstrations, so a thousand of them show it four thousand of the
eleven thousand it has. Problem 3's recipe was chosen on a set of 1,074, where
the same thousand steps was nearly four passes, and was finally run on a set of
6,935, where it was three fifths of one. The step count was held at problem 3's
deliberately, so that the two problems' fits cost the same and the two
results can be set side by side, and the price of that choice is that this
correction has seen a third of its material once. It is also, as problem 3 says
of its own, a tiny fraction of the computation the model's own publishers spend
on a fine-tune.

**The loss fell threefold and the model's paths did not move towards its
teacher's.** The loss is the model's own training objective and cannot be
pictured. So a distance is measured as well: the model is asked for a chunk on
tables it was never fitted on, the answer is decoded into waypoints, and the
distance from the teacher's own waypoints is reported in millimetres. Before the
first step the correction is zero, which means the model is exactly solution 5
— so the three seeds' readings of that one untrained model are a measurement of
the noise, because the answer is drawn from fresh random numbers every time.

| median distance from the teacher's waypoints | untrained | after the fit |
|---|---|---|
| over all kinds of answer | 152 to 163 mm | 110 to 148 mm |
| on the teacher's looks | 185 to 204 mm | 181 to 222 mm |
| on the teacher's pushes | 82 to 97 mm | 84 to 116 mm |

Every band overlaps. Taken apart by kind, the fitted model is no closer to its
teacher than the untrained one. This is a weak instrument — sixteen chunks a
kind, of a drawn answer — but it is strong enough to show that nothing like
problem 3's improvement happened: there, the same measurement fell from about
300 mm to about 100 mm.

## Saying when the table is finished

Problem 4 asks every solution to declare a table done, and a policy has no
output that means it. The shared rule reads the declaration out of behaviour
instead: a run of answers that could not touch a glass is taken as the policy
saying it sees nothing worth doing. That is a rule about the shape of an answer
and not its quality, which is what keeps it fair.

How long that run has to be matters far more for a fitted model than for an
untrained one. A model fitted on this set has learned the teacher's habit of
driving the arm about to see, so it goes quiet for a spell and then acts, and a
count set below the longest such spell would end the table in the middle of one.
The bench sets the count at sixteen, from a measurement of the teacher: its
longest quiet spell that then ends in a push is eleven answers. This solution
takes that number as it comes and sets none of its own, and a comparison on
tables below the held-out line agreed with it — at three quiet answers the
fitted model separated no table and lost two glasses' worth of room, at sixteen
it separated one and lost none.

In the event the question was moot on the held-out tables. **Neither this
solution nor the untrained model said it was done on a single one of them.**
Every table ended either with a glass on the floor or with the clock empty, so
nothing in the two results below turns on the count.

## What it achieves

The measurement is the held-out queue, which every solution to problem 4 is
marked on: the same fifty tables from table ten thousand, in the same order, and
fifteen arm minutes for the whole list. Arm minutes are simulated seconds of the
arm's own motion, and looking costs them like everything else, because the
camera has to be carried. The queue is walked three times, once with each fitted
correction, and that measurement is made once and never repeated, because a
measurement a method is tuned against stops being a measurement.

| the held-out queue | geometry reference | small fitted model | borrowed, untrained | **borrowed, fitted here** |
|---|---|---|---|---|
| Tables attempted | 26 | 10 (1 to 11) | 15 (13 to 15) | **8 (2 to 8)** |
| Tables separated | 10 | 0 | 0 | **0** |
| Tables failed by a topple | 0 | 0 | 14 (12 to 14) | **6 (1 to 7)** |
| Share of glasses pickable at the end | 0.627 | 0.400 | 0.018 | **0.103** |
| Glasses it made pickable | +25 | 0 | −1 | **0** |
| Glasses broken | 0 | 0 | 20 (19 to 22) | **8 (1 to 10)** |
| Said done while still crowded | 14 of 26 | 9 of 10 | 0 | **0** |
| Thinking an answer | 15 ms | 16 ms | 776 ms | **279 ms** |

Four things in that table need reading carefully.

**The gain is the honest column, and it is zero.** Some glasses are drawn with
room already, so the share of pickable glasses starts well above zero on any
table. What a solution did is the change, and this solution's change is nothing
at all in every one of the three walks.

**A high share can mean a short walk.** One of the three corrections reached two
tables before the clock stopped it, and two glasses of the eight on those two
tables could be picked, which reads as a share of 0.25 — the best of the three
walks and the worst walk by every other measure. The three are comparable on the
tables they all reached, which is two.

**The spread between the three corrections is wider than any effect here.** One
reached two tables and another eight, from the same recipe, the same material and
the same number of steps. Nothing in this result should be read at a finer
resolution than that.

**The two thinking figures for the borrowed model are the same forward pass.**
The correction is multiplied into the weights, so the fitted and the untrained
model are the same size and cost the same. They were measured while the machine
was under different loads, which is the whole of the difference between 279 and
776 milliseconds. What the pair of them says against the geometry is the real
reading: a borrowed model costs roughly twenty to fifty times as much thinking
an answer as a hundred lines of arithmetic.

## What the fit changed, and what it did not

The two halves of the pair were also walked over twenty tables below the
held-out line, three times each, with every table given two arm minutes of its
own. That is where the training's effect is clearest, because both sides ran
through one loop under one rule.

| twenty tables, 84 glasses | untrained | **fitted** |
|---|---|---|
| Tables failed by a topple | 18 of 20 | **9 of 20** |
| Glasses broken | 22 | **9** |
| Share of glasses pickable at the end | 0.012 | **0.25** |
| Paths the cell refused to carry out | 1,688 | **65** |
| Answers over the twenty tables | 2,308 | **749** |

**The training halved the damage and stopped the model battering at the cell.**
Twenty-six refused paths for every one of this solution's is the plainest
statement of what the untrained model does: it proposes, over and over, a path
the cell will not drive because the glass at the end of it would topple rather
than slide.

**What it learned is where to hold the jaw.** Measured by the same code on both
sides, over every answer:

| median over every answer | untrained | **fitted** |
|---|---|---|
| Lowest point of a path | 128 mm | **233 mm** |
| Distance travelled across the table | 442 mm | **301 mm** |
| Step between waypoints | 7.8 mm | **4.1 mm** |
| Answers that reach the pushing height | 0.6% | **2.0%** |

The fitted model carries the jaw higher, sweeps shorter and moves slower. All
three are the teacher's commonest answer, which is "go and stand over there at
travel height" — and all three are why the fit cannot separate a table. The jaw
pushes a glass at 75 mm. A path whose lowest point is 233 mm cannot drive a
glass anywhere, and only one answer in fifty comes down to the height where one
can.

**It still breaks glasses, and it breaks them with answers the stopping rule
calls quiet.** The point a path names is the middle of the hand, and the fingers
hang about 70 mm below it, so a path at 233 mm puts the hand's lower edge at
163 mm. Glasses on these tables stand between 97 and 224 mm tall. A sweep 300 mm
long at that height therefore drags the hand through the top of every tall glass
it passes, while the rule records the answer as the policy proposing nothing.
Solution 5 found this fault in the rule's stated reason, and this solution is the
clearest case of it: a quarter of its arm time goes on paths counted as quiet,
and those paths are what put the glasses on the floor.

## The camera on the wrist, against the camera above the table

This is the question problem 4 exists to ask of a borrowed model, and it has a
tidy answer going in. The model was pretrained on real robots, and a real robot
almost always carries its camera on its wrist. Problem 3 handed it a view from a
camera bolted above the table, which it would hardly have met in training.
Problem 4 gives it the view it is used to. So problem 4's input is closer to the
model's home ground, and the expectation was that this would show.

**It did not, and the clearest evidence is from the untrained model.** Solution 5
measured the same tables twice over, once with the wrist picture and once with
the wrist picture and problem 3's old jaw pose, and found that the wrist view on
its own moved the model's answers no closer to the table at all.

**For the fitted model the camera matters, but indirectly, and it made the
training harder rather than easier.** Taking the overhead camera away is what
turned four demonstrations in five into looks. The correction learned the
commonest answer in its material, as a fit will, and in problem 3 that answer was
a push while in problem 4 it is a drive to a viewpoint. The two fits fail in
mirror image:

| | problem 3's fit | problem 4's fit |
|---|---|---|
| What the demonstrations mostly are | pushes | looks, four in five |
| Lowest point of its paths | 75 mm, the pushing height | 233 mm, near travel height |
| How it fails | comes down onto the glass instead of behind it | sweeps over the glass and clips the tall ones |
| Glasses broken against its untrained partner | 42 against 12 | 8 against 20 |

Problem 3's fit learned the height of a push and not where to put the jaw down,
so it crashed into glasses and scored worse than the model it started from.
Problem 4's fit learned the height of a look, so it mostly misses the glasses and
scores better than the model it started from. **Neither learned where to put the
jaw down, which is the only thing the task actually needs.** The camera is not
what separates them; the mixture of answers in the material is, and that mixture
is a consequence of where the camera is.

## Where it is strong, where it breaks, and what is left undone

**Strong.** It is a genuine improvement on the same weights untrained, on both
sets of tables and by every measure of damage. The training costs 27 minutes on a
laptop and about a gigabyte of memory, so this is a cheap thing to try. The fit
runs at the speed of the model it started from, because the correction is folded
into the weights. And the reading of a demonstration into the model's units is
exact, so none of the failure above can be blamed on the material arriving
distorted.

**Broken.** It separates no table and frees no glass. It never says it is done,
so it spends a whole budget on a handful of tables and reaches eight of fifty
where plain geometry reaches twenty-six. It breaks a glass on three tables in
four. And the three fits of one recipe differ fourfold in throughput, so even the
result is unstable.

**What the data cannot give it.** One of the teacher's answers in five is a
push, and one in six of those is the small test shove that finds out whether a
glass will slide at all. The teacher never demonstrates a push onto a glass that would
topple, because it refuses those, so the material contains no example of the one
mistake this task cannot absorb. The usual fix for that is to let the learner
drive and ask the teacher what it should have done — which puts the learner in
the states it actually visits — and it is not built here.

**What would be tried next, in order.** More steps, because a third of one pass
over the material is not a fair trial of this recipe and the cost is known.
Weighting the pushes up in the fitting mixture, so that a fifth of the material
is not drowned by the other four fifths. And giving the model the glass
readings it is not currently shown, which needs a model whose state input is
wider than six numbers — and that is a different borrowed model, not a different
fine-tune.
