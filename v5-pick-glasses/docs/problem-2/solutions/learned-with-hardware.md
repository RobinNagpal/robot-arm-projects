# Problem 2 — learned approaches that need more than a simulator

## Introduction

This document collects four learned approaches to problem 2 that were considered
and then set aside, and it explains what each one is and why it was set aside.
They were originally part of [`solution-overview.md`](solution-overview.md) and
were moved here because none of them can be built and trained inside this
project's simulation alone. By the end you will understand what each approach
does, the idea behind it that is worth knowing even if it is never built, and
which practical condition it fails.

The important thing to say first is that **nothing here is wrong**. Each of
these is a reasonable answer to this problem, and several are what a
well-resourced team would reach for first. They are written up so that the
choice stays visible, and so that the reason for not taking them is the honest
one, which is the machine and the data rather than a view about learned methods.

None of them needs a different *algorithm* to become usable. They need a
different *setup*: a graphics card, or a camera on a real table, or both.

## The test each one had to pass

An approach belongs in the main overview if **everything it needs can be
produced by the simulator on the machine this project runs on**. That machine
has no dedicated graphics card, there is no robot on a bench, and there is no
real-world data. In practice that comes to four conditions.

**The first is no artefact from outside.** Any model an approach uses has to be
trainable from what the simulator renders. A downloaded file of weights fitted
to photographs of the real world is not reproducible here, however good it is.

**The second is no sensor the simulator does not have.** The simulator gives
this cell a depth camera, contact sensors in the gripper pads, and a force
sensor at the wrist. Anything else is a purchase order rather than a design
decision.

**The third is no graphics card it has not got.** Anything that needs compiled
code for a particular make of graphics card is out. The machine's own graphics
path runs, with some operations quietly falling back to the processor.

**The fourth is hours rather than days.** A method that takes a week of
continuous simulation to train cannot be iterated on, and a method you cannot
iterate on will not be debugged.

Everything below fails at least one of those four.

One general note about tooling, which applies to all four and is worth knowing
before depending on any of them. **The licence terms across these model families
differ sharply**, and some of them are copyleft in a way that reaches software
you only ever run as a service and never distribute. At least one popular family
states one licence in its documentation and a different, stricter one in its
licence file, and the licence file is what counts. So for anything that might
ship, reading the licence file is a decision rather than a detail. The specific
terms are not listed in this document, because they change.

---

## Geometry proposes, a promptable model refines

> **Fails condition 1.** Its whole point is a promptable segmentation model, and
> every usable one is a file of weights fitted to millions of real photographs.
> That file cannot be produced from this simulator. It also has no substitute
> trained inside the simulator, because a promptable model that has only ever
> seen renders has no general notion of an object boundary to offer.

*Hybrid, with the model as a proposer. Send the model only the clusters the
geometry is unsure about, prompted with the point the geometry already computed,
then check its answer with the same arithmetic that flagged the cluster.*

### What it is

This is a **hybrid**: the geometry proposes, a learned model refines, and the
geometry decides. The model is never the last word.

Two words are needed first, and the difference between them is the whole reason
this approach exists.

A **closed-set** model answers only with a name from the fixed list it was
trained on, and it returns nothing for anything else — which a robot reads as
"nothing there". That behaviour is dangerous in a cell that may meet something
unexpected.

A **promptable** model takes a picture *and a hint*, and returns the pixels at
that hint. The hint is called a **prompt**, and it is a place rather than words:
a point, a box, or a rough mask. Its answer is a boundary and never a name, so
there is no list to fall off.

### Why anyone does it this way

The reason is that the two halves fail in opposite directions, which is what
makes them safe to combine in one particular order.

**Geometry fails loudly.** A merged pair comes back as a footprint several times
wider than any glass of that kind can be, so the failure states itself: here is
the measured width, and here is the limit it broke. What geometry cannot do is
draw a boundary *through* a clump, because the projection threw that information
away.

**A model fails quietly.** It draws a good boundary on an object it has never
seen, and an equally confident boundary round the wrong thing.

