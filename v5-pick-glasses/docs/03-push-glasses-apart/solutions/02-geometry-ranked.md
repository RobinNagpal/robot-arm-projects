# Solution 2 — geometry generates, a model ranks

> **What it uses** — NumPy for the geometry, and scikit-learn for the one
> fitted part. The model is a set of **gradient-boosted regression trees**, of
> order two hundred trees, which is the standard tool for predicting a number
> from a short list of quantities of different kinds. There is no neural
> network anywhere in it and no accelerator is needed to train it.
> **What it does** — plain geometry writes down every push that is legal, which
> means every push that the arm can reach, that drags the glass and swings the
> jaw clear of every neighbour, that lands inside the glass zone, and that
> touches the glass below the height at which it would tip over instead of
> sliding. That is usually a large set rather than a single answer, so
> something has to choose one of them. The fitted model does that and only
> that: it gives each surviving candidate one score, the candidates are sorted
> by it, and the arm makes the first push on the sorted list. The model can
> never add a push to the list and never bring back one the geometry rejected,
> so it decides the order of the attempts and nothing about whether an attempt
> is safe.
> **How the output is produced** — `look()` hands over where each glass stands
> and how wide it is at its widest and at its foot. The geometry sweeps every
> heading round each crowded glass, steps the travel out along each heading,
> applies its tests, and keeps what survives. Each survivor is described by a
> short list of lengths, angles, counts and ratios, and the model turns that
> list into one number. The highest-scoring push is handed to the bench as a
> parameterised push, and the bench's own macro expands it into the jaw
> trajectory that every solution here is judged on.
> **How it differs from the other five** — [solution
> 1](01-one-fixed-nudge.md) fits nothing at all and pushes a glass a fixed
> fraction of the room it is short of, straight away from the neighbour whose
> edge reaches furthest into that room, so it is this solution with the
> enumeration and the choosing both removed. [Solution
> 3](03-imitation-from-demonstrations.md) fits everything and learns the push
> itself from demonstrations, which is the opposite arrangement, and this
> solution is where its demonstrations come from. [Solution
> 4](04-a-world-model.md) also fits everything, but its model predicts what a
> push will do rather than which push to try, so it attacks the quantity the
> geometry gets wrong instead of ordering the quantity the geometry gets right.
> [Solution 5](05-smolvla-as-it-downloads.md) is a large vision-language-action
> model used exactly as it downloads, with nothing fitted here and nothing
> geometric in front of it. [Solution 6](06-smolvla-fine-tuned.md) is that same
> model with its training continued on this cell, so all of it is fitted, where
> here only the ordering is.
> **What it costs** — the labels are free, because the bench measures the table
> after every push in any case. The training set is a few thousand pairs of a
> candidate and what happened to it, which is minutes of bench time, because a
> push in MuJoCo is cheap. Training a few hundred shallow trees on a table of a
> few thousand rows takes seconds to minutes on an ordinary processor, so there
> is no accelerator to rent and the running cost per push is arithmetic.
> scikit-learn and NumPy are both BSD 3-clause, so the licence costs nothing
> either.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the
> side, all four sensors, and the words this project uses them with. What
> follows is only what is specific to this solution.

## Introduction

This document explains the safest way there is to put a fitted model inside a
machine that can break something, and then says honestly what that particular
model is worth on these particular tables.

The arrangement has a name worth learning, because it recurs wherever learning
meets hardware: **generate, veto, then rank**. Arithmetic writes down every
action that is allowed. Arithmetic then rejects the ones that are not. A model
that has been fitted to data is handed whatever survives, and its only job is
to put that list in order. The arm makes the first push on the list. The model
cannot invent a push and cannot overturn a rejection, so **the worst a wrong
prediction can do is waste one attempt**. In a cell where a toppled glass
cannot be stood back up by anything in this project, that property is worth a
great deal.

Half of this solution is already written and half of it is a design, and the
line between them is worth drawing before anything else. The candidate
generation exists: `03-push-glasses-apart/01-one-fixed-nudge/plan.py` sweeps the headings, steps
the travel out, applies the tests and returns every push that survives, and it
runs on the bench today. What it does with that set is also written, and it is
a printed rule rather than a model: it takes the shortest push that finishes
the job. **Everything in this document about the trees — the inputs they are
shown, the number they predict, the training set and the labelling — is a
design and not code that runs.** Where a number appears below it comes from
the bench's own results file or from a constant in that code, and no
measurement of a fitted ranker is quoted anywhere, because none has been made.

By the end of this document you will understand what a decision tree is and
what boosting a set of them means, why a handful of geometric quantities suits
trees better than it suits a network, why every input is a length, a count or
a ratio and never an address on the table, how the training set is collected
and labelled for nothing, and two things about this solution that matter more
than wherever it lands on the scorecard.

Those two things are worth stating in the introduction, because they are the
reason to read the rest.

**The first is where the learned part sits.** Geometry generates every
candidate and refuses the unsafe ones, and the model only orders what
survives. So a wrong answer costs one wasted push and nothing worse. It cannot
topple a glass, because the topple limit described in [pushing without
toppling](../pushing-without-toppling.md) is a refusal applied before the model
is consulted at all. That is the same position problem 2's learned ranker
occupies, for the same reason, and the parallel is drawn out below.

**The second is that this solution is the teacher.** Solutions 3 and 6 learn
from demonstrations, and a solution that generates safe pushes geometrically
and ranks them supplies those demonstrations for nothing. That is the largest
single thing this solution contributes, and it comes with an honest cost: the
two solutions that learn from it inherit its ceiling, and keeping only the
demonstrations that succeeded trains them on a biased sample of what this
solution happens to do well.

## The problem this solves

[Problem 3](../problem.md) hands the arm a table with four to six glasses on
it, some standing too close together for the open jaw to fit round one without
fouling its neighbour. The arm has to drag them apart, because it may not lift
them: lifting needs a measured profile, measuring needs a clear view from the
side, and a clear view from the side is exactly what the crowding has taken
away.

A push therefore needs three things decided — which glass to move, in which
direction, and how far — and the honest difficulty is that the first attempt
at this produces far too many answers rather than too few. Sweep the headings
round one crowded glass and step the travel out along each of them, and a large
number of those pushes turn out to be perfectly legal. So the problem this
solution addresses is not how to find a safe push. It is **how to choose among
safe pushes**, which is a different question and a smaller one.

