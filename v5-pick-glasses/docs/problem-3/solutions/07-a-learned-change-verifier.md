# Solution 7 — a learned change-verifier

*Hybrid, with the model as a verifier. After each push the arm has a picture of
the glass before and a picture of it after. A small trained model compares the
two and answers the three questions the geometry answers badly: did the glass
move as intended, did something else move, and has anything fallen over.*

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the places the camera works from, all four sensors, and the words this project
> uses them with. What follows is only what is specific to this solution.

## Introduction

This document explains the first learned component worth adding to problem 3,
and why it belongs at the end of a push rather than anywhere else.

[Solution 3](03-plan-feel-look-again.md) already pushes a glass and then looks
again. Its last step is a comparison: the arm re-runs problem 2's separation
over fresh overhead pictures and checks whether the glass ended up where it was
sent. That comparison answers one question well and two questions badly, and one
of the two it answers badly is the failure [the problem](../problem.md) says to
watch hardest. A toppled glass cannot be stood back up by anything in this
project. Everything downstream carries on moving beside it.

This solution replaces only the looking. The planning, the destination search,
the tipping check and the push itself all stay exactly as written. The last step
becomes one question put to a small trained model: what happened?

By the end you will understand why a camera looking straight down is the worst
place to ask that question from, how often the overhead answer is genuinely
unavailable rather than merely noisy, what the model is shown instead of raw
pixels alone, and why its most useful answer is the one that decides nothing at
all. You will also understand why this solution exists: the push height is
computed from a number nobody in this cell measures, and this is the component
that catches the consequence when that guess was wrong.

Every number below was measured by
[`make_07_images.py`](../../../images/generators/problem-3/make_07_images.py),
which prints what it finds. It reads from two places and nowhere else. For
anything about the kind's range it draws four hundred glasses with
`family("tapered_glass", 400, 0)` from `work_cell.glasses.shapes`. For anything
about a crowded table it calls `scene(seed)` in
[`problem-3-sim/bench.py`](../../../problem-3-sim/bench.py), which is the
authoritative generator for this problem, and it uses that file's own room test,
its own jaw and its own definition of a fallen glass. Nothing here is estimated.

## The word, first

A **verifier** is a small decision-maker placed after work that something else
has already done, whose only job is to say whether that work came out right. It
does not do the work. It cannot choose what work to do. It looks at the result
and at the evidence about the result, and it returns a judgement.

That arrangement is chosen deliberately, and the reason is about damage rather
than about accuracy. A model that plans the push decides where a glass goes,
which means a bad model can break something. A model that checks the push
afterwards can only be wrong about a thing that has already happened. The worst
a wrong verdict costs here is a few seconds of arm movement, or a run stopped
when it need not have been.

