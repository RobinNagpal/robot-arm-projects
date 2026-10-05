# Solution 5 — SAM 2 with a keeper

> **What it uses** — SAM 2, the second generation of the Segment Anything model,
> loaded through Hugging Face `transformers` and never trained here;
> scikit-learn for the one small model that is fitted here; PyTorch underneath,
> which reaches this machine's integrated graphics through its MPS backend.
> **What it does** — SAM 2 outlines whatever is at a place it is pointed at, and
> it names none of what it outlines. Pointed at a plain grid of places spread
> over the whole picture, it therefore outlines everything the picture contains:
> the glasses, the table, the rim of a glass, two glasses that ran together into
> one shape. A small model fitted in this cell, called the **keeper**, is then
> handed each of those outlines on its own and decides whether it is one glass.
> So the half of the job that finds shapes is borrowed whole, and the half that
> decides what a shape is gets replaced.
> **How the output is produced** — the depth readings are shaded into a grey
> picture; SAM 2 reads that picture once; a grid of point prompts turns into a
> heap of outlines; scoring, stability and duplicate removal cut the heap down
> to a shortlist of **proposals**; each proposal's pixels and their depth
> readings become a handful of measurements on the table; the keeper reads those
> measurements and answers keep, drop, or more than one glass; what it keeps
> still has to pass a width check against the kind, which is known; and the
> proposals that survive all of that are the masks this solution reports.
> **How it differs from the other five** — **solution 1** writes the deciding
> down as rules and fits nothing at all, where this one fits the deciding and
> borrows the seeing. **Solution 2** fits every number it uses on this cell's
> own pictures, where this one fits almost none of them. **Solution 3** borrows
> a model's shapes *and* its names, where this one borrows the shapes and
> replaces the names. **Solution 4** moves borrowed weights towards this cell's
> pictures, where here the borrowed weights never move at all. **Solution 6**
> fits a whole transformer segmenter in this cell, which makes it the largest
> fitted thing in the set against the smallest.
> **What it costs** — no hand labelling, because the bench's own answer key
> turns a proposal into a training label by arithmetic. Fitting the keeper is
> seconds of processor time with no graphics card; what takes real time is
> running SAM 2 over the arrangements to collect the proposals to fit it on. At
> run time it costs one pass of the picture encoder per picture and very little
> after that. The weights are large and are not owned by this project, so they
> have to be fetched and pinned to a version. The licence is permissive, which
> is something solutions 3 and 4 cannot say.

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the two places the camera works from, from the top and from the side, all four
> sensors, and the words this project uses them with. What follows is only what
> is specific to this solution.

## Introduction

This document describes a way to answer [problem 2](../problem.md) in which
almost nothing is fitted in this cell. The other five solutions either write
every rule down by hand or fit a model to this cell's own pictures. This one
does neither for the part that finds objects: the finding is done by a very
large model that somebody else fitted, somewhere else, on photographs of the
real world, and it is used exactly as it downloads. The only numbers fitted here
belong to a small model that looks at what the large one produced and decides
which parts of it are glasses.

The solution therefore has two halves, and they are very unequal in size. The
first half is a **borrowed model** that can be asked *what is at this point?*
and answers with an outline of the thing at that point. Asked at many points at
once, it outlines everything the picture holds, while naming none of it, because
it produces regions and not labels. The second half is the **keeper**, a small
model fitted in this cell, which is handed each of those outlines in turn and
says whether it is one glass.

By the end you will understand what a foundation model is and what it means for
one to be promptable, how a plain grid of points turns such a model into a
proposer of everything in a scene, why the large model is never trained here and
what that buys, what the keeper is shown and why it is fitted rather than
written as a page of thresholds, why it must give three answers rather than two,
and what its probability has to have done to it before a threshold can be put on
it.

You will also understand the one design question this solution carries inside
itself, which is the most interesting part of the document. A newer generation
of the same borrowed model takes a **word** instead of a point: ask it for
"drinking glass" and it returns every instance of that concept. That would
delete the keeper completely. So this solution has two **rungs**, meaning two
versions of one approach, one of them a generation newer than the other. The
last concept section weighs the two against each other, and the honest answer is
not simply that the newer one is better, because the keeper is the one place in
this whole set of six solutions where the deciding can be explained by printing
its inputs beside its answer.

## The code at the heart of it

This solution is two models meeting at one place, so that place is worth seeing
before the rest of the document explains it. On one side a grid of point
prompts goes into the borrowed model. On the other a short row of measurements
comes back out of what the borrowed model returned, and that row is the only
thing the fitted model ever reads. Everything after this section is an account
of those two sides.

Going in, in `05-sam2-with-a-keeper/sam_keeper.py`: how far apart the grid's
points stand is taken from the narrowest glass the kind allows rather than
chosen, the grid is then laid over the whole picture, and the borrowed model is
called on batches of its points with the picture already encoded.

```python
def prompt_spacing(kind: str) -> int:
    ...
    narrowest = data.widths(kind)[0] / _metres_per_pixel()
    return max(1, int(narrowest / POINTS_ACROSS_SMALLEST))


def _grid(spacing: int, inside: np.ndarray | None = None) -> list[list[float]]:
    """Prompt points (column, row) on a regular grid, optionally only where ``inside`` is true."""
    rows = np.arange(spacing // 2, render.HEIGHT, spacing)
    columns = np.arange(spacing // 2, render.WIDTH, spacing)
    points = [[float(column), float(row)] for row in rows for column in columns]
    ...

    def at(self, points: list[list[float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        ...
        asked = [[[point] for point in points]]
        prepared = self.processor(original_sizes=self.sizes, input_points=asked, return_tensors="pt")
        all_points = _onto(prepared["input_points"], self.where)
        ...
            for start in range(0, all_points.shape[1], PROMPTS_AT_ONCE):
                chunk = all_points[:, start : start + PROMPTS_AT_ONCE]
                out = self.model(image_embeddings=self.embeddings, input_points=chunk, multimask_output=True)
```

Coming out, in the same file: every region that survived the cleanup becomes
numbers measured on the table rather than in the picture. Six of the keeper's
eight come from here. The other two — how many prompt points returned this same
region, and how it nests among the regions beside it — are added by the function
that calls this one, because neither can be known from one region on its own.

```python
def _measure(picture, mask, found, jumps, step, camera, widths) -> list[float]:
    ...
    rows, columns = found.pixels[:, 0], found.pixels[:, 1]
    points = render.to_world(picture, rows, columns)

    low, high = widths
    edge = mask & ~cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return [
        (found.width - low) / (high - low),  # where its width falls in the kind's range
        _roundness(mask),
        float(np.median(points[:, 2]) - TABLE_TOP_Z),  # how far its surface stands off the table
        float(math.dist((found.x, found.y), camera)),  # how far it sits from under the camera
        float(np.mean(jumps[edge] > step)) if edge.any() else 0.0,  # how much of its edge is a step
        _table_area(points),
    ]
```

Two things show in those two blocks. The borrowed half is one call,
`self.model(...)` on a `Sam2Model` loaded through Hugging Face `transformers`,
and every line written around it belongs to this project. And the fitted half
never sees a pixel: what reaches scikit-learn — a
`HistGradientBoostingClassifier` wrapped in a `CalibratedClassifierCV` — is the
list the second block returns. That is what borrowing the seeing and fitting the
deciding looks like in code.

