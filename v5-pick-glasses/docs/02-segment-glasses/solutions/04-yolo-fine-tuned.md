# Solution 4 — the same model, fine-tuned here

> **What it uses** — the Ultralytics package, with PyTorch underneath reaching
> this machine's integrated graphics through its MPS backend. The model is
> Ultralytics YOLO26-seg: the same library, the same model and the same
> downloaded weights as [solution 3](03-yolo-zero-shot.md), with its training
> continued on this cell's own pictures and its list of everyday categories
> replaced by a single class, "glass".
> **What it does** — a model that arrives fitted to photographs of everyday
> objects is not thrown away and not used as it is. Its numbers are kept and its
> training is continued on pictures of this cell, with one class instead of the
> general list, so that it stops being a general describer of photographs and
> becomes a finder of glasses in this room. The outlines it then returns are the
> answer to problem 2.
> **How the output is produced** — one survey picture from the top goes in. The
> fitted model returns, for each thing it believes it has found, a box, a number
> saying how sure it is, and an outline of the pixels inside that box which
> belong to the object. Candidates that overlap a better-scoring candidate too
> heavily are discarded, and the outlines scoring above a bar are kept. Each
> kept outline is one mask, and the bench's shared arithmetic turns a mask into
> a place on the table and a rough width.
> **How it differs from the other five** — [solution
> 1](01-rules-on-the-table.md) uses no model at all, only rules on the table.
> [Solution 2](02-train-from-scratch.md) fits a small network here from random
> numbers and borrows nothing. [Solution 3](03-yolo-zero-shot.md) is this exact
> model with no training in this cell, which makes it this solution's matched
> partner. [Solution 5](05-sam2-with-a-keeper.md) borrows a larger model
> untouched and fits only a small keeper that decides which of its outlines are
> glasses. [Solution 6](06-rf-detr-fine-tuned.md) fine-tunes here as this one
> does, but on a different architecture, which is what makes the two of them a
> test of whether the architecture still matters once both are trained.
> **What it costs** — labels are free, because the bench's own id image gives
> an exact mask for every glass on the training half of the arrangements.
> Training time is real but modest, because the model starts from somebody
> else's numbers rather than from random ones, and it runs on this machine's
> integrated graphics. The licence is the expensive part: Ultralytics YOLO26-seg
> is AGPL-3.0, and a weights file fine-tuned from it is bound by the same terms.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to answer problem 2 by taking a model that was
already fitted elsewhere and continuing its training on pictures of this cell.
The method has a name, **fine-tuning**, and it is the ordinary way a borrowed
model is put to work on a particular job. Nothing here is unusual, and that is
deliberate: this is the standard move, written out in full so that what it buys
could be measured rather than assumed.

**This is a design and not a report.** None of the six solutions to problem 2 is
built, so nothing below describes a program that has run. Where this document
says what the method would do, that is what the design says it would do, and
where it says a check should be applied, that is a prescription rather than a
step something already carries out. No measurement is quoted anywhere, for the
same reason.

**The whole reason this solution exists is that it is one half of a matched
pair.** [Solution 3](03-yolo-zero-shot.md) is this model with no training in
this cell. This is the same model with training in this cell. Everything else
between the two is held still, and it is worth listing exactly what "everything
else" means, because the list is the argument. The [test bench](../the-bench.md)
holds the input still, so both are shown the same pictures of the same
arrangements in the same order. It holds the output still, so both return the
same record per glass. It holds the marking still, so both are measured by the
same numbers computed the same way. And these two solutions hold the library,
the model and the starting weights still, because they are the same library, the
same model and the same downloaded file. One thing differs, which is the
training, and the training brings one further change with it that is worth
naming plainly: the borrowed list of everyday category names is replaced by the
single class "glass", because a model cannot be trained towards this cell's own
labels while still being asked which everyday object it is looking at. That
change belongs to the training and cannot be had separately, so nothing varies
between the two that the training did not bring. That is why **the gap between
solution 3 and this one is a measurement of what fine-tuning buys, and of
nothing else.** That is a rare thing to be able to say about two methods, and it
is the spine of this document.

By the end you will understand what fine-tuning is and why it needs far less
data and far less time than starting from random numbers, what changes when the
general list of everyday categories is replaced by a single class and which of
solution 3's failures that removes outright, where the training set comes from
and why labelling it costs nothing here while it would be the most expensive
part of the same work on real pictures, which of solution 3's weaknesses
training repairs and which it cannot touch, and the two ways training on one
cell's pictures can go wrong.

## The problem this solves

