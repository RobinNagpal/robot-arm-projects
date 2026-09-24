# Problem 2 — how it would be solved

[`problem.md`](problem.md) says what is being asked for. This document says how
it would be answered. It is long, because the point of it is to compare five
ways of doing the job properly rather than to announce one.

## Where we are

The arm has photographed a table with four to six glasses on it. They are all
the same kind, the kind is known, and they are opaque, so the depth camera sees
them perfectly well.

What it has to produce is one set of pixels per glass, a place on the table for
each, and an honest list of the ones it could not separate. It does not pick
anything up. It does not measure a profile. Those come later, and they depend
on this being right, which is why a wrong answer here is expensive.

Two things stand in the way, and they are different problems wearing the same
coat.

**Glasses merge in the picture even when they are far apart on the table.** If
the camera is in line with two of them, one lands on top of the other in the
photograph, and the method problem 1 uses returns them as a single object.

**The camera can no longer stand wherever it likes.** Problem 1 measures a
glass from whichever of nine directions the arm can reach, and with a bare
table several always work. With five glasses, a direction has to clear the line
of sight, the arm's own path, and the edge of its reach at the same time.

## The words, first

Five terms are used throughout, and three of them are used loosely almost
everywhere else. It is worth fixing them before the solutions start.

A **pixel** is one dot in a picture. This camera takes pictures 320 dots wide
and 240 tall.

A **mask** is a picture the same size where every pixel is just yes or no. Here,
yes means "this pixel is part of a glass".

**Connected components**, also called a flood fill, is the step that turns a
mask into separate objects. Take a yes pixel nobody has visited, spread out to
every yes pixel touching it, and call that patch one object. Repeat. It answers
exactly one question — *are these pixels joined?* — and it never asks anything
else, which is the root of the first difficulty above.

A **point cloud** is what you get when every pixel with a depth reading is
turned into a point in the room. The pixel says which direction the camera was
looking, the depth says how far along that direction to go, and the camera's
pose says where the direction starts. Problem 1 already does this.

**Segmentation** is the word that carries three different jobs, and only one of
them answers this problem.

![Three things the word segmentation is used for](../../images/problem-2-three-answers.png)

- **Detection** puts a rectangle round each object. Two overlapping glasses get
  two overlapping rectangles, and the pixels in the overlap belong to both.
- **Semantic segmentation** labels every pixel with a class. Every glass pixel
  comes back labelled "glass", and nothing says which glass. Two overlapping
  glasses are one region — which is the merge this problem exists to prevent.
- **Instance segmentation** labels every pixel with a class *and* with which
  object it belongs to. Five glasses come back as five separate masks.

Problem 2 asks for instance segmentation. Anything that gives less than that
has not answered it.

## Three families, and what "hybrid" means

Every solution below belongs to one of three families. The difference is worth
setting out before the list, because it is not quite the difference most people
expect.

**Programmed.** You state the rule and the computer applies it. No training
data, no model file, no graphics card. It runs in about a millisecond, it works
on an object it has never seen, and when it fails you can usually find out why
by printing one number. Its limit is that somebody has to be able to write the
rule down, and for some questions nobody can.

**Learned.** The behaviour comes from numbers fitted to examples rather than
from a rule anybody wrote. It can do things nobody knows how to state — telling
one object from another in a cluttered photograph, for one — and it pays for
that with a training set, a file of weights that has to be kept in step with
the world, hardware to run it on, and an answer that cannot explain itself.

**Hybrid.** Both, arranged so that the learned part sits inside something
checkable.

The interesting question about a hybrid is not how much of it is learned. It is
**where the learned part sits**, because that is what decides what happens when
the model is wrong — and a model is wrong sometimes, by construction.

![Where the learned part sits decides what happens when it is wrong](../../images/where-the-learned-part-sits.png)

There are four positions, and only the first is what most people picture when
they hear "we used a model".

**As the decider.** The model takes the input and its answer is the answer. A
wrong answer is acted on, because nothing downstream is in a position to
disagree.

**As a proposer.** The rules find candidates and hand the hard ones to the
model; the model suggests something better; the rules then check the
suggestion. A wrong suggestion is rejected by arithmetic, and the system falls
back to what it had.

**As a ranker.** The rules generate every candidate *and* veto the unsafe ones.
The model only puts the survivors in order. A bad ordering costs one wasted
attempt. It cannot cost anything worse, because every candidate had already
passed the safety checks before the model saw it.

**As a verifier.** The rules act, and the model's job is to check what actually
happened. A wrong check costs one extra measurement.

The last three share a property worth naming, because it is the whole argument
for hybrids in a physical system: **the learned part's mistakes are bounded by
something that does not need the model to be right.** That is not a statement
about model quality. A better model narrows the failures; only the arrangement
caps them.

One practical consequence is worth having in mind while reading. A hybrid is
usually *cheaper* than a full learned solution, not more expensive, because the
learned piece has one narrow job. Learning "is this one object or two, given
this crop" needs a fraction of the data of learning "find all the objects", and
it trains on a laptop.

## Feedback: choosing what to measure next

The second theme running through what follows is that **the number of
measurements does not have to be decided in advance.**

![Deciding what to measure next, rather than measuring once](../../images/open-and-closed-loop.png)

Most pipelines are open loop. Take the pictures, work everything out, act. The
number of pictures is fixed before the run starts, so if one object turns out
to be unclear, unclear is how it stays. Everything downstream inherits the
doubt without being told there was one.

A closed loop spends its measurements where they are needed. It takes a
picture, works out what is settled and what is not, and if something is not, it
asks a different question: *where would I have to look for this to become
clear?* Then it goes and looks there, and repeats.

Three things are needed to make that work, and a solution that has only two of
them is not really a loop:

1. **A measure of doubt.** Something that distinguishes "settled" from "not
   sure", rather than always producing an answer. A method that cannot be
   unsure has nothing to drive the loop with.
2. **Actions that could reduce it.** A set of measurements the arm could
   actually take — reachable camera poses, a touch, a different angle — and
   some way of guessing which would help.
3. **A budget.** Every extra look costs arm time, which is by far the most
   expensive resource here. Moving the camera and letting it settle costs
   seconds; running any of the models below costs milliseconds. So the loop has
   to stop, and the sensible rule is to stop when nothing is unclear *or* the
   budget is spent, reporting whatever is still doubtful rather than guessing
   at it.

That third point reverses an instinct most developers bring with them. The
thing to economise on is not computation. It is the number of times the arm has
to move.

## The nine solutions, at a glance

Three programmed, three hybrid, three learned. They are grouped by family and,
within each family, ordered by how much machinery they need.

