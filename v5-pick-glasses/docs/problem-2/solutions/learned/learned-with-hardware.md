# Problem 2 — learned approaches that need more than a simulator

## Introduction

This document describes one learned approach to problem 2 that is not built
here: an **active-vision policy**, which learns from experience where to point
the camera next. It explains what that approach is and which practical condition
it fails. By the end you will understand how such a policy works, the idea
inside it that is worth knowing even though it is never built, and the exact
reason the machine this project runs on cannot train it.

The important thing to say first is that **nothing here is wrong**. A policy
learned this way is a reasonable answer to this problem, and it is what a
well-resourced team might reach for first. It is written up so that the choice
stays visible, and so that the reason for not taking it is the honest one, which
is the cost of the training rather than a view about learned methods.

It needs no different *algorithm* to become usable. It needs a different
*setup*: many simulated worlds running at once, so that the experience it has to
collect costs hours instead of days.

## The test it had to pass

An approach belongs in the [main overview](../solution-overview.md) if
**everything it needs can be produced by the simulator on the machine this
project runs on**. There is no robot on a bench and no data from a real table,
and the machine's own limits are particular rather than general. In practice
that comes to three conditions.

**The first is no sensor the simulator does not have.** The simulator gives this
cell a depth camera, contact sensors in the gripper pads, and a force sensor at
the wrist. Anything else is a purchase order rather than a design decision.

**The second is the particular shape of this machine's graphics.** It has an
integrated GPU that PyTorch reaches through its MPS backend, so models do train
and run on it. What it has not got is an NVIDIA card, and therefore no CUDA, so
anything that needs code compiled for CUDA does not run here at all. And its
memory is shared with the processor rather than being video memory of its own.
The GPU may use almost all of that memory, which is why models fit at all, but
it is the same memory everything else on the machine is using at the same time.

**The third is hours rather than days.** A method that takes a week of
continuous simulation to train cannot be iterated on, and a method you cannot
iterate on will not be debugged.

The approach below fails the third of those, and the second is what closes the
usual way round it.

Notice what is *not* among those conditions: a weights file fitted somewhere
else. A downloaded model is usable here as long as it runs here, and three
solutions in this folder are built that way — [segment anything, then keep the
glasses](08-segment-anything-then-keep-the-glasses.md), [a fine-tuned instance
segmenter](09-a-fine-tuned-instance-segmenter.md), and [amodal masks for the
hidden part](10-amodal-masks-for-the-hidden-part.md).

All three of those run on this machine as it stands, through the same MPS
backend, and
[`problem-2-pretrained`](../../../../problem-2-pretrained/README.md) holds their
code beside what each of them scored. So the claim that a borrowed model is
usable here is a measured one rather than an expectation, and the condition that
matters for such a model is the second one above: it has to run without CUDA,
and it has to fit in memory the rest of the machine is also using.

One note about tooling is worth knowing before depending on any borrowed model,
including those three. **The licence terms across model families differ
sharply**, and some of them are copyleft in a way that reaches software you only
ever run as a service and never distribute. At least one popular family states
one licence in its documentation and a different, stricter one in its licence
file, and the licence file is what counts. So for anything that might ship,
reading the licence file is a decision rather than a detail. The specific terms
are not listed in this document, because they change.

---

## An active-vision policy

> **Fails condition 3.** Everything it needs is inside the simulator, which is
> what makes it frustrating. The cost is throughput: it learns from episodes,
> each episode is a handful of arm movements and a simulator reset, and these
> methods want tens of thousands of them, which comes to days of continuous
> simulation on one machine. The usual way round that is a simulator that steps
> thousands of worlds at once inside the graphics card, and those simulators are
> written for CUDA, so condition 2 shuts that door as well. *A supervised
> version of the same idea, which predicts whether a viewpoint will pay off
> rather than learning a policy, does fit, and it is in the main overview as
> [solution 4](04-choosing-the-next-look.md).*

*Learned, as the decider, and a closed loop by construction. A policy takes the
current belief about the table and outputs where to point the camera next.*

### What it is

A **policy** is a function from what the robot knows to what it does next. Here
that means the belief about the table going in, and the next camera pose coming
out. Nobody writes the rule inside it; the rule is a pile of numbers, the
**weights**, fitted from experience.