Problem 2 asks for one record per glass, each with a mask, a place on the table
and a rough width, and [the problem](../problem.md) names three difficulties.
The second of them is the one a model attacks: two glasses standing well apart
on the table can still leave one connected shape in the picture, because a
camera looking straight down from the top throws each glass's outline outwards
away from the point directly below it, and the taller the glass the further out
it is thrown. A method that treats each connected shape as one object then
reports one glass where two are standing.

A model built to find objects answers that difficulty by the shape of its
output, because it returns **one outline per object** rather than one outline
per connected shape. Solution 3 already borrows such a model, so that part of
the answer is available without training anything. The question this solution
exists to answer is therefore a narrower and more interesting one: **having
borrowed the finding, what is still wrong, and does training fix it?**

Three things are still wrong in solution 3, and all three have the same cause.
The model was fitted on photographs, and this cell renders a grey picture shaded
from depth, in which opaque glasses stand as plain shapes with no transparency,
no highlight on the rim and no texture anywhere. First, the model is working
with a fraction of the evidence it learned to use, so it may find the glasses
poorly or not at all. Second, its list of categories belongs to somebody else,
so a glass may be named under one of two neighbouring everyday categories and
reported twice, or named under a category the filter does not accept and
reported not at all. Third, the number it offers as its confidence was fitted on
photographs, so a bar set on that number means nothing here.

Training on this cell's own pictures is the standard repair for all three at
once, and that is what this solution does.

## The main idea

The idea is one sentence long: keep the borrowed numbers, and continue training
them on the pictures the model will really be shown, with one class instead of
the general list.

Three things follow from that sentence, and the rest of this document is those
three things.

**The numbers do not start from nothing.** A model's weights are the numbers
inside it, and training them from random values would mean teaching the model
everything, down to the fact that an edge is worth noticing. The borrowed
weights already hold that. So training continues from them rather than beginning
beside them, which is why a model of this size is reasonable on this machine,
which has no separate graphics card.

**The pictures are this cell's pictures.** This is the part that makes the
difference to solution 3. Solution 3 asks a model fitted on photographs to work
on a grey picture shaded from depth, which is a different kind of picture.
Fine-tuning does not ask that. It shows the model the grey pictures during
training, so at run time the model is being shown the kind of picture it was
fitted on. The difference between the two kinds of picture is called the
**domain gap**, and fine-tuning is how a domain gap is closed.

**The class list has one entry.** The general list of everyday categories is
replaced by a single class, "glass". So the model no longer has to decide which
everyday object it is looking at. It only has to find instances, and every
instance it finds is a glass or is nothing.

Everything else about the model is unchanged, including the thing that limits
it. Its outline is still built coarsely, for reasons described below, and
training cannot make a coarse outline fine.

## Fine-tuning — continuing somebody else's training

Because fine-tuning is the single thing that separates this solution from its
partner, it is worth setting out carefully and in plain words.

**Training** a network means showing it an example, comparing what it produced
against the answer that was wanted, and nudging every weight a little in the
direction that would have helped. Repeat that over many examples and the weights
settle at values that produce good answers. **Training from a random start**
means the weights begin as noise, so the nudges have to build every part of the
model out of nothing. **Fine-tuning** means the weights begin at values somebody
else's training already settled, so the nudges have much less to do.

The reason that is so much cheaper is worth stating in terms of what the data
has to pay for. Every weight in a model is a number the training data has to
determine. If the data does not contain enough information to pin a weight down,
that weight ends up fitted to accidents of the particular examples it was shown
rather than to anything real. So the amount of data needed grows with the number
of weights that have to be determined from nothing, and fine-tuning changes that
sum almost entirely: the great majority of the weights already sit at values
that work, and the data only has to adjust them.

A comparison from mathematics makes the shape of this clear. Fitting from a
random start is like solving for every coefficient of a long polynomial with no
idea of any of them. Fine-tuning is like being handed a polynomial that already
fits a similar curve and being asked to adjust its coefficients a little. The
second problem needs far fewer points to be well determined, because most of the
answer is already there.

There is a second saving, about time rather than data. A model fitted on
pictures holds, in its early layers, detectors for things common to all vision:
an edge, a corner, a shading that runs smoothly across a curved surface. Those
transfer almost completely, because an edge is an edge. A grey picture shaded
from depth is full of edges, since the rim of a glass against the table behind
it is a large jump in distance and therefore a large jump in grey, and a window
that finds a step from light to dark in a photograph finds the same step here. A
random start spends much of its training discovering those detectors again.
Fine-tuning does not, so only the later judgement — what counts as an object,
and where its edge lies — has to change.

That gives an honest expectation rather than a result, and it should be read as
one. What carries over best is the cheap general machinery at the bottom of the
model. What carries over worst is the judgement at the top, which was fitted to
decide between everyday categories using colour and texture this cell does not
render. So fine-tuning here has more work to do than the usual advice about
borrowed models implies, and still far less work than a random start.

