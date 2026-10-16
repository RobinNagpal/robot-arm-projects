# The target layout — where the glasses should end up

## Introduction

A push has two halves. One half is *how* to push a glass. That is where
friction and tipping live, and it is the rest of this problem. The other half
is *where to push it to*. This page is about that half.

It is separate from the solutions for the same reason
[looking again at what was hidden](../02-segment-glasses/hidden-glasses.md) is
separate in problem 2: **every solution needs it and none of them differs in
it.**

This page shows that choosing where a glass should end up is plain geometry,
not a learning problem. It describes four methods for that geometry and what
each is good for. It explains why the answer is computed once for every
solution. And it shows how the same computation gives the least movement the
task can need, which is the most useful result here.

Read it after [the problem](problem.md) and [the examiner](the-examiner.md). It
uses the gripper's clear room and the readings `look()` gives, and both are
explained there.

## The question, written out

Problem 3 is finished when every glass has about 76 mm of clear room in every
direction, at least one usable side-on viewpoint, and nothing has been knocked
over. That is a statement about **where the glasses are**. So before anything
is pushed, someone has to decide where each glass should go.

The decision has four conditions it must meet, and one thing it should make as
small as possible.

**Every glass has its clear room.** The open jaw needs about 76 mm from a
glass's middle to the neighbour's edge. So two middles must be at least 76 mm
plus half the neighbour's widest width apart. Both glasses must be grippable,
so the pair needs 76 mm plus half the **wider** of the two. The layout must
use this edge version of the test.
[The problem](problem.md#the-gap-that-matters-is-not-the-gap-between-the-glasses)
explains why the test is not symmetric.

![The clear room is measured from a glass's middle in to its neighbour's edge, so the distance two middles need is 76 mm plus half the neighbour's rim; on one real table that makes a narrow glass 11.5 mm inside the room a wide neighbour denies it while the wide one has 1.6 mm to spare, and the symmetric version of the test, which measures out from each glass's own middle, misses 8 crowded glasses and invents 10 that are not.](../../images/03-push-glasses-apart/target-what-has-room-means.png)

**Every glass stands inside the glass zone and outside the rack.**
[The cell](../the-cell.md#the-layout-from-above) gives their sizes: 320 by
360 mm, and 60 by 40 mm.

**Every glass stays within reach.** The arm works comfortably between 300 and
780 mm from its base. A glass pushed outside that ring cannot be picked up
later, even if it is clear of its neighbours.

**Every glass keeps a clear line of sight from the side.** To measure a glass,
the camera stands 300 mm out from it, 120 mm above the table, looking level.
Problem 2's code divides that circle into twenty-four directions 15° apart. At
least one direction must have no other glass in it.

Treat this fourth condition with care, because **nothing in problem 3 tests
it.** The examiner has no line-of-sight check, and no solution chooses a
viewpoint. A layout that meets the first three conditions is accepted whether
or not a camera could see each glass. The condition is a stated aim, not a
marked requirement.

![The four conditions drawn on the table from the top, with the glass zone, the rack on the arm's other side and the comfortable reach ring at 300 and 780 mm; the zone's own corners sit 330 and 777 mm from the base and the rack does not overlap the zone at any point, so only the clear room and the zone walls can ever be the active condition.](../../images/03-push-glasses-apart/target-which-conditions-can-bind.png)

**And the glasses move as little as possible.** Every millimetre pushed is a
chance to knock something over. So among all layouts that meet the four
conditions, the wanted one is the layout nearest to where the glasses are now.

Look at what these conditions need to know. They need where each glass stands
and how wide it is, which `look()` reports. They need the clear room, the glass
zone, the rack and the reach, which the cell publishes as constants. **They do
not need friction, weight, or how a glass behaves when pushed.** So every glass
is a disc of known size at a known place on a flat rectangle. The question is
where to slide the discs so that none overlaps another's clear room, none
leaves the rectangle, and the total sliding is least. That is geometry with no
unknowns. It can be solved fully before the arm touches anything.

## Four ways to place the discs

There are several standard ways to solve this. They trade different things, so
it helps to know them together. Two words come first, because all four use
them.

An **objective** is the single number a method tries to make as small as
possible. Here it is the total travel: for each glass, the square of how far it
moved, added over all glasses. Squaring makes the number smooth, so a method
can follow its slope downhill. It also dislikes one long push more than several
short ones.

A **constraint** is a condition the answer must not break, however good its
objective. Here the constraints are the four conditions above.

### A constrained optimisation

The first method hands the objective and the constraints to a solver and asks
for the answer directly. Nothing is approximated and nothing is left out:
minimise total squared travel, with every pair far enough apart and every glass
inside the zone, outside the rack, inside the reach and with a clear viewpoint.

The usual method for this is **sequential quadratic programming**. The idea is
simpler than the name. The clearance constraints are curved, because a distance
between two middles is a square root. So the solver does not attack the real
problem directly. At the current layout, it replaces the objective with the
nearest simple curved version, and each constraint with the nearest straight
line. What is left is a **quadratic program**: a curved objective with straight
constraints. That shape is solved exactly and fast. The solver moves to that
answer and builds a fresh approximation there. Repeated, the steps settle on an
answer that meets the true constraints. That repetition is the word
*sequential*.

**It is good for being right.** It really minimises the objective, so its
answer defines the floor described below. The cost is that it needs a solver,
it is the slowest of the four, and it can settle in a local optimum. The first
caution at the end deals with that.

### Repulsive relaxation

The second method uses no solver. Give every pair of glasses a **repulsive
cost**: near zero while they are well apart, and rising steeply as they get
close to the required distance. Give the zone walls and the rack the same kind
of cost. Add all the costs together, and the layout has one number that is high
when anything is crowded. Then move every glass a small step in the direction
that lowers that number most. Repeat until nothing moves. That is an
**equilibrium**, where the pushes on every glass cancel.

It is like letting a few like charges loose in a box. They repel, spread out,
and stop when each is pushed equally from every side.

**It is good for speed and simplicity.** It is a few lines of arithmetic, and
for four to six glasses it finishes almost at once. But it is crude. It does
not try to keep travel small, so it spreads glasses further than needed. Its
layout is not the nearest legal one.

Its real advantage is practical. It gives not one layout but a sequence of
them, one per step, each less crowded than the last, none with an overlap.
**That sequence is a set of waypoints.** It gives a route to the finish that
does not pass through a neighbour. The other three methods do not answer that
question at all.

![One crowded table relaxed step by step, from the measured layout through the first two steps to equilibrium, with the circle each glass denies its neighbours drawn throughout; the crowding falls quickly but not at every step, and across fifty tables the layout it settles on asks for about five times the travel the floor requires.](../../images/03-push-glasses-apart/target-relaxation-step-by-step.png)

### Assignment to slots

The third method works differently, and that is its point. It does not ask
where the glasses should go. It fixes the possible positions first, and then
asks only **which glass goes where**.

First, work out a set of positions once. Each is inside the zone, outside the
rack, inside the reach, and far enough from the others that the clear room
holds for any glass of this kind. Call each one a **slot**. Every way of
putting glasses into separate slots is then legal, so nothing is left to check.
The only choice is which glass takes which slot. The cost of a choice is the
total distance the glasses travel.

That is a classic problem, the **assignment problem**: given a cost for every
pairing of a worker with a job, choose a one-to-one pairing with the least
total cost. The **Hungarian algorithm** solves it exactly. Its time grows as
the cube of the number of items, which for four to six glasses is nothing.

![The same five glasses and the same twelve slots in both panels, paired first by giving each glass its nearest free slot and then by the Hungarian algorithm; the places are identical, three of the five glasses go somewhere different, and the greedy pairing costs 435 mm of travel against the Hungarian answer's 312 mm.](../../images/03-push-glasses-apart/target-finding-places-is-not-assigning-them.png)

**It is good for certainty.** The layout cannot be illegal. The answer is
exact, with no seed and no local optimum. Every run gives the same slots, so
two runs are easy to compare. The cost is travel. The nearest slot is rarely
the nearest legal position, so the total movement is higher than a free layout
needs. Use it when a layout that is surely legal and instant is worth more than
the best one.

### Lloyd's algorithm

The fourth method comes from another field. It solves a slightly different
question, spreading points evenly through a region, but it answers this one
nearly for free.

First the idea behind it. Take the glasses' middles and divide the glass zone
by nearest middle. Every point of the table belongs to the glass closest to it.
The points that belong to one glass form its **Voronoi cell**. A crowded glass
has a small cell. A glass alone in a corner has a large one. The cells cover
the zone exactly, with no gaps and no overlaps.

**Lloyd's algorithm** repeats two steps. Work out every glass's Voronoi cell.
Move every glass to the middle of its own cell. Then do it again. A glass with
a neighbour pressing on one side gets moved away from it. So crowding undoes
itself, and each glass drifts to the middle of its fair share of the table.

**It is good for being almost nothing to write.** With a Voronoi routine it is
a few lines, and it rarely fails. It spreads points more evenly than repulsion
does. Its weakness is that even spreading is not the task. It optimises neither
clearance nor travel. It may walk a glass across the table when a nudge was
enough. Its proper use is as a starting layout for the constrained
optimisation, or as a check that the zone has room for the glasses at all.

### Which to use

All four give the same kind of answer, so the choice depends on the use. The
constrained optimisation defines the floor, so it must be run. Repulsive
relaxation is worth keeping beside it for its waypoints. Assignment to slots is
the fallback when a legal layout is needed at once. Lloyd's algorithm is a
starting layout and a check. One of them must be chosen and then frozen, for
reasons the cautions below explain.

![The travel each of the four methods asks for, as a multiple of the floor for the same table, over fifty tables: the constrained optimisation is 1x by definition, assignment to slots sits near four times it and repulsive relaxation near five, Lloyd's algorithm near seven and is the only one that leaves tables illegal, and the same solver started 40 mm away settles in a worse local optimum on five of the fifty.](../../images/03-push-glasses-apart/target-four-methods-against-the-floor.png)

**None of this is in the bench yet.** The examiner exists. So does the
programmed geometry that picks a landing spot one push at a time. That answers
*where can this glass go next*, not *where should every glass finish*. The
shared layout on this page is a design, not code that runs today.

## Why this is shared and not a solution

The layout can be computed. The next question is who computes it. The answer is:
not each solution on its own.

Suppose each solution chose its own targets. Then two solutions could score
differently because one pushes better, or because one aimed at an easier
layout. Targets far apart make the clearance easy. Targets near the legal limit
need much more accurate pushing. The score would then mix up targets with
skill, and the comparison would be worthless.

One layout, computed once from the same measurements and given to every
solution, removes that. Every solution that aims at a destination aims at the
same places. So the only difference left is how well it gets the glasses there.
A solution may still ignore the layout and just push a glass away from its
neighbour, and one of the six does. Its cost shows on the same scale, as travel
against the floor below.

Problem 2 uses the same argument for its own shared step: **the shared part is
everything that is not the thing being compared.**
[Problem 2's examiner](../02-segment-glasses/the-examiner.md#why-there-is-an-examiner-at-all)
makes that case.

## The displacement floor

The layout is useful for aiming. But computing it also gives something more
useful: a yardstick.

When the constrained optimisation finishes, it reports the value of its
objective: the total movement its layout needs. The solver minimised exactly
that number under exactly the task's conditions. So **no layout that meets the
task needs less movement than this**. It is the least the task can cost in
travel. It is called the **displacement floor**.

![One table whose six glasses all start without room, and the smallest set of moves that gives every one of them its room, each arrow labelled with its length; across fifty tables the floor runs from 3 to 171 mm with a median of 61 mm, and it reads as a scale on which a solution at twice the floor spent twice the travel the task demanded.](../../images/03-push-glasses-apart/target-the-displacement-floor.png)

That puts every solution on a scale that means something. A solution moves the
glasses some multiple of the necessary movement. At two times the floor, it
spent twice the travel the task needed. At ten times the floor, it was
wandering. The scale exists **before any solution exists**, because it comes
only from the measurements and the constants. It cannot favour a solution,
because it never saw one.

Over the fifty held-out tables the floor is **3,284 mm in total**. The
examiner's travel figure is divided by that number.
[The comparison](../../03-push-glasses-apart/results/README.md) shows how each
solution lands against it.

The floor rose from 2,534 mm when the invented jaw became a real Robotiq
2F-85. The reason is not about pushing. The floor depends on how much room
each glass needs, which is how far the *open* hand reaches from its middle. On
the 2F-85 the fingers stand 76 mm out, where the old design assumed 70. So
every glass needs 6 mm more space, and a legal layout is harder to reach. It is
still reachable on all fifty tables. That was checked, not assumed. A few more
millimetres each would have made some tables impossible to finish.

The most useful reading is at the bottom of the scale. A solution close to the
floor is not thereby a *good* solution. It means that **its remaining error is
not its fault**. The travel it spent was travel the task required. No smarter
choice of pushes could have spent less. That is the signal to stop improving
this part and look elsewhere. Problem 2's examiner has the same instrument, its
[floor of error](../02-segment-glasses/the-examiner.md#the-ceiling-what-the-best-possible-answer-would-be).

## Two cautions

The floor can only be trusted if two easy mistakes are avoided.

**The solver and its seed must be fixed.** Minimising travel under clearance
has more than one local optimum: a layout that no small change improves, but
that is not the best overall. Picture two glasses crowding each other. Moving
the left one left and moving the right one right are both good answers. Which
one a method finds depends on where it started. So if the solver, its starting
layout and its random seed are not all fixed, two solutions can get different
targets from the same measurements. Then the problem this page exists to remove
comes back. So the layout is computed once per table, stored with it, and
reused by every solution.

**Success stays defined on the clearance, not on the layout.** A solution that
gives every glass its 76 mm of clear room has done what the problem asks, even
if its layout looks nothing like the computed one. There is more than one way
to uncrowd a table. So the check for "done" must be the clearance condition,
applied to where the glasses really are. It must never be each glass's distance
to its target. **The computed layout is the reference and the floor, not the
pass mark.** Scoring distance to the targets would punish a solution for
finding a different good answer.

## What the layout does not tell you

The layout says where the glasses should go. It says nothing about getting
them there. Everything it leaves open is the real work of the solutions:

- **A push is not a translation.** A pushed glass slides and turns at once, so
  the push does not deliver the move the layout asks for.
  [The problem](problem.md#what-else-makes-this-hard) explains why.
- **Which pushes are possible depends on friction, and nobody knows it.**
- **A glass may tip instead of sliding**, and some glasses must be refused
  however clear their target is.
  [Pushing without toppling](pushing-without-toppling.md) covers this.
- **Reaching a target takes several pushes, and their errors add up.** How a
  solution handles that is a large part of what separates the six.
- **The other glasses are in the way, so the order matters.** A glass pushed
  first may pass through where another glass still stands. Choosing the order,
  and sometimes moving a glass twice, is planning the layout does not do.

So the split is clean. Geometry says where. The solutions say how.

## Where to go next

- [The problem](problem.md): why dragging rather than lifting, the three
  distances that matter, and what "done" means.
- [The examiner](the-examiner.md): the shared input, output and marking, and
  the travel each solution reports.
- [Pushing without toppling](pushing-without-toppling.md): how low a push must
  be, and the refusal path.
- [The solutions](solutions/overview.md): what each one puts between the
  measurements and the pushes.