Put them in this order and **the loud failure catches the quiet one**. That is
the pattern worth taking generally: a learned component used as a proposer
inside a checkable envelope. Its output is not trusted but tested, against a
measurement that exists independently of it. So a wrong mask never becomes a
wrong glass. It becomes a width outside a range.

### How it would work here

It would run in three stages, and the order of the stages is the safety
argument.

**First, geometry proposes, with a confidence.** The geometric detector already
gives, for each cluster, a position on the table and a fitted footprint circle.
Add one label to that: a cluster whose circle is inside the kind's allowed range
of widths is **settled**, and one that is not, and that two circles do not
explain either, is **doubtful**. That word is the gate.

**Second, the model refines, and only on doubtful clusters.** The prompt costs
nothing to produce, because the geometry has already computed it. The cluster's
centre, projected back into the picture, is a point prompt. Its bounding box in
the picture is a box prompt. And a clump believed to be two glasses gives two
point prompts.

**Third, geometry decides.** Each mask the model returns goes back through the
first stage's arithmetic: pixels become points in the room, the points drop onto
the table, and a circle is fitted. Accept the answer only if **both** widths are
inside the kind's range and the two centres are far enough apart to be two
glasses. Otherwise both are discarded. The model proposed a boundary, and it did
not get a vote.

It is worth saying why the model is not run on every picture. A mask cannot
improve a number that is already right, and it can make it wrong. One or two
doubtful clusters per run is the right load.

The cost of a call has a shape worth knowing. These models encode the picture
once and then decode once per prompt, and the encoding is the expensive part. So
two prompts cost one encode and two cheap passes.

### What happens when the check rejects the masks

Suppose the third stage rejects the masks. The tempting answers are a larger
model, a second prompt, or a looser threshold, and all three are wrong for one
reason: **the picture does not contain the answer.** Two glasses in line with
the camera hide each other, and no boundary drawn on those pixels recovers what
was never recorded.

The right next action is **another picture from somewhere else**. The rejection
carries exactly what the viewpoint solutions want: which cluster is doubtful,
where it is, and how wide it wrongly appears. Solution 3 then scores the
directions round it for line of sight, arm path and reach, and the new picture
re-enters at the first stage. Cap that at a couple of extra looks. If no
viewpoint separates the pair, then they cannot be separated where they stand,
which is problem 3's business: moving them apart rather than photographing them
harder.

### A worked example

Five glasses of one known kind stand on the table. The camera works from the
top, at the survey height, so the whole zone is in one frame.

*The first stage.* The clustering returns one group fewer than there are
glasses. Most of the groups fit circles comfortably inside the range this kind
allows, so those are settled — and **the model is never loaded for them at
all**, which is the whole point of putting it last. The remaining group fits a
circle several times too wide, and splitting it in two gives two circles that
are both still too wide. So the group is doubtful.

*The second stage.* That group spans a large fraction of the width of the
picture, and its two likeliest centres project to two well-separated pixels.
Those two pixels are the prompts handed to the model: one encode of the picture,
then one cheap decoder pass per prompt.

*The third stage.* The two masks the model returns are re-projected onto the
table and fitted. Both come back inside the kind's range, and their centres come
back further apart than the smallest gap the cell guarantees between two
glasses. Everything agrees, so the pair is accepted.

The other branch is the one worth remembering. Suppose the second mask fits a
circle outside the kind's range. Then **both** masks are discarded, and not just
the bad one — because a model that got one of a pair wrong has told you nothing
trustworthy about the other. The group stays doubtful and goes to solution 3 for
a viewpoint square across the line joining the pair.

### What it needs, and what it is good and bad at

What it needs is a framework to run the model in, a version-pinned weights file,
a projection from a table position back to image pixels, which already exists, a
rule turning a cluster into a prompt, and the circle fit called a second time.
There are no labelled pictures to collect and no training to do.

What it is good at is drawing boundaries through a clump the geometry cannot
cut, which is the one job geometry genuinely cannot do. It enlarges nothing that
is trusted, because every number leaving it came from arithmetic checked against
a range the project holds. And it costs nothing at all when nothing is wrong.

