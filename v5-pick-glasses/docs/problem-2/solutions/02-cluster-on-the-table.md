# Solution 2 — cluster on the table

*Programmed. Stop deciding which pixels go together by looking at the picture.
Decide it by looking at where they are in the room.*

## In one paragraph

Every pixel in a depth picture can be turned into a point in the room: the
pixel gives a direction, the depth gives how far along it, and the camera's
pose says where it starts. Once the pixels are points, "which object is this?"
becomes a question about distance on the table rather than about the picture.
Flatten the points onto the table, group them by distance, fit a circle to each
group, and check that circle against what the kind can be. Two objects that
overlap in a photograph are still 150 mm apart in the room.

## The problem this solves

Four to six drinking glasses stand on a table. They are all the same kind, the
kind is known, they are opaque and upright, and they stand at least 150 mm from
each other in a zone 320 mm by 360 mm. A camera on the arm's wrist photographs
them from about 450 mm above the table top. The job is to say **which pixels
belong to which glass**, where each glass is, and roughly how wide it is — and
to say honestly which glasses could not be told apart.

The method the project already has for one glass does not survive several. It
takes the pixels that stand above the table top and runs a **flood fill**: pick
a pixel nobody has visited, spread out to every neighbouring pixel that is also
above the table, and call that patch one object. With one glass on a bare table
that is enough. With five it is not, and the reason is worth being precise
about.

![Merged in the picture, plainly apart on the table](../../../images/problem-2/02-merged-in-the-picture.png)

Look at the two panels side by side. On the left, the two silhouettes touch, so
the flood fill returns one patch. On the right, the same two objects on the
table, with 102 mm of empty table between their footprints. The projection did
not move them closer together. It threw away the one thing that would have kept
them apart: which pixels were near the camera and which were far.

A photograph of a tall object is not a photograph of its footprint. An object
205 mm tall, seen from 450 mm up, has its top imaged as though it stood
450 / (450 − 205) = 1.84 times further from the point straight below the camera
than it really is. So a tall object's silhouette reaches outwards and lands on
whatever is standing in that direction. Two objects far apart on the table can
share a blob, and one blob means one glass to everything downstream.

The fix is not a better flood fill. It is to stop grouping in the picture.

## The idea, in plain words

A depth camera does not really take a picture. It takes a set of measurements
that happen to be arranged in a grid, and each one says *there is a surface
this far away in this direction*. Arranged in a grid they look like a
photograph, and looking at them as a photograph is what causes the trouble.
Unpack them instead, and each one is a point in the room with three
coordinates.

Once they are points, the question changes shape. "Are these two pixels next to
each other?" becomes "are these two points close together in the room?" — and
those are different questions with different answers. Two pixels can be next to
each other while the points they stand for are 200 mm apart. Two points 3 mm
apart in the room are on the same object, whatever the camera was doing when it
saw them.

So: turn every pixel into a point, throw away the points that lie on the table
itself, squash what is left flat onto the table, and group the resulting dots
by how close they are to each other. Each group is one object's footprint. Fit
a circle to each footprint, and you have a middle and a width. Then check the
width against what this kind of glass is allowed to be, because every glass on
the table is one known kind — and a footprint that no glass of that kind could
have is the method telling you it has merged two.

## Where it comes from

