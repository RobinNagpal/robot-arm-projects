# Implementation notes

Why the project is built the way it is. The code says what happens;
[`pseudocode.md`](pseudocode.md) says in what order; this says why, and what
each number was derived from.

## The design decision the rest follows from

Every other choice in this project comes out of one sentence: **the shapes are
known, the sizes are not.**

A robot that is told "this is a wine glass, hold it 90 mm up" works on the wine
glass whoever wrote the number was holding, and fails on the next one, because
wine glasses do not share proportions. A 150 mm one is not a 190 mm one scaled
down — the stem is a different fraction of the height and the bowl a different
fraction of the width. So a project built on measurements is a project that
needs re-measuring for every set of glassware it meets, and the amount of work
to support a new customer is the amount of work it took to support the first.

The alternative is to store **rules about shapes** and apply them to a
measurement taken a second ago. "Hold the narrowest part below the widest part"
is true of every stemmed glass ever made. Applying it needs a profile, and
getting a profile needs one picture.

This is why `glasses/spec.py` opens with a sentence rather than a constant:

> This file may hold rules and limits. It may not hold the size of any glass.

Everything else in these notes is a consequence.

## A glass is a solid of revolution, and that is the whole trick

Spin any shape about a vertical axis and the outline you see is the same from
every side. So one side-on silhouette gives the diameter at every height up the
glass, and the arm needs exactly one picture rather than a circuit of the
table.

That is what makes the whole approach cheap enough to be worth it. The measured
profile is a complete description of the shape — which means it is also enough
to say what kind of glass this is, which is why there is no trained classifier
anywhere in the project.

A handle breaks the assumption, because a mug with a handle is not a solid of
revolution. That is the one case that takes a second picture, a quarter turn
round, and it is the only reason `expects_handle` exists.

## Finding a glass: the hole is the signal

A depth camera returns nothing where a glass is. Most of the light passes
through and the rest is bent by the curved wall, so the depth image has a hole
in the shape of the glass.

The obvious reaction is to treat this as the problem. It is better treated as
the measurement. A hole in the depth image, with something visible through it
in the colour image, is a glass — and that is exactly as true of a real RealSense
as it is of the simulator. A pipeline built on the hole meets the same
difficulty a real one meets, which a pipeline built on, say, the simulator's
ground-truth object poses would not.

Gazebo, though, does not have this difficulty, and that is a problem. Its
depth camera measures a glass as though it were painted wood: transparency is
a thing its renderer does in colour, not in depth, so the picture that reaches
`glass_mask()` has no hole in it and nothing is ever found.

The hole is therefore put back where it would have been lost, in the sensor.
A segmentation camera sits beside the depth one and says which pixels are
glass, and `WristCamera` blanks the depth at those pixels before handing the
frame on. In a real cell that answer comes from a trained model; here it comes
from the simulator, which knows. Either way it stops at the camera: what
leaves is an ordinary depth picture with holes in it, and everything
downstream is told nothing it could not have measured.

Doing it the other way round — letting the perception read the simulator's
labels, or read the glass's depth because Gazebo happens to offer it — would
have been fewer moving parts and worth nothing, because the pipeline would
then depend on something no real cell has.

`glass_mask()` is therefore three lines, and the comment above it is longer
than the code, because the code is not the interesting part.

Two things the mask is not:

- **It is not a segmentation model.** In a real cell it would be, and
  `glass_mask()` is where that model would be called. The interface would not
  change.
- **It is not reliable in colour alone.** A hole over the empty background is
  the far wall, not a glass, which is why the lit test is there.

## Measuring: pixels to millimetres without a depth reading

The camera cannot range on the glass. But it does not need to, because the
glass stands on the table, and where the table is has been known since startup.

So the arm puts the camera a fixed distance to one side of the glass
(`MEASURE_STANDOFF`, 300 mm) and that distance is what converts an angle into a
length. A pixel subtends `1/fx` radians; at 300 mm it covers `300/fx`
millimetres. That is the entire conversion.

Three details in `perception.py` matter more than they look:

**Width is edge to edge, not a pixel count.** A transparent object segments
with holes in the middle — the model sees the table through it — so counting
glass pixels in a row undercounts badly. The distance from the leftmost glass
pixel to the rightmost does not care about the holes.

**The raggedness check runs on the raw widths, not the smoothed ones.** This
was a bug for a while. Smoothing is a five-row median, which is enough to make
any mask look clean, so a check after it never fires. The check asks whether
the mask was worth trusting; the smoothed profile is what gets measured.
`MAX_RAGGEDNESS` is 0.02 — two per cent of the glass's own width, averaged over
neighbouring rows.

**A half pixel matters at the edges.** A pixel's world position is its centre,
so the outside of the leftmost pixel is half a pixel further out. Without that
correction every width comes out one pixel short, which at 300 mm is about half
a millimetre — small, but it is a bias, not noise, and it is in the number the
fingers are set to.

## Classifying from the profile

`classify()` asks two questions in an order that matters.

**Is there a waist?** A waist is a local narrowing with wider glass above and
below, which is what a stem is. Stemmed glasses also have sloping bowls, so
asking about slope first would call every wine glass tapered.

