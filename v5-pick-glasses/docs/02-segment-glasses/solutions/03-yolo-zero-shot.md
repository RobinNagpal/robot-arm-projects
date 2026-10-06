# Solution 3 — a borrowed model, as it downloads

> **What it uses** — the Ultralytics package, PyTorch running on this machine's
> integrated graphics through Apple's MPS backend, and the Ultralytics
> YOLO26-seg instance segmentation model exactly as it downloads. The weights
> fetch themselves the first time the model is used.
> **What it does** — it shows the borrowed model a survey picture from the top,
> takes the list of objects the model reports, and keeps the outlines whose
> name is a drinking vessel while dropping everything else the model named. A
> survey is three pictures from three overlapping stations, and the model is
> asked about each one on its own, which is the examiner's arrangement rather than
> this solution's.
> Nothing whatsoever is fitted in this cell, so there is not a single number in
> this solution that came from this project's own data.
> **How the output is produced** — the grey picture shaded from depth goes into
> the model; the model returns, for each object it believes it found, a box, a
> name from a fixed list of categories, a confidence number and an outline; the
> design keeps the outlines named as drinking vessels and discards the names
> afterwards; the kept outlines are the masks, and the shared arithmetic in [the
> examiner](../the-examiner.md) turns each mask into a place on the table and a
> rough width.
> **How it differs from the other five** — [solution
> 1](01-rules-on-the-table.md) uses no model at all and reasons about depth with
> arithmetic a person can read. [Solution 2](02-train-from-scratch.md) fits
> every number it holds on this cell's own pictures, where this one fits none.
> [Solution 4](04-yolo-fine-tuned.md) is this same library, this same model and
> these same starting weights with training on this cell's pictures added, and
> with the borrowed list of category names cut to the single class "glass",
> which is part of that training rather than a separate choice. Nothing else
> varies between the two, and that is the point of running both. [Solution
> 5](05-sam2-with-a-keeper.md) borrows a model that outlines without naming, so
> it has to fit a small keeper here to decide which outlines are glasses, which
> is the one thing this solution never needs. [Solution
> 6](06-rf-detr-fine-tuned.md) trains a different architecture here and carries
> a permissive licence instead of this one's.
> **What it costs** — no labels, no training run, no weights file to keep in
> step with the cell, and no graphics card of its own. The whole cost is the
> licence, which is why it has a section to itself below.

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the two places the camera works from, from the top and from the side, all four
> sensors, and the words this project uses them with. What follows is only what
> is specific to this solution.

## Introduction

This document describes how [problem 2](../problem.md) could be answered by
downloading a model and running it, without collecting a single label and
without training anything at all. The solution is built, and what it scored is
recorded beside the code, in
[`03-yolo-zero-shot/README.md`](../../../02-segment-glasses/03-yolo-zero-shot/README.md)
and in that folder's `results.json`. The reasoning below was written before the
run and is kept in the voice it was written in, so where it says what the method
would do, read that as what the design expected rather than as a measurement.

The design is worth writing down because of what it does not contain. Every
other solution that uses a model pays something before it can answer: a set of
labelled pictures, a training run, and a weights file that has to be refitted
whenever the cell changes. This one would pay none of that, because the model it
borrows was already fitted on photographs of everyday scenes, and the list of
things that model can name already contains drinking vessels. So the model would
be asked for glasses and would answer on the first picture, having never seen
this cell.

That makes it the cheapest of the six to try, and it also makes it the baseline
for the sharpest comparison in the set. By the end you will understand what an
instance segmentation model returns and how that differs from the two
neighbouring kinds of segmentation model, why the borrowed category names can
only ever be a filter, how the outline is built and why it is approximate in a
way the arithmetic downstream feels, why the confidence number beside each
outline is not a probability on these pictures even though it looks like one,
what the domain gap is and why it runs in both directions here, and what the
licence costs, because on this solution the licence is a real cost rather than a
footnote.

## The code that does the work

This solution is almost entirely somebody else's code, so the part worth reading
is small: one call into the borrowed library, and the handful of lines that
decide what to keep out of the answer. Those lines are the whole of what this
project wrote, and seeing them is the quickest way to understand both what the
solution is and how little of it is this project's.

