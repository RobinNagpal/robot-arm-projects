# Problem 4 — how it would be solved

## Introduction

[`problem.md`](../problem.md) says what is asked for. This document is the way
into the nine solution documents in the two folders beside it. It says which parts of problems 1,
2 and 3 are reused and where each one sits in a run. It gives what was measured
before any of the nine were written, the words they share, a table of all nine,
and the combination this project would build.

Nothing in problem 4 is built yet. Every number here comes from the project's
own code run on generated glasses, not from a run in the simulator. Where the
numbers come from is said once below and again in each solution document.

Each solution has a document of its own with its argument in full. This one
does not repeat them.

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the places the camera works from, all four sensors, and the words this
> project uses them with.

## Where we are

Four to six glasses stand on the table. They are drawn from more than one of the
four kinds, and some may stand too close to be gripped. The arm has to rack
every one it can and leave the rest standing, each with a reason.

Three problems have already been solved in parts:

- **Problem 1** takes one glass through six steps: find it, measure it, name
  it, choose the grip, squeeze, turn it over. It is built and runs in Gazebo.
- **Problem 2** finds several glasses of one kind and chooses where to stand
  the camera for each. Both a programmed and a learned pipeline are built and
  scored.
- **Problem 3** pushes crowded glasses apart. Both are built and scored; the
  learned forward model is the one chosen.

So problem 4 is mostly a question of **joining**. Most of its solutions are
combinations of pieces that already exist. What is new is the handful of places
where a piece built for one kind stops being right when there are several.

## A run, stage by stage

A run of problem 4 goes through these stages. The table says which problem each
stage comes from, what is available for it, and what having several kinds
changes.

| Stage | Comes from | What exists | What several kinds change |
| --- | --- | --- | --- |
| **Find** every glass from above | problem 2 | [clustering on the table](../../02-segment-glasses/solutions/programmed/02-cluster-on-the-table.md) (programmed); [votes for the centre](../../02-segment-glasses/solutions/learned/06-a-network-trained-from-scratch.md) (learned) | the learned one was trained one kind per table; the width check is weaker, but neither built pipeline uses it |
| **Rack** every glass that already has room | problem 3 | [do not drag at all](../../problem-3/solutions/01-do-not-drag-at-all.md) | nothing |
| **Choose** where to stand the camera | problem 2 | [the veto and a written order](../../02-segment-glasses/solutions/programmed/03-move-the-camera.md); a learned ranker | nothing |
| **Measure** the profile | problems 1 and 2 | the silhouette (programmed); SideNet (learned) | the profile now has to carry the *name*, not only the grip |
| **Name** the kind | problem 1 | `classify()` in `glasses/detect.py` | load-bearing; see below |
| **Grip** and **squeeze** | problem 1 | `find_grip()`, `force.py` | the force cap changes glass to glass |
| **Push** a crowded glass | problem 3 | [plan, feel, look again](../../problem-3/solutions/03-plan-feel-look-again.md); [the learned forward model](../../problem-3/solutions/10-learn-a-forward-model-then-plan.md) | the kind, and so the foot, is not known yet |
| **Rack** it | problem 1 | the tilt budget, then the next free slot | slots run out, and the order decides who is left |
| **Order** the whole run | `task.py` | nearest glass first | it now has to plan for the rack and for the pushes |

Seven of the nine stages need nothing new. The three that do — naming, pushing
and racking — are what the nine solutions are about.

## What was measured before writing the nine

Five findings shaped the solutions. Each is argued in the document named.

**1. Most wrong names end in a refusal, and one does not.** Every one of the
four grip rules was run on every kind of glass, 200 of each. A rule applied to
the wrong kind finds no grip at all, so the glass is refused, which is safe.
The one exception is a stemmed glass called short-stemmed. Both kinds use the
same rule, so the grip is in the same place with the same opening, and every
check passes. What differs is the squeeze: a stemmed glass is held at 6 N and a
short-stemmed one at 20 N. [Let the fingers check the
name](programmed/03-let-the-fingers-check-the-name.md).

