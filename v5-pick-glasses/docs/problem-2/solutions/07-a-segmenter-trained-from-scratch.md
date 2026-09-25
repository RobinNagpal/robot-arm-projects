# Solution 7 — a segmenter trained from scratch

## In one paragraph

This cell does not need a general-purpose model. One class, one kind of object,
one camera, one lighting rig, pictures 320 by 240. A small encoder-decoder — a
U-Net of about 482,000 weights, which is arithmetic on its channel widths and
not a measurement — can be trained from random initialisation on Gazebo renders
alone, because the simulator labels every picture exactly and for nothing. It
returns a probability at every pixel, and the pixels it is unsure about are a
reason to take another picture. It gives semantic and not instance
segmentation, and it learns Gazebo, not the world.

## The problem this solves

[`problem.md`](../problem.md) sets the job. Four to six glasses stand on a table.
They are all of one kind and the kind is known. The arm photographs them from a
wrist camera and has to say **which pixels belong to which glass**, give each
glass a place on the table and a rough footprint width, and name honestly any
pair it could not tell apart.

The first difficulty is that two glasses far apart on the table can still land
on top of each other in a picture, if the camera happens to be in line with
both. Grouping pixels by whether they touch — a flood fill — then returns one
blob, and one blob means one glass to everything downstream.

The programmed answers to that work on the depth reading: lift the points into
the room, and cluster them where they actually are rather than where they
happen to land in the picture. They work well and they are the core of this
project's answer. But they lean entirely on depth, and they lean on the table
plane being findable.

This solution asks a different question. **Can a network be taught to label the
glass pixels directly, from the colour picture, with no rule about planes or
heights written anywhere?** And can that be done here, on an Apple Silicon Mac
with no NVIDIA graphics card, with no photograph of a real glass anywhere in
the project, in hours rather than days?

## The idea, in plain words

![A picture goes in, one probability per pixel comes out](../../../images/problem-2/07-what-is-asked-for.png)

Look at the right-hand panel. It is the same width and the same height as the
picture on the left, but every pixel holds one number between 0 and 1: how sure
the network is that this pixel is glass. The plot underneath follows the dashed
line across one glass. The number is near 0 over the table, near 1 over the
glass, and it passes through the middle only in a band about two pixels wide at
the rim, where genuinely nobody could say.

That is the whole output. Not boxes, not shapes, not sizes — a number per
pixel.

The reason to think a small network can do this well here is that **the cell is
narrow**. A model that has to cope with any object, any camera and any room
needs a great deal of capacity to hold all of that. This cell has:

- one class — glass, or not glass;
- one kind of object, drawn at proportions inside one kind's plausible range,
  65 to 230 mm tall with footprints 45 to 105 mm across;
- one camera, at 320 x 240 with fx = fy = 277.1 pixels;
- one lighting rig, in one simulator;
- objects always standing upright, always opaque.

Almost all the variety a general model is built to absorb simply does not
occur. So the network can be small, and a small network with an endless supply
of exactly labelled pictures is something you can train from nothing in an
afternoon.

## Where it comes from

Three separate ideas meet here, and it is worth taking them in order.

**A neural network, in this context, is a function from a picture to a picture
of labels.** It is not a brain and it is not a search. It is a fixed chain of
arithmetic — multiply the pixels in a small neighbourhood by some numbers, add
them up, discard the negatives, repeat — and the *numbers* are what make one
network different from another. Those numbers are called **weights**. They
start as random noise. **Training** shows the network a picture, compares what
it produced with the answer that was wanted, works out for each weight whether
nudging it up or down would have made the answer better, and nudges. Repeat a
few hundred thousand times and the weights stop being noise. Nobody wrote the
rule the network ends up applying, and nobody can read it back out.

**Encoder-decoder networks for dense prediction** came out of the problem that
a classifier throws away position. A network that says "this picture contains a
glass" is allowed to forget where; a network that has to label every pixel is
not. The fix, which is the shape of everything in this family, is to go down to
a small, wide summary of the whole picture and then climb back up to full size.

**Training on synthetic pictures** is older than either, and it became
respectable once people found a way to stop the network memorising the
simulator. That way is domain randomisation, described further down.

### Fine-tuning, and why the usual advice does not apply

![Two ways to start a network, and why only one of them is open here](../../../images/problem-2/07-scratch-or-fine-tune.png)

Read the table from the top. The two columns are the two ways to begin, and
every row is something that differs between them.

**Fine-tuning** means not starting from noise. You take a network somebody else
trained — usually on a very large collection of labelled photographs — throw
away its last layer, bolt your own on, and continue training on your own small
set of examples. The borrowed part is called a **backbone**, and the idea is
that the early layers of any vision network learn much the same things (edges,
corners, textures, the look of a curved surface) whatever the task, so you may
as well not pay to learn them again.

