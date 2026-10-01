# Problem 2 — the pre-trained way

Several glasses of one kind stand on the table, and the first job of problem 2
is to find each one in the pictures taken from the top. This folder answers that
job three times, and each time it leans on a model that somebody else has
already trained on a large collection of photographs. Very little here is
written down as a rule, and very little is trained from nothing; the work is in
joining a borrowed model to this cell. By the end of this page you will know
what the three solutions are, how to run each of them, what the machine
underneath can and cannot do, where the camera stands and why a survey is three
pictures, how a depth picture is turned into something these models will accept,
how the three are scored against each other and against the two folders that
already do the same job, and what the best score anything could reach on these
pictures is.

Those two folders are the ones to compare against. `../problem-2-programmed`
does the job with geometry and written rules only, and `../problem-2-learned`
does it with small models trained from nothing on the simulator's pictures.
This folder is the third way: the models are large, they arrive with their
weights already fitted, and the part that is fitted here is kept as small as
each solution allows.

## The three solutions

Each solution has its own document, which explains the idea and the trade it
makes. The code for all three lives here, in one folder and one environment,
because they read the same scenes and are judged by the same scorecard.

- Solution 8,
  [segment anything, then keep the glasses](../docs/problem-2/solutions/learned/08-segment-anything-then-keep-the-glasses.md),
  uses SAM exactly as it is downloaded and fits only a small keeper that
  decides which of SAM's proposals are glasses.
- Solution 9,
  [a fine-tuned instance segmenter](../docs/problem-2/solutions/learned/09-a-fine-tuned-instance-segmenter.md),
  continues the training of Mask R-CNN, which arrives with weights fitted to
  photographs, on this cell's pictures with one class.
- Solution 10,
  [amodal masks for the hidden part](../docs/problem-2/solutions/learned/10-amodal-masks-for-the-hidden-part.md),
  keeps solution 9's model and changes only what its masks are trained
  against: each glass's whole outline instead of the part of it the camera can
  see.

## Running it

Everything runs from this folder. Setup happens once and is shared by all
three; training and testing are done one solution at a time; and the last two
commands score no solution at all.

```
make setup                          # once: install the environment, fetch weights
make train SOLUTION=sam             # sam | maskrcnn | amodal
make test  SOLUTION=sam
make test-crowded SOLUTION=sam      # the same, on layouts where one glass hides another
make floor                          # no solution at all: the floor the three are read against
make by-kind                        # what the borrowed model outlines, kind by kind
```

`SOLUTION` says which of the three to work on. `sam` is solution 8,
`maskrcnn` is solution 9 and `amodal` is solution 10. `make train`, `make test`
and `make test-crowded` need it; `make setup`, `make floor` and `make by-kind`
do not, because the environment and the downloaded weights are the same
whichever solution you go on to run, and the last two run no solution.

