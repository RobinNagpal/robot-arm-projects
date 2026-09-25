# Solution 6 — learn which viewpoints pay off

*Hybrid, with the model as a ranker. Solution 3 scores a viewpoint with a rule
somebody wrote. Solution 4 scores it by how far the perception step's doubt
should fall. This one predicts, directly, whether taking that picture will
change the answer — and trains that prediction on an experiment the simulator
can run exhaustively.*

## In one paragraph

Three solutions here choose where to look next; they differ in what they
score. This one scores the thing actually wanted: the chance that a
picture from a given pose splits an ambiguous cluster into two glasses. That
question has an exact answer the simulator can look up — spawn an arrangement,
render from the pose, see whether the ambiguity went — so choosing a viewpoint
becomes ordinary supervised learning on free, exact labels. The geometry still
generates the candidates and still holds the veto; the model only orders what
survives, so a bad prediction costs one wasted look.

## The problem this solves

[`problem.md`](../problem.md) asks for one set of pixels per glass, a position for
each, and an honest list of the pairs that could not be separated. Two glasses
that are far apart on the table can still land on top of each other in a
picture, and when they do, the flood fill returns one blob and everything
downstream believes it is one glass. That is the failure the problem watches
hardest, because it does not announce itself.

The fix is to take a different picture. The camera is on the wrist, so a
viewpoint is an arm pose: it costs seconds of motion, while the picture itself
costs milliseconds. So the question is not *can we look again* but *where,
given that we can only afford one or two more looks*.

