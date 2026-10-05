# Solution 2 — a network trained here from scratch

> **What it uses** — PyTorch, running on this machine's integrated graphics
> through the MPS backend. One small convolutional network, written for this
> cell and fitted entirely inside it. No downloaded weights and no model from
> anybody else, so there is no licence condition to meet.
> **What it does** — one network looks at a survey picture and answers two
> questions at every pixel. The first question is whether the pixel is glass.
> The second question, asked only of the glass pixels, is which way the middle
> of that pixel's own glass lies. Each glass pixel then votes for the place its
> arrow points at, so one glass makes one pile of votes and two glasses make
> two piles, and a connected blob of glass pixels comes apart into separate
> glasses without any rule for cutting it having been written down.
> **How the output is produced** — a survey picture and its depth reading go
> into the network; the first head gives a glass-or-not score at every pixel
> and the second head gives an arrow at every glass pixel; each glass pixel
> casts one vote; the votes are piled up and the peaks are counted; the pixels
> that voted into one peak are one glass's mask; the bench's shared arithmetic
> turns each mask into a place and a width.
> **How it differs from the other five** — [rules on the
> table](01-rules-on-the-table.md) writes the grouping rule by hand, where this
> one fits it from examples. [YOLO as it downloads](03-yolo-zero-shot.md)
> borrows a whole model and changes nothing, where this one borrows nothing.
> [YOLO fine-tuned](04-yolo-fine-tuned.md) and [RF-DETR
> fine-tuned](06-rf-detr-fine-tuned.md) are both trained on this cell's
> pictures as this one is, but they start from somebody else's weights rather
> than from random numbers. [SAM 2 with a keeper](05-sam2-with-a-keeper.md)
> fits only a small decider on top of a borrowed model, where here every weight
> in the network is fitted here.
> **What it costs** — a training set of this cell's own pictures with labels,
> a training run before the solution can answer anything, and a file of weights
> that has to be kept in step with the cell. The training run is short enough
> on this machine's integrated graphics that it can be repeated whenever the
> cell changes, and no dedicated graphics card is needed. At run time one pass
> of a small network over a small picture is cheap beside one movement of the
> arm.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to answer [problem 2](../problem.md) with a network
that is built and fitted entirely inside this cell, borrowing nothing from
anywhere else. That is the one property worth holding on to while reading,
because it is what makes this solution different from the four learned ones
beside it. Each of those starts from weights somebody else fitted to
photographs of the real world. This one starts from random numbers and learns
only from pictures this project rendered itself.

By the end you will understand four things. You will understand why a network
is wanted here at all, which is that the hard part of this problem is a
grouping rule nobody can write down neatly. You will understand how one small
network answers both the question *is this pixel glass* and the question *which
glass is it*, and why asking the second question as an arrow rather than as a
label is what makes the merge answerable. You will understand where the
training labels come from, and this is the part the document is really for,
because there are two quite different answers to it and the second one is the
interesting one. And you will understand why this solution is the control for
the one question the other five cannot answer between themselves, which is what
borrowing somebody else's weights is worth.

That last point is worth stating now, because it explains why this document
exists even though a borrowed model is easier to set up. Every other learned
solution here carries a **domain gap**, which is the gap between the pictures a
model learned from and the pictures it is asked about. A model fitted to
photographs of kitchens and streets has never seen this simulator's table, this
lens or these four kinds of glass, and nobody can say in advance how much of
what it learned still applies. This solution has no domain gap of any size,
because everything it knows came from this cell's own pictures. So when the
six are scored side by side, this one is the line that says whether borrowing
weights was worth anything at all. Without it, a good score from a borrowed
model proves only that the model is good, and not that borrowing helped.

## The network, in the code

The network is written in `02-segment-glasses/02-train-from-scratch/`, and the
piece worth seeing is not its shape but what it is asked for. It answers three
numbers at every pixel of a shrunk picture: one saying whether the pixel is
glass, and two holding the arrow to the middle of that pixel's own glass.

This is the answer it is trained towards, and the network that produces it,
from ``02-train-from-scratch/models.py``. The first function builds the target
out of the simulator's record of which glass each pixel shows. The second is
where PyTorch does the work, and the two `torch.cat` lines are the copies
carried from the way down across to the way up.

```python
def top_target(picture: Picture, glasses) -> np.ndarray:
    """Per pixel: glass or not, and the offset to its rim's middle."""
    ids = picture.ids[::SHRINK, ::SHRINK]
    target = np.zeros((3, *SMALL), dtype=np.float32)
    target[0] = ids > 0
    rows, columns = np.indices(SMALL)
    for index, glass in enumerate(glasses):
        column, row = rim_middle(picture, glass)
        mine = ids == index + 1
        target[1][mine] = (column - columns[mine]) / VOTE_SCALE
        target[2][mine] = (row - rows[mine]) / VOTE_SCALE
    return target


class TopNet(nn.Module):
    ...
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        full = self.at_full(x)
        half = self.at_half(full)
        quarter = self.at_quarter(half)
        up = nn.functional.interpolate(quarter, size=half.shape[-2:])
        up = self.up_half(torch.cat([up, half], 1))
        up = nn.functional.interpolate(up, size=full.shape[-2:])
        return self.head(self.up_full(torch.cat([up, full], 1)))
```

And this is where the votes become one glass's mask, from
``02-train-from-scratch/pipeline.py``. `SHRINK` is how much the picture was
shrunk by, and `_BLOCK` is the offsets of one shrunk pixel's own block, so the
mask claims the whole block each voting pixel stands for.

```python
def pile_mask(picture: Picture, votes: Votes, middle) -> np.ndarray | None:
    """The pixels that voted for one middle, as a boolean mask, or None if too few did.
    ...
    """
    mine = np.linalg.norm(votes.landed - middle, axis=1) < MIDDLE_RADIUS
    if mine.sum() < MIN_VOTES:
        return None
    corners = np.stack([votes.rows[mine], votes.columns[mine]], 1) * SHRINK
    pixels = (corners[:, None, :] + _BLOCK[None, :, :]).reshape(-1, 2)
    pixels = np.clip(pixels, 0, np.array(picture.depth.shape) - 1)
    mask = np.zeros(picture.depth.shape, dtype=bool)
    mask[pixels[:, 0], pixels[:, 1]] = True
    return mask
```

Two things are worth reading off those. The borrowed library supplies the
layers and the training loop, while the idea — an arrow at every glass pixel
instead of a label — lives in the twelve lines that build the target, which is
this project's own arithmetic. And a mask here is a set of votes rather than a
drawn outline: nothing in either piece asks where a glass ends, and the only
line that mentions a boundary is the one that keeps a block inside the picture.

## The problem this solves

The problem is the one [problem 2](../problem.md) states, and this section
narrows it down to the single difficulty this solution is aimed at.

Four to six glasses stand on the table. They are all the same kind, the kind is
known, and they are opaque, so the depth camera gets a reading on them. They
stand far enough apart never to touch. The arm photographs them from the top
and has to say which pixels belong to which glass.

The difficulty is not finding the glass. **It is telling one glass from
another.** Two words are needed to say why. A **mask** is a picture the same
size as the photograph in which every pixel is marked glass or not glass. The
usual step that turns a mask into separate objects is **connected
components**, also called a flood fill: take a marked pixel nobody has visited,
spread out to every marked pixel touching it, call everything you reached one
object, and repeat.

