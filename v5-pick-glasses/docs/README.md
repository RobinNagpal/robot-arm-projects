# Walkthrough

Six documents, one per stage of a run, in the order the arm does them. Read
[`../problem-statement.md`](../problem-statement.md) first if you have not —
these six explain *how* the task is done, and it explains what the task is and
why it is worth doing, which is the part that makes the rest make sense.

## The arc

The six stages are not a list of features. Each one exists because the stage
before it deliberately stopped short, and following that thread is the fastest
way to understand the design.

The arm begins knowing nothing about the table. **Step 1** finds the glasses
from above and produces a position and a rough width for each — and nothing
else, because from overhead a tall glass and a short one look the same. It can
find them at all because the glasses here are opaque, which is an assumption
the [problem statement](../problem-statement.md) sets out rather than a fact
about glassware, and the one that would have to go first to make this a
kitchen. That
missing shape is exactly what **step 2** goes round to the side to measure,
turning one picture into a width at every height up the glass. That profile is
a description of the shape, which is why **step 3** can name the kind of glass
with arithmetic instead of a trained model, and why naming it is worth doing
at all: the kind selects which rule applies. **Step 4** applies it, turning
"hold the narrowest part below the bowl" into a height and a finger gap for
this glass. **Step 5** answers the one question none of the looking could —
how hard to press — by weighing the glass in the air, because wall thickness
is invisible and weight does not follow from size. And **step 6** turns the
glass over and stands it down, feeling for the rack rather than driving to a
height, because by then two measured numbers have been added together and
both carry error.

Read end to end, the thread is that each step hands on the least it can, and
each step is built so that a thing it cannot know honestly is left for the
step that can measure it.

## What each document contains

Every one of them has the same three parts, in the same order:

1. **How the step works**, with the project's own arithmetic on the project's
   own glasses.
2. **What went wrong**, when that step was first put in front of a simulator,
   and what was done about it. Worth reading before changing anything near the
   simulator, because almost none of these faults announced themselves
   anywhere near where they lived — a missing line in a model file arrived as
   an arm that could not plan a path, and a texture drawn at the wrong angle
   arrived as a glass lowered onto bare table.
3. **How else it could have been done** — the models, the frameworks and the
   classical methods that could have stood in that step's place, what each
   would be good and bad at here, and why the code does what it does instead.
   These comparisons are the quickest way to see what the project trades away,
   and it is usually the same trade: accuracy on a hard real-world case,
   against being able to say why a glass was refused.

## The six

- [**Step 1 — finding the glasses**](step1-finding-the-glasses.md). How a
  picture of distances becomes places in the room, why a glass is simply
  something standing above the table once you assume it is opaque, what keeps
  the rack and the arm's own fingers out of the answer, and why one look from
  above is not enough.
- [**Step 2 — measuring one**](step2-measuring-one.md). One picture from the
  side, and why one is enough. Pixels to millimetres using a distance the arm
  knows for a reason that has nothing to do with the glass.
- [**Step 3 — what kind of glass is it**](step3-what-kind-of-glass.md). Reading
  the kind off the measured profile with three tests, and why this is both
  cheaper and more honest than classifying from above.
- [**Step 4 — where to hold it**](step4-where-to-hold-it.md). Three rules, the
  features they read, the ways an answer gets rejected, and why the opening is
  never a number from a file.
- [**Step 5 — how hard to squeeze**](step5-how-hard-to-squeeze.md). Why the
  weight of a glass cannot be seen, what the estimate is good for, and the
  ten-millimetre lift that settles it.
- [**Step 6 — turning it over and standing it down**](step6-turning-it-over.md).
  Rotating about the grip rather than the wrist, the wrist limit that has to be
  checked before the fingers close, the tilt budget, and feeling for the rack.

## The pictures

Every picture in `../images/` is drawn by [`make_images.py`](make_images.py),
which imports the project's modules and plots what they return. Nothing is
illustrative. If a rule changes, the pictures change with it the next time it
is run, which is the only way a diagram stays true.

## Where to go next

For the reasoning behind these choices, read
[`../implementation-notes.md`](../implementation-notes.md). For which file and
function each stage lives in, read [`../pseudocode.md`](../pseudocode.md). For
what the task is and what is still undecided, read
[`../problem-statement.md`](../problem-statement.md).
