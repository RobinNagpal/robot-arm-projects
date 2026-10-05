# Solution 6 — RF-DETR-Seg, fine-tuned here

> **What it uses** — the RF-DETR package, with PyTorch underneath it, reaching
> this machine's graphics processor through the MPS backend. The model is
> **RF-DETR-Seg**, a transformer that detects and segments in one pass. It is
> published under the Apache 2.0 licence and it is offered in a range of sizes,
> so the size can be chosen to suit the machine.
> **What it does** — as designed, it takes one picture from the top and returns
> one mask per glass, with no step in between that has to cut a joined region
> apart. Nothing of it is built, so every line of this block describes an
> intention rather than a run. The
> model arrives with its weights already fitted to a large collection of
> ordinary labelled pictures, and training then continues on this cell's own
> pictures with the list of classes cut down to the single class "glass". The
> model carries a fixed number of **queries**, each of which either reports one
> glass or reports nothing, and a mask is predicted over the whole picture
> rather than inside a rectangle. Because of that, this is also the one solution
> of the six that can be asked for the part of a glass nobody saw.
> **How the output is produced** — the grey picture shaded from depth goes in;
> the model's body turns it into a description of every part of the picture; the
> queries read that description and each returns a class, a rectangle and a mask
> over the whole picture; the queries that report "nothing" are dropped; each
> surviving mask is handed to the bench, which back-projects its pixels with
> their depth readings and the camera's own pose and returns a place and a rough
> width.
> **How it differs from the other five** — against [rules on the
> table](01-rules-on-the-table.md), which fits nothing and is arithmetic a
> person can read, this fits everything and is a file of weights. Against [a
> network trained from scratch](02-train-from-scratch.md), which also fits
> everything here, this begins from somebody else's numbers instead of from
> random ones, and it reports separate glasses from the model itself rather than
> recovering them afterwards by counting where each glass pixel's arrow votes.
> Against [YOLO as it downloads](03-yolo-zero-shot.md), which is fitted
> nowhere and is covered by the AGPL, this is fitted here and is covered by a
> permissive licence. Against [the same YOLO fine-tuned
> here](04-yolo-fine-tuned.md), which is the closest comparison in the set, the
> amount of fitting is held still and the architecture and the licence change.
> Against [SAM 2 with a keeper](05-sam2-with-a-keeper.md), which leaves a large
> borrowed model untouched and fits only a small decision on top of it, this
> adjusts the whole model to the pictures the cell really renders.
> **What it costs** — the labels cost nothing, because the bench renders which
> glass owns each pixel and a mask is a selection over that. The training time
> is the time of a fine-tune rather than of a start from nothing, so it is far
> less than building the same model from random numbers would take, and it is
> still the largest single cost in this solution. The hardware is one laptop
> with a graphics processor sharing the machine's memory, reached through
> PyTorch's MPS backend; there is no NVIDIA card here and no CUDA. The licence
> is Apache 2.0, which permits the model to be used without any obligation on
> the code standing around it.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document describes the sixth of the six answers to problem 2, and it is the
one built on the most modern of the architectures in the set. The problem asks
which pixels belong to which glass, and this solution answers it by taking a
transformer that detects and segments objects, RF-DETR-Seg, and continuing its
training on this cell's own pictures with one class, "glass".

Two things make it worth a document of its own rather than a line in a table.
The first is the shape of its output. Older segmenters find a rectangle round an
object first and then paint a mask inside that rectangle, so the mask can never
reach past the rectangle's edge. This model has no such rectangle standing in
the way of its masks, and that single structural fact is what the rest of this
document builds on. The second is what that fact permits: this is the only one
of the six that can reasonably be asked to mark the part of a glass that nothing
in the picture shows, which is the **second rung** of this solution and is
described in full below.

Nothing here is built. Everything in this document is a design and a set of
prescriptions, and where a check is prescribed the document says so plainly. No
measurement of this model appears anywhere, because no run of it exists.

By the end you will understand what a query is and why a fixed number of them is
a different idea from a search that proposes regions, what set prediction means
and why it removes a cleanup step that other detectors need, what cutting the
class list down to one class does and does not change, why this architecture
suits the request for a glass's whole silhouette better than a rectangle-based
one does, and the single mistake that would do the most damage if this solution
were built carelessly.

## The problem this solves

Four to six glasses stand on the table. They are all of one kind, the kind is
known, and they are solid, so the depth camera reads them. The job, set out in
full in [the problem](../problem.md), is to say which pixels belong to which
glass, to give each glass a place on the table, and to give each a rough
footprint width. Nothing is picked up here and no shape is measured.

What makes that hard is the way a picture from the top treats a glass. A camera
looking straight down does not draw a glass's outline on top of the glass,
because the rim is nearer the lens than the table is, so the outline is thrown
outwards away from the point directly below the camera, and the taller the glass
the further out it goes. This project calls that outward throw **splay**.
Because the kind on the table draws from a wide range of proportions, with its
tall end more than twice the height of its short end, two glasses of one kind
are splayed by very different amounts, and the taller one's stretched outline
can reach across the ground where the shorter one stands.

Two different failures follow from that, and this solution is aimed at both.

The first is that two glasses standing clear of each other on the table can
leave **one joined region** in the picture. A **mask** is a picture the same
size as the photograph in which every pixel holds nothing but yes or no, where
yes means "this is glass". When two outlines meet, the yes pixels of the two
glasses form one joined region, and the usual way of turning such a region into
objects — spread out from a yes pixel to every yes pixel touching it, and call
everything reached one object — returns one object where two glasses stand. That
spreading answers only the question *are these pixels joined?*, and joined is
exactly what the two outlines are.