What it is bad at divides into three things. **It cannot start anything**,
because nothing in it decides where to point. **It cannot name what it
outlined**, so point it at the drying rack or at the arm's own wrist and it will
outline those just as willingly. And its answers are smoother than this camera's
pictures deserve: these models resize internally to something several times
larger than this camera's frame, so blowing the picture up returns a boundary
far smoother than the picture itself justifies, and **the extra smoothness is
invented**. Transparent objects are also the family's worst case.

Its failure modes follow from those. It can outline the wrong thing confidently,
such as the table behind a rim or a highlight as its own object, and the third
stage catches that unless the wrong thing happens to be glass-sized. It can
split one glass, because prompted at a bowl it returns the bowl. Both masks can
pass and both be wrong, which is the residual risk, and agreement across
stations is the remaining defence. And without a cap it thrashes.

### When it would be the right choice

When the cheap method has failed on a named cluster, and not before, because a
model adds nothing to a cluster that already passes the circle fit.

Three cases would earn it. Here, for a doubtful cluster that two circles cannot
explain and no viewpoint resolves. In problem 4, where the kind is unknown and
the allowed width becomes the union of several ranges, loosening the envelope
that keeps this safe. And on real glassware, where there is no depth to cluster,
so the geometric route stops existing and takes the envelope with it.

Until then, the gate should stay shut.

---

## Train an instance model

> **Fails conditions 1 and 4.** The recipe is to fine-tune a model that already
> knows what objects look like, which means starting from a backbone trained on
> real photographs. And on this machine, a fine-tune that takes an hour on a
> rented graphics card takes most of a day. *A version trained from a random
> start on renders alone does fit the budget, and it is in the main overview as
> [solution 7](07-a-segmenter-trained-from-scratch.md).*

*Learned, as the decider. Show a network a few thousand labelled pictures and
let it learn to outline each object separately.*

### What it is

A **neural network** is a program whose behaviour comes from numbers learned
from examples rather than from rules somebody wrote. Those numbers are called
**weights**, and they live in a file.

Three things such a network can do with a picture of five glasses are easy to
confuse, and the difference between them decides whether it answers this problem
at all.

**Detection** returns a rectangle round each glass, and the rectangles of
overlapping glasses overlap too.

**Semantic segmentation** labels every pixel with a class, so every glass pixel
comes back labelled "glass". Nothing says *which* glass, so two overlapping
glasses come back as one region, which is exactly the merge this problem exists
to prevent.

**Instance segmentation** labels every pixel with a class *and* with the object
it belongs to. Five glasses give five **masks**, a mask being a picture where
every pixel is yes or no.

This problem asks which pixels belong to which glass, so it is asking for
instance segmentation, exactly.

### Why anyone does it this way

The reason is the one thing every other method in this project depends on.

Every other method here reasons about geometry, and all of that geometry depends
on the glasses being opaque, so that the depth camera returns a real distance
for every glass pixel.

**A real depth camera gets almost none of that back from real glass.** There is
nothing to cluster, no points above the table, and no circle to fit. What is
left is the colour picture, where a glass shows itself through refraction,
through highlights, and through the way the background bends behind it. Nobody
has written a rule that captures those. A model learns them from examples.

### How it would work here

The pictures from this camera are small by the standards of these models, which
usually expect several times more pixels across. Training and running are
therefore cheap — but the mask boundary stays coarse however good the model is,
because the detail was never in the picture to begin with.

Several families would do the job. One is the established two-stage design that
proposes regions and then predicts a mask inside each one. Another is the
single-stage family from the real-time detection world, which is the easiest
path by a distance and carries the strictest licence terms. A third option is to
use a semantic segmenter and bolt a separating step onto it, which is more work
for less.

**Making the data** is the easy part here, and it is worth noticing how easy.
The simulator knows every glass's outline, so it renders labelled pictures for
nothing, and the labels are perfect. Other renderers produce better-looking
pictures if that ever matters.

**Domain randomisation is what makes rendered data transfer.** Rather than
trying to make the render look real, vary everything you are *not* teaching —
the lighting, the textures, the background, the camera pose, the exposure, the
noise, the glass colour, and how many glasses there are and where — so widely
that reality looks like one more variation. The model then cannot latch onto
anything that differs between simulation and reality, because none of it was
ever constant.