The call and the handling of its answer are in
[`03-yolo-zero-shot/yolo_zero_shot.py`](../../../02-segment-glasses/03-yolo-zero-shot/yolo_zero_shot.py).
The library is Ultralytics: `YOLO` is the model, `attempt_download_asset` is
what fetches the weights, and `model.predict` is the one line where the borrowed
model does its work. Everything around it is this project's, and it is short.

```python
@lru_cache(maxsize=1)
def _model():
    ...
    from ultralytics import YOLO
    from ultralytics.utils.downloads import attempt_download_asset
    ...
    return YOLO(attempt_download_asset(CACHE / MODEL)), device.pick()

...

def masks_from(answer, shape: tuple[int, int]) -> list[np.ndarray]:
    ...
    names: Mapping[int, str] = answer.names
    confidences = np.asarray(answer.boxes.conf, dtype=float).ravel()
    keep = drinking_vessels.are_drinking_vessels(answer.boxes.cls, names) & above_the_bar(confidences)
    surest = sorted(range(len(confidences)), key=lambda index: -confidences[index])
    return merge_doubles(outline_to_mask(answer.masks.xy[index], shape) for index in surest if keep[index])

def look(picture) -> object:
    ...
    model, where = _model()
    answers = model.predict(
        pictures.shade(picture),
        conf=CONFIDENCE_BAR_SET_BY_HAND,
        device=where,
        verbose=False,
    )
    return answers[0].cpu()
```

The filter those lines call is in
[`03-yolo-zero-shot/drinking_vessels.py`](../../../02-segment-glasses/03-yolo-zero-shot/drinking_vessels.py),
and it is worth showing rather than describing, because the solution's one
promise is that nothing in it was tuned to this cell and that promise covers
this list. Every name in it is one of the borrowed model's own categories, read
off its fixed list, and not one was added after anybody saw what the model
called a glass here.

```python
VESSELS = ("wine glass", "cup")

...

NEIGHBOURS = ("bowl", "vase", "bottle")

ACCEPTED = frozenset(VESSELS + NEIGHBOURS)

def is_drinking_vessel(name: str) -> bool:
    """Whether one of the model's category names is kept."""
    return name in ACCEPTED
```

Two things show from that. The borrowed library is reached in exactly one place,
and what this project contributes is a bar on the confidence number, a filter on
names, and the collapsing of a glass that arrived twice — after which the name
is gone and what leaves is a list of masks carrying no claim about what was
outlined. And nothing above reads a fitted file, because there is none: the
folder has no training command at all, and its `fit` function exists only to
refuse. The bar on the confidence number, the share of pixels that makes two
outlines one, and those five names are everything this solution chose, and none
of it came from this cell's data.

## The problem this solves

Problem 2 asks for one record per glass on the table, each with a mask, a place
and a rough width. The difficulty is not seeing that something is there but
deciding **how many things are there**. Two glasses standing well apart on the
table can still leave one connected shape in a picture taken from the top,
because the rim of each glass is nearer the lens than the table is, so each
glass covers more of the picture than its footprint deserves. A method that
treats each connected shape as one object then reports one glass where two are
standing. That is the merge, and it is what most of the six solutions attack.

A model built to find objects attacks the merge directly, because such a model
returns **one outline per object** rather than one outline per connected shape.
Two glasses whose outlines join in the picture are still two objects, and a
model fitted on crowded photographs has met that situation many thousands of
times, in scenes where cups and glasses stand side by side on tables. So the
hope is a reasonable one: the separation this cell finds hard is the separation
the borrowed model was fitted to perform.

What makes this version of the hope worth testing first is its price. The other
model-based solutions need pictures of this cell with every glass outlined, and
then a training run that has to be repeated whenever the cell changes. Here
there would be nothing to collect and nothing to repeat. If the borrowed model
worked even moderately well, it would be the fastest route from no perception at
all to a working report, and that is worth knowing in an afternoon rather than
after a week spent building a training set.

## The main idea

The idea has three steps, and only the first two belong to this solution at all.

**First, run the borrowed model on the survey picture from the top.** The model
is Ultralytics YOLO26-seg, taken exactly as it downloads. It is an **instance
segmentation model**, which means that for every object it believes it has found
it returns four things together: a box around the object, a name taken from a
fixed list of categories, a number saying how sure it is, and an outline marking
which pixels inside the box belong to that object rather than to the background
or to a neighbouring object.

