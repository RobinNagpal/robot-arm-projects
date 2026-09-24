# Implementation notes

Why the project is built the way it is, and what each number was derived from.

It sits behind the other documents rather than beside them.
[`problem-statement.md`](problem-statement.md) says what the task is and why
it is worth doing; [`docs/`](docs/) walks through how a run does it, stage by
stage; [`pseudocode.md`](pseudocode.md) says which file and function each
stage lives in. This one is for the questions those raise and do not answer —
why six degrees rather than two, why the force has two stages, why a rule and
not a table.

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

## Finding a glass: it stands above the table

A glass here is an ordinary opaque object. That is an assumption and not a
fact about glassware — it is set out in
[`problem-statement.md`](problem-statement.md) with what it buys and what it
costs — and everything in this section follows from it.

Because the camera can see a glass, finding one needs no cleverness at all.
A depth picture gives a distance for every pixel; the camera's own pose turns
any pixel and its distance into a point in the room; the table top is a known
height; so a glass is a run of pixels whose points sit above it.

Two bounds keep the rest of the cell out of the answer, and it matters that
neither is a fact about any glass. Nothing taller than the tallest glass the
cell handles counts, which removes the arm's own gripper from its own
pictures. And the side-on view keeps only what lies at roughly the distance it
deliberately stood off at, which removes the rack and the glasses behind the
one being measured. Both are things the arm knows because it chose them.

### What this replaced, and why it is worth knowing

For most of this project's life the glasses were treated as really
see-through, and the design was built on the opposite idea: that the *absence*
of a reading is the reading. A real depth camera gets nothing back through
glass — most of the light passes through and the rest is bent away by the
curved wall — so on real glassware the depth picture arrives with a
glass-shaped gap in it, a patch of pixels with no distance where every other
object would have had one. Treating that gap as the measurement rather than
the obstacle is a genuinely good idea, and it is exactly as true of a real
RealSense as of a simulator.

It failed for a reason that has nothing to do with whether it is a good idea.
Gazebo has no such difficulty: its depth camera measures a glass as though it
were painted wood, because transparency is something its renderer applies to
colour and not to depth. So the gap never appeared, the mask came back empty,
and nothing was ever found. The repair at the time was to manufacture the gap
— a second camera reported which pixels were glass, and the wrist camera
blanked the depth at those pixels before handing the picture on.

That worked, and it was a lot of machinery to make a simulator lie in a
specific way so that the code downstream could believe it. When the glasses
became opaque by assumption, all of it came out: the second camera, the label
on each glass model, the topic that carried it, and the blanking. What is
left is shorter, and it fails more honestly, because a pixel it cannot place
it simply drops rather than arguing about what the colour picture shows there.

The cost is real and should not be hidden. On real glassware this method does
not work at all, and the one that does is the one that was removed. The
comparison in
[`docs/step1-approaches.md`](docs/step1-approaches.md) sets
out what to use instead, and the interface is arranged so that it is one
function.

## Measuring: pixels to millimetres without a depth reading

The camera cannot range on the glass. But it does not need to, because the
glass stands on the table, and where the table is has been known since startup.

So the arm puts the camera a known distance to one side of the glass and that
distance is what converts an angle into a length. A pixel subtends `1/fx`
radians; at 380 mm it covers `380/fx` millimetres. That is the entire
conversion.

How far back to stand is worked out per cell rather than written down, because
what has to fit in the frame — the foot of the glass at the bottom, the rim of
the tallest glass the cell handles at the top — is as much a question about the
lens as about the glass. `MEASURE_STANDOFF` is only the floor on it. It came to
380 mm here, and it used to be a flat 300, which put the foot of the glass in
the last few pixels of the picture and cost more than it saved: see
[`docs/step2-measuring-one.md`](docs/step2-measuring-one.md).

Three details in `perception.py` matter more than they look:

**Width is edge to edge, not a pixel count.** Counting glass pixels in a row
is fragile: a mask can come back with gaps in the middle of an object — a
highlight, a patch the sensor missed, or, on a real see-through glass, the
table showing through — and every one of those makes a count too small. The
distance from the leftmost glass pixel in a row to the rightmost does not care
what happened between them.