**Does it break the project's rule?** The rule is that no glass's size appears
anywhere in the project. The model outputs a mask, in pixels, and a mask holds
no distances, so size still comes from the depth reading and the camera
geometry, measured during the run. So the answer is no: nothing is written down,
and the arm still measures every glass itself.

But it does put a **size-shaped prior** into a file nobody can inspect, having
been trained on one range of proportions. That is knowledge about glass sizes
held inside the project, and the report should say so out loud.

### A worked example

Five glasses stand on the table. Two of them are a long way apart, at twice the
distance the cell guarantees, but they happen to line up with the camera, so
their outlines touch in the picture.

Today the detector returns one mask of everything above the table top, and the
grouping step turns it into blobs. The lined-up pair become one blob, far wider
than any glass of that kind can be, and everything downstream believes it is one
large glass.

A trained model returns five masks, and the lined-up pair are two of them
sharing a boundary. Each mask then runs through the existing code unchanged:
points in the room, a circle fitted at the table, and a position and rough width
reported.

### What it needs

**Pictures.** The recipe is to fine-tune rather than train from scratch, which
means taking a model that already knows what objects look like and teaching it
this one class. A few hundred labelled pictures is enough to see it work and a
few thousand to be steady, and the simulator renders them overnight. How many
are enough here has not been measured, and this document will not guess.

**A machine to train on**, and this is the awkward part. The cell runs on a
machine with no dedicated graphics card, and while training does run on the
machine's own graphics path, some operations fall back to the processor, so a
fine-tune of an hour on a rented card can take most of a day here. It is
possible; it is not something you do between two experiments. Anything needing
compiled code for a particular make of card is out entirely.

**Somewhere to run it afterwards.** On pictures this small, running the model
should sit comfortably inside the time an arm movement takes, but **that has not
been measured here and no figure is quoted**. One published comparison shows why
guessing is unwise: a model expressly designed to be small can take *seconds*
per picture on a laptop processor, while a larger model that somebody has taken
the trouble to convert for the machine's own accelerator runs in milliseconds on
the same class of machine. **What matters is whether anybody has done that
conversion work, and not how small the model is.**

### What it is good and bad at

What it is good at is that it separates glasses that overlap in the picture
without needing depth at all. It copes with reflections and highlights far
better than any threshold. It works on real transparent glassware, which nothing
else here does without new hardware. And it enters the existing code at one
function.

What it is bad at is that it says nothing in real distances and it cannot say
why it decided anything. It knows only the glasses it was trained on, so a kind
outside that range is one it outlines badly with no warning. And here it is more
machinery than the job needs, because comparing depths separates two glasses
standing a legal distance apart exactly, with a reason you can print.

Its failure modes are worth knowing because they are unusually quiet.

**It fails confidently.** A merged pair comes back as one mask with a high
score. When a geometric method merges, it leaves evidence behind — a footprint
far wider than any glass of that kind can be — and the circle fit catches it.
When a model merges, all it leaves is a number, and the number says it is sure.

**It goes out of date silently.** Add a kind of glass, change the proportion
ranges, or change the lighting, and the weights describe something that no
longer exists. Nothing in the repository says so, and the tests still pass.

**It gets in the way.** Every other method here can be changed and re-run in a
minute. This one puts a training loop between the change and the answer, and
that is paid on every experiment.

### When it would be the right choice

On the day the glasses stop being opaque, because then every geometric method
here loses its input at once. Also if the glassware becomes open-ended, because
the circle fit leans hard on knowing the kind's range of widths. Until then it
is a fallback worth knowing how to build, and worth not building.

---

## Amodal masks and learned association

> **Fails conditions 1 and 4.** It needs two networks rather than one, and the
> published model families for predicting hidden extents are built on
> real-image backbones and real datasets, several of them non-commercial. The
> simulator can supply exact labels for the hidden part, which is the
> encouraging half; the training cost on this machine is the other half.

*Learned, as the decider. Predict the whole extent of a partly hidden object,
not just its visible pixels, and learn to recognise the same object across
several viewpoints.*

### What it is

This approach has two halves, and each half has its own vocabulary.

