# Problem 2 — how it would be solved

## Introduction

[`problem.md`](../problem.md) says what is being asked for. This document says
how it would be answered, and it is the way into the nine solutions that follow
it. It explains the three difficulties the problem sets, the words all nine
documents share, the one question worth asking of any solution that contains a
trained model, and the combination of solutions this project recommends. By the
end you will know which document to read next and why, and you will know that
the answer to this problem is a combination of methods rather than a choice
between them.

Each of the nine has a full document of its own, so this one does not repeat
them. For each it says what the method is for, which difficulty it attacks, and
when it is worth reaching for.

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the two places the camera works from, from the top and from the side, all four
> sensors, and the words this project uses them with.

## Where we are

The arm has photographed a table with four to six glasses on it. They are all of
one kind, the kind is known, and they are opaque, so the depth camera sees them
perfectly well.

What it has to produce is one set of pixels per glass, a place on the table for
each, a rough width for each, and two honest statements: which glasses it could
not separate, and where it could not have seen a glass at all. It does not pick
anything up and it does not measure a shape. Those come later, and they depend
on this being right, which is why a wrong answer here is expensive.

Two properties of the arrangement create every difficulty below, and both are
deliberate choices in the problem statement.

**The kind is tapered and its range of sizes is wide.** Tapered means the rim is
wider than the base, so the glass opens outwards as it rises. The range runs
from a tapered shot glass at one end to a large tapered glass at the other, so
two glasses of the same kind can differ several times over in height.

**The glasses stand apart, but not comfortably apart.** There is a guaranteed
smallest gap between centres, and it is wide enough that even the two widest
glasses of the kind leave a strip of bare table between their rims, so nothing
ever touches. However, that strip is narrow, and a later section explains what
that costs.

## The one effect behind everything

Before the three difficulties, one effect needs naming, because all three of
them come from it.

![Why splay happens](../../../images/splay-why-it-happens.png)

From the top, the arm lifts the camera high above the table and points it
straight down. From up there a glass's outline is not drawn over the glass,
because the rim is nearer the lens than the table is, so it is drawn larger and
further out from the middle of the picture. The outline therefore leans
outwards, away from the point directly below the camera, and **the taller the
glass, the further out it is thrown**. This project calls that effect **splay**.

Splay has a second property that is less obvious and that the solutions lean on
heavily. It is a **radial scaling** about the point directly below the camera,
meaning it multiplies distance-from-that-point and size by the same factor. A
scaling about a point leaves angles about that point unchanged, so splay never
alters how wide a glass looks *as an angle*; it only decides how far out along
its own direction the outline lands. That is what turns the difficulties below
from things you can describe into things you can compute.

## The three difficulties

The difficulties are ordered here by how dangerous they are, which is not the
order in which they are easiest to notice.

### A glass can be missing from a picture altogether

Put a tall glass somewhere near the middle of the picture and a short one beyond
it. The tall one's outline sweeps a long way outwards and the short one's barely
moves, so the sweep can pass over the short glass and cover it entirely. The
short glass then produces no pixels at all, and the picture holds one glass of
an entirely legal width with nothing wrong about it.

This is the worst of the three, and the reason is worth stating plainly. **Every
check in this project is a check on something that was found.** A width can be
compared against what the kind allows, a fitted circle has a residual, and a
group can be asked how many stations saw it. None of those exists for a glass
that produced no pixels, so none of them can fire.

### Glasses merge in the picture even when they are apart on the table

![Overlapping in the picture is not touching on the table](../../../images/problem-2-merged-in-the-picture.png)

If the tall glass's outline reaches the short one without covering it, the two
outlines touch, and the step that groups touching pixels hands back a single
patch. One patch means one glass to everything downstream.

This failure is at least **loud**, because the patch is wider than any glass of
the kind can be, so something can notice. But noticing is not separating, and
the projection has already thrown away what would be needed to separate them,
which is which pixels were near the camera and which were far. The fix is
therefore not a better grouping rule in the picture; it is to stop grouping in
the picture.

### The camera can no longer stand wherever it likes

![Where the camera may stand, once there are several glasses](../../../images/problem-2-where-can-the-camera-stand.png)

The camera is on the wrist, so choosing where the camera stands means choosing
where the whole arm stands. A viewpoint therefore has to clear three things at
once: the line of sight, because a glass behind the target lands in the same
picture; the reach, because standing well back from a glass near the edge puts
the camera outside the working area; and the motion planner, because the path
there may cross a glass that is in the way. Each of those alone is survivable,
but together they can leave a glass with no usable viewpoint at all.