**Second, keep the outlines whose name is a drinking vessel.** The fixed list of
categories the model was fitted on is a general one, covering the ordinary
contents of ordinary photographs, and several of its entries are things a person
drinks from. Those are the ones this design would keep, and everything else the
model named would be dropped.

**Third, hand the kept outlines to the shared arithmetic.** An outline is a set
of pixels, and turning a set of pixels into a place on the table and a width is
a job the examiner does, the same way, for every solution that produces masks.
Nothing about that step changes here.

So the whole of this solution is the first two steps, and the second step is a
filter on a list of names rather than anything fitted. That is the point to
remember: **this solution would contain no numbers fitted in this cell at all**,
not one.

![The whole chain, with the one step this project wrote marked out: a grey picture from the top goes into the borrowed model exactly as it downloads, the model returns a box, a name, a score and an outline for every object it believes it found, a gate keeps an outline only when its name is one of five, the name is then thrown away and the examiner's shared arithmetic turns what is left into a place and a width; the funnel underneath is the measured one, in which 180 glasses standing across 36 pictures produced 87 named outlines and five names on the list of five, every one of them the same name.](../../../images/02-segment-glasses/03-the-name-is-the-only-gate.png)

## What instance segmentation is, and the two kinds beside it

Three kinds of model all produce outlines, and they are not interchangeable, so
they are worth separating before going further.

**Semantic segmentation** labels every pixel with a category and stops there. It
would mark all the glass pixels in the picture as glass, which sounds like what
this problem wants until you notice that two glasses whose outlines join produce
one connected region of glass pixels, with nothing in the output saying where
one ends and the next begins. A semantic model therefore hands the merge
straight back, unsolved.

**Instance segmentation** labels every pixel *and* says which object it belongs
to. Two glasses whose outlines join come back as two outlines that happen to be
adjacent, so the merge is answered inside the model. This is why problem 2
reaches for this kind of model and not for the simpler one.

**Promptable segmentation** outlines whatever is at a place you point to, and
names nothing at all. It separates objects very well and has no opinion about
what they are. That is the kind of model [solution 5](05-sam2-with-a-keeper.md)
borrows.

That last difference is the whole reason this document is shorter than solution
5's. A model that outlines without naming has to be followed by something that
decides which of its outlines are glasses, and in solution 5 that something is a
small keeper fitted on this cell's pictures. A model that outlines **and** names
needs no such thing, because the naming is already done. The borrowed model's
list of categories does the job that solution 5 has to fit a keeper to do, and
that is exactly why this solution can claim that nothing in it is fitted here.

## Why the borrowed names are a filter and never the kind of glass

The naming is also where the weakness of borrowing first becomes visible, so
this is the section to read most carefully.

The list of categories the model knows was drawn up to describe photographs of
the everyday world, and it contains several entries a drinking glass could
plausibly belong to: a stemmed drinking vessel, a plain cup, and a few shapes
that are near neighbours of both. The cell's four kinds do not correspond to
those entries. The two kinds with a stem, the stemmed glass and the short
stemmed glass, resemble the stemmed vessel in the list. The two without a stem,
the straight glass and the tapered glass, resemble the plain cup. But the
resemblance is loose, the model has never seen these particular shapes, and the
boundary it draws between its own categories was never meant to tell this cell's
two stemmed kinds apart.

Two consequences follow from that mismatch.

The first is that **the filter on names has to be generous**. If only one
category were accepted, every glass the model named with a neighbouring category
would be thrown away, and the solution would lose a whole kind for no reason. So
the filter should accept the whole group of drinking-vessel categories, and
accept in exchange that it will sometimes also admit something that is not a
glass.

The second is that **the name must never be carried into the record as the kind
of glass**. The temptation is real, because a free guess at the kind looks like
a gift. It is not a gift: it is a category from somebody else's list, assigned
by a model that was never shown this cell's kinds, and it would be wrong often
enough to be dangerous. Problem 2 does not ask for the kind in any case, since
every glass in one arrangement is the same kind and that kind is known, and
naming a kind from a glass's own profile is [what problem 1 does after the arm
has looked at the glass from the
side](../../problem-1/step3-what-kind-of-glass.md). So the name here serves as a
filter and is then thrown away.