## The problem this solves

Problem 2 puts four to six glasses on the table. They are all of one kind, the
kind is known, and they are opaque, so the depth camera sees them. The job is to
say which pixels belong to which glass, and to give each glass a place on the
table and a rough footprint width. Nothing is picked up and no shape is
measured.

What is asked for is therefore **instance segmentation**, meaning one outline
per object rather than one label per pixel, because how many glasses there are
is part of the answer. The difficulty is not noticing that something is on the
table but deciding **how many things are there**, since two glasses standing
clearly apart can still leave one connected shape in a picture taken from the
top.

Four of the other five solutions reach that answer at one of two prices, and
this one is an attempt to pay neither in full.

Solution 1 pays in **rules somebody has to write**. Every limit inside which it
is safe has to be worked out by a person and stated in code, so its cost is that
somebody must be able to state the rule at all.

Solutions 2, 4 and 6 pay in **fitting**. Each of them ends up with a file of
weights that is a second copy of this cell, produced by hours of rendering and
hours of training. That copy has a quiet failure mode: change the lighting,
change the table's surface, widen the range of sizes a kind is drawn from, and
the file is out of date in a way that no test of the code can notice.

This solution avoids the second price by borrowing weights that were never
fitted to this cell, so there is nothing in them that can fall out of step with
it, and it avoids most of the first price by fitting the one decision that is
left over.

The catch arrives with the first sentence of the design, and much of the rest of
this document is about it. **A model that was never fitted to this cell also
never saw this cell.** It does not know about splay, it does not know that
everything on the table is one kind of object, it does not know the gap the cell
guarantees between two glasses, and there is no way to tell it any of those
things.

## The main idea

The main idea is to stop asking for glasses and start asking for everything,
then to throw away what is not a glass.

**The first half is to ask for everything.** Rather than fit something that
finds glasses, take a model that can be asked what is at a point and get back an
outline of the thing at that point, and then ask it at points spread evenly over
the whole picture. Every point lands on something, so what comes back is an
outline of the table, an outline of each glass that is distinguishable at all,
outlines of parts of glasses such as a rim, and outlines of groups of glasses.
None of them carries a name. The model is SAM 2, and no gradient is ever
computed through it in this project.

**The second half is to decide what to keep.** Each outline that survives a
first cleanup is called a **proposal** from here on. The **keeper** is a small
model which is shown a handful of measurements about one proposal and answers
whether that proposal is one glass. The keeper is the only thing fitted in this
solution, it would fit in seconds, and the examples it would learn from cost
nothing, because the bench already knows which pixels belong to which glass in
the arrangements it draws.

So, in the plainest terms: **everything that finds objects is borrowed whole,
and everything fitted here is one small decision at the end.** Beside the
borrowed model's weights, the keeper's numbers are a rounding error.

That split is not an accident of convenience, and it is the sentence worth
carrying through the rest of the document. **The job is divided along the line
that transfers best.** A shape is a shape everywhere: a step in distance between
one surface and the surface behind it is the same kind of evidence in a
photograph of a kitchen and in a grey picture shaded from depth, which is why
the proposing half can be borrowed from a model that never saw this cell. What
counts as a cup, on the other hand, is a judgement that somebody fitted to
somebody else's collection of pictures, and it has no reason to agree with what
counts as a glass here. So the proposing half is borrowed and the naming half is
replaced. **That is the opposite trade from solution 3**, which borrows both
halves and takes the borrowed model's names as the answer.

## What a foundation model is

Before the main idea can be made precise, the word for the borrowed half has to
be defined, because everything this solution buys and everything it risks
follows from the definition.

A **foundation model** is a model fitted once, on a very large and very general
collection of data, at a cost nobody expects to repeat, and then used for many
tasks it was not fitted for in particular. The fitting is done by somebody with
a warehouse of machines, and the using is done by everybody else with a
download. A lens is the closest physical comparison: it was ground for no
particular photograph, it suits an enormous range of them, and it knows nothing
about the scene in front of it.

One property of SAM 2 is what makes it usable in this project at all. **It is
class-agnostic**, which means it returns regions with no labels attached to
them. It holds no list of object types and is never asked to recognise anything,
so it never needs the word glass, and the fact that it was fitted on pictures of
everyday things rather than on glasses in a simulated cell does not by itself
disqualify it.

SAM 2 has three parts, and the split between them matters twice later on. A
**picture encoder** turns the whole picture into a block of numbers, and this is
the expensive part, which runs once per picture. A **prompt encoder** turns one
prompt into a small block of numbers. A **mask decoder** combines the two and
produces a mask, and this part is cheap, running once per prompt.

### What promptable means

The word doing the work above is *promptable*, and it does not mean the same
thing as a network that takes a picture and returns an answer.

A **prompt** is a small extra input saying *which* thing in the picture you
mean. For SAM 2 it is a point, meaning "the thing here", or a box, meaning "the
thing inside this rectangle", or a rough mask. The picture and the prompt go in
together and one mask comes out, so changing the prompt while leaving the
picture alone gives a different mask from exactly the same weights. In
programming terms the model is a function of two arguments rather than one,
which is why one picture has as many answers as you care to ask for.

![The same picture and the same unchanged weights return a different mask for each point prompt, because the prompt is a second argument and nothing else about the model changed.](../../../images/02-segment-glasses/05-what-promptable-means.png)

There is a second part of promptability, and it is the more useful part here.
**Ambiguity is returned rather than resolved.** A point on the wall of a glass
genuinely could mean three different things: that patch of wall, the whole
glass, or the glass together with whatever stands behind it. The model does not
guess between them. For one point it returns several masks at different extents
— roughly a part, a whole, and something larger — each with its own estimate of
how good that mask is, and the choice is handed back to whoever asked. That
behaviour is why the heap of proposals further down this document contains a rim
without its glass, and it is what gives the keeper something to choose between
rather than one answer to accept.

One more property has to be stated here, because a later section rests entirely
on it. **A prompt selects; it does not add information.** Pointing at a picture
says which part of that picture interests you. It cannot tell the model about
anything the picture holds no evidence of.

## Turning a promptable model into a proposer of everything

If one prompt gives one thing, then many prompts give many things, and that is
the whole of the step which turns SAM 2 from a tool somebody points at objects
into something that finds the objects by itself.

The design is to lay a regular grid of points over the picture taken from the
top and to prompt once at every point of it. The grid aims at nothing, which is
the point of it: nothing has to know where the glasses are before they have been
found. Each point lands on whatever is under it — bare table returns the table,
a glass wall returns that wall and that glass and something larger, a mouth
returns the mouth — and a grid fine enough to put several points on the
narrowest glass the kind allows touches everything in the scene at least once.

![A regular grid of prompt points laid over the picture from the top, with the points landing on a glass marked apart from the points landing on bare table, and the many points that returned the same mask counted up beside it.](../../../images/02-segment-glasses/05-the-prompt-grid.png)

What makes this affordable is the three-part split named above. The expensive
picture encoder runs **once**, and every prompt after it is one pass through the
small mask decoder, so prompting at every point of a grid costs very little more
than prompting at one.

### What comes back, and the cleanup that is not fitted

What comes back is not a list of objects but a heap, and there are three
problems in it. Many grid points land on the same glass, so the same region
arrives many times over with slightly different edges. For a single point the
model returns a part, a whole and something larger, so the heap holds a rim, the
glass that rim belongs to, and that glass together with its neighbour, all of
them defensible answers to the same prompt. And some masks are simply unstable,
which is the signature of a boundary the model is not really sure about.