**If there is, how far up is it?** `SHORT_STEM_FRACTION` is 0.17. This is the
one place the classifier has to separate two things the silhouette barely
distinguishes, and the number came from looking at the two populations rather
than from a principle: a wine glass's waist sits at 20–28 per cent of its
height, an Irish coffee glass's at about 13. Putting the threshold at 17 leaves
room on both sides.

**If there is no waist, does the wall lean?** `TAPER_THRESHOLD_DEG` is 6,
measured over the lower half. Below six degrees the wall is upright enough for
flat pads to press on without sliding, which is the only difference that
matters to the gripper — so the threshold is a statement about the gripper, not
about glassware.

`classify()` returning `None` is a real answer, not an error. It means a shape
no rule describes, and the right response is to leave the glass standing.
Forcing it into the nearest kind is how a project quietly starts dropping
things.

## Why six degrees, and why it is a pad property

`VERTICAL_TOLERANCE` in `profile.py` is 6 degrees, and it decides what counts
as an upright band of wall.

It started at 2 degrees, which is the number you pick if you are thinking about
geometry. It refused every short mould-tapered tumbler in the test family — a
wall that leans 3 degrees is not vertical, and 2 degrees says so.

Six comes from the pad instead. A silicone pad 12 mm tall and 4 mm thick
conforms by about 1.2 mm across its height before the contact patch starts to
run out, and `atan(1.2/12)` is 5.7 degrees. So the tolerance is a fact about
the gripper, and if the pads were harder it would go down.

This is the general shape of every threshold in the project worth trusting:
derived from a piece of hardware, not chosen because it looked about right.

## The grip: three rules, and four ways to reject one

The rules in `rules.py` are short because the features in `profile.py` do the
work.

| Rule | Used by | What it finds |
| --- | --- | --- |
| `lowest_vertical_section` | straight glass | the lowest band of wall within `VERTICAL_TOLERANCE` of upright, at least `min_band_height_m` tall |
| `narrowest_below_widest` | stemmed, short-stemmed | the waist below the widest point |
| `flattest_in_band` | tapered glass | a cone has no upright wall anywhere, so take the least-sloping band in the search window |

All three search low down, in a band given as fractions of the glass's own
height. Low for one reason: after the turn, the end that was low is the end
that is high, so holding low means the fingers finish above the rack rather
than among the pegs.

The opening is then read off the profile at the chosen height. It is a
measurement, not a lookup.

`_check()` then rejects the answer four ways:

- the opening is outside what this kind should ever need — a "stem" 60 mm wide
  means the rule found something that is not a stem;
- the opening is wider than the gripper opens at all;
- the band is shorter than the pads need to sit on;
- the grip is more than halfway up the glass, which after the turn would put
  the fingers down among the rack pegs.

The last one is the "hold it low" principle, enforced rather than assumed. A
rejection raises `NoGrip` with the reason in it, and that reason ends up in the
run report next to the glass that was left standing.

## Force: why one stage is not enough

Grip force has to beat gravity through friction:

    force >= mass * g / (friction * number of pads)

With `GRIP_FACTOR` 0.6 for silicone on glass and two pads, and `SAFETY_FACTOR`
2 on top, a 300 g glass wants about 5 N.

The problem is `mass`. Wall thickness is invisible from outside, and it is what
decides the weight: a thin-walled 190 mm flute weighs less than a squat
tumbler. So the estimate from the profile — shell volume times `GLASS_DENSITY`
2500 — is wrong by roughly a third in either direction.

A third is fine for a starting squeeze and not fine for the real one, so the
sequence is:

1. `CONTACT_FORCE_N` (1 N) to take up the slack. The width at contact is the
   true width, measured by touch. If it disagrees with the camera by more than
   4 mm, the grasp is not where it was supposed to be.
2. `starting_force()` from the estimate.
3. Lift `WEIGH_LIFT` (10 mm) and read the wrist sensor. Now the mass is known.
4. `force_for_measured_mass()`. If it is more than the estimate, **set the
   glass down first** and re-grip. Increasing the squeeze on a held glass
   arrives as a step change, and a step change is what cracks a thin wall.

`force_cap_n` per kind is what lets the arm refuse. A glass that turns out
heavier than its walls can take raises `TooHeavyToHold`, and the run says so
instead of squeezing until something gives.

The ten-millimetre lift is deliberately small. It is the last moment a mistake
is free — the glass is off the table and nothing has been turned over yet — and
setting it back down from 10 mm costs nothing.

## Slip is measured, not assumed

`is_slipping()` compares the finger gap now with the gap when the glass was
gripped. Fingers that have crept closed mean the glass is sliding down through
the pads.

It is checked during a 20 degree lean, and the angle is the point. Twenty
degrees puts some of the weight on the pads sideways, which is what makes a
marginal grip fail, and it is a lean a glass can be brought back from. A
hundred and eighty degrees is not.

## Turning over: about the grip, not about the wrist

Inverting a glass is a rotation, and what it rotates about decides whether it
is safe.