## What one class does

The class list is the other thing this solution changes, and its effect is
sharper than it first looks.

The borrowed model names each object it finds from a list fixed when the model
was fitted. That list describes the ordinary contents of ordinary photographs,
and several of its entries are things a person drinks from, with a few near
neighbours beside them. Solution 3 has to accept a whole group of those
categories, because accepting only one of them would throw away every glass the
model happened to name with another. Replacing the list with a single class
removes that whole arrangement. The model is no longer asked **what** it is
looking at. It is asked only **where the instances are**, and each instance it
returns is either a glass or a mistake.

Two of solution 3's failures disappear with the list, and it is worth naming
them one at a time.

**A glass can no longer be reported twice under two names.** In solution 3 a
single glass may be named under two neighbouring everyday categories, arriving
as two outlines of nearly the same pixels, and that duplicate then has to be
noticed and collapsed somewhere after the model. With one class there is only
one name available, so the two candidates covering one glass are two candidates
of the same class, and the model's own step for reducing overlapping candidates
to one answer deals with them inside the model. The duplicate never leaves it.

**A glass can no longer be lost to a name the filter does not accept.** A
rendered glass seen from the top is a plain shaded shape, and a model fitted on
photographs can reasonably call such a shape a bowl, a vase or a bottle. In
solution 3 such an outline would be dropped and the glass missed. [The
bench](../the-bench.md) says that **missed** is the count to watch hardest,
because a missed glass leaves no trace at all. With one class, a found object
cannot be named out of the answer.

One thing the single class does not give is the kind of glass. The four kinds
are the straight glass, the tapered glass, the stemmed glass and the short
stemmed glass, and this solution would distinguish none of them, because it
would be trained to answer "is this an instance" and nothing else. That is not a
loss. Every glass in one arrangement is the same kind and the kind is known, so
no part of problem 2 asks for it.

## Where the training set comes from

Fine-tuning needs examples, which means pictures with every glass already
outlined, and this is where this cell is unusually fortunate.

[The bench](../the-bench.md) renders an **id image** beside every picture: at
each pixel, which glass that pixel shows, or nothing. The bench keeps that image
to itself at run time and never hands it to a solution, because a solution that
read one would not be answering the problem. However, the bench does make it
available as a **training label**, and only on the training half of the
arrangements, so that nothing is ever tested on an arrangement it learned from.

From an id image every label this model needs is a selection over an array the
renderer produced anyway. The mask for one glass is the set of pixels carrying
that glass's identity. The box is the smallest rectangle containing them. The
class is always "glass". There is no person drawing outlines, no budget for that
person, and none of the mistakes that person would make.

**It is worth saying plainly that this is a privilege of working in a
simulator.** On real photographs this is the expensive part of the whole
exercise, and usually the part that decides whether a method is affordable at
all: somebody has to outline every object in every picture by hand, the work is
slow, and the outlines disagree with each other. A simulator that already knows
which glass owns each pixel removes that cost completely. Any judgement made
here about whether fine-tuning is worth its price should carry that
qualification with it, because on real pictures the price would be quite
different.

Free labels are not the same as a good training set, and one choice still has to
be made well. The cell's own placement rule keeps glasses a comfortable distance
apart, so a training set drawn only from arrangements of that kind would never
show the model a pair that was hard to separate. The bench also draws
**crowded** arrangements, which push the glasses as close as the cell allows,
and the training set should hold those in proportion with the ordinary ones. The
principle is general and worth remembering: **the edge of what the method will
be asked to handle should sit somewhere in the middle of its training set**, so
that the model has met worse than it ever will.

## What training closes, and what it cannot touch

This is the section the matched pair exists for. Solution 3's weaknesses are
known, and training repairs some of them and inherits others untouched.

**The domain gap closes.** This is the large one. Solution 3 is shown a kind of
picture it was never fitted on, and a model used across such a gap fails in a
characteristic way: not by producing nonsense, but by producing confident,
plausible, wrong answers, which is worse because nothing downstream looks
suspicious. Fine-tuning removes the gap by construction, because the pictures
the model is fitted on are the pictures it will be asked about. The shaded grey,
the absent transparency, the missing highlight on a rim, the teardrop silhouette
leaning away from the point below the camera: all of those are simply what a
glass looks like, as far as the fine-tuned model is concerned, because that is
what every glass in its training set looked like.

**The naming failures close**, for the reason the previous section gives. There
is one class, so a glass cannot be duplicated across two names or dropped
because of one.

**The confidence number becomes meaningful enough to set a bar on.** More on
that in the next section.

