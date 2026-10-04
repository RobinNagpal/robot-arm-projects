# The test bench — the same question for every answer

## Introduction

This problem is answered six different ways, and six answers are only
comparable if they were asked the same question and marked by the same examiner.
The test bench is that examiner. It draws the arrangements of glasses, renders
the pictures, hands exactly those pictures to whichever solution is being tried,
and then marks what comes back against what it knows it put out. By the end of
this document you will understand what the bench gives a solution, what it keeps
to itself, how a report is matched to a real glass, which numbers decide whether
one method beat another, and why one of those numbers matters far more than it
first appears.

Read this before any of the solution documents, because every one of them
assumes it.

## Why there is a bench at all

Without one, each method would arrive with its own arrangements and its own
idea of a good answer, and nothing could be concluded by putting their results
side by side. The bench exists to remove every difference between the six
except the one being studied.

It does that by holding three things fixed. The **input** is the same pictures
from the same arrangements, in the same order. The **output** is the same record
per glass, produced by the same final step. The **marking** is the same set of
measurements, computed the same way. Everything a solution is free to change
sits between the input and the output, and that is exactly the part we want to
compare.

The comparison that follows from this is sharper than it sounds. Two of the six
solutions use the same model from the same library, starting from the same
downloaded weights, and one of them has had its training continued on this
cell's pictures. That training also cuts the borrowed list of everyday
categories down to a single class, because a model cannot be trained towards
this cell's labels while still being asked which household object it is looking
at — so the two changes cannot be had separately. Because the bench holds
everything else still, nothing varies between those two that the training did
not bring, which makes the gap between them a measurement of what training
bought.

## What the bench draws

**It draws the arrangements, not Gazebo.** The real simulator would produce a
slower picture of the same thing, and a few hundred arrangements are needed, so
the bench renders them directly from the cell's own glass shapes, the cell's own
table layout and the wrist camera's real lens. Nothing about the geometry is
invented for convenience.

**Each arrangement holds four to six glasses of one kind**, and the kind changes
from one arrangement to the next so that all four kinds are met in turn. The
glasses stand far enough apart never to touch.

**There are two families of arrangement.** The ordinary one spaces the glasses
as the cell's spawner would. The crowded one pushes them as close as the cell
allows, which is where the methods separate most, because crowding is what
creates both the merge and the complete hiding.

**Arrangements are split into a training half and a test half**, by the number
used to draw them. Anything a method is fitted on comes from below the dividing
line, and everything it is marked on comes from above it, so no method is ever
tested on an arrangement it learned from.

## What a solution is given

For each arrangement, the camera is parked at several overlapping stations above
the glass zone, looking straight down. The overlap matters: a glass cut off at
the edge of one station's picture sits well inside another's.

From each picture a solution may read three things:

- the **grey picture**, shaded from how far away each surface is;
- the **depth reading** at every pixel;
- the **camera's pose**, which the arm knows from its own joint encoders.

That is the whole input. It is the same for all six, and it is handed over by
the bench rather than fetched by the solution, so no solution can quietly read
anything else.

## What the bench keeps to itself

Every picture also carries an **id image**: at each pixel, which glass that
pixel shows, or nothing. The bench renders it alongside the depth and never
gives it to a solution at run time.

That image is the bench's whole power, and it is used for two different jobs
which are worth keeping apart.

**As the answer key**, it is how marking works. Because the bench knows which
glass owns each pixel, it can decide what a returned mask is really a picture
of.

**As a training label**, it is what a fitted method learns from — but only from
the training half of the arrangements. A method may be *trained* on id images
and is never *run* on them. Any method that read one while answering would not
be answering this problem.

## What must come back

One record per glass, holding its mask pixels, its place on the table and a
rough width of its footprint. Beside those records come the two honest
statements [the problem](problem.md) asks for: which glasses could not be
separated and why, and which parts of the table could not have been seen at
all. Neither is a list of glasses, and the bench counts both rather than
treating a reported doubt as a missing answer.

**The step that turns a mask into a place and a width is the bench's, not the
solution's.** This is the single most important decision in the whole
arrangement, so it is worth being clear about why. Each mask pixel carries a
depth reading, so it becomes a point in the room. The axis is taken from the
points at the top of the glass rather than from all of them, because a rim leans
outwards from the point below the camera, so the middle of the whole cloud sits
off to one side of where the glass really stands while the middle of the rim
sits over it. The width is how far the cloud reaches from that axis, taken as a
high percentile so that one stray point cannot widen it.

