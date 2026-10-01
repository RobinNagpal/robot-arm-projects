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
and how the three are scored against each other and against the two folders that
already do the same job.

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
three; training and testing are done one solution at a time.

```
make setup                          # once: install the environment, fetch weights
make train SOLUTION=sam             # sam | maskrcnn | amodal
make test  SOLUTION=sam
make test-crowded SOLUTION=sam      # the same, on layouts where one glass hides another
```

`SOLUTION` says which of the three to work on. `sam` is solution 8,
`maskrcnn` is solution 9 and `amodal` is solution 10. Both `make train` and
`make test` need it; `make setup` does not, because the environment and the
downloaded weights are the same whichever solution you go on to run.

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

How many scenes each command uses has a default per solution rather than one
default for all three, because the work per scene is not the same: running SAM
over a picture costs several seconds and one training step costs under two. Pass
`SCENES=n` to `make train` or `TEST_SCENES=n` to `make test` to change it.

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

What a truncated mask costs is real. A mask that stops where the hidden part
begins gives a glass whose place on the table is wrong and whose width is too
small, and the damage is that both look reasonable: the width is one a glass of
this kind could have, and the outline fits what was seen with little error, so
the check meant to catch a bad find passes it instead. An amodal mask gives the
whole footprint back.

**How often that happens here was measured, and it is not the normal case.** The
solution's document says partly hidden glasses are what this scene is like, and
for this cell that is false. A spawned layout keeps 150 mm between glasses. At
the simulator's 750 mm not one glass in five hundred is hidden by another, even
by a single pixel. At the cell's own 450 mm it is 0.6 per cent of them, and the
worst of those is 4 per cent covered. So solution 10 is built and scored here, because
the case it was built for does occur and complete covering is possible at the
guaranteed gap, but on the layouts the cell really produces the amodal target is
nearly always the visible one and the two solutions answer alike. The difference
only appears on the crowded layouts, which is why `make test-crowded` exists and
why training draws crowded scenes as well as spawned ones: over 99 per cent of
the hidden pixels a run has to learn from come from the crowded half.

Two limits have to be stated with it. Amodal completion extends the evidence it
is given, so it needs some of the glass to be visible to extend from. A glass
that a taller one covers completely leaves nothing to extend, and no amount of
training changes that.

The second limit is about what a completed mask may then be used for, and it is
where solution 10 can poison its own answer. The place and the width are read off
the depth reading under each pixel of the mask, and an amodal mask claims pixels
where the camera saw the glass in *front*. Those pixels back-project onto that
nearer glass, so handing the whole silhouette to the shared arithmetic drags the
answer onto the wrong glass: with exact masks and no model at all, the whole
silhouette places a hidden glass 45 mm out where its visible pixels place it
11 mm out. The solution's own document prescribes the repair, which is to keep
the **observed** part and the **asserted** part apart and fit on the observed
one, and that is what the code does. Where two reported outlines overlap the
nearer of the two is what the camera saw there, so the split is read off the
answer itself and needs no truth. What the completion supplies is that split and a
glass reported at all where a truncated mask would have been too small to fit; it
supplies no depth reading, because it has none to supply.

## What comes out

Each run writes its numbers into this folder, and the numbers are made to sit
beside the other two folders' numbers. Before anything can be scored, each mask
has to become a place on the table and a width, because that is what problem 2's
later steps are given. The masks are turned into those two numbers by arithmetic
over the depth readings of the pixels inside each mask, which is the same
arithmetic the other folders use, so no part of the comparison depends on which
approach drew the mask.

`make test SOLUTION=sam` writes `results-sam.json`, and the other two write
`results-maskrcnn.json` and `results-amodal.json`; `make test-crowded` writes the
same names with `-crowded` on the end. The scoring itself is
`../problem-2-sim/scoring.py`, shared by every approach to this problem: it
counts the glasses found, missed, merged and split, and measures how far each
found place is from the true place. A found glass is matched to a true one by the
glass identities under its pixels, so the scorecard needs one picture holding
every glass with none hiding another, which is what the 750 mm overhead view is.
That picture is used for scoring and is never handed to a solution; it is also
the picture the other two folders are scored in, so the find counts here mean the
same as theirs. `../problem-2-results` explains what each of those numbers means
and why a merge is the dangerous one.

That gives three comparisons. The first is between these three solutions, and
it is the cleanest, because they read the same pictures and differ only in how
the masks are made, so a difference in the scorecard belongs to that
difference and to nothing else. The second is against
`../problem-2-programmed`, which is the same job done with written rules and no
training at all. The third is against `../problem-2-learned`, whose small
models are trained from nothing on these same simulator pictures and so carry
no domain gap. That last comparison is the one to read first, because it is
what says whether borrowing large weights fitted on photographs beats fitting
small weights on the pictures the cell actually produces. This page states no
results of its own; the numbers come from the files a run on your machine
writes.

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
  glass's place on the table and its width.
- `train.py` — behind `make train`: fits what the chosen solution fits and
  saves it. Its table is the only place in the folder that knows the three
  solutions apart.
- `run.py` — behind `make test`: asks the solution about each station's picture,
  brings the three answers together, scores them and writes
  `results-<solution>.json`.
- `test_pretrained.py` — behind `make check`: the quick checks, which need no
  weights.
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