Throwing it away is also what keeps this solution inside the rule that governs
the whole project, which is that **no glass's size is written down anywhere**. A
borrowed category carries an implied size with it, because the model's idea of a
stemmed drinking vessel was formed from photographs of real ones, at the sizes
real ones come in. If the name travelled any further than the filter, that
implied size would travel with it, and a belief about how big a glass is would
have entered the cell without anything having measured it. Dropping the name
immediately after filtering is what prevents that, and it is a deliberate choice
rather than tidiness.

## How the outline is produced, and why it is approximate

The outline needs some explanation too, because its shape is not free to be
anything, and the restriction has a consequence the arithmetic downstream feels.

A model of this kind does not draw an outline pixel by pixel. Instead it
computes, once for the whole picture, a short list of coarse pattern images, and
then for each object it returns a short list of weights. The object's outline is
the weighted sum of those patterns, cut at a threshold, and then enlarged to the
size of the picture. The useful comparison is a familiar one from maths: this is
the same move as approximating a curve by a short weighted sum of fixed basis
functions. A handful of terms captures the broad shape of almost anything, and
no handful of them will ever capture a fine detail that none of the basis shapes
contains.

Two things follow for this cell.

**A thin part of a glass is the first thing lost.** A stem is narrow compared
with the bowl above it, so it is exactly the sort of detail a coarse pattern
cannot hold, and the outline would tend either to thicken it into a stub or to
drop it. The examiner measures how much of each real glass a mask covered and
breaks that number down by kind for precisely this reason, and the expectation
here is the one the problem statement already sets out from the shapes alone:
the two kinds without a stem should be outlined almost exactly, and the two with
a stem should be where the method does worst, and the stemmed glass worst of
all. That is an expectation drawn from the shape of the glasses and the
coarseness of the outline, not a measurement of this model.

![The two mask numbers broken down by kind, measured on the handful of glasses whose names got past the filter: the two kinds without a stem are covered almost exactly and the stemmed kinds worst, which is the order this section predicts from the shapes alone, while the outline leaks only a few percent onto the table in every kind; each bar carries the number of glasses its median is taken over, and that number is between one and five, so the order is a hint rather than a result.](../../../images/02-segment-glasses/03-the-outlines-were-not-the-problem.png)

**The edge of the outline is approximate, and the arithmetic reads the width
from the edge.** The shared step takes a glass's width from how far its mask's
points reach away from the axis, so an outline that is a little too generous
reports a glass a little too wide, and one that is a little too tight reports it
a little too narrow. The error would not cancel out over many glasses, because
the enlargement step tends to err the same way every time. This is the main
reason to expect this solution to sit further from the best achievable answer
than a model fitted on this cell's own pictures, and it is a limit of the
outline rather than of the finding.

## The number beside each outline, and why it is not a probability

Each outline arrives with a number the model offers as its confidence, and it is
worth being precise about what that number would be worth here, because the
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
to be honest about their size. So this design may use the number to sort the
outlines and to set a bar below which an outline is ignored, but it must treat
that bar as a **knob, not as a probability threshold with a meaning**. Calling
it a probability would be claiming a property nobody has measured.

What the code does with that knob is the strictest thing it could do: it leaves
it at the value the library itself uses when nobody chooses one. Nothing here
looked at this cell's pictures and moved it, because the moment a bar is tuned
on arrangements from the examiner, this solution stops being a borrowed model used
as it downloads and becomes a very small fitted one. The bar is therefore a
borrowed number like the weights are borrowed, and the scorecard records that
nothing at all was fitted here.

This is also the one place where the solution could be improved without
abandoning its central promise. Fitting a small correction from the model's
scores to honest probabilities needs no change to the model and no outlines
drawn by hand, only a set of arrangements where the answer is known. That would
be a few fitted numbers rather than none, and it would buy a bar that means
something. It is worth noting as an option and worth keeping out of the
baseline, because the baseline's whole value is that it fits nothing.

## The domain gap, which is the main risk

Everything above assumes the borrowed model works at all on this cell's
pictures, and that assumption deserves its own section, because the difference
between what the model was fitted on and what it would be shown here is large
and runs in both directions.

A **domain gap** is the difference between the data a model was fitted on and
the data it is used on. Models fail across such a gap in a characteristic way:
not by producing nonsense, but by producing confident, plausible, wrong answers,
which is worse, because nothing downstream looks suspicious.

