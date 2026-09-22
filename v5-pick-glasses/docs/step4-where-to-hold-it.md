# Step 4 — where to hold it

The arm knows the shape and it knows the kind. Now it has to pick a height to
grip at and a distance to open the fingers to.

Code: `glasses/rules.py`, `glasses/profile.py`, `glasses/spec.py`.

## What makes a grip point good

Three things, and every rule in the project is an attempt to satisfy all three
at once.

**The wall must be upright enough.** Flat pads on a sloping wall slide, and the
steeper the slope the more of the grip force turns into a push down the wall
instead of into it. `VERTICAL_TOLERANCE` is 6 degrees, and the number comes
from the pads: a 12 mm silicone pad conforms by about 1.2 mm across its height,
and `atan(1.2/12)` is 5.7 degrees.

It started at 2 degrees, which is what you pick if you are thinking about
geometry rather than about rubber. It refused every short mould-tapered tumbler
in the test family, because a wall that leans 3 degrees is not vertical and 2
degrees says so. Six is a fact about the hardware; two was an opinion.

**There must be enough of it.** A pad needs a band of wall at least as tall as
the pad to sit on. That is `min_band_height_m`, and it is 8–12 mm depending on
the kind.

**It must be low.** After the turn, the end that was at the bottom is at the
top. Hold a glass halfway up and, once it is upside down, the fingers are level
with the rack pegs. Every search band in `spec.py` stops at or below half the
glass's height, and `_check()` enforces it as well, because a rule that finds
something high up has found the wrong thing.

## Three rules

![One rule per kind](../images/grip-per-kind.png)

| Rule | Used by | What it looks for |
| --- | --- | --- |
| `lowest_vertical_section` | straight glass | the lowest band of wall within 6° of upright, at least a pad tall |
| `flattest_in_band` | tapered glass | the least-sloping band in the search window |
| `narrowest_below_widest` | stemmed, short-stemmed | the waist below the widest point |

`flattest_in_band` exists because a cone has no upright wall anywhere. Asking
for one returns nothing, so the tapered rule asks a different question: of all
the places a pad could sit, which is closest to upright? On a conical tumbler
that is near the base, where the wall has had least distance to spread.

`narrowest_below_widest` is the one that reads like a sentence about glassware,
and it is true of every stemmed glass ever made. The widest point of a wine
glass is its rim or the belly of its bowl; below that the glass necks down to
the stem before flaring out again into the foot. The narrowest point in
between is the stem, wherever it happens to be on this particular glass.

## Finding the waist was harder than it sounds

`waist_at()` originally returned the first index of the narrowest run of
widths. On a glass with a long parallel stem that is a plateau, many rows wide,
and the first row of that plateau is at the bottom — right where the stem
starts flaring into the foot. The arm would have gripped the flare, which is
sloping, wider, and exactly where a stem is weakest.

It now returns the **middle of the longest narrowest run**, which on a parallel
stem is the middle of the stem.

A second bug in the same area is worth recording because it only appeared once
in forty glasses. The generator drew the foot diameter independently of the
bowl diameter, so occasionally the foot came out wider than the bowl — which
makes the *base* the widest point of the glass, leaves `waist_at()` searching a
slice below the base, and crashes on an empty array. Real glasses do not have
feet wider than their bowls, and the generator now draws the foot as a fraction
of the bowl.

Neither of those would have been found with one test glass. Both were found by
running the rules over a family of forty.

## The opening is read off, never looked up

Once the rule has returned a height, the finger opening is the width the camera
measured **at that height**:

```python
opening = profile.width_at(height)
```

That single line is the whole reason this project can handle a glass nobody
measured. There is no lookup, no average stem diameter, no per-kind default.
The camera saw 9.2 mm at 30.8 mm up, so the fingers go to 9.2 mm.

Change the glass and both numbers change, with nothing to edit.

## Four ways an answer is rejected

A rule can return a number that is arithmetically correct and a bad idea — a
"waist" found in a mask artefact, a stem on a glass far too wide for the
gripper. `_check()` catches four cases, each one much cheaper here than with
the arm already moving:

1. **The opening is outside what this kind should ever need.** A stem 60 mm
   across is not a stem; the rule found something else.
2. **The opening is wider than the gripper opens at all** (95 mm).
3. **The band is shorter than the pads need.**
4. **The grip is more than halfway up the glass**, which after the turn puts
   the fingers among the rack pegs.

Each raises `NoGrip` with the reason written out, and that reason is what ends
up in the run report next to the glass that was left standing.

## Why this beats a table of measurements

