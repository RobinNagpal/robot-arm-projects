# Solution 4 — learned doubt steers the next picture

## In one paragraph

The arm cannot look everywhere, so it has to choose. This solution leaves the
geometry in charge of where the camera may stand — reachable, unoccluded,
plannable — and gives a learned number the smaller job of saying which survivor
is worth the seconds. The number estimates how much doubt a look would remove.
It never admits a pose the arithmetic rejected, and never decides that a cluster
is settled. That ordering is what makes this a hybrid, and what caps the damage
when the estimate is wrong — which is the failure the design is arranged around.

## The problem this solves

Several glasses stand on the table. Four to six of them, all of one kind, the
kind known, at least 150 mm apart, upright and opaque. The arm has to say which
pixels belong to which glass, where each one stands, and how wide its footprint
is. It also has to say, honestly, which glasses it could not separate.

Two things get in the way, and they are different problems.

The first is that **two glasses far apart on the table can land on top of each
other in a picture**. If the camera happens to be in line with both, the near
one covers part of the far one and the grouping step returns a single object.
The projection has thrown away the fact that would have separated them: which
pixels were near and which were far. No amount of work on that picture puts it
back.

The second is that **the camera can no longer stand wherever it likes**. It is
on the wrist, so choosing where it stands means choosing where the whole arm
stands. A viewpoint has to clear the line of sight, the arm's own reach, and the
planner, all at once. With five glasses on the table, a glass can end up with no
usable viewpoint at all.

[`problem.md`](../problem.md) names the failure to watch hardest: a **merge**, two
real glasses reported as one. A split glass looks wrong immediately. A merged
pair looks like one large glass, and everything downstream believes it.

That last sentence is the whole reason this document spends so long on what a
doubt number is. A merge is precisely the case where a perception step is
*confident and wrong*.

## The idea, in plain words

Take the pictures you always take. Work out what is settled and what is not. For
anything not settled, ask where you would have to look for it to become clear,
go and look there, and work it out again. Stop when nothing is doubtful or when
the time budget is spent.

That loop needs a number that says how doubtful each thing is. You can write
that number down as a rule — "a footprint circle wider than 105 mm is
suspicious" — and for this cell such a rule gets you a long way. Or you can fit
it from examples, which is what this solution does.

The reason to fit it is simple: **a hand-written rule can only be suspicious of
what its author knew to distrust.** A fitted one can be suspicious of patterns
nobody wrote down. The reason to be careful about fitting it is just as simple:
a fitted number can be wrong, and a number that is wrong in the confident
direction is worse than no number at all, because it silences the loop.

So the arrangement matters more than the model. The geometry generates the
candidate viewpoints and holds the veto. The learned score only sorts what
survives. The worst a bad sort can do is waste one look, and a hard cap says how
many looks there can be.

## Where it comes from

Three separate lines of work meet here, and it is worth knowing which is which.

**Active perception.** The idea that a camera which can move is not the same
instrument as one that cannot. A fixed camera receives whatever the scene sends
it; a camera on a wrist can be aimed, and the aiming is part of the measurement.
The name is from Ruzena Bajcsy's *Active Perception* (Proceedings of the IEEE,
1988). The claim is that a problem which is unsolvable from one viewpoint,
however clever the processing, is often easy once the camera may move.

**Next best view.** The loop that follows from it. Given what has been seen, and
the viewpoints the camera could reach, which one next? The term is Connolly's,
from *The Determination of Next Best Views* (ICRA, 1985). It was invented for
building a model of an object by photographing it from several sides, and the
score it used was volumetric: how much of the unknown space would this view
resolve.

**Active learning.** A different field with the same shape. When labelling data
costs money, you do not label at random; you label the examples the model is
least sure about. Burr Settles' *Active Learning Literature Survey* (2009) is
the standard summary. The measure of "least sure about" is exactly the
uncertainty number discussed below. The difference here is what a measurement
costs: in active learning it is a human's time, and here it is seconds of arm
motion, which for a run that should take tens of seconds is a much harder
budget.

**Uncertainty in fitted models.** The fourth strand, and the newest. Neural
networks return a score per class that looks like a probability and mostly is
not. A body of work from about 2015 onwards asks how to get a number out of such
a model that can be trusted as a statement of doubt. The useful references are
given in the section on the five sources below.

This solution is the meeting point: an active-perception loop, whose choice of
what to measure next is driven by a fitted estimate of doubt, inside a geometric
filter that does not need the fit to be right.

## How it works, step by step

### First: what "uncertainty" means for a perception step

A perception step returns an answer. **Uncertainty** is a second number returned
beside it, saying how far to trust the first.

The shape of that number follows the shape of the answer. A **detection** — a
rectangle round an object — gets one number for the whole rectangle. A
**segmentation** — a yes-or-no label per pixel — gets one number per pixel, so
the doubt is itself a picture: a map of where the model was guessing. For this
problem the second is the useful one, because the doubt in a merged pair is
concentrated exactly along the seam where one glass ends and the other begins.

Most write-ups stop there, and that is the point at which they go wrong. Three
questions have to be asked of any such number before it is allowed to steer an
arm.

### The three cases, and the only one that matters

![Three cases a doubt number has to tell apart](../../../images/problem-2/04-three-cases-of-doubt.png)

Look at the third panel. The doubt number is low and the answer is wrong, and
the bar looks exactly like the bar in the first panel, where the answer was
right.

The three cases are:

- **Confident and right.** Two masks, two glasses, low doubt. Nothing to do, and
  nothing to spend a look on.
- **Unsure and right.** The answer is correct, but the number is high. The loop
  spends a look it did not need. That costs seconds of arm time. It does not
  cost correctness, and in a system where the arm can refuse a glass rather than
  break it, seconds are the cheaper currency.