**The raggedness check runs on the raw widths, not the smoothed ones.** This
was a bug for a while. Smoothing is a five-row median, which is enough to make
any mask look clean, so a check after it never fires. The check asks whether
the mask was worth trusting; the smoothed profile is what gets measured.
`MAX_RAGGEDNESS` is 0.02 — two per cent of the glass's own width, averaged over
neighbouring rows — or two pixels, whichever is the more forgiving. The second
half of that is not a hedge: a fraction of the glass's own width assumes a
glass a hundred-odd pixels across, and on one forty pixels across the
one-pixel wander any mask edge has is already two and a half per cent, so the
fraction alone throws out clean pictures of narrow glasses.

**A half pixel matters at the edges.** A pixel's world position is its centre,
so the outside of the leftmost pixel is half a pixel further out. Without that
correction every width comes out one pixel short, which at this standoff is
about seven tenths of a millimetre — small, but it is a bias, not noise, and it is in the number the
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
measured from 5% to 45% of the glass's height. Below six degrees the wall is upright enough for
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
| `nearest_centre_of_mass` | straight glass | the band of wall within `VERTICAL_TOLERANCE` of upright, at least `min_band_height_m` tall, closest to the estimated centre of mass |
| `lowest_vertical_section` | nothing now | the lowest band of wall within `VERTICAL_TOLERANCE` of upright, at least `min_band_height_m` tall |
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
report something, up to `DESCENT_LIMIT` (60 mm) past the top of the peg. It
starts with the rim above the peg, because the move over the slot is sideways.
Coming down that far without touching anything is itself an answer: the glass is not where it was thought to
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

## Where the faults were, and where they appeared

Getting this to run at all turned up a long run of faults, and they are
written up at the step each one belongs to in [`docs/`](docs/). What is worth
saying here is the pattern they share, because it shaped how the project is
debugged now.

Nearly every one of them announced itself a long way from where it lived. A
sensor missing from the model arrived as an arm that could not plan a path. A
texture drawn at the wrong angle arrived as a glass lowered onto bare table. A
force read along an axis that happens to be level arrived as a glass sliding
out of the fingers during a lean. In every case the log said what failed, and
what failed was almost never what was wrong — so time went on the wrong thing
until somebody looked at what the arm could actually see at the time.

Four of them sat below everything else and are worth recording here rather
than in a step, because they are about the model and the plumbing rather than
about glasses. The wrist force sensor is mounted on the fixed joint where the
gripper bolts on, and the tool that turns the robot description into something
the simulator loads folds fixed joints into the part above them, taking the
sensor with them; the model was right, the simulator loaded it without
complaint, and the sensor was simply not there. Once it existed nothing served
it, because the world loaded the system that draws camera pictures and force
sensors are handled by a different one that was never listed. Once it was
served the readings went nowhere useful, because the part that publishes them
has no setting for which name to publish under, so the name written in the
configuration was read by nobody while the arm listened on it. And the gripper
was in collision with itself before it had moved, because each pad is bolted
flat to its fingertip and the planner had never been told that this is normal.

Two habits came out of all this and have paid for themselves. Moves are
planned up to three times before being called impossible, because the planner
grows its tree from samples that fall at random and a move it fails once it
often solves next time — while a pose that genuinely cannot be reached still
fails every attempt just as fast. And every run now writes an account of
itself into `runs/`, as a markdown file with the pictures it took beside the
sentences, flushed as it happens so that a run which dies half way still
leaves everything up to the moment it died. The one thing in that file the arm
does not get to have is what was actually put on the table, written by the
world builder before the arm sees any of it, so that what the arm worked out
can be held against what was really there. Most of the later faults were found
by reading one of those files, several of them in a single pass.

## What simulation will not tell you

Worth being honest about, because the whole project runs in a simulator.

- **Real glass is not opaque.** This project assumes it is, which is the
  single largest difference between the cell here and a kitchen. On real
  glassware the depth camera returns nothing where the glass is, and finding
  one means a trained segmentation model or one of the other methods compared
  in step 1 — none of which are as simple as the height test used here.
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