## The words, first

Five terms run through all nine documents, and three of them are used loosely
almost everywhere else, so it is worth fixing them before the solutions start.

A **pixel** is one dot in a picture, and a **mask** is a picture of the same
size in which every pixel is simply yes or no. Here, yes means that the pixel is
part of a glass.

**Connected components**, also called a flood fill, is the step that turns a
mask into separate objects. Take a yes pixel nobody has visited, spread out to
every yes pixel touching it, call that patch one object, and then repeat. It
answers exactly one question — *are these pixels joined?* — and it never asks
anything else, which is the root of the second difficulty above.

A **point cloud** is what you get when every pixel that has a depth reading is
turned into a point in the room. The pixel says which direction the camera was
looking, the depth says how far along that direction to go, and the camera's
pose says where that direction starts.

**Segmentation** is the word that carries three different jobs, and only one of
them answers this problem.

![Three things the word segmentation is used for](../../../images/problem-2-three-answers.png)

**Detection** puts a rectangle round each object, so two overlapping glasses
give two overlapping rectangles and the pixels in the overlap belong to both.
**Semantic segmentation** labels every pixel with a class, so every glass pixel
comes back labelled "glass" and nothing says which glass, which makes two
overlapping glasses into one region — exactly the merge this problem exists to
prevent. **Instance segmentation** labels every pixel with a class *and* with
which object it belongs to, so five glasses come back as five separate masks.

This problem asks for instance segmentation, and anything that gives less than
that has not answered it.

## Three families, and what "hybrid" means

With the words fixed, the nine can be grouped. Every one of them belongs to one
of three families, and the difference between the families is not quite the one
most people expect.

**Programmed.** You state the rule and the computer applies it. There is no
training data, no file of weights and no graphics card. It runs in about a
millisecond, it works on an object it has never seen before, and when it fails
you can usually find out why by printing one number. Its limit is that somebody
has to be able to write the rule down, and for some questions nobody can.

**Learned.** The behaviour comes from numbers fitted to examples rather than
from a rule anybody wrote, so it can do things nobody knows how to state. It
pays for that with a training set, a file of weights that has to be kept in step
with the world, hardware to run it on, and an answer that cannot explain itself.

**Hybrid.** Both together, arranged so that the learned part sits inside
something checkable.

### The question to ask of any hybrid

The interesting question about a hybrid is not how much of it is learned. It is
**where the learned part sits**, because that is what decides what happens when
the model is wrong, and a model is wrong sometimes by construction.

![Where the learned part sits decides what happens when it is wrong](../../../images/where-the-learned-part-sits.png)

There are four positions it can occupy, and only the first is what most people
picture when they hear that a model was used.

**As the decider.** The model takes the input and its answer is the answer. A
wrong answer is acted on, because nothing further down the pipeline is in a
position to disagree with it.

**As a proposer.** The rules find the candidates and hand the hard ones to the
model, the model suggests something better, and the rules then check the
suggestion. A wrong suggestion is rejected by arithmetic, so the system falls
back to what it already had.

**As a ranker.** The rules generate every candidate *and* reject the unsafe
ones, and the model only puts the survivors in order. A bad ordering costs one
wasted attempt and cannot cost anything worse, because every candidate had
already passed the safety checks before the model saw it.

**As a verifier.** The rules act, and the model's job is to check what happened.
A wrong check costs one extra measurement.

The last three share something worth naming, because it is the whole argument
for hybrids in a machine that moves: **the learned part's mistakes are limited
by something that does not need the model to be right.** That is not a claim
about how good the model is. A better model makes failures rarer; only the
arrangement puts a ceiling on how bad they can get.

One practical consequence is worth having in mind while reading. A hybrid is
usually *cheaper* than a fully learned solution rather than more expensive,
because the learned piece has one narrow job. Learning "is this one object or
two?" needs a small fraction of the data that learning "find all the objects"
needs, and it trains on an ordinary laptop.

## Feedback: choosing what to measure next

The second theme running through the nine is that **the number of measurements
does not have to be decided in advance.**

![Deciding what to measure next, rather than measuring once](../../../images/open-and-closed-loop.png)

Most pipelines are open loop. They take the pictures, work everything out, and
act. The number of pictures is fixed before the run starts, so if one object
turns out to be unclear then unclear is how it stays, and everything downstream
inherits the doubt without ever being told there was one.