There are two ways to fit them, and the difference matters a great deal for
cost.

**Reinforcement learning** lets the robot try. It looks somewhere, and
eventually is handed a number, the **reward**, saying how well the whole attempt
went. Thousands of attempts later, actions that tended to precede high reward
have become more likely. Nobody ever says which individual look was good, and
that is inferred from the totals — which is precisely why it takes so many
attempts.

**Imitation learning** shows it the answer instead. Run an expert, whether a
person with a joystick or a slow method already known to be right, record what
the expert saw and did, and fit the policy to reproduce the choice. This is
called **behaviour cloning**, and it is ordinary supervised learning. It needs
no reward at all, and it can never beat the expert it copied.

### Why anyone does it this way

Two reasons, and the second is the stronger one.

The first is speed. Scoring a viewpoint properly is expensive while choosing one
is cheap. Solution 3's score casts a ray per pixel into an occupancy map for
every candidate, whereas a policy does one forward pass, and you pay the cost
once, offline.

The second is reach. A geometric score exists only where somebody can write one
down. Here they could. Where the cue is subtler, nobody can.

### How it would work here

**The observation** would deliberately not be the raw picture, because
appearance is exactly what will not transfer out of the simulator. Instead, feed
the policy what the geometry has already produced: the glass zone as a coarse
grid of cells, each marked empty, occupied or never-seen; one row per cluster
holding its position, its fitted width, how many stations saw it and whether
that width is inside the kind's range; and how many looks remain in the budget.
That is a few hundred numbers in total, which is small enough to train on a
processor.

**The action** could in principle be a camera pose, which is six numbers. In
practice, do not. Take a **fixed list of candidate poses** — a ring of
directions round the target, multiplied up by a few heights — and let the action
be a choice among them, plus one extra action meaning **stop**.

Making the action discrete is the sane engineering choice here, for a specific
reason worth understanding. Every candidate in a fixed list can be checked once
against the arm's reach and against whether any joint angles reach it, so the
policy **cannot name a pose the arm will not hold**, because the impossible ones
are masked out before it chooses. A continuous six-dimensional space would spend
most of its exploration pointing the camera at mid-air.

**The reward is the hard part**, and this is where the approach becomes fragile.
The obvious reward is this problem's own score sheet: a point per glass
correctly separated, a point off per merged pair, and a small penalty per look
so that dithering costs something. But that needs to know which glasses were
really there. The simulator writes down everything it spawned, so in simulation
the reward is exact. **Reality has no such file.** You could pay for a proxy,
such as the circle fit passing — but a policy optimises exactly what you pay
for, and one paid for a passing fit learns viewpoints from which the fit passes,
and not viewpoints from which the answer is right.

**How long it would take** is the condition this approach fails. An episode is a
handful of looks, each an arm movement of a few seconds, plus a reset — call it
some tens of seconds of wall clock running without a display, which is a figure
to measure rather than guess. Multiply that by the tens of thousands of episodes
these methods want and it is **days** on one process, or a fraction of that with
several in parallel. Meanwhile a single learning step takes milliseconds. So
**the simulator is the bottleneck, by orders of magnitude**, and every
optimisation effort belongs there rather than in the learning code.

### The feedback loop

This is not a solution with feedback bolted on. It **is** the loop, and it runs
in five steps.

First, **observe**: run the survey from the top, cluster, fit circles, and build
the observation. Second, **choose**: the policy returns one of the candidate
poses, or `stop`, and the ones failing reach or joint angles were masked out
before it chose. Third, **move**: plan and execute, taking a few seconds, and if
the plan fails, mask that candidate and go back to choosing. Fourth,
**re-observe**: take the pictures, fold the new points into the same clusters,
fit again, and rebuild the observation. Fifth, **stop** on the stop action, or
when the budget of looks runs out, with clusters still failing their fit
reported as unseparated.

Two properties of that loop are deliberate. The belief is **cumulative**,
because each look adds points to the same clustering rather than starting again.
And the **budget is external rather than learned**, so a policy that never says
stop wastes a fixed number of looks rather than running for ever.

### A worked example

Glass A stands about halfway out across the arm's reach. Glass B stands further
out, at the smallest gap from A the cell allows. B sat behind A from most of the
survey stations, so the merged cluster fits a circle about twice as wide as any
glass of this kind can be.