**The coarse outline does not close.** This is the limit worth understanding,
because it is the one that survives everything this solution does. A model of
this kind does not draw an outline pixel by pixel. It computes, once for the
whole picture, a short list of coarse pattern images, and then returns for each
object a short list of weights. The object's outline is the weighted sum of
those patterns, cut at a threshold, and then enlarged to the size of the
picture. The comparison from mathematics is the useful one: this is the same
move as approximating a curve by a short weighted sum of fixed basis functions.
A handful of terms captures the broad shape of almost anything, and no handful
of them will ever capture a fine detail that none of the basis shapes contains.

Two consequences follow, and training changes neither.

**A thin part of a glass is the first thing lost.** A stem is narrow compared
with the bowl above it, so it is exactly the sort of detail a coarse pattern
cannot hold, and the outline tends either to thicken it or to drop it. The
bench's marking is broken down by kind for this reason, and [the
problem](../problem.md) already says what to expect from it: the two kinds with
no stem are outlined almost exactly by anything that tries, the stemmed kinds
are where methods differ, and the stemmed glass is the hardest of the four.
Fine-tuning can teach the model that a stem is
part of the glass. It cannot give the model a way to describe a shape its
outline machinery is too coarse to express.

**The edge of the outline stays approximate, and the width is read from the
edge.** The bench reads a glass's width from how far its mask's points reach out
from its axis, so an outline that is slightly too generous reports a glass
slightly too wide and one slightly too tight reports it slightly too narrow. The
enlargement step tends to err the same way each time, so the error does not
average away over many glasses. Training moves where that error sits; it does
not remove the mechanism that produces it.

**A partly hidden glass stays a problem.** The outline this model returns is
**modal**, which means it marks only the pixels where the camera actually saw
the object. When one glass stands partly behind another, the outline of the one
behind stops where the one in front begins, so the bench reads a glass whose
visible part is a slice of its true silhouette. A slice is both narrower than
the whole and sits off to one side, so the glass is reported as a smaller glass
in the wrong place. Training on masks of visible pixels cannot repair that,
because the training labels have the same limit the output does. Repairing it
means training the model towards a different target — the whole silhouette
rather than the visible part — and that is the choice [solution
6](06-rf-detr-fine-tuned.md) carries inside it.

**A completely hidden glass stays invisible**, for a reason no model can argue
with. That is its own section below.

## The number beside each outline

Each outline arrives with a number the model offers as its confidence, and what
that number is worth is one of the smaller things training changes.

A number is a **calibrated** probability when its claims come true about as
often as it says they will: among the outlines it scores very highly, nearly all
should really be glasses, and among those it scores middling, a middling share
should be. Solution 3's number was calibrated, to whatever degree it was
calibrated at all, on photographs, and a model's confidence is the first thing
to drift when the input changes, usually becoming too sure rather than too
cautious. So a bar set on solution 3's number is a knob set by hand and nothing
more.

Here the number comes from weights fitted on this cell's own pictures, so it has
a much better claim to mean something. That claim still has to be checked rather
than assumed, and the bench makes the check easy: the bar should be chosen on
the training half of the arrangements and measured on the test half, which is
the split the bench already enforces. Where the bar sits is a trade, and it is
the same trade in both solutions. Set it low and bare table is reported as
glass; set it high and faint glasses are dropped.

One warning applies to this solution unchanged, because training does not
affect it. The number is produced by the same weights that produced the outline,
so it is not an independent check on that outline. It is about whether the thing
is a glass, not about whether its outline is right, and a glass whose mask was
cut short by a neighbour standing in front of it can still be scored highly,
because it plainly is a glass.

## Two ways training on one cell's pictures goes wrong

Fine-tuning is cheap and it is not free of risk, and the two risks have names
worth knowing.

**Catastrophic forgetting.** Continuing a model's training on a narrow set of
pictures moves its weights away from the general answer they held, so the model
becomes better at this cell and worse everywhere else. The general vocabulary of
everyday categories is gone in any case, because it was replaced by one class,
but the effect reaches further than the vocabulary: the fine-tuned weights
describe a world of shaded depth pictures of opaque glasses, and asking them
about an ordinary photograph would be asking them about a world they were
trained out of. Within this project that is not a loss, because the only
pictures this model will be shown are this cell's. It does mean the fine-tuned
weights are a thing with a narrow purpose, and it is one reason a weights file
has to be kept in step with the cell rather than treated as a fixed asset.

**Overfitting.** A model fitted on a small set of examples can learn the
examples instead of the thing the examples are of. Here that would mean learning
the arrangements rather than the glasses: which parts of the frame tend to hold
a glass, how many glasses tend to be present, which spacings are common. Such a
model scores well on the pictures it was trained on and poorly on new ones. Two
things guard against it, and both are already in place. The bench divides the
arrangements into a training half and a test half and never marks a method on an
arrangement it learned from, so overfitting appears as a gap between the two
halves rather than hiding. And the labels being free means the training set can
be made large and varied at the cost of rendering time alone, which is the
cheapest defence against overfitting there is.

