# Solution 9 — a fine-tuned instance segmenter

*Learned, with the model as the decider. A standard instance segmentation
network arrives already fitted to a large collection of everyday photographs,
and its training continues on this cell's own pictures with one class, so that a
picture goes in and one mask per glass comes out.*

> **The cell is described once, in [the cell](../../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to answer problem 2 with a model that already
produces the exact kind of answer the problem asks for. Problem 2 asks which
pixels belong to which glass, and the name for that question in the wider field
is **instance segmentation**: not "where is there glass" but "here is glass
number one, and here, separately, is glass number two". There is a standard
model for that question, and it is called **Mask R-CNN**. The version used here
is torchvision's `maskrcnn_resnet50_fpn_v2`, and it arrives with its weights
already fitted to COCO, a large collection of labelled photographs of everyday
objects.

Because the model arrives fitted, the work here is not to train it but to
**continue** training it. That is called **fine-tuning**, and it means keeping
the numbers somebody else arrived at and nudging them on this cell's own
pictures, with the list of classes cut down to a single one, "glass". The
simulator supplies those pictures and their labels for nothing, so the training
set costs only the time it takes to render.

What that buys is the most direct answer in this folder. A picture goes in, and
a list comes out in which each entry is one glass, with a box round it, a score
saying how sure the model is, and a mask marking its pixels. There is no
grouping distance to choose, no circle to fit before the glasses can be counted,
and no rule saying how close two points have to be to belong together. Two
glasses whose outlines join come back as two entries, because each is built
separately.

What it costs is that the answer rests on a file of weights rather than on
arithmetic anyone can read, and that most of those weights were fitted to
photographs of a world this cell does not contain.

By the end you will understand what instance segmentation is and why a map of
classes cannot do its job, how Mask R-CNN splits the work into proposing regions
and then examining each one, what a backbone is and what it means for one to
arrive already fitted, why fine-tuning needs far less data than a random start
and what knowledge really carries over when the borrowed pictures are
photographs and the new ones are shaded depth, why two proposals covering one
glass collapse into one answer, and exactly where this family of methods stops.

## The problem this solves

Four to six glasses stand on the table. They are all the same kind, the kind is
known, and they are solid, so the depth camera reads them. The job is to say
which pixels belong to which glass, to give each glass a position on the table,
and to give each a rough footprint width. What makes that hard is taken in four
short steps below: how a picture joins two glasses together, what each of the
two answers already on offer pays to get round that, and the one difficulty none
of them can touch.

### In the picture, two outlines join

If the camera is roughly in line with two glasses, the near one covers part of
the far one and their two outlines meet. From the top the same thing happens for
a different reason: a glass's outline is thrown outwards away from the point
directly below the camera, and the taller the glass the further out it goes.
This project calls that outward stretch **splay**. Because the kind here spans a
small tapered glass at one end and a large one at the other, two glasses a
normal distance apart can have outlines that overlap once splay has stretched
them.

A **mask** is a picture the same size as the photograph in which every pixel
holds nothing but yes or no, where yes means "this is glass". When two outlines
meet, the yes pixels of the two glasses form one joined region, and the usual
way of turning a mask into objects — spread out from a yes pixel to every yes
pixel touching it, and call everything reached one object — returns one object
where there are two. That spreading answers only the question *are these pixels
joined?*, and joined is precisely what the two outlines are.

### On the table, two glasses can be too close to group apart

[Cluster on the table](../programmed/02-cluster-on-the-table.md), solution 2,
avoids the picture entirely. Every pixel with a depth reading becomes a point in
the room, the points standing clear of the table are kept, and points closer
together than a chosen **grouping distance** go into one group. That one
distance has to satisfy two demands at the same time. It must be larger than the
biggest hole inside one glass's own points, or one glass comes back as two, and
it must be smaller than the strip of bare table between two glasses, or two come
back as one. At the spacing this cell guarantees there is room between those two
limits, so the choice is comfortable. However, it still has to be made and
justified, and it is a number the person setting the cell up owns for ever.

### A class map cannot say which glass

[A network trained from scratch](06-a-network-trained-from-scratch.md), solution
6, replaces the arithmetic with a small network whose first head answers a
question about classes: is this pixel glass, or is it table? That head cannot
answer problem 2, because a label that is the same everywhere cannot mark a
boundary. Every pixel of two joined glasses carries the value "glass", so there
is nowhere in the output for the information "and this half is a different glass
from that half" to live.

### The difficulty none of these can touch

The hardest difficulty is that a glass can be missing from the picture
altogether. Because a tall glass's splayed outline can cover a short glass
completely, the short glass produces no pixels, and no method that reads pixels
can find it. The section [when the glasses are completely
hidden](#when-the-glasses-are-completely-hidden) works out exactly why and says
which solutions do answer it.

## The main idea

The main idea is to stop building the separating step and to borrow a model
whose output is already separated.

Mask R-CNN does its work in two stages, and the shape of those two stages is the
whole reason its output can hold separate objects. The first stage looks over
the picture and **proposes regions**: rectangles that might contain an object,
with no claim about what the object is. The second stage takes each proposed
rectangle on its own, decides what class of thing is inside it, tightens the
rectangle round it, and paints a mask of the object's pixels **inside that
rectangle only**.

The important word is *inside*. Because the mask for one object is predicted
within that object's own rectangle, the question "which glass does this pixel
belong to" never has to be asked. Each answer was built in its own frame from
the beginning, so two glasses whose pixels touch in the picture produce two
rectangles and two masks, and the masks are allowed to overlap without anything
being confused.

![A class map labels every pixel glass or table and merges two joined glasses
into one region, while an instance segmenter returns one separate mask per
glass](../../../../images/problem-2/09-class-map-against-instances.png)

The left panel of that picture is what a class map returns for two glasses whose
outlines meet, which is one region, and the right panel is what this solution
returns, which is two masks that happen to overlap. Only the second is an answer
to problem 2.

The second half of the main idea is where the numbers come from. Mask R-CNN is
large, and training something that size from random numbers would need a great
many labelled pictures. It does not have to be, because the weights that ship
with it were already fitted to COCO, and training continues from those weights
on this cell's pictures with the class list cut to one class. That is
fine-tuning, and it is why a model of this size is reasonable on a laptop.

## The picture the model is given

Before going further, one fact about this cell has to be stated, because every
later section depends on it and it is the single largest risk in this solution.

**The cell's renderer does not produce colour.** What it produces is a depth
reading for every pixel, meaning how far away the surface at that pixel is, and
a glass identity for every pixel, meaning which glass the surface belongs to.
The second of those is what makes the training labels free. The first is the
only picture there is.

Mask R-CNN expects an ordinary colour photograph, with three channels of red,
green and blue. So the code builds one: it shades the depth reading into a grey
value, so that near surfaces come out at one end of the range and far surfaces
at the other, and repeats that single grey channel three times to make the three
channels the model wants. The result looks like a black and white photograph.

That is a genuine difference from the pictures the weights were fitted on, and
it is not a difference in the *shape* of the input, because the shape is exactly
what the model expects. It is a difference in the **statistics** of the input:
real photographs have colour that varies between the channels, edges from paint
and print and shadow as well as from geometry, and texture inside every surface.
A shaded depth picture has none of that, its edges are all geometric, and its
three channels are identical. The name for that kind of difference is the
**domain gap**, meaning the gap between the world a model was fitted on and the
world it is asked to run in.

One thing reduces the risk, and it is the whole reason this solution is worth
writing. Fine-tuning does not merely use the borrowed weights; it **continues
training them** on the pictures the model will really see. So the grey pictures
are not an unfamiliar input the model has to survive at run time. They are the
input it is fitted on. The domain gap therefore costs accuracy and training
effort rather than costing correctness outright, and [what knowledge is actually
being reused](#what-knowledge-is-actually-being-reused) works out how much of
the borrowing survives.

## The two stages

With the input settled, the two stages can be taken in order, and the reason
there are two of them is a general principle rather than a detail of this model.
Asking "where are all the objects" in one step over a whole picture has an
answer of no fixed length and no fixed positions, which is awkward for a network
whose output is a fixed block of numbers. Asking "what is inside this one
rectangle, and which of its pixels belong to the object" has a fixed-size
answer, which a network handles comfortably. So the work is split: one stage
turns the open question into a list of rectangles, and the other answers the
easy fixed-size question once per rectangle. That split is what the R-CNN family
of models is built around.

![Stage one slides over the picture and proposes many rectangles that might hold
an object, and stage two cuts each rectangle out, classifies it, tightens it and
paints a mask inside it](../../../../images/problem-2/09-the-two-stages.png)

### The first stage: proposing regions

The first stage is called the **region proposal network**. It slides over the
picture and, at every position, asks a small pair of questions about a set of
fixed reference rectangles centred there. Those rectangles are called
**anchors**, and they come in several sizes and several ratios of width to
height, so between them they cover the shapes an object might have.

The two questions asked of each anchor are simple. The first is whether the
anchor contains an object of any kind, or background — not which class, so the
first stage knows nothing about glasses and does not need to. The second is how
the anchor should be shifted and resized to sit more tightly round what is in
it.

The output is therefore a long list of rectangles with a rough score each, cut
down to the best few before the second stage sees it. Those survivors are the
**proposals**, each a guess saying only "something is here, roughly this big".

One property of that design matters a great deal here. **The proposals are
produced independently of one another.** Two glasses whose outlines meet sit at
different positions, so different anchors fire on them and two proposals come
out. Nothing has to notice a seam and nothing has to decide where to cut,
because nothing ever considered them as one thing.

### The second stage: classify, tighten and mask

The second stage receives those proposals one at a time and produces three
things for each.

The first is a **class**, chosen from the model's class list plus a background
option. Here the list has one entry, "glass", so the choice is between glass and
background, which means the second stage's real job in this cell is to throw
away the proposals that landed on bare table.

The second is a **tightened rectangle**. The proposal was a shifted anchor and
is only roughly right, so the second stage predicts a further adjustment, using
the much better look it gets at the region's own contents.

The third is a **mask**, and this is where instance segmentation happens. The
second stage predicts, for a small grid covering the rectangle, whether each
cell of that grid is part of the object or not. That grid is then stretched back
up to the size of the rectangle and dropped into place in the full picture, so
it is a statement about one object inside one rectangle.

One piece of machinery is worth naming, because it is what makes the mask
accurate. Cutting a rectangle out of the model's internal picture means reading
values at positions falling between whole pixels, and rounding those positions
shifts the cut slightly. That hardly matters for deciding a class and matters a
great deal for a mask, so Mask R-CNN blends the neighbouring values rather than
rounding, an operation its authors named **RoIAlign**. The lesson generalises:
**a step whose error is tolerable for one output can be the dominant error for
another.**

## The backbone, and what it means for one to arrive fitted

Both stages look at the picture, and neither looks at the raw pixels. They look
at what a shared part of the model has already made of it, and that shared part
is called the **backbone**.

A backbone is the part of a vision model that turns a picture into a stack of
**feature maps**. A feature map is a grid, smaller than the picture, in which
every position holds not a colour but a list of numbers describing what is in
that part of the picture: whether there is an edge and which way it runs,
whether there is a corner or a repeating texture, and at deeper levels whether
there is something that looks like a rim. Nobody decides what those numbers
mean; they are whatever training found useful.

The backbone here is a **ResNet**, a stack of convolutions arranged so that each
block adds a correction to what came before it rather than replacing it. A
**convolution** takes a small square window, slides it over its input, and at
each position multiplies the values in the window by a fixed set of weights and
adds them up. Adding corrections rather than replacing is what lets a very deep
stack train at all.

Now the point of this section. **Almost all of this model's weights are in the
backbone, and they arrive already fitted.** The two stages on top are small by
comparison, so what is downloaded is mostly a general-purpose answer to "what is
in this part of this picture", worked out from a large collection of
photographs.

![The backbone turns a picture into feature maps holding edges, corners,
textures and object-like parts, and those maps arrive already fitted from a
large collection of
photographs](../../../../images/problem-2/09-what-a-backbone-brings.png)

Read that picture from left to right: small local things such as edges and
corners first, then larger composed things built out of the level below, and
every level is numbers somebody else's training paid for.

### The feature pyramid

There is a difficulty in using a backbone for detection, and the fix for it is
the other half of this model's name.

The difficulty is that the backbone's levels trade two things against each
other. Each time the grid is halved, one position stands for a larger patch of
the original picture, so the deeper levels know more about context and less
about exactly where anything is. A small object may be visible in the early
levels, where positions are precise, and invisible in the deep ones, where it is
smaller than one position, while a large object is the other way round. So
detection cannot use one level: it needs precise positions for small objects and
broad context for large ones at the same time.

A **feature pyramid network** is the standard answer. It takes the backbone's
levels, starts at the deepest and works back up: at each step it doubles the
deep level's grid, adds it to the matching level from the backbone, and calls
the sum that level of the pyramid. Every level is then the size the backbone
produced it at while also carrying the deep levels' sense of context. The region
proposal network runs on all of them, with small anchors on the fine levels and
large anchors on the coarse ones.

This matters directly here. A glass seen from the top covers a small patch of a
large picture, while a glass seen from the side, at the measuring standoff,
fills much of the frame. One model has to handle both, and the pyramid is why it
can.

## Fine-tuning

The backbone arrives fitted, and this section is about what to do with that:
keep those numbers and carry on training.

**Training** a network means showing it an example, comparing what it produced
against the answer wanted, and nudging every weight in the direction that would
have helped. **Training from a random start** means the weights begin as noise,
so the nudges have to build every part of the model from nothing, including the
parts that only detect edges. **Fine-tuning** means the weights begin somewhere
useful, so the nudges have much less to do.

![Training from a random start has to discover edges, corners and textures
before it can learn anything about glasses, while fine-tuning begins with those
already in place and only has to learn what a glass looks
like](../../../../images/problem-2/09-fine-tune-against-scratch.png)

### Why it needs far less data

The reason is best stated in terms of what the data has to pay for. Every weight
in a model is a number the training data has to determine, and if the data does
not contain enough information to pin a weight down, that weight ends up fitted
to accidents of the particular examples given. That is called **overfitting**,
and it shows as a model scoring well on its training pictures and badly on new
ones. So the data needed grows with the number of weights determined from
nothing, and fine-tuning changes that sum: the great majority of the weights are
already at values that work, so the data only has to adjust them, and the few
that genuinely start from scratch are in the very last layers, where the class
list changed. A training set that would be hopeless for a random start is
therefore comfortable.

There is a second reason, about time rather than data: a random start spends
much of its training discovering that edges matter, that corners matter and that
a smooth gradient is a curved surface, which the borrowed weights already hold.

### What knowledge is actually being reused

Now the honest question, and it is the one that decides whether this solution is
a good idea. The borrowed weights were fitted to photographs of everyday
objects, and this cell's pictures are depth shaded into grey. What carries over
is strong at the early levels and weak at the deep ones, and the reason is what
each level holds.

The early levels hold **edge and gradient detectors**, and an edge is an edge. A
depth picture is full of edges, because a glass's rim against the table behind
it is a large jump in depth and therefore a large jump in grey, and a window
that finds a step from light to dark in a photograph finds the same step here.
Those levels transfer almost entirely, and this is where most of the benefit
sits.

The middle levels hold **shapes and surface arrangements**: curves, corners,
regions that bulge, regions that are flat. These transfer partly. A glass rim in
a shaded depth picture is a smooth closed curve with a gradient across it, and
the middle levels of a model fitted on photographs already describe such curves
— fitted on gradients caused by light rather than by distance, but the geometry
producing the gradient is the same.

The deep levels hold **object-like parts**, and this is where the reuse is
weakest. They were fitted to say things like "this looks like the handle of a
cup", learned from colour and texture as much as from shape, and a shaded depth
picture has neither. So they arrive describing properties the new pictures
largely do not have, and fine-tuning has to move them far.

That gives an honest summary. **The borrowing is worth having and it is worth
less here than the usual advice implies.** What is genuinely inherited is the
machinery of turning a picture into useful local descriptions, which is the
expensive and boring part, and what has to be earned is everything above it. One
consequence is practical: because the deep levels have to move and the early
ones do not, it is reasonable to nudge the early levels gently or not at all
while letting the later parts change freely.

### What the labels here are, and why they cost nothing

The training set is where this cell is unusually fortunate, and it is what makes
fine-tuning practical rather than merely possible.

Mask R-CNN is trained on pictures in which every object is marked with a class,
a rectangle and a mask. In the ordinary case a person draws every one of those
masks by hand, which is why labelled data is the scarce resource in this field.

Here nothing is drawn. The renderer already reports a glass identity for every
pixel, so the mask for one glass is the set of pixels carrying that identity,
the rectangle is the smallest one containing them, and the class is always
"glass". Every label is a selection over an array the renderer produced anyway,
so there is no annotator, no annotator's budget and no annotator's mistakes.

That does not make the training set automatically good. The cell's own rule
keeps glasses a comfortable distance apart, and a set drawn only from that rule
never shows the model a pair that was hard to separate, so the training scenes
have to include pairs standing much closer than the rule allows and pairs whose
outlines overlap heavily after splay, while keeping the ordinary case in
proportion. The principle is worth remembering: **the edge of the specification
should sit somewhere in the middle of the training set**, so that the model has
met worse than it ever will.

## What comes out: boxes, scores and masks

With the model and its training described, this section is about its output,
because the output is three things per object and each does a different job. For
every object it believes in, the model returns a **box**, the tightened
rectangle round the object; a **score**, a number between zero and one saying
how sure the model is that this is a glass rather than background; and a
**mask**, marking the object's pixels inside the box. The three arrive together,
from the same second stage, on the same proposal.

![One glass produces a box, a score and a mask together, and the same three come
out once per object with the masks allowed to
overlap](../../../../images/problem-2/09-boxes-scores-masks.png)

The masks in that picture overlap, and that is not an error. In a class map,
overlapping would be a contradiction, because a pixel can hold only one label.
Here each mask belongs to a different object and says "this pixel is part of
me", so two masks claiming one pixel simply means the near glass covers the far
one there, and nothing has to resolve it for the count to be right.

### What the score is good for

The score is the model's own confidence, produced by the same weights that
produced the mask. So it is not an independent check and must not be treated as
one: a model that is confidently wrong reports a high score, and nothing in the
score could reveal that. What it is genuinely good for is three things.

The first is a **threshold**. Most proposals reaching the second stage are
background with low scores, so keeping only the entries above a threshold is how
the list becomes a list of glasses. Where the threshold sits is a trade: low,
and bare table gets reported as glass; high, and faint glasses are dropped.

The second is **ordering**, so that the most confident glasses are dealt with
first and the doubtful ones last. The third is **triggering another look**. A
glass reported with a score well below the others is exactly the case where a
second picture from a different place is worth the seconds it costs, and the
project already has the loop for that: [move the
camera](../programmed/03-move-the-camera.md) works out where the camera can
stand, and [choosing the next look](04-choosing-the-next-look.md) decides which
of those places earns the trip.

What the score does not tell you is whether the *mask* is right. It is about the
class, so a glass whose mask is cut short by something in front of it can still
be scored highly, because it plainly is a glass. That gap is what [amodal masks
for the hidden part](10-amodal-masks-for-the-hidden-part.md) exists to narrow.

## Overlapping proposals, and how they collapse to one

The output is one entry per object, and this section is about why, because the
first stage does not produce one proposal per object at all.

Recall that the first stage scores a set of anchors at every position. A glass
in the picture does not cover exactly one anchor at exactly one position; it
overlaps several anchors of similar size at neighbouring positions, and all of
them score highly, because all of them really do contain most of the glass.
After tightening, those proposals form a cluster of boxes almost on top of each
other.

![Several proposals land on one glass, they are sorted by score, and each one
overlapping the best by more than the allowed amount is
discarded](../../../../images/problem-2/09-overlapping-proposals.png)

The standard fix is **non-maximum suppression**, and it is one of the few parts
of this model that is plain arithmetic rather than learned. Sort every surviving
box by its score, highest first, and keep the highest. Then measure how much
each remaining box overlaps it, using the ratio of the area the two share to the
area they cover between them, and discard every box whose ratio is above a
chosen amount, because a box overlapping that heavily is describing the same
object. Repeat with the highest-scoring box left, until nothing remains to
consider.

Two things about it are worth noticing. The first is that the overlap ratio is
its only setting, and it is a ratio of areas rather than a distance on the
table, so it does not change with how far away the camera is: unlike solution
2's grouping distance, it is not a length that has to be justified against the
geometry of the cell. The second is where it can go wrong. Non-maximum
suppression assumes heavy overlap means duplication, so where two different
objects genuinely overlap heavily it discards one of them. That case is real
here, because splay can push a tall glass's outline right over a short one's.
The ratio therefore has to be generous enough to survive the cell's worst
legitimate overlap, and the softer variant named under [the general ideas behind
this](#the-general-ideas-behind-this) exists for exactly that difficulty.

## What this solution does not need

Everything above describes what the model does. This short section is about what
it removes, because that is the clearest way to see what is being bought.

**There is no grouping distance.** Solution 2 has to choose one length and
defend it against two opposing demands, and that choice is then a permanent
property of the installation. Here nothing groups points at all. **There is no
circle fit needed to separate anything** either: solution 2 uses a group's
fitted width to notice when a group is really two glasses, which is how a merge
is caught, while here two glasses do not merge into one entry, so nothing has to
be caught after the fact. Nor is there a separate stage turning a mask into
objects, which solution 6 needs because its first head returns a class map.

**There is no rule about how close two points may be.** Nothing here compares
two positions and decides whether they are near enough to belong together. The
only overlap comparison anywhere is non-maximum suppression, and that compares
two *claims about one object*, not two pieces of evidence that might be one
object.

The circle fit is worth keeping for a different purpose. Each reported mask's
pixels back-project to points on the table, and a circle fitted to them gives a
centre, a width and a fit error, so a glass whose fitted width falls outside the
range this kind can be is not believed, whatever its score: **the model proposes
and the geometry disposes.**

## How the concepts fit together

Everything above is one pipeline, and it is worth seeing in order before the
failure cases, because each stage inherits what the last one produced.

A **depth picture** comes out of the renderer and is shaded into a grey picture
with three identical channels, because that is the shape of input the model
expects. The **backbone**, whose weights arrived fitted to photographs and were
then nudged on this cell's pictures, turns that into a stack of **feature
maps**, and the **feature pyramid** mixes the deep levels' context back into the
fine levels so that small glasses seen from the top and large glasses seen from
the side are both described well. The **region proposal network** runs over
every level of the pyramid and returns many **proposals**, each a rectangle that
might hold an object, and **non-maximum suppression** reduces the clusters
describing one glass to one each. The **second stage** takes each survivor,
decides glass or background, tightens the rectangle and paints a **mask** inside
it. What comes out is a list in which each entry is one glass with a box, a
score and a mask. Each mask's pixels are then back-projected onto the table, a
**circle** is fitted to them for a centre and a width, and an entry whose width
is impossible for this kind is refused.

Three things are worth holding on to. The **two-stage shape** is what makes the
output hold separate objects, because a mask predicted inside its own rectangle
cannot be confused with a neighbour's, so the hardest part of problem 2 is
answered by the shape of the output rather than by a step that had to be got
right. The **borrowed weights** are what make a model this size trainable here,
and they are worth less than usual because the pictures this cell renders are
not photographs, so fine-tuning has to close most of the gap and what survives
it is the early, general part of the borrowing. And the **arithmetic check**
keeps the whole thing honest: nothing about the model's confidence may overrule
a measured footprint that no glass of this kind could have.

## When the glasses are completely hidden

A glass can be missing from a picture altogether. It is standing on the table,
it is solid, the depth camera is pointed straight at the part of the table it
stands on, and not one pixel of it comes back. This is the most dangerous
difficulty in the problem, and this solution's answer to it is short and
absolute.

The way it happens from the top is splay. A glass's outline is thrown outwards
away from the point directly below the camera, and the taller the glass the
further out it goes. The kind here has a tall end more than twice the height of
its short end, so a tall glass's outline is stretched much further than a short
one's, and standing the short glass beyond the tall one along the line running
out from the point below the camera lets the tall glass's stretched outline
cover it entirely. From the side it is plainer: the near glass is in the way,
and because it is nearer it is drawn larger, so a glass directly behind it
disappears however far behind it stands.

**A glass with no pixels generates no proposal.** The first stage scores anchors
by what is inside them, and what is inside every anchor covering the hidden
glass's place is the tall glass in front of it and the table around it. Nothing
in that patch of the picture came from the hidden glass, so the anchors there
describe the tall glass, and the second stage receives one proposal, correctly
calls it a glass, and paints a correct mask over the tall glass's pixels.

**Nothing in the output is wrong.** There is no low score, because the one glass
found really is a glass and the model is right to be sure. There is no
impossible fitted width, because the surviving pixels back-project to the tall
glass's own real footprint: splay decides which pixels exist and not where they
land, so every pixel returns to its own true place on the table. Every check
this solution has is a check on something that was found, and there is nothing
to check.

![A glass covered completely produces no pixels, so no anchor sees it, so no
proposal is made and no amount of fine-tuning can create
one](../../../../images/problem-2/09-where-it-stops.png)

**No amount of fine-tuning helps.** This is worth settling exactly, because more
training is the first thing anyone suggests. Take the scene with the hidden
glass and the same scene with that glass taken away: the renderer produces the
same depth picture for both, pixel for pixel. A model is a function of its
input, so no model of any size, trained by any method, can return different
answers for two identical inputs. What differs between the two scenes left no
trace in the input, so this is a fact about the input rather than about the
model.

There is one qualification, and it is the subject of the next solution rather
than a way out of this one. A model *can* be trained to mark the part of an
object that something else is covering, which is called **amodal segmentation**,
and [amodal masks for the hidden part](10-amodal-masks-for-the-hidden-part.md)
does exactly that with this same architecture. However, amodal completion
extends evidence, so it needs some of the glass to be visible to extend from.
With no pixels there is nothing to extend, and a model asked to mark a glass
that *might* be behind this one would be inventing a scene rather than reading a
picture.

So this solution cannot handle the completely hidden case and must hand it on.
What it hands on is not a glass but a region: the part of the table it could not
have seen. Three solutions share that work. Working out the region is arithmetic
on splay and on the glasses that *were* found, and it belongs to [cluster on the
table](../programmed/02-cluster-on-the-table.md), which computes the blind
region for a camera position and reports each part of it large enough to hold a
glass as an unsearched patch. Deciding which of those patches is worth spending
a picture on belongs to [is anything hiding
there](05-is-anything-hiding-there.md), which learns that one judgement from
numbers the geometry has already produced. Moving the camera and taking the
picture belongs to [move the camera](../programmed/03-move-the-camera.md), which
turns a request for a different view into a pose the arm can reach.

This solution contributes the masks those three argue from, and none of the
argument.

## A worked example

Everything here follows from the cell as described and from the pipeline above.

**The scene.** Five glasses of one kind stand on the table. Two of them stand
much closer together than the cell's rule allows, roughly along the line running
out from the point below the camera, so splay stretches the taller one's outline
over part of the shorter one's. In the picture from the top their two outlines
join into one region with no seam along it. The other three stand clear.

**What solution 2 would return.** The two close glasses are near enough that the
chain of points crosses the strip between them, so they come back as one group
spanning both glasses and the gap. A circle fitted to it is far wider than any
glass of this kind can be, so the range check fires — correctly, and on a group
it has no way to divide. The run reports four glasses and one doubtful group.

**What this solution returns.** The region proposal network finds anchors firing
on all five glasses, including both of the close pair, because the two sit at
different positions and different anchors cover them. Non-maximum suppression
reduces each glass's cluster of proposals to the best one, and the second stage
calls each of the five survivors glass rather than background, tightens its
rectangle and paints a mask inside it. The two masks of the close pair overlap
where the taller glass covers the shorter one, and that is allowed.

**Why the hard pair came apart.** Nothing separated them, and that is the point
worth taking away. There was never a joined region for anything to divide,
because the two glasses were separate proposals before either had a mask.

**The check.** Each mask's pixels are back-projected onto the table and a circle
is fitted to them. All five widths fall inside the range this kind allows, so
five glasses are reported, each with a centre, a width and a fit error.

**Now the case this solution cannot answer.** Add a sixth glass, at the short
end of the kind's range, standing beyond the tallest glass along the line
running out from the point below the camera and close enough that the tall
glass's stretched outline covers it completely. The depth picture holds no pixel
of it, so no anchor covering its place holds anything of it, so no proposal is
made and no entry appears. Five entries come back, all correct, all legal, all
confident.

**What the run does about it.** Nothing in this solution's output raises a
question, so the question has to come from elsewhere. The blind-region
arithmetic in solution 2 takes the five reported glasses, works out for each the
wedge of table its own outline could have hidden, and reports any part of that
region large enough to hold the smallest glass of this kind as an unsearched
patch. Solution 5 judges that patch worth a look, solution 3 finds a pose the
arm can reach with a clear line of sight into it, and the arm takes one more
picture. In that picture the sixth glass has pixels, so it has anchors, so it
has a proposal.

## Running it yourself

The code for this solution lives with the other two borrowed-model solutions, in
one folder with one environment, described in
[`problem-2-pretrained/README.md`](../../../../problem-2-pretrained/README.md).

Setting the environment up and fetching the weights is done once:

    make setup

Then fine-tuning and testing are each one command, with the solution named:

    make train SOLUTION=maskrcnn
    make test  SOLUTION=maskrcnn

The machine is an Apple M4 with a ten-core integrated graphics processor and
memory shared between it and the main processor. PyTorch reaches that graphics
processor through its MPS backend, so the code selects MPS when it is available
and falls back to the main processor otherwise; there is no NVIDIA card and no
CUDA here. The shared memory is why a model this size fits at all, because the
graphics processor can use nearly all of the machine's memory.

## What it needs

This is one of the more demanding solutions in this folder to set up, and it is
worth being plain about that before anyone starts.

It needs a **deep learning framework** and the environment to run it in, which
is a large dependency for a cell whose recommended answer is a page of
arithmetic. It needs a **downloaded file of weights**, fetched once by the setup
command; that file is large, it is not something to commit alongside the code,
and the project does not produce it, so it comes from outside and is taken on
trust.

It needs a **training set**, which the renderer produces and labels for nothing,
including the hard arrangements the cell's own rule would never generate. That
is the genuinely cheap part, and it is what makes fine-tuning reasonable here.
It needs **time on the machine**, though far less than a random start would.

And once fine-tuned, it needs **a file of weights kept in step with the world**.
Change the camera, the lighting, the way depth is shaded into grey, or the range
of sizes a kind is drawn from, and the file is quietly out of date in a way no
test of the code will notice. Against all that, what it needs at run time is
modest: one pass over one picture is a fraction of a second, which is nothing
beside the seconds an arm movement costs, so the cost of this solution sits
almost entirely in building it rather than in running it.

## Where it is strong and where it breaks

**It answers the question actually asked.** Problem 2 asks for instances and
this model's output is instances. Every other method here answers a different
question and then adds machinery to convert it, and every piece of that
machinery is somewhere a mistake can be made.

**It separates glasses whose outlines join.** Two glasses that meet in the
picture are two proposals before either has a mask, so there is no joined region
and nothing to divide.

**It has nothing to tune.** There is no grouping distance, no seam threshold and
no rule about how close two points may be. Its two settings, the score threshold
and the overlap ratio, are plain numbers with obvious meanings, and neither is a
length that has to be justified against the geometry of the cell. It also
handles both views with one model, because the feature pyramid lets the same
weights describe a glass that is small from the top and large from the side.

**Its masks stop where the visible pixels stop.** A glass partly covered by
another gets a mask of only the part the camera can see, and this is the
weakness that matters most in practice, because one kind spans a small tapered
glass to a large one and partly hidden glasses are therefore the normal case. A
mask cut short back-projects to an arc rather than a full footprint, so the
fitted circle comes out too small and in the wrong place — and it can still be a
width this kind allows, with a small fit error, so the check meant to catch a
bad measurement passes it. That is a quiet failure, and it is what [amodal masks
for the hidden part](10-amodal-masks-for-the-hidden-part.md) exists to fix.

**It is blind to a glass hidden completely.** No pixels means no proposal, which
means no entry, no low score and nothing to check. That is a fact about the
input rather than about the model, and the section above works it out in full.

**Its answer cannot explain itself.** When a fitted circle is wrong you can
print one number and see why; when this model is wrong you can look at the
picture and guess. Every quantity inside it is a block of numbers with no
meaning anybody assigned, so debugging is a matter of examples rather than of
reasoning, and the arithmetic check wrapped round it is what makes that
tolerable.

**Its weights are a second copy of the world, and most of them came from
somewhere else.** The code says what the cell is; the weights say what the cell
looked like on the day they were fitted, on top of what a large collection of
photographs looked like. Keeping that in step is a maintenance job the
programmed solutions do not have, and the part that came from outside cannot be
regenerated here at all.

**The domain gap is real and it is not removed.** Fine-tuning does fit the model
to shaded depth pictures, so it runs on the pictures it was fitted on, which is
the important thing. What remains is that the borrowing was worth less than the
usual advice implies, because the deep levels arrived describing a world of
texture and colour this cell does not have.

## The general ideas behind this

Nothing here was invented for glassware. Every component is a standard piece of
the modern detection toolkit. What is specific to this cell is only the choice
of one class, the source of the labels, and the shaded depth pictures.

### Region-based detection — propose, then examine

The general idea is to answer an open question by turning it into many closed
ones: rather than asking a network to name every object at once, find regions
that might hold an object and ask a fixed question about each region on its own.
**R-CNN** (Girshick and colleagues,
[arXiv:1311.2524](https://arxiv.org/abs/1311.2524)) did this with an external
region finder, **Fast R-CNN**
([arXiv:1504.08083](https://arxiv.org/abs/1504.08083)) made the examining stage
share one pass over the picture, and **Faster R-CNN** (Ren, He, Girshick and
Sun, [arXiv:1506.01497](https://arxiv.org/abs/1506.01497)) replaced the external
finder with a small network of its own, so that the whole thing became one
model.

It is used wherever accuracy matters more than speed and objects must be
reported individually: inspection, medical imaging, aerial survey and any
counting task. It is rarely right when the answer is needed many times a second
on limited hardware, because examining each region separately costs more than
the one-pass detectors that predict boxes straight from a grid. For more, see
[object detection](https://en.wikipedia.org/wiki/Object_detection).

### Mask R-CNN — a mask inside each region

Add a third output to the examining stage, alongside the class and the tightened
box: a small grid saying which parts of the box are the object. That is **Mask
R-CNN** (He, Gkioxari, Dollár and Girshick, 2017,
[arXiv:1703.06870](https://arxiv.org/abs/1703.06870)), whose authors also showed
that the cut-out step has to read positions between whole pixels by blending
rather than rounding. The variant used here, `maskrcnn_resnet50_fpn_v2`, is the
same design with a modernised training recipe (Li and colleagues,
[arXiv:2111.11429](https://arxiv.org/abs/2111.11429)).

It is used wherever objects of one class touch or overlap and have to be
reported separately: counting cells under a microscope, counting fruit on a
tree, picking parts out of a bin, and exactly this job. It is rarely right when
a class map is all that is wanted, because the region machinery is then pure
cost.

### Feature pyramid networks — every scale at once

A deep backbone produces levels that are precise about position and poor about
context near the input, and the reverse near the output. A **feature pyramid
network** (Lin and colleagues,
[arXiv:1612.03144](https://arxiv.org/abs/1612.03144)) builds a path back from
the deep levels to the shallow ones, adding each deep level into the matching
shallow one, so that every level ends with both properties, and the detector
runs on all of them.

It is used in nearly every modern detector, and it is the standard answer
whenever the objects in a picture vary a great deal in size, which they do here
because the same glass is small from the top and large from the side. It is
rarely necessary when every object is about the same size in every picture,
where one level does the job for less arithmetic.

### Transfer learning and fine-tuning — starting from somebody else's numbers

Take a model fitted on a large general task, keep its weights, replace the last
layers with ones shaped for the new task, and continue training on the new data.
It works because the early layers of a vision model learn things common to all
vision — edges, corners, gradients, textures — and only the later layers learn
things specific to the original task. Yosinski and colleagues
([arXiv:1411.1792](https://arxiv.org/abs/1411.1792)) measured that directly,
showing how transferability falls away with depth, which is the effect described
in [what knowledge is actually being
reused](#what-knowledge-is-actually-being-reused). The weights borrowed here
come from COCO (Lin and colleagues,
[arXiv:1405.0312](https://arxiv.org/abs/1405.0312)), a large collection of
photographs of everyday objects labelled with masks.

It is used whenever labelled data for the real task is scarce, which is almost
always. It is rarely the right choice when labels are free and plentiful and the
new pictures look nothing like the borrowed ones, because then the borrowed
weights bring knowledge of a world you do not have while also forcing your model
to be the size somebody else chose. That is the argument [a network trained from
scratch](06-a-network-trained-from-scratch.md) makes, and this solution takes
the other side of it deliberately, to find out what the borrowing is worth here.
For more, see [transfer
learning](https://en.wikipedia.org/wiki/Transfer_learning).

### Non-maximum suppression — keeping one answer per object

When many overlapping claims describe the same thing, sort them by confidence,
keep the best, discard everything overlapping it too heavily, and repeat on what
is left. The procedure is old and appears wherever detectors do, with an
efficient formulation given by Neubeck and Van Gool (*ICPR*, 2006). A softer
variant, which reduces an overlapping box's score rather than deleting it, is
**Soft-NMS** (Bodla and colleagues,
[arXiv:1704.04503](https://arxiv.org/abs/1704.04503)), and it exists precisely
for scenes where two different objects really do overlap heavily.

It is used in every detector that produces more candidates than objects, which
is all of them, and also in corner finding, peak picking and line detection. It
is rarely right without care in crowded scenes, because it cannot tell
duplication from genuine overlap, and this cell is one of the awkward cases,
since splay can push one glass's outline right across another's.

### Average precision — measuring a detector honestly

A detector's output is a list with scores, so measuring it is not a matter of
counting right answers. The standard measure sweeps the score threshold from
high to low and records **precision**, the share of reported objects that are
real, against **recall**, the share of real objects that were reported. The area
under that curve is the **average precision**, which summarises the whole trade
in one number and so does not depend on where the threshold happens to sit.
Whether a reported object matches a real one is decided by the overlap between
their masks. The form in general use was set out for the PASCAL Visual Object
Classes challenge (Everingham and colleagues, *IJCV*, 2010) and carried into
COCO.

It is used for every detection and instance segmentation benchmark there is, and
it is right whenever a method returns a ranked list and the operating point is
not fixed in advance. It is rarely the right measure on its own here, and the
reason matters: it averages over everything, so a method that finds most glasses
well and misses the rarest and most dangerous case still scores well. The
failure this problem says to watch hardest is a glass that produced no pixels,
and that failure moves this number very little. The lesson is the one solution 6
draws about pixel accuracy: **a score that averages over easy cases will be
optimised by a model that is good at easy cases.** For more, see [precision and
recall](https://en.wikipedia.org/wiki/Precision_and_recall).

## Where it sits among the other solutions

This solution sits between two others that answer the same question with
different amounts of borrowing.

Against [a network trained from scratch](06-a-network-trained-from-scratch.md),
solution 6 builds a small network from nothing on labels the simulator gives
away, and it has to add a separating stage on top because a class map cannot
hold instances. This solution asks for instances and gets them, with no
separating stage. In exchange, solution 6 is a few hundred thousand weights that
can be committed alongside the code and regenerated without thinking about it,
while this is a large downloaded file that cannot be regenerated here. Solution
6's arrows are also a different mechanism, and one that works when two glasses
actually touch, which is the case this solution has not been shown to handle. So
the choice is not "borrowed is better"; it is capability now against a model the
project fully owns.

Against [segment anything, then keep the
glasses](08-segment-anything-then-keep-the-glasses.md), the trade runs the other
way. Solution 8 borrows more and trains less: its segmenter is used exactly as
downloaded and the only thing fitted is a small decision about which of its
proposals are glasses. That needs almost no training data and brings the largest
domain gap of the three, because nothing about the borrowed weights is ever
adjusted to the pictures this cell renders. This solution trains more and so
fits its weights to the actual input, which is why its domain gap costs accuracy
rather than correctness. If the question is how little training one can get away
with, solution 8 wins; if it is which of these has actually seen this cell's
pictures, this one does.

Against [cluster on the table](../programmed/02-cluster-on-the-table.md), the
comparison is the one every learned solution here faces. On any day the depth
readings work, solution 2 is better in almost every way that matters: it is a
page of arithmetic rather than a file of weights, it needs no training set, it
explains its own failures, and it can say where it has not looked. This solution
needs depth too, because depth shaded into grey is the only picture the renderer
makes, so it buys no independence from the depth camera. What it does buy is
that no length has to be chosen and no merge has to be caught after the fact.

And what none of them can do is notice a glass absent from the picture. That
failure is answered by geometry rather than by appearance: [cluster on the
table](../programmed/02-cluster-on-the-table.md) works out where a glass could
have been hiding, [is anything hiding there](05-is-anything-hiding-there.md)
decides which hiding place is worth the trip, and [move the
camera](../programmed/03-move-the-camera.md) turns that into a pose the arm can
reach. This solution supplies the masks those three argue from, and none of the
argument.

← [Segment anything, then keep the
glasses](08-segment-anything-then-keep-the-glasses.md) · [Amodal masks for the
hidden part](10-amodal-masks-for-the-hidden-part.md) →