The complaint it is aimed at is therefore not safety. The geometry already in
this repository toppled nothing at all over the bench's fifty held-out tables,
as its results file records. The complaint is the number of attempts: that run
spent **212 pushes on 251 glasses, and 90 of those were repeat pushes of a
glass it had already moved once**. A repeat push is a push that did not achieve
what it was chosen for, so a method that chose better among the same candidates
would spend fewer of them. That is the gap a ranker is pointed at.

It is worth naming the other number in that same results file, because this
solution does not touch it. **52 of the 251 glasses were refused for having
nowhere clear to push them to.** That is a shortage of candidates rather than a
bad ordering of them, and a ranking over an empty set is still empty. So
whatever this solution is worth, it is worth nothing at all against the largest
single failure in that record.

## The main idea

The idea is one sentence long: ask the geometry for **every** safe push rather
than for the best one, and let a fitted model put the survivors in order.

Three things follow from that sentence, and they are the shape of the whole
solution.

**Everything that can reject a push is arithmetic.** Reach, the swept paths of
the glass and of the jaw, the glass zone, the rack and the topple limit are all
tests, they all run before the model, and each of them can remove a candidate
outright. None of them consults the model, so the model has no way to make an
unsafe push available.

**The model's entire output is an ordering.** It produces one number per
candidate, the candidates are sorted by that number, and nothing downstream
reads the number itself. A model that was wrong by the same amount on every
candidate would still order them perfectly, which is a much weaker thing to ask
of a fitted function than predicting the outcome correctly.

**The method degrades to what already exists.** Delete the fitted model, keep
the printed rule that takes the shortest job-finishing push, and the run is the
geometry in `03-push-glasses-apart/01-one-fixed-nudge` exactly. So this solution extends that code
rather than replacing it, and it can be tried and then abandoned at no cost.

The contrast that makes the arrangement worth understanding is with the obvious
alternative, which is to let a model choose the push directly. Such a model
reads the arrangement and emits a heading and a distance, so **its output space
is every push there is, safe or unsafe**. Nothing in the shape of the model
says which of the two it just produced, so a geometric check has to be placed
after it, and once that check is there it is doing the same safety work the
geometry does here, for a model that is far harder to fit. Solutions 3 to 6 are
all of that kind, and they are not wrong to be: a model that chooses the push
can express pushes the enumerator never offers. The point of this solution is
the opposite trade, and the next sections are the two halves of it.

![The enumerator writes down every push, the filter keeps only the safe ones, and the model reorders what is left, so nothing it can emit is unsafe; a model that chooses the push instead has every push in its output space and needs a geometric check bolted on after it.](../../../images/03-push-glasses-apart/06-generate-veto-then-rank.png)

## What the geometry proposes

The enumerator is the built half of this solution, so it comes first, and its
exact shape decides what the model is later handed.

For one crowded glass it sweeps **72 headings**, one every 5°, all the way
round. Along each heading it steps the travel out in **2 mm steps to 150 mm**.
At every step it asks four questions: does the moving glass's own path clear
every other glass, does the swept path of the fingers clear them, does the
swept path of the wrist and the gripper body clear them, and is the destination
both inside the glass zone and inside the ring the arm reaches comfortably. The
first step that fails ends that heading, because a clash found at one length is
still there at any greater length along the same line.

Two properties of that loop decide everything that follows, and both are
structural rather than accidental.

**Each heading stops at the first travel that gives the glass room.** Once a
push works, no longer push along the same heading is offered. So there is **at
most one job-finishing push per heading**, which puts a hard ceiling of 72 on
how many of them one glass can have, and every one of them is the shortest push
that works along its own line.

**The pushes that do not finish the job are kept as well.** A push that leaves
the glass still crowded, but less crowded than it was, is kept as long as it
cuts the table's total shortfall of room by at least 10 mm. The printed rule
uses this second kind only when there is no job-finishing push anywhere on the
table. This set is the large one: the enumerator offers every 2 mm step along
every heading up to the first clash, so it can run to thousands of candidates
for a single glass.

The consequence of the first property is the most important thing in this
document, and it is worth drawing out slowly rather than leaving implied.
Because each heading stops the moment the push works, **every job-finishing
candidate lands on the same contour**: just past the line where the glass has
the room it needs, plus the 10 mm of aiming margin the planner adds so that a
push landing a little short still clears. They are the same achievement reached
from different directions. So on the question the run is actually scored on —
how many glasses have room afterwards — those candidates are a **tie**, and
they differ only in how far the glass has to travel, which the geometry prints
for nothing.

![On one crowded table the pushes that finish the job fan out in every direction, and because each heading stops at the first travel that works, every one of them leaves the glass within a millimetre of the same room margin and scores exactly the same; they differ only in how far the glass travels.](../../../images/03-push-glasses-apart/06-the-room-test-and-the-fan.png)

**A ranking problem in which the candidates within a group are tied carries no
information.** A model fitted to that group would return the same value for
every member of it, which is the correct answer and a useless one. So the
signal a ranker could use does not live in the job-finishing set at all. It
lives in the wider set of pushes that only ease the crowding, where the
candidates genuinely differ from one another, and where the geometry is
guessing at a sequence of pushes rather than finishing the job in one.

![The enumerator almost always finds a safe push for a crowded glass and rarely finds one that finishes the job; the job-finishing candidates score identically in every set there is, while the wider set of pushes that only ease the crowding is where the candidates differ.](../../../images/03-push-glasses-apart/06-how-alike-the-survivors-are.png)

That is a sharp conclusion to reach before the model has been described, and it
is the honest shape of this solution. The arrangement is excellent. The
question it is asked here is one the arithmetic has largely already answered.

## What the filter removes before the model is asked

One of those four tests deserves its own section, because it is the one that
can cause the failure nothing can repair, and because the height it is
evaluated at is easy to get wrong.

[Pushing without toppling](../pushing-without-toppling.md) sets out the rule in
full, and the short form is that a glass pushed at height `h`, standing on a
foot `2a` across, on a table it rubs against with friction `μ`, slides while

    h  <  a / μ