The first half is about what a mask covers. Every segmenter named so far marks
only the pixels you can see, and that habit has a name. **Modal segmentation**
labels an object's visible pixels and stops where something else gets in front
of it. **Amodal segmentation** labels the object's *whole* extent, hidden part
included. Put one glass half behind another, and a modal model returns the
visible half of the back one, while an amodal model returns the whole footprint,
inferring the hidden part from what it can see. The word comes from psychology,
where *amodal completion* is the everyday business of reporting one cat behind a
railing rather than five slices of cat.

Why that matters here is arithmetic rather than aesthetics. Everything
downstream turns a mask into points on the table and fits a circle. **A mask cut
short by something in front of it gives a circle that is too small and in the
wrong place**, because the centre of the visible part is not the centre of the
glass. And both of those errors are silent, because a wrong footprint comes back
not as an error but as a plausible number.

The second half is **association**, which means deciding that a detection in one
picture is the same physical glass as one in another. With several stations, two
pictures each, and five glasses, there are dozens of detections and only five
objects. That is known as the **data association problem**, and it is a separate
job from finding the glasses.

### Why anyone does it this way

The reason is that a truncated footprint is the very failure this problem says
to watch hardest, wearing different clothes.

The problem statement says the dangerous failure is the *merged* pair, because
it does not announce itself. Now follow what happens when part of a glass is
hidden. The circle fitted to what remains comes back **narrower** than the glass
really is — and if enough is hidden, it comes back narrow enough to land at the
bottom of the kind's allowed range rather than outside it. So solution 2's
circle fit passes it in silence. **The wrongness has been hidden by the very
check that was supposed to catch it.**

For the second half, association, the classical answer is geometric, and
solutions 2 and 3 use it: two detections are one glass if their positions are
close and their heights agree. That fails exactly when a position is wrong
*because* the mask was truncated, which is geometry arbitrating with broken
numbers.

The learned answer ignores position altogether. The model turns each detection
into an **embedding**, which is a short list of numbers produced by a network
from that detection's pixels. Nobody chooses what the numbers mean. The network
is trained so that two views of one object land close together in that space and
views of different objects land far apart. The usual training signal is a
**triplet loss**, which takes an anchor, another view of the same object, and a
different object, and then pulls the first pair together while pushing the
second apart. So "is this the same glass?" becomes "is this distance small?".

The neighbouring field is **multi-object tracking**, and it supplies four useful
words. A **track** is an identity followed over time. A **cost matrix** prices
matching each detection to each track. A standard assignment algorithm picks the
cheapest one-to-one matching. And **re-identification** is the embedding half of
the job.

### How it would work here

**The models** are the difficulty. Predicting hidden extents is a small field
and most of it is research code, and the closest fits sit on a framework that is
shaped for a kind of graphics card this machine does not have. The route that
would work here is a standard two-stage instance model with a second output head
added for the hidden extent.

**The public datasets are mostly unusable**, partly because several are
non-commercial and partly because none of them holds glassware.

**The simulator supplies the data free, and that is what makes this practical.**
Render each glass alone against the empty table, and that silhouette is the
whole extent, exact. Render the whole scene, and that is the visible extent. The
difference between the two is the hidden part. There is no annotator, so there
is no annotator's error, and the same renders label the association half for
nothing as well.

**The pipeline** would then run the model on each picture and fit the circle to
the *whole* extent rather than the visible one, which is existing code being fed
an untruncated footprint. Then embed every detection and solve the matching
across pictures.

### The feedback loop

The useful output of the matching is not the match itself but the **margin** on
it.

Suppose a detection sits almost exactly as far from one candidate as from
another, while two views of the *same* glass normally sit far closer together
than either. Then the match is a coin toss wearing a number, and the right
response is to say so.

**An uncertain association is a reason to take one more picture, from a
viewpoint where the two candidates would look different.** That is solution 3's
next-best-view machinery with the score swapped: instead of scoring unknown
volume, score the **predicted margin**, by predicting for each reachable
viewpoint how the two candidates would look and preferring the one that puts
their embeddings furthest apart.

Here is the intuition for what that score would choose. Two glasses of
noticeably different heights look **identical** from the top, because from up
there you see only their footprints. From the side, their difference in height
is the most obvious thing about them. So the loop picks a view from the side.
Cap it at a couple of extra looks, then report the pair unseparated.

