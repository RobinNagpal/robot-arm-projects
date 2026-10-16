# Solution 3 — a borrowed model, as it downloads

> **What it uses** — the Ultralytics package, PyTorch on this machine's
> integrated graphics through Apple's MPS backend, and the Ultralytics
> YOLO26-seg instance segmentation model exactly as it downloads. The weights
> fetch themselves the first time the model is used.
> **What it does** — It shows the borrowed model each survey picture from the
> top. It keeps the outlines the model names as drinking vessels and drops the
> rest. The kept outlines are the masks. **Nothing is fitted in this cell.**
> **How it differs from the other five** — [Solution
> 4](04-yolo-fine-tuned.md) is this same model with training on this cell's
> pictures added. Nothing else differs between the two, which is why both are
> run. [Where it sits among the other five](#where-it-sits-among-the-other-five)
> places it beside the rest.
> **What it costs** — no labels, no training and no graphics card of its own.
> The real cost is [the licence](#the-licence-which-is-the-real-cost-here).

> **The cell is described once, in [the cell](../../the-cell.md).** That page
> covers the layout, the camera's two working places, the four sensors and the
> words this project uses. This page covers only what is special to this
> solution.

## Introduction

This page asks whether [problem 2](../problem.md) can be answered by
downloading a model and running it. No labels are collected and nothing is
trained. The solution is built. Its scores are in
[`03-yolo-zero-shot/README.md`](../../../02-segment-glasses/03-yolo-zero-shot/README.md)
and in that folder's `results.json`. The reasoning below was written before
the run. Where it says what the method "would" do, read that as what the design
expected, not as a measurement.

Every other model-based solution pays before it can answer: labelled pictures,
a training run, and a weights file to refit when the cell changes. This one
pays none of that. Its model was fitted on everyday photographs, and its list
of names already includes drinking vessels. So it can be asked for glasses on
the first picture.

That makes it the cheapest of the six to try. This page explains what an
instance segmentation model returns, why the borrowed names can only be a
filter, why the outline is approximate, why the confidence number is not a
probability here, why the domain gap is the main risk, and what the licence
costs.

## The code that does the work

This solution is almost all somebody else's code. The part this project wrote
is one call into the library and a few lines that choose what to keep.

The call is in
[`03-yolo-zero-shot/yolo_zero_shot.py`](../../../02-segment-glasses/03-yolo-zero-shot/yolo_zero_shot.py).
The library is Ultralytics. `YOLO` is the model, `attempt_download_asset`
fetches the weights, and `model.predict` is the one line where the borrowed
model works.

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

The filter is in
[`03-yolo-zero-shot/drinking_vessels.py`](../../../02-segment-glasses/03-yolo-zero-shot/drinking_vessels.py).
Every name in it comes from the borrowed model's own fixed list. None was added
after anybody saw what the model called a glass here.

```python
VESSELS = ("wine glass", "cup")

...

NEIGHBOURS = ("bowl", "vase", "bottle")

ACCEPTED = frozenset(VESSELS + NEIGHBOURS)

def is_drinking_vessel(name: str) -> bool:
    """Whether one of the model's category names is kept."""
    return name in ACCEPTED
```

The library is reached in one place. This project adds three things: a bar on
the confidence number, a filter on names, and merging a glass that arrived
twice. After that the name is gone, and only masks leave. Nothing reads a
fitted file, because there is none. The folder has no training command, and
its `fit` function exists only to refuse. None of the three choices came from
this cell's data.

## The problem this solves

[Problem 2](../problem.md#glasses-merge-in-the-picture-even-when-they-stand-apart-on-the-table)
explains the merge: two glasses that stand apart can leave one connected shape
in the picture. Most of the six solutions attack that.

A model built to find objects attacks it directly. It returns **one outline
per object**, not one per connected shape. The borrowed model was fitted on
many photographs of cups and glasses side by side. So the hope is fair: the
separation this cell finds hard is the one the model was fitted to do.

The price is what makes it worth testing first. There is nothing to collect
and nothing to retrain. If it worked even moderately well, it would be the
fastest route to a working report. That is worth knowing in an afternoon, not
after a week of building a training set.

## The main idea

There are three steps, and only the first two belong to this solution.

**First, run the borrowed model on the survey picture from the top.** The model
is Ultralytics YOLO26-seg, used as it downloads. It is an **instance
segmentation model**. For each object it finds, it returns four things: a box,
a name from a fixed list, a confidence number, and an outline of the object's
pixels.

**Second, keep the outlines whose name is a drinking vessel.** The model's list
is a general one for everyday photographs. Several entries are things people
drink from. Those are kept, and everything else is dropped.

**Third, hand the kept outlines to the examiner.** The examiner turns each mask
into a place and a width, the same way for every solution.

The second step is a filter on names, not anything fitted. **This solution
contains no numbers fitted in this cell.**

![The whole chain, with the one step this project wrote marked out: a grey picture from the top goes into the borrowed model exactly as it downloads, the model returns a box, a name, a score and an outline for every object it believes it found, a gate keeps an outline only when its name is one of five, the name is then thrown away and the examiner's shared arithmetic turns what is left into a place and a width; the funnel underneath is the measured one, in which 180 glasses standing across 36 pictures produced 87 named outlines and five names on the list of five, every one of them the same name.](../../../images/02-segment-glasses/03-the-name-is-the-only-gate.png)

## What instance segmentation is, and the two kinds beside it

Three kinds of model produce outlines. They are not interchangeable.

**Semantic segmentation** labels every pixel with a class, as [solution 2's
first head](02-train-from-scratch.md#semantic-segmentation--a-class-label-at-every-pixel)
does. Two joined glasses come back as one region of glass pixels. So it hands
the merge straight back.

**Instance segmentation** labels every pixel *and* says which object it belongs
to. Two joined glasses come back as two outlines side by side. The model
answers the merge itself. That is why this solution uses this kind.

**Promptable segmentation** outlines whatever is at a point you give it, and
names nothing. [Solution 5](05-sam2-with-a-keeper.md) borrows that kind. So it
must fit a small keeper here to decide which outlines are glasses. This model
names its outlines, so it needs no keeper. That is why this solution can fit
nothing.

## Why the borrowed names are a filter and never the kind of glass

The names are where borrowing first shows its weakness.

The model's list was made for everyday photographs. It has a few entries a
glass could fall under: a stemmed drinking vessel, a plain cup, and some near
neighbours. The cell's four kinds do not match them. The two stemmed kinds look
like the stemmed vessel. The straight and tapered glasses look like the cup.
But the match is loose, and the model never saw these shapes.

Two things follow.

**The filter has to be generous.** If only one name were accepted, every glass
named with a neighbouring name would be lost. So the filter accepts the whole
group, and may sometimes let through something that is not a glass.

**The name must never go into the record as the kind of glass.** It is a name
from somebody else's list, given by a model that never saw this cell's kinds.
It would often be wrong. Problem 2 does not ask for the kind anyway, because
the kind is known. Naming a kind from a glass's profile is [what problem 1 does
from the side](../../problem-1/step3-what-kind-of-glass.md).

Dropping the name also keeps the project's main rule: **no glass's size is
written down anywhere.** A borrowed name carries an implied size, learned from
real glasses at real sizes. If the name went further than the filter, that size
would go with it. So the name is dropped right after filtering, on purpose.

## How the outline is produced, and why it is approximate

The outline's shape is restricted, and the examiner's arithmetic feels the
result.

The model does not draw an outline pixel by pixel. It computes a few coarse
pattern images once for the whole picture. For each object it returns a few
weights. The outline is the weighted sum of the patterns, cut at a threshold,
then enlarged to picture size. This is like approximating a curve with a few
fixed basis functions. A few terms catch the broad shape. They never catch a
fine detail that no basis shape holds.

Two things follow for this cell.

**A thin part is lost first.** A stem is narrow next to the bowl, so a coarse
pattern cannot hold it. The outline tends to thicken it into a stub or drop
it. The design expected the stemmed kinds to do worst, as [the
problem](../problem.md#what-is-on-the-table) predicts from the shapes alone.

![The two mask numbers broken down by kind, measured on the handful of glasses whose names got past the filter: the two kinds without a stem are covered almost exactly and the stemmed kinds worst, which is the order this section predicts from the shapes alone, while the outline leaks only a few percent onto the table in every kind; each bar carries the number of glasses its median is taken over, and that number is between one and five, so the order is a hint rather than a result.](../../../images/02-segment-glasses/03-the-outlines-were-not-the-problem.png)

**The edge is approximate, and the examiner reads the width from the edge.** A
generous outline gives a glass that is too wide. A tight one gives a glass that
is too narrow. The error does not cancel, because the enlarging step tends to
err the same way each time. So this solution should sit further from the best
possible answer than a model fitted here. That is a limit of the outline, not
of the finding.

## The number beside each outline, and why it is not a probability

Each outline comes with a confidence number. The obvious reading of it is
wrong here.

A number is a **calibrated** probability when its claims come true about as
often as it says. Of the outlines it scores very high, nearly all should be
glasses. This model was calibrated on photographs. This cell's pictures are not
photographs. Under changed input, confidence is the first thing to drift. It
usually becomes too sure.

The **order** of the numbers survives better. A badly calibrated model may
still rank a clear glass above a doubtful one. So the design may use the number
to sort outlines and to set a bar. But that bar is **a knob, not a probability
threshold**.

The code leaves the knob at the library's own default. Nobody moved it after
looking at this cell's pictures. Tuning it on the examiner's arrangements would
make this a small fitted model. So the bar is borrowed, like the weights.

This is the one place the solution could improve without breaking its promise.
A small correction from scores to honest probabilities needs no model change
and no hand-drawn outlines. It needs only arrangements with known answers. That
would be a few fitted numbers instead of none. It is kept out of the baseline,
because the baseline's value is that it fits nothing.

## The domain gap, which is the main risk

[Solution 2](02-train-from-scratch.md#why-nothing-is-borrowed-and-what-that-buys)
defines the **domain gap**: the difference between the pictures a model
learned from and the pictures it is asked about. Models fail across it by
giving confident, plausible, wrong answers. Here the gap is large and runs in
two directions.

**The picture is not a photograph.** The cell gives a grey picture shaded by
depth. A photograph model leans on real light: shading on curves, table
texture, shadows where an object meets the table, and colour. Little of that is
here.

**The glass is not a photographed glass.** This direction is easy to forget. A
real glass is transparent. A photograph shows the background through it, a
highlight down one side, and a bright line at the rim. Those features tell a
model it is looking at a glass. The cell renders glasses as solid shaded shapes.
So the strongest evidence for the model's own category is gone. Only the round
silhouette is left.

![A drinking glass as a photograph shows it from the side, with a bright line where the rim catches the light, a highlight running down one side, the wall behind showing through it and a shadow where it meets the table, set beside the same kind of glass as this cell renders it from the top: a plain disc shaded by how far away the nearest surface is, with not one of those four features present, so that all the model is left with is a round silhouette and its width.](../../../images/02-segment-glasses/03-a-glass-from-the-top.png)

This is the clearest reason the solution might fail outright. It is also what
makes [solution 4](04-yolo-fine-tuned.md) the interesting comparison. Solution
4 continues this model's training on this cell's pictures, which is the
standard repair for this gap. The difference between the two measures what the
gap costs.

![Every name the borrowed model offered over thirty-six pictures, kind by kind and with no filter in front of it, set against the five names the filter accepts: four of those five were never offered once, the only accepted name that ever arrived was vase, five times out of eighty-seven, and seventy-six of the eighty-seven were a sports ball or a frisbee, which are the two roundest things on the model's list. The model finds the objects and names them; it simply does not call them drinking vessels.](../../../images/02-segment-glasses/03-what-it-named.png)

## The masks are what this contributes

[The examiner](../the-examiner.md#what-must-come-back) fixes the input and the
output for all six, and turns masks into places itself. So this solution
contributes only masks. Two points are its own.

First, one glass can be named twice, under two neighbouring names, as two
outlines over nearly the same pixels. The examiner would count that as a split.
So the code merges outlines that share most of their pixels before handing
anything over.

Second, a mask that claims pixels the camera never saw must say which ones.
That does not arise here. This model outlines only pixels where the object was
visible.

## How the concepts fit together

Every point above follows from one decision: **fit nothing here**. That
decision makes the solution free to try. It also removes every lever that would
normally fix its problems: the names, the coarse outline, the uncalibrated
score and the domain gap.

## When the glasses are completely hidden

A fully covered glass leaves no pixel, and no method that reads pictures can
find it. [Looking again at what was hidden](../hidden-glasses.md) is the shared
answer, and [solution 1](01-rules-on-the-table.md#when-the-glasses-are-completely-hidden)
shows the arithmetic from found glasses.

**This solution has the least to add.** It has no check of its own to fire.
The model returns one outline per object it sees, and a hidden glass is not in
the picture. So no entry appears.

## A worked example

One crowded arrangement shows the expected failures together.

Four stemmed glasses stand in the glass zone. One is near the middle, at the
tall end of its kind's range. One is a little way out from it, at the short
end. One is near the edge of the frame. The fourth stands clear. The camera
takes the survey picture from the top.

Suppose the model returns six outlines:

- The tall glass comes back twice, under two neighbouring names, with nearly
  the same pixels. Its bowl is outlined well. Its stem is thickened into a
  stub.
- The glass near the edge comes back once, outlined reasonably. The bowl is
  the easy part wherever the glass stands.
- The glass standing clear comes back once, outlined cleanly.
- The short glass comes back once. But the tall glass's outline leans out and
  overlaps it. So its outline holds only the part not covered.
- The table is named too, and the filter drops it. That is the sixth outline.

What the arithmetic makes of that is the useful part. The tall glass's two
outlines are merged into one record, so the double naming costs nothing. The
clear glass is reported accurately. The edge glass gets a good place and a
width pulled in a little by the lost stem. The short glass's place is pulled
towards its visible part, and its width is read from a slice. So it is reported
too narrow.

That last report is the hazard. Four glasses went out and four reports came
back, so the counts look right. One report is quietly wrong, and nothing marks
it as doubtful. A wrong report that looks right is worse than no report.

**The real run failed in a different way.** This example assumes the model
names the glasses and draws them imperfectly. In fact it does not name them.
Over the held-out scenes nothing was merged, split or falsely found. But nine
glasses in ten were never reported. The measured failure is silence. The [code
README](../../../02-segment-glasses/03-yolo-zero-shot/README.md) gives the
numbers.

## What it needs

Very little, which is the point.

It needs the Ultralytics package and the model's weights. The package
downloads the weights the first time, so there is no data preparation. It runs
on this machine's integrated graphics through PyTorch's MPS backend, like the
rest of this project's learned work. The weights are small.

The model comes in several sizes. The small end is the sensible start: the
glasses fill a fair part of the frame, and a larger model costs time without
clear gain on such plain silhouettes. Whichever size is chosen, solution 4
trains that same one, because the pair is only clean when both start from the
same file.

It needs no labelled pictures, no training run, no weights file to keep in step
with the cell, and no held-out set, because no number in it was chosen here.

## The licence, which is the real cost here

The model carries a condition the rest of the project does not. Read it here,
not later.

Ultralytics YOLO26-seg is licensed under the AGPL-3.0. Anybody who distributes
the software, **or offers its functionality over a network**, must publish the
full source under the same terms. The network clause is the hard part. It
reaches a product that never ships the model and only serves answers from it.
Everything else this project uses is permissively licensed, as [the
implementation notes](../../../implementation-notes.md) record. So this one
part would change the terms of the whole perception step in a product.

For this folder the licence costs nothing. The folder compares methods, and
nothing is shipped or served. Nothing in the design depends on this particular
model. The question is whether any off-the-shelf instance segmenter works here,
and the answer carries over to one with a friendlier licence. [Solution
6](06-rf-detr-fine-tuned.md) already uses a permissively licensed segmenter,
and the implementation notes name others.

## Where it is strong and where it breaks

Its strengths all come from fitting nothing. It can be tried in an afternoon,
before anybody pays for labels. It answers the merge inside the model. No other
solution can be cheaper, so if this one were good enough, several others would
not need to exist.

Its weaknesses are listed in the sections above: an approximate edge that is
worst at the stem, an uncalibrated confidence, borrowed names that only filter,
and a domain gap large enough that it may not work at all.

It also cannot do anything that needs fitting. Its outlines mark only visible
pixels. So a glass partly behind another reads as a smaller glass in the wrong
place. The fix is to train a model to return the whole silhouette, and this
solution trains nothing. A fully hidden glass is invisible to it. For both, the
project's usual answer applies: report the doubt, not a guess, and send the arm
to look again.

**One check the others make is left out on purpose.** Every other solution
refuses a report whose width no glass of the kind could have. This solution is
also handed the kind, and ignores it. The quietly wrong report in the worked
example is exactly what that check would catch. Catching it here would hide the
behaviour that the comparison with solution 4 exists to measure. A reader who
builds on this solution, rather than comparing it, should add the check. The
code says so where the kind is received.

So this is the first thing to run, and unlikely to be the one carried into a
product. Its value is the comparison it makes possible.

## The general ideas behind this

Four named ideas sit under this solution. Each has places where it is the wrong
tool.

### Zero-shot transfer — using a model on a task it was never fitted for

A model is used **zero-shot** when it gets no examples of the new task and
relies only on what it learned elsewhere. It works when the new task is a
special case of the old one. That is close to true here, because the model's
training set had drinking vessels on tables.

It is usually the right first move when a general model exists and labels are
expensive. It costs an afternoon and shows how hard the problem is. It is
usually wrong as a final answer when the input looks different from the
training data, as here. It is also wrong when you need finer categories than
the model knows, as here too.

### Closed-vocabulary detection — a fixed list of things that can be named

This kind of model can only return names from a list fixed at training time.
That is a **closed vocabulary**. It is why the names here can only filter: the
list was written without this cell in view, so it cannot hold the four kinds.

It is right when your categories are on the list. Then it is efficient and
predictable. When they are not, there are two usual repairs. One is to train
further on your own categories, which is [solution 4](04-yolo-fine-tuned.md).
The other is a model that takes a description in words, which is less reliable
about outlines.

### One-stage detect-and-segment, against propose-then-classify

This model finds and names in one pass. [Solution
5](05-sam2-with-a-keeper.md) does it in two: one model proposes regions, and a
second decides which to keep.

One pass is faster and simpler, and right when the model's names are the ones
you want. Two steps are right when they are not. The proposing half survives a
domain gap much better than the naming half. A shape is a shape everywhere, but
what counts as a cup was fitted to somebody else's data. This solution and
solution 5 sit on either side of that trade.

### Calibration under changed input

This is the idea in [the number beside each
outline](#the-number-beside-each-outline-and-why-it-is-not-a-probability).
Moving a model to new data breaks its calibration but often leaves its ranking
usable. Trusting the ranking is usually safe. Trusting the numbers needs a
small correction fitted on data with known answers. That repair is cheap and
almost always worth doing before a confidence bar decides anything important.

## Where it sits among the other five

This solution is one end of a line through the others. Here nothing is fitted
and the model's own names pick the glasses. [Solution
5](05-sam2-with-a-keeper.md) borrows a model that does not name, and fits a
small keeper here. [Solution 4](04-yolo-fine-tuned.md) continues this model's
training here, and [solution 6](06-rf-detr-fine-tuned.md) does the same for a
different model. [Solution 2](02-train-from-scratch.md) fits everything here
and borrows nothing. [Solution 1](01-rules-on-the-table.md) sits outside the
line, with no model at all. Read in that order, [the six
solutions](overview.md) measure what each step of fitting buys.

**The pair with solution 4 is the cleanest comparison in the folder.** It is
the same model and the same starting weights, plus training here. That training
also cuts the names to one class, "glass". [The
examiner](../the-examiner.md#why-there-is-an-examiner-at-all) explains why the
two changes come together, and why the gap between the pair measures what
training bought. That pair is the main reason to build this solution.

![What that pair measured: ten glasses of a hundred found on the spawned layouts and four of a hundred and one on the crowded ones, against the examiner's floor at 100 and 83 and against solution 4, which is this same model with its training continued here, at 99 and 73; and the scorecard's five columns for this solution, in which merged, split and false are all zero, so every glass it reported was a real glass and the whole of the failure is the ninety glasses that got no report at all.](../../../images/02-segment-glasses/03-silence-against-the-floor.png)

← [A network trained here from scratch](02-train-from-scratch.md) · [The same
model, fine-tuned here](04-yolo-fine-tuned.md) →