**2. A reflection can make a tumbler into a wine glass, and the checks pass.**
A notch 6 mm tall that takes 40% off the width of a straight or tapered glass
got that glass called stemmed 369 times in 400, and 132 of those got a stem
grip. The outline is never refused as ragged. A notch 3 mm tall is smoothed
away. [A name that shows its
evidence](programmed/02-a-name-that-shows-its-evidence.md).

**3. Through the cell's camera, the wall lean comes in steps.** Every straight
glass reads 0°. Every tapered glass reads 7.1° or 14.0°. Nothing reads in
between, so "how close was the call" cannot be read off the number the code
uses today. A straight line fitted up the wall gives a continuous lean, to
within about half a degree. [A name that shows its
evidence](programmed/02-a-name-that-shows-its-evidence.md).

**4. The rack runs out, and taking the next free slot makes it worse.** On 1500
mixed tables, the slot choice as it is today left 183 grippable glasses
standing for want of a slot. Choosing each slot with the glasses still on the
table in mind left 56 when planned from the widths seen from above, and 49 —
the fewest possible — with the heights as well. [Plan the rack for the
whole table](programmed/04-plan-the-rack-for-the-whole-table.md).

**5. The glass that has to be pushed often has not been named, and its foot
decides whether it tips.** At a friction of 0.3, every straight, stemmed and
short-stemmed glass can be pushed safely, and 116 of 200 tapered ones. Pushed
without knowing the kind, assuming the narrowest foot any kind has, 17 of 800
can. But 58% of the crowded glasses on mixed tables still have a clean side
view, so they can be measured and named before anything touches them. [Measure
before you push](programmed/05-measure-before-you-push.md).

### Where the numbers come from

A throwaway script run in the project's own environment. It imports
`classify()`, `find_grip()`, `estimate_mass()`, `holding_force()` and the rack
functions from `rack/layout.py`, and runs them on `family(kind, 200, seed=41)`
for each kind.

Side views are not rendered in Gazebo. Each glass's outline is drawn as a mask
at the level view's own scale — 1.37 mm per pixel, 380 mm back — with the top
stretched 6 to 10 mm, because that is how much too tall the level view reads a
glass. The mask then goes through `profile_from_mask()`, the same as on a run.
The cell's glasses are opaque and make no reflections, so the notches in
finding 2 were drawn into the mask by hand.

The rack tables are 4 to 6 glasses of at least two kinds, drawn at random, with
the rack in the middle of `RACK_AREA`. The crowded tables in finding 5 use
`_crowded_layout()` from `problem-3-sim/bench.py`, with each glass's kind drawn
separately, and the view check from `problem-2-programmed/views.py`.

## The words

**Named** and **called** mean what `classify()` returned. **Made as** means
the kind the glass was drawn as. A glass is **named wrongly** when the two
differ.

A **wrong but plausible** name is one where the wrong kind's rule still finds a
grip and every check passes. It is the case [the problem](../problem.md) asks
to count, and the only one that can do harm.

A **margin** is how far a measurement is from the line that decides the name,
in that line's own units: degrees for the lean, a fraction of the height for
the waist.

A **wide** glass is one that `needs_empty_neighbour()` says must have the slots
beside it left empty. A **narrow** one does not. Which one a glass is depends on
its width and its height, and has nothing to do with its kind.