The two risks pull in opposite directions in one respect, and knowing that saves
confusion. Training longer and harder on this cell's pictures closes the domain
gap further while making both forgetting and overfitting more likely. So there
is a sensible amount of training rather than a maximum, and the test half of the
arrangements is what decides where it is.

## The masks are what this contributes

One point about the output has to be clear, because it decides what the
comparison with solution 3 is a comparison of.

**Turning a mask into a place on the table and a rough width is the bench's job,
not this solution's.** The bench takes each mask pixel with its depth reading,
turns it into a point in the room, takes the axis from the points at the top of
the glass and the width from how far the points reach out from that axis. Every
solution in this folder is given that same step, so **a difference in the score
belongs to the mask.** This solution contributes only the masks, and so does
solution 3, which is exactly why the gap between the two is readable.

It follows that **this solution produces no pose.** Models produce masks. The
place comes from depth and the camera's own pose, by arithmetic, and a glass
standing upright on a flat table has no orientation left to find. [The
bench](../the-bench.md) states this once so that no solution has to argue it
again.

## How the concepts fit together

The pieces now join into one pipeline, and it is short, because almost
everything in it was borrowed and only one thing was changed.

A grey picture shaded from depth is rendered by the bench and handed over with
its depth readings and the camera's pose. Before any of that, and once, the
model was fitted: weights that arrived from a large collection of everyday
photographs had their training continued on the training half of these same
arrangements, with labels taken from the bench's id image and with the general
list of categories replaced by the single class "glass". At run time the fitted
model is shown the picture and returns candidates, each with a box, a confidence
number and an outline built as a weighted sum of coarse patterns. Candidates
overlapping a better one too heavily are discarded, so one object leaves one
answer. The outlines above the bar are the masks. The bench's shared arithmetic
turns each mask into a place and a width, and the bench marks the result.

Three things are worth holding on to from all of that.

**The finding was borrowed and the fitting was local**, which is the whole
design. The expensive, general part of the model — turning a picture into useful
local descriptions — came from somebody else's training, and the cheap, specific
part — what an instance is in this cell, and where its edge lies — was learned
here from labels that cost nothing.

**The domain gap closed and the coarse outline did not.** Those are the two
halves of solution 3's trouble, and training addresses exactly one of them. So
this solution should be expected to find glasses far more reliably than its
partner while measuring their edges in much the same way, and the bench's two
mask numbers are where that expectation can be checked.

**The comparison is the product.** Even if this solution were not the one
carried forward, the pair would have earned its place, because a measured answer
to "what does fine-tuning buy on this kind of picture?" is worth more than an
opinion about it.

## When the glasses are completely hidden

Every solution document in this folder answers this question, which is whether
the method can find a glass that no picture holds. This one's answer is **that
it cannot, from either of the camera's places**, and the reasoning is short and
absolute.

Looking **from the top**, a glass's outline is thrown outwards away from the
point directly below the camera, and the taller the glass the further out it
goes. Because one kind holds both short glasses and much taller ones, a tall
glass's stretched outline can sweep over a short neighbour and cover it
completely. The short glass then produces no pixels at all. A model finds
objects in a picture, and there is nothing of that glass in the picture to find,
so no candidate is produced and no entry appears.

Looking **from the side**, it is plainer. A near glass stands in the way, and
because it is nearer it is drawn larger, so a glass directly behind it
disappears however far behind it stands.

**No amount of training helps, and this is worth settling exactly, because more
training is the first thing anyone suggests.** Take the arrangement with the
hidden glass, and the same arrangement with that glass taken away. The renderer
produces the same picture for both, pixel for pixel. A model is a function of
its input, so no model of any size, fitted by any method, can return two
different answers for two identical inputs. What differs between the two
arrangements left no trace in the input. This is therefore a fact about the
input and not about the model, and it is the one place where this solution and
its untrained partner are guaranteed to score the same.

Nothing in the output raises a question either. There is no low confidence
number, because the glass that was found really is a glass and the model is
right to be sure. There is no impossible width, because the visible pixels
belong to the glass in front and return to its own true footprint. Every check
on this solution's output is a check on something that was found, and here there
is nothing to check.

So this solution reports the case rather than answering it, and what it reports
is not a glass but a region of table it could not have seen. Working out that
region is arithmetic on the outward throw and on the glasses that **were**
found, and then going to look at it is a move of the arm. Both belong to the
part every solution in this folder shares rather than to any one of them, as
[looking again at what was hidden](../hidden-glasses.md) sets out. This solution
contributes the masks that shared part argues from, and none of the argument.

