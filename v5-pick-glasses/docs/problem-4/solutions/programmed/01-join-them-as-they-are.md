# Solution 1 — join them as they are

*Programmed, and the baseline. Take problem 2's finding, problem 3's pushing
and problem 1's six steps, chain them in that order, and change nothing. Every
other solution is measured against this one.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

The problem statement says problem 4 is problems 1, 2 and 3 joined up, plus one
thing none of them has. So the first thing to try is to join them and see
where the one thing bites.

This document does that. It says what the joined pipeline is, which of its
joins hold, and which break. Three break. Each one is the subject of a later
solution, and this document is where the size of each break is measured.

## The pipeline

```text
find every glass from above                    problem 2, clustering on the table
loop:
    rack every glass that has room             problem 3, solution 1
        measure it from the side               problem 1, step 2
        name it                                problem 1, step 3
        choose the grip                        problem 1, step 4
        squeeze, lift, weigh                   problem 1, step 5
        take the next free slot, stand it down problem 1, step 6
    if a glass still has no room:
        push one, look again                   problem 3, plan-feel-look-again
    if nothing can be pushed: refuse the rest, with the reason
```

The only glue is the order. `task.py` already takes glasses nearest first and
runs problem 1's six steps on each. Problem 3's programmed loop already racks
every glass with room before it pushes anything. Put the two together and the
loop above is what comes out.

## What holds

**Finding.** Problem 2's clustering drops depth points onto the table and groups
them by distance. Nothing in it is about a kind. On problem 2's 50 test scenes
it found all 250 glasses, and a mixed table is no harder for it: glasses still
stand at least 150 mm apart before problem 3 crowds them.