A closed loop spends its measurements where they are needed. It takes a picture,
works out what is settled and what is not, and when something is not it asks a
different question: *where would I have to look for this to become clear?* Then
it goes and looks there, and repeats. This is the same shape as any control loop
in physics, where the next action depends on the error measured after the last
one.

Three things are needed to make that work, and a solution with only two of them
is not really a loop.

The first is **a measure of doubt**, meaning something that separates settled
from not sure rather than always producing an answer. A method that cannot be
unsure has nothing to drive a loop with.

The second is **actions that could reduce it**, meaning a set of measurements
the arm could actually take together with some way of guessing which of them
would help.

The third is **a budget**. Every extra look costs arm time, which is by far the
most expensive resource here, because moving the camera and letting it settle
costs seconds while running any of these models costs milliseconds. So the loop
has to stop, and the sensible rule is to stop when nothing is unclear or when
the budget is spent, reporting whatever is still doubtful rather than guessing
at it.

That third point reverses the instinct most programmers bring with them. **The
thing to save here is not computation. It is the number of times the arm has to
move.**

## Everything here runs in simulation

One rule has been applied to all nine, and it is worth stating before the list,
because it removed some otherwise obvious candidates.

**A solution appears in this document only if everything it needs can be
produced by the simulator on the machine this project runs on.** That machine
has no dedicated graphics card, there is no robot on a bench, and there is no
real-world data. Four conditions follow from that.

There may be **no artefact from outside**, because any model has to be trainable
from what the simulator renders, and a downloaded file of weights fitted to
photographs of the real world is not reproducible here however good it is. There
may be **no sensor the simulator does not have**, since this cell has a depth
camera, contact sensors in the gripper pads and a force sensor at the wrist, and
anything else is a purchase order rather than a solution. There may be **no
graphics card it has not got**. And training must take **hours rather than
days**, because a method needing a week of continuous simulation cannot be
iterated on, and a method you cannot iterate on will not get debugged.

That rule is not a view about learned methods. Several good answers fail it, and
they are written up in full in
[`learned-with-hardware.md`](learned-with-hardware.md) beside the condition each
one fails. None of them needs a different algorithm to become usable; they need
a different setup.

The rule does have one consequence worth seeing coming. It pushes the learned
solutions towards **small models trained from scratch on synthetic data**, and
away from the fine-tune-a-large-model recipe that is the default advice
everywhere else. For a cell that handles one kind of object under one lighting
setup through one camera, that turns out to be less of a sacrifice than it
sounds.

There is also a practical gradient across the nine that belongs here rather than
being discovered later. The first three need nothing added to the environment at
all. Everything from the fourth onwards begins by adding a dependency, and the
learned ones add a large one, which is part of their cost in a cell whose
recommended answer is a page of arithmetic.

## The nine, at a glance

