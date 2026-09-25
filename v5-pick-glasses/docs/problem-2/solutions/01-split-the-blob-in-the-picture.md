# Solution 1 — split the blob in the picture

*Programmed. Keep the mask the detector already builds. When one patch of
pixels is too wide to be a single glass, cut it in two, using nothing but the
picture.*

## In one paragraph

When two glasses line up with the camera, the near one stands in front of the
far one and the flood fill that works perfectly for one glass returns a single
patch. This solution splits that patch without depth, a model or a second
photograph. It works because the camera looks level from 120 mm above the table
top, so the table recedes to a horizon and **a glass standing further away has
its base drawn higher up the picture**. Find the level stretches along the
underside of the patch: one glass makes one, two glasses at different distances
make two at different heights, and the lower stretch is the nearer glass. It
costs a fraction of a millisecond, it never splits a single glass, and it says
nothing at all when the far glass's base is hidden.

## The problem this solves

Problem 1 turns each photograph into a mask — every pixel marked glass or not
glass — and then groups the marked pixels by whether they touch. That grouping
is **connected components**, and it answers exactly one question: *are these
pixels joined to each other?*

For one glass on a bare table that question is the right one. For several it
stops being enough, because two glasses that are nowhere near each other on the
table can still be joined in a photograph.

But *where* that happens is worth getting right, because the obvious answer is
wrong.

![Where the overlap actually is](../../../images/problem-2/01-where-the-overlap-is.png)

**It does not happen in the survey.** The survey looks straight down from
450 mm. Two solid glasses cannot interpenetrate on the table, and problem 2
guarantees they stand at least 150 mm apart centre to centre, so their
footprints are never closer than about 45 mm. Looking straight down at them,
their silhouettes do not touch either. Over 4320 legal arrangements — four
kinds, six sizes each, every separation from 150 to 300 mm, every angle — with
both glasses wholly inside one 320×240 frame, **not one produced a merged
patch**.

The reason is that the frame shrinks as you go up.

![Why the survey cannot produce the case](../../../images/problem-2/01-the-survey-cannot-see-it.png)

One survey picture holds 520 mm of table, but only 358 mm at the height of this
kind's rim, because the rim is 140 mm nearer the lens than the table is. Two
glasses far enough apart to be legal are therefore either both inside the frame
and comfortably separate, or one of them is falling off the edge — and a glass
half out of the picture is a different problem, which the survey already solves
by overlapping its stations so that anything cut off at one is well inside
another.

**It happens in the level view.** When the arm stands the camera 380 mm from a
glass and looks level — the geometry problem 1's step 2 uses to measure a
profile, and the one [solution 3](03-move-the-camera.md) sends the camera to —
a glass 180 mm further back is genuinely behind the near one. There, merging is
the normal case rather than a rarity: of 168 in-line pairs across the four
kinds, 132 came back as one patch.

So this document is about the level view, and only the level view. That is a
correction to an earlier version of this page, which drew two footprint circles
overlapping — a picture of something that cannot happen, since two solid
glasses cannot occupy the same piece of table.

### A glass is a circle in one place only

Worth fixing now, because it is the assumption that produced the wrong picture.

![A standing glass is not a circle](../../../images/problem-2/01-a-glass-is-not-a-circle.png)

A glass is a circle in its **footprint**. No camera in this cell sees the
footprint straight on. From above, the rim is wider than the base *and* 140 mm
nearer the lens, so it images larger and lands further out: the silhouette is a
teardrop leaning away from the point under the camera, and a 42 mm footprint
comes back 156 mm wide. From the side, the silhouette is the glass's profile —
a tall tapered shape. Neither is a circle of the footprint's size, and any
method that assumes one is solving a different problem.

## The idea, in plain words

Stand a glass on a table and photograph it from a camera that is above the
table but pointing level. The table stretches away from you to a horizon. A
glass close to you has its base low in the picture; a glass further away has
its base higher up, nearer the horizon. This is the same effect that puts the
far kerb higher in the frame than the near one in a photograph of a street.

![Further away means higher up](../../../images/problem-2/01-bases-sit-higher.png)

Now put numbers on it. The camera sits 120 mm above the table. A glass 380 mm
away has its base **87 pixels** below the horizon; one 560 mm away has its base
**59 pixels** below it. The difference is **28 pixels** — a large, obvious gap.