- **Confident and wrong.** One mask over two glasses, and low doubt. Nothing is
  flagged, so no look is taken, and the run reports one 232 mm glass. The
  measurement step downstream then tries to measure a profile for an object that
  does not exist.

A doubt number is only worth having if it catches the third case. Every method
below is best at the second case and worst at the third, and any write-up that
does not say so is selling something.

There is a further reason this matters here specifically. The uncertainty over a
merged mask is often *genuinely* low, because the mask is a perfectly good mask
— of two glasses. The model was asked "which pixels are glass?" and got the
right answer. Nothing in that question has an opinion about how many glasses
there are. The doubt has to come from somewhere that does, and in this design
that somewhere is the footprint circle.

### Wrong is not the same as unusual

![Being wrong and being unusual are different things](../../../images/problem-2/04-wrong-or-unusual.png)

The left-hand column of that picture is the one to read. Both cells have
ordinary, familiar-looking inputs; one answer is right and one is wrong, and no
amount of novelty detection tells them apart.

This is the distinction that gets skipped. There are two quite different things
a number can track.

**Novelty**, also called out-of-distribution detection, is high when the input
looks unlike the training data. It is genuinely useful: a model asked about
something it has never seen should say so. Methods that measure it typically
look at where the input lands in the network's own feature space, and ask how
far that is from anything seen during training.

**Error-awareness** is high when the answer is wrong, whatever the input looked
like. This is what the loop actually wants and it is much harder to get.

The two coincide in one corner — an unusual input that also produces a wrong
answer — which is the corner most papers are scored on. They come apart in the
corner that matters here: a perfectly ordinary picture, from the same simulator,
the same camera and the same kind of glass as every training example, where the
model has still merged two objects. Nothing is unusual, because nothing is. A
novelty score sees exactly nothing.

For this cell that has a blunt practical consequence. Everything the model will
ever see comes out of one simulator, through one camera, with one kind of glass
on the table. The right-hand column of the picture is nearly empty, so novelty
detection buys almost nothing — until [problem 4](../../problem-4/problem.md),
where the kind is no longer known and four kinds may share a table. Then it
buys a great deal, and a badly calibrated model is most confident precisely on
the shape it has never seen.

### Two kinds of doubt, and only one is worth an arm move

A second split, and this one is standard.

**Aleatoric** doubt is noise in the measurement. Depth readings jitter; the edge
of a silhouette falls between two pixels. Taking the same picture again from the
same place does not remove it, because the ambiguity is in the measurement
itself.