and tips over above that. The height that counts is the **top edge of the
jaw**, not its middle, because a glass that is wider higher up meets the top
edge first. The middle of the jaw rides at 50 mm, which is as low as the
gripper reaches without fouling the table, and the fingers are 30 mm tall, so
the top edge stands at 65 mm. Those are the gripper's own numbers and they do
not change from one glass to the next. What changes is `a`, because every glass
has its own foot, so **the limit is computed for each glass from its measured
foot width** rather than agreed once for the whole kind.

The term nobody has is `μ`. Nothing in the cell measures friction and the bench
never tells any solution the coefficients it runs the physics with, so the
limit a solution computes is only as good as a guessed number. The geometry
already in this repository handles that by carrying the whole range it is
willing to believe, **0.2 to 0.5 for glass on a dry wooden top**, and asking a
three-way question of every glass. If the limit clears the jaw's top edge even
at the most pessimistic friction in that range, the glass is safe to push. If
it fails even at the most generous one, the glass is refused. If the two ends of
the range disagree, the arm settles it by making a **5 mm push** and looking
before and after: a glass that slid has moved, and a glass that leaned instead
fell back where it stood.

All of that runs inside the filter, which means it runs **before** the model.
So a glass that would tip never reaches the ranker, and no score the model can
produce brings it back. This is the mechanism behind the safety claim in the
introduction, and it is worth stating as a rule rather than as an
implementation detail: **everything that can reject a push is arithmetic, and
the model comes after all of it.** The model is never asked about safety, so it
cannot cause an unsafe movement.

## The model: boosted trees that score one candidate at a time

Now the fitted half. The model has to turn a short list of quantities into one
number, so this section explains what kind of model does that and why this kind
was chosen.

**A decision tree** is a sequence of threshold questions arranged as a tree.
Each internal point of the tree asks one question about one input, such as "is
the travel more than 50 mm?", and sends the candidate left or right depending
on the answer. A candidate falls through the questions until it reaches a leaf,
and the leaf holds a number, which is the tree's prediction. A single tree of
this kind is a crude predictor: it can only produce as many distinct answers as
it has leaves, and its answer changes in steps rather than smoothly.

**Boosting** is how a crowd of crude predictors is turned into a good one. Fit
one shallow tree to the data. Work out what it got wrong, candidate by
candidate. Then fit the next tree not to the original target but to those
errors, so that the second tree's job is to correct the first. Add the two
together, work out what the sum still gets wrong, and fit a third tree to that.
Repeat. Each tree is weak, each one is fitted to whatever the sum of the
previous ones has left over, and the sum of all of them is the model. The
arrangement has a mathematical comparison that makes it concrete: it is
gradient descent, where each step down the slope is taken by adding a small
tree rather than by adjusting a coefficient. **A model of order two hundred
trees** is an ordinary size for a table of a few thousand rows, which is what
this solution has.

This solution uses the **regression** form, which predicts a number, and it
uses it **pointwise**, which means the model is shown one candidate at a time
and scores it on its own without being told what it is competing against. Each
candidate gets one scalar score, and the candidates are then sorted by it. That
is the simplest of the three ways a ranking can be fitted, and the section on
general ideas below says what the other two are and what the choice costs.

### Why trees rather than a network

A number predicted from a short table of quantities of different kinds — an
angle, several lengths, a count, a ratio — is the case decision-tree boosting
was made for, and there are four reasons that are worth separating.

**The inputs are not on a common scale and trees do not care.** An angle in
radians, a distance in millimetres and a count of neighbours are three
different kinds of number with three different ranges. A network has to be
given them on comparable scales, because every input enters through a weighted
sum and a large-valued input would otherwise dominate the sum before training
begins. A tree never sums its inputs. It only ever compares one input against
one threshold, so the scale of each input is a private matter and rescaling any
of them changes nothing at all.

**A threshold is the natural shape of the answer here.** Much of what makes a
push good in this cell is a comparison against a limit: is the destination
clear by more than the gripper needs, is the push height below the topple limit
for this foot, is the destination further from the zone edge than the aiming
error. A tree is built out of exactly those comparisons, so it expresses them
in one question each. A network has to build a sharp comparison out of smooth
weighted sums, and it needs rows of data to do it.

**It is cheap and it needs few rows.** A few hundred shallow trees on a few
thousand rows trains in seconds to minutes on an ordinary processor, with no
graphics card involved anywhere. That matters here beyond the price, because it
means the whole question — does ordering help — can be asked and answered in an
afternoon rather than budgeted for.

**It says which inputs mattered.** A boosted-tree model reports how much each
input contributed to its predictions, so a wrong answer can be investigated.
That is not a small thing in a system that will be debugged by a person reading
a printed candidate list.

**A network would also work**, and it is worth being plain about the trade
rather than dismissing it. The honest statement of the trade has two halves.
Against trees on this input, a small network needs more rows to reach the same
accuracy and explains nothing about why it answered as it did, which is a loss
on both counts. But the input would not have to stay as it is. If the
arrangement were given to the model as an **occupancy grid** — a picture of the
zone, with the glasses marked on it — rather than as a short list of numbers,
then a network becomes the right choice and a tree the wrong one, because a
network reads a grid naturally and a tree would have to ask threshold questions
about individual cells of it. So the real choice is not trees against networks.
It is a short list of relations against a picture of the table, and the model
follows from that choice rather than the other way round. This solution chooses
the short list, for the reason the next section gives.

## The inputs are lengths, counts and ratios

Every input this model is shown is a length, an angle, a count or a ratio, and
**none of them is an address on the table**. That is the most important design
decision in the fitted half, and it is a decision about generalisation rather
than about convenience.

The list is short. For each candidate push the model is shown:

- **the contact angle**, measured relative to the line from the glass's middle
  to the nearest neighbour's edge, so that "pushing straight away from the
  crowd" is one value of one input rather than a different value for every
  place on the table;
- **the push distance**, which is how far the glass is to travel once the jaw
  has touched it;
- **how much clear room the destination would have**, which is every clearance
  recomputed with the glass moved to where this push would put it;
- **how far the destination is from the edge of the glass zone**, and **how far
  it is from the rack**, because a push that is legal but lands close to either
  has very little margin for the error a push actually carries;
