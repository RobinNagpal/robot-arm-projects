# Solution 5 — a model that already knows what a glass is

*Learned, as the decider. A segmentation model fitted on everyday photographs
already has categories for drinking vessels, so it is used exactly as it
downloads. Nothing whatsoever is fitted in this cell.*

> **The cell is described once, in [the cell](../../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to answer problem 2 by downloading a model and
running it, without collecting a single label and without training anything at
all. Every other learned solution in this problem pays something before it can
answer: a set of labelled pictures, a training run, a weights file to keep in
step with the cell. This one pays none of that, because the model it borrows was
already fitted on photographs of everyday scenes, and the list of things it can
name already contains drinking vessels. So the model is asked for glasses and it
answers, on the first picture, having never seen this cell.

That makes it the cheapest solution in the set to try, and it also makes it the
one that teaches the clearest lesson about borrowed models. The lesson is that
borrowing gives you the **finding** almost free and gives you the **meaning**
not at all. The model will outline something glass-shaped and attach a name to
it, but that name belongs to somebody else's list of categories, drawn up for a
different purpose, and the boundaries of that list are not this cell's
boundaries between its four kinds of glass.

By the end you will understand what an instance segmentation model returns and
how that differs from a model that only labels pixels, why this particular model
needs nothing fitted here when the closely related [solution
8](08-segment-anything-then-keep-the-glasses.md) needs a small fitted keeper,
how the outline is built and why it is approximate in a way that matters to the
arithmetic downstream, why the number the model reports alongside each outline
is not a probability in this cell even though it looks like one, and what the
licence costs, because here that is a real cost rather than a footnote.

## The problem this solves

Problem 2 asks for one report per glass on the table, each with a place and a
width, and the difficulty is not seeing that something is there but deciding
**how many things are there**. Two glasses standing close together, seen from
the top, leave one connected shape in the picture, and a rule that treats each
connected shape as one object reports one glass where two are standing. That is
the merge, and it is what most of the solutions in this folder attack.

A model fitted to find objects attacks it directly, because such a model is
built to return **one outline per object** rather than one outline per connected
shape. Two glasses touching in the picture are two objects, and a model that was
fitted on crowded photographs has seen that situation many thousands of times,
in scenes where cups and glasses stand side by side on tables. So the hope is
reasonable: the separation this cell finds hard is the separation the borrowed
model was fitted to do.

What makes this version of the hope worth testing is the price. The other
model-based solutions need pictures of this cell with every glass outlined by
hand or by the simulator, and then a training run that has to be repeated
whenever the cell changes. Here there is nothing to collect and nothing to
repeat. If the borrowed model works even moderately well, it is the fastest
route from no perception at all to a working report, and that is worth knowing
before anybody spends a week building a training set.

## The main idea

The idea has three steps, and only the first is new to this folder.

**First, run the borrowed model on the survey picture.** The model used here is
Ultralytics YOLO26-seg, taken as it downloads. It is an **instance segmentation
model**, which means that for every object it believes it has found it returns
four things together: a box around the object, a name taken from a fixed list of
categories, a number saying how sure it is, and an outline marking which pixels
in the box belong to that object rather than to the background or to a
neighbouring object.

**Second, keep the outlines whose name is a drinking vessel.** The fixed list of
categories the model was fitted on is a general one, covering the ordinary
contents of ordinary photographs, and several of its entries are things a person
drinks from. Those are the ones this solution keeps, and everything else the
model names is dropped.

**Third, hand those outlines to the arithmetic the other solutions already
use.** An outline is a set of pixels, and turning a set of pixels into a place
on the table and a width in millimetres is a job this project already does, the
same way, for every solution that produces masks. Nothing about that step
changes here.

So the whole of this solution is the first two steps, and the second step is a
filter on a list of names rather than anything fitted. That is the point worth
holding on to: **this solution contains no numbers fitted in this cell at all**,
not one.

## What instance segmentation is, and why it is the right kind of model

A new reader meets several kinds of model that all produce outlines, and they
are not interchangeable, so it is worth separating them before going further.

**Semantic segmentation** labels every pixel with a category and stops there. It
would mark all the glass pixels in the picture as glass, which sounds like what
this problem wants until you notice that two touching glasses produce one
connected region of glass pixels, with nothing in the output saying where one
ends and the next begins. A semantic model therefore hands the merge straight
back, unsolved.

**Instance segmentation** labels every pixel *and* says which object it belongs
to. Two touching glasses come back as two outlines that happen to be adjacent,
and the merge is answered inside the model. This is why problem 2 reaches for
this kind of model and not the simpler one.

**Promptable segmentation**, which is what [solution
8](08-segment-anything-then-keep-the-glasses.md) borrows, outlines whatever is
at a place you point to, and names nothing at all. It separates objects
very well and has no opinion about what they are.

That last difference is the whole reason this solution is shorter than solution
8. A model that outlines without naming has to be followed by something that
decides which of its outlines are glasses, and in solution 8 that something is a
small classifier fitted on this cell's pictures. A model that outlines **and**
names needs no such thing, because the naming is already done. The borrowed
model's list of categories is doing the job that solution 8 has to fit a keeper
to do.

## Why the names are a hint and never an answer

The naming is also where the borrowing starts to show its edges, so this is the
section to read most carefully.

The list of categories the model knows was drawn up to describe photographs of
the everyday world, and it contains several entries that a drinking glass could
plausibly fall under: a stemmed drinking vessel, a plain cup, and a few shapes
that are near neighbours of both, such as a bottle or a vase. The cell's four
kinds do not line up with those entries. Two of the kinds, the ones with a stem,
resemble the stemmed vessel in the list. The two without a stem resemble the
plain cup. But the resemblance is loose, the model has never seen these
particular shapes, and the boundary it draws between its own categories was
never meant to tell this cell's two stemmed kinds apart.

Two consequences follow, and they pull in opposite directions.

The first is that **the filter on names has to be generous**. If only one
category were accepted, every glass the model named with the other one would be
thrown away, and the solution would lose a whole kind for no reason. So the
filter accepts the whole group of drinking-vessel categories, and accepts that
it will sometimes also admit something that is not a glass.

The second is that **the name must never be carried into the report as the kind
of glass**. It would be very tempting, because a free guess at the kind looks
like a gift. It is not a gift: it is a category from somebody else's list,
assigned by a model that was never shown this cell's kinds, and it would be
wrong often enough to be dangerous. The kind of glass is measured later, by
[problem 1](../../../problem-1/step3-what-kind-of-glass.md), from the glass's
own profile after the arm has looked at it properly. This solution's output is a
place and a width, exactly like every other solution's, and the name is thrown
away once it has served as a filter.

That second point also keeps this solution inside the rule that governs the
whole project, which is that **no glass's size is written down anywhere**. A
borrowed category carries an implied size with it, because the model's idea of a
stemmed drinking vessel comes from photographs of real ones. Dropping the name
after filtering is what stops that implied size leaking into the cell.

## How the outline is produced, and why it is approximate

The outline needs a little explanation too, because its shape is not free to be
anything, and the restriction has a consequence the arithmetic downstream feels.

A model of this kind does not draw an outline pixel by pixel. Instead it
computes, once for the whole picture, a short list of coarse pattern images, and
then for each object it returns a short list of weights. The object's outline is
the weighted sum of those patterns, thresholded, and then enlarged to the size
of the picture. The comparison worth holding is a familiar one from maths: this
is the same move as approximating a curve by a short weighted sum of fixed basis
functions. A handful of terms captures the broad shape of almost anything, and
no handful of them will ever capture a fine detail that none of the basis
shapes contains.

Two things follow for this cell.

**A thin part of a glass is the first thing lost.** A stem is narrow compared
with the bowl above it, so it is exactly the sort of detail a coarse pattern
cannot hold, and the outline tends either to thicken it or to drop it.
A measurement of a different borrowed model, recorded in [the pretrained
folder](../../../../problem-2-pretrained/README.md), ranks the four kinds that
way: the stemmed kind is outlined worst, the short stemmed kind next, and the
two without a stem almost exactly. That is a reason to expect the same ranking
here rather than a measurement of this model.

**The edge of the outline is approximate, and the arithmetic takes the width
from the edge.** The shared arithmetic reads a glass's width from how far the
outline's points spread away from its middle, so an outline that is a little too
generous reports a glass a little too wide, and one that is a little too tight
reports it a little too narrow. The error does not cancel out over many glasses,
because the enlargement step tends to err the same way each time. This is the
main reason to expect this solution to sit further from the best achievable
answer than a model fitted on this cell's own pictures, and it is a limit of the
outline rather than of the finding.

## The number beside each outline, and why it is not a probability

Each outline arrives with a number that the model offers as its confidence, and
it is worth being precise about what that number is worth here, because the
obvious reading of it is wrong.

A number is a **calibrated** probability when its claims come true about as
often as it says they will: among the outlines it scores very highly, nearly all
should really be glasses, and among those it scores middling, a middling share
should be. Whatever calibration this model has was obtained on photographs. This
cell's pictures are not photographs, and a model's confidence under changed
input is the first thing to drift, usually becoming too sure rather than too
cautious.

What survives the change better than the numbers is their **order**. A model
whose scores are badly calibrated may still rank a clear glass above a doubtful
one, because ranking only needs the scores to move in the right direction, not
to be honest about their size. So this solution may use the number to sort and
to set a bar below which an outline is ignored, but it must treat that bar as a
**knob set by hand and checked on held-out renders**, not as a probability
threshold with a meaning. Calling it a probability would be claiming a property
nobody has measured.

This is also the one place where the solution could be improved without
abandoning its central promise. Fitting a small correction from the model's
scores to honest probabilities needs no change to the model and no labelled
outlines, only a set of renders where the answer is known. That would be a few
fitted numbers rather than none, and it would buy a threshold that means
something.

## The domain gap, which is the main risk

Everything above assumes the borrowed model works at all on this cell's
pictures, and that assumption deserves its own section, because the difference
between what the model was fitted on and what it is shown here is large and runs
in both directions.

A **domain gap** is the difference between the data a model was fitted on and
the data it is used on. Models fail across such gaps in a characteristic way:
not by producing nonsense, but by producing confident, plausible, wrong answers,
which is worse because nothing downstream looks suspicious.

**The picture is not a photograph.** The cell renders a grey picture shaded from
depth. A borrowed model's strength on real photographs comes largely from real
light: the way a surface changes shade as it curves, the texture of a table, a
shadow that says where an object meets the surface it stands on, the colour
differences that separate one object from the one behind it. Very little of that
is present here. The model is being asked to work with a fraction of the
evidence it learned to use.

**The glasses are not photographed glasses, either.** A real drinking glass is
transparent, so a photograph of one shows the background through it, a bright
highlight along one side, and a bright line where the rim catches the light.
Those are precisely the features that tell a model, in a photograph, that it is
looking at a glass. The cell's glasses are rendered as solid shaded shapes, so
the strongest evidence the model has for its own category is absent, while the
broad silhouette, which is weaker evidence, is all that remains.

Put together, this is the clearest reason the solution might fail outright
rather than merely do poorly, and it is also the reason the comparison with
[solution 9](09-a-fine-tuned-instance-segmenter.md) is the interesting one.
Solution 9 takes a model of the same general kind and continues its training on
this cell's pictures, which is the standard repair for exactly this gap. The
difference between the two is therefore a clean measurement of what the gap
costs, and that is the single most useful thing this solution could contribute
to the folder even if it performs badly.

## The arithmetic still decides

It is worth stating plainly what protects the report when the borrowed model is
wrong, because the model here is the decider and a decider's mistakes are acted
on.

Three guards stand between an outline and the report, and none of them needs
the model to be right. The **one report per place** rule collapses two outlines
that resolve to the same spot on the table, and that rule is already part of
the pipeline the borrowed-model solutions share. It matters here because a
single glass can be named twice under two neighbouring categories and arrive as
two outlines of nearly the same pixels. The **glass count** from the problem
statement says how many objects should have been found, so a run that reports
too few knows it is missing something and can ask for another look. A **width
check**, refusing an outline whose implied width falls outside what any kind of
glass in this cell can be, would catch the common failure of an outline that
swallowed its neighbour, and that one is a prescription rather than something
the built pipeline does today.

Together those guards put a ceiling on how wrong the answer can get, which is
why a borrowed model used as the decider is not as reckless as it sounds. They
do not make it right, and a better model is still the only thing that makes
failures rarer.

## Modal masks, and the glass standing behind another

One limit is worth separating out, because it is shared with a sibling solution
and is the reason that sibling exists.

The outline this model returns is **modal**, meaning it marks only the pixels
where the camera actually saw the object. When one glass stands partly behind
another, the outline of the one behind stops where the one in front begins. The
arithmetic then reads a glass whose visible part is a slice of its true
silhouette, and a slice is both narrower than the whole and sits off to one
side, so the glass is reported as a smaller glass in the wrong place. That is
not a failure of the borrowed model; it is what a modal outline means.

[Solution 10](10-amodal-masks-for-the-hidden-part.md) exists to repair exactly
this, by training a model to return the object's whole silhouette instead of
only its visible part. That repair is not available here, because it requires
training, and training is the one thing this solution does not do. So a partly
hidden glass is a known weakness of this solution with no fix inside it, and the
honest response is the project's usual one: report the doubt rather than the
guess, and let the arm take another look.

## How the concepts fit together

The pieces now connect into one picture, and it is a short one because the
solution is short.

A model fitted elsewhere is shown this cell's picture and returns, for each
thing it found, an outline and a name. The names come from a general list, so
they are used only to decide which outlines are worth keeping and are then
thrown away, because they carry an implied idea of size that must not enter this
project. The outlines are built from a short weighted sum of coarse patterns and
then enlarged, so they are good about where a glass is and only approximate
about where its edge lies, and the arithmetic downstream reads the width from
that edge. The number beside each outline orders them usefully but means nothing
as a probability, because the pictures are not what it was calibrated on. And
the same change of pictures is the main risk to the whole arrangement, since the
light and transparency that tell a model it is looking at a glass are mostly
absent from a grey picture shaded from depth.

Every one of those is a consequence of one decision: **fit nothing here**. That
decision is what makes the solution free to try, and it is also what removes
every lever that would normally be pulled to fix the problems above.

## When the glasses are completely hidden

Every solution document in this folder answers this question, and the answers
differ in a way worth comparing. This one's answer is **no, in both of the
camera's places**, and the reason is the same reason as for the other
mask-producing solutions.

**Looking from the top**, a tall glass's outline can sweep over a short one and
cover it completely, so the short glass appears in no picture at all. A model
that finds objects in a picture can only find objects the picture contains.
There is nothing at those pixels but the tall glass, so one outline comes back,
correctly describing the glass the camera could see, and the covered glass is
not merely mis-measured but absent from the model's output entirely. No bar on
the confidence number and no change of model size alters this, because the
evidence is not weak, it is missing.

**Looking from the side**, the situation is cleaner and worse. Two scenes, one
with a far glass standing behind a near one and one with the far glass taken
away, produce the same picture pixel for pixel. The model is a function of the
picture, so it returns the same outlines with the same names and the same
numbers for both. Nothing the model could be asked would distinguish them.

The cure for both is not in this solution at all. It lies in [clustering on the
table](../programmed/02-cluster-on-the-table.md), which works out which parts of
the table nobody could have seen, and in [moving the
camera](../programmed/03-move-the-camera.md), which covers those parts from new
positions. This solution contributes the outlines those two argue from, and
contributes nothing to the argument.

## A worked example

Follow one crowded arrangement through, because the failures above are easier to
recognise once they have been seen together.

Three glasses stand in the zone: a stemmed glass near the middle, standing at
the tall end of its range, a straight glass a little way out from it at the
short end of its own, and a tapered glass off at the edge of the frame. The
camera takes the survey picture from the top.

The borrowed model returns four outlines. The stemmed glass comes back
twice, once under each of two neighbouring drinking-vessel categories, with
nearly the same pixels both times and the bowl outlined well while the stem is
thickened into a stub. The tapered glass comes back once, outlined cleanly,
because a wide shape with no thin part is the easiest thing here for a coarse
outline to hold. The straight glass comes back once, but the stemmed glass's
outline leans outwards from the point below the camera and overlaps it, so the
short glass's outline holds only the part of it that the tall one did not cover.
The table itself is named and dropped by the filter.

What the arithmetic then makes of that is instructive. The two outlines of the
stemmed glass resolve to one place, so the one-report-per-place rule collapses
them into a single report, and the double naming costs nothing. The tapered
glass is reported accurately. The straight glass is reported at a place
pulled towards the part of it that stayed visible, and with a width read from a
slice of its silhouette rather than the whole, so it is reported too narrow.
Its width may still fall inside the range some kind of glass can be, in which
case nothing refuses it and a wrong report reaches the report file with nothing
marking it as doubtful.

That last sentence is the honest summary of this solution. The count says three
glasses were found and three were expected, so the run looks successful, and one
of the three is quietly wrong. It is the failure a borrowed model used as the
decider produces most often, and the reason the comparison against a model
fitted here matters.

## What it needs

Very little, which is the point.

It needs the Ultralytics package and the model's weights, which the package
downloads by itself the first time it runs, so there is no data preparation step
of any kind. It runs on this machine's integrated graphics through the same
backend the other borrowed-model solutions in this project use, and the weights
are small enough that memory is not a concern. The model family comes in several
sizes; the smaller end is the sensible place to start, because the glasses here
fill a reasonable part of the frame and a larger model costs time without
obviously buying accuracy on silhouettes this plain.

What it does not need is the expensive part of every other learned solution
here: no labelled pictures, no training run, no weights file to keep in step
with the cell, and no held-out set except the small one used to set the bar on
the confidence number.

## The licence, which is a real cost here

This section exists because the choice of model carries a condition that the
rest of this project does not, and a reader who takes this solution forward
should meet it here rather than discover it later.

Ultralytics YOLO26-seg is licensed under the AGPL. The AGPL requires that
anybody who distributes the software, **or offers its functionality over a
network**, makes the complete corresponding source available under the same
terms. That network clause is the part that bites, because it reaches a product
that never ships a copy of the model to anybody and only serves answers from it.
Everything else this project depends on is permissively licensed and can be used
commercially without that obligation, as [the implementation
notes](../../../../implementation-notes.md) record, so this one component would
change the terms of the whole perception step if it were carried into a product.

The choice is made here with that understood. This folder exists to compare
methods and learn what each kind of model buys, and for that purpose the licence
costs nothing. If the method proved to be the right one and the work were headed
somewhere commercial, the replacement is straightforward and the implementation
notes already name the candidates: permissively licensed instance segmenters
that do the same job, one of which [solution
9](09-a-fine-tuned-instance-segmenter.md) already uses. Nothing in this
solution's design depends on the borrowed model being this particular one, which
is worth saying plainly: what is being tested is whether an off-the-shelf
instance segmenter works here at all, and the answer to that question transfers
to whichever one is licensed conveniently.

## Where it is strong and where it breaks

The strengths all come from the same source, which is that nothing is fitted.

There is nothing to collect, nothing to train and nothing to keep in step with
the cell, so the solution can be tried in an afternoon and gives the folder a
reading on what a borrowed model is worth before anybody invests in labels. It
answers the merge directly, because a model that finds objects returns one
outline per object rather than one per connected shape. It needs no graphics
card of its own. And it is a genuine upper bound on convenience: no other
solution here can be cheaper, so if this one were good enough, several of the
others would not need to exist.

The weaknesses divide into what the borrowing costs and what it cannot be asked
to do.

What the borrowing costs is accuracy at the edge and honesty in its numbers. The
outline is built coarsely and enlarged, so widths carry an error that does not
average away, and the thin stem of a glass is where it is worst. The confidence
number is uncalibrated on these pictures, so any bar on it is a hand-set knob.
The names are somebody else's categories, so they filter usefully and mean
nothing beyond that. And the domain gap is large enough that the whole thing may
simply not work, since the light and transparency that identify a glass in a
photograph are mostly missing from a grey picture shaded from depth.

What it cannot be asked to do is anything that needs fitting. A partly hidden
glass is read as a smaller glass in the wrong place, and the repair for that
needs training. A completely hidden glass is invisible to it, and no model can
find what left no pixels. Neither limit has a fix inside this solution, and both
are reported as doubt rather than guessed at.

The honest position is therefore that this is the first thing to run and
unlikely to be the thing that ships. Its value is the comparison it makes
possible rather than the accuracy it delivers.

## The general ideas behind this

Four named ideas sit under this solution, and each is worth knowing in its own
right, including where it is normally the wrong tool.

### Zero-shot transfer — using a model on a task it was never fitted for

A model is used **zero-shot** when it is applied to a task with no examples of
that task at all, relying entirely on what it learned elsewhere. It works when
the new task is genuinely a special case of the old one, which is close to true
here: finding drinking vessels on a table is something the borrowed model's
training set contained.

It is normally the right first move whenever a general model exists and labels
are expensive, because it costs an afternoon and tells you how hard your problem
actually is. It is normally wrong as a final answer when the input differs
visibly from what the model was fitted on, which is the case here, and wrong
whenever the categories you need are finer than the categories the model knows,
which is also the case here.

### Closed-vocabulary detection — a fixed list of things that can be named

A model of this kind can only ever return names from a list fixed when it was
fitted. That is called a **closed vocabulary**, and it is the structural reason
the names here are a filter rather than an answer: the list cannot contain this
cell's four kinds, because it was written before this cell existed.

A closed vocabulary is right when your categories really are on the list, and it
is efficient, predictable and easy to reason about. It is wrong when they are
not, and the usual repairs are to fine-tune the model onto your own categories,
which is [solution 9](09-a-fine-tuned-instance-segmenter.md), or to use a model
that accepts a description in words instead of a fixed list, which removes the
restriction at the cost of being markedly less reliable about outlines.

### One-stage detect-and-segment, against propose-then-classify

This solution's model does the finding and the naming together in a single pass.
The alternative arrangement, used by [solution
8](08-segment-anything-then-keep-the-glasses.md), proposes regions first with one
model and classifies them afterwards with another.

Doing both at once is faster and simpler, and it is the right choice when the
categories you want are the ones the model names. Separating the two is the
right choice when they are not, because the proposing half transfers across a
domain gap much better than the naming half does: shapes are shapes everywhere,
while what counts as a cup is a judgement that was fitted to somebody else's
data. That is the trade this solution and solution 8 are placed on either side
of, and it is the cleanest reason to run both.

### Calibration under changed input

A model's confidence is fitted, implicitly, on the data it was trained and
validated on, so moving it to different data breaks the calibration while often
leaving the ranking usable. Knowing which of those two properties you depend on
is the practical point.

Trusting the ranking is usually safe and is what this solution does. Trusting
the numbers requires a repair, which is a small correction fitted on data where
the answer is known, and that repair is cheap and almost always worth doing
before a threshold on a confidence number is allowed to decide anything that
matters.

## Where it sits among the other solutions

This solution is one end of a line that runs through three of the others, and
the line is the useful way to see it.

At this end, nothing is fitted in the cell and the borrowed model's own
vocabulary picks the glasses. One step along, [solution
8](08-segment-anything-then-keep-the-glasses.md) borrows a model that outlines
without naming and fits a small keeper here to pick the glasses, so a little is
fitted and the part that transfers worst is replaced. Another step along,
[solution 9](09-a-fine-tuned-instance-segmenter.md) continues a borrowed model's
training on this cell's own pictures, so the finding is borrowed and then
adjusted. At the far end, [solution 6](06-a-network-trained-from-scratch.md) fits
everything here and borrows nothing.

Read in that order, the four of them measure what each increment of fitting
buys, and this solution is the baseline the other three are read against. It is
also the only one of them that could be running this afternoon, which is a
different kind of usefulness and not a small one.

← [Choosing the next look](04-choosing-the-next-look.md) · [A network trained
from scratch](06-a-network-trained-from-scratch.md) →
