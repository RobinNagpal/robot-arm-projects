# Solution 10 — amodal masks for the hidden part

*Learned, as the decider. The same instance segmenter as solution 9, in the same
place in the pipeline, with one change: each mask is trained against the whole
silhouette of its glass rather than against only the pixels the camera can see
of it.*

> **The cell is described once, in [the cell](../../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to make a learned instance segmenter report the part
of a glass that nothing in the picture shows. It is the smallest of the three
solutions built on a large pre-trained model: the model, the weights it starts
from, the pictures it trains on and the code that consumes its answers are all
the same as in [a fine-tuned instance
segmenter](09-a-fine-tuned-instance-segmenter.md), and what differs is only the
answer each mask is scored against during training.

That small change is worth a document because of a failure the rest of the
project cannot detect. When something stands in front of a glass, or when
the edge of the picture falls across it, the mask of that glass stops early, and
the footprint worked out from a mask that stops early is wrong in the one way
that gets past every check this project has: it looks like the footprint of a
smaller glass standing somewhere slightly different. A mask that includes the
missing part hands the glass on as a glass of its own, with the part nobody saw
marked as asserted rather than measured.

By the end you will understand what the words modal and amodal mean, why the
label needed to train the amodal version costs nothing in a simulator when it is
expensive and arguable on real photographs, what changes in the model and what
does not, why a mask claiming pixels nobody saw is a prediction rather than a
measurement and how far it should then be trusted, how to tell whether the
completion works when the usual measure of a segmenter gives the wrong answer
here, what running it shows and the one way of using the completion that ruins
the answer while every check still passes, what stops such a model from
inventing glass where there is none, and why the whole idea stops dead at the
one case the problem says to watch hardest.

## The problem this solves

Four to six glasses stand on the table. They are all of one kind, the kind is
known, and they are solid, so the depth camera sees them. The job is to say
which pixels belong to which glass, to give each glass a position on the table,
and to give each a rough footprint width. Nothing is picked up and no shape is
measured here.

To see the failure this solution repairs, one step further down the pipeline has
to be described, because that is where the damage appears rather than in the
mask itself.

### What a mask is turned into

A **mask** is a picture the same size as the photograph in which every pixel is
just yes or no, where yes means "this is glass". An **instance** mask is one
mask per object, so a picture holding several glasses comes back as several
masks rather than as one region covering all of them.

What happens to each instance mask is the arithmetic [cluster on the
table](../programmed/02-cluster-on-the-table.md) already uses. Every pixel of
the mask has a depth reading, so it becomes a point in the room, and dropping
the height turns it into a point on the table. A glass seen from the top is a
circle, so the points of one glass should fill a disc, and fitting a circle to
that disc returns a **centre**, which is where the glass stands, a **width**,
which is how wide its footprint is, and a **fit error**, which is how far the
points sit from the fitted circle on average.

Those three numbers are then checked, and that check is the safety net the whole
project rests on. The kind on the table is known and a kind has a range of
footprint widths it allows, so a fitted width outside that range means the thing
found is not one glass of this kind, and it is reported as doubtful rather than
acted on. A large fit error means the points are not disc-shaped, which again
means the group is not one glass. The check is arithmetic rather than judgement,
and it is what makes a learned component tolerable anywhere in this project:
**the model proposes and the geometry disposes.**

Two of those three numbers are what the code beside this document computes, and
the third is not. That code takes the axis from the points at the top of the
glass and the width from how far the cloud spreads around that axis, so a centre
and a width come out of it and no fit error does. The fit error belongs to the
circle fit [cluster on the
table](../programmed/02-cluster-on-the-table.md) describes, so every mention of
one from here on is a number that solution has and a run of this one does not.

### A mask cut short passes the check

Now put something in front of a glass. The camera sees the near object's surface
where the far glass would otherwise have been, so the far glass's mask loses
every pixel behind that surface. What is left is not a smaller copy of the
glass. It is a crescent, cut along one side, with every remaining pixel lying
towards the side the camera could still see.

![A mask cut short by an object in front of it, the crescent of points it leaves
on the table, and the small displaced circle fitted to that crescent shown
against the true
footprint](../../../../images/problem-2/10-the-truncated-footprint.png)

Follow what the circle fit does with that crescent, because each of the three
numbers goes wrong differently and only one of them goes wrong loudly.

**The centre moves.** A fit uses every point it is given and nothing else, so
the centre it returns sits where the points it was given are arranged around.
The surviving points are all on one side of the true centre, so the fitted
centre is pulled towards that side, and the more of the glass is hidden the
further it is pulled.

**The width shrinks.** The crescent spans less of the circle than the whole disc
does, so the circle that best explains it is smaller than the true one. The
fitted width comes out under the truth, and again by more the more of the glass
is hidden.

**And the fit error stays small.** This is what makes the failure dangerous. The
surviving points have not become noisy or scattered; they are a clean patch of a
clean disc, and a clean patch of a disc is well explained by a smaller disc. So
the number whose job is to say "these points are not a glass" says nothing at
all, because as far as it can tell they are a perfectly good glass.

Put the three together and the outcome is a **plausible wrong answer**. The
width is inside the range the kind allows, because a kind whose range runs from
a small tapered glass to a large one has room for the shrunken figure — a short
measurement does not look like an error, it looks like a shorter glass. The fit
error is small. Both checks pass. So the pipeline reports a glass with a
believable width at a position where no glass is standing, and nothing anywhere
in the run contradicts it. In a run with no fit error in it, which is the run
beside this document, the failure is quieter still, because the one number that
might have objected is never computed at all.

Compare that with the failure these checks were designed for. When two glasses
merge into one region the fitted width comes out far wider than any glass of
this kind can be, the check fires, and the group is reported as doubtful. That
failure is loud. **This one is quiet**, and a quiet failure is worse in a cell
where the next step is an arm moving towards where the answer said the glass
was.

### How a glass comes to be partly hidden

A mask comes back cut short for two quite different reasons. They appear on
different tables and only one of them needs a crowded one, so they are worth
separating before either is answered.

**One is a neighbour standing in the way.** Two facts about the kind on the
table are what make that possible at all, and they are worth setting out,
because between them they decide which tables it appears on.

The first is **splay**. Seen from the top, a glass's outline is thrown outwards
away from the point directly below the camera, and the taller the glass the
further out it goes. So a tall glass's outline covers ground in the picture well
beyond where the glass actually stands, and whatever stands beyond it along that
direction is behind that outline.

The second is the **range of sizes inside one kind**. This kind ranges the
widest of the four the cell handles, with the tall end more than twice the
height of the short end, so a tall glass and a short glass of the same kind are
splayed by very different amounts. It is that difference which lets one outline
sweep across the other.

Put the two together and a tall glass standing between the camera and a short
one takes a bite out of the short one, and it does so at the gap the cell
guarantees rather than needing the glasses closer than the cell allows. Nothing
has to be contrived. But the arrangement has to line up for it: the two glasses
have to lie along one line running out from the point below the camera, close
together along that line, and differ a great deal in height. Swing the pair
across that line instead, or space it further out, or make both glasses the same
height, and the bite goes.

**The other is the edge of the picture**, and no neighbour takes part in it. The
survey does not photograph the zone from one place. It works from three stations
spread along the zone, so each station's frame is offset from the zone and part
of the zone lies at or past that frame's edge. Splay then works exactly as it
does against a neighbour — the further a glass stands from the point below the
camera, the further out its rim is thrown — so a glass standing well inside the
zone can still have its rim thrown over the edge of the frame. What the station
returns is the near part of the footprint and nothing of the rest.

**Downstream the two are one failure.** Whichever of them cut the mask, what is
left is a crescent of a disc, and every word of [a mask cut short passes the
check](#a-mask-cut-short-passes-the-check) applies to it unchanged: the fitted
circle is too small and displaced, the width is one the kind allows, and the fit
error is the fit error of a clean patch of a clean disc.

### How often each happens, and why it matters anyway

Both are measured with the project's own renderer, at the cell's own survey
height and from the three stations the cell computes, and they come out very
differently.

**A neighbour in the way is uncommon rather than the normal case.** Across
spawned scenes of this kind, only a small share of glasses lose any pixels at
all to a neighbour, and a smaller share again lose every pixel at one station,
though none loses them at more than one. Complete covering is **possible at the
guaranteed gap between centres**, and an arrangement that produces it can be
written down, but the cell's placement rule puts glasses where it rarely
happens.

**The edge of the picture is the ordinary case.** Nearly every glass is cut by
it at one station or another, most glasses have no station at all that returns a
whole footprint, and roughly one in six have exactly one. So the crescent this
document is about is not a rare arrangement waiting on a crowded table. It is
the usual shape of what one station hands the arithmetic, and [cluster on the
table](../programmed/02-cluster-on-the-table.md#asking-the-stations-to-agree)
records the same measurement, where it is the reason the stations are asked to
agree.

That is worth saying plainly, because it changes what this solution is worth.
The quiet failure described above — a footprint too small and displaced, with a
width the kind allows and a fit error a genuine glass would give — is not a rare
failure kept on the books for safety's sake. It is what one picture ordinarily
returns. So the truncated footprint is worth taking seriously on two counts
rather than one: the failure is **ordinary**, and **nothing in the run says when
it happens**, because both checks pass and a position where no glass stands is
acted on. Which of its two causes a completion reaches is the next question.

**Completion reaches the first cause and not the second, and that is measured.**
Completing behind a near glass and completing past the edge of the picture are
different problems. The first asserts pixels inside the frame, where a mask has
room to hold them; the second would have to assert glass where the mask has no
pixels at all, and a mask cannot hold a pixel the picture does not have. So the
whole silhouette of a glass the frame cut is the visible mask of that glass,
because a silhouette rendered from that same station stops at that same edge,
and a run bears it out: on the layouts the cell spawns for itself this solution
and [solution 9](09-a-fine-tuned-instance-segmenter.md) score alike, and the
renderer's own exact silhouettes, handed to the shared arithmetic with no model
anywhere in the chain, score no better there than its exact visible masks. The
geometric check survives either way, because the ring outside the frame is
already part of the blind region [cluster on the
table](../programmed/02-cluster-on-the-table.md) computes, and what the cell
does about the frame edge is to survey from three stations and ask them to
agree.

**Both causes appear in the harness**, which is what lets either of them be
measured rather than argued.
[`problem-2-sim`](../../../../problem-2-sim/README.md) renders its own top view
from higher than the cell's survey height and takes one picture rather than
three: the higher the camera the less splay throws each outline, and one frame
from that height holds the whole zone with room around it. The code for this
solution does not use that view. It stands the camera at the cell's own survey
height and takes the three pictures a survey there needs, so the frame edge cuts
masks in every run of it. The neighbour needs more than the height, because the
cell's placement rule spaces glasses too well for it, so the harness builds
**crowded layouts** on purpose and the test command asks for them by name.
Neither cause has to be argued from geometry rather than watched.

A neighbour in the way needs the **crowded layout**: glasses lining up along one
line out from the point below the camera, close together along it, with the tall
ones in front of the short ones. The frame edge needs nothing of the sort, only
a glass near the edge of a station's picture, which is where most glasses are at
some station. The frame edge is also the cause a whole silhouette cannot
describe, so the amodal target and the visible one are the same mask wherever
the frame edge alone did the cutting, and they come apart only where a neighbour
is in the way. That is why this solution is scored on the crowded layouts as
well as on the spawned ones, and the two scorecards are read apart rather than
averaged into one number.

## The main idea

The idea follows from the diagnosis and it is one sentence long: **ask the model
for the whole silhouette of each glass, not just the visible part of it.**

If the mask covers the whole silhouette, the glass is a region of its own, with
its outline where the glass's outline really runs. The region is drawn round the
whole shape rather than round the sliver the camera saw, so the sliver is
attributed to the glass it came off instead of being swallowed into the region
of the glass in front, and a sliver too thin to be worth proposing on its own is
proposed as part of something whole. Nothing downstream changes, because what
comes out is still a mask per glass.

The price is as simple, and it decides what the completion may be used for. Some
pixels in such a mask are pixels where the camera saw another object's surface,
so the model is asserting that glass continues underneath what is in front of
it, and an assertion is not an observation. Worse, the depth reading at such a
pixel is the other object's reading, so it says how far away that object is and
nothing about this glass. **The whole silhouette says how far a glass reaches,
never how far away it is**, and everything that consumes it has to know which of
its pixels are which.

The rest of this document works through that trade: the two words the idea needs
and the everyday version that makes them intuitive, why the training label is
free here, what changes in the model and what does not, what follows from part
of the mask being asserted, how to measure whether the completion works and what
running it shows, what bounds the risk of the model inventing glass, and the
case none of it reaches.

## What modal and amodal mean

The two words come from psychology rather than from computer vision, and the
psychological meaning is the one that makes them easy to remember.

A **mode** here means a sense: seeing, hearing, touching. Something is
**modally** present when it arrives through a sense, so the part of a glass
whose own surface the camera sees is modally present in the picture. Something
is **amodally** present when the perceiver has it without any sense delivering
it, and the part of a glass hidden behind another object is amodally present:
you know it is there, you know roughly where its edge runs, and no light from it
reached the camera.

Applied to masks, that gives the pair of terms used from here on. A **modal
mask** covers the pixels where the object's own surface is what the camera sees.
An **amodal mask** covers the pixels the object would occupy if nothing stood in
front of it. The amodal mask always contains the modal one, and the difference
between them is the **hidden part**.

![A glass with another in front of it shown three ways: the modal mask covering
only visible pixels, the amodal mask covering the whole silhouette, and the
hidden part that is the difference between
them](../../../../images/problem-2/10-modal-against-amodal.png)

The everyday version is worth stating, because it shows that the amodal answer
is the normal one and the modal answer is the odd one. Look at a cat sitting
behind a garden railing. What you see, strictly, is a set of vertical strips of
cat separated by bars. What you report is **one cat**. Nobody has to be taught
this, and the alternative report — several slices of cat, of various widths — is
so strange that it takes an effort to produce. A modal segmenter is a system
that reports the slices, which is exactly what it was asked for and exactly what
the picture contains; it becomes a problem only when the next step assumes a
whole object, and here the next step is a circle fit, which assumes precisely
that.

One more property matters for training. **On an unobstructed glass the modal and
amodal masks are the same**, because there is no hidden part to complete. So
training against amodal targets costs nothing on the easy scenes, and there is a
free test available later: on a glass with a clear view, a model that adds
anything at all is adding something wrong.

## Why the label costs nothing here

Everything above is standard, and so is the reason amodal segmentation is not
simply the default everywhere: on real photographs the label is expensive and
arguable. An annotator looking at the cat behind the railing has to draw the
cat's boundary where the bars cross it, which means drawing a line through a
place nobody can see, and two careful people will draw it differently with no
way to check who was right. So amodal datasets are smaller than modal ones,
their labels carry a disagreement that cannot be removed, and a model trained on
them is fitted partly to the annotators' guesses.

**None of that applies here, and the reason is the simulator.** The simulator
holds the scene, so it can be asked to render it more than once. Render it with
everything in place and you have the picture the model trains on. Render it
again with all the glasses but one taken away, from the same camera pose, and
the identity map of that second render marks every pixel that glass would occupy
with nothing in front of it. That is the amodal mask exactly, with no guessing
in it.

![The full scene render beside one render per glass with the other glasses
removed, and the exact masks each one yields, including the hidden part obtained
by subtraction](../../../../images/problem-2/10-labels-for-free.png)

Three things follow, and each is worth having. The label is **exact rather than
agreed**, because the boundary of the hidden part is where the simulator's
geometry puts it and would be in the same place if the scene were rendered again
tomorrow. The **hidden part is available on its own**, by subtracting the modal
mask from the amodal one, which separates the part of the answer that was easy
from the part that was the point and is what makes the measurements below
possible. And the **visible fraction** of every glass in every scene is known,
because dividing the size of the modal mask by the size of the amodal one says
how much of that glass the camera could see.

## What changes in the model, and what does not

With the label in hand the change is easy to state, because the architecture is
unchanged. It is the same instance segmenter as [solution
9](09-a-fine-tuned-instance-segmenter.md) — torchvision's
`maskrcnn_resnet50_fpn_v2`, starting from the same weights fitted to a large
collection of everyday photographs, fine-tuned on this cell's pictures with one
class, "glass". Nothing is added to it, nothing is taken away, and no layer
changes shape.

What changes is **what the mask branch is scored against**. Where solution 9
compares each predicted mask with the pixels the camera can see of that glass,
this one compares it with the whole silhouette. The loss is the same loss, the
optimiser is the same optimiser, and the pictures going in are the same
pictures.

![The same architecture drawn twice with the same weights and the same input,
differing only in the target the mask branch is scored against: visible pixels
on one side, whole silhouette on the
other](../../../../images/problem-2/10-only-the-target-changes.png)

That is the lesson [a network trained from
scratch](06-a-network-trained-from-scratch.md) draws from its two heads, and it
is worth having in the general form, because it is one of the most useful things
to know about this kind of model. **One network answers different questions by
changing its last layer and its target.** The body learns to describe what is in
the picture, and the question being asked lives almost entirely in what the
final layer produces and what that output is compared with. Here even the last
layer keeps its shape, so the question lives entirely in the target.

### The box has to grow with the mask

One consequence of the change is not optional, and it follows from how the model
works. It works in two stages: it first proposes rectangles that might contain
an object, and then, for each rectangle it keeps, predicts a mask **inside that
rectangle**. The mask is produced on a small grid covering the rectangle and
stretched to its size, so it physically cannot extend past the rectangle's edge.

Now notice what the amodal target asks for. The whole silhouette of a partly
hidden glass sticks out beyond the visible part of it, so the smallest rectangle
containing the amodal mask is larger than the smallest rectangle containing the
modal one. If the rectangles are still trained against the visible extent, every
completion is clipped at the rectangle's edge and the model is being asked for
something it has no room to express.

So the box target has to become amodal too, and the rectangle each glass is
trained to be found in is the one containing its whole silhouette, which the
same second render supplies. That has a further implication worth being plain
about: the proposal stage is now learning to propose a rectangle **larger than
the evidence in the picture**, which is harder than proposing one round a
visible blob.

### "Only the target changes" is true of the code, not of the task

The code change is small and the task change is not. Solution 9's mask branch
traces a boundary that is present in the picture, which is a question about
where the evidence stops. This one traces part of a boundary that is not in the
picture, which is a question about what a glass of this kind looks like and
about which of the two objects at a boundary is in front. The second question
needs the model to have learned the shape of the kind, and it needs the
near-and-far relation to come out right, because completing the wrong one of the
two objects produces a mask extending over a glass that is actually nearer the
camera.

So the same architecture may need more training, or more capacity, to do this
job as well as it does the modal one. Whether it has enough of either is **not
known**, and this document will not assert it. It is something to measure, and
the honest expectation is that the mask score over the hidden part will be
clearly worse than the score over the visible part.

## A mask that is partly a prediction

An amodal mask claims pixels whose evidence is some other object's surface. The
camera looked at those pixels and the near glass came back, so for every pixel
of the hidden part the model is not reporting what it saw but what it believes
is behind what it saw. **A footprint fitted to such a mask as it stands is
therefore a prediction rather than a measurement**, and how much of one it is
varies from glass to glass within the same picture. The rest of this section is
about how not to fit one that way, and about what the completion is worth once
the two kinds of pixel are kept apart.

![One reported answer split into its observed part and its asserted part, with
the fit error computed over the observed part only and the visible fraction
carried alongside as a
confidence](../../../../images/problem-2/10-prediction-not-measurement.png)

### Report the two parts separately

The model should not hand on one silhouette with the join hidden. It should hand
on the observed part and the asserted part as two things, because each consumer
downstream has its own tolerance for the second and none of them can apply that
tolerance once the two have been merged. This costs nothing: the modal mask is
predictable from the same features by the same kind of branch, and even without
a second branch the observed part is recoverable, because the depth reading at a
pixel says whether the surface there is at the far glass's distance or at the
near object's.

The arithmetic is the first consumer of that split and the strictest. The
asserted pixels are named and left out of it, so the place and the width come
from the pixels the camera saw and from nothing else, and nothing is inferred in
their place: what an asserted pixel would be worth is a question about geometry,
and a guess at it here would be arithmetic nobody asked for. Which pixels are
asserted is read off the answer itself rather than off any truth, because where
two reported outlines overlap both glasses lie along those rays and the camera
saw the nearer of them.

### Feeding the asserted pixels in is the mistake that passes every check

Leaving them out has to be done on purpose, because a silhouette arrives as one
mask and the arithmetic will take any mask it is given. An asserted pixel's
depth reading belongs to whatever stood in front of the glass, so the point it
gives sits on that other object, somewhere between the camera and the glass
being reported, and a patch of such points drags the answer across the gap
between the two. That makes it the one implementation mistake worth stating on
its own.

What that costs is measured, with the renderer's own exact masks and no model
anywhere in the chain, over the partly hidden glasses of the crowded layouts.
Naming the asserted pixels and leaving them out places a glass close to where it
stands. Feeding them in instead puts the place about four times further out and
makes the fitted footprint roughly twice as wide as it should be. Through the
whole scorecard it multiplies the number of pairs merged into one report by more
than ten.

Nothing complains while it happens. The mask looks like a better mask, the
footprint stays round, and the width stays inside the range the kind allows, so
what comes out is a plausible wrong answer of exactly the sort the first half of
this document is about, reached by the repair rather than by the failure the
repair is for.

### What the completion buys is attribution rather than measurement

Put the split and the exclusion together and the value of the whole silhouette
sits where a reader does not first look for it. The asserted pixels are left
out, so they contribute nothing to the place and nothing to the width: the
measurement is the one the observed pixels alone would have given, and the
completion supplies no measurement at all, because it has no reading to supply.
What it supplies comes earlier than the measurement and is worth more. The model
proposes **one region per glass**, drawn round the shape the glass really has,
so the visible part of a hidden glass is attributed to the glass it belongs to
instead of being swallowed into the region of the glass in front, and the
rectangle has room to hold the whole shape instead of stopping where the
evidence stops. A glass a modal segmenter leaves out of its report altogether is
reported here as itself, and that is where the gain measured further down comes
from.

The other side of it is reported rather than hidden. Where the completion covers
a glass the camera barely saw, what arrives is an outline with too little seen
inside it to place, and such an outline is handed on as doubtful rather than
placed from nothing. This solution raises that doubt far more often than
[solution 9](09-a-fine-tuned-instance-segmenter.md) does, and that is the
completion working rather than failing: the glass is proposed, and the
arithmetic says plainly that what was seen of it will not place it. A glass
reported as doubtful is a result in this project and not a failure.

### The visible fraction is a free confidence

Once the two parts are separate their ratio is available, and it is the
**visible fraction** defined above. Like the vote spread in [a network trained
from scratch](06-a-network-trained-from-scratch.md), it is a confidence that
costs one division and that comes from the answer itself rather than from the
model's opinion of itself. It should travel with every reported glass, and it
should be calibrated once: run the trained model over held-out renders where the
truth is known, record how far the fitted centre and width land from the truth
at each level of visible fraction, and the raw ratio becomes a statement about
expected error rather than an uninterpreted number.

### Trust it for a position, never for a measurement

A **position to go and look at** can come from such an answer without
hesitation, and that is what the completion is for. A slightly wrong position
costs a picture, and a glass reported in a slightly wrong place is better than a
glass not reported at all.

A **measurement that decides a grip** may not come from it, and the reason can
be given exactly. The asserted pixels supply no reading, so what the width is
fitted to is the part the camera saw, which for a mostly hidden glass is a
crescent, and a crescent gives a width under the truth. The completion neither
invents that width nor repairs it. This project's rule is that the last
millimetres are felt rather than driven: the fingers close until they touch and
then check the width, and the glass comes down until the rim touches and then
checks the weight transferred. A width fitted to part of a glass is exactly what
that rule keeps away from the gripper. So the width reported here is a rough
figure for planning and for the range check, and the real measurement still
comes from the look from the side and from the fingers.

### The fit error stops being a check over the whole mask

The fit error works as a check because real points scatter: points off a real
disc are a noisy disc, and a group that is not a disc produces a fit error
saying so. But the asserted pixels were drawn by a model that has learned what a
glass of this kind looks like from above, which is to say a model that has
learned to draw circles, so those pixels lie on a circle **by construction**.
The fit error over the whole amodal mask is therefore small whatever the truth
is, and a check that always passes is not a check.

The repair must not be skipped. **Compute the fit error over the observed part
only.** Those points are measurements, they scatter like measurements, and
asking whether they lie on one disc is a genuine test of the group they came
from: a region that has swallowed a neighbour, or a strip of table, answers no.
What it cannot test is the completion, which supplies no point on the table to
be tested, and the check that does test the completion is the last of the three
below.

## Measuring whether it works

The next question is how to tell whether the model is doing what it was asked,
and the ordinary measure of a segmenter misleads here in two ways. It matters,
because a model of this kind can be built, trained and declared successful while
completing nothing at all.

The ordinary measure is **overlap**, often called intersection over union: the
number of pixels both the predicted and the true mask contain, divided by the
number either of them contains. It is one for a perfect match and zero when the
two share nothing.

![Three ways of scoring the same amodal prediction: overlap against the visible
truth, overlap against the whole silhouette, and overlap over the hidden part
alone, with the footprint error curve against visible fraction
underneath](../../../../images/problem-2/10-measuring-whether-it-works.png)

### Overlap against the visible truth punishes the model for working

The first trap is to keep the measurement code from solution 9, which compares
each predicted mask with the pixels the camera can see. Every pixel of a correct
completion lies outside that truth, so every one of them is counted as a
mistake: the better the completion the more such pixels there are and the lower
the score, so a model completing perfectly scores **worse** than one completing
nothing, and the highest score available goes to a model that has learned to
ignore the amodal target entirely. The general lesson is the one [a network
trained from scratch](06-a-network-trained-from-scratch.md) states about a score
dominated by background pixels: **a score that rewards doing nothing will be
optimised by a model that does nothing.**

### Overlap against the whole silhouette is dominated by the easy part

The obvious correction is to compare against the whole silhouette, and on its
own that is still a poor guide. For most glasses the hidden part is a minority
of the silhouette, and for a glass with a clear view it is nothing, so the
overlap mostly reports how well the model traced the visible boundary — which is
solution 9's job and which the model was already good at. Averaged over a
dataset, a model that never completes scores close to one that completes
everything correctly, with the difference buried under the part both find easy.

So the second measure has to isolate the part that is the point. **Compute the
overlap over the hidden part alone**, which the simulator supplies exactly by
subtraction. That number ignores every pixel the model could have got right by
tracing a visible edge, so it is the only mask score here that says anything
about the completion itself, and it is the one to watch during training.

### The measure that actually matters is the footprint error

Both measures above score masks, and a mask is not what this solution is for.
What the pipeline consumes is a centre and a width, so the error in those is
most of what decides whether this solution earns its place. Run the trained
model over held-out renders, fit the footprint to each reported glass, and
compare the centre and the width with the truth. Then report the result **as a
curve against visible fraction rather than as one average**, because a single
average is where this failure hides: the well-seen glasses are numerous and
nearly perfect, and averaging them with the badly hidden ones gives a
comfortable figure describing no case in particular.

And count the glasses found, missed and merged beside it, because what this
solution changes shows up in those counts before it shows up in any footprint. A
completion that attributes a crescent to the glass it came off adds a glass to
the answer; it does not improve the footprint of a glass that was already there.

## What running it shows

Those measures have been taken, over held-out scenes no training ever saw, at
the cell's own survey height and from its three stations, on both kinds of
layout, and scored by the scorecard every pipeline in this project shares. What
comes out falls into three findings, and they are worth taking in order: the
first says the idea works, the second says how much room is left above it, and
the third says where it buys nothing at all.

**On a crowded layout the idea works.** Against [solution
9](09-a-fine-tuned-instance-segmenter.md), from the same architecture, the same
borrowed weights and the same scenes, this solution finds about one glass in ten
more of them, and the worst place error among the glasses it reports comes down
by about a quarter. The reason is the [attribution rather than the
measurement](#what-the-completion-buys-is-attribution-rather-than-measurement):
what it adds are hidden glasses whose visible part is attributed to them, rather
than better measurements of the glasses solution 9 already had.

**On a crowded layout it is also at the ceiling.** Hand the renderer's own exact
silhouettes to the same arithmetic, with no model anywhere in the chain, and no
more glasses are found than this solution finds. So what it still misses is not
missed for want of a better segmenter. It is missed because a glass with no
pixels at a station has nothing to extend, which is the limit [a glass hidden
completely](#when-the-glasses-are-completely-hidden) sets and the one no
training moves.

**On a spawned layout the completion buys nothing, and that is the honest half
of the result.** This solution and solution 9 score identically there, down to
the same worst place error, and exact whole silhouettes score the same as exact
visible masks. What cuts a mask on a table the cell lays out for itself is the
edge of the picture, and a silhouette rendered from that station is cut off at
that same edge, so the amodal target is the visible target and the completion
has nothing to add. That is why the two kinds of layout are scored apart from
each other: one number averaged over both would hide the whole result.

## The risk of inventing glass where there is none

A model trained to extend evidence has an obvious failure direction, and it is
the mirror image of the failure this solution is for: it can extend evidence
that did not need extending, or extend a scrap of evidence into a whole object
that is not there.

Two facts about this cell make that concrete. A narrow strip of glass pixels
looks much the same whether it is the visible sliver of a mostly hidden glass or
simply the edge of something that ends there, and the first should be completed
while the second should not. And splay stretches every outline in a picture from
the top outwards, so an outline's far edge can look cut off when the glass
merely ends. This failure is loud where the one it replaces is quiet, and three
cheap checks bound it.

**Those three checks are work still to do rather than work already done**, and
saying so is worth more to a reader than letting them be taken for granted. The
code beside this document splits every reported mask into its observed and
asserted parts and keeps the asserted pixels out of the arithmetic, which is
what [report the two parts separately](#report-the-two-parts-separately) asks
for. On the strength of what it then finds it refuses nothing: no width is
tested against the range the kind allows, no asserted part is intersected with
the blind region, and the arithmetic it shares computes no fit error for
anything to be tested against. The **visible fraction** is the plainest gap of
the lot, because the split that would give it is computed for every reported
mask and the ratio costs one division, and still no such number travels with the
answer. So what the completion earns on its own is a position good enough to
look from; the three checks below are what a cell has to wrap round this model
before a completed mask may be acted on.

### The kind's own range of widths

Inventing glass means reporting a glass where none stands, and every report
carries a width, so the range check from the start of this document has real
work to do again here. The pixels of an invented region are pixels the camera
saw something at, bare table or the edge of a glass that ends there, so they
give points on the table and a width of their own, and a width outside the range
this kind allows is reason enough to refuse the report and hand it on as
doubtful. Notice what has changed: against a truncated modal mask the check was
useless, because the truncated width looked like a legal smaller glass, while
against an invention it catches the thing directly, since claiming a glass means
claiming a footprint and a claimed footprint either fits the kind or does not.

### The observed points must sit on one disc

The second check is the one recovered at the end of the last section, and what
it tests is the group of pixels rather than the completion. Fit a circle to the
**observed** points and to nothing else, because an asserted pixel carries no
reading to make a point from, and then ask how far those points sit from it:
that asks whether what the camera saw is a patch of one glass's disc. A
region that has swallowed a neighbour, or a strip of table, or two glasses at
once, answers no. The completion itself is left to the third check, which is the
one that looks at the asserted pixels directly.

### The assertion has to lie somewhere the camera could not see

The third check does not involve the model at all, and it is the strongest of
the three, because it is geometry.

[Cluster on the table](../programmed/02-cluster-on-the-table.md) already
computes, from the glasses it found and the recorded camera pose, which pieces
of table no ray from the lens reached, and it calls that the **blind region**. A
model claiming a glass continues behind the near glass is claiming something
about a part of the scene the camera could not see, which is allowed. A model
claiming a glass continues across a patch the camera had a clear view of, and
where bare table came back, is contradicting a direct observation.

So intersect the asserted part with the blind region for that picture. Anything
asserted outside it is wrong on arithmetic alone, with no reference to the
model, the training set or the kind. The check is cheap, it needs nothing this
project does not already have, and it is the reason a learned completion can be
let near the arm.

### And a free test for the quiet version

One form of invention escapes all three checks: a model that completes a little
on every glass, whether or not anything is in front of it, reports footprints
that are all slightly too wide and displaced slightly outwards, and no single
answer looks wrong. The aggregate catches it, and the aggregate is free. **On a
glass with nothing in front of it, the amodal mask must equal the modal one.**
So keep only the unobstructed glasses in the held-out scenes and measure what
the model adds to them: the correct answer is nothing, and any systematic
addition is a bias worth knowing about before the model is trusted.

## How the concepts fit together

Everything above is one chain, and it is worth reading in order, because each
stage inherits what the one before it produced. A **picture** from the top goes
in. The model proposes rectangles that might contain a whole glass, including
the part of it nothing shows, and for each rectangle it keeps it predicts an
**amodal mask** covering that glass's whole silhouette, with a score. The mask
is split into its **observed part**, where the depth reading agrees that the
surface seen there belongs to this glass, and its **asserted part**, which is
the rest. Every pixel of the observed part becomes a **point on the table**, and
an asserted pixel becomes no point at all, because the reading under it belongs
to whatever stood in front. The place and the width come from those points, and
so does a **fit error** wherever the arithmetic computes one, every one of them
a measurement of the part that was seen; the silhouette has already done its
work, in deciding which pixels are this glass's.

Then three checks have to run, and each can only reject. The width must lie
inside the range the kind allows. The observed points must sit on one disc. The
asserted part must lie inside the **blind region** the geometry says this camera
pose could not see. A glass passing all three is reported with its centre, its
width and its **visible fraction**; a glass failing any of them is reported as
doubtful, with the check it failed, and handed to [move the
camera](../programmed/03-move-the-camera.md).

Three things are worth holding on to. The **target** decision is the whole
solution, since everything else is solution 9 unchanged. The **separation**
decision is what keeps it honest, because the arithmetic and every surviving
check need observed and asserted pixels kept apart. And the **arithmetic**
decision is unchanged from every other solution here: the model proposes a
silhouette, and the kind's range of widths, the observed points and the blind
region dispose.

## When the glasses are completely hidden

Everything so far is about a glass with some of itself in the picture. This
section is about a glass with none, and it is the honest limit of the whole
idea, so it is worth being exact about why no amount of training moves it.

Start from what completion is. **Amodal completion extends evidence.** The model
sees a boundary that stops, sees a surface in front of where it stopped, and
continues the boundary behind that surface in the way a glass of this kind would
continue. Every part of that description begins with something in the picture:
the visible sliver says where the glass is, how wide it is, and how far the
completion has to reach.

Now take the sliver away. A glass covered completely contributes no pixels, so
there is no boundary that stops, no partial outline to continue and no scrap of
surface to say which glass of the kind's range this is. There is nothing to
extend, and a model that extends nothing produces nothing.

![A glass with a sliver visible being completed correctly, beside the same pair
arranged so that nothing of the far glass reaches the picture, leaving the
completion no evidence to start
from](../../../../images/problem-2/10-where-it-stops.png)

The argument can be put more strongly than "it does not work", and it is worth
putting that way because more training is the first thing anybody proposes. Take
the scene with the covered glass, and the same scene with that glass removed.
The two produce the **same picture, pixel for pixel**. No function of the
picture can tell them apart — not this model, not a larger one, not one trained
for longer on more scenes — because the thing that differs between the two
scenes left no trace in the input. That is a fact about the input rather than
about the model, and training cannot change facts about the input.

A model *could* be trained to mark a glass that **might** be behind this one,
since the simulator can supply that label too, and it is worth saying exactly
what such a model would be doing. It would be reporting where glasses tend to
stand in scenes like this one, which is a statement about the range of
arrangements rather than about this arrangement. That is **inventing a scene
rather than reading a picture**, and it would mark a glass behind every tall
glass, including all the times there is nothing there. Trading a silent miss for
a confident invention is a bad trade where the next step is an arm moving, and
it is the trade this project's rules refuse: anything doubtful is reported,
never guessed.

A guess about a part of the scene nobody observed is a question about geometry
rather than about appearance, and the right machinery for it is not a segmenter.
This project already has that machinery, in three pieces.

**Where a glass could have been hiding** is worked out by [cluster on the
table](../programmed/02-cluster-on-the-table.md), which takes the glasses that
*were* found, their widths and heights, and the camera's pose, computes the
pieces of table no ray from the lens reached, and keeps the ones large enough to
hold the smallest footprint this kind allows.

**Which of those patches is worth spending a picture on** is settled by nothing
in this folder, so they are covered in whatever order the geometry suggests.
That is worth knowing, because moving the arm is the expensive resource here
and most blind patches are empty.

**Taking the picture** belongs to [move the
camera](../programmed/03-move-the-camera.md), which turns a place worth looking
at into a pose the arm can reach.

One thing this solution does contribute there. Completion needs less of a glass
than any other method here, so the point at which hiding becomes complete is
further away with this model than without it, and glasses that would have gone
missing entirely under a modal segmenter are found and placed from the sliver
that is left, which is what the crowded layouts measure. **The boundary moves;
it does not disappear.** Beyond wherever it now sits, this solution has nothing
to say, and says so.

## A worked example

Everything below follows from the cell's own geometry, and it takes one
arrangement through three positions.

**The arrangement.** A tall glass and a short glass of the same kind stand at
the closest separation the cell guarantees, and the camera looks down from the
top. The short glass is further out from the point directly below the camera
than the tall one, along the same line running outwards from that point. Splay
throws both outlines outwards, and because the tall glass is the taller its
outline is thrown further, so it sweeps across the ground where the short glass
stands.

**What a modal segmenter reports.** The tall glass comes back whole with a
correct footprint. The short glass comes back as a crescent down one side: the
fitted centre is pulled towards the crescent, the fitted width comes out under
the truth, and the fit error is small because a patch of a disc is well
explained by a smaller disc. The width lands inside the range the kind allows,
because a kind spanning a small tapered glass to a large one has room for a
short measurement. So two glasses are reported with believable widths, one of
them standing where no glass is standing, and the arm goes where it was told. Or
the crescent is never proposed as a region of its own, and one glass is reported
where two stand.

**What this solution reports.** The short glass's mask includes the part behind
the tall glass, so the short glass is a region of its own and the crescent is
attributed to it rather than swallowed into the tall glass's region. The
observed part is the crescent and the asserted part is the rest, so the visible
fraction is low and travels with the answer. The asserted pixels carry the tall
glass's depth readings, so they are left out, and the place and the width come
from the crescent: the place is good enough to send a camera to, and the width
is under the truth. The crescent is a patch of one glass's disc, so a fit error
over the observed points is small. The asserted part lies in the tall
glass's own shadow, inside the blind region, so nothing is claimed where the
camera had a clear view. None of the three checks has anything to object to, so
the glass is reported, placed well enough to look at again and flagged as mostly
inferred.

**What the flag then buys.** Because the visible fraction is low, the reported
width plans and does not grip. The arm goes to the side, stands back at the
measuring standoff and looks level, and from there nothing is in front of the
short glass, so its modal and amodal masks coincide and its footprint is
measured rather than predicted. The completion decided **where to look**, and
the look decided **what is true**.

**Push the pair the other way.** Put the short glass exactly behind the tall one
along that line, and its whole outline disappears under the tall glass's splayed
one. There is no crescent and nothing to extend. One region comes back where two
glasses stand, the footprint fitted to it is the tall glass's own correct
footprint, and **nothing in the answer is wrong** — it is simply short by one
glass. No check fires, because every check here is a check on something that was
found. That is the case handed to geometry, and no version of this solution
answers it.

## Running it yourself

The code for all three pre-trained solutions lives in one folder with one
environment between them, described in
[`problem-2-pretrained`](../../../../problem-2-pretrained/README.md).

The setup command is run once, and it installs the environment and fetches the
weights this solution starts its fine-tuning from.

    make setup

Then training and testing take the name of the solution, and this one is
`amodal`:

    make train SOLUTION=amodal
    make test  SOLUTION=amodal

That test scores the layouts the cell spawns for itself. The layouts where one
glass really does stand in front of another are asked for by name, and they are
the only ones on which this solution can differ from solution 9 at all:

    make test-crowded SOLUTION=amodal

One more command runs the same scenes with no model in them at all. It hands the
renderer's own masks to the same arithmetic, over both kinds of layout, which is
the floor every number here is read against and where the cost of feeding the
asserted pixels in was measured:

    make floor

Running `make train SOLUTION=maskrcnn` instead trains [solution
9](09-a-fine-tuned-instance-segmenter.md) from the same architecture on the same
scenes with the visible masks as targets, and putting both solutions through
both test commands is how [what running it shows](#what-running-it-shows) was
arrived at: the completion pays on the crowded layouts, and on the spawned ones
the two solutions cannot be told apart.

## What it needs

This solution needs everything solution 9 needs, and then two things of its own.

It needs a **deep learning framework** and an environment to run it in, which is
a large dependency for a cell whose recommended answer is a page of arithmetic.
It needs the **pre-trained weights** fetched once, which is a file large enough
to belong outside the repository. It needs a **graphics processor**: the machine
here is an Apple M4 with a ten-core integrated graphics processor and memory
shared between processor and graphics, reached through the framework's MPS
backend and falling back to the main processor otherwise. There is no NVIDIA
card and no CUDA anywhere in this project, and the shared memory is why a model
of this size fits. And it needs a **file of weights kept in step with the
world**, because changing the lighting, the camera, the table or the range of
sizes a kind is drawn from leaves the file quietly out of date in a way no test
of the code will notice.

The two extra needs are both about the training data. It needs **one extra
render per glass per scene**, because the amodal label for a glass is the
identity map of that scene with the other glasses taken away, so rendering time
grows with the number of glasses in a scene. That is a real cost and still a
small one, because it is machine time rather than a person's time.

And it needs a **training set spread across the whole range of visible
fraction**. The cell's placement rule produces a mixture weighted towards
well-seen glasses, and a model trained on that mixture meets the hard case
rarely and optimises for the easy one. So scenes have to be spawned with glasses
far more heavily covered than the rule would ordinarily produce, while keeping
the easy scenes too, in proportion, so the model does not learn that something
is always hidden. The training set is built that way, with the crowded layouts
standing beside the spawned ones.

### The pictures are not photographs

One difficulty is shared with the other two pre-trained solutions, it is the
largest risk in all three, and it must not be buried.

The cell's renderer produces a depth reading per pixel and a glass identity per
pixel. **It does not produce colour.** The model, and the weights it starts
from, expect an ordinary colour photograph, so the code makes one: it shades the
depth into a grey picture and repeats that picture across the three colour
channels. That is a genuine difference from the pictures the weights were fitted
on, and not a small one, because those weights carry knowledge about texture,
shading, the colours things tend to be and what edges in real photographs look
like, and a grey depth shading has none of those properties. How much of the
borrowed knowledge survives is **not known**, and it is the first thing the
measurements should be read for.

It matters slightly more here than for solution 9. Completion is a judgement
about which of two surfaces is in front and about how a shape continues, and in
real photographs the cues for that are largely about appearance: texture
stopping, shading turning, a shadow falling. A grey depth shading keeps the
geometric cues and loses the rest. Those are the stronger cues for upright
solids on a flat table, so there is reason to expect this to work, but a reason
is not a result.

## Where it is strong and where it breaks

**It reports a partly hidden glass as a glass of its own.** This is the point of
the solution. A modal segmenter swallows the crescent of a hidden glass into the
region of the glass in front, or leaves it out for being too thin to propose,
and this one hands it on attributed to the glass it came off, which on a crowded
layout finds about one glass in ten more and brings the worst place error down
by about a quarter. What it does not do is measure the part nobody saw: those
pixels carry another object's depth readings and are left out, so the footprint
is still the footprint of the part that was seen, too small and displaced in the
quiet way the first half of this document describes.

**It does nothing about the edge of the picture**, which is the commoner of the
two causes, and that is measured rather than guessed at. A glass whose outline
the frame cut is cut in its whole silhouette too, because a silhouette rendered
from that station stops at that same edge, so there is nothing to assert and
this solution and solution 9 answer alike on every layout the cell spawns for
itself. What the cell does about the frame edge is to survey from three stations
and ask them to agree.

**It costs almost nothing over solution 9.** The architecture, the starting
weights, the training pictures and the arithmetic downstream are all the same;
the change is the target each mask is scored against, and the simulator supplies
the label for it.

**Part of its answer is asserted, and it cannot explain itself.** The asserted
pixels are kept out of the arithmetic, so what they cost is not a wrong
measurement but the standing invitation to use them as one: a run that hands the
whole silhouette on instead places a glass several times further from where it
stands, with every check still passing. And a model that extends evidence can
extend evidence that did not need extending. The three checks wrapped round it
are what make that tolerable, and in the code beside this document they are
still to be built.

**It is blind to a glass hidden completely.** No pixels means nothing to extend.
That is a fact about the input, it is shared with every method here that works
from pixels, and it is handed to geometry.

## The general ideas behind this

Nothing here is new. Amodal segmentation is an established task with its own
datasets and measurements, occlusion reasoning is older than learned vision,
learning from labels a simulator produces is standard in robotics, and the
perceptual phenomenon the whole thing is named after was described in the middle
of the last century. What is unusual is the combination: a cell narrow enough
that a completion can be checked against a known range of shapes, and a
simulator that makes the otherwise expensive label free and exact.

### Amodal completion and amodal instance segmentation

The task of predicting an object's whole extent rather than only its visible
pixels was posed for learned vision by Li and Malik, *Amodal Instance
Segmentation* ([arXiv:1604.08202](https://arxiv.org/abs/1604.08202)), who worked
round the labelling difficulty by pasting objects over other objects, so that
the whole extent was known by construction . Zhu and colleagues, *Semantic
Amodal Segmentation* ([arXiv:1509.01329](https://arxiv.org/abs/1509.01329)), had
people annotate whole extents on real photographs and measured how well the
annotators agreed, which is the cost this document escapes. Follmann and
colleagues, *Learning to See the Invisible*
([arXiv:1804.08864](https://arxiv.org/abs/1804.08864)), put the amodal target
into an instance segmenter of exactly this shape. Ke, Tai and Tang, *Deep
Occlusion-Aware Instance Segmentation with Overlapping BiLayers*
([arXiv:2103.12340](https://arxiv.org/abs/2103.12340)), go further and model the
occluder and the occluded object as two layers at once, which is the principled
version of the near-and-far judgement this solution needs its model to make
implicitly.

It is normally the right tool where a later step needs the whole object rather
than the visible piece of it: picking from a cluttered bin, where the grasp is
planned on the object's shape; tracking, where an object passing behind
something should stay one object; and reasoning about depth order. It is right
here for the first of those reasons, because the circle fit is a computation on
a whole shape.

It is not the right tool where the visible extent is what is wanted, which
covers most measurement: if the question is how much of a surface can be seen,
or where exactly it can be touched, a completion answers a different question
and makes the answer worse. It is also poor where there is no strong prior on
shape, because completing an object needs knowledge of how objects of that sort
continue, and a model without it extends boundaries arbitrarily. For more, see
[amodal perception](https://en.wikipedia.org/wiki/Amodal_perception), which
covers both the phenomenon and the computational task.

### Occlusion reasoning and layered scene models

Behind amodal completion sits an older and more general idea: a picture is not a
flat arrangement of regions but a stack of surfaces at different depths, . Wang
and Adelson, *Representing Moving Images with Layers* (IEEE Transactions on
Image Processing, 1994), made that stack the representation itself. Hoiem, Efros
and Hebert, *Recovering Occlusion Boundaries from an Image* (International
Journal of Computer Vision, 2011), attacked the piece this solution needs
directly: given a boundary between two regions, which of the two is in front?
That question is unavoidable here, because completing the wrong side of a
boundary produces a mask extending over a glass that is actually nearer the
camera.

It is normally the right tool whenever a decision depends on what is behind
something: planning a view, planning a grasp, deciding whether an object has
gone away or merely gone behind something. It is at its best when the geometry
is simple enough to compute exactly, which is why this cell can do part of it
with arithmetic. It is not the right tool when a scene is too irregular for the
hidden region to have a usable form, which is the common case, and there the
usual approach is to trace rays through cells, making the answer approximate. It
is also no substitute for looking again: knowing a region is unobserved tells
you to observe it, and no amount of reasoning produces the observation.

### Learning from labels that cost nothing

The third idea is what makes this solution practical rather than merely correct,
and every learned solution here rests on it. When the training pictures come
from a renderer, the renderer already knows the answer, so the label is a
by-product of making the picture rather than separate work. Richter and
colleagues, *Playing for Data: Ground Truth from Computer Games*
([arXiv:1608.02192](https://arxiv.org/abs/1608.02192)), is the clearest
demonstration of the argument, and the amodal case is where it pays best of all:
a renderer can answer "what would this object look like with nothing in front of
it?" exactly, and a person looking at a photograph cannot answer it at all.

The catch is that a model trained on renders has learned the renderer, and the
standard answer is **domain randomisation**: vary everything you are not trying
to teach, over a range wider than reality, so the model cannot use any of it as
a shortcut (Tobin and colleagues,
[arXiv:1703.06907](https://arxiv.org/abs/1703.06907)). Here that means the
light, the table's colour and texture, the glasses' tint and proportions, the
camera pose, the exposure, the picture noise and the arrangement itself, while
holding fixed the lens, the upright glasses and the flat table, which are the
task rather than nuisances.

It is normally the right approach wherever labels would otherwise be drawn by
hand and a simulator of the task exists, which covers most of robotics, and it
is especially right where a person could not produce the label reliably even
with unlimited time. It is not the right approach where the thing being learned
is precisely what the simulator gets wrong: a renderer's treatment of appearance
is its weakest part, so a model trained on renders to judge a fine appearance
question is learning from the wrong teacher. That is the risk hanging over this
solution's grey depth shading, which is why the risk is written down plainly
rather than argued away.

### The psychology of amodal completion in human vision

The last idea is the oldest, and it is where the word comes from. Michotte,
Thinès and Crabbé, *Les compléments amodaux des structures perceptives* (1964),
named the phenomenon: part of a perceived object is present to the perceiver
without being delivered by any sense. Kanizsa, *Organization in Vision* (1979),
showed with figures rather than argument how strong and how automatic the effect
is, including cases where a boundary is perceived across a region containing
nothing at all. Kellman and Shipley, *A theory of visual interpolation in object
perception* (Cognitive Psychology, 1991), turned it into a testable theory,
setting out the geometric conditions under which two visible fragments are
joined into one object behind an occluder — which is, in effect, a specification
of what a completion model is supposed to compute.

Two things there matter here. The first is that completion in people is governed
by the fragments and by nothing else: what is joined is decided by how the
visible edges run towards each other. That is the restriction this document
insists on, and it is why a glass with no fragments is outside the scope. The
second is that the effect is not a guess a person can inspect or switch off,
which is a warning when reading a model's output: a completion looks exactly as
solid as an observation, and the only way to tell them apart is to keep a record
of which pixels came from where.

The psychology is the right thing to consult about **what** a completion should
produce, because it describes a system that solves this problem well. It is the
wrong thing to consult about how far to trust one, because a person does not
have to hand a footprint to a machine that will move towards it. For more, see
[amodal perception](https://en.wikipedia.org/wiki/Amodal_perception) and the
[Gestalt principle of good
continuation](https://en.wikipedia.org/wiki/Principles_of_grouping), which is
the rule of thumb the interpolation theories make precise.

## Where it sits among the other solutions

This solution is [solution 9](09-a-fine-tuned-instance-segmenter.md) with one
change, so the comparison with it is the only one needing care, and it comes
down to a single trade.

**What the change buys** is that a partly covered glass is reported as itself,
which a crowded layout measures as about one glass in ten more found and a worst
place error about a quarter lower. Solution 9's masks are modal, so a partly
covered glass gives it a crescent, and a crescent is swallowed into the region
of the glass in front or left out for being too thin to propose. What the change
does not buy is the footprint of the part nobody saw, because the completion
supplies no depth reading, and it does not reach the edge of the picture at all:
covering by a neighbour is the one cause the two solutions differ on, and on
every layout the cell spawns for itself they score alike.

**What the change costs** is four things, and solution 9 pays none of them. The
glasses it reports that solution 9 would have left out are the mostly hidden
ones, so the widths it adds are the widths of crescents and have to travel with
the visible fraction that says so. The asserted pixels have to be named and kept
out of the arithmetic before anything is fitted, and a run that hands the whole
silhouette on instead places a glass several times further from where it stands
than solution 9 would, with every check still passing. The rectangles have to be
proposed around whole silhouettes, which is a harder detection task. And there
is a new failure direction, inventing glass where there is none, bounded by the
kind's range of widths, by the observed points and by the blind region once a
cell runs those checks, but not removed.

Solution 9 is therefore the thing to build first, because it is the same code
without the extra label and the extra risk, and this change earns its place
where glasses stand in front of one another and nowhere else.

Against [cluster on the table](../programmed/02-cluster-on-the-table.md) the
comparison is more interesting, because that solution attacks the same
difficulty from the opposite side and the two do not overlap at all. Its
blind-region arithmetic asks **where could a glass have been?** and looks at no
pixels: it takes the glasses it found, their widths and heights, the camera's
pose and the splay geometry, and computes which pieces of table no ray reached
and which of those are large enough to hold the smallest footprint this kind
allows. This solution asks **what is the whole shape of the glass I can partly
see?** and looks only at pixels: it takes a fragment and extends it, and it has
nothing to say about a place where no fragment exists.

Those are complements rather than alternatives. This solution shrinks the set of
glasses that go missing, by needing less of a glass to be visible; the
blind-region arithmetic bounds what is left, by naming the places a missing
glass could still be standing. Neither can do the other's job: no completion
finds a glass with no pixels, and no geometry says which glass a sliver of
pixels came off.

The rest of the folder fits around those two. [Split the blob in the
picture](../programmed/01-split-the-blob-in-the-picture.md) and [a network
trained from scratch](06-a-network-trained-from-scratch.md) work from visible
pixels only, so both inherit the truncated-footprint failure, and the second
names amodal segmentation as the repair without performing it — this performs
it, and the part of the failure it reaches is which glass a truncated mask
belongs to. [Segment anything, then keep the
glasses](08-segment-anything-then-keep-the-glasses.md) has the same gap and
cannot close it this way, because its masks come from a model used as
downloaded.

And where this solution stops — a glass covered completely, with no fragment to
extend — is where the argument leaves appearance altogether and becomes
geometry, which is the second half of [cluster on the
table](../programmed/02-cluster-on-the-table.md) and not this document.

← [A fine-tuned instance segmenter](09-a-fine-tuned-instance-segmenter.md) ·
[Learned approaches that need more than a simulator](learned-with-hardware.md) →
