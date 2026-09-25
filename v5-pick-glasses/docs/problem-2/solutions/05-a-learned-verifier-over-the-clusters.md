# Solution 5 — a learned verifier over the clusters

## In one paragraph

Do not learn the perception. The geometry already separates almost every glass
on the table, in millimetres you can print. What it cannot settle is the
handful of groups on the boundary — one object, or two? So learn that one
decision, from the thirteen numbers the circle fit has already produced. The
input is small, so the model trains in minutes on a laptop. Its most useful
answer is "I cannot tell", which asks the arm for one more picture. Delete the
weights file and the geometry answers as before.

## The problem this solves

Several glasses stand on a table. They are all of one kind, that kind is known,
and the arm has to say which pixels belong to which glass. The awkward part is
that two glasses far apart on the table can land on top of each other in a
photograph, and the flood fill that works perfectly for one glass then returns
a single blob.

[Solution 2, cluster on the table](solution-overview.md#solution-2--cluster-on-the-table),
fixes that properly. Turn every pixel with a depth reading into a point in the
room. Drop each point straight down onto the table. Group the resulting dots by
how close they are to each other. Fit a circle to each group, and check the
circle's diameter against the range this kind of glass is allowed to have.

That works. It is exact, it is fast, it needs no training data, and every step
is a number you can print. It gets almost everything right.

Almost. The circle fit has to commit to a threshold, and reality has no step in
it there.

![The residue is one narrow band](../../../images/problem-2/05-the-ambiguous-band.png)

Each dot is one group of points the clustering produced, placed by the diameter
of the circle fitted to it. The blue row was really one glass, the orange row
was really two. They barely overlap — which is why the rule works — but the
shaded band holds both, and a rule that must answer "one or two" from that one
number has to guess inside it. The ringed orange dot at 89 millimetres is the
worked example further down: two glasses, fitted as one circle, inside the
allowed range, and therefore silently accepted.

That last case is the one `problem.md` says to watch hardest. A **merged** pair
— two real glasses reported as one — does not look wrong downstream. It looks
like one large glass, and everything after it believes that.

## The idea, in plain words

There are two honest ways to use a model here.

The first is to hand it the whole job: give it the picture, let it return one
mask per glass. That is a real and respectable approach, and it is
[solution 7](solution-overview.md#solution-7--a-segmenter-trained-from-scratch)
and [solution 8](solution-overview.md#solution-8--per-pixel-votes-for-the-centre).
It also means the model owns every answer, including the thousands of easy ones
the geometry already gets right for free.

The second is to leave the geometry exactly as it is, and add a model with one
job: *look at this one doubtful group and tell me whether it is one object or
two.*

![Where the verifier sits](../../../images/problem-2/05-where-the-verifier-sits.png)

Everything grey already exists. The only new thing is the dashed box, and it is
asked about the minority of groups the circle fit could not settle. Look at
what goes into it — not pixels, but thirteen numbers the fit has already
computed — and at what comes out: three answers, not two.

The third answer is the interesting one, and the rest of this document keeps
coming back to it. A verifier that can say "I cannot tell" is not a classifier
any more. It is the doubt signal that a feedback loop needs.

## Where it comes from

### The pattern, and what to call it

The pattern is: **do not learn the whole task, learn the one decision the rules
do badly.** It turns up everywhere, under several names, and none of them has
won.

**Verifier** is the name used when a cheap stage proposes an answer and a
second stage checks it. That is the closest fit here, and it is the name this
document uses.

**Cascade** is the name used when cheap tests run first and an expensive test
runs only on whatever survives. The classic example is
[OpenCV's cascade classifier](https://docs.opencv.org/4.x/db/d28/tutorial_cascade_classifier.html)
for face detection — a chain of stages, each one throwing away most of what
reaches it, so the costly stage sees very little. OpenCV is Apache-2.0
([licence](https://github.com/opencv/opencv/blob/4.x/LICENSE)).

**A learned gate** is the name used when the model does not answer the question
itself, but picks which branch of a rule-based system runs.

**Residual learning** is used in conversation to mean "learn what the rules got
wrong". Be careful with it in writing: in the literature the phrase means the
skip connections inside a ResNet
([He et al.](https://arxiv.org/abs/1512.03385)), which is a different idea
entirely.

So: no settled term. If you say "a small learned verifier over the geometric
clusters", nobody will misunderstand you, and that is about as good as the
naming gets.

### Why the pattern exists

It exists because the two families of method fail in opposite directions, and
somebody noticed you can put the failure of one inside the guard rails of the
other.

A programmed rule is exact, cheap, inspectable and needs no data. Its weakness
is that it must commit to a number. Ninety millimetres is one glass; ninety-one
is not. Nothing in the physical world changes at 90 mm, so the rule is wrong in
a band around its own threshold, and no amount of care in choosing the number
removes the band. It only moves it.

A fitted model has a soft boundary instead of a step, and it can use several
weak pieces of evidence at once, which is exactly what a hand-written rule is
bad at. Its weaknesses are that it needs examples, cannot explain itself, and
goes stale when the world changes underneath it.

Ask a model one narrow question and all three weaknesses shrink at once. That
is the whole argument.

![Learn the whole task, or learn the one decision](../../../images/problem-2/05-whole-task-or-one-decision.png)

Read the last three rows first. They are the ones that decide whether a
component belongs in a machine that moves.

## How it works, step by step

### 1. Decide which groups get asked about

The verifier is not run on everything. It is run on the groups the geometry
could not settle, and *drawing that band is a design decision, not a detail*.
Draw it too narrow and the model never sees the cases that matter; draw it too
wide and you are paying a model to answer questions arithmetic already
answered.

A group is doubtful, and goes to the verifier, if any of these hold:

- the one-circle diameter is within about 8 mm of either end of the kind's
  allowed range — near the step, in other words, on either side of it;
- the one-circle fit is poor, meaning its RMS residual is above about 4 mm;
- only one station saw it.

The second condition is the one that catches the worked example below, and it
is the reason the trigger cannot be a rule about diameter alone. A merged pair
can fit a perfectly in-range circle. What it cannot do is fit it *well*.

A word on "RMS residual", since the rest of this leans on it. Fit a circle to a
set of boundary points. Each point is some distance from that circle — a few
millimetres in, or a few out. That distance is the **residual**. Square them
all, take the mean, take the square root: that is the **RMS residual**, one
number saying how far the points sit from the circle on average. A real glass
seen properly fits with a residual of about a millimetre or two, because a
glass really is round. A group that is not one round thing does not.

### 2. Turn the group into a row of numbers

This is the step that makes the whole solution cheap, so it is worth being
exact about it.

The model is **not** shown the picture. It is shown a row of numbers that the
clustering and the circle fit have already produced along the way.

![What the model is shown](../../../images/problem-2/05-the-features.png)

On the left is one genuinely ambiguous group, drawn from the cell's own
geometry. Two glasses stand 88 mm apart with the camera in line with both, so
the near one hides nearly all of the far one. The red spokes are the residuals
of the single-circle fit — look at how long they are on the right-hand side,
where the far glass's few surviving dots drag the fit outwards. In the middle,
the same dots projected onto the line between the two candidate centres: two
humps with a gap between them. On the right, the thirteen numbers all of that
turns into.

Grouped by what they ask:

| What it asks | The numbers |
| --- | --- |
| Is this the right size for one glass? | fitted diameter over the kind's mean diameter; the larger and smaller candidate diameters over the same |
| Is it really round? | RMS residual of the one-circle fit; its single worst residual; RMS residual of the best two-circle fit; the ratio of the first to the third |
| Could it be two things? | gap between the two candidate centres, in fitted radii; the clearance between their two rims; how deep the dip is between the humps |
| Is there enough evidence? | dots per square millimetre against what the camera geometry predicts; how many stations saw it |
| What shape is the cloud? | its height above the table over its footprint width |

**Why features rather than raw pixels.** Four reasons, and the first two matter
most.

*The units are physical.* Every number above is a length in millimetres, or a
ratio of two lengths. None of them changes when the arm stands somewhere else,
because the projection onto the table has already removed the viewpoint. A
model fed raw pixels has to learn the camera — the focal length, the standoff,
the foreshortening — before it can learn anything about glasses, and it has to
relearn all of it the day the camera moves.

*The problem gets small.* Thirteen numbers is a thirteen-dimensional problem. A
320 × 240 crop is a 76,800-dimensional one. That difference is the difference
between a few thousand training examples and tens of thousands, and between
seconds of training and hours of it.

*It is readable.* When the verifier gets one wrong, the thirteen numbers print
beside its answer, and you can usually see why in a few seconds. A wrong answer
from a convolutional network is a wrong answer.

*It cannot cheat.* Given raw pixels, a small model trained on simulator
renderings will happily learn the simulator's lighting, or its background, or
some artefact of its renderer. Features computed in table millimetres give it
nothing of the sort to latch onto.

The honest cost of this choice: a feature is a piece of the answer written down
by hand. If the thirteen numbers do not contain the evidence, no model can
recover it, and something in the picture that a human eye would notice is
simply gone. That is the trade, and for this cell it is a good one, because the
evidence here really is geometric.

### 3. Fit something small

At thirteen inputs and one binary output, the model choice is nearly free — but
two are worth naming.

**A gradient-boosted tree — the one to try first.**
[`HistGradientBoostingClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)
in [scikit-learn](https://scikit-learn.org/) (BSD-3-Clause,
[licence](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING)). A
tree asks a sequence of yes/no questions about single numbers — "is the
residual ratio above 3.2?" — and gradient boosting fits a few hundred small
trees in sequence, each one correcting what the previous ones got wrong. It
suits this problem because the decision genuinely is a set of thresholds
combined, which is what a tree is; because it does not care that the features
are on wildly different scales; and because it trains on a CPU in seconds at
this size.

**A random forest**, which is
[`RandomForestClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html)
in the same library, is the obvious alternative: many independent trees, each
on a random slice of the data, voting. It is simpler to reason about and its
vote share is a more natural probability. It is usually a little less accurate
than boosting on tabular data of this shape, though on thirteen clean features
the difference may not show.

**A very small convolutional network**, in
[PyTorch](https://pytorch.org/) (BSD-3-style,
[licence](https://github.com/pytorch/pytorch/blob/main/LICENSE)), is the answer
if the thirteen numbers turn out not to be enough and a picture of the group is
genuinely needed. A network of a few convolutional layers over a 32 × 32 crop
of the footprint mask trains on this Mac's
[MPS backend](https://pytorch.org/docs/stable/notes/mps.html) in minutes rather
than hours. It is the second thing to try, not the first, because it reopens
every cost the feature row closed.

Why not something larger? Because **this is an Apple Silicon Mac with no NVIDIA
graphics card**. Anything wanting compiled CUDA kernels is not buildable here
at all, and anything wanting a day of fine-tuning cannot be iterated on. See
[`learned-with-hardware.md`](learned-with-hardware.md) for the methods that
were moved out for exactly that reason.

### 4. Get the training data for nothing

The labels come free, and that is the second reason this solution is the first
learned thing worth building.

[Gazebo](https://gazebosim.org/) (Apache-2.0) spawns the glasses. It therefore
knows exactly how many there are and where each one stands. Every group the
clustering produces during a simulated run can be compared against that record
and labelled *one* or *two* without a human looking at anything. No annotation,
no labelling tool, no afternoon lost.

Two things matter about how the data is collected.

**Do not sample uniformly.** A run with glasses scattered at random produces
overwhelmingly easy groups, and a training set of easy groups teaches nothing
about the band. Spawn pairs deliberately: separations from about 60 to 120 mm,
camera stations deliberately placed in line with pairs, some glasses at the
edge of the picture where half their dots are missing. The ambiguity lives
there, so that is where the examples should come from.

**Keep a held-out set.** Fit on one set of runs, measure on runs the model has
never seen. Everything in the next section depends on that being done properly.

An honest note on volume. A few thousand rows is the right order to aim for. If
each simulated arrangement of five glasses yields one or two doubtful groups,
that is a couple of thousand arrangements, each needing a spawn and a handful
of renders. Whether that is one hour or six on this machine is **uncertain** —
it has not been measured — but it is an overnight job at worst, and it can run
unattended.

## How it works here

Put the numbers of this cell to it.

The camera is 320 × 240 with fx = fy = 277.1 pixels, and the survey holds it
450 mm above the table. One pixel therefore covers 450 / 277.1 = **1.62 mm** of
table, so **2.64 mm²** per pixel. A station takes two pictures 120 mm apart, so
a patch of table that both pictures see arrives as about 2 / 2.64 = **0.758
dots per square millimetre**. That is what the density feature is measured
against. It is deliberately crude — a glass's top is nearer the camera than the
table is, so a well-seen footprint comes in above it — and it does not need to
be better than crude, because the model is shown the comparison, not asked to
trust it.

The verifier runs on the CPU in about a millisecond. The picture it can ask for
costs seconds of arm motion, because the camera is on the wrist and moving it
means moving the whole arm. That is three to four orders of magnitude, and it
is the ratio that decides the design: **spend computation freely, spend arm
moves carefully.**

Where the code would go: a feature extractor of about thirty lines sitting on
top of solution 2's clustering, a loader, and a version-pinned model file
checked in beside it. `scikit-learn` would be added to `pixi.toml` from
conda-forge. Nothing else changes.

## A worked example

The numbers below are not invented. They come out of the geometry drawn in the
pictures above, which `make_05_images.py` computes rather than draws by hand.

**The arrangement.** Two glasses of the kind whose footprint range is 60 to
90 mm. Their true diameters are 72 mm and 69 mm, and they stand 88 mm apart —
so their rims are 88 − 36 − 34.5 = 17.5 mm from touching. At the 25 mm grouping
distance solution 2 uses, that is one group, not two. The camera happens to be
almost in line with both, so the near glass hides nearly all of the far one.

**What the geometry finds.** 3,300 dots. The single circle fitted to the
group's outline comes out at **88.6 mm across**.

Look at what that means. The kind's range is 60 to 90 mm. **88.6 is inside it.**
The check that makes solution 2 safe passes, the two-circle hypothesis is never
tried, and one glass is reported where there are two. This is the merge that
does not announce itself, and it happens without a single step of the pipeline
doing anything wrong.

**What the geometry also has, and ignores.** The RMS residual of that fit is
**17.5 mm**, with a worst single residual of **52.2 mm**. A glass that really is
one round thing does not fit like that. Split the dots in two and fit each half:
**73.3 mm** and **24.8 mm**, with centres **95.2 mm** apart and an RMS residual
of **1.8 mm** — nine times better. But the 24.8 mm circle is far below the
kind's 60 mm floor, so the two-circle answer fails the range check too.

Both hypotheses are defective. The rule prefers the one that passes its check.

**The row handed to the verifier.**

| Feature | Value | Arithmetic |
| --- | --- | --- |
| fitted diameter / kind's mean | 1.18 | 88.6 / 75 |
| one circle: RMS residual | 17.5 mm | |
| one circle: worst residual | 52.2 mm | |
| two circles: RMS residual | 1.8 mm | |
| residual ratio, one / two | 9.6 | 17.47 / 1.81, before rounding |
| larger candidate / kind's mean | 0.98 | 73.3 / 75 |
| smaller candidate / kind's mean | 0.33 | 24.8 / 75 |
| centre gap / larger radius | 2.60 | 95.2 / 36.65 |
| clearance between the two rims | +0.94 | (95.2 − 36.65 − 12.4) / 49.05 |
| dip depth along the centre line | 1.00 | the gap between the humps is empty |
| dot density / predicted | 0.87 | (3,300 / 5,030) / 0.758 |
| height / footprint width | 1.72 | 152 / 88.6 |
| stations that saw it | 1 of 3 | |

**What comes back.** The verifier has not been built, so the number here is
illustrative rather than measured: something like **0.62** — the probability
that this is two objects. Above even, because of the residual, the empty dip
and the thin evidence. Not far above, because the diameter is comfortably in
range and one of the two candidate circles is nonsense.

0.62 falls between the two thresholds, so the verifier **abstains**.

**What the abstention buys.** The arm takes one more picture, from the
perpendicular to the line joining the two candidate centres, 380 mm back and
120 mm above the table. Re-clustered and re-fitted, the group becomes two
circles of **72 mm** and **69 mm**, centres **88 mm** apart, both inside the
range. The geometry answers on its own.

The model's contribution was not the answer. It was knowing that it did not
have one, and where to look.

## The feedback loop

This section is the point of the whole solution.

A classifier that must answer is a component. A classifier that may decline to
answer is a **loop**, because declining is a request for another measurement,
and another measurement is something the arm can actually go and take.

### Calibration first

Before a threshold can mean anything, the number it is applied to has to mean
something.

A model that outputs 0.9 is claiming that, among all the cases it scores 0.9,
about nine in ten really are two objects. A model whose outputs behave that way
is **calibrated**. Models very often are not: they report 0.9 and are right two
thirds of the time, or report 0.5 and are right nearly always. The standard
reference for how badly modern networks do this is
[Guo et al.](https://arxiv.org/abs/1706.04599).

![Calibration, and the two thresholds](../../../images/problem-2/05-calibration-and-the-bands.png)

On the left is a **reliability diagram**: reported probability along the
bottom, how often that turned out to be right up the side. The dashed diagonal
is what an honest number looks like. The orange curve is the failure to fear —
it says 0.89 and is right 0.68 of the time, which is precisely how a merged
pair gets confidently acted on.

Fixing this is routine and cheap. Fit the model, then fit a second, tiny
function that maps its raw scores onto honest probabilities, using held-out
data the model never trained on.
[scikit-learn's calibration guide](https://scikit-learn.org/stable/modules/calibration.html)
covers both usual choices — a sigmoid fit, and isotonic regression, which fits
any increasing curve — and
[`CalibratedClassifierCV`](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html)
does it in one line. It costs a held-out set and about a second.

### Then the two thresholds

On the right of the same picture: one confidence axis, two thresholds, three
answers.

- below 0.25 — **one object**; act on it;
- above 0.75 — **two objects**; act on it;
- in between — **cannot tell**; go and take another picture.

In plain words, that is a **confidence threshold with a reject option**: the
model is allowed to hand the question back instead of guessing. The idea is old
and the oldest reference is Chow, *On optimum recognition error and reject
tradeoff*, IEEE Transactions on Information Theory, 1970
([IEEE Xplore](https://ieeexplore.ieee.org/document/1054406)). The modern
literature calls the same thing selective prediction, or classification with a
reject option.

The band is a dial with a cost on each side, and the arrows in the picture say
which way. Widen it and more groups get a second look: fewer wrong calls, more
arm time. Narrow it and the arm moves less, and more merged pairs get believed.
Because a merged pair is the expensive failure and arm time is merely slow, the
band should start wide and be narrowed only when a scored run shows the extra
looks are not changing any answers.

### What an abstention asks for

![The abstain path as a loop](../../../images/problem-2/05-the-abstain-loop.png)

An abstention is not a shrug. It is a request with an address, and that is what
makes this cheap.

The two-circle fit has already produced two candidate centres. If those two
centres are real, the viewpoint that separates them is the one perpendicular to
the line joining them — from there they stand side by side instead of one
behind the other. So the next viewpoint needs no search and no scoring model.
The abstention names it.

The loop, in full: cluster and fit → verifier → abstain → move the camera and
take one picture → cluster and fit again → verifier again. It stops when the
verifier is confident, or when the budget of two extra looks is spent. If the
budget runs out and the group is still doubtful, that is a **result**: the pair
is reported unseparated and handed to [problem 3](../../problem-3), whose job is
to move glasses apart.

This is the same loop that
[solution 3, move the camera](solution-overview.md#solution-3--move-the-camera),
runs on a hand-written rule. The verifier does not replace that loop. It gives
it a better reason to fire.

## What it needs

**Libraries.**

- [NumPy](https://numpy.org/) — BSD-3-Clause
  ([licence](https://github.com/numpy/numpy/blob/main/LICENSE.txt)). Already a
  dependency.
- [scikit-learn](https://scikit-learn.org/) — BSD-3-Clause
  ([licence](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING)).
  Would be added to `pixi.toml` from conda-forge.
- [Gazebo](https://gazebosim.org/) — Apache-2.0. Already running; it is the
  source of the labels.
- Optionally [PyTorch](https://pytorch.org/) — BSD-3-style
  ([licence](https://github.com/pytorch/pytorch/blob/main/LICENSE)) — only if
  the small convolutional variant is tried.

**Hardware.** None beyond the machine already in use. No CUDA, no graphics
card, no external service.

**Data.** A few thousand labelled rows, generated in simulation, weighted
towards the ambiguous band. An overnight run at worst; the exact cost on this
machine is **uncertain**.

**Code.** A feature extractor of roughly thirty lines on top of solution 2's
clustering; a loader; a training script. The heaviest part is the data
generation harness, not the model.

**Artefacts, and one discipline about them.** One version-pinned model file,
checked in beside its loader. Its size is **uncertain** until it is fitted, but
a few hundred small trees is kilobytes, not megabytes. And **store a hash of
the feature list inside the file**. Add a feature, change an order, rename
something, and the loader must refuse the old model rather than quietly feed it
the wrong thirteen numbers. A silently misread model is much worse than a
missing one: a missing one falls back to the geometry, and a misread one
answers confidently from nonsense.

## What it is good at

**It is small enough to trust.** One binary question, thirteen inputs, a
training set you can open and read. Everything about it fits in one person's
head, which is not true of any model that owns a whole perception step.

**Its failures are bounded by arithmetic it does not control.** It cannot
invent a glass, move a position, or change a reported width. Those come from
depth measured during the run. The worst it can do is cause one extra picture,
or leave a pair for problem 3 that could have been separated.

**It degrades to the pure-geometry answer.**

![What happens with no weights file](../../../images/problem-2/05-degrades-to-geometry.png)

Missing file, corrupt file, feature-list hash mismatch, failed import — the
caller catches it and abstains on every doubtful group. Abstaining on everything
is exactly what solutions 2 and 3 do today. The run takes a few more pictures
and reports a few more unseparated pairs; the masks, positions and widths are
identical, because they were never the model's to produce.

That property is rarer than it sounds and worth a great deal. Most learned
components fail to *nothing*: lose the weights and the system has no answer at
all. This one fails to *the previous system*. It means the model can be added
before it is fully trusted, removed without a rewrite, and retrained on a
different schedule from everything around it.

**It is cheap to retrain.** The labels regenerate themselves. When the spawner
changes, the training set changes with it, and the fit takes seconds.

## What it is bad at

**It is only as good as the band it is asked about.** The trigger conditions
are hand-written, and a case that never reaches the verifier never gets
verified. This is the failure the worked example is chosen to illustrate: a
trigger on diameter alone would have let that merged pair straight through, and
only the residual condition catches it.

**It holds a size-shaped prior that nobody can read.** Ratios against the
kind's mean diameter help, but a model trained on one kind has learned that
kind's proportions. That is knowledge about glass sizes living in a file, which
sits uneasily beside
[the rule that governs this repo](../../../CLAUDE.md) — no glass's size appears
anywhere in the project. It is defensible, because the number it holds is a
soft boundary in a ratio rather than a measurement, and because nothing it
outputs becomes a dimension. But the report should say plainly that a fitted
file is in the loop.

**It does not survive problem 4.** With four kinds on the table the allowed
diameter becomes the union of four ranges, and the question itself changes:
"one or two" turns into "one, or two, and of which kinds". The model would have
to be refitted, and probably redesigned.

**It needs depth.** Everything upstream of it begins with turning a pixel into
a point in the room. Real glassware returns no depth, and then there is no
cluster, no circle and nothing to verify.

## How it fails

**Confidently and wrongly.** The failure to watch. A merged pair scored 0.05 —
decisively "one object" — passes every gate, and no extra look is taken. Miscalibration
is how it arrives — a probability that looks decisive because the training set
held too few hard cases. The defence is the calibration check, run against the
simulator's record: among the groups scored 0.9, about nine in ten should
really have been two. If they are not, this is a heuristic wearing a weights
file, and it should be treated as one.

**It abstains on everything.** Change the camera, the table height or the
lighting, and the features drift away from anything the model saw in training.
Every group lands in the band, the arm spends its whole budget on extra looks,
and the run crawls. This failure is loud, which is the good news — and because
abstaining is the safe direction, it costs time rather than correctness.

**It goes stale silently.** Change the spawner's proportion ranges and the
model is describing glasses that no longer exist on the table. Nothing raises
an error, the unit tests still pass, and the accuracy quietly falls. The
feature-list hash catches a changed *feature set*; it cannot catch a changed
*world*. Only a scored run against the simulator's record can.

**It gets the trigger band wrong.** Covered above, and worth repeating, because
it is the failure that hides behind good headline numbers: a verifier with
excellent accuracy on the cases it sees, and no opinion at all about the ones
that were never routed to it.

## When it would be the right choice

Three conditions, and this cell meets all three.

1. **A programmed method already gets most of the way.** If it does not, a
   learned tie-breaker in front of a bad answer is still a bad answer. Here the
   clustering and the circle fit settle nearly everything.
2. **The residual failure is one nameable decision.** Not "perception is a bit
   unreliable", but "this specific question, on this specific input, is where
   the mistakes are". Here it is *one object or two*.
3. **Truth is cheap to generate.** The simulator knows what it spawned, so the
   labels cost nothing but compute.

It would be the wrong choice if the rules were not already close, if the
failures were scattered across many different kinds of mistake, or if labelling
needed a person. And it is worth being honest about the ordering: the verifier
should not be built until a scored run shows that ambiguous clusters are a real
share of the failures. Measure which failure you have before choosing a
component to fix it.

## Where it sits

It leans on **cluster on the table**, which produces every number it is shown
and every answer it is not asked about, and on **move the camera**, which is
the loop its abstentions drive. It competes with **learned doubt steers the
next picture** and **learn which viewpoints pay off** for the title of "first
learned component", and it wins on cost: those two rank viewpoints, which is
useful only once the cheap rule is known to choose badly, whereas this answers
a question the rules demonstrably cannot. Against **a segmenter trained from
scratch** and **per-pixel votes for the centre** it is not really a competitor
at all — those replace the perception, and would only be reached for if the
depth reading itself stopped being trustworthy.

← [The problem](../problem.md) ·
[Solution overview](solution-overview.md#solution-5--a-learned-verifier-over-the-clusters) ·
[Problem 3 — moving them apart](../../problem-3) →