![Eight wine glasses, and where the rule holds each one](../images/why-rules-not-sizes.png)

The left panel is eight wine glasses the project generated. They are all called
the same thing and no two are alike: heights from 131 to 230 mm, bowls of
different depths, stems of different lengths and thicknesses. The red mark on
each is where `narrowest_below_widest` decided to hold it.

The right panel is the same information as a table of measurements would have
to hold it — one dot per glass, and a spread of 25 mm in grip height for a
glass height that varies by 100 mm. The relationship is loose enough that no
single number works, which is exactly what makes a lookup table the wrong
shape for this problem.

One rule covers all of them. Adding a ninth glass to the left panel needs no
change at all, and *that* is the property the project is really built around.

## Could the arm learn where to hold it instead

A fair question, and worth answering with evidence rather than taste, because
the rules above are the most opinionated part of the project.

The rules are not producing wrong numbers. A glass that really is 189 mm tall
and 64 mm across measures 180 × 63, is called a stemmed glass, and the stem is
found. What goes wrong is narrower than that: the rules produce **one** answer,
and when that answer is three millimetres out the arm has nowhere to go. The
fingers close on a 5 mm stem, meet nothing, and the glass is left standing.

So the real weakness is not that the grip point is calculated. It is that it is
calculated *once*.

### What would actually help

**Search instead of a single answer.** Each rule returns its best height. It
could return a ranked list instead — every height where a pad would fit, across
every approach direction and wrist roll, scored on wall slope, how much pad is
in contact, whether the arm can reach it and whether the wrist can still turn
it over. The arm then works down the list. This is the cheapest change on this
page and the one that would fix the most, because "no way of holding this
glass" is usually "no way of holding it *the first way tried*".

**Feel for it.** The project already says the last millimetres are felt rather
than driven, and then does not follow through: if the fingers meet nothing, the
glass is refused. They could instead open, move a few millimetres using the
wrist force and the fingertip contacts, and close again. A stem is findable by
touch in two or three tries.

**Close the loop with the camera on the way in.** The approach is open-loop —
compute a pose, move to it, hope. Watching the glass during the descent would
take out the error that is left after the measurement.

None of those three is learning. All three attack the failures that are
actually happening.

### Learning it

**Copying an expert works and is proven next door.**
[`v5-learn-pick-place`](../../v5-learn-pick-place) does exactly this: a
scripted expert does the job a few hundred times, and an ACT policy learns to
copy it, reaching 74% on blocks it never saw. Note what that project did *not*
learn — the block is still found with plain geometry from a depth camera. Only
the movement is learned. That split is the useful one, and it would carry over
here: the profile and the kind stay measured, the last part of the reach
becomes a policy, and MoveIt stops being in the way.

**Reinforcement learning is the wrong member of that family for this job.**
Three reasons, in order of how much they matter:

1. *The reward is the hard part.* "Do not chip the rim, do not crush it, and
   leave it standing if you are unsure" is a set of constraints, not a score.
   This project treats a refused glass as a success, and there is no natural
   way to reward an arm for declining.
2. *It would not touch most of the failures.* A glass that is measured wrongly
   is refused by the rules before anything moves. No policy sees that.
3. *The sample cost.* Contact-rich grasping wants a number of episodes with
   five or more zeroes on it. A run here takes about five minutes in Gazebo,
   so this would mean rebuilding the cell in a fast simulator first — most of
   a project before the first episode.

Copying an expert avoids all three, and there *is* an expert to copy: the rules
on this page, on the glasses they already handle.

**A grasp network off the shelf does not fit.** Contact-GraspNet and the like
take a point cloud and return grasps. A glass returns no point cloud — that is
the whole premise of this project, and the reason the depth picture has a hole
in it. Feeding one of these models the input that glass destroys is not a
promising start.

### What learning would cost

Two things, and neither is the training time.

The project's one rule is that no glass's size appears anywhere in it. A policy
trained on this family of glasses has their proportions in its weights. Nothing
would be written down, and the rule would still be broken — just somewhere
nobody can read it.

And a rule can say why it refused. "The rule wants the fingers 246 mm apart,
outside the 20 to 95 mm a straight glass should ever need" is a sentence that
sends you to the bug. A policy that does not grasp a glass has no reason to
offer, and a project whose refusals are results needs its refusals to be
legible.

The honest summary: search and touch first, because they are cheap and they fix
what is broken. Learn the movement after that, if the reach is still the weak
part. Learning where to hold a glass is the last thing to give away, not the
first.

→ [Step 5 — how hard to squeeze](step5-how-hard-to-squeeze.md)