Two of the candidate directions lie along the line joining A and B, which are
the worst possible directions, and at every height they fail on **reach** alone,
because standing back from A along that line puts the camera either folded in
against the base or stretched out past the far limit. So they never even reach
the policy.

The policy picks the candidate square across the line joining A and B. One
movement, a few seconds. The cluster resolves into two discs, both widths inside
the kind's range, so the policy says stop and the episode collects its reward.

**Now the comparison that matters.** Solution 3's arithmetic chose that *same*
viewpoint, before the planner was asked anything at all — and it can say
**why**: from the blocked direction, B would cover a large part of the width of
the frame directly behind A. The policy chose the same pose and can say nothing
at all about its reasons beyond a number. Same answer, and only one of the two
can be audited.

### What it needs

A training environment wrapped round the existing cell, where resetting spawns
four to six glasses, stepping moves the arm and re-runs perception, and the
reward reads the spawn record. **That wrapper is the real work**, because it
must reset the simulator thousands of times without leaking processes. Then a
standard reinforcement-learning library, and days of machine time. No labelled
pictures, and nothing the machine's own graphics cannot run: what the machine
cannot supply is the simulator time.

### What it is good and bad at

What it is good at is run-time speed, because choosing is one forward pass,
which is microseconds against the seconds a movement costs. It can also use cues
nobody wrote down, where a viewpoint pays off for reasons the circle fit misses.
And it optimises the thing itself, meaning merges and splits, where information
gain is only a proxy for them.

What it is bad at, first, is that **it cannot explain itself**, and here that is
practical rather than philosophical. This problem says the failure to watch
hardest is the merged pair, because it looks plausible downstream. A policy that
stops one look early produces exactly that failure, and reports confidence while
doing it.

It is also more machinery than this problem has earned. What it would learn is
computable: the kind is known, the range of widths is known, and occlusion is a
line-of-sight test. **Where a geometric score exists and is auditable, a network
trades the explanation for a speed-up**, and here the explanation is worth more.

Its failure modes are worth naming, because two of them are expensive to
discover.

**Reward hacking.** Charge too much per look and the policy stops at once and
eats the merge penalty; charge too little and it burns its whole budget every
run. That balance is not derivable, and each attempt at it costs another
training run.

**Drift out of the simulator.** This is milder here than for tasks involving
contact, because there is no friction, no deformation and no impact, and what
matters is straight lines from camera to object, which the simulator gets right.
Feeding clusters rather than pixels removes most of the appearance gap too. But
the policy also learned this simulator's depth noise and the way its readings
drop out at glancing angles — and a real camera that loses the far rim of a
glass at a steep angle shifts **every** observation the policy ever sees.

**Silent staleness.** Change the kind of glass, the lighting, or the list of
candidate directions, and the weights describe a cell that no longer exists,
while the tests still pass.

**Real glassware removes the input** altogether, because the observation is
built from clusters, and clusters come from depth that real glass does not
return.

### When it would be the right choice

When the doubt stops being a short list. Here, one known kind and a known range
of widths make "one glass or two?" arithmetic, and auditable. Problem 4 has
several kinds, some never measured, and the union of their ranges is wide enough
that the circle fit stops deciding much. A policy that had learned which looks
resolve ambiguity would have something real to offer there.

One shape is worth keeping even so. Solution 3's score is a working expert and
it runs in simulation for free, so **behaviour cloning against it** gives a fast
policy with no reward design at all — at the price of a policy that can only
approach what it copied, having lost the explanation that made the original
worth having.

## What to take from it

One pattern is worth carrying away from this approach, because it applies well
beyond this project.

A learned component is safe or unsafe depending on **where in the pipeline it
sits**, and not on how good its model is. A policy of this kind sits at the
least safe end, because the policy decides and nothing checks it: what it
outputs is a camera pose, and a pose carries no width to compare against the
range this kind of glass allows. The solutions in this folder that borrow
weights sit further back in the pipeline, because each of them outputs a mask, a
mask becomes a circle on the table, and a circle is a number that arithmetic
somewhere else can refuse.

So the question to ask of any learned component is not "how accurate is it?" but
**"what checks it, and would that check notice this particular way of being
wrong?"** That question is what the main overview's solutions are arranged
around, and it is the thing to hold on to if this approach is ever built.