And notice the second line on that plot. The two glasses' *rims* differ by only
5 pixels, because a rim sits nearly at the camera's own height and therefore
nearly on the horizon. So the top of the blob says almost nothing about
distance, and the bottom of it says a great deal. All the information is in the
underside.

That is the whole method:

> **Look along the underside of the patch. Find the stretches that are level —
> the places where something is standing on the table. One glass makes one. Two
> glasses at different distances make two, at different heights.**

## Where it comes from

Splitting a binary patch into objects is old ground, and the standard tool is
**watershed on the distance transform** — treat the patch as a landscape whose
depth is each pixel's distance from the outside, find the deepest points, and
flood outwards from each until the floods collide. It is in every image
processing textbook, it is one call in OpenCV, and for touching cells in a
microscope image or coins on a scanner it is the right answer.

It is not the right answer here, and the reason is structural rather than a
matter of tuning.

![Why the distance transform cannot help](../../../images/problem-2/01-the-distance-transform-fails.png)

The distance transform asks *how far is this pixel from the outside?* In a
squat, round object the deepest point is a single peak at the middle. Two such
objects give two peaks, and the wall between the floods lands neatly at the
waist.

A standing glass seen from the side is about four times taller than it is wide.
Its distance from the outside is capped by its half-width, and it is capped by
the same half-width all the way up. The deepest set is not a point but a **line
running up the middle** — a ridge. Two overlapping ridges merge into one ridge,
one marker survives the threshold, and there is nothing to flood from.

Measured across the four kinds: of 122 merged pairs, watershed split **four**.
Three per cent. No choice of threshold rescues it, because the failure is that
a tall thin shape has no peak to put a marker on.

