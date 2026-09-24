# Problem 5 — kinds whose proportions are not known

The same as [problem 4](../problem-4/problem.md), except that the glasses are
not drawn from proportions anybody wrote down. A wine glass may have a stem that
is a third of its height or a tenth of it. A tumbler may be 90 mm tall or
240 mm. The arm still has to measure each one, pick it up, invert it and rack
it.

This is the problem the whole project exists for.

## What is on the table

Glasses of the four shapes, at proportions drawn from a range far wider than
the one problem 4 uses — wide enough that no two glasses of a kind look much
alike, and wide enough to include sizes nobody anticipated when the rules were
written.

Everything else is problem 4: several kinds at once, at least 150 mm apart to
begin with, the same rack.

## What is new

Nothing about the *pipeline*. Everything about what may be written down.

Problem 4 can, if it has to, get away with a number that is true of the glasses
in its ranges. Problem 5 cannot get away with any number that is about a glass
at all. The only things that may be held are sentences about shape and numbers
about the gripper.

![Eight wine glasses, and where the rule holds each one](../../images/why-rules-not-sizes.png)

That picture is the argument. Eight glasses, all called the same thing, no two
alike — heights from 131 to 230 mm, stems of different lengths and thicknesses.
The mark on each is where the rule decided to hold it. One rule covers all of
them, and a ninth glass needs no change at all.

The right panel is the same information as a table of measurements would have to
hold it: one dot per glass, and a spread of 25 mm in grip height for a glass
height that varies by 100 mm. The relationship is loose enough that no single
number works. **That is what makes a lookup table the wrong shape for this
problem, and it is the only reason the project is built the way it is.**

## The four things that must not be written down

1. **A height to grip at.** It comes from the rule applied to the measured
   profile, every time.
2. **A finger opening.** It is the width the camera measured at the height the
   rule chose, a second earlier.
3. **A weight, or a force.** The force comes from the weight, and the weight is
   measured by lifting the glass ten millimetres.
4. **A band to search in, expressed in millimetres.** Search bands are
   fractions of the glass's own height, which is why they survive a glass twice
   the size.

What *may* be written down is anything about the gripper: how wide it opens,
how tall its pads are, how low its body may go, how far its wrist turns. Those
are facts about the cell and they do not change when the glassware does.

## The six steps, and what changes at each

**Step 1 — find the glasses.** Unchanged. Nothing in it was ever about a
particular glass; a glass is something standing above the table.

**Step 2 — measure one.** Unchanged, and the one number it needs — how far back
to stand — is already worked out from the lens and the tallest glass the cell
handles rather than from any glass.

**Step 3 — name the kind.** This is where the pressure lands. The two thresholds
that name a kind — a waist below 0.17 of the height, a wall leaning more than
6 degrees — were set by looking at two populations of generated glasses. Widen
the populations and the two will overlap, and glasses will land on the line.
A classifier that reports how close the call was is no longer a nicety here.

**Step 4 — choose where to hold it.** The rules already work this way and this
is what they were built for. The pressure is on the *checks* rather than the
rules: an unusual glass is much more likely to produce an answer that is
arithmetically correct and a bad idea, which is what the five rejections exist
to catch.

**Step 5 — how hard to squeeze.** The mass estimate gets worse, because it
scales a wall thickness category by a shape that is now much more variable. It
does not matter much, because the estimate is openly a guess and the lift is
what settles it. This is the step that degrades most gracefully.

**Step 6 — turn it over and stand it down.** The tilt budget already computes
per glass from its measured width and height. Unchanged.

## What is already known to fail

This problem is not hypothetical, and the project has already measured how badly
it does at it. [`known-gaps.md`](../known-gaps.md) records the result of giving
200 random glasses of each kind to the real classifier and grip rules, using
their exact shapes with no camera error — the best case.

Most sizes cannot be held at all. Straight glasses got a grip in 85 cases out of
200, and only between 125 and 170 mm tall. Short-stemmed glasses got a grip in
none.

That is the honest state of problem 5 today: **the rules generalise in the way
they were designed to, and the gripper does not.** The limit is not the rule
finding the wrong place. It is that a glass under about 120 mm tall has no place
at all between the lowest the gripper body can go and the highest a grip can be
and still be invertible.

## What "done" means

A run is **done** when every glass is racked or refused with a reason, exactly
as in problem 4.

The number that matters here is different from every other problem's: **what
fraction of the plausible range of each kind can be handled at all.** A run that
racks four glasses says nothing if all four were the sizes the cell happens to
suit. The instrument for this is not a run; it is the property test over a
generated family, run across the whole range.

## Where the work would start

Not on the rules. On the cell.

The three open questions at the end of the
[problem statement](../../problem-statement.md#decisions-still-open) are all
really about this problem: whether a slimmer gripper body would open up the
short glasses, whether the arm is bolted in the right place, and whether the
task should be planned as a whole so that a grip is chosen knowing what the turn
and the placement will need.