## A worked example

Follow one arrangement through, because the difference from solution 3 is easier
to recognise once both have been run over the same table.

**The arrangement.** Five stemmed glasses stand in the glass zone, drawn at
proportions from across the kind's range, so they are not all the same height.
Two of them stand as close together as the cell allows, roughly along the line
running out from the point below the camera, with the taller one nearer that
point. The camera takes the survey picture from the top. In that
picture the two close glasses leave one connected shape, with no seam along it.

**What solution 3 would return.** The borrowed model would find shapes, and
every outline would then have to survive the filter on names. The taller of the
close pair might be named under two neighbouring everyday categories and arrive
twice. One of the clear glasses might be named as something the filter does not
accept and be dropped, which would cost a glass with nothing in the output to
show for it. And every outline would be produced by weights that had never seen
a picture like this one, so how many of the five were found at all is genuinely
in doubt.

**What this solution would return.** The fitted model would be shown a kind of
picture it had been trained on, and the five glasses would be five instances of
the only class it knows. Each glass would produce several candidates; the step
that discards candidates overlapping a better one would reduce each cluster to a
single answer, so five entries would be expected rather than seven or three. No
entry could be lost to a name, because there is one name. The bowls would be
outlined well and the stems would be thickened or dropped, because a stem is
thin and the outline is coarse — and that part would look much as it does in
solution 3, since it is the one thing training does not change.

**Where the two would still agree.** The nearer of the close pair covers part of
the one behind it, so the mask of the one behind holds only the part the camera
saw. Both solutions return modal masks, so both would hand the bench a slice of
a silhouette rather than the whole of one. The bench would then report that
glass too narrow and at a place pulled towards the part that stayed visible. Its
width might still fall inside the range a stemmed glass can have, in which case
nothing would refuse it, and a wrong report would reach the marking with nothing
marking it as doubtful.

**And the case neither can answer.** Complete covering needs a kind whose range
of proportions holds both short glasses and much taller ones, and that is the
tapered glass rather than the stemmed glass, so take an arrangement of tapered
glasses instead. Stand one of them, drawn at the short end of that range, beyond
the tallest glass in the arrangement along the line running out from the point
below the camera, close enough that the tall glass's stretched outline covers it
completely. It produces no pixels, so neither solution produces an entry for it.
Every entry that did come back would be legal and confident, and the count would
be one short of the number put out. Only the shared geometry that works out
where a glass could have been hiding can raise that question, and only moving
the arm can answer it.

The honest summary of the example is that fine-tuning changes the first half of
it and not the second. The finding becomes reliable and the naming failures
disappear; the coarse edge, the slice of a hidden silhouette and the glass with
no pixels are all exactly where they were.

## What it needs

It needs the **Ultralytics package** and the model's weights, which the package
fetches by itself. That file is large, it comes from outside the project, and it
is not something to commit beside the code.

It needs **PyTorch**, reaching this machine's integrated graphics through its
MPS backend. There is no separate graphics card here, and memory is shared
between the graphics processor and the main processor, which is what lets a
model this size be trained at all on this machine.

It needs a **training set**, which the bench renders and labels for nothing from
the training half of the arrangements, including the crowded arrangements the
cell's own placement rule would never produce. It needs **time on the machine**
for the training run, far less than a random start would need but not nothing.
It needs a **held-out half** for setting the bar on the confidence number and
for checking that the model learned the glasses rather than the arrangements,
and the bench provides exactly that.

And once fitted, it needs **a weights file kept in step with the cell**. Change
the camera, the way depth is shaded into grey, or the range of proportions a
kind is drawn from, and the file is quietly out of date in a way no test of the
code would notice. Against all of that, what it needs at run time is modest: one
pass over one picture, which is a small fraction of the seconds an arm movement
costs. The cost of this solution sits almost entirely in building it rather than
in running it.

## The licence

The choice of model carries a condition the rest of this project does not, and
anyone who chooses this solution should meet that condition here rather than
discover it later.

Ultralytics YOLO26-seg is licensed under the **AGPL-3.0**. The AGPL requires
that anybody who distributes the software, **or offers its functionality over a
network**, makes the complete corresponding source available under the same
terms. The network clause is the part that matters most here, because it reaches
a product that never gives a copy of the model to anybody and only serves
answers from it. Everything else this project depends on is permissively
licensed and can be used commercially, as [the implementation
notes](../../../implementation-notes.md) record, so this one component would
change the terms of the whole perception step if it were carried into a product.

**This solution carries the condition twice over, and that is the difference
from solution 3.** Solution 3 runs the downloaded weights and nothing more. This
one produces a new weights file by continuing the training of those weights, and
a file derived from an AGPL work is bound by the same terms. So the output of
the training run is not a clean asset the project owns outright: it inherits the
licence of the thing it was derived from, and it cannot be relicensed by having
been trained here.