It is the standard advice everywhere, and the reason is worth stating plainly:
**labelled real pictures are scarce.** Somebody has to sit down and draw round
every object in every picture. A few hundred is a week of work; a few hundred
thousand is a funded project. Against that, a backbone that took somebody else
a month of eight graphics cards is free, and it cuts the number of labels you
need by an order of magnitude.

Two things make that argument collapse in this cell.

**First, every backbone worth borrowing was fitted to real photographs.**
ImageNet ([image-net.org](https://www.image-net.org/)) and COCO
([cocodataset.org](https://cocodataset.org/)) are photographs. So is everything
trained on them, and so are the promptable foundation models such as Segment
Anything ([arXiv:2304.02643](https://arxiv.org/abs/2304.02643), code
Apache-2.0). This project's rule is that everything a solution needs must be
producible by Gazebo on this machine, and a file of weights fitted to
photographs of the real world is not. It is not a judgement about whether those
models are good. They are excluded by where their numbers came from. The
versions of this project that *do* allow them are written up separately in
[`learned-with-hardware.md`](learned-with-hardware.md).

**Second, the scarcity that fine-tuning exists to solve is not present.** The
simulator already knows which pixels are which object — it drew them. Asking
Gazebo for a render and its per-object mask costs the same as asking for the
render. There is no annotator, so there is no annotator's budget and no
annotator's mistakes. Labels are not scarce here. They are free.

There is a third, smaller reason. Most ready-made backbones want CUDA kernels,
and this machine has no NVIDIA card. That alone would not decide anything —
plenty of them run on CPU — but it removes the last practical argument for
borrowing.

So: random initialisation. Which is only reasonable *because* of the second
point. Training from scratch on a few hundred hand-drawn labels would be a bad
idea. Training from scratch on an endless supply of exact ones is not.

## How it works, step by step

### The architecture: an encoder-decoder, and specifically a U-Net

![The U-Net shape, with the tensor sizes for a 320 x 240 input](../../../images/problem-2/07-the-u-net-shape.png)

Follow the left column down, then the right column up. The dashed green lines
are the part that gives the shape its name.

**The down path, or encoder.** Start with the picture: 320 wide, 240 tall, four
channels deep — red, green, blue and depth. Apply two convolutions. A
**convolution** takes a small window, here 3 x 3, slides it over the whole
picture, and at each position multiplies the values in the window by a fixed
set of weights and adds them up. One set of weights produces one output
channel; sixteen sets produce sixteen. The result is still 320 x 240, but now
sixteen channels deep instead of four.

Then **halve it**. A 2 x 2 max pool takes each block of four pixels and keeps
the largest, giving 160 x 120. Two more convolutions, this time producing 32
channels. Halve again to 80 x 60, widen to 64 channels. Halve again to 40 x 30,
widen to 128. That last, smallest, widest layer is the **bottleneck**.

Two things happen on the way down, and they pull against each other. Each
halving throws away exactly where something is — after three of them, one unit
stands for an 8 x 8 patch of the original. But each halving also means the next
convolution's 3 x 3 window covers four times as much of the original picture.
So the deeper units know less precisely where they are looking and much more
about what is around them. That trade is the whole reason for going down.

A useful thing to notice, since 320 and 240 both divide by 8 exactly: 320 / 8 =
40 and 240 / 8 = 30, with nothing left over. Three halvings need no padding and
no cropping. (They divide by 16 too — 20 x 15 — which matters below.)

**The up path, or decoder.** Now reverse it. A **transposed convolution**, 2 x
2, doubles 40 x 30 back to 80 x 60 while narrowing 128 channels to 64. Then two
more 3 x 3 convolutions, and double again, and again, until the tensor is back
to 320 x 240 with 16 channels. A final 1 x 1 convolution — a window of exactly
one pixel, so no mixing across space at all, just a weighted sum of the 16
channels — collapses it to one channel. A logistic function squashes that to
between 0 and 1, and that is the probability map.

**The skip connections.** Here is the problem the up path has on its own. The
bottleneck knows there is a glass roughly over there, but three max pools have
destroyed the information about exactly which pixel its rim sits on. Doubling
the tensor back up cannot invent that detail; it was thrown away.

So do not throw it away. Before each halving, keep a copy of the tensor. On the
way back up, when the decoder reaches that size again, **glue the copy on** as
extra channels — hence the 128 channels feeding the first decoder convolution
at 80 x 60: 64 from below and 64 copied across. The decoder then has both the
context from below and the sharp edges from the matching level. That is what
the dashed lines are, and what the U in U-Net refers to: down one arm, across
the crossbars, up the other. The design is Ronneberger, Fischer and Brox, 2015
([arXiv:1505.04597](https://arxiv.org/abs/1505.04597)), written for microscope
images, where the same problem — label every pixel, few examples — arises.

### How many weights that is

![Where the weights sit, and what a fourth halving would cost](../../../images/problem-2/07-where-the-weights-are.png)

The left chart is the count per block; the right one is the argument for or
against going one level deeper.

A 3 x 3 convolution from *m* input channels to *n* output channels holds
3 x 3 x *m* x *n* weights, plus one bias per output channel. Everything below
is that formula applied to the widths above, and nothing else. **It is
arithmetic on the channel widths, not a measurement of anything.** No network
was built or weighed to produce it.

| block | what it does | weights |
| --- | --- | --- |
| down 1 | 4 -> 16, then 16 -> 16 | 2,912 |
| down 2 | 16 -> 32, then 32 -> 32 | 13,888 |
| down 3 | 32 -> 64, then 64 -> 64 | 55,424 |
| bottleneck | 64 -> 128, then 128 -> 128 | 221,440 |
| up 3 | double, then 128 -> 64, 64 -> 64 | 143,552 |
| up 2 | double, then 64 -> 32, 32 -> 32 | 35,936 |
| up 1 | double, then 32 -> 16, 16 -> 16 | 9,008 |
| head | 1 x 1, 16 -> 1 | 17 |
| **total** | | **482,177** |

Two things fall out of that table.

**The deep, narrow layers hold nearly all the weights.** The bottleneck and the
first decoder block together are 364,992 of the 482,177 — 76 per cent. That is
because weights scale with the *product* of the channel widths, which doubles
twice per level, while the spatial size shrinks by four. Widening the deepest
level is expensive; widening the first is nearly free.

**The whole thing is small.** At four bytes per weight, 482,177 weights is
1.93 MB. Stored as 16-bit floats it is under a megabyte. This is a file you can
commit, version and regenerate without thinking about it.

### One place where the arithmetic gives a warning

There is a number worth computing before trusting this design, and it is on the
right-hand panel above. It is the **receptive field**: how much of the input one
unit at the bottleneck actually depends on.

Work it out layer by layer. Each 3 x 3 convolution extends the field by one
pixel either side, at whatever scale it is working. Start at 1. Two
convolutions at full scale take it to 5. A pool takes it to 6 and doubles the
scale. Two convolutions at that scale: 14. Pool: 16. Two more: 32. Pool: 36.
Two more at the bottleneck's scale of 8: **68**.

So one bottleneck unit sees a 68 x 68 patch of the input. At survey height —
450 mm above the table, fx = 277.1 — one pixel covers 450 / 277.1 = 1.62 mm, so
that patch is about **110 mm of table**. The glasses in this cell are
guaranteed to stand **at least 150 mm apart**. The deepest layer, which is the
one with the context to reason about a neighbour, cannot see two glasses at the
same time.

A fourth halving fixes it: 20 x 15 at the bottleneck, a receptive field of 140
pixels, about 227 mm of table. It costs 1,941,249 weights instead of 482,177 —
four times as many. Whether the extra level is needed is **uncertain**: the
decoder's convolutions widen the field further on the way back up, and the
evidence a network uses to separate two overlapping silhouettes may be entirely
local to the seam. It is flagged here because it is the kind of thing that is
much cheaper to check with arithmetic before training than to diagnose after.

### The loss, and why most pixels being table matters

![The class imbalance, and what it does to a score](../../../images/problem-2/07-most-pixels-are-table.png)

The left panel counts the pixels; the right one shows two different scores
disagreeing about the same three answers.

Training needs a **loss**: one number saying how wrong an answer was, which the
nudging is trying to reduce.

The obvious loss for a yes-or-no decision per pixel is **binary cross entropy**.
For a pixel that really is glass, the penalty is minus the logarithm of the
probability the network gave it — so being sure and right costs nothing, being
sure and wrong costs a great deal. For a pixel that is really table, the same
with the probability flipped. Average over every pixel in the picture.

That average is where the trouble is, and it comes straight out of this cell's
geometry. One picture is 320 x 240 = 76,800 pixels. At survey height a glass
with a 78 mm footprint is about 48 pixels across, so its silhouette is roughly
1,810 pixels. Five of them is about 9,048 pixels — **11.8 per cent of the
picture**. Very nearly nine pixels in ten are table.

So the average is dominated by table pixels, and a network can lower it a long
way without learning anything useful. Suppose it starts by saying 0.5 to
everything: the loss is 0.693 per pixel. Now suppose it learns one thing only —
"say 0.02 everywhere", which is "there is never any glass". The table terms
each cost 0.020, the glass terms each cost 3.912, and the weighted average is
**0.479**. The loss has fallen by nearly a third and the network has learned to
produce an empty picture. That is a real trap, not a theoretical one, and it is
worst early in training when there is nothing better on offer.

Two standard fixes, and this would use both.

**Weight the rare class up.** Multiply every glass pixel's term by a constant
chosen to balance the two classes — roughly 88.2 / 11.8, about 7.5 — so the two
halves of the picture matter equally.

**Add a loss that measures overlap rather than counting pixels.** The **Dice
coefficient** is twice the number of pixels both the answer and the truth call
glass, divided by the total number either of them calls glass. It is 1 for a
perfect match and 0 when they share nothing, and, crucially, it does not have a
term for the table at all. Using 1 minus Dice as a loss, alongside the weighted
cross entropy, is the usual recipe; it comes from Milletari and colleagues,
2016 ([arXiv:1606.04797](https://arxiv.org/abs/1606.04797)).

The right-hand panel is why. Three answers, two scores:

| the answer | pixel accuracy | Dice |
| --- | --- | --- |
| say "table" everywhere | 0.882 | 0.000 |
| every mask 3 pixels too thin | 0.972 | 0.867 |
| exactly right | 1.000 | 1.000 |

Pixel accuracy gives a useless answer 0.882 and a visibly wrong one 0.972 — it
cannot tell them apart from a good one, because it is mostly reporting how many
table pixels were correctly called table. Dice gives the useless answer 0 and
notices the thin masks. A score that rewards saying nothing will be optimised
by a network that says nothing.

### Domain randomisation

![One scene rendered many ways, and what stays fixed](../../../images/problem-2/07-domain-randomisation.png)

Six renders of the same arrangement. Look at what changes between them, and
then at the two lines underneath saying what is deliberately held still.

Here is the failure it prevents. Gazebo will render this table, under this
light, with this grey, for ever, exactly the same way. If every training
picture has the table at the same shade, the network is free to learn "glass
means the pixels that are not that shade of grey". That rule will score
perfectly on every training picture and on every held-out one, because the
held-out pictures came out of the same renderer. Then somebody changes the
world file, or adds a light, or the table texture is updated, and the model
falls over for a reason nobody can see in any of the numbers.

**Domain randomisation** is the fix, and it is blunt: vary everything you are
not trying to teach, scene by scene, over a range wider than anything you
expect to meet. The network cannot then use any of the varied things as a
shortcut, because none of them is reliable. What is left constant is the shape
and position of the objects, so that is what it has to learn. The idea is from
Tobin and colleagues, 2017
([arXiv:1703.06907](https://arxiv.org/abs/1703.06907)), written for getting a
network trained in a simulator to work on a real robot.

It is worth stressing, because it is the part people skip: **it matters even
though this cell only ever runs in one simulator.** The world file will change
during the project's life — lights get added, textures get replaced, the table
moves. A model that has quietly keyed on any of those breaks silently the day
one changes. Randomising is how you find that out during training instead.

What would be varied, scene by scene:

- **light** — direction, intensity, colour temperature, and how many sources;
- **the table** — its colour and texture;
- **the glasses** — tint, reflectivity, and each one's proportions drawn
  independently from its kind's plausible range;
- **the camera pose** — a few millimetres and a degree or two around the
  nominal survey pose, because the arm's own positioning is not exact;
- **exposure and sensor noise**;
- **the arrangement** — four to six glasses, placed anywhere in the 320 x 360 mm
  zone.

And one thing worth randomising **past** the specification: the minimum
separation. The cell guarantees 150 mm, but training with pairs down to 60 or
80 mm makes 150 mm an ordinary interior case rather than the hardest thing the
network ever saw. The edge of the specification should be somewhere in the
middle of the training set.

What would **not** be varied: the camera's intrinsics. fx = fy = 277.1 and
320 x 240 are facts about the camera this cell has, not nuisances to be robust
to. Teaching the network to cope with focal lengths it will never meet spends
capacity for nothing. Likewise the glasses stand upright on a flat table,
because that is the task and not an accident of the setup.

## How it works here

### The input, and the depth channel

Four channels: red, green, blue, and depth. Depth is there and it is free, so
there is no reason to throw it away — but taking it raises a question, because
one of the reasons to want this solution at all is that it does not *need*
depth. If the glasses ever become real glass, the depth camera stops returning
anything useful through them, and every method that clusters points in the room
loses its input at once. A colour-only method survives that day.

If depth is simply fed in, the network will lean on it, because it is by far
the easiest signal in the picture, and the colour path will never develop. The
fix is **modality dropout**: on some fraction of training pictures, replace the
depth channel with zeros. The network then has to be able to work without it.
What fraction is right is a choice, not a measurement; a half is the obvious
starting point and it is **uncertain** whether that is the right number here.

Depth is normalised by dividing by the camera's maximum range, 3.0 m, so the
channel sits in the same 0-to-1 range as the colour. It is not converted into a
height above the table, which would be handing the network the very cue the
clustering solutions use and would make the colour-only claim hollow.

### What the network gives, and what it does not

![A per-pixel class map cannot say which glass](../../../images/problem-2/07-semantic-against-instance.png)

The middle panel is the point. One region, every pixel correctly labelled
"glass", and no way to ask it which glass.

A per-pixel class map is **semantic** segmentation: it says what each pixel is,
not which object it belongs to. Problem 2 asks for **instance** segmentation,
so on its own this solution does not answer the problem, and the separating has
to be added. The two cheap places to add it are a second output channel
predicting each object's **boundary**, so the regions can be cut apart along the
predicted seam, or a pair of channels predicting, at every glass pixel, the
**offset to the centre of its own object**. Offsets fail more gently, because a
seam has to be predicted along its whole length and a single missing pixel
rejoins two objects, whereas offsets are one vote per pixel and a few wrong
votes are simply outvoted. That mechanism is not explained here:
[solution 8](08-per-pixel-votes-for-the-centre.md) is that idea in full.

### The data and the recipe

The training set is generated, not collected. A script spawns a random scene
inside Gazebo ([gazebosim.org](https://gazebosim.org/), Apache-2.0) according
to the randomisation list above, renders it from a survey pose, and writes out
the picture together with the per-object mask the simulator already holds. Two
pictures per station, 120 mm apart, matching what the arm will actually take.

**How much.** A few thousand scenes is the order to aim for — call it 4,000
scenes and 8,000 pictures. Whether that is enough is **uncertain**, and the way
to find out is a curve rather than an argument: train on 1,000, 2,000, 4,000
and 8,000 and see where held-out Dice stops improving.

**The training loop.** Adam as the optimiser
([arXiv:1412.6980](https://arxiv.org/abs/1412.6980)), batches of 16,
normalisation after every convolution — batch normalisation
([arXiv:1502.03167](https://arxiv.org/abs/1502.03167)) is fine at batch 16, and
group normalisation ([arXiv:1803.08494](https://arxiv.org/abs/1803.08494)) is
the alternative if the batch has to shrink. Weighted cross entropy plus 1 minus
Dice. Stop when the held-out loss stops falling.

**The library.** [PyTorch](https://pytorch.org/) (BSD-3-style
[licence](https://github.com/pytorch/pytorch/blob/main/LICENSE)) with
[NumPy](https://numpy.org/) (BSD-3-Clause) for the arrays and
[OpenCV](https://opencv.org/) (Apache-2.0) for the connected-components step
that turns a thresholded map into regions. A U-Net this size is about eighty
lines of PyTorch and is worth writing out rather than importing, but if a
ready-made one is used — `segmentation_models.pytorch`
([github.com/qubvel-org/segmentation_models.pytorch](https://github.com/qubvel-org/segmentation_models.pytorch),
MIT) is the usual choice — note that its encoder defaults to ImageNet weights.
That default has to be turned off explicitly, or the project's rule is broken
by a keyword argument nobody looked at.

**The hardware.** PyTorch reaches the GPU on an Apple Silicon Mac through the
**MPS** backend — Metal Performance Shaders, Apple's own GPU compute library —
by moving tensors to `torch.device("mps")`. Apple documents the setup at
[developer.apple.com/metal/pytorch](https://developer.apple.com/metal/pytorch/).
Two practical notes: some operations are not implemented for MPS and fall back
to the CPU, which is why `PYTORCH_ENABLE_MPS_FALLBACK=1` exists and why a
fallback in the inner loop can cost more than the GPU saves; and MPS uses the
machine's unified memory, so there is no separate card memory to run out of.

**The time budget, honestly.** Here is what can be computed and what cannot.

The arithmetic per picture *can* be computed. Summing the multiply-accumulates
over every convolution at its own spatial size gives **3.08 billion** per
forward pass, or about **6.2 GFLOPs**. A backward pass is roughly twice a
forward one, so a training step over 8,000 pictures is about **148 TFLOPs** per
epoch. That is arithmetic on the same channel widths as the parameter count.

The rate at which this machine actually performs it **has not been measured and
is not guessed at here.** It depends on which operations fall back to the CPU,
on how fast the data loader keeps up, and on the machine. The honest recipe is:
time one epoch, multiply by the number of epochs, and decide then. For scale
only, and as pure division: if the machine sustained a useful 1 TFLOP per
second the epoch would take about two and a half minutes, and if it sustained a
fifth of that, about twelve. Forty epochs is then somewhere between an hour and
eight. "An afternoon" is plausible on that arithmetic and is **not a
measurement**.

Rendering time is in the same position. Gazebo has to set up and render 8,000
pictures; the per-scene cost has not been measured. Time ten and multiply.

## A worked example

Take the merge that this problem exists to prevent, and put numbers on it.

**The geometry.** The camera is at survey height, 450 mm above the table,
looking down. fx = 277.1, so at the table plane one pixel covers

    450 / 277.1 = 1.62 mm

and the picture covers about 520 x 390 mm. One caution about that figure: it is
exact only at the centre of the frame. The left and right edges of the picture
are further from the camera — 450 / cos 30 degrees = 520 mm — so a pixel there
covers 1.88 mm, about 15 per cent more. Every number below uses the
centre-of-frame scale and is therefore good to about that.

**The two glasses.** Both are of a kind whose footprint runs 60 to 90 mm; both
happen to be 78 mm across. They stand 180 mm apart on the table, which clears
the 150 mm minimum comfortably. Unluckily, the line joining them points almost
straight away from the camera.

Each is 78 / 1.62 = **48 pixels** across. Their centres land **30 pixels**
apart in the picture. Since 30 x 1.62 = 48.6 mm, only 49 mm of their 180 mm
separation is across the camera's view; the rest,

    sqrt(180^2 - 48.6^2) = 173 mm

is along the line of sight, where the picture cannot record it.

Two discs 48 pixels across with centres 30 pixels apart overlap. The union runs
from 24 pixels left of the near centre to 24 right of the far one:
30 + 48 = **78 pixels** across, 79 counting both edge pixels. Its area is about
3,120 pixels.

**What the network returns.** One region. The probability map is near 1 across
all 3,120 pixels of it, because every one of them genuinely is glass. The
network is not wrong. It answered the question it was asked, and the question
had no place in it for "two".

A 78-pixel region is 126 mm wide, and no glass of this kind is wider than
90 mm, so a circle fit against the kind's known range can *notice* that
something is off. Noticing is not separating.

**What the confidence map adds.** This is where the loop starts, and the
numbers are in the next section.

**What the second look does.** Move the camera round to look across the line
joining the two glasses rather than along it, from the side-on standoff of
380 mm. There one pixel covers 380 / 277.1 = **1.37 mm**. The 173 mm that was
hidden along the line of sight is now 173 / 1.37 = **126 pixels** across the
picture, and each glass is 78 / 1.37 = **57 pixels** wide. Two 57-pixel discs
with centres 126 pixels apart leave a clear gap of about 69 pixels between
them. They come back as two regions, each confident to its rim, and the merge
is gone.

## The feedback loop

![Interior doubt marks the region to photograph again](../../../images/problem-2/07-confidence-map.png)

Three panels: the probability map, then only the pixels it is unsure about,
then the two ways of counting those pixels.

A per-pixel model has a natural measure of doubt built into its output, which
most methods do not. It does not return a mask; it returns a **confidence map**,
one probability per pixel. Thresholding it at 0.5 gives a mask and throws the
doubt away. Keeping it gives the loop something to run on.

Call a pixel **doubtful** if its probability is between 0.3 and 0.7 — the
network cannot say. Then there are two things to read off.

**Where the doubt is matters more than how much of it there is.** Look at the
middle panel. Every region has a doubtful rim, because at the edge of any
object some pixel really is half glass and half table. That is not news; it
happens on every object in every picture and it says nothing about whether the
region is one glass or two. The merged pair has something else: a band of doubt
running across the **inside** of the region, where the near glass's rim passes
over the far one.

So the statistic has to exclude the rim, or the rim will drown it. Cut a collar
three pixels wide off the outside of each region and count doubt only in what
is left. On the drawing in that figure — and these are measurements of the
drawing, which is arithmetic on discs, not of a trained network — the numbers
come out as:

| region | doubtful, whole region | doubtful, interior only |
| --- | --- | --- |
| A, on its own | 7.8% | 0.0% |
| B, on its own | 7.8% | 0.0% |
| C, on its own | 7.8% | 0.0% |
| D, the merged pair | 17.7% | 13.3% |

Counted over the whole region the pair is a little over twice its neighbours,
which is a signal but a weak one, and it would get weaker for a bigger glass
because perimeter grows more slowly than area. Counted over the interior it is
the difference between nothing and something. That is the statistic to use.

**The three things a loop needs**, from the overview's test:

1. **A measure of doubt.** Interior doubtful fraction, per region. The
   threshold is best set relative to the other regions in the same picture —
   "far more doubtful than its neighbours" — rather than as an absolute number,
   because that self-calibrates against the lighting and the exposure of that
   particular frame.
2. **An action that could reduce it.** The band's direction says which one. The
   band marks where one object's edge crosses another, so the two objects are
   stacked along the direction perpendicular to the band. The camera should move
   so that it is no longer looking along the line joining them — round, not
   closer.
3. **A budget.** Moving the arm and letting it settle costs seconds; a picture
   costs milliseconds; one forward pass through this network is 6.2 GFLOPs, so
   tens of milliseconds at most. The expensive thing is the move. Cap it at two
   extra looks per doubtful region, and when the budget is spent **report the
   region as doubtful rather than guessing**, which is the handover problem 2
   owes to problem 3.

The loop's weakness is stated under "How it fails" below, and it is the
important one: this loop only fires when the network is unsure. A network that
is confident and wrong fires nothing.

## What it needs

**Software**, all of it already in this project's environment or one line from
it:

- [PyTorch](https://pytorch.org/) — BSD-3-style
  [licence](https://github.com/pytorch/pytorch/blob/main/LICENSE) — the network,
  the training loop, and the MPS backend.
- [NumPy](https://numpy.org/) — BSD-3-Clause — arrays.
- [OpenCV](https://opencv.org/) — Apache-2.0 — connected components on the
  thresholded map.
- [Gazebo](https://gazebosim.org/) — Apache-2.0 — the renderer and the source
  of every label.

**Data.** A randomising spawner and a script that dumps each render beside its
per-object masks. A few thousand scenes; how many is enough is uncertain.
Nothing from outside the simulator, and nothing drawn by hand.

**Hardware.** The machine this project already runs on. No NVIDIA card, no
CUDA, no downloaded weights.

**Time.** Rendering the set, then training. Both are bracketed above and
neither has been measured on this machine.

**Artefacts to keep.** One weights file, 1.93 MB as 32-bit floats, version
pinned and regenerable from the spawner's seed.

## What it is good at

**It does not need depth.** The map can be learned from colour alone, which
matters on the day the glasses stop being opaque. Every method that clusters
points in the room loses its input at once when the depth camera starts seeing
through things; this one degrades instead of stopping. That property has to be
trained for, with modality dropout, or it will not be there.

**It is small enough to retrain on a whim.** Change the lighting rig, change
the kind of glass, change the table: regenerate the set and retrain. A fine-tune
of a large backbone is most of a day and a careful choice of learning rates; at
482,177 weights this is a script you start and come back to.

**It writes no rule down.** There is no plane-fitting tolerance, no height
threshold, no assumption that the table is flat and level. Those are the
parameters that need adjusting every time the cell changes.

**It reports its own doubt for free.** Very few programmed methods can say "I
am not sure about this bit", and it is exactly what the loop needs.

## What it is bad at

**It does not separate instances.** This is the big one. A class map is one
region per clump, and the separating has to be bolted on. On its own this
solution does not answer problem 2.

**It says nothing in millimetres.** The output is pixels. Every number the arm
acts on — a position on the table, a footprint width — still has to come from
the depth reading under those pixels, with the camera pose and the intrinsics.
The network narrows down which pixels; it does not measure anything.

**It carries a size prior nobody can read.** Trained only on one kind drawn from
one plausible range, the network has learned that range, in a form nobody can
inspect or state. That is uncomfortably close to this project's central rule
that no glass's size appears anywhere. It is not a constant in a file, but it
is a fact about glass sizes baked into a file that the project ships. The
report should say so.

**It cannot be debugged by printing a number.** When the clustering solution is
wrong you can print the plane fit and the point count and see why. When this is
wrong, you can look at the confidence map, and that is all.

## How it fails

**It learns Gazebo.** A network trained only on renders has fitted one
renderer's shading model, one noise model and one idea of what a highlight looks
like. Pointed at a real camera it will not work, and domain randomisation
narrows that gap without closing it. **This is an accepted trade here, and it
should be stated rather than buried:** this cell only ever runs in Gazebo, so a
model that only works in Gazebo is a model that works. It stops being acceptable
the moment a real arm is involved, and at that point this solution needs
either real data or a much more serious randomisation effort — which is the
same conclusion the sim-to-real literature reaches.

**It is confident and wrong.** The failure the loop cannot catch. Two glasses
merge into one region with a clean edge, no interior band, and probabilities
near 1 throughout. Nothing fires. One large glass is reported and everything
downstream believes it. This is the *merged* failure that the problem statement
singles out as the one to watch hardest, precisely because it does not announce
itself. The guard against it is not the network. It is the arithmetic
downstream: fit a circle to the region's footprint and check the diameter
against the kind's known range, and refuse a 126 mm footprint for a kind whose
widest member is 90 mm.

**It fails on something outside its training set without saying so.** A network
asked about something it has never seen does not return "I do not know"; it
returns a confident answer from whichever part of its training was nearest. A
glass lying on its side, an object of a different kind, a reflection on the
table — all of these produce an answer with no warning attached.

**It breaks silently when the world file changes.** New light, new table
texture, camera moved: the model is now being asked about something slightly
outside what it was fitted to. Nothing throws. The Dice on a fresh held-out set
drops, if anyone runs it. Domain randomisation is the mitigation and a held-out
set regenerated after every world change is the detection.

## When it would be the right choice

Two conditions have to hold together, and neither is enough alone.

**The labels have to be free.** Which means a simulator that already knows the
answer and will render as many examples as asked. If somebody has to draw the
masks, this is the wrong approach and fine-tuning is the right one.

**The problem has to be narrow.** One class, one camera, one cell, one lighting
setup. Narrowness is what lets the network be small, and small is what lets it
train from noise in hours on a machine with no graphics card.

Both hold here, which is why training from scratch beats fine-tuning in this
cell and almost nowhere else. Note what happens when either goes: widen the
problem to several kinds of object in several rooms and the network has to grow
and the data has to grow with it; take away the simulator and the labels have
to be drawn. Either change flips the recommendation back to the standard advice.

There is also a condition that does *not* have to hold: nobody needs a graphics
card. That is the point of keeping it this small.

## The general methods behind this

This is mainstream deep segmentation, shrunk. Every component is standard and
most of them are ten years old; what is unusual is only the decision to train
from random initialisation on synthetic data rather than fine-tune something
large.

### Semantic segmentation — a class label at every pixel

Rather than a box round an object, produce a label for each pixel. The idea
became practical with **fully convolutional networks** (Long, Shelhamer and
Darrell, [arXiv:1411.4038](https://arxiv.org/abs/1411.4038)), which replaced a
classifier's final dense layers with convolutions so that any-sized images map
to any-sized label maps.

- **Mostly used for** medical imaging, satellite and aerial imagery, driving
  scenes, and industrial inspection — anywhere the *extent* of a thing matters
  more than its bounding box.
- **Rarely right for** counting or separating individuals, because a class label
  has nowhere to record *which* object a pixel belongs to. Two touching things
  of the same class come back as one region, which is the limitation this
  solution runs into and [solution 8](08-per-pixel-votes-for-the-centre.md)
  removes.
- **More:** [image segmentation](https://en.wikipedia.org/wiki/Image_segmentation).

### The encoder–decoder with skip connections — U-Net

Halve the resolution repeatedly while widening the channels, then double it back
up, and copy each encoder level across to the matching decoder level so that
detail lost on the way down is available on the way back. That is **U-Net**
(Ronneberger, Fischer and Brox,
[arXiv:1505.04597](https://arxiv.org/abs/1505.04597)), designed for biomedical
images with very few training examples, which is exactly why it suits a small
synthetic dataset.

- **Mostly used for** dense prediction with limited data: cell and organ
  segmentation, defect detection, depth and normal estimation. It is still the
  default architecture for a small segmentation problem.
- **Rarely right for** problems needing broad semantic context or many classes,
  where a pretrained transformer or a large backbone earns its size. A small
  U-Net knows only what its receptive field and its training set contained.

### Overlap losses — scoring the shape, not the pixel count

Cross-entropy averages over pixels, so on an image that is 90 per cent
background a model can score well by predicting background everywhere.
**Dice** and **IoU** losses score the overlap between predicted and true
regions instead, and are usually added to rather than substituted for
cross-entropy (Milletari et al.,
[arXiv:1606.04797](https://arxiv.org/abs/1606.04797)).

- **Mostly used for** class-imbalanced dense prediction, which is nearly all of
  medical imaging and most industrial inspection.
- **Rarely right alone** — Dice is unstable for very small or empty targets, so
  the standard practice is a sum of the two losses rather than either by itself.

### Domain randomisation — training on variation instead of realism

A simulator will render the same table under the same light for ever, and a
network handed a constant will use it. Randomise everything you are *not*
teaching — lighting, textures, colours, camera pose, exposure, noise, the number
and placement of objects — so that the only stable signal left is the one you
want learned (Tobin et al.,
[arXiv:1703.06907](https://arxiv.org/abs/1703.06907)).

- **Mostly used for** sim-to-real transfer in robotics, where synthetic data is
  free and real labelled data is not. It is the cheapest reality-gap fix and
  often enough on its own.
- **Rarely sufficient for** anything depending on fine appearance that the
  renderer does not model — transparency, subsurface scattering, specular
  highlights, exactly the properties real glassware has. It also costs capacity:
  a model robust to everything is worse at any one thing.
- **More:** [domain adaptation](https://en.wikipedia.org/wiki/Domain_adaptation)
  for the alternatives.

### Training from scratch against fine-tuning a foundation model

The default advice everywhere is to start from pretrained weights. It is right
when data is scarce and the domain is broad — and wrong when the domain is one
class, one camera and one lighting rig, and labels are free. A borrowed backbone
spends most of its capacity on the thousand things this cell never contains, and
weights fitted to real photographs are an artefact from outside the simulator.

- **Mostly used:** fine-tuning wins almost always in general computer vision,
  and [SAM](https://arxiv.org/abs/2304.02643) and
  [Mask R-CNN](https://arxiv.org/abs/1703.06870) are what a normal project
  reaches for first.
- **Rarely right to skip it** unless the problem really is narrow and the labels
  really are free. Both conditions hold here; when either goes, so does the
  argument.

## Where it sits

It competes directly with **cluster on the table**, which answers the same
question by rule rather than by fitted numbers, needs no training and no model
file, and beats it on everything except the day depth stops working. It is
incomplete on its own and leans on **per-pixel votes for the centre** to turn a
class map into one mask per glass — that is the same network with two more
output channels, not a different solution. Its confidence map is exactly the
doubt signal that **move the camera** needs to decide where to look next, so the
two compose rather than compete. And if the goal is the smallest learned thing
that earns its place, **a learned verifier over the clusters** is cheaper than
this, because it only has to answer "one object or two" about a crop somebody
else found.

The version of this idea that starts from a downloaded backbone is written up
in [`learned-with-hardware.md`](learned-with-hardware.md), beside the condition
it fails.