The repairs are standard, and not one of them involves fitting anything. **Drop
the low-scoring masks**, using the quality estimate the model already returns
beside each one. **Drop the unstable ones**, by nudging the cut-off that turns
the model's output into a yes-or-no mask and keeping only those masks that
barely change when it moves. Then **remove the duplicates** with a step called
**non-maximum suppression**: sort the masks by score, walk down the list keeping
each one, and throw away any later mask that overlaps a mask already kept by
more than a chosen amount. The **overlap** of two masks means the area both of
them claim divided by the area either of them claims, which is one for identical
masks and zero when they share nothing.

The quality estimate and the stability earn their place here and nowhere else.
They are a **gate** rather than evidence: their job is to cut the heap down to a
shortlist before anything else looks at it, and the keeper is deliberately never
shown either of them, because what the keeper has to decide is what a region
*is*, not how sure the borrowed model was while drawing it.

After that cleanup there is a shortlist of regions, each with an outline and a
score, and **not one of them has a name**. The regions are there and they are
good regions, but nothing says which of them are glasses, nothing says the
largest one is the table, and nothing says that the pair which ran together into
one shape is two glasses rather than one very wide one.

![The shortlist that comes back over one scene holds the table, each glass on its own, a rim without the glass it belongs to and a pair of glasses taken as one shape, all of them on the same footing and not one of them carrying a name.](../../../images/02-segment-glasses/05-everything-is-proposed.png)

So the borrowed model has answered a different question from the one the problem
asks. It says *where the regions are*, and the problem asks *which regions are
glasses, and how many*. The rest of this solution is about closing that gap
without ever training the borrowed model.

## Why the borrowed model is never trained here

The obvious way to close that gap is to train the model, and this solution does
not. **Never trained** means the weights file is used exactly as it downloads:
no gradient is computed through it, no layer of it is replaced, and nothing
about this cell reaches its numbers. Running it is a forward pass and nothing
else.

Four things follow, and together they are the case for this solution. **There is
no training set for the part that finds objects**, because arrangements are
still rendered for the keeper's sake, but the keeper learns from a short table
of measurements per proposal rather than from pictures. **There is nothing that
can go out of date**, because the borrowed model never saw this cell, which is
the exact opposite of solutions 2, 4 and 6, whose weights record what this cell
looked like on the day they were fitted. **It cannot have fitted itself to the
renderer**, so it needs none of the randomisation that a model fitted here
needs. And **setting it up is a download rather than a training run**.

Against those, one cost lands immediately, and it shapes every section after
this one. **There is no way to teach it anything.** Every difficulty that is
specific to this cell has to be handled either **before** the model, by choosing
what picture to hand it, or **after** the model, by the keeper. Splay, the
single known kind, the guaranteed gap between two glasses, the wide range of
sizes inside one kind: the borrowed model knows none of it and cannot be told.
That is why the sections which follow are about the input and the output, and
why none of this document is about the model's insides.