That is understood and accepted, because this folder exists to compare methods
and learn what each one buys, and for that purpose the licence costs nothing.
If this method proved to be the right one and the work were headed somewhere
commercial, the replacement is straightforward and the implementation notes
already name candidates: permissively licensed instance segmenters that do the
same job, one of which [solution 6](06-rf-detr-fine-tuned.md) already uses under
Apache 2.0. Nothing in this solution's design depends on the borrowed model
being this particular one. What is being tested is what fine-tuning buys on this
kind of picture, and that answer transfers to whichever model is licensed
conveniently.

## Where it is strong and where it breaks

**It answers the question actually asked.** Problem 2 asks which pixels belong
to which glass, and this model's output is one outline per object. Nothing has
to be converted, and no step has to find a seam in a joined region.

**It is fitted on the pictures it will be shown.** That is the single strongest
thing about it, and the thing its partner cannot claim. The domain gap is closed
by construction rather than left to hope.

**Its labels cost nothing.** The bench's id image gives exact masks for free, so
the usual reason not to fine-tune a model does not apply here.

**It has little to set by hand.** There is no grouping distance and no seam
threshold. Its two settings, the bar on the confidence number and the overlap
allowed before a candidate is discarded, are plain numbers with obvious
meanings, and neither is a length that has to be justified against the geometry
of the cell.

**It is one half of the cleanest comparison in the folder**, and that is a
strength of the design rather than of the model.

Against that, three kinds of weakness.

**What it inherits from the model.** The outline is built coarsely and enlarged,
so the width carries an error that does not average away, and the thin stem of a
glass is where it is worst. The masks are modal, so a partly hidden glass is
reported as a smaller glass in the wrong place. A completely hidden glass is
invisible to it, and no training can change that. The confidence number is about
the class and not about the mask, so a badly cut outline can still be scored
highly.

**What it owes to being trained.** A fine-tuned model becomes good at this cell
and worse elsewhere, so its weights are a narrow asset that has to be kept in
step with the cell. A small or uniform training set would teach it the
arrangements rather than the glasses, and only the test half of the arrangements
would reveal it. And its answer cannot explain itself: when solution 1's rules
are wrong you can print a number and see why, and when this model is wrong you
can look at the picture and guess.

**What it owes to the licence.** The AGPL reaches both the library and the
weights file fine-tuning produces, which is the one weakness here that no amount
of engineering removes.

## The general ideas behind this

Nothing in this solution was invented for glassware. Every part of it is a
standard piece of modern practice, and each is worth knowing on its own,
including where it is normally the wrong tool.

### Transfer learning and fine-tuning

