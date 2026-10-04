# Solution 9 — plan the whole table with the push model

*Learned, with the model as a decider inside a loop that looks again. Take
problem 3's forward model — the one that predicts what a push does to every
glass on the table — and retrain it for mixed tables: each glass's own kind as
an input, and "not measured" as a kind of its own. Then make the search that
chooses a push count what the rack can still take. Used for the pushes. The
slots themselves stay with the arithmetic of solution 4.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

Problem 3 chose [a learned forward model and a search over
pushes](../../../03-push-glasses-apart/solutions/10-learn-a-forward-model-then-plan.md). On 50
held-out tables it cleared more glasses than the programmed planner in half the
pushes, and toppled none. Problem 4 inherits that choice. This document says
what the model needs to become a problem 4 model, and what the search needs to
become a problem 4 search.

None of it is built. Nothing here is measured beyond what problem 3 measured.
It is the plan for the one learned piece in the recommended combination.

## What problem 3's model is

From [`problem-3-learned`](../../../../problem-3-learned/README.md): a small
network, three layers of 256, trained five times from different starts. Where
the five disagree, it has not seen a push like the one asked about.

- **In**, 34 numbers: the table's kind; the pushed glass's height, widest width
  and foot; the push; and where up to five other glasses stand and how big they
  are.
- **Out**, 14 numbers: where every glass moves, the chance something topples,
  and the chance the jaw is blocked on the way down.

A search tries 1,500 pushes per crowded glass, drops any that any of the five
copies gives more than a 1% chance of toppling something, and makes the one
that leaves least room missing. Then the arm looks again and plans afresh.

It was trained on 38,012 pushes made in MuJoCo, about 31 minutes on a laptop.

## What has to change in the model

### The kind, per glass

The model is told **the table's** kind, the same on every row. In problem 4
there is no table kind. Each glass has its own, or has none yet.

So the kind moves from the table to the glass. The pushed glass gets a kind out
of five: the four, or **not measured**. Each of the other glasses gets the same.
And a glass that is not measured has no foot, so its foot goes in as zero
alongside the flag that says so.

### Training it on glasses it is not told about

The model has to learn what "not measured" means, and there is only one honest
way to teach it. During training, hide the kind and the foot of some glasses at
random — the simulator still knows them, and still pushes them for real — and
let the model learn what happens to a glass it was not told about.

What it learns is the spread of outcomes over the kinds a hidden glass could
be, weighted by how often each appears on the training tables. That is **not the
worst case**. It is an average. A tapered glass pushed as "not measured" topples
more often than the average not-measured glass, and the model's topple chance
for it will be too low.

So the topple limit for a push on a not-measured glass has to be stricter than
the 1% for a measured one. How much stricter is a number to set on tuning
tables, the way problem 3 set its 1%. [Solution 5](../programmed/05-measure-before-you-push.md)
keeps that case as rare as possible by measuring first and moving measured
glasses in preference.

### More data

The input grows: five kinds per glass instead of four per table, and the flag.
Problem 3's model already missed topples it had seen too rarely — a jaw lifting
a stemmed glass under its bowl, a jaw body clipping a neighbour behind. Mixing
kinds on one table makes every such case rarer per kind. How many pushes it
takes is not known until it is tried. Problem 3's two rounds took about 25
minutes of collecting; several times that is still hours, not days.

## What has to change in the search

### Push only for glasses the rack can take

In problem 3, `take()` lifts a glass off the table and it is gone. There is no
rack, so every glass freed is worth freeing.

In problem 4 the rack can be full. A push that frees a glass the rack has no
room for is a push made for nothing — and every push is the one moment a glass
can be toppled. So the search's score gains a term:

```text
score = room still missing on the table, counted only for glasses the rack can still take
      + a small cost per millimetre pushed
```

"Glasses the rack can still take" comes from [solution
4](../programmed/04-plan-the-rack-for-the-whole-table.md)'s capacity: the rack as it is, and
the widths and heights of the glasses still standing. That is arithmetic, and
exact.

A glass the rack cannot take is refused for want of a slot straight away, and
not pushed. On a six-glass table where a wide glass is racked early, that can be
two glasses that never need touching.

### Prefer the measured glass

When two glasses crowd each other, moving either makes room for both. The
search prefers the push on the glass whose kind and foot are known, as
[solution 5](../programmed/05-measure-before-you-push.md) argues. With the stricter limit for
not-measured glasses, this happens by itself: fewer of their pushes survive.

## Why the slots are not learned too