### A worked example

The camera works from the top. Glass A stands well in front of glass B and in
line with the camera, so A hides roughly a fifth of B's footprint.

*With the visible mask only.* What is left of B is a crescent rather than a
disc. Fit a circle to the crescent and it comes back **narrower than B really
is** — and, this is the part that bites, narrow enough to still be **inside**
the kind's allowed range. So the check passes. Worse, the centre of a crescent
is not the centre of the disc it was cut from, so the position comes back wrong
too. The result is one glass, of a plausible width, in a place it is not.

*With the whole extent, inferred.* The model returns the complete disc, hidden
part included. Its width comes back very close to the truth and its centre
likewise, **and it is flagged with how much of it was inferred rather than
seen** — which is the honest part, and the part the visible mask cannot offer.

*The association.* Another station sees B with nothing in front of it, and its
embedding sits far closer to the first station's truncated B than to any other
glass, so that match is clear. The awkward pair — two glasses of nearly
identical proportions — come back almost equidistant, which is the coin toss
above. **One look from the side, where their difference in height shows,
separates them decisively.**

### What it is good and bad at

What it is good at is that it attacks the truncated-footprint failure, which
nothing else here detects at all, and it turns association into evidence rather
than assumption. It also gives numbers to be uncertain about: the margin drives
the extra look, and the fraction of a footprint that was inferred marks a
mostly-guessed footprint as doubtful.

What it is bad at is specific to this cell, and it is a real objection. **Every
glass is the same kind.** An appearance embedding on four to six nearly
identical objects has very little to work with. What signal exists comes from
the proportions drawn at random inside the kind's range, plus incidental marks
and lighting — and in a clean render of untextured glasses there may be almost
none. That is a real reason to doubt whether the embedding half earns its keep
here.

Its failure modes are worth naming. **The completion is invented and looks
measured**, because a predicted extent for a glass that is almost entirely
hidden is almost entirely guesswork, yet it comes back as a clean, confident
outline, and without the inferred fraction reported alongside it nothing
whatever says so. There can also be a **systematic completion bias**: if the
renders over-represent one occlusion geometry, then every footprint is wrong the
same way, which is much harder to spot than random error. And there can be an
**identity swap**, where two glasses matched the wrong way round give two
confident positions, each belonging to the other — likeliest when the margin is
miscalibrated, because if you measure within-object distance only on clean
renders then every match looks confident and the loop never fires.

### When it would be the right choice

When objects genuinely hide each other and there are many viewpoints to
reconcile: a bin, a crowded shelf, a tray of glassware pushed together. Where
occlusion is the normal case rather than the accident, a model that predicts the
hidden part is not extra machinery — **it is the measurement**. It is also the
natural partner for the verifier on real glassware, where no depth is left to
cluster.

For this cell it is far more than the problem needs. Four to six glasses stand a
comfortable distance apart on a bare table, and most pictures show every glass
whole. Where one does not, solution 3 moves the camera a short way and the
occlusion goes away, which is seconds of arm time against two trained models. It
earns its place when the arm *cannot* reach a clear viewpoint, and here it
usually can.

---

## An active-vision policy

> **Fails condition 4.** Everything it needs is inside the simulator, which is
> what makes it frustrating. The cost is throughput: thousands of simulator
> resets and days of machine time, and the usual escape — a simulator running
> on a graphics card with thousands of worlds at once — is exactly what this
> machine cannot do. *A supervised version of the same idea, which predicts whether a
> viewpoint will pay off rather than learning a policy, does fit, and it is in
> the main overview as [solution 6](06-learn-which-viewpoints-pay-off.md).*

*Learned, as the decider, and a closed loop by construction. A policy takes the
current belief about the table and outputs where to point the camera next.*

### What it is

A **policy** is a function from what the robot knows to what it does next. Here
that means the belief about the table going in, and the next camera pose coming
out. Nobody writes the rule inside it; the rule is a pile of numbers, the
**weights**, fitted from experience.

There are two ways to fit them, and the difference matters a great deal for
cost.