**Epistemic** doubt is the model not knowing. A different picture can remove it,
because the information was available and was simply not in the picture you
took. Kendall and Gal set the two side by side for computer vision in [*What
Uncertainties Do We Need in Bayesian Deep Learning for Computer
Vision?*](https://arxiv.org/abs/1703.04977).

Only epistemic doubt justifies moving the arm. A merge is epistemic almost by
definition: the fact that separates the two glasses exists, it is simply not
present in a picture taken in line with both. That is why this problem responds
to a new viewpoint at all, and it is also why the estimate ought to be able to
tell the two apart. Several of the methods below can, at least in principle;
whether they do well enough to matter here is uncertain and would have to be
measured.

### Five ways to get the number

![Five sources of a doubt number, and what each costs](../../../images/problem-2/04-five-sources-of-doubt.png)

Read the last column: on this machine the differences at inference time are
almost irrelevant, and the differences in training cost are not.

**Predictive entropy.** A segmentation model usually ends in a *softmax*: a
layer that turns raw scores into numbers between zero and one that sum to one,
per pixel. Entropy measures how spread out those numbers are. For a two-class
choice the entropy in bits is
`-(p log2 p + (1-p) log2 (1-p))`: one full bit at p = 0.5, 0.47 bits at p = 0.9,
0.14 bits at p = 0.98. It costs one forward pass, which is to say nothing, and
it is what almost everyone uses first.

Its weakness is that softmax outputs are badly calibrated — they are
systematically more confident than they should be. Guo and colleagues measured
this across several architectures in [*On Calibration of Modern Neural
Networks*](https://arxiv.org/abs/1706.04599). A confidently wrong answer comes
back with confidently low entropy, which is the third panel of the first
picture. Hendrycks and Gimpel's maximum-softmax-probability baseline (ICLR 2017)
is the same quantity used for novelty detection, and it is a baseline precisely
because it is the weakest thing that works at all.

**Monte Carlo dropout.** *Dropout* is a training trick: switch a random subset
of the network's units off on each training step so the network cannot lean on
any one of them. It is normally switched off when the model is used. Leave it
on, run the same picture ten times, and you get ten slightly different answers;
their spread is an estimate of the model's own uncertainty. Gal and Ghahramani
gave the argument for treating this as an approximation to Bayesian inference in
[*Dropout as a Bayesian Approximation*](https://arxiv.org/abs/1506.02142), and
[Bayesian SegNet](https://arxiv.org/abs/1511.02680) is the per-pixel version.
Cost: ten forward passes instead of one, and dropout layers in the network.

**Ensembles.** Train five copies of the same network with different random
seeds, run all five, and measure how far apart their answers are. Where they
agree, the answer is determined by the data; where they disagree, it was
determined by the seed. [Deep
ensembles](https://arxiv.org/abs/1612.01474) win most published comparisons of
uncertainty methods and cost the most, because the training cost multiplies by
the number of copies.

**Evidential and Bayesian deep learning.** Instead of predicting a probability,
predict a *distribution over* probabilities — a statement not just of "70 per
cent glass" but of how much evidence stands behind that 70 per cent. One forward
pass returns both the answer and the strength of the evidence, so a model can
say "I have seen very little like this" without being run ten times. Sensoy and
colleagues set out the classification version in [*Evidential Deep Learning to
Quantify Classification Uncertainty*](https://arxiv.org/abs/1806.01768); Amini
and colleagues did the regression version in [*Deep Evidential
Regression*](https://arxiv.org/abs/1910.02600). The cost is a different training
loss and a fresh set of things to get wrong; the evidence strength needs its own
calibration check, exactly like a softmax does.

**Disagreement between two views.** No model at all. The survey already takes
two pictures at each station, 120 mm apart. Segment both, project each onto the
table, and measure how far apart the two put the same glass. A pixel that
genuinely belongs to a near glass moves one way between the two views; a pixel
wrongly assigned to it moves differently, and the projected footprint wobbles.
At the 450 mm survey height one pixel covers 450 / 277.1 = **1.6 mm** of table,
so a disagreement of more than a few millimetres is not depth noise. This costs
nothing, because both pictures have already been taken and paid for.

**Which of these suit a machine with no NVIDIA card?** All of them, at inference
— and that is the wrong question. A small segmenter on a 320 x 240 picture runs
in a small number of milliseconds on Apple Silicon, whether through
[PyTorch](https://github.com/pytorch/pytorch)'s CPU path or its Metal backend.
Exactly how many milliseconds is uncertain and has to be measured, but the order
is clear: ten forward passes are still thousands of times cheaper than one arm
move. What actually costs is training. Predictive entropy and MC dropout add no
training at all. Evidential methods add a new loss and a new calibration
problem. Ensembles multiply the training by five, which turns one overnight job
into five. Two-view disagreement adds nothing to either.

PyTorch is BSD-3-Clause.
[TorchUncertainty](https://github.com/ENSTA-U2IS-AI/torch-uncertainty) and
[Laplace](https://github.com/aleximmer/Laplace) package several of these methods
so you do not implement them yourself; both look permissively licensed, but the
licence file should be read rather than taken on trust here — treat the exact
terms as uncertain.

### Calibration: the check that makes the number mean something

![What a calibration check looks like](../../../images/problem-2/04-calibration.png)

The gap between the red curve and the dashed diagonal is the thing to look at:
where the model says 95 and is right 72, the loop is being talked out of exactly
the looks it most needed.

A doubt number is calibrated when its claims are true on average: of the cases
where it claims 90 per cent confidence, about 90 per cent should be right. The
check is mechanical:

1. Run the whole pipeline over a few hundred spawned arrangements.
2. Put every prediction in a bin by the confidence it claimed — 0.5 to 0.6, 0.6
   to 0.7, and so on.
3. For each bin, work out what fraction were actually right, scored against the
   simulator's own record of what it spawned.
4. Plot claimed against observed. A perfectly calibrated model sits on the
   diagonal. A curve below the diagonal is overconfident, which is the usual
   direction and the dangerous one.

The single-number summary of that plot is the average gap, weighted by how many
predictions fell in each bin, which the literature calls expected calibration
error. The weighting matters, and the right-hand panel shows why: nearly all
predictions claim high confidence, so a gap in the top bin costs far more than
the same gap in the middle.

The cheap repair is **temperature scaling**: divide the network's raw scores by
a single number before the softmax, and fit that number on data held back from
training. One parameter, fitted in seconds, and Guo and colleagues found it
fixed most of the gap. It does not make a wrong answer right. It makes the
model's claim about that answer honest, which is all the loop needs.

Until that plot exists for this cell, the doubt number is a heuristic that
happens to live in a weights file. That is not an argument against fitting it.
It is an argument for measuring it before trusting it, and it is cheap here:
the simulator knows what it spawned, so the labels cost nothing.

### The classical half: information gain over an occupancy map

The other half of the hybrid is the part that has been done with arithmetic
since the 1980s, and it is worth understanding properly before deciding not to
use all of it.

An **occupancy map** cuts the room into small cubes and stores, for each cube, a
probability that it is occupied. The idea is Moravec and Elfes', from *High
resolution maps from wide angle sonar* (ICRA, 1985). A cube at 0.5 is a cube you
know nothing about. A cube at 0.02 is one you are fairly sure is empty.

The doubt in a single cube is its entropy, by the same formula as before: one
bit at 0.5, 0.14 bits at 0.02. The doubt in the whole map is the sum over all
cubes. **Information gain** for a candidate viewpoint is the expected drop in
that sum: cast one ray per pixel from the pose the camera would occupy, walk
along each ray through the cubes it crosses, and add up the entropy those
observations would resolve. Whichever pose resolves the most is the next best
view. Isler and colleagues (ICRA, 2016) and Delmerico and colleagues
(*Autonomous Robots*, 2018) work through the variants and compare them.

[OctoMap](https://octomap.github.io/) is the standard implementation (Hornung
and colleagues, *Autonomous Robots*, 2013). It stores the cubes in an octree — a
tree that keeps one large node for a large empty region instead of a million
small ones — which is what makes the memory tolerable. The core library is
BSD-3-Clause; note that the octovis viewer and the dynamicEDT3D extension
shipped alongside it are under different, more restrictive terms, so check
before linking anything. MoveIt 2 (BSD-3-Clause, https://moveit.ai/) already
maintains an occupancy map through its occupancy map monitor, so in this project
the structure exists whether or not this solution is built.

**Is it feasible on a processor with no graphics card?** Comfortably, at this
scale. The objects stand in a zone 320 x 360 mm and are at most 230 mm tall. At
5 mm cubes that is 64 x 72 x 46, about **212,000 cubes**. One candidate
viewpoint casts one ray per pixel, so **76,800 rays**, each crossing a few tens
of cubes. That is a few million cube visits: milliseconds in compiled code, and
two dozen candidates still comfortably under a second. It is plain integer and
floating-point work, with nothing that wants CUDA.

So the classical score is affordable. The reason it is not the whole answer is
that it answers a different question. Occupancy entropy asks *where is the room
unmapped*. The doubt here is *is this one glass or two*, and both readings of a
merged pair produce a perfectly well-mapped table. The volumetric score would
happily send the arm to look at the empty half of the table, where there is more
unknown space and nothing anyone needs to know.

What survives from it is the *shape* of the idea: score a candidate by the doubt
it would remove, not by how convenient it is. This solution keeps that shape and
replaces the volumetric measure of doubt with one aimed at the actual question.

### The ordering, which is what makes this a hybrid

![The geometry generates and vetoes; the model only sorts](../../../images/problem-2/04-geometry-then-model.png)

Note that the numbers only ever fall. The learned stage takes seven candidates
and returns the same seven in a different order.

This is the part to get right, because it is what the rest of the design leans
on. Candidates are generated and filtered **geometrically, before anything
learned runs**.

1. **Generate.** Problem 1's standoff routine already produces nine directions
   round a target at 380 mm, level, 120 mm above the table. Make it 24 at
   15-degree spacing; generating candidates is free.
2. **Reach.** The camera lands at the cluster's position plus 380 mm along the
   chosen direction. That point has to be between 300 and 780 mm from the arm's
   base. One square root per candidate.
3. **Line of sight.** Reject any candidate whose sight line to the target passes
   through another cluster's fitted footprint circle. A line-circle test per
   pair.
4. **Plannability.** Run inverse kinematics on what is left — MoveIt 2's
   `setFromIK`, milliseconds each — and drop anything the arm cannot actually
   hold.

Only now does the model see anything, and all it does is sort. It cannot propose
a pose. It cannot re-admit a pose the geometry rejected. It cannot declare a
cluster resolved.

Three consequences follow, and they are the argument for the whole arrangement:

- **A bad ordering costs one wasted look**, bounded by the cap. It cannot cost a
  collision, because every candidate passed the reach and planning checks before
  the model saw it. It cannot cost a merge, because the merge check is
  geometric.
- **The system degrades to something that works.** Delete the weights file and
  the filter still returns a list of reachable, unoccluded, plannable
  viewpoints. Sort that list by the printed rule and you have
  [solution 3](solution-overview.md#solution-3--move-the-camera) exactly.
- **The model's job is small enough to fit.** Learning "which of seven
  pre-approved poses is best" needs far less data than learning "find all the
  objects", and it trains on a laptop.

### What the model is actually trained to predict

One design decision here is easy to get wrong, and getting it wrong reintroduces
the failure the rest of the design was built to survive.

The obvious target is *the expected drop in the model's own uncertainty*. It is
the textbook choice and it is what makes this solution the one it is. But taken
alone it has a hole in it: if the perception step is confidently wrong, there is
no uncertainty to drop, so every candidate scores near zero and the ordering
carries no information. The estimate fails in exactly the case where it is
needed.

The repair is to make the doubt a small vector rather than one number, and to
train the score on the whole of it:

- the mean per-pixel entropy over the cluster's mask — the model's own doubt;
- the residual of the footprint circle fit against the kind's 45 to 105 mm range
  — geometric doubt, which owes nothing to the model;
- the disagreement between the station's two views — model-free doubt, already
  paid for.

The learned part is then a predictor of how far that vector would fall if the
camera went to a given pose. Where the model's own doubt is real, it dominates.
Where the model is confidently wrong, the geometric component still has
something to say, and the score still orders sensibly. Making a model's own
confidence the sole currency of doubt is the mistake; the geometry has to be in
the currency too.

**Training data is free.** Spawn an arrangement in Gazebo. Run the survey. Note
which clusters are doubtful and by how much. Pick a candidate pose, render the
view the camera would get from it, run the geometry again, and measure how far
the doubt actually fell. That pair — the state and the pose in, the measured
drop out — is one training example, and the simulator produces them without an
arm moving and without anyone labelling anything. [Gazebo](https://gazebosim.org/)
is Apache-2.0 and is already running. A few thousand examples is an overnight
job on this machine.

One honest note on where this sits relative to its neighbour. Predicting
*whether the answer changes* — did this cluster become two in-range circles, yes
or no — is a more direct target than predicting how far a doubt number falls,
and that is a different solution in this folder, "learn which viewpoints pay
off". The difference is real but small: this solution's continuous doubt also
tells the loop *whether to look at all* and *when to stop*, where a
does-it-change classifier only ranks poses and needs something else to decide
that.

## How it works here

The cell is fixed, and the numbers decide most of the design.

**The camera.** Wrist-mounted RGB-D, 320 x 240 pixels, 60-degree horizontal
field of view, focal length fx = fy = 277.1 pixels, useful range 0.05 to 3.0 m.
It moves with the arm, so a **viewpoint costs seconds and a picture costs
milliseconds**. That single asymmetry drives everything below: take more
pictures from each place you go, and go to fewer places.

**The survey.** Three fixed stations at 450 mm above the table, two pictures per
station 120 mm apart. One picture covers about 520 x 390 mm of table, so about
1.6 mm per pixel. The survey is not learned and must not be: an adaptive method
needs a belief to start from, and at the beginning there is none.

**The objects.** Four to six glasses of one known kind, standing in a zone
320 x 360 mm, at least 150 mm apart, 65 to 230 mm tall, footprints 45 to 105 mm
across.

**The doubt test.** After the survey, group the points on the table and fit a
circle to each cluster's footprint. A cluster is doubtful if any of these hold:

- the fitted circle is outside 45 to 105 mm;
- two circles fit the cluster no better than one, so the split is ambiguous;
- the cluster was seen from only one station, so nothing corroborates it.

The first of those is the one that catches a merge, and it is arithmetic. It
does not need the model, and it fires whatever the model says.

**The candidate poses.** 24 directions at 15-degree spacing round a doubtful
cluster, the camera 380 mm back, level, 120 mm above the table — the same
standoff geometry the next problem needs for its side-on measurement, so a look
taken here is not wasted if it also serves that.

**The filter.** Reach (300 to 780 mm from the base), line of sight, inverse
kinematics, in that order, cheapest first.

**The score.** One forward pass of a small network per surviving candidate.
Seven candidates is seven passes, milliseconds in total.

**The budget.** Two extra looks per cluster, four per run.

## A worked example

The survey has finished. There are five clusters on the table.

Four of them fit footprint circles of 71, 74, 76 and 78 mm. All are inside the
kind's 45 to 105 mm range, so all four are settled.

The fifth fits a circle of **232 mm**. No glass of this kind is that wide. Its
centre is at x = 0.40 m, y = −0.35 m, which is
sqrt(0.40² + 0.35²) = **532 mm** from the arm's base; call it 530.

The mean per-pixel entropy over that cluster's mask is **0.06 bits** — the
segmenter is confident. This is the third panel of the first picture, and it is
the geometric check that flags the cluster, not the model. Budget for the
cluster: two looks.

### Filtering the 24 candidates

Write θ for the angle between the standoff direction and the line running
outward from the arm's base through the cluster. The camera lands 380 mm from
the cluster along that direction, so its distance from the base is

    sqrt(530² + 380² + 2 · 530 · 380 · cos θ)
    = sqrt(425,300 + 402,800 · cos θ)   mm

**Reach.** The 780 mm ceiling needs 425,300 + 402,800 cos θ ≤ 608,400, so
cos θ ≤ 0.455 and θ ≥ **63 degrees**. The 300 mm floor needs
425,300 + 402,800 cos θ ≥ 90,000, so cos θ ≥ −0.832 and θ ≤ **146 degrees**. Of
the 24 directions, the ones whose offset from the outward line falls in that
band are 75, 90, 105, 120 and 135 degrees, on either side. **Ten survive; 14 are
out of reach.**

**Line of sight.** A neighbouring cluster sits to one side, and the sight lines
at −120 and −135 degrees pass through its fitted footprint circle. Worth being
concrete about what that means: the neighbour would then be 480 mm from the
camera, and its 105 mm footprint spans
105 × 277.1 / 480 = **61 pixels** of the 320 across, sitting on top of the
target. **Eight left.**

**Plannability.** `setFromIK` fails on +135 degrees. **Seven are scored.**

### The ordering

![The rule's order and the model's order, over the same seven](../../../images/problem-2/04-rule-and-model-orders.png)

The bar chart is ordered the way the printed rule takes the candidates, and the
first bar it takes is zero.

Here is what the geometry could not know. The 232 mm cluster is two glasses of
78 and 74 mm footprint, standing 155 mm apart, and the line joining them runs at
120 degrees to the outward line from the base. Both are inside **one** fitted
circle, so no line-of-sight test has anything to test against.

How far apart the two land in a picture taken from angle θ is the separation
seen edge-on, converted to pixels:

    155 mm × (277.1 / 380 mm per pixel) × |sin(θ − 120°)|
    = 113 px × |sin(θ − 120°)|

And they stop touching only when that exceeds the sum of their half-widths in
pixels:

    (39 + 37) mm × 277.1 / 380 = 55 px

| θ | camera, from base | the two glasses land | does the look work? |
| --- | --- | --- | --- |
| +75° | 728 mm | 80 px | yes |
| +90° | 652 mm | 57 px | just |
| +105° | 567 mm | 29 px | no |
| +120° | 473 mm | 0 px | no — dead in line |
| −75° | 728 mm | 29 px | no |
| −90° | 652 mm | 57 px | just |
| −105° | 567 mm | 80 px | yes |

**What the printed rule does.** Every survivor has a clear line of sight to the
cluster, because the filter has already seen to that, so the rule falls through
to its tiebreak: prefer least reach. That orders them +120, +105, −105, +90,
−90, +75, −75. Its first pick is +120 degrees, which is the one direction that
looks straight along the line joining the two glasses. The look reproduces the
merge exactly. Its second pick, +105, puts them 29 pixels apart, which is still
inside a single silhouette. **Both of the cluster's two looks are spent and
nothing is resolved**, and the run reports a cluster it could in fact have
separated.

**What the learned score does.** It orders them −105, +75, +90, −90, +105, −75,
+120, and takes −105 first. The two candidates at 80 pixels tie on separation,
and the tiebreak goes to −105 because the camera sits 567 mm from the base
rather than 728 — less extension, less wobble, less distance to travel. The
model was never told that; it came out of training on what actually happened
when the arm went there.

The illustrative part here is the model's ordering. The pixel arithmetic in the
table is not illustrative: it is what the camera would see.

### The look itself

Plan, move, settle: seconds, and the only real cost. Then take **five** pictures
along the 120 mm slide rather than two, because a picture costs milliseconds and
the arm is already there.

The cluster resolves into two circles, 78 and 74 mm, centres 155 mm apart, both
inside the kind's range. One look spent of four.

### The counter-argument, which is the honest part

Look again at what the model learned to prefer: viewpoints across the long axis
of the doubtful cluster. That can be written down.

> Fit an ellipse to the doubtful cluster's footprint points. Take its long axis.
> Sort the surviving candidates by how nearly perpendicular they are to it.

That is four lines of arithmetic, it needs no data, no weights file and no
training run, and on this example it picks the same viewpoint. This is why the
overview marks this solution *the richest version of moving the camera* rather
than something to build first. With one known kind, the thing that makes a look
pay off is one nameable quantity, and a nameable quantity should be named rather
than fitted.

The case for fitting it starts when there is no single quantity to name — when
the kind is unknown, the allowed footprint range is the union of several, and
whether a look pays off depends on the shape as well as the geometry. That is
[problem 4](../../problem-4/problem.md), not this one.

## The feedback loop

This is the part of the solution that does the work, so it is worth setting out
in full.

![The loop, with the budget as the way out](../../../images/problem-2/04-the-loop.png)

Follow the right-hand edge: there are three ways out, and one of them is simply
running out of time.

### The five steps

**0. Survey.** Three fixed stations, two pictures each, at 450 mm. Not learned,
and not adaptive. An adaptive method needs a belief about the table to choose
its first viewpoint, and before the first picture there is none. The survey
assumes nothing, covers the whole 320 x 360 mm zone, and hands back a first
belief. Everything after it is the tail of the survey, not a replacement for it.

**1. Measure.** Lift the masked pixels onto the table using their depth, group
the resulting points, and fit a footprint circle to each group. This is
arithmetic, and it is what produces the belief the rest of the loop reasons
about: a position, a footprint and a confidence per cluster.

**2. Score the doubt.** For every cluster, assemble the doubt vector: the mean
per-pixel entropy over its mask, the circle-fit residual against the 45 to
105 mm range, and the disagreement between the station's two views. A cluster is
doubtful if the geometric test fires, or if the model's doubt is above
threshold, or if it was seen from one station only. **Any one of the three is
enough.** This is a deliberate choice: the tests are ORed, not ANDed, so a
silent model cannot suppress a geometric complaint.

If nothing is doubtful, the loop is done. Out come one mask, one position and
one rough width per glass.

**3. Choose a viewpoint.** Take the most doubtful cluster. Generate 24
candidates round it. Apply the geometric filter — reach, line of sight, inverse
kinematics — and keep the survivors. Score the survivors with the model and take
the best.

If no candidate survives the filter, that is not a perception failure. It is a
fact about where the glasses are standing, and the only remedy is to move one,
which is [problem 3](../../problem-3/problem.md)'s job. Report the cluster and stop
working on it.

**4. Move and photograph.** Plan, move, settle. Then take several pictures while
the arm is there, because pictures are free relative to the journey.

**Then back to step 1**, with the new pictures added to the belief. Note that it
is a *re-measure*, not a patch: the clustering and the circle fitting run again
over everything, so a look can also change the answer for a cluster it was not
aimed at.

### The budget, which is the exit condition

![Where the seconds go, and what the cap is for](../../../images/problem-2/04-budget-and-the-cap.png)

The left panel is in units of one station's worth of arm motion, because the
absolute number has to be measured rather than asserted.

Write *t* for the cost of one plan, move and settle — one station's worth of arm
motion. It has to be timed from the survey routine as it actually runs, not
guessed in a document.

- The survey is **3t**.
- With the cap of four extra looks, the worst case is **7t**: a bit more than
  twice the survey.
- Six clusters each taking two looks would be **15t**, five times the survey.
  For a run that is supposed to take tens of seconds, that does not fit.

Hence two caps, not one:

- **Two looks per cluster.** Stops a single hopeless cluster eating everything.
- **Four looks per run.** Stops six moderately doubtful clusters between them
  eating everything.

The right panel of the picture shows why both are needed. One cluster resolves
on its first look and gives the remaining three back. Another — a pair that
happens to lie in line with every pose the geometry left — never resolves, and
without the per-cluster cap it would take all four, each look scoring well and
none of them helping.

When a cap fires, the cluster is reported as unresolved, with the reason. That
is a result, not a failure: [`problem.md`](../problem.md) asks for exactly this
list, and it is the input to problem 3.

### What the loop costs in computation, which is nothing

Worth stating plainly, because the instinct runs the other way. Per doubtful
cluster: 24 square roots for the reach test, about a hundred line-circle tests
for the sight lines, ten inverse kinematics calls at milliseconds each, and
seven forward passes of a small network. Even the full volumetric score — 76,800
rays over 212,000 cubes — would be milliseconds.

Against *t*, measured in seconds, all of that is free. **The thing to economise
on is the number of times the arm moves, not the arithmetic.** A design that
saves computation by taking one more look has the trade exactly backwards.

## What it needs

**Libraries.**

- [PyTorch](https://github.com/pytorch/pytorch) — BSD-3-Clause — the segmenter,
  the scoring network, and dropout and ensembling for free.
- [Gazebo](https://gazebosim.org/) — Apache-2.0 — already running, and the
  source of every training example.
- [MoveIt 2](https://moveit.ai/) — BSD-3-Clause — `setFromIK` for the
  plannability filter, and the occupancy map if the volumetric score is ever
  wanted.
- [OpenCV](https://opencv.org/) — Apache-2.0 from version 4.5 — masks,
  connected components, ellipse fitting.
- [NumPy](https://numpy.org/) — BSD-3-Clause — the projection and the circle
  fits.
- [OctoMap](https://octomap.github.io/) — core library BSD-3-Clause, with
  differently licensed extensions alongside it — only if the volumetric score is
  built.
- Optionally
  [TorchUncertainty](https://github.com/ENSTA-U2IS-AI/torch-uncertainty) or
  [Laplace](https://github.com/aleximmer/Laplace) for the packaged uncertainty
  methods. Licences look permissive; treat them as uncertain until read.

**Data.** None from outside. Every example comes from Gazebo: spawn an
arrangement, survey it, note the doubtful clusters, render a candidate view,
re-run the geometry, record the drop. A few thousand examples, generated
unattended.

**Hardware.** The Apple Silicon Mac the project already runs on. No NVIDIA card
and no CUDA at any point. Training is an overnight job for a small network;
inference is milliseconds. How many milliseconds exactly is uncertain and should
be measured before the numbers above are relied on.

**Time.** The geometric filter is needed whether or not the model is built, so
it is not a cost of this solution. On top of it: a day or so to wire up the
example generator, an overnight training run, and then the calibration
measurement, which is the part most likely to be skipped and the part that
decides whether any of it was worth doing.

## What it is good at

**Spending arm time in proportion to doubt.** A fixed rule spends the same
effort on a cluster that is obviously fine and one that is obviously not. This
spends none on the first and all of it on the second, and the amount is decided
during the run rather than before it.

**Degrading to something that works.** Remove the weights and the geometry still
returns reachable, unoccluded, plannable viewpoints in the printed rule's order.
That is a complete, working solution. The model is an improvement on an ordering
that already exists, not a dependency.

**Bounded failure.** A bad ordering costs one look. The cap turns "costs one
look" into "costs at most four", and nothing about the safety of the arm or the
correctness of the merge test depends on the model being right.

**Cheap labels.** The simulator knows the truth, so both the training set and
the calibration check cost machine time rather than anybody's attention.

**Reusable looks.** The candidate poses are the standoff geometry the next
problem needs anyway — 380 mm back, level, 120 mm above the table — so a look
taken to resolve a merge can double as the start of a measurement.

## What it is bad at

**Buying an ordering that was already good enough.** With one known kind, the
geometric filter usually leaves several viewpoints that all work, and the
printed rule picks an acceptable one most of the time. The worked example above
was constructed to be a case where it does not, and such cases exist, but the
average gain over a decent rule is small. That is the overview's verdict and it
is the right one.

**A doubt that is a short list of identical questions.** Everything on this
table is the same kind of glass, so the doubt is *one glass or two*, asked five
times. Learning shines where the question is graded and varied. Here it is very
nearly binary, and a threshold answers a binary question perfectly well.

**Anything that needs the model to be the authority.** By construction the model
cannot declare a cluster resolved. If you want a single learned component that
settles the question, this is not that solution — see the learned verifier, or
the segmenter trained from scratch.

**Real glassware.** Everything here starts from depth readings. Real glass is
transparent, and a depth camera does not return a usable surface for it. The
whole belief — clusters, footprint circles, the geometric doubt term — assumes
the simulator's opaque stand-ins.

## How it fails

**The estimate itself is wrong, in the confident direction.** This is the
failure that matters and the one everything above is arranged around. A merged
pair comes back as one clean mask with low entropy everywhere. Nothing is
flagged, no look is taken, and the run reports one large glass.

Five guards, and **not one of them is the model**:

1. **The geometry decides, always.** Whether a cluster counts as resolved is the
   footprint circle against the kind's 45 to 105 mm range. It is never the
   entropy. A confidently wrong model cannot make a 232 mm circle acceptable.
2. **A floor the score cannot lower.** A cluster whose circle is out of range, or
   that was seen from one station only, gets a look regardless of what the model
   says. The model may reorder the candidates; it may not empty the queue.
3. **Hard caps on looks.** Two per cluster, four per run. This bounds the cost of
   every mistake the model can make, including the mistakes nobody anticipated.
4. **Fall back to the rule.** If the weights file is missing, if a score is not a
   finite number, or if scoring takes longer than its allotted slice, sort by the
   printed rule and carry on. The run must never depend on the file existing.
5. **The model-free cross-check.** The two views at each station are 120 mm
   apart and cost nothing extra. If they disagree about where a glass stands by
   more than depth noise allows — more than a few millimetres, at 1.6 mm per
   pixel — believe the disagreement over the model's confidence.

And one measurement, which is not a guard but tells you whether the guards are
carrying the whole weight: run the calibration check against the simulator's
record. If the 90-per-cent-confident predictions are right far less than 90 per
cent of the time, the number is decoration.

**Out of distribution.** The model is trained on one kind of glass. Problem 4
puts four kinds on a table, and an unfamiliar shape is exactly where a
miscalibrated model is most confident. The caps are what stop that from turning
into a run that never ends.

**Thrashing.** A cluster that no reachable viewpoint can resolve pulls look after
look, each one scoring well and none of them helping, because the score predicts
a drop that never arrives. The per-cluster cap is the only thing that stops it.

**The belief is wrong where the filter cannot see it.** The line-of-sight test
works on fitted footprint circles. A merged pair modelled as one wide circle
predicts its own occlusions wrongly — and, as the worked example showed, cannot
see the occlusion *inside* itself at all. This is not a flaw in the learned part;
it is a limit of the geometric half, and it is the thing the learned part is
there to compensate for.

**No candidate survives.** All 24 directions out of reach, blocked or
unplannable. Not a failure of perception, and not something a better model would
fix. It is a fact about where the glasses stand, and the remedy is to move one.

## When it would be the right choice

When the doubt stops being a short list of identical questions.

In this problem it does not. The kind is known, the allowed footprint range is a
single interval, and *one glass or two* is asked five times. A printed rule — and
especially the ellipse-axis rule above — answers it, and the geometric filter
does the part that actually protects the arm.

It becomes the right choice when several of these hold:

- **The doubt is graded rather than binary.** Several kinds on the table, each
  with its own allowed range, so a footprint of 108 mm is mildly odd for one kind
  and impossible for another.
- **What makes a viewpoint pay off depends on more than one nameable quantity.**
  When it is just the long axis of the cluster, name it.
- **Arm time is genuinely scarce relative to the number of doubtful things.**
  With four looks and one doubtful cluster, the ordering barely matters. With
  four looks and five doubtful clusters, it decides which ones get resolved.
- **The calibration plot has been drawn and is close to the diagonal.** Without
  it, this is a heuristic with extra steps and a file to keep in sync.

The sensible order of work follows from that. **Build the geometric filter now**,
because the printed rule needs it too and it is where the safety lives. Log the
score and the outcome of every look from the first run onwards. Fit the model
only once those logs show the cheap rule choosing wrongly often enough to be
worth the weights file.

## The general methods behind this

This solution joins two literatures: one about making a model say how sure it
is, and one about deciding what to measure next. Both are general, and the
second is much older than the first.

### Uncertainty quantification in deep learning — a model that reports its own doubt

A network trained the usual way outputs a number between 0 and 1 and will emit
0.99 on an input unlike anything it has seen. Making that number mean something
is a field in itself. The three practical families:

**Monte Carlo dropout** — leave dropout switched on at inference, run the same
input several times, and read the spread (Gal and Ghahramani,
[arXiv:1506.02142](https://arxiv.org/abs/1506.02142)). Cheapest to adopt,
weakest guarantees.

**Deep ensembles** — train several models from different initialisations and
read their disagreement (Lakshminarayanan et al.,
[arXiv:1612.01474](https://arxiv.org/abs/1612.01474)). Consistently the
strongest of the three, and the most expensive, since it multiplies training
cost.

**Evidential and Bayesian methods** — have the network output the parameters of
a distribution rather than a point (Sensoy et al.,
[arXiv:1806.01768](https://arxiv.org/abs/1806.01768)). One forward pass, at the
cost of a less familiar loss.

- **Mostly used for** anything where being wrong is expensive and abstaining is
  cheap: medical imaging, autonomous driving, industrial inspection, and active
  learning, where the doubt is what selects the next thing to label.
- **Rarely right for** settings where the model is wrong in ways it cannot
  represent. Every method here measures *disagreement among plausible models*,
  so a systematic error shared by all of them is invisible. None of it detects
  "my training data did not contain this situation at all" reliably.
- **More:** [uncertainty quantification](https://en.wikipedia.org/wiki/Uncertainty_quantification);
  [ensemble learning](https://en.wikipedia.org/wiki/Ensemble_learning).

### Aleatoric and epistemic uncertainty — two different kinds of not knowing

**Aleatoric** uncertainty is in the data and does not shrink with more of it:
a blurred edge is genuinely ambiguous. **Epistemic** uncertainty is in the
model and does shrink: a shape it has not seen enough of. Only the second is a
reason to go and look again — and the distinction is what makes this solution's
loop sensible rather than superstitious (Kendall and Gal,
[arXiv:1703.04977](https://arxiv.org/abs/1703.04977)).

- **Mostly used for** deciding *what to do* about doubt: epistemic doubt says
  gather more, aleatoric doubt says the measurement will not improve and you
  should abstain or change the sensor.
- **Rarely separable cleanly** in practice. The decomposition is model-relative
  and the two are easy to confuse, which is why the guard below never lets the
  model decide anything on its own.

### Calibration — making a probability mean what it says

A model is **calibrated** when things it calls 90 per cent likely happen 90 per
cent of the time. Modern networks are badly overconfident by default, and the
standard fix is **temperature scaling**: one parameter fitted on held-out data
(Guo et al., [arXiv:1706.04599](https://arxiv.org/abs/1706.04599)). Without it,
a threshold on a confidence is a threshold on an arbitrary number.

- **Mostly used for** any system that acts on a probability rather than an
  argmax — triage, abstention, risk-weighted decisions, and exactly the
  budget-spending this solution does.
- **Rarely optional.** If nothing downstream reads the number as a probability,
  calibration does not matter; the moment a threshold appears, it does.
- **More:** [Platt scaling](https://en.wikipedia.org/wiki/Platt_scaling);
  scikit-learn's [calibration guide](https://scikit-learn.org/stable/modules/calibration.html).

### Active learning and information gain — choosing the most informative next measurement

The general principle is older than the vision problem: given a budget, spend it
on the measurement that most reduces what you do not know. In machine learning
this is **active learning**, where the model picks which example to have
labelled; in robotics it is view planning, where it picks where to stand. Both
score candidates by expected reduction in uncertainty.

- **Mostly used for** settings where measurements are expensive and plentiful in
  choice: labelling budgets, scientific experiment design, robot exploration.
- **Rarely right for** cheap measurements. If another picture costs
  milliseconds, take several and skip the reasoning — which is precisely why
  this cell's *pictures* are taken freely and only its *moves* are planned.
- **More:** Settles,
  [Active Learning Literature Survey](https://burrsettles.com/pub/settles.activelearning.pdf);
  [active learning](https://en.wikipedia.org/wiki/Active_learning_%28machine_learning%29).

## Where it sits

It leans on **cluster on the table**, which supplies the belief the whole loop
reasons about — the footprint circles, and with them the geometric half of the
doubt and the line-of-sight veto — and it is the same loop as **move the
camera**, with the ordering fitted instead of printed; strip the model out and
the two are identical. It competes most directly with **learn which viewpoints
pay off**, which fits the more direct target of whether a look changes the answer
rather than whether a doubt number falls, and it would happily consume the doubt
signal that **a learned verifier over the clusters** produces, since that
verifier is a better source of the one-glass-or-two question than a segmenter's
softmax will ever be.