The [problem](../../problem.md#problem-2s-strongest-tool-is-taken-away) warns that
the footprint check gets weaker with four kinds. That is true, and it does not
matter here, because neither of problem 2's built pipelines uses a footprint
check. [Problem 2's
overview](../../../problem-2/solutions/solution-overview.md#where-what-was-built-can-fail)
lists it as missing.

**Choosing a view, measuring, gripping, squeezing.** None of these is about a
kind except through the name. `find_grip()` takes the name and looks up the
rule. `force.py` takes the name and looks up the wall. The force cap changing
from one glass to the next is correct behaviour, as the problem says.

**Racking what has room first.** Problem 3's solution 1: a racked glass is
nobody's neighbour. Nothing about it depends on the kind.

## What breaks

### The name can be wrong where nothing checks it

In problem 1 a wrong name is cheap. The wrong rule usually finds no grip and the
glass is refused.

That is still mostly true. Every rule was run on every kind, 200 glasses each,
from profiles measured through the cell's side view:

| Glass made as | straight rule | tapered rule | stemmed rule | short-stemmed rule |
| --- | --- | --- | --- | --- |
| straight | **179** | 0 | 0 | 0 |
| tapered | 0 | **94** | 0 | 0 |
| stemmed | 0 | 0 | **75** | 75 |
| short-stemmed | 0 | 0 | 0 | **0** |

The bold numbers are the right rule. Off the diagonal, all but one entry is
zero: a wrong rule finds nowhere to hold the glass, and it is refused. That is
the safe failure problem 1 relies on.

The one entry that is not zero is a stemmed glass under the short-stemmed rule.
Both kinds use `narrowest_below_widest`, so the grip is in the same place with
the same opening on all 75. Every check passes. The difference is the wall:
a stemmed glass is `thin` and is held at 6 N, a short-stemmed one is `thick`
and is held at 20 N. `holding_force()` holds a weighed glass at its wall's
rating, not at what its weight needs. So a stemmed glass named short-stemmed is
turned over and carried at more than three times what its stem is rated for.

Through the camera, no stemmed glass was named short-stemmed. The nearest one
that could be gripped had its waist at 0.215 of its height, against a line at
0.17. So in this cell the case needs a larger error than the camera makes. A
reflection is one. [Solution 2](02-a-name-that-shows-its-evidence.md) and
[solution 3](03-let-the-fingers-check-the-name.md) are about this.

### The rack runs out

`_choose_slot()` in `task.py` takes the free slots, keeps the ones a glass of
this width can use, prefers the ones the arm can stand over from either side,
and takes the furthest of those. It looks at the glass in hand and nothing else.

With one kind, that is mostly fine. With several, the rack holds glasses of
different widths, and a wide glass needs both neighbours empty. Which glasses
are wide depends on the kind: 116 of 200 tapered and 122 of 200 stemmed glasses
are wide, against 13 of 200 straight and 6 of 200 short-stemmed.

On 1500 mixed tables of four to six glasses, counting only the glasses that can
be gripped at all:

| | glasses racked | refused for want of a slot |
| --- | --- | --- |
| the slot choice as it is | 3103 | 183 |
| the most that could be racked | 3237 | 49 |

So 134 glasses, on 123 of the 1500 tables, are left standing that a better
choice of slot would have racked. [Solution
4](04-plan-the-rack-for-the-whole-table.md) is that better choice.

### Pushing needs the kind, and nobody has measured it yet

Problem 3's push check says a glass slides while the push is below `a / μ`,
half the foot width over the friction, and tips above. The height to check is
65 mm, the top edge of the jaw. So the foot decides whether a glass may be
pushed at all.

In problem 3 this was easy. The kind was known for the whole table, and
`look()` in `problem-3-sim/bench.py` hands over the foot width with every glass.
Problem 3's [results](../../../../problem-3-results/README.md#what-these-results-do-not-cover)
already say that this is generous: a camera looking down sees the widest part,
not the foot.

In problem 4 the kind is not known until the glass has been measured from the
side, and the glass that has to be pushed is the one whose side view the
crowding may have taken away. The foot, as a share of the widest part, is very
different from kind to kind:

| Kind | foot, as a share of the widest part |
| --- | --- |
| straight | 0.90 – 0.98 |
| tapered | 0.38 – 0.58 |
| stemmed | 0.70 – 0.95 |
| short-stemmed | 0.75 |

Both built pushers break on this. The programmed planner reads the foot from
`look()`. The learned forward model is given the table's one kind as an input
and the foot as another. Neither has anything to do with a table where the kind
differs per glass and is not known. [Solution 5](05-measure-before-you-push.md)
and [solution 9](../learned/09-plan-the-whole-table-with-the-push-model.md) are about this.

## A worked example

A table of five, worked through with the functions in `rack/layout.py`: two
tapered glasses 190 and 210 mm tall with rims of 96 and 100 mm, a stemmed glass
200 mm tall with a 90 mm bowl, and two narrow straight glasses. The two tapered
glasses stand close together; everything else has room. All three tall glasses
are wide: the 90 mm bowl leaves 5 mm a side in a 100 mm slot, which a 200 mm
glass uses up at 1.4° of tilt, and the arm is only trusted to 3°.

1. The survey finds all five.
2. The three with room are racked, nearest first. The first straight glass is
   narrow and takes slot 4, the furthest slot the arm can reach from both
   sides. The stemmed glass is wide. Of the slots whose neighbours are both
   free, 2 is the only one in reach from both sides, so it takes 2 and uses up
   1, 2 and 3. The second straight glass takes slot 5.
3. One tapered glass is pushed clear. Here the joined pipeline has to know its
   foot. On problem 3's bench it is handed over. On a real cell it is not.
4. Both tapered glasses are wide. The only free slot is 0, and its neighbour,
   slot 1, is used up. Neither fits. Both are refused for want of a slot.

Four could have been racked. Put the first straight glass in slot 2, the
stemmed glass in slot 0 (using up 0 and 1), and the second straight glass in
slot 3. Slot 5 then still has an empty neighbour, and one tapered glass fits
there. The slot choice lost a glass because it only looked at the glass in
hand, and the loss was settled by the very first glass racked.

## What it needs

Nothing new. Every piece exists. The joining is a few dozen lines in `task.py`
and a mixed-kind version of problem 3's bench to score it on.

## Where it is strong and where it breaks

**Strong.** It is all built, all checkable, and every refusal says why. Most
wrong names still end in a refusal, because the grip rules' own checks are
strict. Nothing here needs training.

**Breaks.** In three places, each measured above: a stemmed glass named
short-stemmed passes every check and is squeezed at 20 N; the rack refuses 134
glasses in 3237 that a better slot choice would rack; and the push check has no
foot for a glass that has not been named.

## Where the idea comes from

Nothing to cite. This is what the problem statement means by "joined up", done
literally, so that each later solution can be measured by what it adds.

## Where it sits among the other solutions

It is the baseline. [Solutions 2](02-a-name-that-shows-its-evidence.md) and
[3](03-let-the-fingers-check-the-name.md) fix the name. [Solution
4](04-plan-the-rack-for-the-whole-table.md) fixes the rack. [Solutions
5](05-measure-before-you-push.md) and
[9](../learned/09-plan-the-whole-table-with-the-push-model.md) fix the push.

← [Solution overview](../solution-overview.md) · [Solution 2 — a name that shows its evidence](02-a-name-that-shows-its-evidence.md) →