A flood fill answers exactly one question, which is *are these pixels joined?*
And joined is what two glasses in a survey picture often are, because a camera
looking straight down throws each glass's outline outwards from the point below
the lens, so each glass covers more of the picture than its footprint on the
table deserves. Two glasses with clear table between them can therefore leave
one connected shape, and a method that treats one connected shape as one object
reports one glass where two are standing.

**Training harder does not remove that difficulty, because it is a limit on the
shape of the answer rather than on the quality of the fit.** A picture that
labels every pixel with a class is called **semantic** segmentation. A picture
that labels every pixel with a class *and* with which object it belongs to is
called **instance** segmentation. This problem asks for the second. A perfectly
fitted class map still merges two joined glasses, because "glass" is the only
value it has room to hold, and a value that is the same everywhere cannot mark
a boundary. So the fix is not a better network. **It is a different output**,
and that is what the second half of this solution's network is.

![Two glasses in line with the camera overlap in the picture, and a class map has only one value to put on both of them, so the separating has to come from a different output — which here is the arrow at each glass pixel towards the middle of its own glass.](../../../images/02-segment-glasses/06-semantic-against-instance.png)

## The main idea

The main idea has two halves. The first half is a claim about this cell rather
than about networks, and the second half is the different output just promised.

**This cell is narrow, so the network can be small.** Consider how little
varies here. There is one class to predict, glass or not glass. There is one
kind of glass at a time, drawn from inside that kind's range of proportions.
There is one camera with one lens. There is one simulator with one lighting
setup. The glasses are always upright and always opaque. Almost all the variety
a general-purpose model is built to absorb simply does not occur here, so a
small network has enough capacity for the job — and a small network with an
endless supply of labelled pictures is something that can be fitted from
nothing on an ordinary machine.

**The second half is that each glass pixel is asked for an arrow instead of a
label.** At every pixel it calls glass, the network predicts a short arrow
pointing towards the middle of that pixel's own glass. Add the arrow to the
pixel's own position and the result is a **vote** for where that glass's middle
is. One glass makes one pile of votes, because all of its pixels point at the
same middle. Two glasses make two piles, because each glass's pixels point at
their own middle. So counting glasses becomes counting piles, and splitting a
blob becomes asking which pile each of its pixels voted into.