**The picture is not a photograph.** The cell gives a solution a grey picture
shaded from how far away each surface is. A borrowed model's strength on real
photographs comes largely from real light: the way a surface changes shade as it
curves, the texture of a table, a shadow that says where an object meets the
surface it stands on, and the colour differences that separate one object from
the one behind it. Very little of that is present here. The model would be asked
to work with a fraction of the evidence it learned to use.

**The glasses are not photographed glasses either, and this is the direction
that is easy to forget.** A real drinking glass is transparent, so a photograph
of one shows the background through it, a bright highlight along one side, and a
bright line where the rim catches the light. Those are precisely the features
that tell a model, in a photograph, that it is looking at a glass. The cell's
glasses are rendered as solid shaded shapes, so the strongest evidence the model
has for its own category is absent, while the broad silhouette, which is weaker
evidence, is all that remains. So the gap is not only that the picture is poorer
than a photograph; it is also that the thing in the picture no longer looks like
the thing the model was taught to name.

![A drinking glass as a photograph shows it from the side, with a bright line where the rim catches the light, a highlight running down one side, the wall behind showing through it and a shadow where it meets the table, set beside the same kind of glass as this cell renders it from the top: a plain disc shaded by how far away the nearest surface is, with not one of those four features present, so that all the model is left with is a round silhouette and its width.](../../../images/02-segment-glasses/03-a-glass-from-the-top.png)

Put together, this is the clearest reason the solution might fail outright
rather than merely do poorly, and it is also what makes the comparison with
[solution 4](04-yolo-fine-tuned.md) the interesting one. Solution 4 takes this
same model and continues its training on this cell's pictures, which is the
standard repair for exactly this gap. The difference between the two would
therefore be a clean measurement of what the gap costs, and that is the most
useful thing this solution could contribute to the folder even if it performed
badly.