[Solution 3](solution-overview.md#solution-3--move-the-camera) answers it with a
rule: throw away the poses the arm cannot reach, throw away the ones looking
through another glass, and of what is left take the one needing least reach.
That rule is cheap, printable, and right most of the time. It also has a blind
spot that is not a bug in the rule but a fact about the geometry.

![Two candidate looks a least-reach rule cannot tell apart](../../../images/problem-2/06-the-rule-cannot-tell-them-apart.png)

Look at the two coloured cameras. Both stand 380 mm back from the same cluster,
both are 336 mm from the arm's base, and neither has anything in the way. The
least-reach rule scores them identically, because **how far the camera is from
the base depends only on the angle between the standoff direction and the line
out from the base** — and that angle is the same whichever side you swing to.
Every good viewpoint has a mirror image with exactly the same reach.

The two are not equally useful. One looks across the line joining the hidden
pair and returns two silhouettes with 65 pixels of table between them. The
other looks almost along that line, the near glass covers most of the far one,
and the picture comes back as a single 89-pixel blob — no better than the one
before it, and one look poorer.

To tell them apart the score would have to know about the line joining the
proposed pair, and about which views have already been taken, and about how
those interact with the fitted radii. Somebody could write that rule. Somebody
would then have to write the next one, and the one after that. The alternative
is to stop writing rules and measure the thing directly.

## The idea, in plain words

Ask the question you actually care about.

You are standing in front of a cluster that the circle fit has rejected — it
came back as one circle 158 mm across, and no glass of this kind is. You have
eight camera poses to choose between. What you want to know about each one is
one single thing: **if I go there and take the picture, will this cluster come
apart into two glasses, or not?**

That is a yes-or-no question about a specific pose in a specific arrangement.
It has an exact answer. And crucially, you can find out the answer *without the
arm*, because the simulator will render the view from any pose it is asked for
and then tell you what it spawned.

So: generate thousands of arrangements, find the ambiguous clusters, render
each candidate pose, record whether the ambiguity was resolved, and fit a
function from the pose's geometry to that yes or no. Then, at run time, use the
fitted function to order the candidates.

![Three ways to score the same eight viewpoints](../../../images/problem-2/06-three-scorers.png)

The three panels are the same arrangement and the same eight candidates, scored
three ways. The rows at the bottom are the orderings each scorer produces;
green means the pair really does come apart from there, red means it does not.

- **Solution 3** scores by least reach. Its top two are tied to the millimetre
  and one of them is useless.
- **Solution 4** scores by how far the segmenter's own per-pixel doubt should
  fall. That is a better question than reach, but it is still a proxy, and it
  has a specific bad case: from the pose that lines the two glasses up, the
  blob looks like one clean, well-bounded glass, so the model is *confident* —
  and a large predicted drop in doubt is exactly the wrong answer.
- **Solution 6** scores the chance the picture splits the cluster. It is the
  only one of the three that puts both useless looks at the end, because it is
  the only one being asked about the outcome rather than about a stand-in for
  it.

The useful generalisation is not "learning beats rules". It is that **the
shape of a learning problem is worth working out before reaching for the
heaviest tool that fits it.** This one turned out to be a table of features and
a column of zeros and ones.

## Where it comes from

Three separate lines of work meet here.

**Active perception.** The observation that a camera which can move is not the
same instrument as one that cannot. Ruzena Bajcsy's *Active Perception*
(Proceedings of the IEEE, 1988) is the paper that named it, and Connolly's
*The Determination of Next Best Views* (ICRA, 1985) is the loop that follows
from it: given what you have seen and where you could go, where next? Scott,
Roth and Rivest's survey *View planning for automated three-dimensional object
reconstruction and inspection* (ACM Computing Surveys, 2003) collects the
classical answers, nearly all of which score a viewpoint by how much unknown
volume it would resolve. Solution 3 is a small, hand-cut version of that
tradition.

**Predicting whether an action will work, from data.** In grasping, the same
step was taken about ten years ago and for the same reason. Nobody could write
down a rule that said whether a particular gripper pose would hold a particular
object, so instead people collected attempts and fitted a function from the
pose to whether it worked. Pinto and Gupta's
[*Supersizing Self-supervision*](https://arxiv.org/abs/1509.06825) (ICRA 2016)
had a robot try tens of thousands of grasps and label them by whether the
object came up. Levine et al.'s
[*Learning Hand-Eye Coordination for Robotic Grasping*](https://arxiv.org/abs/1603.02199)
(2016) is the larger version. Neither is reinforcement learning: there is no
episode and no reward, just an input, an attempt, and a recorded outcome. The
label is free because the world produces it.

**Next best view as supervised learning.** Putting those together — scoring a
viewpoint by a fitted function rather than a formula — is also published.
Vasquez-Gomez et al.'s
[*Supervised learning of the next-best-view for 3D object reconstruction*](https://arxiv.org/abs/1905.05833)
trains a network to pick the best of a fixed set of poses, with the labels
generated by simulating each pose and measuring what it gained. That is the
same move made here, for a different payoff.

The reason this matters is cost, and the comparison worth having in mind is
against the obvious heavier alternative: a policy trained by reinforcement
learning, which is written up as
[an active-vision policy](learned-with-hardware.md#an-active-vision-policy) in
the companion document.

![The same question asked two ways](../../../images/problem-2/06-supervised-against-reinforcement.png)

Read the "working out which look helped" row first, because it is the one that
decides everything else. A reinforcement-learning agent takes several looks and
then gets one number saying how the episode went; working out which of the
looks earned it is the central difficulty of the method, and it is why episodes
have to be played out in their thousands. Here the label for one look does not
depend on what the arm does next, so there is nothing to attribute. Remove the
credit assignment and the episode goes with it, and with the episode goes the
reward function, the exploration schedule, the discount factor, and most of the
machine time.

A policy does buy one thing this does not: it can also learn *when to stop*.
Here that decision stays a written rule — stop when nothing is ambiguous, or
the budget is spent.

## How it works, step by step

### Step 1 — say exactly what the label means

A **label** is the known answer attached to one training example. Getting it
right is most of the work, and here the choice is between two candidates that
sound alike:

- *Was the final answer correct?* — needs ground truth, which the arm does not
  have at run time.
- *Did this picture change the answer?* — needs only the two fits, before and
  after.

Take the second. The label is 1 if the cluster that failed the circle fit came
back as two circles inside the kind's diameter range, and 0 otherwise. It is
observable during a normal run, which turns out to matter a great deal later.

A scalar version — how much the one-circle fit's residual dropped — trains the
same way and carries more information per row. An ordering needs only the
ranking, so the binary version is enough to start with.

### Step 2 — make the rows

![One row of training data, start to finish](../../../images/problem-2/06-one-training-example.png)

Five steps, none of which needs a person or an arm:

1. **Spawn.** The simulator puts four to six glasses of one kind in the zone at
   random, at least 150 mm apart, with proportions drawn from the kind's
   plausible range.
2. **Fit and find the ambiguity.** Run the normal survey and the normal
   clustering. A cluster whose fitted circle falls outside the kind's range is
   ambiguous — in the picture above, one fits at 220 mm.
3. **Pick a candidate.** Generate the standoff directions round that cluster
   and drop the ones the geometry rejects.
4. **Render.** Gazebo draws the view from that pose. The arm does not move;
   nothing is planned; this is a camera placed in a scene graph.
5. **Write the row.** The features from step 3, and the outcome from re-running
   the fit on step 4's picture.

The label in step 5 is *read*, not judged. The simulator holds the true poses
of everything it spawned, so "did the cluster come apart into the right two
glasses" is a lookup.

Repeat for every surviving candidate of every ambiguous cluster of every
arrangement. About ten candidates survive per cluster, and an arrangement
usually yields one or two ambiguous clusters, so two thousand arrangements give
of the order of twenty thousand rows.

### Step 3 — decide what the model gets to see

This is the design decision with the most consequences, and there is one
argument that settles it before any of the others.

**At the moment the score is wanted, the picture does not exist.** You are
deciding whether to spend three seconds of arm time going somewhere. The only
thing available is a prediction of what would be seen, computed from the
current belief. There are no pixels to feed to anything.

So the input is geometry: about twenty numbers describing the candidate against
the pair, against everything else on the table, against the arm's limits, and
against the views already taken.

Three further reasons to prefer hand-made numbers to raw pixels even where
pixels are available:

- **Rows needed.** Twenty numbers can be fitted from thousands of rows. A
  320 × 240 input needs orders of magnitude more, and every one of those rows
  costs a render.
- **Transfer.** Millimetres and degrees mean the same thing under a different
  light, a different glass colour and a different camera gain. Appearance does
  not, and the whole point of the simulator-only rule is that nothing may
  depend on a look that Gazebo happens to produce.
- **Debugging.** When a tree-based model chooses wrongly you can print the
  twenty numbers and see which one was unusual. A wrong answer from a
  convolutional network over a rendered image is a much longer afternoon.

### Step 4 — fit something small

The target is binary and the inputs are a short table of heterogeneous numbers
— angles, millimetres, ratios, counts. That is the case
**gradient-boosted decision trees** were made for. A decision tree asks a
series of threshold questions ("is the angle to the join line above 47
degrees?") and lands in a leaf holding a prediction. Boosting fits a first,
deliberately weak tree, looks at what it got wrong, fits a second tree to
that error, and adds it in; a few hundred small trees in sequence add up to a
good predictor. The method is Friedman's (*Greedy Function Approximation: A
Gradient Boosting Machine*, Annals of Statistics, 2001).

The practical choices, all CPU-only:

- [`HistGradientBoostingClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)
  from scikit-learn — already a dependency-free wheel, BSD-3-Clause
  ([licence](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING)),
  and it trains twenty thousand rows of twenty columns in seconds on this
  machine. This is the one to start with.
- [LightGBM](https://github.com/microsoft/LightGBM) (MIT) and
  [XGBoost](https://github.com/dmlc/xgboost) (Apache-2.0) are the same family
  with more knobs. Neither is needed at this size.
- A small multi-layer network in
  [PyTorch](https://pytorch.org/) (BSD-3-style,
  [licence](https://github.com/pytorch/pytorch/blob/main/LICENSE)) is worth
  having only for the scalar target, where it fits a smooth function more
  naturally than a staircase of thresholds does. On an Apple Silicon Mac it
  runs on the MPS backend in minutes. It is not the first thing to build.

Whatever is fitted, it must be checked against rows it has never seen. Hold out
a fifth of the *arrangements* — not a fifth of the rows — because two
candidates from the same arrangement are not independent, and splitting by row
lets the model look up the answer.

## How it works here

### The candidate list, and who is allowed to veto

![24 directions in, 8 scored: the geometry vetoes, the model only orders](../../../images/problem-2/06-veto-then-ordering.png)

This ordering is the safety argument, and it is worth stating as a rule rather
than as an implementation detail: **everything that can reject a pose is
arithmetic, and the model comes after all of it.**

1. **Generate.** Problem 1's `_standoffs()` already makes nine directions round
   a target at 380 mm from it, level, 120 mm above the table. Make it 24 at
   15-degree spacing; generating more candidates costs nothing.
2. **Reach.** The camera lands at the cluster plus 380 mm along the direction,
   and that point must be 300 to 780 mm from the arm's base.
3. **Line of sight.** Reject any ray that passes through another cluster's
   fitted footprint circle.
4. **Plannability.** Run inverse kinematics on what is left —
   [MoveIt 2](https://moveit.ai/)'s `setFromIK` (BSD-3-Clause), milliseconds
   each — and drop the poses the arm cannot hold.
5. **Score.** The model sees the survivors and returns a number for each. It
   cannot add a pose, and it cannot remove one.

Because of that ordering, the worst thing a wrong prediction can do is put a
reachable, unblocked, plannable pose first when a different reachable,
unblocked, plannable pose would have been better. The cost is one look. It is
not possible for the model to cause an unsafe move, because it is never asked
about safety.

### What the model is shown

![Everything the model is given, drawn where it lives](../../../images/problem-2/06-the-features.png)

The features are grouped by what they are about, and every one of them is a
millimetre, a degree or a count.

**About the pair the fit proposed.** The diameter of the one-circle fit; the
two diameters the two-circle fit proposes; their separation expressed in fitted
radii rather than millimetres, so the number means the same thing for a large
glass and a small one; and how much worse the one circle fits than the two,
which is how strongly the geometry believes there are two things there at all.

**About the candidate against that pair.** The angle between the line of sight
and the line joining the two proposed centres — ninety degrees is the
separating angle and zero degrees is the useless one — its sine, the predicted
separation in pixels, and the predicted overlap in pixels. Those last two are
the same geometry expressed in the units the camera actually works in, which is
where the constants live: `fx = fy = 277.1` pixels, so a 168 mm separation at
380 mm depth is 168 × 277.1 / 380 ≈ 123 pixels of the 320 across.

**About the candidate against everything else.** How close the ray passes to
each of the three nearest other clusters, in that cluster's own radii, and how
many clusters fall inside the camera's wedge. Note the subtlety the picture
shows: a neighbour can be close to the line of sight and still block nothing,
because it sits on the far side of the cluster. The sign of the projection is
part of the feature, not an afterthought.

**About the arm.** The reach — camera to base, against the 300 and 780 mm
limits — the standoff, and the height above the table. These are already known
from step 2 of the filter, so they are free.

**About what has already been looked at.** The angle from the nearest view
already taken, how many views this cluster has, and how many looks the budget
has left. This group is the one a hand-written rule usually forgets, and it is
what makes the difference in the worked example below: a picture taken fifteen
degrees from one you already have is nearly the same picture.

## A worked example

The survey finishes. Four clusters fit circles between 71 and 78 mm, inside the
kind's 60 to 90 mm range. The fifth fits at **158 mm**, which no single glass
of this kind can be, so it is ambiguous. It stands 470 mm from the base. The
budget allows four extra looks for the whole run.

**What the fit proposes.** Two circles of 76 mm and 71 mm, with centres only
54 mm apart. That separation is not believable — the spawner never puts two
glasses closer than 150 mm — and the reason is instructive: from the survey's
line the far glass is mostly hidden behind the near one, so the reconstructed
points sit almost on top of each other. The *direction* of the join line is
reliable. Its *length* is an under-estimate, which is one more reason to feed
the model the separation in radii and let it learn how much to trust it.

**Reach.** A camera 380 mm out from a cluster 470 mm from the base sits

    sqrt(470² + 380² + 2 × 470 × 380 × cos θ)

from the base, where θ is the angle between the standoff direction and the line
out from the base. The 780 mm ceiling needs

    2 × 470 × 380 × cos θ  ≤  780² − 470² − 380²
    357200 × cos θ         ≤  608400 − 365300 = 243100
    cos θ                  ≤  0.681      →  θ ≥ 47 degrees

and the 300 mm floor needs cos θ ≥ −0.771, so θ ≤ 140 degrees. On a 15-degree
grid that leaves ±60, ±75, ±90, ±105, ±120 and ±135: **twelve of the 24
survive.**

**Line of sight.** One neighbour stands 185 mm from the cluster. Its 52 mm
radius subtends about 16 degrees either side as seen from the cluster, so it
covers three of the grid directions. Confirming that it really would spoil the
picture: from 520 mm away its 105 mm footprint spans
105 × 277.1 / 520 ≈ **56 pixels** of the 320 across, directly over the target.
**Nine left.**

**Plannability.** `setFromIK` returns nothing for one of the nine. **Eight are
scored.**

**The scores.** The best is +120 degrees, at **0.88**: square across the join
line, clear of every footprint, 60 degrees from the nearest view already taken,
and 432 mm of reach. Two of the others are worth naming because a hand-written
rule gets them wrong:

- **−135 degrees scores 0.07.** It has the least reach of any survivor, 336 mm,
  and a clear line of sight, so solution 3's rule ranks it joint first. It is
  15 degrees off the join line, so the two glasses stay on top of each other.
- **+60 degrees scores 0.12.** It is reachable at 737 mm and unblocked, but it
  is the direction the survey already looked from. Whatever it returns, the run
  has seen it.

**The look.** Plan, move, settle: about three seconds. Then five pictures along
the 120 mm parallax slide rather than two, because the move is what costs and a
picture is milliseconds.

At 380 mm one pixel covers 380 / 277.1 = **1.37 mm**. The two glasses are
really 168 mm apart, which from the chosen pose projects
168 × 277.1 / 380 ≈ **123 pixels** apart, against silhouettes 55 and 52 pixels
wide — **69 pixels of clear table between them.** The fit returns circles of
74 mm and 70 mm, both in range, 168 mm apart. The cluster is resolved and one
look of four has been spent.

For contrast, the same arithmetic from −135 degrees: the pair projects 33 pixels
apart against silhouettes of 66 and 46 pixels, so they merge into a single blob
89 pixels across — about 96 mm at the near glass's distance, still outside the
kind's range, so the cluster stays ambiguous and the run is one look poorer.

Finally, a row is appended to the log: the twenty features of the pose that was
taken, and the outcome 1.

## The feedback loop

This solution is a closed loop twice over. The obvious loop is the one inside a
run: look, see what happened, look again if you must. The second loop is the
one that matters more, and it is the reason to build this at all.

![Every look taken is another labelled row](../../../images/problem-2/06-improves-with-use.png)

### Inside a run

1. **Fit.** A cluster whose circle falls outside the kind's diameter range is
   ambiguous.
2. **Generate and veto.** 24 candidates, filtered for reach, line of sight and
   inverse kinematics. If nothing survives, stop and hand the cluster to
   [problem 3](../../problem-3/problem.md).
3. **Predict and order.** Score each survivor and take the highest.
4. **Move and photograph.** Seconds for the move, then five pictures along the
   120 mm parallax slide.
5. **Observe.** Re-fit. Two circles inside the range, or not?
6. **Record.** Append one row: step 3's features, step 5's outcome.

It stops when nothing is ambiguous, when the budget is spent, or when a cluster
has no surviving candidate. Whatever is still ambiguous is reported as
ambiguous, which is what `problem.md` asks for.

Two rules keep the loop from running away, and neither of them is the model:

- **A floor that ignores the score.** Any cluster failing the circle fit gets
  one look whatever the prediction says. Otherwise a model that predicts no
  payoff anywhere silently reports a merged pair as one large glass.
- **A cap.** Two extra looks per cluster and four per run. Three survey
  stations are the run's cost today and the whole run should take tens of
  seconds, so four extra looks roughly doubles it. Six does not fit.

### Between runs

Step 6 is what separates this from a model trained once and frozen, and the
reason it works is the choice made back in step 1 of the method.

**The run-time label needs no ground truth.** It is not *was the answer right*
— the arm cannot know that — but *did the answer change*, which is two circle
fits and a comparison. So the label is available in normal running, on the real
table, with no simulator and nobody watching. Every look the arm takes is
another labelled row.

The right-hand panel above is the shape of the claim, and it is drawn rather
than measured: nothing here has been run. The point of it is the flat line. A
hand-written rule performs exactly as well on its thousandth run as on its
first. A fitted one does not have to.

Three guards on the retraining, all of them boring and all of them necessary:

- **Retrain offline, between runs, never mid-run.** A model that changes during
  a run makes the run unreproducible, and an unreproducible run cannot be
  debugged.
- **Check calibration, do not assume it.** Of the looks the model scored at
  0.9, did nine in ten actually resolve? scikit-learn's
  [calibration guide](https://scikit-learn.org/stable/modules/calibration.html)
  has the method and the reliability plot. If the answer is no, this is a
  heuristic wearing a weights file, and it should be said so out loud.
- **Log something other than the model's favourite.** A log holding outcomes
  only for poses the model already liked teaches it nothing about the rest, and
  retraining on it can entrench an early mistake. Take the second-ranked
  candidate about one look in twenty. This is the cheapest possible version of
  what the active-learning literature calls exploration; Settles'
  [*Active Learning Literature Survey*](https://burrsettles.com/pub/settles.activelearning.pdf)
  (University of Wisconsin–Madison, 2009) is the standard tour of the better
  versions, and none of them is needed at this scale.

## What it needs

**Libraries.** [NumPy](https://numpy.org/) (BSD-3-Clause,
[licence](https://github.com/numpy/numpy/blob/main/LICENSE.txt)) and
[scikit-learn](https://scikit-learn.org/) (BSD-3-Clause,
[licence](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING)) are
all that is required. [PyTorch](https://pytorch.org/) (BSD-3-style,
[licence](https://github.com/pytorch/pytorch/blob/main/LICENSE)) only if the
scalar target is wanted later. The geometric filter, the circle fit and
[MoveIt 2](https://moveit.ai/)'s `setFromIK` (BSD-3-Clause) are needed for
solution 3 anyway, so this solution adds no dependency the cell does not
already carry — scikit-learn excepted.

**Data.** Produced by [Gazebo](https://gazebosim.org/) (Apache-2.0), which is
already running. Of the order of two thousand arrangements, each sweeping its
ambiguous clusters against the surviving poses: tens of thousands of rows.
Nothing from outside the simulator, no photographs, no downloaded weights.

**Hardware.** A CPU. The trees train in seconds and predict in microseconds.
Nothing here wants CUDA, which is the condition that removed several otherwise
good answers from this document.

**Time.** The sweep is the real work and its cost is dominated by Gazebo, not
by the fitting. The overview's estimate is a few hours unattended; that number
should be *timed on the first hundred arrangements and extrapolated*, not
believed. The harness that drives the sweep — spawn, survey, enumerate, render,
re-fit, append — is a few hundred lines and is the part that will take a day to
get right.

**Artefacts to keep in step.** A weights file of a few hundred kilobytes, and
beside it a hash of the feature list, so that a changed or reordered feature
makes the loader refuse rather than quietly misread column seven. A log file
that grows.

## What it is good at

**It optimises the thing actually wanted.** Every other scorer here optimises a
stand-in: unknown volume, expected entropy, least reach. Those are stand-ins
because the real target was thought to be unmeasurable. Here it is measurable,
so there is no reason to accept the stand-in.

**It gets most of what a learned looking policy offers for a fraction of the
cost.** No episodes, no reward function, no exploration schedule, no days of
machine time, and no GPU.

**It degrades to something sensible.** Delete the weights file and the filter
still returns reachable, unblocked, plannable poses; order them by reach and
you have solution 3. There is no state in which removing the model leaves the
cell unable to run.

**It gets better with use**, and the improvement costs nothing but a log file,
because the run-time label is free.

**It is inspectable.** Twenty named numbers and a tree ensemble: when it
chooses wrongly you can print the row, and gradient-boosted trees will tell you
which features they lean on.

## What it is bad at

**It buys an ordering, not a capability.** Where the cheap rule already picks an
acceptable viewpoint most of the time — and with one known kind and five
glasses it often does — the gain is small and the machinery is not.

**It needs the two-circle fit to state the ambiguity.** The features describe a
candidate *relative to a proposed pair*. A cluster too degenerate for the
two-circle fit to say anything arrives half described, and the model is
scoring against a line it does not really have.

**It has nothing to say when the list is empty.** If every one of the 24
directions is out of reach, blocked or unplannable, there is nothing to order.
That is not a defect of the ranker; it is the case that exists to be handed to
problem 3.

**Its labels are only as honest as the simulator.** Everything it learns about
depth noise, glass edges and occlusion comes from Gazebo's renderer. The
transfer question is real, and the answer here is that the features are
millimetres and degrees rather than appearance, which is the best defence
available without a robot on a bench.

## How it fails

![Two limits, and only one of them is the model's fault](../../../images/problem-2/06-where-it-stops-working.png)

**It predicts a payoff that never arrives.** The top-scored look is taken, the
cluster does not come apart, one look of four is gone, and the pair is reported
unseparated. This is the ordinary failure and it is bounded by the cap.

**It predicts no payoff anywhere.** No look is taken, and a merged pair is
reported as one large glass — the failure `problem.md` watches hardest. The
guard is not the model: any cluster failing the circle fit gets one look
whatever the score.

**It is asked about a table it was never trained on.** A predictor fitted on
arrangements of five glasses may not transfer to eight. With eight there are
more clusters near every candidate and the separations are smaller, so features
like "how many clusters fall inside the wedge" take values the training set
never held. A tree asked about a value off the end of its range does not say
so — it answers from whichever leaf it falls into, with the same confidence as
always. The defences are to spawn the training set across the *whole* declared
range of four to six glasses rather than a convenient middle, to record the
feature ranges seen in training beside the weights, and to fall back to
solution 3's ordering when a live row falls outside them.

**It cannot rank a candidate the geometry never generated.** The model's world
is the 24 standoff directions at one standoff distance and one height. If the
right answer is a pose at 300 mm, or tilted down, or from a different height,
no score will find it, because no score is asked. Widening the candidate set is
free and is the first thing to try when the ordering is good but the outcome is
not.

**The log is a biased sample.** Outcomes are recorded only for poses that were
taken, and poses are taken because the model liked them. Retraining on that log
without the one-in-twenty exploration rule can lock in an early mistake.

**It goes stale silently.** Change the standoff list, the standoff distance, or
the spawner's proportion ranges, and the weights now describe a cell that no
longer exists. Nothing crashes. The feature hash catches a changed *feature*;
it does not catch a changed *world*, and only re-running the sweep does.

**Real glassware removes its input.** The whole chain starts with depth
readings that transparent glass does not give, which is the standing caveat on
every depth-based solution in this document.

## When it would be the right choice

Three conditions, and all three hold here:

1. **The candidate list is long enough that the order matters.** Eight
   survivors, a budget of four looks for the whole run.
2. **A wasted look is the expensive outcome.** Arm time is by far the scarcest
   resource; computation is not scarce at all.
3. **The label is exact and free.** The simulator knows what it spawned, so the
   experiment can be run exhaustively without anyone labelling anything.

Where it would not be the right choice: when the rule already picks well.
So the order of work is **solution 3 first, scored** — run it, record for every
ambiguous cluster whether its first choice resolved the cluster, and look at
the number. If the rule's first pick usually works, this solution earns nothing
and should not be built. If it does not, the log from that scored run is
already the beginning of the training set.

There is also a version of this that is worth more later. At
[problem 4](../../problem-4/problem.md) the kind stops being known, the allowed
diameter becomes the union of several ranges, and the ambiguity stops being a
short list of near-identical questions. That is where a hand-written rule runs
out of things it can be told, and where a fitted score that has seen thousands
of arrangements starts to be worth its weight.

## Where it sits

It is the same loop as *move the camera*, with the scoring rule replaced by a
fitted function, and it falls back to exactly that rule when the model is
removed — so it should be built on top of that solution rather than instead of
it. It competes with *learned doubt steers the next picture*, which asks the
same question through the perception model's uncertainty instead of through the
outcome; that version is richer and is the one to reach for once the doubt
stops being binary, but it inherits the confidently-wrong failure that this one
sidesteps by never asking the model how sure it is. It leans on *cluster on the
table* for the circle fit that declares a cluster ambiguous and then judges
whether the look worked, and it hands anything it cannot resolve to
[problem 3](../../problem-3/problem.md), which is allowed to move the glasses.