The method below replaces it, and it is not novel either. It is the
**ground-plane constraint**: if a camera's height above a flat support surface
is known, the image row at which an object meets that surface gives the
object's distance directly, since a camera at height *h* looking level puts an
object at distance *Z* exactly `f·h / Z` pixels below the horizon. The contact
point is the *foot point* in pedestrian detection, and mapping the image onto
the plane this way is **inverse perspective mapping** (Mallot et al.,
*Biological Cybernetics*, 1991). The canonical statement of why it is worth so
much is Hoiem, Efros and Hebert's
[Putting Objects in Perspective](https://doi.org/10.1007/s11263-008-0137-5)
(CVPR 2006, extended in *IJCV* 2008): a ground plane plus a camera height turns
a picture into a measurement.

What is slightly unusual here is the *use*. That constraint is normally spent
on estimating distance or pruning detections by scale. Using it to **separate**
two objects — two contact rows in one patch means two objects — is the same
arithmetic put to a different job.

The cell has an unusually clean version of it: a flat, level table at a known
height, rigid with the arm, and objects that all stand on it.

> Robotics-basics has nothing on this. Its perception documents cover sensors,
> programmed methods, and models that find and measure, but not the
> ground-plane family — which is a real gap, because it is the cheapest
> monocular depth cue there is and it needs no model at all.

## How it works, step by step

### 1. Notice the patch is too wide

The trigger is the one number this method takes from outside the picture: the
widest the known kind can be. Problem 2 says every glass on the table is one
known kind, and that kind's specification holds its range.

![The blob, and what flags it](../../../images/problem-2/01-the-blob.png)

At 380 mm, one pixel covers 1.37 mm, so this kind's 90 mm rim occupies 66
pixels. Add two pixels, because a drawn edge rounds outward and a rasterised
silhouette is a pixel wider than the arithmetic says on each side. Anything up
to 68 pixels is left alone; the pair measures 86 and is flagged.

That margin is not a fudge to be tuned away. It is the difference between a
mathematical edge and a pixel grid, it is two pixels wide, and leaving it out
makes the method fire on every single glass it sees.

### 2. Take the underside

For every lit column of the patch, find the lowest lit row. That sequence of
rows is the underside of the blob.

### 3. Find the level stretches

Walk along the underside and collect maximal runs of columns whose row stays
constant to within a pixel. Keep runs at least five columns long, which throws
away the near-vertical sides where the underside is not a contact line at all
but the wall of the glass.

Each surviving run is a place where something stands on the table.

![The test itself](../../../images/problem-2/01-contact-runs.png)

### 4. Two stretches, far enough apart, means two glasses

If two runs sit at least eight pixels apart in row, the patch holds two glasses.
The cut goes between them, and **which is nearer comes free**: the lower stretch
is the nearer glass, because nearer bases sit lower.

Eight pixels is the one threshold in the method, and it is derivable rather
than chosen. At this standoff, 28 pixels separates glasses 180 mm apart in
depth. The smallest depth difference worth calling two glasses is the 150 mm
that problem 2 guarantees between centres, which at these distances is about
22 pixels. Eight is comfortably below that and comfortably above the pixel or
two of noise in a rasterised edge.

### Why it counts level stretches and not steps

This is the part that took a wrong turn first, and the failure is instructive.

The obvious test is *is there a step in the underside?* It catches 93 per cent
of merged pairs, which looks excellent until you run it on a single glass.

![The control](../../../images/problem-2/01-the-control.png)

A stemmed glass's bowl hangs out over its foot. Along its underside, the
columns under the foot report the foot's base; the columns beyond the foot but
still under the bowl report the bowl's underside, which is much higher. That is
a step of **96 pixels** in a single, solitary glass. Counting steps splits 69
per cent of single glasses — it invents a second glass that is not there.

Counting *level stretches* is immune to it, because however odd a glass's shape,
it rests on the table in exactly one place, so it has exactly one level stretch.
Across 120 single glasses of all four kinds at four distances, the test split
**none of them**.

That asymmetry is deliberate. A splitter that fires on a single glass turns one
correct answer into two wrong ones, and two wrong positions are worse for
everything downstream than one patch honestly reported as unresolved.

### What about GrabCut?

GrabCut refines an outline. Given a rough box round an object it separates
foreground from background by modelling their colours and smoothing the result,
and it is genuinely useful where a threshold leaves a ragged edge — the last
pixel or two where a glass meets the table.

It never decides how many objects there are. Given a box round two merged
glasses it returns a tidier outline of the same merged pair. It is worth having
downstream of this method and it is not a substitute for it.

## A worked example

Two glasses of a kind whose rim is 90 mm and whose base is 43 mm, standing
140 mm tall. The camera is level, 120 mm above the table. Glass A is 380 mm
away; glass B is 180 mm further back and 60 mm to one side.

**What comes back.** One patch, 86 pixels wide. At 1.37 mm a pixel that is
118 mm, against the 68-pixel limit the kind allows. Flagged.

**The underside.** 86 columns of lowest-lit rows. Two level runs survive:

| | columns | row | what it is |
|---|---|---|---|
| lower | 18 – 49 | 148 | glass A's base, 87 px below the horizon |
| higher | 55 – 74 | 119 | glass B's base, 59 px below the horizon |

**29 pixels apart** — the arithmetic above predicted 28, and the extra pixel is
the rasterised edge. Comfortably over the eight-pixel threshold.

**The answer.** Two glasses. The cut goes at column 52. The lower run is the
nearer one, so the left-hand piece is glass A at roughly 380 mm and the
right-hand piece is glass B, further off. Two masks, and an ordering, from one
photograph and about a third of a millisecond.

**What it has not produced.** Any position in millimetres. Both pieces are still
silhouettes, and a silhouette does not sit where its glass does.

## The feedback loop

It has none, and that is worth saying plainly rather than dressing up.

This method looks at one picture and returns an answer or an abstention. It
cannot ask for another photograph, it cannot change where the camera stands,
and it does not accumulate anything between frames.

What it does produce is a **clean handover**. Three outcomes, and each names its
own next step:

- **two level stretches, far enough apart** — two glasses, with an ordering;
- **one level stretch, patch within the kind's width** — one glass, untouched;
- **one level stretch, patch too wide** — something is wrong and this picture
  cannot say what. Hand it to [move the camera](03-move-the-camera.md).

The third outcome is the useful one, because it is specific. It does not say
"unsure"; it says *there is more here than one glass and I cannot see the second
one's base from where I am standing* — which tells the next solution what the
new viewpoint has to achieve.

## What it needs

Nothing that is not already installed and nothing that is not already running.

- The mask problem 1's detector already builds.
- One number from outside the picture: the widest the kind can be, which its
  specification holds.
- The distance the camera stood off, to turn that number into pixels — which
  the arm knows, because it chose it.
- NumPy. Not even OpenCV, strictly: the underside is one `argmax` per column and
  the runs are a single pass over the result.

About thirty lines. No model, no weights file, no graphics card, no training
set, no licence question, and no new dependency — which, given that everything
from [solution 4](04-learned-doubt-steers-the-next-picture.md) onward starts by
adding PyTorch or scikit-learn, is not nothing.

## What it is good at

**It is nearly free.** A third of a millisecond on a 320×240 patch, against
seconds for the arm to move anywhere.

**It never invents a glass.** Zero false splits across 120 single glasses of all
four kinds. The method is built round that asymmetry.

**It says which is nearer, for free.** Not just two masks but their ordering,
which is a genuine extra: the near one is the one worth measuring first, because
the far one may need moving anyway.

**Every step prints.** Two run positions and a row difference. A wrong answer is
a number you can read, not an activation you cannot.

**It needs no depth.** Everything here is the mask. On real glassware the depth
camera returns a glass-shaped hole and every method that clusters points in the
room loses its input; this one carries on, given a mask from colour.

## What it is bad at

**It cannot see a base that is hidden.** When the far glass stands close to
directly behind the near one, its base never reaches the camera, and there is
nothing on the underside to find.

![Where it works and where it cannot](../../../images/problem-2/01-where-it-works.png)

Of 122 merged pairs it split 76. Broken out by how far the far glass stood to
one side, the pattern is sharp rather than gradual: **from 40 mm of lateral
offset onward it split every merged pair, 74 of 74.** Below that it split two of
48. There is no middle ground to tune into, because the question is simply
whether any of the far glass's base is exposed.

**It gives no position.** Both pieces are silhouettes laid on the table plane,
carrying the bias problem 1 already measured — a glass 157 mm away reported at
244 mm. Splitting a blob gives two wrong positions where there was one.

![What a split does not buy](../../../images/problem-2/01-what-it-does-not-buy.png)

**It assumes the table is flat, level and at a known height.** All three are
true in this cell and all three are assumptions. A table 5 mm out of level
across the zone moves a contact row by about a pixel at this standoff, which is
tolerable; a sloping table would not be.

**It only works from a level camera.** From the survey view there is no horizon
in the frame and no contact-row difference to read, which is consistent, because
from the survey view there is nothing to split.

## How it fails

**Silently, when the far base is hidden.** The patch comes back as one glass,
too wide, and the width check is what catches it. This is the failure the method
is arranged around: it fails to a flag, not to a wrong answer.

**A glass at the edge of the frame,** cut off by the picture's boundary, has an
underside that ends at the edge rather than at its own base. The run is still
level and still at the right row, so the test survives it — but the *width*
check does not, because a cut-off silhouette is narrower than the glass. A patch
touching the frame edge should be reported as cut off rather than measured.

**Something else standing in the patch.** The method finds level stretches, not
glasses. Anything else resting on the table inside the same patch — the rack's
foot, a dropped glass — produces a level stretch and is counted. The circle fit
in [solution 2](02-cluster-on-the-table.md) is the guard, and it is one of the
reasons this is a first pass rather than an answer.

**Three glasses in a line** produce three runs, which the method handles, but
the middle one is the most likely to have its base hidden by the near one. The
honest output is two glasses and a too-wide flag on the remainder.

## When it would be the right choice

**As the first thing tried in the level view.** It is free, it runs on data that
already exists, and it resolves the majority of in-line pairs. There is no
argument for not running it before anything more expensive.

**When there is no depth.** On real glassware — the direction this project would
eventually go — the depth image has a glass-shaped hole where the glass is, and
[solution 2](02-cluster-on-the-table.md) has nothing to cluster. A mask from
colour plus this test is then a working answer rather than a worse one.

**As a second opinion.** It is wrong in *different circumstances* from the
geometric methods: it fails when a base is hidden, clustering fails when points
are missing, and those are not the same arrangements. Two independent methods
agreeing is worth more than either alone.

**It is not the thing to lead with in the survey**, because in the survey the
case it solves does not arise. That is not a weakness of the method. It is the
reason problem 2 is a viewpoint problem before it is a segmentation problem.

## The general methods behind this

Nothing in this solution was invented for glassware. It is four standard ideas,
three of which are in every image-processing textbook and one of which is the
oldest trick in monocular vision. Each is worth knowing on its own account.

### Connected-component labelling — grouping pixels that touch

Sweep a binary image, give every set of mutually touching marked pixels one
label. It answers *are these pixels joined?* and nothing else: it has no notion
of size, shape or how many objects a blob ought to contain. It is the step this
solution exists to repair.

- **Mostly used for** counting and isolating well-separated blobs — cells on a
  slide, characters on a scanned page, blobs after background subtraction in a
  fixed camera.
- **Rarely right for** anything where objects touch or overlap in the image.
  There, it silently merges, and merging is the one error it cannot report.
- **More:** [connected-component labelling](https://en.wikipedia.org/wiki/Connected-component_labeling);
  `cv2.connectedComponentsWithStats` in OpenCV.

### The ground-plane constraint — where an object meets the floor is how far away it is

If the camera's height above a flat surface is known, the image row at which an
object touches that surface gives its distance: a camera at height *h* looking
level puts an object at distance *Z* exactly `f·h / Z` pixels below the horizon.
One row, one division, and a metric depth. The contact point is called the
*foot point*; mapping a whole image onto the plane this way is *inverse
perspective mapping*.

- **Mostly used for** driving and surveillance, where everything of interest
  stands on a road or a floor: estimating how far away a pedestrian or car is
  from a single camera, rejecting detections whose size and contact row
  disagree, and building bird's-eye-view images for lane following.
- **Rarely right for** objects that are not resting on the plane — anything
  held, stacked, flying, or on a shelf — and for scenes where the plane's pose
  is unknown or not flat. It also degrades badly if the contact point is
  occluded, which is exactly this solution's failure case.
- **More:** Hoiem, Efros and Hebert,
  [Putting Objects in Perspective](https://doi.org/10.1007/s11263-008-0137-5)
  (CVPR 2006, extended in *IJCV* 2008);
  [3D projection](https://en.wikipedia.org/wiki/3D_projection) for the
  underlying arithmetic.

### Watershed on the distance transform — the method this one replaces

Treat a blob as a landscape whose height is each pixel's distance from the
outside, flood from the deepest points, and build a wall where two floods meet.
The [distance transform](https://en.wikipedia.org/wiki/Distance_transform)
supplies the landscape; the
[watershed](https://en.wikipedia.org/wiki/Watershed_%28image_processing%29)
(Vincent and Soille, *PAMI*, 1991) does the flooding.

- **Mostly used for** separating touching *round, squat* things of similar
  size: cells, coins, grains, pills, nuclei in microscopy. On those it is close
  to unbeatable for the price.
- **Rarely right for** long, thin or highly elongated objects, because their
  distance transform has a ridge rather than a peak and the markers merge. That
  is why it splits three per cent of this cell's pairs, and why no threshold
  rescues it.
- **More:** `cv2.distanceTransform` and `cv2.watershed` in OpenCV;
  `skimage.segmentation.watershed` in scikit-image.

### GrabCut — tightening an outline you already roughly have

Given a rough box around one object, model the colours inside against those
outside and cut the boundary where the two disagree, smoothing the result
([GrabCut](https://en.wikipedia.org/wiki/GrabCut), Rother, Kolmogorov and Blake,
SIGGRAPH 2004).

- **Mostly used for** interactive photo editing and for cleaning up the last
  pixel or two of a mask whose threshold was approximately right.
- **Rarely right for** deciding *how many* objects are present. It refines one
  boundary; given two merged objects it returns a tidier merged pair.
- **More:** `cv2.grabCut` in OpenCV.

## Where it sits

It is a **first pass in the level view**, not a competitor to
[cluster on the table](02-cluster-on-the-table.md). The two do different jobs:
this one says how many glasses are in a patch and which is nearer, and
clustering says where they are in millimetres. Where depth exists, clustering is
the answer and this is a cheap cross-check; where depth does not, this is what
is left.

Its natural companion is [move the camera](03-move-the-camera.md), which
supplies the one thing this method cannot ask for — a viewpoint from which the
hidden base is not hidden. A pair this solution cannot split is not a failure
report; it is a well-specified request.

← [Solution overview](solution-overview.md) ·
→ [Solution 2 — cluster on the table](02-cluster-on-the-table.md)