The second is that a glass can be **partly covered** by the glass in front of
it. Its mask then stops where the near glass begins, and what is left is not a
smaller copy of the glass but a slice of it, lying all to one side. That failure
is quiet rather than loud, and the whole of [the second
rung](#the-second-rung--training-against-the-whole-silhouette) is about it.

There is a third difficulty neither of those reaches, which is a glass covered
so completely that it contributes no pixels at all. [When the glasses are
completely hidden](#when-the-glasses-are-completely-hidden) settles what this
solution can and cannot do about it, and the answer is short.

## The main idea

The main idea is to use a model whose output already holds separate objects, and
to use one whose masks are not shut inside rectangles.

Those are two separate claims and it is worth keeping them apart. The first is
shared with other solutions in this set: a model that returns one mask per
object needs no step that divides a joined region, because the division never
had to happen. The second belongs to this solution alone, and it is what the
second rung rests on, because a mask asked to cover more than the camera saw has
to be free to grow.

The second half of the main idea is where the numbers inside the model come
from. A model of this kind holds a great many weights, and determining all of
them from this cell's pictures alone would be unreasonable. It does not have to
be done, because the weights arrive already fitted to a large collection of
ordinary labelled pictures, and training continues from those weights on this
cell's own pictures with the class list cut down to one entry. That is
**fine-tuning**, and it is why a model this size is a sensible thing to put on
one laptop.

## What a transformer segmenter does differently

Everything above says what is wanted. This section says how this model's shape
differs from the older shape, because the difference is the reason the rest of
the document is possible.

**The older shape is propose, then refine.** A detector of that kind first looks
over the picture and proposes rectangles that might hold an object, with no
claim about what the object is. It then takes each proposed rectangle on its
own, decides what is inside it, tightens the rectangle round it, and paints a
mask of the object's pixels **inside that rectangle only**. The mask is produced
on a small grid covering the rectangle and then stretched to the rectangle's
size, so it physically cannot reach past the rectangle's edge. The list of
proposals has no fixed length: it starts long, it is cut down, and the cutting
down is a step of its own.

**This model's shape is a fixed set of slots.** It carries a fixed number of
**queries**. A query is not a rectangle and not a region; it is a small list of
numbers that the model carries along and updates as it reads the picture, and
its job is to ask one question over the whole picture: *is there an object here,
and which pixels are it?* The number of queries is decided before training and
never changes, and it is chosen to be comfortably larger than the number of
objects any picture is expected to hold.

The programming comparison is exact enough to be worth using. The older shape is
a list that grows: candidates are appended as they are found, and the list is
then pruned down to the answers. This shape is a **fixed-size array of optional
values**, declared once. Every slot is either filled in with one object or left
empty, the array is the same length for every picture, and nothing is appended
and nothing is removed. A picture with two glasses and a picture with six
glasses produce arrays of the same length, differing only in how many slots are
filled.

The masks follow from that. Each filled slot's query is turned into a short list
of numbers describing the object it found, and separately the model produces a
description of every pixel in the picture. The mask for that object is then
"which pixels of the whole picture match this query's description", computed
pixel by pixel across the whole frame. So a mask is a statement about the entire
picture from the start, and **there is no rectangle for a mask to escape**, for
the simple reason that the mask was never drawn inside one. The model does also
report a rectangle round each object, because a rectangle is a convenient thing
to have, but the rectangle is a result of the answer rather than a container the
answer was built in.

## Why that matters for this problem

That difference matters here for two reasons, one immediate and one that this
solution's second rung depends on entirely.

The immediate reason is that two glasses whose outlines join are two different
slots from the beginning. The queries work over the whole picture at once, so
nothing ever considered the joined region as one thing, and nothing has to
notice a seam or decide where to cut it. Two masks come out, and they are
allowed to overlap, because each one says "these pixels are part of me" about a
different object rather than putting one label on each pixel.

The reason that matters more is about room to grow. A glass partly covered by
the glass in front of it has evidence in the picture only on one side, so the
smallest rectangle round the pixels the camera saw of it is smaller than the
glass really is. In the older shape, that rectangle is the frame the mask is
painted in, so a mask that should cover the whole glass is clipped at an edge
decided by the evidence. Here there is no such edge. A mask may claim any pixel
in the picture it likes, so asking the model for the whole shape of a glass is a
request the architecture can express rather than one it has to be forced into.
That request is [the second
rung](#the-second-rung--training-against-the-whole-silhouette), and it is the
reason this architecture was chosen for this place in the set.

## One class

Before the training can be described, one small change to the model has to be
stated, because it is the same change [the same YOLO fine-tuned
here](04-yolo-fine-tuned.md) makes and it is easy to overstate.

A borrowed detector arrives knowing a general category list: many kinds of
everyday object, each with its own name. Here that list is replaced by a single
entry, "glass". So each query's class answer is a choice between two things
only, "glass" and "nothing", and the model is no longer being asked what sort of
object it has found. It is being asked only whether it has found one and which
pixels it is.

Two things follow, and they pull in opposite directions. In this solution's
favour, the question is easier: there is no chance of calling a glass a vase,
and the general category list was a description of a world this cell does not
contain anyway. Against it, the class answer stops being useful information. A
model with a category list can be read as saying "I am sure this is a glass
rather than a bowl", while here a high score means only "I am sure something is
here", so the score cannot be read as agreement about the kind. That is no loss
in this problem, because the kind on the table is already known, but it becomes
one in [problem 4](../../problem-4/problem.md), where naming the kind is the
question.

One thing does not follow. Cutting the class list down does not make the model
smaller or the training shorter in any important way, because almost all of the
weights are in the part that reads the picture and that part does not know what
the class list is.

## Set prediction

With the slots and the single class in place, the next question is how the
training gets one answer per glass instead of several, and this is where this
family of models differs most sharply from the older one.

**Set prediction** means that the model's whole output is treated as one set of
answers to be compared against the set of real objects, rather than as a pile of
candidates to be sorted out afterwards. At each training step, the model's
filled slots are matched to the real glasses in the picture **one to one**: each
real glass is assigned exactly one query, each query gets at most one real
glass, and the pairing chosen is the one that fits best overall. Every query
left over is told that the right answer for it was "nothing".

The consequence is the part worth remembering. A query that reports a glass that
another query has already been matched to is not rewarded for being nearly
right; it is told that its answer should have been "nothing". So the duplicate
answers are trained out of the model rather than removed from its output. The
model learns, over the whole training set, that the slots must divide the
objects between themselves, and a picture with four glasses comes back with four
filled slots because that is what the training rewarded.

Compare that with the older shape, where several proposals land on one object
because several reference rectangles at neighbouring positions all really do
contain most of it. All of them score highly, so the output holds a cluster of
overlapping claims about one object, and a separate arithmetic step has to
reduce the cluster to one answer: sort the claims by score, keep the best,
discard every claim overlapping it by more than a chosen amount, and repeat.
That step is called non-maximum suppression, and it has one setting and one
assumption. The setting is how much overlap counts as duplication. The
assumption is that heavy overlap **means** duplication — and in this cell that
assumption is awkward, because splay can push one glass's stretched outline
right across another's, so two genuinely different objects can overlap heavily
and one of them can be thrown away for looking like a duplicate of the other.

Set prediction removes both the setting and the assumption. There is no overlap
amount to choose, so there is one fewer number that somebody has to justify
against the geometry of this cell, and two heavily overlapping objects are not
in competition with each other, because each occupies its own slot. That is a
real advantage here and it should be stated as the design expectation it is, not
as something this folder has measured.

The cost of set prediction is also real and worth naming. Matching the slots to
the objects one to one is a decision the training step has to make before it can
score anything, and which query ends up responsible for which glass can change
from one step to the next early in training. Models of this family are therefore
known to need patience in training, and the published work on them is largely
about making that matching settle faster.

## Fine-tuning this model here

The architecture is settled, so this section is about where its numbers come
from, because that is the other half of the design and it decides whether the
model is reasonable to build at all.

**Training** a network means showing it an example, comparing what it produced
against the answer wanted, and nudging every weight in the direction that would
have helped. **Training from a random start** means every weight begins as
noise, so the nudges have to build the whole model from nothing, including the
parts that merely find edges. **Fine-tuning** means the weights begin somewhere
useful, so the nudges have far less to do. This model arrives fitted to a large
collection of ordinary labelled pictures, and almost all of its weights are in
the part that reads a picture rather than in the queries on top, so what is
borrowed is mostly a general-purpose answer to "what is in this part of this
picture".

Why that needs less data is best said in terms of what the data has to pay for.
Every weight is a number the training data has to determine, and a weight the
data cannot pin down ends up fitted to accidents of the particular examples
given, which is called **overfitting** and shows as a model scoring well on its
training pictures and badly on new ones. The amount of data needed therefore
grows with the number of weights determined from nothing, and fine-tuning
changes that sum: most of the weights already sit at values that work and only
have to be adjusted. This is why a few hundred pictures is a sensible training
set for a model of this size, and a few hundred pictures is what this cell can
produce without difficulty.

The labels are where this cell is unusually fortunate. In the ordinary case a
person draws every mask by hand, which is why labelled data is the scarce
resource in this field. Here nothing is drawn. The bench renders, beside every
picture, an image saying which glass owns each pixel, described in [the test
bench](../the-bench.md), so one glass's mask is the set of pixels carrying its
identity and the class is always "glass". Every label is a selection over an
array the bench produced anyway. The bench hands those labels out only for the
training half of its arrangements and marks on the other half, so no model is
ever tested on an arrangement it learned from.

There is one honest warning about the pictures themselves. The cell's renderer
produces no colour: it produces a depth reading for every pixel, and the picture
the model is given is that depth shaded into grey. The borrowed weights were
fitted to ordinary pictures, which have colour varying between their channels,
edges from paint and print and shadow as well as from geometry, and texture
inside every surface. A shaded depth picture has none of that and all of its
edges are geometric. The name for that difference is the **domain gap**, meaning
the gap between the world a model was fitted on and the world it is asked to run
in. Fine-tuning does not remove the gap, but it does the one thing that matters
most: the grey pictures are not an unfamiliar input the model must survive at
run time, they are the input it is fitted on. So the gap is expected to cost
accuracy and training effort rather than correctness. That is reasoning about
the design and not a result.

There is a second warning about the training set, and it is a rule this document
prescribes rather than something any code here does. The cell's own placement
rule keeps glasses a comfortable distance apart, so a training set drawn only
from that rule never shows the model a pair that was hard to separate. The
training arrangements therefore have to include pairs standing much closer than
the rule allows and pairs whose outlines overlap heavily after splay, while
keeping the ordinary case in proportion. The principle is worth remembering:
**the edge of the specification should sit somewhere in the middle of the
training set**, so that the model has met worse than it ever will.

## The second rung — training against the whole silhouette

Everything above describes a model that marks the pixels the camera can see of
each glass. This section is the step up, and it belongs to this solution rather
than to any of the other five, because this is the architecture whose masks have
room to hold it.

The step is one sentence long: **train each mask against the glass's whole
silhouette — the shape it would have if nothing stood in front of it — instead
of against only the pixels the camera can see of it.** A mask of that sort is
called an **amodal** mask, and the word is worth unpacking once. A **mode** here
means a sense: seeing, hearing, touching. Something is **modally** present when
a sense delivers it, so the part of a glass whose own surface the camera sees is
modally present in the picture. Something is **amodally** present when the
perceiver has it although no sense delivered it, which is the part of a glass
hidden behind another object: you know it is there, you know roughly where its
edge runs, and no light from it reached the camera. So a **modal mask** covers
the pixels where the glass's own surface is what the camera saw, and an **amodal
mask** covers the pixels the glass would occupy if nothing stood in front of it.
The amodal mask always contains the modal one, and the difference between the
two is the **hidden part**.

![The same arrangement from the top, shown three ways: the modal mask of the covered glass holds only the pixels where its own surface was seen, the amodal mask holds its whole silhouette, and the difference between the two is the hidden part.](../../../images/02-segment-glasses/10-modal-against-amodal.png)

The everyday version shows that the amodal answer is the normal one. Look at a
cat sitting behind a garden railing. What reaches your eyes, strictly, is a set
of vertical strips of cat separated by bars, and what you report is **one cat**.
The alternative report, several slices of cat of various widths, is so strange
that it takes an effort to produce. A model marking only visible pixels is a
system that reports the slices, which is exactly what it was asked for and
exactly what the picture holds. It becomes a problem only when the next step
assumes a whole object.

One property of the two masks matters for the training. **On a glass with
nothing in front of it the modal and amodal masks are the same**, because there
is no hidden part to complete. So training against whole silhouettes costs
nothing on the easy pictures, and it leaves a free test available afterwards: on
a glass with a clear view, a model that adds anything at all is adding something
wrong.

### Why it helps

The reason this is worth doing is the quiet failure named in [the problem this
solves](#the-problem-this-solves), and it is worth following through to the
place where the damage appears.

Put one glass partly behind another. The camera sees the near glass's surface
where the far glass would otherwise have been, so a mask marking only visible
pixels loses every pixel of the far glass behind that surface. What is left is a
slice of the glass, cut along one side, with every remaining pixel lying towards
the side the camera could still see.

Now hand that slice to the arithmetic every solution in this problem shares. It
back-projects each mask pixel with its depth reading into a point in the room
and drops the height to get a point on the table, takes the axis from the points
at the top of the glass and the width from how far the cloud reaches out from
that axis. A whole footprint gives a disc, and the arithmetic reads it
correctly. A slice is narrower than the whole and it lies off to one side of the
true centre, so the arithmetic reads a glass that is both **smaller than the
truth and standing where no glass stands**.

That failure is dangerous because of what does *not* happen. The reported width
is still a width this kind of glass is allowed to have, because a kind whose
range runs from a small glass to a much larger one has room for a short
measurement: a slice does not look like an error, it looks like a shorter glass.
So nothing in the answer objects, and the arm is sent towards a place where
there is no glass. Compare it with the loud failure these checks were built for:
when two glasses come back as one region the width comes out wider than any
glass of this kind can be, the check fires, and the region is reported as
doubtful. **A loud failure is a result; a quiet one is a trap**, and in a cell
whose next step is an arm moving, the quiet one is far worse.

A mask covering the whole silhouette repairs the thing that caused it. The far
glass becomes a region of its own, with its outline where the glass's outline
really runs, so its visible slice is attributed to the glass it came off instead
of being swallowed into the region of the glass in front, and a slice too thin
to be worth reporting on its own is reported as part of something whole.

### Why this architecture suits it

This is where the shape of the model earns its place, and the argument is short
because the work was done in [what a transformer segmenter does
differently](#what-a-transformer-segmenter-does-differently).

A whole silhouette sticks out beyond the visible evidence. In the older shape,
the mask is painted inside a rectangle, and the rectangle is found from what the
picture shows, so the completion is clipped at an edge the evidence drew and the
model is being asked for something it has no room to express. Making that work
means training the rectangles to be amodal as well, which is asking the
proposing stage to propose a rectangle **larger than the evidence in the
picture**. Here there is nothing to fix, because the mask is computed over the
whole picture from the start. **With no rectangle to escape, a mask is free to
grow**, and asking for the whole silhouette changes only what the mask is scored
against during training.

That is worth stating as a general lesson, because it is one of the more useful
things to know about models of this sort. **One network answers a different
question by changing its target rather than its shape.** The body learns to
describe what is in the picture, and the question being asked lives in what the
final output is compared with. Here not even the last part of the model changes
shape, so the question lives entirely in the target.

The code change being small does not make the task change small, and it would be
dishonest to let that pass. Marking visible pixels traces a boundary that is
present in the picture, which is a question about where the evidence stops.
Marking a whole silhouette traces part of a boundary that is not in the picture,
which is a question about what a glass of this kind looks like and about which
of two objects at a boundary is in front. The second question needs the model to
have learned the shape of the kind, and it needs the near-and-far relation to
come out right, because completing the wrong one of the two objects produces a
mask spreading over a glass that is actually nearer the camera. So this rung may
need more training, or a larger size of the model, than the first rung does.
Whether it does is **not known here**, and this document does not assert it.

### The trap, and it is the one thing most easily got wrong

Now the part that matters a great deal, and it is the single thing this solution
would most easily get wrong. It deserves its own section because the mistake is
invisible: it makes the mask look better while making the answer much worse.

A mask covering the whole silhouette claims pixels where the camera saw some
other object's surface. The model is asserting that the glass continues
underneath what is in front of it, and an assertion is not an observation. The
damage comes from the depth reading. **The depth reading at such a pixel belongs
to whatever stood in front**, so it says how far away the near glass is and
nothing at all about the glass being reported. Feed it into the shared
arithmetic and the point it gives sits on the near glass, somewhere between the
camera and the glass being reported, and a patch of such points drags the
computed place across the gap and onto the object in front.

So the rule is absolute. **A mask that claims pixels the camera never saw the
glass at must say which pixels those are**, handing on the observed part and the
asserted part as two things rather than one silhouette with the join hidden. The
bench then **excludes those readings rather than guessing values for them**, and
that is the bench's own stated behaviour rather than something this solution has
to arrange. Nothing is inferred in their place either: what an asserted pixel
would be worth is a question about geometry, and a guess at it inside a
segmenter would be arithmetic nobody asked for.

Working out which pixels are asserted costs nothing, which removes the only
excuse for not doing it. The depth reading at a pixel already says whether the
surface there sits at this glass's distance or at the near object's, so the
split can be read off the answer itself without any reference to the truth.

The failure if the split is skipped would pass every check the project has. The
mask would look like a better mask, the footprint fitted to it would still be
round, and the width would still be inside the range the kind allows, so what
comes out would be a plausible wrong answer of exactly the kind this rung exists
to prevent, reached by the repair instead of by the failure the repair is for.
[The test bench](../the-bench.md) reports the measurement that settles it, taken
with exact masks and no model anywhere in the chain: naming the asserted pixels
and leaving them out places a glass markedly closer to where it stands than
feeding them in does. That measurement belongs to the bench's arithmetic rather
than to any model, so it applies here unchanged.

### What the completion actually buys

Put the rule together with the exclusion, and the value of the whole silhouette
turns out to sit where a reader does not first look for it. This is worth being
exact about, because it is the easiest thing in this rung to misdescribe.

The asserted pixels are left out, so they contribute nothing to the place and
nothing to the width. The measurement is the one the observed pixels alone would
have given, and the completion supplies no measurement at all, because it has no
reading to supply. **What it buys is attribution rather than measurement.** The
model reports one region per glass, drawn round the shape the glass really has,
so the hidden glass's visible part is credited to that glass instead of being
absorbed into the region of the glass in front. A glass that would otherwise
have been left out of the report altogether is reported as itself, in roughly
the right place, with a width that comes from the part that was seen and is
therefore under the truth.

Two consequences follow, and both are honest rather than flattering. The first
is that a width from such a report is a figure for planning and not for
gripping. This project's rule is that the last millimetres are felt rather than
driven: the fingers close until they touch and then check the width. A width
fitted to part of a glass is exactly what that rule keeps away from the gripper.
The second is that where the completion covers a glass the camera barely saw,
what arrives is an outline with too little seen inside it to place, and such an
outline should be handed on as doubtful rather than placed from nothing. A glass
reported as doubtful is a result in this project and not a failure.

One further number comes free once the two parts are kept apart, and this
document prescribes carrying it. Dividing the size of the observed part by the
size of the whole mask gives the **visible fraction**, which says how much of
that glass the camera actually saw. It costs one division, it comes from the
answer itself rather than from the model's opinion of itself, and it should
travel with every reported glass, because every consumer further down has its
own tolerance for how much of an answer was asserted and none of them can apply
that tolerance once the two parts have been merged.

### The risk of inventing glass, and what bounds it

A model trained to extend evidence has an obvious failure direction, and it is
the mirror image of the failure this rung is for: it can extend evidence that
needed no extending, or extend a scrap of evidence into a whole object that is
not there. Two facts about this cell make that concrete. A narrow strip of glass
pixels looks much the same whether it is the visible sliver of a mostly hidden
glass or simply the edge of something that ends there, and splay stretches every
outline in a picture from the top outwards, so an outline's far edge can look
cut off when the glass merely ends.

This failure is loud where the one it replaces is quiet, and two cheap
prescriptions bound it. Both are prescriptions and neither is anything this
folder runs.

**The width must lie inside the range the kind allows, unless the picture ran
out before the glass did.** Inventing glass means reporting a glass where none
stands, and every report carries a width, so a width outside the range this kind
allows is reason enough to refuse the report and hand it on as doubtful — when
the mask it was measured from lies inside the frame. When the mask reaches the
edge of the frame it is not. At the cell's own survey height one picture does not
hold the glass zone, so a glass at the far side of a station's frame is cut in
half and the width read off the half is not the glass's width; refusing on it
refuses the view and not the mask. That was measured on masks nothing can
improve on: handed the bench's own exact masks, one station at a time over 20
held-out spawned arrangements, the kind's range of footprints refuses 66 of 297
glass sightings, and **every one of those 66 reaches the frame edge**. The three
overlapping stations are the answer to such a report instead.

Notice as well that this check is useless against a mask cut short by the glass
in front of it, where the shrunken width looks like a legal smaller glass, and
useful against an invention, where claiming a glass means claiming a footprint
and a claimed footprint either fits the kind or does not.

**The asserted part must lie where the camera could not see.** A model claiming
a glass continues behind the near glass is claiming something about a part of
the scene the camera could not see, which is allowed. A model claiming a glass
continues across a patch the camera had a clear view of, and where bare table
came back, is contradicting a direct observation. So the asserted part should be
intersected with the piece of table no ray from the lens reached, and anything
asserted outside it is wrong on arithmetic alone, with no reference to the
model, the training set or the kind. That is the strongest of the two, because
it is geometry rather than judgement, and it is the reason a learned completion
can be let near the arm at all.

There is also a free test for the quiet version of invention, where a model
completes a little on every glass whether or not anything is in front of it, so
that every footprint comes out slightly too wide and displaced slightly outwards
and no single answer looks wrong. **On a glass with nothing in front of it, the
amodal mask must equal the modal one.** So keep only the unobstructed glasses in
the marking half of the arrangements and measure what the model adds to them:
the right answer is nothing, and any systematic addition is a bias worth knowing
about before the model is trusted.

### How to tell whether the completion works at all

The last thing this rung needs is a way to tell whether the model is doing what
it was asked, because the ordinary measure of a segmenter misleads here, and a
model of this kind can be built, trained and declared a success while completing
nothing.

The ordinary measure is **overlap**: the number of pixels both the predicted and
the true mask hold, divided by the number either of them holds. Measured against
the visible truth it punishes the model for working, because every pixel of a
correct completion lies outside that truth and is counted as a mistake, so the
better the completion the lower the score and the best score goes to a model
that has learned to ignore the amodal target entirely. The lesson generalises:
**a score that rewards doing nothing will be optimised by a model that does
nothing.** Measured against the whole silhouette it is better but still a poor
guide, because for most glasses the hidden part is a minority of the silhouette
and for a glass with a clear view it is nothing, so the number mostly reports
how well the visible boundary was traced, which is the first rung's job.

So the measure to watch during training is the **overlap over the hidden part
alone**, which the bench can supply exactly by subtracting one of its own masks
from the other. That number ignores every pixel the model could have got right
by tracing a visible edge. Beside it belong the counts of glasses found, missed
and merged, because what this rung changes shows up in those counts before it
shows up in any footprint: a completion that attributes a slice to the glass it
came off adds a glass to the answer rather than improving the footprint of a
glass that was already there.

![A stand-in prediction that completes most of the hidden part but stops short of its far edge scores well when the overlap is counted over the pixels the camera saw and much worse when it is counted over the hidden part alone, which is why the hidden part alone is the number to watch.](../../../images/02-segment-glasses/10-measuring-whether-it-works.png)

## The masks are what this contributes

Everything above is about producing masks, and this section says plainly where
this solution stops, because it is the same place all six stop and it is what
makes the six comparable at all.

Turning a mask into a place on the table and a rough width is **the bench's job,
not this solution's**. [The test bench](../the-bench.md) describes that step in
full: each mask pixel carries a depth reading, so it becomes a point in the
room, the axis comes from the points at the top of the glass, and the width
comes from how far the cloud reaches out from that axis. The same function does
it for every one of the six.

Two things follow and neither is re-derived here. **A difference in the score
belongs to the mask**, because nothing else is allowed to differ, so no solution
can win by measuring more cleverly and none can lose by measuring worse. And
**no model in this problem produces a pose.** Models produce masks. The place
comes from the depth readings and the camera's own pose, by arithmetic, and a
glass standing upright on a flat table has no orientation left to find.

The one thing this solution owes that step, beyond the masks themselves, is the
split described in [the
trap](#the-trap-and-it-is-the-one-thing-most-easily-got-wrong): when a mask
claims pixels the camera never saw the glass at, it must say which ones.

## How the concepts fit together

Everything above is one chain — the chain this solution is designed to run,
since none of it is built — and it is worth reading in order, because each stage
inherits what the one before it produced.

A **grey picture**, shaded from the depth reading at every pixel, goes in. The
body of the model reads it and produces a description of every part of it, using
weights that arrived fitted to a large collection of ordinary pictures and were
then nudged on this cell's own pictures. A fixed number of **queries** read that
description, and each one returns either "nothing" or one object: a class, which
here is only ever "glass", a rectangle, and a **mask** computed pixel by pixel
over the whole picture rather than inside the rectangle. Because the training
matched queries to real glasses **one to one**, the filled slots do not
duplicate each other, so no step afterwards has to reduce overlapping claims to
one answer.

On the second rung the mask covers the glass's **whole silhouette** rather than
only what the camera saw, so it is then split into its **observed part**, where
the depth reading agrees that the surface seen there belongs to this glass, and
its **asserted part**, which is the rest. The observed pixels go to the shared
arithmetic and become points on the table. The asserted pixels are named and
excluded, because the reading under each of them belongs to whatever stood in
front. Out of that come a **place** and a **rough width**, both measurements of
the part that was seen, and the **visible fraction** this document prescribes
carrying alongside them.

Then the prescribed checks, each of which can only refuse. The width must lie
inside the range the kind allows, unless the mask it was measured from reaches
the edge of the frame, where the width belongs to the part of the glass the
picture held. The asserted part must lie inside the piece of
table the camera could not see. A glass passing both is reported with its place,
its width and its visible fraction; a glass failing either is reported as
doubtful, with the check it failed.

Three things are worth holding on to. The **shape of the output** is what
answers the hardest part of the problem, because a fixed set of slots filled one
to one holds separate objects without anything having to divide a joined region.
The **absence of a rectangle round each mask** is what makes the second rung a
change of target rather than a change of architecture. And the **separation of
observed from asserted pixels** is what keeps the second rung honest, because
the arithmetic and both surviving checks need the two kinds of pixel kept apart.

## When the glasses are completely hidden

Every document in this set has to answer this, and this one answers it twice,
because the second rung moves the boundary without removing it.

A glass can be missing from a picture altogether. It is standing on the table,
it is solid, the depth camera is pointed straight at the part of the table it
stands on, and not one pixel of it comes back. From the top that happens through
splay: the tall end of this kind is more than twice the height of its short end,
so a tall glass's outline is thrown much further out than a short one's, and
standing the short glass beyond the tall one along the line running out from the
point below the camera lets the tall glass's stretched outline cover it
entirely.

**A glass with no pixels fills no slot.** The queries read the picture, and what
the picture holds where the hidden glass stands is the tall glass in front of it
and the table around it. Nothing in that part of the picture came from the
hidden glass, so one slot is filled with the tall glass, correctly, with a
correct mask over the tall glass's pixels, and the hidden glass appears nowhere.

**Nothing in the output is wrong.** There is no low score, because the glass
that was found really is a glass. There is no impossible width either, because
the surviving pixels back-project to the tall glass's own real footprint: splay
decides which pixels exist and not where they land, so every pixel returns to
its own true place on the table. Every check prescribed above is a check on
something that was found, and there is nothing to check.

**No amount of training helps, and this can be put more strongly than "it does
not work".** Take the scene with the hidden glass, and the same scene with that
glass taken away. The renderer produces the same picture for both, pixel for
pixel. A model is a function of its input, so no model of any size, trained by
any method for any length of time, can return different answers for two
identical inputs. What differs between the two scenes left no trace in the
input, so this is a fact about the input rather than about the model, and
training cannot change facts about the input.

The second rung does not escape that, and the reason is what completion is.
**Completion extends evidence.** The model sees a boundary that stops, sees a
surface in front of where it stopped, and continues the boundary behind that
surface in the way a glass of this kind would continue. Every part of that
description begins with something in the picture: the visible sliver says where
the glass is, how wide it is, and how far the completion has to reach. Take the
sliver away and there is no boundary that stops, no partial outline to continue
and no scrap of surface to say which glass of the kind's range this is. There is
nothing to extend, and a model that extends nothing produces nothing.

A model *could* be trained to mark a glass that **might** be behind this one,
since the bench can supply that label too, and it is worth saying what such a
model would be doing. It would be reporting where glasses tend to stand in
arrangements like this one, which is a statement about the range of arrangements
rather than about this arrangement. That is **inventing a scene rather than
reading a picture**, and it would mark a glass behind every tall glass,
including all the times there is nothing there. Trading a silent miss for a
confident invention is a bad trade where the next step is an arm moving, and it
is the trade this project's rules refuse: anything doubtful is reported, never
guessed.

What the second rung does contribute is a boundary further out. Completion needs
less of a glass than anything else in this set, so the point at which hiding
becomes complete is further away with it than without it, and a glass that would
have gone missing entirely is reported from the sliver that is left. **The
boundary moves; it does not disappear.** Beyond wherever it now sits, this
solution has nothing to say, and should say so.

![A partly covered glass still reaches the picture, so it fills a slot of its own and leaves an edge to carry on from, while a glass whose outline is swallowed whole reaches it nowhere and leaves nothing to extend, which is the rung at which completion stops.](../../../images/02-segment-glasses/10-where-it-stops.png)

So the completely hidden case has to be handed on, and what is handed on is not
a glass but a region: the part of the table this picture could not have seen.
Working that region out is arithmetic on splay and on the glasses that *were*
found, and going to look at it is a move of the arm. Both belong to the shared
part of this problem described in [looking again at what was
hidden](../hidden-glasses.md), which every one of the six points at rather than
restating. This solution contributes the masks that argument starts from, and
none of the argument.

## A worked example

Everything below follows from the cell's own geometry and from the design above.
Nothing in it is a measurement, because no run of this solution exists.

**The arrangement.** Five glasses of one kind stand on the table, and the camera
looks down from the top. Three of them stand clear of each other. The other two
stand much closer together than the cell's rule allows, roughly along the line
running out from the point below the camera, with the taller one nearer that
point, so splay stretches the taller one's outline across part of the shorter
one. In the picture their two outlines join into one region with no seam along
it.

**What the first rung would return.** The queries work over the whole picture,
so the two close glasses occupy two different slots, and the joined region is
never considered as one thing. Five slots come back filled, and because the
training matched slots to glasses one to one, no sixth slot reports either of
the close pair a second time and nothing has to discard a duplicate. The two
masks of the close pair overlap where the taller glass covers the shorter one,
and that is allowed, because each mask says "these pixels are part of me" about
a different glass. Nothing separated the two, and that is the point worth taking
away: there was never a joined region for anything to divide.

**What the first rung would still get wrong.** The shorter glass's mask stops
where the taller one begins, so it is a slice lying all to one side. Handed to
the shared arithmetic, that slice gives a width under the truth and a place off
to one side of where the glass stands, and the width is still one this kind
allows, so nothing objects. Five glasses are reported, one of them smaller than
it is and standing where it is not.

**What the second rung would return instead.** The shorter glass's mask covers
the part behind the taller one as well, so the shorter glass is a region of its
own and its visible slice is credited to it rather than absorbed into the taller
glass's region. The mask is then split: the observed part is the slice, and the
asserted part is the rest. The asserted pixels carry the taller glass's depth
readings, so they are named and the bench leaves them out, and the place and the
width come from the slice alone. The place is good enough to send a camera to.
The width is still under the truth, and the visible fraction travelling with the
answer says so. The asserted part lies in the taller glass's own shadow, where
the camera could not see, so nothing is claimed where the camera had a clear
view, and neither prescribed check has anything to refuse.

**What the flag then buys.** Because the visible fraction is low, the reported
width plans and does not grip. The arm goes round to the side, stands back at
the measuring standoff and looks level, and from there nothing is in front of
the shorter glass, so its two masks coincide and its footprint is measured
rather than asserted. The completion decided **where to look**, and the look
from the side decides **what is true**.

**Now the case neither rung answers.** Push the shorter glass directly behind
the taller one along that line, close enough that the taller one's stretched
outline covers it completely. The picture holds no pixel of it, so no slot is
filled with it and there is no sliver to extend. Four glasses are reported where
five stand, every report correct, every width legal, every score confident, and
no check fires, because every check here is a check on something that was found.
That is the case handed to the geometry.

## What it needs

This is one of the more demanding solutions in the set to set up, and it is
worth being plain about that before anyone starts.

It needs a **deep learning framework and the environment to run it in**, which
is a large dependency for a cell whose simplest answer is a page of arithmetic.
It needs a **downloaded file of weights**, which is large, which is not
something to keep beside the code, and which this project cannot produce, so it
comes from outside and is taken on trust.

It needs a **training set**, which the bench renders and labels for nothing,
including the crowded arrangements the cell's own rule would never produce. That
is the genuinely cheap part and it is what makes fine-tuning reasonable here. It
needs **time on the machine** for the fine-tune, far less than a start from
random numbers would need but still the largest cost in the solution, and the
second rung may need more of it than the first.

It needs **hardware it fits on**. The machine here is a laptop whose graphics
processor shares memory with the main processor, and PyTorch reaches that
graphics processor through its MPS backend, so the code would select MPS when it
is available and fall back to the main processor otherwise. There is no NVIDIA
card here and no CUDA. The shared memory is part of why a model of this size
fits at all, and the model being offered in a range of sizes is the other part,
because a smaller size can be chosen if the larger one does not fit.

And once fine-tuned it needs **a file of weights kept in step with the world**.
Change the camera, the way depth is shaded into grey, or the range of
proportions a kind is drawn from, and the file is quietly out of date in a way
no test of the code will notice. Against all that, what it needs at run time is
modest: one pass over one picture is a small fraction of the seconds an arm
movement costs, so the cost of this solution sits almost entirely in building it
rather than in running it.

The licence is the one thing it does not need to worry about. Apache 2.0 is
permissive: the model may be used, changed and shipped inside other work without
any obligation falling on the code around it. That is a real difference from
[YOLO as it downloads](03-yolo-zero-shot.md) and [the same YOLO fine-tuned
here](04-yolo-fine-tuned.md), both of which are covered by the AGPL, and it is
worth knowing before a choice is made rather than after.

## Where it is strong and where it breaks

**It answers the question actually asked.** The problem asks which pixels belong
to which glass, and the output is one mask per glass. Every method in this set
that answers a different question has to add machinery to convert its answer,
and every piece of that machinery is somewhere a mistake can be made.

**It separates glasses whose outlines join, and nothing has to decide where to
cut.** Two glasses that meet in the picture occupy two slots, so there is no
joined region and nothing to divide.

**It has one fewer number to justify than the older shape does.** Because the
slots are matched to the glasses one to one during training, there is no overlap
amount deciding when two claims are duplicates, and so no setting that has to be
generous enough to survive the worst legitimate overlap this cell can produce.
The score threshold remains, and it is a plain number with an obvious meaning
rather than a length that has to be defended against the geometry of the cell.

**It is the only one of the six that can be asked for the part of a glass nobody
saw**, and that is a consequence of its shape rather than a feature bolted on.
With no rectangle round each mask, the completion is a change of target and
nothing else.

**Its licence is permissive**, which matters when the same model has to be
shipped inside something else.

**Its second rung is the easiest thing in this set to implement wrongly.** If
the asserted pixels are fed into the shared arithmetic instead of being named
and excluded, the answer gets worse in exactly the way the rung exists to
prevent, and nothing complains: the mask looks better, the footprint stays
round, and the width stays inside the range the kind allows.

**Models of this family are known to want patience in training.** The one-to-one
matching has to settle before the slots stop changing their minds about which
glass each of them is responsible for, and this cell's pictures are not the kind
of picture the borrowed weights were fitted on, so the fine-tune has a domain
gap to close as well. That is a cost in training time rather than in
correctness, because the pictures the model is fitted on are the pictures it
will be run on.

**It is blind to a glass hidden completely**, and so is its second rung. No
pixels means no slot filled, no low score and nothing to check. That is a fact
about the input rather than about the model.

**Its answer cannot explain itself.** When a page of arithmetic is wrong you can
print one number and see why; when this model is wrong you can look at the
picture and guess. Every quantity inside it is a block of numbers with no
meaning anybody assigned, so working out a failure is a matter of examples
rather than of reasoning, and the prescribed checks on the width and on where
the assertion lies are what have to make that tolerable.

**Its weights are a second copy of the world, and most of them came from
somewhere else.** The code says what the cell is; the weights say what the cell
looked like when they were fitted, on top of what a large collection of ordinary
pictures looked like. Keeping that in step is a maintenance job the arithmetic
solution does not have, and the borrowed part cannot be regenerated here at all.

## The general ideas behind this

Nothing here was invented for glassware. Every part of it is a standard piece of
the modern detection toolkit, and what is specific to this cell is only the
choice of one class, the source of the labels, the grey pictures shaded from
depth, and the decision to ask for whole silhouettes.

### Detection as set prediction

The general idea is to make a detector output a **set** of a fixed size and to
train it by matching that set against the true objects one to one, so that
duplicate answers are trained away instead of pruned away. **DETR** (Carion and
colleagues, [arXiv:2005.12872](https://arxiv.org/abs/2005.12872)) did this
first, with a fixed number of queries, a transformer reading the whole picture,
and a one-to-one matching computed by the **Hungarian algorithm** (Kuhn, *Naval
Research Logistics Quarterly*, 1955), which finds the cheapest complete pairing
between two sets and is a standard piece of combinatorial optimisation rather
than anything to do with vision.

It is used wherever a clean list of objects is wanted without a pruning step,
and it suits crowded scenes, because two genuinely overlapping objects are not
competing for one answer. It is rarely the right choice when the number of
objects in a picture can exceed the number of slots, since the slots are fixed
and the surplus objects simply have nowhere to go, and it is a poor choice when
training time is the binding constraint, because the matching takes a while to
settle. For more, see [object
detection](https://en.wikipedia.org/wiki/Object_detection).

### Attending to a few places rather than everywhere

Reading a whole picture with every query attending to every position is
expensive, and the standard answer is to have each query sample a small number
of positions it chooses rather than all of them. **Deformable DETR** (Zhu and
colleagues, [arXiv:2010.04159](https://arxiv.org/abs/2010.04159)) introduced
that, together with running it over several scales at once, which is what made
this family practical and sped up the training it is known for needing. Later
work in the line, including **DINO** (Zhang and colleagues,
[arXiv:2203.03605](https://arxiv.org/abs/2203.03605)) and the real-time variants
after it, is largely about making the matching settle faster and the whole model
run in a fixed small time.

It is used in nearly every current transformer detector. It is rarely necessary
when every object is about the same size in every picture, where a single scale
and simpler attention do the job for less arithmetic. That is not this cell,
where the same glass covers a small patch of the picture from the top and much
of the frame from the side.

### A mask per query, over the whole picture

The general idea is to stop painting masks inside boxes. Give each query a short
description of the object it found, produce a description of every pixel, and
take the mask to be the pixels whose description matches the query's.
**MaskFormer** and **Mask2Former** (Cheng and colleagues,
[arXiv:2107.06278](https://arxiv.org/abs/2107.06278) and
[arXiv:2112.01527](https://arxiv.org/abs/2112.01527)) set out that formulation
and showed that one model in this shape answers segmentation by class, by
instance and by both at once, differing only in the target it is trained
against.

It is used wherever objects of one class touch or overlap and have to be
reported separately, and it is the right shape whenever a mask may need to reach
past where the evidence for the object stops, which is exactly why it is chosen
here. It is rarely right when a single map of classes is all that is wanted,
because the queries are then pure cost.

### Transfer learning and fine-tuning

Take a model fitted on a large general task, keep its weights, change the last
part to suit the new task, and continue training on the new data. It works
because the early parts of a vision model learn things common to all vision —
edges, corners, gradients, textures — and only the later parts learn things
specific to the original task. Yosinski and colleagues
([arXiv:1411.1792](https://arxiv.org/abs/1411.1792)) measured that directly,
showing how much transfers and how it falls away with depth. The pictures such
weights are usually fitted on are collections like COCO (Lin and colleagues,
[arXiv:1405.0312](https://arxiv.org/abs/1405.0312)), and a backbone may instead
arrive fitted without labels at all, as in **DINOv2** (Oquab and colleagues,
[arXiv:2304.07193](https://arxiv.org/abs/2304.07193)), which is the route recent
detectors in this family favour.

It is used whenever labelled data for the real task is scarce, which is almost
always. It is rarely the right choice when labels are free and plentiful and the
new pictures look nothing like the borrowed ones, because the borrowed weights
then bring knowledge of a world you do not have while also fixing your model at
the size somebody else chose. That is the argument [a network trained from
scratch](02-train-from-scratch.md) makes, and this solution takes the other side
of it on purpose. For more, see [transfer
learning](https://en.wikipedia.org/wiki/Transfer_learning).

### Amodal segmentation

The general idea is to mark the whole extent of an object including the part
another object covers, rather than only the visible part. **Amodal instance
segmentation** was posed as a task by Li and Malik
([arXiv:1604.08202](https://arxiv.org/abs/1604.08202)), with an earlier
formulation over whole scenes by Zhu and colleagues
([arXiv:1509.01329](https://arxiv.org/abs/1509.01329)), and later work predicts
the visible and the whole mask side by side so that the hidden part is available
on its own (Follmann and colleagues,
[arXiv:1804.08864](https://arxiv.org/abs/1804.08864)).

It is used in robot picking, in driving, and anywhere a partly covered object
has to be reasoned about as a whole, and it is right whenever the step after the
segmenter assumes a whole object, which is exactly the case here. It is rarely
right on real photographs without care, because the label has to be drawn
through a place nobody can see, so two careful annotators disagree with no way
to settle who was right, and a model trained on such labels is fitted partly to
the annotators' guesses. **None of that applies in a simulator**, which is why
this rung is cheap here: the bench can render the arrangement again with the
other glasses taken away, and the mask that comes back is the whole silhouette
exactly, with no guessing in it. For more, see [image
segmentation](https://en.wikipedia.org/wiki/Image_segmentation).

![The whole silhouette is asked of the simulator rather than of a person: render the scene once for the pixels the camera sees of each glass, render the covered glass again with the others taken away for the shape it would have had, and the difference between the two is the hidden part.](../../../images/02-segment-glasses/10-labels-for-free.png)

## Where it sits among the other five

This solution sits at the far end of the ladder, with everything fitted here and
the most modern architecture under it. Each comparison below holds something
still and changes one thing, which is what makes the set worth having.

Against [the same YOLO fine-tuned here](04-yolo-fine-tuned.md), the comparison
is the sharpest in the set after solutions 3 and 4, and it is the reason this
solution exists. Both are fitted the same way, on the same pictures, with the
same single class and the same free labels, so **the amount of fitting is held
still and the architecture is what changes**. The gap between those two is
therefore about design rather than about training. Two differences of design are
worth naming. The first is the one-to-one matching, which removes the overlap
amount deciding when two claims are duplicates. The second is that there is no
rectangle round each mask, which is what lets this solution be asked for a whole
silhouette while the other cannot be without reworking what its rectangles are
trained to cover. The licence differs too, and it is not a small thing: that
solution is covered by the AGPL and this one by Apache 2.0.

Against [YOLO as it downloads](03-yolo-zero-shot.md), two things change at once,
so the comparison is coarser. That solution is fitted nowhere and this one is
fitted here, and the architectures differ as well. The pair worth reading for
what training alone buys is solutions 3 and 4, which share a library, a model
and a set of starting weights and differ only in whether the model was trained
on this cell's pictures. This solution and solution 4 are the pair worth reading
for what architecture buys once both are trained.

Against [SAM 2 with a keeper](05-sam2-with-a-keeper.md), the trade runs the
other way round. That solution borrows more and fits less: its segmenter is used
exactly as it downloads, and the only thing fitted is a small decision about
which of its regions are glasses. That needs almost no training data and leaves
its domain gap wide open, as solution 3 also does, because nothing in the
borrowed weights is ever adjusted to the pictures this cell renders. This
solution fits the whole model, so its weights have actually seen the pictures it
will be run on, which is why its domain gap is expected to cost accuracy and
training time rather than correctness. If the question is how little training
one can get away with, that solution wins; if it is which of them has met this
cell's pictures, this one does.

Against [a network trained from scratch](02-train-from-scratch.md), both fit
everything here and the difference is where the numbers start and what the
output is. That solution begins from random numbers and owns every weight, which
means a small file that can be kept beside the code and regenerated without
thinking about it. It reaches separate glasses by a step outside the network
rather than from the network's own output: its network answers two questions at
every pixel, whether the pixel is glass and which way the middle of that pixel's
own glass lies, and the glasses are then the piles that those votes form, which
are counted afterwards. So both solutions hold separate objects, and what
differs is where the separating happens. This solution asks the model for
instances and gets them with nothing counted afterwards, in exchange for a large
downloaded file it cannot regenerate. So the choice is not "borrowed is better";
it is capability now against a model the project fully owns.

Against [rules on the table](01-rules-on-the-table.md), the comparison is the
one every fitted solution here faces, and it is not flattering. On any day the
depth readings work, that solution is better in almost every way that matters:
it is a page of arithmetic rather than a file of weights, it needs no training
set, it explains its own failures, and it can say where it has not looked. This
solution needs depth too, because depth shaded into grey is the only picture the
renderer makes, so it buys no independence from the depth camera. What it does
buy is that no length has to be chosen and defended, that two joined glasses
were never one region, and that the part of a glass nobody saw can be asked for
at all.

And the thing none of the six can do is notice a glass absent from the picture.
That is answered by geometry rather than by appearance, in [looking again at
what was hidden](../hidden-glasses.md), which all six point at. This solution
moves the boundary at which hiding becomes complete further out than the other
five, and it does not remove it. The whole comparison, with all six side by
side, is in [the overview](overview.md).

← [SAM 2 with a keeper](05-sam2-with-a-keeper.md) · [The six solutions
compared](overview.md) →