An obvious extension is to let the search plan pushes and slots together, or
to learn a value for each whole-table plan. It is not worth it. The rack has
six slots and three states each. [Solution
4](../programmed/04-plan-the-rack-for-the-whole-table.md) finds the best slot exactly, in
milliseconds, by trying every way of filling it. A learned part there could
only be worse.

What the push search needs from the rack is one number per table state: how
many more glasses fit. Solution 4 gives it.

## Where the model sits

As in problem 3, a **decider** for the push, inside a loop that checks. The arm
makes the push the search chose, and then looks. A push that did not do what
was expected is found on the next look, and the next plan starts from what is
really there.

What the look cannot undo is a topple. That is where this model is weakest in
problem 3, and where mixing kinds makes it weaker. It is why the stricter limit
and the preference for measured glasses are there, and why [problem 3's early
abort](../../../03-push-glasses-apart/solutions/08-a-learned-early-abort.md), which watches the
wrist during the push, is still the next thing to add.

## The step in pseudocode

```text
look
for each crowded glass:
    kind  = its measured kind, or "not measured"               solution 5 decides which
    foot  = its measured foot, or none
    if the rack cannot take it: refuse it for want of a slot   solution 4's capacity
search 1,500 pushes per crowded glass the rack can take:
    predict with the five copies
    drop: topple chance over the limit — 1% if measured, stricter if not
    drop: a glass landing outside the zone; the jaw out of reach; a move longer than the push
    score: room missing, for glasses the rack can take; plus millimetres pushed
make the best push; look again                                  problem 3, unchanged
```

## What it needs

- `problem-3-sim/bench.py` draws each glass's kind separately — the same change
  every problem 4 solution needs.
- `problem-3-learned/features.py` puts the kind on each glass instead of the
  table, with a fifth "not measured" value and the foot zeroed with it.
- Collection that hides some glasses' kinds at random.
- A second topple limit, for not-measured glasses, set on tuning tables.
- The rack capacity from [solution 4](../programmed/04-plan-the-rack-for-the-whole-table.md)
  in the search's score.
- A training run: hours on a laptop, as in problem 3.

## Where it is strong and where it breaks

**Strong.** It keeps the approach problem 3 measured as the best: more glasses
freed in fewer pushes, and nothing toppled on the held-out tables. It needs no
friction value and no tipping formula written down. And counting the rack stops
it pushing glasses that were never going to be racked.

**Breaks.**

- **It is not trained, so it is not measured.** Whether it keeps problem 3's
  result on mixed tables is unknown.
- **"Not measured" teaches an average, not a worst case.** The stricter limit is
  a patch, and its value is a tuning number.
- **Everything problem 3's model gets wrong, it gets wrong too**, and probably
  more often: topples it rates safe, a landing tail of 25 mm, refusals that
  cannot explain themselves, and silent answers outside what it has seen. [The
  problem 3 overview](../../../03-push-glasses-apart/solutions/solution-overview.md#where-the-chosen-solution-can-fail)
  lists them.
- **It has learned MuJoCo's friction.** A real table makes it wrong with no
  warning but the next look. [Problem 3's solution
  9](../../../03-push-glasses-apart/solutions/09-identify-the-contact-parameters.md) is the
  answer to that.

## Where the idea comes from

**Model-based planning with a learned forward model.** Learn what an action
does, then search actions against the model, one step at a time, re-planning
after each real step. [Problem 3's solution
10](../../../03-push-glasses-apart/solutions/10-learn-a-forward-model-then-plan.md#where-the-idea-comes-from)
has the references.

**Training under hidden information.** Showing a model inputs with parts hidden,
so that it learns what to expect when they are missing, is how a model is made
to cope with a missing sensor. What it learns is the expectation over what
could be hidden, which is why the limit has to be set apart.

**Planning against a resource.** The rack is a resource that runs out, and a
push is only worth making if what it frees can use the resource. Folding the
resource into the score is the standard way to stop a planner spending effort
on goals it cannot reach.

## Where it sits among the other solutions

It is the push half of the recommended combination. It needs [solution
5](../programmed/05-measure-before-you-push.md) to give it kinds and [solution
4](../programmed/04-plan-the-rack-for-the-whole-table.md) to give it the rack's capacity. It
is the retrained pushing piece of [solution
8](08-the-learned-pipelines-retrained.md).

← [Solution 8 — the learned pipelines, retrained](08-the-learned-pipelines-retrained.md) · [Solution overview](../solution-overview.md) →