This is the standard recipe for a robot arm working over a table, and it has
been for about twenty years. Robotics-basics writes it up as
[point clouds: remove the plane, then cluster](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#16-point-clouds-remove-the-plane-then-cluster):
take the depth picture as a cloud of points, find the largest flat surface and
delete it — that is the table — and group whatever is left into clumps. Each
clump is an object.

It became the default because of what it does *not* need. No training data. No
model file. No idea what the objects are. It works on an object the robot has
never seen, which no model trained on a fixed list of classes does, and it
gives positions in metres directly, which is what the arm needs anyway. It was
built into the Point Cloud Library — [pointclouds.org](https://pointclouds.org/),
BSD 3-Clause — as `pcl::EuclideanClusterExtraction`, and that implementation is
why so much tabletop code from the 2010s looks the same.

Three older ideas sit underneath it, and each is worth a sentence.

**The pinhole camera model** says a camera turns a direction in the room into a
position in a picture by dividing by distance. Run it backwards and a position
in a picture gives you a direction. It is the arithmetic in the next section,
and it is the foundation of everything here. The standard reference is Hartley
and Zisserman's *Multiple View Geometry in Computer Vision*.

**RANSAC** — random sample consensus, from Fischler and Bolles, 1981 — is how
the plane is usually found: pick three points at random, make the plane through
them, count how many other points lie on it, keep the best plane after a few
hundred tries. This cell does not need it, for a reason given later.

**Density clustering.** Grouping points by how close they are to each other,
rather than by fitting a shape to them, was set out for databases as DBSCAN by
Ester, Kriegel, Sander and Xu in 1996. Euclidean cluster extraction is the
simplest member of that family: DBSCAN with the "how many neighbours count as
dense" parameter set to one, which leaves a single parameter behind.

## How it works, step by step

Five steps, built up in order. The project already has the first.

### Step 1 — a pixel becomes a point in the room

This is the foundation, so it gets done slowly.

![One pixel becomes a direction, then a point](../../../images/problem-2/02-pixel-to-point.png)

On the left, what the camera actually hands over; on the right, what one of
those numbers means in the room. Follow the blue line: it starts at the camera,
passes through the highlighted pixel, and stops where the depth says the
surface is.

A picture from this camera is 320 pixels across and 240 down. The colour image
holds three numbers per pixel. The depth image holds one: how far away the
nearest surface is along the direction that pixel looks. A pixel on its own is
not a thing. It is a direction with a distance written on it.

**The direction** comes from where the pixel is in the grid and from two
numbers that describe the lens. The middle of the picture is at
cx = 160, cy = 120, half of 320 and half of 240. The focal length is
fx = fy = 277.1 pixels, which is not a length in millimetres but a conversion
factor: it is how many pixels sideways in the picture correspond to one unit of
sideways-ness per unit of distance. It comes straight from the field of view —
160 / tan(30°) = 277.1 for a camera 320 pixels wide covering 60 degrees.

**The distance** is the depth reading itself. One detail matters: on this kind
of camera the depth is the distance measured along the lens axis, not the
length of the slanted ray. The ray is slightly longer, and the arithmetic below
takes care of that automatically.

**Where the direction starts** is the camera's pose — where the camera was and
which way it was pointing when the picture was taken. The camera is on the
wrist, so its pose comes from the arm's joint angles through the chain of link
lengths the robot description already holds.

Put together, for a pixel at column u and row v with depth Z:

    X = (u − cx) × Z / fx
    Y = (v − cy) × Z / fy
    Z = Z

X, Y and Z are millimetres — or metres, whatever Z was — in the camera's own
frame: X to the right of the lens axis, Y down, Z out along it. Then one 4 × 4
matrix multiply by the camera's pose turns those three numbers into three
numbers in the arm's frame, which is the frame everything else in this project
speaks.

Doing that for every pixel that has a depth reading gives a **point cloud**: a
list of positions, with no grid and no neighbours, just points.

### Step 2 — throw away the table

The arm's base and the table are bolted to the same frame, and the table top's
height was measured once at startup. So "is this point on the table?" is a
comparison against a known number, not a search. Keep the points more than
5 mm above the table top — below that is measurement noise on the table itself
— and less than 260 mm above it, which is above the tallest glass the cell
handles. Everything kept is standing on the table.

This is the simplification the cell gets for free. The standard recipe spends
RANSAC here, hunting for the largest plane. Here the plane is a constant.
That is worth knowing about rather than copying blindly: if the table were ever
moved, or the arm remounted, the constant would be wrong in a way that RANSAC
would not be, and the symptom would be a floor of stray points that never
clusters into anything.

### Step 3 — flatten onto the table

Drop the height. A point at (x, y, z) becomes a dot at (x, y). The cloud
becomes a flat scatter of dots on the table top, as though seen from directly
above with no perspective at all.

This step looks like throwing information away, and it is — but it is throwing
away the one dimension that was making the problem harder.

![Why flattening comes before grouping](../../../images/problem-2/02-why-flatten.png)

On the left, the same two objects as points in full 3-D. Notice the shaded
band: there are points on the tops and a few near the bases, and almost nothing
in between, because a camera looking nearly straight down sees a vertical wall
edge-on and nothing lands on it. On the right, the same points flattened.

The numbers are what make the case. In 3-D, the top of one object and the base
of the same object are 205 mm apart, with a hole between them. The nearest
points of two *different* objects are 102 mm apart. So there is no single
grouping distance that works: anything under 102 mm splits one object into a
cap and a skirt, and anything over 205 mm joins the two objects into one group.
205 mm is more than 102 mm, and no number lives in an empty window.

Flattened, the same object is a disc 76 mm across and the gap to its neighbour
is still 102 mm. Now the window is wide and any sensible number sits in it.

A useful way to hold this: **height is the dimension that varies most and
discriminates least.** Two objects on a table differ in where they stand, not
in how far off the floor they are. Clustering in full 3-D is the right thing to
do for objects stacked or hanging; for upright objects on a known surface it
imports a difficulty that is not there.

One caveat, since the document is trying to be exact. The flattened disc is not
the object's base. It is the outline of the object's **widest horizontal
section**, because that is what hides everything under it from a camera looking
down. For a tumbler the rim and the base are nearly the same width and the
distinction does not matter. For a glass with a bowl wider than its foot, the
flattened disc is the bowl. What problem 2 is asked for is a *rough width*, and
the widest section is the honest answer to that; the exact profile is problem
1's side-on measurement, and it is not this step's job.

### Step 4 — group the dots by distance

The grouping rule is one sentence, and it really is this simple:

> Start from a dot nobody has visited. Take every dot within *d* of it. Take
> every dot within *d* of those. Keep going until nothing new is added. That
> clump is one object. Then start again from a dot that has not been used.

That is **Euclidean cluster extraction**. The only parameter is *d*, the
distance that counts as close. Nothing else is chosen: not the number of
groups, not their size, not their shape.

Two properties of the rule are worth naming, because both matter later.

It is **transitive**. A joins B if they are within *d*; if B joins C, then A, B
and C are all one group, even if A and C are 300 mm apart. That is what lets a
long thin scatter of dots stay together, and it is also why a single stray dot
in the gap between two objects can bridge them.

It **finds the groups rather than being told how many**. Methods that ask "put
these dots into five groups" cannot report that there were four, or six, and
the whole point of problem 2 is to be able to say that.

The naive way to run it compares every dot with every other dot. With ten
thousand dots that is a hundred million comparisons, which is slow in any
language and hopeless in Python. The standard fix is to put the dots into
square bins of side *d* first. Two dots within *d* of each other must be in the
same bin or in one of the eight touching it, so each dot is compared with a
handful of others rather than with all of them. The same trick under a
different name is a k-d tree, which is what `scipy.spatial.cKDTree` builds.

### Step 5 — fit a circle, and check it

A glass seen from above is a circle. Each group of dots is a filled disc, more
or less, and fitting a circle to it gives a middle and a diameter.

The fit itself is short. Looking for the centre (a, b) and radius r that best
explain the dots, the awkward form is

    (x − a)² + (y − b)² = r²

which is not linear in a, b and r. Multiply it out and rearrange, and

    x² + y² = 2a·x + 2b·y + (r² − a² − b²)

is linear in the three unknowns 2a, 2b and (r² − a² − b²). So it is an ordinary
least-squares problem — one call to `numpy.linalg.lstsq` — and the radius comes
back out at the end. That is the algebraic circle fit, and it is exact
arithmetic with no iteration and no starting guess.

A fit beats a bounding box, which is what the current code uses, because it
uses every dot. A bounding box uses two: the extreme ones, which are exactly
the dots most likely to be noise.

Then comes the step that makes the whole method safe.

![The circle fit is the safety net](../../../images/problem-2/02-circle-fit-decides.png)

Left: one circle fitted to the whole group comes out at 260 mm, which nothing
of this kind can be, so it is rejected. Middle: two circles are tried instead,
at 76 and 73 mm. Right: the ruler both are measured against.

Every glass on the table is one known kind, and the kind's own specification
holds the range its widest section can be. Across the four kinds the cell
handles that range is 45 to 105 mm, and within a single kind it is much
narrower — 60 to 90 mm for the kind used in the examples here. So the diameter
that comes out of the fit is a number that can be checked against a number the
project already holds:

- **One circle, diameter in range** — one object. Take it.
- **Out of range** — this is not one object of this kind. Try two circles.
- **Two circles, both in range, and together they explain all the dots** — it
  was two objects. Report both.
- **Still out of range** — say so. Report the group as doubtful, with its
  measured width and the range it failed, and do not guess.

Trying two circles means splitting the group's dots in two first. The plain way
is k-means with k = 2: drop two seed points anywhere, assign each dot to the
nearer seed, move each seed to the middle of the dots assigned to it, and
repeat until nothing moves. Then fit a circle to each half. It takes a
millisecond on a few hundred dots and it needs no model.

What makes this check worth having is that it is **arithmetic, not judgement**.
"That is too wide to be one glass" is a sentence with two numbers in it, and
both are known before the run starts. The report can print them.

## How it works here

Put the five steps against this cell's numbers.

![The whole method in four pictures](../../../images/problem-2/02-four-steps.png)

The four panels are the pipeline: the depth picture, the points that stand
above the table, the flattened dots grouped at 25 mm, and one circle per group.
Everything below is the arithmetic behind those four panels.

**How many points there are.** The object zone is 320 mm by 360 mm. At survey
height one pixel covers about 1.6 mm of table, so the zone is about 200 by 225
pixels — around 45 000 of the picture's 76 800. Five objects with their
silhouettes take up something like a quarter to a third of that, so a picture
yields of the order of ten thousand points above the table. That is a size
NumPy handles without thinking about it.

**How close the points are to each other.** On the table top, 1.6 mm apart. On
the top of a 205 mm object the camera is only 245 mm away rather than 450, so
the spacing there is 1.6 × 245 / 450 ≈ 0.9 mm. On a wall seen at a slant the
spacing stretches, by roughly one over the cosine of the angle between the ray
and the direction sticking straight out of that surface — but even at a steep
slant it stays within a few millimetres.
Depth noise adds a little scatter on top. Nowhere on one object's flattened
footprint is there a gap of more than a few millimetres.

**How the grouping distance is chosen.** This is the one number the method
needs, so it is worth showing both ends of the window rather than asserting a
value.

![Choosing the one parameter](../../../images/problem-2/02-grouping-distance.png)

The shaded ends are the two ways of getting it wrong, and the band between them
is everything that works. Note where 150 mm sits: it is the centre-to-centre
spacing, not the gap, and the difference is the point of the picture.

*The lower end* is set by the largest gap between neighbouring dots on one
object's own footprint. From the paragraph above, that is a few millimetres.
Below about 10 mm the chain starts breaking and one object comes back as
several.

*The upper end* is set by the smallest clear gap between two different objects'
footprints. The objects stand at least 150 mm apart — but that is measured
centre to centre, and clustering sees edge to edge. The gap is 150 mm minus the
two radii. For the widest glasses of this kind, 90 mm across, that is
150 − 45 − 45 = 60 mm. Above 60 mm the chain can hop the gap.

So the window is about 10 mm to 60 mm. **25 mm** is the choice: comfortably
above the noise, comfortably below the smallest real gap, and low in the window
on purpose, because a split object announces itself and a merged pair does not.

**What the fit is checked against.** The kind's range, which belongs in
`glasses/spec.py` with the other rules. Note that this does not break the
project's rule against writing glass measurements down: a range that every
glass of a kind falls inside is a limit, the same sort of thing as "hold the
narrowest part below the bowl". It is not one glass's size, and no glass is
ever assumed to sit anywhere particular inside it.

**Agreement across stations.** The survey already visits several stations and
merges what they saw, so the extra check costs nothing.

![Two stations, and why they are asked to agree](../../../images/problem-2/02-two-stations-agree.png)

The grey patches are the table each object hides from that station. In the left
panel one object sits 254 mm off to the side, so its top is thrown outwards
past the edge of the frame and only the near half of its footprint comes back;
in the right panel that same object is nearly straight below the camera and its
footprint is complete, while a different one is now the awkward one.

Three rules fall out of that picture:

1. A group found in about the same place from more than one station is a real
   object.
2. Its width is taken from the station that saw it nearest to straight down,
   because that is the station whose view of its footprint is least bitten into.
3. A group found from one station only is **reported as doubtful**, not as an
   object. It may well be real. It has been seen once.

Two glasses that merge in one station's picture will almost never merge from
another 200 mm away, because which direction a tall object's silhouette reaches
depends entirely on where the camera is standing.

**What it costs.** Step 1 is arithmetic the project already does. Steps 2 to 5
are new: a comparison, a column drop, a binned flood fill and a least-squares
solve — about 25 lines of NumPy. Timings on this machine are uncertain until
measured, but the shape of the answer is not: this is milliseconds to tens of
milliseconds, against seconds for every centimetre the arm moves. Computation
is not the thing to economise on here.

## A worked example

Five glasses of one kind, each about 205 mm tall, footprints between 60 and
90 mm. Their true positions, in metres from the arm's base:

| | x | y | width |
| --- | --- | --- | --- |
| G1 | 0.533 | −0.320 | 85 mm |
| G2 | 0.636 | −0.436 | 68 mm |
| G3 | 0.360 | −0.120 | 76 mm |
| G4 | 0.580 | −0.140 | 73 mm |
| G5 | 0.360 | −0.330 | 81 mm |

The closest pair is G1 and G2, 155 mm apart, which satisfies the cell's 150 mm
rule with 5 mm to spare. Station A puts the camera 450 mm above the table,
straight above (0.48, −0.26), which is the middle of the zone. Its picture
covers 520 by 390 mm, so the whole zone is in frame.

### One pixel

Take the pixel at column 200, row 169, whose depth reads 0.245 m.

    X = (200 − 160) × 0.245 / 277.1 = +0.0354 m
    Y = (169 − 120) × 0.245 / 277.1 = +0.0433 m
    Z =  0.245 m

The ray to that point is √(0.0354² + 0.0433² + 0.245²) = 0.2513 m long, about
2.5% longer than the depth reading — which is the difference between "along the
lens axis" and "along the ray", and the reason the two sideways terms are
needed rather than the distance alone.

The camera looks straight down and its picture is lined up with the table, so
moving right in the picture is +x and moving down the picture is −y. The pose
turns those three numbers into a point at

    x = 0.480 + 0.0354 = 0.515      y = −0.260 − 0.0433 = −0.303

standing 450 − 245 = 205 mm above the table top. That is a point on the top of
G1, 25 mm in from its centre. One pixel down, 76 799 to go.

### What grouping in the picture returns

G1 stands 80 mm from the point straight below the camera, in the direction of
the zone's far corner. Its rim, 205 mm up, is imaged as though it stood 1.84
times further out — and so is its radius. Its silhouette therefore reaches
1.84 × (80 + 42.5) = 225 mm out from the point below the camera.

G2 stands 235 mm out in the same direction. Its own near edge is at
235 − 34 = 201 mm. Since 225 is more than 201, **the two silhouettes overlap**,
and the flood fill returns them as one patch: four blobs for five glasses.

The merged blob runs from G1's near edge at 80 − 42.5 = 37 mm out to the corner
of the frame at 325 mm. That is about 180 pixels; at the table's scale of
1.6 mm per pixel, roughly 290 mm. No glass of this kind is wider than 90 mm, so
the picture can tell that something is wrong. It cannot tell what, because the
thing that would separate them — which pixels were near and which were far —
went out of the picture when the picture was taken.

### What grouping on the table returns

G1 and G2 are 155 mm apart, centre to centre. Take off their two radii, 42.5
and 34, and there is **78 mm of clear table** between their footprints. At a
25 mm grouping distance the chain cannot cross 78 mm of nothing, so they are
two groups. Every other pair is further apart than that, so five groups come
out of one picture:

| | fitted diameter | true width | in range 60–90? | dots |
| --- | --- | --- | --- | --- |
| G1 | 84 mm | 85 mm | yes | full footprint |
| G2 | 69 mm | 68 mm | yes | **partial** — its top is out of frame |
| G3 | 76 mm | 76 mm | yes | full footprint |
| G4 | 74 mm | 73 mm | yes | full footprint |
| G5 | 81 mm | 81 mm | yes | full footprint |

The fits land within a millimetre or two of the truth, which is what using
every dot rather than the two extreme ones buys.

G2 needs the footnote. It stands 235 mm from the point below the camera, so its
imaged top would sit 1.84 × 235 = 432 mm out — past the corner of the frame at
325 mm. Part of it is simply not in the picture, its group is short of dots, and
its fitted circle is pulled towards the part that is present. The value is
plausible and it is not trusted.

Station B, 200 mm away at (0.62, −0.40), stands almost directly over G2: 39 mm
from the point below the camera. From there G2's whole footprint comes back and
its fit is clean. The survey visits several stations, and each glass's width is
taken from the station that saw it nearest to straight down.

**Result:** five glasses, five positions, five widths, no merges, nothing
doubtful — from pictures in which the old method saw four objects.

### Now the awkward case

This one the problem's scene generator will not produce, because it keeps
glasses 150 mm apart. The method still has to behave sensibly in it, because
problem 3 is about exactly this.

![Where the method stops working](../../../images/problem-2/02-touching-is-the-limit.png)

Three scenes, in order of difficulty. The first is the case above. The second
is recoverable, but not by distance. The third is not recoverable at all.

Two glasses 76 and 73 mm wide standing 90 mm apart have
90 − 38 − 36.5 = 15.5 mm of clear table between them. That is less than 25 mm,
so the chain crosses and they come back as one group. The circle fitted to that
group is 165 mm across, well outside 60 to 90, so the group is split and two
circles are tried: 76 mm and 73 mm, both in range, and together they account
for every dot. Two glasses — and a pair standing this close is precisely what
problem 3 exists to move apart.

Two glasses actually touching have no gap at any grouping distance. One group,
always. The fit can suspect two from the width, but there is nothing left to
measure and no distance reasoning left to do. With three in a row it cannot even
say how many. That case is the handover, and the next section says so plainly.

## The feedback loop

**This solution does not have one, and that is a deliberate limitation rather
than an oversight.**

A feedback loop, in the sense the other solutions in this folder use the term,
needs three things: a measure of doubt, a set of actions that might reduce it,
and a budget to stop it running forever. Cluster-on-the-table has the first and
none of the others. It runs on whatever pictures it is given, from whatever
stations the survey visited, and produces an answer. If a glass was seen badly
it stays seen badly.

What it does produce is good doubt, in four named forms, and each is a number
rather than a feeling:

- a group whose fitted diameter is outside the kind's range;
- a group whose two-circle split also failed the range;
- a group found from one station only;
- a group with fewer dots than the minimum an object of this size should give,
  which usually means most of it was hidden.

Those four flags are exactly the input that [move the camera](solution-overview.md#solution-3--move-the-camera)
consumes: that solution's whole job is to take a doubtful group, work out where
the camera would have to stand for it to become clear, check that the arm can
get there, go and look, and run the clustering again on the better picture.
[Learned doubt steers the next picture](solution-overview.md#solution-4--learned-doubt-steers-the-next-picture)
and [learn which viewpoints pay off](solution-overview.md#solution-6--learn-which-viewpoints-pay-off)
are richer versions of the same loop, and
[a learned verifier over the clusters](solution-overview.md#solution-5--a-learned-verifier-over-the-clusters)
adds a fifth flag by looking at each group and saying whether it looks like one
object or two.

The cost of having no loop is easy to state. With a fixed set of stations,
anything the fixed set happened to see badly is reported badly. The circle fit
catches the merges it can catch by width alone, and the station agreement
catches the ones that depend on viewpoint, but a pair that merges from every
station the survey happens to visit is reported as one wide object with a
"width out of range" flag and nothing more. That is not a wrong answer — it is
flagged — but it is an incomplete one, and closing that gap is what the arm has
to move for.

## What it needs

**Libraries.** Nothing that is not already installed.

- [NumPy](https://numpy.org/) — BSD 3-Clause. The arithmetic: the projection,
  the binning, the least-squares circle fit.
- [SciPy](https://scipy.org/) — BSD 3-Clause. Optional. `spatial.cKDTree` makes
  the neighbour search faster than a hand-rolled bin grid. Not currently in
  `pixi.toml`; it is a one-line addition if the timing ever calls for it.
- [OpenCV](https://opencv.org/) — Apache 2.0, already installed as `py-opencv`.
  Not needed for this method, but it is where the existing mask code lives.
- [ROS 2 Jazzy](https://docs.ros.org/) — Apache 2.0. `sensor_msgs/Image` and
  `cv_bridge` to get the depth picture into an array, and tf2 for the camera
  pose.

The reference implementation of Euclidean cluster extraction lives in the
[Point Cloud Library](https://pointclouds.org/) — BSD 3-Clause — and
scikit-learn's DBSCAN ([scikit-learn.org](https://scikit-learn.org/),
BSD 3-Clause) does the same job with a different parameter set. Neither is
needed: the algorithm is a flood fill over a bin grid, and writing it directly
keeps the dependency list short and the debugging simple.

**Data.** None. No training set, no labels, no weights, no model file, no
licence question about what a model was trained on.

**Hardware.** The depth camera the cell already has, and the CPU. No graphics
card. It runs unchanged on an Apple Silicon Mac.

**Numbers it needs to be told.** Three, and all of them already exist in the
project: the table top's height, from `table/layout.py`; the camera's intrinsic
parameters, from the camera description; and the kind's width range, which
belongs in `glasses/spec.py` with the other rules. The grouping distance, 25 mm,
is new, and belongs with the perception code that uses it.

**Time.** Around 25 lines of new code, plus the tests. There is no training
step, so there is no day of waiting to find out whether it worked.

## What it is good at

**It works on an object nobody has described.** The clustering knows nothing
about glasses. It groups points that are close together. Change the objects and
it carries on working, right up to the circle fit — and even that only needs a
number, not a model.

**It is fast, and it is exact.** No inference, no random sampling, no
iteration except the few rounds of k-means in the split. The same input gives
the same output every time, which is worth more than it sounds when debugging a
robot.

**It fails legibly.** Every step is a number that can be printed: how many
points survived the height filter, how many groups came out, each group's dot
count, each fitted diameter, each residual. When it goes wrong there is always
a number that went wrong first.

**The circle fit turns a guess into arithmetic.** "That is too wide to be one
glass" is a sentence with two numbers in it, and both come from the project's
own specification rather than from a threshold someone tuned.

**It answers in the units the arm uses.** Positions come out in metres from the
arm's base, not in pixels that then need projecting. The next step can act on
them directly.

## What it is bad at

**It cannot separate glasses that genuinely touch.** Distance separates objects
only where there is distance. This is the real limit, and it is what problem 3
exists to remove.

**The circle fit leans on knowing the kind.** That is what makes it strong in
problem 2 and exactly what problem 4 takes back. With four kinds on the table
the allowed range becomes the union of four ranges, 45 to 105 mm, and a
footprint too wide for a tumbler is an ordinary wine glass's bowl. The check
gets weaker in proportion to how much the kinds overlap.

**It assumes a footprint is round.** A glass seen from above is a circle, so
that holds here. It would not hold for a book, a box or a jug with a handle,
and the fit's residual — how far the dots sit from the fitted circle on average
— is the number that would notice.

**It needs depth.** Every step begins with "turn the pixel into a point in the
room". Real glassware returns no depth at all, being transparent, and then none
of this runs. The simulator renders glasses as opaque, so the cell is fine; a
real bench would not be, and that is a fact about the cell rather than about
the method.

**It has one hand-chosen number.** 25 mm is justified above rather than tuned,
but it is still a constant that encodes an assumption about how far apart the
objects stand. Change the scene so the objects stand 20 mm apart and it is
wrong — which is another way of saying the method has a domain, and knows it.

## How it fails

**Two glasses one behind the other at almost the same distance from the camera
stay one group**, because their flattened discs overlap. Only the circle fit
notices, and only by width.

**A glass at the edge of the picture loses part of its footprint**, because its
top is thrown outwards past the frame edge. A circle fitted to most of a disc
is pulled towards the part that is present. The station-agreement rule is the
guard: take the fit from the station that saw it nearest to straight down.

**A stray depth reading bridges two groups.** The grouping rule is transitive,
so one bad dot sitting in the gap joins two objects into one. The usual guards
are to drop groups with fewer dots than an object could plausibly give, and to
require a dot to have a minimum number of neighbours before it can extend a
chain — which is DBSCAN's second parameter, brought back deliberately once it
is needed rather than by default.

**The table height drifts.** If the measured table top is 3 mm too low, a
ribbon of table-top points survives the height filter and connects everything
to everything. The symptom is unmistakable — one enormous group — and the
number to print first is how many points survived the filter.

**A glass outside the height band is invisible.** The filter keeps points 5 to
260 mm above the table. The top of that band sits above the 230 mm tallest
glass the cell handles, so nothing in specification is cut. Anything taller
would be, and silently: the points above 260 mm would simply be dropped, the
group would still form from what is left, and nothing would say why. A guard
worth having is to report how many points were dropped at each end.

## When it would be the right choice

Whenever the objects are opaque, standing on a known surface, and mostly not
touching — which is to say, almost every tabletop cell. It should be the first
thing tried, before any of the cleverer options, because it is cheap to build,
cheap to run and easy to argue with.

It is the right choice here in particular because the cell hands it three gifts:
the table's height is known rather than searched for, the objects are upright
and round so a flattened footprint really is a disc, and every object is one
known kind so its width can be checked against a number the project already
holds. Take any one of those away and the method gets weaker; take all three
away and it becomes the generic tabletop recipe, which still works but has to
be trusted rather than checked.

It stops being the right choice when the objects touch, when there is no depth
to work with, or when the difficulty is the viewpoint rather than the grouping.

## Where it sits

It stands on problem 1's work: the pixel-to-point arithmetic and the measured
table height are already there, and this solution is the two steps that come
after them. It replaces [split the blob in the picture](solution-overview.md#solution-1--split-the-blob-in-the-picture),
which attacks the same merges with a cut through the mask and is treating the
symptom of a projection that has already lost the information. It hands its
doubt straight to [move the camera](solution-overview.md#solution-3--move-the-camera),
which is the loop this solution has not got, and its groups are the input that
[a learned verifier over the clusters](solution-overview.md#solution-5--a-learned-verifier-over-the-clusters)
would check. Where it stops — two glasses touching — is where
[problem 3](../../problem-3/problem.md) starts.