**Reinforcement learning** lets the robot try. It looks somewhere, and
eventually is handed a number, the **reward**, saying how well the whole attempt
went. Thousands of attempts later, actions that tended to precede high reward
have become more likely. Nobody ever says which individual look was good, and
that is inferred from the totals — which is precisely why it takes so many
attempts.

**Imitation learning** shows it the answer instead. Run an expert, whether a
person with a joystick or a slow method already known to be right, record what
the expert saw and did, and fit the policy to reproduce the choice. This is
called **behaviour cloning**, and it is ordinary supervised learning. It needs
no reward at all, and it can never beat the expert it copied.

### Why anyone does it this way

Two reasons, and the second is the stronger one.

The first is speed. Scoring a viewpoint properly is expensive while choosing one
is cheap. Solution 3's score casts a ray per pixel into an occupancy map for
every candidate, whereas a policy does one forward pass, and you pay the cost
once, offline.

The second is reach. A geometric score exists only where somebody can write one
down. Here they could. Where the cue is subtler, nobody can.

### How it would work here

**The observation** would deliberately not be the raw picture, because
appearance is exactly what will not transfer out of the simulator. Instead, feed
the policy what the geometry has already produced: the glass zone as a coarse
grid of cells, each marked empty, occupied or never-seen; one row per cluster
holding its position, its fitted width, how many stations saw it and whether
that width is inside the kind's range; and how many looks remain in the budget.
That is a few hundred numbers in total, which is small enough to train on a
processor.

**The action** could in principle be a camera pose, which is six numbers. In
practice, do not. Take a **fixed list of candidate poses** — a ring of
directions round the target, multiplied up by a few heights — and let the action
be a choice among them, plus one extra action meaning **stop**.

Making the action discrete is the sane engineering choice here, for a specific
reason worth understanding. Every candidate in a fixed list can be checked once
against the arm's reach and against whether any joint angles reach it, so the
policy **cannot name a pose the arm will not hold**, because the impossible ones
are masked out before it chooses. A continuous six-dimensional space would spend
most of its exploration pointing the camera at mid-air.

**The reward is the hard part**, and this is where the approach becomes fragile.
The obvious reward is this problem's own score sheet: a point per glass
correctly separated, a point off per merged pair, and a small penalty per look
so that dithering costs something. But that needs to know which glasses were
really there. The simulator writes down everything it spawned, so in simulation
the reward is exact. **Reality has no such file.** You could pay for a proxy,
such as the circle fit passing — but a policy optimises exactly what you pay
for, and one paid for a passing fit learns viewpoints from which the fit passes,
and not viewpoints from which the answer is right.

**How long it would take** is the condition this approach fails. An episode is a
handful of looks, each an arm movement of a few seconds, plus a reset — call it
some tens of seconds of wall clock running without a display, which is a figure
to measure rather than guess. Multiply that by the tens of thousands of episodes
these methods want and it is **days** on one process, or a fraction of that with
several in parallel. Meanwhile a single learning step takes milliseconds. So
**the simulator is the bottleneck, by orders of magnitude**, and every
optimisation effort belongs there rather than in the learning code.

### The feedback loop

This is not a solution with feedback bolted on. It **is** the loop, and it runs
in five steps.

First, **observe**: run the survey from the top, cluster, fit circles, and build
the observation. Second, **choose**: the policy returns one of the candidate
poses, or `stop`, and the ones failing reach or joint angles were masked out
before it chose. Third, **move**: plan and execute, taking a few seconds, and if
the plan fails, mask that candidate and go back to choosing. Fourth,
**re-observe**: take the pictures, fold the new points into the same clusters,
fit again, and rebuild the observation. Fifth, **stop** on the stop action, or
when the budget of looks runs out, with clusters still failing their fit
reported as unseparated.

Two properties of that loop are deliberate. The belief is **cumulative**,
because each look adds points to the same clustering rather than starting again.
And the **budget is external rather than learned**, so a policy that never says
stop wastes a fixed number of looks rather than running for ever.

### A worked example

Glass A stands about halfway out across the arm's reach. Glass B stands further
out, at the smallest gap from A the cell allows. B sat behind A from most of the
survey stations, so the merged cluster fits a circle about twice as wide as any
glass of this kind can be.