Take a model fitted on a large general task, keep its weights, reshape the last
layers for the new task, and continue training on the new data. It works because
the early layers of a vision model learn things common to all vision — edges,
corners, gradients, textures — and only the later layers learn things specific
to the original task. Yosinski and colleagues
([arXiv:1411.1792](https://arxiv.org/abs/1411.1792)) measured that directly,
showing how well a layer transfers falling away with depth.

It is normally the right choice whenever labelled data for the real task is
scarce, which is almost always. It is normally the wrong choice when labels are
free and plentiful **and** the new pictures look nothing like the borrowed ones,
because then the borrowed weights bring knowledge of a world you do not have
while also forcing your model to be the size somebody else chose. This cell sits
awkwardly between those two, since its labels are free and its pictures are
unlike photographs, which is exactly the argument [solution
2](02-train-from-scratch.md) makes and this solution deliberately takes the
other side of. For more, see [transfer
learning](https://en.wikipedia.org/wiki/Transfer_learning).

### Domain adaptation

A model fitted on one kind of data and used on another is working across a
**domain gap**, and the family of methods for closing it is called **domain
adaptation**. Fine-tuning on labelled data from the new domain is the simplest
member of that family and the strongest when such data exists.

It is right whenever you can obtain labelled examples of the real input, as
here. It is wrong, or rather unavailable, when you cannot, and then the harder
members of the family are needed: adapting with no labels at all, or
deliberately varying the training data so widely that the new domain falls
inside the range already covered. The second of those, **domain randomisation**,
is the usual answer when a model trained in a simulator has to work on real
pictures, and it is worth knowing because the problem it solves is the mirror
image of the one here.

### Single-class detection, against a closed vocabulary

A detector fitted with a fixed list of categories can only return names from
that list, which is called a **closed vocabulary**. Cutting the list to one
entry turns naming into pure finding, and the model's remaining job is to
separate instances.

One class is right when the question really is "where are the instances of this
one thing", which is what problem 2 asks, and it is efficient, because none of
the model's capacity is spent telling categories apart. It is wrong when the
categories matter, and it then throws away information that was free: a model
that has to distinguish several classes can use the disagreement between them as
evidence, and a single-class model has no such signal. In this cell the kinds
are known in advance, so there is nothing to give up.

### Catastrophic forgetting

A network trained on a new task tends to lose what it knew of the old one,
because the weights that held the old knowledge are the same weights the new
training moves. The effect was first described for simple networks by McCloskey
and Cohen, and the modern treatment protects the weights that mattered most to
the old task (Kirkpatrick and colleagues,
[arXiv:1612.00796](https://arxiv.org/abs/1612.00796)).

It matters a great deal when a model must stay good at several things, which is
why continual learning is a field at all. It matters very little here, because
the model is wanted for one cell and nothing else, and this is the honest reason
the usual precautions against it are not taken: not that the effect is absent,
but that its cost in this project is zero.

### Overfitting and the held-out split

A model fitted on a finite set of examples can fit accidents of those examples
rather than the thing they are examples of. The standard defence is to divide
the data, fit on one part and measure on another, so that any such accident
shows as a gap between the two scores.

It is the right practice everywhere and there is no case against it. Its usual
difficulty is that data is scarce, so dividing it hurts. That difficulty does
not arise here, because arrangements are rendered rather than collected and more
of them cost only time. For more, see
[overfitting](https://en.wikipedia.org/wiki/Overfitting).

### Non-maximum suppression

When many overlapping claims describe the same thing, sort them by confidence,
keep the best, discard everything overlapping it too heavily, and repeat on what
is left. The procedure appears in every detector, because every detector
produces more candidates than there are objects. Its only setting is the overlap
allowed, and because that is a ratio of areas rather than a distance, it does
not have to be justified against the size of anything in the room.

It is right wherever a detector's candidates cluster on one object. It is wrong
without care in crowded scenes, because it cannot tell duplication from genuine
overlap, and this cell is one of the awkward cases: the outward throw from the
top can push one glass's outline right across another's. A softer variant, which
reduces an overlapping candidate's score rather than deleting it, is
**Soft-NMS** (Bodla and colleagues,
[arXiv:1704.04503](https://arxiv.org/abs/1704.04503)), and it exists for exactly
that difficulty.

## Where it sits among the other five

[The six solutions](overview.md) form a ladder, ordered by how much of them was
fitted in this cell, and this one stands near the top of it.

Against [solution 3](03-yolo-zero-shot.md), there is nothing to compare except
training, and that is the point. Same library, same model, same starting
weights, same input, same output, same marking. The single class that replaces
the borrowed category list comes with the training rather than beside it, so it
is part of what is being measured and not a second variable. Whatever separates
the two scores is what fine-tuning bought, and nothing else can be blamed for
it. If this document is read for one reason, it should be that one.

Against [solution 1](01-rules-on-the-table.md), the comparison is model against
rules. Solution 1 is a page of arithmetic that explains its own failures and
needs no training set, no weights file and no licence. This solution needs all
three and answers the merge by the shape of its output rather than by a rule
somebody had to get right. On any day the depth readings are good, the rules are
better in almost every way that is not accuracy.

Against [solution 2](02-train-from-scratch.md), the comparison is borrowing
against building. Solution 2 fits a small network here from random numbers, so
the project owns every number in it and can regenerate them, and in exchange it
has to learn the general machinery of vision from this cell's pictures alone.
This solution borrows that machinery and adjusts it, so it is trainable in much
less time, and the price is a large downloaded file the project cannot reproduce
and a licence attached to it.

Against [solution 5](05-sam2-with-a-keeper.md), the comparison is how much to
fit. Solution 5 borrows a larger model untouched and fits only a small keeper
that decides which of its outlines are glasses, which needs the least training
data of any learned solution here and leaves its domain gap wide open, as
solution 3 also does, because nothing in the borrowed weights is ever adjusted
to this cell's pictures. This
solution fits the whole model, so its weights have actually seen the pictures
they will be asked about.

Against [solution 6](06-rf-detr-fine-tuned.md), the comparison is architecture.
Both are fine-tuned here on this cell's own pictures with one class and free
labels, so the training is held still and the model is what differs. That makes
the pair a test of whether the choice of architecture still matters once both
have been trained on the job, which is the natural question to ask after this
solution's own pair has answered what training is worth at all.

Read as a ladder, the six measure what each increment of fitting buys. This
solution is the rung where all of the fitting happens on a borrowed model, and
its partner one rung below is the rung where none of it does.

← [A borrowed model, as it downloads](03-yolo-zero-shot.md) · [SAM 2 with a
keeper](05-sam2-with-a-keeper.md) →