Freezing a large borrowed model and fitting something small behind it is
ordinary practice, named with its citations in [the general ideas behind
this](#the-general-ideas-behind-this).

## The picture the borrowed model is handed

One thing stands between the input this problem defines and the input the
borrowed model expects, and it is the riskiest choice in the whole design, so it
belongs before the keeper rather than after it.

The bench hands over a grey picture shaded from how far away each surface is,
the depth reading at every pixel, and the camera's own pose. SAM 2, like every
model of its kind, was fitted on ordinary colour photographs. So what it is
shown here is a picture of distances dressed up as a photograph, and the single
grey channel has to be repeated across all three colour channels to be a legal
input at all.

![An ordinary colour photograph of the kind the borrowed weights were fitted on beside the grey picture shaded from depth that this cell renders, with the colour, texture, highlight and shadow boundaries the first carries and the second does not, and the single grey channel repeated across all three colour channels.](../../../images/02-segment-glasses/05-the-domain-gap.png)

A **domain gap** is the difference between the examples a model was fitted on
and the examples it is used on. The physics comparison is exact and worth
holding on to: a formula fitted over one range of temperatures and then used
outside that range does not announce that it has left the range. It returns
numbers, confidently, and they are wrong. A model with a domain gap behaves the
same way, which is why a gap has to be looked for on purpose rather than waited
for.

Four things differ between the two kinds of picture, and they do not all point
the same way.

**Brightness means distance rather than surface.** In a photograph a step in
brightness is usually a step between materials, or a shadow edge, or a
highlight. Here it is a step in distance and nothing else. The two agree at a
glass's silhouette, where the wall and the table behind it really are at
different distances, and they disagree nearly everywhere else.

**There is no texture anywhere.** Photographs carry grain, wood, print and dirt,
while a picture shaded from depth is smooth by construction, so a model leaning
on texture boundaries finds none to lean on.

**Glass does not look like glass.** In a photograph it is transparent, carries
highlights and bends what is behind it, while shaded depth draws it as an opaque
solid with a clean outline. That happens to be in this solution's favour,
because the glasses in this problem are opaque anyway, and it is favour by
accident rather than by design.

**Missing readings leave holes.** Wherever the depth camera returns nothing, the
shading has to invent a brightness, and a hole filled with a constant is a
region with a crisp edge which the borrowed model will happily propose as an
object.

Three prescriptions follow, and they are prescriptions rather than descriptions
of anything built. Shade so that silhouettes are the strongest boundaries in the
picture, by normalising each picture's shading to the range of depth that
picture actually contains. Add some shape shading, since the slope of a surface
relative to the camera can be computed from the depth readings themselves, so
that a curved wall reads as curved rather than as a flat ramp. And fill the
holes from their neighbours rather than with a constant, so that a missing
reading does not become an object with an outline.

None of that closes the gap, and the honest claim is smaller: it makes the
picture more like the pictures the weights were fitted on. The problem itself
says that the two kinds of glass with a stem are harder than the two without,
and that the stemmed glass is the hardest of the four, and that ordering is
exactly what a shaded depth picture makes worse, because a stem is thin and the
silhouette it offers is nearly nothing. Where the shading cannot be made good
enough, the remedy is not available inside this solution at all: it is solution
4 or solution 6, where the weights are allowed to move towards the pictures this
cell really produces.

## The keeper

The keeper is where this solution stops being borrowed. It is to run once per
surviving proposal, read a short table of numbers about that proposal, and
return how likely it is that the proposal is exactly one glass.

### What the keeper is shown

The keeper is not shown pixels, and the reason is not cost. It is that the
useful facts about a proposal are not in its pixels but in what its pixels mean
on the table, and this project already has the arithmetic that works that out.

Every proposal's pixels carry depth readings, because the glasses here are
opaque, so each proposal becomes a set of points in the room. The points at the
top of the proposal give its middle, because seen from the top a rim leans
outwards while its own middle stays over the glass, and how far the cloud of
points reaches from that middle gives a width. The heights of those same points
say how far the proposal's surface stands above the table. The rest of the
measurements come from the shape of the outline, from the depth readings along
that outline, and from the other proposals lying beside it. The keeper would be
shown a handful of them, and they are worth walking through in order.

**Where the measured width falls inside the range this kind of glass allows** is
the strongest single input, because the kind is known and the range of widths
that kind is drawn from is known with it. A footprint narrower than the
narrowest glass of this kind can be is a part of something rather than a glass,
and one wider than the widest is more than one thing.

**How round the proposal is**, meaning its own area against the area its outline
could enclose, comes next. A filled disc is as round as a region can be, while a
ring, a crescent, and two footprints joined by a strip of table all fall well
short of that.

**How far its surface stands above the table** follows from the same points, and
it is what tells the table apart from everything standing on it, because bare
table lies at the table's own height and a glass stands clear of it.

**How far it sits from the point directly below the camera** is about the
viewpoint rather than about the glass. A glass directly below the camera is seen
straight down and shows almost none of its wall, while one far out from that
point leans away and shows a great deal of it, so the same glass gives a
differently shaped proposal in the two places, and the keeper is told which of
the two it is looking at.

**How many prompt points returned this same mask** is counted by the duplicate
removal already and costs nothing to keep, and a region that many points of the
grid agreed on is a firmer thing than one a single prompt found.

**Whether another proposal contains it, or it contains one**, which is called
the **containment** measurement from here on, is the input a hand-written rule
always forgets, and it is how a part declares itself. A rim is a proposal
sitting entirely inside a larger proposal whose own width is perfectly legal,
and that larger proposal is one holding a smaller one, so a single count read
both ways separates a part from the whole it belongs to.

**How much of its outline is a step in depth rather than a smooth run** is the
last thing the picture itself can offer. Where a glass ends, the depth reading
jumps from its wall to the table behind it, so an outline made of such jumps is
the outline of a thing standing on the table, while an outline running smoothly
across one surface is a boundary the cut-off drew rather than one the room
holds.

**How much table the proposal stands over** closes the list, and it is an area
on the table rather than a count of pixels, which is what separates the table
itself from anything that could be a glass of this kind.

| What the measurement says | Why it bears on the question |
| --- | --- |
| where the measured width falls in the range this kind allows | the kind's range of widths is known, so a width outside it is not one glass of this kind |
| how round it is, its own area against the area its outline could enclose | a glass seen from the top is a filled disc whatever the splay, while a rim is a ring and a joined pair has a waist |
| how far its surface stands above the table | a proposal lying at the table's own height is the table |
| how far it sits from the point directly below the camera | splay grows with that distance, so the same glass gives a different proposal near the camera and far from it |
| how many prompt points returned this same mask | a region the grid agreed on many times is firmer than one a single prompt found |
| whether another proposal contains it, or it contains one | a proposal inside a legal glass is a part of that glass, and the glass is the proposal that holds it |
| how much of its outline is a step in depth rather than a smooth run | a thing standing on the table ends where the depth jumps to the table behind it |
| how much table it stands over | the table stands over far more of itself than any glass of this kind can cover |

Every one of those is a **length, a count or a ratio, and not one of them is an
address in the picture**, which is a requirement rather than a preference. The
reason is plain: a pixel address means something different from every place the
camera can stand. The camera here is on the wrist, so it visits several stations
over the glass zone and the same glass appears at a different address in each
picture, while its footprint width, its roundness and its height above the table
are the same numbers from all of them. An input measured in pixels would
therefore teach the keeper about where the camera was parked when the
arrangements for fitting it were rendered, which is exactly the lesson it must
not learn. The one input that does speak about the camera speaks about it on
purpose, because how far a proposal sits from the point below the camera is how
much splay to expect in it.

One worry about that list is worth settling before the list is used, because the
list invites it. Seen from the top, the **mouth** of a glass is a filled disc
whose footprint is the footprint of the glass it belongs to: a width the kind
allows, as round as a footprint gets, and standing well clear of the table. On
every measurement taken from the footprint a mouth therefore looks exactly like
one glass, so the worry is that the keeper holds a mouth as a glass of its own
beside its own glass, and the report then names more glasses than the table
holds.

It does not, and the reason is where a mouth lands rather than what it measures.
A mouth's footprint is its own glass's footprint, so a mouth kept as a glass
would be reported at the place that glass already stands, and a rule of **one
report per place on the table** collapses the two into one. Two glasses of one
kind standing side by side are at least the narrowest width that kind allows
apart, so a second report nearer than that is the same glass arriving twice
rather than another glass. The keeper has its own way of noticing a part inside
a whole, which is the containment measurement, and where that is not enough the
geometry still holds the count.

### Why the keeper is fitted rather than written

Every one of those inputs could be a written threshold instead, so the case for
fitting them has to be made rather than assumed, and there are three parts to
it.

**The first is the nature of the evidence, and it is the real argument.** It is
several weak pieces at once, and not one of them is decisive on its own.
Consider a proposal roughly one glass wide, roughly round, and standing clear of
the table: that is one glass, or the near part of two, or a mouth, and no single
measurement separates the three. Consider a proposal slightly wider than the
kind allows: that is two glasses, or one glass whose mask leaked a little onto
the table. In both cases every measurement leans one way or the other and none
of them settles it. Combining several weak pieces of evidence is precisely what
a written threshold does worst and a small fitted model does best, because a
threshold has to commit to a cut on one measurement at a time while a fitted
model can learn that a width near the top of the range matters only when the
roundness is also low. Writing that down by hand means writing a cut for every
combination, and the number of combinations grows faster than anybody will
maintain.

The second part is this solution's own purpose. A page of thresholds over
regions is a programmed solution, and problem 2 already has one of those in
solution 1. The question this solution exists to answer is how little has to be
written down, so the last decision is fitted rather than written.

The third part is that **the labels are free**, which is what makes the second
part affordable. The bench's answer key says which glass owns each pixel, so the
overlap between a proposal and each real glass's pixels is a subtraction and a
division: overlapping one glass well and no other is one glass, overlapping none
is not a glass, and overlapping two of them well is more than one glass. That is
arithmetic rather than judgement, with no annotator and no annotator's mistakes.
Those labels come only from the training half of the arrangements, and the
keeper is never run on the answer key.

### Three answers, not two

That third label is a real answer rather than a spare category, because in this
cell it is the ordinary way for a proposal to be wrong. So the keeper gives
three answers.

**Keep** means the proposal is one glass, so its pixels are that glass's mask
and go into the report.

**Drop** means the proposal is not a glass, which is what the table, a rim and
an unstable region all are.

**More than one glass** is the third, and it is to be handled rather than
discarded. The design is to prompt the borrowed model again with a fresh grid of
points placed only inside that one proposal. That can work where the whole
picture could not, because when one glass stands in front of another the near
glass's rim is much closer to the camera than the far glass's wall, and that
step in depth is the kind of boundary the borrowed model can find. If at least
two of the regions which come back stand at different places on the table with
widths inside the kind's range, the pair is reported as those two glasses.

If they do not, the pair is **reported as an unseparated pair**, carrying its
reason, and handed to [problem 3](../../03-push-glasses-apart/problem.md).
That is not a failure. This project's rule is that anything doubtful is reported
and never guessed, and a pair the arm cannot tell apart is stated as the input
to the next problem rather than turned into one wide glass that everything
downstream would believe.

### What kind of model the keeper is

The keeper's input is a short table of numbers of different kinds — widths,
heights, distances, ratios and counts — and its answer is one of three
categories. That is the case **gradient-boosted decision trees** were made for
(Friedman, *Greedy Function Approximation: A Gradient Boosting Machine*, Annals
of Statistics, 2001), and scikit-learn provides them.

A tree asks threshold questions and lands in a leaf holding a prediction.
Boosting fits one weak tree, then fits the next tree to whatever the first one
got wrong, and adds them up. Trees suit this table for three reasons. They do
not care that a width measured as a length and a ratio between zero and one are
on different scales, so nothing has to be rescaled. They find combinations of
conditions by themselves, which is the whole argument of the section above. And
on a table of this size they would fit in well under a second on an ordinary
processor with no graphics card involved, which is a pleasant contrast with the
model in front of them.

**This is the only one of the six solutions where a classical model does the
deciding.** Solutions 2, 4 and 6 decide with a neural network fitted here,
solution 3 decides with a borrowed network's own list of names, and solution 1
decides with arithmetic a person wrote. Here a borrowed network proposes and a
small classical model disposes, which is also why the deciding can be explained:
the keeper's inputs are a short list of named measurements, so printing them
beside its answer is an explanation a person can read and argue with.

### Calibration, and why the probability needs it

The keeper returns a probability, and before any threshold is put on that
probability it has to be made to mean something.

A probability is **calibrated** when its claims come true about as often as it
says they will: among the proposals it scores very highly, nearly all should
really be one glass, and among those it scores middling, a middling share should
be. A model fitted to be right as often as possible is not fitted to be honest
about how sure it is, and boosted trees in particular tend to push their scores
towards the ends of the range, so a raw score of nine tenths is not a promise
that nine proposals in ten like it are glasses.

That matters here because the score is not used only to sort. It is compared
against a threshold, and a threshold on a number whose size means nothing is a
knob somebody turned until the result looked good. So a small correction from
the raw score to an honest probability is fitted as part of the keeper's own
fit, in **folds**: the table of proposals is cut into parts, and each part takes
its turn at being held back while the trees are fitted on the others and the
correction on it. No correction is therefore fitted on rows the trees behind it
were shown, because a correction fitted on the keeper's own training rows would
learn the keeper's optimism rather than correct it. The correction is
a handful of numbers more, and it is the cheapest honest thing in this
solution.

**One weakness in that is worth naming, because nothing in the run will show
it.** The folds cut the table of proposals row by row, and one arrangement
contributes many rows, so proposals of the same glasses on the same table can
land on both sides of a fold. Those rows are not independent of each other, so
the correction sees something a little easier than a fresh arrangement would be,
and the probability it produces is therefore a little kinder than the truth. The
cure is to cut the folds by arrangement rather than by row, so that every
proposal from one table stays together, and it is not expensive. It is simply
not what this code does today.

With a calibrated probability, the keeper can have **two thresholds rather than
one**, and the band between them means "I cannot tell". A proposal landing in
that band is neither quietly kept nor quietly dropped: it is a reason to take
another picture from another place, which costs arm time and is cheap compared
with being wrong. That band is also where a glass half hidden behind another one
should land, because a footprint fitted to a sliver of a glass is either
narrower than the kind allows or less round than a whole one, or both.

![The keeper gathered into one picture: each proposal is read as eight measurements by a short set of boosted trees, which answers keep, more than one glass, or drop, and the band between the two thresholds on its calibrated probability means take another picture.](../../../images/02-segment-glasses/05-the-keeper.png)

### The arithmetic still decides

One thing does not change from solution 1, and it is what keeps this solution
inside the same safety argument as the rest of the project.

A proposal the keeper wants to keep still has its width measured against the
kind, and if that width falls outside the range this kind of glass can be, the
proposal is **not reported as a glass**, whatever the keeper said. It becomes a
doubtful report carrying its reason instead.

**With one exception, and the exception is about the view rather than the
proposal.** At the cell's own survey height one picture does not hold the glass
zone, so a glass at the edge of a station's frame shows part of its footprint
and the width measured off that part is part of a width. Refusing on it refuses
the view, and that was measured on masks nothing can improve on: handed the
bench's own exact masks, one station at a time over 20 held-out spawned
arrangements, the kind's range of footprints refuses 66 of 297 glass sightings,
and **every one of those 66 reaches the frame edge**. So the check is not put to
a proposal whose mask reaches that edge. What answers such a proposal instead is
the survey rather than a refusal inside one picture: the cell stands at three
overlapping stations, and the report kept is the one from the station the glass
stood nearest the middle of.

A second piece of arithmetic settles what the width check cannot. **Two reports
at one place on the table are one glass reported twice**, because two glasses of
one kind standing side by side have their centres at least the narrowest width
that kind allows apart, so a report landing nearer than that to one already kept
is the same glass arriving a second time, and only the surer of the two keeps
the place. That is geometry the cell guarantees rather than a number somebody
tuned, and it is what holds the count honest when a mouth and the glass below it
are both kept.

So the borrowed model proposes, the keeper sorts, and the geometry disposes. A
fitted component chooses among regions and a rule nobody trained decides whether
the choice is believable, which is what makes a model this foreign safe to use
here at all.

## The second rung — a word instead of a grid

Everything above is one generation of this solution. There is a second, and it
is the most interesting question this document carries, because it would delete
the keeper entirely.

SAM 3 is available through the same library, and it takes **open-vocabulary text
prompts**. Open-vocabulary means the model is not limited to a fixed list of
categories: the prompt is a phrase rather than a point, and the model returns
every instance of the concept that phrase names. So instead of a grid of points
and a keeper, the whole of this solution's finding and deciding would be a
single request for "drinking glass", answered with one outline per glass. There
is no heap to clean up, because nothing proposes the table or a rim in the first
place, and there is nothing to fit, because the naming is done inside the
borrowed model.

**Both rungs are the same solution.** Both borrow a promptable foundation model
and train nothing in this cell. They differ only in where the judgement "this is
a glass" lives: on the lower rung it lives in a small fitted model in this
folder, and on the upper rung it lives inside borrowed weights, reached through
a word.

What is gained is real and worth stating plainly. There is **less code**: no
grid, no scoring and stability gate, no duplicate removal, no table of
measurements, no classifier, no calibration, and no training step of any kind.
There is **nothing fitted at all**, so the solution has no training half of the
arrangements, nothing to keep in step with the cell, and nothing that can be
fitted to the renderer by mistake. And the proposals that do come back are
already about glasses, so the whole class of mistakes the keeper exists to catch
— the table proposed as an object, a rim proposed without its glass — does not
arise.

What is lost is one thing, and it is the thing this document values most. **The
keeper is the one place in the set of six where the deciding is explainable by
printing its inputs beside its answer.** When the keeper drops a region, the
reason is a short list of named measurements and the answer that followed from
them, and a person can read that list, disagree with it, and point at the
measurement that was wrong. A text prompt moves that judgement inside a model
nobody here can inspect, so when it misses a glass there is nothing to print:
the only available response is to try a different phrase and see what happens.
The difference is between a decision with a readable argument behind it and a
decision that can only be measured from the outside.

There is a second loss, and it is about where this solution then sits. **With a
text prompt this solution begins to resemble solution 3**, because both of them
then rely on a borrowed model's own idea of what a glass is. The resemblance is
only partial, because the two reach that idea differently — solution 3 can only
return a name from a list fixed before it was downloaded, while an open
vocabulary is not limited to any list — and the open vocabulary is a genuine
improvement on a fixed list, since the fixed list has to contain something close
enough to a drinking glass while the phrase can simply say so. But the
structural trade is the same one, and it is the trade this solution was built to
avoid: borrowing both halves rather than borrowing the half that transfers and
replacing the half that does not.

One practical note belongs here, because the licence is one of this solution's
advantages and that advantage is not automatically inherited. The terms a newer
generation of weights is released under have to be read for themselves rather
than assumed to match the generation before it, and here that matters more than
as a caution. **The upper rung has not been run on this machine.** The library
holds the model and the code for this rung is written against it, but the newer
weights are gated: the upload will not hand them over without an account that
has been granted access. So this rung has no scorecard, and none has been
invented for it: only the lower rung has been measured.

So the recommendation is still not to choose once. Fit the keeper, because it is
small and it fits in seconds, and run both rungs on the same held-out
arrangements on a machine whose account has been granted the newer weights. The
bench makes that comparison honest, and if the text prompt wins, the keeper is
still the thing that explains why a region was refused.

## The masks are what this contributes

Everything above produces masks, and nothing above produces a place or a width.

Turning a mask into a place on the table and a rough width is the bench's job,
described once in [the test bench](../the-bench.md) and shared by all six
solutions: every mask pixel carries a depth reading, so it becomes a point in
the room, the axis comes from the points at the top of the glass, and the width
is how far the cloud reaches from that axis. **So this solution contributes only
the masks, and any difference in its score belongs to the mask.** It cannot win
by measuring more cleverly and it cannot lose by measuring worse.

One consequence is worth stating because it removes a question this solution
invites. **No model here produces a pose.** The borrowed model produces regions,
the keeper produces a decision about a region, and the pose comes from depth and
the camera's own pose by arithmetic. A glass standing upright on a flat table
has no orientation left to find.

## How the concepts fit together

Everything above is one pipeline, worth seeing in order before the failure
cases, because each stage works only on what the stage before it passed along.

The depth readings are **shaded** into a grey picture. The **picture encoder**
runs once over it. A **grid of point prompts** then goes through the mask
decoder, one cheap pass each, and scoring, stability and duplicate removal
reduce what comes back to a shortlist of **proposals**. Each proposal's pixels
become **points in the room**, and a place, a width, a height above the table
and the rest of the **measurements** come out of those points and of the
proposals beside it. The **keeper** reads the measurements and answers one of
three things, with its probability **calibrated** so that the two thresholds
mean what they say. A proposal it keeps must still pass the **width check**
against the kind before it is reported, and where two reports land at **one
place on the table** only the surer of them survives. A proposal it calls more
than one glass goes back for a **second round of prompts inside itself**.
Anything left over is **reported doubtful**, which for a pair means handing it
to problem 3.

Three things about that chain are worth holding on to.

**The only fitted stage is the keeper**, which reads a table of numbers rather
than pictures, so everything that finds objects is borrowed and none of it knows
anything about this cell.

**The riskiest stage is the shading**, because it is the only place where a
choice that no arithmetic can check changes what every later stage sees.

**The width check sits after the keeper rather than before it**, so a wrong
answer from the keeper still has to get past a rule nobody fitted, and a wrong
keep therefore becomes a doubtful report rather than a wrong glass.

## When the glasses are completely hidden

A glass can be missing from a picture altogether. It stands on the table, it is
opaque, the camera is pointed at the part of the table it stands on, and not one
pixel of it comes back, because a taller glass's outline has been thrown
outwards by splay until it sweeps right over the shorter one. This is the most
dangerous of the three difficulties in [problem 2](../problem.md), every
solution has to say what it does about it, and this solution's answer is a clean
and complete no.

Being exact about why takes five steps, and each one closes a different escape
route.

**There is no region to propose.** The borrowed model grows a mask from the
picture's own content at the place the prompt points at. A prompt point anywhere
over the piece of picture where the hidden glass ought to be lands on the
covering glass, so what comes back is the covering glass, and that answer is
*correct*. Nothing has malfunctioned.

**Prompting harder does not help**, and this is where the property named earlier
matters. A prompt selects; it does not add information. There is no point, no
box and no rough mask that makes the model return a glass which cast no pixels,
because a prompt works on the pixels that are there. A box drawn round the empty
stretch of table returns the table, or the covering glass, depending on where
its edges fall.

**The keeper is never consulted**, because it only ever sees proposals and there
is no proposal for this glass. All three of its answers are about a region that
exists.

**No check can fire.** Every check here is a check on a proposal: the measured
width, how round it is, how far it stands above the table, how many prompts
agreed on it, how it sits among the other proposals. What comes back for the
covering glass is one proposal with a legal width, a round footprint, a proper
height above the table and the agreement of many prompts. **Nothing about it is
wrong.** The picture is one believable glass where two are standing, which is
the shape this difficulty always takes.

![A prompt point over the piece of table where the hidden glass stands lands on the covering glass, so the mask that comes back is the covering glass's, no proposal for the hidden glass ever exists, and the keeper is never consulted about it.](../../../images/02-segment-glasses/05-where-it-stops.png)

**And more model does not help either.** The arrangement with the hidden glass
and the same arrangement with that glass removed produce the same picture, pixel
for pixel. No function of the picture can tell them apart, whatever its size and
however it was fitted, because the thing that differs between the two left no
trace in the input. A larger checkpoint changes nothing, a text prompt on the
second rung changes nothing, and neither would training the borrowed model if
training it were allowed.

One more thing is worth saying, because it is the temptation this solution
invites. A foundation model's strength is that it generalises to objects it
never saw, and it is easy to hope that this covers the hidden case as well. It
does not. The difficulty here is not an unfamiliar object but **an absent one**,
and generalisation handles evidence of a new kind, while here there is no
evidence of any kind.

So this solution cannot handle the completely hidden case and has to hand it on,
and what it hands on is not a glass but a **region**: the part of the table it
could not have seen. Working out that region is arithmetic on splay and on the
glasses that *were* found, and moving the camera to look again is the shared
part of this problem, described once in [looking again at what was
hidden](../hidden-glasses.md), which every solution points at. This solution
contributes the masks those two argue from, and none of the argument.

## A worked example

One picture from the top shows the whole chain working, and failing once. It is
a walk through the design rather than a record of a run.

**The picture.** Five glasses stand in the glass zone, drawn across the kind's
range of sizes, two of them along a line running out from the point below the
camera. The depth is shaded into grey, normalised so that the tallest rim and
the table sit at opposite ends of the range of grey.

**The proposals.** The grid of prompts returns a heap, and after scoring,
stability and duplicate removal a shortlist is left: the table, four regions
each about one glass wide, one region far wider than the kind allows, three rims
and two mouths.

**The keeper.** The table is dropped, on its width and on lying at the table's
own height. The rims are dropped, on being rings rather than filled discs and on
sitting inside proposals whose widths are legal. The mouths are the interesting
case, because their footprints are perfectly legal, so the keeper may well hold
one of them as a glass and nothing it is shown says otherwise. Four proposals
are kept as one glass each, and the wide one is answered "more than one glass".

**The width check and the second round.** All four kept proposals have a width
inside the kind's range, so all four are reported with a mask, and the wide one
fails the check as it should. A fresh grid of points inside that wide region
returns two masks, split along the step between the near glass's rim and the far
glass's wall, and both of their widths land inside the kind's range, so the pair
is reported as two glasses rather than as an unseparated pair.

**One report per place.** The near glass of that pair was also proposed on its
own, so it now arrives twice, and the mouth the keeper held stands at the place
its own glass already occupies. Both are second reports at a place already
taken, so both are dropped, and five glasses are reported where five stand.

**Where it fails.** Behind the tallest glass in the arrangement a sixth glass is
standing that nothing in this run has any opinion about. It cast no pixels, so
no prompt point could reach it, so no proposal exists for it, so the keeper was
never asked. The report says five glasses and one region of table that could not
have been seen, and the second of those two statements is this solution's entire
contribution to finding the sixth.

**What it costs.** Running the borrowed model is the whole of the cost to within
a rounding error: the picture encoder runs once per picture, every prompt after
it is cheap, and what the keeper adds is too small to see beside them. The whole
chain still costs far less than one movement of the arm.

## What it needs

It needs a **deep learning framework** and the environment to run it, which is a
large dependency for a cell whose simplest answer is a page of arithmetic.

It needs a **weights file this project does not own**, which is a real
difference from solutions 2, 4 and 6, whose weights are produced here and can be
produced again at any time. These cannot be produced here at all, so they have
to be fetched, pinned to a version, and stored where a run can find them.

It needs **arrangements for the keeper**, which the bench renders and labels for
nothing, and far fewer of them than a network fitted from scratch needs, because
the keeper learns from a short table of numbers rather than from pictures. The
calibration needs no arrangements beyond those, because it is fitted in folds of
the keeper's own table rather than on a second set of its own.

Fitting the keeper takes **seconds** once the proposals are in hand, with no
graphics card. What takes the time is running the borrowed model over those
arrangements to get the proposals, which is where nearly all of this solution's
cost sits, at fitting time and at run time both. At run time it needs one pass
of the picture encoder per picture, which is the largest single cost here and
still small beside one movement of the arm. The machine is an Apple processor
with integrated graphics and memory shared with the processor, which PyTorch
reaches through its MPS backend, falling back to the processor where that is
absent; no separate graphics card and no CUDA are involved, and the shared
memory is why a model this size fits at all.

And it needs **the shading got right**, which is the only part where a careless
choice makes everything after it worse without anything complaining.

Finally, the **licence is permissive**, which is a real advantage rather than a
footnote. Solutions 3 and 4 use weights under the AGPL, which places conditions
on anything built around them, so on the day this cell becomes a product rather
than an experiment those two have a question to answer and this one does not.

## Where it is strong and where it breaks

**Almost nothing is fitted here, and what is fitted is small, fast and
inspectable.** Everything that finds objects is borrowed whole, and the borrowed
part cannot fall out of step with this cell because it never knew anything about
it. The keeper fits in seconds on a processor, its inputs are a short list of
named measurements, and printing those beside its answer is an explanation a
person can read. No other solution in this set has that property.

**It needs the least data of the four that fit anything**, because a model
learning from a short table of measurements needs a small fraction of the
arrangements a model learning from pictures does.

**It splits the job along the line that transfers.** Shapes are shapes
everywhere, so the proposing half is borrowed with confidence; what counts as a
cup is somebody else's judgement fitted to somebody else's pictures, so the
naming half is replaced. That is the opposite trade from solution 3, and it is
the clearest reason to prefer this solution to that one.

**It notices things nobody described**, because the grid of prompts proposes
every region in the scene, so a spoon left on the table arrives as a proposal
and is answered "not a glass" rather than passed over in silence. Every other
solution in this set is blind to whatever falls outside the one class it knows.

**Its doubt is cheap and explicit.** Three answers rather than two, two
thresholds rather than one, a width check after the keeper and one report per
place on the table: each of those turns a wrong answer into a doubtful report
rather than into a wrong glass, which is what this project asks for.

Against those, the weaknesses are not small.

**The domain gap is the largest risk and it cannot be closed from inside.** The
weights were fitted on photographs and they are being shown depth dressed up as
a grey picture, the two stemmed kinds are where a shaded silhouette offers
least, and the only levers available are the shading and the grid, because
nothing here is trained. Where those levers are not enough, the answer is
solution 4 or solution 6.

**It cannot be taught this cell's hard cases.** Pairs standing closer than the
cell's rule allows, pairs actually touching, a glass half hidden behind another:
all of those can go into a training set for solutions 2, 4 and 6, and none of
them can be communicated to the borrowed model at all.

**Every part of it works by finding regions and the boundaries between them**,
so it inherits what every boundary method inherits: where the evidence holds no
boundary, nothing finds one. Two glasses that run together with no seam anywhere
along the join are proposed as one region, for the same reason that a rule
following connected pixels would join them.

**It depends on depth twice over.** The keeper's best inputs — the footprint
width and the height above the table — come from depth readings, and so does the
picture itself, because the picture *is* shaded depth. So on the day the glasses
become real transparent glass and the depth camera stops returning anything
through them, this solution has no input at all, not even a picture.

**It is blind to a glass hidden completely**, for the reasons worked out above,
and that is a fact about the input rather than about the model.

## The general ideas behind this

Nothing here is new. It is a foundation model used zero-shot, a grid of prompts,
a standard cleanup, a small classifier on top and a calibration step, and each
one has a literature and a set of cases where it is the right answer.

### Foundation models — one very expensive fit, reused many times

A very large model is fitted once on a very broad collection of data and then
used, unchanged or lightly adapted, for many tasks it was not fitted for. The
term and the argument are set out by Bommasani and colleagues, 2021
([arXiv:2108.07258](https://arxiv.org/abs/2108.07258)); the general mechanism is
[transfer learning](https://en.wikipedia.org/wiki/Transfer_learning).

It is normally the right tool when the fit is far too expensive to repeat, when
your own labels are scarce, and when your task is one of many similar ones. It
is normally the wrong tool when the task is narrow, the labels are free, and the
borrowed model's world differs from yours — which is exactly the argument
solution 2 makes for fitting a small network here from nothing.

### Promptable segmentation — Segment Anything

The model takes a picture and a prompt — a point, a box or a rough mask — and
returns a mask, with several masks and a quality estimate for each when the
prompt is ambiguous. It is class-agnostic, so it outlines without naming.
Kirillov and colleagues, 2023
([arXiv:2304.02643](https://arxiv.org/abs/2304.02643)) introduced it, and the
second generation extends the same idea to video by carrying a memory between
frames (Ravi and colleagues, 2024,
[arXiv:2408.00714](https://arxiv.org/abs/2408.00714)). The video memory is not
used here, because this problem is answered one picture at a time, but the
second generation's stronger picture encoder is the reason to prefer it.

It is normally the right tool when you need the outline of something you cannot
name in advance, when a person is choosing among the proposals, or as the first
stage of something that classifies. It is normally the wrong tool when you need
a decision rather than an outline, because it names nothing; when objects are
defined by something other than their appearance boundaries; and when the input
is not a photograph, which is the risk this document gives a whole section to.

### Open-vocabulary segmentation — a phrase instead of a point

A model takes a phrase in ordinary language and returns every instance of the
concept that phrase names, rather than choosing from a fixed list of categories.
The idea that a phrase and a picture can be matched in one space became
mainstream with CLIP (Radford and colleagues, 2021,
[arXiv:2103.00020](https://arxiv.org/abs/2103.00020)), and the segmentation
models built on it are the second rung of this solution.

It is normally the right tool when the thing you want is easy to say and hard to
write a rule for, and when nobody needs to audit the decision. It is normally
the wrong tool when the decision has to be explainable, because the judgement
lives inside weights nobody can inspect, and when the concept you mean is
narrower than the phrase you have, since you cannot tell the model which of
several readings you meant.

### Propose, then classify

Producing many candidate regions with a cheap general method and then deciding
about each one separately is an old structure. It is how R-CNN worked (Girshick
and colleagues, 2013, [arXiv:1311.2524](https://arxiv.org/abs/1311.2524)), with
selective search (Uijlings and colleagues, *International Journal of Computer
Vision*, 2013) as the proposer. This solution is that structure with a far
better proposer and a far smaller decider.

It is normally the right tool when missing an object at the first stage is much
worse than proposing too many, because a later stage can always reject. It is
normally the wrong tool when the proposer and the decider disagree about what
counts as one object, which is this document's "more than one glass".

### Zero-shot transfer — using a model on a task it was never fitted for

A model is applied to a task, or to data, it was not fitted on, with no further
fitting. The general notion is [zero-shot
learning](https://en.wikipedia.org/wiki/Zero-shot_learning).

It is normally the right tool when you have no labels at all, and as the first
thing to try before anything is fitted, because it costs a download. It is
normally the wrong tool when you do have labels and the task is narrow, because
fine-tuning then wins nearly always, which is the argument solutions 4 and 6
make against this one.

### A small head on frozen features

Freeze a large borrowed model, take what it produces, and fit something small on
top of it. This was shown to work early and well (Donahue and colleagues, 2013,
[arXiv:1310.1531](https://arxiv.org/abs/1310.1531); Razavian and colleagues,
2014, [arXiv:1403.6382](https://arxiv.org/abs/1403.6382)), and it is the
standard first thing to try with any borrowed model. The keeper is this pattern
with one difference: it is shown measurements computed from each proposal rather
than the model's own internal numbers, because measurements on the table mean
the same thing from every viewpoint and can be read by a person.

It is normally the right tool when data is small and the borrowed features
already contain what the task needs. It is normally the wrong tool when they do
not, because no small head recovers a distinction the frozen part threw away,
and at that point the weights themselves have to move.

### Gradient-boosted decision trees

Many weak trees are fitted one after another, each to the errors of the ones
before it, and added up (Friedman, *Greedy Function Approximation: A Gradient
Boosting Machine*, Annals of Statistics, 2001).

It is normally the right tool for a short table of numbers of mixed kinds with a
category to predict, which is exactly the keeper's job, and it needs no
rescaling of the inputs. It is normally the wrong tool for raw pixels, sound or
text, where a network that can learn its own features wins easily.

### Calibration — making a score mean what it says

A model's output is turned into an honest probability by fitting a small
correction on data the model was not fitted on, either a shape with two
parameters (Platt, 1999) or a monotone staircase ([isotonic
regression](https://en.wikipedia.org/wiki/Isotonic_regression), Zadrozny and
Elkan, 2002). Boosted trees are a standard example of a model that needs it,
because boosting pushes scores towards the ends of the range.

It is normally the right tool whenever a threshold or a cost is going to be
applied to a score, which is the keeper's case exactly. It is normally
unnecessary when only the ordering is used, because a correction that never
decreases cannot change an ordering, and it is not a repair for a model that is
simply wrong: a calibrated bad model is honestly unsure rather than secretly
unsure.

### The domain gap, and sim-to-real

A model carries the habits of the collection it was fitted on, argued memorably
by Torralba and Efros, *Unbiased Look at Dataset Bias*, CVPR 2011; the general
problem is [domain adaptation](https://en.wikipedia.org/wiki/Domain_adaptation).
There are three usual repairs: make the synthetic pictures look more like real
ones, make the model insensitive to the difference by varying everything that is
not the task (domain randomisation, Tobin and colleagues, 2017,
[arXiv:1703.06907](https://arxiv.org/abs/1703.06907)), or translate one
appearance into the other with a fitted model (Zhu and colleagues, 2017,
[arXiv:1703.10593](https://arxiv.org/abs/1703.10593)).

Two things are unusual about the gap in this solution. It runs **the opposite
way** from the usual sim-to-real direction, because the weights come from
photographs while the pictures come from a renderer. And the standard repair is
**not available**, because randomisation happens while training and nothing here
is trained, so the only lever is the input.

Randomisation is normally the right tool when you control the training and want
robustness against an appearance you cannot predict, and appearance translation
when you have examples of both appearances and nothing simpler works. Neither is
right when the model cannot be trained at all, and then the honest options are
to change the input or to stop borrowing.

## Where it sits among the other five

The comparison worth making first is against **solution 3**, because the two are
the only solutions here that fit nothing that finds objects, and they make
opposite choices about what to borrow. Solution 3 borrows a model's shapes and
its names together, so the whole answer is the borrowed model's own idea of what
a glass is. This solution borrows the shapes and replaces the names with
something fitted here and readable. That is the better half to replace, because
a boundary between one surface and the surface behind it transfers from
photographs to this cell far better than a category boundary does. The second
rung of this solution gives that advantage back, which is why the section about
it is careful rather than enthusiastic.

Against **solution 4** the comparison is about where the adaptation happens.
Solution 4 moves the borrowed weights towards this cell's pictures, which is the
honest remedy for the domain gap and the only remedy this solution does not
have. What it costs is a training run that has to be repeated whenever the cell
changes, and a weights file that is a second copy of the cell. This solution has
no such file and therefore nothing that can go stale, and it pays for that with
a worse outline wherever the shading serves the kind badly.

Against **solutions 2 and 6** the two sit at opposite ends of one axis. Those
borrow nothing and fit everything; this borrows everything and fits almost
nothing. Their weights are produced here and are a second copy of this cell,
which has to be kept in step with it; this solution's weights are large, owned
by somebody else, and know nothing about this cell to be out of step with. They
cost hours of rendering and fitting; this costs a download and minutes. And the
honest half of that comparison is that they can be taught this cell's hard cases
and this one cannot.

![Beside the borrowed weights, which arrive already fitted and never move again, the numbers fitted in this cell are a rounding error, where solution 2 brings nothing in and fits every number it uses on this cell's own pictures.](../../../images/02-segment-glasses/05-borrowed-against-trained.png)

Against **solution 1** the comparison is the least flattering, and it should be
stated plainly. Solution 1 is a page of arithmetic: no training set, no weights,
a cost in run time too small to be worth naming beside a pass of a picture
encoder, and its failures explained by printing one number of its own. On any
day the depth readings work it is the simpler tool, and this solution does not
survive the loss of depth either, since it needs depth for the keeper's inputs
*and* to make the picture at all. So this is not the solution that survives real
glassware. It is the solution that survives having almost no training data,
which is a different and narrower virtue.

What this solution is genuinely for is to find out how far borrowed weights get
in this cell with almost nothing fitted behind them, and to find out at what
point an explainable decision is worth more than a shorter program. The bench
answers the first question by running it beside the other five on the same
arrangements. The second question is the one the two rungs of this solution ask
of each other, and it is a judgement rather than a measurement.

← [The same model, fine-tuned here](04-yolo-fine-tuned.md) · [RF-DETR-Seg,
fine-tuned here](06-rf-detr-fine-tuned.md) →