![Every name the borrowed model offered over thirty-six pictures, kind by kind and with no filter in front of it, set against the five names the filter accepts: four of those five were never offered once, the only accepted name that ever arrived was vase, five times out of eighty-seven, and seventy-six of the eighty-seven were a sports ball or a frisbee, which are the two roundest things on the model's list. The model finds the objects and names them; it simply does not call them drinking vessels.](../../../images/02-segment-glasses/03-what-it-named.png)

## The masks are what this contributes

It is worth stating plainly where this solution stops, because the boundary is
the same for all six and is what makes them comparable.

The input is fixed by the examiner: for each survey picture, the grey picture
shaded from depth, the depth reading at every pixel, and the camera's own pose,
and nothing else. In particular no solution may read the simulator's record of
what it spawned. The output is fixed too: one record per glass, holding its mask
pixels, its place on the table and a rough width.

The step between the mask and the place belongs to [the test
examiner](../the-examiner.md) rather than to the solution. So **this solution
contributes only the masks**, and any difference in its score belongs to the
mask. It cannot win by measuring more cleverly and it cannot lose by measuring
worse. One consequence is worth repeating because it removes a question that
would otherwise be asked here: **no model in this problem produces a pose.**
Models produce masks, the place comes from depth and the camera's own pose by
arithmetic, and a glass standing upright on a flat table has no orientation left
to find.

Two further points follow from that boundary. A single glass can be named twice,
under two neighbouring drinking-vessel categories, and arrive as two outlines
covering nearly the same pixels; the examiner counts a real glass that collected
two reports as a split, so the design should merge outlines that cover
substantially the same pixels before it hands anything over, rather than leaving
the examiner to count one glass twice. And a mask that asserts pixels the camera
never saw the glass at must say which ones, because the depth reading at such a
pixel belongs to whatever stood in front; that case does not arise here, since
the outlines this model returns mark only pixels where the object was actually
visible.

## How the concepts fit together

The pieces now connect into one picture, and it is a short picture because the
solution is short.

A model fitted elsewhere would be shown this cell's grey picture from the top
and would return, for each thing it found, an outline and a name. The names come
from a general list, so they would be used only to decide which outlines are
worth keeping and then thrown away, because a borrowed category carries an
implied size that must not enter this project. The outlines are built from a
short weighted sum of coarse patterns and then enlarged, so they are good about
where a glass is and only approximate about where its edge lies, and the shared
arithmetic reads the width from that edge. The number beside each outline would
order them usefully but would mean nothing as a probability, because the
pictures are not what it was calibrated on. And the same change of pictures is
the main risk to the whole arrangement, since the light and the transparency
that tell a model it is looking at a glass are mostly absent from a grey picture
shaded from depth.

Every one of those is a consequence of one decision: **fit nothing here**. That
decision is what would make the solution free to try, and it is also what
removes every lever that would normally be pulled to fix the problems above.

## When the glasses are completely hidden

Every solution document in this folder answers this question, and the answers
differ in a way worth comparing. This one's answer is **no, from either of the
camera's two places**, and the reason is the same reason as for the other
mask-producing solutions.

**Looking from the top**, a tall glass's outline can sweep over a short one and
cover it completely, so the short glass appears in no picture at all. A model
that finds objects in a picture can only find objects the picture contains.
There would be nothing at those pixels but the tall glass, so one outline would
come back, correctly describing the glass the camera could see, and the covered
glass would not merely be mis-measured but absent from the model's output
entirely. No bar on the confidence number and no change of model size alters
this, because the evidence is not weak, it is missing.

**Looking from the side**, the situation is cleaner and worse. Two arrangements,
one with a far glass standing behind a near one and one with the far glass taken
away, produce the same picture pixel for pixel. The model is a function of the
picture, so it would return the same outlines with the same names and the same
numbers for both. Nothing the model could be asked would distinguish them.

The cure for both lies outside this solution, in [looking again at what was
hidden](../hidden-glasses.md), which every one of the six points at. It works
out which parts of the table nobody could have seen and sends the camera to
cover them from new positions. This solution would contribute the outlines that
argument starts from, and would contribute nothing to the argument itself.

## A worked example

Following one crowded arrangement through makes the failures above easier to
recognise, because they appear together rather than one at a time.

Four glasses of the stemmed kind stand in the glass zone, which is the fewest an
arrangement holds. Three of them are where the interest is: one near the middle,
standing at the tall end of the range its kind allows, one a little way out from
it at the short end of that range, and one off near the edge of the frame. The
fourth stands clear of the other three and is outlined without any trouble. The
camera takes the survey picture from the top.

Suppose the borrowed model returns six outlines. The tall glass comes back
twice, once under each of two neighbouring drinking-vessel categories, with
nearly the same pixels both times, its bowl outlined well and its stem thickened
into a stub. The glass near the edge comes back once and is outlined reasonably,
because the bowl is the easy part and the stem is the hard part wherever the
glass stands. The glass standing clear comes back once as well, outlined
cleanly. The short glass comes back once too, but the tall glass's outline leans
outwards from the point directly below the camera and overlaps it, so the short
glass's outline holds only the part of it the tall one did not cover. The table
itself is named and dropped by the filter, which accounts for the sixth outline.

What the arithmetic would make of that is the instructive part. The two outlines
of the tall glass cover substantially the same pixels, so merging them before
handing anything over turns them into one record and the double naming costs
nothing. The glass standing clear is reported accurately, and the glass near the
edge is reported with a place that is good and a width pulled in a little by the
lost stem. The short glass is reported at a place pulled towards the part of it
that stayed visible, and with a width read from a slice of its silhouette rather
than from the whole of it, so it is reported narrower than it is.

That last report is the hazard this solution carries. Four glasses were put out
and four reports came back, so the counts look right. One of the four is
quietly wrong, and nothing in the run marks it as doubtful, which is why the
comparison against the same model fitted here matters: a wrong report that
looks right is worse than no report.

**The run, when it was made, failed in a different way from this, and the
difference is worth more than the example.** This walk-through assumes the
model names the glasses and then draws them imperfectly. It does not name them.
Over the held-out scenes nothing at all was merged, split or falsely found,
while nine glasses in ten were never reported, so the quietly wrong report
above is a hazard the method has rather than the failure it actually produced.
The measured failure is silence, and the section on what was measured gives
it.

## What it needs

Very little, which is the whole point.

It needs the Ultralytics package and the model's weights, which the package
downloads by itself the first time the model is used, so there is no data
preparation step of any kind. It would run on this machine's integrated graphics
through PyTorch's MPS backend, the same backend the rest of this project's
learned work uses, and the weights are small enough that memory is not a
concern. The model family comes in several sizes, and the smaller end is the
sensible place to start, because the glasses fill a reasonable part of the frame
and a larger model costs time without obviously buying accuracy on silhouettes
this plain. Whichever size is chosen, solution 4 continues the training of that
same one, because the pair is only clean while both start from the same file.

What it does not need is the expensive part of every other learned solution
here: no labelled pictures, no training run, no weights file to keep in step
with the cell, and no held-out set at all, because there is no number in it
that this cell chose.

## The licence, which is the real cost here

This section exists because the choice of model carries a condition the rest of
the project does not, and a reader who takes this solution forward should meet
that condition here rather than discover it later.

Ultralytics YOLO26-seg is licensed under the AGPL-3.0. The AGPL requires that
anybody who distributes the software, **or offers its functionality over a
network**, makes the complete corresponding source available under the same
terms. That network clause is the demanding part, because it reaches a product
that never ships a copy of the model to anybody and only ever serves answers
from it. Everything else this project depends on is permissively licensed and
can be used commercially without that obligation, as [the implementation
notes](../../../implementation-notes.md) record, so this one component would
change the terms of the whole perception step if it were carried into a product.

The choice is made here with that understood. This folder exists to compare
methods and to learn what each kind of model buys, and for that purpose the
licence costs nothing, because nothing is shipped and nothing is served. Nothing
in this solution's design depends on the borrowed model being this particular
one, which is worth saying plainly: what is being tested is whether an
off-the-shelf instance segmenter works here at all, and the answer to that
question transfers to whichever one is licensed conveniently. [Solution
6](06-rf-detr-fine-tuned.md) already uses a permissively licensed segmenter, and
the implementation notes name others, so the replacement is straightforward if
the method proved to be the right one and the work were headed somewhere
commercial.

## Where it is strong and where it breaks

The strengths all come from the same source, which is that nothing is fitted.

There would be nothing to collect, nothing to train and nothing to keep in step
with the cell, so this solution could be tried in an afternoon and would give
the folder a reading on what a borrowed model is worth before anybody invests in
labels. It attacks the merge directly, because a model that finds objects
returns one outline per object rather than one per connected shape. It needs no
graphics card of its own. And it is a genuine upper bound on convenience: no
other solution here can be cheaper, so if this one were good enough, several of
the others would not need to exist.

The weaknesses divide into what the borrowing costs and what it cannot be asked
to do.

What the borrowing costs is accuracy at the edge and honesty in its numbers. The
outline is built coarsely and then enlarged, so a width carries an error that
does not average away, and a thin stem is where it is worst. The confidence
number is uncalibrated on these pictures, so any bar on it is a hand-set knob.
The names are somebody else's categories, so they filter usefully and mean
nothing beyond that. And the domain gap is large enough that the whole thing may
simply not work, since the light and the transparency that identify a glass in a
photograph are mostly missing here.

What it cannot be asked to do is anything that needs fitting. The outlines mark
only pixels where the camera actually saw the object, so a glass standing partly
behind another is read as a smaller glass in the wrong place, and the repair for
that is to train a model to return the whole silhouette, which this solution
cannot do because it trains nothing. A completely hidden glass is invisible to
it, and no model can find what left no pixels. Neither limit has a fix inside
this solution, and the project's usual answer applies to both: report the doubt
rather than the guess, and send the arm to look again.

**One check the other solutions make is deliberately left out here, and the
reason is the comparison.** Every sibling refuses a report whose width no glass
of the kind on the table could have, which turns a bad outline into a stated
doubt instead of a wrong answer. This solution is handed the kind as well, and
ignores it. That is not an oversight: the quietly wrong report in the worked
example above is exactly what such a check would catch, and catching it here
would hide the behaviour that the comparison with solution 4 exists to measure.
A reader building on this solution rather than comparing it should add the
check, and the code says so where the kind is received and unused.

The honest position is therefore that this is the first thing to run and
unlikely to be the one carried into a finished product. Its value is the
comparison it makes possible rather than the accuracy it would deliver.

## The general ideas behind this

Four named ideas sit under this solution, and each is worth knowing in its own
right, including where it is normally the wrong tool.

### Zero-shot transfer — using a model on a task it was never fitted for

A model is used **zero-shot** when it is applied to a task with no examples of
that task at all, relying entirely on what it learned elsewhere. It works when
the new task is genuinely a special case of the old one, which is close to true
here, because finding drinking vessels standing on a table is something the
borrowed model's training set contained.

It is normally the right first move whenever a general model exists and labels
are expensive, because it costs an afternoon and tells you how hard your problem
really is. It is normally wrong as a final answer when the input differs visibly
from what the model was fitted on, which is the case here, and wrong whenever
the categories you need are finer than the categories the model knows, which is
also the case here.

### Closed-vocabulary detection — a fixed list of things that can be named

A model of this kind can only ever return names from a list fixed when it was
fitted. That is called a **closed vocabulary**, and it is the structural reason
the names here can be a filter and nothing more: the list cannot contain this
cell's four kinds, because it was written without this cell in view.

A closed vocabulary is right when your categories really are on the list, and
then it is efficient, predictable and easy to reason about. It is wrong when
they are not, and the two usual repairs are to continue the model's training on
your own categories, which is [solution 4](04-yolo-fine-tuned.md), or to use a
model that accepts a description in words instead of a fixed list, which removes
the restriction at the cost of being markedly less reliable about outlines.

### One-stage detect-and-segment, against propose-then-classify

This solution's model does the finding and the naming together in a single pass.
The alternative arrangement, used by [solution 5](05-sam2-with-a-keeper.md),
proposes regions first with one model and decides afterwards with a second which
of them to keep.

Doing both at once is faster and simpler, and it is the right choice when the
categories you want are the ones the model names. Separating the two is the
right choice when they are not, because the proposing half survives a domain gap
much better than the naming half does: a shape is a shape everywhere, while what
counts as a cup is a judgement that was fitted to somebody else's data. That is
the trade this solution and solution 5 sit on either side of, and it is the
cleanest reason to run both.

### Calibration under changed input

A model's confidence is fitted, without anybody intending it, on the data the
model was trained and checked on, so moving the model to different data breaks
the calibration while often leaving the ranking usable. Knowing which of those
two properties you depend on is the practical point.

Trusting the ranking is usually safe, and it is what this solution would do.
Trusting the numbers requires a repair, which is a small correction fitted on
data where the answer is known, and that repair is cheap and almost always worth
doing before a bar on a confidence number is allowed to decide anything that
matters.

## Where it sits among the other five

This solution is one end of a line that runs through three of the others, and
the line is the useful way to see it.

At this end, nothing is fitted in the cell and the borrowed model's own
vocabulary picks the glasses out. One step along, [solution
5](05-sam2-with-a-keeper.md) borrows a model that outlines without naming and
fits a small keeper here to pick the glasses, so a little is fitted and the part
that transfers worst is the part replaced. Another step along, [solution
4](04-yolo-fine-tuned.md) continues this very model's training on this cell's
own pictures, so the finding is borrowed and then adjusted, and [solution
6](06-rf-detr-fine-tuned.md) does the same for a different architecture. At the
far end, [solution 2](02-train-from-scratch.md) fits everything here and borrows
nothing, and [solution 1](01-rules-on-the-table.md) sits outside the line
altogether, with no model and no fitting of any kind.

Read in that order, [the six solutions](overview.md) measure what each increment
of fitting buys, and this one is the baseline the others are read against.

One of those comparisons is sharper than the rest, and it is the reason this
document and the next one should be read together. **Solution 4 is this same
model, from this same library, starting from these same downloaded weights, with
its training continued on this cell's own pictures.** The examiner holds the input,
the output and the marking still for both. One further thing changes with the
training, and it is honest to name it: solution 4 replaces the borrowed list of
category names with the single class "glass", because a model cannot be trained
towards this cell's own labels while still being asked which everyday object it
is looking at. That change comes with the training rather than beside it, so
nothing varies between the pair that the training did not bring, and the gap
between their scores would be a measurement of what the training bought and of
nothing else. No other pair in the folder is that clean, and that is the main
reason this solution is worth building even though it is unlikely to be the one
carried forward.

![What that pair measured: ten glasses of a hundred found on the spawned layouts and four of a hundred and one on the crowded ones, against the examiner's floor at 100 and 83 and against solution 4, which is this same model with its training continued here, at 99 and 73; and the scorecard's five columns for this solution, in which merged, split and false are all zero, so every glass it reported was a real glass and the whole of the failure is the ninety glasses that got no report at all.](../../../images/02-segment-glasses/03-silence-against-the-floor.png)

← [A network trained here from scratch](02-train-from-scratch.md) · [The same
model, fine-tuned here](04-yolo-fine-tuned.md) →