**Room**, **push**, **topple** and **probe** mean what the [problem 3
overview](../../problem-3/solutions/solution-overview.md#the-words) says.

## Three families, and where the learned part sits

The three families are the ones problems 2 and 3 use. **Programmed**: somebody
writes the rule. **Learned**: the behaviour is fitted to examples. **Hybrid**:
both, with the learned part inside something that can be checked.

What matters in a hybrid is where the model sits, because that decides what
happens when it is wrong. As a **decider**, its answer is acted on. As a
**proposer**, its suggestion is checked by rules. As a **ranker**, it only
orders what rules already allowed. As a **verifier**, it checks what the rules
did. The [problem 3
overview](../../problem-3/solutions/solution-overview.md#three-families-and-what-hybrid-means)
draws this.

For naming, this is sharper than anywhere else in the project. The name picks
the rule, the rule picks where the fingers go and how hard they press, and
nothing after that looks at the name again. **A learned part that decides the
name is a decider over everything downstream.** Every hybrid here keeps the
model out of that seat.

## The rule every solution passed

The same as problems 2 and 3. Everything a solution needs has to come from the
simulator on this machine: an Apple Silicon Mac, no NVIDIA card, no robot on a
bench, no real-world data. Anything trained is trained on what the simulator
produces, in hours rather than days.

Two good answers fail this rule and are left out. Naming a glass with an
open-vocabulary model such as CLIP needs a model trained on real photographs.
A grasp network that picks the grip without a name needs a graphics card to
train. [Problem 1's step 3](../../problem-1/step3-what-kind-of-glass.md#other-ways-to-decide-what-kind-of-glass-it-is)
already argues why neither suits this step even with the hardware.

## The nine, in two folders

The solutions are split the way problem 2's are: by whether they contain a
trained model. The five in [`programmed/`](programmed/) are rules somebody
wrote down. The four in [`learned/`](learned/) all have numbers fitted to
examples somewhere inside them, whether the fitted part decides the answer or
only checks or orders what the rules allowed. So the two hybrids sit with the
learned ones.

| # | Solution | Family | Stage | Where the model sits | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | [Join them as they are](programmed/01-join-them-as-they-are.md) | programmed | all | — | the baseline; loses glasses to the rack |
| 2 | [A name that shows its evidence](programmed/02-a-name-that-shows-its-evidence.md) | programmed | name | — | **used** |
| 3 | [Let the fingers check the name](programmed/03-let-the-fingers-check-the-name.md) | programmed | grip, squeeze | — | **used — the only defence against the 20 N case** |
| 4 | [Plan the rack for the whole table](programmed/04-plan-the-rack-for-the-whole-table.md) | programmed | rack, order | — | **used** |
| 5 | [Measure before you push](programmed/05-measure-before-you-push.md) | programmed | order, push | — | **used — it costs nothing** |
| 6 | [A learned second opinion on the name](learned/06-a-learned-second-opinion-on-the-name.md) | hybrid | name | verifier | not yet; worth it on real pictures |
| 7 | [Guess the kind from above](learned/07-guess-the-kind-from-above.md) | hybrid | order, push | ranker | rejected |
| 8 | [The learned pipelines, retrained](learned/08-the-learned-pipelines-retrained.md) | learned | find, measure, push | decider | find and push yes, measure no |
| 9 | [Plan the whole table with the push model](learned/09-plan-the-whole-table-with-the-push-model.md) | learned | push, order | decider | **used for the pushes**; the rack stays arithmetic |

In one line each:

1. Chain problem 2's finding, problem 3's pushing and problem 1's six steps,
   and change nothing.
2. Make the name carry its evidence: a lean fitted up the wall, a stem that has
   to be long enough to be a stem, and both kinds' rules when the call is
   close.
3. Before closing, look down the fingers at the width; after the lift, compare
   the weight with what the named kind should weigh.
4. Choose each slot so that the glasses still standing can still fit.
5. Take the side view of every crowded glass that has one before pushing
   anything, so the kind and foot are known when the push is chosen.
6. A small model on the profile, trained on generated glasses, that can only
   ask for another look or a refusal.
7. Guess the kind from the height and width seen from above, to plan with.
8. Problem 2's and problem 3's learned pipelines retrained on mixed tables,
   with the rules naming the glass from SideNet's profile.
9. Problem 3's forward model with the kind given per glass, or "not measured",
   searching pushes and the order together.

## The decision

**Solutions 2, 3, 4 and 5 on top of the pieces already chosen, with problem 3's
forward model retrained as solution 9 describes.** Not built. In the order a
run does it:

1. **Find** with problem 2's clustering on the table. It needs no retraining
   for mixed kinds, and on problem 2's test scenes it found every glass, the
   same as the learned one.
2. **Rack every glass that has room** first, as problem 3's solution 1 does.
3. **Measure every crowded glass that has a clean side view** before pushing
   anything — [solution 5](programmed/05-measure-before-you-push.md). Measure with the
   silhouette, not SideNet: [solution 8](learned/08-the-learned-pipelines-retrained.md)
   shows why the name cannot be read from SideNet's profile.
4. **Name it with its evidence** — [solution
   2](programmed/02-a-name-that-shows-its-evidence.md).
5. **Push** with problem 3's forward model, retrained on mixed tables with the
   kind given per glass — [solution
   9](learned/09-plan-the-whole-table-with-the-push-model.md). Prefer moving a measured
   glass to an unmeasured one.
6. **Grip and squeeze** as problem 1, with the fingers checking the name —
   [solution 3](programmed/03-let-the-fingers-check-the-name.md).
7. **Rack it** in the slot that leaves room for the glasses still standing —
   [solution 4](programmed/04-plan-the-rack-for-the-whole-table.md).

**Why this combination.** Each piece answers one of the five findings, and four
of the five are rules that cost no training and can be read line by line. The
one learned part is the one problem 3 already chose and measured. Solution 5
costs nothing at all: it changes only the order of work the arm does anyway.

**What it gives up.** A second training run for the push model, on mixed
tables, of unknown size. Problem 3's took 38,012 pushes and 31 minutes for one
kind per table. And three new numbers that are fractions of a glass's own
height or degrees — the doubt bands and the shortest stem — each of which was
set by looking at generated glasses, the same way the two naming lines were.

### What would be added next

1. **[A learned second opinion](learned/06-a-learned-second-opinion-on-the-name.md)**,
   once there are real pictures to train it on. In the simulator it can only
   learn the artefacts that were drawn for it.
2. **A slimmer gripper, or grips from an angle.** Not a problem 4 solution.
   Short-stemmed glasses cannot be held at all today (0 of 200), and only 94 of
   200 tapered ones. That is [problem 5's](../../problem-5/problem.md) work and
   [`known-gaps.md`](../../known-gaps.md)'s first entry, and it is the largest
   loss in any problem 4 run.

### How it would be known to work

It would need a `problem-4-sim`: problem 3's bench with each glass's kind drawn
separately, and with side masks that can carry a drawn reflection. Scored
against the simulator's own record, the numbers are problem 4's own:

- glasses named as made, against what was spawned;
- glasses named wrongly but plausibly — this should be zero;
- glasses refused for want of a slot, against the fewest possible for that
  table, which [solution 4](programmed/04-plan-the-rack-for-the-whole-table.md) can compute
  exactly;
- and problem 3's: racked, toppled, pushes, refusals by reason.

Then `make run GUI=false` in Gazebo, because nothing is verified until the whole
thing has run end to end.

## Where the recommended combination can fail

- **Short-stemmed glasses are never racked.** The grip rules find nowhere to
  hold one below the cell's lowest grip. Every problem 4 table with one on it
  ends with that glass refused. [Known gaps](../../known-gaps.md).
- **A reflection taller than a short stem is still a stem.** The stem-length
  check separates a 10 mm notch from the shortest stem generated here by a
  factor of nearly two. A reflection band a sixth of the glass's height would
  pass it. The finger view and the weighing are what is left.
  [Solution 3](programmed/03-let-the-fingers-check-the-name.md).
- **A glass with no side view is pushed without its kind.** 42% of crowded
  glasses on mixed tables had no clean view. They can be moved only with the
  probe, or not at all, and the probe does not catch a glass that tips late in
  the push. [Solution 5](programmed/05-measure-before-you-push.md).
- **Planning the rack ignores the reach preference.** The code prefers slots
  the arm can stand over from either side. A planner that packs better will
  use the end slots more often, and whether the arm can place a glass there
  whichever way round it holds it is a question for Gazebo.
  [Solution 4](programmed/04-plan-the-rack-for-the-whole-table.md).
- **The forward model has not been trained on mixed tables.** Whether it keeps
  problem 3's result is not known until it is.
  [Solution 9](learned/09-plan-the-whole-table-with-the-push-model.md).
- **Every rule here was checked on glasses from the project's own ranges.** The
  margins that look comfortable — the nearest grippable stemmed glass is 0.045
  of its height from the short-stem line — were measured on those ranges.
  Problem 5 widens them.

← [The problem](../problem.md) · [Problem 5 — kinds whose proportions are unknown](../../problem-5) →
