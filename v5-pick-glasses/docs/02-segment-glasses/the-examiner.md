# The examiner — the same question for every answer

## Introduction

The examiner is the program that tests every solution to [the
problem](problem.md). It draws the arrangements of glasses and renders the
pictures. It hands those pictures to a solution. Then it marks what comes back
against what it knows it put out.

It tests each solution twice. One run has the glasses spaced as the cell spaces
them. The other has them crowded closer than the cell allows. So each solution
gets two scorecards.

This page explains what a solution is given and what the examiner hides. It
also shows how a report is matched to a glass, and which numbers count most.
Every solution document assumes it.

## Why there is an examiner at all

Without one, each method would bring its own arrangements and its own idea of a
good answer. Their results could not be compared. The examiner removes every
difference except the method.

It holds three things fixed:

- the **input**: the same pictures of the same arrangements, in the same order;
- the **output**: the same record per glass, made by the same last step;
- the **marking**: the same measurements, computed the same way.

A solution may change only what sits between the input and the output.

This makes sharp comparisons possible. The best one is solutions 3 and 4: the
same model, with and without training on this cell. The [results
page](../../02-segment-glasses/results/README.md#what-the-comparison-says)
reads that gap.

## What the examiner draws

**It draws the arrangements itself, not with Gazebo.** A few hundred
arrangements are needed, and Gazebo would be slow. The examiner renders them
from the cell's own glass shapes, table layout and wrist camera lens. No
geometry is made up for convenience.

**Each arrangement holds four to six glasses of one kind.** The kind changes
from one arrangement to the next, so all four kinds come up in turn. The glasses
never touch.

So **a score is an average over all four kinds**. A run of 20 arrangements holds
roughly a quarter of each kind. The kinds are not equally hard to outline, so
the examiner also reports every measurement by kind.

**There are two families of arrangement.** They differ only in how far apart
the glasses stand.

The **ordinary family** is what the cell's own spawner makes. It keeps 150 mm
between any two centres. That leaves bare table between every pair of glasses.
Each glass makes its own patch of pixels, and nothing is hidden.

The **crowded family** pushes the glasses closer: a third to two thirds of the
ordinary spacing. This is where the methods differ most. Two close glasses run
into one patch of pixels, so one report covers both. A short glass behind a tall
one can vanish from the picture.

**Arrangements are split into a training half and a test half** by the number
used to draw them. A method is fitted only on arrangements below the dividing
line. It is marked only on arrangements above it. So no method is tested on an
arrangement it learned from.

### Every solution is tested twice, once on each family

**A solution is run twice, once on each family, and gets two scorecards.** Each
run uses the same 20 held-out arrangements of its family. Both are marked the
same way. So the only change between the two scorecards is how close the
glasses stood.

The table gives the size of each run and the question it asks.

| run | arrangements | glasses | what it asks |
|---|---|---|---|
| the ordinary run | 20 | 100 | can the method do the job the cell actually sets it? |
| the crowded run | 20 | 101 | where does the method begin to break? |

The gap between a solution's two rows shows how much it relied on the glasses
standing apart.

A fitted solution is trained only once. Its training set mixes both families,
all from below the dividing line. So no method meets crowding for the first time
in the run that scores it.

## What a solution is given

The examiner hands over the input that [the problem](problem.md#what-goes-in)
defines: for each survey picture, the grey picture, the depth at every pixel,
and the camera's pose. The stations overlap, so a glass cut off at the edge of
one picture sits inside another.

The examiner hands this over. The solution does not fetch it. So no solution can
quietly read anything else.

## What the examiner keeps to itself

Every picture also has an **id image**. At each pixel it says which glass that
pixel shows, or none. The examiner renders it with the depth and never gives it
to a solution at run time.

The id image has two jobs.

**As the answer key**, it makes marking possible. The examiner knows which glass
owns each pixel. So it can tell what a returned mask really shows.

**As a training label**, a fitted method learns from it, but only on the
training half. A method may be *trained* on id images. It is never *run* on
them.

## What must come back

One record per glass, as [the problem](problem.md#what-must-come-out) asks:
mask, place and rough width. The examiner adds one more field: **whether the
picture held the whole glass**. A glass at the edge of a frame shows only part
of its footprint, so its width is only part of a width. A solution that refuses
a report on its width needs to know this. The examiner reports the fact. What to
do with it is up to the solution.

The two honest statements come back too: glasses that could not be separated,
and table that could not be seen. The examiner counts both. It does not treat a
stated doubt as a missing answer.

**The solution picks the pixels, and the examiner does the measuring.** Three
things turn a mask into a place and a width: the mask's pixels, the depth at
each pixel, and the camera's pose. The examiner runs this step itself, the same
way for every solution.

The step is short. The pixels become points in the room. The glass's upright
axis comes from the points at its top, not from all of them. The rim leans
outwards in the picture, but its middle still sits over where the glass stands.
The width is how far the points reach from that axis. It uses a high
percentile, so one stray point cannot widen it.

So the final answer depends only on which pixels the solution chose. No solution
can win by measuring more cleverly. **The method that scores best is simply the
one whose masks pin down the exact position and size of the glasses.**

**No model in this problem produces a pose.** Models produce masks. The place
comes afterwards, from depth and the camera's pose. An upright glass on a flat
table has no turn left to find.

## How a report is matched to a real glass

Before counting, the examiner decides which real glass each report is about. It
looks at the report's pixels. It asks the id image which glass owns most of
them. That glass is the match.

Matching by pixels, not by position, is deliberate. It still works when a method
is badly wrong about the place. A mask that clearly shows glass three is
credited to glass three, even if its place is far off.

## What the examiner measures

### Did it separate the glasses?

The matching gives these counts. Together they cover every way the finding step
can go right or wrong.

| Count | What it means |
|---|---|
| **put out** | how many glasses were really on the table |
| **found** | how many distinct real glasses got a report |
| **missed** | real glasses that got no report at all |
| **merged** | one report whose pixels substantially cover two real glasses |
| **split** | one real glass that collected two reports |
| **false** | a report whose pixels belong to no glass at all |

**Missed is the count to watch hardest.** A split glass shows itself, because
both halves are too small to be a glass. A merged pair looks like one large
glass, and everything later believes it. A missed glass leaves no trace at all.
The only defence is to work out where a glass could hide. [Looking again at what
was hidden](hidden-glasses.md) does that.

### How far out was the place?

For each found glass, the examiner records how far the reported place is from
the true one. It reports the middle value and the worst.

**This number saturates.** The step that turns a mask into a place is forgiving
on purpose. It takes the axis from the rim and the width from a percentile, so a
ragged mask edge cannot move the answer. So two quite different masks can give
almost the same place. Near the floor of error below, this number can no longer
tell two methods apart. That is why the mask itself is measured too.

### How good was the mask?

This measurement separates methods when the place cannot.

It gives two numbers per glass: **how much of the real glass the mask covered**,
and **how much of the mask was not that glass**. The first falls when an outline
loses a thin stem or stops at a glass in front. The second rises when an outline
leaks onto the table or swallows a neighbour.

Both are **broken down by kind of glass**. An average over all four kinds would
hide which kinds are hard. The [results
page](../../02-segment-glasses/results/README.md#what-the-numbers-mean) shows
what the breakdown found: a written rule loses the stem, and a fitted model does
not.

The measurement is checked on the floor below, where the masks are the
renderer's own. There both numbers are perfect for all four kinds. A correct
yardstick must say that about a perfect mask.

### The ceiling: what the best possible answer would be

One more measurement is not about any method. The examiner runs its own id
images through the shared step, as if a method had returned perfect masks. The
result is the **floor of error**. It is the best place and width the shared step
can give when the mask is exactly right.

This floor makes the other numbers readable. A method very close to the floor
has little error of its own left. Its remaining error comes from the shared
step.

The floor also exposes one trap. Some methods predict the hidden part of a
glass. Their masks then claim pixels where the camera never saw that glass. The
depth at such a pixel belongs to whatever stood in front. Using it drags the
computed place onto that object. With exact masks, leaving those pixels out
gives a place several times closer than using them. So a mask that claims hidden
pixels must say which ones. The examiner then ignores their depth readings.

## Where to go next

- [The problem](problem.md): what is asked for, and the three difficulties.
- [Looking again at what was hidden](hidden-glasses.md): the shared part that
  finds a glass no picture held.
- [The six solutions](solutions/overview.md): what each method puts between the
  input and the output.