- **how many neighbours sit within a radius** of the glass being moved, which
  is the one input that describes the crowd rather than the push, and describes
  it as a count;
- **the foot width of the glass being moved**, which is what the topple limit
  is computed from and also what decides how the glass turns as it slides;
- **the push height as a fraction of the topple limit**, which is the jaw's top
  edge divided by the limit for this glass's measured foot at the most
  pessimistic friction in the believed range. The height itself is fixed, so
  this ratio varies only with the glass, and it says how close to the line this
  push is standing.

Notice what every one of those is. Each is a relation between two things in the
scene, or a property of the glass being moved, or a comparison against a limit.
Not one of them is "this push happens at x = 430, y = −290".

**That exclusion is deliberate, and the reason is what a position would teach
the model.** The bench's crowded tables are drawn by standing most glasses
deliberately close to a glass already down and the rest anywhere they fit, as
[the test bench](../the-bench.md) describes. Over many tables that produces a
distribution: crowds form more often in some parts of the zone than others,
purely because of where the arm reaches, where the rack sits and how the
placement rule happens to work. Give the model the position and it will find
that distribution, because it is real and it predicts the training labels. The
model would then be scoring a push by **where on this cell's table it happens
to be**, which is a fact about this bench's placement rule and not a fact about
pushing. Change the rack, move the zone, or draw the tables by another rule,
and the model is quietly describing a cell that no longer exists, while nothing
errors and nothing looks suspicious.

The relational inputs make the right thing true by construction instead. Take
any arrangement, slide it across the zone and turn it round, and every input in
the list above is unchanged, because every one of them is a relation between
parts of the scene that moved together. So **the model cannot tell the two
arrangements apart, which means it must score them the same** — and scoring
them the same is correct, because a push is exactly as good in one as in the
other. A model given coordinates would have to learn that invariance from data,
and it would learn it imperfectly from a finite number of tables.

Two of the inputs look positional and are not, and the distinction is worth
making because it is easy to confuse. The distance to the edge of the glass
zone and the distance to the rack are **distances to fixed features of the
cell**, which is a relation and generalises: a destination 15 mm from a
boundary has 15 mm of margin wherever that boundary is. A coordinate pair is an
address, and an address generalises to nothing. The rule to carry away is that
a model should be shown the quantities the physics depends on, and the physics
of a push depends on distances, angles and widths. It does not depend on where
the table's origin was put.

## How it is trained

The training set follows from the two halves above, and the pleasant part is
that collecting it needs no extra work.

**Generate the candidates geometrically, on the training tables.** The bench
numbers its tables and splits those numbers, with everything above a fixed
dividing line reserved for testing, so training draws only from below it and no
solution is ever marked on a table it was fitted on. For each crowded table the
enumerator produces its candidate set exactly as it would at run time.

**Execute every candidate on the bench.** Reset the table, make the push,
measure the result. This is the step that would be unaffordable on a real arm
and costs almost nothing here, because a push in MuJoCo is cheap and the bench
runs faster than real time. **A few thousand candidate-and-outcome pairs is
minutes of bench time**, which is the single reason this solution's data cost is
near zero.

**Label each one with what happened.** The label has two parts. The first is
**how much clear room was gained**, measured over the whole table rather than
over the pushed glass alone, so that a push which frees one glass by crowding
another is not rewarded for half of its effect. The second is **whether the
glass toppled**, which is recorded for every push and makes a push the worst
possible candidate when it is true.

**Fit the regression on those labels.** One row per candidate, one number per
row, and the ordering of the model's predictions is all that is used
afterwards.

Two things about that labelling deserve more than a line.

**Toppling appears in the training set even though the filter rejects unsafe
pushes**, and this is not a contradiction. The filter rejects a push whose
contact height is above the limit **as the geometry computes it**, and that
computation contains a guessed friction. When the guess is too generous the
limit comes out too high, the filter passes a push it should have refused, and
the glass goes over. Those are exactly the rows worth having, because they
teach the model to prefer pushes that stand further from the limit even among
pushes the arithmetic called safe. So the ratio of push height to topple limit
earns its place in the input list: it is the input through which the model can
express caution about a number nobody measured.

**The label is only as honest as the bench**, and the honest part of that
sentence is the friction. The bench's coefficients decide every topple in the
training set, and they are three fixed numbers rather than a measurement of
anything real. A model fitted on these labels has learned what topples on this
bench, and carrying it to a different table would mean carrying an assumption
about friction that was never checked.

One guard belongs on retraining, and it is the ordinary failure of every
feedback loop built on a model's own choices. **Only the chosen candidate is
ever executed for real during a run.** So a log collected while the model is
driving the arm holds outcomes only for the region the model already prefers,
and retraining on that log locks in whatever the model believed first. The
standard repair is to take the second-ranked candidate occasionally, which
costs a little and keeps the data honest. Retraining itself belongs between
runs and never during one, because a model that changes during a run makes that
run impossible to reproduce, and a run that cannot be reproduced cannot be
debugged.

## Where the learned part sits is what makes it safe

The two previous sections described a fitted model inside a machine that
handles glass, so the obvious question is what happens when it is wrong. The
answer is the strongest thing about this solution, and it comes from the
arrangement rather than from the model being good.

**A wrong answer costs one wasted push and nothing worse.** The model's output
is a permutation of a set, so the only mistake available to it is putting a
worse candidate before a better one. The arm then makes a push that was safe,
legal and less useful than another safe legal push would have been, looks at
the table, and chooses again. That costs seconds of arm movement and one entry
in the push count.

**It cannot topple a glass.** Toppling is settled by the limit described above,
which is a refusal applied before the model is consulted. There is no score the
model can produce that makes a rejected push available again, because the
rejection happened earlier in the sequence and nothing later reads the model's
output back into it. The same holds for the other three ways a push can go
wrong: leaving the glass zone, leaving the arm's reach, and striking the rack
are all geometric tests on the destination, all of them run before the model,
and none of them consults it.

**So the ceiling on how badly this can fail comes from the arrangement and not
from the model's accuracy.** That is a rare thing to be able to say about a
fitted component, and it is the whole argument for the pattern. A better model
makes wasted pushes rarer. Only the geometry decides how bad things can get.

