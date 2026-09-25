# Solution 9 — self-supervised from the arm's own movement

*Learned, as the decider. The arm knows exactly how it moved the camera, so the
geometry between two pictures of a still scene is a free training signal.*

## In one paragraph

Teaching a network which pixels belong to which glass normally needs somebody
to draw round every glass in every picture. This solution needs nobody. The
camera sits on the wrist, so the arm knows exactly how far it moved between two
pictures, and geometry then says where each surface point must land in the
second. Points on one glass move together; points on the glass behind move by a
different amount. That agreement is the label. It comes from the joint
encoders, not from a human and not from the simulator, so the same training
would run on real hardware.

## The problem this solves

Four to six glasses stand on the table. They are all one kind, and the kind is
known. The arm has to say which pixels belong to which glass, give each glass a
position on the table, and name honestly any pair it could not separate.

The difficulty this document is about is not seeing the glasses. It is telling
one from another. Two glasses standing 150 mm apart on the table can land on
top of each other in a photograph if the camera happens to be in line with
both, and then the usual method — take every pixel standing above the table
top, and group the ones that touch — returns a single blob. One blob means one
glass to everything downstream, and that mistake does not announce itself.

A learned method could in principle draw the boundary that the touching-pixels
rule cannot. But a learned method has to be trained, and training needs the
right answer written beside each example. Those right answers are the
**labels**, and getting them is where most of the cost of a learned method
lives.

![Three ways to get the right answer written beside each picture](../../images/problem-2/09-where-the-labels-come-from.png)

Look at the three columns. The first is the usual recipe: a person draws round
every object, thousands of times. The second is what the other two learned
solutions in this set do — Gazebo already knows which mesh each rendered pixel
came from, so the labels are free. The third is this solution, and the thing to
notice is that its supervision does not come from inside the simulator at all.
It comes from the joint encoders, which a real arm also has.

That difference is the reason this solution is in the document. Everything else
learned here would have to be retrained from scratch, with new labels, the day
the code met a real camera. This one would not.

## The idea, in plain words

Take a picture. Move the camera sideways by a known amount. Take another
picture. Nothing in the scene moved, so the two pictures show the same surfaces
from two places.

Because the scene held still, the two pictures are not two unrelated pictures.
Every surface point in the first has exactly one correct place in the second,
and where it lands depends on only one unknown: how far away it is. Near
surfaces swing a long way across the image. Far surfaces barely move. That
effect is called **parallax** — the same thing that makes a fence post fly past
the window of a train while a distant hill hardly shifts.

![The scene stands still; only the camera moves](../../images/problem-2/09-two-views-parallax.png)

Look at the two frames on the right. Glass A, the nearer one, moves 66 pixels.
Glass B, 150 mm further away, moves 51. The gap between them in the picture
grows by 15 pixels, and that growth is the only thing in the two pictures that
says they are two objects: they are the same kind, the same colour and the same
shape, so appearance says nothing at all.

The useful part is that **every pixel of glass A moves by the same 66 pixels**,
and every pixel of glass B by the same 51. The Gestalt psychologists — the
early-twentieth-century school that studied how people group what they see —
gave that a name: **common fate**. Things that move together are read as one
thing. A flock of birds is one flock because the birds turn together. Here the
glasses are not moving, but the camera is, and relative motion is relative
motion: from the camera's point of view the whole scene slides past, and each
object slides at its own rate.

So: pixels that move together belong together. No human said so. Geometry did.

## Where it comes from

Three separate lines of work meet here, and it is worth knowing which is which.

**Supervised learning** is the default. Each training example carries a right
answer written beside it, by a person. The network is nudged until its output
matches. It works, and its cost is the writing.

**Self-supervised learning** removes the person. The right answer is computed
from the data itself, using something already known to be true. The usual
examples elsewhere are hiding part of a sentence and training a network to
guess the missing word, or hiding part of an image and training it to fill the
hole: in both cases the answer was in the data all along. Here the known truth
is not a hidden word. It is geometry — specifically, that a rigid scene
photographed from two known poses obeys a constraint that has no free
parameters in it.

**Motion segmentation** is the classical form of the grouping idea: split an
image into regions by how the regions move. Layered models of moving scenes go
back at least to Wang and Adelson's *Representing Moving Images with Layers*
(1994 — confident of the paper's existence and its subject, less so of its
details, so treat any specific claim about it as uncertain). Classical motion
segmentation assumes that the *objects* move. Here they do not, which matters
and is dealt with below.

