# Solution 5 — measure before you push

*Programmed. Problem 3 pushes a crowded glass without measuring it, because a
crowded glass cannot be picked up. But a glass the gripper cannot get round can
often still be photographed. Measure every crowded glass that has a clean side
view before anything is pushed. Its kind, and so its foot, is then known when
the push is chosen. And when two glasses crowd each other, push the one that
was measured.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

This solution changes no code in any step. It changes the order the steps run
in. That makes it the cheapest thing in problem 4, and one of the most
important, because it is what gives the push its most important input.

## The problem this solves

### The push needs the foot, and the foot comes from the kind

A pushed glass slides while the push is lower than `a / μ` — half its foot
width over the friction with the table — and tips above it. [Problem
3](../../../problem-3/problem.md#how-low-the-push-has-to-be-and-why-it-is-a-property-of-the-glass)
explains why the height to check is 65 mm, the top edge of the jaw.

So the foot decides whether a glass may be pushed at all. And the foot, as a
share of the glass's widest part, is set by its kind:

| Kind | foot, as a share of the widest part |
| --- | --- |
| straight | 0.90 – 0.98 |
| tapered | 0.38 – 0.58 |
| stemmed | 0.70 – 0.95 |
| short-stemmed | 0.75 |

From above, the camera sees the widest part and not the foot, which is hidden
under the bowl or the rim. Problem 3's bench hands the foot over anyway, and
[problem 3's results](../../../../problem-3-results/README.md#what-these-results-do-not-cover)
flag it as generous. With one known kind per table, a real cell could at least
bound the foot from the kind. With several kinds, it cannot.

### Pushing without the kind refuses almost everything

How many glasses of each kind may be pushed at 65 mm, 200 of each:

| | straight | tapered | stemmed | short-stemmed |
| --- | --- | --- | --- | --- |
| true foot, μ = 0.3 | 200 | 116 | 200 | 200 |
| true foot, μ = 0.5 | 56 | 0 | 115 | 0 |
| foot unknown, assumed the narrowest any kind has, μ = 0.3 | 0 | 17 | 0 | 0 |

The last row is what a careful arm must assume about a glass it has not
measured: its foot might be 0.38 of its widest part. At that, 17 glasses in 800
may be pushed. Every other crowded glass would be refused.

## The main idea

Problem 3 says lifting is not available because of a circle: to lift a glass
the arm needs its profile, to get the profile it needs a side view, and
crowding took the side view away.

That is true of some crowded glasses, not all. **Crowding for the gripper and
crowding for the camera are different things.** The gripper needs about 70 mm
of clear table round the glass's middle, in every direction. The camera needs
one direction, 380 mm out, along which no other glass covers the target or
joins its outline.

### How many crowded glasses can still be seen

200 mixed tables were built with `_crowded_layout()` from
`problem-3-sim/bench.py`, each glass's kind drawn separately, and each table
kept only if at least one glass lacked room. For every glass without room,
`problem-2-programmed/views.py` was asked for its best allowed place — reachable,
not standing in another glass, nothing squarely in the way — and whether that
place leaves a clear gap in the picture between the target and every glass that
could spoil it.

| | glasses |
| --- | --- |
| on the tables | 994 |
| without room | 735 |
| without room, **with a clean side view** | **427 (58%)** |
| without room, no clean view | 308 |
| … of which a glass crowding it has a clean view | 156 |
| … of which every glass crowding it has one | 59 |

On problem 3's own test tables, one kind each, it is 417 of 760, 55%. So
problem 3 could have measured more than half of its crowded glasses before
pushing them. It did not need to, because the bench handed the foot over.

On 61 of the 200 mixed tables, every crowded glass has a clean view. On those,
no glass is ever pushed without its kind.

## The order, and what it changes

```text
look; rack every glass that has room                     problem 3, solution 1
measure from the side every crowded glass with a clean view
    name it, keep its profile                            problem 1, steps 2 and 3
while a glass still has no room:
    choose the push:
        prefer moving a measured glass                   its foot is known
        a glass not yet measured is moved only with the probe, or not at all
    push, look again
    a glass that has gained a clean view: measure it now
    a glass that has gained room: rack it, using the profile it already has
```

Three things follow.

**The foot is known for 58% of the crowded glasses before any push.** For those,
the push check is exact: no guessing about the kind.

**When two glasses crowd each other, the measured one moves.** Room is about the
pair, so moving either one makes room for both. Of the 308 crowded glasses that
cannot be seen, 156 are crowded by a glass that can. Pushing that one frees
the unseen glass without ever touching it.

**A profile belongs to the glass, not the place.** A measured glass that is then
pushed does not need measuring again: its shape has not changed. After each
push the arm looks again, and the glass is where the push aimed it, give or
take a few millimetres, while its nearest neighbour is at least 70 mm off. So
which glass is which is easy to keep track of.

### And the glasses that stay unseen

152 of the 735 crowded glasses on these tables are crowded only by glasses that
also cannot be seen. One of them has to be pushed without its kind. For those,
this solution offers what problem 3's programmed approach already has: the
**probe**, a 5 mm test push that watches how the glass starts to move, and
stops if it starts to tip. Or it refuses the glass.

Problem 3's results say the probe is not enough on its own. One tapered glass
passed its probe and tipped later in the push. [Problem 3's solution
8](../../../problem-3/solutions/08-a-learned-early-abort.md), which watches the
wrist force during the whole push, is the answer to that, and it is not built.

## What it costs

Almost nothing. Every glass that is racked gets a side view anyway. Here some
of those views are taken earlier, before a push rather than after it. A glass
measured before its push is not measured again, so the number of side views
does not go up.

The cost is that a side view is taken for a glass that is later refused — one
that could not be pushed anywhere useful. That is one arm move per such glass.

## A worked example

Two glasses stand 95 mm apart, centre to centre: a stemmed glass 210 mm tall
with an 88 mm bowl, and a tapered glass 150 mm tall with an 80 mm rim. Neither
has room.

**As problem 3 would do it.** From above, both are round and about the same
width. The kind of neither is known. At μ = 0.3, with the narrowest foot any
kind has assumed — 0.38 of the widest part — the stemmed glass's foot would be
33 mm, and `a / μ` 56 mm, under the 65 mm the jaw reaches. For the tapered
glass the same sum gives 51 mm. Both are refused. Or, if the foot is handed over as
on the bench, the arm pushes whichever the planner prefers.

**With this solution.** The arm tries a side view of each. Suppose the stemmed
glass's best place is clean: the tapered glass is off to one side in the picture. It is
measured and named stemmed. Its foot is 0.8 of its bowl, 70 mm, so `a / μ` is
117 mm, well above the jaw. It may be pushed. The tapered glass's only clean
places are out of reach, so it is not measured.

The stemmed glass is pushed away. The tapered glass now has room without having
been touched. It is measured, named and racked. The stemmed glass, already
measured, is racked from where it was pushed to.

## What it needs

- In `task.py`, the order above. The survey, the side view, the naming and the
  push are all existing steps.
- A record per glass of its profile, kept across pushes, and matched after each
  look by nearest position.
- In the push planner, a preference for the measured glass of a crowded pair,
  and the probe for one that is not.
- No new numbers.

## Where it is strong and where it breaks

**Strong.** It turns the foot from a guess into a measurement for most crowded
glasses, at no cost in arm time. It moves known glasses rather than unknown
ones. And it is only a reordering, so it can be added without changing any
step.

**Breaks.**

- **The view check does not ask the motion planner.** `views.py` checks reach,
  standing clear and line of sight. It does not check that the arm can get the
  camera there without crossing another glass. [Problem
  2](../../../02-segment-glasses/solutions/solution-overview.md#where-what-was-built-can-fail)
  says the same of both its pipelines. Near a crowd, that check matters more,
  so the real share of crowded glasses that can be measured is likely lower
  than 58%.
- **Glasses crowded only by glasses that cannot be seen** are still pushed
  blind or refused. On these tables that is about one crowded glass in five.
- **Keeping track of a glass after a push** is easy in the simulator and
  assumed here. A push that goes badly wrong — a glass that spins into another
  — could swap two identities. Problem 3's learned approach had pushes land up
  to 25 mm from their aim.
- **It uses the profile to name the glass before the fingers can check the
  name.** The checks of [solution 3](03-let-the-fingers-check-the-name.md) come
  later, at the grip. A glass pushed on a wrong name is pushed with the wrong
  foot. The foot is read off the profile directly, though, not off the name,
  so for the push the name does not matter.

## Where the idea comes from

**Acting to see.** Choosing actions for what they let the robot measure next is
called active perception. Here the action that pays is not a push but a look
taken earlier than it would have been. [Problem 2's
overview](../../../02-segment-glasses/solutions/solution-overview.md#feedback-choosing-what-to-measure-next)
sets out what it takes for a machine to choose its next measurement.

**Resolving uncertainty before committing.** When a decision depends on an
unknown that can be measured cheaply, measure it first. The whole project runs
on this: weigh before the full squeeze, feel before the last millimetres.

**Moving the known object.** In the rearrangement literature, a planner that can
choose which object to move prefers the one whose behaviour it can predict. The
same reasoning, here with the foot as the thing to predict.

## Where it sits among the other solutions

It feeds the push. [Solution 9](../learned/09-plan-the-whole-table-with-the-push-model.md)
is the push planner it feeds, and needs the kind per glass that this solution
provides. [Solution 7](../learned/07-guess-the-kind-from-above.md) is the other way of
getting the kind before a push, and is rejected. This solution is in the
recommended combination.

← [Solution 4 — plan the rack for the whole table](04-plan-the-rack-for-the-whole-table.md) · [Solution 6 — a learned second opinion on the name](../learned/06-a-learned-second-opinion-on-the-name.md) →
