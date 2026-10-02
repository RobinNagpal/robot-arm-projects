# Solution 4 — plan the rack for the whole table

*Programmed. Choose each glass's slot so that the glasses still standing can
still fit. The rack has six slots and three things each can hold, so every
possible way of filling it can be checked in a few milliseconds. No heuristic
is needed; the best answer is simply computed.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

[The problem](../../problem.md#the-rack-has-to-be-shared-out) says the slot choice
stops being "the next free one" and becomes a decision that can run out of
room. This document measures how often it does, and replaces the slot choice
with one that looks at the whole table.

It turns out to be the cheapest fix in problem 4, and the one with the clearest
answer. The rack is small enough that the best possible choice can be computed
exactly, every time, so there is nothing to tune.

## The problem this solves

### What a wide glass costs

A glass stood upside down over a peg has a few millimetres either side before
it touches its neighbour. It pivots about its rim on the way down, so tilt uses
that room up quickly on a tall glass. `tilt_budget_deg()` in `rack/layout.py`
works out how much tilt a glass can afford. If that is less than the 3° the arm
can be trusted to hold, `needs_empty_neighbour()` says the glass is **wide**:
the slots either side of it must stay empty.

Wide has nothing to do with kind. It depends on the glass's widest part and its
height. But kinds differ a lot in how often they produce one. Of 200 glasses of
each kind:

| Kind | wide |
| --- | --- |
| straight | 13 |
| tapered | 116 |
| stemmed | 122 |
| short-stemmed | 6 |

With one kind per table, as in problems 2 and 3, the glasses on a table are
mostly all wide or mostly all narrow. With several kinds, the rack gets a mix,
and a mix is where the choice of slot matters.

### What the code does today

`_choose_slot()` in `task.py`:

1. keeps the free slots this glass can use — for a wide glass, only those whose
   neighbours are both free;
2. of those, prefers the ones the arm can stand over from either side, because
   which side it will stand on is settled by how the glass was picked up. With
   the rack in the middle of its area, that is slots 2, 3 and 4;
3. takes the furthest from the arm's base, so no racked glass is ever between
   the arm and the next slot.

Then `slots_consumed()` marks the slot used, and for a wide glass its two
neighbours too.

Every step looks at the glass in hand and at nothing else. The first narrow
glass of a run goes to slot 4, in the middle of the row, because slot 4 is the
furthest the arm can reach from both sides. That one choice can decide that no
wide glass fits later.

### How often it costs a glass

1500 tables of four to six glasses, at least two kinds each, drawn at random.
Each glass was measured through the cell's side view and given a grip or not;
a glass that cannot be held never reaches the rack and is not counted. The
glasses were taken in a random order, standing in for nearest-first.

| | racked | refused for want of a slot | tables short of the best |
| --- | --- | --- | --- |
| the slot choice as it is | 3103 | 183 | 123 |
| the best possible | **3237** | **49** | — |

Out of 3286 glasses that could be held, the slot choice as it is loses 134 that
could have been racked. They fall on 123 of the 1500 tables.

The losses are small here for a reason that has nothing to do with the rack:
only 44% of the glasses on these tables can be held at all. [Known
gaps](../../../known-gaps.md) has why. If every glass could be held — which is
what fixing that gap would bring — the same arithmetic on 5000 tables gives:

| | racked | tables where every glass is racked |
| --- | --- | --- |
| the slot choice as it is | 19031 | 1619 |
| the best possible | 21906 | 2526 |

Then the slot choice loses 13% of the glasses, and a third of the tables that
could have been cleared are not.

### The rack is too small for some tables whatever is done

A wide glass takes three slots, or two at an end. Six glasses need six slots.
So a table of six with even one wide glass on it cannot all be racked. Of the
1605 six-glass tables above, only 166 could be racked completely by any choice
of slots.

That is not something to fix here. It is a fact about a six-slot rack, and
"refused for want of a slot" is the correct result for those tables. What this
solution does is make sure a glass is only refused that way when there really
was no room.

## The main idea

The rack has six slots, and each can be empty, hold a narrow glass or hold a
wide one. That is 3⁶ = 729 ways of filling it, and most of them break the
empty-neighbour rule. Checking all of them takes a few milliseconds.

So for any rack, partly filled, and any list of glasses still to come, the
**most of them that can still fit** can be found by trying every way of filling
the empty slots and keeping the best. Call it the rack's **capacity** for those
glasses.

The slot for the glass in hand is then the one that leaves the largest
capacity for the rest:

```text
for each slot this glass can use:
    value = 1 + capacity(the rack with this glass in that slot, the glasses still standing)
leave  = capacity(the rack as it is, the glasses still standing)
if leave > the best value: leave this glass standing for now
else: take the slot with the best value; ties go the way the code already
      prefers: reachable from both sides, then furthest from the base
```

The "leave it standing for now" line matters. Sometimes the glass in hand is a
wide one that would use up the room for two narrow ones. Racking the two
narrow ones first and coming back racks more. The glass left is not refused
yet. It is tried again at the end with whatever room is left.

## What is known about the glasses still standing

The capacity needs to know which of the glasses still standing are wide. None
of them has been measured from the side yet. The survey has seen each one from
above.

From above, the arm gets each glass's widest part. That alone decides most of
them. The tallest glass the cell handles is 230 mm and the shortest 65 mm, so:

- a glass under 75.9 mm across is never wide, however tall it is;
- a glass over 93.2 mm across is always wide, however short.

Of 800 glasses, 285 fall between the two, and whether they are wide depends on
their height.

There are two ways to treat those:

- **Plan them as wide.** The safe assumption: a glass planned as wide and
  measured narrow only ever frees room. On the 1500 tables this racked 3230,
  seven short of the best, on 7 tables.
- **Use the survey's height.** The survey's depth readings put the rim at a
  height. Problem 3's bench reports a height with every glass it sees. With the
  height known, every glass is decided, and this racked 3237, the best.

Planning them as wide gets all but 7 glasses in 3237 and needs nothing new.

## Sharing an empty slot

`slots_consumed()` takes both neighbours of a wide glass out of use. So two wide
glasses two slots apart are not allowed, although the empty slot between them
is an empty neighbour to both, and that is all either needs.

Letting two wide glasses share an empty slot changes the best possible count by
23 glasses in 21906 when every glass can be held. It is not worth the change to
`slots_consumed()`, and this solution leaves it alone.

## Racking the widest first is worse

An obvious fix is to take the wide glasses first, so they get the room they
need before the narrow ones fill it. With the slot choice as it is, that racks
15450 of the 21906, against 19031 for a random order. The wide glasses go to
the middle of the row, where the reach preference sends them, and each one uses
three slots.

The order is not the problem. The slot is.

## A worked example

The five glasses from [solution 1](01-join-them-as-they-are.md#a-worked-example):
two narrow straight glasses and three wide ones — a stemmed glass and two
tapered glasses — taken in the order narrow, wide, narrow, wide, wide.

| glass | the slot choice as it is | with this solution |
| --- | --- | --- |
| narrow | slot 4 | slots 2 and 3 leave room for 3 more, every other slot for 2. Takes 3, the further |
| wide | slot 2 — uses 1, 2, 3 | slots 0 and 5 leave room for 2 more, slot 1 for 1. Takes 5, the further — uses 4, 5 |
| narrow | slot 5 | slot 2 leaves room for 1 more, slots 0 and 1 for none. Takes 2 |
| wide | nowhere | slot 0 — uses 0, 1 |
| wide | nowhere | nowhere |
| **racked** | **3** | **4** |

Four is the most any choice of slots could rack from these five. The last wide
glass is refused for want of a slot, correctly: there was no room for it.

## What it needs

- In `rack/layout.py`: `capacity(occupied, still_to_come)`, trying every way of
  filling the empty slots; and a slot choice that uses it. Plain arithmetic,
  no ROS, testable like the rest of that file.
- In `task.py`: `_choose_slot()` is handed the survey's widths of the glasses
  still standing, and the loop learns to leave a glass for later.
- The two widths above, 75.9 and 93.2 mm, are not new numbers. They come out of
  `tilt_budget_deg()` with the cell's shortest and tallest glass, and are worked
  out, not stored.
- Tests: on random mixed tables, the planned count equals the best possible
  count, and a glass is never refused for want of a slot when there was a slot
  for it.

## Where it is strong and where it breaks

**Strong.** It is exact. On these tables it racks as many as any choice of
slots could, and a refusal for want of a slot now means there was no room. It
needs nothing trained and no new number about a glass. It costs no arm time.

**Breaks.**

- **It uses the end slots more.** The code prefers slots 2 to 4 because the arm
  can stand over them from either side. A plan that packs better puts glasses
  in 0, 1 and 5 more often. Those slots are only reachable one way round, and
  which way round the glass is held is settled before the slot is. If the pick
  happens to leave the arm on the wrong side, the glass is in the fingers with
  nowhere it can go. The slot choice as it is already falls back to those
  slots when it must, so this is more of an existing risk, not a new one.
  Whether it bites is a question for Gazebo.
- **A glass the survey missed.** Capacity is planned for the glasses the survey
  saw. One that appears later — found behind another, or pushed into view — was
  not planned for.
- **It plans for glasses that may never reach the rack.** A glass still standing
  may turn out to have no grip. The plan kept room for it. Re-planning after
  every measurement puts that room back, but a slot already chosen stays chosen.
- **It does not fix the size of the rack.** Six-glass tables with a wide glass
  still end with a refusal.

## Where the idea comes from

**Bin packing, and exhaustive search when the problem is small.** Putting
items of different sizes into a fixed row is a packing problem, which is hard
in general and trivial at six slots. When every possibility can be listed in
milliseconds, listing them beats any rule of thumb, and there is nothing left to
argue about.

**Online choice with lookahead.** The glasses arrive one at a time, in an order
set by something else — here, reaching the nearest first. A choice made
without looking at what is still to come is called greedy, and is the thing
that went wrong here. Planning each choice against what is known of the rest is
the standard answer.

**Planning under an unknown, on the safe side.** A glass not yet measured is
planned as the worst it can be. It can only turn out better. This is the same
pattern the project uses everywhere a number is not known yet.

## Where it sits among the other solutions

It fixes the rack and leaves everything else alone. It is in the recommended
combination. [Solution 9](../learned/09-plan-the-whole-table-with-the-push-model.md) plans
pushes and slots together with a learned model; for the slot half, this
solution is exact and needs no model, so solution 9 is only used for the
pushes.

← [Solution 3 — let the fingers check the name](03-let-the-fingers-check-the-name.md) · [Solution 5 — measure before you push](05-measure-before-you-push.md) →