**Self-supervised depth and ego-motion learning** is the nearest living
relative. SfMLearner ([Zhou et al., CVPR 2017](https://github.com/tinghuiz/SfMLearner),
MIT licence) trains two networks together from unlabelled video: one guesses
the depth of every pixel, the other guesses how the camera moved between
frames. Neither has a label. They are trained against each other, by warping
one frame into the next and checking whether the brightness lines up.
Monodepth2 ([Godard et al., ICCV 2019](https://github.com/nianticlabs/monodepth2))
refines the recipe, under **Niantic's own non-commercial licence** — usable for
reading and for research, not for a product.

Those methods have to *estimate* the camera's motion, and that estimate is
where a large part of their error lives. **Here the camera motion is not
estimated. It is commanded.** The camera is bolted to the wrist, the joint
encoders report where the wrist is, and the arm chose the move in the first
place. Half of the hard problem in that literature simply does not exist in
this cell.

The last ingredient is **contrastive learning**, which is how the grouping gets
turned into something a network can output. SimCLR ([Chen et al.,
2020](https://arxiv.org/abs/2002.05709)) and MoCo ([He et al.,
2019](https://arxiv.org/abs/1911.05722)) are the standard references. Both
train on whole images rather than pixels, but the loss is the same shape, and
it is a dozen lines of code rather than a library.

## How it works, step by step

### 1. What the network is asked to produce

Not a class. Not a box. An **embedding**.

An embedding is a short list of numbers attached to something, arranged so that
*distance between the lists means similarity*. If two things get lists that are
close together, they are alike; if the lists are far apart, they are not. The
numbers themselves mean nothing on their own — only the distances matter.

Here the network takes one 320 by 240 picture and returns, for every pixel, a
list of perhaps 16 numbers. Two pixels on the same glass should get lists that
point nearly the same way. Two pixels on different glasses should get lists
that point apart.

![An embedding: every pixel becomes a point](../../images/problem-2/09-embedding-space.png)

Look at the right-hand panel. Every pixel of the picture has become one point.
The pixels of the blue glass have landed in one clump and the pixels of the red
glass in another. Nothing in that picture names a glass, and nothing counts
them — the box on the far right says so, and it is the honest limit of the
method, returned to later.

### 2. Where the training pairs come from

For any pixel in picture 1, the arm knows the camera's pose for both pictures.
If it also knew that pixel's depth, it could say exactly which pixel of picture
2 shows the same speck of glass. Depth is the one unknown.

So the network is given a second job: predict a depth for every pixel. Then:

1. Take picture 1 and the predicted depths.
2. Using the known camera motion, **warp** picture 1 into the viewpoint of
   picture 2 — that is, move every pixel to where the predicted depth says it
   should now be.
3. Compare the warped picture with picture 2, pixel by pixel, on brightness.

Where the warp lands on matching brightness, the predicted depth was right.
Where it does not, it was wrong, and the mismatch is what the training pushes
down. This is the **photometric loss**, and it is the whole of the supervision:
two pictures and two encoder readings. Nothing else.

Once depth is roughly right, the apparent shift of each pixel is known, and the
pairs fall out:

- two pixels whose shifts agree, to within the measurement noise, are a
  **positive pair** — they are on the same surface;
- two pixels whose shifts differ by clearly more than the noise are a
  **negative pair**.

### 3. The contrastive loss, in words

Pick a pixel — call it the anchor. Take its positive partner, and take a
handful of negatives chosen from elsewhere in the picture. Look at the
distances from the anchor to each of them in the embedding space.

The loss is low when the positive is nearer to the anchor than every negative
is, and high when some negative has crept in closer. Training therefore does
two things at once, and they are the two arrows in the diagram above: it
**pulls** the anchor and its partner together, and it **pushes** the anchor and
its negatives apart.

There is nothing in that recipe about glasses, or about how many there are. It
only ever says *these two belong together, those two do not*. That is exactly
what the geometry can certify and exactly the limit of what it can certify.

### 4. What comes out

At run time, one picture goes in, and a 16-number vector per pixel comes out.
Pixels are grouped by clustering those vectors. Each cluster is a candidate
region, and every candidate region is then handed to the ordinary arithmetic —
turn the pixels into points on the table using the depth camera, fit a circle,
and reject the region if its diameter is not one this kind of glass could have.
The network proposes; the arithmetic decides.

## How it works here

### The data already exists

Every survey station already takes two pictures 120 mm apart. A picture costs
milliseconds and an arm move costs seconds, so taking five pictures along that
120 mm slide instead of two costs almost nothing, and gives ten pairs per
station rather than one. A few hundred spawned scenes then give tens of
thousands of training pairs, and every one of them is labelled by the encoders.

### The arithmetic of the signal

One formula carries this whole solution. A surface at depth *z* moves across
the image by

    shift in pixels = slide in millimetres x 277.1 / depth in millimetres

where 277.1 is this camera's focal length in pixels, quoted in the cell's
specification for both axes. For the survey's 120 mm slide, the numerator is a
fixed 120 x 277.1 = **33,252**, so the shift is 33,252 divided by the depth in
millimetres.

What matters for separating two glasses is not either shift but the
**difference** between them.

![Apparent shift against depth, and separation against slide](../../images/problem-2/09-depth-against-shift.png)

The left-hand plot is that formula, drawn. Two things to take from it. First,
the curve is steep at close range and flat far away: the same 20 mm of depth
difference is worth far more separation near the camera than far from it.
Second, the marked pair at 500 and 520 mm is the hard case — two glasses almost
the same distance away come out only 2.6 pixels apart, which is the width of a
couple of pixels of noise.

The right-hand plot is the part that makes this a usable method rather than an
observation. Separation is **linear in the slide**. Double the slide, double the
separation. That turns the arm into a dial.

### Two stations, two sets of depths

The cell has two kinds of viewpoint, and they sit at different ranges, so the
arithmetic lands differently at each.

**The survey station** puts the camera 450 mm above the table looking down. The
table top is therefore 450 mm away and shifts 33,252 / 450 = 73.9 pixels. The
rim of a 200 mm glass is 250 mm away and shifts 133.0 pixels. The rim of a
100 mm glass is 350 mm away and shifts 95.0 pixels. Three surfaces, three
clearly different rates: 74, 95 and 133 pixels. At this range the signal is
generous.

**The side-on station** puts the camera 380 mm back from a glass, level, 120 mm
above the table. Glasses then sit at roughly 380 to 650 mm, and a second glass
in line behind the target is the merge this problem exists to prevent. At
500 mm and 650 mm the shifts are 66.5 and 51.2 pixels — 15.3 pixels apart,
which is plenty. At 500 mm and 520 mm they are 66.5 and 63.9 — 2.6 pixels
apart, which is not.

### The cost of the slide

There is a price, and the same formula gives it. A big slide moves everything a
long way across a 320-pixel-wide frame, and things fall off the edge.

At the survey station, the table plane shifts 73.9 pixels for the standard
120 mm slide, so the two pictures still share 320 − 74 = 246 pixels of width,
about 77 per cent. Slide 375 mm and the table shifts 231 pixels, leaving only
89 pixels in common — under a third of the frame, and the near rims, which
shift furthest, would already be gone.

So a long slide is not free, and it is not unlimited. Past a couple of hundred
millimetres the camera has to be re-aimed to keep the pair in view, and
re-aiming adds a rotation. That is not fatal: the rotation is commanded too, so
it can be warped out exactly before the shift is measured. But it is extra
machinery, and past a few hundred millimetres the honest answer is that this
has stopped being one station with a long slide and become a second station
somewhere else — which is the job of the *move the camera* solution, not this
one.

## A worked example

A survey station 450 mm above the table returns one blob. Its pixels span 164
columns, which at the table plane, where one pixel is 1.6 mm, is 262 mm across.
No glass of this kind has a footprint wider than 105 mm. So the blob is not one
glass. It is two, standing in line from where the camera happened to be.

The station's second picture was taken 120 mm along. Run both through the
network:

- the pixels of the near glass, whose rim is 250 mm from the camera, shift
  33,252 / 250 = **133.0 pixels**;
- the pixels of the far glass, whose rim is 350 mm away, shift
  33,252 / 350 = **95.0 pixels**;
- the table between and behind them, at 450 mm, shifts
  33,252 / 450 = **73.9 pixels**.

Three populations, 38 and 21 pixels apart. The network was fitted so that
pixels whose shift agrees share an embedding direction, so those three
populations land in three places in the embedding space. Clustering returns two
glass regions and the table.

The boundary between the two glass regions runs where the shift changes — along
the silhouette of the near glass where it crosses the far one. That is an
**occlusion edge**, not a brightness edge, so the fact that the two glasses are
identical in colour costs nothing at all. This is the point of the whole
method: it draws a line that no brightness-based rule could see.

Both regions then go through the ordinary check. Their pixels become points on
the table, a circle is fitted to each, and each is accepted only if its diameter
lands inside the 45 to 105 mm range this kind of glass can have. Two plausible
circles: two glasses, reported. One implausible circle: the region is rejected
and the pair is reported as unseparated, which is a result the problem
explicitly asks for.

## The feedback loop

This is where the solution is at its best, and it is worth being precise about
why.

Most learned components answer whatever they are asked and give no useful sign
when they should not have. This one does, because the doubt has a number
attached: **the separation, in pixels, between two candidate populations of
shifts.** If that number is 38, the answer is settled. If it is 2.6, it is not.

And because separation is linear in the slide, the arm can work out exactly how
far it must move to make a specific doubtful pair unambiguous.

![The deliberate-motion loop, with the millimetres on it](../../images/problem-2/09-deliberate-motion-loop.png)

Follow the four boxes. The arithmetic in the second one is the whole idea. For
the 500 and 520 mm pair, each millimetre of slide buys

    277.1 x (1/500 - 1/520) = 277.1 x 0.0000769 = 0.0213 pixels

so three pixels of separation needs 3 / 0.0213 = **141 mm** of slide, and eight
pixels needs 8 / 0.0213 = **375 mm**.

For the tighter pair at the survey station — two glasses whose rims are 250 and
260 mm from the camera, a 10 mm difference in height — each millimetre buys

    277.1 x (1/250 - 1/260) = 277.1 x 0.0001538 = 0.0426 pixels

which is twice as much, because close range is where the curve is steep. Eight
pixels there needs only 188 mm — though, as the next list says, 188 mm at that
range is already far enough to push a centred glass out of the frame.

That is a measurement chosen to settle one named doubt. The arm is not taking
another picture and hoping. It has priced the answer, in millimetres, before it
moves. Compare that with a method whose response to an unclear case is to run a
bigger network on the same picture: the information was not in the picture, and
no amount of computing will put it there.

Three practical limits on the loop, all of them arithmetic rather than opinion:

- **The frame.** A glass in the middle of the picture reaches its edge once it
  has shifted 160 pixels, which takes a slide of 160 x 250 / 277.1 = 144 mm at
  the survey station's near range, and 160 x 500 / 277.1 = 289 mm at the
  side-on station. Both of the slides worked out above — 188 mm and 375 mm —
  are past that, so neither can be a plain sideways slide. The camera has to be
  re-aimed to keep the pair in view, and the rotation warped out afterwards,
  which is exact because the rotation is commanded too.
- **The reach.** The glasses stand in a zone 320 by 360 mm, and the arm's
  comfortable reach is 300 to 780 mm from its base. A 375 mm slide is wider
  than the object zone, and there are places on the table from which it simply
  cannot be made.
- **The budget.** An arm move costs seconds; running the network costs
  milliseconds. So the loop must stop, and the rule is to stop when nothing is
  unclear or the budget is spent, reporting whatever is still doubtful. A pair
  the arm could not separate is a result this problem asks for, not a failure.

## What it needs

- **[PyTorch](https://pytorch.org/)**, BSD-3-style licence
  ([text](https://github.com/pytorch/pytorch/blob/main/LICENSE)), running on
  Apple's MPS backend. No CUDA, and no compiled custom kernels.
- **[Gazebo Harmonic](https://gazebosim.org/)**, Apache-2.0, to render a few
  hundred scenes.
- **[NumPy](https://numpy.org/)**, BSD-3, for the projection arithmetic.
- **Data**: pairs of pictures from each station, with the joint encoder reading
  logged beside every picture. That is all. No masks, no per-object labels, no
  spawn record.
- **No pretrained weights.** Nothing is downloaded and nothing was fitted to
  real photographs, so nothing here fails the rule that everything must be
  buildable inside the simulator on a machine with no NVIDIA card.
- **Time**: hours rather than days, for a small network on 320 by 240 pictures
  of one kind of object under one lighting setup. The exact figure is uncertain
  until it is run.

The simulator's record of what it spawned is used to **score** the result. It is
never used to train it. That distinction is the whole point of this solution.

## What it is good at

**It learns a boundary nobody can write down.** The line between two identical
overlapping glasses is not a brightness edge and not a corner. It is an
occlusion edge, and it is exactly what a shift-based grouping sees.

**Its labels are free and endless.** Every pair of pictures the arm has ever
taken is a training example. There is no annotation step to fall behind.

**It is indifferent to colour and texture.** Two glasses of the same colour are
no harder than two of different colours, because colour was never the signal.

**It would transfer to hardware unchanged.** A real UR5e has joint encoders and
a wrist camera. The supervision this method needs exists there too, so the same
training loop would run on a real cell without anyone drawing a single mask.
None of the other learned solutions here can say that.

## What it is bad at

![Where the signal runs out](../../images/problem-2/09-the-limit.png)

**Nothing in this scene moves except the camera.** The glasses stand still, so
the only differential signal available is parallax, which is a function of
depth alone. What the network learns, stripped of the vocabulary, is a
depth-discontinuity detector wearing an embedding's clothes. That is genuinely
useful, and it is much less than the phrase "self-supervised object
segmentation" suggests.

**Two glasses the same distance away separate by nothing.** The left-hand panel
above is the whole argument: the 0.0213 pixels per millimetre came from the
depth gap, and if the depth gap is zero, so is the separation, at every
baseline. Appearance cannot break the tie, because the glasses are one known
kind and look identical.

**It returns affinity, not a count.** The right-hand panel says it: the network
only ever says *these two pixels are alike, those two are not*. It never says
"four glasses". Something downstream must still cluster the vectors and choose
how many groups there are, and choosing too few is the merge all over again.

**The cell already has a depth camera.** This is the awkward one. The depth
camera measures the thing parallax is being used to infer, directly and without
training. In this cell, on opaque glasses, clustering the depth readings in
millimetres is simpler, needs no model file, and works on the first frame.

## How it fails

**Identical objects at equal range.** Two glasses 20 mm apart in depth give
2.6 pixels at the survey slide. Two glasses at the same depth give nothing at
all. There is no appearance cue to fall back on.

**Textureless surfaces.** The photometric loss works by checking whether the
warped picture lines up with the real one, and that check needs brightness
variation to grip. A flat, evenly lit surface looks the same wherever the warp
puts it, so the depth it implies is unconstrained and the training signal is
weak exactly where the glasses are plainest.

**Staleness.** Change the lighting, or the kind of glass, and the embedding is
describing a cell that no longer exists — while every unit test still passes,
because the tests do not know about lighting.

**Confidence where it is wrong.** A merged pair comes back as one tidy region
with no complaint attached. That is the failure `problem.md` says to watch
hardest, and the reason the circle-fit check downstream is not optional.

## When it would be the right choice

Not here, and the reason is the depth camera. When depth is measured directly,
inferring it from parallax with a trained network is work being done twice, and
the simpler of the two answers should win.

It becomes the right choice in three situations, all of which are one step away.

**When the objects are not of one known kind.** That is problem 4. An embedding
that says *same or different* without naming anything is precisely what is
wanted when the catalogue of things on the table is open.

**When labels are impossible rather than merely expensive.** With identical
overlapping objects, the boundary a human would draw is a guess as well. A
geometric constraint is a better teacher than a guessing human.

**When the depth reading fails.** Real glassware is transparent, and a
structured-light or stereo depth camera returns very little from it. On that
day, the clustering-in-millimetres approach has nothing to cluster, and this is
one of the few methods here that could still be trained, because its
supervision is the arm's own motion rather than the depth image. Whether a
photometric loss survives a transparent surface — where the brightness seen
through the glass belongs to whatever is behind it — is uncertain, and would
have to be tried.

## Where it sits

It competes with *a segmenter trained from scratch* and *per-pixel votes for
the centre*: all three are learned deciders trained inside the simulator, and
this is the only one of the three whose supervision would survive outside it.
It leans on *cluster on the table*, which turns its proposed regions into
circles on the table and rejects the implausible ones, and its feedback loop is
the same loop as *move the camera* — with the difference that this one can say,
in millimetres, how far the camera has to go.