| # | Solution | Family | Where the model sits | Which difficulty it attacks |
|---|---|---|---|---|
| 1 | [Split the blob in the picture](01-split-the-blob-in-the-picture.md) | programmed | — | the merge, mainly from the side |
| 2 | [Cluster on the table](02-cluster-on-the-table.md) | programmed | — | the merge, **and where nobody could have seen** |
| 3 | [Move the camera](03-move-the-camera.md) | programmed | — | no usable viewpoint, and covering unsearched places |
| 4 | [Learned doubt steers the next picture](04-learned-doubt-steers-the-next-picture.md) | hybrid | ranker | which look to spend the budget on |
| 5 | [Is anything hiding there?](05-is-anything-hiding-there.md) | hybrid | verifier | which unsearched place is likely occupied |
| 6 | [Learn which viewpoints pay off](06-learn-which-viewpoints-pay-off.md) | hybrid | ranker | which look to spend the budget on |
| 7 | [A segmenter trained from scratch](07-a-segmenter-trained-from-scratch.md) | learned | decider | finding glasses with no depth readings |
| 8 | [Per-pixel votes for the centre](08-per-pixel-votes-for-the-centre.md) | learned | decider | separating glasses that touch |
| 9 | [Self-supervised from the arm's own movement](09-self-supervised-from-the-arms-own-movement.md) | learned | decider | separating glasses with no labels |

## The three programmed solutions

### Solution 1 — split the blob in the picture

Read the bottom edge of a patch and find the flat stretches along it, because a
glass rests on the table in exactly one place, so each flat stretch is one glass
standing on it. With the camera at the side and held level, how far below the
horizon a base is drawn depends only on how far away the glass is, which turns
the bottom edge of a patch into a set of distances that can be read straight off
the picture.

Its appeal is that it needs **no depth readings at all**, which matters because
real glassware returns none. Its limit is that it cannot see a base that is
hidden, and with the wide range of sizes a large glass can hide a small one so
completely that the method reports one glass and is right about everything it
was actually asked.

→ [the full document](01-split-the-blob-in-the-picture.md)

### Solution 2 — cluster on the table

Stop deciding which pixels belong together by looking at the picture, and decide
it by looking at where they are in the room instead. Every pixel with a depth
reading becomes a point, the points are dropped onto the table, and dots close
together are chained into one glass. A circle fitted to each group then gives a
position and a width, and checking that width against the range the kind allows
is what keeps the whole thing honest.

**This solution now has a second half, and that second half is the reason the
problem was changed.** It also works out which parts of the table could not have
been seen. Because splay is a radial scaling and the glasses that were found
have known positions, widths and heights, the region each found glass hides is a
wedge with a closed form, and any part of that wedge large enough to hold the
smallest glass of the kind is reported as an **unsearched patch**. That makes
this the only solution here that can say anything at all about a glass nobody
has seen.

→ [the full document](02-cluster-on-the-table.md)

### Solution 3 — move the camera

If you cannot see something from where you are standing, walk round. The work is
in choosing where to walk to, and three tests decide it, cheapest first: the
arm's reach, then whether another glass would share the frame, then whether the
planner can find a path. Everything that can reject a pose is arithmetic, and it
all runs before the planner is asked anything.

It now serves two kinds of request rather than one. A **doubtful glass** has a
position, so the viewpoints worth trying are the ones around it. An **unsearched
patch** has no glass in it at all, so the question becomes which fewest camera
positions between them see every patch. That is the set cover problem, and its
greedy method is provably close to the best possible, which is why the solution
chooses positions for all the patches together instead of one patch at a time.

→ [the full document](03-move-the-camera.md)

## The three hybrids

### Solution 4 — learned doubt steers the next picture

Keep solution 3's structure exactly as it is, and replace only the rule that
orders the surviving candidates with a learned estimate of how much doubt a look
would remove. The geometry still generates the candidates and still holds every
rejection, so a wrong prediction costs one wasted look and nothing more.

Its most useful idea is that **the doubt has to be a list of measurements rather
than one number from the model**, combined in such a way that a confident model
cannot silence a geometric complaint. That list now has a fifth entry, the
unsearched area, and without it the loop spends its whole budget improving
glasses it can already see while an unseen one goes unmentioned.

→ [the full document](04-learned-doubt-steers-the-next-picture.md)

### Solution 5 — is anything hiding there?

The geometry can say that a patch **could** be hiding a glass. It cannot say
that one probably **is**, because the evidence bearing on that question is
several weak pieces at once, and weighing several weak pieces is exactly what a
fixed threshold does worst.

Two things about it are worth reading even if it is never built. This verifier
cannot be shown pixels even in principle, because the thing it is asked about is
defined by the absence of pixels, which is a useful reminder to ask what
evidence exists before asking what a model should look at. And its strongest
single input comes from the **problem statement** rather than from the camera:
the table holds four to six glasses, so finding four means two are somewhere.

→ [the full document](05-is-anything-hiding-there.md)

### Solution 6 — learn which viewpoints pay off

Score a candidate viewpoint by the thing actually wanted, which is the chance
that a picture from there splits an ambiguous group or finds a glass that was
not in the list before. That question has an exact answer the simulator can look
up, so choosing a viewpoint becomes ordinary supervised learning with labels
that cost nothing.

Its best property is the choice of label. It records *did the answer change*
rather than *was the answer correct*, and the first of those needs no ground
truth, so it can be read on a real table as well as in simulation. Every look
the arm ever takes becomes another labelled example.

→ [the full document](06-learn-which-viewpoints-pay-off.md)

## The three learned solutions

### Solution 7 — a segmenter trained from scratch

Train a small network from a random start, on pictures the simulator renders and
labels for nothing, to say at every pixel whether that pixel is glass. The cell
is narrow enough that a small network is enough, and the document's most useful
sections are the ones about the traps: why the obvious measure of success
rewards saying nothing at all, and an arithmetic check worth doing before
training rather than after.

It can say which pixels are glass but not which glass they belong to, and like
everything that works from pixels, it is blind to a glass that produced none.

→ [the full document](07-a-segmenter-trained-from-scratch.md)

### Solution 8 — per-pixel votes for the centre

Ask each glass pixel for an arrow pointing towards the middle of its own glass,
and then count the places the arrows point at. **Nothing has to find a boundary,
so nothing can get a boundary wrong**, which is why this is the only method here
that separates glasses that touch.

The wide range of sizes makes it valuable here, because partly hidden glasses
are the normal case and a crescent of pixels still votes towards the right
centre. It is still blind to a glass that is hidden completely, because a glass
with no pixels casts no votes.

→ [the full document](08-per-pixel-votes-for-the-centre.md)

### Solution 9 — self-supervised from the arm's own movement

The arm knows exactly how it moved the camera, so the geometry between two
pictures of a still scene is a training signal that costs nothing. Points on one
glass shift together, points on the glass behind shift by a different amount,
and that agreement is the label.

It is the only learned solution here whose training would survive being moved to
real hardware, because its supervision comes from the joint encoders rather than
from the simulator's private record of the scene. It is also more machinery than
this cell needs, because the cell already has a depth camera that measures
directly what parallax is being trained to infer.

→ [the full document](09-self-supervised-from-the-arms-own-movement.md)

## The decision, which is a combination

The change to the problem changed this section more than any other, and the
short version is that **there is no longer a single solution to choose**.

The reason is that the three difficulties need different kinds of answer, and no
single method supplies more than one of them. A method that places what it can
see cannot say what it could not see, and a method that says what it could not
see cannot go and look.

**Build solution 2 first, both halves of it.** The clustering places every glass
the pictures contain, and it is a small amount of arithmetic on work the project
already does. The blind-region arithmetic is a similar amount again, and it is
what lets a run say where it has not looked. A run with only the first half is
confidently wrong on exactly the failure the problem says to watch hardest.

**Build solution 3 next, including the covering step.** Without it, solution 2's
doubts and unsearched patches are reported and nothing acts on them. With it,
the arm can go and settle them, and the covering step is what stops the arm
paying one movement per patch when a single position often serves several
patches at once.

**Then stop, and measure.** Measure how often an unsearched patch actually turns
out to have something standing in it, and how often the printed rule in solution
3 picks a viewpoint that settles the doubt on its first try. Those two
measurements decide whether anything else on this list is worth building, and
both of them are cheap to take.

Everything beyond those two is an **ordering improvement rather than a new
capability**. Solutions 4, 5 and 6 all leave the answers exactly as they were
and change only which look the budget is spent on, which is worth having when
the budget binds and worth nothing when it does not — and that is precisely what
the measurement above tells you.

Solutions 7, 8 and 9 are for a different world rather than a better version of
this one. They earn their place on the day depth readings stop working, which is
the day the glasses become real glass, or on the day the glasses are allowed to
touch. Until one of those happens they are answers to questions this cell is not
asking.

## Where the recommended combination can fail

Naming the failures of the chosen answer is more useful than listing its
strengths, and there are four worth carrying into the individual documents.

**A glass hidden behind a glass that was itself hidden** is outside the reach of
the blind-region arithmetic, because that arithmetic reasons from the glasses it
found. Across every legal arrangement that was checked, this does not arise in
this cell, because the survey stations between them see every glass. It is,
however, exactly what to watch on the day somebody removes a station or widens
the zone the glasses may stand in.

**A badly measured glass casts a badly computed wedge.** Both the line-of-sight
test and the blind-region arithmetic take their input from fitted circles, so a
footprint measured from an arc rather than from a whole circle produces a wedge
in the wrong place. A small share of glasses is seen from only one station, and
those are exactly the glasses whose fitted circle is wrong in a plausible way,
so the flag that marks them is the defence and it is not optional.

**The grouping distance depends on two numbers this solution does not own.** How
close two measured dots have to be before they count as the same object sits in
a window whose ends come from the widest rim the kind allows and the guaranteed
gap between centres, and both of those live elsewhere. The window is wide today,
so the value is easy to get right and just as easy to leave behind on the day
somebody widens a kind. Deriving it and printing both ends costs nothing and is
the only version of this that stays correct.

**Two glasses that genuinely touch** leave no strip of bare table at any
grouping distance, so distance has nothing left to say and only the fitted width
can suspect that something is wrong. That case is [problem
3](../../problem-3/problem.md)'s business, and it is where solution 8 would
begin to earn its keep.

## How it would be solved

← [The problem](../problem.md) · [The ones that need more than a
simulator](learned-with-hardware.md) · [Problem 3 — moving them
apart](../../problem-3/problem.md) →