![Every glass pixel's arrow ends on the middle of its own glass, so one glass makes one pile of votes and two glasses joined in the picture make two piles, and the seam between them is a change of direction rather than a gap.](../../../images/02-segment-glasses/06-the-voting-idea.png)

Two things about that are worth noticing immediately, because they are why this
design is chosen over the obvious alternatives.

**Nothing has to find a boundary, so nothing can get a boundary wrong.** Where
two glasses meet in the picture, the pixels do not change at all. What changes
is the direction the arrows point: the pixels on one side point one way and the
pixels on the other side point the other way. The seam between them is a
consequence rather than something anything has to locate.

**A wrong vote is outvoted rather than fatal.** A glass seen from the top
covers many pixels, so it casts many votes, and a handful of them pointing the
wrong way are a handful of strays in a pile of many. Compare that with
predicting the seam directly, where one missing pixel along the seam rejoins
two objects completely.

The rest of this document builds that up. First comes what exists in code and
what is a design, so that nothing later has to be read twice. Then what a
network is and what training from scratch means. Then the shape of the network
and the two heads in turn. Then the two rungs of this solution, which are the
two places the training labels can come from. Then what the solution hands to
the bench, the failure that no amount of training can fix, and where this sits
among the other five.

## What exists in code, and what is a design

All six solutions are built, and this one is built in two layers, so it is
worth separating them plainly before going further.

**What exists.** A network of exactly the shape described below is already
written in this project's code. It has the two heads this document describes:
one channel saying whether a pixel is glass, and two channels holding the two
parts of the arrow. It is written in PyTorch and it runs on
this machine's integrated graphics through the MPS backend, which is the
interface PyTorch uses to reach graphics hardware on this kind of machine
rather than a dedicated graphics card. Its training labels are read from the
simulator's own record of which glass each pixel shows. Its votes are piled up
into a tally and the peaks of that tally are picked off one at a time, largest
first, and the pixels that voted near a peak are that peak's glass.

Running it as one of the six cars on the shared [test bench](../the-bench.md)
is built too. The training set is drawn from the bench's own arrangements, half
of them crowded and all of them below the bench's dividing line, and the
solution is scored on held-out arrangements above that line and writes its own
`results.json` beside itself.

**What is a design.** Four things this document describes are written here and
not built: the two fixes for the rare class in the loss, the check on a pile's
fitted width, the second alarm on how far a pile's votes sit from their own
peak, and the whole of the second rung described below, which changes where the
labels come from. Where this document prescribes a check or a threshold, it
says so, and it quotes no measurement from anywhere.

## What a network is, and what training from scratch means

Before the two heads can be described, three words need defining, because
everything after this uses them.

A **neural network** is a program whose behaviour comes from numbers fitted to
examples rather than from rules anybody wrote. Those numbers are called
**weights**. They start as random noise, and **training** shows the network an
example, compares what it produced against the answer wanted, and nudges every
weight in the direction that would have helped. Nobody writes the rule the
network ends up applying, and nobody can read that rule back out afterwards.

**Fine-tuning** means not starting from random numbers. You take a network
somebody else fitted to a large collection of labelled photographs, replace its
last layer with your own, and carry on training from there. This is the
standard advice almost everywhere, and the reason is that labelled real
pictures are scarce: somebody has to draw round every object in every picture,
so a borrowed network cuts the number of labels you need by a large factor.

**Training from scratch** is the other option: start from random numbers and
learn everything from your own examples. It is normally the worse choice, for
exactly the reason fine-tuning is the standard advice. It is the right choice
here, and the next section is why.

## Why nothing is borrowed, and what that buys

The usual argument for fine-tuning rests on labels being scarce, so the first
thing to check is whether they are scarce here. They are not.

**Labels in this cell are free and exact.** The bench renders every picture
itself, so it also knows, for every pixel, which glass that pixel shows. Asking
for that record costs no more than asking for the picture. There is no
annotator, so there is no annotator's budget, no annotator's fatigue and no
annotator's mistakes. The scarcity that fine-tuning exists to solve is simply
not present, and training from scratch on an endless supply of exact labels is
a quite different proposition from training from scratch on a few hundred
hand-drawn ones.

**And borrowing brings a domain gap, which this solution is the only learned one
without.** A borrowed model's weights say what the world looked like in the
pictures it was fitted to, and those were photographs of real rooms with real
objects. This cell is a simulator with one table, one lens and four kinds of
glass that no photograph collection contains. Nobody can say in advance how
much of what such a model learned still applies here, and the honest way to
find out is to measure it. That is this solution's job in the comparison: it is
the line with no borrowed knowledge in it at all, so the distance between it
and the four borrowed ones is a measurement of what borrowing was worth.

There is a third, smaller reason, which decides nothing by itself but removes
the last practical argument for borrowing. Many ready-made models expect a
dedicated graphics card and this machine has none. A network small enough to
be written for this cell does not.

What all of that costs is set out in [what it needs](#what-it-needs), and the
short version is a training set, a training run and a file of weights to keep
in step with the cell. Those are real costs and rules on the table does
not pay any of them.

## The shape of the network

With the choice of a random start settled, the shape of the network can be
described, and it is the standard shape for labelling every pixel of a picture.

The network has a **down path** and an **up path**, and the two are joined
across the middle.

The down path starts with the picture and applies **convolutions**. A
convolution takes a small square window, slides it over the picture, and at
each position multiplies the values inside the window by a fixed set of weights
and adds them up. One set of weights produces one output channel, and many
sets produce many channels, so a convolution turns a picture of a few channels
into a block of numbers of many channels. Between groups of convolutions the
block is **halved**, meaning it comes out half as wide and half as tall, while
the number of channels is doubled.

Two things happen on the way down and they pull against each other. Each
halving throws away exactly *where* something is, because one unit now stands
for a whole patch of the original picture. But each halving also means the next
window covers four times as much of the original picture as it did before. So
deeper units know less and less precisely where they are looking, and more and
more about what is around them. **That trade is the entire reason for going
down**, because an arrow towards the middle of a glass cannot be predicted by a
pixel that can only see itself. The pixel has to see enough of the glass around
it to tell which way the middle lies.

The up path reverses the halving, enlarging the block step by step until it is
back to the size of the picture it started from, and narrowing the channels as
it goes. A final convolution with a window of exactly one pixel, so no mixing
across space at all, collapses the channels to the handful of output values
this solution wants at each pixel.

The up path alone cannot work, and the reason is the first of the two things
that happened on the way down. The deepest layer knows there is a glass roughly
over *there*, but the halvings destroyed which exact pixel its rim sits on, and
enlarging the block again cannot invent a detail that was thrown away. So the
detail is not thrown away: before each halving a copy of the block is kept, and
on the way back up the copy is attached on as extra channels. The fine detail
comes across on the copy, the sense of context comes up from below, and the
convolution after the join mixes the two. Those copies are called **skip
connections**, and a network built this way is a **U-Net**, from Ronneberger,
Fischer and Brox, 2015 ([arXiv:1505.04597](https://arxiv.org/abs/1505.04597)).

### What goes in

The network is given the depth reading turned into something like a height
above the table, and two further channels that say where in the frame each
pixel sits. All three go in at half size, which is four times quicker to train
on and still leaves a glass many pixels across.

The last of those needs explaining, because it looks like a strange thing to
tell a network. A camera looking straight down throws a glass's outline
outwards from the point directly below the lens, and it throws it further the
taller the glass is. So the direction from a pixel to the middle of its own
glass depends on where in the frame that pixel is seen, which means a pixel
cannot answer the question from appearance alone. Telling the network where
each pixel sits hands it the one fact it cannot see.

### The warning worth checking before training

There is one piece of arithmetic worth doing **before** trusting this shape,
and it follows directly from the trade on the down path. How much of the
original picture one deep unit depends on is called its **receptive field**,
and it is easy to work out: each convolution extends the field a little at
whatever scale it is working at, and each halving doubles that scale, so the
field grows slowly at first and then in larger and larger jumps.

Turn the deepest layer's field into a distance on the table, using how much
table one pixel covers from the height the camera flies at, and compare it with
the smallest gap the cell guarantees between two glasses. **If that patch of
table is smaller than the gap, then the one layer with enough context to reason
about a neighbour cannot see two glasses at once**, and it is structurally
incapable of the comparison you might have hoped it was making. Adding one more
halving fixes it, at the price of several times as many weights in the deepest
block, because a convolution's weight count grows with the product of its two
channel counts.

Whether the extra depth is actually needed here is not known, and this document
is not going to pretend otherwise. Two things could rescue the shallower shape:
the up path's own convolutions widen the field further, and the evidence that
separates two joined outlines may be entirely local to the seam, in which case
no unit ever needs to see both glasses at once. It is flagged here because it
is far cheaper to check with arithmetic beforehand than to diagnose afterwards,
when all you have is a network that quietly never separates anything.

## The first head: which pixels are glass

The shape is settled, so the two heads can be taken in turn, and the first is
the simpler. It has one output channel, it gives one number per pixel, and that
number is how sure the network is that the pixel is glass. A function that
squashes any number into the range zero to one turns it into a probability, and
a threshold on that probability is the mask.

Training needs a **loss**, which is one number saying how wrong an answer was
and which the nudging then tries to reduce. The ordinary loss for a yes-or-no
answer per pixel is **binary cross entropy**: for a pixel that really is glass
the penalty is smaller the higher the probability the network gave it, so being
sure and right costs almost nothing while being sure and wrong costs a great
deal, and for a table pixel it is the same with the probability flipped. Then
the penalty is averaged over every pixel in the picture.

**That average is where the trouble is**, and the trouble comes straight out of
this cell's geometry. Seen from the top, a glass covers a small patch of a large
picture, and there are only a handful of glasses, so the great majority of every
picture is bare table. Glass is the rare class by a wide margin. A network can
therefore lower the average a long way by learning exactly one thing, which is
to say "not glass" everywhere: the many table pixels then cost almost nothing
each, and the few glass pixels cost a great deal each but there are few of
them. The network has been rewarded for producing an empty picture, and this is
worst early in training, when saying nothing is the easiest improvement
available.

Two standard fixes exist, and **both are prescriptions here rather than
descriptions of what is built**.

The first is to **weight the rare class up**, multiplying every glass pixel's
contribution by the ratio of the two class sizes, so that the glass pixels and
the table pixels contribute equally to the total. Saying nothing is then no
longer an improvement at all.

The second is to **add a loss that measures overlap rather than counting
pixels**. The **Dice coefficient** is twice the number of pixels that both the
answer and the truth call glass, divided by the total number either of them
calls glass. It is one for a perfect match and zero when they share nothing,
and it has no term for the table at all. Using one minus Dice alongside the
weighted cross entropy is the usual recipe, from Milletari and colleagues, 2016
([arXiv:1606.04797](https://arxiv.org/abs/1606.04797)).

![Bare table outnumbers glass by a wide margin in every picture from the top, so a score that counts pixels is already high for a network that answers table everywhere, while a score that measures overlap gives that same network nothing.](../../../images/02-segment-glasses/06-most-pixels-are-table.png)

The general lesson is worth more than the detail: **a score that rewards saying
nothing will be optimised by a network that says nothing.**

## The second head: which way is the middle of my own glass

The first head stops exactly where the problem starts asking which glass is
which, so this is where the second head comes in. It keeps the network's shape
and its training recipe unchanged and adds two more output channels, holding
the two parts of an arrow. Nothing else about the network changes, which is why
the two heads are one network and not two.

### Why the arrow is an easier question than it looks

The arrow runs from a pixel to the middle of that pixel's own glass, so the
longest arrow that can ever occur is half the widest footprint the cell
handles. Every training target is therefore a pair of numbers inside a small
and known box, and **a target that is bounded is far easier to fit than an
unbounded one**. The network is never asked for a large number, so it never has
to learn how large numbers scale.

The second head also spends none of its capacity on the easy question, because
the loss is applied **over glass pixels only**. Most pixels in a picture from
the top are table, and a table pixel has no correct arrow at all, since there
is no glass for it to point at. So the arrow loss is multiplied by the mask
before it is added up, and the network is scored on the arrow only where the
question has an answer.

One more choice inside the loss matters. The arrow is scored by how far it is
from the true arrow, measured in a way that does not let a handful of wild
pixels dominate every update. Pixels right at the edge of a glass, where a
pixel may genuinely belong to either of two glasses, are exactly the wild ones,
and a loss that squares every error would let them drown out the many pixels
that are nearly right.

### Which frame the arrow is measured in

This is the one decision inside the second head that is worth going through
slowly, because the two reasonable answers give the network two different jobs.

**The arrow can be measured in the picture.** Then the target is a shift of so
many pixels across and so many down, and the network is predicting something
about the photograph. This is what the built network does, and it is why the
network is also told where in the frame each pixel sits: the same glass seen
near the middle of the frame and seen out at the edge needs a different arrow,
and the position channels are what let the network tell those two cases apart.

**Or the arrow can be measured on the table.** Every glass pixel has a depth
reading, and depth with the camera's own pose turns a pixel into a point in the
room, which drops onto a place on the table. So the arrow could be a distance
on the table instead, and then it would not depend on the camera at all: the
same glass would demand the same answer wherever the camera stood and wherever
in the frame it appeared. The price is that the arrow then needs the depth
reading at run time, so the solution would lose the one thing it gets for free
by working on the picture, which is an answer that does not depend on depth
coming back. That matters because real glassware returns almost no depth, and
it is the reason this choice is worth stating rather than assuming.

![An arrow measured in the picture is a different number for the same glass at every range, while an arrow measured on the table is the same number wherever the camera stood, which is the whole of the choice between the two frames.](../../../images/02-segment-glasses/06-image-space-against-table-space.png)

Either way the votes are what comes next, and the rest of this document does
not depend on which frame was chosen.

## From votes to glasses

Each glass pixel now has a vote, so the remaining question is how a cloud of
votes becomes a count of glasses. One glass's votes should land in one tight
pile, so the question is where the votes pile up.

**What is built counts them.** Every vote is added into a tally the size of the
picture, the tally is smoothed a little so that votes landing on neighbouring
places reinforce each other, and then the largest place in the tally is taken
as a middle, the votes around it are set aside, and the next largest place is
taken, until no place has enough votes left to be a glass. The pixels whose
votes landed near one middle are that middle's glass.

**The published method for the same job is mean shift**, and it is worth
knowing because it is what the general idea is called. Put a circular window
down on one vote, move the window to the average position of the votes inside
it, and repeat until it stops moving; each move is a step uphill towards
thicker votes, and the votes whose windows stop in the same place are one pile
(Comaniciu and Meer, 2002). Its important property is what it does **not** need
to be told: unlike methods that divide data into a fixed number of groups,
nothing has to say how many piles to expect. That matters here more than
usually, because in this problem the count *is* the answer.

![One glass's votes land in one thick patch and two glasses' votes in two, and the published method for finding those patches slides a window uphill to the average of the votes inside it until it stops, so the starts that stop together are one glass.](../../../images/02-segment-glasses/06-vote-cloud-and-mean-shift.png)

Both forms have exactly one number to choose, which is how close two votes have
to be to count as the same pile, and it is pinned at both ends before anything
is run. The **floor** is the spread of one glass's own votes, because a window
much smaller than that scatter fits inside one pile and climbs some lump within
it, so one glass comes back as several peaks. The **ceiling** is the closest
two middles can ever be, which is two of the narrowest glasses of the kind
standing as close as the cell allows, because a window reaching much more than
half of that covers both middles at once and the two piles merge into one.
There is comfortable room between those two limits. It is worth seeing what a
careless choice costs, because the failure is quiet: a window large enough to
span the narrowest possible gap between middles swallows two middles whole, so
it merges exactly the pairs this solution exists to separate, and it does so
without complaining, because a merged pile looks perfectly tight.

Two checks go with the counting. The first is in the built code; the second is
a prescription.

**A pile needs enough votes.** A glass seen from the top covers many pixels, so
a pile built from a small fraction of the votes a whole glass should cast is
doubtful however tight it looks. This is the check that catches confident
agreement between witnesses who all stood in the same wrong place: a glass
reduced to a crescent down one edge votes only from that crescent, and those
votes agree closely with each other while being wrong together.

**A pile needs a believable width.** The pixels that voted into one pile are
fitted with a circle on the table, and a pile whose fitted width falls outside
the range this kind of glass can be is not reported as a glass, whatever the
votes say. So the network proposes and the arithmetic disposes, which is what
keeps this solution inside the same safety argument as rules on the table: a
learned part decides which pixels group together, and a rule nobody trained
decides whether the result is believable.

## The two rungs: where the labels come from

Everything up to here is one method, and nothing in it says where the training
labels come from. That question has two answers, and the rest of the method
does not change between them. The network is the same network, the two heads
are the same two heads, the votes are the same votes and the checks are the
same checks. **Only the source of the labels changes**, which is why the two
are two rungs of one solution rather than two solutions.

The first rung takes its labels from the bench's answer key, which makes them
free and exact. The second rung takes its labels from the arm's own movement,
which makes them neither free nor exact, and buys something else instead. The
second rung is the point of this document, and the first is best read as the
thing it is a step up from.

## Rung one — labels from the answer key

The bench renders every picture itself, so alongside the grey picture and the
depth reading it has an **id image**: at every pixel, which glass that pixel
shows, or nothing. The [test bench](../the-bench.md) describes it in full,
including the rule that a method may be trained on id images from the training
half of the arrangements and is never given one while answering. This rung is
built on that permission.

From an id image both heads' labels fall out by arithmetic.

**The first head's label is the id image with the identities forgotten.** A
pixel is glass if the id image names any glass there, and table otherwise.
There is nothing to judge and nothing to draw.

**The second head's label is a subtraction.** For a pixel the id image assigns
to one particular glass, the target arrow is that glass's middle minus the
pixel's own position. The bench knows where each glass stands because it put it
there, so both ends of the subtraction are known exactly, and the arrow is a
calculation rather than an opinion.

So the labels are free, in the sense that asking for them costs no more than
asking for the picture, and exact, in the sense that there is no judgement in
them anywhere to be wrong. That is a better position than almost any real
vision project is in, and it is the whole reason training from scratch is
sensible here. No annotator also means no limit on how many arrangements can be
labelled beyond the time it takes to render them.

The honest weakness of this rung is not in the labels. It is in what they
depend on. The id image comes from the simulator's own record of what it
rendered, and a real camera on a real table has no such record. So everything
this rung learns is learned from a source that exists only while the glasses
are simulated, and the day the cell meets real glasses, this rung has to be
labelled again by somebody drawing round things. The second rung is what
removes that dependency.

## Rung two — labels from the arm's own movement

The second rung asks the same network the same two questions and fits it with
no answer key at all. Nothing in the simulator's record is read, not even
during training.

What replaces the answer key is a fact about this cell that is easy to pass
over. **The camera is on the wrist, so the arm knows exactly how it moved the
camera between two pictures.** That movement is not estimated from the
pictures. It is commanded, and then read back from the joint encoders. So for
two pictures of a scene that stood still while the camera moved, geometry says
where each surface point must have landed in the second picture, given how far
away it is. Points on one glass therefore move together, and points on a
different glass at a different distance move by a different amount. **That
agreement is the label.**

![The arm's own encoders say exactly how far it slid the camera between two pictures of a still scene, and every pixel of the near glass then shifts by one amount while every pixel of the far glass shifts by another, which is the agreement this rung uses in place of an answer key.](../../../images/02-segment-glasses/07-two-views-parallax.png)

### Parallax: the shift goes as one divided by the depth

The effect the rung lives on is called **parallax**, and you have seen it from
a moving train, where the near fence races past the window while the far hills
barely move. When the camera slides sideways, a surface moves across the
picture by an amount equal to the slide divided by how far away the surface is.
Near things move a lot, far things move a little, and things infinitely far
away do not move at all.

Two consequences matter. The first is that the relationship is one divided by
the depth, so it is steep close up and nearly flat far away: the same
difference in depth is worth a great deal of separation near the camera and
almost nothing far from it. The second is that the separation between two
surfaces' shifts grows in step with the slide, so **a longer slide buys more
separation, in proportion**. That turns the arm into a dial it can set
deliberately, and it is the reason this rung can say in advance how far it must
move to settle a particular doubt.

![How far a surface moves between the two pictures goes as one divided by its depth, so the effect is steep close up and nearly flat far away, and the separation between two glasses' shifts grows in step with the slide, which is what turns the arm into a dial.](../../../images/02-segment-glasses/07-depth-against-shift.png)

### Why the slide has to be sideways, and why the top view is the weak case

Parallax separates two surfaces by how far apart **in depth** they are, so it
separates two glasses only when the gap between them is much larger than the
range of depths each glass covers by itself. That condition is worth checking
against the two places this cell puts the camera, because it comes out
differently in each.

**From the top it is a weak signal, for two reasons.** Two glasses of one kind
have their rims at nearly the same height, so from a camera looking straight
down they are at nearly the same distance from the lens, and there is almost no
depth gap between the two objects to work with. Worse, each glass on its own
runs from its rim, well up towards the camera, down to the table far below it,
so each glass by itself covers a wide range of depths and both cover the same
wide range. Two ranges of shifts lying on top of each other cannot be told
apart however far the camera slides.

**From the side the geometry turns over.** A glass standing in line behind
another is much further back than either glass is wide, so the gap between the
two objects is now large while the range of depths each covers by itself is
only its own width, which is small. The two sets of shifts end up far apart,
which is exactly what parallax needs. And the arm already slides the camera
sideways at every survey station, because a station takes two pictures a short
distance apart; a slide taken deliberately for this purpose is the same kind of
movement, just longer and from the side.

![The loop this rung prescribes would not take another picture and hope: it would name the doubt in pixels, divide by how much separation one millimetre of slide is worth, move the arm exactly that far, and check each region that came back against the range this kind of glass can be.](../../../images/02-segment-glasses/07-deliberate-motion-loop.png)

So this rung's labels come mostly from pictures taken from the side, which has
a plain consequence worth stating rather than hiding. **The labels for the
hardest case, which is the merge in a picture from the top, are the ones this
rung is worst at producing**, because that is exactly where parallax is weak.
The rung still trains the network that runs on pictures from the top, because
training and running are separate, and only the trained network is used at run
time, on exactly the input the bench hands every solution. But the supervision
it gets for the merge is weaker than the answer key's, and that is the price of
not reading the answer key.

### What an embedding is

The first rung could turn its labels into targets directly, because the answer
key says which glass a pixel belongs to and therefore where its arrow should
point. Movement gives something weaker: it says whether two pixels belong
together, and nothing about which glass they are or how many glasses there are.
So the network's output has to change shape to carry that weaker information,
and the shape it changes to is called an embedding.

An **embedding** is a short list of numbers the network produces at every
pixel, arranged so that **two lists being close together means the two pixels
belong together**. The numbers themselves mean nothing on their own. There is
no channel that says "glass number two" and no number that counts anything.
Only the distances between lists carry information.

A comparison helps here. Think of giving every pixel a position on a map, where
the map has no place names and no scale, and the only thing you may ask is how
far apart two pixels are. Pixels on one surface are put in one neighbourhood,
pixels on a different surface are put in a different neighbourhood, and
grouping the pixels afterwards is reading the neighbourhoods off the map. The
map is the embedding, and the network's job is to draw it.

### What contrastive training does

With that output shape in place, the labels from movement are exactly the right
kind of label for it.

Two pixels whose shifts between the two pictures agree to within the
measurement noise are a **positive pair**, meaning they are on the same
surface. Two pixels whose shifts differ by clearly more than the noise are a
**negative pair**, meaning they are not. Those two verdicts are all movement
gives, and they are all this training needs.

**Contrastive training** turns them into a loss. Pick a pixel, take its
positive partner and a handful of negative ones, and make the loss low only
when the partner's list is closer to the pixel's list than every one of the
negatives' lists is. Training therefore **pulls** a pixel and its positive
partner together on the map and **pushes** a pixel and its negatives apart. Do
that over many pixels and many pairs, and the map arranges itself so that the
pixels of one surface sit together and the pixels of different surfaces sit
apart, without anybody ever having said what a glass is.

![Every pixel becomes a short list of numbers, and training pulls a pixel and its positive partner together while pushing it away from its negatives, so the pixels of one surface end up in one neighbourhood without anything ever naming a glass.](../../../images/02-segment-glasses/07-embedding-space.png)

What that gets right is worth naming, because no appearance-based rule can do
it. The line the embedding draws runs where the **depth jumps**, and not where
the brightness changes. So two glasses of the same kind, the same colour and
the same shape are no harder for this rung than two different ones, which is
the exact case that defeats a method relying on how things look.

What it does not get is equally worth naming. **Nothing in an embedding names a
glass and nothing counts them.** The map says which pixels belong together, and
something else has to decide how many neighbourhoods there are. So the lists
are grouped, each group becomes a candidate region, and every candidate region
goes through the same checks rung one's piles go through: enough pixels, a
circle fitted on the table, and a width inside the range this kind of glass
can be. The grouping step here is doing the job mean shift does for the votes,
and it has the same one number to choose and the same two limits pinning it.

That makes the check after the network less optional here than anywhere else in
this document, because a merged pair comes back from an embedding as one tidy
region with no complaint attached to it at all.

![Two glasses of one kind standing the same distance from the lens shift by the same amount however far the camera slides, so there is nothing for parallax to separate them by; and where there is, an embedding still says only which pixels are alike and never how many glasses there are.](../../../images/02-segment-glasses/07-the-limit.png)

### What this rung buys and what it costs

It buys one thing, and the thing is about the future rather than about this
problem. **This is the only rung whose supervision a real arm also has.** A
real arm has joint encoders and a wrist camera, which is everything this rung
needs. Every other solution here that is fitted in this cell, including rung
one, is fitted to labels that exist only because the pictures were rendered, so
every one of them would have to be labelled again from nothing on the day the
code met real hardware. This one would not.

![A person drawing round every glass, the simulator's record of which glass each pixel shows, and the arm's own encoders are three ways to get the answer written beside a picture, and only the last of them is one a real arm would still have.](../../../images/02-segment-glasses/07-where-the-labels-come-from.png)

It costs three things. The labels are **weaker**, as the section above says,
and weakest exactly where the problem is hardest. The labels are **not free**,
because collecting them means moving the arm, and an arm movement costs seconds
while a picture costs milliseconds and a pass of the network costs less than
that; so a training set gathered this way is paid for in arm time rather than
in render time. And the whole rung depends on there being something to match
between two pictures, so it is weakest where the pictures are plainest, which
is a surface of one even shade.

The honest conclusion is that rung one is the rung to build for this problem
and rung two is the rung to reach for when the cell leaves the simulator. This
cell has a working depth camera, which measures directly what parallax is being
trained to infer, so inside this problem rung two is doing hard work for
information the cell already has. It earns its place the day that stops being
true.

## The training set

Both rungs need a set of arrangements to learn from, and two decisions about
that set decide whether the network works at all. They apply to each rung
equally.

**Spawn the hard case.** The cell's own rule keeps glasses a comfortable
distance apart, and a training set drawn only from that rule never once shows
the network a pair that a page of arithmetic could not already separate. So the
teaching has to happen on pairs standing far closer than the rule allows, which
is what the bench's crowded family of arrangements is for. But keep the easy
case too, in proportion, or the network quietly learns that there is always a
pair to find. As a general rule, **the edge of the specification should sit
somewhere in the middle of the training set**, so that the network has met
worse than it ever will in use.

**Randomise everything that is not shape.** A simulator will render the same
table under the same light for ever, and a network given a constant will use it
as a clue: if every training picture has the table at the same shade, the
network is free to learn that glass means the pixels that are not that shade.
That rule scores perfectly on the training pictures and on the held-out ones
too, because both came out of the same renderer, and then somebody changes a
light and the network fails for a reason that appears in no number.
**Domain randomisation** is the fix, and it is blunt: vary the lighting, the
table's colour and texture, the glass tint, the exposure, the picture noise,
the camera pose and the number and placement of the glasses, over a range wider
than anything expected, so that none of them is a reliable shortcut and shape
is the only thing left that predicts the answer (Tobin and colleagues, 2017,
[arXiv:1703.06907](https://arxiv.org/abs/1703.06907)).

![The same kind of arrangement rendered under different lighting, table colour and texture, glass tint, exposure, picture noise and camera pose, with the lens and the picture size held fixed on purpose, so that shape is the only thing left that predicts the answer.](../../../images/02-segment-glasses/06-domain-randomisation.png)

One thing would **not** be varied, which is the camera's lens. The focal length
and the picture size are facts about the camera this cell has rather than
nuisances to be made robust against, and teaching the network to cope with
lenses it will never meet would spend its limited capacity on nothing.

And the split between learning and marking is the bench's, not this solution's.
The bench divides its arrangements into a training half and a test half, so a
network fitted on the first is marked on the second and is never tested on an
arrangement it learned from.

## The masks are what this contributes

Everything above produces one thing, and it is worth being plain about what
happens to it.

This solution contributes **only the masks**: which pixels in which picture are
which glass. Turning a mask into a place on the table and a rough width is the
bench's job, done by one shared piece of arithmetic that every one of the six
solutions goes through, and it is described in the [test
bench](../the-bench.md). So a difference in the score belongs to the mask. This
solution cannot win by measuring more cleverly and it cannot lose by measuring
worse.

One consequence follows, and it is the same for all six. **No model here
produces a pose.** Models produce masks. The place comes from the depth
readings under the mask together with the camera's own pose, by arithmetic, and
a glass standing upright on a flat table has no orientation left to find.

## How the concepts fit together

Everything above is one chain, and it is worth seeing the whole of it in order
before the failure cases, because each stage inherits what the last one got
wrong.

A **survey picture** goes in, with its depth reading and two channels saying
where in the frame each pixel sits. The **network**, whose down path and up
path are shaped so that a unit near the output can see a large part of the
scene, produces two things at every pixel: a **probability** that the pixel is
glass, and an **arrow** towards the middle of that pixel's own glass. The
probability is thresholded into a **mask**. Every mask pixel adds its arrow to
its own position and casts a **vote**. The votes pile up, one pile per glass,
and the piles are counted without anything having been told how many to expect.
A pile with too few votes is doubted; a pile whose fitted width is not one this
kind of glass could have would be turned down by the check prescribed above.
What survives is one mask per glass, handed to the bench's shared arithmetic.

Three things in that chain are worth holding on to.

**The output shape is what makes the merge answerable.** A class map has
nowhere to record which glass a pixel belongs to, so no amount of training
could make one separate two joined glasses. An arrow has somewhere to record
it, and the separation falls out of counting rather than out of cutting.

**The loss is what most often goes wrong.** Most pixels in these pictures are
table, so a measure of success that counts pixels rewards a network for saying
nothing, and the fix is to score the overlap of the shape rather than the count
of the pixels.

**The arithmetic after the network is what keeps the whole thing honest.** The
network proposes; the vote count and the kind's own range of widths dispose. A
pile of votes implying a footprint no glass of this kind could have is turned
down by a rule nobody trained.

## When the glasses are completely hidden

Every solution in this problem has to answer the case where a glass is absent
from the picture altogether, and this one's answer has two halves that point in
opposite directions.

The first half is unusually good. Every other method here separates two glasses
by finding something between them: a gap in the picture, a strip of bare table,
a seam. This one finds nothing between them. Each glass pixel votes for its own
glass's middle whether or not anything can be told apart anywhere, so a glass
that is only **partly** covered still speaks. Its surviving pixels vote for the
right middle, and they do not have to be joined to each other, or to make a
recognisable shape, or to lie on any particular part of the glass. Because one
kind spans a small glass and a much taller one, a glass can be left with only a
crescent of itself even at the gap the cell guarantees, and a crescent is
exactly what voting handles best.

![When a tall glass's outline is thrown far enough outwards to swallow a shorter neighbour standing at the closest separation the cell allows, not one vote mentions the covered glass; swing the same pair off the line out from the camera and the crescent that survives casts few votes, but they pile up almost exactly where that glass really stands.](../../../images/02-segment-glasses/06-hidden-from-above.png)

The second half is a hard stop. **A glass covered completely owns no pixels, so
it casts no votes, so there is no pile to find.** There is no loose spread to
notice and no short count to fail, because both of this solution's own alarms
are measurements of votes and there are no votes to measure. The vote map
simply has one peak where two glasses are standing, and nothing in it is wrong.

![Looking level the near glass's outline covers the far one whole with no outward throw needed, and the single pile of votes left behind is tight, well filled and a believable width, so nothing about it looks wrong; step the far glass off the line of sight and the strip that appears votes for its own middle.](../../../images/02-segment-glasses/06-hidden-from-the-side.png)

It is worth settling whether more training would help, because it is the first
thing anyone suggests. Take the arrangement with the hidden glass and the same
arrangement with that glass taken away: the two produce the same picture, pixel
for pixel. No function of the picture can tell them apart, whatever its shape
and however it was fitted, because the thing that differs between the two
arrangements left no trace in the input. **This is a fact about the input and
not about the model**, and it is the same limit every method here that works
from pixels runs into.

There is one qualification worth working out rather than waving at, because it
is the obvious objection. A network *can* be trained to mark part of an object
it cannot see, and the name for that is **amodal segmentation**, which means
predicting an object's whole extent rather than only its visible pixels. The
bench could label it, because it can render each glass's mask with the other
glasses taken away. But amodal completion extends evidence, so it needs some of
the object to be visible to extend from, and with no pixels at all there is
nothing to extend. A model asked to mark a glass that *might* be standing
behind this one would be inventing an arrangement rather than reading a
picture. Whether predicting the hidden part of a partly visible glass is worth
doing is studied inside [RF-DETR fine-tuned](06-rf-detr-fine-tuned.md), which
carries that question as its own second rung.

The two views lose a glass in different ways, and the difference is worth
separating, because what this solution cannot see is not the same in each. From
the top, a glass disappears only under the outward throw of a taller
neighbour's outline, and that throw has to run so far out that the covered glass
was never inside the frame to begin with. Nothing is missing from the picture;
the picture never reached that part of the table.

![Four pictures from the top as the camera slides outwards show the covered glass sitting outside the frame in every one of them, so from the top this solution loses a glass only where its picture never reached, and a short sideways move of the camera ends even that.](../../../images/02-segment-glasses/07-hidden-from-above.png)

From the side nothing is thrown outwards at all. The near glass's outline simply
lies over the far one's along the line the two of them stand on, and pushing the
far glass further back does not help, because it only shrinks in the picture
while the near outline stays as it is. Here the covered glass is inside the
frame, and this solution still has no pixel of it to vote with.

![Looking from the side, the far glass contributes not one pixel while it stands on the line of sight, however much further back it is put, and only sideways movement brings it back — in less of a slide than a survey station already makes between its two pictures.](../../../images/02-segment-glasses/07-hidden-from-the-side.png)

So what this solution hands on is not a glass but a region: the part of the
table it could not have seen. Working out that region is geometry on the
outward throw of the outlines and on the glasses that *were* found, and going
to look at it is a movement of the arm. Both belong to [looking again at what
was hidden](../hidden-glasses.md), which every one of the six shares, and this
solution contributes the masks that argument starts from and none of the
argument.

## A worked example

This example follows one crowded arrangement through the method, and it is the
case the whole solution exists for.

**What is on the table.** Two glasses of one kind stand much closer together
than the cell's own rule allows, which is the crowded family of arrangements
the bench draws deliberately. There is still bare table between their rims, but
only a little.

**What the picture does to them.** From the top, each glass's outline is thrown
outwards from the point below the lens, so each covers more of the picture than
its footprint deserves. The two outlines join. A flood fill over the mask comes
back with **one** shape, spanning both glasses and the gap between them, and
that shape is far wider than any glass of this kind can be. A rule that checks
widths therefore notices that something is wrong — and that is all it can do,
because nothing in a class map says where to cut.

**What the votes do.** The pixels of the two glasses are exactly as joined as
before, because nothing has changed about the pixels. Their votes are not. Each
glass's pixels point inwards at their own glass's middle, so the votes land in
two piles whose separation is the full distance between the two middles, which
is comfortably more than the counting step can span. Both piles are tight, both
have plenty of votes, and a circle fitted to each pile's voters comes back
inside the range this kind of glass can be. **Two glasses, two masks, out of a
picture in which the pixels themselves never came apart.**

**The case that defeats the votes.** Now stand one glass mostly behind another,
so that only a crescent down one side of it is ever visible. It contributes a
small fraction of the votes it should, and worse, every one of them comes from
that same crescent, so the votes agree with each other and are wrong in the
same direction. The pile lands off the true middle and its spread comes out
much wider than a tight pile's. The short count is the alarm the code measures
and it fires on its own; the wide spread is the second warning this document
prescribes. Neither of them is the network's own opinion of itself: both are
measurements of the votes. The pair is reported as one the arm could not
separate, with its reason, which is a result this problem asks for and not a
failure.

![The less of a glass reaches the picture the fewer votes it casts and the further its votes sit from their own peak, so a short count and a wide spread are two separate warnings, both of them measurements of the votes rather than the network's opinion of itself.](../../../images/02-segment-glasses/06-too-few-votes.png)

**What it costs in time.** Running the network on a picture costs milliseconds.
Moving the arm to a new place and letting it settle costs seconds. So the
balance of this solution is to compute freely and move rarely, and the whole of
its cost sits in building it rather than in running it.

## What it needs

This is the most demanding of the six to set up, and it is worth being plain
about that before anyone starts.

**A deep learning framework and the environment to run it in.** PyTorch, on
this machine's integrated graphics through the MPS backend. No dedicated
graphics card is needed, and nothing is downloaded, so there is no licence
condition on anything this solution uses.

**A training set.** For rung one, arrangements rendered by the bench with their
id images, which costs render time and nothing else. For rung two, pairs of
pictures with the camera's movement logged beside each one, which costs arm
time.

**A training run**, before the solution can answer anything at all. The network
is small and the pictures are small, so the run is short enough on this machine
to be repeated whenever the cell changes, which is the property that makes the
next line bearable.

**A file of weights kept in step with the cell.** This is the cost that is easy
to forget. The code says what the cell is; the weights say what the cell looked
like when they were fitted. Change the lighting, the camera or the range of
proportions a kind is drawn from, and the file is quietly out of date in a way
that no test of the code will notice.

At run time what it needs is small: one pass of a small network over a small
picture, which is nothing beside the seconds an arm movement costs.

## Where it is strong and where it breaks

**It has no domain gap.** Everything it knows came from this cell's own
pictures, so nothing it learned has to be transferred from a world it will
never see. This is the reason it is the control for the comparison, and it is
the one strength no borrowed model can claim.

**It separates glasses that are joined in the picture.** Nothing has to find a
boundary, so nothing can get a boundary wrong, and the separation survives
cases where there is no gap anywhere to find.

**It is unusually good at a partly hidden glass.** A crescent of surviving
pixels still votes towards the right middle, and the votes do not have to be
joined to each other or to make a recognisable shape.

**Its doubt costs nothing.** How many votes a pile holds is a confidence per
glass, and how far its votes sit from its own peak would be a second one. Both
are measurements of the votes rather than the network's opinion of itself,
which is a better kind of warning than most learned methods give; the count is
the one the code measures.

**It is blind to a glass hidden completely.** No pixels means no votes, which
means no pile, no spread and no short count. This is a fact about the input
rather than about the model.

**It needs a training set and a training run before it answers anything.** The
borrowed model that changes nothing can be pointed at a picture on the day it
is downloaded. This one cannot, and that gap in setup cost is real.

**Its answer cannot explain itself.** When a fitted circle is wrong you can
print one number and see why. When a network is wrong you can look at the
picture and guess. The arithmetic wrapped around it is what makes that
tolerable.

**Its weights are a second copy of the cell**, and keeping them in step with
the first copy is a maintenance job rules on the table simply does not
have.

## The general ideas behind this

Every part of this is standard, and most of the parts are not new. Two things
here are unusual: fitting from a random start on rendered pictures rather than
fine-tuning something large, and asking one network a question about classes
and a question about instances from the same shared body.

### Semantic segmentation — a class label at every pixel

Rather than a box round an object, produce a label for every pixel. The idea
became practical with **fully convolutional networks** (Long, Shelhamer and
Darrell, [arXiv:1411.4038](https://arxiv.org/abs/1411.4038)), which replaced a
classifier's final layers with convolutions so that a picture of any size maps
to a label map of the same size.

It is used wherever the extent of a thing matters more than a box round it,
such as medical imaging, aerial pictures and industrial inspection. It is
rarely right for counting or separating individuals, because a class label has
nowhere to record which object a pixel belongs to, and that is the limitation
the second head here exists to remove. For more, see [image
segmentation](https://en.wikipedia.org/wiki/Image_segmentation).

### The encoder–decoder with skip connections

Halve the resolution repeatedly while widening the channels, then enlarge it
back, copying each level on the way down across to the matching level on the
way up so that detail lost going down is available coming back. That is the
**U-Net** (Ronneberger, Fischer and Brox,
[arXiv:1505.04597](https://arxiv.org/abs/1505.04597)), designed for biomedical
images with very few training examples, which is exactly why it suits a small
rendered training set.

It remains the default for a small segmentation problem. It is rarely right for
problems needing broad understanding of a scene or many classes, where a large
pre-trained network earns its size, because a small network knows only what its
receptive field and its training set contained.

### Overlap losses — scoring the shape rather than the pixel count

Cross entropy averages over pixels, so on a picture that is mostly background a
model can score well by predicting background everywhere. **Dice** and
**intersection over union** losses score the overlap between the predicted and
the true regions instead, and they are usually added to cross entropy rather
than used in place of it (Milletari and colleagues,
[arXiv:1606.04797](https://arxiv.org/abs/1606.04797)).

They are used wherever one class is far rarer than the other, which covers most
medical and industrial segmentation. They are rarely enough on their own,
because an overlap score says nothing about how confident the individual pixels
were, which is information a feedback loop can use.

### The Hough transform — local evidence for a global claim

A single edge pixel cannot say where a shape is, but it can vote for every
shape that would explain it; add up the votes and the peaks are the shapes
really present. Hough's 1962 patent did this for straight lines, and the
**generalised Hough transform** (Ballard, 1981) extended it to any shape by
replacing the equation with a table of offsets.

It is used for finding shapes in noisy, cluttered pictures where much of the
outline is missing. Voting is naturally robust to things being hidden, because
the visible part still votes correctly. It is rarely right for shapes with many
parameters, because the table of votes grows explosively with them. For more,
see the [Hough transform](https://en.wikipedia.org/wiki/Hough_transform).

### Learned voting — replacing the table of offsets with a model

**Hough forests** (Gall and Lempitsky, 2009) first replaced the hand-built
table of offsets with a learned one. The neural descendants apply the same
structure to pixels and points: **VoteNet**
([arXiv:1904.09664](https://arxiv.org/abs/1904.09664)) has points from a depth
sensor vote for object middles, and **PVNet**
([arXiv:1812.11788](https://arxiv.org/abs/1812.11788)) has pixels vote for
landmark points, specifically because voting survives things being hidden.

These are used for finding objects in cluttered scenes and bin picking, where a
method needing the whole object visible fails and a method needing only a
fraction does not. They are rarely right for objects with no well-defined
middle, or where the offsets are large compared with the picture, because then
the number the network has to predict grows and the votes scatter.

### Mean shift — finding peaks without being told how many

Slide a window to the average of the points inside it and repeat until it stops
moving; every starting point that ends in the same place belongs to one peak
(Comaniciu and Meer, 2002). Unlike methods that divide data into a fixed number
of groups, it does not need the count in advance, which is the whole point
here, because the number of groups is the answer.

It is used for finding peaks when the count is unknown, such as tracking and
colour segmentation. It is rarely right for data with many dimensions, where it
is slow and the window size becomes impossible to choose, and it is poor for
groups of very different densities, where one window size cannot serve both.
For more, see [mean shift](https://en.wikipedia.org/wiki/Mean_shift).

### Self-supervised learning — labels from the structure of the data

Rather than annotate anything, construct a task whose answer is already implied
by the data, so that the supervision is free and unlimited. Rung two is this
idea with the arm's own encoders as the generator of labels.

It is used where unlabelled data is abundant and labels are expensive, and in
robotics, where a robot's sense of its own position is a label generator that
never tires. It is rarely right where the invented task can be solved by a
shortcut that does not need the understanding you wanted, and designing a task
with no shortcut is the hard part of the field. For more, see [self-supervised
learning](https://en.wikipedia.org/wiki/Self-supervised_learning).

### Geometry as supervision, and depth without depth labels

If a camera's movement between two pictures is known, then a point's position
in the first picture determines where it must appear in the second, given its
depth. That is the **epipolar constraint**, and it turns a depth guess into a
checkable prediction. **SfMLearner** (Zhou and colleagues,
[arXiv:1704.07813](https://arxiv.org/abs/1704.07813)) built a training recipe
on it with no depth labels at all, and **Monodepth2** (Godard and colleagues,
[arXiv:1806.01260](https://arxiv.org/abs/1806.01260)) fixed most of its
practical failures.

Those methods have to **estimate** the camera's movement, and that estimate is
where a large part of their error lives. In this cell the movement is not
estimated but commanded, so the hardest half of that literature's problem does
not exist here. The approach is rarely right for surfaces without texture or
for scenes where the objects move between the two pictures, which breaks the
still-scene assumption entirely. For more, see [structure from
motion](https://en.wikipedia.org/wiki/Structure_from_motion).

### Grouping by shared motion — common fate

Points on one rigid surface move together in the picture and points on a
different surface at a different distance do not. The Gestalt psychologists
called that **common fate**: a flock of birds is one flock because the birds
turn together. It is one of the very few grouping cues that needs no model of
appearance at all, which is why it works on two identical glasses.

It is used for video segmentation and tracking, and anywhere objects are hard
to tell apart by how they look. It is rarely right where nothing moves relative
to anything else, which is exactly why rung two is weak from the top: two rims
at nearly the same distance have almost no relative movement to group by.

### Contrastive training — turning "these belong together" into a loss

Pull together the outputs for things that belong together and push apart the
outputs for things that do not. **SimCLR** (Chen and colleagues,
[arXiv:2002.05709](https://arxiv.org/abs/2002.05709)) and **MoCo** (He and
colleagues, [arXiv:1911.05722](https://arxiv.org/abs/1911.05722)) are the
standard references, and the related idea of giving each pixel an identity code
and grouping the codes is **associative embedding** (Newell and colleagues,
[arXiv:1611.05424](https://arxiv.org/abs/1611.05424)).

It is used wherever pairs that belong together are easy to construct but
categories are not, which is most of self-supervised vision. It is rarely
enough on its own when the count of groups matters, because an embedding says
which things belong together and never how many groups there are, and that is
exactly the gap the checks after the network fill here.

### Training from scratch against fine-tuning a large model

The last idea is the choice this whole document turns on. Fine-tuning wins
whenever labels are scarce, which is almost always. Training from scratch wins
in the narrow case where labels are free, the problem is small, and the borrowed
weights would bring knowledge of a world you do not have. This cell is that
narrow case, and it is worth noticing how rare that is rather than generalising
from it.

## Where it sits among the other five

This solution is the one with nothing borrowed in it, so its place in the
comparison is fixed by that and not by its score.

Against [rules on the table](01-rules-on-the-table.md), the comparison is
whether a fitted grouping rule beats a written one. The written rule is a page
of arithmetic that explains its own failures and needs no training set, and on
any day the depth readings work it is the easier tool. This solution earns its
place where no single written rule can be made to work, which is where two
glasses leave no gap anywhere to find.

Against the four that borrow weights, the comparison is the one this solution
exists for. [YOLO as it downloads](03-yolo-zero-shot.md) borrows everything and
fits nothing. [YOLO fine-tuned](04-yolo-fine-tuned.md) and [RF-DETR
fine-tuned](06-rf-detr-fine-tuned.md) borrow a starting point and then fit on
this cell's pictures as this solution does. [SAM 2 with a
keeper](05-sam2-with-a-keeper.md) borrows a large model and fits only a small
decider on top of it. Every one of those four carries a domain gap of unknown
size, and this solution carries none, so **the distance between this line and
those four is the measurement of what borrowing was worth**. If the borrowed
models do no better than a network fitted here from random numbers, then their
size and their licences bought nothing in this cell.

One pairing is sharper than the rest and is worth knowing while reading this
one. [YOLO as it downloads](03-yolo-zero-shot.md) and [YOLO
fine-tuned](04-yolo-fine-tuned.md) are the same model from the same library
with the same starting weights, and the only difference between them is whether
it was trained on this cell's pictures. The gap between those two measures what
training bought. The gap between this solution and the pair of them measures
what the starting weights bought.

And what this solution cannot do, on any day, is notice a glass that is absent
from the picture. That failure is answered by geometry rather than by
appearance, in [looking again at what was hidden](../hidden-glasses.md), which
all six share. This solution contributes the masks that argument starts from,
and none of the argument.

← [Rules on the table](01-rules-on-the-table.md) · [YOLO as it
downloads](03-yolo-zero-shot.md) →