Rotating about the tool origin swings the glass through an arc as wide as the
fingers are long — 170 mm here — which sweeps it across whatever is next to it.
Rotating about the grip point turns it on the spot, because the grip point is
the one place on the glass that is not moving relative to the fingers.

So `rotate_tool()` takes the point to turn about, and the task passes the grip
point every time.

## The wrist limit, and why it is checked before the grasp

The last wrist joint stops a little short of a full turn. Whether the arm can
invert a glass therefore depends on which way round it took hold of it.

A parallel gripper is symmetric, so there are always two ways round that grip
the same glass identically. They are not identical to the arm. `can_rotate_tool()`
plans the turn without executing it, and the task calls it while hovering, before
the fingers close, trying the second way round if the first cannot be turned.

Getting this wrong is the single most expensive mistake available in this task,
because it is discovered with the glass already in the gripper and there is
nothing to do but put it back.

## Placing: feel for the rack

Both the glass's height and the height it is held at were measured, so both
carry error, and they add. Driving to a calculated height is therefore how a
rim gets chipped.

`descend_until_contact()` goes down in 2 mm steps until the pad contact sensors
report something, up to `DESCENT_LIMIT` (60 mm). Coming down 60 mm without
touching anything is itself an answer: the glass is not where it was thought to
be.

Then `load_transferred()` checks the wrist sensor is back to reading the
gripper alone (`GRIPPER_WEIGHT_N`, 9.5 N, plus a margin) before the fingers
open. A glass caught on a peg is still hanging from the gripper, and opening
the fingers on it drops it.

## The tilt budget

A glass going into a slot has `(spacing - width) / 2` of room on each side, and
it pivots about its rim as it goes down, so the angle that uses up that room is

    atan(clearance / height)

An 80 mm glass in 100 mm slots has 10 mm a side: 6.3 degrees at 90 mm tall, 3.3
at 175 mm, 1.6 if it is also 90 mm wide. `ARM_TILT_ACCURACY_DEG` is 3, so the
third of those is refused a slot of its own and the neighbour is left empty,
which doubles the spacing and takes it to 17.4 degrees.

What makes this worth a function rather than a rule of thumb is that it depends
on the *measured* width and height, so it is decided per glass, on the day.

## What the tests are actually for

141 tests, no simulator, under a second. They exist to answer one question:
**does this rule work on glasses nobody had in mind when it was written?**

That is why `family(kind, count, seed)` draws forty glasses spread across the
plausible range of proportions, and why the tests run over all forty. Every
significant bug in this project was found by a family test and would have been
missed by a single example:

- `waist_at()` returned the *first* index of a plateau, which on a glass with a
  flared foot is the foot rather than the stem. It now returns the middle of
  the longest narrowest run.
- `foot_diameter` was drawn independently of `bowl_diameter`, so occasionally
  the foot was the widest part of the glass, which left `waist_at()` searching
  an empty slice. Feet are now a fraction of the bowl.
- `VERTICAL_TOLERANCE` at 2 degrees refused every short tumbler, as above.
- `SHORT_STEM_FRACTION` at 0.30 called every wine glass short-stemmed.

There is one test premise worth mentioning because it was wrong and the fix is
instructive. `test_every_drawn_glass_is_classified_as_its_own_kind` demanded
that a glass be labelled with the kind it was generated as. That is the wrong
requirement: a shallow cone drawn as a tapered glass is legitimately grippable
by the straight-glass rule, and labelling it straight is not a mistake. The
test now asks the question that matters — **does every glass get a kind whose
rule can actually hold it** — and is both easier to pass and harder to cheat.

## Licences

Everything here is permissively licensed and can be used commercially: ROS 2
(Apache-2.0), Gazebo (Apache-2.0), MoveIt 2 (BSD-3), ros2_control (Apache-2.0),
OpenCV (Apache-2.0), NumPy (BSD-3), trimesh (MIT).

One warning for anyone extending the perception step. **Ultralytics YOLO is
AGPL-3.0.** It is the first thing most people reach for, and the AGPL's network
clause makes it unusable in a commercial product without buying a licence. If
you need a segmentation model here, torchvision's Mask R-CNN (BSD-3),
Detectron2 (Apache-2.0) and mmdetection (Apache-2.0) do the same job under
licences that will not surprise you.

## What simulation will not tell you

Worth being honest about, because the whole project runs in a simulator.

- **Real glass segmentation is harder than a depth hole.** The hole is the
  right signal, but reflections, specular highlights and one glass seen through
  another are not modelled here.
- **Contact with a curved, slippery, brittle surface is the weakest part of any
  physics engine.** The friction and softness numbers in
  `gripper.urdf.xacro` are plausible, not measured.
- **Nothing here can tell you what force actually breaks a wine glass stem.**
  The force caps are conservative guesses. On real hardware they would be the
  first thing to calibrate, and the second would be the margin in
  `load_transferred()`.

What simulation does tell you, and what this project is really for, is whether
the *reasoning* holds: whether a rule stated as a sentence about a shape
survives contact with forty glasses that nobody chose to suit it.