This is precisely the position problem 2's learned ranker occupies, and the
parallel is exact enough to be worth following. There, the shared machinery for
[looking again at what was
hidden](../../02-segment-glasses/hidden-glasses.md) has to decide which of
several places to stand the camera should be tried first. The geometry works
out every candidate position and rejects the ones that are unreachable or whose
line of sight is blocked, and a small fitted model orders what is left by how
much it would be worth looking from there. That document states the reason in
one sentence, and it is the same sentence that applies here: where the model
sits is the whole reason it is safe to have, because a bad ordering costs one
wasted look and nothing worse.

The two cases differ in one respect, and it raises the bar here rather than
lowering it. **A wasted look in problem 2 costs seconds of arm movement. A
wasted push in problem 3 costs seconds and a contact with a glass**, and
contact is where things break. So a push ranker has to be better than a
viewpoint ranker to be worth the same amount.

## It is the teacher

The second thing that makes this solution matter more than its score is that
two other solutions cannot start without it, and this is the largest single
thing it contributes.

[Solution 3](03-imitation-from-demonstrations.md) and [solution
6](06-smolvla-fine-tuned.md) both learn from **demonstrations**, which are
recorded examples of the task being done. A demonstration is one run of a
crowded table, from the measurements through a sequence of pushes to a table
where every glass has room, with the action recorded at each step. Collecting
demonstrations is normally the expensive part of imitation learning, because
normally a person has to drive the arm through the task by hand, and the
expense is why imitation learning is often judged on how few demonstrations it
needs.

**Here they cost nothing.** This solution generates safe pushes geometrically
and ranks them, so it can be run over as many training tables as the bench can
draw, and each run records a complete demonstration without a person present.
The pushes in it are safe by construction, because the same filter that
protects a real run protects a recorded one. So the cost of the demonstration
set is bench time, which is minutes, and nothing else.

That is a real contribution and it has to be stated with its cost, because the
cost is not obvious and it reaches both of the solutions that learn from it.

**Those two inherit this solution's ceiling.** A policy fitted on
demonstrations is fitted towards reproducing the behaviour in them. Every
demonstration here was produced by ordering candidates the enumerator wrote
down, so the demonstrations contain only the pushes the enumerator can express.
If the heading sweep is too coarse to include the push a situation really
wanted, or if one of the tests rejects something that would in fact have been
fine, that push appears in no demonstration and the policy fitted on them has
no way to discover it. A learner trained purely on this teacher therefore has
this teacher's ceiling, whatever its own capacity. The usual repair is to let
the policy act, score what happens, and learn from that as well, which stops
being imitation learning and starts being something more expensive.

**And filtering the demonstrations to successes trains on a biased sample.**
The natural thing to do with a recorded set is to keep the runs that finished
the table and discard the rest, because a policy fitted on failures learns to
fail. But the runs that finished are not a random sample of the tables. They
are the tables this solution happens to be good at: the ones where the
enumerator found a job-finishing push, where the crowding was the kind its
inputs describe well, where the glasses were not close to the topple limit. The
tables it struggles with — the ones where there is nowhere clear to push a glass
to, which its own results file says is the commonest refusal — are the ones
most likely to be discarded. So a policy fitted on filtered successes is fitted
on an easier distribution of tables than the one it will be marked on, and it
will look better in training than it turns out to be. Keeping the failures with
their outcomes recorded is one answer; weighting the kept runs so that hard
tables are not under-represented is another. Doing neither, and quietly
training on successes alone, is the mistake worth naming here because it is the
default thing to do.

## The pushes are what this contributes

One point about the output has to be clear, because it decides what a
comparison with the other five is a comparison of.

This solution thinks in **parameterised pushes**: which glass to move, where to
put the fingertips down, which way to point the jaw, how far to feel forward
and how far to push once it has touched. That is exactly what the bench's
`push()` already accepts, and **the expansion of those numbers into a jaw
trajectory is a macro the bench owns.** The bench brings the closed jaw down at
the chosen start point, feels forward slowly until the force passes a small
threshold, pushes the asked-for distance, backs off a couple of centimetres and
lifts clear. Every parameterised push is expanded the same way by the same
code, so this solution gains nothing and loses nothing in that step.

It follows that **what this solution contributes is the choice of push and
nothing else**. The trajectory is the bench's, the physics is MuJoCo's, and the
marking reads the table afterwards rather than the action, which is what lets a
three-number push and a chunk of waypoints from a learned policy be compared at
all. [The test bench](../the-bench.md) states that once so that no solution has
to argue it again.

One consequence is worth drawing out, because it is a genuine limitation rather
than a formality. A parameterised push is a straight drag along one heading. A
policy that emits waypoints directly can describe a push that curves, slows,
or changes direction partway through, and no member of this solution's
candidate set can express any of those. That is part of the ceiling named in
the previous section, and it is the clearest example of what the enumeration
costs.

## How the concepts fit together

The pieces now join into one loop, and the loop is the one [pushing without
toppling](../pushing-without-toppling.md) describes: plan, feel, look again.

Before any of it, and once, the model is fitted. Candidates are generated
geometrically on the training tables, every one of them is executed on the
bench, each is labelled with the clear room the table gained and with whether
the glass toppled, and a few hundred boosted regression trees are fitted to
those labels on a table of a few thousand rows.

At run time, one pass of the loop goes like this. `look()` hands over where
each glass stands and how wide it is at its widest and at its foot, carrying
problem 2's measured error. Any glass that already has room is racked and
removed from the problem. For each glass that is still crowded, the topple
limit is evaluated from its measured foot across the believed range of
friction, and a glass that tips before it slides at every friction in that
range is refused with the reason. For the glasses that remain, the enumerator
sweeps the headings, steps the travel out, applies its four tests and keeps the
survivors. Each survivor is turned into the short list of lengths, angles,
counts and ratios described above, the model scores it, and the candidates are
sorted. The highest-scoring push is handed to the bench, which expands it into
a trajectory, carries it out, and reports what the jaw felt. Then the arm looks
again, and the loop repeats with the arrangement as it now is rather than as it
was planned to be.

Three things are worth holding on to from all of that.

**The safety is the geometry's and the ordering is the model's**, which is the
whole design, and deleting the model leaves a working run rather than a broken
one.

