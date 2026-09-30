# Problem 2 — how it would be solved

## Introduction

[The problem](../problem.md) says what is asked for and why it is hard. This
document is the way into the seven solutions. It covers what they share: what
each does about a glass nobody saw, the few words they use, where a learned part
can sit, what it means to choose the next measurement, and the rule every one of
them had to pass. It ends with what was built, and where that can fail.

Each solution has a full document of its own, and this one does not repeat them.
The table of [the seven](#the-seven-in-two-folders) says in one line what each
is and which difficulty it attacks.

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the two places the camera works from, from the top and from the side, all four
> sensors, and the words this project uses them with.

## Where we are

Four to six opaque glasses of one kind stand on the table. The kind is tapered
and its range of sizes is wide, and the glasses stand at least 150 mm apart
between centres, which leaves a narrow strip of bare table between any two rims.
The arm has to produce a set of pixels, a place and a rough width for each
glass, and two honest statements: which glasses it could not separate, and where
it could not have seen a glass at all. It does not pick anything up and it does
not measure a shape.

[The problem](../problem.md#the-three-difficulties) sets out the three
difficulties: a glass can be missing from a picture altogether, glasses merge in
the picture while standing apart on the table, and the camera can no longer
stand wherever it likes. All three come from **splay**, which [the
cell](../../the-cell.md#the-words) explains.

The solutions lean on one property of splay that is easy to miss. It is a
**radial scaling** about the point directly below the camera: it multiplies
distance from that point and size by the same factor. So it never changes how
wide a glass looks *as an angle*; it only decides how far out along its own
direction the outline lands. That is what turns the difficulties from things you
can describe into things you can compute.

## When a glass is completely hidden

This is the worst of the three difficulties, because **every check in this
project is a check on something that was found**. A width can be compared
against what the kind allows, a fitted circle has a residual, and a group can be
asked how many stations saw it. A glass that produced no pixels gives none of
them anything to fire on.

The two places the camera works from produce it in different ways, and only one
of them produces it in this cell.

- **Looking straight down**, a tall glass's outline sweeps over a short one. The
  range of sizes inside this kind is wide enough for that to happen at the
  guaranteed gap between centres rather than needing the glasses closer than the
  cell allows, with the covering glass comfortably inside the frame. So from the
  top a glass can go missing either because something covered it or because the
  survey never looked at that piece of table, the two are indistinguishable from
  the picture, and the signal worth having is therefore *unsearched area* rather
  than *hidden glass*.
- **Looking level**, no sweep is involved. One glass stands in front of another,
  which needs neither a height difference nor closeness: two glasses 600 mm
  apart hide each other as completely as two 150 mm apart, and the one that goes
  is the further one, whatever its height.

Every solution document ends with a section called "when the glasses are
completely hidden". They do not agree, and the disagreement is the useful part.

| # | Looking straight down | Looking level |
|---|---|---|
| [1](programmed/01-split-the-blob-in-the-picture.md#when-the-glasses-are-completely-hidden) | never asked: the method reads a bottom edge against a horizon, and there is none | answers "one glass" confidently and is not wrong about anything it was asked |
| [2](programmed/02-cluster-on-the-table.md#when-the-glasses-are-completely-hidden) | partly: it cannot find the glass but it can bound where one could be, and the stations then look | no: the blocked strip never closes, so it cannot be bounded |
| [3](programmed/03-move-the-camera.md#when-the-glasses-are-completely-hidden) | no: the cure is the station layout, not anything the loop decides | partly: it refuses poses that would hide one *known* glass behind another |
| [4](learned/04-choosing-the-next-look.md#when-the-glasses-are-completely-hidden) | partly: doubt attaches to a place rather than a glass, though the candidate poses are one ring at one height | no: two pictures differing by zero pixels cannot carry different doubt |
| [5](learned/05-is-anything-hiding-there.md#when-the-glasses-are-completely-hidden) | yes, as far as ranking goes: the blind wedge has a measurable reach and area | barely: the strip is computed from what was already known, so nothing varies |
| [6](learned/06-a-network-trained-from-scratch.md#when-the-glasses-are-completely-hidden) | no, and this is the cleanest no here: zero pixels cast zero votes | no: the two scenes produce the same picture pixel for pixel, though a sliver of a glass is worth more here than anywhere else |
| [7](learned/07-self-supervised-from-the-arms-own-movement.md#when-the-glasses-are-completely-hidden) | no: hands it to solution 2 and the overlapping stations | yes: the revealing pictures are already being taken |

## The words

**Mask**, **patch** and **cluster** mean what [the
cell](../../the-cell.md#the-words) says. Three more run through all nine.

**Connected components**, also called a flood fill, turns a mask into separate
objects: take a glass pixel nobody has visited, spread to every glass pixel
touching it, call that patch one object, and repeat. It answers only *are these
pixels joined?*, which is why two glasses that touch in a picture come back as
one.

A **point cloud** is every pixel with a depth reading turned into a point in the
room. The pixel gives the direction, the depth gives how far along it, and the
camera's pose gives where the direction starts.

**Segmentation** is used for three different jobs, and only one of them answers
this problem.

![Three things the word segmentation is used for](../../../images/problem-2-three-answers.png)

**Detection** puts a rectangle round each object, so pixels where two overlap
belong to both. **Semantic segmentation** labels every pixel "glass" or not, and
nothing says which glass, so two overlapping glasses become one region.
**Instance segmentation** labels every pixel with a class *and* with which
object it belongs to, so five glasses come back as five masks. This problem asks
for instance segmentation, and anything less has not answered it.

## Three families, and what "hybrid" means

**Programmed.** You state the rule and the computer applies it. No training
data, no weights file, no graphics card. It runs in about a millisecond, works
on an object it has never seen, and when it fails you can usually find out why
by printing one number. Its limit is that somebody has to be able to write the
rule down.

**Learned.** The behaviour comes from numbers fitted to examples, so it can do
things nobody knows how to state. It pays with a training set, a weights file
that has to be kept in step with the world, hardware to run it, and an answer
that cannot explain itself.

**Hybrid.** Both together, arranged so that the learned part sits inside
something checkable.

### The question to ask of any hybrid

The question is not how much of it is learned but **where the learned part
sits**, because that decides what happens when the model is wrong, and a model
is sometimes wrong by construction.

![Where the learned part sits decides what happens when it is wrong](../../../images/where-the-learned-part-sits.png)

- **As the decider.** The model's answer is the answer. A wrong answer is acted
  on, because nothing downstream is in a position to disagree.
- **As a proposer.** The rules hand the hard cases to the model and check its
  suggestion. A wrong suggestion is rejected by arithmetic, and the system falls
  back to what it had.
- **As a ranker.** The rules generate every candidate and reject the unsafe
  ones; the model only orders the survivors. A bad ordering costs one wasted
  attempt and nothing worse.
- **As a verifier.** The rules act and the model checks what happened. A wrong
  check costs one extra measurement.

In the last three, **the learned part's mistakes are limited by something that
does not need the model to be right**. A better model makes failures rarer; only
the arrangement puts a ceiling on how bad they get.

A hybrid is usually *cheaper* than a fully learned solution, not dearer, because
the learned piece has one narrow job. Learning "is this one object or two?"
needs a small fraction of the data that "find all the objects" needs, and trains
on an ordinary laptop.

## Feedback: choosing what to measure next

**The number of measurements does not have to be decided in advance.**

![Deciding what to measure next, rather than measuring once](../../../images/open-and-closed-loop.png)

An open-loop pipeline takes a fixed number of pictures, works everything out and
acts, so an object that turns out unclear stays unclear and everything
downstream inherits the doubt without being told. A closed loop takes a picture,
works out what is not settled, asks *where would I have to look for this to
become clear?*, goes and looks, and repeats.

It needs three things, and with only two it is not really a loop:

- **a measure of doubt** that separates settled from not sure, rather than always
  producing an answer;
- **actions that could reduce it**, with some way of guessing which would help;
- **a budget**, because every extra look costs arm time. The loop stops when
  nothing is unclear or the budget is spent, and reports what is still doubtful
  rather than guessing.

That reverses the usual instinct. **The thing to save here is not computation.
It is the number of times the arm has to move**: a move costs seconds, and any
of these models costs milliseconds.

## The rule every solution passed

A solution is listed here only if **everything it needs can be produced by the
simulator on the machine this project runs on**: no graphics card, no robot on a
bench, no real-world data. The four conditions that follow, and the good answers
that fail them, are in [the ones that need more than a
simulator](learned/learned-with-hardware.md).

Two consequences are worth seeing coming. The rule pushes the learned solutions
towards **small models trained from scratch on synthetic data**, away from the
usual advice to fine-tune a large model; for a cell with one kind of object, one
lighting setup and one camera, that is less of a sacrifice than it sounds. And
the first three solutions need nothing added to the environment, while
everything from the fourth on begins by adding a dependency, and the learned
ones add a large one.

## The seven, in two folders

The solutions are split by whether they contain a trained model. The three in
[`programmed/`](programmed/) are rules somebody wrote down; the four in
[`learned/`](learned/) all have numbers fitted to examples somewhere inside
them, whether the fitted part decides the answer or only puts candidates in
order.

| # | Solution | Family | Where the model sits | The idea | What it attacks |
|---|---|---|---|---|---|
| 1 | [Split the blob in the picture](programmed/01-split-the-blob-in-the-picture.md) | programmed | — | each flat stretch along a patch's bottom edge is one glass standing on the table; needs no depth readings | the merge, mainly from the side |
| 2 | [Cluster on the table](programmed/02-cluster-on-the-table.md) | programmed | — | drop the depth points onto the table and group them by distance; then compute which parts of the table nobody could have seen | the merge, **and where nobody could have seen** |
| 3 | [Move the camera](programmed/03-move-the-camera.md) | programmed | — | walk round, testing reach, then line of sight, then the planner; cover the unsearched patches with the fewest positions | no usable viewpoint, and unsearched places |
| 4 | [Choosing the next look](learned/04-choosing-the-next-look.md) | hybrid | ranker | keep solution 3's candidates and vetoes, and order the survivors by a learned score: either how much doubt a look removes, or the chance it changes the answer | which look to spend the budget on |
| 5 | [Is anything hiding there?](learned/05-is-anything-hiding-there.md) | hybrid | verifier | weigh several weak clues, the glass count among them, to say which unsearched patch probably holds a glass | which unsearched place is likely occupied |
| 6 | [A network trained from scratch](learned/06-a-network-trained-from-scratch.md) | learned | decider | one small network, two heads: which pixels are glass, and which way each glass pixel's own centre lies | finding glasses with no depth, and separating glasses that touch |
| 7 | [Self-supervised from the arm's own movement](learned/07-self-supervised-from-the-arms-own-movement.md) | learned | decider | points on one glass shift together when the arm moves the camera, and that is the label | separating glasses with no labels |

Two of those entries are documents that were written separately and then joined,
because in each pair the second was not a different method but the same method
with one part changed.

**Solution 4** was two ways of ordering the same candidates. Both keep [move the
camera](programmed/03-move-the-camera.md)'s candidate generation and all of its
vetoes, and both replace only the rule that sorts the survivors — one with a
learned estimate of how much doubt a look would remove, the other with a learned
estimate of whether the answer would change. They agree completely about what is
*allowed* and differ only about what is *preferred*, so they are now one
document describing a ladder with two rungs.

**Solution 6** was two heads on one network. The same shape, the same training
recipe and the same source of labels produce a class map when the last layer has
one output channel, and one mask per glass when it has two. Describing them
apart meant writing the same network down twice.

## The decision: what was built

Two pipelines were built, and both are scored on the same 50 held-out scenes
drawn by [`problem-2-sim`](../../../problem-2-sim/README.md). The one this
project takes forward is **the learned pipeline**. [Its
README](../../../problem-2-learned/README.md) says how it works and why, how to
train it, and how to look at what each model is taught and answers.

**The learned pipeline** has three steps.

1. **Find.** TopNet does [solution 6](learned/06-a-network-trained-from-scratch.md): each
   glass pixel votes for the middle of its own glass, and the votes are
   counted. The place and width of each glass then come from the voting
   pixels' depth readings, by arithmetic.
2. **Choose where to look from the side.** 24 places round each glass. Geometry
   vetoes the places out of reach, the places where the camera would stand in
   another glass, and the places with a glass squarely in the way: the
   arithmetic tests of [solution 3](programmed/03-move-the-camera.md), without asking the
   motion planner. A learned Ranker orders what is left. It sits in the ranker
   position of [choosing the next look](learned/04-choosing-the-next-look.md), so
   a wrong order wastes a look and nothing more. A best score under 0.5 hands the glass to problem 3.
3. **Measure.** SideNet reads the height and 16 widths straight off the side
   picture. This is problem 1's job, done here by a model.

**The programmed twin**,
[`problem-2-programmed`](../../../problem-2-programmed/README.md), takes the
same three steps with rules: [solution
2](programmed/02-cluster-on-the-table.md)'s clustering on the table to find, the
same veto with a written rule to order the places, and a silhouette measurement
that is checked and tried from up to three places.

| Step | Learned | Programmed |
|---|---|---|
| Find | 250 of 250; position 0.4 mm median | 250 of 250; 0.2 mm median |
| Choose | first place clean 232 of 245; 5 handed over | 246 of 250; 2 handed over |
| Measure | height 5.4 mm median, 36 mm worst | height 0.8 mm median, 2.3 mm worst |

The learned pipeline finds glasses as well as the rules do and measures them
worse. Its README says why.

**What is not built.** Neither pipeline has these parts of the seven:

- solution 2's second half, the blind-region arithmetic that says where nobody
  could have seen a glass;
- solution 3's covering step, and its check with the motion planner;
- the survey from several stations. Both take one overhead picture from
  750 mm, high enough that the whole glass zone is in frame.

No test scene needed them to find every glass. They are what to add first when
the cell changes, for the reasons below.

## Where what was built can fail

**Nothing says where a glass could have been missed.** The one overhead picture
holds the whole zone, and no test scene lost a glass. But the problem asks for
the places that could not have been seen, and the pipeline has no such list. The
day the zone widens or the glasses get taller, a missing glass will leave no
trace. Solution 2's second half is the fix.

**Glasses that could not be separated are not reported.** The problem asks for
that list too. The votes either split two glasses or they do not, and nothing
compares a found glass's width against what the kind allows.

**SideNet's answer is not checked.** It gets one picture and no retry. When the
Ranker's first choice is spoiled, 13 times in 245 on the test scenes, the
spoiled picture is measured as if it were clean. The programmed twin catches
this with a width check and tries the next place.

**Heights come out about 3% short.** `pipeline.measure` passes the 16 levels on
as the glass's profile, and a profile's height is its top level, which sits at
97% of the height SideNet said.

**200 examples is few.** SideNet pulls unusual glasses towards the average, so
its worst errors are the tallest stemmed glasses read short. The Ranker's first
choice is clean 232 times in 245, against 219 for a random allowed place, so it
has learned little.

**The veto does not ask the motion planner.** A place can pass the veto while
the arm's path to it crosses a glass. The same is true of the programmed twin.

**Everything is learned from a perfect depth camera.** Both pipelines run only
on `problem-2-sim`'s pictures, not in Gazebo, and those show opaque glasses with
a depth reading on every pixel. Real glass gives almost no depth readings, and
all three models are given depth.

**Two glasses that genuinely touch** are [problem
3](../../problem-3/problem.md)'s business. Voting is the method that could
separate them, but no test scene has glasses touching.

## How it would be solved

← [The problem](../problem.md) · [The ones that need more than a
simulator](learned/learned-with-hardware.md) · [Problem 3 — moving them
apart](../../problem-3/problem.md) →
