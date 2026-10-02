# Solution 2 — a name that shows its evidence

*Programmed. Make the name say how close the call was and what it rests on.
Measure the lean with a line fitted up the wall, so that it is a number and not
a step. Require a stem to be long enough to be a stem. And when the call is
close, run both kinds' rules instead of guessing between them.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

In problem 1, `classify()` returns a name or nothing. A glass that only just
cleared a line is treated exactly like one far from it. [Problem 1's step
3](../../../problem-1/step3-what-kind-of-glass.md#where-this-approach-can-fail)
lists that as a weakness, and [the problem](../../problem.md) says problem 4 is
where it has to be fixed.

This document fixes it, and finds on the way that "add a confidence" is not
enough. There are two different ways a name goes wrong. A **close call** is a
glass near one of the two lines. A **confident mistake** is a glass far from
every line with the wrong name anyway, because the profile itself is wrong. A
margin catches the first and says nothing about the second. This solution
does something about both.

## The problem this solves

`classify()` asks three questions of the measured profile:

```text
is there a waist?             the narrowest point below the widest, with wider glass both sides
if so, how high is it?        below 0.17 of the height: short-stemmed; above: stemmed
if not, does the wall lean?   over 6°: tapered; under: straight
```

[Solution 1](01-join-them-as-they-are.md#the-name-can-be-wrong-where-nothing-checks-it)
measured what a wrong name costs. Most wrong names end in a refusal, because
the wrong rule finds no grip. So what matters is:

- **tapered or straight**, near the 6° line. A wrong call here is a refusal.
  That is safe, but it is a glass lost.
- **stemmed or short-stemmed**, near the 0.17 line. A wrong call here passes
  every check, and the glass is held at 20 N instead of 6 N.
- **a waist that is not a stem**. A tumbler with a notch in its outline is named
  stemmed, and the stemmed rule may find a grip at a stem that does not exist.

## What the lean looks like through the cell's camera

The first thing a margin needs is a number that can be close to the line.
The lean, as the code measures it today, is not one.

`wall_lean_deg()` takes the median of `slope()` over 5% to 45% of the height.
`slope()` compares the width 12 mm apart, which is `LEAN_SPAN`. The level view
sees 1.37 mm per pixel, so 12 mm is about eight rows, and the wall has to move
out a whole pixel across those eight rows before the slope changes at all. One
pixel across eight rows is already 7.1°.

So, measured through masks drawn at the cell's scale, 200 glasses of each:

| Glass made as | lean the code reads |
| --- | --- |
| straight | 0.0° on all 200 |
| tapered | 7.1° on 163, 14.0° on 37 |

Nothing reads in between. The 6° line sits between the first two steps, so
every straight glass is "6° under" and every tapered glass is "1.1° over". A
margin computed from this number carries no information.

It also means the classifier is right on all 400 by luck of where the step
falls. With exact profiles, 42 of the 200 tapered glasses lean less than 6°
and are named straight. Through the camera, the step rounds them up to 7.1°,
and they are named tapered.

### A lean that is a number

Fit a straight line to the edge of the profile over the same band, 5% to 45% of
the height. The band is 40 to 100 rows tall, and a line through that many rows
finds the slope to a fraction of a pixel.

Against the exact outline, the fitted lean through the camera is out by a
median of 0.54° on straight glasses and 0.32° on tapered ones. The worst is
1.3° and 1.7°. That is a number a margin can be computed from.

### And why a precise lean on its own makes things worse

With the fitted lean, 50 of the 200 tapered glasses read under 6° and are named
straight. Through the camera, the straight rule found no grip on any tapered
glass: its `just_below_centre_of_mass` rule needs a run of wall upright to
within its tolerance, and a measured cone has none.

So switching to the fitted lean alone would refuse 50 tapered glasses that the
stepped lean racks today. The precise number is only useful together with
something that acts on it. That is the doubt band below.

## A stem has to be long enough to be a stem

`waist_at()` finds the longest run of profile at its narrowest width, and asks
that there is wider glass on both sides. It does not ask how long the run is.

A real stem is long. Measured through the camera, as a share of the glass's
height:

| | shortest | 5th percentile | median |
| --- | --- | --- | --- |
| stemmed glasses | 0.287 | 0.301 | 0.375 |
| short-stemmed glasses | 0.154 | 0.158 | 0.171 |
| a 10 mm notch cut 40% into a straight or tapered glass | — | — | 0.048, and 0.083 at most |

A reflection that cuts a notch into a tumbler's outline makes a short narrow
run. The shortest real stem is nearly twice the longest notch. So a stem can be
required to run **at least 0.12 of the glass's height**. That is a rule about
shape, a fraction of the glass's own height, and it is allowed under the
project's rule.

How much it matters: notches were drawn into the masks of the 400 straight and
tapered glasses, at a random height between 15% and 45% of the glass:

| Notch | named stemmed or short-stemmed | given a stem grip |
| --- | --- | --- |
| 3 mm tall, any depth | 0 | 0 — smoothing removes it |
| 6 mm tall, 20% of the width | 236 | 20 |
| 6 mm tall, 40% of the width | 369 | 132 |
| 6 mm tall, 60% of the width | 372 | 172 |

None of these masks was refused as ragged. The raggedness check looks for an
edge that wanders from row to row, and a notch is a clean step in and out.

With the 0.12 rule, every one of those waists is too short to be a stem. The
glass falls through to the lean question and is named straight or tapered. The
rows of the rejected run have to be left out of the fitted line, or the notch
drags the lean. That part is not measured here.

## The doubt band, and what happens inside it

Every name now comes with its margin. Close to a line, the name is **in doubt**
between the two kinds either side of it.

| Line | margin in | in doubt when | why that wide |
| --- | --- | --- | --- |
| 6° lean | degrees, fitted | within 1.7° | the worst fitted error measured |
| 0.17 waist | share of the height | within 0.02 | the level view reads a glass 6 to 10 mm tall, which moves the share by up to 0.015 |

A glass in doubt is not refused, and the name is not guessed. **Both kinds'
rules are run**:

- If only one finds a grip, that one is used. For tapered against straight,
  this is what happens: through the camera, no glass got a grip from both.
- If both find a grip, the grip is used with **the lower of the two force caps**.
  For stemmed against short-stemmed, both rules find the same grip, so this is
  6 N rather than 20 N. The report says "stemmed or short-stemmed", and
  [solution 3](03-let-the-fingers-check-the-name.md) settles which after the
  glass is weighed.
- If neither finds one, the glass is refused, the same as today.

This is safe for one reason that is worth stating: **each rule checks its own
answer**. The opening limits, the band height, the lowest grip and the halfway
line are checked against the profile, not against the name. Running a second
rule adds a second checked answer. It does not remove a check.

How often the band is entered, on the 800 glasses measured through the camera:
with the fitted lean, 66 tapered glasses are within 1° of the line, and more
within 1.7°. No straight glass is. On the waist line, 1 of 400 stemmed and
short-stemmed glasses is within 0.02, and 121 within 0.04. So the lean line is
where this does its work in this cell, and the waist line is where problem 5
will need it.

## The second view, for a stem

A stem is round, so it looks the same from every side. A reflection depends on
where the light is and where the camera is, and moves when the camera moves.

`task.py` already takes a second picture at 90° for every short-stemmed glass,
to look for a handle. This solution takes it for every glass named stemmed or
short-stemmed too, and requires the waist to be at the same height, to within
the stem's own length, in both. A notch that is only in one picture is not a
stem.

This one is not measured. The cell's glasses are opaque and make no
reflections, so a drawn notch appears in whichever picture it was drawn into.
The check is here because it costs one arm move on a glass that is about to be
picked up by its stem, which is the one place a wrong waist does harm.

## The step in pseudocode

```text
profile = measured from the side                     unchanged

waist, run = the longest narrowest run below the widest
if waist and run >= 0.12 of the height:              new: a stem must be long enough
    share = waist / height
    name  = short-stemmed if share < 0.17 else stemmed
    doubt = within 0.02 of 0.17                      new
    second view at 90°: the waist must be there too  new, for any stem
else:
    lean  = a line fitted up the wall, 5% to 45%     new: fitted, not stepped
    name  = tapered if lean > 6° else straight
    doubt = within 1.7° of 6°                        new

if doubt:
    grips = each of the two kinds' rules, each with its own checks
    keep the one that found a grip; if both, the lower force cap
else:
    grip  = the named kind's rule                    unchanged
```

## A worked example

A straight glass 162 mm tall with a 62 mm rim. A bright band 8 mm tall crosses
it at 30% of its height and takes 40% off the width there.

**Today.** The mask passes the raggedness check. `waist_at()` finds the notch:
a narrowest run with wider glass above and below, at 0.30 of the height. It is
above 0.17, so the glass is named **stemmed**. The stemmed rule looks between
5% and 60% of the height, finds the waist inside that band, and puts the grip at
51 mm with the fingers 34.3 mm apart. Every check passes: 34.3 mm is inside
the 4 to 40 mm a stem may be, 51 mm is above the lowest grip, and below
halfway.

The arm then opens the fingers to 54.3 mm — the opening plus 20 mm — and comes
in. The glass there is 58.2 mm across. The pads meet the wall on the way in,
before the fingers ever close.

**With this solution.** The notch run is about 8 mm, 0.05 of the height. That is
less than 0.12, so it is not a stem. The glass goes to the lean question. A
straight glass's fitted lean is at most about 3° — its true lean under 1.5°,
plus the fit's worst error — well outside the doubt band, so it is named
**straight** with no doubt, and the straight rule holds it just below its centre of mass, as for any
tumbler.

## What it needs

- `classify()` returns the name, the margin and, in doubt, the second kind.
- `profile.py` gains a fitted lean and the length of the stem run.
- `task.py` runs both rules when in doubt and keeps the lower cap.
- Three new numbers in `detect.py`: the shortest stem, 0.12 of the height; and
  the two doubt bands, 1.7° and 0.02 of the height. Each is a rule about shape.
- Tests against `family()` for every kind: the doubt band is entered on the
  glasses near a line and on no others, and a drawn notch is never named a stem.

## Where it is strong and where it breaks

**Strong.** It is a few dozen lines, all of them readable. It turns the one
confident mistake that was measured — a notch named a stem — back into the
right name. And it never makes a name less safe: in doubt it adds a checked
answer and takes the lower squeeze.

**Breaks.**

- **A reflection band taller than a short stem is still a stem.** The shortest
  stem generated here is 0.154 of its glass's height. A band 0.12 of the height
  passes. On a 160 mm glass that is 19 mm of reflection, which is a lot, but not
  impossible on real glass under a strip light.
- **The three numbers were set by looking at generated glasses**, like the two
  lines they sit beside. Problem 5 widens the ranges, and short stems will
  get shorter.
- **The doubt bands are as wide as the errors this simulator makes.** A real
  camera will make others.
- **The second view is unmeasured.** Its whole value is against reflections,
  which the cell does not make.

## Where the idea comes from

**Classification with a reject option.** A classifier allowed to say "not
sure" rather than forced to name something, and the trade between how often it
declines and how often it is wrong. The classic reference is C. K. Chow, "On
optimum recognition error and reject tradeoff", *IEEE Transactions on
Information Theory*, 1970. Here the doubt is not turned into a refusal but into
a second checked rule, which is the cheaper answer when both rules can be run
in a millisecond.

**Sub-pixel edge fitting.** Fitting a line or a curve to many edge pixels finds
a position or a slope far finer than one pixel. It is the standard way to
measure from a coarse picture, and the reason the fitted lean is a number.

**Checking the evidence, not the confidence.** A margin says how close the
call was on the question asked. It says nothing about whether the question was
the right one. The stem-length rule asks a second question that a reflection
cannot answer the same way a stem does.

## Where it sits among the other solutions

It fixes the name before anything moves. [Solution
3](03-let-the-fingers-check-the-name.md) checks the name again after the
fingers touch, for the mistakes this one cannot see. [Solution
6](../learned/06-a-learned-second-opinion-on-the-name.md) is the learned version of the
same idea, as a verifier.

← [Solution 1 — join them as they are](01-join-them-as-they-are.md) · [Solution 3 — let the fingers check the name](03-let-the-fingers-check-the-name.md) →