**The loop is what recovers from a bad prediction.** Nothing here trusts that a
push lands where it was aimed. The arrangement is re-read after every push, so
a push that fell short, went too far or turned the glass is simply the state of
the table that the next pass plans against. That is why a wrong ordering costs
a push rather than a run.

**What the loop cannot recover is a toppled glass**, because nothing in problem
3 lifts anything. That single fact is why the topple limit is a refusal rule
rather than a risk weighed against the value of moving the glass, and it is why
the model's position after the refusal matters more than the model's accuracy.

## When a glass cannot be pushed safely

Every solution document answers this question, and this one's answer is that
**the refusal belongs entirely to the arithmetic and the model is never
consulted about it.**

There are two reasons a glass is refused here, and they are the two [the
problem](../problem.md) names.

**It tips before it slides.** The limit `a / μ` is small when the foot is
narrow or the friction is high, and it can come out below the 65 mm at which
the jaw's top edge touches the glass — which is already the lowest contact the
gripper can offer, since the middle of the jaw rides at 50 mm and cannot go
lower without fouling the table. For such a glass there is no contact height
the arm can offer below the limit, so it tips whatever the arm does. Because the
friction is a guess rather than a measurement, the test is made at both ends of
the believed range: safe if the limit clears the jaw's top edge even at the most
pessimistic friction, refused if it fails even at the most generous one, and
settled by a 5 mm push and a look when the two ends disagree — and refused even
then if the lean such a push could cause is not small compared with the angle
the glass would fall past. That test runs inside the filter, so a glass it
refuses produces no candidates and the model is handed nothing.

**There is nowhere clear to push it to.** Every candidate along every heading
clashed with a neighbour, left the glass zone or left the arm's reach. The
candidate set is empty, and **a ranking over an empty set is still empty**. This
is the commoner refusal by a wide margin in the record this solution extends:
all 52 of the glasses that run left on the table were refused for this reason,
and not one for tipping.