**`make setup`** installs the environment with [pixi](https://pixi.sh), which
is the only thing to install by hand, and then fetches the weights the three
solutions start from: SAM's weights, and the photograph-trained weights that
Mask R-CNN is fine-tuned from. Both files are large, so this is the longest
one-off step on this page, and how long it takes depends more on the network
than on the machine. The files are written into a cache on disk and are not
fetched twice, so every later `make setup` only checks that they are there and
finishes at once.

**`make train SOLUTION=...`** draws scenes from the simulator, makes a picture
and its true masks from each scene, and fits the part that this solution fits.
For `sam` the only thing fitted is the keeper, so SAM is run over each training
scene to get its proposals and the keeper is fitted on top of them; fitting the
keeper is quick, and running SAM is what takes the time. For `maskrcnn` and
`amodal` the whole segmenter is trained, which is the slower job of the two,
and `amodal` takes about as long as `maskrcnn` because only the target masks
differ between them. All three are far slower than the small models in
`../problem-2-learned`, which train in about a minute; start one of these and
do something else while it runs. What it fits is saved beside the downloaded
weights, so testing can pick it up.

**`make test SOLUTION=...`** runs the solution you have trained over the
held-out scenes, which no training ever sees, scores it with the shared
scorecard, and writes the numbers. Nothing is fitted, and every scene is three
pictures. For `maskrcnn` and `amodal` that is a couple of minutes. For `sam` it
is the longest command on this page, longer than its own training: every picture
goes through SAM once for the grid of prompts, and again inside every proposal
the keeper calls more than one glass, so the work per scene depends on what the
keeper says. The weights are not committed, so train a solution before testing
it.

**`make test-crowded SOLUTION=...`** scores the same solution on the crowded
layouts instead, where glasses stand closer than the layout rule allows and one
really does hide part of another. It is the only place solution 10 can differ
from solution 9, so the two runs are reported apart rather than averaged into
one number.

**`make floor`** scores no solution. It hands the shared arithmetic the masks
the renderer itself drew the scenes from and runs them through the same survey
and the same scorecard, which says what the best possible masks are worth here
and so how much of each solution's error is the solution's own. It needs no
weights and no training, so it is the one scoring command that runs straight
after `make setup`, without waiting for anything to be fitted.
[The best any of them could do](#the-best-any-of-them-could-do) is what it
measures and what came out of it.

**`make by-kind`** asks a narrower question than any scorecard, and only about
solution 8. It shows the borrowed model a few scenes of each kind of glass,
takes the proposals that come back with no keeper after them and no scorecard,
and reports how much of each glass the best single proposal holds. So it answers
whether the borrowed model draws an outline round a glass of this kind at all,
which is the one thing solution 8 cannot train its way out of. It needs what
`make setup` fetched and nothing that `make train` fits, and it writes
`results-by-kind.json`.
[Which glasses the borrowed model outlines](#which-glasses-the-borrowed-model-outlines)
is what came out of it.

How many scenes `make train` uses has a default per solution rather than one
default for all three, because the work per scene is not the same: running SAM
over a picture costs several seconds and one training step costs under two. The
three commands that score, on the other hand, all use the same number of them,
so that every scorecard on this page is claimed on the same scenes. Pass
`SCENES=n` to `make train`, and `TEST_SCENES=n` to `make test`,
`make test-crowded` or `make floor`, to change either. `make by-kind` keeps a
small count of its own, because it asks about kinds of glass rather than about a
run, and the kinds differ far more than two scenes of one kind do.

`make check` runs the quick checks that need no weights, as in the other
folders.

## What it runs on

The speed of those commands comes from one unusual thing about this machine, so
it is worth saying what the machine is. This is an Apple silicon Mac. Its GPU
is built into the same chip as the CPU, and instead of each having its own
memory the two share a single pool, which is called unified memory. PyTorch
reaches that GPU through a backend named MPS, which is Apple's own interface
for this kind of work and sits where CUDA would sit on a machine with an NVIDIA
card. The code asks whether MPS is available, uses it when it is, and falls
back to the CPU when it is not, so everything still runs either way, only more
slowly on the CPU. There is no NVIDIA card here and no CUDA, and nothing in
this folder needs either.

Three things follow from that in practice. The first is speed: a rented machine
with a modern NVIDIA card would train these models in a fraction of the time,
because that is the hardware they and their libraries were built around, and
every training run here is longer than the same run would be there. The second
is that the amount of work is small enough for the first point not to decide
anything. A few hundred pictures is a small training set by the standards of
these models, and a run of that size finishes in a wait you can sit through,
which is what matters for a project where the point is to compare approaches
rather than to reach the best possible score. The third is memory, and it is
the reason any of this is possible: because the CPU and the GPU share one pool,
the GPU can use nearly all the memory in the machine, where a laptop with a
separate graphics card would give its GPU a small slice of dedicated memory.
Models of this size fit because of the unified memory, not because they are
small.

## Where the camera stands

Before the pictures themselves, where they are taken from, because all three
solutions are handed the same ones and none of them chooses. `data.py` owns the
camera for that reason.

The camera stands at the cell's own `SURVEY_HEIGHT`, 450 mm above the table, and
not at the 750 mm `../problem-2-sim` uses for its one overhead picture. The arm
works from 450 mm, so that is the height a claim about this cell has to be made
at. What follows from it is measured and costs something. Seen from above an
outline leans away from the point below the camera, and the higher the glass the
further it leans, so from 450 mm **one picture does not hold the glass zone**: a
tall glass at the far side of the zone is cut off at the frame edge although the
table under it is in shot, and a cut silhouette has its middle in the wrong
place. So the cell does not take one picture from that height. It takes
**three**, at the stations `survey_stations` works out from how much table one
picture covers less what a survey loses off it, which is exactly the arithmetic
`work_cell/task.py` uses. Each solution is asked about each picture on its own,
and `run.py` brings the three answers together and counts each glass once,
keeping the report from the station the glass stood nearest the middle of,
because that is the view of it with the least splay and no cut.

Three stations are not a cure, only the cell's own arrangement. With exact masks
straight from the simulator and no model involved at all, one picture from 450 mm
places a glass 15 mm from where it stands on the median; three stations bring
that to 6 mm; the 750 mm picture gives 0.3 mm. The remainder is the frame edge,
it is the same for all three solutions, and it is the floor every number in this
folder sits on.
[The best any of them could do](#the-best-any-of-them-could-do) is that floor
through the whole scorecard, and `make floor` is the command that measures it.

## Where the pictures come from

Those pictures are not photographs, and that is the most important thing to
understand before reading what each solution does. The scenes come from
`../problem-2-sim`, shared with the other two folders so that all approaches
are compared on the same table. Its renderer gives two numbers for every pixel:
a depth reading, which is how far away the surface at that pixel is, and a
glass identity, which says which glass the pixel shows, or that it shows no
glass. The identity is the truth that every training target here is built from,
and it costs nothing, because the simulator knows what it drew.

What the renderer does not give is colour. It draws none at all. The three
models, however, all expect an ordinary colour photograph, which is three
channels of numbers, one for red, one for green and one for blue. So the code
makes something in that shape out of what it has: it shades the depth reading
into a grey value, with near surfaces one shade and far surfaces another, and
then repeats that single grey channel three times to fill the three colour
channels.

This has to be said plainly, because it is the single largest risk in all three
solutions. The result has the shape of a photograph but is not one. Weights
fitted on photographs of everyday objects were fitted on texture, shading,
reflection and colour, and a shaded depth picture has none of those; its edges
are steps in distance and nothing else. The distance between the pictures a
model's weights were fitted on and the pictures it is given here is called the
domain gap, and every claim any of these three solutions makes rests on how
well it survives that gap. Solution 8 carries the most of it, because the model
that finds the objects is never trained on these pictures at all. Fine-tuning
in solutions 9 and 10 moves the weights towards these pictures, which narrows
the gap but does not close it.

## What each solution does

### Solution 8 — segment anything, then keep the glasses

SAM is a promptable model, which means it is given a picture and a prompt and
returns a mask: the prompt says where to look, and the mask says which pixels
belong to the thing found there. Prompt it with a grid of points spread over
a picture taken from the top and it proposes masks for everything in the
scene, glasses and table alike, knowing nothing about what a glass is. SAM's
weights are used exactly as they are downloaded, and nothing here changes them.

What has to be added is a keeper, which is the part that decides which of the
proposals are glasses. To keep the written-down part as small as possible the
keeper is itself learned: a small classifier over each proposal, fitted on
simulator scenes where the truth is known. So the only thing fitted in this
solution is that keeper, and everything that finds the objects is borrowed
whole. That is the tension in it. This is the least trained and the most
borrowed of the three, so it needs almost no training data, and it brings the
largest domain gap with it.

### Solution 9 — a fine-tuned instance segmenter

Where solution 8 borrows a model that knows nothing about glasses, solution 9
teaches a borrowed model what a glass is. Mask R-CNN is the standard answer to
instance segmentation, which means finding each separate object in a picture
and the pixels that belong to it. It proposes regions of the picture,
classifies each region, and predicts a mask inside each box it keeps. It
arrives with weights fitted to a large collection of photographs of everyday
objects, and fine-tuning means continuing that same training on this cell's
pictures with a single class, "glass".

This is the most end-to-end of the three: a picture goes in, and a list of
instance masks with a score for each comes out, with no clustering, no circle
fit and no grouping rule anywhere. That buys two things. There is nothing to
tune, because no threshold or grouping rule was written in the first place. And
two glasses whose outlines join in the picture come apart without being told
to, because each instance gets a mask of its own. What it costs is that the
answer cannot explain itself. It rests on weights rather than on arithmetic
that anyone can read, so when it is wrong there is no line to point at.

### Solution 10 — amodal masks for the hidden part

Solution 10 uses the same model as solution 9, built the same way, and changes
only what each instance's mask is trained against. Instead of the pixels the
camera can see of a glass, the target is the glass's whole outline, as it would
be if nothing stood in front of it. A mask like that is called amodal. The
label costs nothing, because the simulator can render each glass on its own and
take the outline from that.

What a truncated mask costs is real. The place comes from the middle of the
points at the rim of the mask and the width from how far the points spread out
from there, so a mask cut along one side puts that middle off towards the side
the camera could still see and makes the spread too small. The glass is reported
standing where no glass stands, with a width under the truth.

Nothing in this folder says when that has happened. The two checks written for
exactly this failure are a width outside the range the kind allows and a fit
error no real glass would give, and neither is in the path of solutions 9 and
10. The shared arithmetic returns no fit error at all, because it takes the axis
from the rim and the width from a percentile of the spread rather than by
fitting a circle that could be residual-checked; and neither `segmenter.py` nor
`run.py` ever compares a width it reports against what the kind allows. Where
those checks do exist, they exist elsewhere: the width range is in solution 8's
keeper, which hands over a proposal whose width no glass of the kind could have,
and the fit error belongs to the circle fit in
[cluster on the table](../docs/problem-2/solutions/programmed/02-cluster-on-the-table.md).
So the quiet failure is quieter here than where it is first described: there is
no check to pass.

**An amodal mask does not give that footprint back.** The shared arithmetic
takes the asserted pixels out of the mask before it begins, so a completed mask
is measured from the pixels the camera really saw, which is the same evidence
the truncated mask left it, and the place and the width come out the same. What
the completion buys comes earlier than the measurement. The model proposes one
region per glass, so the crescent that was seen is attributed to the glass it
came off instead of being swallowed into the region of the glass in front, and
the box is free to grow to hold the whole shape rather than stopping where the
evidence stops. That is why solution 10 finds more glasses on a crowded table
while the place it gives them there is no better than solution 9's.

**How often a neighbour gets in the way here was measured, and it is not the
normal case.** A spawned layout keeps 150 mm between glasses. At the simulator's
750 mm not one glass in five hundred is hidden by another, even by a single
pixel. At the cell's own 450 mm it is 0.6 per cent of them, and the
worst of those is 4 per cent covered. So solution 10 is built and scored here, because
the case it was built for does occur and complete covering is possible at the
guaranteed gap, but on the layouts the cell really produces the amodal target is
nearly always the visible one and the two solutions answer alike. The difference
only appears on the crowded layouts, which is why `make test-crowded` exists and
why training draws crowded scenes as well as spawned ones: over 99 per cent of
the hidden pixels a run has to learn from come from the crowded half.

A glass cut short is still the ordinary case on an ordinary table, but the
edge of the picture is what does it rather than a neighbour, and a completion
cannot reach that cause: a mask cannot assert a pixel the picture does not have.
[The best any of them could do](#the-best-any-of-them-could-do) measures what
that leaves.

Two limits have to be stated with it. Amodal completion extends the evidence it
is given, so it needs some of the glass to be visible to extend from. A glass
that a taller one covers completely leaves nothing to extend, and no amount of
training changes that.

The second limit is about what a completed mask may then be used for, and it is
where solution 10 can poison its own answer. The place and the width are read
off the depth reading under each pixel the arithmetic is given, and an amodal
mask claims pixels where the camera saw the glass in *front*. Those pixels
back-project onto that nearer glass, so handing the whole silhouette to the
shared arithmetic drags the answer onto the wrong glass. How much it costs was
measured with exact masks and no model at all, over the partly hidden glasses of
the crowded scenes: feeding those pixels in puts the reported place about four
times further from the truth and makes the fitted footprint roughly twice as
wide, and through the whole scorecard it turns a couple of merges into more than
a dozen. **This is the one mistake here that destroys the result while nothing
in the run objects**: the model's own confidence in the mask is untouched, and,
as above, there is no check between the mask and the report to fire, neither on
the width it gives nor on how well the points it used sit together. The
solution's own document prescribes the repair, which is to keep the **observed**
part and the **asserted** part apart and fit on the observed one, and that is
what the code does. Where two reported outlines overlap, the nearer of the two
is what the camera saw there, so the split is read off the answer itself and
needs no truth. What the completion supplies is that split and a glass reported
at all where a truncated mask would have been too small to fit; it supplies no
depth reading, because it has none to supply.

## What comes out

Each run writes its numbers into this folder, and the numbers are made to sit
beside the other two folders' numbers. Before anything can be scored, each mask
has to become a place on the table and a width, because that is what problem 2's
later steps are given. The masks are turned into those two numbers by arithmetic
over the depth readings of the pixels inside each mask, which is the same
arithmetic the other folders use, so no part of the comparison depends on which
approach drew the mask.

`make test SOLUTION=sam` writes `results-sam.json`, and the other two write
`results-maskrcnn.json` and `results-amodal.json`; `make test-crowded` writes
the same names with `-crowded` on the end, and `make floor` writes
`results-floor.json` and `results-floor-crowded.json`. All eight files are in
the folder, so the numbers can be read without running anything, and a run of
your own replaces them. The scoring itself is `../problem-2-sim/scoring.py`,
shared by every approach to this problem: it counts the glasses found, missed,
merged and split, and measures how far each found place is from the true place.
A found glass is matched to a true one by the glass identities under its pixels,
so the scorecard needs one picture holding every glass with none hiding another,
which is what the 750 mm overhead view is. That picture is used for scoring and
is never handed to a solution; it is also the picture the other two folders are
scored in, so the find counts here mean the same as theirs.
`../problem-2-results` explains what each of those numbers means and why a merge
is the dangerous one.

That gives three comparisons. The first is between these three solutions, and
it is the cleanest, because they read the same pictures and differ only in how
the masks are made, so a difference in the scorecard belongs to that
difference and to nothing else. The second is against
`../problem-2-programmed`, which is the same job done with written rules and no
training at all. The third is against `../problem-2-learned`, whose small
models are trained from nothing on these same simulator pictures and so carry
no domain gap. That last comparison is the one to read first, because it is
what says whether borrowing large weights fitted on photographs beats fitting
small weights on the pictures the cell actually produces.

What the six solution files hold is this, from twenty held-out scenes of each
kind on one machine. "Handed over" is the proposals a solution would neither
keep nor drop, counted because a glass reported as doubtful is a result and not
a failure: problem 3 can be asked about it, where a glass reported wrongly is
nobody's to question.

| Solution | Layouts | Glasses found | Missed / merged / split / false | Position error, median · worst | Handed over |
|---|---|---|---|---|---|
| 8, SAM and a keeper | spawned | 74 of 100 | 26 / 0 / 0 / 0 | 2.7 · 43.1 mm | 221 |
| | crowded | 75 of 101 | 26 / 0 / 0 / 0 | 0.8 · 31.1 mm | 215 |
| 9, fine-tuned Mask R-CNN | spawned | 100 of 100 | 0 / 0 / 0 / 0 | 6.8 · 46.5 mm | 31 |
| | crowded | 75 of 101 | 26 / 2 / 1 / 0 | 0.5 · 86.2 mm | 84 |
| 10, amodal masks | spawned | 100 of 100 | 0 / 0 / 0 / 0 | 6.8 · 46.5 mm | 209 |
| | crowded | 84 of 101 | 17 / 2 / 1 / 0 | 1.2 · 62.9 mm | 479 |

Read along the rows first. Solution 8 is the careful one: it misses about a
quarter of the glasses, invents none, and hands over what its keeper cannot
settle instead of guessing at it. The two fine-tuned solutions find every glass
on an ordinary table and cannot be told apart there, to the glass and to the
tenth of a millimetre. On the crowded layouts they come apart, and solution 10
finds about one glass in ten more of them than solution 9 does, which is the
case it was built for and the only case it was built for. What it gains there is
the finding and not the placing, as the two medians in those rows show, which is
exactly what a completion buys. What none of these rows says on its own is how
much better any of them could have done, and that is the next section.

## The best any of them could do

Those rows are easier to read beside the same table with no model in it at all.
The renderer knows exactly which pixels each glass covers, so its own masks can
be put through the arithmetic above, the same survey of three stations and the
same scorecard, with nothing fitted and nothing predicted anywhere between the
picture and the number. `make floor` is that run, and what comes out is the
floor every number in the table above sits on: no segmenter reading these
pictures can draw a better mask than the one the renderer drew the picture from.

A mask can be exact in more than one sense, so the run reports three. The first
is the pixels the camera can see of a glass, which is what solution 9 is trained
to draw. The second is a glass's whole outline with the pixels it only asserts
named, so that their depth readings stay out of the arithmetic, which is what
solution 10 is trained to draw and how solution 10 uses it. The third is that
same whole outline with nothing named, which is no sense of exact at all but the
mistake described above, run here so that its cost is a measurement rather than
a warning.

| Masks | Layouts | Glasses found | Missed / merged / split / false | Position error, median · worst |
|---|---|---|---|---|
| what the camera sees | spawned | 100 of 100 | 0 / 0 / 0 / 0 | 6.3 · 46.5 mm |
| | crowded | 83 of 101 | 18 / 1 / 1 / 0 | 0.4 · 50.0 mm |
| whole outlines, asserted pixels named | spawned | 100 of 100 | 0 / 0 / 0 / 0 | 6.3 · 46.5 mm |
| | crowded | 83 of 101 | 18 / 1 / 1 / 0 | 0.4 · 50.0 mm |
| whole outlines, nothing named | spawned | 100 of 100 | 0 / 0 / 0 / 0 | 6.3 · 46.5 mm |
| | crowded | 69 of 101 | 32 / 14 / 2 / 0 | 0.1 · 72.7 mm |

The same twenty held-out scenes of each kind, the same three stations and the
same scorecard as the solutions, and nothing handed over in any row, because an
exact mask is either large enough to fit a footprint to or it is not.

**On the layouts the cell's own placement rule produces, the two fine-tuned
solutions are already at the floor.** Exact masks find every glass, and so do
they. The place exact masks give is better by half a millimetre on the median,
and the glass placed furthest from where it stands is exactly as far out either
way. So what is left of that error on an ordinary table belongs to the
arithmetic and to the geometry of looking from the top, and not to the model.
The cause is the edge of the picture: a footprint cut short by the frame
back-projects to an arc rather than to a whole disc, and an arc fits a circle
that is too small and in the wrong place.
[Cluster on the table](../docs/problem-2/solutions/programmed/02-cluster-on-the-table.md)
measures how often the frame does that, and the answer is that it is the
ordinary case rather than an unlucky one. The crowded rows are the same fact
from the other side: those glasses stand near the point below a camera, where
there is neither splay nor a cut, and the place comes out more than ten times
closer than on an ordinary table.

**On the crowded layouts exact masks find about four glasses in five, and
solution 10 finds as many of them.** A glass that no station sees a single pixel
of has nothing to segment, so that shortfall is a fact about the input rather
than about any model: exact masks cannot find what is in no picture either.
Solution 10 comes within a glass of the floor there, so what it misses is mostly
not waiting on a better model, while solution 9, trained on the visible masks
alone, is well below it. That gap is the whole case for training against whole
outlines, and it is a case about crowded tables only.

**Completion buys nothing where nothing stands in front of anything.** The
spawned rows are the same in all three senses of exact, to the glass and to the
tenth of a millimetre, and even the mistake costs nothing there, because on
these layouts a whole outline has almost nothing to assert. That is the measured
reason solutions 9 and 10 cannot be told apart on an ordinary table.

One place the table can mislead is the last row's median, which looks like the
best figure on the page. It is better only because the glasses the mistake ruins
have stopped being counted as found at all: fourteen reports swallow two glasses
at once, which is fourteen fewer glasses found than with the asserted pixels
named, and a merge is the dangerous answer rather than a modest one. Taken one
glass at a time, which `results-floor-crowded.json` also reports, feeding the
asserted pixels in puts the place about four times further out and makes the
footprint roughly twice as wide.

## Which glasses the borrowed model outlines

The floor says how much of each solution's error belongs to its model rather
than to the view. For solution 8 there is one more measurement of that kind, and
it divides the model's share by kind of glass. `make by-kind` runs it, and it
leaves out everything the solution adds: no keeper, no survey, no scorecard. For
every glass in a few held-out scenes of each kind it finds the single proposal
that matches that glass best, and reports the match two ways, because the two
answer different questions. **Overlap** is the shared pixels against the pixels
either the proposal or the glass holds, so it falls when a proposal spills past
a glass as well as when it stops short of one. **Coverage** is the share of the
glass's own pixels the proposal holds, which is the question "how much of this
glass was proposed at all". A glass counts once per station that sees enough of
it.

| Kind | Glasses | Overlap, median | Coverage, median | Proposed at all | Whole enough to measure |
|---|---|---|---|---|---|
| straight | 33 | 0.98 | 0.98 | 100% | 100% |
| tapered | 30 | 0.99 | 0.99 | 100% | 97% |
| short stemmed | 33 | 0.83 | 0.86 | 100% | 39% |
| stemmed | 26 | 0.74 | 0.79 | 88% | 19% |

"Proposed at all" counts the glasses whose best proposal holds at least half of
them, which is the loosest reading anybody would accept, and "whole enough to
measure" those whose best proposal holds at least nine tenths.

**The borrowed model's weakness ranks the kinds, and the ranking follows the
shape.** A glass whose outline is one wall running from the table to the rim is
a strong boundary in a picture shaded from depth, and the straight and the
tapered kinds come back outlined almost exactly, whole enough to measure nearly
every time. A wide bowl standing on a thin stem is not that: the short stemmed
kind loses part of its outline more often than not, and the stemmed kind is the
worst of the four, where the best proposal typically holds about four fifths of
the glass, barely one in five is whole enough to measure, and a minority are cut
so badly that nothing proposed holds even half the glass.

This is the measured reason solution 8 misses the glasses it misses, and the
reason its misses are not spread evenly over the table. Nothing in the solution
can move it either, because the model that draws the outlines is used exactly as
it was downloaded and only the keeper is fitted: a keeper can choose among the
proposals it is handed, and a glass no proposal holds is not among them. It is
also the clearest thing on this page about the domain gap, because the same
model outlines the easy kinds almost perfectly in the same pictures, so what
fails is the shape against these pictures rather than the pictures alone.

## Layout

These are the files the folder holds and what each one is for.

- `Makefile` — the commands above.
- `pixi.toml`, `pixi.lock` — the environment: Python, PyTorch and the model
  libraries. It is its own environment, apart from the ROS one.
- `ruff.toml` — the style rules, as in the other folders.
- `weights.py` — fetches SAM's and Mask R-CNN's starting weights into the
  cache, and finds them there again afterwards.
- `device.py` — chooses MPS when it is available and the CPU otherwise.
- `pictures.py` — shades a depth reading into a grey picture and repeats it
  across three channels.
- `data.py` — owns the camera, and builds the training and held-out examples
  from `../problem-2-sim`: the three survey pictures per scene, and either the
  visible masks or the whole-glass masks. Also the crowded layouts, and the
  limits on a kind of glass that the cell is told.
- `sam_keeper.py` — solution 8: the grid of prompts, SAM's proposals, and the
  small keeper that decides which of them are glasses.
- `segmenter.py` — solutions 9 and 10: the Mask R-CNN model, built the same
  way for both.
- `masks_to_glasses.py` — turns instance masks and the depth reading into each
  glass's place on the table and its width, using only the pixels the camera saw
  the glass at. That is the rule solution 10 stands or falls by, so it is
  written down here, in the module that would be the one to break it.
- `train.py` — behind `make train`: fits what the chosen solution fits and
  saves it. Its table is the only place in the folder that knows the three
  solutions apart.
- `run.py` — behind `make test`: asks the solution about each station's picture,
  brings the three answers together, scores them and writes
  `results-<solution>.json`.
- `floor.py` — behind `make floor`: the renderer's own masks through the same
  survey and the same scorecard, in the three senses a mask can be exact, and no
  model anywhere. It is the only file here allowed to look the scene behind a
  picture up.
- `proposals_by_kind.py` — behind `make by-kind`: the borrowed model's
  proposals, with nothing after them, so that what it outlines well can be read
  kind by kind.
- `test_pretrained.py` — behind `make check`: the quick checks, which need no
  weights.
- `results-*.json` — what the runs above wrote: one file per solution per kind
  of layout, two from `make floor`, and one from `make by-kind`.
- `weights/` — the fetched weights and the fitted ones. Not committed.

All three solutions are reached through the same three calls, and nothing outside
`train.py`'s table knows which of them is running:

```
fit(examples, *, amodal, save)   # fit what this solution fits, and save it
load(save)                       # the fitted thing, ready to be asked
Finder.find(picture, kind)       # the glasses in one picture, and the doubts
```

A solution is handed a picture and the kind of glass on the table, which the
problem statement says the cell is told, and never the list of glasses behind the
picture. That is what stops a solution reaching the truth at test time. `find`
hands back one `Found` per glass and one short reason per proposal it could
neither keep nor drop, which the scorecard counts as handed over.