[Problem 2's solution 5](../../problem-2/solutions/05-is-anything-hiding-there.md)
uses the same pattern on a different question, and the two documents mean the
same thing by the word. There the geometry works out where an object could be
hiding and the verifier says whether one probably is. Here the geometry works
out where a glass should have ended up and the verifier says whether it did.
Both return a third answer as well as yes and no, both mean the same thing by
it, and the section on the feedback loop below says what that third answer is
for.

## The three questions a push leaves behind

Start from what solution 3 already knows when a push finishes.

It knows where the glass stood before, because problem 2 measured it. It knows
how wide the glass is across its widest part, for the same reason. It knows
where it sent the glass, because it computed that destination itself and checked
it against four tests. It knows where the fingers first touched the glass,
because the push is a guarded move and contact is a measurement. And it has a
fresh overhead picture, taken from a pose the arm can return to but not exactly.

Three questions have to be answered from that, and they are not equally hard.

**Did the glass move as intended?** This one the geometry answers honestly. The
separation stage fits a footprint to the glass, and the distance between the old
footprint and the new one is a number. It will not be exact, but it is a real
measurement of the thing being asked about.

**Did anything else move?** This one the geometry answers badly. There are four
to six glasses on the table. Re-running the separation returns a footprint for
each of them, every one carrying its own error, and the question is whether any
of those footprints moved by more than that error. A knocked neighbour is a real
change buried among five spurious ones.

**Has anything fallen over?** This one the geometry barely answers at all. To the
separation stage a toppled glass is a group of points that does not fit a
circle — and so is a glass half hidden behind its neighbour, and so is a glass
at the edge of the frame. The stage was built to place upright glasses. It was
never given a way to say that something is not upright.

The rest of this section is about the third question, because it is the one that
matters and because the reason it is hard is specific and measurable.

## Why the view from above cannot tell a topple from a big push

A camera looking straight down at a glass sees a round blob. A camera looking
straight down at the same glass lying on its side sees a longer blob of the same
width. Whether those two are different enough to tell apart depends entirely on
the glass, and this kind of glass is drawn from a range wide enough that
sometimes they are not.

### The asymmetry, stated exactly

A standing glass presents its widest part in every direction. For the tapered
kind that widest part is the rim, so the blob is a circle somewhere between
65 mm and 105 mm across, and it measures the same whichever way you measure it.

A toppled glass presents two different lengths. Across the glass it still
presents the rim, so the short extent of the blob is the same 65 to 105 mm it
always was. Along the glass it presents something close to its height, so the
long extent runs from 98 mm to 237 mm over the four hundred drawn.

The word *close* is doing work there, and it is worth being exact about why.
A tapered glass is a cone. A cone laid on a flat table rests along one slant
line of its own wall, which means its axis cannot be level: the rim end is the
fatter end, so the axis rises from the base end to the rim end. The shape the
camera sees is therefore the glass's profile foreshortened by that tilt, with
the rim's overhang added at each end. Over the four hundred drawn glasses, one
that has gone right over comes to rest leaning 72 to 86 degrees from upright,
with a median of 82, so its axis is still four to eighteen degrees off level.
The blob comes out a little longer than the glass is tall rather than a little
shorter.

So the whole difference between the two blobs is one ratio: how tall the glass
is, divided by how wide it is. That ratio is what the overhead view has to work
with, and for this kind it is allowed to be close to one.

![The same glass standing and toppled, seen from straight above, for the glass
of the kind where the two are hardest to tell apart, for a middling one, and for
the one where they are
easiest](../../../images/problem-3/07-the-same-glass-twice.png)

The three glasses in that picture are all from the same family of four hundred,
picked out by how much the blob changes. The hardest is 90 mm tall with a 98 mm
rim: standing it is a 98 mm circle, toppled it is 107 by 98 mm, so the blob
grows by 9 mm. The easiest is 227 mm tall with a 66 mm rim: standing it is a
66 mm circle, toppled it is 230 by 66 mm, so the blob grows by 164 mm.

### How often the two blobs genuinely overlap

There is no single right way to ask whether two blobs are the same, so here are
four, all measured over the same four hundred glasses. Read each row as a test
somebody might put on the overhead picture, followed by the number of glasses
whose topple that test fails to notice.

| The test on the overhead blob | How many of the 400 it misses |
| --- | --- |
| is the blob longer than the 105 mm this kind is allowed to be? | 12, which is 3.0 per cent |
| has the long extent grown by more than 20 mm? | 16, which is 4.0 per cent |
| is the blob less round than 0.8, short extent over long? | 22, which is 5.5 per cent |
| has the area changed by more than a fifth? | 26, which is 6.5 per cent |

The first row is the most damning of the four, because it is the test that needs
no memory of the glass. A blob 107 mm long is two millimetres outside the range
this kind is drawn from, and a blob shorter than that is a legal footprint for
a standing glass of the kind. Twelve of the four hundred, toppled, produce a
blob that nothing in the picture marks as unusual.

The other three rows compare the glass with itself, which is a fairer test,
because the arm does know how wide the glass was before it pushed it. They are
better, and they are not good: between four and seven glasses in every hundred
go over without the overhead blob changing by as much as the measurement error
in reading it.

### The depth reading, and where it reverses

The camera is an RGB-D camera, so there is a second number available: how high
the tallest point of the glass is above the table. That is a genuinely strong
signal, and this document would be dishonest if it pretended otherwise. Standing,
the tallest point is the glass's own height, 90 to 230 mm. Toppled, the tallest
point is the far side of the rim circle held up off the table, 64 to 104 mm.
Over the four hundred the tallest point falls by a median of 73 mm, and by as
much as 161 mm for the tallest glass of the kind.

Two things spoil it.

The first is that the drop is not the same size for every glass, so the threshold
is a different number for every glass. Eighteen of the four hundred change their
tallest point by 10 mm or less when they fall over, which is inside the error of
a depth reading of a thin rim from 450 mm away.

The second is stranger and worth stating plainly. **For four of the four hundred
the tallest point goes up.** A wide, short glass lying on its side stands taller
than it did upright, because a 105 mm rim circle held on edge is taller than a
90 mm glass. Any rule written as "a toppled glass loses height" gets those four
exactly backwards.

![Where in the kind's declared range the overhead reading fails: which glasses
produce a toppled blob still inside the legal width, and which ones get taller
when they fall over](../../../images/problem-3/07-where-the-confusion-is-real.png)

Put the two readings together and the picture is a little better and not much.
Sixteen of the four hundred — one glass in twenty-five — have both readings fail
at once: the blob grows by 20 mm or less *and* the tallest point changes by 10 mm
or less. Loosen the tolerances to 30 mm and 20 mm and it is 31 of the four
hundred. Those are the glasses this solution exists for.

### And displacement, which is the one the geometry gets right

The third overhead number is how far the middle of the blob moved, and it does
separate a topple from an intended push. It is worth going through carefully,
because the size of a push in this problem is much smaller than it first looks.

Start with how far a push actually has to go. The bench's room test, `has_room`
in [`bench.py`](../../../problem-3-sim/bench.py), is the project's own, and it
is **not symmetric**: a glass has room when every other glass's *edge* is at
least 70 mm from its middle, so what a glass needs depends on how wide its
neighbour is rather than on how wide it is. Against the narrowest glass this
kind allows that is 102.5 mm between middles; against the widest it is 122.5 mm.
A narrow glass standing beside a wide one is therefore crowded while the wide
one beside it is not, and a single symmetric threshold gets those cases
backwards.

Run that test over the first 200 tapered test tables `scene(seed)` produces,
from seed 10001. They hold 1000 glasses between them, four to six to a table,
and 707 of those glasses have no room — a median of four per table. For each
one, the distance it has to move to clear its worst neighbour runs from 0.1 mm
to **31.6 mm**, with a median of 12.6 mm and a 99th percentile of 29.5 mm.
Pushes in this problem are short.

Now the topple. When a glass tips it pivots about the leading edge of its foot
and the body falls outward, so the middle of the blob ends up well beyond where
the glass stood. Over the four hundred drawn glasses it lands between 64 mm and
151 mm away, with a median of 109 mm.

The two do not come close to meeting. The longest push any of those 200 tables
asks for is 31.6 mm, and not one of the four hundred topples moves the blob's
middle less than twice that.

That comparison is made on the table rather than in the picture, and the
difference matters more than it sounds. The camera is 450 mm up, so an outline
is thrown outwards away from the point below the lens by a factor that grows
with height — the **splay** described in [the cell](../../the-cell.md). A
standing glass's outline is thrown out by between 1.25 and 2.05 over the four
hundred; a lying one's, being low, by only 1.08 to 1.13. So read straight off
an uncorrected picture, the longest push looks like 39 to 65 mm of movement and
the smallest topple like 69 mm. The two still do not overlap, but the whole
margin is **5 mm**. Problem 2's separation corrects splay using depth, and that
correction is what turns a 5 mm margin into a comfortable one.

![The three outcomes as the overhead pipeline reports them, on one of the
bench's own crowded
tables](../../../images/problem-3/07-what-the-overhead-view-reports.png)

That picture is the summary of this whole section, drawn on table 11117 from the
bench's own generator. The pushed glass is 92 mm tall and 104 mm across; its
neighbour is 80 mm across and 103 mm away, which the asymmetric room test leaves
7 mm short. Displacement tells a successful push from a topple: 7 mm against
71 mm. It says nothing whatever about the neighbour, because the neighbour is a
different circle and its change is one real difference among five noisy ones.
And the two readings that would say *what kind* of wrong thing happened — the
blob's shape and the tallest point — are the two that fail together on one glass
in twenty-five.

### The line the project actually draws

Everything above has compared a standing glass with one lying flat on its wall.
That is not where the project draws the line, and the real line is much harder.

`bench.py` defines a fallen glass with one constant and one test:
`STANDING_TILT_DEG = 20.0`, and `self.tilt(glass) < STANDING_TILT_DEG`. A glass
leaning more than 20 degrees from upright has fallen over. That is the verdict
the simulator records, the verdict `take()` is judged against, and therefore the
verdict this verifier has to reach from pictures.

For comparison, a tapered glass of this kind only comes to rest on its wall at a
lean of between 72 and 86 degrees, a median of 82. The project's line sits a
long way before that.

So ask what the overhead view sees at exactly 20 degrees, the moment the glass
crosses the line. Two answers, both measured over the same four hundred glasses.

**The blob barely changes.** Its longest extent moves by anywhere from −2 mm to
+58 mm, a median of 28 mm, and 129 of the four hundred — nearly a third — are
still no longer than the 105 mm a standing glass of this kind is allowed to be.
For the hardest glass in the set the blob goes from 98 mm to 99 mm.

**The tallest point goes the wrong way.** Leaning the glass over lifts its far
rim, so at 20 degrees the tallest point is *higher* than it was upright — for
every one of the four hundred, by 2 mm to 21 mm, a median of 12 mm. A rule that
watches for the tallest point to drop is not merely weak at this lean. It is
pointing in the opposite direction.

There is a third detail in the same picture, and it is the one that would catch
a rule out first. For the first few degrees of lean the blob gets **shorter**,
not longer. The rim is still the widest part of the outline, and tilting that
circle makes it project as a slightly narrower ellipse before the glass has
leaned far enough for the foot end to reach out the other way.

![What the overhead view sees at the lean where the project starts calling a
glass fallen](../../../images/problem-3/07-the-twenty-degree-line.png)

The practical consequence is that "has it fallen?" is a question about an angle,
and the overhead view cannot measure that angle while it is small. The next
section is about why a model helps with that, and the section after it is about
the view that measures the angle directly.

## Why a model here rather than three more thresholds

Everything above could be turned into rules. Three numbers, three thresholds, a
decision table. It is worth saying why that is the wrong shape for this
particular question, because "use a model" is not an argument.

The evidence bearing on "what happened to this glass?" is **several weak pieces
at once, none of them decisive, and each one's meaning depends on the glass**.
A blob that grew by 9 mm is a topple on the 90 mm-tall, 98 mm-wide glass and is
noise on the 227 mm-tall, 66 mm-wide one, whose topple grows the blob by 164 mm.
A tallest point that fell 70 mm is a topple on a 163 mm glass and less than half
the drop a 227 mm one produces. A tallest point that *rose* 12 mm is a glass at
exactly the lean the project calls fallen, and it is also what a wide glass
looks like after nothing happened to it but a measurement error. Every threshold
has to be a function of the glass's own measurements, of the lean being asked
about, and of what the push asked for, and the interactions between them are
exactly what nobody can write down.

Combining several weak pieces of evidence, none of which is decisive, is the
thing a threshold does worst and a fitted model does best. That is the whole
argument, and it is the same argument the verifier pattern always rests on.

**What it costs** is the usual list. A training set has to be generated. A file
of weights has to be kept in step with the cell. The answer cannot explain
itself: the rules refuse a glass with a sentence containing two numbers, and this
returns 0.27, which has no parts. And the model knows only the glasses it was
shown.

**The alternative that has to be built first** is a logistic regression on three
numbers: the change in the blob's long extent, the change in the tallest point,
and the change in the ratio of the two, each expressed as a fraction of the
glass's own measured width. That is about twenty lines with
[scikit-learn](https://scikit-learn.org/) (BSD-3-Clause), it trains in a second,
and given the numbers above it will already get the great majority right.
**If the larger model cannot beat it on the glasses it gets wrong, the larger
model should not be built.** The measurement that matters is not overall
accuracy but performance on the one glass in twenty-five where both overhead
readings fail, because those are the only cases where anything is at stake.

## What the verifier is shown

The input is the before and the after, and it is worth being exact about what
that means, because "the two pictures" is not enough on its own.

### Why not the two pictures alone

**Change detection** is the field this belongs to: comparing two pictures of the
same scene, taken at different times, to say what differs. It grew up on
satellite imagery, where the same ground is photographed months apart.

The obvious method is **pixel differencing** — subtract one picture from the
other and look at what is left. It works only if the camera has not moved. Here
the camera is on the wrist, and the planner that returns the arm to the
photographing pose is repeatable rather than exact. Shift a 320 by 240 picture by
two pixels and every edge in it lights up — every rim, the edges of the table,
every shadow — and the one glass that actually moved is buried in the result.

Telling a change detector about the camera's motion is the general case, and in
general it is hard. **This cell is not the general case**, and the reason is the
one fact [the cell](../../the-cell.md) says shapes most of these solutions: the
camera is on the wrist, so its pose is known exactly from the joint encoders and
forward kinematics. `tf2`
([github.com/ros2/geometry2](https://github.com/ros2/geometry2), BSD-3-Clause)
publishes it at both moments.

That makes a much better input available. The camera is RGB-D, so the before
picture carries depth. Every pixel of it can be pushed out to the point in space it came from, and
photographed again from wherever the camera is standing now. This is **reprojection**, and what comes back is the scene as it
would have looked from the second pose had nothing changed. The two pictures then
agree on geometry, and every difference left in them is a real difference in the
world. The arm itself is masked out the same way: the joint angles say which
pixels are gripper.

**What it costs** is one extra array operation per push, a few milliseconds, and
a dependence on the camera pose being right. In simulation it is exact. On a real
arm it is not, and a wrong pose makes the model see changes that are not there.

### The three groups of input

With the alignment fixed, the model is shown three groups of things. Each group
answers a different kind of question, and the third group is the one that
distinguishes this solution from a picture classifier.

**The two crops.** A 96 by 96 window centred on where the glass is known to be,
taken from the before picture and from the reprojected after picture, colour and
depth together. This is what carries the shape of the thing in the window.

**The push that was commanded.** How far the arm was told to move the glass, in
which direction, at what height above the table, and how far into the approach
the fingers first felt contact. Without this the model cannot tell an overshoot
from a topple, because both look like a glass that moved further than the middle
of the crop.

**The glass's own measurements, and the geometry's own answer.** How wide the
glass was before, how tall its tallest point was before, what the separation
stage reports now for the blob's two extents and its tallest point, and how far
it says the middle moved. These are the numbers the previous section measured.
They are given to the model directly rather than left for it to rediscover from
pixels, because they are already computed, they are already splay-corrected, and
a small model fitted on a few thousand examples should not be spending its
capacity learning arithmetic that is exactly known.

That last group is what "the before and after evidence, not raw pixels alone"
means. Problem 2's solution 5 could not show its verifier any pixels at all,
because the thing it asks about was never photographed. Here the pixels exist and
they are worth having. They are just not sufficient, and the reason is the whole
of the section above: the difference between a standing glass and a toppled one,
seen from above, is sometimes 9 millimetres in one direction.

### The model, and why a twin

The two crops are fed to a **twin-branch**, or **siamese**, network: two copies
of one small convolutional network that share a single set of weights, one fed
the before crop and one the after crop. Their outputs are subtracted, the
difference is joined to the numbers from the other two groups, and a small head
turns all of it into three probabilities.

**Why shared weights rather than two networks.** Two independently trained
branches drift into two different ideas of what a glass looks like, and then the
difference between their outputs contains that drift as well as the change in the
scene. Sharing the weights makes the difference mean something: the same function
was applied to both pictures, so anything left is a property of the pictures. The
idea and the name come from Bromley and colleagues, who used it to decide whether
two signatures were written by the same person
([Signature Verification using a "Siamese" Time Delay Neural Network](https://proceedings.neurips.cc/paper/1993/hash/288cc0ff022877bd3df94bc9360b9c5d-Abstract.html),
1993).

**What it costs** is that both branches must see comparable pictures, which is
what the reprojection is for, and that the model has half as many parameters to
spend as two independent branches would.

Concretely: a ResNet-18 backbone from
[torchvision](https://github.com/pytorch/vision) (BSD-3-Clause), trained in
[PyTorch](https://pytorch.org/) (BSD-3-Clause) on the Metal backend, because
**this is an Apple Silicon Mac with no NVIDIA graphics card**. Two classical
methods are worth building alongside the logistic regression as further floors
to beat: aligned differencing with a threshold, in
[OpenCV](https://github.com/opencv/opencv) (Apache-2.0), and structural
similarity, in [scikit-image](https://scikit-image.org/) (BSD-3-Clause).

## Three answers, and the fourth one that matters

The model returns three probabilities, not a score.

1. **Moved as intended.** The glass went roughly where it was sent. Carry on to
   the next crowded pair.
2. **Moved unexpectedly.** It went less far than asked, or off the line, or a
   neighbour shifted. Measure it again and push again from where it now is.
3. **Fallen over.** Stop, and report.

**Why three classes rather than an anomaly score.** An **anomaly score** is a
single number meaning *this is unusual*, fitted on normal data alone. Unusual
here covers a glass a little short of its destination, a change in the lighting,
and a glass on its side. Those are three situations with three different correct
actions, and one number cannot distinguish them. There is a second reason, and it
is the stronger one: an anomaly detector is never shown an anomaly, so it cannot
be taught what a topple looks like. Gazebo will make topples all day.

The fourth answer is the one this solution is really for. The verdict is
**uncertain** when the largest of the three probabilities falls below a bar, or
when the top two are close together. The model is then saying **"I cannot tell"**,
and that means exactly what it means in [problem 2's
verifier](../../problem-2/solutions/05-is-anything-hiding-there.md): the evidence
available does not settle the question, and another measurement is the only way
forward.

It is worth seeing why that answer is worth more here than a forced guess. The
arm has an action that produces the missing evidence, it knows which action, and
the action costs seconds. Nothing else in this problem turns doubt into a
movement. Everything else either produces an answer or produces a refusal.

## The feedback loop

An uncertain verdict sends the arm to a second viewpoint, chosen so that it
settles the question the first one could not.

### Why the missing information has a direction

Looking straight down is the worst angle for telling a standing glass from a
fallen one, and the previous section put numbers on how bad. Seen level from low
down, the two are nothing alike, and the difference is not a matter of degree.

Take the one measurement that works from there: how much of the glass lies along
the table, divided by how tall it stands. Standing, a glass of this kind rests on
its foot, so the number is the base diameter over the height. Over the four
hundred drawn glasses that runs from 0.11 to 0.58, with a median of 0.26.
Toppled, the glass rests along its whole wall, so the number is the length of
that wall over the height of the rim circle held on edge. Over the same four
hundred that runs from 0.99 to 3.45, with a median of 1.89.

The two ranges do not touch. There is a clear gap between 0.58 and 0.99 and not
one of the four hundred glasses falls in it, standing or toppled. That is the
whole case for the second look.

That ratio settles a glass flat on its wall. The project's line is earlier, at
20 degrees, and the side view settles that case too — by a different reading,
which is worth separating out. A glass leaning 20 degrees is still balanced on
the edge of its foot, so almost nothing of it lies along the table and the ratio
above stays small. What the side view does show is the **lean itself**: the
silhouette's two walls are both turned by the same angle, so the axis is
directly measurable. Over the four hundred glasses, 20 degrees of lean swings
the middle of the rim sideways by between 31 mm and 79 mm, a median of 54 mm,
against rims that are only 65 to 105 mm across. The glass is visibly off its
axis. From above, the same lean moved the blob's longest extent by a median of
28 mm and moved the tallest point the wrong way.

So the second look is not one measurement but a view in which both readings
exist: the ratio for a glass that is all the way over, and the lean angle for a
glass that has only just crossed the line.

![What a low, level view settles: the same glass standing and toppled, and the
ratio that separates the two over every glass of the
kind](../../../images/problem-3/07-the-side-on-look-settles-it.png)

### Where the camera goes

**The height.** [The cell](../../the-cell.md) puts the level view 120 mm above
the table. For this purpose the camera wants to be lower, around 80 mm, and the
reason is in the numbers above: a toppled glass of this kind stands between
64 mm and 104 mm tall, so from 120 mm the camera is looking down on it and the
table appears behind it. From 80 mm the glass is seen against the background
instead, and the outline that carries the answer is the outline against the
background rather than against the table.

**The direction.** The arm can stand anywhere on a circle round the glass. Score
the poses at working range by how many other glasses lie in the line of sight,
and take the clearest one the arm can comfortably reach. This is the same choice
[solution 3 of problem 2](../../problem-2/solutions/03-move-the-camera.md) makes
for measuring a glass, and the same arithmetic serves.

**A second direction, if needed.** A glass that fell straight towards the camera
foreshortens, and foreshortened it can look like a standing one. A second pose 90
degrees round the circle removes that case. It is only taken if the first
side-on look is itself uncertain.

**How many looks.** Two, and then stop. Each is a few seconds of arm movement,
so the whole budget is under ten seconds. If the verdict is still uncertain after
the second, the arm does not guess. It reports the glass as doubtful and leaves
it, which is the same answer this project gives everywhere else: a refused glass
is a result, not a failure.

### The asymmetry in the thresholds, and why it is deliberate

The two mistakes this model can make do not cost the same, so the thresholds
should not be symmetric.

A false "everything is fine" leaves the arm working beside a fallen glass that
nothing here can stand back up, and every later move is planned against a table
the arm has misunderstood. A false alarm costs a stopped run and a line in the
report.

So the bias goes in twice, in two different places.

**In the training loss.** Missing a topple is penalised several times more
heavily than inventing one. The exact weight is a dial, and the honest way to set
it is to run the pipeline on seeded arrangements and count both kinds of mistake
rather than to pick a number that sounds cautious.

**In the run-time bars.** Accept "moved as intended" only above about 0.9. Treat
"fallen" as live from about 0.2 upwards. Let everything in between buy a look
rather than a decision. Those two numbers are starting points, not results; what
makes them defensible is that they are asymmetric in the direction the costs are
asymmetric.

The principle generalises past this cell: **make the model eager to ask for
another picture and reluctant to say everything is fine.**

One property of the probabilities has to hold before any bar may be put on them.
A probability is **calibrated** when its claims come true about as often as it
says they will. If the model says "fallen, 0.2" about a hundred glasses, about
twenty of them should have fallen. Models are very often not calibrated, and the
standard repair is not a better model but a small separate step afterwards: fit
the model, then fit a tiny function mapping its raw scores onto honest
probabilities, on data the model never trained on. It costs a held-out set and a
second of computation, and it does not make a wrong answer right. It makes the
model's claim about that answer honest, which is what a threshold needs.

## The safety net under a number the arm is never told

This solution's place in the set is easiest to see from the one piece of
arithmetic every solution in problem 3 shares, and from the guess inside it.

A pushed object slides while the contact height `h` is below `a / μ`, where `a`
is half the base width and `μ` is the friction between the glass and the table.
Above that it tips. The base width the arm measures. The friction it does not,
and this is the place to be careful about a distinction the whole problem turns
on. The simulator **does** know the friction: `bench.py` sets
`TABLE_FRICTION = 0.35` and uses it on every table. That number is ground truth,
used to run the physics and to score the outcome. It is never handed to the arm
and it is never an input to any decision. When this document says the friction
is unknown, it means unknown to the arm.

There is a second number here that is easy to get wrong, and the bench is
explicit about it. The jaw comes down so that its middle rides at 50 mm, which
is `LOWEST_GRIP`, the lowest the gripper goes. But the jaw's fingers are 30 mm
tall, so its top edge is at 65 mm — and a tapered glass is wider higher up, so
the top edge is what the glass meets first. **The height that decides whether a
tapered glass slides or tips is 65 mm, not the 50 mm the arm aims at.**

Put those together over the four hundred drawn glasses. Read each row as one
combination of a contact height and a friction, and the last column as how many
of the four hundred would slide rather than tip.

| Contact at | With friction | Glasses that slide |
| --- | --- | --- |
| 50 mm, where the arm aims | 0.3, a common guess | 372 of 400 |
| 50 mm | 0.35, the simulator's | 308 of 400 |
| 50 mm | 0.5, also plausible | 54 of 400 |
| 65 mm, where the glass touches | 0.3 | 223 of 400 |
| 65 mm | 0.35, the simulator's | 100 of 400 |
| 65 mm | 0.5 | none at all |

The friction at which each glass stops sliding, touched at 65 mm, runs from 0.20
to 0.45 with a median of 0.31. The simulator's 0.35 sits above that median,
which is the whole difficulty in one number: for most glasses of this kind, the
table is grippier than the glass can stand.

Now the failure this solution catches. An arm that guesses 0.3 and checks it
against the 50 mm it is aiming at declares 372 of the 400 safe to push.
**Of those 372, 272 — 68 per cent of the whole population — go over**, because
the real friction is 0.35 and the real contact is at 65 mm. Even an arm that
allows for the jaw's top edge correctly, and still guesses 0.3, declares 223
safe and loses 123 of them.

![What the friction guess declares safe, and what the table really
does](../../../images/problem-3/07-the-safety-net.png)

That is this solution's argument in one number. The geometry cannot do better,
because the input it would need is deliberately withheld.
[Solution 4](04-predict-the-slide.md) applies the classical theory of planar
pushing and arrives at the same place: the theory is correct and one of its
inputs is missing. Pushing as low as the gripper reaches, which
[the problem](../problem.md) recommends and
[solution 3](03-plan-feel-look-again.md) does, is already what the bench does
and it is not enough. [Solution 9](09-identify-the-contact-parameters.md)
attacks the guess directly by estimating the contact parameters from what the
pushes actually did, and [solution 8](08-a-learned-early-abort.md) attacks it
during the push by watching the force trace. This solution attacks the
consequence: when the guess was wrong, something has to notice, and noticing is
what a verifier is for.

### What the bench hands over for free, and what a cell would not

One honest note belongs here, because it changes how this solution should be
read.

The bench's `look()` returns, for each glass, its position, its height, its
widest width, its foot width — each with problem 2's measured error added — and
a `standing` flag. That flag is `self.tilt(glass) < STANDING_TILT_DEG`. It comes
straight from the physics, with no error and no doubt, because the simulator
knows exactly how far every glass is leaning.

So inside the bench this solution appears to solve a problem that does not
exist. That is a convenience of the bench and not a fact about the cell. In a
real cell nothing measures a glass's lean, and the boolean has to be produced
from pictures by something. This document is about what that something would
have to be, and the measurements above are why it cannot be three thresholds.
The same note applies in reverse to the bench's other readings: `look()` returns
the glass's standing height and widest width whatever its lean, so the bench
does not model the toppled footprint at all, and the confusion this document
measures is invisible from inside it.

## Training it, and the trap

The labels are free, which is the pleasant part. Gazebo Harmonic
([gazebosim.org](https://gazebosim.org/), Apache-2.0) knows exactly where it put
each glass and exactly where each one ended up, so every push produces a
before crop, an after crop, the commanded push, the measured numbers, and the
true answer, with nobody labelling anything by hand.

The trap is **class imbalance**, and it is severe here. A topple is rare in
normal running — one push in a few hundred, if the tipping check is doing its
job. A model trained on that mixture learns the cheapest rule available:
*nothing ever falls over.* That rule is right on all but that one push in a few
hundred, and it is worth nothing at all.

There are two halves to the fix and both are needed.

**Generate topples deliberately.** Spawn glasses whose base is too narrow for the
push height, raise the friction, push high on purpose. Keep going until about one
training pair in five is a topple. The simulator will do this all day and it
costs only time.

**Score on topples caught, never on accuracy.** Accuracy is the measure the lazy
rule wins. The numbers to watch are how many real topples the model reports, how
many false alarms that costs, and — the one specific to this document — how it
does on the glasses where both overhead readings fail. Sixteen of four hundred is
four per cent of the population, so a test set drawn uniformly will contain few
of them, and a model can score beautifully overall while being useless on exactly
the cases the solution was built for. Build a separate test set of those glasses
and report its number separately.

## A worked example

Table 11117 from the bench's own generator, which is the table the outcome
pictures above are drawn on. Six glasses of the tapered kind; three of them have
no room.

*The glass.* Glass 0 stands at (323, −257) on the table. It is 92 mm tall,
104 mm across the rim and 46 mm across the foot — very nearly the hardest
proportions in the whole kind, which is why this table was chosen. Its binding
neighbour is glass 4, 80 mm across and 103 mm away. The room test wants 110 mm
between their middles, so glass 0 is 7 mm short.

*The push.* Seven millimetres, away from glass 4 along the line through both
middles. The jaw comes down to 50 mm, feels forward until it touches, pushes and
backs off.

*The routine look.* Forward kinematics says the camera came back to within a few
millimetres and a fraction of a degree of where it stood before. That is far too
much for pixel differencing, so the before picture is reprojected into the after
camera's frame and a 96 by 96 crop is taken at the glass's known position.

*What the geometry reports.* The blob is 110 by 104 mm where it was 104 mm
round, so the long extent has grown by 6 mm. The tallest point reads 99 mm where
it was 92 mm, so it has gone *up* by 7 mm. The middle of the blob has moved
71 mm, where the push asked for 7.

*What a rule would make of that.* A rule thresholding the blob's width would
pass it, because 110 mm is five millimetres outside what a standing glass of
this kind may be and well inside any tolerance a 2.5 mm width error justifies. A
rule thresholding the tallest point would pass it, and would pass it in the
confident direction, because the glass got taller. A rule thresholding
displacement would flag it, because 71 mm is ten times the push — but "flag it"
in solution 3's comparison means "moved unexpectedly", whose prescribed action
is to measure the glass again and push it again. Pushing a glass that is already
lying down is worse than doing nothing.

*What the verifier returns.* Moved as intended 0.31, moved unexpectedly 0.42,
fallen 0.27. Nothing clears 0.9, and the top two are close. Uncertain.

*The chosen look.* The clearest arc round glass 0 is the one away from glass 4
and glass 1. The arm goes out on that side and down to 80 mm above the table,
looking level. About four seconds.

*What the second look shows.* The silhouette has 96 mm lying along the table and
stands 99 mm tall, so the ratio is 0.97. Standing, that ratio for this glass
would be 46 over 92, which is 0.50. The nearest any of the four hundred standing
glasses of this kind comes to 0.97 is 0.58. The answer is not close.

*The second verdict.* Fallen 0.96, which agrees with what the bench recorded,
because the glass is leaning far past the 20 degrees `STANDING_TILT_DEG` allows.
The run stops and reports. It cost four seconds to reach a conclusion the view
from above could not have reached at all.

*The other ending.* Had the side-on look come back with 46 mm on the table and
92 mm of height — a ratio of 0.50 — the verdict would have been "moved as
intended" at about 0.94, the 71 mm would have been explained some other way, and
the run would have carried on. The four seconds buy the answer either way. That
is the trade this solution makes: **the cost of looking is seconds, and the cost
of believing a toppled glass is still standing is the failure this problem
exists to avoid.**

## What it needs

No new hardware. The camera, the depth channel and the joint encoders are all
already in the cell and already used.

New code, in five pieces: the reprojection of the before picture into the after
camera's frame; a script that generates training pairs in Gazebo with topples
forced to one in five; the training itself and the weights file it produces; the
viewpoint chooser for the second look; and the two-look cap with its report
line.

## Where it is strong and where it breaks

The strengths come from where it sits rather than from the model.

It answers the two questions the geometry cannot, from one comparison rather than
a full survey of the table. It turns doubt into an action, which nothing else in
this problem does. Its errors fall on the side that costs seconds rather than the
side that costs a glass. And it **degrades to solution 3**: delete the weights
file and the run still works, with the old comparison and its old blind spot.

The weaknesses divide into what it cannot see, what is hard about training it,
and where it is simply the wrong tool.

**It cannot explain itself.** The programmed refusals in this project state a
number and a limit. This returns 0.27, which has no parts. When it is wrong,
finding out why means looking at its inputs beside its answer, which is why those
inputs are worth keeping small and named.

**It depends on the alignment.** A wrong camera pose makes the model see changes
that are not there. This is exact in simulation and much less so on a real arm,
and it is the property most likely to break when this leaves the simulator.

**It only knows the glasses it was shown.** A glass leaning against its
neighbour has stopped part way, and the bench will call it fallen or standing on
a single degree either side of 20. The model will pick one of the three answers
anyway, and near that line it should be picking "I cannot tell" instead, which is
a matter of what it was trained on rather than of how it was built. The same
goes for a glass that has rolled: a tapered glass lying on its wall rolls in a
circle rather than in a straight line, and that is a case worth generating
deliberately.

**It follows the pushed glass.** The crop is centred where the target was, so a
neighbour knocked at the far side of the table is outside it. The fix is to run
the same model on every glass rather than only the pushed one, which costs
milliseconds and is worth doing from the start.

**It can stop being read.** A verifier that says "fine" on 199 pushes in 200 stops
being looked at, and the two hundredth was the one that mattered. The defence is
that its uncertain verdict triggers an arm movement rather than a log line, so it
is never merely advisory.

And the honest limit: **its value depends on a measurement nobody has taken.**
The four per cent figure above is the fraction of the *kind's range* where the
overhead reading fails, not the fraction of *runs* in which a topple happens.
The friction arithmetic says that fraction should be large — 272 of 400 glasses
pushed over by a guess of 0.3 against the bench's real 0.35 — but arithmetic is
not a measurement. Run the bench over a few hundred seeded tables, count the
glasses whose tilt ends past `STANDING_TILT_DEG`, and use that number. If it is
near zero the arithmetic is wrong somewhere and this solution can wait. If it is
anywhere near what the arithmetic predicts, this is the component to add next,
because the failure it catches cannot be undone by anything else in the
project.

## Where the idea comes from

Three ideas sit behind this, and all three are older than the machine learning
around them.

### Verifiers and cascades — a cheap exact test first

Arrange the work in order of cost, so that a cheap exact method handles
everything it can and an expensive or learned one is consulted only on what is
left. When the second stage checks the first it is usually called a **verifier**;
when it simply runs on the survivors, a **cascade**. The best-known example is
the Viola–Jones face detector, which made real-time detection possible by
rejecting almost every window of an image in a handful of arithmetic operations
([DOI](https://doi.org/10.1109/CVPR.2001.990517), 2001).

This is used wherever there is a large easy majority and a small hard minority,
which is exactly the shape of this problem: most pushes go as planned, and a few
do not. It is rarely right when the cheap stage cannot be made both fast and
safe, because whatever the first stage discards, no later stage ever sees. Here
the cheap stage is the geometry, and it is safe in one specific sense worth
naming: it never *removes* a glass from consideration. It hands every glass on
with its three numbers attached.

### Classification with a reject option — a model allowed to decline

Instead of forcing every input into a class, allow a third answer: decline, and
hand the case to something else. The rule for when to decline is old and simple
(Chow, [DOI](https://doi.org/10.1109/TIT.1970.1054406), 1970): decline when the
best probability falls below a threshold set by the relative cost of an error and
a refusal.

It is used wherever being wrong is expensive and a fallback exists, and it is
rarely right where declining simply means failing. Here declining means moving
the camera, which costs four seconds, and the error it avoids is a glass nobody
can stand back up. The reject option earns its place more easily in this cell
than almost anywhere.

### Change detection, and the case where the camera pose is known

Comparing two pictures of the same scene at different times is a field in its own
right, with most of its literature written about satellites and most of its
difficulty coming from registration — getting the two pictures into the same
frame before comparing them. The general case is genuinely hard.

The lesson worth carrying is not about change detection but about problems in
general. Before reaching for the method that handles the general case, it is
worth asking which part of the general case this particular cell does not have.
Here the camera is on a wrist with encoders on every joint and a depth channel
beside the colour, so the registration problem — the hard part — is already
solved by arithmetic somebody else wrote. What remains is the easy part, and the
easy part is small enough for a small model.

## Where it sits among the other solutions

This solution sits on top of [solution 3](03-plan-feel-look-again.md) and changes
only its last step. Everything before the look again is unchanged:
[solution 1](01-do-not-drag-at-all.md) still decides whether a push is needed at
all, [solution 2](02-one-fixed-nudge.md) is still the baseline the loop is
measured against, and solution 3's destination search, tipping check and guarded
move are all untouched.

Against the other hybrids, the difference is where the model sits in the
sequence. [Solution 5](05-a-learned-residual-on-the-push-model.md) puts a model
in front of the push, correcting a prediction of where the glass will go.
[Solution 6](06-geometry-generates-a-model-ranks.md) puts one in the middle,
ordering candidates the geometry has already vetted. This one puts a model after
the push, where it cannot influence the action at all. That is the safest of the
three places, and it is also the one where the geometry is weakest, which is why
the overview calls this the first learned thing worth adding.

The closest relative is [solution 8](08-a-learned-early-abort.md), which is the
same pattern moved earlier. It watches the wrist force during the push and stops
if the trace looks like an object beginning to tip. The difference is worth
stating plainly, because the two are easy to confuse. **Solution 8 can prevent a
topple. This one can only report it.** Solution 8 is therefore the more valuable
of the two if it works, and the harder to get right, because it has to decide in
milliseconds from a force trace rather than in seconds from two pictures. They
are not alternatives. A cell running both would abort the pushes it could and
verify the outcome of the ones it did not.

Against the fully learned solutions, the comparison is about how much is at
stake. [Solution 9](09-identify-the-contact-parameters.md) estimates the
friction the arm is never told, which would shrink the population this solution
has to catch.
[Solution 10](10-learn-a-forward-model-then-plan.md) and
[solution 11](11-search-a-push-strategy.md) learn what to do rather than what
happened, which puts a fitted function in charge of the only action in this
problem that can break something. This one cannot break anything, which is the
whole reason it goes first.

Its honest position is therefore narrow and clear. It is the cheapest learned
component in the set, it is aimed at the failure the problem statement says to
watch hardest, and the case for building it rests on a measurement — how often
this cell actually topples a glass — that should be taken before a line of it is
written.