![The topple limit is evaluated at the jaw's top edge across the whole believed range of friction, and on the held-out tables it refuses nothing: every refusal in the record is a glass with nowhere clear to push it to.](../../../images/03-push-glasses-apart/06-where-the-refusals-come-from.png)

Both refusals are reported with their reason, which makes the run **correct but
incomplete** rather than wrong. That distinction is the project's position
wherever contact is involved: a glass that was refused is still a glass
standing on a table, and anything later may yet move it or measure it, while a
glass that was pushed over is finished and the arm carries on working beside
it. So no fallback may be added that tries anyway, and the model is not a
fallback: it has no input through which to disagree with a refusal.

## A worked example

Follow one crowded table through the whole method, because the argument is
easier to recognise once the candidate set has a shape.

**The table.** Four tapered glasses stand in the glass zone, drawn at
proportions from across that kind's range, so they are not all the same size.
Two of them stand comfortably clear of everything. The other two stand close
enough together that neither has the room the open jaw needs, and because the
room test measures to the neighbour's edge rather than to its middle, the two
are short by slightly different amounts even though they stand the same
distance apart — the narrower of the pair is the more crowded, because its
wider neighbour's rim reaches further into the gap.

**Two glasses leave before any push is planned.** The two that already have
room are racked and taken away, so the push planner is asked about a two-glass
table rather than a four-glass one. That is worth noticing because it is the
cheapest thing in this whole problem and it happens first on every table.

**The topple limit runs next, and defers.** Both remaining glasses stand on
feet whose measured width puts the limit above the jaw's top edge at the
pessimistic end of the believed friction range and below it at the generous
end, so the arithmetic returns neither "safe" nor "refused" but "try". The arm
therefore makes a 5 mm push on each and looks before and after. Both move, so
both are proven to slide and the run continues. Nothing about this step involves
the model, and if either glass had failed at both ends of the range it would
have been refused here with its reason and the model would never have seen a
candidate for it.

**The geometry proposes, at length.** For each of the two glasses the
enumerator sweeps 72 headings and steps the travel out in 2 mm to 150 mm,
discarding every step at which the glass's path, the fingers' swept path, the
body's swept path, the zone or the reach fails. What survives is a large set,
running well into the hundreds for each glass, because most headings admit many
lengths before anything clashes.

**A minority of those finish the job.** For each glass the job-finishing pushes
fall into two arcs: one pointing roughly away from the neighbour, and one
pointing round the neighbour the other way. There is at most one per heading, so
there are at most 72 of them per glass however many headings admit one.

**And every one of them scores the same.** Each leaves both glasses with room,
so the label is the same whichever is chosen, and each comes to rest just past
the line it had to clear plus the planner's 10 mm of aiming margin, because the
enumerator stopped each heading the moment the push worked. The only thing
separating them is how far the glass has to travel, and the geometry prints
that number for every candidate without being asked.

**The printed rule takes the shortest.** A model asked to order those
candidates can agree with that choice, or disagree with it and prefer a longer
push, or take longer to produce the same answer. There is no fourth thing it can
do, because the candidates are not distinguishable on the quantity the model was
fitted to predict.

**The wider set is where the model would have something to say.** Beyond the
job-finishing arcs, each glass has a large number of pushes that ease the
crowding without clearing it, and those do differ from one another. They are
also the pushes whose real outcome depends most on the friction and on how the
weight sits under the glass — which is to say on exactly the quantities a ranker
is not being asked about, and exactly the quantities [solution
4](04-a-world-model.md) fits a model of.

## What it needs

It needs **scikit-learn and NumPy**, both small, both pure software, and both
BSD 3-clause, so there is no licence condition to carry anywhere and nothing to
revisit if this work were taken further.

It needs the **enumerator**, which exists in `03-push-glasses-apart/01-one-fixed-nudge/plan.py` and
runs on the bench today. This is the part of the solution that is built, and it
is also the part that decides the ceiling.

It needs a **training set**, which is a few thousand pairs of a candidate and
what happened to it, generated on the training half of the bench's tables and
executed there. That is minutes of bench time and no human labelling at all,
because the bench measures the table after every push in any case. It needs the
**held-out half** of the tables for marking, which the bench already enforces by
splitting its table numbers.

It needs **no accelerator**, and this is the clearest cost difference between
this solution and the four that follow it. A few hundred shallow trees on a few
thousand rows trains in seconds to minutes on an ordinary processor. There is
nothing to rent for a weekend and nothing to rent by the month, so the figure
to quote against the other solutions' rental costs is zero.

At run time it needs **one pass of the trees per candidate**, which is
arithmetic: a few hundred threshold comparisons per tree, a few hundred trees,
and no matrix multiplication anywhere. Even a candidate set in the thousands
costs a small fraction of the seconds one arm movement takes, so the compute
column on the scorecard is close to the fixed nudge's rather than to a
foundation model's.

And once fitted it needs **a model file kept in step with the cell**. Change
the heading sweep, the step length, the glass zone or the way the bench draws
its crowded tables, and the fitted model quietly describes a cell that no
longer exists, in a way no test of the code would notice.

## Where it is strong and where it breaks

The strengths are real, and they are the reason to understand this arrangement
even after deciding not to spend much on it here.

**The learned part cannot cause the failure that cannot be undone.** Toppling,
leaving the glass zone, leaving the arm's reach and striking the rack are all
settled before the model is consulted. In a cell whose one unrecoverable
failure is a toppled glass, that is the property worth designing around, and
the zero topples in the record of the geometry this solution extends is what it
looks like when it holds.

**It degrades to something that works.** Delete the model and the printed rule
runs the table. There is no state in which this solution is broken rather than
merely unimproved.

**It is checkable.** Every candidate can be printed with its score, every
refusal remains the geometry's and prints with a reason, and the model reports
which of its inputs mattered. When this solution is wrong, a person can find
out why by reading a list.

**It is cheap in every currency.** No accelerator, no licence condition, no
human labelling, minutes of bench time, and a run-time cost that is arithmetic.

**And it is the teacher**, which is the contribution that survives even if its
own score is unremarkable.

Against that, three kinds of weakness.

**What the measurement will probably say.** The job-finishing candidates are
tied by construction, as the section on the enumerator shows, so the ordering
carries no information in exactly the part of the candidate set where the task
is actually being finished. What is left for the model is the wider set of
pushes that only ease the crowding, and there the printed rule already uses the
quantity that matters most, which is travel. **Before building this, measure the
spread of the label within each candidate group**, and measure how much better
the best possible opening push would be than the printed rule's. Both are a
line of arithmetic over an enumerator that already exists, and both are cheap
enough that there is no excuse for fitting a model first.

**What the design cannot do.** It cannot invent a candidate, so its quality is
the enumerator's quality rather than the model's. It cannot express a push that
is not a straight drag along one heading. It does not transfer across a change
in the number of glasses, because a model fitted on tables of five has never
seen the crowding that eight produce, and nothing errors when it is asked
anyway. And it says nothing at all about the commonest refusal in the record,
which is a glass with nowhere clear to go.

**What it cannot survive.** A log collected while the model is driving holds
outcomes only for the candidates the model already prefers, so retraining on it
without occasionally taking the second-ranked candidate locks in an early
mistake.
Change the sweep or change the way tables are drawn, and the fitted model is
out of date silently. And every label in the training set was decided by the
bench's private friction, which was never measured against anything real.

**How it fails, when it fails, is quietly.** A badly fitted ranker orders the
candidates roughly at random. Nothing errors, nothing topples, and the run
simply spends more pushes and leaves more glasses behind than it needed to. The
test is to count pushes per run against the printed rule on the held-out
tables, and to keep the simpler one if it wins.

## The general ideas behind this

Nothing in this solution was invented for glassware. Four ideas in it are worth
knowing separately from this cell, each with an honest note on where it is
normally right and where it is not.

### Generate, veto, then rank

Arithmetic writes down the candidates and holds an absolute veto, and the
fitted part is only allowed to reorder what survives. **Position in the
sequence is what limits the damage a wrong prediction can do**, and it limits
it by construction rather than by the model being accurate.

It is the standard answer wherever a fitted component is wanted in a system
that can cause physical harm, and it appears in motion planning, grasp
selection and flight control in the same form. It is the wrong shape when the
set of possible actions is too large or too awkward to write down, which is
exactly when a policy earns its place, and it is the wrong shape when the
enumerator can already tell which survivor is best — because then the model is
being asked a question that has already been answered. This cell is close to the
second of those two cases, which is the measured verdict this document keeps
returning to.

### Learning to rank

Nothing downstream uses the number the model predicts. Only the order matters.
That is called [learning to
rank](https://en.wikipedia.org/wiki/Learning_to_rank), and it is an easier
problem than predicting the number, because a model that is wrong by the same
amount everywhere still ranks perfectly.

There are three ways to fit it, and they are worth distinguishing because this
solution chooses the first. **Pointwise** fitting, which is what is used here,
shows the model one candidate at a time and asks it for that candidate's score
on its own. **Pairwise** fitting shows it two candidates from the same group and
asks which is better, so the thing being fitted is a comparison rather than a
value. **Listwise** fitting shows it the whole group and scores the order it
produces. Pairwise and listwise match the real objective more closely, because
the real objective is an order and not a set of values, and they are the usual
choice where the groups are large and the differences within them are subtle.
Pointwise is chosen here because it is the simplest thing that can work, because
the label it needs is exactly the label the bench produces anyway, and because
nothing in the measured shape of these candidate sets suggests the extra
machinery would be repaid. If the within-group spread of the label turned out to
be large, pairwise fitting would be the next thing to try.

Learning to rank is used for search, recommendation and advertisement placement,
and in the same form for ordering candidate grasps, viewpoints and motions. It
is rarely right where the size of the number is used rather than the order, such
as deciding whether to act at all: **ranking tells you which candidate is best,
and never whether the best one is any good.** And it needs one condition this
cell largely fails, which is the lesson of this whole document: the candidates
within a group have to differ in the thing being ranked. When a group is a tie
the training signal is empty, and the fitted model's measured accuracy will look
perfect while telling you nothing. **Check the within-group spread of the label
before building the model.**

### Gradient boosting on tabular inputs

Fit a weak predictor, fit the next one to what the sum of the previous ones got
wrong, add them up, and repeat. With shallow decision trees as the weak
predictors this is **gradient boosting**, and it remains the first thing to
try when the input is a short table of quantities of different kinds rather
than a picture, a sound or a sentence. It needs no rescaling of the
inputs, it expresses a threshold in one question, it trains in seconds on a
processor, and it reports which inputs mattered.

It is normally right on tabular data of up to a few hundred thousand rows, which
covers the great majority of cases where somebody wants a number predicted from
a handful of measurements. It is normally wrong when the input has structure a
tree cannot see: neighbouring pixels of a picture, successive samples of a
sound, words in order. A tree asks about one input at a time, so it cannot
express "this region is crowded" over a grid without a great many questions,
which is precisely why the alternative input discussed above — an occupancy grid
of the zone — would mean changing the model as well.

### Learning a utility rather than a perception

The model here does not say what is on the table. It says how much a given
action would help. That is **utility** or **value** estimation, and what makes
it workable is that the answer is cheap to check: take the action in the
simulator and see what happened. The move has a well known ancestor in
grasping, where nobody could write down a rule saying whether a gripper pose
would hold an object, so attempts were collected and a function was fitted from
the pose to whether it worked — Pinto and Gupta's [*Supersizing
Self-supervision*](https://arxiv.org/abs/1509.06825) (ICRA 2016) is the clearest
example, with a robot making tens of thousands of attempts and labelling each by
whether the object came up. Applied to pushing rather than grasping, the same
move produced Agrawal and colleagues' [*Learning to Poke by
Poking*](https://arxiv.org/abs/1606.07419) (2016), which fits a model relating a
poke to the displacement it caused, and Zeng and colleagues' [*Learning
Synergies Between Pushing and Grasping*](https://arxiv.org/abs/1803.09956)
(2018), which learns where to push and where to grasp in a cluttered bin with
pushes scored by whether they make a later grasp possible.

It is worth noticing that this is not reinforcement learning, and the
distinction is why the pattern is cheap. There is no episode and no reward, only
an input, an attempt and a recorded outcome. The world produces the label.

Utility estimation is used for choosing among actions wherever the outcome can
be simulated or replayed, such as view planning, grasp ranking and move
ordering in games. It is rarely right where the outcome cannot be judged without
doing it for real, because then there is no free set of labels and the problem
becomes reinforcement learning with all of its cost in attempts. And it is
pointless where the utility is a closed-form function of quantities the planner
already holds — which is this cell's case, and the reason the two papers on
pushing above are worth reading against this document rather than as support
for it. Both are set in cluttered bins where the geometry genuinely cannot
write down the good actions: objects overlap, shapes are unknown, and one push
rearranges several things at once. A table with a few upright glasses on it,
each a circle of measured width, is not that case.

The mechanics underneath all of this is older and is not a rule of thumb.
Matthew Mason's *Mechanics and Planning of Manipulator Pushing Operations*
(International Journal of Robotics Research, 1986) is where planar pushing
became a subject with results in it, including which way an object turns when it
is pushed, and Kevin Lynch and Mason's *Stable Pushing: Mechanics,
Controllability, and Planning* (same journal, 1996) works out when a push keeps
an object under control rather than letting it slip away. The lesson those
papers carry into this document is the one the arrangement above keeps
confirming: where the mechanics has an answer, arithmetic gets it, and the
uncertainty that is left sits in the numbers the mechanics needs and nobody
measured — the friction, and the way the weight is distributed under the foot.

## Where it sits among the other five

[The six solutions](overview.md) form a ladder ordered by how much of each one
was fitted in this cell, and this one stands on the lowest rung that has
anything fitted at all.

Against [solution 1](01-one-fixed-nudge.md), the comparison is whether choosing
is worth anything. Solution 1 pushes a glass a fixed fraction of the room it is
short of, straight away from the neighbour whose edge reaches furthest into that
room, and looks again, with no enumeration and nothing fitted. This solution
writes down every safe push and chooses among them. So the gap between the two
measures the value of the whole geometric apparatus, and the gap between this
solution's printed rule and this solution's model measures the value of the
ordering alone. Those are two separate questions and it is worth keeping them
apart.

Against [solution 3](03-imitation-from-demonstrations.md), the comparison is
imitation against enumeration, and the two are connected rather than merely
opposed. Solution 3 fits a policy that emits the push directly, so it can
express motions this solution's candidate set cannot, and it pays for that by
having no structural guarantee of safety: a policy's output space is every push
there is. It also needs demonstrations, and this solution is where they come
from. So the pair measures something quite specific, which is whether a policy
fitted on this teacher's behaviour exceeds the teacher — and the section above
on inheriting a ceiling says why that is a harder thing to achieve than it
sounds.

Against [solution 4](04-a-world-model.md), the comparison is which question
deserved a model, and it is the sharpest comparison in this folder. Both fit
something, and the difference is what. This solution fits a model of **how much
a push would help**, which is a quantity the geometry already computes exactly
from the destination. Solution 4 fits a model of **what a push will actually
do**, which is the quantity the geometry gets wrong, because predicting where a
pushed glass ends up needs the friction and the weight distribution that nobody
here has. The record in this repository already contains a result bearing on
that choice: the learned approach in `03-push-glasses-apart/04-a-world-model`, which is solution 4's
first rung, racked 208 of the 251 glasses in 113 pushes with 15 repeats, where
the geometry alone racked 199 in 212 pushes with 90 repeats, and neither toppled
anything. **The learning that paid in this cell attacked the quantity the
geometry gets wrong, not the quantity it gets right.** That is the single most
useful thing to take from placing these two side by side.

Against [solution 5](05-smolvla-as-it-downloads.md) and [solution
6](06-smolvla-fine-tuned.md), the comparison is scale and origin. Those two are
the same large vision-language-action model, one used exactly as it downloads
and one with its training continued here, and the only difference between them
is that training. Both read a picture rather than a list of measurements and
both emit waypoints rather than push parameters, and the one of them whose
training was continued here needed a rented accelerator for it. This solution
is the other end of the ladder in every one of those respects: a few
hundred shallow trees over eight numbers, trained on a processor, with the
safety held by arithmetic that was written rather than fitted. If a scorecard
ever shows this solution close to those two, the interesting reading is not that
the trees are clever. It is that the geometry was doing most of the work all
along.

← [One fixed nudge, then look again](01-one-fixed-nudge.md) · [Imitation from
demonstrations](03-imitation-from-demonstrations.md) →