Because that step is shared, **a difference in the result belongs to the mask**.
No solution can win by measuring more cleverly, and none can lose by measuring
worse. The only thing any of them contributes is which pixels belong to which
glass, which is what this problem asks.

One consequence is worth stating plainly, because it answers a question that
would otherwise come up in all six documents. **No model in this problem
produces a pose.** Models produce masks. The pose comes from depth and the
camera's own pose, by arithmetic, and a glass standing upright on a flat table
has no orientation left to find.

## How a report is matched to a real glass

Before anything can be counted, the bench has to decide which real glass a
report is talking about. It does this by pixels rather than by position: it
looks at the pixels the report is made of, asks the id image which real glass
owns most of them, and that majority owner is the glass the report refers to.

Matching by pixels rather than by position is deliberate, because it still works
when a method is badly wrong about where the glass stands. A report whose mask
is plainly a picture of glass number three is credited to glass number three,
even if the place it computed is well off.

## What the bench measures

### Did it separate the glasses?

Five counts come straight out of the matching, and between them they describe
every way the finding step can go right or wrong.

| Count | What it means |
|---|---|
| **put out** | how many glasses were really on the table |
| **found** | how many distinct real glasses got a report |
| **missed** | real glasses that got no report at all |
| **merged** | one report whose pixels substantially cover two real glasses |
| **split** | one real glass that collected two reports |
| **false** | a report whose pixels belong to no glass at all |

**Missed is the count to watch hardest.** A split glass announces itself,
because both halves are too small to be a glass. A merged pair looks like one
large glass, which is worse, because everything downstream believes it. A
missed glass leaves no trace at all — no bad number, no failed check, nothing
in the run to read. The only defence is to have worked out in advance where a
glass could have been hiding, which is what [looking again at what was
hidden](hidden-glasses.md) is for.

### How far out was the place?

For each glass that was found, the bench records how far the reported place is
from the true one, and reports the middle value and the worst.

**This number saturates, and knowing that saves a lot of confusion.** The step
that turns a mask into a place is deliberately forgiving, because it takes the
axis from the rim and the width from a percentile precisely so that a ragged
mask edge cannot move the answer. The consequence is that two quite different
masks can produce almost the same place — close enough to the floor of error
described below that the difference between the two masks disappears into it.
When two answers both sit that near the best the shared step can give, this
number can no longer tell them apart, which is why the mask itself has to be
measured as well.

### How good was the mask?

This is the measurement that separates methods when the place cannot, and it is
the reason the bench looks at the mask itself rather than only at what the
arithmetic made of it.

Two numbers per glass: **how much of the real glass the mask covered**, and
**how much of the mask was not that glass**. The first catches an outline that
lost the thin stem of a glass or stopped at the edge of an occluder. The second
catches an outline that leaked onto the table or swallowed a neighbour.

Both are then **broken down by kind of glass**, because the four kinds are not
equally hard and an average over all four hides the interesting part. The two
kinds without a stem are outlined almost exactly by anything that tries; the
stemmed kinds are where methods differ, and the stemmed glass is the hardest of
the four.

### The ceiling: what the best possible answer would be

One more measurement is not about any method. The bench can run its own id
images through the shared arithmetic, as though a method had returned perfect
masks. What comes out is the **floor of error**, or equivalently the ceiling of
achievable accuracy: the best place and width the shared step can produce even
when the mask is exactly right.

That number is what makes the others readable. A method within a hair of the
floor is not a good method so much as a method whose remaining error is not its
fault, and knowing that stops effort being spent on the wrong half of the
pipeline.

It also exposes one trap that is easy to fall into. A mask may claim pixels the
camera never saw the glass at, which happens on purpose when a method predicts
the hidden part of a glass. The depth reading at such a pixel belongs to
whatever stood in front, so feeding it in drags the computed place onto the
object in front. Measured with exact masks, naming those pixels and leaving them
out gives a place several times closer than feeding them in. So a mask that
asserts pixels must say which ones, and the bench excludes their depth readings
rather than guessing a value for them.

## Where to go next

- [The problem](problem.md) — what is asked for, and the three difficulties.
- [Looking again at what was hidden](hidden-glasses.md) — the shared part that
  recovers a glass no picture held.
- [The six solutions](solutions/overview.md) — what each method puts between the
  input and the output.
