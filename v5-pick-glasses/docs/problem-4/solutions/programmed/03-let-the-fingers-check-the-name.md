# Solution 3 — let the fingers check the name

*Programmed. The name is decided from one picture, and everything after it
trusts it. This solution adds two checks that do not come from that picture.
Before the fingers move in, the arithmetic checks that they clear the glass
over the whole height of the pad. After the lift, the weight is compared with
what the named kind should weigh, before the glass is squeezed at its kind's
rating.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

[The problem](../../problem.md#1-naming-the-kind-becomes-load-bearing) says that
nothing downstream re-checks the name, and that the first thing to notice a
wrong one is the width at first contact in step 5. That is right, and it is
already built: `_close_until_touching()` in `task.py` closes at 1 N and refuses
the glass if the fingers stop more than 4 mm from the width the camera said.

This document asks what that check misses. It misses two things, and they are
the two wrong names that can do harm:

- a waist that is not a stem, where the pads meet the glass **before** the
  fingers start to close, so the touch check never runs;
- a stemmed glass named short-stemmed, where the grip is in the right place at
  the right width, so the touch check passes, and the harm is in how hard the
  glass is then squeezed.

[Solution 2](02-a-name-that-shows-its-evidence.md) tries to stop both from the
picture. This one catches what gets through, from something the picture did not
decide.

## The problem this solves

### The fingers meet the glass on the way in

On a run, the fingers are opened to the grip's opening plus 20 mm, the arm comes
in, and only then do the fingers close. So the touch check assumes the opened
fingers fit round the glass.

When the profile has a notch in it, the opening is the notch's width, not the
wall's. If the wall is more than 20 mm wider than the notch, the pads hit it on
the way in.

Notches were drawn into the side masks of the 200 straight and 200 tapered
glasses, at a random height between 15% and 45%, and every glass that was given
a stem grip was followed through:

| Notch | stem grips | pads hit the wall on the way in | touch check fires after closing |
| --- | --- | --- | --- |
| 20% of the width, 6 mm tall | 14 | 0 | 14 |
| 20% of the width, 10 mm tall | 23 | 0 | 23 |
| 40% of the width, 6 mm tall | 119 | 84 | 35 |
| 40% of the width, 10 mm tall | 143 | 97 | 46 |
| 60% of the width, 6 mm tall | 164 | 164 | — |
| 60% of the width, 10 mm tall | 173 | 173 | — |

These are a fresh draw of notch heights, so the counts differ a little from
[solution 2](02-a-name-that-shows-its-evidence.md#a-stem-has-to-be-long-enough-to-be-a-stem)'s.

A shallow notch is caught today: the fingers fit, close at 1 N, stop against
the real wall, and the glass is refused. A deep one is not caught at all. The
pads push into the side of a glass that is standing free on the table, and a
tall tumbler pushed at 51 mm is the thing problem 3 exists to avoid.

### The right place, the wrong squeeze

A stemmed glass and a short-stemmed glass are gripped by the same rule. Named
either way, the grip is at the same height with the same opening. [Solution
1](01-join-them-as-they-are.md#the-name-can-be-wrong-where-nothing-checks-it)
measured this on all 75 stemmed glasses that can be gripped: the two answers
are identical.

What differs is the wall. `holding_force()` holds a weighed glass at its wall's
rating, not at what its weight needs, because the weight sum does not stop a
glass turning about the line between the pads. A stemmed glass is `thin`,
6 N. A short-stemmed glass is `thick`, 20 N. So a stemmed glass named
short-stemmed is turned over and carried at 20 N, on a stem rated for 6.

The touch check cannot see this. The fingers stop exactly where the camera
said they would.

## The main idea

Check the name against things the name predicts and the one picture did not
decide.

1. **Before moving: the fingers must clear the glass over the whole pad.** A
   pad is 14 mm tall. The rule chooses one height, but the pad covers 7 mm
   either side of it. So the widest the profile gets over that span must be
   less than the opened fingers.
2. **After closing: the width at contact.** Already built, unchanged.
3. **After the lift: the weight must fit the named kind's wall.** Each wall
   category gives its own estimate of the weight from the same profile. The
   weighed mass says which category the glass is actually in. The glass is held
   at the lower of the two ratings: its name's and its weight's.

## The first check: the fingers must clear the glass

This one is pure arithmetic on the profile the arm already has. It runs in
`find_grip()`'s checks, before any move.

```text
span  = grip height ± half a pad
widest = the widest the profile gets inside that span
refuse if widest > the opening the fingers will be opened to
```

Today the checks look at the width only at the grip height. That is correct for
a stem, where the width is the same all the way along, and for a straight wall.
It is wrong for anything narrower at one height than just above or below it.
That is exactly what a notch is, and nothing a real grip rule should choose.

Measured on the same notched glasses:

- every glass whose pads would have hit the wall on the way in was refused by
  this check, before moving;
- every other notched glass is caught by the touch check, as today;
- none of the 352 real grips found in the same run — 180 straight, 96 tapered
  and 76 stemmed glasses measured through the camera — was refused by it.

So together with the touch check, no notched glass reached the point of being
squeezed or pushed.

## The second check: the width at contact

Unchanged. `_close_until_touching()` closes at 1 N and refuses the glass if the
fingers stop more than 4 mm from the camera's width. With the first check in
front of it, it now only ever runs with fingers that fit.

## The third check: the weight must fit the name

`estimate_mass()` works out a glass's weight from its measured profile and its
kind's wall category: `thin`, `normal` or `thick`. The estimate is wrong by about
a third either way, which `spec.py` says openly, because it only has to get the
first squeeze into the right range. The lift that follows weighs the glass
properly.

The three wall categories are far apart. For the same profile, the `thick`
estimate is 2.5 times the `thin` one. On every stemmed glass measured, that
ratio was exactly 2.5, because the wall enters the sum the same way on every
glass of a shape. A factor of 2.5 is far outside an error of a third.

So the weighing can name the wall:

```text
guess for each wall category = estimate_mass(profile, that category)
the weighed wall = the category whose guess is nearest the weighed mass
hold at the lower rating: the name's wall, or the weighed wall
if they disagree, the report says so
```

A stemmed glass named short-stemmed weighs about 40% of what a short-stemmed
glass of that shape would. The weighed wall is `thin`, and it is held at 6 N.

This check sits almost in the right place in the sequence. Step 5 goes: close
at 1 N, squeeze at the estimate, lift 10 mm and weigh, **then** set down and
re-grip at the rating. The 20 N comes only at the re-grip, and the weighing is
before it.

The squeeze at the estimate is the one gap. It is worked out from the name's
wall, so a wrongly named stemmed glass is estimated at 2.5 times its weight and
squeezed accordingly before it is weighed. For the glass in the worked example
below, that is 7.4 N instead of 2.9 N, on a stem rated for 6. So the starting
squeeze needs the same treatment as the re-grip: **cap it at the lowest rating
of every kind whose rule gives this same grip.** The rules are run anyway, in
microseconds. For a glass with a stem, that is the stemmed glass's 6 N whenever
the stemmed rule finds the same grip.

The other direction is already safe. A short-stemmed glass named stemmed is
estimated at 40% of its real weight. The weighed mass then asks for more than a
thin wall's 6 N, and `force_for_measured_mass()` refuses it as too heavy to hold.
That is a refusal, not a break.

## The step in pseudocode

```text
grip = the named kind's rule, or both, as in solution 2
refuse if the profile is wider than the opened fingers anywhere within half a pad of the grip      new

open the fingers to the opening + 20 mm, come in                   unchanged
close at 1 N; refuse if contact is more than 4 mm from the opening unchanged
squeeze at the estimate, capped at the lowest rating of any kind whose rule gives this grip        new cap
lift 10 mm, weigh                                                  unchanged

the weighed wall = the category whose estimate is nearest the weight                              new
cap = the lower of the name's rating and the weighed wall's                                        new
set down, re-grip at cap, carry on                                 unchanged, with the new cap
```

## A worked example

**A notch.** The straight glass from [solution
2](02-a-name-that-shows-its-evidence.md#a-worked-example): 162 mm tall, 62 mm
rim, a bright band 8 mm tall at 30% of its height taking 40% off the width.
Named stemmed, gripped at 51 mm, opening 34.3 mm. The fingers would open to
54.3 mm. The pad covers 44 to 58 mm, and outside the notch the glass there is
about 58 mm across. The first check refuses the grip: the glass is wider than
the fingers inside the pad's span. The arm does not move.

**A squeeze.** A stemmed glass 227 mm tall with an 89 mm bowl and a 13.5 mm
stem. This is the grippable stemmed glass whose waist is nearest the short-stem
line, at 0.215 of its height. Suppose some error names it short-stemmed. The
grip is at 51 mm with the fingers 15.1 mm apart, exactly as it would be under
its right name. The first and second checks pass, correctly. The stemmed rule
gives the same grip, so the starting squeeze is capped at 6 N; it comes to
2.9 N. The lift weighs it at about 180 g. The `thick` estimate from
its profile is 450 g, the `thin` one 180 g. The weighed wall is `thin`, and it
is re-gripped at 6 N, not 20.

## What it needs

- One more check in `rules.py`'s `_check()`: the widest the profile gets within
  half a pad of the grip, against the opened fingers. `PAD_HEIGHT` is already
  in `arm/dimensions.py`, and the 20 mm is already in `task.py`.
- In `force.py`, a function that says which wall category a weighed mass fits,
  and in `task.py`, the lower of the two caps at the re-grip.
- No new numbers about a glass. The categories and their ratings are already in
  `spec.py`.
- Tests on `family()` of every kind: the span check refuses no real grip; a
  drawn notch never reaches the fingers; the weighed wall of every glass is its
  own kind's.

## Where it is strong and where it breaks

**Strong.** Both checks rest on something other than the picture the name came
from: one on the geometry of the gripper, one on a scale. Neither adds a move.
Neither adds a number about any glass. And the one wrong name that passes every
existing check — the 20 N case — is caught before the 20 N is applied.

**Breaks.**

- **A notch taller than the pad.** The first check looks 7 mm either side of
  the grip. A reflection band more than 14 mm tall, centred on the grip, has no
  wider wall inside the span. The touch check then decides, and only if the
  fingers fit.
- **Two kinds with the same wall.** The weighing names the wall, not the kind.
  Straight and tapered glasses are both `normal`, so a mix-up between them
  cannot be seen by weight. It does not need to be: the two rules find no
  grip on each other's glasses, so that mix-up ends in a refusal anyway.
- **Real walls vary.** In the simulator each glass's mass is worked out from its
  own kind's wall, so the estimate from the right profile is close to exact. A
  real cupboard mixes heavy and light glasses of one shape. A thick-walled
  wine glass could weigh like a short-stemmed one, and would be held at 6 N
  anyway, because its name is the lower of the two. That is the safe side.
- **The capped starting squeeze could be too light for a heavy glass with a
  stem.** 6 N lifts about 370 g. The short-stemmed glasses generated here are
  estimated at 176 to 334 g, so none is short of squeeze today. A heavier one,
  in problem 5, would slip in the 10 mm lift and be refused.
- **It does not help a glass that is refused.** A glass it catches is left on
  the table with a reason. It is not racked.

## Where the idea comes from

**Guarded moves and contact checks.** The last millimetres are felt, not
driven: close until touching, then compare. This project uses it in step 5 and
step 6, and [the gripping
area](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md)
of robotics-basics sets out the five-step squeeze it comes from.

**Checking a model's prediction against a different sensor.** The name is a
model of the glass. Each kind predicts a width at contact and a weight. Checking
a prediction with a sensor that played no part in making it is the same idea as
problem 3's "look again" after a push.

**The cheap exact check first.** The span check is arithmetic that runs in
microseconds and catches the deep notches before anything moves. The weighing
is a sensor reading the run already takes.

## Where it sits among the other solutions

It is the backstop behind [solution 2](02-a-name-that-shows-its-evidence.md).
Solution 2 stops a wrong name from the picture; this one stops it from doing
harm when the picture was wrong. Both are in the recommended combination.
[Solution 6](../learned/06-a-learned-second-opinion-on-the-name.md) would sit in front of
both, as a verifier on the picture.

← [Solution 2 — a name that shows its evidence](02-a-name-that-shows-its-evidence.md) · [Solution 4 — plan the rack for the whole table](04-plan-the-rack-for-the-whole-table.md) →