Two of the candidate directions lie along the line joining A and B, which are
the worst possible directions, and at every height they fail on **reach** alone,
because standing back from A along that line puts the camera either folded in
against the base or stretched out past the far limit. So they never even reach
the policy.

The policy picks the candidate square across the line joining A and B. One
movement, a few seconds. The cluster resolves into two discs, both widths inside
the kind's range, so the policy says stop and the episode collects its reward.

**Now the comparison that matters.** Solution 3's arithmetic chose that *same*
viewpoint, before the planner was asked anything at all — and it can say
**why**: from the blocked direction, B would cover a large part of the width of
the frame directly behind A. The policy chose the same pose and can say nothing
at all about its reasons beyond a number. Same answer, and only one of the two
can be audited.

### What it needs

A training environment wrapped round the existing cell, where resetting spawns
four to six glasses, stepping moves the arm and re-runs perception, and the
reward reads the spawn record. **That wrapper is the real work**, because it
must reset the simulator thousands of times without leaking processes. Then a
standard reinforcement-learning library, and days of machine time. No labelled
pictures, and no dedicated graphics card.

### What it is good and bad at

What it is good at is run-time speed, because choosing is one forward pass,
which is microseconds against the seconds a movement costs. It can also use cues
nobody wrote down, where a viewpoint pays off for reasons the circle fit misses.
And it optimises the thing itself, meaning merges and splits, where information
gain is only a proxy for them.

What it is bad at, first, is that **it cannot explain itself**, and here that is
practical rather than philosophical. This problem says the failure to watch
hardest is the merged pair, because it looks plausible downstream. A policy that
stops one look early produces exactly that failure, and reports confidence while
doing it.

It is also more machinery than this problem has earned. What it would learn is
computable: the kind is known, the range of widths is known, and occlusion is a
line-of-sight test. **Where a geometric score exists and is auditable, a network
trades the explanation for a speed-up**, and here the explanation is worth more.

Its failure modes are worth naming, because two of them are expensive to
discover.

**Reward hacking.** Charge too much per look and the policy stops at once and
eats the merge penalty; charge too little and it burns its whole budget every
run. That balance is not derivable, and each attempt at it costs another
training run.

**Drift out of the simulator.** This is milder here than for tasks involving
contact, because there is no friction, no deformation and no impact, and what
matters is straight lines from camera to object, which the simulator gets right.
Feeding clusters rather than pixels removes most of the appearance gap too. But
the policy also learned this simulator's depth noise and the way its readings
drop out at glancing angles — and a real camera that loses the far rim of a
glass at a steep angle shifts **every** observation the policy ever sees.

**Silent staleness.** Change the kind of glass, the lighting, or the list of
candidate directions, and the weights describe a cell that no longer exists,
while the tests still pass.

**Real glassware removes the input** altogether, because the observation is
built from clusters, and clusters come from depth that real glass does not
return.

### When it would be the right choice

When the doubt stops being a short list. Here, one known kind and a known range
of widths make "one glass or two?" arithmetic, and auditable. Problem 4 has
several kinds, some never measured, and the union of their ranges is wide enough
that the circle fit stops deciding much. A policy that had learned which looks
resolve ambiguity would have something real to offer there.

One shape is worth keeping even so. Solution 3's score is a working expert and
it runs in simulation for free, so **behaviour cloning against it** gives a fast
policy with no reward design at all — at the price of a policy that can only
approach what it copied, having lost the explanation that made the original
worth having.

## What to take from all four

Reading these four together, one pattern is worth carrying away, because it
applies well beyond this project.

Each of these approaches is safe or unsafe depending on **where in the pipeline
it sits**, and not on how good the model is. The first one is safe because a
model proposes and arithmetic checks. The last one is the least safe, because
the policy decides and nothing checks. The two in the middle sit between those,
because each produces a number that something else can test, but each can also
produce a plausible wrong number that nothing catches.

So the question to ask of any learned component is not "how accurate is it?" but
**"what checks it, and would that check notice this particular way of being
wrong?"** That question is what puts three of these four behind a gate, and it
is what the main overview's solutions are arranged around.