| | Solution | Family | Where the learned part sits | Closed loop? | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | [Split the blob in the picture](#solution-1--split-the-blob-in-the-picture) | programmed | — | no | cheap, and treats the symptom |
| 2 | [Cluster on the table](#solution-2--cluster-on-the-table) | programmed | — | no | **chosen — the core** |
| 3 | [Move the camera](#solution-3--move-the-camera) | programmed | — | **yes** | **chosen — the loop** |
| 4 | [Geometry proposes, a model refines](#solution-4--geometry-proposes-a-promptable-model-refines) | hybrid | proposer | partly | a good fallback |
| 5 | [Learned doubt steers the next picture](#solution-5--learned-doubt-steers-the-next-picture) | hybrid | ranker | **yes** | the richest version of solution 3 |
| 6 | [A learned verifier over the clusters](#solution-6--a-learned-verifier-over-the-clusters) | hybrid | verifier | **yes** | **the first learned thing worth adding** |
| 7 | [Train an instance model](#solution-7--train-an-instance-model) | learned | decider | no | the answer for real glassware |
| 8 | [Amodal masks and learned association](#solution-8--amodal-masks-and-learned-association) | learned | decider | partly | for heavy occlusion, which this is not |
| 9 | [An active-vision policy](#solution-9--an-active-vision-policy) | learned | decider | **yes** | elegant, and unauditable |

Each is written the same way: what it is, why anyone does it like that, how it
would work in this cell, **the feedback loop** if it has one, a worked example
with real numbers, what it needs, what it is good and bad at, how it fails, and
when it would be the right choice.

---

## Solution 1 — split the blob in the picture

*Programmed. Keep the mask the geometry already builds. When one patch is
too wide to be a single object, cut it in two, using nothing but the
picture.*

### What it is

Problem 1 builds a **mask**: a picture the size of the camera's, each pixel
marked yes where the 3D point there stands above the table top. It then runs a
**flood fill**, or **connected components**: take an unvisited yes pixel, spread
to every yes pixel touching it, call that patch one object, repeat.

Connected components answers one question — *are these pixels joined?* It never
asks how wide the patch is. So two glasses whose silhouettes touch anywhere come
back as one patch, and one patch means one glass downstream.

This approach adds a step: when a patch is too wide to be one glass, cut it,
using only the picture.

### Why anyone does it this way

Splitting a clump of touching things of one colour is an old job in image
processing, and watershed was designed for it. robotics-basics sets it out under
[watershed and GrabCut](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#15-watershed-and-grabcut),
and lists "objects that overlap" as a job
[connected components](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#13-edges-contours-and-connected-components)
cannot do. It is also the cheapest thing on the list: no new sensor, no model
file, no training set, no graphics card.

### How it would work here

**The distance transform.** For every yes pixel, write down how far it is to the
nearest no pixel. Deep inside a blob that number is large; one pixel in from the
edge it is 1. Upside down, it is a landscape: blob middles are valleys, edges are
ridges.

**Markers.** A marker is a patch declared in advance to belong to one object.
Two ways to get them with no human. Take the **local maxima** of the distance
transform — the deepest points, one per glass. Or shave layers off the outside
until the bridge between the glasses is eaten away and two lumps are left. The
**erosion trick** is the same thing: eroding by a disc of radius *r* keeps the
pixels deeper than *r*.

**Watershed, and what flooding means.** That landscape has one basin per glass.
Punch a hole at each marker and let water rise through it at the same rate
everywhere. Each basin fills with its own colour, and where two would meet a wall
is built instead. When the flooding stops, every pixel belongs to one marker and
the walls are the cuts. Watershed is a flood fill starting from several places at
once and stopping where the floods collide.

**GrabCut, and where it fits.** GrabCut refines a rough box round one object
into a tight outline, by modelling the colours inside the box against those
outside. It does not split a clump, so it is not the tool for this job. It comes
afterwards, to tighten each half.

**The round-object version.** From above a glass is a circle, and two
overlapping circles make a blob with a **waist**, a pinch where the outlines
cross. That is the narrowest place, so the distance transform dips there, and
cutting there is the whole method, specialised. Its close relative is **Hough
circle detection**, which scores every centre and radius against the edges.

**Licence.** `cv2.distanceTransform`, `cv2.erode`, `cv2.watershed`,
`cv2.grabCut` and `cv2.HoughCircles` are OpenCV, Apache-2.0, free commercially;
the same algorithms are in scikit-image, BSD-3. Neither needs a GPU, which
matters on a Mac with no NVIDIA card.

### A worked example

At survey height, 450 mm up, one picture covers about 520 by 390 mm across 320
by 240 pixels, so one pixel is 1.6 mm.

Two glasses of the widest kind, 105 mm across, stand in line with the camera. Each
silhouette is about 65 pixels wide, and their centres land 50 pixels apart, so the
outlines overlap and the flood fill returns one blob of 114 pixels by 65 — **185
by 105 mm**. No glass 105 mm across can be 185 mm long, so it is flagged.

The distance transform peaks at 32 pixels (52 mm) at each centre and dips to 20
pixels (32 mm) at the waist. Threshold at 0.7 of the peak, 22.4 pixels: the bridge
drops out and both peaks survive. Flood from them and they collide at the waist,
leaving a cut 40 pixels long. Two pieces come out, each about 104 mm across,
inside the kind's range.

The split worked. Both positions are still silhouettes laid on the table plane,
and problem 1 measured what that costs: a glass 157 mm away reported at 244 mm.

### What it needs

The mask problem 1 already builds. One number, the largest footprint the kind
can have, which its specification holds. One tuning constant, the fraction of the
peak at which markers are cut. OpenCV, already a dependency.

### What it is good at

It is cheap: a millisecond a frame, no weights file to keep in step with the
glassware, no data to collect. Its failures are legible — find the number that was
too low and you know why. And it **needs no depth at all**. If the depth camera
fails, or the glasses become real glass, every geometric method here stops and
this one carries on, given a mask from colour.

### What it is bad at

It cannot tell a wide blob from two glasses; width is the whole of its evidence.
It gives no position better than the one it started with, since both halves are
still silhouettes on the table plane carrying the same bias. And 0.7 is not a fact
about anything. It is a number that worked on the examples it was tried on.

### How it fails

**Heavy overlap.** The same two glasses, 20 pixels apart instead of 50. The blob
is 137 mm long, still too wide to be one glass, so it is noticed. But the waist is
now 30 pixels against a 32-pixel peak, a dip of six per cent. No threshold
separates the markers without destroying them, so watershed returns one region.
The split holds only while the centres are more than about 1.43 radii apart, here
46 pixels or 74 mm. Light overlap is easy. Heavy overlap is the case that matters,
and it is the one that fails.

**Over-splitting.** A ragged mask edge puts a second dip in the distance
transform, and watershed cuts one glass in two. That at least is loud: the pieces
come out too small for the kind.

**The fundamental objection.** The blob is wide **because of where the camera
was standing**, not because of anything about the glasses. Two glasses 150 mm
apart merge from one viewpoint and separate cleanly from another 200 mm along, and
nothing in the mask records that. A method reasoning inside the picture cannot
tell a projection accident from two objects genuinely side by side, so it cuts
both the same way. The depth picture holds that answer already, and clustering on
the table reads it directly.

### When it would be the right choice

When there is no depth. On real glassware the depth picture has a glass-shaped
hole where the glass is, and every method that clusters points in the room has
nothing to cluster. A mask from colour plus a watershed split is then a working
answer rather than a worse one.

Also as a cheap second check: if a cluster's fitted circle is far too big, a
watershed on its pixels costs a millisecond and either agrees or does not.

It is the wrong separator to lead with here, because the depth is present and
already knows what the picture threw away.

![Splitting the blob in the picture](../../images/problem-2-the-waist.png)

![Splitting the blob in the picture](../../images/problem-2-the-waist.png)

---

## Solution 2 — cluster on the table

*Programmed. Stop deciding which pixels go together by looking at the
picture. Decide it by looking at where they are in the room.*

### What it is

Stop deciding which pixels go together by looking at the picture. Decide it by
looking at the table.

Every pixel in a depth picture can be turned into a point in the room — the
pixel says which direction the camera was looking, the depth says how far along
that direction to go, and the camera's pose says where that direction starts.
Problem 1 already does this, to find out which points are above the table top.

Once the pixels are points, "which glass is this?" becomes a question about
distance in the room rather than about neighbouring pixels. Points that are
close together in the room are one glass. Points that are far apart are two,
**even when they were next to each other in the picture.**

Grouping points by how close they are is called **clustering**. The version
used here is the simplest one: start with a point, take everything within a few
millimetres of it, take everything within a few millimetres of those, and carry
on until nothing new is added. That clump is one object. Then start again with
a point that has not been used. It has a name — Euclidean cluster extraction —
and one parameter, the distance that counts as "close".

### Why anyone does it this way

Because it is the standard recipe for a robot arm over a table, and it has been
for twenty years. Robotics-basics sets it out as
[point clouds: remove the plane, then cluster](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#16-point-clouds-remove-the-plane-then-cluster):
take the depth picture as a cloud of points, find the biggest flat surface and
delete it — that is the table — and group what is left into clumps. Each clump
is an object.

It is the default because of what it does *not* need. No training data. No
model file. No idea what the objects are. It works on an object the robot has
never seen, which no model trained on fixed classes does, and it gives 3-D
positions in metres directly, which is what the arm needs anyway.

This cell gets one simplification for free. The standard recipe finds the table
with RANSAC, a search that picks three points at random, makes the plane through
them, counts how many other points lie on it, and keeps the best after a few
hundred tries. Here the table is bolted to the same frame as the arm and its
height was measured at startup, so the plane is a constant and finding it is a
comparison rather than a search.

### How it would work here

Four steps, and the project already has the first.

**1. Points above the table.** Unchanged from problem 1. Every pixel with a
depth becomes a point; keep the ones more than 5 mm above the table top and
less than 260 mm above it, which is the tallest glass the cell handles.

**2. Group them by distance on the table.** Project each point straight down
onto the table and group the resulting dots. Two glasses 150 mm apart are two
groups of dots 150 mm apart, whatever the camera was doing. The grouping
distance has to be smaller than the gap between glasses and larger than the gap
between two points on one glass. At survey height one pixel is about 1.6 mm on
the table, and the glasses stand at least 150 mm apart, so anything between
about 10 mm and 100 mm works. Take 25 mm: comfortably above the noise, and far
below the smallest real gap.

Projecting down rather than clustering in full 3-D is worth doing on purpose.
A glass is a tall thin thing, and in 3-D its top and its bottom are 200 mm
apart, which is further than the gap to its neighbour. Flattened onto the table
it is a disc 75 mm across, and the ambiguity disappears.

**3. Fit a circle to each footprint.** A glass seen from above is a circle.
Fit one to each group's dots and you get a middle and a diameter, both better
than the bounding box the current code uses, because a fit uses every dot
rather than the two extreme ones.

Then check the diameter. **This is the step that makes the whole thing safe,
and it is only available because problem 2 says every glass is one known kind.**
The kind's own specification holds the range its rim can be — 45 to 105 mm
across the four kinds, and much narrower within one. A footprint outside that
range is not one glass. Try two circles instead. If two circles fit and both are
in range, there were two glasses; if they are not, say so and move on rather
than guess.

**4. Agree across stations.** The survey already visits several stations and
merges what they saw. Ask more of it: a glass should be found in about the same
place from more than one station, and a group seen from one station only should
be reported as doubtful rather than as a glass. Two glasses that merge from one
station will almost never merge from another 200 mm away.

### A worked example

Two glasses, 75 mm across, standing 180 mm apart, with the camera in line with
both.

*In the picture:* one blob. Laid down on the table its edges are 260 mm apart —
the far glass's ray lands beyond the near one. Connected components returns a
single object 260 mm wide. No glass in the cell is wider than 105 mm, so
something is wrong, but the picture cannot say what.

*On the table:* the near glass's points land in a disc round (0.42, −0.31). The
far glass's points land in a disc round (0.55, −0.19). The nearest dot of one
group is 105 mm from the nearest dot of the other. At a 25 mm grouping distance
they are two groups, not one.

*The circle fit:* 76 mm and 73 mm. Both inside the kind's 60–90 mm range. Two
glasses, at those two places, with a width each. Done.

Now the awkward case. The two glasses stand 90 mm apart, so their footprints
are 15 mm from touching. At 25 mm grouping they become one group. The circle
fit returns 165 mm, which is outside the range. Two circles are tried: 74 mm and
72 mm, 90 mm apart, both in range. Two glasses — and a pair this close is
exactly what problem 3 has to move.

### What it needs

Nothing that is not already installed. NumPy for the arithmetic. The depth
camera the cell already has. No model, no weights, no graphics card, no training
set, and no licence question.

About 25 lines of new code: the projection to the table, the grouping, and the
circle fit. Everything else exists.

### What it is good at

**It works on an object nobody has described.** The clustering knows nothing
about glasses. It groups points.

**It is fast and it is exact.** No inference, no sampling. On a 320×240 picture
this is a few milliseconds.

**It fails legibly.** Every step is a number you can print. A merged pair is a
diameter outside a range, and the report can say which range and by how much.

**The circle fit turns a guess into arithmetic.** "That is too wide to be one
glass" is a sentence with two numbers in it, and both are known.

### What it is bad at

**It cannot separate glasses that genuinely touch.** Distance separates them
only where there is distance. This is the limit that problem 3 exists to remove,
and it is a real one.

**The circle fit depends on knowing the kind.** That is what makes it strong in
problem 2 and it is exactly what problem 4 takes back. With four kinds on the
table the range is the union of four ranges, and a footprint too wide for a
tumbler is an ordinary wine glass foot.

**It needs depth.** Everything here begins with "turn the pixel into a point in
the room". Real glassware returns no depth at all, and then none of this runs.

### How it fails

**Two glasses one behind the other at almost the same distance** stay one
group, because on the table their discs overlap. The circle fit is the only
thing that notices.

**A glass at the edge of the picture** has half its points missing, and a circle
fitted to half a disc is biased towards the half you have.

**A reflection or a stray depth reading** adds dots where there is no glass. One
stray dot inside the grouping distance joins two groups into one. Dropping
groups below a minimum size handles most of this.

**The grouping distance is a chosen number.** 25 mm works for glasses 150 mm
apart. It will not work for glasses 20 mm apart, and problem 3's whole job is to
produce glasses that are further apart than that.

### When it would be the right choice

Whenever the objects are opaque, standing on a known surface, and mostly not
touching — which is to say, almost every table-top cell. It should be the first
thing tried, and the other four solutions in this document are what to reach
for when it is not enough: when the objects touch, when there is no depth, or
when the viewpoint itself is the problem.

![The chosen method, in three steps](../../images/problem-2-cluster-and-fit.png)

![The chosen method, in three steps](../../images/problem-2-cluster-and-fit.png)

---

## Solution 3 — move the camera

*Programmed, and a closed loop. Instead of working harder on the pictures
you happen to have, go and take better ones — choosing where to stand by a
rule you can print.*

### What it is

Every other approach here takes the pictures as given and works harder on them.
This one changes the pictures.

**Active perception** is the idea that a camera which can move is not the same
instrument as one that cannot. A fixed camera receives whatever the scene sends
it. A camera on a wrist can be *aimed*, and the aiming is part of the
measurement. The name is from Ruzena Bajcsy's *Active Perception* (Proceedings
of the IEEE, 1988), and the claim is that a problem unsolvable from one
viewpoint, however clever the maths, is often easy once the camera may move.

**Next best view**, usually NBV, is the loop that follows. Given what has been
seen, and the viewpoints the camera could reach, which one next? The term is
Connolly's, from *The Determination of Next Best Views* (ICRA, 1985).

### Why anyone does it this way

Because projection throws information away and no processing puts it back.
[`problem.md`](problem.md) says it plainly: two glasses in line with the camera
land on top of each other, and the picture no longer holds which pixels were
near and which far. A watershed on that blob is guessing. A camera 200 mm to
the left has the fact.

It is also cheap. A trained instance model wants a labelled set, weights and a
graphics card this cell has not got. An extra viewpoint costs seconds of arm
motion.

### How it would work here

An NBV loop has four parts: a **belief** about what is out there, a set of
**candidate viewpoints**, a **score** for how much each would help, and a
**cost** to reach it.

*Belief.* The survey already builds one: every cluster has a position, a
footprint circle and a confidence.

*Candidates.* Problem 1's `_standoffs()` already makes nine directions round a
glass at 380 mm, level, 120 mm above the table, and making that finer is free.

*Score.* The textbook score is **information gain**: mark the room in small
cubes as free, occupied or unknown, cast a ray per pixel from the candidate
pose, and count the unknown volume it would resolve.
[OctoMap](https://octomap.github.io/) (Hornung et al., *Autonomous Robots*,
2013; BSD licence) is the standard implementation, and MoveIt 2 keeps one
already, through its occupancy map monitor. Isler et al. (ICRA 2016) and
Delmerico et al. (*Autonomous Robots*, 2018) work the variants through, and it
is all CPU ray casting, so none of it wants CUDA.

It is also more than this cell needs. With one known kind and five glasses the
doubt is a short list of questions, mostly *is that 260 mm blob one glass or
two?* So the score becomes a heuristic: prefer the viewpoint whose wedge holds
the doubtful cluster and no other glass, then the one needing least reach.

*Cost.* The camera is on the wrist, so every viewpoint is an arm pose, and can
be unreachable or unplannable. Test reach with inverse kinematics first —
MoveIt 2's `setFromIK`, milliseconds — then call the planner on the survivors,
best first.

### A worked example

Glass A stands at x = 0.40, y = −0.30, so 500 mm from the base. Glass B is at
x = 0.52, y = −0.39: 650 mm out, 150 mm from A. The unit vector A→B is
(0.8, −0.6).

Two of the nine directions lie along that line, and both die on reach alone.
Standing 380 mm back from A on the far side from B puts the camera at
(0.096, −0.072) — **120 mm from the base**, inside the 300 mm minimum. On B's
side it lands at (0.704, −0.528) — **880 mm**, past the 780 mm limit.

The first was blocked as well. From there B is 530 mm away, and at fx = 277.1 a
105 mm footprint spans 105 × 277.1 / 530 ≈ **55 pixels** of the 320 across,
directly behind A. Two glasses, one silhouette.

Now the perpendicular direction, unit (0.6, 0.8). The camera goes to
(0.628, 0.004) — **628 mm from the base**, inside 300 to 780 — with B 90
degrees off the line of sight. At 380 mm one pixel covers 380 / 277.1 =
**1.37 mm**. That is the next best view, and arithmetic found it before the
planner was asked anything.

### What it needs

A belief to start from, which is the chicken and egg: you cannot predict what a
viewpoint would show without knowing roughly what is on the table, and that is
the job.

Two ways out. One is to score unknown volume rather than objects: at the start
everything is unknown, so a volumetric score works from nothing, which is what
exploration planners such as Bircher et al.'s open-source receding-horizon NBV
planner (ICRA 2016) do. The other is to keep the fixed opening sweep and go
adaptive afterwards, and that is the one to use here, because the sweep exists.
The three stations assume nothing, cover the 320 × 360 mm zone at 35% overlap,
and hand back a coarse map; NBV then runs on the doubtful clusters only. It is
the tail of the survey, not a replacement.

Last, a cost model. One extra look is a plan, a move, a settle and the two
pictures 120 mm apart that parallax wants — about what one more station costs,
and the figure should be timed from `_survey()` rather than guessed here. With
it goes a cap: two extra looks per cluster, stopping when the circle fit
passes.

### What it is good at

Merges caused by where the camera happened to be, which is most of them. A
merge is an accident of geometry, and geometry is what an arm can change. The
loop stops when the doubt is gone, so a run that stops early names the cluster
it stopped on.

### What it is bad at

It is heavier than the problem needs, which is why the overview marks it *the
right idea, more than is needed*: a bounded search with a fixed scoring rule
gets most of the benefit and no loop. It also spends arm time to buy certainty,
and six glasses each wanting a confirming look is six extra stations.

### How it fails

**No candidate survives.** If all nine directions round a glass are out of
reach, blocked or unplannable, the search returns nothing. That is not a
perception failure but a fact about where the glasses stand, and the only
remedy is to move one — the handover to
[problem 3](../problem-3/problem.md).

**The belief is wrong where the score cannot see it.** Occlusion is predicted
from footprint circles, so a merged pair modelled as one wide circle predicts
its own occlusions wrongly, and the loop chooses a viewpoint that is blocked.

**It thrashes.** Without the cap, a doubtful cluster pulls look after look and
the run never ends.

**Real glassware removes the belief**, which starts from depth readings that
real glass does not give.

### When it would be the right choice

When scoring a viewpoint is cheap next to moving to it, and there is a
specific, nameable doubt to settle. Here: run the fixed survey, fit circles,
then invoke the loop only on clusters that failed the fit or were seen from one
station. Full information gain earns its weight at problem 4, where several
unknown kinds mean the doubt stops being a short list.

---

## Solution 4 — geometry proposes, a promptable model refines

*Hybrid, with the model as a proposer. Send the model only the clusters the
geometry is unsure about, prompted with the point the geometry already
computed, then check its answer with the same arithmetic that flagged the
cluster.*
### What it is

A **hybrid**: geometry proposes, a learned model refines, geometry decides.
The model is never the last word.

Two words first. A **closed-set** model answers only with a name from the
fixed list it was trained on, and returns nothing for anything else — which a
robot reads as "nothing there". A **promptable** model takes a picture *and a
hint*, and returns the pixels at that hint. The hint is a **prompt**: a place,
not words — a point, a box, or a rough mask. Its answer is a boundary, never a
name, so there is no list to fall off.

The promptable models are the **Segment Anything** family. Licences read from
the projects:

| Model | Licence | Without CUDA? |
| --- | --- | --- |
| [SAM](https://github.com/facebookresearch/segment-anything) | Apache-2.0, code and weights | yes, slowly |
| [SAM 2](https://github.com/facebookresearch/sam2) | Apache-2.0, code and weights | yes; smallest size comfortably |
| [MobileSAM](https://github.com/ChaoningZhang/MobileSAM) | Apache-2.0 | yes |
| [FastSAM](https://github.com/CASIA-LMC-Lab/FastSAM) | **AGPL-3.0**, inherited from Ultralytics | yes, but the licence bites |
| [EfficientSAM](https://github.com/yformer/EfficientSAM) | uncertain; I have not read its licence file | yes |

FastSAM's README claims Apache-2.0 while its `LICENSE` file says AGPL-3.0; the
licence file counts. SAM 2 is the safe default.

**There is no NVIDIA GPU here** — this is an Apple Silicon Mac. None of these
need CUDA, but all were tuned for it, so running one means
[PyTorch](https://pytorch.org/) (BSD-3) on Metal, or a conversion with
[coremltools](https://github.com/apple/coremltools) (BSD-3).

### Why anyone does it this way

The two halves fail in opposite directions.

Geometry fails **loudly**. A merged pair comes back as a footprint 262 mm
across when the kind is 60 to 90, so the failure is a sentence with two
numbers in it. What geometry cannot do is draw a boundary through a clump,
because the projection threw that information away.

A model fails **quietly**. It draws a good boundary on an object it has never
seen, and an equally confident boundary round the wrong thing.

In this order, the loud failure catches the quiet one. That is the pattern
worth taking generally: **a learned component used as a proposer inside a
checkable envelope.** Its output is not trusted but tested, against a
measurement that exists independently of it. A wrong mask never becomes a
wrong glass; it becomes a diameter outside a range.

### How it would work here

**1. Geometry proposes, with a confidence.** The geometric detector already
gives, per cluster, a position on the table and a fitted footprint circle. Add
one label: a cluster whose circle is inside the kind's diameter range is
**settled**; one that is not, and that two circles do not explain either, is
**doubtful**. That word is the gate.

**2. The model refines — doubtful clusters only.** The prompt costs nothing,
because the geometry already computed it: the cluster's centre, projected back
into the picture, is a **point prompt**, its pixel bounding box is a **box
prompt**, and a clump believed to be two glasses gives two point prompts.

**3. Geometry decides.** Each mask goes back through stage 1's arithmetic:
pixels to points in the room, dropped onto the table, circle fitted. Accept
only if **both** diameters are in the kind's range and the centres far enough
apart to be two glasses. Otherwise both are discarded. The model proposed a
boundary; it did not get a vote.

**Why not every frame.** A mask cannot improve a number that is already right,
and it can make it wrong. One or two doubtful clusters per run is the right
load.

**What a call costs.** Encoder once per picture, decoder once per prompt, so
two prompts is one encode and two cheap passes. The encode is the bill. The
only measured Apple Silicon figures I have are Ultralytics' own: FastSAM-s
**58.0 ms**, MobileSAM **23,802 ms**, on a 2025 M4 Air, CPU — much of that gap
being the runtime, not the model. What SAM 2 would cost here is uncertain.

### The feedback loop

Suppose stage 3 rejects the masks. The tempting answers are a larger model, a
second prompt, or a looser threshold. All three are wrong for one reason:
**the picture does not contain the answer.** Two glasses in line with the
camera occlude each other, and no boundary drawn on those pixels recovers what
was never recorded.

The right next action is **another picture from somewhere else**. The
rejection carries what the viewpoint solutions want: which cluster is
doubtful, where it is, and how wide it wrongly appears. Solution 3 scores
directions round it for line of sight, arm path and reach, and the new picture
re-enters at stage 1. Cap it at two extra looks. If no viewpoint separates the
pair, they are unseparable where they stand — problem 3's business, moving
them apart rather than photographing them harder.

### A worked example

Five glasses of one known kind, footprint range 60 to 90 mm. The station sits
450 mm above the table, so one picture covers about 520 by 390 mm across 320
by 240 pixels, and one pixel is 1.6 mm.

*Stage 1.* Four clusters. Three fit circles of 77, 81 and 74 mm — settled, and
the model is never loaded for them. The fourth fits 262 mm; two circles give
131 and 129 mm, both out of range. Doubtful.

*Stage 2.* That cluster spans 262 / 1.6 ≈ **164 pixels** of the 320 across,
and its two likeliest centres project to pixels **80 apart**, 128 mm on the
table. Those are the prompts: one encode, two decoder passes.

*Stage 3.* Re-projected and fitted, the masks give **76 mm** and **73 mm**,
centres **158 mm** apart — both inside 60 to 90, and above the 150 mm the cell
guarantees between glasses. Accepted.

The other branch: the second mask fits at **118 mm**. Both are discarded, the
cluster stays doubtful, and it goes to solution 3 for a viewpoint
perpendicular to the line joining the pair.

### What it needs

PyTorch on Metal, or a Core ML conversion, and a version-pinned weights file
of tens to hundreds of megabytes. No labelled pictures and no training. A
projection from a table position back to image pixels, which exists; a rule
turning a cluster into a prompt; and stage 3, the circle fit called a second
time.

### What it is good at

Boundaries through a clump the geometry cannot cut — the one job geometry
genuinely cannot do. It enlarges nothing that is trusted, since every number
leaving it came from arithmetic checked against a range the project holds. It
costs nothing when nothing is wrong, and needs no data.

### What it is bad at

**It cannot start anything.** Nothing in it decides where to point.

**It cannot name what it outlined.** Point it at the rack or the arm's own
wrist and it outlines those just as willingly.

**Small pictures.** These models resize internally to around 1024 across, so
blowing 320 by 240 up returns a boundary smoother than the picture justifies.

**Transparent objects**, which the family handles worst.

### How it fails

**It outlines the wrong thing, confidently** — the table behind a rim, or a
highlight as its own object. Stage 3 catches that unless the wrong thing
happens to be glass-sized.

**It splits one glass.** Prompted at a bowl, it returns the bowl.

**Both masks pass and both are wrong.** The residual risk. Agreement across
stations is the remaining defence.

**It thrashes** without the cap, and a pinned weights file behind a gate that
rarely opens is never exercised by the tests.

### When it would be the right choice

When the cheap method has failed on a named cluster, and not before: a model
adds nothing to a cluster that passes the circle fit.

Three cases earn it. Here, for a doubtful cluster two circles cannot explain
and no viewpoint resolves. In problem 4, where the kind is unknown and the
allowed diameter becomes the union of several ranges, loosening the envelope.
And on real glassware, where there is no depth to cluster, so the geometric
route stops existing and takes the envelope with it.

Until then, the gate should stay shut.

---

## Solution 5 — learned doubt steers the next picture

*Hybrid, with the model as a ranker. The fixed sweep happens first. Then a
learned estimate of how unsure each object is decides which extra picture is
worth taking, from candidate poses the geometry has already filtered.*
### What it is

Solution 3 moves the camera by a rule somebody wrote. This one moves it by a
number the machine learned.

**Uncertainty** is a number the perception step returns beside its answer,
saying how far to trust it. A **detection** — a rectangle round an object —
gets one number. A **segmentation** — a yes-or-no label per pixel — gets one
per pixel, so the doubt is itself a picture: a map of where the model is
guessing.

**Aleatoric** doubt is noise in the picture; another picture from the same place
will not remove it. **Epistemic** doubt is the model not knowing, and a better
picture will ([Kendall and Gal](https://arxiv.org/abs/1703.04977)). Only
epistemic doubt is worth an arm move.

The survey runs first and is not learned. Then a loop: score the reachable
viewpoints by how much each should cut the doubt, take that picture, run the
geometry again.

### Why anyone does it this way

A hand-written score can only be suspicious of what its author knew to distrust.
A fitted score is not.

The real ways to get the number:

- **Predictive entropy.** A segmentation model ends in a softmax — a
  probability per class per pixel. Entropy over those is near zero when one
  class wins, high when two are level. One pass. But softmax scores are badly
  calibrated ([Guo et al.](https://arxiv.org/abs/1706.04599)): a confident wrong
  answer gets a confident low entropy.
- **Monte Carlo dropout.** Dropout switches random units off during training.
  Leave it on at inference, run the picture ten times, and measure the spread
  ([Gal and Ghahramani](https://arxiv.org/abs/1506.02142);
  [Bayesian SegNet](https://arxiv.org/abs/1511.02680) is the per-pixel version).
- **Ensembles.** Train five copies with different seeds and take their
  disagreement. [Deep ensembles](https://arxiv.org/abs/1612.01474) win most
  published comparisons and cost the most.
- **Evidential deep learning.** The network predicts a distribution *over* the
  class probabilities, so in one pass it can say "I have seen little like this"
  ([Sensoy et al.](https://arxiv.org/abs/1806.01768);
  [Amini et al.](https://arxiv.org/abs/1910.02600) for regression).
- **Disagreement between two views.** No model. Segment both pictures of a
  station, project each onto the table, and measure how far apart they put the
  same glass. The survey already takes two pictures 120 mm apart, so it is free.

[PyTorch](https://github.com/pytorch/pytorch) (BSD-3-Clause) gives dropout and
ensembles alone; [TorchUncertainty](https://github.com/ENSTA-U2IS-AI/torch-uncertainty)
and [Laplace](https://github.com/aleximmer/Laplace) package the rest. Both look
permissive, but I have not read their licence files.

### How it would work here

**The classical half.** The textbook score is **information gain**. Cut the room
into cubes, each holding a probability it is occupied: a cube at 0.5 is one bit
of doubt, a cube at 0.02 almost none. Cast a ray per pixel from a candidate pose
and add the entropy of every cube it crosses.
[OctoMap](https://octomap.github.io/) (BSD-3) is the usual store.

CPU-feasible? Comfortably. At 5 mm cubes the 320 x 360 mm zone, 230 mm tall, is
64 x 72 x 46 — about 212,000 cubes. One candidate casts 76,800 rays across tens
of cubes each: milliseconds, and two dozen stay under a second, with nothing
wanting CUDA on this Apple Silicon Mac. But occupancy entropy answers *where is
the room unmapped*, and the doubt here is *one glass or two*.

**The ordering is the whole point.** Candidates are generated and filtered
geometrically *before* anything learned runs.

1. **Generate.** `_standoffs()` makes nine directions round a target at 380 mm,
   level, 120 mm above the table. Make it 24 at 15-degree spacing.
2. **Reach.** The camera lands at the cluster plus 380 mm along the direction,
   and must be 300 to 780 mm from the base.
3. **Occlusion.** Reject any line of sight passing through another cluster's
   fitted footprint circle.
4. **Plannability.** Inverse kinematics on the survivors — MoveIt 2's
   `setFromIK`, milliseconds each.

The model scores only what is left. It never proposes a pose, only ranks ones the
arm is known to reach — the ordering that makes this hybrid.

**Training.** In: the picture, the belief, one candidate pose. Out: the expected
drop in that object's uncertainty. Labels are free — render the view, run the
geometry, measure the drop. [Gazebo](https://gazebosim.org/) is Apache-2.0 and
already running, so a few thousand examples is an overnight job.

### The feedback loop

1. **Survey.** Three fixed stations, two pictures each. Not learned: it assumes
   nothing, which an adaptive method cannot do from a standing start.
2. **Geometry and doubt.** Cluster, fit a circle, check the diameter. A cluster
   is doubtful on an out-of-range circle, on two circles fitting no better, or on
   one station only.
3. **Choose.** Generate, filter, score, take the best.
4. **Move, photograph, back to step 2.**

It stops on no doubt left, the budget spent, or no candidate surviving — the
handover to problem 3.

### A worked example

The survey finishes with five clusters. Four fit circles of 71 to 78 mm, inside
the kind's range. The fifth fits at **165 mm**, which no single glass here can
be. It stands 530 mm from the base; budget, four extra looks.

**Reach.** The camera lands sqrt(530² + 380² + 2·530·380·cos θ) from the base,
where θ is the angle between the standoff direction and the line out from the
base. The 780 mm ceiling needs θ ≥ 63 degrees and the 300 mm floor θ ≤ 146, so
**ten of 24 survive.**

**Occlusion.** Two look through a neighbour: at 480 mm and fx = 277.1 its 105 mm
footprint spans 105 × 277.1 / 480 ≈ **61 pixels** of the 320, on top of the
target. **Eight left.**

**Score.** `setFromIK` fails on one, so **seven are scored**, milliseconds each.
The best predicts a 0.41 drop in mean per-pixel entropy, the runner-up 0.12.

**Move and re-run.** Plan, move, settle: seconds, then five pictures along the
120 mm slide rather than two, because a picture costs milliseconds. The group
resolves into circles of 74 mm and 71 mm, centres 88 mm apart, both in range.
One look spent of four.

### What it needs

One of the five uncertainty methods, bolted onto the segmenter in use. A scoring
model and the simulator run behind it. The geometric filter, needed anyway. And a
budget with arithmetic behind it: three stations at a few seconds each is the
run's cost today, and the whole run should take tens of seconds, so **two extra
looks per cluster and four per run** roughly doubles the survey. Six does not
fit.

### What it is good at

It spends arm time in proportion to the doubt, which a fixed rule cannot. And it
degrades gracefully: strip the model out and the filter still returns reachable,
unoccluded viewpoints — the first of which is solution 3.

### What it is bad at

It buys a better *ordering* where the cheap rule already picks an acceptable
viewpoint most of the time. With one known kind the doubt is a short list of
near-identical questions, which is not where learning earns its keep.

### How it fails

**Confidently wrong, which is worse than uncertain.** A merged pair comes back as
one clean mask with low entropy everywhere. Nothing is flagged, no look is taken,
and the run reports one large glass — the failure `problem.md` watches hardest.

Four guards, and none of them is the model:

- **The geometry decides; the model only orders.** Whether a cluster is resolved
  is the circle fit against the kind's 45 to 105 mm range, never the entropy.
- **A floor that ignores the score.** A cluster seen from one station only gets a
  look regardless.
- **The model-free cross-check.** If a station's two views disagree about a glass
  by more than depth noise allows, believe the disagreement.
- **Calibration, measured.** Against the simulator's record of what it spawned,
  check that the 90-per-cent-confident predictions are right 90 per cent of the
  time. If not, this is a heuristic wearing a weights file.

**Out of distribution.** The model is trained on one kind, and problem 4 puts
four on the table — an unfamiliar shape is where a miscalibrated model is most
confident. Without the cap on extra looks, a cluster resolvable from nowhere
pulls look after look, each scoring well and none helping.

### When it would be the right choice

When the doubt stops being a short list. Here it is *one glass or two*, asked
five times, and a fixed rule answers it. At problem 4 the kind is unknown, the
allowed diameter becomes the union of four ranges, and the doubt turns graded
rather than binary — which is when a per-pixel map says what a threshold cannot.
Build the filter now, and fit the model once a scored run shows where the cheap
rule chooses wrongly.

---

## Solution 6 — a learned verifier over the clusters

*Hybrid, with the model as a verifier. Do not learn the perception. Learn the
one question the rules are worst at — is this one object or two — on the crop
the rules have already isolated.*
### What it is

Solution 2 groups points on the table and fits a circle to each footprint. The
residue is a narrow band where the fit is *ambiguous*: one circle slightly too
wide for the kind, or two circles that both fit badly.

This does not replace the geometry. It adds a **small learned classifier** with
one job: *is this group one object or two?* It is asked only about groups the
geometry could not settle, using numbers it already computed.

The pattern has no settled name. **Verifier**, when a cheap stage proposes and a
second checks. **Cascade**, when cheap tests run first and the costly one only on
survivors, as in
[OpenCV's cascade classifier](https://docs.opencv.org/4.x/db/d28/tutorial_cascade_classifier.html).
**Learned gating**, when a model picks a rule-based system's branch. "Residual
learning" is used this way in talk, but in papers it means a ResNet's skip
connections. In one sentence: **do not learn the whole task, learn the one
decision the rules are worst at.**

### Why anyone does it this way

The geometry is exact, fast and inspectable, and needs no data. Its weakness is
the threshold it must commit to — 90 mm is one glass, 91 mm is not — when reality
has no step in it there. A model gives a soft boundary instead, learned from
examples.

A model's weaknesses are data, opacity and going stale. Ask it one binary
question on a dozen numbers and all three shrink. Size matters too: **this is an
Apple Silicon Mac with no NVIDIA GPU**, where a full instance model costs a day
of fine-tuning and this forest costs seconds.

### How it would work here

**The input is features, not pixels.** A dozen numbers per doubtful group:

- fitted diameter over the kind's mean diameter;
- RMS residual of the one-circle fit, its worst single residual, the same for the
  best two-circle fit, and the ratio of the two;
- gap between the two candidate centres, in fitted radii;
- dot count, and dots per square millimetre against what the camera predicts at
  that range — at 450 mm one pixel is 1.6 mm, so that is arithmetic;
- stations that saw it, how far its centre moved between them, and its height,
  inside the cell's 65–230 mm.

Features beat raw pixels here. They are in millimetres, so the model never
relearns the camera, and they do not change with where the arm stood. A dozen
numbers need hundreds of examples where a 320×240 crop needs tens of thousands.
And each prints beside the answer, so a wrong call is readable.

**The model.** A gradient-boosted tree or random forest from
[scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html)
(BSD-3-Clause,
[licence](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING)): a few
hundred shallow trees, seconds to train on the CPU. To use a 32×32 crop of the
mask as well, a tiny convolutional network in [PyTorch](https://pytorch.org/)
(BSD-3-style,
[licence](https://github.com/pytorch/pytorch/blob/main/LICENSE)) trains in minutes
on the Mac's MPS backend. Start with the trees.

**The data.** [Gazebo](https://gazebosim.org/) (Apache-2.0) knows what it spawned,
so every group comes labelled for nothing. Do not sample uniformly: spawn pairs 60
to 120 mm apart, where the ambiguity lives. A few thousand rows is the order to
aim for, settled on a held-out set.

### The feedback loop

**The most useful output is not yes or no. It is "I cannot tell".**

The model returns a probability, calibrated on held-out data
([scikit-learn's calibration guide](https://scikit-learn.org/stable/modules/calibration.html)).
Two thresholds give three answers: one glass, two glasses, or abstain — Chow's
**reject option** (IEEE Transactions on Information Theory, 1970,
[IEEE Xplore](https://ieeexplore.ieee.org/document/1054406)).

An abstention is a request with an address: solution 3. The two-circle fit gives
two candidate centres, so the viewpoint that resolves them is the one
perpendicular to the line between them — a next-best-view with no search. Take
that picture, re-cluster, re-fit and ask again, capped at two extra looks. If it
still abstains, the pair is reported unseparated and handed to problem 3. The band
is a dial: wide buys certainty with arm time, narrow merges more.

### A worked example

The kind's footprint range is 60 to 90 mm. A group comes back with 340 dots. One
circle fits at **97 mm**, RMS residual **6.2 mm** — outside the range, but by four
pixels' worth. Two circles fit at **63 mm** and **59 mm**, RMS **3.1 mm**, centres
**44 mm** apart. Both are in range, but 44 mm between circles of 63 and 59 mm
means the rims interpenetrate, which two upright glasses cannot do.

The verifier gets the row: diameter ratio 1.29, residual ratio 2.0, centre gap
1.40 radii, 340 dots at 0.81 per square mm against 0.78 expected, one station. It
returns **0.46** — inside the 0.25 to 0.75 band, so it abstains.

The arm takes one more picture, perpendicular to the 44 mm line, 380 mm back. The
group splits into **72 mm** and **69 mm**, 88 mm apart, and the geometry answers on
its own. The model's contribution was not the answer. It was knowing it did not
have one, and where to look.

### What it needs

NumPy and scikit-learn, both BSD-3. One version-pinned weights file of a few
hundred kilobytes, checked in beside its loader. A feature extractor,
about thirty lines on solution 2's clustering. No GPU and no CUDA. And a hash of
the feature list inside the model file, so adding a feature makes the loader
refuse the old model rather than misread it.

### What it is good at

**It is small enough to trust, and cheap to retrain:** one binary question, a
dozen inputs, a training set you can look at.

**It degrades to the geometry.** Missing file, corrupt file, wrong feature list,
failed import — the caller catches it and abstains on every doubtful group, which
is what solutions 2 and 3 do today. A few more pictures, a few more unseparated
pairs, and nothing downstream notices but the timing. A learned component whose
worst case is the previous behaviour is a rare and valuable thing.

**Its failures are bounded.** It cannot invent a glass, move a position or report
a width. Those come from depth measured during the run.

### What it is bad at

**It is only as good as the band it is asked about.** Draw that band wrong and it
never sees the cases that matter.

**It holds a size-shaped prior.** Ratios help, but a model trained on one kind has
learned that kind's proportions — knowledge about glass sizes in a file nobody can
read, which the report should admit. And it does not carry into problem 4, where
the allowed range becomes a union of ranges and the question changes.

### How it fails

**Confidently and wrongly.** A merged pair scored 0.95 for "one glass" is the
failure to watch hardest. Miscalibration is how it arrives: a probability that
looks decisive because the training set held too few hard cases.

**It abstains on everything.** A change in the camera, the table height or the
lighting shifts the features away from what it saw, every group lands in the band,
and the arm thrashes. Loud, which is the good news.

**It goes stale silently.** Change the spawner's proportion ranges and the model
describes glasses that no longer exist. The tests still pass.

### When it would be the right choice

When a programmed method already gets most of the way, the residual failure is one
nameable decision, and truth for it is cheap to generate. All three hold here, and
that is why this beats replacing the whole perception step: a model owning every
pixel costs thousands of labelled pictures and a day of training, cannot be
checked, and buys an answer the geometry already gives in millimetres.

It is wrong when the rules are not already close: a tie-breaker in front of a bad
answer is still a bad answer. And it is wrong on real glassware, where there is no
depth, no cluster and no circle to verify. That is solution 5's day.

---

## Solution 7 — train an instance model

*Learned, as the decider. Show a network a few thousand labelled pictures and
let it learn to outline each object separately.*
### What it is

A **neural network** is a program whose behaviour comes from numbers learned
from examples rather than from rules somebody wrote. The numbers are called
**weights**, and they live in a file. Three things such a network can do with a
picture of five glasses are easy to confuse.

- **Detection** returns a rectangle round each glass. Rectangles of overlapping
  glasses overlap too.
- **Semantic segmentation** labels every pixel with a class. Every glass pixel
  comes back labelled "glass". Nothing says *which* glass, so two overlapping
  glasses come back as one region — the merge this problem exists to prevent.
- **Instance segmentation** labels every pixel with a class *and* with the
  object it belongs to. Five glasses give five **masks**, a mask being a
  picture where every pixel is yes or no.

Problem 2 asks which pixels belong to which glass. That is instance
segmentation, exactly.

### Why anyone does it this way

Every other method here reasons about geometry, and all of it depends on the
glasses being opaque, so that the depth camera returns a real distance for
every glass pixel.

A real depth camera gets almost none back from real glass: nothing to cluster,
no points above the table, no circle to fit. What is left is the colour
picture, where a glass shows itself through refraction, highlights and the way
the background bends behind it. Nobody has written a rule that captures those.
A model learns them from examples.

### How it would work here

The pictures are 320 x 240, small by the standards of these models, which
usually expect 640 pixels or more. Training and inference are therefore cheap,
and the mask boundary stays coarse however good the model is.

The families worth considering, with licences read from the projects:

- **Mask R-CNN.** In `torchvision` it is BSD-3 throughout, the clean option.
  **Detectron2** has better recipes but its **weights are CC BY-SA 3.0** under
  Apache-2.0 code, and it is CUDA-shaped with no release since 2021.
- **YOLO-seg, from Ultralytics.** The easiest path by a distance, and
  **AGPL-3.0**: you must publish the source of anything you combine it with,
  including software you only run as a service and never distribute, and the
  weights carry the same terms however you got them. A commercial licence
  exists, priced by negotiation. For anything that might ship, that is a
  decision rather than a detail, and the same inheritance catches FastSAM.
- **Something smaller.** `segmentation_models_pytorch` (MIT) is semantic only,
  so it needs a separating step bolted on. Hugging Face `transformers`
  (Apache-2.0) fine-tunes Mask2Former and OneFormer, both MIT. At this size a
  Mask R-CNN on a small ResNet backbone is already small.

**Making the data.** The simulator knows every glass's outline, so it renders
labelled pictures for nothing, and the labels are perfect. Gazebo is Apache-2.0
and already running; Kubric (Apache-2.0) and BlenderProc (GPL-3.0 — the data is
yours, the tool is copyleft) render better.

**Domain randomisation** is what makes rendered data transfer. Rather than try
to make the render look real, vary everything you are *not* teaching —
lighting, textures, background, camera pose, exposure, noise, glass colour,
how many glasses and where — so widely that reality looks like one more
variation. The model then cannot latch onto anything that differs between
simulation and reality, because none of it was ever constant.

**Does it break the project's rule?** The model outputs a mask, in pixels, and
a mask holds no millimetres. Size still comes from the depth reading and the
camera geometry, measured during the run. So no: nothing is written down, and
the arm still measures every glass itself. It does put a *size-shaped prior* in
a file nobody can inspect, having been trained on one range of proportions.
That is knowledge about glass sizes held inside the project, and the report
should say so.

### A worked example

Five glasses stand on the table. Two are 300 mm apart but line up with the
camera, so their outlines touch in the picture.

Today `standing_on_the_table()` in `glasses/detect.py` returns one boolean mask
of everything above the table top, and `find_glasses()` groups it into blobs.
The lined-up pair become one blob 260 mm wide, and everything downstream
believes it is one large glass.

A trained model returns five masks, and the lined-up pair are two of them
sharing a boundary. Each mask runs through the existing code unchanged: points
in the room, circle fitted at the table, position and rough width reported.

### What it needs

**Pictures.** You fine-tune rather than train from scratch: take a model that
already knows what objects look like and teach it this one class. A few hundred
labelled pictures is enough to see it work, a few thousand to be steady, and
the simulator renders them overnight. How many are enough here has not been
measured, and I will not guess.

**A machine to train on.** This is the awkward part. The cell runs on an Apple
Silicon Mac and **there is no NVIDIA GPU**. PyTorch trains on Apple's **MPS**
backend, the Mac's own graphics processor, but some operations fall back to the
CPU, and a fine-tune of an hour on a rented NVIDIA card can take most of a day
here. It is possible; it is not something you do between two experiments.
Anything needing compiled CUDA kernels is out entirely: Detectron2's, mmcv's,
the deformable-convolution variants, TensorRT, Isaac ROS.

**Somewhere to run it.** `torchvision` Mask R-CNN runs on MPS, and Ultralytics
with `device="mps"`. At 320 x 240 that should sit inside the time an arm move
takes, but I have not measured it and will not quote a figure. One comparison
shows why guessing is unwise: MobileSAM, designed to be small, takes about 24
seconds per image on an M4 Air's CPU, while Depth Anything V2 Small runs in
24.6 ms on an M3 Max through CoreML and the Neural Engine. What matters is
whether anyone has done the CoreML work, not how small the model is.

### What it is good at

It separates glasses that overlap in the picture without needing depth. It
copes with reflections and highlights far better than any threshold. It works
on real transparent glassware, which nothing else here does without new
hardware. And it enters at one function.

### What it is bad at

It says nothing in millimetres and it cannot say why. It knows only the glasses
it was trained on; a kind outside that range is one it outlines badly, with no
warning. And here it is more machinery than the job needs, because comparing
depths separates two glasses 300 mm apart exactly, with a reason you can print.

### How it fails

**Confidently.** A merged pair comes back as one mask with a high score. A
geometric method that merges leaves evidence — a footprint 260 mm across when
the kind is 60 to 90 — and the circle fit catches it. A model that merges
leaves a number, and the number says it is sure.

**Out of date.** Add a kind, change the proportion ranges, change the lighting
in the world file, and the weights describe something that no longer exists.
Nothing in the repository says so, and the tests still pass.

**In the way.** Every other method here can be changed and re-run in a minute.
This one puts a training loop between the change and the answer, paid on every
experiment.

### When it would be the right choice

The day the glasses stop being opaque, when every geometric method here loses
its input at once. Also if the glassware becomes open-ended, because the circle
fit leans hard on knowing the kind's diameter range. Until then it is a
fallback worth knowing how to build and worth not building.

---

## Solution 8 — amodal masks and learned association

*Learned, as the decider. Predict the whole extent of a partly hidden object,
not just its visible pixels, and learn to recognise the same object across
several viewpoints.*
### What it is

Every segmenter named so far marks only the pixels you can see. The habit has a
name. **Modal segmentation** labels an object's visible pixels and stops where
something else gets in front. **Amodal segmentation** labels the object's *whole*
extent, hidden part included. Put one glass half behind another: a modal model
returns the visible half of the back one, an amodal model the whole footprint,
inferring the hidden part from what it can see. From psychology: *amodal
completion* is reporting one cat behind a railing, not five slices.

Why it matters here is arithmetic. Everything downstream turns a mask into points
on the table and fits a circle. **A mask cut short by an occluder gives a circle
too small and in the wrong place**, because the centre of the visible part is not
the centre of the glass. Both errors are silent: a wrong footprint comes back not
as an error but as a plausible number.

The second half is **association**: deciding that a detection in one picture is
the same physical glass as one in another. Three stations, two pictures each,
five glasses — thirty detections, five objects. That is the **data association
problem**, a separate job from finding the glasses.

### Why anyone does it this way

`problem.md` says the failure to watch hardest is *merged*, because it does not
announce itself. A truncated footprint is the same failure in different clothes:
the range for one kind is 60–90 mm, so a glass 30 per cent hidden reports about
60 mm, and solution 2's circle fit passes it in silence.

For association the classical answer is geometric, and solutions 2 and 3 use it:
two detections are one glass if their positions are close and their heights
agree. It fails when a position is wrong *because* the mask was truncated —
geometry arbitrating with broken numbers.

The learned answer ignores position. The model turns each detection into an
**embedding**: a short list of numbers, typically 128 or 256 of them, produced by
a network from that detection's pixels. Nobody chooses what the numbers mean. The
network is trained so two views of one object land close together in that space
and views of different objects land far apart, by ordinary Euclidean or cosine
distance. The usual signal is a **triplet loss** — an anchor, another view of it,
and a different object; pull the first pair together, push the second apart.
"Same glass?" becomes "is this distance small?"

The neighbouring field is **multi-object tracking**. A **track** is an identity
over time; a **cost matrix** prices matching each detection to each track; the
**Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`, SciPy, BSD-3)
picks the cheapest one-to-one assignment; **re-identification** is the embedding
half. DeepSORT (https://github.com/nwojke/deep_sort), the classic
appearance tracker, is **GPL-3.0**; ByteTrack
(https://github.com/ifzhang/ByteTrack) is MIT.

### How it would work here

**The models.** Amodal segmentation is a small field, and most of it is research
code. **UOAIS** (https://github.com/gist-ailab/uoais, ICRA 2022) fits closest —
RGB-D, tabletop, class-free, predicting a visible mask, an amodal mask and an
occlusion flag per object; licence uncertain. **BCNet**
(https://github.com/lkeab/BCNet, MIT) models occluder and occluded as two layers.

Both sit on **Detectron2**, which solution 5 flags as CUDA-shaped and unreleased
since 2021. With no NVIDIA card that is the real obstacle, not model size. A
`torchvision` Mask R-CNN (BSD-3) with a second head for the amodal mask runs on
MPS, and is the route I would take.

**The datasets** are mostly unusable here: COCO-Amodal
(https://github.com/Wakeupbuddy/amodalAPI, licence uncertain) and KINS
(https://github.com/qqlu/Amodal-Instance-Segmentation-through-KINS-Dataset),
annotated on KITTI and so **CC BY-NC-SA, non-commercial**. Neither holds glasses.

**The simulator supplies the data free, which is what makes this practical.**
Render each glass alone against the empty table: that silhouette is the amodal
mask, exact. Render the whole scene: that is the modal mask. The difference is
the occlusion mask. No annotator, so no annotator error, and the same renders
label association free.

**The pipeline.** Run the model on each picture and fit the circle to its amodal
mask — existing code, fed an untruncated footprint. Then embed every detection
and solve the cost matrix across pictures.

### The feedback loop

The margin on that assignment is the useful output. If a detection sits 0.11
from candidate A and 0.13 from B, while two views of one glass typically sit
0.05 apart, the match is a coin toss wearing a number.

**An uncertain association is a reason to take one more picture, from a viewpoint
where the two candidates would look different.** That is solution 3's
next-best-view machinery with the score swapped: instead of unknown volume, score
the **predicted margin** — for each reachable viewpoint, predict how A and B
would look and prefer the one putting their embeddings furthest apart. Two
glasses drawn 230 mm and 205 mm tall look identical from above and differ by
25 mm from level, so the loop picks a level view. Cap it: two extra looks, then
report the pair unseparated.

### A worked example

At survey height, 450 mm up, one pixel covers 1.6 mm. Glass A stands 180 mm in
front of glass B, in line with the camera. B's footprint is 78 mm, or 49 pixels,
and A hides 22 per cent of its disc.

*Modal.* B's visible part is 38 pixels, **61 mm** — inside the 60–90 mm range, so
it passes. The circle fitted to that crescent has its centre **8.5 mm** from B's
true one. One glass, 61 mm across, in a place it is not.

*Amodal.* The model returns the whole disc: 77 mm against a true 78, centre
within 2 mm, flagged as 22 per cent inferred.

*Association.* Station 2 sees B unoccluded; its embedding sits 0.04 from station
1's truncated B against 0.19 for the nearest other glass. The awkward pair, of
nearly identical proportions, come back at 0.11 and 0.13; one level look
separates them to 0.06 and 0.21.

### What it needs

Rendered data with amodal masks, free from the simulator, and a second mask head
to predict them. An embedding network and a triplet loss on the same renders,
SciPy for the assignment, and solution 5's training cost, doubled.

### What it is good at

It attacks the truncated-footprint failure, which nothing else here detects, and
turns association into evidence rather than assumption. It gives numbers to be
uncertain about: the margin drives the extra look, and the occlusion fraction
marks a mostly-guessed footprint doubtful.

### What it is bad at

**Every glass is the same kind.** An appearance embedding on four to six nearly
identical objects has very little to work with. What signal exists comes from the
proportions drawn at random inside the kind's range, plus incidental marks and
lighting — and in a clean render of untextured glasses there may be almost none.
That is a real reason to doubt the embedding half earns its keep here.

### How it fails

**The completion is invented and looks measured.** An amodal mask for a glass 90
per cent hidden is almost all guess, yet comes back as a clean outline with a
high score. Without the occlusion fraction, nothing says so.

**A systematic completion bias.** If the renders over-represent one occlusion
geometry, every footprint is wrong the same way, which is harder to spot.

**An identity swap.** Two glasses matched the wrong way round give two confident
positions, each belonging to the other. It is likeliest when the margin is
miscalibrated: measure within-object distance on clean renders and every match
looks confident, so the loop never fires.

### When it would be the right choice

When objects genuinely hide each other and there are many viewpoints to
reconcile: a bin, a crowded shelf, a tray of glassware pushed together. Where
occlusion is the normal case and not the accident, a model that predicts
the hidden part is not extra machinery — it is the measurement. It is also
solution 5's partner on real glassware, where no depth is left to cluster.

For this cell it is far more than the problem needs. Four to six glasses stand
150 mm apart on a bare table, and most pictures show every glass whole. Where one
does not, solution 3 moves the camera 200 mm and the occlusion goes away, seconds
of arm time against two trained models. It earns its place when the arm cannot
reach a clear viewpoint, and here it usually can.

---

## Solution 9 — an active-vision policy

*Learned, as the decider, and a closed loop by construction. A policy takes the
current belief about the table and outputs where to point the camera next.*
### What it is

A **policy** is a function from what the robot knows to what it does next.
Here: belief about the table in, next camera pose out. Nobody wrote the rule
inside it. The rule is a pile of numbers — the **weights** — fitted from
experience. There are two ways to fit them.

**Reinforcement learning.** Let the robot try. It looks somewhere, and
eventually is handed a number — the **reward** — saying how well the whole
attempt went. Thousands of attempts later, actions that tended to precede high
reward have become more likely. Nobody says which individual look was good;
that is inferred from the totals, which is why it takes so many attempts.

**Imitation learning.** Show it the answer instead. Run an expert — a person
with a joystick, or a slow method already known to be right — record what the
expert saw and did, and fit the policy to reproduce the choice. This is
**behaviour cloning**, ordinary supervised learning. It needs no reward, and it
can never beat the expert it copied.

### Why anyone does it this way

Scoring a viewpoint properly is expensive; choosing one is cheap. Solution 3's
score casts a ray per pixel into an occupancy map, for every candidate. A
policy does one forward pass, and you pay the cost once, offline. And a
geometric score exists only where somebody can write one down. Here they could.
Where the cue is subtler, nobody can.

### How it would work here

**The observation.** Not the raw picture — appearance is what will not transfer
out of Gazebo. Feed it what the geometry produced: the 320 x 360 mm glass zone
as a grid of 20 mm cells, 16 x 18 = 288 of them, each empty, occupied or
never-seen; one row per cluster, holding position, fitted diameter, how many of
the three stations saw it and whether that diameter is in range; and how many
looks remain. About nine hundred numbers, small enough to train on a CPU.

**The action.** In principle a camera pose: six numbers. In practice, don't.
Take a fixed list of **candidate poses** — problem 1's `_standoffs()` gives
nine directions at 380 mm, and three heights make 27 — and let the action be a
choice among them, plus one meaning **stop**. Discrete is the sane engineering
choice: every candidate is checked once against the 300–780 mm reach and
against inverse kinematics, so the policy cannot name a pose the arm will not
hold, and failures are masked out. A continuous six-dimensional space would
spend most of its exploration in mid-air.

**The reward, which is the hard part.** Use problem 2's own score sheet: +1 per
glass correctly separated, −1 per merged pair, −0.05 per look. That needs to
know which glasses were really there. Gazebo writes down everything it spawned,
so in simulation the reward is exact. **Reality has no such file.** You could
pay for a proxy, such as the circle fit passing — but a policy optimises
exactly what you pay for, and one paid for a passing fit learns viewpoints from
which it passes, not viewpoints from which the answer is right.

| Tool | Link | Licence | Needs CUDA? |
| --- | --- | --- | --- |
| Gymnasium | https://github.com/Farama-Foundation/Gymnasium | MIT | no |
| Stable-Baselines3 | https://github.com/DLR-RM/stable-baselines3 | MIT | no; PyTorch on Apple's MPS backend or CPU |
| Ray RLlib | https://github.com/ray-project/ray | Apache-2.0 | no |
| Gazebo Harmonic | https://gazebosim.org/ | Apache-2.0 | no; headless here already |
| MuJoCo | https://github.com/google-deepmind/mujoco | Apache-2.0 | no for the CPU engine; its MJX fast path wants a GPU, and Apple Silicon support is uncertain |
| Isaac Lab | https://github.com/isaac-sim/IsaacLab | BSD-3-Clause | **yes** — Isaac Sim needs an NVIDIA RTX card |

Gymnasium defines the interface — `reset()`, `step(action)`, a reward.
Stable-Baselines3 supplies the algorithms and is the right first choice here;
RLlib is for scaling across machines. **Isaac Lab is out**: this is an Apple
Silicon Mac with no NVIDIA GPU, and everything CUDA-shaped goes with it.

**How long.** An episode is at most six looks, each an arm move of a few
seconds, plus a reset — call it ten seconds of wall clock headless, a figure to
measure rather than guess. At 50,000 episodes that is five days on one process,
under a day with eight in parallel. A gradient step is milliseconds, so **the
simulator is the bottleneck, by three orders of magnitude.**

### The feedback loop

This is not a solution with feedback bolted on. It **is** the loop.

1. **Observe.** Run the three-station survey, cluster, fit circles, build the
   observation.
2. **Choose.** The policy returns one of the 27 candidates, or `stop`. Those
   failing reach or IK were masked before it chose.
3. **Move.** Plan and execute, a few seconds. If the plan fails, mask that
   candidate and return to step 2.
4. **Re-observe.** Take the pictures, fold the new points into the same
   clusters, refit, rebuild the observation.
5. **Stop** on `stop`, or when the six-look budget runs out. Clusters still
   failing their fit are reported unseparated — the handover to problem 3.

The belief is **cumulative** — each look adds points to the same clustering
rather than starting again — and the **budget is external, not learned**, so a
policy that never says `stop` wastes six looks rather than running forever.

### A worked example

Glass A at x = 0.40, y = −0.30, 500 mm from the base. Glass B at x = 0.52,
y = −0.39, 650 mm out and 150 mm from A. B sat behind A from two of the three
stations, and the merged cluster fits a circle 165 mm across against the kind's
60–90 mm range. Two of the nine directions lie along the A–B line, and at all
three heights they fail on reach alone: 380 mm back from A lands either 120 mm
from the base or 880 mm out, against limits of 300 and 780.

The policy picks candidate 14, the perpendicular, camera at (0.628, 0.004). One
move, about three seconds. The cluster resolves into discs of 76 mm and 73 mm,
both in range, so the policy says `stop` and the episode returns
2 − 0.05 = **1.95**.

Solution 3's arithmetic chose that same viewpoint before the planner was asked
anything, and can say why: from the blocked direction B spans
105 x 277.1 / 530 ≈ 55 of the 320 pixels directly behind A. The policy chose
candidate 14 with a value of 0.83, and can say nothing.

### What it needs

A Gymnasium environment round the existing cell: reset spawns four to six
glasses, step moves the arm and re-runs perception, reward reads the spawn
record. That wrapper is the real work, because it must reset Gazebo thousands
of times without leaking processes. Then Stable-Baselines3, PyTorch on MPS or
CPU, and days of machine time. No labelled pictures, and no NVIDIA card.

### What it is good at

Run-time speed: choosing is a forward pass, microseconds against the seconds a
move costs. Cues nobody wrote down, where a viewpoint pays off for reasons the
circle fit misses. And it optimises the thing itself, merges and splits, where
information gain is only a proxy for them.

### What it is bad at

It cannot explain itself, and here that is practical rather than philosophical.
Problem 2 says the failure to watch hardest is the merged pair, because it
looks plausible downstream. A policy that stops one look early produces exactly
that failure, and reports confidence while doing it.

It is also more machinery than this problem has earned. What it would learn is
computable: the kind is known, the diameter range is known, occlusion is a
line-of-sight test. Where a geometric score exists and is auditable, a network
trades the explanation for a speed-up.

### How it fails

**Reward hacking.** Charge too much per look and it stops at once and eats the
merge penalty; too little and it burns six looks every run. That balance is not
derivable, and each attempt costs another training run.

**Sim-to-real drift.** Milder than for contact tasks — no friction, no
deformation, no impact, and what matters is straight lines from camera to
object, which Gazebo gets right. Feeding clusters rather than pixels removes
most of the appearance gap too. But the policy learned this simulator's depth
noise and its dropout at glancing angles, and a real camera that loses the far
rim at 60 degrees shifts every observation.

**Silent staleness.** Change the kind, the lighting or the standoff list and
the weights describe a cell that no longer exists. The tests still pass.

**Real glassware removes the input**, which is built from clusters, and
clusters from depth that real glass does not return.

### When it would be the right choice

When the doubt stops being a short list. Here, one known kind and a diameter
range make "one glass or two?" arithmetic, and auditable. Problem 4 has several
kinds, some never measured, and the union of their ranges is wide enough that
the circle fit stops deciding much. A policy that learned which looks resolve
ambiguity has something to offer there.

One shape is worth keeping even so. Solution 3's score is a working expert and
runs in simulation for free, so behaviour cloning against it gives a fast
policy with no reward design at all — and one that can only approach what it
copied, having lost the explanation that made the original worth having.

## The decision

**Solutions 2 and 3 are the core. Solution 6 is the first learned thing worth
adding. Solution 4 is the fallback behind it. Solutions 7, 8 and 9 are answers
to a different cell, and it is worth being exact about which.**

### Why the core is programmed

Problem 2 gives away two things for free, and together they make the separation
arithmetic rather than inference.

**Every object is one known kind**, so its footprint is a circle whose diameter
sits inside a range the project already holds. **And they are opaque**, so the
depth camera can see them. Group the points on the table, fit a circle, check
it against the range: a footprint too wide for one object is a merged pair, said
in two numbers, and fitting two circles says where the two of them are.

Nothing learned improves on that, because there is nothing left to infer.

### Why one loop is chosen with it

Separation cannot fix a viewpoint. No amount of cleverness applied to a picture
of an object standing behind another object produces the side-on measurement
the next step needs. Solution 3 is chosen alongside solution 2 because it
answers the *other* difficulty, and the two barely overlap.

Solution 3 is the geometric version of the loop: candidate viewpoints filtered
for reach and occlusion, scored by a rule. Solution 5 is the same loop with a
learned score, and solution 9 is the same loop with the whole thing learned.
Start with the rule. It is auditable, it needs no data, and it is a fair
baseline for deciding whether either of the others is worth its cost.

### Why the verifier is the learned part to add first

Of the six solutions with a learned component, solution 6 is the one to build,
and the reasons generalise beyond this problem.

**It learns the one thing the rules are worst at**, rather than replacing
something the rules already do well. The geometry separates almost everything;
what it handles badly is the ambiguous cluster.

**Its input is small and structured**, so the model is small. A handful of
features and a gradient-boosted tree trains in minutes on a laptop, which
matters on hardware with no NVIDIA GPU.

**It is a verifier, so its mistakes are cheap.** A wrong verdict costs one more
picture. Compare that with solution 7, where a wrong mask is acted on.

**It degrades to the pure-geometry answer.** Delete the weights file and the
system still runs, a little worse. Very few learned components have that
property, and it is worth a great deal.

**And its most useful output is "I cannot tell"**, which is what turns the whole
thing into a loop. A verifier that only ever says yes or no has thrown away the
information that would have told the arm to go and look again.

Solution 4 sits behind it as the fallback: when the verifier is unsure *and*
another viewpoint has not settled it, a promptable segmenter is a cheap second
opinion that needs no training at all.

### What the three learned solutions are actually for

They are not turned down because they are learned. Each answers a question this
cell does not ask.

**Solution 7** is the answer the day the objects are transparent. Then there is
no depth to cluster and solutions 1 to 6 do not run at all. Its cost here —
weights to keep in step, a training loop in front of every experiment, no
explanation — buys nothing, because a distance comparison already does the job.

**Solution 8** is the answer when objects genuinely hide each other. Here they
stand 150 mm apart and the arm can usually find a clear line of sight, so
predicting the hidden half of an object is machinery aimed at a difficulty that
mostly is not present.

**Solution 9** is the most intellectually satisfying entry on the list and the
hardest to justify. A geometric viewpoint score can be printed, argued with and
corrected. A policy's choice cannot. When a score is computable, prefer the
score.

### What would be built, in order

1. **The clustering and the circle fit** — solution 2. About 25 lines on top of
   what exists, and it fixes the failure that does not announce itself.
2. **The viewpoint filter** — the safety half of solution 3. Reject occluded
   and unreachable poses before asking the planner, and report objects with no
   viewpoint left.
3. **The extra look** — the loop half of solution 3, with a rule for a score
   and a budget of one or two extra looks.
4. **The verifier** — solution 6, once a run has been scored and the numbers
   say the ambiguous cluster is a real share of the failures. Not before.
5. Nothing else, unless the objects change.

Steps 1 to 3 are programmed. Step 4 is where a model earns its place, and the
order is the point: **measure which failure you actually have before choosing a
component to fix it.**

### How it would be known to work

The simulator writes down every object it spawned — a file the report may read
and the arm may not. So the numbers are all available:

- **merged**: two real objects reported as one. Watch this hardest; it is the
  failure that looks plausible downstream.
- **split**: one real object reported as two. It looks wrong immediately, so it
  is the safe direction to be wrong in.
- **position error** per object, against the truth.
- **extra looks spent**, and how many of them changed the answer. A loop whose
  extra looks never change anything is a loop worth deleting.
- **no viewpoint**: objects handed on to problem 3, which is a result rather
  than a failure.

---

## Where the chosen solution can fail

**Glasses that genuinely touch still cluster into one.** Distance separates them
only where there is distance. The circle fit notices — a footprint too wide for
one glass and not resolvable into two — and then there is nothing more this
problem can do. That is the handover to [problem 3](../problem-3/).

**The circle fit assumes the kind, and problem 4 takes that back.** Across four
kinds the allowed diameter is the union of four ranges, wide enough that a
footprint too wide for a tumbler is an ordinary wine glass foot.

**A glass seen from one station only is reported as doubtful, and may be real.**
Safe direction, and it will sometimes mean a real glass left out of a run.

**Pairing the two pictures of a station gets harder with every glass added.** A
wrong pairing gives a confident position for a glass that is not there. The
height check catches the impossible pairings and not the plausible ones.

**None of it runs on real glassware**, for the reason the decision gives.

← [The problem](problem.md) · [Problem 3 — moving them apart](../problem-3/) →
