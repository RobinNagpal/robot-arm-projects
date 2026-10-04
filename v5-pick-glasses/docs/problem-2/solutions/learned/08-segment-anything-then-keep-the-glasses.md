# Solution 8 — segment anything, then keep the glasses

*Learned, as the decider. A large segmentation model that was fitted somewhere
else outlines everything in the picture, and the only thing fitted in this cell
is a small learned keeper sitting after it, deciding which of those outlines are
glasses.*

> **The cell is described once, in [the cell](../../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to answer problem 2 with almost nothing fitted in
this cell at all. Every other learned solution here fits a model to this cell's
own pictures. This one fits nothing that finds objects: the finding is done by a
model somebody else trained on photographs of the real world, used exactly as it
was downloaded, and the only numbers fitted here belong to a small classifier
that looks at what that model produced and decides which parts of it are
glasses.

The solution therefore has two halves, and they are extremely unequal in size.
The first is a **borrowed model** that can be asked to outline whatever is at a
given place in a picture. Asked at many places at once, it outlines everything
the picture contains — the glasses, the table, the rim of a glass, two glasses
that merged into one shape — knowing nothing about what a glass is, because it
names nothing. The second is the **keeper**, a small fitted classifier handed
each of those outlines, which says whether it is one glass.

By the end you will understand what a foundation model is and what it means for
one to be promptable, how a plain grid of point prompts turns such a model into
a proposer of everything in a scene, why the large model is never trained here
and what that buys, what the keeper is shown and why it is fitted rather than
written, and what happens to the proposals that turn out to be the table, or the
rim of a glass without the glass, or two glasses at once.

You will also understand the tension it lives with, because it runs through
every section. **This is the least trained and the most borrowed of all the
solutions in this problem.** It needs the least data of any of them and brings
the largest gap between what its weights were fitted on and what it is shown,
and those two facts are the same fact seen from two sides.

That gap does not fall evenly on the four kinds of glass this cell knows, and it
falls in the same order every time. Shown a grey picture shaded from depth, the
borrowed model outlines a straight glass or a tapered one almost exactly, it
cuts into the bowl of a short stemmed one, and it cuts worst of all into the
stemmed kind, where the best proposal for a glass typically holds about four
fifths of it and a minority of glasses are cut badly. What it loses there is the
accuracy of the outline rather than the glass itself, and that is still the
worst result anywhere in this solution and the strongest argument against it. It
is worked through in [the domain
gap](#the-domain-gap-which-is-the-largest-risk-here).

## The problem this solves

Four to six glasses stand on the table. They are all of one kind, the kind is
known, and they are solid, so the depth camera sees them. The job is to say
which pixels belong to which glass, to give each glass a place on the table, and
to give each a rough footprint width. Nothing is picked up and no shape is
measured here.

What is asked for is **instance segmentation**, one mask per object rather than
one label per pixel, because the count of the glasses is part of the answer. The
[overview](../solution-overview.md) sets that distinction out for all the
solutions.

The other solutions reach that answer at one of two prices, and this solution is
an attempt to pay neither.

The programmed solutions pay in **rules somebody has to write**. Solution 1
splits a region in the picture and solution 2 groups points on the table, and
both need a human to work out the rule and the limits inside which it is safe.
Its cost is that somebody must be able to state the rule in the first place.

The learned solutions pay in **fitting**. Solution 6 trains a network on this
cell's own renders, and the cost there is not the labels, which the simulator
gives away, but the training itself: hours of rendering, hours of fitting, and
afterwards a file of weights that is a second copy of the world. Change the
lighting, change the table's texture, widen the range of sizes a kind is drawn
from, and that file is quietly out of date in a way no test of the code will
notice.

This solution avoids the second price by borrowing weights that were never
fitted to this cell, so nothing in them can go out of date with it, and it
avoids most of the first by fitting the one decision that remains.

The catch is visible already, and the rest of the document is largely about it.
**A model that was never fitted to this cell also never saw this cell.** It does
not know about splay, it does not know that there is one kind of object, it does
not know the gap the cell guarantees between two glasses, and there is no way to
tell it any of those things.

## The main idea

The main idea is to stop asking for glasses and start asking for everything,
then throw away what is not a glass.

**The first half is to ask for everything.** Instead of fitting something that
finds glasses, take a model that can be asked *what is at this point?* and get
back an outline of the thing at that point. Ask it at points spread evenly over
the whole picture. Every point lands on something, so what comes back is an
outline of the table, an outline of each glass that is distinguishable at all,
outlines of parts of glasses, and outlines of groups of glasses. None of them
carries a name, because the model produces regions and not labels. The model
used here is **SAM**, the Segment Anything Model, in its smallest released size,
`facebook/sam-vit-base`, and it is never trained in this project.

**The second half is to decide what to keep.** Each surviving outline is called
a **proposal** from here on, and the **keeper** is a small classifier that is
shown a handful of measurements about a proposal and returns how likely that
proposal is exactly one glass. The keeper is the only fitted thing in this
solution, it fits in seconds, and it learns from scenes where the simulator
knows which pixels belong to which glass.

So, in the plainest terms: **everything that finds objects is borrowed whole,
and everything fitted here is one small decision at the end.** Beside the
borrowed model's weights, the keeper's numbers are a rounding error.

The rest of this document builds that up in order: what a foundation model is
and what promptable means, how a grid of prompts turns one into a proposer of
everything, why the large model is never trained, what the keeper is shown, the
one risk that lives at the input, and where the whole thing stops.

## What a foundation model is

Before the main idea can be made precise, the word for the borrowed half has to
be defined, because everything this solution buys and everything it risks comes
out of the definition.

A **foundation model** is a model fitted once, on a very large and very general
collection of data, at a cost nobody expects to repeat, and then used for many
tasks it was not specifically fitted for. The fit is done by somebody with a
warehouse of machines; the use is done by everybody else with a download. A lens
is the closest physical comparison: it was ground for no particular photograph,
it suits an enormous range of them, and it knows nothing about the scene in
front.

One property of SAM is what makes it usable in this project at all. **SAM is
class-agnostic**: it returns regions with no labels attached. It has no list of
object types and is never asked to recognise anything, so it never needs to know
the word glass, and the fact that it was fitted on photographs of everyday
things rather than on glasses in a simulated cell does not by itself disqualify
it.

SAM has three parts, and the split between them matters later. A **picture
encoder** turns the whole picture into a block of numbers, and this is the
expensive part, run once per picture. A **prompt encoder** turns the prompt into
a small block of numbers. A **mask decoder** combines the two and produces a
mask, and this part is cheap, run once per prompt.

### What promptable means

The word that does the work above is *promptable*, and it is not the same idea
as a network that takes a picture and returns an answer.

![A single picture with three different point prompts on it, and the three
different masks that come back from the same unchanged
weights](../../../../images/problem-2/08-what-promptable-means.png)

A **prompt** is a small extra input that says *which* thing in the picture you
mean: for SAM a point, meaning "the thing here", a box, meaning "the thing
inside this rectangle", or a rough mask. The picture and the prompt go in
together and one mask comes out, and changing the prompt while leaving the
picture alone gives a different mask from exactly the same weights. The model is
a function of two arguments rather than one, so one picture has as many answers
as you ask for.

There is a second part of promptability, and it is the more interesting part.
**Ambiguity is returned rather than resolved.** A point on the wall of a glass
genuinely could mean three things: that patch of wall, the whole glass, or the
glass together with whatever it stands in front of. SAM does not guess. For one
point it returns several masks at different extents — roughly a part, a whole,
and something larger — each with its own estimate of how good that mask is, and
the choice is handed back to whoever asked. That behaviour is why the pile of
proposals later in this document contains a rim without its glass, and it is
what gives the keeper something to choose between rather than one answer to
accept.

One more property has to be stated here, because the last section of this
document rests entirely on it. **A prompt selects; it does not add
information.** Pointing at a picture says which part of that picture interests
you. It cannot tell the model about anything the picture holds no evidence of.

## Turning a promptable model into a proposer of everything

If one prompt gives one thing, then many prompts give many things, and that is
the whole of the trick that turns SAM from a tool somebody points at objects
into something that finds the objects by itself.

![A regular grid of prompt points laid over the picture from the top, with the
points landing on the table, on glass walls, on rims and on
mouths](../../../../images/problem-2/08-the-prompt-grid.png)

Lay a regular grid of points over the picture taken from the top and prompt once
at every point. The grid does not aim at anything, which is the point of it:
nothing has to know where the glasses are before they have been found. Each
point lands on whatever is under it — bare table returns the table, a glass wall
returns that wall, that glass and something larger, a mouth returns the mouth —
and a grid fine enough to put several points on the smallest glass this kind
allows touches everything in the scene at least once.

The reason this is affordable is the three-part split named above. The expensive
picture encoder runs **once**, and every prompt after it is one pass through the
small mask decoder, so prompting at every point of a grid costs very little more
than prompting once.

### What comes back, and the cleanup that is not learned

What comes back is not a list of objects but a heap, with three problems in it.
Many grid points land on the same glass, so the same region arrives dozens of
times with slightly different edges. For one point the model returns a part, a
whole and something larger, so the heap holds a rim, the glass the rim belongs
to, and that glass together with its neighbour, all of them defensible answers
to the same prompt. And some masks are simply unstable, which is the signature
of a boundary the model is not really sure about.

The repairs are standard and none of them involves fitting. **Drop the
low-scoring masks**, using the quality estimate SAM already returns with each
one. **Drop the unstable ones**, by nudging the cut-off that turns the model's
output into a yes-or-no mask and keeping only the masks that barely change when
it moves. Then **remove the duplicates** with a step called **non-maximum
suppression**: sort the masks by score, walk down the list keeping each one, and
throw away any later mask that overlaps a mask already kept by more than a
chosen amount. The **overlap** of two masks means the area both claim divided by
the area either claims, which is one for identical masks and zero when they
share nothing.

The quality estimate and the stability earn their keep here and nowhere else.
They are a **gate** rather than evidence: they cut the heap down to a shortlist
before anything else looks at it, and the keeper further on is never shown
either of them, because what it has to decide is what a region is rather than
how sure the borrowed model was about drawing it.

![The proposals that survive the cleanup, drawn over one scene: the table, each
glass, two rims, one mouth, and a pair of glasses as a single
region](../../../../images/problem-2/08-everything-is-proposed.png)

After the cleanup there is a shortlist of regions, each with an outline and a
score, and **not one of them has a name**. The regions are there and they are
good regions, but nothing says which of them are glasses, nothing says the
largest one is the table, and nothing says the pair that merged into one shape
is two glasses rather than one very wide one.

So SAM has answered a different question from the one the problem asks. It has
said *where the regions are*, and the problem asks *which regions are glasses,
and how many*. The rest of this solution is about closing that gap without
training SAM.

## Why SAM is never trained here, and what that buys

The obvious way to close that gap is to train the model, and this solution does
not. **Never trained means the weights file is used exactly as downloaded**: no
gradient is computed through SAM, no layer of it is replaced, and nothing about
this cell reaches its numbers. Running it here is a forward pass.

![On one side the borrowed model, fitted elsewhere on photographs, with all of
the weights and none of the knowledge of this cell; on the other the keeper,
fitted here on simulator scenes, with a handful of numbers and all of the
knowledge of this
cell](../../../../images/problem-2/08-borrowed-against-trained.png)

Four things follow, and together they are the case for this solution. **There is
no training set for the part that finds objects**: scenes are still rendered,
since the keeper has to be fitted on something, but the keeper learns from a
short table of measurements per proposal rather than from pictures. **There is
nothing to go out of date**, because SAM never saw this cell, which is the exact
opposite of solution 6, whose weights record what the cell looked like on the
day they were fitted. **It cannot have fitted itself to the simulator**, so it
needs none of the randomisation solution 6 needs. And **setting it up is a
download rather than a training run**.

Against those, one cost lands immediately and it shapes everything after this
section. **There is no way to teach it anything.** Every difficulty specific to
this cell has to be handled either **before** the model, by choosing what
picture to hand it, or **after** the model, by the keeper. Splay, the single
known kind, the guaranteed gap between two glasses, the wide range of sizes
inside the kind: SAM knows none of it and cannot be told. That is why the
sections that follow are about the input and the output, and none of this
document is about the model's insides.

Freezing a large borrowed model and fitting something small on top of it is
standard practice, named with its citations in [the general ideas behind
this](#the-general-ideas-behind-this).

## The keeper

The keeper is where this solution stops being borrowed. It runs once per
surviving proposal, reads a short table of numbers about it, and returns how
likely that proposal is exactly one glass.

### What the keeper is shown

The keeper is not shown pixels, and the reason is not cost. It is that the
useful facts about a proposal are not in its pixels but in what its pixels mean
on the table, and the project already has the arithmetic that works that out.

Every proposal's pixels have depth readings, because the glasses here are solid,
so each proposal becomes a set of points in the room the same way [cluster on
the table](../programmed/02-cluster-on-the-table.md) makes them. The points at
the top of the proposal give its middle, because seen from the top a rim leans
outwards while its own middle stays over the glass, and how far the cloud of
points reaches from that middle gives a width. The heights of the same points
say how far the proposal's surface stands above the table. The rest come from
the shape of its outline, from the depth readings along that outline, and from
the other proposals beside it. **The keeper is shown eight measurements of one
proposal**, and they are worth walking through in the order it reads them.

**Where the measured width falls inside the range this kind of glass allows** is
the strongest single input, because the kind is known and its range of widths is
known with it. A footprint narrower than the narrowest glass of this kind can be
is a part of something rather than a glass, and one wider than the widest is
more than one thing.

**How round the proposal is**, meaning its own area against the area its outline
could enclose, is the next. A filled disc is as round as a region can be, while
a ring, a crescent, and two footprints joined by a strip of table are all well
short of that. **How far its surface stands above the table** follows from the
same points, and it is what tells the table from everything standing on it: bare
table lies at the table's own height, and a glass stands clear of it.

**How far it sits from the point directly below the camera** is about the
viewpoint rather than about the glass. A glass directly below the camera is seen
straight down and shows almost none of its wall, while one far out from that
point leans away and shows a great deal of it, so the same glass gives a
differently shaped proposal at the two places and the keeper is told which of
the two it is looking at. **How many prompt points returned this same mask** is
counted by the duplicate removal and costs nothing to keep: a region that many
points of the grid agreed on is a firmer thing than one a single prompt found.

**Whether another proposal contains it, or it contains one**, which is called
the **containment** measurement from here on, is the one a hand-written rule
always forgets, and it is how a part declares itself. A rim is a proposal
sitting entirely inside a larger proposal whose own width is perfectly legal,
and that larger proposal is one holding a smaller one, so a single count read
both ways separates a part from the whole it belongs to.

**How much of its outline is a step in depth rather than a smooth run** is the
last thing the picture itself can offer. Where a glass ends, the depth reading
jumps from its wall to the table behind it, and an outline made of such jumps is
the outline of a thing standing on the table, while an outline running smoothly
across one surface is a boundary the cut-off drew rather than one the room
holds. **Its area on the table** closes the list, and it is how much table the
proposal stands over rather than how many pixels it has, which is what separates
the table from anything that could be a glass of this kind.

![The keeper as a funnel taking many proposals and answering one of three things
about each, with its two thresholds and the eight measurements it reads set out
beside them](../../../../images/problem-2/08-the-keeper.png)

| What the measurement says | Why it bears on the question |
| --- | --- |
| where the measured width falls in the range this kind allows | the kind's range of widths is known, so a width outside it is not one glass of this kind |
| how round it is, its area against the area its outline could enclose | a glass from the top is a filled disc whatever the splay, while a rim is a ring and a joined pair has a waist |
| how far its surface stands above the table | a proposal at the table's own height is the table |
| how far it sits from the point directly below the camera | splay grows with that distance, so the same glass gives a different proposal near the camera and far from it |
| how many prompt points returned this same mask | a region the grid agreed on many times over is firmer than one a single prompt found |
| whether another proposal contains it, or it contains one | a proposal inside a legal glass is a part of that glass, and the glass is the proposal that holds it |
| how much of its outline is a step in depth rather than a smooth run | a thing standing on the table ends where the depth jumps to the table behind it |
| its area on the table | the table stands over far more of itself than any glass of this kind can cover |

Every one of those is a length, a count or a ratio, and not one of them is an
address in the picture, so a proposal means the same thing to the keeper
wherever in the frame it landed. That property is required of any model fed
numbers rather than pixels, and for a plain reason: an input measured in pixels
means something different from every place the camera can stand. The one input that does speak about the camera speaks
about it deliberately, because how far a proposal sits from the point below the
camera is how much splay to expect in it.

One worry about that list is worth settling before the list is used, because the
list invites it. Seen from the top, the **mouth** of a glass is a filled disc
whose footprint is the footprint of the glass it belongs to: a width the kind
allows, as round as a footprint gets, and standing well clear of the table. On
every measurement taken from the footprint a mouth therefore looks exactly like
one glass, and the worry is that the keeper holds the mouth as a glass of its
own beside its own glass, so that the report names more glasses than the table
holds.

It does not, and the reason is where a mouth lands rather than what it measures.
A mouth's footprint is its own glass's footprint, so a mouth kept as a glass is
reported at the place that glass already stands, and the rule that keeps **one
report per place on the table** collapses the two into one. Two glasses of one
kind standing side by side are at least the narrowest width that kind allows
apart, so a second report nearer than that is the same glass arriving twice
rather than another glass. The keeper has its own way of noticing a part inside
a whole, which is the containment measurement, and where that is not enough the
geometry still holds the count. Nothing in the run invented a glass.

### Why the keeper is learned rather than written

Every one of those inputs could be a threshold instead, so the case for fitting
them has to be made rather than assumed, and there are three parts to it.

The first is the nature of the evidence. **It is several weak pieces at once,
and not one of them is decisive.** A proposal roughly one glass wide, roughly round and
standing clear of the table: is that one glass, the near part of two, or a
mouth? A proposal slightly wider than the kind allows: two glasses, or one whose
mask leaked onto the table? Combining several weak pieces of evidence is what a
threshold does worst and a fitted model does best.

The second is this solution's own purpose. A page of thresholds over regions is
a programmed solution, and problem 2 already has two of those. The question here
is how little has to be written down, so the last decision is fitted.

The third is that **the labels are free**, which makes the second affordable.
The simulator returns a glass identity for every pixel, so the overlap between a
proposal and each glass's true pixels is a subtraction and a division:
overlapping one glass well and no other is one glass, overlapping none is not a
glass, and overlapping two well is more than one glass. That is arithmetic
rather than judgement, with no annotator and no annotator's mistakes.

### Three answers, not two

That third label is a real answer rather than a spare category, because in this
cell it is the normal way for a proposal to be wrong.

**Keep** means the proposal is one glass, so its fitted centre and width go into
the report and its pixels are that glass's mask. **Drop** means it is not a
glass. **More than one glass** is handled rather than discarded: prompt SAM
again with a fresh grid of points placed only inside that proposal, which
sometimes returns the two glasses separately, because the near glass's rim
stands much closer to the camera than the far glass's wall and that step is
something SAM can find. If at least two of the new regions stand at different
places with widths inside the kind's range, the pair is reported as those
glasses.

If they do not, the pair is **reported as an unseparated pair**, with its place
and its reason, and handed to [problem 3](../../../problem-3/problem.md). That
is the ending solution 6 reaches for the same situation, and it is a result
rather than a failure: anything doubtful is reported, and never guessed.

### What kind of classifier it is, and one property it must have

The keeper's input is a short table of numbers of different kinds — widths,
heights, distances, ratios and counts — and its answer is one of three
categories. That is the case **decision-tree boosting** was made for (Friedman,
*Greedy Function Approximation: A Gradient Boosting Machine*, Annals of
Statistics, 2001), and it is the same choice [solution
4](04-choosing-the-next-look.md#why-trees-rather-than-a-network) makes for the
same reason. A tree asks threshold questions and lands in a leaf holding a
prediction; boosting fits a weak tree, then fits the next one to whatever the
first got wrong, and adds them up. On a table this size it fits in well under a
second with no graphics card, which is a pleasant contrast with the model in
front of it.

Before any threshold is put on its output, the probability has to be
**calibrated**, meaning its claims come true about as often as it says they
will. [Solution
5](05-a-model-that-already-knows-a-glass.md#the-number-beside-each-outline-and-why-it-is-not-a-probability)
sets out what that means and how it is repaired, and none of it differs here.
What is worth adding is that the keeper has **two thresholds rather than one**,
with the band between them meaning "I cannot tell". A proposal in that band is
not silently kept or dropped; it is a reason to take another picture, which is
cheap compared with being wrong.

On scenes it was never fitted on, the two thresholds do what they were put there
for. What the keeper keeps is almost always really one glass: nothing it
kept was reported as a glass that was not there, and no report of one covered
two glasses at once. The price of that is paid in the middle band, which is
wide. The keeper hands over far more proposals than it keeps, and nearly every
one of them carries the doubt that it cannot tell whether the proposal is one
glass. A doubtful report is a result rather than a failure in this project, so
that is the solution behaving as it was designed to, but a keeper this unsure is
a keeper that leaves work for the arm, which has to move and look again. [What
running it shows](#what-running-it-shows-and-what-can-be-done-about-it) says how
far each of those two halves goes. What the keeper can do at all is limited by
what it is handed, and what it is handed for a stemmed glass is [the domain
gap](#the-domain-gap-which-is-the-largest-risk-here).

### The arithmetic still decides

One thing has not changed from the programmed solutions, and it is what keeps
this solution inside the same safety argument as the rest of the project. A
proposal the keeper wants to keep still has its width measured against the kind,
and if that width falls outside the range this kind of glass can be, the
proposal is **not reported as a glass**, whatever the keeper said. It becomes a
doubtful report carrying its reason instead, which is one of the things handed
on at the end of a run.

A second piece of arithmetic settles what the width check cannot. **Two reports
at one place on the table are one glass reported twice.** Two glasses of one
kind standing side by side have their centres at least the narrowest width that
kind allows apart, so a report landing nearer than that to one already kept is
not a second glass, and only the surer of the two keeps the place. That is
geometry the cell guarantees rather than a number somebody tuned, and it is what
holds the count to the glasses that are really there when a mouth and the glass
below it are both kept.

So the borrowed model proposes, the keeper sorts, and the geometry disposes. A
learned component chooses among regions and a rule nobody trained decides
whether the choice is believable, which is what makes a model this foreign safe
to use.

## The domain gap, which is the largest risk here

Everything above assumed SAM is being handed a picture it can work on, and that
assumption is the weakest part of this solution by a wide margin.

**The cell's renderer produces a depth reading per pixel and a glass identity
per pixel. It does not produce colour.** SAM, like every model of its kind,
expects an ordinary colour photograph. So the code makes one: it shades the
depth readings into a grey picture and repeats that single channel across all
three colour channels. What SAM is shown is therefore a picture of distances
dressed up as a photograph.

![A photograph of the kind SAM's weights were fitted on beside a grey picture
shaded from depth, with the boundaries each one carries marked
underneath](../../../../images/problem-2/08-the-domain-gap.png)

A **domain gap** is the difference between the examples a model was fitted on
and the examples it is used on. The physics comparison is exact and worth
holding on to: a formula fitted over one range of temperatures and then used
outside that range does not announce that it has left the range. It returns
numbers, confidently, and they are wrong. A model with a domain gap behaves the
same way, which is why a gap has to be looked for rather than waited for.

### What is actually different about the picture

Five things differ, and they do not all point the same way, which is why this
section cannot simply conclude that the solution fails.

**Nothing in the picture is colour**, so a grey picture repeated across three
channels is a legal input and an unusual one, and everything the weights learned
about colour is dead weight here.

**Brightness means distance rather than surface.** In a photograph a step in
brightness is usually a step between materials, or a shadow edge, or a
highlight. Here it is a step in distance and nothing else. The two agree at a
glass's silhouette, where the wall and the table behind it are genuinely at
different distances, and they disagree everywhere else.

**There is no texture anywhere.** Photographs have grain, wood, print and dirt,
while a shaded depth picture is smooth by construction, so a model leaning on
texture boundaries finds none.

**Glass does not look like glass.** In a photograph it is transparent, carries
highlights and bends what is behind it, while shaded depth draws it as an opaque
solid with a clean outline. That is in this solution's favour, because the
simulated glasses are opaque anyway, and it is favour by accident.

**Missing readings leave holes.** Wherever the depth camera returns nothing the
shading has to invent brightness, and a hole filled with a constant is a region
with a crisp edge that SAM will happily propose as an object.

### What running it shows, and what can be done about it

Every other risk here can be reasoned about before anything is run: the width
check follows from the kind's range, the keeper's inputs can be printed, and the
second round of prompting either splits a region or does not. **This one is
settled only by running it**, because how a model fitted on photographs behaves
on a shaded depth picture follows neither from the paper that describes it nor
from this document. Running it, with the weights exactly as downloaded, settles
more than the gap, so the whole of what came back is worth taking first, over
twenty held-out scenes surveyed from three stations each and holding about a
hundred glasses between them.

**It never merged two glasses into one report, and it never invented a glass.**
That holds on both kinds of layout, and no other solution in this folder can say
the first half of it. The width check after the keeper and the one report per
place on the table are what earn it: a footprint wider than the kind allows is
refused rather than reported, and a second report at a place already taken is
the same glass arriving twice. **It finds about three quarters of the glasses
and misses about a quarter.** Where it does report a glass the place is good: on
the ordinary layouts its centres sit closer to the true ones than the fine-tuned
segmenter of [solution 9](09-a-fine-tuned-instance-segmenter.md) manages on the
same scenes. That is worth one sentence and no more, because it reports far
fewer glasses than that solution does and the ones it reports are the easy ones.

The other half of what came back is the doubt. **It hands over far more
proposals than it keeps**, and nearly all of them carry the one reason that it
cannot tell whether the proposal is one glass. A few dozen more are proposals it
read as more than one glass where the second round of prompting did not separate
them, and a handful are proposals it wanted to keep whose width the kind does
not allow. None of that is a malfunction, because a refused glass is a result
here and every one of those proposals is reported rather than guessed at, but it
is the honest measure of what the solution costs: every doubt is work handed to
the arm.

Crowded layouts, where glasses really do stand in front of one another, change
less than might be expected. The share of glasses found is about the same as on
the ordinary layouts, and still nothing was merged and nothing invented. What
crowding does instead is fill the doubts: more pairs arrive that the second
round of prompting cannot take apart, so crowding shows up as more work handed
on rather than as a wrong count.

Those are the shape of the whole solution, and the gap this section is about
lives inside them. The gap itself is measured on its own, by asking the proposal
stage alone, with no keeper and no scorecard, how much of each glass the best
proposal for it holds. That is a handful of scenes of each kind rather than the
whole held-out set, so what comes out of it is a **ranking across the four
kinds** rather than an exact figure for any of them: almost exact on the
straight and the tapered kinds, worse on the two stemmed kinds, and worst on the
stemmed kind, which is the taller of those two.

**On straight and tapered glasses the borrowed model is very nearly right.** The
best proposal it returns for a glass of those kinds matches that glass's true
pixels almost exactly, which is as much as anything fitted here could manage. A
silhouette is the kind of boundary shaded depth shows most strongly, and a glass
whose outline runs as one wall from the table to the rim is almost all
silhouette, so the picture holds exactly the evidence the model leans on.

**On the stemmed kind it is the worst result in this solution, and it is a
worse outline rather than a missing glass.** A wine glass seen from above is a
wide bowl over a thin stem and a foot, so the silhouette the shading can offer
is a broad disc joined to almost nothing, and SAM cuts into the bowl rather than
round it. Nearly every such glass still comes back with a proposal. What the
cutting costs is how much of the glass that proposal holds: typically about four
fifths of it, with only about one glass in five held almost entirely and about
one in eight cut badly enough to lose more than half. **The short stemmed kind
sits between that and the two good kinds, and much nearer the good ones**,
because every glass of it keeps at least half of its pixels and about two in
five are held almost entirely.

What a cut proposal costs further down the chain is mostly the footprint rather
than the glass. One that cuts into the bowl gives a footprint narrower than the
glass really has, so the place and the width reported are less accurate, and
where the cut is bad enough the width falls outside what the kind allows and the
proposal becomes a doubtful report instead of a glass. Nothing later in the
chain repairs either of those, because the keeper reads the footprint it is
given and the width check is right to refuse one no glass of this kind could
have. This is
SAM's proposals failing rather than the keeper failing, and it is the strongest
argument anywhere in this document for [solution
9](09-a-fine-tuned-instance-segmenter.md), where the weights are allowed to move
towards the pictures this cell really produces.

What can be done does not involve training, because training is not available
here. **Shade so that silhouettes are the strongest boundaries in the picture**,
by normalising each picture's shading to the range of depth it actually
contains, so the glasses and the table spread across the full range of grey
rather than compressing into a narrow band. **Add some shape shading**, since a
surface's slope relative to the camera is computable from the depth readings
themselves, so that a curved wall reads as curved rather than as a flat ramp.
**Fill the holes from their neighbours** rather than with a constant, so a
missing reading does not become an object with an outline.

And **try several shadings and score them**, which is the cheapest useful work
here and is available precisely because the shading is a choice rather than a
measurement. Render a set of scenes, shade each one several ways, run the whole
chain, and compare the results against the truth the simulator already holds.
That is a search over a handful of options rather than a training run, and the
two stemmed kinds are where it has the most to gain, the tall one most of all,
because theirs is the silhouette the shading serves worst.

None of that closes the gap; it makes the picture more like the pictures the
weights were fitted on, which is a more modest claim. On the kinds that already
work it is enough. On the stemmed kind the honest remedy is [solution
9](09-a-fine-tuned-instance-segmenter.md), where the weights are allowed to
move, because moving them towards the pictures you have is what fine-tuning is
for.

## What the proposals are when they are not one glass

The keeper drops what is not a glass, and the three ways a proposal comes to be
wrong are worth examining, because each arises for a different reason and one of
them is dangerous in a way the other two are not.

### The table

Bare table is one large region with a clear outline, so a grid of prompts
proposes it several times and the cleanup keeps one. Turned into points it gives
a width vastly greater than any glass of this kind can be, an area on the table
to match, and a surface lying at the table's own height rather than standing
clear of it, so the keeper drops it on any one of those and the width check
would drop it anyway. One by-product is worth passing on rather than dropping:
a mask of bare table says which part of the table has nothing standing on it,
which is what the blind-region arithmetic in [cluster on the
table](../programmed/02-cluster-on-the-table.md) reasons about.

### A rim without its glass

This case is not an error, and understanding why is understanding promptability.
A point on the rim of a glass is genuinely ambiguous: the rim is a thing and the
glass is a thing, and both answer "what is here?". SAM returns both rather than
guessing, so **part proposals are the model declining to guess**, and they
arrive for every glass in the picture.

Most of them are easy: a rim is a ring rather than a filled disc, so it is far
from round, and it sits inside a larger proposal whose own width is legal, which
is exactly what the containment measurement is for.

One of them is not easy, and it is the most instructive case in this solution.
Seen from the top, the **mouth** of a glass is a filled disc whose width is the
glass's own rim width. Its footprint is round, it stands clear of the table, and
its width sits comfortably inside the kind's range. On every measurement taken
from the footprint it looks exactly like one glass, because in footprint terms
it *is* the glass.

So the dangerous proposal is not the one that looks wrong. **It is the one that
looks right.** The keeper's own way of catching it is the containment
measurement, because a mouth is a proposal sitting inside its own glass's
proposal, and that is the general lesson of giving a model measurements rather
than pixels — somebody has to know in advance which measurement carries each
distinction.

What settles the case even when the keeper holds the mouth is arithmetic on the
places reported rather than any measurement, and it is the arithmetic set out
with [the keeper's inputs](#what-the-keeper-is-shown). A mouth kept as a glass
stands at its own glass's place, two reports at one place are one glass reported
twice, and only one of them survives. The width check cannot help here, because
a mouth's width is legal; the geometry can, and it is what keeps the count
honest.

### Two glasses at once

The third case is the one the problem is really about, and here SAM behaves
exactly like the programmed methods it was brought in to replace.

When a tall glass's splayed outline sweeps over a shorter one, the two make a
single region in the picture with no seam anywhere along it. SAM proposes
regions, and a region with no internal boundary is one region, so it proposes
the pair as one thing, for precisely the reason a flood fill would join them,
which [solution 1](../programmed/01-split-the-blob-in-the-picture.md) and
[solution
6](06-a-network-trained-from-scratch.md#in-the-picture-outlines-overlap) both
work through. Borrowing a very large model does not change the nature of the
evidence in the picture.

What is available is the measured width, which is far wider than the kind
allows, so the pair is caught. Catching it is not separating it, and the
separating is the second round of prompting described above, which has real
evidence to work with when one glass stands in front of the other, because the
near rim and the far wall sit at different distances and the shading shows the
step. When it works, two legal widths come back. When it does not, the pair is
reported as one unseparated pair and handed on.

The general shape of that limitation is worth being blunt about, because it is
the honest comparison with solution 6. **Every part of this solution works by
finding regions and the boundaries between them.** So it inherits what every
boundary method inherits: where there is no boundary in the evidence, nothing
finds one. Solution 6's voting is the only method in this problem that needs no
boundary at all, and on that one case it is simply better.

## How the concepts fit together

Everything above is one pipeline, worth seeing in order before the failure
cases, because each stage only works on what the last one passed it. The depth
readings are **shaded** into a grey picture. The picture encoder runs **once**
over it. A **grid of point prompts** then goes through the mask decoder, one
cheap pass each, and scoring, stability and duplicate removal reduce what comes
back to a shortlist of **proposals**. Each proposal's pixels become **points on
the table**, and a place, a width, a height above the table and the rest of the
**eight measurements** come out of them and of the proposals beside them. The
**keeper** reads those and answers one of three things. A proposal it keeps must
still pass the **width check** before it is reported with a mask, a place and a
width, and where two reports land at **one place on the table** only the surer
of them is kept, because two glasses of one kind cannot stand that close. A
proposal it calls more than one glass goes back for a **second round of prompts
inside itself**. Anything left over is **reported doubtful**, which for a pair
means handing it to problem 3.

Two things about that chain are worth holding on to. **The only fitted stage is
the keeper**, which reads a table of numbers rather than pictures, so everything
that finds objects is borrowed and none of it knows anything about this cell.
And **the riskiest stage is the shading**, because it is the only place where a
choice nobody can check by arithmetic changes what every later stage sees.

The third thing is where the safety is. The width check sits after the keeper
rather than before it, so a wrong answer from the keeper still has to get past a
rule nobody trained, and a wrong keep therefore becomes a doubtful report rather
than a wrong glass.

## When the glasses are completely hidden

A glass can be missing from a picture altogether. It is standing on the table,
it is solid, the camera is pointed at the part of the table it is on, and not
one pixel of it comes back. This is the hardest of the three difficulties in
this problem, every solution document has to say what it does about it, and this
solution's answer is a clean and complete no.

![A prompt point placed over the hidden glass's part of the table, the mask that
comes back being the covering glass, and the keeper never being consulted
because no proposal for the hidden glass
exists](../../../../images/problem-2/08-where-it-stops.png)

Being exact about why takes five steps, and each one closes a different escape
route.

**There is no region to propose.** SAM grows a mask from the picture's own
content at the place the prompt points at. A prompt point anywhere over the
piece of picture where the hidden glass ought to be lands on the covering glass,
so what comes back is the covering glass, and that answer is *correct*. Nothing
has malfunctioned.

**Prompting harder does not help**, and this is where the property named earlier
matters. A prompt selects; it does not add information. There is no point, no
box and no rough mask that makes SAM return a glass which cast no pixels,
because a prompt works on the pixels that are there. A box drawn round the empty
stretch of table returns the table, or the covering glass, depending on where
its edges fall. Promptability is a way of choosing among the things a picture
contains, and this glass is not one of them.

**The keeper is never consulted**, because it only ever sees proposals and there
is no proposal for this glass; all three of its answers are about a region that
exists.

**No check can fire.** Every check here is a check on a proposal: the fitted
width, how round it is, how far it stands above the table, how many prompts
agreed on it, how it sits among the other proposals. What comes back for the
covering glass is one proposal with a legal width, a round footprint, a proper
height above the table and the agreement of many prompts. **Nothing about it is
wrong.** The picture is one believable glass where two are standing, which is
the shape this difficulty always takes.

**And more model does not help either.** The scene with the hidden glass and the
same scene with that glass removed produce the same picture, pixel for pixel. No
function of the picture can distinguish them, whatever its size and however it
was fitted, because the thing that differs between the two scenes left no trace
in the input. A larger checkpoint changes nothing, and neither would training
SAM if training it were allowed.

One more thing is worth saying, because it is the temptation this solution
invites. A foundation model's strength is that it generalises to objects it
never saw, and it is easy to hope that covers this case too. It does not: the
difficulty here is not an unfamiliar object but **an absent one**, and
generalisation handles evidence of a new kind, while here there is no evidence
of any kind.

So this solution cannot handle the completely hidden case and has to hand it on,
and what it hands on is not a glass but a **region**: the part of the table it
could not have seen. Working out that region is arithmetic on splay and on the
glasses that *were* found, and it belongs to [cluster on the
table](../programmed/02-cluster-on-the-table.md); moving the camera and taking
the picture belongs to [move the camera](../programmed/03-move-the-camera.md).
This solution contributes the masks those two argue from, and none of the
argument.

### The partly hidden case, which is different

Complete hiding is the extreme of a range, and the rest of that range is
reached at the gap the cell guarantees, because the kind here runs from a small
tapered glass to a much larger one. It is uncommon rather than ordinary, and it
wants a crowded line of glasses rather than any table of this kind.

A crescent of a glass is a region, so SAM may well propose it, and the proposal
will be a good outline of exactly the crescent. The keeper then sees a footprint
fitted to a sliver: a width smaller than the kind allows, or a footprint less
round than a whole one is, or both. So its answer is neither keep nor drop
but the middle band, which means take another picture: the arm looks from the
side, across the line joining the crescent to the glass in front of it, and from
there the glass is not hidden. That is workable and it is not the best answer
available in this project. [Solution 10](10-amodal-masks-for-the-hidden-part.md)
is built for exactly this case, because it predicts a glass's whole footprint
rather than the part the camera can see, and [solution
6](06-a-network-trained-from-scratch.md#when-the-glasses-are-completely-hidden)
handles it by having every surviving pixel vote for its own glass's centre. This
solution notices a crescent and asks for another look, which costs arm time that
the other two do not spend.

The middle band earns its place, and not by catching crescents. On an ordinary
layout almost nothing is actually hidden, so crescents are rare, and what fills
the band instead is the two stemmed kinds, whose proposals SAM cut into. They
arrive in the band for the same reason a crescent would — a footprint fitted to
part of a glass is the wrong width or the wrong shape — but the cause is the
borrowed model's outline rather than another glass standing in the way. A
doubtful report is the right answer either way; what is worth knowing is that on
this cell's ordinary tables the band is reporting on the kind of glass rather
than on the layout.

## A worked example

One scene from the top shows the whole chain working, and failing once.

**The picture.** Five glasses stand in the zone, drawn across the kind's range
of sizes, two of them along a line running out from the point below the camera.
The depth is shaded into grey, normalised so that the tallest rim and the table
sit at opposite ends of the range.

**The proposals.** The grid of prompts returns a heap, and after scoring,
stability and duplicate removal a shortlist remains: the table, four regions
each about one glass wide, one region far wider than the kind allows, three rims
and two mouths.

**The keeper.** The table drops, on its width and on standing at the table's own
height. The rims drop, on being rings rather than filled discs and on sitting
inside legal proposals. The mouths are the interesting case, because their
footprints are perfectly legal, so the keeper may well hold one of them as a
glass and nothing it is shown says otherwise. Four proposals are kept as one
glass each, and the wide one is answered "more than one glass".

**The width check and the second round.** All four kept proposals have a width
inside the kind's range, so all four are reported with a mask, a place and a
width, and the wide one fails the check as it should. A fresh grid of points
inside that wide region returns two masks, split along the step between the near
glass's rim and the far glass's wall, and both widths land inside the kind's
range, so the pair is reported as two glasses rather than as an unseparated
pair.

**One report per place.** The near glass of that pair was also proposed on its
own, so it now arrives twice, and a mouth the keeper held stands at the place
its own glass already occupies. Both are second reports at a place already
taken, so both are dropped, and five glasses are reported where five stand.

**Where it fails.** Behind the tallest glass in the scene a sixth glass is
standing that nothing in this run has any opinion about. It cast no pixels, so
no prompt point could reach it, so no proposal exists for it, so the keeper was
never asked. The report says five glasses and one region of table that could not
have been seen, and the second of those statements is this solution's entire
contribution to finding the sixth.

**What it costs.** Running SAM is the whole of the cost to within a rounding
error: the picture encoder runs once per picture, every prompt after it is
cheap, and what the keeper adds is too small to see beside them. The whole chain
still costs far less than the seconds one arm movement costs.

## Running it yourself

The code for this solution and for the two that follow it lives in one folder,
with one environment, described in [its own
README](../../../../problem-2-pretrained/README.md).

    make setup                      # once: install the environment, fetch weights
    make train SOLUTION=sam
    make test  SOLUTION=sam
    make test-crowded SOLUTION=sam

`make setup` builds the environment and fetches `facebook/sam-vit-base` once.
`make train SOLUTION=sam` fits **only the keeper** — nothing in it touches SAM's
weights, and the word train is kept because the other two solutions in the
folder use the same command. `make test SOLUTION=sam` runs the whole chain over
held-out scenes of the kind the cell's own placement rule produces and scores
what comes out against the truth the simulator holds, which is also where the
choice of shading is settled. `make test-crowded SOLUTION=sam` does the same on
layouts built to stand one glass in front of another, which is where the claims
above about crowding come from.

One more command answers the question this document treats as the largest risk,
and it is worth running before the others:

    make by-kind

It asks what the borrowed model outlines well, one kind of glass at a time, with
no keeper and no scorecard after it: for every glass it reports how much of that
glass the best proposal holds. That is the measurement the ranking across the
four kinds comes from, and it is cheap because it needs no fitting at all.

The machine is an Apple M4 with a ten-core integrated GPU and memory shared with
the processor, which PyTorch reaches through its MPS backend, falling back to
the processor when it is absent; no NVIDIA card and no CUDA are involved. That
shared memory is why a model this size fits at all, and the smallest released
size of SAM is used because a larger encoder buys better outlines at a cost in
seconds.

## What it needs

It needs a **deep learning framework** and the environment to run it, which is a
large dependency for a cell whose recommended answer is a page of arithmetic.
And it needs a **weights file the project does not own**, which is a real
difference from solution 6, whose weights are small enough to commit beside the
code and can be regenerated at any time. SAM's cannot be regenerated here at
all, so they have to be fetched, pinned to a version, and stored where the run
can find them.

It needs **scenes for the keeper**, which the simulator renders and labels for
nothing, and far fewer of them than a network fitted from scratch needs, because
the keeper learns from a short table of numbers rather than from pictures.
Fitting it takes **seconds** once the proposals are in hand, with no graphics
card; what takes the time is running SAM over those scenes to get the
proposals, which is where nearly all of this solution's cost sits, at fitting
time and at run time both. At run time it needs one pass of the picture encoder
per picture, which is the largest single cost here and still small beside one
arm movement. And it needs **the
shading got right**, which is the only part where a careless choice degrades
everything downstream without anything complaining.

## Where it is strong and where it breaks

**Nothing it reported was two glasses, and nothing it reported was a glass that
was not there.** Over the held-out scenes, on ordinary layouts and on crowded
ones alike, it never merged two glasses into one report and it never invented
one, and no other solution in this folder can say the first half of that. It is
the strength to lead with, because it is earned rather than lucky: a kept
proposal still has to have a width inside the range this kind of glass can be,
and two reports at one place on the table are one glass reported twice. What it
costs is on the other side of the ledger. **It finds about three quarters of the
glasses** and hands over far more proposals than it keeps, nearly all of them
with the doubt that it cannot tell whether the proposal is one glass, so the
report it writes is cautious and short rather than complete.

**Almost nothing is fitted here.** Everything that finds objects is borrowed
whole, and the borrowed part cannot go out of date with this cell because it
never knew anything about it. It also needs the least data of any learned
solution in this problem, because a model learning from a short table of
measurements needs a fraction of the scenes a model learning from pictures does.

**It finds things nobody described**, because SAM proposes every region in the
scene, so a spoon left on the table arrives as a proposal and is answered "not a
glass" rather than ignored. Every other solution here is blind to whatever falls
outside its one class.

**The domain gap is measured, and it ranks the four kinds.** The weights were
fitted on photographs and are being shown depth dressed up as a grey picture. On
straight and tapered glasses that costs almost nothing: the best proposal for a
glass matches the real glass almost exactly. **On the stemmed kind it is
the worst result here.** SAM cuts into the bowl of a wine glass seen from above,
so the glass is still proposed but the proposal typically holds about four
fifths of it and a minority are cut badly, which costs the accuracy of the
footprint and, for that minority, the glass. The short stemmed kind sits between
the two and much nearer the good ones. The gap cannot be removed by training,
because nothing here is trained, and the only levers are the shading and the
prompt grid.

**It depends on depth twice over.** The keeper's best inputs, the fitted
footprint width and the height above the table, come from depth readings, and so
does the picture itself, because the picture *is* shaded depth. So on the day
the glasses become real glass and the depth camera stops returning anything
through them, this solution has no input at all, not even a picture; [solution
6](06-a-network-trained-from-scratch.md) is the one that survives that day.

**It is blind to a glass hidden completely**, for the reasons worked out above,
and that is a fact about the input rather than about the model.

**It cannot be improved by teaching it**, so if SAM proposes badly the only move
is to solution 9. And **its answer cannot fully explain itself**, though it is
better off than most learned methods here, because every kept proposal arrives
with a footprint, a place and a width, so the *check* explains itself even when
the model does not.

## The general ideas behind this

Nothing here is new. It is a foundation model used zero-shot, a grid of prompts,
a standard cleanup and a small classifier on top, and each has a literature and
a set of cases where it is the right answer.

### Foundation models — one very expensive fit, reused many times

A very large model is fitted once on a very broad collection of data and then
used, unchanged or lightly adapted, for many tasks it was not fitted for. The
term and the argument are set out by Bommasani and colleagues, 2021
([arXiv:2108.07258](https://arxiv.org/abs/2108.07258)); the general mechanism is
[transfer learning](https://en.wikipedia.org/wiki/Transfer_learning).

It is normally the right tool when the fit is far too expensive to repeat, your
own labels are scarce, and your task is one of many similar ones. It is normally
the wrong tool when the task is narrow, the labels are free, and the borrowed
model's world differs from yours — which is exactly the argument [solution
6](06-a-network-trained-from-scratch.md#why-train-from-scratch-rather-than-borrow)
makes for training from nothing in this cell.

### Promptable segmentation — Segment Anything

SAM takes a picture and a prompt — a point, a box or a rough mask — and returns
a mask, with several masks and a quality estimate for each when the prompt is
ambiguous. It is class-agnostic, so it outlines without naming. Kirillov and
colleagues, 2023 ([arXiv:2304.02643](https://arxiv.org/abs/2304.02643)), with
the project page at [segment-anything.com](https://segment-anything.com) and the
smallest released weights at
[facebook/sam-vit-base](https://huggingface.co/facebook/sam-vit-base). A later
version extends the same idea to video by carrying a memory between frames (Ravi
and colleagues, 2024, [arXiv:2408.00714](https://arxiv.org/abs/2408.00714)).

It is normally the right tool when you need the outline of something you cannot
name in advance, when a person is choosing among the proposals, or as the first
stage of something that classifies. It is normally the wrong tool when you need
a decision rather than an outline, because it names nothing; when objects are
defined by something other than their appearance boundaries; and when the input
is not a photograph, which is the risk this document spends a whole section on.

### Propose, then classify

Producing many candidate regions with a cheap general method and then deciding
about each one is an old structure. It is how R-CNN worked (Girshick and
colleagues, 2013, [arXiv:1311.2524](https://arxiv.org/abs/1311.2524)), with
selective search (Uijlings and colleagues, *International Journal of Computer
Vision*, 2013) as the proposer. This solution is that structure with a far
better proposer and a far smaller decider, and the grid of prompts plus scoring,
stability and non-maximum suppression is how SAM is turned into the proposer.

It is normally the right tool when missing an object at the first stage is much
worse than proposing too many, because a later stage can reject. It is normally
the wrong tool when the proposer and the decider disagree about what counts as
one object, which is this document's "two glasses at once".

### Zero-shot transfer — using a model on a task it was never fitted for

A model is applied to a task, or to data, it was not fitted on, with no further
fitting. The idea became mainstream with CLIP (Radford and colleagues, 2021,
[arXiv:2103.00020](https://arxiv.org/abs/2103.00020)), and the general notion is
[zero-shot learning](https://en.wikipedia.org/wiki/Zero-shot_learning).

It is normally the right tool when you have no labels at all, and as the first
baseline before anything is fitted, because it costs a download. It is normally
the wrong tool when you do have labels and the task is narrow, because
fine-tuning then beats it nearly always, which is [solution
9](09-a-fine-tuned-instance-segmenter.md)'s argument against this one.

### A small head on frozen features

Freeze a large borrowed model, take what it produces, and fit something small on
top. This was shown to work early and well (Donahue and colleagues, 2013,
[arXiv:1310.1531](https://arxiv.org/abs/1310.1531); Razavian and colleagues,
2014, [arXiv:1403.6382](https://arxiv.org/abs/1403.6382)), and it is the
standard first thing to try with any borrowed model. The keeper is this pattern
with one difference: it is shown measurements computed from each proposal rather
than the model's internal numbers, because measurements on the table mean the
same thing from every viewpoint and can be read by a person.

It is normally the right tool when data is small and the borrowed features
already contain what the task needs. It is normally the wrong tool when they do
not, because no small head recovers a distinction the frozen part threw away,
and at that point the weights themselves have to move.

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

Two things are unusual about the gap here. It runs **the opposite way** from the
usual sim-to-real direction, because the weights come from photographs and the
pictures come from a simulator. And the standard repair is **not available**,
because randomisation happens while training and nothing here is trained, so the
only lever is the input.

Randomisation is normally the right tool when you control the training and want
robustness against an appearance you cannot predict, and appearance translation
when you have examples of both appearances and nothing simpler works. Neither is
right when the model cannot be trained at all, and then the honest options are
to change the input or to stop borrowing.

## Where it sits among the other solutions

The comparison worth making first is against [solution
6](06-a-network-trained-from-scratch.md), because the two sit at opposite ends
of one axis. Solution 6 borrows nothing and fits everything; this one borrows
everything and fits almost nothing. Solution 6's weights are small enough to
commit beside the code and are a second copy of this cell, which has to be kept
in step with it; this solution's weights are large, owned by somebody else, and
know nothing about this cell to be out of step with. Solution 6 costs hours of
rendering and fitting; this one costs a download and minutes.

Then the honest part of that comparison. **Solution 6 can be taught this cell's
hard cases and this one cannot.** Pairs standing much closer than the cell's
rule allows, pairs actually touching, crescents behind another glass: all of
those go into solution 6's training set, and none can be communicated to SAM.
Solution 6 also separates objects with no boundary between them, which is the
case that matters most here, and on the stemmed kind it is the better tool,
because what defeats this one there is the borrowed model's own outline and
nothing behind that model can mend it. Against that, this solution notices
objects nobody described, needs far less data, and has nothing that goes stale.

The comparison against [solution
9](09-a-fine-tuned-instance-segmenter.md) is the one the scorecards settle,
because the two were run on the same scenes and both turn a mask into a place
with the same arithmetic. Solution 9 finds every glass on an ordinary layout
and this solution finds about three quarters of them, which is the whole of
solution 9's case. Against that, this solution never merged two glasses into one
report on either kind of layout and solution 9 did merge on the crowded ones,
and on ordinary layouts the places it reports sit closer to the truth. Both of
those are the dividend of reporting less: what it keeps, it keeps only when a
borrowed model outlined the glass cleanly and the arithmetic agreed afterwards.

The comparison against [cluster on the
table](../programmed/02-cluster-on-the-table.md) is shorter and less flattering.
Solution 2 is a page of arithmetic: no training set, no weights, about a
millisecond to run, its failures explained by printing one number, and a glass
placed more accurately than this places it. On any day the depth readings work
it is the better tool, and preferring a borrowed foundation model on such a day
is choosing the harder instrument for a job the easier one already does.

And the thing that has to be said plainly, because it is the reply to the
obvious defence of this solution: **it does not survive the loss of depth
either.** Solution 2 needs depth to turn pixels into points, and this solution
needs depth for the keeper's footprint and height inputs *and* to make the
picture at all, since the picture is shaded depth. So this is not the learned
solution that survives real glassware. It is the learned solution that survives
having almost no training data, which is a different and narrower virtue.

What this solution is genuinely for is to find out how far borrowed weights get
in this cell with nothing fitted behind them, and the answer is in hand: almost
all the way on straight and tapered glasses, most of the way on the short
stemmed kind, and least far on the stemmed one, whose outlines come back
cut into the bowl. That splits the next step by kind. For a stemmed kind it is
[solution 9](09-a-fine-tuned-instance-segmenter.md), which lets those weights
move towards the pictures this cell produces; for a glass standing behind
another glass it is [solution
10](10-amodal-masks-for-the-hidden-part.md), which changes what each mask is
fitted against.

← [Self-supervised from the arm's own
movement](07-self-supervised-from-the-arms-own-movement.md) · [A fine-tuned
instance segmenter](09-a-fine-tuned-instance-segmenter.md) →
